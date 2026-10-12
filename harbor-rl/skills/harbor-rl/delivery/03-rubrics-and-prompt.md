# rubrics.toml 与 prompt.md 编写规则

## 1. 判分链路（必须理解，否则写不对 rubric）

- 判官是 **claude-code agent judge**：以 CLI 进程跑在 verifier 容器内，**自己用 Bash 工具读交付物**（不再由 Reward Kit 预读文件塞进 prompt）。
- **每条 criterion 单独起 1 个 judge 会话独立评分**（`mode = "individual"`，逐条串行）。
- cwd = `/app`；`input_files/`、`output/` 同级可见；`tests/` 挂到 `/tests`（含 `__golden_output/`）。
- 供应商负责 `rubrics.toml` 与 `prompt.md` 的**内容**；聚合由 `finalize.py` 全题池化，供应商**不自行聚合**。

## 2. rubrics.toml 模板

```toml
[judge]
judge = "claude-code"          # 固定值，判官类型
prompt_template = "prompt.md"  # 固定值，指向同目录 prompt.md
model = "qwen3.7-plus"         # 裁判模型，照抄
timeout = 7200                 # 单个 judge 会话（individual 模式下 = 每条 criterion 一个会话）超时秒数
mode = "individual"            # 每条评分点独立评分
weight = 1.0                   # 固定值，照抄

[[criterion]]
id = "R1"
name = "R1"
description = "报告计算出近三年毛利率为 68%（±0.5pp），并标注同比变动方向为正。 Deliverables to inspect: `output/FIN-T2-001_财务分析报告.xlsx`."
type = "binary"
weight = 10.0

[[criterion]]
id = "R3"
name = "R3"
description = "给出结论但缺少对应的数据支撑（表格引用或可追溯的计算过程）。评分为 1–5 整数，按违规程度判定（negate 条目，Reward Kit 归一化后自动翻转计分）：5=绝大多数结论无任何数据支撑；4=超过半数结论缺少数据支撑；3=约半数结论缺少数据支撑；2=仅个别结论缺少数据支撑；1=所有结论均有表格引用或可追溯的计算过程。 Deliverables to inspect: `output/FIN-T2-001_财务分析报告.xlsx`."
type = "likert"
points = 5
negate = true
weight = 7.0

[scoring]
aggregation = "weighted_mean"
```

## 3. 字段约束

| 字段 | 约束 |
|---|---|
| `[judge].judge` | 固定 `"claude-code"` |
| `[judge].model` | 合法 LiteLLM 模型串，按示例照抄（`"qwen3.7-plus"`）。运行时被 `REWARDKIT_MODEL`（test.sh 由 `JUDGE_MODEL` 派生）覆盖，toml 值是**无注入时的兜底** |
| `[judge].prompt_template` | 固定 `"prompt.md"`，指向同目录提示词文件 |
| `[judge].timeout` | **单个 judge 会话的超时秒数。缺省仅 300，必须显式写 7200** —— agent judge 要反复调 Bash 读文件，远慢于一次性调用；会话超时不写 reward.json，**整题无分**。且须 < `[verifier].timeout_sec`（18000） |
| `[judge].weight` | 固定 `1.0` 照抄。不参与主分，只影响 Reward Kit 审计值 |
| `[judge].mode` | **必写 `"individual"`**：每条 criterion 单独起一个 judge 会话评分（逐条串行） |
| `[scoring].aggregation` | 固定 `"weighted_mean"` |
| `[[criterion]].id` | 必填，题内唯一，`rubrics.json` 中对应条目的编号保持一致，便于人工追溯 |
| `[[criterion]].name` | 必填，**恒等于 `id`** |
| `[[criterion]].description` | 单条可独立判定的标准 + 待查交付物路径清单；likert 条目还须含各档位锚点 |
| `[[criterion]].type` | 只允许 `binary` 和 `likert`；likert 时 judge 输出 **1–5 整数**（配合 `points = 5`），必须在 description 按该标度写档位锚点 |
| `[[criterion]].points` | likert 必填，**固定写 5**（统一 5 档，锚点恒为 5/4/3/2/1）。不显式写时 Reward Kit 也按 5 处理，但**必须写出**，防止误设其它档数导致锚点与标度错位 |
| `[[criterion]].weight` | 只允许 **`3.0` / `7.0` / `10.0`** |
| `[[criterion]].negate` | `true` = 该条描述"候选犯了什么错"；判官判"存在"得 0、"不存在"得 1 |

