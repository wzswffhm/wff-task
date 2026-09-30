# 三份规范题型判定、端到端流程与 skill 规划

> 本文是三份材料的**汇总结论**。三份材料的独立解析笔记分别见：
> - `../2026-09-30_RL0-1-数据生产规范Guideline for外部供应商（法/解析笔记.md`
> - `../2026-09-30_基于weakness和skill 的数据构造方案（金融/解析笔记.md`
> - `./解析笔记.md`（rewardkit 交付规范）

---

## 一、三份规范的分工

| 文件 | 角色 | 回答什么 |
|---|---|---|
| RL0-1-数据生产规范（法律） | **出题设计层（法律）** | 出什么领域/标签的题、三个核心组成、打分项设计、难度分级 |
| 基于 weakness 和 skill 的数据构造方案（金融） | **出题设计层（金融）** | 出哪几类构造题型、每类怎么构造、C1–C5 复杂度、14 种 weakness |
| 评测题包交付规范（rewardkit）20260913 | **交付实现层（通用）** | 五件套、task.toml、rubrics.toml、prompt.md、判分链路、验收标准、打包 |

**组合关系**：后两份文件均明确要求「须与 rewardkit 交付规范组合使用」。出题设计层产出**内容**，交付层负责**封装与判分**。

---

## 二、需要做的题型（7 类）

判定依据：文件 2 §3「专项数据」一级/二级表（5 类）+ §4「Weakness-driven 数据」（1 类）+ 文件 1 法律领域常规题（1 类）。

| # | 题型 | 规范出处 | 数量/占比 | 核心构造特征 |
|---|---|---|---|---|
| 1 | **常规办公场景题（法律）** | 文件1 §2–§7 | 本批法律题按 A1 20% / A2 60% / A3 20% | 无 skill 依赖；真实法律办公场景；Law1–Law6 均匀覆盖；三/四级标签自补；无任何三级标签超过 2 道 |
| 2 | **Skill Discovery** | 文件2 §3.2 | 200（专项 20%） | 环境装**多个 skill（含干扰项）**；模型自行判断是否需要 skill、该用哪个；`expected_skill_dependencies` 必须是 `skill_set` 的**真子集** |
| 3 | **Skill Generation / Editing** | 文件2 §3.2 | 200 | 创建 skill / 修改已有 skill / 从 SOP 抽取 skill / skill migration / skill package repair |
| 4 | **Skill Dependency** | 文件2 §3.2 | 200 | 缺 skill 特有知识必错。三类：① 冲突必须暂停问用户；② 环境特化 SOP（少一步状态即失败）；③ 特殊阈值/映射/优先级/fallback 直接决定 final answer |
| 5 | **Workflow Execution** | 文件2 §3.3 | 200 + 200 | **Dependency-aware**：A→B、A→C、B+C→D、D→Final 的依赖拆解与状态维护；**Subagent**：必须回收多个异步子代理结果才能完成 Final |
| 6 | **Weakness-driven** | 文件2 §4 | 1000（占全批 50%） | 14 种 weakness（W1–W14）定向埋点，**标的 tag 必须在题面/environment 有能稳定诱发该弱点的设计点**；复杂度 C1–C5 |
| 7 | **MCP Scaling（低优）** | 文件2 §3.2 末 | 低优 | 非原生工具、陌生 Tool Schema、不同 Tool 组合下的泛化；须在题中显式提供可用工具集合/MCP |

### 2.1 复杂度分层（全题型共用，用于 metadata.task_complexity）

| 指标 | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| 文件数 | 2 | 5 | 10 | 25 | 50+ |
| Requirement 数 | 3 | 6 | 10 | 15 | 20 |
| 输出产物数 | 1-2 | 2-3 | 3-4 | 4-6 | 4-8 |
| Evidence Chain | 1-hop | 2-hop | 3-hop | 4-hop | 5-hop |
| 执行步数 / 子任务 | 1–3 / 1 | 4–7 / 2–3 | 8–15 / 4–6 | 16–30 / 7–10 | 30+ / 10+ |
| 工具种类数 | 1 | 2 | 3 | 4 | 5+ |
| **题量占比** | **12%** | **25%** | **35%** | **18%** | **10%** |

