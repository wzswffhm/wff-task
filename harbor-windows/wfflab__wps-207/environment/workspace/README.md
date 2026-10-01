# wjob

把 PowerShell 脚本当作流水线步骤来执行，并如实报告成败。

```python
from wjob import run_script

result = run_script("cmd /c exit 3")
result.exit_code        # -> 3
result.stderr           # -> 错误流内容
```

## 为什么不能只看进程返回码

- PowerShell 的**非终止错误**不会改变进程退出码，脚本报错也可能返回 0
- 原生命令（`.exe`）的退出码只写进 `$LASTEXITCODE`，不会自动成为进程退出码
- 错误信息默认走 stderr，若不合并采集就会丢失

## 组成

| 模块 | 职责 |
|---|---|
| `wjob.psrun` | 启动 PowerShell 并采集结果 |
| `wjob.result` | `PSResult` / `PSJob` |

## 约束

- 只用 Python 标准库
- 目标环境为 Windows（Windows PowerShell 5.1）
- 断网可运行