### 权重档位 ↔ 重要级别

| 级别 | 原分数 | 写法 | 落点 |
|---|---|---|---|
| Critically Important | +10 | `weight = 10.0 + type` | rubrics.toml |
| Important | +7 | `weight = 7.0 + type` | rubrics.toml |
| Slightly Important | +3 | `weight = 3.0 + type` | rubrics.toml |
| Slightly Detrimental | −3 | `weight = 3.0 + negate = true` | rubrics.toml |
| Detrimental | −7 | `weight = 7.0 + negate = true` | rubrics.toml |
| Critically Detrimental | −10 | `weight = 10.0 + negate = true` | rubrics.toml |

> **扣分只能 `negate = true` + 正 weight，绝不能写负数 weight**——负 weight 条目会被平台聚合脚本判为异常剔除并记评分不可用（`verifier_error = 1`），扣分静默失效、**整次评分作废重评**。

## 4. 三条硬性写法（缺一即整题判分崩溃 / 静默 0 分 / 档位漂移）

1. 每条 criterion **必须写 `name = "<id>"`**（与 `id` 相同）。
   不写时 `name` 由 `description` 自动 slugify，**纯中文 description 会生成空串**，全部条目键塌缩 → Reward Kit 解析崩溃。
2. `description` 里**必须写明待查交付物的完整路径**（`Deliverables to inspect:` 清单，路径形如 `output/<文件名>`）。
3. `type = "likert"` 的条目，**必须显式写 `points = 5`** 且在 description 里写明档位锚点。
   judge 被要求输出 1 到 5 的整数，锚点按 **5/4/3/2/1** 逐档写明对应的具体情形。
   不给锚点，judge 的中间档位给分**不可复现、不可审计**；锚点写成 0–1 小数则会被输出 schema（integer）拒掉。

### likert 方向约定

| 条目性质 | 锚点方向 | 示例 |
|---|---|---|
| 正向条目 | 按**满足程度**写：5 = 完全满足 … 1 = 完全不满 | `5=WACC 落在 [10%,12%] 区间内；4=偏离合理区间不超过 ±1%；3=偏离 ±1%–±3%；2=偏离 ±3%–±5%；1=WACC 完全未给出，或偏离超过 ±5%` |
| `negate = true` 条目 | 按**违规程度**写：5 = 违规完全成立（归一化后计 0 分）；1 = 完全无违规（翻转后满分） | `5=绝大多数结论无任何数据支撑；…；1=所有结论均有表格引用或可追溯的计算过程` |

**数值算例**（`points = 5`、`weight = 7.0`）：正向条 raw 5/4/3/2/1 → 计入 `+7 / +5.25 / +3.5 / +1.75 / +0`；negate 条按违规程度 raw 5/4/3/2/1 → 扣 `7 / 5.25 / 3.5 / 1.75 / 0`。

> **负向条目优先用 `binary`**：违规通常"成立/不成立"没有中间态，且负向多档在现网无生产先例、判官一致性缺少验证；确需按违规程度分档扣分时才用 `likert`（如上例 R3），并把每一档写到**可独立核验**。

## 5. criterion 语义字段（写进 rubrics.json，指导 rubric 设计）

| 字段 | 取值 | 含义 |
|---|---|---|
| `criterion_type` | `Objective` / `Subjective` | Objective = 可度量、可验证，仅凭回答本身即可明确判定；Subjective = 需要打分员的判断与语境解读（语气/质量/风格，或对某理由、断言、示例是否成立的判断） |
| `criterion_necessity` | `Explicit` / `Implicit` | Explicit = 在 prompt 中逐字明文给出的要求；Implicit = 没有明说但从语境中必然推导出的要求 |
| `type`（设计态） | `Binary` / `Gradient` | Binary = 答案要么满足要么不满足，中间状态无意义；Gradient = 存在程度差异且对最终质量有意义（**对应 harbor 的 `likert`**） |
| `weight`（设计态） | `{+10, +7, +3, −3, −7, −10}` | 不能取任何其他值。**不接受恶意负分、故意增加题目难度/降低分数的行为** |
| `dimension` | 见 §7 | 打分项所属评价维度 |

