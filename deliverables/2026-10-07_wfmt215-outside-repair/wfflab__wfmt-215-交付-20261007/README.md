# Windows 专项 Coding Bench 交付包 — `wfflab__wfmt-215`

- 交付日期：2026-10-07
- 题包标识：`task_id = wfflab__wfmt-215` ｜ `task_version = 2.0.0`
- 题目方向：`Windows/文件格式与序列化（LEB128 varint + CRC32 容器）/Python/缺陷修复`
- **资格判定：`qualified = true`**（四模型资格门禁全部通过）
- 资格 epoch：`2026-10-07T06:12:40+00:00`
- 汇总工件：`evidence/model_runs_summary_wfp.json`（由 `summarize_model_runs.py` 生成，exit=0）
- 生成时间：`2026-10-07T22:59:00.589047+08:00`

## 一、交付清单（四件套）

| # | 文件 | 说明 | SHA256 |
|---|---|---|---|
| 1 | `wfflab__wfmt-215-v2.0.0.zip` | 题包本体（ZIP 根 = task-id；含 `instruction.md` / `task.toml` / `environment/` / `tests/`，**不含 `solution/`**） | `f428ef8ac749694f40a94bfc4c68a4d48ada67f3759f8b66cc86425ec210b71b` |
| 2 | `evidence/score_summary.png` | 模型得分与门禁判据截图 | `a0c744c86a8b5c8a420f124d511c97c2c461a33317098e87689dae91a39bf5a0` |
| 3 | `evidence/oracle_nop_controls.png` | Oracle / no-change 对照截图 | `d04ec526d4e22bb49e79bcb69cc6693526e6e465151e75a7c024f21510f8134f` |
| 4 | `evidence/model_runs_summary_wfp.json` | 汇总数据（权威读数） | `ba8481262732bd13470a960698833af44e3ffae4816afb59b4671fe520840c5a` |

## 二、门禁结果

| 模型 | 需求轮数 | 有效轮 | scores | sum | 剔除（上游故障） |
|---|---|---|---|---|---|
| QWEN | 3 | 3 | `[0, 0, 0]` | **0** | 0 |
| OPUS | 3 | 3 | `[1, 1, 0]` | **2** | 2 |
| GLM | 1 | 1 | `[1]` | **1** | 0 |
| KIMI | 1 | 1 | `[0]` | **0** | 0 |

**gates**：`controls_passed=True` ｜ `model_counts_complete=True` ｜ `opus_sum_greater_than_qwen=True`（**OPUS 2 > QWEN 0**）｜ `task_version_consistent=True` ｜ `epoch_pinned=True` ｜ `agent_failures_excluded=2` ｜ **`qualified=True`**

- 对照：no-change ×3 全 `VALID` + `verdict=0`；golden ×3 全 `VALID` + `verdict=1`。
- OPUS 本轮由 4router 端点提供（`https://4router.net`），3 轮 `[1, 1, 0]`。
- 剔除项均为 provider / 网关层故障（`error`），按规范**不得计 0**，已排除出计分集合（`e43c` / `c3ca`，ebond 端点 `HTTP 403 INSUFFICIENT_BALANCE`）。

## 三、关键约束

1. 题包 ZIP 内**不含** `solution/`、答案、隐藏测试以外的评测内容或任何凭据。
2. 跑分所用题包即本交付题包本体（`runner/tasks/wfflab__wfmt-215` 为指向题包目录的符号链接）。
3. 资格 epoch 内的运行证据均已固化于 `evidence/`；跨 Epoch 结果不作比较。
4. 交付前对 `tests/rubric.json` 补齐了顶层 `total_weight: 1.0` 声明并同步重绑 `judge.toml` 的 `source_sha256`——**纯元数据/摘要声明**，`aggregate_results.ps1` 只读取 `rubric.items`，不改动任何判据、测试或 verdict，故已完成的跑分继续有效。
