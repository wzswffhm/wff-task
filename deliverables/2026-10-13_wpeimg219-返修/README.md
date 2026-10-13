# wfflab__wpeimg-219 · 交付记录（1.3.0 → 1.4.0）

| 项 | 值 |
| --- | --- |
| 交付 ZIP | `package/wfflab__wpeimg-219-v1.4.0-delivery.zip` |
| 任务身份 | `wfflab__wpeimg-219` v1.4.0 |
| 采购分类 | 原生开发与互操作（Windows PE/COFF 映像；判分期真实调用 imagehlp!MapFileAndCheckSumW 与 kernel32!CreateFileW） |
| required testcase | 43（F2P 35 / P2P 8）
| 评分族 | 纯程序化 1.0（`llm_judge_weight = 0.0`） |
| 生成时间 | 2026-10-14T04:54:44.116849+08:00 |

> `extras/`（伴随材料）不进交付包；`solution/` 仅在 Golden 轮注入。

## 1. 控制组（真实 Windows 容器）

| 轮 | 正式分 | run_validity | cases |
| --- | --- | --- | --- |
| `ctl-nop-1` | 0 | VALID | 43/43 |
| `ctl-nop-2` | 0 | VALID | 43/43 |
| `ctl-nop-3` | 0 | VALID | 43/43 |
| `ctl-oracle-1` | 1 | VALID | 43/43 |
| `ctl-oracle-2` | 1 | VALID | 43/43 |
| `ctl-oracle-3` | 1 | VALID | 43/43 |

结论：**Golden ×3 = 1（OK）、no-change ×3 = 0（OK）**。

## 2. 模型轮次（真实 Windows 容器）

| 模型 | 正式分（逐轮） | 逐轮 cases | 合计 |
| --- | --- | --- | --- |
| Qwen3.8-Max-0902 | 1 / 1 / 1 | 43/43 / 43/43 / 43/43 | 3 |
| Opus 5 | 1 / 1 / 1 | 43/43 / 43/43 / 43/43 | 3 |
| GLM-5.3（可选） | — | — | 0 |
| Kimi K3（可选） | — | — | 0 |

**区分度准入**：Opus 总分 3、Qwen 总分 3，逐 testcase 累计 129 vs 129 → **FAIL**。

## 3. 身份一致性

全部 12 个原生 Harbor job 的 `task_checksum` 同一值：`8af4efbac29d722f82574432c79da66a49ffcc345cbeafacbf1ef798be49236b`。

逐轮明细见 `jobs/_index/assembly_report.json`。

## 4. 返修说明

见包内 `REFIT-2026-10-13.md`（逐条闭环 + 本机对照 + 容器控制组 + 隔离证据）。

## 5. 本地证据索引

| 路径 | 内容 |
| --- | --- |
| `package/wfflab__wpeimg-219-v1.4.0-delivery.zip` + `.sha256` | 交付包与校验和 |
| `evidence/images/score_summary.png` | 模型得分与区分度 |
| `evidence/images/oracle_nop_controls.png` | 控制轮对照 |
| 包内 `jobs/` | 原生 Harbor job（控制组 + 模型轮次） |
| `harbor-windows/_qc_runs/relaunch-20261013/219/` | 原始日志与轮次汇总 |
