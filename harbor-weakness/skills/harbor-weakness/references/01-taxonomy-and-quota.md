# 金融领域分类、题量配额与交付 Metadata

> 本文件是**总纲**：回答"这批要出多少题、每类多少条、难度怎么分、每题要写哪些元数据"。
> 各类怎么构造 → `02`–`08`；交付格式与判分 → `../delivery/00-delivery-standard.md`。

---

## 1. 领域范围与分布约束

| 项 | 要求 |
|---|---|
| 领域 | **金融（FIN）**，本批仅此一个领域 |
| 总量 | **2000 条** |
| 分布 | 金融领域下数据须**均匀分布** |
| 硬约束 | **不接受一个知识点 / workflow 出题 ≥ 3 道** |

> 出题前先建"知识点台账"，每出一道题登记其细分知识点/业务动作，**同一细分点计数达到 2 即应换点**。

---

## 2. 两大数据块

| 块 | 条数 | 出发点 | 目标 |
|---|---|---|---|
| **专项数据**（skill / tool / workflow） | **1000** | 从**能力维度**出发 | 系统、完整覆盖某一能力的场景 / 难度 / 环境 / 任务形态 |
| **Weakness-driven 数据** | **1000** | 从**已观测缺陷**出发 | 稳定复现并训练具体 Bad Pattern |

> 两块**共用**难度分级（A1/A2/A3）、复杂度分级（C1–C5）与交付格式，
> 差异只在**选题依据**：专项是"能力要覆盖全"，weakness 是"缺陷要复现准"。

---

## 3. 专项数据：5 个二级类型

| 一级 | 二级 | 条数 | 构造细则 |
|---|---|---|---|
| Skills 数据 | **Skill Discovery** | 200 | `02-skill-discovery.md` |
| Skills 数据 | **Skill Generation / Editing** | 200 | `03-skill-authoring.md` |
| Skills 数据 | **Skill Dependency** | 200 | `04-skill-dependency.md` |
| Workflow Execution | **Dependency-aware Workflow** | 200 | `05-workflow.md` |
| Workflow Execution | **Subagent Workflow** | 200 | `05-workflow.md` |
| — | **MCP Scaling**（低优） | 机动 | `05-workflow.md` §MCP |

### 3.1 为什么要做 scaling 专项（背景）

当前 RL 数据中多数任务仍运行在相对简单的环境里：

- 以 filesystem / shell / 少量原生工具为主；
- Tool schema、可用能力、调用方式相对固定；
- **Skill 即使存在，也常常只是辅助信息，并非完成任务所必需**；
- Workflow 多为线性的「读取 → 处理 → 输出」，缺少真实业务中的状态变化、异步依赖、异常恢复、跨工具协同。

**下一阶段目标**：从单纯扩充 **Task Distribution**，转向扩充 **Environment Distribution**。

### 3.2 MCP Scaling（低优，机动配额）

扩大模型在**非原生工具、陌生 Tool Schema、不同 Tool 组合**下的泛化能力。

| 要求 | 说明 |
|---|---|
| 显式声明工具集 | 每条任务必须**明确提供当前 Environment 下可用的工具集合 / MCP** |
| 工具来源 | 可用框架已有能力，也可**动态注入自定义工具**（须在题面显式说明） |
| 优先级 | 低——在 5 个主要类型配额满足后再补 |

---

## 4. 难度分级（A1 / A2 / A3）

按**三模型平均正确率**划分。**平均分 < 0.7 即难度达标**，达标后再按区间归级（区间不重叠）。

| 级别 | 占比 | 单领域数量 | 平均正确率 | 定位 |
|---|---|---|---|---|
| **A1** 基础 | 20% | 50 | 60% ≤ 得分 < 70% | 有门槛但常规 |
| **A2** 进阶 | 60% | 150 | 50% ≤ 得分 < 60% | 主力难度 |
| **A3** 高难 | 20% | 50 | 得分 < 50% | 拉分位 |

> 单领域 250 题的口径下按上表配比；全批 2000 条时按同一比例外推。
> **三模型**：`gpt-5.6-sol`、`claude-opus-4-8`、`qwen3.8-max0902`；**裁判**：`qwen3.7-plus`。
> 详细跑分口径 → `../delivery/06-model-validation.md`。

---

## 5. 复杂度分级（C1–C5）与题量配比

`task_complexity` 按**六项硬指标**判定（文件数 / Requirement 数 / 产物数 / Evidence Chain / 执行步数 / 工具种类），
**不得从 difficulty 换算**。

| 等级 | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| 题量（weakness 1000 条口径） | **120** | **250** | **350** | **180** | **100** |
| 占比 | 12% | 25% | 35% | 18% | 10% |

> 完整分级表与判定方法 → `07-complexity-scales.md`。
> 专项 1000 条的复杂度无强制配比，但**须与所在类型的构造强度匹配**（如 Subagent Workflow 通常 ≥ C3）。

---

## 6. 专项数据交付 Metadata

每条专项数据在 `[metadata]` 中额外维护：

```toml
skill_set                   = ["approval-workflow"]   # 环境内安装的功能型 skill（= environment/skills/ 下的目录名）
task_complexity             = "C3"                    # C1–C5
expected_skill_dependencies = ["approval-workflow"]   # 完成任务真正必须依赖的 skill（子集，可为空）
weakness_tag                = ["W07-流程跳步"]          # ≥1 个
```

