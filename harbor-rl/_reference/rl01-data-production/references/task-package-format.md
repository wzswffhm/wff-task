# 题包结构、task.toml 与 Skill 形态

## 目录结构

```text
<题目编号，如 AQ-002>/
|-- task.toml                      # 任务声明（见下）
|-- instruction.md                 # 任务描述，Agent 唯一可见
|-- environment/
|   |-- Dockerfile                 # 功能型 skill 在这里装进环境：COPY skills/ /skills/
|   |-- skills/
|   |   `-- <skill-name>/
|   |       |-- SKILL.md           # Anthropic Skill 格式
|   |       |-- scripts/           # read_document.py / propose_edits.py / add_comment.py …
|   |       `-- references/        # 被 SKILL.md 引用的补充规则，如 anchors.md
|   `-- app/                       # 任务输入：参考文件本体
|-- tests/
|   |-- test.sh -> run_verifier.py # 判分入口
|   `-- rubrics.json               # 判据
`-- solution/
    `-- solve.sh
```

## task.toml

```toml
schema_version = "1.4"                 # 照抄

# 格式：/app/output/{你的交付物名称}，末尾固定加一行 /logs/artifacts/output
artifacts = [
  "/app/output/FIN-T2-001_财务分析报告.xlsx",
  "/app/output/FIN-T2-001_毛利率趋势.png",
  "/logs/artifacts/output",
]

[task]
name = "work/fin1-001"                 # 任务名称
version = "1.0.0"                      # 任务版本
description = "基于两期年报与交易流水产出财务分析报告"

[metadata]
task_id = "FIN1-skill-DEP-001"         # 题目编号
author_organization = "<供应商名>"
category = "skill-dependency"
domain = "金融"                        # 通用办公/金融/医疗/法律，支持后续新增
domain_l2 = "投资银行"                 # 二级标签，对齐知识体系表
capabilities = "财务比率计算、估值口径"  # 该任务能评测的具体专业能力
difficulty = "A2"                      # A1/A2/A3
vl_dependency = "否"                   # 是否依赖视觉-语言能力：是/否
source_note = "任务来源、真实性保障、真实场景中的交付物是什么"
tools = "Excel/Python"                 # 所需办公工具/数据库
domain_knowledge = "再融资定增的财务分析口径与可比公司估值方法"   # 选填
task_complexity = "C2"                 # C1–C5
weakness_tag = ["W07-流程跳步", "W12-约束遵循"]   # 覆盖 ≥1 个
environment_template = "<平台已确认的环境模板名>"
tool_set = ["filesystem", "shell", "python"]
skill_set = []                         # 本示例未提供技能；有技能时填目录名
expected_tool_dependencies = ["filesystem", "shell", "python"]
expected_skill_dependencies = []       # 必须是 skill_set 的子集
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
timeout_sec = 72000.0                  # 缺省 72000

[verifier]
timeout_sec = 18000.0
user = "root"

[verifier.env]
# Judge 相关变量统一 JUDGE_ 前缀，只写在本段，严禁写入 [environment.env]。
# 必选项由运行环境注入；可选项一律用 ${VAR:-默认值} 语法给默认值。
JUDGE_API_KEY = "${JUDGE_API_KEY:-}"                    # 必选：judge 网关 key
JUDGE_BASE_URL = "${JUDGE_BASE_URL:-}"                  # 必选：judge 网关地址（可带 /v1，test.sh 负责剥）
JUDGE_MODEL = "${JUDGE_MODEL:-qwen3.7-plus}"            # 裁判模型
JUDGE_PROVIDER = "${JUDGE_PROVIDER:-anthropic}"         # 信息性声明
JUDGE_API_PROTOCOL = "${JUDGE_API_PROTOCOL:-anthropic}" # openai 时降级为 LLM judge
# 兼容旧环境的兜底注入
EVAL_API_KEY = "${EVAL_API_KEY:-}"
EVAL_API_BASE = "${EVAL_API_BASE:-}"
LITELLM_DROP_PARAMS = "true"

[environment]
os = "linux"
build_timeout_sec = 18000.0
network_mode = "public"                # claude-code 框架下不要写 no-network
cpus = 2
memory_mb = 8192
storage_mb = 30720                     # 照抄
```

## 元数据字段约束

| 字段 | 类型 | 取值写法 / 约束 |
|---|---|---|
| `skill_set` | array | 环境内安装的功能型 skill 目录名，须与 `environment/skills/<name>/` 逐一对应；可含干扰项（Skill Discovery 场景） |
| `task_complexity` | enum | C1–C5，按分级表的文件数 / requirement / evidence-hop 等硬指标判定，不按感觉 |
| `expected_skill_dependencies` | array | `skill_set` 的子集：不依赖它任务必失败的 skill。Skill Discovery 任务里该项应严格小于 `skill_set`（存在故意的无关 skill） |
| `weakness_tag` | array | 覆盖 ≥1 个，按算法词表填写（词表未下发时先标 TBD） |
| `difficulty` | enum | A1 易 / A2 中 / A3 难 |
| `vl_dependency` | enum | 是 / 否 |
| `artifacts` | array | `/app/output/{交付物名}`，并固定包含 `/logs/artifacts/output` |

其余必填字段：题目编号、所属领域、所属领域二级/三级/四级标签、评测的能力、难度等级、任务说明、所需工具；领域知识依赖为选填。三级标签需按出题内容补足（暂空），四级标签描述题目所属细分场景。

## 功能型 Skill 的标准形态

当前主要通过写入 `environment/skills/<name>/` 的方式提供。`SKILL.md` 用 Anthropic Skill 格式：frontmatter 为 `name` / `description` / `compatibility`，正文写分步 SOP、脚本用法、失败恢复，以及"绝不能用别的方式完成任务"这类硬规则。

```markdown
---
name: contract-redliner
description: Redline Word (.docx) contracts with native tracked changes and margin comments … Use when asked to redline, mark up, revise a .docx legal document — every edit must be a real tracked change applied via the bundled scripts, never by rewriting the file.
compatibility: Requires Python 3.10+ with python-docx==1.2.0, docx-revisions, lxml.
---
```

Skill 能不能省略，取决于里面有没有"特有信息/行为规则"：特殊业务规则、环境特化 SOP、特殊阈值与内部映射、业务优先级、fallback 顺序。这些内容必须直接影响最终答案，否则 Skill 只是可有可无的 contextual document。构造手法见 [design-patterns.md](design-patterns.md)。

同时，`instruction.md` 必须显式强调要使用该 skill，例如：

> Every edit and every comment goes through the contract-redliner skill installed in this environment — never write `[ADD:…]` / `[DELETE:…]` markup, and never modify the document by any other means.

## 判分入口

`tests/test.sh` 是判分入口（可转 `run_verifier.py`），最终必须产出 `/logs/verifier/reward.txt` 或 `/logs/verifier/reward.json`（0.0–1.0）。判据写在 `tests/rubrics.json`，字段规范见 [rubrics-spec.md](rubrics-spec.md)。

## Dockerfile 要点

- 基础镜像必须来自公共仓库（Docker Hub、阿里云镜像站等可公开拉取），禁止 `FROM` 本机私有镜像。
- 不得 `COPY solution/` 或 `tests/`，防止 Agent 读到答案与判据。
- 预装 Agent 与 Verifier 依赖（如 `claude-code`、`python3`、`uv/uvx`、rewardkit 依赖预热），把下载动作放到 build 层，避免每个 trial 重新联网安装。
- Windows 工作区复制进 Linux 容器后，记得处理 CRLF 与可执行权限（`sed -i 's/\r$//'` 加 `chmod +x`）。
