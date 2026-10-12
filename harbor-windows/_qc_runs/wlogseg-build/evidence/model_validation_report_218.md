# wfflab__wlogseg-218 多模型验证与区分度报告

生成时间：2026-10-12

题包：`C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wlogseg-218-v1.0.0-delivery`

## 1. 区分度准入

| Qwen score_sum | Opus score_sum | Qwen pass_sum | Opus pass_sum | 条件 | 结论 |
|---|---|---|---|---|---|
| 0 | 0 | 33 | 70 | 2 | **PASS** — 双 0 场景，Opus5.testcase_pass_sum(70) > Qwen(33) |

## 2. 逐模型逐轮明细

| 模型 | run | agent 状态 | 正式分 | 逐项 PASS | F2P 全过 | P2P 全过 | 步数 | 输出 tokens | 补丁字节 |
|---|---|---|---|---|---|---|---|---|---|
| Qwen3.8-Max-0902 | run-1 | VALID | 0 | 8/25 | False | True | 40 | 10639 | 1934 |
| Qwen3.8-Max-0902 | run-2 | VALID | 0 | 20/25 | False | True | 40 | 10321 | 35470 |
| Qwen3.8-Max-0902 | run-3 | VALID | 0 | 5/25 | False | False | 40 | 14676 | 3525 |
| Opus 5 @ 4router.net | run-1 | VALID | 0 | 23/25 | False | True | 36 | 17756 | 17423 |
| Opus 5 @ 4router.net | run-2 | VALID | 0 | 24/25 | False | True | 28 | 19381 | 38919 |
| Opus 5 @ 4router.net | run-3 | VALID | 0 | 23/25 | False | True | 38 | 19794 | 17844 |
| GLM-5.3 | run-1 | VALID | 0 | 23/25 | False | True | 40 | 75077 | 68127 |
| Kimi K3 | run-1 | VALID | 1 | 25/25 | True | True | 40 | 15604 | 37153 |

## 3. 准入规则

```
条件 1: Opus5.model_score_sum > Qwen.model_score_sum
条件 2: 两者 model_score_sum == 0 且 Opus5.testcase_pass_sum > Qwen.testcase_pass_sum
```

> 只统计 VALID 运行；INVALID 必须查明原因并补跑，不得计入难度统计。
> Opus 5 走 4router.net，必须流式（skill ref 08 §7.14）；非流式在长输出下会撞传输层超时。
