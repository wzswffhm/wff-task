# FIN3-WKN-153 · qwen3.8-max-0902 跑分留档说明（2026-10-12）

## 一、读数与复算

| 项 | 值 |
|---|---|
| `reward`（主分） | **0.752747** |
| `criteria_counted` | **34 / 34** |
| `verifier_error` | **0**（判分可信） |
| 复算（本目录 `reward-details.json`） | Σ(正分项 `w·v`) = **137.0**；正分池 `W_pos` = **182.0**；negate 扣减 = **0.0** → 137 / 182 = **0.752747**，与 `reward.json` 一致 |
| 判据漂移检查 | 34 条判据的 `weight` / `description` 与现行 `FIN3-WKN-153/tests/rubrics.toml` **逐条一致**（drift = 0） |
| negate 条目 | N01–N04 四项均为 `value = 1.0`（**未触发违规**），故不扣分 |
| 判分耗时 | **45.8 分钟**（2026-10-12 12:31:28 → 13:17:15 UTC），与 oracle 40 min / gpt 54 min / opus 48 min 同量级 |

> `reward-details.json` 顶层 `reward.score`（0.7816）是 rewardkit 的中间聚合口径（把 negate 项按 `value = 1.0` 计入分母），
> 与 `reward.json` 的主分口径不同；本目录以 `reward.json` 的标准口径（正分池 182 归一）为准。

## 二、本次判分是「verifier-only 重判」，不是完整 trial

- **判分 trial**：`_qc_runs/g5-153-qwen/trials/qwen38max-153-reg1`（`agent = nop`）；
  本目录 `轨迹/regrade-trial.log` 即该次判分 trial 的日志。
- **完整 agent trial**：`_qc_runs/g5-153-qwen/trials/qwen38max-153`（第 ④ 次尝试，2026-10-12 19:00–19:51）
  - agent 段**成功**：6 件交付物齐备（`artifacts/manifest.json` 全 `ok`）、`terminal_reason = completed`、cost ≈ $7.41；
  - 判分段**失败**：`exit_code = judge:scorer_error`，原始报错
    `{"api_error_status":401, ..., "result":"Failed to authenticate. API Error: 401 API-key is blocked."}`
    —— 判官凭据被平台封禁（原 `JUDGE_API_KEY` 直测 `qwen3.7-plus` 与 `qwen3.8-max-0902` 均返回
    `401 InvalidApiKey: API-key is blocked.`）；
  - 因此该 trial 的 `reward.json` 是 **fail-closed 占位**（`criteria_counted = 0` / `verifier_error = 1`），**不是 0 分**，已排除出难度统计。

因此本目录：

- `output/` 的 6 件交付物 = 该次 agent 段的**真实产出**；
- `轨迹/claude-code.txt`、`轨迹/trajectory.json` = 该次 agent 段的**真实轨迹**（与 `output/` 同源，3.65 MB / 2.30 MB）；
- `reward.json` / `reward-details.json` = 复用上述交付物的 verifier-only 重判结果。

### 判分方式（依据 `delivery/06-model-validation.md` §「复用已记录的交付物重判」）

本题 verifier 为 **shared 模式**，`harbor trial regrade` 不适用，故采用该文档给出的等价路径：
`-a nop` + bind mount 把该模型真实交付物挂到容器 `/app/output`，只跑真判分（脚本：`_qc_runs/g5_153_regrade_qwen_v2.sh`）。
判官模型与协议**未变**（仍为 `qwen3.7-plus` / `anthropic` / individual 模式 / `timeout = 7200`），
仅将被平台封禁的 API key 换为直测可用的同平台 key。

> 该执行体前三次尝试的失败均属判官侧：① 网关 socket 断连；②③ 单条判判工具循环停滞逾 30 / 21 分钟；
> ④ 判官 key 被封。均如实登记于 `summary.json` 的 `blocker` 与 `交付文档.md` §3.2.2，未以估计值填充。

## 三、定档结论（三模型齐备）

| 执行体 | reward | 判据数 | verifier_error |
|---|---|---|---|
| oracle（G4 参考解） | **1.000000** | 34 | 0 |
| **qwen3.8-max-0902** | **0.752747** | 34 | 0 |
| gpt-5.6-sol | **0.664835** | 34 | 0 |
| claude-opus-4-8 | **0.609890** | 34 | 0 |

- **三模型均分 = 0.675824 < 0.70 → 难度门 PASS（未破档）**，实际落档 **A1**（0.675824 ∈ [0.60, 0.70)）；
- 本执行体为三模型中**最高分**（0.752747），与 oracle 1.000000 相差 24.7 个百分点，判据具备区分度；
- `task.toml` 的 `difficulty` 已按实测均分由设计申报的 A2 回填为 **A1**。
