# wchunk 工作区

采集器的落盘容器格式实现。模块布局：

```
wchunk/
    __init__.py             # 公开 API 出口
    codec.py                # pack / unpack / verify
    crc.py                  # compute_crc（尾部校验和）
    errors.py               # WChunkError（kind 标记）
    header.py               # 文件头
    stream.py               # iter_records / read_all（流式读取）
    varint.py               # 可变长整数辅助
assets/
    sample.wchk             # 权威样本（外部采集器落盘的真实文件）
    sample_empty.wchk       # 零记录样本
docs/
    FORMAT.md               # 设计草稿（已与实现、样本脱节，勿据此实现）
tests/
    test_wchunk_basic.py    # 可见的冒烟测试（只覆盖最基础往返）
```

## ⚠️ 关于 docs/FORMAT.md

`docs/FORMAT.md` 是格式设计**早期**的草稿，之后实现与样本都改动过若干次，
**它现在与真实字节布局不一致**，不要按它实现。

判断格式的唯一依据是 `assets/` 下的样本：正确的实现必须能做到

1. `verify(open("assets/sample.wchk","rb").read()) is True`；
2. `pack(unpack(sample)) == sample`（逐字节一致）。

换句话说：**样本就是规范**。

## 为什么冒烟测试一直是绿的

`tests/test_wchunk_basic.py` 只验证「自己 `pack()` 的数据能被自己 `unpack()`
读回」，**完全不接触 `assets/`**。因此即使实现与真实样本不兼容，冒烟测试
依然通过 —— 这正是问题被掩盖的原因。

## 运行可见测试

```
python -m pytest tests\test_wchunk_basic.py
```

可见冒烟测试只验证「自己写的数据自己能读回来」，**它全绿不代表格式正确**。

题面契约见任务 instruction.md；判分使用隐藏的语义套件（不随题面下发）。
修复时不要改动公开 API 的签名，也不要改动 `assets/`、`docs/`、`tests/`。