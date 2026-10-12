## 根因

对照 `assets/` 下的样本字节逆向出真实布局，发现实现有四处与样本不符（`docs/FORMAT.md` 草稿的描述正是过时的那几条）：

1. **段对齐边界是 8 字节，不是 4**（`segment.py` 的 `ALIGNMENT`）。这同时解释了「容器长度对不上」和「段边界错位」。
2. **索引条目是 8 字节的 `(offset, length)` 对，不是 4 字节的纯 offset**（`index.py`）。
3. **CRC 多了一次取反**：原 `crc32_update` 把 `zlib.crc32` 的结果再 `^ 0xFFFFFFFF`，所以算不出任何标准 CRC-32。去掉取反后 `compute_crc(b"123456789") == 0xCBF43926`（标准校验值），且满足分块累积律。
4. **校验和覆盖范围漏了段内填充**：第二个 trailer 值是「文件头 + 整个段区（含填充）」的 CRC-32，原实现按 `header + 各段(头+数据)` 拼接、跳过了填充。

## 改动

- `crc.py`：改用标准 CRC-32（CRC-32/ISO-HDLC），`crc32_update` 支持流式累积。
- `segment.py`：`ALIGNMENT` 改为 8；新增 `decode_segment_header` 供流式读取用。
- `index.py`：条目改为 8 字节 `(offset, length)`；`parse_index` 返回二元组列表。
- `header.py`：魔数优先判定（短且魔数错时报 `magic` 而非 `truncated`）；头部不足报 `truncated`。
- `codec.py`：按真实布局 pack/unpack；校验和覆盖 `data[:index_offset]`；错误分类按「长度不足 → `truncated`、自相矛盾/多余尾字节 → `structure`、CRC 不符 → `checksum`」排序；额外校验尾部索引与顺序推进的段位置一致；`verify` 捕获所有异常。
- `stream.py`：重写为真正惰性的流式解析——只用 `read(n)`（`n` 为正整数，容忍短读），逐段 yield，索引逐条读取，取完最后一段后再校验索引与尾部校验和。

## 验证

- `verify(sample)` / `verify(sample_empty)` 均为 `True`；`pack(unpack(...))` 对两个样本逐字节一致。
- `tests/test_wlogseg_basic.py` 6 项全绿（未改动任何测试文件）。
- 错误分类实测：magic / version / truncated（多种截断长度）/ structure（段数 ±1、多余尾字节）/ checksum（内容篡改）均正确，`verify` 对 `None`、`b""`、`str` 都返回 `False` 而不抛异常。
- 流式：用只允许 `read(n>0)` 的严格文件对象验证首段产出后仅消费 32/392 字节；篡改内容时抛 `kind="checksum"`。
- 其他：非法 `seg_id`（负数/越界/非 int/bool）与非 bytes payload 均抛 `WSegError`；200 段 420KB 容器往返一致；长度公式与 `16 + Σ align8(8+len) + 8*n + 8` 吻合。
- 已清理 `__pycache__`，工作区只剩 6 个实现文件的改动。
