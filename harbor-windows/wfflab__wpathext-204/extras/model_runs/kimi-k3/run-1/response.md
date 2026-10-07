修复了 wexec 在 Windows 上按名字查找/执行命令的三个缺陷，仅改动 wexec/ 包内两个文件，公开签名与既有语义保持不变。

## wexec/resolve.py
1. **PATHEXT 解析**：`executable_extensions()` 不再返回硬编码的 `(".exe",)`，而是解析环境变量 `PATHEXT`（按 `os.pathsep` 切分、过滤空项、补前导点），保持其声明顺序；PATHEXT 缺失或为空时才退回 `EXECUTABLE_EXTENSIONS` 兜底值。
2. **不再叠加扩展名**：新增 `_has_extension()`，名字本身带扩展名（如 `direct.CMD`、`tool.exe`）时直接按原名在 PATH 各目录中查找，不会再拼成 `tool.exe.exe`；不带扩展名时才按 PATHEXT 顺序逐个拼接试探（目录优先、扩展名次之，与 Windows shell 行为一致）。Windows 文件系统大小写不敏感，`hello.CMD` 可被 `hello.cmd` 等任意大小写形式命中。

## wexec/runner.py
3. **批处理脚本经命令解释器启动**：解析结果扩展名为 `.bat`/`.cmd`（大小写不敏感）时，改用 `shell=True`（即经 COMSPEC 指定的 cmd.exe）执行，避免 CreateProcess 直接启动批处理抛 WinError 193；脚本路径加引号以支持含空格的目录，参数原样透传，脚本的退出码与 stdout/stderr 如实反映在 `CompletedProcess` 中。非批处理（`.exe` 等）仍走原来的列表式 CreateProcess 路径，行为不变。

## 验证
- 仓库自带 5 个测试全部通过（未改动 tests/）。
- 用临时目录中的脚本（系统 temp，不在仓库内）验证了全部验收标准：`resolve("hello")` 命中 `hello.CMD`；切换 PATHEXT 顺序后 `dual` 分别解析为 `dual.cmd`/`dual.exe`；`resolve("direct.CMD")` 直接命中不叠加；`run(["hello"])` 成功执行 .CMD/.BAT 并正确返回退出码（0/5/42）与标准输出/错误；`run_ok` 成功时返回去尾空白的 stdout、失败时抛 RuntimeError。另验证了 PATHEXT 缺失/为空兜底、无前导点规范化、空名字/空 argv 异常、含空格路径、参数转发、`resolve("cmd")` 等边界情况。