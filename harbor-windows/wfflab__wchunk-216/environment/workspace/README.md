# wchunk 工作区

```
wchunk/                     # 候选实现（待修复的包）
    __init__.py             # 公开 API 出口
    codec.py                # pack / unpack / verify
    crc.py                  # compute_crc（当前实现为草稿口径的 CRC 变体）
    errors.py               # WChunkError（kind 标记）
    header.py               # 12 字节文件头
    stream.py               # iter_records / read_all（流式读取）
    varint.py               # 可变长整数辅助（草稿声称的记录编码方式）
assets/
    sample.wchk             # 权威样本（外部采集器落盘的真实文件）
    sample_empty.wchk       # 零记录样本
docs/
    FORMAT.md               # 设计草稿（已与实现、样本脱节，勿据此实现）
tests/
    test_wchunk_basic.py    # 可见的冒烟测试（只覆盖最基础往返）
```

## 为什么冒烟测试一直是绿的

`tests/test_wchunk_basic.py` 只验证「自己 `pack()` 的数据能被自己 `unpack()`
读回」，**完全不接触 `assets/`**。因此即使实现与真实样本不兼容，冒烟测试
依然通过 —— 这正是问题被掩盖的原因。

## 判官如何验收

判官另有一套隐藏的语义套件（不随题面下发），逐条核对：

1. `verify(open("assets/sample.wchk","rb").read()) is True`，且
   `pack(unpack(sample)) == sample`（**逐字节**）；
2. 记录区的**字节布局与真实样本一致**（字段宽度、字节序、记录边界）；
3. 尾部校验和是通用 CRC 变体，覆盖**文件头与全部记录**，对任意输入成立；
4. 结构 / 完整性问题抛 `WChunkError` 且 `kind` 分类正确，
   `verify()` 永不抛异常；
5. `iter_records()` 惰性流式读取（只允许固定大小的 `read(n)`）；
6. 公开 API 的名称与签名不回归。

**修复时不要改动公开 API 的签名，也不要改动 `assets/`、`docs/`、`tests/`。**