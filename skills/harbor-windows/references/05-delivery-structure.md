# 05 · 交付结构与伴随材料

来源：规范第五章 5.4 / 5.5

---

## 一、批次交付目录树

```
delivery-<batch>-<version>/
├── outside_harbor/                     # 沿用现有提交结构：每题平台导入 JSON
│   └── <task-id>.json
├── outside_harbor-assets/              # 沿用现有提交结构：题目与执行资产
│   ├── .ap-tools/                      # 暂沿用；最终归属待多团队确认
│   └── <task-id>/                      # 必须整理成冻结 Schema 的标准 Harbor Task
│       ├── task.toml
│       ├── instruction.md
│       ├── environment/
│       ├── solution/
│       └── tests/
└── delivery-extras/                    # 暂定新目录名：题外强制交付材料
    ├── batch_manifest.csv
    ├── knowledge_tree_coverage_report.csv
    ├── validation_report.md
    ├── model_summary.csv
    ├── known_issues.md
    ├── checksums.sha256
    ├── CHANGELOG.md
    └── tasks/<task-id>/
        ├── metadata/
        │   ├── source_and_license.json
        │   ├── labels.json
        │   ├── lineage_and_contamination.json
        │   └── manifest.json
        ├── evidence/
        │   ├── no_change/
        │   ├── golden/
        │   ├── clean_room/
        │   ├── negative_and_equivalent_controls/
        │   └── cleanup_and_restore/
        ├── model_runs/
        │   ├── qwen3.8-max-0902/
        │   ├── opus-5/
        │   ├── glm-5.3/
        │   └── kimi-k3/
        ├── testcase_mapping.csv
        ├── quality_review.md
        └── remediation_and_retest.md
```

---

## 二、关键约定

### 2.1 两个主目录的关系

| 项 | `outside_harbor/<task-id>.json` | `outside_harbor-assets/<task-id>/` |
|---|---|---|
| 用途 | **仅平台导入** | **正式题本体** |
| 性质 | 不等于标准 Harbor Task | 通过冻结 Schema 校验的 Harbor 内容 |
| 身份 | 必须与右侧引用**同一** `task_id + task_version + task_hash` | 同左 |

> 两者**不得各自维护一份互相偏离的题面或判分规则**。

### 2.2 历史包整改

- 历史每题根目录的 `source.json`、运行证据和质检材料 → 本轮移入 `delivery-extras/tasks/<task-id>/`
- **只有冻结 Harbor Schema 明确要求的字段**才保留在 Task 内
- 历史 `tests/judge.toml`、`tests/rubric.json` 和聚合器**不得原样继承其权重**，须改为 **required F2P/P2P 二值判分**
- 若平台暂时必须保留兼容文件，应保证其**只表达二值规则**，并与标准 Harbor Verifier 结果一致

### 2.3 `.ap-tools/` 处理

- 目前可先按压缩包形态保留，以免阻断直接产题和现有平台运行
- 但必须**区分**：仍在使用的工具 / 历史修复脚本 / 旧版本证据
- 最终联调时再决定工具归属
- **无论位置如何，均不得进入 Agent 可见环境**

### 2.4 大文件与离线依赖

- 离线 NuGet/npm/Go/Rust 等依赖、fixture、baseline repo 等**执行所需资产**可保留在
  `environment/` 或 `tests/` 的标准允许位置
- 但必须：**版本锁定、有 Hash、来源合法**，且不泄漏 Solution 或隐藏验收内容
- **大文件不能仅因"属于资产"就全部移到题外**，否则破坏题目的离线可复现性

---

## 三、伴随交付物最低覆盖（8 项）

| # | 内容 | 归档位置 |
|---|---|---|
| 1 | 题目来源、License/授权、Repo、Commit、Issue/PR、Lineage、污染和重复风险 | `metadata/source_and_license.json`、`metadata/lineage_and_contamination.json` |
| 2 | 主知识方向、次级标签、语言、任务类型、目标 Windows 环境和难度说明 | `metadata/labels.json` |
| 3 | `requirement → testcase → F2P/P2P` 双向映射及每项依据 | `testcase_mapping.csv` |
| 4 | no-change、Golden、干净重建、等价实现、错误反例、清理和恢复结果 | `evidence/*` |
| 5 | Qwen/Opus 各 3 次 + GLM/Kimi 可运行性检查的配置、真实模型标识、运行状态、逐 testcase 结果、轨迹、最终补丁、耗时和 Badcase 归因 | `model_runs/<model>/` |
| 6 | 环境、Task、Solution、Tests、运行日志和结果文件的版本、Digest/Hash | `metadata/manifest.json`、`checksums.sha256` |
| 7 | Hack/答案泄漏检查、证据完整性缺口、已知问题、整改和复验记录 | `quality_review.md`、`known_issues.md`、`remediation_and_retest.md` |
| 8 | 批次清单、覆盖统计、验收状态和版本变更记录 | `batch_manifest.csv`、`knowledge_tree_coverage_report.csv`、`validation_report.md`、`CHANGELOG.md` |

### 泄漏红线

- 这些材料**不得在 Agent 作答阶段可见**
- 不得通过**镜像、挂载、Git 历史、缓存或日志**泄漏到被测工作区
- 采购方可导入内部质检平台，但**平台录入不能替代原始文件和 Hash 交付**

---

## 四、manifest.json 字段建议

```json
{
  "task_id": "<task-id>",
  "task_version": "1.0",
  "task_hash": "<sha256>",
  "source_commit": "<sha>",
  "base_commit": "<sha>",
  "image_ref": "<registry>/<repo>:<tag>",
  "image_digest": "sha256:<digest>",
  "artifacts": {
    "task_toml_sha256": "...",
    "instruction_md_sha256": "...",
    "test_patch_sha256": "...",
    "oracle_patch_sha256": "...",
    "spec_sha256": "..."
  },
  "windows_target": { "version": "...", "edition": "...", "arch": "...", "locale": "..." },
  "frozen_baseline": {
    "harbor_schema": "1.3",
    "harness": "harbor-rewardkit==0.1.7",
    "models": ["Qwen3.8-Max-0902", "Opus 5", "GLM-5.3", "Kimi K3"]
  }
}
```

---

## 五、交付前自检

- [ ] `outside_harbor/` 与 `outside_harbor-assets/` 引用**同一身份三元组**
- [ ] Task 目录内**无**自定义必需字段
- [ ] `delivery-extras/tasks/<task-id>/` 六个子项齐全（metadata/evidence/model_runs/testcase_mapping/quality_review/remediation）
- [ ] 批次级 7 个汇总文件齐全
- [ ] `checksums.sha256` 覆盖全部交付物
- [ ] 无 Solution / 隐藏 Tests / 答案 / 凭据泄漏
- [ ] 镜像 **Digest** 已另存（非只记 tag）
- [ ] Git Tag/Release + 环境 Digest + 批次清单可相互定位
