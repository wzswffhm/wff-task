# 多模型验证报告

生成时间：2026-10-04

## 1. 区分度准入汇总

| task_id | Qwen score_sum | Opus score_sum | 满足条件 | 结论 |
|---|---|---|---|---|
| wfflab__wtask-216 | 3.0 | 3.0 | - | FAIL — 两者正式分和相同且不全为 0（Opus 3.0 vs Qwen 3.0） |

## 2. 逐模型运行状态

| task_id | 模型 | 要求 | VALID | INVALID | PENDING | 状态 |
|---|---|---|---|---|---|---|
| wfflab__wtask-216 | Qwen3.8-Max-0902 | 3 | 3 | 0 | 0 | READY |
| wfflab__wtask-216 | Opus 5 | 3 | 3 | 0 | 0 | READY |
| wfflab__wtask-216 | GLM-5.3 | 1 | 1 | 0 | 0 | READY |
| wfflab__wtask-216 | Kimi K3 | 1 | 1 | 0 | 0 | READY |

## 3. 准入规则

```
条件 1: Opus5.model_score_sum > Qwen.model_score_sum
条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen.testcase_pass_sum
```

> 只统计 VALID 运行；INVALID 必须查明原因并补跑，不得计入难度统计。
> 模型门槛不能覆盖数据质量门槛：题面歧义、错误测试、环境故障、答案泄漏、Windows 价值不足时仍不得验收。
> 不得为制造分差而增加题面未声明要求或冷门陷阱。

