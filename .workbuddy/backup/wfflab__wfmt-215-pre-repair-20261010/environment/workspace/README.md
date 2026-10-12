# wfmt 工作区

采集器的落盘容器格式实现。模块布局：

```
wfmt/
  errors.py     # WFormatError（kind 标记）
  varint.py     # uvarint（LEB128）编解码
  crc.py        # 尾部校验和
  header.py     # 文件头
  codec.py      # 记录编解码 + 整份容器 pack/unpack/verify
  stream.py     # 流式读取 iter_records / read_all
tests/
  test_wfmt_basic.py    # 可见的冒烟测试（只覆盖最基础往返）
docs/
  FORMAT.md             # 早期格式草稿（见下方警告）
assets/
  sample.wfmt           # 权威样本（外部采集器落盘的真实文件）
  sample_empty.wfmt     # 零记录样本
```

## ⚠️ 关于 docs/FORMAT.md

`docs/FORMAT.md` 是格式设计**早期**的草稿，之后实现与样本都改动过若干次，
**它现在与真实字节布局不一致**，不要按它实现。

判断格式的唯一依据是 `assets/` 下的样本：正确的实现必须能做到

1. `verify(open("assets/sample.wfmt","rb").read()) is True`；
2. `pack(unpack(sample)) == sample`（逐字节一致）。

换句话说：**样本就是规范**。

## 运行可见测试

```
python -m pytest tests\test_wfmt_basic.py
```

可见冒烟测试只验证「自己写的数据自己能读回来」，**它全绿不代表格式正确**。

题面契约见任务 instruction.md；判分使用隐藏测试
`tests/test_wfmt_semantics.py`。修复时不要改动公开 API 的签名。