> **⚠️ `levels` 的键是「比例键」`1 / 0.75 / 0.5 / 0.25 / 0`，绝不是判官侧整数 `5 / 4 / 3 / 2 / 1`。**
> 设计态 `rubrics.json` 与运行态 `rubrics.toml` 是**两套标度**，最容易在这里写错：
>
> | 文件 | 标度 | 写法 |
> |---|---|---|
> | `rubrics.json`（设计态） | **比例键** `1 / 0.75 / 0.5 / 0.25 / 0` | `"levels": {"1": …, "0.75": …, "0.5": …, "0.25": …, "0": …}`，`1` = 完全满足、`0` = 完全不满足 |
> | `tests/rubrics.toml`（运行态） | **整数** `5 / 4 / 3 / 2 / 1` | `type = "likert"` + `points = 5`，五档锚点写进 `description`（judge 输出 1–5 整数） |
>
> 映射关系 `比例键 → 1 + 4 × 比例键`（`1→5`、`0.75→4`、`0.5→3`、`0.25→2`、`0→1`），**锚点文本顺序不变**。
> 用整数 `1`–`5` 当 `levels` 键会被 package validator / preflight 判 **FAIL**（键集必须恰为 `{0, 0.25, 0.5, 0.75, 1}`）；
> `levels` 只写成键名列表（无锚点文本）同样不合法，必须是「键 → 锚点文本」的对象。
> **`negate = true` 条目用同一键集**：键 `1` 对应判官 `5` = 违规完全成立（归一化翻转后计 0 分）；键 `0` 对应判官 `1` = 无违规（翻转后满分）。

**Gradient（likert）设计态示例**：

```json
{
  "id": "R06",
  "description": "DCF 估值模型中使用的 WACC 取值应落在合理区间 [10%, 12%] 内，越接近得分越高",
  "dimension": "内容质量-数值与计算准确性",
  "criterion_type": "Objective",
  "criterion_necessity": "Explicit",
  "type": "gradient",
  "weight": 7.0,
  "levels": {
    "1":    "WACC 落在 [10%, 12%] 区间内",
    "0.75": "WACC 偏离合理区间不超过 ±1%（如 9.0%–9.9% 或 12.1%–13.0%）",
    "0.5":  "WACC 偏离合理区间 ±1%–±3%（如 7.0%–8.9% 或 13.1%–15.0%）",
    "0.25": "WACC 偏离合理区间 ±3%–±5%（如 5.0%–6.9% 或 15.1%–17.0%）",
    "0":    "WACC 完全未给出，或偏离合理区间超过 ±5%"
  }
}
```

> 落到 `rubrics.toml` 时：比例键 `0/0.25/0.5/0.75/1` 映射为 judge 的 `1/2/3/4/5` 整数，并把每一档写进 description。
> 自查：`json.load(rubrics.json)` 后，每个 `type == "gradient"` 条目的 `levels` 键集必须恰为 `{0, 0.25, 0.5, 0.75, 1}`——`check_rubrics.py` 已内置该校验。

## 6. prompt.md 模板（可直接复制，把交付物格式按题目实际情况调整）

```markdown
You are an evaluation judge with filesystem access. Working directory: `/app`.
Evaluate the candidate's deliverables against the criteria at the end of this prompt.

[Material map]
  /app/output/            THE SUBJECT OF EVALUATION — the candidate's deliverables.
                          Only these files can earn or lose points.
  /app/input_files/       Task inputs given to the candidate (read-only). Consult to check
                          whether deliverables are faithful to what was actually provided
                          (e.g. a cited data source really exists; a stated fact is not fabricated).
  /tests/__golden_output/   One acceptable reference solution. See policy below.

[Reference-solution policy]
The reference is for calibration only — expected structure, field naming, magnitude of
numbers. It is NOT an answer key and NOT a diff target. Two hard rules:
  - Never award points because the reference satisfies a criterion. If the candidate's
    file lacks something, it lacks it.
  - Never deduct for differing from the reference. Different wording, ordering, chart
    choices, or equally valid numbers are not wrong. Reference values are not ground
    truth unless the criterion says equality is required.
Where reference and criterion appear to disagree, the criterion wins.

[Tool usage — technical only, does NOT change scoring policy]
Inspect the deliverables however works best: shell commands, Python, any library in this
container. Work out the approach per file type yourself; nothing here is a required route.
`markitdown <path>` is a handy one-step text extractor for .xlsx/.docx/.pptx/.pdf. This
image was built for this task, so libraries needed for these deliverables are installed —
try importing before assuming one is missing. No network access; no Task/Explore subagents.
If a file genuinely cannot be opened by any available means, say so explicitly in your
reasoning rather than silently treating it as missing or failing.

Fairness anchor:
None of the above changes how strictly you judge. Score each criterion exactly as the
rubric prescribes; data extracted with any tool counts the same as reading the original.
If a deliverable referenced by a criterion does not exist, judge per its description
(typically false). Score only `/app/output/` — inputs and reference are evidence, never
the thing being scored.

{criteria}
```

