# wfflab__wlogseg-218 · 交付记录（1.0.0 → 1.1.0）

| 项 | 值 |
| --- | --- |
| 交付 ZIP | `package/wfflab__wlogseg-218-v1.1.0-delivery.zip` |
| 任务身份 | `wfflab__wlogseg-218` v1.1.0 |
| 采购分类 | 通用编码能力（Windows 运行时执行；不主张 Windows 专属价值） |
| required testcase | 26（F2P 18 / P2P 8）
| 评分族 | 纯程序化 1.0（`llm_judge_weight = 0.0`） |
| 生成时间 | 2026-10-13T23:03:52.720977+08:00 |

> `extras/`（伴随材料）不进交付包；`solution/` 仅在 Golden 轮注入。

## 1. 控制组（真实 Windows 容器）

| 轮 | 正式分 | run_validity | cases |
| --- | --- | --- | --- |
| `ctl-nop-1` | 0 | VALID | 26/26 |
| `ctl-nop-2` | 0 | VALID | 26/26 |
| `ctl-nop-3` | 0 | VALID | 26/26 |
| `ctl-oracle-1` | 1 | VALID | 26/26 |
| `ctl-oracle-2` | 1 | VALID | 26/26 |
| `ctl-oracle-3` | 1 | VALID | 26/26 |

结论：**Golden ×3 = 1（OK）、no-change ×3 = 0（OK）**。

## 2. 模型轮次（真实 Windows 容器）

| 模型 | 正式分（逐轮） | 逐轮 cases | 合计 |
| --- | --- | --- | --- |
| Qwen3.8-Max-0902 | 0 / 0 / 0 | 10/26 / 22/26 / 23/26 | 0 |
| Opus 5 | 0 / 0 / 0 | 24/26 / 8/26 / 23/26 | 0 |
| GLM-5.3（可选） | 0 | 25/26 | 0 |
| Kimi K3（可选） | 0 | 8/26 | 0 |

**区分度准入**：Opus/Qwen 总分同为零且逐 testcase 累计同为 55；全部规定模型运行均为 VALID/0，按甲方「全模型零分平局」例外允许通过 → **PASS**。

## 3. 身份一致性

全部 14 个原生 Harbor job 的 `task_checksum` 同一值：`a4e33ca3981e901423e15e7340726bd0541caa9c2ffc5e0949e127f316f4ae76`。

逐轮明细见 `jobs/_index/assembly_report.json`。

## 4. 返修说明

见包内 `REFIT-2026-10-13.md`（逐条闭环 + 本机对照 + 容器控制组 + 隔离证据）。

## 5. 本地证据索引

| 路径 | 内容 |
| --- | --- |
| `package/wfflab__wlogseg-218-v1.1.0-delivery.zip` + `.sha256` | 交付包与校验和 |
| `evidence/images/score_summary.png` | 模型得分与区分度 |
| `evidence/images/oracle_nop_controls.png` | 控制轮对照 |
| 包内 `jobs/` | 原生 Harbor job（控制组 + 模型轮次） |
| `harbor-windows/_qc_runs/relaunch-20261013/218/` | 原始日志与轮次汇总 |
