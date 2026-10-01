# wexec

构建流水线里用来查找并执行外部命令的小工具。

```python
from wexec import resolve, run_ok

resolve("ninja")                  # -> 'C:\\tools\\ninja.EXE'
print(run_ok(["ninja", "--version"]))
```

## 组成

| 模块 | 职责 |
|---|---|
| `wexec.resolve` | 按 PATH 与 `PATHEXT` 把命令名解析成磁盘路径 |
| `wexec.runner` | 执行解析结果并返回标准结果对象 |

## 约束

- 只用 Python 标准库
- 目标环境为 Windows
- 断网可运行
