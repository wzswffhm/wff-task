# 10 · Windows 题运维坑与复用套路

> 来源：2026-10-07 `wfflab__wfmt-215` / `wfflab__wreparse-217` 实证。本文件是**操作层**细节，
> `MEMORY.md §6` 只保留索引。与 §7.11（`-Execute` 绝对路径）、§7.12–§7.14（传输层/流式）配套读。

## 1 Windows 容器题适配坑（6 条）

| # | 症状 | 处置 |
|---|---|---|
| ① | Dockerfile `ENV PATH="C:\\x;…;${PATH}"` 在 Windows 容器**不展开** | 用**正斜杠**并**显式列全** `C:/Windows/System32` + `C:/Windows/System32/WindowsPowerShell/v1.0` |
| ② | `RUN … python -c "a, b"` 双引号被 PowerShell 参数解析**拆散**（python 收到裸 `import`） | 改**单引号 + 绝对路径**：`& 'C:\Python312\python.exe' -c '…'` |
| ③ | **embed 发行版的 `python312._pth` 隔离 `sys.path`、完全忽略 `PYTHONPATH`** | 路径写进 `._pth`；或**通用解**：在 scratch 根放 `conftest.py` 做 `sys.path.insert(0, root)` |
| ④ | `WORKDIR C:\x` 反斜杠被 Docker 吃掉 | 写 `C:/x` |
| ⑤ | 容器内 git 报 dubious ownership | `git config --global --add safe.directory`（`C:/testbed` 属主 SYSTEM） |
| ⑥ | `runner.py` 清理 `work/` 触发 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`（>50 项）→ 分片**静默中断** | 必须带 `--keep-work`（`run_matrix.ps1` 已内置） |

## 2 计划任务编排（复用命令 + 3 坑）

```powershell
Register-ScheduledTask -TaskName oh-<tag> `
  -Action   (New-ScheduledTaskAction -Execute <PS绝对路径> `
              -Argument '-File …\matrix-task.ps1 -Tag <tag> -Models <M> -Runs <N> -TaskId <id>' `
              -WorkingDirectory <runner>) `
  -Trigger  (New-ScheduledTaskTrigger -Once -At (Get-Date).AddDays(120)) `
  -Settings (New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
              -MultipleInstances IgnoreNew -StartWhenAvailable) -Force
Start-ScheduledTask -TaskName oh-<tag>
```

- `matrix-task.ps1` 内 `& $psExe -File run_matrix.ps1 …`；`run_matrix.ps1` 已带 `-KeepWork`；GLM/KIMI 固定 `Runs=1`。
- 多分片 = 每片 **`-Tag` 唯一 + `-Runs 1`**（并行单例优于串行 `Runs=3`）。

| # | 坑 |
|---|---|
| ① | **`-Execute` 必须绝对路径**：裸 `powershell.exe` → `LastTaskResult=2147942402`(0x80070002)，任务显 `Ready` 却**从不执行、零日志** |
| ② | 注册后**立即** `Start-ScheduledTask` 的任务会被自身 `-Once -At` 触发器**二次触发** |
| ③ | **`-Once -At (Get-Date).AddDays(1)` 会在次日同一时刻自动开火**（`oh-r9-qwen` 实证，差点顶掉 last-3 窗口）→ **用毕必须 `Stop-ScheduledTask` + `Disable-ScheduledTask`，trigger 推 +120 天**；收口全量核对 `Get-ScheduledTask oh-* \| Triggers.StartBoundary` |

## 3 飞书写回（Windows 作业表）编码坑

- wiki `O1qjw1qFRijaf8kal5scROn9nmc` → base `EsJebL8JJaf7g4sIbItcnMFgnvg` / table `tblRDxcGkblflMBA`。
- 脚本 `generate-win/scripts/upload_feishu.ps1`（`-ConfirmWrite` 必需，默认状态 `待提交`）。
- 字段：方向 `fldiuFJbFr` ｜ 提示词 `fldOv2xWDV`=instruction.md ｜ 状态 `fldd6UxkAs` ｜
  oracle-nop 截图 `fldZI4BCU2` ｜ 分数截图 `fldg4yePGJ` ｜ 四件套 ZIP `fldnki9xts`。不写 auto_number。
