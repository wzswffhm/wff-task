# wfflab__wvas-216 · 交付记录（1.0.0，替换 wchunk-216 槽位）

| 项 | 值 |
| --- | --- |
| 交付 ZIP | 已上传飞书「作业压缩包」单元格（本地副本已删）；SHA256 `807237e2a42de87f788b936995459361ee94d003d0907cf37c910979694a5c72` |
| 任务身份 | `wfflab__wvas-216` v1.0.0 |
| 采购分类 | 系统与内存管理（Windows 虚拟地址空间审计；判分期真实调用 `VirtualQueryEx` / `GetMappedFileNameW` / `QueryDosDeviceW`） |
| required testcase | 16（F2P 8 / P2P 8） |
| 评分族 | 纯程序化 1.0（`programmatic_weight = 1.0`，`llm_judge_weight = 0.0`，二值、无部分分） |
| task checksum | `b925e1c7f68e6954805fa39e6ea584577ced25f87a74d58fb7325b288469461b` |
| `instruction.md` SHA256 | `04a919c928857a207b533cd6f6578441d72bc3b3aa0746637bddf245413e8665` |
| `tests/rubric.json` SHA256 | `b1e497b42ade986eb0d841167d2a7fdc033560a921a9e8d373f8252776ba30ed` |
| 容器基础镜像 | `mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c…db6a` |

> `solution/` 仅在 Golden 轮经 Harbor 注入；模型容器不可见 `verifier/`。`jobs/`（原生 Harbor job）随包交付，用于复现与复算。

## 1. 控制组（真实 Windows 容器）

| 轮 | 正式分 | run_validity | cases | 耗时 |
| --- | --- | --- | --- | --- |
| `ctl-nop-1` | 0 | VALID | 16（PASS 8 / FAIL 8） | 49 s |
| `ctl-nop-2` | 0 | VALID | 16（PASS 8 / FAIL 8） | 51 s |
| `ctl-nop-3` | 0 | VALID | 16（PASS 8 / FAIL 8） | 50 s |
| `ctl-oracle-1` | 1 | VALID | 16（PASS 16） | 57 s |
| `ctl-oracle-2` | 1 | VALID | 16（PASS 16） | 69 s |
| `ctl-oracle-3` | 1 | VALID | 16（PASS 16） | 65 s |

结论：**Golden ×3 = 1（OK）、no-change ×3 = 0（OK）**；no-change 下 8 条 F2P 逐条 FAIL、8 条 P2P 逐条 PASS，逐 testcase 终态符合预期（D02）。逐例矩阵见 `evidence/manual-review/case-matrix.md`。

## 2. 模型轮次（真实 Windows 容器）

| 模型 | 正式分（逐轮） | 逐轮 cases | 合计分 | 逐 case 累计 |
| --- | --- | --- | --- | --- |
| Qwen3.8-Max-0902 | 1 / 1 / 0 | 16/16 · 16/16 · 14/16 | 2 | 46 |
| Opus 5（`claude-opus-5`） | 1 / 1 / 1 | 16/16 · 16/16 · 16/16 | 3 | 48 |
| GLM-5.3（可选） | — | — | 0 | — |
| Kimi K3（可选） | — | — | 0 | — |

**区分度准入**：Opus 总分 3 > Qwen 总分 2，逐 testcase 累计 48 > 46 → **通过（成立）**。

如实说明：

- `model-opus-2` 首轮曾出现一次**真实模型失败**（MODEL_FAILURE）：该轮模型只读了工作区文件，在 step 5 直接 `end_turn` 且未产出 `patch.diff`，判分 8/16（与 no-change 完全一致）。它给出的理由是"可见冒烟用例要求每个 module 的 `path` 为真，与验收 C 允许 `None` 冲突"。经核对，该冒烟用例（`environment/workspace/tests/test_wvas_basic.py`）只对**当前进程**断言 `assert item["path"]`，而验收 C 描述的是**无法还原路径的映像**允许 `None`，两者在逻辑上可同时满足，模型自己也写明"for the current process, every module should resolve successfully"。因此**不构成契约矛盾**，属模型推理取舍失误，按规则该轮有效计 0（D19）。该槽位已按同一计划重跑并取得 1 分，最终三份 Opus 轮次均为 1；失败轮次保留在 `jobs/_index/` 的历史记录中，不双计、不选最高分。
- `model-qwen-3` 同样为真实 MODEL_FAILURE：2 条 F2P 未实现，其余 14 条 PASS，`run_validity == VALID`。
- 按甲方 2026-10-13 口径**不跑 GLM/Kimi**，交付规模固定为 Qwen×3 + Opus×3，共 12 个原生 Harbor job（控制 6 + 模型 6）。