---

## 三、端到端流程

```
① 选题与定级 → ② 设计环境与源文件 → ③ 写 instruction.md → ④ 造 environment/skills/（Skill 类题）
→ ⑤ 产出 solution/golden_output/ → ⑥ 写 task.toml + rubrics.json → ⑦ 写 tests/rubrics.toml + prompt.md
→ ⑧ 复制固定模板 test.sh / finalize.py → ⑨ 镜像构建与自检 → ⑩ golden 预检（Oracle）
→ ⑪ 三模型跑分与难度验证 → ⑫ 打包提交前 17 项自检 → ⑬ 打包提交
```

| 步骤 | 关键动作 | 产出 |
|---|---|---|
| ① 选题与定级 | 从真实付费办公场景选题；按三模型预估正确率定 A1/A2/A3；定 `task_complexity` C1–C5；定 `weakness_tag`（≥1，与实埋 trigger 一一对应） | 选题卡 + metadata 草案 |
| ② 设计环境与源文件 | 真实输入材料（CSV/PDF/合同/日志/年报…），脱敏；总大小 ≤20 GB（计入整批） | `environment/input_files/` |
| ③ 写 instruction.md | 场景+角色、源文件表、交付物表、硬约束独立段落；源路径 `/app/input_files/`、交付路径 `/app/output/`；有 skill 时列明技能名+绝对路径 | `instruction.md` |
| ④ 造 skills/ | Skill 类题必需：`SKILL.md`（frontmatter + SOP）+ `scripts/` + `references/`；instruction 中显式要求"通过该 skill 完成，禁止其它方式" | `environment/skills/<name>/` |
| ⑤ 产出参考答案 | 与 deliverable 文件名/格式/数量严格一致 | `solution/golden_output/`、`tests/__golden_output/` |
| ⑥ task.toml + rubrics.json | schema 1.4 全字段；`artifacts` 由 deliverables 机械展开 | `task.toml`、`rubrics.json` |
| ⑦ rubrics.toml + prompt.md | judge=claude-code、model=qwen3.7-plus、mode=individual、timeout=7200；criterion 用 binary/likert，weights ∈ {3,7,10}，negate 表达扣分 | `tests/rubrics.toml`、`tests/prompt.md` |
| ⑧ 固定模板 | **逐字复制、含注释、不得改动** | `tests/test.sh`、`tests/finalize.py` |
| ⑨ 镜像构建与自检 | Dockerfile 官方源、claude-code 2.1.114、harbor-rewardkit==0.1.7 | 自检末行 `OK` |
| ⑩ golden 预检 | `harbor run -p <题> -a oracle` | 主分 > 0.85 且 `verifier_error=0` |
| ⑪ 三模型跑分 | Claude code 框架，三模型各 1 次，裁判 qwen3.7-plus | 跑分轨迹 + 均分记录 |
| ⑫ 提交前自检 | 17 项清单 | 自检报告 |
| ⑬ 打包提交 | 批次→题目→五件套；zip 命名规范 | zip + `交付文档.md` |

---

## 四、验证流程（重点）

> **编号说明**：下文的 `G1–G6` 是本规划文档与 skill 为便于索引而**归纳的门禁编号**。
> 规范原文（rewardkit §7「验收标准」+ §8「打包与提交」）**未使用该编号体系**，引用时须注明"归纳编号"。

### 4.1 G1–G4 门禁（按顺序，任一不过禁止提交）

