# 伴随材料模板（metadata-templates）

复制到 `delivery-extras/tasks/<task-id>/metadata/`，替换所有占位符。

| 模板 | 对应规范条目 | 用途 |
|---|---|---|
| `source_and_license.json` | 3.5-① | 来源、License、授权、隐私、Windows 相关性 |
| `labels.json` | 3.5-② | 主知识方向、次级标签、语言、任务类型、Windows 环境、难度 |
| `lineage_and_contamination.json` | 3.5-① | Lineage、污染风险、重复风险、Hack 四层分级 |
| `manifest.json` | 3.5-⑥ | 身份三元组、制品哈希、冻结基线 |

## 其余伴随材料（CSV / MD，无 JSON 模板）

| 文件 | 关键列 / 章节 |
|---|---|
| `testcase_mapping.csv` | `requirement_id, requirement_text, testcase_id, group(F2P/P2P), evidence` |
| `quality_review.md` | 质检结论（PASS/FAIL/FLAG/BLOCKED）、证据缺口、Hack 审查四层分级 |
| `remediation_and_retest.md` | 问题、根因、整改动作、复验方式、复验结论 |
| `evidence/golden/` | 3 次运行记录 + 原始日志 + report.json + 干净重建证明 |
| `evidence/no_change/` | 3 次运行记录 + P2P 全过 + 核心 F2P 失败的证据 |
| `evidence/clean_room/` | 干净环境重建/恢复后的复验结果 |
| `evidence/negative_and_equivalent_controls/` | 空实现/固定返回/提前退出/硬编码/只修一半/吞异常/禁用功能 |
| `evidence/cleanup_and_restore/` | 注册表/服务/计划任务/证书/ACL/防火墙/驱动 变更的清理与回滚证据 |
| `model_runs/<model>/` | `config.json` + `run-1..3/`（轨迹、逐 testcase 结果、最终补丁、耗时） |

## 批次级文件

| 文件 | 用途 |
|---|---|
| `batch_manifest.csv` | 批次清单：task_id、版本、hash、状态 |
| `knowledge_tree_coverage_report.csv` | 知识树覆盖统计 |
| `validation_report.md` | 批次验收状态 |
| `model_summary.csv` | 各模型得分汇总（用于区分度计算） |
| `known_issues.md` | 已知问题 |
| `checksums.sha256` | 全部交付物哈希 |
| `CHANGELOG.md` | 版本变更记录 |

> 缺任一批次级文件或题级六项 → **不得验收**（规范 5.1）。