- 标注员 `flda4emMz7` 是 user 字段、默认 `current_user`（**勿硬编码 openId**）。
- **★ 必须先设 `[Console]::OutputEncoding` / `$OutputEncoding` = UTF8**：zh-CN 主机默认 GBK 解码
  lark-cli 的 UTF-8 stdout → 中文 JSON 乱码 → read-back 抛 `Invalid lark-cli JSON`；
  此时**记录已创建、附件未上传** → 补救 = 带 `-RecordId <rec…>` 续跑（脚本自动跳过已存在附件）。
  已固化进脚本（备份 `upload_feishu.ps1.bak-preencoding`）。

## 4 runner.py 参数化与并行

- 原把 217 特征**硬编码 8 处**（`WReparse` 白名单 / 契约文档 / PowerShell 人设 / tool schema / mirror+fingerprint / 首轮 prompt）+
  `read_file` 仅 UTF-8 → **换任何题都结构性 0 分**（215 实证：agent 自述"write_file 被限制在 WReparse 之下"）。
- 现由 `resolve_task_profile(task_dir)` 从 `task.toml` 推导：`[policy].mutable_paths[0]`→可写模块；
  `read_only_paths` 中以 `/docs` 结尾→参考文档；`[metadata].tags`/模块后缀→语言人设；`assets/**`→二进制样本。
  `DEFAULT_PROFILE` = 217 原值（**217 零影响**）；`read_file` 对二进制返 hex dump。
- **并行跑分**：`run_id` 加 `secrets.token_hex(2)` 后缀。否则同模型多分片同秒启动 → `run_id` 相同 →
  共用 `work/` 与容器名互踩（三片齐死 `WinError 3`）。

## 5 两个环境专用坑

- **PowerShell 工具是 PS 7.6.4**：`New-ScheduledTaskSettingsSet` 须用 `-AllowStartIfOnBatteries`
  （5.1 名 `-AllowStartOnBatteries` 在 PS7 绑定失败且 **non-terminating** → `-Settings` 静默变 `$null`
  → 注册报 "argument is null or empty"）。
- **写日志勿用会把输出文件本身匹配进去的通配符**（`-Filter "*wfo2*"` 读自己 → 78 MB 膨胀）。
- **本机跑题**：管理员 + PS，绝对路径 `$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe`；
  **PowerShell 工具不回 stdout → 一律 `*> file` 再 Read**。

## 6 交付落盘与飞书写回（表锁）坑

**单题交付产物（5 件，与 217 同构）**：`README.md` + `evidence/oracle_nop_controls.png`
（oracle/nop截图）+ `evidence/score_summary.png`（分数截图）+ `evidence/model_runs_summary_*.json`
（权威读数）+ 四件套 ZIP（作业压缩包，ZIP 根 = task-id，含 `task.toml`/`instruction.md`/`environment/`/
`tests/`，**不含 `solution/`**）。手工交付入口建议再附 `instruction.md`（供粘贴「提示词」字段）与字段对照表。

- **★ 飞书写回 `permission_denied`（code `800020812`）= 表被锁**：不是 token 失效。
  `base +base-get` 看 `is_advanced: true`；**读得到、建行/传附件被拒**。对应群公告「18:00 后可能锁表
  （仅可阅读）」。处置：**先 `record-list` 确认未产生脏记录**（避免重复），再改走"桌面交付 + 手动上传指引"，
  等解锁或换有写权限账号补写。**不要用"新建"试探可写性**（会产生脏行）。
- **★ 桌面/个人目录受 `safe-delete` 保护**：`rm` / `Remove-Item` 优先走回收站；回收失败即
  `SAFE_DELETE_FAIL_CLOSED` **拒绝回退删除**；被其它进程占用的文件**无法覆盖**（`PermissionError: [Errno 13]`）。
  → 交付产物一律**新建 / 解压**到桌面，**不做覆盖删除**；需要"重建"时就换个新文件名。
- **交付物哈希自检**：落盘后对 4 件核心产物 `sha256sum`，逐一比对 `README.md` 里声明的 SHA256。
