# Outside Harbor Windows 题包格式培训 Demo

本文用一个现有题包的真实结构，向专家讲清楚 Windows 专项题包里每个文件的职责、内容边界、注释规范和常用模板。示例优先使用最小、最清晰的 `windows-powershell-ads-001` 结构；其他题包只是在这个骨架上增加了依赖、fixtures、参考源码或管理员工序。



## 1. 先记住一句话



- `instruction.md` 写给参与者；
- `tests/**` 定义并执行客观判定；
- `solution/**` 是隐藏参考答案；
- `environment/**` 只负责还原、准备和驱动真实环境。

普通模型资产的发布范围不应包含 `solution/**`。该目录只用于组织方 Golden 校验。



## 2. 标准文件树



下面是一个 Windows 题包的标准骨架。`<task-dir>` 表示具体题目目录，例如 `windows-powershell-ads-001`；所有题包内路径都从该题目目录出发。



```Plain Text
<task-dir>/
├── task.toml                           # 平台元数据和资源/超时配置
├── source.json                         # 题目来源、谱系、许可证、外采追溯信息
├── instruction.md                      # 参与者唯一需要阅读的任务说明书
│
├── environment/                        # 还原题目的真实执行环境
│   ├── adapter.toml                    # 运行器绑定描述，声明 prepare/start/exec_agent/test 等
│   ├── Dockerfile                      # 安装平台依赖，不写业务逻辑
│   ├── prepare.ps1                     # 准备或重置题目初始状态
│   ├── validate_environment.ps1        # 判断环境是否就绪
│   ├── run.ps1                         # 题目的主运行入口
│   ├── restore.ps1                     # 恢复上一阶段或固定基准状态
│   ├── cleanup.ps1                     # 清理临时状态、构建产物和驻留进程
│   └── workspace/                      # 参与者可以看到并修改的项目源码；按需出现
│
├── tests/                              # 客观测试、判定协议和评分映射
│   ├── test.ps1                        # 自动生成；不要手写、手改或格式化
│   ├── test.bat                        # 可选的传统入口包装
│   ├── run_tests.ps1                   # 实际执行测试并生成 result.json
│   ├── aggregate_results.ps1           # 汇总单个测试结果并对照 rubric
│   ├── judge.toml                      # 判定配置摘要和 rubric.json 的 SHA-256
│   ├── rubric.json                     # 权威评分规则
│   ├── run_matrix.ps1                  # 可选；批量运行多组场景
│   ├── *_probe.ps1                     # 可选；原子化探针或边界夹具
│   └── fixtures/                       # 可选；测试专用 nupkg、manifest 或数据集
│
└── solution/                           # 隐藏参考答案；普通模型资产不得携带
    ├── README.md                       # 解释参考实现，不预测或描述他人实现
    ├── solve.ps1                       # 将参考文件写入 workspace 的参考入口
    ├── solve.bat                       # 可选传统入口
    └── reference.patch                 # 可选参考 diff
```



不同题目会按需出现以下扩展项：



```Plain Text
environment/
├── Dockerfile.admin-overlay            # 题目需要更高权限或额外系统配置时使用
├── Dockerfile.scorer                   # 某些评测器需要独立构建容器时使用
├── docker-compose.yaml                 # 多服务或多容器场景
├── assets/nuget/*.nupkg                # 离线 NuGet 依赖
├── assets/vendor/                      # 供应商提供的原始资料；通常不属于可直接公开的题面
├── calibration/expected.json           # 固定的可复现期望结果
├── dependencies.lock.json              # 锁定依赖
└── offline-packages/                   # 需要物理断网还原的依赖包

solution/
├── reference/                          # 完整参考源码树
├── baseline/                           # 基线源码或缺陷版源码
└── changed_files/                      # 组织方只想暴露哪些文件属于参考改动
```



注意：顶层 `.DS_Store`、构建产物、临时目录和包含个人信息的材料都不是题包的一部分，不要进入最终发布清单。



## 3. 每类文件到底写什么



