# task.toml 编写指南（schema 1.4，外发交付）

## 完整模板

```toml
schema_version = "1.4"                             # 照抄
# 格式：/app/output/{你的交付物名称}
artifacts = [
  "/app/output/FIN-T2-001_财务分析报告.xlsx",
  "/app/output/FIN-T2-001_毛利率趋势.png",
]

[task]
name = "acme-eval/fin-t2-001"           # 任务名称：org/领域-编号，org 段 = 供应商代号
version = "1.0.0"                       # 任务版本，返修递增补丁号
description = "基于两期年报与交易流水产出财务分析报告"
keywords = ["finance", "office", "L3"]  # [领域英文名, "office", 长程等级]

[metadata]
task_id = "FIN-T2-001"                  # 任务 id，与目录名、[task].name 的 name 段一致
domain = "金融"                          # 任务领域（分类表枚举）
category_l1 = "投资银行"                 # 一级分类（分类表枚举）
category_l2 = "股权资本市场业务"          # 二级分类（分类表枚举）
scene_l3 = "再融资定向增发分析"           # 三级场景（分类表枚举）
capabilities = "财务比率计算、估值口径"    # 评测能力
office_task_type = "T2 数据处理"         # T1文档/T2数据处理/T3PPT/T4邮件/T5会议/T6检索/T7专业判断/T8全流程/其他
difficulty = "L3"                       # 长程任务等级 L2~L5（按长程性，非题目难度）
vl_dependency = "不依赖vl"               # 强依赖vl / 弱依赖vl / 不依赖vl
source_note = "任务来源、真实性保障、真实场景中的交付物是什么"
tools = "Excel/Python"                  # 完成任务所需工具
expert_minutes = 240                    # 熟练专家(≥10年)完成时间(分钟)，须与 difficulty 自洽
domain_knowledge = "..."                # 选填：领域知识依赖说明
expected_pass_rate = 0.3                # 选填：目标模型通过率预估 0~1

[[metadata.deliverables]]               # 交付物一：path 相对 /app/output/，必交写死精确文件名
path = "FIN-T2-001_财务分析报告.xlsx"
required = true
desc = "主交付物：财务分析报告"

[[metadata.deliverables]]
path = "FIN-T2-001_毛利率趋势.png"
required = true
desc = "毛利率趋势折线图"

# Numeric rubrics metadata（id 与 judge.toml/gating.toml 的 criterion id 一一对应）
[[metadata.rubric_index]]
id = "R1"
dimension = "交付物内容质量-准确性"
criterion_type = "Objective"
criterion_necessity = "Explicit"
weight = 10.0                            # 计分项 3.0/7.0/10.0；gating 项不写
negate = false                           # true = 描述"候选犯了什么错"
gating = false                           # true = 该条在 gating/

[[metadata.rubric_index]]
id = "G1"
dimension = "安全合规"
criterion_type = "Objective"
criterion_necessity = "Implicit"
gating = true                            # gating 项：无 weight

[environment]
network_mode = "no-network"              # 或 allowlist（同段补 allowed_hosts）
os = "linux"
# 只允许键：os / network_mode / allowed_hosts / build_timeout_sec / docker_image /
#           cpus / memory_mb / storage_mb / env / healthcheck
# 禁止写 workdir —— 工作目录由 environment/Dockerfile 的 WORKDIR /app 决定
cpus = 2
memory_mb = 8192
storage_mb = 30720

[agent]
user = "agent"
# timeout_sec 缺省 72000；L4/L5 长程任务按实际需要上调

[verifier]
timeout_sec = 18000.0                    # 按 judge 耗时填写
user = "agent"
network_mode = "no-network"
# [verifier.env] 逐字照规范 3.1 示例，${JUDGE_GATEWAY}/${OPENAI_API_KEY}/${OPENAI_BASE_URL}
# 是占位符，不得替换成真实密钥
```

## 逐字段约束（规范 3.2 字段表）

| 字段 | 必填 | 填法 |
|------|------|------|
| schema_version | 是 | `"1.4"` 照抄 |
| artifacts | 是 | 由交付物清单机械展开：每个 required=true 的 deliverables.path 前加 `/app/output/`，不增不减不改字 |
| [task].name | 是 | `acme-eval/fin-t2-001` 式；org 段与批次目录前缀同一供应商代号 |
| [task].version | 是 | `"1.0.0"`；返修 1.0.0→1.0.1 |
| [task].description | 是 | 一句话，可直接用 instruction.md 标题 |
| [task].keywords | 是 | `[领域英文名, "office", 长程等级]` |
| [metadata].task_id | 是 | 与目录名、[task].name 的 name 段三处一致（按小写连字符规则归一化后比较） |
| [metadata].domain | 是 | 领域分类表枚举，禁自造近义说法 |
| category_l1 / category_l2 / scene_l3 | 是 | 分类表逐级枚举原文 |
| capabilities | 是 | 评测能力 |
| office_task_type | 是 | T1~T8 / 其他 |
| difficulty | 是 | L2~L5，按长程性（专家人时/必要步骤/工具类别/反馈轮次） |
| vl_dependency | 是 | 强/弱/不依赖 vl |
| source_note | 是 | 为什么选这题、真实性如何保障、真实场景交付物是什么 |
| tools | 是 | 完成任务的办公工具 |
| expert_minutes | 是 | 熟练专家完成分钟数，须与 difficulty 自洽 |
| domain_knowledge | 否 | 领域知识依赖说明 |
| expected_pass_rate | 否 | 目标模型通过率预估 |
| [[metadata.deliverables]] | 是 | path（相对 /app/output/，`/` 分隔）/ required / desc |
| [[metadata.rubric_index]] | 是 | id 与 judge/gating criterion 一一对应；dimension 取 6.7 维度表；weight 3/7/10 与 judge.toml 一致；gating 项不写 weight |
| [environment] | 是 | 只允许规范字段表内键；禁 workdir；resources 可按需调整 |
| [agent].timeout_sec | — | 缺省 72000；L4/L5 按需上调 |
| [verifier].timeout_sec | 是 | 按 judge 耗时填，示例 18000.0 |
| [verifier].user / network_mode / allowed_hosts / [verifier.env] | 是 | 逐字照规范 3.1 示例；占位符保持原样 |

## deliverables 命名规则（4 条硬规则）

1. required=true 必须写**精确文件名**，禁止 glob/通配/"或等价命名"；glob 只允许 required=false 的过程性产物。
2. 文件名不得含日期、时间戳、版本号等动态成分；业务上需含日期的把具体字符串写死。
3. 大小写敏感：清单、instruction.md、artifacts、solution/golden_output/、tests/golden_output/、judge 的 files **六处逐字节一致**（含全/半角、空格、下划线/连字符）。
4. 需要目录层级时在 path 中写出；judge 的 files 必须逐个写文件路径，**不要填目录**（填目录 Reward Kit 只读第一层）。
5. UTF-8，单文件 ≤200 字节，无控制字符；建议以题目编号为前缀避免与 Agent 中间产物混淆。

## 占位符与密钥

- 题包任何位置**不得出现真实密钥/token/凭证**；需要时用占位符（如 `<API_KEY>`）并在任务书说明。
- `[environment].env` 中不得出现凭证或评分相关信息。
- task.toml 里的 `${VAR}` 占位行保持原样，不要改成真实密钥；本地自测时自行 export。
