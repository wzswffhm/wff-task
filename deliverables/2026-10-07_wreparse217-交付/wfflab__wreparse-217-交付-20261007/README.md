# Windows 专项 Coding Bench 交付包 — `wfflab__wreparse-217`

- 交付日期：2026-10-07
- 题包标识：`task_id = wfflab__wreparse-217` ｜ `task_version = 1.0.0`
- **资格判定：`qualified = true`**（四模型资格门禁全部通过）
- 资格 epoch：`2026-10-06T00:59:28+00:00`
- 汇总工件：`evidence/model_runs_summary_r12.json`（由 `summarize_model_runs.py` 生成，exit=0）
- 生成时间：`2026-10-07T13:50:08.530470+08:00`

## 一、交付清单（四件套）

| # | 文件 | 说明 | SHA256 |
|---|---|---|---|
| 1 | `wfflab__wreparse-217-v1.0.0.zip` | 题包本体（ZIP 根 = task-id；含 `instruction.md` / `task.toml` / `environment/` / `tests/`，**不含 `solution/`**） | `8785dec8ce03e600f7d94a8be385779ef8c3d30fd8ba9cae09f6498c2f457ff9` |
| 2 | `evidence/score_summary.png` | 模型得分与门禁判据截图 | `fe00a04e708425b205135ab57f0e02428089ff6e1666a4c7fcf411dd9353222a` |
| 3 | `evidence/oracle_nop_controls.png` | Oracle / no-change 对照截图 | `bdc5e8253d5891d8ec6f8325e7060fda7af3bda599741227058dfbcc4aea3341` |
| 4 | `evidence/model_runs_summary_r12.json` | 汇总数据（权威读数） | `d8d3760d6ab8dde759cd5b5146ddf2d5d2db164d846bb55240e4fd1a5a2ceed8` |

## 二、门禁结果

| 模型 | 需求轮数 | 有效轮 | scores | sum | 剔除（上游故障） |
|---|---|---|---|---|---|
| QWEN | 3 | 5 | `[0, 1, 1]` | **2** | 1 |
| OPUS | 3 | 12 | `[1, 1, 1]` | **3** | 0 |
| GLM | 1 | 1 | `[1]` | **1** | 2 |
| KIMI | 1 | 1 | `[1]` | **1** | 0 |

**gates**：`controls_passed=True` ｜ `model_counts_complete=True` ｜ `opus_sum_greater_than_qwen=True`（**OPUS 3 > QWEN 2**）｜ `task_version_consistent=True` ｜ `epoch_pinned=True` ｜ `agent_failures_excluded=3` ｜ **`qualified=True`**

- 对照：no-change ×3 全 `VALID` + `verdict=0`；golden ×3 全 `VALID` + `verdict=1`。
- 剔除项均为 provider/网关层故障（`error` / `no_tool_call`），按规范**不得计 0**，已排除出计分集合。

## 三、关键约束

1. 题包 ZIP 内**不含** `solution/`、答案、隐藏测试或任何凭据。
2. 跑分所用题包即本交付题包本体（`runner/tasks/wfflab__wreparse-217` 为指向题包目录的符号链接）。
3. 资格 epoch 内的运行证据均已固化于 `evidence/`；跨 Epoch 结果不作比较。
4. 飞书写回未执行（待确认）。
