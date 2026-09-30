# task.toml（schema 1.4）完整模板与字段说明

## 1. 书写顺序（强制）

```
schema_version → artifacts → [task] → [metadata] → [[metadata.deliverables]]
→ [agent] → [verifier] → [verifier.env] → [environment]
```

## 2. 完整模板（照抄改写，逐字保留注释与占位符）

```toml
schema_version = "1.4"                             # 照抄
# 格式： /app/output/{你的交付物名称}
artifacts = [
  "/app/output/FIN-T2-001_财务分析报告.xlsx",
  "/app/output/FIN-T2-001_毛利率趋势.png",
  "/logs/artifacts/output",
]
[task]
name = "work/fin1-001"                             # 任务名称，work/<task_id 小写连字符>
version = "1.0.0"                                  # 任务版本
description = "基于两期年报与交易流水产出财务分析报告"   # 任务描述
keywords = ["finance", "office", "A2"]             # [领域英文名, "office", 难度等级]
[metadata]
task_id = "FIN1-skill-DEP-001"                     # 题目编号：领域缩写-任务类型-序号
author_organization = "<供应商名>"
category = "skill-dependency"                      # 题目类型
domain = "金融"                                     # 一级标签：通用办公/金融/医疗/法律
domain_l2 = "投资银行"                              # 二级标签（对齐知识体系表）
domain_l3 = "<三级标签>"                            # 三级标签
domain_l4 = "<四级标签>"                            # 四级标签
capabilities = "财务比率计算、估值口径"              # 评测的能力
difficulty = "A2"                                  # A1 易 / A2 中 / A3 难
vl_dependency = "否"                                # 是否依赖 VL（视觉-语言能力）：是/否
source_note = "任务来源、真实性保障、真实场景中的交付物是什么"
tools = "Excel/Python"                             # 所需办公工具/数据库
domain_knowledge = "再融资定增的财务分析口径与可比公司估值方法"   # 选填
task_complexity = "C2"                             # C1-C5，不从 difficulty 换算
weakness_tag = ["W07-流程跳步", "W12-约束遵循"]      # 覆盖 ≥1 个，按算法词表填写
environment_template = "<平台已确认的环境模板名>"
tool_set = ["filesystem", "shell", "python"]       # 按实际可用能力填写
skill_set = []                                     # 本示例未提供技能；有技能时填写目录名
expected_tool_dependencies = ["filesystem", "shell", "python"]   # 按实际必要能力填写
expected_skill_dependencies = []                   # 必须是 skill_set 的子集
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
timeout_sec = 72000.0                              # 缺省 72000
[verifier]
timeout_sec = 18000.0                              # 须 > judge 会话超时（7200）
user = "root"
[verifier.env]
# Judge 相关变量统一 JUDGE_ 前缀，只写在 [verifier.env]、严禁写入 [environment.env]。
# 必选项（运行环境注入，AP 必给）；可选项一律用 ${VAR:-默认值} 语法给默认值。
JUDGE_API_KEY = "${JUDGE_API_KEY:-}"               # 必选：judge 网关 key
JUDGE_BASE_URL = "${JUDGE_BASE_URL:-}"             # 必选：judge 网关地址（可带 /v1，test.sh 负责剥）
JUDGE_MODEL = "${JUDGE_MODEL:-qwen3.7-plus}"       # 可选：裁判模型（经 REWARDKIT_MODEL 运行时生效）
JUDGE_PROVIDER = "${JUDGE_PROVIDER:-anthropic}"    # 可选：信息性声明
JUDGE_API_PROTOCOL = "${JUDGE_API_PROTOCOL:-anthropic}"   # 可选：openai 时降级为 LLM judge
# 兼容旧环境的兜底注入
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

## 3. 字段说明表

| 字段 | 说明 | 必填 | 约束 |
|---|---|---|---|
| `[metadata].task_id` | 题目编号 | 是 | 格式 `领域缩写-任务类型-序号`，如 `FIN1-001` |
| `[metadata].domain` | 所属领域（一级标签） | 是 | 通用办公 / 金融 / 医疗 / 法律 |
| `[metadata].domain_l2` | 所属领域二级标签 | 是 | 对齐知识体系表 |
| `[metadata].domain_l3` / `domain_l4` | 三/四级标签 | 是 | 对齐知识体系表 |
| `[metadata].capabilities` | 评测的能力 | 是 | 该任务能评测的具体专业能力 |
| `[metadata].difficulty` | 难度等级 | 是 | A1(<70%) / A2(<60%) / A3(<50%)，验收见 06 号文档 |
| `[metadata].vl_dependency` | 是否依赖 VL | 是 | 是 / 否 |
| `[metadata].source_note` | 任务说明 | 是 | 为什么选这个任务、真实性如何保障、真实场景交付物是什么 |
| `[metadata].tools` | 所需工具 | 是 | Word/Excel/PPT 等 |
| `[metadata].domain_knowledge` | 领域知识依赖 | 否 | 完成任务所需的专业知识说明 |
| `[metadata].environment_template` | 环境模板名 | 本专项必填 | string；平台已确认模板名，与实际镜像依赖一致，**不替代 Dockerfile** |
| `[metadata].tool_set` | 模型可用的工具能力集合 | 本专项必填 | array[string]；用平台已有工具名，如 filesystem / shell / python；仅声明实际可用能力；**不要求三者分别对应独立原生工具** |
| `[metadata].skill_set` | 环境内可用技能 | 本专项必填 | array[string]；与 `environment/skills/<name>/` 逐一对应，名称与 SKILL.md 中 `name` 一致；**可含干扰技能**，无技能写 `[]` |
| `[metadata].expected_tool_dependencies` | 真正必要的工具能力 | 本专项必填 | array[string]；必须是 `tool_set` 的**子集**；无依赖写 `[]`；**不是要求每种工具都调用一次** |
| `[metadata].expected_skill_dependencies` | 真正必要的技能 | 本专项必填 | array[string]；必须是 `skill_set` 的**子集**；可为空；**含干扰技能的发现任务应为真子集**，不能仅因安装了技能就认定存在依赖 |
| `[metadata].task_complexity` | 任务复杂度 | 本专项必填 | string；C1–C5，按算法分级表填写，**不从 difficulty 直接换算** |
| `[metadata].weakness_tag` | 覆盖的弱点标签 | 本专项必填 | array[string]；按算法材料的数组写法填写**至少一项**，取值用正式词表 |
| `[metadata].expected_pass_rate` | 目标模型通过率预估 | 否 | 0~1 |
| `[[metadata.deliverables]]` | 参考答案（交付物清单） | 是 | 见 §4 |
| `[environment].network_mode` | — | 是 | **固定 `public`**。claude-code 框架下不要写 `no-network`：agent setup 阶段要联网安装 claude CLI，基线断网会直接 AgentSetupTimeoutError、整题跑不起来。确需断网语义的题目先与平台确认后再交 |
| `[agent].timeout_sec` | — | 是 | 缺省 72000 |

**以下格式照抄不改**（Harbor 侧要求的字段，与验收无关，按下表机械填写，不要自行发挥）：

| 字段 | 填法 |
|---|---|
| `schema_version` | `"1.4"` |
| `artifacts` | 由交付物清单机械展开：每个 `required = true` 的 `deliverables.path` 前面加 `/app/output/`，**不增不减、不改字** |
| `[task].name` | `work/fin1-001` |
| `[task].version` | `"1.0.0"` |
| `[task].description` | 一句话说明，可直接用 instruction.md 的标题 |
| `[task].keywords` | `[领域英文名, "office", 难度等级]`，如 `["finance", "office", "A2"]` |
| `[verifier].timeout_sec` | `18000.0` |
| `[verifier].user` / `[verifier.env]` | 逐字照抄模板：`user = "root"`；judge 变量统一 `JUDGE_` 前缀——`JUDGE_API_KEY` / `JUDGE_BASE_URL` **必选**（运行环境注入，不要替换成真实值），`JUDGE_MODEL` 等可选项必须用 `${VAR:-默认值}` 语法。**`ANTHROPIC*` / `OPENAI*` 不写进 toml**，由 test.sh 从 `JUDGE_`（兜底 `EVAL_API*`）推导 |
| `[environment].os` / `build_timeout_sec` / `cpus` / `memory_mb` / `storage_mb` | 逐字照抄模板；确需上调时在提交说明里注明原因 |

## 4. `[[metadata.deliverables]]` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `path` | string | 相对 `/app/output/` 的文件名或 glob；分隔符用 `/` |
| `required` | bool | `true` = 缺失即判未完成交付；`false` = 可选产物 |
| `desc` | string | 一句话说明 |

### 五条命名与结构规则

| # | 规则 | 原因 |
|---|---|---|
| 1 | `required = true` 必须写**精确文件名**，禁止 glob / 通配 / "或等价命名" | glob 只允许用于 `required = false` 的过程性产物 |
| 2 | 文件名不得含日期、时间戳、版本号等动态成分 | Agent 每次生成的名字不同，criteria 里写的交付物名永远对不上；业务上需含日期的，把具体字符串**写死** |
| 3 | **大小写敏感**。清单、instruction.md、artifacts、`solution/golden_output/`、`tests/__golden_output/`、criterion description 中引用的交付物路径**六处逐字节一致**（含全角/半角、空格、下划线/连字符） | Linux 容器内，`Report.docx ≠ report.docx` |
| 4 | 需要目录层级时在 `path` 中写出；criterion description 里引用交付物时**逐个写完整文件路径**（如 `output/<文件名>`），不要只写目录 | agent judge 靠 description 里的路径线索找文件，只给目录容易漏查文件、却照 criteria 判"没写" |
| 5 | UTF-8，单个文件名 ≤200 字节，无控制字符；建议以题目编号为前缀 | 避免与 Agent 中间产物混淆 |

## 5. `[environment]` 允许的键（白名单）

只允许 Harbor 字段表内的键：

```
os  network_mode  allowed_hosts  build_timeout_sec  docker_image
cpus  memory_mb  storage_mb  env  healthcheck
```

- **不要写 `workdir`** —— 工作目录由 `environment/Dockerfile` 的 `WORKDIR /app` 决定。
- `[environment].env`（agent 侧环境变量）遵循**最小必要原则**：完成任务不需要的变量一律不配。
- **`JUDGE_*` 只准写在 `[verifier.env]`**，严禁写入 `[environment].env` —— judge 凭据进 agent 环境等于把评分通道泄漏给被测模型。

## 6. 后置校验命令

```bash
harbor task update "path/to/FIN-T2-001" --org "<供应商代号>"
harbor task update "path/to/tasks" --org "<供应商代号>" --scan    # 整目录批量
```

> `[task]` 段缺失时可批量补齐，补齐后仍需手工核对 `name` 是否符合命名规则（该命令按目录名生成 name）。
> 本地自测（`harbor run -p ...`）不需要登录 Harbor，供应商代号可自行拟定（建议用组织简拼，全批次固定，返修沿用）。
