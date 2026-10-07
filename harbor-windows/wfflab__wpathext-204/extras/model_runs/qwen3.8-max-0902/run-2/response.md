## 改动概览（只改了 `wexec/resolve.py` 与 `wexec/runner.py`，未触碰 `tests/`）

### `wexec/resolve.py`
1. **`executable_extensions()` 真正解析 `PATHEXT`**：按 `os.pathsep` 切分、去空白、补前导点、统一小写、按声明顺序去重；只有 `PATHEXT` 缺失/为空/全是空项时才退回 `EXECUTABLE_EXTENSIONS`（兜底语义与签名不变）。
2. **新增 `candidate_names(name)`**，实现与 `SearchPath` 一致的试探顺序：
   - 名字已带 `PATHEXT` 里的扩展名（`direct.CMD`、`tool.exe`）→ 只返回它本身，**绝不叠加**成 `tool.exe.exe`；
   - 名字带的是别的扩展名（`build.py`）→ 先原样试，再按 `PATHEXT` 顺序补全；
   - 名字无扩展名 → 完全按 `PATHEXT` 声明顺序补全（`.exe` 不再特殊）。
3. **`resolve()`** 仍是「PATH 目录顺序 → 目录内按 PATHEXT 顺序」，因此 `hello.CMD`/`hello.BAT` 能被找到，且 PATHEXT 顺序变化会直接改变结果；名字含路径分隔符时按 Windows 语义相对 cwd 解析而不翻 PATH；依旧返回绝对路径、找不到时抛 `CommandNotFound`。
4. **`_on_disk_spelling()`**：命中后用 `os.scandir` 把文件名换成磁盘上真实的大小写，所以 `resolve("hello")` 返回的正是 `...\hello.CMD`（与 README 中 `ninja.EXE` 的示例一致），而不是我们拼出来的小写形式；扫描失败/无权限时安全回退。

### `wexec/runner.py`
1. **批处理脚本经命令解释器启动**：`.cmd`/`.bat`（大小写不敏感）不再直接交给 CreateProcess（那会抛 WinError 193），而是通过 `COMSPEC`（缺失时退回 `resolve("cmd")`，再退回 `cmd.exe`）执行。
2. **命令行拼成 `cmd.exe /S /C "<整条命令>"`**，配合 MSVCRT 引用规则并把 cmd 元字符（`& | < > ( ) ^ "`）包进引号：脚本路径含空格/括号、参数含空格或 `&` 都能原样送达（已实测 `my dir\spaced.CMD` + `x y`）。
3. **退出码如实回传**：脚本 `exit /b N` → `CompletedProcess.returncode == N`；stdout/stderr 仍被采集，额外加 `errors="replace"` 防止不可解码字节导致崩溃。
4. `run` / `run_ok` 的签名、空 argv 的 `ValueError`、`run_ok` 的 `RuntimeError` 语义完全保持不变；非批处理命令仍走原来的 list 形式。

### 验证（临时脚本写在系统 TEMP 下，已删除，仓库内无残留）
- 仓库自带 `tests/` 5 项全部通过；
- 验收 1/2/3/4 全部实测通过：`resolve("hello") == <dir>\hello.CMD`；`PATHEXT=".CMD;.BAT"` vs `".BAT;.CMD"` 结果随之切换；`resolve("direct.CMD")` 直接命中；`run(["hello"])` 返回 `returncode=0`、stdout=`hello-out`，`.BAT` 的 `exit /b 3` 返回 3 且 stderr 被采集；
- 反例守护：目录里只有 `ghost.exe.exe` 时 `resolve("ghost.exe")` 抛 `CommandNotFound`（不再叠加扩展名）；`trap.exe` 命中 `trap.exe` 而非 `trap.exe.exe`；
- 边界：PATHEXT 未设置时退回 `.exe` 且 `resolve("cmd")` 仍可用、COMSPEC 缺失时回退、绝对/相对带路径名字、`run([])`、`resolve("")`。
- 仅用标准库，断网可运行；`git status` 仅显示两个实现文件被修改。