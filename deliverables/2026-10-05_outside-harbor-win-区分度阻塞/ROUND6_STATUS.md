# ROUND6_STATUS — `wfflab__wreparse-217` 第 6 轮模型矩阵状态简报

> 检查时间：**2026-10-05 22:47 (+08)**　检查人：自动化任务
> 工作区：`deliverables/2026-10-04_outside-harbor-win/runner`
> 题包：`harbor-windows/wfflab__wreparse-217`（本轮**未修改任何题包文件**）
> 第 6 轮 tag：`q6` / `o6` / `a6`，起跑 19:17:39

## 0. 结论（先行）

**第 6 轮矩阵【未跑完】。** 三个完成标记中只有 `o6` 已生成，`q6` 与 `a6` 仍在运行：

| 标记 | 状态 | 时间 |
| --- | --- | --- |
| `logs/matrix-o6.done` | ✅ 已生成 | 19:44:41 |
| `logs/matrix-q6.done` | ❌ 缺失 | — |
| `logs/matrix-a6.done` | ❌ 缺失 | — |

两个未完成分片**均在正常运行、非卡死**，但 `a6` 的 GLM 严重退化（受第 5 轮遗留分片并发抢占）。
按任务约定，**未执行** `summarize_model_runs.py`、**未打包**、**未截图**、**未写飞书**。

---

## 1. 分片明细

### 1.1 o6 — OPUS ×3（已完成）

| run_id | verdict | status | 结束时间 |
| --- | --- | --- | --- |
| `20261005T191739-candidate-opus-5-01` | 1 | VALID | 19:20:15 |
| `20261005T192015-candidate-opus-5-02` | 0 | VALID | 19:28:41 |
| `20261005T192841-candidate-opus-5-03` | 1 | VALID | 19:44:40 |

**OPUS 本轮 `model_score_sum = 2`**（3 轮，每轮上限 1.0）。分片 19:44:41 结束，elapsed 1,622s。

### 1.2 q6 — QWEN ×3（进行中）

| run_id | verdict | status | 备注 |
| --- | --- | --- | --- |
| `20261005T191739-candidate-qwen3.8-max-0902-01` | **INVALID** | INVALID | verifier exit=1，20:03:33 |
| `20261005T200333-candidate-qwen3.8-max-0902-02` | **1** | VALID | 21:51:24 |
| `20261005T215125-candidate-qwen3.8-max-0902-03` | — | 运行中 | 21:51:25 启动，容器 Up 55min |

- **QWEN 已确认有效轮次：1 轮 = 1 分**，第 3 轮在飞，第 1 轮不可判分。
- `qwen…-01` 之所以 INVALID，**不是引擎故障**（引擎 29.7.2 全程在线），而是候选模型把模块改坏、
  导致 verifier 无法产出 `result.json`。`stderr.log` 原文：
  `INVALID: importing the candidate module failed: … Cannot convert value "-1610612733" to type "System.UInt32"`。
  → 属候选自身失败导致的不可判分；按 Windows 二值判分规则记 INVALID，**不伪装 0 分**。

### 1.3 a6 — GLM ×1 + KIMI ×1（进行中）

| 模型 | run_id | 状态 | 备注 |
| --- | --- | --- | --- |
| GLM | `20261005T191739-candidate-glm-5.3-01` | 运行中 | 19:17 启动，已 3h28m，turn 17 / 80 |
| KIMI | — | 尚未启动 | 分片内串行：须等 GLM 先结束 |

`a6` 分片日志只写到 GLM 的启动行（PowerShell 重定向缓冲，实际进展看 `agent.log`）。

---

## 2. 容器与进程/任务状态（检查时刻实测）

**`docker ps -a`：**

| 容器 | 状态 |
| --- | --- |
| `oh-20261005t215125-candidate-qwen3-8-max-0902-03` | Up 55 minutes |
| `oh-20261005t191739-candidate-glm-5-3-01` | Up 3 hours |

**计划任务（`Get-ScheduledTask`）：**

| 任务 | 状态 |
| --- | --- |
| `oh-docker-keeper` | **Running**（引擎探针 `windows/29.7.2`，托管正常） |
| `oh-r6-qwen` | Running |
| `oh-r6-aux`（=a6） | Running |
| `oh-r6-opus` | Ready（已完成） |

**在跑进程：** `matrix-task.ps1 -Tag q6`、`matrix-task.ps1 -Tag a6`、`run_matrix.ps1 -Tag a6`、
`run_matrix.ps1 -Tag q6`、`run.ps1 -Models QWEN`、`run.ps1 -Models GLM`、
`runner.py --models QWEN`、`runner.py --models GLM`。

---

## 3. 判定：仍在运行，非卡死

| 判据 | q6 run3 | a6 GLM |
| --- | --- | --- |
| 容器 | Up 55min | Up 3h |
| `agent.log` mtime | 22:45:13（距检查 ~2min） | 22:45:39（距检查 ~2min） |
| 进程存活 | ✅ | ✅ |
| 结论 | **运行中** | **运行中（但严重退化）** |