| 门 | 内容 | 通过标准 | 工具/方式 |
|---|---|---|---|
| **G1 结构门** | 五件套齐全 + 固定模板未被改动 + requirements.txt 空文件也交 + solve.sh/test.sh LF 且带可执行位 | 结构完整 | 目录与文件检查 |
| **G2 内容门** | 交付物文件名**六处逐字节一致**（instruction.md / deliverables.path / artifacts / solution/golden_output / tests/__golden_output / criterion description）；task_id 三处一致；无真实密钥 | 一致 | 逐字节比对 |
| **G3 评分器门** | `weight` 仅 3.0/7.0/10.0、无负 weight；`type` 仅 binary/likert；likert 均显式 `points = 5` 且 description 含 5/4/3/2/1 锚点；每条 criterion 有 `name` 且等于 `id`；description 含 `Deliverables to inspect:` 路径清单；`prompt.md` 含 `{criteria}` 且 prompt + 全部 description < 100 KB；Critically Important ≥2 条；内容质量维度正分 ≥30%；"总是需要"维度已覆盖 | 全部满足 | rubrics.toml 解析脚本 |
| **G4 判分门（实测）** | ① **golden 预检**：`harbor run -p <题> -a oracle` → 主分 **> 0.85**，`verifier_error = 0`；② 镜像自检末行 `OK`（含 `claude --version` 含 2.1.114）；③ 人为制造失败（清空 `JUDGE_API_KEY`）时 `reward_exit_message.json` 出现且 `exit_code` 归类正确 | 实测通过 | harbor CLI + docker |

### 4.2 难度验证门（模型验收，G5）

- **框架**：Claude code
- **待测模型**：`gpt-5.6-sol`、`claude-opus-4-8`、`qwen3.8-max0902`
- **裁判模型**：`qwen3.7-plus`
- **跑法**：满分归一化为 1.0，**每种模型跑 1 次**，取三模型平均分
- **通过标准**：
  - 三模型平均分 **< 0.7**；
  - 且**至少有一个模型有得分**（防全 0 死题）；
  - 按难度等级核对区间：**A1 ∈ [0.6, 0.7)、A2 ∈ [0.5, 0.6)、A3 < 0.5**；
  - 参考答案得分 **> 0.85**。
- **留档要求**：提交题目文件时须**同步提供模型产物和跑分轨迹**。
- **注意**：难度未达标应重做题目或调整定级，**不得伪装跑分**。

### 4.3 人工质检与 AI 机检（**由领域规范要求，不属 G 编号体系**）

人工质检重点考察：**题目真实性、参考答案合理性、打分项设计合理性、是否 hack 等异常作弊**——一经发现**直接打回**。
另有 AI 机检：AI 质检题目质量 / 打分项生成 / AI 质检打分项质量 / AI 总分检查（同 G5 指标）。

### 4.4 判分链路可靠性契约（防"静默 0 分"）

| 契约 | 语义 |
|---|---|
| `reward.json.reward` | 主分；**评分不可用时刻意记 0** |
| `reward.json.verifier_error` | **1 = 本次评分不可信**（判官限额/超时/评分器异常）→ 平台应**重评**，而非记零分 |
| `reward.txt` | 单一数值，与 `reward.json` 的 reward 一致 |
| `reward-details.json` | 逐条明细（审计件），缺失不影响主分 |
| `reward_exit_message.json` | **仅评分不可用时存在**（`judge:timeout` / `judge:api_error` / `judge:parse_error` / `judge:scorer_error` / `judge:invalid_output` / `judge:unknown`） |

> 计分公式：`S_max = Σ正向 weight`；`分子 = Σ正向 weight×value − Σ负向 weight×(1−value)`；`reward = clip(分子/S_max, 0, 1)`。**负向不进分母**。

---

## 五、需要的模型与工具链

### 5.1 模型清单

| 角色 | 模型 | 用途 | 备注 |
|---|---|---|---|
| 待测模型 A | `gpt-5.6-sol` | 难度验证 | Claude code 框架下运行 |
| 待测模型 B | `claude-opus-4-8` | 难度验证 | 同上 |
| 待测模型 C | `qwen3.8-max0902` | 难度验证 | 同上 |
| **裁判模型** | **`qwen3.7-plus`** | 打分（judge） | `rubrics.toml` 的 `[judge].model`；运行时由 `JUDGE_MODEL` → `REWARDKIT_MODEL` 覆盖 |

### 5.2 工具链

