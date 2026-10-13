# 多模型验证报告

生成时间：2026-10-08

适用范围：本目录当前实际交付的 2 个题包。

## 1. 区分度准入汇总

| task_id | Qwen score_sum | Opus score_sum | 满足条件 | 结论 |
|---|---|---|---|---|
| wfflab__wfmt-215 | 0 | 2 | 是 | PASS — Opus 严格高于 Qwen |
| wfflab__wreparse-217 | 2 | 3 | 是 | PASS — Opus 严格高于 Qwen |

## 2. 逐模型运行状态

| task_id | 模型 | 要求 | VALID | INVALID | PENDING | 状态 |
|---|---|---|---|---|---|---|
| wfflab__wfmt-215 | Qwen3.8-Max-0902 | 3 | 3 | 0 | 0 | READY |
| wfflab__wfmt-215 | Opus 5 | 3 | 3 | 0 | 0 | READY |
| wfflab__wfmt-215 | GLM-5.3 | 1 | 1 | 0 | 0 | READY |
| wfflab__wfmt-215 | Kimi K3 | 1 | 1 | 0 | 0 | READY |
| wfflab__wreparse-217 | Qwen3.8-Max-0902 | 3 | 5 | 0 | 0 | READY |
| wfflab__wreparse-217 | Opus 5 | 3 | 12 | 0 | 0 | READY |
| wfflab__wreparse-217 | GLM-5.3 | 1 | 1 | 0 | 0 | READY |
| wfflab__wreparse-217 | Kimi K3 | 1 | 1 | 0 | 0 | READY |

## 3. 准入规则

```
条件 1: Opus5.model_score_sum > Qwen.model_score_sum
条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen.testcase_pass_sum
```

> 只统计 VALID 运行；agent 自身失败（HTTP 4xx/5xx、超时、no_tool_call）的轮次已排除，
> 排除明细见各题 `jobs/_index/qualification_summary.json` 的 `excluded_agent_failures`。
> 模型门槛不能覆盖数据质量门槛。

---

## 4. 2026-10-12 返修口径补充（wfmt-215 / wchunk-216）

本节由质检返修（报告 004 / 005 号条目）追加，**不重算、不改写**上方 2026-10-08 的历史数值。

### 4.1 Kimi K3 槽位判为 INVALID

| task_id | 试次 | 失败原因 | 处置 |
|---|---|---|---|
| wfflab__wfmt-215 | `jobs/task__0FH0XP7` | HTTP 429 `AccountQuotaExceeded`（`2026-10-11T12:05:43` → `12:11:48 +08:00`，失败前 3 turns / 4 tool_calls） | 无效槽位，不计入积分；`jobs/invalid-slots.json` 单列；槽位开放，待配额恢复后按同一计划槽位重跑 |
| wfflab__wchunk-216 | `jobs/task__5Bygi5c` | HTTP 429 `AccountQuotaExceeded`（`2026-10-11T03:44:49` → `04:46:26 +08:00`，失败前 7 turns / 19 tool_calls） | 同上 |

这两条历史上被 runner 的失败分支写成 `reward=0.0`，**不是能力测量**；一票否决第 14 条禁止把
环境/基础设施缺陷记为模型 0 分。因此 `model_summary.csv` 与 `model_validation_summary.json`
中对应行的 `validity` 已改为 `INVALID`，积分字段留空（历史 `jobs/` 记录未改写）。

### 4.2 wfflab__wchunk-216 的区分度方向

`_qc_runs/qc-216-auto/model-gate.json`：Qwen 3 次 `model_score_sum=0`、Opus 3 次 `model_score_sum=2`
→ 满足「Opus 严格高于 Qwen」。但该轮 144 条 errors 显示逐 case 状态为 `NONE`（评分证据不完整，
`pass=false`），因此该积分**只作区分度方向证据**，不作为最终验收数；正式复核需在 216 1.2.1 上重跑。

### 4.3 返修后的评分口径

自 216 1.2.1 / 215 2.1.1 起，两题评分族为**纯程序化 1.0**（`programmatic-v3` /
`rubric-conditions-v3`）；不生效的 llm_judge 50% 声明已正式废止（版本化说明见各包
`REFIT-2026-10-12.md`）。二值门禁不变：required F2P + P2P 全过 = 1，否则 0。

### 4.4 控制组复验（返修后，本机）

| task | Golden | no-change |
|---|---|---|
| wfflab__wchunk-216 1.2.1 | 19/19，`formal_score=1` | 9/19，`formal_score=0` |
| wfflab__wfmt-215 2.1.1 | 16/16，`formal_score=1` | 7/16，`formal_score=0` |

证据归档：`_qc_runs/refit-215-216/`（`result-golden-*.json`、`result-nochange-*.json`、
`negative-access-*.json`、`validate-env-*.txt`）。

