# 参考实现（wfmt）

本目录是组织方用于 Golden / Oracle 校验的隐藏参考答案，**不进入任何对外交付包**。

## 参考实现满足了什么契约

`solution/reference/wfmt/` 是 `environment/workspace/wfmt/` 的完整替换版本，可原样通过
`assets/sample.wfmt` 与 `assets/sample_empty.wfmt`（**样本是唯一权威依据**，
`docs/FORMAT.md` 是早期草稿，与真实布局已经不一致）：

| 契约 / 验收条目 | 参考实现的关键点 |
| --- | --- |
| A 样本兼容 | 文件头 `MAGIC = b"WFMT"` + 1 字节版本 + 4 字节小端记录数（`HEADER_SIZE = 9`）；`pack(unpack(sample)) == sample` 逐字节一致；零记录样本同样可 `verify` 并原样回写 |
| B 记录语义 | 每条记录 = `uvarint(tag)` + `uvarint(len(payload))` + `payload`，随后补零对齐到 4 字节（`ALIGN = 4`）；`unpack` 按文件顺序返回 `[(tag, payload), ...]`，空 `payload` 合法 |
| C 校验和 | 尾部 4 字节小端 **CRC-32/ISO-HDLC**（`zlib.crc32`），覆盖「文件头 + 全部记录体（含对齐填充）」；对任意输入成立，不匹配样本时才成立 |
| D 错误分类 | 所有结构/完整性问题抛 `WFormatError`，`kind ∈ {magic, version, truncated, structure, varint, checksum}`；从不用 `ValueError` / `struct.error` / `IndexError` 泄漏；`verify()` 捕获全部异常并返回 `False`（**从不抛异常**） |
| E 流式读取 | `iter_records()` 惰性产出，仅以固定大小 `read(CHUNK_SIZE=4096)` 向文件对象要数据，绝不 `read()` 无参 / `read(-1)` / `readlines()`；用增量 CRC 校验尾部，校验失败抛 `WFormatError(kind="checksum")`；尾部有多余数据抛 `kind="structure"` |
| F 不得回归 | `tests/test_wfmt_basic.py` 冒烟测试继续通过；`pack` / `unpack` / `verify` / `iter_records` / `read_all` / `WFormatError` 等公开 API 名称与签名保持不变 |

## 模块划分

| 模块 | 职责 |
| --- | --- |
| `header.py` | 魔数、版本、记录数；`parse_header` 抛出 `magic` / `version` / `truncated` |
| `varint.py` | LEB128 小端续位无符号变长整数；越界抛 `varint`，数据不足抛 `truncated` |
| `crc.py` | CRC-32/ISO-HDLC 计算与 4 字节小端打包 |
| `codec.py` | 单条记录编解码、`pack` / `unpack` / `verify` 整份读写；填充非零抛 `structure`，记录数与长度不符抛 `structure` |
| `stream.py` | 定长窗口读取器与 `iter_records` / `read_all`；不缓存整份容器 |
| `errors.py` | `WFormatError(kind, message, **details)` |

## 边界与不变式

- 只读：解析/校验过程不修改输入数据。
- 无外部依赖：仅用标准库（`struct` / `zlib`），可在 Windows 容器内直接导入。
- 公共 API 名称与参数名保持不变，未新增导出符号。
- 尾部校验和覆盖范围与解析路径一致，因此篡改**头或任一记录体**都会被 `verify()` 拒绝。

## 使用方式

`solve.ps1` 会把 `reference/wfmt/` 镜像到 `environment/workspace/wfmt/`，用于
Oracle / Golden 控制跑。它可重复执行，且不产生网络请求或临时日志。