| 组件 | 版本/要求 | 用途 |
|---|---|---|
| `harbor-rewardkit[all]` | `==0.1.7` | 判分框架（verifier 容器内预装） |
| `@anthropic-ai/claude-code` | **钉死 2.1.114** | agent judge（评分行为随 CLI 版本漂移，必须锁版本） |
| 基础镜像 | `python:3.12-slim` | 任务镜像基底 |
| 解析库 | markitdown / openpyxl / python-docx / python-pptx / pypdf / pandas / matplotlib / PyYAML / chardet | judge 读交付物 + 出题侧生成交付物 |
| 系统包 | nodejs/npm、libreoffice-calc/writer、fonts-noto-cjk | claude CLI 运行依赖 + 中文交付物渲染校验 |
| CLI | `harbor run -p <题目目录> -a oracle` / `harbor task update` | 本地预检 + 提交登记 |

### 5.3 环境变量（交付文档须逐条说明）

`JUDGE_API_KEY`（必选）、`JUDGE_BASE_URL`（必选）、`JUDGE_MODEL`（默认 `qwen3.7-plus`）、`JUDGE_PROVIDER`（默认 `anthropic`）、`JUDGE_API_PROTOCOL`（默认 `anthropic`）、`EVAL_API_KEY` / `EVAL_API_BASE`（旧环境兜底、默认空）、`LITELLM_DROP_PARAMS`（默认 `true`）。

> **`JUDGE_*` 只准写在 `[verifier.env]`，严禁写入 `[environment].env`**——judge 凭据进 agent 环境等于把评分通道泄漏给被测模型。
> **超时不可经环境变量配置**：judge 会话超时（`rubrics.toml` `timeout=7200`）与 verifier 总超时（`task.toml` `[verifier].timeout_sec=18000`）只能改 toml 重新交付。

---

## 六、交付标准（速查）

### 6.1 交付物形态

```
<批次目录：供应商名+领域+一级分类+时间>/
├── 交付文档.md            # 环境变量配置说明（必交，放批次根）
├── <题目编号>/            # 一题一目录，目录名 = 题目编号
│   ├── instruction.md
│   ├── task.toml
│   ├── rubrics.json
│   ├── environment/  (Dockerfile + requirements.txt + input_files/ [+ skills/])
│   ├── solution/     (solve.sh + golden_output/)
│   └── tests/        (test.sh + finalize.py + rubrics.toml + prompt.md + __golden_output/ [+ __assets/])
└── ...
```

### 6.2 硬性验收清单（摘要）

| 维度 | 标准 |
|---|---|
| 参考答案 | 主分 **> 0.85**，且未命中任何 negate 条目 |
| 难度 | 三模型平均分 **< 0.7**，至少一个模型有得分；等级区间 A1 0.6~0.7 / A2 0.5~0.6 / A3 <0.5 |
| Rubric | Critically Important ≥2 条；内容质量维度正分 ≥30%；weight ∈ {3,7,10}；无负 weight；likert 全套锚点 |
| 命名一致性 | 交付物文件名六处逐字节一致；task_id 三处一致 |
| 安全 | 题包任何位置无真实密钥/token；`[environment].env` 无凭证与评分信息 |
| 洁净 | 无 `.git/`、`__pycache__/`、`.venv/`、`__MACOSX/`、`.DS_Store`、`reward.json`、`logs/`、`jobs/` |
| 编码 | 全 UTF-8，单文件名 ≤200 字节，禁符号链接；无不可见空白（U+00A0 / U+3000） |
| 体积 | 单题交付物 ≤2 GB；整批 zip ≤20 GB |
| 打包层级 | 批次目录 → 题目目录 → 五件套（不多套一层、不平铺） |
| 命名 | 单题「供应商+领域+一级分类+时间」；批次「供应商+领域+批次+时间」；按领域分别打包 |
| 返修 | `[task].version` 补丁号递增；批次目录名加 `_fix<N>`；供应商代号不变 |

---

## 七、与现有 skill 的关系

| 现有 skill | 关系 | 处理 |
|---|---|---|
| `harbor-sota` | **同族但不同代**：它按《外发版-评测题包交付规范 v4》（20260808）出题，评分器是 `tests/graded/judge.toml` + `tests/gating/gating.toml`（Judge 模型 + all_pass 一票否决）、参考答案在 `tests/golden_output/`、验收为 Oracle≥0.7 + 空产物≤0.10 | **不改动**；作为范式参考（主文件 + references 按需加载的结构、反模式清单、checklist 写法） |
| `harbor-windows` | 同为「主 SKILL.md + references + scripts + assets」的高质量范式 | **不改动**；参考其「三条底线 / 端到端流程 / 常见陷阱 / 一票否决 / 参考文件索引」的组织方式 |
| `harbor-16` | 内部 RL 题包（pytest 程序化评分） | **不改动**；仅确认不混用口径 |
| 本批新建 | 按 7 类题型新建对应出题 skill + 1 个公共交付底座 | 见下节 |