### prompt.md 六条规则

1. **`{criteria}` 占位符必须保留**——Reward Kit 会把 criterion 列表渲染进去，删掉等于 judge 收不到评分项。
2. `Fairness anchor` 段**不要删**、也**不要在 prompt.md 里加任何评分宽严的表述**——工具提示被误读成"放宽判分"会使判分严格度漂移。
3. `Material map` 段**不要删**——judge 的 cwd 是 `/app`，`input_files/` 与 `output/` 同级可见，`tests/` 被挂到 `/tests`（含 `__golden_output/`）。三者都在 judge 视野内，**模板沉默不等于禁止**，只会把"要不要去翻参考答案"交给模型临场决定，同一批次内不同 criterion 会话的口径就此漂移。**必须显式写明三区语义**。
4. `Reference-solution policy` 段**不要删、不得弱化**——尤其"不得因参考答案满足就给分，一切以候选交付物为准"与"不得逐值比对"两条。前者防的是空产物得分（参考答案里有 ≠ 候选做到了）；后者防的是把参考解当唯一正确答案，对同样有效的不同解法误扣分。
5. 工具提示段保持**"提示"而非"强制"**——列出容器内可用的解析途径（markitdown CLI、openpyxl / python-docx / python-pptx / pypdf 等库）供 judge 选用，不要写成"必须用某条命令"：判官模型能力不一，部分模型可直接读 PDF 等格式，写死单一路径会挡掉更强的原生能力。环境确有的限制（如 Task/Explore 子代理不可用）照实告知即可，避免 judge 白耗 turn。
6. **总量有上限**：`prompt.md` 模板 + 全部 criterion description 之和须 **< 100 KB**（prompt 经命令行参数传给 judge，超长会 E2BIG 直接起不来）。

> `tests/__golden_output/` 是必交目录，在 verifier 容器内挂载为 `/tests/__golden_output/`，judge 可直接读取 —— 因此 `prompt.md` **必须**写明它的位置与使用政策（见规则 3、4 与上面的模板）。

## 7. Rubric 细则要求

**打分项 = 一个得分点 / 扣分点**：模型回答到了我们希望的 → 得分；回答到了我们不希望的 → 扣分。

### 五项准则（每条 rubric 先过这五关）

| 检查项 | 标准 |
|---|---|
| 原子性 | 每条判据仅检查一个方面（避免一条捆绑多个独立事实 / 多个可接受值） |
| 客观性 | 判据为可客观验证的事实性陈述，不含"风格 / 美观"等过于主观的表述 |
| 区分度 | 正负样本明显区分；正分判据能区分"部分正确"与"完全正确" |
| 完整性 | 覆盖多个维度 |
| 鲁棒性 | 多次 judge 判断基本稳定 |

### 单条打分项要求

| 要求 | 说明 |
|---|---|
| 原子性 | 描述一个独立、明确、可验证的评分点，仅检查一个方面 |
| 准确无歧义 | 表述完整、事实正确、依据可靠，使不同评分者能形成一致理解 |
| 可独立判断 | 包含作出判断所需的关键信息，不要求评分者额外推导、补充标准或二次判断<br>✗ 不推荐："收入实现了明显增长。" ✓ 推荐："收入同比增长了 65%。" |
| 来源合理 | 必须来自：① 项目描述中的明确要求；② 参考文件中的明确要求；③ 根据任务目标和使用场景可合理推导出的隐含要求。**不能凭空增加"伪需求"** |
| 有明确判定锚点 | 禁止"语言流畅""结构清晰""内容专业"等空洞描述<br>✗ 不推荐："PPT 排版美观。" ✓ 推荐："单页正文不超过 150 字，文本无明显遮挡、重叠或溢出。" |
| 客观可验证 | 优先评价能直接核查的事实、数据、结构和结果；确需评价主观质量时必须转化为具体的可观察标准 |
| 粒度合理 | 既不把多个独立要求合并为一项，也不把一个完整动作拆成大量无实际意义的小项 |
| 打分对象 | 输出文件有多个时，在打分项中**明确给出本条的打分对象** |

### 打分项之间的要求

