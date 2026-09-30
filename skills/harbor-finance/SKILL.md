---
name: harbor-finance
description: >
  生产金融（FIN）领域 Harbor 评测题包，覆盖两大块共 2000 条：① 专项数据 1000 条——
  Skill Discovery（该不该用/用哪个 skill，含干扰技能）、Skill Generation/Editing（创建/修改/
  从 SOP 抽取/迁移/修复 skill）、Skill Dependency（skill 中的特殊规则不可省略，含冲突暂停、
  环境特化 SOP、特殊计算口径）、Dependency-aware Workflow（A→B、A→C、B+C→D 依赖拆解与
  完成记账）、Subagent Workflow（必须回收多个异步子 Agent 结果才能完成）、MCP Scaling（低优，
  陌生 Tool Schema 泛化）；② Weakness-driven 数据 1000 条——W1–W14 全量弱点定向构造
  （长文档硬约束、冲突选边、阻塞恢复、Requirement Coverage Accounting、该问不问、Global
  Re-planning、长表抗干扰、派发即完成、skill 形式化调用、大 workspace 覆盖、无据自造、
  跨源核对缺失、规划失当、脱敏疏漏），并按 C1–C5 复杂度（文件数/Requirement/产物/Evidence
  Chain/步数/工具种类）配比 120/250/350/180/100。含 A1/A2/A3 难度分级、均匀分布约束
  （同一知识点出题 <3 道）、metadata 四字段（skill_set / task_complexity /
  expected_skill_dependencies / weakness_tag）规范与 W1–W14 覆盖台账（每种 50–250 条）。
  Use when the user asks to 出金融题 / 金融题包 / skill 专项题 / workflow 题 / weakness 题 /
  W1-W14 / C1-C5. Keywords: finance, FIN, skill discovery, skill dependency, skill authoring,
  dependency-aware workflow, subagent workflow, MCP scaling, weakness-driven, W1-W14, C1-C5,
  difficulty-control, 环境分布, 覆盖记账, 埋点, trigger, bad pattern.
description_zh: 金融领域出题（专项 + Weakness）
description_en: Finance domain task authoring
disable: false
agent_created: true
---

# 金融（FIN）领域出题：专项数据 + Weakness 定向

**目标**：在**金融领域**下同时扩充两种分布——
① **Task/Environment Distribution**（专项数据：skill / tool / workflow 能力）；
② **Defect Coverage**（Weakness 数据：已观测缺陷的定向复现）。

**交付实现见本 skill 的 `delivery/`**（五件套、task.toml 1.4、rubrics.toml、prompt.md、固定模板、
打包与验收；原独立 skill `harbor-rewardkit` 已内联至此，本 skill 自包含）。
本 skill 的 `references/` 只回答**出什么题、怎么构造**。

---

## 用途与触发条件

触发词：金融题 / 金融题包 / skill 专项题 / workflow 题 / weakness 题 / W1–W14 / C1–C5 / 定向构造。

**不适用**：法律领域题（→ `../../harbor-legal/SKILL.md`）、Windows Coding 题（→ `harbor-windows`）、
内部 RL 题包（→ `harbor-16`）。

---

## 一批 = 2000 条，两块结构

| 块 | 条数 | 选题依据 | 构造细则 |
|---|---|---|---|
| **专项数据** | **1000** | 从**能力维度**出发，追求系统完整覆盖 | `references/02`–`05` |
| **Weakness-driven** | **1000** | 从**已观测缺陷**出发，追求稳定复现 | `references/06`–`08` |

### 路由表

| 二级类型 | 条数 | 参考文件 |
|---|---|---|
| Skill Discovery | 200 | `references/02-skill-discovery.md` |
| Skill Generation / Editing | 200 | `references/03-skill-authoring.md` |
| Skill Dependency | 200 | `references/04-skill-dependency.md` |
| Dependency-aware Workflow | 200 | `references/05-workflow.md` |
| Subagent Workflow | 200 | `references/05-workflow.md` |
| MCP Scaling（低优） | 机动 | `references/05-workflow.md` |
| Weakness W1–W14 | 1000 | `references/06-weakness-catalog.md` + `08-design-and-rubric.md` |
| 复杂度 C1–C5 判定 | — | `references/07-complexity-scales.md` |
| 领域/配额/metadata 总纲 | — | `references/01-taxonomy-and-quota.md` |