| 区域 | 文件 | 必须写的内容 | 不要在这里写的内容 |
|-|-|-|-|
| 元数据 | `task.toml` | Docker 镜像、题目 ID、作者、标签、难度、agent/verifier/environment 超时、CPU、内存 | 业务需求、步骤提示、测试方法 |
| 溯源 | `source.json` | 任务 ID、版本、来源类型、来源文档/仓库、谱系、风险、授权说明 | 具体答案、未脱敏的本机绝对路径、密钥 |
| 题面 | `instruction.md` | 背景、目标、可观察行为、输入/输出协议、边界、运行入口、用户可见验收 | 直接算法伪代码、测试断言细节、隐藏参考答案 |
| 环境 | `Dockerfile` | 安装运行时、依赖、系统组件；保证依赖可离线复现 | 动态生成测试数据之外的评测断言 |
| 环境 | `prepare.ps1` | 创建 fixture，初始化状态，验证前置条件，明确退出码 | 修改被测业务实现 |
| 环境 | `run.ps1` | 串联 prepare、测试或真实入口；返回准确的 `$LASTEXITCODE` | 重新定义评分 |
| 测试 | `run_tests.ps1` | 设置场景、调用业务/API、产生独立检查项，写出机器可读 `result.json` | 把题目要求改写成更容易通过的弱断言 |
| 测试 | `aggregate_results.ps1` | 按权威 `rubric.json` 映射 test_id 到权重和通过条件 | 手动覆盖权重 |
| 测试 | `rubric.json` | 描述可观察行为、权重、test_ids、证据位置、通过条件和失败原因 | 纯主观描述或无法执行的泛泛标准 |
| 金标 | `solution/README.md` | 说明参考实现满足了哪个行为契约和哪些关键边界 | 展示内部工作流程、评审意见或临时调试过程 |



### 3.1 `task.toml`



它是最小平台配置，不同题目之间应该只保留真实差异，不要复制无关字段。



```TOML
# 题包平台 schema 版本由上游约定保持不变。
version = "1.0"

# 只使用锁定的镜像 tag；不要使用 latest、浮动 tag 或本地无回复现的镜像。
docker_image = "registry.example/dthr-datasets/windows_zq:<immutable-task-image>"

[metadata]
quality_restoration_version = "20260921.1"
author_name = "vendor"
task_id = "windows-powershell-ads-001"
tags = ["coding", "windows", "powershell", "ntfs"]
difficulty = "L3"

[agent]
timeout_sec = 7200.0

[verifier]
timeout_sec = 7200.0

[environment]
build_timeout_sec = 3600.0
cpus = 2
memory = "4G"
```



审阅要点：



- `task_id`、题包目录和对外记录必须一致。
- 镜像必须是可追踪的固定 tag。
- 资源不足导致挂起时先修配置，不要改成放宽数值的假重试。

### 3.2 `source.json`



它是溯源卡，不是设计文档。用最少字段回答“内容来自哪里、能不能追责、是否有第三方素材”。



```JSON
{
  "task_id": "windows-powershell-ads-001",
  "task_version": "0.8.0",
  "source_type": "expert_constructed",
  "source_document": "<脱敏后的需求文档引用>",
  "source_section": "3.1 Windows 专项交付内容形态; 4.3 Evaluator 与终态判分",
  "repo": null,
  "commit": null,
  "issue_or_pr": null,
  "license": "Original pilot assets authored for this evaluation; no third-party code bundled.",
  "source_time": "2026-09-07",
  "lineage": "Windows procurement requirement -> expert-constructed pilot -> local calibration",
  "pollution_risk": "Low for local draft; external exposure review pending.",
  "authorization": "No external repository or third-party asset is included."
}
```



规范：



- 命名整体倾向拼音、英文单词或驼峰；避免用单字母变量、随意缩写和逐段复数的泛泛集合。局部块例如问卷分组、段落、阶段卡片可以用更窄的语义名，如 `blocks`、`sectionFragment`，并在整个文件中一贯使用。
- 外采题目要保留 `source_type: "vendor_delivery"` 并填写供应商来源、校验 hash 或冻结流程。
- 逐步替换虚构示例为真实值；本机私有路径、账号、URL 会泄露上下文的值不要进入文档或题面。
- 来源被二次修正时，继续在 `task-id` 相关 DTO 明确说明实际含义，而不是靠同名猜意。

### 3.3 `instruction.md`



