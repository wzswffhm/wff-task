# 多模型验证报告

生成时间：2026-10-01

## 1. 区分度准入汇总

| task_id | Qwen score_sum | Opus score_sum | 满足条件 | 结论 |
|---|---|---|---|---|
| wfflab__winstall-210 | None | 1.0 | - | BLOCKED — 主模型有效运行不足 3 次，暂不可判定 |

## 2. 逐模型运行状态

| task_id | 模型 | 要求 | VALID | INVALID | PENDING | 状态 |
|---|---|---|---|---|---|---|
| wfflab__winstall-210 | Opus 5 | 3 | 3 | 0 | 0 | READY |

## 3. 准入规则

```
条件 1: Opus5.model_score_sum > Qwen.model_score_sum
条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen.testcase_pass_sum
```

> 只统计 VALID 运行；INVALID 必须查明原因并补跑，不得计入难度统计。
> 模型门槛不能覆盖数据质量门槛：题面歧义、错误测试、环境故障、答案泄漏、Windows 价值不足时仍不得验收。
> 不得为制造分差而增加题面未声明要求或冷门陷阱。

