# FIN3-WKN-153 · claude-opus-4-8 跑分留档说明（2026-10-12）

## 一、读数与复算

| 项 | 值 |
|---|---|
| `reward`（主分） | **0.609890** |
| `criteria_counted` | **34 / 34** |
| `verifier_error` | **0**（判分可信） |
| 复算（本目录 `reward-details.json`） | Σ(正分项 `w·v`) = **111.0**；正分池 `W_pos` = **182.0**；negate 扣减 = **0.0** → 111 / 182 = **0.609890**，与 `reward.json` 一致 |
| 判据漂移检查 | 34 条判据的 `weight` / `description` 与现行 `FIN3-WKN-153/tests/rubrics.toml` **逐条一致**（drift = 0） |
| negate 条目 | N01–N04 四项均为 `value = 1.0`（**未触发违规**），故不扣分 |
| 判分耗时 | 48.3 分钟（2026-10-12 14:47:18 → 15:35:37 UTC），与 oracle 40 min / gpt 54 min / qwen 46 min 同量级 |

> `reward-details.json` 顶层 `reward.score`（0.6553）是 rewardkit 的中间聚合口径（把 negate 项按 `value = 1.0` 计入分母），
> 与 `reward.json` 的主分口径不同；本目录以 `reward.json` 的标准口径（正分池 182 归一）为准。

## 二、判分是「verifier-only 重判」，不是首次完整 trial

- **判分 trial**：`_qc_runs/g5-153-opus/trials/opus48-153-reg1`（`agent = nop`）；本目录 `轨迹/regrade-trial.log` 即该次判分 trial 的日志。
- **完整 agent trial**：`_qc_runs/g5-153-opus/trials/opus48-153`（21:38 启动）
  - agent 段**成功**：约 15 分钟完成，6 件交付物齐备，全程**无 403 / 无鉴权报错**；
  - 判分段**推进到 28/34 条后停滞**：第 29 条判官出现 A11 型空转 —— 它已给出该条结构化评分，却被反复提示
    "上次输出未使用工具调用"，于是反复执行 `Bash: echo "Complete"`，会话文件仍以 ~16 KB/25 s 增长而
    `StructuredOutput` 停在 13（进程 `claude -p` 已 16:58、pcpu 6.3%，判定不可自愈）；
  - 22:46 终止（`harbor EXIT=143`），该 trial 的 `reward.json` 为 **fail-closed 占位**
    （`criteria_counted = 0` / `verifier_error = 1`），**不是 0 分**，已排除出难度统计。

因此本目录：

- `output/` 的 6 件交付物 = 该次 agent 段的**真实产出**；
- `轨迹/claude-code.txt`、`轨迹/trajectory.json` = 该次 agent 段的**真实轨迹**（与 `output/` 同源，1.16 MB / 892 KB）；
- `reward.json` / `reward-details.json` = 复用上述交付物的 verifier-only 重判结果。

### 判分方式（依据 `delivery/06-model-validation.md` §「复用已记录的交付物重判」）

本题 verifier 为 **shared 模式**，`harbor trial regrade` 不适用，故采用等价路径：
`-a nop` + bind mount 把该模型真实交付物挂到容器 `/app/output`，只跑真判分（脚本：`_qc_runs/g5_153_regrade_opus_v2.sh`）。
判官模型与协议**未变**（仍是 `qwen3.7-plus` / `anthropic` / individual / `timeout = 7200`）。
重判时判官行为正常：会话数 1→34 稳定推进，未再出现空转。

## 三、定档结论（三模型齐备）

| 执行体 | reward | 判据数 | verifier_error |
|---|---|---|---|
| oracle（G4 参考解） | **1.000000** | 34 | 0 |
| qwen3.8-max-0902 | **0.752747** | 34 | 0 |
| gpt-5.6-sol | **0.664835** | 34 | 0 |
| **claude-opus-4-8** | **0.609890** | 34 | 0 |

- **三模型均分 = 0.675824 < 0.70 → 难度门 PASS（未破档）**；且至少一个模型有得分、无 `verifier_error=1` 的有效性问题；
- 落档区间：**0.675824 ∈ [0.60, 0.70) → A1**（题目设计申报为 A2，按规范以**实测均分**归级，
  故 `task.toml` 的 `difficulty` / `keywords` / `tags` 已由 A2 回填为 **A1**）；
- 与 oracle 的 1.000000 拉开 39.0 个百分点（opus 口径），判据对该执行体具备区分度。
