# wfflab__wfmt-215 跑分结果摘要

- 题包版本：**2.1.1**（目录名 `wfflab__wfmt-215-v2.1.0-delivery`）
- 生成时间：2026-10-13 18:30:19
- 模型口径：甲方 2026-10-13 规则 —— GLM/Kimi **不再必需**，只跑 控制组 + Opus + Qwen（12 轮）
- 运行环境：本地 Outside-Harbor runner + Windows 容器（`outside-harbor/wfflab__wfmt-215:2.1.1`）

## 逐轮明细

### NOP 控制（no-change）（3 轮）

| run_id | verdict | testcase | 有效性 | 耗时 | 结束 |
|---|---|---|---|---|---|
| `20261013T170439-no-change-no-change-01-15da` | 0 | 7/16 | VALID | 8.9s | 10-13 17:04:48 |
| `20261013T170449-no-change-no-change-01-eaec` | 0 | 7/16 | VALID | 9.2s | 10-13 17:04:58 |
| `20261013T170459-no-change-no-change-01-0400` | 0 | 7/16 | VALID | 9.1s | 10-13 17:05:08 |

### Oracle 控制（golden）（3 轮）

| run_id | verdict | testcase | 有效性 | 耗时 | 结束 |
|---|---|---|---|---|---|
| `20261013T170510-golden-golden-01-2480` | 1 | 16/16 | VALID | 14.9s | 10-13 17:05:24 |
| `20261013T170525-golden-golden-01-3845` | 1 | 16/16 | VALID | 16.0s | 10-13 17:05:41 |
| `20261013T170543-golden-golden-01-598b` | 1 | 16/16 | VALID | 18.8s | 10-13 17:06:01 |

### Opus 5（3 轮）

| run_id | verdict | testcase | 有效性 | 耗时 | 结束 |
|---|---|---|---|---|---|
| `20261013T170603-candidate-opus-5-01-304f` | 0 | 7/16 | VALID | 1094.7s | 10-13 17:24:18 |
| `20261013T172420-candidate-opus-5-01-9923` | 1 | 16/16 | VALID | 2492.1s | 10-13 18:05:52 |
| `20261013T180723-candidate-opus-5-01-8846` | 1 | 16/16 | VALID | 1203.3s | 10-13 18:27:26 |

### Qwen3.8-Max-0902（3 轮）

| run_id | verdict | testcase | 有效性 | 耗时 | 结束 |
|---|---|---|---|---|---|
| `20261013T171816-candidate-qwen3.8-max-0902-01-1400` | 0 | 7/16 | VALID | 371.6s | 10-13 17:24:28 |
| `20261013T172430-candidate-qwen3.8-max-0902-01-2012` | 0 | 7/16 | VALID | 372.8s | 10-13 17:30:43 |
| `20261013T173044-candidate-qwen3.8-max-0902-01-cd2f` | 0 | 7/16 | VALID | 362.2s | 10-13 17:36:47 |

## 结论

- 控制组 `no-change`：[0, 0, 0]，符合预期（全 0）
- 控制组 `golden`：[1, 1, 1]，符合预期（全 1）
- 模型累计分：Opus 5 = **2**，Qwen3.8-Max = **0**
- testcase 累计通过数：Opus = **39**，Qwen = **21**
- 区分度门禁：**通过**（Opus 总分严格高于 Qwen）
