修复 wproc 在 Windows 上的三类失控问题，只改动 wproc/ 包内两个模块，并新增了一个测试文件（既有测试未动）。

## 根因
1. `terminate_process` 只 `proc.kill()` 直接子进程，后代（cmd /c 拉起的程序等）继续运行。
2. 超时路径把 `communicate` 已读到的数据和管道里残余数据全部丢弃，返回 `output=b""`。
3. `proc.communicate(timeout=...)` 会等管道 EOF，而 EOF 要等所有继承管道写端的后代退出——直接子进程已退出也会被拖到预算耗尽，误判为超时。

## 修改

### wproc/processes.py
- Windows 上为每次运行创建专用 Job Object（`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`），用 `CREATE_BREAKAWAY_FROM_JOB` 创建子进程（父 Job 禁止 breakaway 时退回普通创建，Win8+ 支持 Job 嵌套）并 `AssignProcessToJobObject` 纳入；句柄挂在 `proc._wproc_job` 上。ctypes 原型全部显式声明，避免 64 位句柄截断。
- `terminate_process`：优先 `TerminateJobObject` 终止**整棵进程树**（只含本次运行的进程，不波及无关进程），再 `wait` + 关闭句柄；无 Job 时退化为原 `kill()` 逻辑。
- 新增 `release_process`：正常结束时先解除 `KILL_ON_JOB_CLOSE` 再关句柄，让仍在运行的后台后代继续存活、不被误杀，也不泄漏句柄。

### wproc/runner.py
- 不再用 `communicate(timeout=...)`。新增 `_OutputReader` 守护线程持续把合并输出从管道排进内存（管道缓冲区不会塞满，数百 KiB 输出不丢）。
- 主线程只 `proc.wait(timeout)` 等**直接子进程**：正常退出 → `release_process` + 给读取线程 1 秒排空窗口（无后代时 EOF 瞬时到达、立即返回；有后代持管道时最多 1 秒带快照返回，绝不拖到预算耗尽），`timed_out=False`、真实退出码；超时 → `terminate_process` 杀整棵树（所有写端关闭、EOF 必达）→ 完整收集截止前已写出的输出，`timed_out=True`。
- `check=True` 语义不变：非零抛 `CommandFailed`、超时抛 `CommandTimedOut`，异常携带完整结果。公开签名与 `RunResult` 语义全部保持。

## 验证（沙箱即 Windows）
- 既有 10 个测试全部通过，无回归。
- 新增 `tests/test_wproc_windows_tree.py` 8 个测试全部通过：超时杀整棵树（python→cmd /c→孙进程，返回后观察 4 秒无活动）、不误伤无关进程、超时保留已写出的小/大（384 KiB）输出、子进程退出但孙进程持管道时立即返回（timed_out=False、真实退出码 0/7、输出完整）、check 两种异常携带完整结果。
- 额外验证：正常返回后后台孙进程仍存活（release 不误杀）、timeout=None 正常、连续 30 次运行稳定。