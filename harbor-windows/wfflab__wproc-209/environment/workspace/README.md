# wproc

在 Windows 上**受控地**运行子进程：收集输出、限制运行时间、结束整棵进程树。

```python
from wproc import run

result = run(["python", "build.py"], timeout=600, cwd="C:/work/app")
if result.timed_out:
    print("构建超时，已终止")
else:
    print(result.returncode, result.text())
```

## 语义

- `run(command, timeout=None, cwd=None, env=None, check=False)` 返回一个 `RunResult`
- 子进程的 **stdout 与 stderr 合并**到 `RunResult.output`（`bytes`）
- `timeout` 是**整条命令**的挂钟预算，单位秒；到点必须终止这次运行
- `check=True` 时非零退出码抛 `CommandFailed`，异常对象上带着完整结果
- `env` 表示**替换**子进程的环境，而不是在父进程环境上追加

## 运行结果

| 属性 | 含义 |
|---|---|
| `returncode` | 子进程的退出码；未能拿到时为 `None` |
| `output` | 合并后的输出字节 |
| `timed_out` | 是否因为超出 `timeout` 而被终止 |
| `ok` | 是否正常结束且退出码为 0 |

## 组成

| 模块 | 职责 |
|---|---|
| `wproc.processes` | 启动子进程、结束子进程 |
| `wproc.runner` | `run()`：预算控制、输出收集、结果封装 |
| `wproc.results` | `RunResult` |
| `wproc.errors` | `CommandFailed` / `CommandTimedOut` |

## 约束

- 只用 Python 标准库（可调用 Windows 自带命令行工具）
- 目标环境为 Windows
- 断网可运行