---

## 配额速查

| 维度 | 要求 |
|---|---|
| 领域分布 | 金融下**均匀分布**；**不接受一个知识点 / workflow 出题 ≥ 3 道** |
| 难度 | A1 20% / A2 60% / A3 20%（按三模型平均正确率归级，区间不重叠） |
| 复杂度（weakness 1000 条） | C1 120 / C2 250 / C3 350 / C4 180 / C5 100 |
| weakness 覆盖 | 覆盖**全部 14 种**；每种**≥50 且 ≤250** 条；每条标 **≥1** 个 |
| metadata | `skill_set` / `task_complexity` / `expected_skill_dependencies` / `weakness_tag` 四项齐全 |

---

## 端到端流程

```
① 查台账（知识点分布 + weakness 覆盖进度） → ② 定类型（专项 or weakness）
→ ③ 选定场景（金融业务动作，真实可落地） → ④ 按 C 级定复杂度与规模
→ ⑤ 构造 environment（源文件 / skills / 埋点） → ⑥ 写 instruction.md
→ ⑦ 产出 golden（规避缺陷 / 满足全部正分项） → ⑧ 设计 rubric（含负向与分档）
→ ⑨ 填写 metadata（含 weakness_tag） → ⑩ 交付自检（`delivery/` G1–G6 + 本型专项自检）
```

### ① 查台账

两张台账在出题前必查，否则必然违反分布约束：

| 台账 | 登记项 | 约束 |
|---|---|---|
| 知识点台账 | 细分知识点 / 业务动作 | 同一细分点 **≤2 道** |
| weakness 台账 | `task_id, C级, tag1..tag3` | 每种 weakness **∈ [50, 250]** |

### ②③ 定类型与场景

- 场景必须是**金融真实业务动作**（财报分析、估值建模、对账勾稽、尽调、投研、风控、合规审阅等）；
- 交付物须为**该场景下真实会产出的文件**（Excel 模型、投资 memo、尽调清单、对账差异表）；
- 禁止"为构造而构造"的伪场景（如"请在 100 个 CSV 中找数字 7"）。

### ④ 定复杂度

按 `references/07-complexity-scales.md` 的六项硬指标逐项对齐：文件数 / Requirement 数 / 产物数 /
Evidence Chain / 执行步数 / 工具种类。**六项大多同档 → 取该档；跨档取众数**。

### ⑤ 构造 environment

- 专项题：`environment/skills/<name>/` 装入功能型 skill（`SKILL.md` + `scripts/` + `references/`），
  Dockerfile 中 `COPY skills/ /skills/`；skill 须与 `skill_set` **逐一对应**；
- weakness 题：埋点落在数据 / 目录结构 / 跨源冲突上，须满足**可发现 · 稳定复现 · 不可提示**三要素；
- 脱敏规则同法律领域 → `../../harbor-legal/references/02-input-files.md`。

### ⑥ 写 instruction.md

- `skill_set` 非空的题：按 `references/02` / `references/04` 的写法**显式指明技能入口**，
  但**不得**泄漏埋点（不写"注意数据中有重复记录"）；
- 要求项数量与交付物数量按 C 级设定（同时是 difficulty-control 旋钮）。

### ⑦⑧ golden 与 rubric

golden 必须**满足全部正分项、不命中任何 negate 条目**，且主分 > 0.85。
rubric 见 `references/08-design-and-rubric.md`（四种写法 + 每个 weakness 的判分抓手 + 常见错误对照）。

### ⑨ metadata