> **不得混用**：`harbor-sota`（v4 / judge.toml + gating.toml）与本次 rewardkit 20260913（rubrics.toml + prompt.md + agent judge）**评分体系与文件结构不同**，同一批次内不可混用。

---

## 八、新建 skill 清单（2 个）

**收敛原则**：skill 的粒度对齐**规范文件**，而非对齐题型细分，**且不为交付标准单设 skill**。

三份规范中，两份是「生成题包的要求」（各一个领域），一份是「交付标准」——
故落为 **2 个题型 skill**，交付标准作为 `delivery/` 子目录**内联进两个 skill**，使每个 skill **自包含**。

| # | skill | 对应规范 | 定位 |
|---|---|---|---|
| 1 | `harbor-legal` | 文件1《RL0-1 数据生产规范（法律）》 | **题型 skill ①**：法律领域常规办公题。Law1–Law6 分布、三/四级标签、法律专业维度打分项 |
| 2 | `harbor-finance` | 文件2《基于 weakness 和 skill 的数据构造方案（金融）》 | **题型 skill ②**：金融领域。内含两块共 2000 条——专项数据 1000 条（Skill Discovery / Skill Generation·Editing / Skill Dependency / Dependency-aware Workflow / Subagent Workflow / MCP Scaling）+ Weakness-driven 1000 条（W1–W14 × C1–C5） |

### 8.1 题型 → skill 的承载映射

| 题型（§二） | 承载 skill | 参考文件 |
|---|---|---|
| 1 常规办公题（法律） | `harbor-legal` | `references/01`–`03` |
| 2 Skill Discovery | `harbor-finance` | `references/02-skill-discovery.md` |
| 3 Skill Generation / Editing | `harbor-finance` | `references/03-skill-authoring.md` |
| 4 Skill Dependency | `harbor-finance` | `references/04-skill-dependency.md` |
| 5 Workflow Execution（Dependency-aware + Subagent） | `harbor-finance` | `references/05-workflow.md` |
| 6 Weakness-driven（W1–W14） | `harbor-finance` | `references/06`–`08` |
| 7 MCP Scaling（低优） | `harbor-finance` | `references/05-workflow.md` §MCP |

### 8.2 交付标准的内联（不单设 skill）

`delivery/` 在两个 skill 下**各存一份、内容完全一致**（校验：`diff -r skills/harbor-legal/delivery skills/harbor-finance/delivery`）：

| 文件 | 内容 |
|---|---|
| `delivery/00-delivery-standard.md` | 交付标准总纲（原独立 skill 正文）：与 `harbor-sota` 的口径差异、G1–G6、13 步流程、judge 可靠性契约、反模式 |
| `delivery/01`–`08` | 题包结构 / task.toml 1.4 / rubrics.toml+prompt.md / 打包自检 / 环境与 solve / 模型验证 / 踩坑录 / 技能包封装 |
| `delivery/templates/` | 平台固定模板 `test.sh`、`finalize.py`（逐字复制） |
| `delivery/assets/` | task.toml、rubrics.toml、prompt.md、Dockerfile、rubrics.json 起手模板 |

**分工**：`references/` = 出题设计（选题、场景、埋点、判分抓手）；`delivery/` = 交付实现（格式、判分链路、打包、验收）。
两个 skill 内部均**不重复**对方内容——两者各自完整。

> **维护约定**：`delivery/` 为**同源双份**，规范更新时须同步修改两处；
> 每次改完跑一次 `diff -r` 校验，不一致即视为未完成。

> **注册方式**：`~/.workbuddy/skills/` 下 2 个条目均为指向 `wff-task/skills/<name>` 的目录联结（junction），
> 单一事实源在仓库内，改仓库文件即改用户级 skill。