两个 run 的 `agent.log` 均在检查前 2 分钟内被写入，说明模型调用仍在往返，**并非挂起**。
GLM 日志中出现 `!! model call attempt 1 failed: TimeoutError: The read operation timed out`，属上游调用超时重试，拖慢但未中断。

---

## 4. 根因：第 5 轮 `a5` 分片与第 6 轮 `a6` 并发抢占同一上游 key

这是本轮 `a6` 严重退化的**根本原因**：

- 第 5 轮的 `a5` 分片（tag a5，`-Models GLM,KIMI -Runs 1`）在 **16:39:41 启动后一直未结束**，
  直到 **21:38:48** 才写出 `matrix-a5.done`：
  - GLM `20261005T163942-…glm-5.3-01` → **verdict=0, VALID**，耗时 **17,529s（4.87h）**
  - KIMI `20261005T213151-…kimi-k3-01` → **verdict=1, VALID**，耗时 418s
- 即 `a5.GLM`（16:39→21:31）与 `a6.GLM`（19:17→…）在 **19:17–21:31** 期间**并发运行**。
- `run_matrix.ps1` 注释明确：*"the auxiliary models share one upstream key and parallel runs on a shared key starve each other."*
  → `a6.GLM` 被 `a5.GLM` 抢占上游配额，速度被拖垮，至今 3.5h 仅推进到 turn 17/80。

**校正既有记录**：此前"第 5 轮（q5/o5/a5）已全部作废"的说法需修正——
- `q5`（17:41:45）与 `o5`（16:46:51）**确实全 INVALID**，原因是 Docker Desktop 引擎掉线
  （`failed to connect to the docker API at npipe://…dockerDesktopWindowsEngine`）。
- 但 **`a5` 分片并未作废**：它跨过引擎恢复一直跑到 21:38，产出了 **GLM=0 / KIMI=1 两条 VALID 结果**。
- 第 5 轮作废的准确理由是：**q5 / o5 全 INVALID，缺少可配对的 QWEN/OPUS 有效轮次**，而非全分片失败。

> 影响：该并发不仅拖慢 `a6`，也在 19:17–21:31 期间与 `q6`/`o6` 争抢 CPU 与上游配额，可能压低第 6 轮整体速度。

---

## 5. 归属澄清：21:31 那份 KIMI 结果不属于第 6 轮

`runs/…/20261005T213151-candidate-kimi-k3-01`（KIMI，verdict=1，16/16 PASS，8/8 rubric）
**属于第 5 轮的 `a5` 分片**（见 §4），**不是**第 6 轮 `a6` 的产出。
第 6 轮的 KIMI 尚未开始，将在 `a6.GLM` 结束后串行启动。

---

## 6. 本轮未执行项（按任务约定）

| 项 | 状态 | 原因 |
| --- | --- | --- |
| `summarize_model_runs.py` 汇总 | ⛔ 未执行 | 需三标记齐全 |
| 证据截图 `make_evidence_images.py` | ⛔ 未执行 | SKILL 第 7 阶段，门禁未到 |
| `package_harbor.ps1` 打四件套 ZIP | ⛔ 未执行 | SKILL 第 8 阶段，门禁未到 |
| 飞书写回 | ⛔ 未执行 | 留待用户确认 |
| 修改题包文件 | ⛔ 未执行 | 无任何写入 |

---

## 7. 下一步建议

1. **让 `q6`/`a6` 自行跑完，稍后重查**。`q6.run3` 已 55min（历史单轮 46–108min，接近完成）；
   `a6.GLM` 在 `a5` 结束后应提速，但按历史耗时（4.9h）仍需数小时。建议**下次检查设在 ≥1h 后**，
   或将其设为周期性检查。
2. **不要在 `a5` 运行期间启动任何新分片**：同一 key 的并发会让 aux 模型互相饿死（本轮实证）。
   后续轮次应在启动前确认无遗留 `run_matrix.ps1` / `runner.py` 进程。
3. **`q6.run1` INVALID 的处置**：系候选把模块改坏（`UInt32` 转换异常）导致不可判分，属真实失败，
   按规则保留 INVALID、不补跑成 0 分；QWEN 以有效 2–3 轮计分。
4. **全部完成后的收口**：运行
   `python summarize_model_runs.py --workspace-root …/runner --task-id wfflab__wreparse-217 --control-runs 3`，
   读取 `opus_sum_greater_than_qwen`：
   - 若 `true` → 执行 SKILL 第 7、8 阶段（证据截图 + 打四件套 ZIP 并从全新解压校验），飞书写回留用户确认。
   - 若 `false` → 不打包、不写飞书，转入难度增强。
5. **难度增强方向预判**（详见同目录 `BLOCKER.md`）：本题预期难点仍是
   ——① QWEN 天花板效应（历史 4/4 满分）；② 当前唯一可用的 Opus 5 端点（`api.ebondai.com`）逐检查错误率
   约为 QWEN 的 16 倍。**优先项仍是取得健康的 Opus 5 端点凭据**，其次再考虑提高题目难度（完整返修周期配额）。

---

*本简报只读取日志与容器状态，未对 `harbor-windows/wfflab__wreparse-217` 做任何写入。*