推荐按下面的章节顺序写，确信、具体、单一含义。一个行为要点不要在多处互相矛盾地描述两遍。



```Markdown
# Windows 来源标记清理器：批处理事务版

## 背景

只有一段话：用户遇到的实际问题是什么？为什么现在要做这次改动？

## 目标

点名需要完善的文件与函数。优先以唯一点位加清晰行为描述。

## 必须满足的行为

1. 输入含义：列出普通模式接受的输入形式。
2. 成功状态：描述真实副作用和返回的状态。
3. 失败状态：逐类说明应返回 Failed 的条件，不允许模糊表述。
4. 幂等/隔离：重复调用、部分失败或重复路径时要如何表现。
5. 协议字段：规定 API 对外对象和结果 JSON 字段。

## 边界和约束

- 说清平台、网络、权限和性能要求。
- 明确允许修改的点位；必要时明确禁止修改的相邻模块。

## 运行入口

提供真实可执行指令。例如：`.\workspace\run.ps1`

## 用户可见验收

列出专家应能演示的场景。
```



题面写作规范：



- 每个“必须满足的行为”都要落在真实的可观察副作用、返回值、日志、指标或终态，不要写到抽象思路为止。
- 行为项编号稳定；不要在一处用例子引入新的特殊条件却不在边界和验收中重复体现。
- 给专家一个明确的最短公共可复现场景，再加分页/卡片/清单展示其他变体。

### 3.4 `environment/run.ps1`



主运行入口必须简单，只负责确定准备、执行和退出码。



```PowerShell
[CmdletBinding()]
param(
    [string]$TaskRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputPath = $null
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $TaskRoot 'results\result.json'
}

& (Join-Path $PSScriptRoot 'prepare.ps1') -TaskRoot $TaskRoot
if ($LASTEXITCODE -ne 0) {
    exit 2
}

& (Join-Path $TaskRoot 'tests\run_tests.ps1') `
    -WorkspaceRoot (Join-Path $TaskRoot 'workspace') `
    -OutputPath $OutputPath

exit $LASTEXITCODE
```



规范：



- `run.ps1` 只调用一次 `prepare.ps1`；不要在同一进程生命周期里重复准备或留下不可重入状态。
- 每个子命令的退出码都要向上传递；环境准备失败保留错误码，测试结束返回测试退出码。
- 用 `Join-Path` 组合 Windows 路径，不要用字符串拼接拼出易错分隔符。
- 当活动码本内既有的导出映射与本平台约束冲突时，以本文件为准。
- 输出位置默认集中在 `results/`；不要允许分散写盘或依赖当前目录。

### 3.5 `environment/prepare.ps1`



这是环境准备脚本，不是候选代码的一部分。专家应把它理解成“每个全新 run 开始时的可靠 stage setter”。



推荐头部：



```PowerShell
[CmdletBinding()]
param(
    [string]$TaskRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
```



正文顺序：



1. 验证必需运行时、只读资产或已有 workspace 存在。
2. 清理上次运行留下的瞬态产物。
3. 创建固定 fixture。
4. 打印简短可关联的操作成功信息。
5. 任一步骤失败时保留退出码，不要吞异常。

### 3.6 `environment/cleanup.ps1`



该文件必须有真实清理能力。常见需要覆盖的对象包括：



- 测试产生的临时目录和临时文件；
- 构建产物或缓存；
- 注册表、计划任务、服务配置等系统终态；
- 由 fixture 启动的驻留进程；
- evaluator 自己创建的临时 root。

清理脚本应可重复运行，并且在清理后能让独立复核证明没有残留。



### 3.7 `tests/rubric.json`



`rubric.json` 是权威评分规则。每个 item 都应有稳定 ID、可观察行为和精确的 `test_ids` 映射。



```JSON
{
  "schema_version": "programmatic-v1",
  "task_id": "windows-powershell-ads-001",
  "task_version": "0.8.0",
  "items": [
    {
      "rubric_id": "ads-removal",
      "description": "Removes exactly the Zone.Identifier stream and preserves the primary file.",
      "type": "programmatic",
      "weight": 0.15,
      "test_ids": [
        "result-removed",
        "zone-stream-removed",
        "other-streams-preserved"
      ],
      "evidence_source": "results/result.json",
      "pass_condition": "Target stream is absent; primary bytes, identity, length, attributes and timestamps are unchanged.",
      "failure_reason": "The implementation removes the wrong stream, misses the target stream, or replaces the primary file."
    }
  ],
  "total_weight": 1.0
}
```



