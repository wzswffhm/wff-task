修复 `wjob/psrun.py`：PowerShell 步骤失败被误判为成功、错误流被丢弃的问题。

## 根因
1. `run_script`/`run_file` 直接返回 `proc.returncode`。PowerShell 进程退出码既不携带原生命令的 `$LASTEXITCODE`（`cmd /c exit 3` → 1/0 而非 3），也不反映非终止错误（`Write-Error`、访问不存在路径后脚本继续 → 0）。
2. `PSResult(... stderr="")` 硬编码为空，错误流被整段丢弃。
3. `run_file` 用 `-File`，存在同样的退出码问题。

## 改动（仅 `wjob/psrun.py`）
- 新增 `wrap_script()`：给调用方脚本套一层薄外壳。
  - 前缀：`try { [Console]::OutputEncoding = UTF8 } catch { }` 固定输出编码（无控制台宿主下不炸），紧接 `$Error.Clear()`，只统计本次脚本的错误且外壳自身不污染计数。
  - 脚本体放进 `& { ... }`：`$LASTEXITCODE`/`$Error` 是全局状态照常可见，但错误定位只指向脚本自己那一行，避免把整段外壳文本灌进 stderr。
  - 后缀：`$LASTEXITCODE` 非零优先采用；否则 `$Error.Count > 0` → `SCRIPT_ERROR_EXIT_CODE`(1)；都无则 0。脚本自身的 `exit N` 仍然优先（后缀不会执行）。
- `_invoke()` 把 `proc.stderr` 如实写入 `PSResult.stderr`，两路输出统一 UTF-8 + `errors="replace"` 解码（不受宿主机代码页影响，也不会抛解码异常）。
- 经 `env` 注入 `NO_COLOR=1`（`setdefault`，不覆盖用户设置），让 PowerShell 7 错误日志无 ANSI 转义。
- `run_file()` 改为解析绝对路径 + `quote_path()` 安全转义单引号，走同一套外壳，`.ps1` 步骤获得一致的退出码语义。

## 验证（Windows PowerShell 5.1 与 pwsh 7 双引擎实测）
- `cmd /c exit 3`（含后续输出）→ 3；`cmd /c "echo publish-failed 1>&2 & exit 2"` → 2 且 stderr 含 `publish-failed`
- `Write-Error` / `Get-Item C:\nope`（单独或后接语句）→ 1，错误信息出现在 stderr
- `throw`、`1/0`、`$ErrorActionPreference='Stop'` 失败 → 非零 + stderr
- 脚本与 `.ps1` 内的 `exit 5`/`exit 7` → 5/7
- 成功脚本 → 0，stdout 完整（管道、函数、here-string、Unicode UTF-8、Write-Host/Warning、Test-Path）
- 原生命令写 stderr 但退出 0 → 仍为 0（无误报）
- `run_file` 路径含空格/单引号、相对路径、文件不存在均正确
- `timeout` 仍抛 `TimeoutExpired`；`PSJob.run`、`repr`、`environment_info` 行为不变
- 仓库自带 5 个测试在两个引擎下全部通过

公开签名与既有语义未变，仅用标准库，断网可运行；未新增/修改/删除 tests/ 下任何文件，仓库无遗留调试文件或缓存（git status 仅 `M wjob/psrun.py`）。