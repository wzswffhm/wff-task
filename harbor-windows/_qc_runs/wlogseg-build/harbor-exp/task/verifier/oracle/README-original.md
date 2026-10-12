# 参考实现（wlogseg）

`oracle/reference/wlogseg/` 是 `environment/workspace/wlogseg/` 的完整替换版本，
可原样通过 `assets/sample.wlsg` 与 `assets/sample_empty.wlsg`
（**样本是唯一权威依据**）以及隐藏的语义套件。

`solve.ps1` 会把 `reference/wlogseg/` 镜像到 `environment/workspace/wlogseg/`，
用于 Oracle 控制：从干净检出可复现正向预检（Oracle 必须 25/25）。

## 关键实现要点（与草稿 FORMAT.md 的差异）

| 章节 | 权威行为（以样本为准） | 草稿写错的地方 |
|---|---|---|
| 文件头 | `MAGIC = b"WLSG"` + 1 字节版本 + 1 字节标志 + **2 字节小端**段数 + **4 字节小端**索引偏移 + 4 字节保留（`HEADER_SIZE = 16`） | 未说明标志位与索引偏移的含义 |
| 段 | `seg_id u16 LE + flags u8 + reserved u8 + body_len u32 LE + payload`，段整体（头 + 数据 + 填充）补齐到 **8 字节**边界 | 写成补齐到 **4 字节** |
| 尾部索引 | 每段 **8 字节** = `offset u32 LE + length u32 LE`，`length` 含该段的填充 | 写成每段只有 **4 字节偏移**、没有长度字段 |
| 尾部 | **8 字节** = `index_crc u32 LE` + `data_crc u32 LE` | 未说明这两个校验和各自覆盖哪一段 |
| 校验和 | 标准 CRC-32/ISO-HDLC（`zlib.crc32 & 0xFFFFFFFF`），对任意输入成立 | 写成「再做一次按位取反」的私有变体 |
| 校验和的覆盖 | `data_crc` 覆盖文件头与**整个段区**（含段头、数据与对齐填充）；`index_crc` 覆盖索引区 | 只笼统写成「段区校验和」 |
| 校验顺序 | 长度/魔数/版本 → 截断（数据不足）→ 结构矛盾 → checksum；顺序决定 `kind` 分类 | 未描述 |
| 错误 | `WSegError(kind)` ∈ {magic, version, truncated, structure, checksum}；`verify()` 永不抛异常 | 未区分 verify 的静默语义 |
| 流式 | `iter_segments()` 惰性产出，仅固定大小 `read(n)` 要数据；索引与两个校验和在最后一段之后校验 | 未描述 |

## 分类判据（参考实现遵循的顺序）

1. **magic / version**：文件头字段本身不受支持。
2. **truncated**：按已声明的结构算，需要的字节还没读到就已经结束——包括整个
   索引区缺失、索引区只读到一半、尾部校验和缺失、以及某个段头声明的数据长度
   远超文件剩余字节。**数据不足永远优先**于任何矛盾判定。
3. **structure**：字节齐备但自相矛盾——索引偏移落在文件头内、段越过索引区、
   索引条目与顺序推导出的段布局不符、段数与索引区大小不符、尾部校验和之后
   还有多余字节。
4. **checksum**：结构与声明一致，但尾部校验和与重算结果不符。

## 文件职责

| 文件 | 职责 |
|---|---|
| `codec.py` | `pack` / `unpack` / `verify` 与校验顺序 |
| `header.py` | 16 字节文件头的构建与解析 |
| `segment.py` | 段头布局、8 字节对齐与段编码 |
| `index.py` | 尾部 8 字节索引条目的构建与解析 |
| `crc.py` | `compute_crc` / `crc32_update` = `zlib.crc32(data, value) & 0xFFFFFFFF` |
| `stream.py` | `iter_segments` / `read_all`（增量 CRC + 流式读取） |
| `errors.py` | `WSegError(kind, message)` |

## 冒烟测试

`environment/workspace/tests/test_wlogseg_basic.py` 对 Gold 与候选都必须通过
（它不碰 `assets/`）；真正的验收由隐藏语义套件完成。