规范：



- `rubric_id` 只描述稳定类目，不承担页面样式路由语义。
- 一个 rubric 内的 `test_ids` 有先后依赖时，用 `requires_test_ids` 明确门槛，不要把映射分散到环境或物料中。
- 描述中的风险等级、失败原因和证据来源都必须可在提交时落地；不要写“若干项”“等效方案”或只存在于他人草图里的概念。
- 保持同一类描述术语稳定，不要为了排版创建看似不同实则相同的行为类别。

### 3.8 `tests/judge.toml`



这是评分判器的配置摘要，重点是绑定关系和防篡改。



```TOML
schema_version = "outside-six-programmatic-rubric-v1"
authoritative_source = "rubric.json"
source_sha256 = "<rubric.json 的 SHA-256>"
programmatic_weight = 1.0
llm_judge_weight = 0.0

[[rubrics]]
rubric_id = "ads-removal"
weight = 0.15
test_ids = ["result-removed", "zone-stream-removed", "other-streams-preserved"]
pass_condition = "Target stream absent; primary file identity and bytes unchanged."
```



不要同时允许 `rubric.json` 和 `judge.toml` 各自自由漂移。改动 `rubric.json` 后，如果管道要求，必须重新生成或校对 `judge.toml` 的 hash 和对应条目。



### 3.9 `tests/test.ps1`



`test.ps1` 是平台调用题目测试的稳定入口。本文只需要明确它在题包内的接口职责，不展开仓库级的装配或生成过程。具体断言、场景准备和结果汇总仍分别放在 `run_tests.ps1`、探针脚本和 `aggregate_results.ps1` 中。



规则：



- 不要在 `test.ps1` 中重复实现测试断言或评分规则。
- 测试行为变更应落到 `run_tests.ps1`、探针脚本、`rubric.json` 或汇总脚本。
- `test.ps1` 必须提供稳定的调用方式，并把实际测试的退出码原样返回给调用方。

### 3.10 `solution/**`



`solution/` 是组织方用来证明“刚好这个问题存在可重复答案”的位置，不是教学教程目录。



常见布局：



```Plain Text
solution/
├── README.md         # 参考实现满足了什么行为契约
├── solve.ps1         # 从冻结源/模板构建参考实现
├── reference.patch   # 与基线的最小参考 diff
└── reference/        # 完整参考源码，当 patch 无法承载复杂多文件变化时使用
```



`solve.ps1` 应遵守以下规则：



- 每次运行幂等；
- 不意外附带网络请求或临时日志/密钥；
- 被替换或拷贝的目标文件行为稳定；
- 使用仓库或组织认可的清理/备份机制，而不是自行长期占有用户文件；
- 会在紧凑终端日志中打印临时文件时选择不易歧义的 key（例如带操作对象的 stable slug），并确保自然排序。

## 4. 注释和文案规范



### 4.1 什么时候写注释



只在解释非显然的用途、边界、平台限制、不变量或历史依据时写注释。不要写“这是变量”“循环数组”“执行下一步”这类噪声。



推荐：



```PowerShell
# Restore must remove only the marker stream; rebuilding the primary file
# would invalidate its identity, timestamps, attributes and unrelated streams.
```



避免：



```PowerShell
# Remove stream
Remove-Item -LiteralPath $Path -Stream 'Zone.Identifier'
```



### 4.2 文件编码和路径



- 脚本使用 UTF-8，带不带 BOM 应与现有仓库保持一致；不要在一个任务里混用多种编码。
- Windows 路径统一用 `Join-Path` 组合；只对已知 `C:\\` 常量使用显式转义。
- 相对路径必须说明相对哪个根目录，通常是任务根目录或脚本所在目录。

### 4.3 生成文件头



机器生成文件必须一眼可见：



```Plain Text
Generated ... Do not edit.
```



同时应说明生成来源或应修改的源文件，避免之后的人把小的格式化修改当成修复。



