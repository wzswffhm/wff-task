import pathlib

DAILY = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\.workbuddy\memory\2026-10-07.md")
AUTO = pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\.workbuddy\memory\automations"
    r"\fed023f6-1b9c-489c-854d-c3515c9cb0b9\memory.md"
)

daily_text = """
### D. Outside Harbor runner 参数化修复 + 215 重跑（16:20–16:40，用户「再跑一个题包」「qwen的模型用不了了吗」）

**先澄清**：QWEN **模型没坏** —— 实测阿里云 MaaS 端点（`…maas.aliyuncs.com/apps/anthropic`）HTTP 200、
1.5s 返回 PONG；217 的 `[0,1,1]=2` 依然有效。215 拿 0 是 runner 缺陷，不是模型。

**根因**：`runner/runner.py` 把 217 的题目特征**硬编码 8 处** —— 模块名 `WReparse`（mirror_workspace /
workspace_fingerprint / WRITABLE_SUBPATH / is_writable / 两个 tool schema / SYSTEM_PROMPT / 首轮 prompt）、
契约文档 `docs/REPARSE-CONTRACT.md`、PowerShell 人设。agent 的 `write_file` 白名单因此只放行
`…\\WReparse`，215 要改的 `wfmt/` 一个字节都动不了 → 任何候选模型必然结构性 0 分。
另有隐藏缺陷：`read_file` 只按 UTF-8 解码，而 215 题面明确「`docs/FORMAT.md` 是过时草稿，
`assets/*.wfmt` 二进制样本才是唯一权威」—— 旧 runner 连样本都读不了。

**修复**：新增 `resolve_task_profile(task_dir)` 从 `task.toml` 推导（`[policy].mutable_paths[0]`→可写模块；
`read_only_paths` 中以 `/docs` 结尾项→参考文档；`[metadata].tags`/模块后缀→语言人设；`assets/**`→样本目录）；
`DEFAULT_PROFILE` 的默认值即 217 原设定 → **217 行为零变化**。`read_file` 增加二进制 hex dump
（16 字节/行，上限 64 KB）；`mirror_workspace`/`workspace_fingerprint`/写白名单全部跟随 profile。

**附带修并发坑（并行跑分必须）**：`run_id` = `{秒级时间戳}-{mode}-{label}-{序号}`。同模型的两个分片
同秒启动 → run_id 完全相同 → 共用同一 `work/` 目录与容器名 → `copy_tree` 互踩，**三个分片全秒退**
（`WinError 3: 系统找不到指定的路径 … case\\environment\\workspace`）。修复：追加
`secrets.token_hex(2)` 随机后缀。`summarize_model_runs.py` 用 `run_root.glob("*/*/result.json")` 定位、
按 `result.json` 内 `model_alias` 匹配模型，`run_id` 仅作文本记录 → 改格式零影响。

**验证**（`_verify_runner_param.py`，无需 Docker）：
| 项 | 217 | 215 |
|---|---|---|
| 模块 / 语言 | WReparse / powershell | wfmt / python |
| 参考文档 / 样本 | REPARSE-CONTRACT.md / — | FORMAT.md / assets |
| 写白名单 | 仅模块内 ALLOW，docs/instruction deny | 仅 wfmt 内 ALLOW，docs/assets/instruction deny |
端到端：view 中 `wfmt/` 就位 ✓；指纹前后变化 ✓；改动正确回写 case ✓；`sample.wfmt` 309 B 逐字节保真 ✓；
hex dump 首行 `57 46 4d 54` = `WFMT` ✓。

**★ PowerShell 工具是 PS 7.6.4（不是 5.1）**：`New-ScheduledTaskSettingsSet -AllowStartOnBatteries`
在 PS7 中**不存在**（那是 5.1 的名字），参数绑定失败且为 **non-terminating** → `$settings` 静默变 `$null`
→ `Register-ScheduledTask -Settings` 报 "argument is null or empty"。正确名 **`-AllowStartIfOnBatteries`**。

**处置**：禁用全部遗留 `oh-r*` 计划任务（防 elapsing one-shot 补跑）；删除旧废轮（无 result.json）；
起 3 个并行分片 `oh-wfq1/2/3`（各 `-Models QWEN -Runs 1 -TaskId wfflab__wfmt-215`，触发器推到 +120 天，
**未加** `-StartWhenAvailable`）。16:37:43 起跑，容器 `oh-…-f61d` / `-17c7` / `-2d61` 均 Up。

**产物**：`WFMT_RUNNER_PARAM.md`（修复报告）、`_verify_runner_param.py`、`scripts_backup/runner.py.pre_param`
（修复前 sha256 `85968ca0c6baab03`）；runner.py 现 sha256 `4698662eec3349f2`（42,079 B）。
"""

auto_text = """
## 2026-10-07 16:40 — 用户「再跑一个题包」+「qwen的模型用不了了吗」→ 修 runner 后重跑 215

**澄清用户疑问**：QWEN **模型可用** —— 实测端点 HTTP 200 / 1.5 s / PONG；217 的 `[0,1,1]=2` 仍有效。
215 那轮 0 分是 **runner 硬编码 217 路径**（`WReparse` 写白名单 + 只读 UTF-8 读不了二进制样本）所致，
详见 `deliverables/2026-10-07_wfmt215-outside-repair/WFMT_RUNNER_PARAM.md`。

**已完成**：runner 参数化（从 `task.toml` 推导模块/文档/语言/样本目录 + 二进制 hex dump +
`run_id` 随机后缀防并行撞车）；217 零影响（dry-run 对照等价）；215 解析正确；端到端链路验证通过。

**当前状态**：3 个并行分片 `oh-wfq1/2/3` 于 16:37:43 起跑（QWEN×1 each，`--keep-work`），
容器 `oh-…-f61d` / `-17c7` / `-2d61` Up。全部遗留 `oh-r*` 计划任务已 Disabled。

**下次（HOURLY）要点**：
1. 查 `runner/logs/matrix-wfq1.done`、`matrix-wfq2.done`、`matrix-wfq3.done`（**三个都要齐**）。
   未齐 → 只在 `ROUND_WFMT_STATUS.md` 追加一行进度（docker ps + agent.log 尾部），**绝不启动新分片**。
2. 齐了 → `summarize_model_runs.py --workspace-root <runner> --task-id wfflab__wfmt-215
   --after 2026-10-07T06:12:40+00:00 --control-runs 3`（**必须带 --after**）→ `logs/_wfqsummary.json`。
   `models.QWEN.score_sum` ≤2 → 再起 OPUS×3（4router 端点）期望 3>2；=3 → 题太易，需调 rubrics/题面后重跑。
3. ⚠️ 用毕务必 `Disable-ScheduledTask oh-wfq1/oh-wfq2/oh-wfq3`（本次触发器虽已推到 2027-02-04，仍应显式禁用）。
4. **不写飞书**（待用户确认）；⛔ 不调难度/turn 作区分杠杆。
"""

for path, text in ((DAILY, daily_text), (AUTO, auto_text)):
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)
    print(f"appended {len(text)} chars -> {path}")