- **互不重复、互不冲突**：不同打分项评价不同内容，避免同一问题被重复计分，也不能出现判定标准相互矛盾。例："公文是否专业、有条理且合规"应拆分为：文种选择是否正确 / 格式要素是否齐全（标题、主送机关、正文、落款、发文字号等）/ 请求事项是否明确、是否符合"一文一事"。
- **具有区分度**：正分项和负分项的判定边界应明确；`type` 为 gradient 的正分项要求能区分"部分满足"和"完全满足"。
- **整体覆盖完整**：所有打分项合起来覆盖任务主要目标与关键能力，能从不同维度评价交付物质量。
- **权重体现重要性**：根据各打分项对任务结果的影响程度设置不同 weight，避免机械地使用相同权重。
- **允许设置合理亮点项**：可评价项目要求之外、但基于常识会影响用户判断或交付质量的内容；应有明确价值和合理依据，不能无限扩展任务范围。
- **判断结果稳定（鲁棒性）**：同一套打分项由不同 Judge 或在不同时间多次评分时结果应基本一致；波动较大时进一步明确描述、判定边界和示例。

## 8. 评价维度体系

每条打分项需要有其所属评分维度（一级 + 二级，二级可为空）。**维度根据任务的要求动态调整，不同任务需要有区分度。**

| 一级维度 | 二级标签 | 主要检查什么 | 典型条目 |
|---|---|---|---|
| **指令遵循【必须】** | — | instruction 中显式要求的任务内容与交付约束是否被完整执行，包括范围限定、数量、命名、路径、格式、单位、精度以及明确要求包含或禁止的内容等。**只检查 instruction 明确提出的要求**；内容本身是否正确、专业、深入，归入对应内容质量维度 | 「结果文件名为 `sales_summary.xlsx`」「存放在 output/」「金额以万元为单位保留两位小数」→ 拆成 3 条 |
| **内容质量【必须】** | 结论正确性 | 基于已有事实、数据和分析形成的最终判断、结论、推荐或决策是否正确，是否与证据一致，是否存在结论与数据相矛盾、判断方向错误或关键结论遗漏。重点检查"最终得出了什么判断"，而非具体计算过程或论证深度 | 数据显示 A 市场在增长率、利润率和竞争强度等关键指标上均优于 B 市场，最终推荐应为 A 市场，而不能错误推荐 B |
| | 数值与计算准确性 | 数值提取、公式计算、统计口径、单位换算、聚合方式、分母选择、时间范围、精度及容差 | 合计行 = 各月之和（±0.01）；亿元 / 万元换算正确 |
| | 专业规范 | 是否符合任务所属行业/领域的专业知识、规则、标准和通行实践，包括会计准则、法律规则、医学规范、行业标准、专业术语及业务口径 | 「应收账款」按适用会计准则正确分类；法律分析使用现行有效的法律规则而非已失效规定；财务模型中的 EBITDA、FCF 等指标使用符合专业惯例的定义与口径 |
| | 分析与论证质量 | 产出中的事实、数据和引用是否忠实于输入材料及可验证的客观事实，不无依据地编造、篡改或混淆信息；引用和来源是否真实可追溯；跨文件处理时是否正确区分主体、版本、时间和统计口径。既检查 workspace 内事实，也检查任务涉及的外部客观事实 | 「A 公司于 2016 年成立」能在 `industry_report.pdf` 表 3 溯源到该项内容，溯源不到即视为编造的幻觉内容 |
| | 事实忠实性 | 同上 | 学术调研需求中给出看似真实的论文标题、作者、期刊和 DOI，但实际查不到，为幻觉内容，需要检查 |
| | 内容逻辑性与分析深度 | 分析到位、论证充分、有没有回答真问题、洞察深度。在指令遵循之外单独考察深度、逻辑、思想内涵。论点有准确论据 / 材料支撑 | 销售额下滑分析给出 ≥2 条有数据支撑的归因，而不是复述「出现了下滑」 |
| | 结构与组织 | 信息架构和组织方式是否合理，包括章节/页面结构是否完整、内容层级是否清晰、顺序是否符合逻辑、信息分组是否合理、关键模块是否缺失，以及文字、表格和图表是否放置在合理的上下文中 | 报告按「核心结论 — 分析依据 — 风险 — 建议」形成清晰结构 |
| 操作与交付安全 | — | Agent 执行过程中是否安全处理用户已有文件和 workspace。不得误删、覆盖、破坏无关源文件，不得因编辑或格式转换造成数据、公式、页面或其他原有内容意外丢失 | 处理完成后 `data.csv` 仍完整可打开；被覆盖或删除则命中扣分项 |
| 安全合规 | — | 产出内容及执行行为是否满足隐私、数据安全、版权、法律法规及业务合规要求，避免泄露敏感信息、违规使用内容或产生明显误导、偏见及其他可能造成实际风险的问题 | 对外报告不得直接暴露输入文件中的身份证号、手机号等敏感个人信息 |
| 超预期贡献 | — | 其他要求都满足之后，进一步提升交付价值的部分 | 事实二次核对、产物兼容性与易用性、防呆设计、指出 instruction 本身的疏漏以及更完善的交付物 |
| 视觉美感 | — | 交付物是否足够美观（排版、配色等），比较偏主观。**仅针对交付物有美观度要求的情况需要配置得分点，普通任务不建议包含** | PPT 的配色和排版是否美观 |

