# 参考实现（wpeimg）

`oracle/reference/wpeimg/` 是 `environment/workspace/wpeimg/` 的完整替换版本，
可原样通过 `assets/amd64-module.bin` 与 `assets/i386-module.bin`
（**样本是唯一权威依据**）以及隐藏的语义套件。

`solve.ps1` 会把 `reference/wpeimg/` 镜像到 `environment/workspace/wpeimg/`，
用于 Oracle 控制：从干净检出可复现正向预检（Oracle 必须 27/27）。

## 关键实现要点（与 `docs/FORMAT.md` 草稿的差异）

| 章节 | 权威行为（以样本与 Windows 语义为准） | 初始实现错在哪 |
|---|---|---|
| DOS 头 | 前 `0x40` 字节以 `MZ` 开头；读不全先报 `truncated` | 只查长度，未查 `MZ` 之外的情况（此处初始实现是对的） |
| NT 头 | `e_lfanew`（`0x3C`，u32 LE）处为 `PE\0\0`，其后 20 字节文件头；读不全先报 `truncated` | 不检查长度，越界抛 `struct.error` |
| 可选头 | 幻数 `0x10B`（PE32）/ `0x20B`（PE32+）；`SizeOfOptionalHeader` 决定节区表位置 | 不检查幻数；节区表偏移写死 224 |
| ImageBase | PE32 是 `+28` 处的 **u32**；PE32+ 是 `+24` 处的 **u64** | 一律按 u64 读，PE32 样本报出天文数字 |
| is_pe32_plus | 由幻数决定 | 恒为 `True` |
| 节区表 | 起始 = 可选头偏移 + `SizeOfOptionalHeader`；每条 40 字节；读不全报 `truncated` | 固定 224 偏移、无长度检查 |
| 校验和 | Windows `imagehlp!MapFileAndCheckSumW` 的算法（见下） | 用 `zlib.crc32`，且不清零 CheckSum 字段 |
| RVA 映射 | `rva < size_of_headers` 直接映射；否则按节区 `virtual_address`/`virtual_size` 定位，`delta >= raw_size` 返回 `None` | 把入参当 VA（减 ImageBase）；不处理头部区间；不查 `raw_size` |
| 结构自检 | 8 条自洽性检查，全部报 `structure` | 完全没有这一层 |
| 判定顺序 | `dos → signature → optional → truncated → structure → checksum` | 先算校验和，结构错误被 CRC 遮住 |
| 流式 | 惰性读取，只发固定大小 `read(n)` | 先 `fileobj.read()` 整读再解析 |

## 校验和算法（与 Windows 完全一致）

按 32 位小端无符号字累加，逐字做一次进位折叠：

```
checksum = 0
把 CheckSum 字段那 4 个字节当作 0
for 每个完整的 4 字节小端字 w:
    checksum = checksum + w
    checksum = (checksum & 0xFFFFFFFF) + (checksum >> 32)
尾部余下 1/2/3 字节按小端拼成一个字（高位补 0），同样参与上面两步
checksum = (checksum & 0xFFFF) + (checksum >> 16)   # 第一次 16 位折叠
checksum = (checksum & 0xFFFF) + (checksum >> 16)   # 第二次 16 位折叠
checksum = (checksum + 文件长度) & 0xFFFFFFFF
```

`ChecksumAccumulator` 是该算法对「已清零字段的字节流」的增量形式：
`update(chunk)` 只在凑满 4 字节时消费，剩余字节留到下一次；`value(total_length)`
把余数拼成尾字后做同样的两次折叠并加上 `total_length`。把字段清零是调用方
（`compute_checksum`）的责任。

离线取得的权威值（`imagehlp!MapFileAndCheckSumW`，status 全为 0）：

| 文件 | +0 | +1 | +2 | +3 | +17 |
|---|---|---|---|---|---|
| `amd64-module.bin` | 74415 | 74417 | 74930 | 74934 | 74687 |
| `i386-module.bin` | 9700 | 9702 | 10215 | 10219 | 9972 |

追加字节依次为 `\x01`、`\x01\x02`、`\x01\x02\x03`、`\xff`×17。
隐藏套件把这张表硬编码为常量，因此套件在容器内不需要任何 Windows 组件。

## 分类判据（参考实现遵循的顺序）

1. **dos**：数据够 `0x40` 字节，但开头不是 `MZ`。
2. **signature**：数据够到 `e_lfanew + 24`，但那里不是 `PE\0\0`。
3. **optional**：幻数既不是 `0x10B` 也不是 `0x20B`，或 `SizeOfOptionalHeader`
   装不下该布局的固定部分（PE32 96 字节 / PE32+ 112 字节）。
4. **truncated**：读 DOS 头、NT 头、可选头或节区表时数据不足。
   **数据不足永远优先**于同层的种类判定。
5. **structure**：头部齐备但自相矛盾——节区文件区间越过文件末尾、虚拟区间
   重叠、文件区间重叠、`virtual_address` 未按 `SectionAlignment` 对齐、
   `raw_pointer` 未按 `FileAlignment` 对齐、`SizeOfHeaders` 未按
   `FileAlignment` 对齐、`SizeOfHeaders` 小于节区表末尾、`SizeOfImage` 小于
   按 `SectionAlignment` 上取整后的节区覆盖范围。
6. **checksum**：结构自洽，但记录的 `CheckSum` 非 0 且与重算结果不符。

映像尾部多出的字节（Authenticode 签名等）**是合法的**，不参与任何判定。

## 文件职责

| 文件 | 职责 |
|---|---|
| `errors.py` | `WImgError(kind, message)` 与六个 kind 常量 |
| `headers.py` | DOS 头、NT 头、两种可选头布局的解析 |
| `layout.py` | 节区表定位与解码、`inspect` 的布局模型、`rva_to_offset` |
| `checksum.py` | `ChecksumAccumulator`、`checksum_field_offset`、`compute_checksum` |
| `probe.py` | 结构自检 `_check_structure`、`inspect` 的判定顺序、`verify` |
| `stream.py` | 惰性 `iter_sections` |
| `__init__.py` | 公开面 `__all__`（14 项）与 `__version__` |

## 冒烟测试

`environment/workspace/tests/test_wpeimg_basic.py` 对 Gold 与候选都必须通过
（它不碰 `assets/`）；真正的验收由隐藏语义套件完成。
