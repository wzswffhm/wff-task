# winpipe 工作区

本目录是 `winpipe` 包的开发工作区。

```
winpipe/
  __init__.py    # 对外入口
  errors.py      # WPipeError / PipeBusyError（kind 标记）
  native.py      # kernel32 命名管道 ctypes 薄封装
  server.py      # PipeServer
  client.py      # PipeClient
tests/
  test_wpipe_basic.py   # 可见的冒烟测试
```

运行冒烟测试：

```powershell
$env:PYTHONPATH = (Get-Location)
python -m pytest tests\test_wpipe_basic.py -q
```

`instruction.md` 给出完整的验收契约。冒烟测试只覆盖最基础的往返，
不代表验收标准。