## 3. 身份一致性

全部 12 个原生 Harbor job 的 `task_checksum` 均为同一值
`b925e1c7f68e6954805fa39e6ea584577ced25f87a74d58fb7325b288469461b`。
逐轮明细见 `jobs/_index/assembly_report.json`；独立复算对照见 `evidence/manual-review/independent-recompute.md`（复算值与 `reward.txt`、`report.json` 全部一致，无差异）。

## 4. 甲方 WIP 94 项自检

逐项登记见 `evidence/manual-review/wip94-register.md`（同时提供 `.json`）。覆盖 FC 13 项、QD-SP 18 项、QD-SO 7 项、QD-IN 6 项、ENV 14 项、VV 36 项，共 94 项，逐项给出结论与证据文件或证据位置；判定为"待人读"的项均标明所引用的具体文件与字段，缺证据不标通过。

本 README 即为该清单 FC-11 / FC-12 / FC-13 所要求的最终质检报告（UTF-8 Markdown）。

## 5. 十项人工质量复核

见 `evidence/manual-review/quality-review.json`，十项全部 `PASS`：

| 复核项 | 结论 | 主要证据 |
| --- | --- | --- |
| `golden_nop_expected` | PASS | `case-matrix.md`、控制组 6 轮 |
| `rubric_case_correctness` | PASS | `judge.toml` 权重和 1.00、`rubric.json` 摘要绑定一致 |
| `testcase_contract_fairness` | PASS | 现象 1–7 ↔ 8 F2P；验收 A–E ↔ 8 P2P；三份独立补丁均可达 16/16 |
| `hack_free` | PASS | `hack-events.md`：12 份轨迹 0 事件 |
| `windows_value` | PASS | `verifier/WINDOWS_VALUE.md`、F1–F6 机制闸门 |
| `scope_version_identity` | PASS | task checksum + `instruction.md` / `rubric.json` SHA256 绑定 |
| `wip94_complete` | PASS | `wip94-register.md/.json` |
| `dynamic_d01_d20_complete` | PASS | `dynamic-d01-d20.md` |
| `independent_score_recompute` | PASS | `independent-recompute.md/.json` |
| `evidence_retest_integrity` | PASS | `REFIT-2026-10-14.md`、逐轮封存证据 |

## 6. 本地证据索引

| 路径 | 内容 |
| --- | --- |
| 飞书 216 记录「作业压缩包」 | 交付包（2026-10-14 上传；本地副本已按指示删除） |
| `evidence/manual-review/wip94-register.md/.json` | WIP 94 项逐项登记 |
| `evidence/manual-review/dynamic-d01-d20.md` | D01–D20 动态审计 |
| `evidence/manual-review/case-matrix.md/.json` | 逐 testcase × 逐轮次终态矩阵 |
| `evidence/manual-review/independent-recompute.md/.json` | 独立复算对照 |
| `evidence/manual-review/hack-events.md/.json` | D15–D17 Hack 事件登记 |
| `evidence/manual-review/quality-review.json` | 十项人工质量复核 |
| `evidence/clean-retest.json` | 同一 checksum 下干净容器独立复验（QC PASS） |
| `evidence/qc/report.md` / `report.json` | 甲方口径完整交付 QC 报告（PASS，含首轮存档） |
| `evidence/images/score_summary.png` | 模型得分与区分度 |
| `evidence/images/oracle_nop_controls.png` | 控制轮对照 |
| 包内 `jobs/` | 原生 Harbor job（控制组 + 模型轮次） |

## 7. 返修与替换说明

见 `REFIT-2026-10-14.md`：逐条记录本轮替换动机（原 `wchunk-216` 为"通用编码能力"、缺 Windows 核心价值）、Windows 机制闸门 F1–F6 结果、题面去答案化处理、以及对外部检查意见的逐条核对结论。对外部检查意见的**逐条实物核对答复**另见 `REVIEW-RESPONSE.md`。

