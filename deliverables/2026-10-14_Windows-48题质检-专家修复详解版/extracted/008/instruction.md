# 清理完整进程树的 Windows 超时助手

请修改 `src/` 里的 WinTask.exe。它接收 marker 路径、worker 延时毫秒数和超时毫秒数。worker 在延时结束后写入 marker。

如果 worker 及时结束，命令返回 0，marker 存在；如果超时先到，命令必须返回 124，并结束由本次调用启动的整个进程树，不能有后代进程在命令返回后继续写 marker。重复调用不能留下 worker 进程或 `.worker.cmd` 临时脚本。

命令行保持为 `WinTask.exe <marker> <workerMs> <timeoutMs>`。输出必须是可解析的 JSON；参数错误返回 2，普通 I/O 或启动失败返回 3。
