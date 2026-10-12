## 根因

`docs/FORMAT.md` 的草稿描述与真实布局有三处关键偏差，实现照着草稿写，于是只能自产自消：

1. **索引条目是 8 字节**（`offset` + 段整体长度），草稿说 4 字节且只存偏移 —— 这同时导致了「容器长度对不上」和「段边界错位」。
2. **段对齐到 8 字节**，草稿说 4 字节。
3. **校验和是标准 CRC-32**，原实现额外做了一次 `^ 0xFFFFFFFF`（zlib 内部已经做过），得到的值不属于任何标准变体；且 data CRC 的覆盖范围要**包含对齐填充**，原实现把填充排除在外。

布局是从 `assets/sample.wlsg` 的字节逆推的：段偏移/长度 `(16,16) (32,8) (40,24) (64,264) (328,16)` 相加正好等于 header 里的 `index_offset=344`，且两个尾部 CRC 分别等于 `zlib.crc32(索引区)` 与 `zlib.crc32(data[:344])`。

## 改动

- `crc.py` — 去掉多余的异或，改用标准 CRC-32；`crc32_update` 保持可增量累积（`crc32_update(b2, crc32_update(b1)) == compute_crc(b1+b2)`），供流式校验使用。
- `index.py` — `INDEX_ENTRY_SIZE` 4→8，条目改为 `(offset, length)` 对。
- `segment.py` — `ALIGNMENT` 4→8；截断类错误改报 `truncated`。
- `header.py` — 数据不足报 `truncated`，但在字节已足以判定时优先报 `magic` / `version`（这样 `b"WL"` 这类极短输入也能分对类别）。
- `codec.py` — data CRC 改为覆盖「文件头 + 整个段区（含填充）」；新增不变式校验：段区必须正好终止于 `index_offset`、索引条目必须与实走段区一致、容器尾部不得有多余字节。`pack` 的输入校验收敛到 `WSegError("structure")`。
- `stream.py` — 原先直接 `handle.read()` 整体读入再委托 `unpack`，现重写为真正惰性：只用固定大小 `read(n)`（`n>0`，大 payload 按 64 KiB 分块），边读边增量算 CRC，取完最后一段后再校验尾部索引与两个校验和。

错误分类顺序上，段区遍历在校验和之前，因此「声明长度自相矛盾」报 `structure`，而「内容被篡改但结构自洽」报 `checksum`。

## 验证

- `verify(sample)` / `verify(sample_empty)` 均为 `True`，`pack(unpack(·))` 对两个样本逐字节一致。
- `compute_crc(b"123456789") == 0xCBF43926`（CRC-32 标准检验向量）。
- 错误分类矩阵全部正确：坏魔数→`magic`，坏版本→`version`，截断/`b""`/`b"WL"`→`truncated`，篡改 payload 或 trailer→`checksum`，段数或索引偏移矛盾、尾部多余字节→`structure`；`verify` 全程不抛异常。流式路径分类与之一致。
- 流式惰性：读出第一段时只消耗了 392 字节中的 32 字节；用包装过的文件对象断言 `read()` / `read(-1)` / `readlines()` 从未被调用。
- 300 组随机段集合的 `pack`/`unpack`/`read_all`/回写往返全部通过，且长度符合 `16 + Σ align8(8+len) + 8·n + 8`。
- `tests/test_wlogseg_basic.py` 6 项全绿，公开 API 签名未变；已清理 `__pycache__`，未新增或改动测试文件。