```toml
[metadata]
skill_set                   = ["approval-workflow"]   # 或 []
task_complexity             = "C3"
expected_skill_dependencies = ["approval-workflow"]   # skill_set 的子集
weakness_tag                = ["W07-长表格数据覆盖"]
```

| 类型 | `skill_set` vs `expected_skill_dependencies` |
|---|---|
| Skill Discovery | 前者含干扰项，后者**严格小于**前者 |
| Skill Dependency | 后者**非空**且等于关键 skill |
| 其余 | 视构造需要填写，可为空数组 |

### ⑩ 交付自检

跑 `delivery/` G1–G6 与 17 项自检（`G1–G6` 为归纳编号，规范原文无此编号），**外加**：

| # | 本型专项自检 |
|---|---|
| 1 | 每条 `weakness_tag` 在题面 / environment 中有对应 trigger |
| 2 | 每条 `weakness_tag` 在 rubric 中有对应判定项 |
| 3 | `task_complexity` 与六项硬指标一致 |
| 4 | 批次内该 weakness 计数 ∈ [50, 250] |
| 5 | golden 已正确规避该缺陷 |
| 6 | instruction 无任何提示性措辞（检索禁词表） |
| 7 | 同一知识点出题数 ≤2 |

---

## difficulty-control 维度（本批价值所在）

> **观测**：Qwen 在"要求项更多、交付物更多、跨应用更多"的 hard query 上，
> 思考与工具调用**没有随难度增加，甚至有所下降**，明显弱于其他模型；Opus 会相应增加执行与验收投入。

因此把三项作为**显式难度旋钮**（与 C 级指标对齐）：

| 旋钮 | C1 | C5 |
|---|---|---|
| 要求项数 | 3 | 20 |
| 交付物数 | 1–2 | 4–8 |
| 跨应用 / 跨工具数 | 1 | 5+ |

**预期模型表现分化即来源于此**——这是该批次的核心价值，构题时应有意识地在三项上加压。

---

## 反模式（禁止）

1. 同一知识点 / workflow 出题 **≥3 道**（违反均匀分布）。
2. 某种 weakness 覆盖数 **<50 或 >250**（违反批次约束）。
3. `weakness_tag` 与埋点 / rubric 不对应（硬凑覆盖数）。
4. Skill Discovery 题的 `expected_skill_dependencies` 等于 `skill_set`（退化成无干扰项）。
5. Skill Dependency 题的 `expected_skill_dependencies` 为空（删掉 skill 也能做对 → 不是依赖题）。
6. Skill 只是"辅助信息"而非完成任务所必需（违反 scaling 初衷）。
7. `task_complexity` 凭感觉填，与六项硬指标不符。
8. 缺陷**不能稳定复现**（只是偶发）。
9. 埋点**不可发现**（再正确的模型也避不开）→ 变成无解题。
10. 埋点在 instruction 中被提示。
11. 用降低可读性 / 注入无意义噪声冒充难度。
12. 伪场景（无真实业务价值，纯为凑数据规模）。
13. 交付元数据缺项（尤其 `skill_set` 与实际目录不一致）。
14. 违反 `delivery/` 的任一硬约束（权重档位、`name` 与 `id` 一致、likert 档位锚点、`network_mode = "public"` 等）。

---

## 交付实现（`delivery/`）

本 skill **自包含**交付规范（原独立 skill `harbor-rewardkit` 已内联至此），无需外部依赖。