### 4.4 语言和语气



- 中文描述用主动语态：“`run.ps1` 串接 prepare 与测试”，不要写“脚本被执行了”。
- 技术名词保留原文，例如 `FAIL_TO_PASS`、`PASS_TO_PASS`、NTFS ADS、`OrdinalIgnoreCase`。
- 不要承诺未验证的网络隔离、管理员能力或算力结果。

## 5. 专家训练练习：三分钟读包



给专家一个未知题包时，让他按这个顺序回答：



1. 打开 `task.toml`，说出题目 ID、镜像、超时和资源。
2. 打开 `source.json`，判断这道题是官方标准构建、外采重构还是本地起草。
3. 读 `instruction.md`，找出唯一允许修改的点位。
4. 找到 `environment/run.ps1`，确认主运行路径会走到哪份测试入口。
5. 打开 `tests/rubric.json`，列出评分类别和权重大小。
6. 找到关键测试脚本，确认每个 rubric 是否都有对应 `test_id`。
7. 只用 `solution/README.md` 验证参考契约，不阅读参考代码，直到评审确有必要。

### 可填写的 demo 表格



让每人在自己的题包旁完成这张表：



| 问题 | 你的答案 | 证据文件 |
|-|-|-|
| 参与者要修改哪个文件/函数？ |  | `instruction.md` |
| 主运行入口是什么？ |  | `environment/run.ps1` |
| 如何准备 fixtures？ |  | `environment/prepare.ps1` |
| 测试产物落在哪里？ |  | `tests/run_tests.ps1` |
| 判分规则是什么？ |  | `tests/rubric.json` |
| 哪些测试必须执行？ |  | `tests/run_tests.ps1`、`tests/rubric.json` |
| 清理后会检查哪些残留？ |  | `environment/cleanup.ps1` |
| 参考答案证明了什么？ |  | `solution/README.md` |



任何人答不出某一行的证据文件位置，都说明题包层级还不够清楚。



## 6. 发布前检查清单



完成一份题包前，至少逐项核对：



- [ ] 目录名、`task.toml` 与 `source.json` 中的 `task_id` 互相一致。

- [ ] `instruction.md` 只有面向参与者的必要信息，不泄漏答案。

- [ ] 允许修改的点位在题面、可执行入口和验证场景中都能一致落点。

- [ ] 敏感值没有出现在日志、注释、fixture 名或 `source.json`。

- [ ] 每个 rubric 都只有一套权威计数器和映射，能追溯到确定的 test_id。

- [ ] 断言覆盖终局状态、文件/注册表内容、时间戳、日志和必要的审计产物。

- [ ] 特殊平台用例（断网、无管理员、Windows 安全语义）在题面或测试矩阵中有明确标识。

- [ ] 仅由 fixture 提供的信息不要抄进题面，只给引用键或摘要。

- [ ] `solution/**` 已从普通模型资产剔除。

- [ ] `tests/test.ps1` 能从题目目录正常启动测试并准确返回退出码。

## 7. 一个浓缩示例：从“看到文件”到“写对所有测试”



题目原型：批处理清理 NTFS ADS 来源标记。



1. **题面**：写清楚输入可以是空格、中文、方括号，必须使用 literal path。
2. **业务状态机**：成功后主文件身份、字节、时间戳和无关数据流都不变。
3. **失败路径**：目录、不存在、reparse point、另一条数据流都必须返回 `Failed`。
4. **幂等**：无标记返回 `AlreadyClean`，重复调用不允许表现出清掉了原本不存在的流。
5. **事务**：Atomic 模式必须先预检整批，再做变更；提交失败要最佳努力回滚。
6. **测试**：逐项建立 fixture，验证流、内容、identity、长度、时间戳、属性。
7. **rubric**：ads-removal、safe-inputs、preservation、audit 分别绑定自己的 `test_id`。
8. **solution**：只声称参考解满足以上契约，并通过全部 29 项程序化检查。

这就是这套格式最重要的原则：每一个分层文件都围绕同一个题目协议协作，而不是各自追求“看起来专业”。同一份意图最好只用一处权威表达；一份题包只有在题面、环境和测试充分一致，并且经过正确聚焦评审通过后，才能推向生产。