| 字段 | 类型 | 取值写法 / 约束 |
|---|---|---|
| `skill_set` | array | 环境内安装的 skill 目录名，须与 `environment/skills/<name>/` **逐一对应**；**可含干扰项**（Skill Discovery 场景） |
| `task_complexity` | enum | C1–C5 |
| `expected_skill_dependencies` | array | `skill_set` 的**子集**；Skill Discovery 任务中应**严格小于** `skill_set`（存在故意无关的 skill） |
| `weakness_tag` | array | ≥1 个，按算法词表填写 |

> 四项字段齐全才算交付完整。`expected_skill_dependencies` 与 `skill_set` 的关系是
> **Skill Discovery / Skill Dependency 的唯一区分抓手**（详见 `references/02` 与 `references/04` 的边界说明）。

### 6.1 各类型的 metadata 差异化写法

| 类型 | `skill_set` | `expected_skill_dependencies` | 备注 |
|---|---|---|---|
| Skill Discovery | 2–4 个（含干扰项） | **严格小于** `skill_set`，可含 0 | 考察"该不该用 / 用哪个" |
| Skill Dependency | 1–2 个 | **等于**关键 skill（非空） | 无它必失败 |
| Skill Generation / Editing | 通常 `[]` 或 1 个模板 skill | 通常 `[]` | 产物是 skill 本身 |
| Dependency-aware Workflow | 视需要 | 视需要 | 重点在 `[[metadata.deliverables]]` 的依赖结构 |
| Subagent Workflow | 视需要 | 视需要 | 重点在子任务信息切分 |
| Weakness-driven | 视需要 | 视需要 | 重点是 `weakness_tag` ↔ 埋点 ↔ 判分三方对应 |

---

## 7. 完整 task.toml 参考（专项数据）

```toml
schema_version = "1.4"                             # 照抄
artifacts = [
  "/app/output/FIN-T2-001_财务分析报告.xlsx",
  "/app/output/FIN-T2-001_毛利率趋势.png",
  "/logs/artifacts/output",
]
[task]
name = "work/fin1-001"
version = "1.0.0"
description = "基于两期年报与交易流水产出财务分析报告"
[metadata]
task_id = "FIN1-skill-DEP-001"
author_organization = "<供应商名>"
category = "skill-dependency"
domain = "金融"
domain_l2 = "投资银行"
capabilities = "财务比率计算、估值口径"
difficulty = "A2"
vl_dependency = "否"
source_note = "任务来源、真实性保障、真实场景中的交付物是什么"
tools = "Excel/Python"
domain_knowledge = "再融资定增的财务分析口径与可比公司估值方法"
task_complexity = "C2"
weakness_tag = ["W07-流程跳步", "W12-约束遵循"]
environment_template = "<平台已确认的环境模板名>"
tool_set = ["filesystem", "shell", "python"]
skill_set = []
expected_tool_dependencies = ["filesystem", "shell", "python"]
expected_skill_dependencies = []
tags = ["finance", "office", "A2", "skill-dependency", "sop-enforcement", "workflow", "docx", "llm-judge"]
[[metadata.deliverables]]
path = "FIN-T2-001_财务分析报告.xlsx"
required = true
desc = "主交付物：财务分析报告"
[[metadata.deliverables]]
path = "FIN-T2-001_毛利率趋势.png"
required = true
desc = "毛利率趋势折线图"
[agent]
timeout_sec = 72000.0
[verifier]
timeout_sec = 18000.0
user = "root"
[verifier.env]
JUDGE_API_KEY = "${JUDGE_API_KEY:-}"
JUDGE_BASE_URL = "${JUDGE_BASE_URL:-}"
JUDGE_MODEL = "${JUDGE_MODEL:-qwen3.7-plus}"
JUDGE_PROVIDER = "${JUDGE_PROVIDER:-anthropic}"
JUDGE_API_PROTOCOL = "${JUDGE_API_PROTOCOL:-anthropic}"
EVAL_API_KEY = "${EVAL_API_KEY:-}"
EVAL_API_BASE = "${EVAL_API_BASE:-}"
LITELLM_DROP_PARAMS = "true"
[environment]
os = "linux"
build_timeout_sec = 18000.0
network_mode = "public"      # claude-code 框架下不要写 no-network
cpus = 2
memory_mb = 8192
storage_mb = 30720           # 照抄
```

> 书写顺序、`[environment]` 键白名单、`deliverables` 命名规则等**硬约束**
> → `../delivery/02-task-toml.md`（本文件的模板已符合，直接抄用即可）。

---

## 8. 验收口径（两块共用）

| 环节 | 判定 |
|---|---|
| ① 参考答案 | 用打分项给参考答案打分，**正确率 > 0.85** |
| ② 难度 | 3 个模型执行并打分，**平均分 < 0.7**；**至少一个模型有得分**（避免死题） |
| ③ 人工质检 | 考察题目真实性、参考答案合理性、打分项合理性、**是否 hack** |
| ④ 轨迹 | 提交题目时**同步提供模型产物与跑分轨迹** |

> 人工质检一经发现异常作弊，**直接打回**。