| 文件 | 内容 |
|---|---|
| `delivery/00-delivery-standard.md` | 交付标准总纲：与 `harbor-sota` 的口径差异、G1–G6 六道门、13 步端到端流程、judge 可靠性契约、反模式 |
| `delivery/01-bundle-structure.md` | 题包结构、组件清单、容器内路径与可见性、资源上限 |
| `delivery/02-task-toml.md` | task.toml schema 1.4 完整模板、逐字段说明（含本专项必填的 `skill_set` / `tool_set` / `task_complexity` / `weakness_tag` 等）、`deliverables` 命名规则 |
| `delivery/03-rubrics-and-prompt.md` | rubrics.toml 字段约束、权重档位、likert 锚点、prompt.md 六规则、维度体系 |
| `delivery/04-package-and-checklist.md` | 打包命名、提交前 17 项自检、交付文档与环境变量模板 |
| `delivery/05-environment-and-solve.md` | Dockerfile 完整模板、镜像硬性要求与自检、`solution/solve.sh` |
| `delivery/06-model-validation.md` | 三模型难度验证流程、等级区间、跑分轨迹留档 |
| `delivery/07-pitfalls.md` | 高频故障与踩坑录（含"静默 0 分"成因与排查） |
| `delivery/08-skill-packaging.md` | `environment/skills/` 技能包封装规范（**Skill Discovery / Dependency / Authoring 三类必读**） |
| `delivery/templates/` | 平台固定模板 `test.sh` / `finalize.py`（**逐字复制**，不得改写） |
| `delivery/assets/` | task.toml / rubrics.toml / prompt.md / Dockerfile / rubrics.json 起手模板 |

### 出题态与交付态的分工（勿混用）

| 层面 | 归 `references/` | 归 `delivery/` |
|---|---|---|
| 选题、场景、埋点、干扰项设计 | ✔ | |
| `weakness_tag` ↔ 埋点 ↔ 判分三方对应 | ✔ | |
| 五件套目录结构与命名 | | ✔ |
| task.toml 字段书写顺序与白名单 | | ✔ |
| rubrics.toml 权重档位 / likert 锚点 / `negate` 写法 | | ✔ |
| 打包、17 项自检、跑分归档 | | ✔ |

> **口径一致性提醒**：`harbor-sota` 使用旧版 v4 规范（`judge.toml` + `gating.toml`），
> 与本次 rewardkit 20260913（`rubrics.toml` + `prompt.md` + claude-code agent judge）
> **结构不同、不得混用**。同一批次内不可两种口径并存。

## 参考文件索引

| 文件 | 内容 |
|---|---|
| `references/01-taxonomy-and-quota.md` | 领域范围与分布约束、两大数据块、5 类专项、A1–A3 与 C1–C5 配额、metadata 四字段规范、完整 task.toml 模板、验收口径 |
| `references/02-skill-discovery.md` | Skill Discovery：三子场景、干扰技能构造法、难度旋钮、技能入口写法与禁止写法、D1/D2/D3 判分抓手 |
| `references/03-skill-authoring.md` | Skill Generation / Editing：S1–S5 五类任务、输入材料设计、缺陷类型库、验收要素与 rubric |
| `references/04-skill-dependency.md` | Skill Dependency：三类范式（冲突暂停 / 环境特化 SOP / 特殊计算口径）、强弱依赖分级、判据"删掉 skill 能否做对" |
| `references/05-workflow.md` | Dependency-aware Workflow（依赖拆解与状态记账）与 Subagent Workflow（信息切分、结果回收）、MCP Scaling 要点 |
| `references/06-weakness-catalog.md` | W1–W14 全量表：典型行为 / 具体 case / 推荐构造方式 / rubric 设计 |
| `references/07-complexity-scales.md` | C1–C5 六项硬指标分级表、判定方法、题量配比、覆盖统计脚本 |
| `references/08-design-and-rubric.md` | 埋点三要素与强度分级、`weakness_tag` 标注与三方对应矩阵、rubric 四形态实例、专项自检脚本 |
| `delivery/00-delivery-standard.md` | 交付底座（与 harbor-sota 的口径差异、G1–G6、13 步流程、反模式） |
| `delivery/03-rubrics-and-prompt.md` | rubrics.toml / prompt.md 通用规则与评分机制 |
| `delivery/06-model-validation.md` | 三模型难度验证流程与等级区间 |
| `delivery/08-skill-packaging.md` | skill 打包进 `environment/skills/` 的目录规范与自检 |
| `../../harbor-legal/references/02-input-files.md` | 脱敏规则（W14 与全部金融题共用） |
