# wscan 工作区

Windows 磁盘扫描与硬链接去重工具。模块布局：

```
wscan/
  errors.py      # WScanError（kind 标记）
  scan.py        # ScanResult / scan_tree —— 目录树扫描统计
  dupes.py       # dedupe —— 内容去重 + 硬链接替换
tests/
  test_wscan_basic.py   # 可见的冒烟测试
```

运行可见测试：

```
python -m pytest tests\test_wscan_basic.py
```

题面契约见任务 instruction.md。修复时不要改动公开 API 的签名与
模块布局；判分使用隐藏测试 `tests/test_wscan_semantics.py`。
