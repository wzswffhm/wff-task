修复了 wexec 在 Windows 上的三个核心问题：

1. **PATHEXT 支持**：`executable_extensions()` 现在从环境变量 PATHEXT 读取扩展名列表，而不是硬编码只返回 `.exe`，支持 `.cmd`、`.bat` 等所有声明的可执行扩展名。

2. **扩展名叠加**：`resolve()` 现在检查命令名是否已经带有可执行扩展名，避免了 `tool.exe` 被错误拼接成 `tool.exe.exe` 的问题。

3. **批处理脚本执行**：`run()` 现在识别 `.cmd` 和 `.bat` 文件，通过 `cmd.exe /c` 启动它们而不是直接执行，解决了 WinError 193 问题，并正确传递退出码和输出。

所有修改仅涉及 `wexec/resolve.py` 和 `wexec/runner.py` 两个实现文件，保持了公开 API 签名不变，原有测试全部通过，满足所有验收标准。