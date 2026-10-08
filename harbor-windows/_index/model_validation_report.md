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