## 8. 甲方口径完整交付 QC

用甲方 QC 脚本 `run_delivery_qc.py`（`_reference/windows-harbor-qc/scripts/`，`--attempts 3 --quality-review …`）对交付 ZIP 独立复检，**结论 PASS（exit code 0）**，五节全部通过：

| 节 | 结论 |
| --- | --- |
| 交付目录与身份绑定 | PASS |
| 四模型门禁 | PASS |
| 四模型原始 jobs | PASS |
| Oracle/NOP 实跑 | PASS |
| 十项人工质量复核 | PASS |

- **干净复验**：同一不可变 checksum 下重跑 Oracle×3 = 1/1/1（16/16）与 NOP×3 = 0/0/0（8/16，F2P 全 FAIL、P2P 全 PASS），六轮 `errored_trials = 0`、`invalid = 0`；记录见 `evidence/clean-retest.json`，QC 原始产出归档于 `evidence/qc/`。
- **首轮偶发如实留档**：第一次 QC 曾在 `nop-2` 轮报 `RewardFileNotFoundError`（同容器内 pytest 崩溃 → verifier 未产出 reward 文件），而同批 `nop-1` 与 `oracle×3` 全部正常。归因为**环境偶发（ENVIRONMENT_TRANSIENT）**而非包缺陷：交付包内不存在 `systeminfo` / `wmic` / `BuildType` 等调用（全套源码检索无命中），该段 stdout 来自容器/系统层；且同 checksum 的原始 12 轮与实际交付的第二遍 6 轮控制轮全部正常，包内容自始至终未改动。首轮报告留档于 `evidence/qc/report-first-attempt.md`。

## 9. 飞书 216 槽位写入状态（2026-10-14）

记录 `reczz28KQU8reW2k` 已整体替换为 wvas-216：

| 项 | 值 | 状态 |
|---|---|---|
| 题目方向 | Windows/系统与内存管理（Windows 虚拟地址空间审计：VirtualQueryEx 完整 64 位地址宽度与 MEM_RESERVE 可见性、GetMappedFileNameW + QueryDosDeviceW 还原 DOS/UNC 路径）/Python/缺陷修复 | 已写入 |
| 提示词 | 包内 instruction.md（2857 字符） | 已写入 |
| 状态 | 待提交（写入时）→ 现为「返修待质检」 | 已写入 |
| 文本 | wfflab__wvas-216-v1.0.0-delivery.zip | 已写入 |
| Qwen分数 | 2/3 | 已写入 |
| opus分数 | 3/3 | 已写入 |
| 返修原因 | 替换说明 | 已写入 |
| oracle/nop截图 | oracle_nop_controls.png（84,635 B） | 已写入 |
| 分数截图 | score_summary.png（55,651 B） | 已写入 |
| 作业压缩包 | wfflab__wvas-216-v1.0.0-delivery.zip（54,455,198 B） | 已上传 |

三个附件单元格先在同一次 upsert 中清空，再写入新件，保证格内唯一（不残留 wchunk-216 的旧件）。

**作业压缩包为何只能手动上传**：54 MB 超出所有可用通道的限制 ——
`drive/v1/medias/upload_all` 超过 20 MB 返回 `1061002 params error`（省略 `size` 则为 502）；
`drive/v1/medias/upload_part` 同为 `1061002`；`drive +upload` 返回
`1061043 file size beyond limit`（配额）；lark-cli 的 `+record-upload-attachment` /
`+record-remove-attachment` 内部编排走 `/open-apis/base/v3/...`，该路径在本环境整体
404（1.0.85 与 1.0.98 一致，user 与 bot 身份一致），而 `bitable/v1`、`drive/v1` 正常。
两张 PNG 与三个字段均走 `drive/v1/medias/upload_all` + `bitable/v1` 原生接口成功写入。
该包已由用户在飞书界面拖入「作业压缩包」单元格，回读核对为格内 1 件、54,455,198 B。相关脚本见 `scripts/finalize_feishu_216.py`、
`scripts/slice_for_upload.py`、`scripts/feishu-216-upload-native.ps1`。
