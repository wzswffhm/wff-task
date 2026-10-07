# wportalloc 工作区

Windows 服务端口池分配器。模块布局：

```
wportalloc/
  errors.py      # WPortAllocError（kind 标记）/ PortInUseError
  probe.py       # is_port_free —— 端口空闲探测
  listener.py    # allocate —— 创建独占监听 socket
  health.py      # check_service —— 服务健康探测（客户端）
tests/
  test_wport_basic.py   # 可见的冒烟测试
```

运行可见测试：

```
python -m pytest tests\test_wport_basic.py
```

题面契约见任务 instruction.md。修复时不要改动公开 API 的签名与
模块布局；判分使用隐藏测试 `tests/test_wport_semantics.py`。