### 不同维度的权重设置要求

- 内容质量、操作与交付安全**应该总是较高 weight**；
- 对于 ppt 等设计类交付物，**视觉美感与格式规范**维度应该较高 weight；
- 对于行业性比较突出的交付物，**专业规范**维度应该较高 weight；
- 对于写作类交付物，**结构与组织**维度应该较高 weight；
- 对于数学计算要求较高的交付物（如金融场景），**数值与计算准确性**维度应该较高 weight。

## 9. 打分项分布要求

- **领域锚点占比**：交付物内容质量维度（其下所有二级标签）锚点正分，**占全部正分的 30% 以上**——表示本题对专业性有很高要求，非简单指令遵循就可满分，要求有极强的领域知识理解。
- **关键项占比**：每题**至少包含 2 条 Critically Important（+10）**评分项，模拟用户真实期望，给出最影响产物本身可用性的打分点。
- **−10 分项**：仅用于重大专业错误、幻觉、业务安全、合规风险等真正影响答案可信度的情形，**不得滥用**。
- **一般来说，指令遵循、结论正确性、分析与论证质量与事实忠实性这些维度总是需要的**；行业性比较突出的交付物应覆盖专业规范维度；ppt 等设计类交付物应覆盖视觉美感与格式规范维度；写作类交付物应覆盖结构与组织维度；数学计算要求较高的（如金融场景）应覆盖数值与计算准确性维度。

## 10. 评分机制（由 finalize.py 全题池化，供应商不自行聚合）

```
S_max（满分基准） = Σ 全部正向条目的 weight        ← 负向条目不进分母
分子             = Σ 正向 weight × value − Σ 负向 weight × (1 − value)
主分 reward      = clip(分子 / S_max, 0, 1)
```

| type | value |
|---|---|
| `binary` | 0 或 1 |
| `likert` | judge 输出 1–5 的整数（条目统一 `points = 5`）；Reward Kit 归一化为 `(raw − 1) / 4`：1→0、2→0.25、3→0.5、4→0.75、5→1 |
| `negate = true` 的条目 | Reward Kit 自动翻转：`1 − 上述归一化值`（"完全没违规" = 1.0） |

## 11. rubric 设计自查脚本（建议落成本地检查）

```bash
python3 - <<'PY'
import tomllib, pathlib, collections
p = pathlib.Path("tests/rubrics.toml")
d = tomllib.loads(p.read_text(encoding="utf-8"))
crit = d["criterion"]
print("条数:", len(crit))
assert all(c.get("name") == c["id"] for c in crit), "存在 name != id"
assert all(c["weight"] in (3.0, 7.0, 10.0) for c in crit), "weight 越界"
assert all(c["type"] in ("binary", "likert") for c in crit), "type 越界"
assert all(("points" in c and c["points"] == 5) for c in crit if c["type"] == "likert"), "likert 未写 points=5"
assert all("1" in str(c["description"]) and "5" in str(c["description"]) for c in crit if c["type"] == "likert"), "likert 缺锚点"
assert all("Deliverables to inspect" in c["description"] for c in crit), "缺交付物路径清单"
pos = [c for c in crit if not c.get("negate")]
assert sum(1 for c in pos if c["weight"] == 10.0) >= 2, "Critically Important 少于 2 条"
print("正向 weight 总和:", sum(c["weight"] for c in pos))
print("警告: 需人工核对『内容质量维度正分 ≥30%』与『总是需要维度已覆盖』")
PY
```
