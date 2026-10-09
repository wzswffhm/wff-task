# 参考实现（wchunk）

`solution/reference/wchunk/` 是 `environment/workspace/wchunk/` 的完整替换版本，
可原样通过 `assets/sample.wchk` 与 `assets/sample_empty.wchk`
（**样本是唯一权威依据**）以及隐藏的语义套件。

`solve.ps1` 会把 `reference/wchunk/` 镜像到 `environment/workspace/wchunk/`，
用于 Oracle 控制：从干净检出可复现正向预检（Oracle 必须 18/18）。

## 关键实现要点（与草稿 FORMAT.md 的差异）

| 章节 | 权威行为（以样本为准） | 草稿写错的地方 |
|---|---|---|
| 文件头 | `MAGIC = b"WCHK"` + 1 字节版本 + **4 字节小端**记录数（`HEADER_SIZE = 12`）+ 3 字节保留 | 记录数写成**大端** |
| 记录 | `tag u16 LE + size u16 LE + payload`，每条记录补齐到 **8 字节**边界 | 写成 **uvarint** 且**无对齐填充** |
| 尾部 | **6 字节** = `CRC-32(header+records, 小端 u32)` + `tag_sum(u16 LE)` | 写成只有 **4 字节**校验和（未记 tag_sum） |
| 校验和 | 标准 CRC-32/ISO-HDLC（`zlib.crc32 & 0xFFFFFFFF`，**含最终异或**），对任意输入成立 | 写成「初值 `0xFFFFFFFF` **不做最终异或**」的变体 |
| 校验顺序 | 长度 → magic → version → 结构解析(含截断) → CRC → tag_sum（顺序决定 `kind` 分类） | 未描述 |
| 错误 | `WChunkError(kind)` ∈ {magic, version, truncated, structure, checksum}；`verify()` 永不抛异常 | 未区分 verify 的静默语义 |
| 流式 | `iter_records()` 惰性产出，仅固定大小 `read(n)` 要数据；尾部校验和在取完全部记录后校验 | 未描述 |

## 文件职责

| 文件 | 职责 |
|---|---|
| `codec.py` | `pack` / `unpack` / `verify` 与校验顺序 |
| `header.py` | 12 字节文件头的构建与解析 |
| `crc.py` | `compute_crc` = `zlib.crc32(data) & 0xFFFFFFFF` |
| `stream.py` | `iter_records` / `read_all`（增量 CRC + 流式读取） |
| `errors.py` | `WChunkError(kind, message)` |

## 冒烟测试

`environment/workspace/tests/test_wchunk_basic.py` 对 Gold 与候选都必须通过
（它不碰 `assets/`）；真正的验收由隐藏语义套件完成。