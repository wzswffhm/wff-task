# 《windwos-第二版》规范解析报告

> 解析对象：`C:\Users\Administrator\Desktop\windwos-第二版.pdf`（16 页，版本日期 2026-09-28，替代 v1.0.2）
> 解析日期：2026-09-29
> 原文抽取：同目录 `windwos-第二版_原文.txt`

---

## 一、文档性质与定位

**这不是一道题的题目说明，而是采购方发布的《Windows 专项 Coding Bench 数据采购》交付规范与验收标准。**

| 维度 | 内容 |
|---|---|
| 需求名称 | Windows 专项 Coding Bench 数据采购 |
| 适用对象 | 供应商、生产团队、验收团队 |
| 数据用途 | Agentic Coding 模型评测、横向比较、能力缺陷分析、稳定性回归 |
| 采购规模 | **不冻结**——正式题数/候选题数/批次安排另书面确认 |
| 最终交付 | 计分题本体 = 符合**冻结 Schema** 的标准 Harbor Task；伴随材料放在**题包外的批次级交付区** |

**核心判据一句话**：能真实暴露 Coding Agent 在 **Windows** 开发/调试/构建/运行/系统状态处理上的能力缺陷。

---

## 二、采购目标与核心原则（第二章）

题目难度必须来自**真实工程语义、跨文件状态、执行时序、环境约束、版本差异、失败路径、多目标权衡**。

**禁止**难度来自：歧义、信息缺失、错误环境、错误测试、冷僻知识背诵。

正式题必须**同时**满足 5 条：

| # | 原则 | 含义 |
|---|---|---|
| 1 | Windows 有价值 | 核心实现、错误根因或验收机制**实质依赖** Windows 平台语义 |
| 2 | 能力可真实验证 | Agent 在冻结 Windows 环境完成；Evaluator 在**真实 Windows Runtime** 触发验证 |
| 3 | 题面与测试一致 | 每条计分 testcase 可追溯到题面明确要求 / 题内可见公共契约 / 修改相关兼容性要求 |
| 4 | 验证功能而非写法 | 允许等价实现；**不得**绑定 Golden 的私有函数名、参数个数、内部布局、固定调用顺序或代码文本 |
| 5 | 可复现可审计 | 初始态、Golden、模型运行、逐 testcase 结果、环境身份、最终补丁**闭合对应** |

> **红线**：不得因某模型全失败、模型自报成功、实现接近 Golden、进度紧张而放宽题面/测试/验收标准。

---

## 三、Windows 专项准入（第三章）

### 3.1 价值反事实判定（逐题必答）

> **如果将目标 OS 替换为 Linux 或 macOS，主要实现、错误根因和 Evaluator 是否基本不变？**
> 若"是" → **原则上不属于 Windows 专项题**。

**以下情况不能单独证明 Windows 价值**（6 条常见误判）：

1. 题面出现 PowerShell、批处理、盘符、反斜杠、C# 或 Windows 路径
2. 将通用算法、普通业务逻辑或跨平台任务放到 Windows 机器运行
3. 只增加 Windows 启动脚本，核心实现仍与平台无关
4. 只验证编译成功、文件存在、进程存在、日志关键词或代码字符串
5. 使用 WSL 内纯 Linux 结果、Linux Mock、模型自写测试或模型自报代替正式 Windows 判分

### 3.2 可接受的价值来源（12 个主流方向）

| 方向 | 代表性能力 |
|---|---|
| .NET 与桌面应用 | .NET/.NET Framework、WinForms、WPF、WinUI、Windows App SDK、桌面生命周期与部署 |
| 原生开发与互操作 | Win32、C/C++、P/Invoke、COM、ABI、MSVC、Windows SDK |
| Shell 与自动化 | Windows PowerShell 5.1、PowerShell 7、CMD/Batch、非交互执行、错误流与退出码 |
| 文件系统与路径 | NTFS、ADS、ACL、文件锁、长路径、盘符、UNC、符号链接/Reparse Point、大小写与路径规范化 |
| 系统管理 | 注册表、Windows Service、计划任务、环境变量、证书、安装与卸载状态 |
| 进程与执行上下文 | 进程树、Job Object、Session、桌面与焦点、权限边界、生命周期和资源释放 |
| 安全与身份 | UAC、Token、ACL、凭据、最小权限、审计、加密与安全存储 |
| 网络与 IPC | Named Pipe、Windows Socket、SMB、端口与防火墙、进程间通信 |
| 构建、安装与打包 | MSBuild、NuGet、MSI/MSIX、Inno/NSIS、签名、升级/回滚/卸载闭环 |
| 编码与区域 | UTF-8/BOM、代码页、Locale、中文用户名/路径、时区与区域格式 |
| 诊断与可观测性 | Event Log、Dump、WinDbg、ETW、性能与故障诊断 |
| 设备与系统底层 | 设备 API、驱动、内核交互及需要真实专用环境的工程问题 |

- 知识树用于**引导覆盖**，不要求机械复刻旧版分类或配额
- 每题申报**一个主方向**和必要的次级标签
- 采购方按批次检查覆盖度（是否过度集中在单一语言/题型/冷门 API）
- **S1–S2 级的表面 Windows 题不得进入正式集**

---

## 四、题目内容与来源要求（第四章）

每题**必须具备 8 项**：

1. 明确、真实且**不泄露解法**的 `instruction.md`
2. 可稳定复现初始问题的代码仓、工程资产或系统状态
3. 冻结的 Windows 版本、Edition、架构、Locale、Shell/Runtime、依赖与权限
4. 可执行、可清理、可恢复的环境
5. Oracle / Reference Solution
6. 与参考解**实现相互独立审查**的隐藏测试，含 F2P 与 P2P
7. 来源、Repo、Commit、Issue/PR、License、授权、Lineage 与污染风险记录
8. 初始态、Golden、空实现/错误反例和模型运行的可核对结果

**题面应写**：背景/现象、目标、功能边界、约束、允许修改范围、用户可见的验收标准
**题面不得写**：Golden Patch、答案路径、隐藏测试、精确修改位置、可直接照抄的实现步骤

**禁止**：重复题；仅替换名称/常量/路径/语言/描述的表面变体题
**被测工作树与可见 Git 历史不得包含**：Solution、Golden Patch、隐藏 Tests、预期答案或 Reward 信息

---

## 五、标准 Harbor 交付要求（第五章）

### 5.1 最终题包

- 每题必须是采购方**冻结 Harbor Schema 可直接加载、执行、判分**的标准 Task
- **默认按 Harbor schema 1.3 对接**；平台若在生产前确认更新版，以书面冻结版为准
- 固定结构（**不得**为兼容旧结构新增自定义必需目录或私有字段）：

```
<task-id>/
├── task.toml
├── instruction.md
├── environment/
├── solution/
└── tests/
```

> ⚠️ **"题包只包含标准 Harbor" ≠ 只交付题包。**
> 模型运行记录、质检证据、来源与授权、标签、版本、Hash、Badcase 归因、批次统计均为**强制交付物**，
> 必须完整保存在**题包外**的伴随交付区，并通过 `task_id + task_version + task_hash` 与对应 Harbor Task 唯一关联。
> **缺少伴随材料的题目不得验收。**

### 5.2 各部分职责

| 部分 | 职责 |
|---|---|
| `task.toml` | 声明任务身份、版本、资源、超时、环境和标准执行入口 |
| `instruction.md` | Agent **唯一**题面，内容与实际下发版本一致 |
| `environment/` | 提供可复现初始工作区和目标 Windows 执行环境；依赖版本锁定；**禁止泄露 Solution 和隐藏 Tests** |
| `solution/` | 可执行参考解或参考补丁，**仅用于 Golden 验证**，不向 Agent 暴露 |
| `tests/` | 独立程序化 Verifier，执行 F2P、P2P 及必要的 Windows 终态检查 |

> **Windows VM / Server / 桌面 / 企业环境 / 驱动 / 硬件题，不得为迁就目录形式而用 Linux Mock 或普通容器替代。**
> 必要的 Runner/Adapter 由平台与供应商在 Harbor 标准扩展机制内冻结，**不能改变"最终仍是标准 Harbor Task"的要求**。

### 5.3 版本与协作

- 统一使用 **GitHub 或双方确认的 Git 版本库**协作；**不再以聊天附件和多份压缩包作为主版本传递方式**
- 每题使用**稳定 task_id + 显式版本号**
- 任何影响题面/环境/Solution/Tests/判分的修改**必须升级版本并记录变更**
- **禁止静默覆盖**已提交或已验收版本
- 提交、Tag/Release、环境 Digest 和批次清单必须**可相互定位**
- 最终交付可按约定导出，但 **Git 冻结版本为唯一来源**

### 5.4 批次交付结构（暂定，待多团队联调冻结）

先参考 `outside_harbor-dev_0911.zip` 已采用的提交结构：

```
delivery-<batch>-<version>/
├── outside_harbor/                     # 沿用：每题一个平台导入 JSON
│   └── <task-id>.json
├── outside_harbor-assets/              # 沿用：题目与执行资产
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

关键约定：

- `outside_harbor/<task-id>.json` 用于**平台导入，不等于**标准 Harbor Task；正式题本体以 `outside_harbor-assets/<task-id>/` 中**通过冻结 Schema 校验**的 Harbor 内容为准
- 两者必须引用**同一个** `task_id + task_version + task_hash`，不得各自维护互相偏离的题面或判分规则
- 历史包中每题根目录的 `source.json`、运行证据和质检材料，本轮应移入 `delivery-extras/tasks/<task-id>/`
- 历史 `tests/judge.toml`、`tests/rubric.json` 和聚合器**不得原样继承其权重**，须改为 **required F2P/P2P 二值判分**
- `.ap-tools/` 目前可先按压缩包形态保留；但必须区分仍在使用的工具、历史修复脚本和旧版本证据；**无论位置如何，均不得进入 Agent 可见环境**
- 离线 NuGet/npm/Go/Rust 依赖、fixture、baseline repo 可保留在 `environment/` 或 `tests/` 的标准允许位置，但必须**版本锁定、有 Hash、来源合法**，且不泄漏 Solution 或隐藏验收内容
- **大文件不能仅因"属于资产"就全部移到题外**，否则破坏离线可复现性

### 5.5 伴随交付物最低覆盖（8 项）

1. 题目来源、License/授权、Repo、Commit、Issue/PR、Lineage、污染和重复风险
2. 主知识方向、次级标签、语言、任务类型、目标 Windows 环境和难度说明
3. `requirement → testcase → F2P/P2P` 双向映射及每项依据
4. no-change、Golden、干净重建、等价实现、错误反例、清理和恢复结果
5. Qwen/Opus 各 3 次 + GLM/Kimi 可运行性检查的配置、真实模型标识、运行状态、逐 testcase 结果、轨迹、最终补丁、耗时和 Badcase 归因
6. 环境、Task、Solution、Tests、运行日志和结果文件的版本、Digest/Hash
7. Hack/答案泄漏检查、证据完整性缺口、已知问题、整改和复验记录
8. 批次清单、覆盖统计、验收状态和版本变更记录

> 这些材料**不得在 Agent 作答阶段可见**，不得通过镜像、挂载、Git 历史、缓存或日志泄漏到被测工作区。
> 采购方可导入内部质检平台，但**平台录入不能替代原始文件和 Hash 交付**。

### 5.6 跨目录身份与一致性门禁

**唯一验收身份 = `task_id + task_version + task_hash`**

必须满足：

- Harbor Task、平台配置、镜像 Digest、验收材料和模型运行均**显式引用同一身份**
- `task_id` 在文件名、`task.toml`、来源材料、平台配置和结果文件中一致
- **镜像标签不是不可变身份，必须另存实际 Digest**
- 发现类似历史 **D6-002 来源包内部误用 D6-001 ID** 的情况，必须在正式交付前修正，**不得只在备注中长期兼容**
- 任何题面/环境/Solution/Tests/required testcase 变更均升级题目版本并重新执行受影响验收
- 批次自动校验必须**拒绝**：缺引用、错 ID、错版本、Hash 不匹配、同一题多真源

---

## 六、测试与二值评分标准（第六章）

### 6.1 testcase 与题面映射（双向）

```
题面要求/公开契约 → testcase → F2P/P2P 分组
testcase → 题面要求/公开契约 → 预期行为
```

**必须逐条检查**：

- testcase 是否严格对应模型实际收到的题面或当时可见的公共契约
- 是否加入**未声明要求、与题面相反的要求或事后新增契约**
- 是否触发候选代码的**真实生产路径和目标 Windows 机制**
- 是否验证**输入输出、公共接口、产物、异常、状态或副作用**，而非特定代码写法
- 是否能接受**独立等价正确实现**
- **P2P 是否在初始态通过且与修改范围相关**
- **F2P 是否确由目标缺陷导致初始态失败，并在 Golden 后通过**

> 公开 API、协议、文件格式或 ABI 本身有明确契约时可严格验证；
> **不得将 Golden 新增的私有函数名、签名、代码布局或固定调用方式变成隐藏要求。**

### 6.2 正式计分（二值）

```
score = 1  ⟺  所有 required F2P 均 PASS 且 所有 required P2P 均 PASS
score = 0      存在任一 required testcase 为 FAIL
score = null/INVALID   存在 required testcase 未执行、缺失、SKIP，
                       或发生环境、Runner、Verifier、解析、授权等基础设施异常
```

- **不设置 testcase 权重、部分分、LLM/Agent Judge 或主观质量分**
- **INVALID 不得伪装成模型 0 分**，不得纳入难度统计；修复后须在**相同冻结条件**下补跑
- **不得**临时缩小 required 清单、改变分母或删除失败 testcase 以得到 1 分
- 测试级通过数量**仅**用于故障定位和"双方均为 0"时的模型区分度辅助比较，**不产生任何正式部分分**

### 6.3 功能测试要求

- 核心断言必须验证**真实功能、Windows 行为或系统终态**
- Patch Diff、源码关键词、正则、文件/进程/端口存在和日志文本**只能作为辅助证据**
- **构建成功不能作为核心功能的唯一判据**
- Mock/Stub 必须与冻结真实依赖的输入、输出和错误语义一致
- 异步、子进程和负观察场景必须有**完成回执或独立健康哨兵**，不能把提前退出或观察器未启动判为通过
- 每次运行前**清除旧构建产物和系统残留**，确保产物来自本轮候选代码
- 注册表、服务、计划任务、证书、ACL、防火墙、安装器、驱动和设备变更**必须可清理、可恢复**

---

## 七、Golden、空跑与稳定性验收（第七章）

### 7.1 同一身份运行
Golden、no-change 和模型候选必须使用**同一** base、环境、依赖、测试树、评分规则和资源预算。
Golden 必须有**直接证据**证明参考解已实际应用，不能只依赖环境变量、任务名称或日志标题。

### 7.2 Golden path（干净环境）
- 所有 required F2P 与 P2P **执行且 PASS**
- **正式分数为 1**
- **无 SKIP、MISSING、ERROR、旧产物复用或隐藏环境依赖**
- 最终补丁、测试树、环境和日志身份可以核对

> Reference Solution **不是天然真值**。若 Golden 与题面冲突、只适配某种内部写法或破坏既有行为，
> 应修复题目/测试/参考解，**不得为保证 Golden=1 而修改题意**。

### 7.3 no-change 与错误反例（干净环境）
- **P2P 全部通过**
- **至少一个核心 F2P 因目标缺陷失败**
- **正式分数为 0**
- 失败原因**不是**依赖缺失、测试语法、环境未就绪或其他基础设施问题

除 no-change 外，还应按题目风险验证：空实现、固定返回、提前退出、硬编码、只修一半、吞异常、禁用功能等反例。

### 7.4 稳定性（提交验收前至少完成）
- no-change 独立运行 **3 次**，结果均为 **0**
- Golden 独立运行 **3 次**，结果均为 **1**
- 至少**一次**从干净环境重新构建或恢复后复验
- 每次 required testcase 集合和终态一致，无**非模型原因**抖动
- 清理或快照恢复后**无影响后续运行的残留**

---

## 八、多模型验证与准入门槛（第八章）

### 8.1 冻结条件
所有比较必须使用**相同的** Harbor Task 版本、Harness、Windows 环境、工具权限、网络策略、资源预算和采样配置。**环境恢复后再开始下一次独立运行。**

### 8.2 主要模型

**Qwen3.8-Max-0902 与 Opus 5 每题各独立运行 3 次**。只统计 VALID 运行，INVALID 必须查明原因并补跑。

| 指标 | 定义 |
|---|---|
| `model_score_sum` | 同一模型 3 次二值正式分数之和，取值 **0–3** |
| `testcase_pass_sum` | 同一模型 3 次运行中 required testcase 的 PASS 数量总和；**仅用于双方正式分均为 0 时比较**，不形成部分分 |

**单题须满足以下任一条件**：

1. `Opus5.model_score_sum > Qwen3.8-Max-0902.model_score_sum`；**或**
2. 两者 `model_score_sum = 0` 且 `Opus5.testcase_pass_sum > Qwen3.8-Max-0902.testcase_pass_sum`

若两者正式分和相同且不全为 0，或双方均为 0 但 testcase 表现没有严格区分 →
**该题区分度不满足准入要求，应分析后整改或替换。**

> **模型门槛不能覆盖数据质量门槛。** 即使满足分差，存在题面歧义、不可解约束、错误测试、环境故障、
> 薄题、答案泄漏或 Windows 价值不足时仍不得验收。
> **不得为制造分差而增加题面未声明要求、错误隐藏测试或冷门单点陷阱。**

### 8.3 辅助模型
**GLM-5.3 与 Kimi K3 每题至少完成 1 次有效运行**，主要用于确认：

- Agent 能正常进入、读取和修改工作区
- 构建、测试和结果采集链路可运行
- 不存在模型无关的 infra、权限、依赖或 Verifier 质量问题

不要求 GLM-5.3、Kimi K3 与 Qwen/Opus 形成固定排名，也不要求各跑 3 次。
若任一辅助模型因**题目或基础设施**问题无法完成有效运行，必须先修复；
若属**模型自身能力失败**且运行链路有效，可按真实结果记录。

---

## 九、旧 6 题转换要求（第九章）

`outside_harbor-dev_0911.zip` 中的 6 题是本轮旧题转换和提交目录的直接参考。

**必须先做变更对比**：把该压缩包中的**修复版本**与供应商**最初提交的原始版本**逐题对比，形成变更清单，说明：
改了什么、原问题是什么、修复是否已经动态验证、是否应保留到本题新版本、是否值得沉淀为后续新题的通用生产规范。

> **无法取得原始提交或无法确认变更来源时，应明确标为证据缺口，不得把现状全部宣称为已验证修复。**

### 每题必须重新完成（12 项）

1. 以**冻结 Harbor Schema 重新校验** `task.toml`、目录和入口；历史文件能运行 **≠** 已符合本次标准 Schema
2. 将 `instruction.md + task.toml + environment/ + solution/ + tests/` 整理为**唯一标准 Harbor Task**；`source.json`、运行证据和质检材料放入 `delivery-extras/`
3. 保留 `outside_harbor/<task-id>.json` 作为现阶段平台提交入口，并与 `outside_harbor-assets/<task-id>/` 的**同一身份三元组**绑定
4. **统一并修正题目 ID、版本和 Hash**，消除历史 `task.toml`、`source.json`、平台 JSON、镜像标签和来源包之间的身份冲突
5. **重做题面—testcase 双向映射**，删除越界、相反或绑定内部实现的测试
6. 评分统一改为 **F2P/P2P 全过得 1，否则得 0**，清除 `judge.toml`、`rubric.json` 及聚合器中的**权重与部分分语义**
7. **重新验证 Golden=1、no-change=0**，并逐项解释所有异常、SKIP 和缺失
8. 检查测试是否真正触发 Windows 机制，避免路径/readiness、依赖、权限、旧产物、Mock 失真和异步提前退出等历史问题
9. 保留离线依赖、fixture 和 baseline repo 等真正影响复现的执行资产，但核对**来源、Hash、体积、隐藏边界和实际加载路径**
10. 盘点 `.ap-tools` 中仍需要的发布、Golden、网络、轨迹和 QC 工具；标明有效版本，删除或隔离过期/重复/仅服务历史版本的工具
11. **重新执行 Qwen/Opus 各 3 次及 GLM/Kimi 可运行性检查**
12. 与**新题使用相同版本库、批次流程和验收标准**交付

> 历史"已修""已通过"或旧分数**仅作为风险线索**，不替代本次实测。
> 若转换后仍不能满足 Windows 价值、二值判分、稳定性或模型区分度要求，应**淘汰并用新题替换**。

### 9.1 修复对比与后续复用要求

旧 6 题须在 `delivery-extras/tasks/<task-id>/original_comparison/` 中至少保留：
原始提交身份及 Hash、当前压缩包版本身份及 Hash、文件级变更清单、变更原因、验证证据、保留/撤回结论、对后续新题的复用建议。

**重点判断以下历史修复是否应转为后续题目的通通检查**（而非直接复制实现）：

- Windows 根目录、工作目录、`WINDIR/SystemRoot`、Shell 和路径解析是否与真实 Runner 一致
- Node/.NET/NuGet 等工具链和离线依赖是否预装、锁版本并在**断网条件**下真实可用
- prepare、Agent 修改、patch capture 和 verifier 是否操作**同一个实际工作区**
- 构建失败是否立即停止，是否清理旧二进制和旧结果，避免运行历史产物伪通过
- required testcase 是否完整执行；缺失、重复、SKIP、ERROR 和解析失败是否**正确标为 INVALID**
- 环境/fixture/权限异常是否与候选功能失败**分开**，不能用大 try/catch 静默变成模型 0
- Mock、跨进程、异步回执和负观察是否保真，不能只凭退出码、文件存在或固定等待判定
- 网络访问、外部源码下载、本地答案搜索、评分目录读写和轨迹完整性是否可审计
- Golden 是否真实应用参考解、no-change 是否稳定为 0、每项结果是否可由**同版本日志和 Hash** 复核

> "值得后续题目参考"应沉淀为**风险、检查方法、正反控制和结果字段**，不要求后续题机械复用旧脚本、旧 Mock、旧阈值或旧目录。

---

## 十、生产、质检与验收流程（第十章）

项目**直接进入产题**，不以长周期 Pilot 阻塞生产；但首批代表性题应尽快完成格式和判分闭环核验，发现的共性问题必须**同步修正后续题目**。

### 10.1 推荐流程

```
候选与 Windows 价值预筛
→ 来源/授权/污染/重复检查
→ 标准 Harbor 构题
→ 题面与 testcase 双向审查
→ Windows 环境、Golden、no-change 与反例验证
→ Qwen/Opus 各 3 跑，GLM/Kimi 可运行性检查
→ 逐 testcase、轨迹、Hack 与分数复核
→ 整改复验
→ 版本冻结与正式交付
```

### 10.2 单题验收层级（11 层）

| 层级 | 必查内容 |
|---|---|
| 来源与合规 | Repo、Commit、License、授权、隐私、Lineage、污染和重复 |
| Windows 准入 | 反事实判定、目标 Windows Runtime、核心 Windows 机制是否位于成功路径 |
| Harbor 格式 | 标准目录、Schema、入口、版本、资源和超时可被平台直接加载 |
| 环境 | 可构建/恢复、依赖锁定、权限可控、清理无残留，**E2–E4 不以 Mock 替代** |
| 题面与测试 | 要求真实下发、双向映射完整、无越界要求、功能验证且接受合理多解 |
| 对照 | no-change 3 次为 0，Golden 3 次为 1，干净重建/恢复成立 |
| 评分 | 无权重、无部分分、F2P/P2P 全过为 1 否则为 0，异常为 INVALID |
| 多模型 | Qwen/Opus 各 3 次满足区分度；GLM/Kimi 无模型无关运行故障 |
| 安全与完整性 | Solution/隐藏 Tests 不可见；无网络取答案、本地搜答案、篡改测试/评分或旧产物复用 |
| 版本 | 题包、环境、测试、Solution、运行结果和整改记录可对应到同一冻结版本 |

### 10.3 逐运行状态与归因

| 类别 | 取值 |
|---|---|
| testcase 状态 | `PASS` / `FAIL` / `SKIP` / `MISSING` / `ERROR` / `NOT_RUN` |
| 运行有效性 | `VALID` / `INVALID` / `PENDING` / `CANCELLED` |
| 质检结论 | `PASS` / `FAIL` / `FLAG` / `BLOCKED` / `N/A` |

> 编译失败、超时、缺测试和解析错误**只是现象**，必须继续定位为：题面、测试、环境/平台、聚合器、
> 证据完整性、模型能力或 Hack 等**根因**。
> **只有题面清晰、测试公平、环境有效且证据完整时，才能归为模型能力失败。**

### 10.4 Hack 与答案泄漏审查

审查 Agent 是否：

- 联网搜索、下载上游源码、PR、Commit、Patch 或答案
- 读取本地 Solution、Golden、隐藏 Tests、其他题目、Git 残留、缓存或历史制品
- 修改 Tests、Verifier、结果文件或环境以绕过判分
- 复用旧二进制、伪造 PASS、跳过测试或只打印成功

> 报告须区分**尝试 / 成功访问 / 实际使用 / 已证明影响成绩** 四个层级。
> **关键词未命中不能证明绝对无 Hack；请求失败也不能误写为下载成功。**

### 10.5 一票否决（14 条）

出现任一情况，单题**不得进入正式集**：

1. Windows 反事实判定不通过，或未在真实目标 Windows Runtime 判分
2. 题面不可解、关键约束缺失，或实际下发内容与验收要求不一致
3. Golden 无法稳定得 1，或 no-change 无法稳定得 0
4. P2P 在 base 失败、F2P 与目标缺陷无关，或 required testcase 缺失/跳过却被计分
5. testcase 与题面冲突、增加未声明要求、误杀合理多解，或绑定 Golden 私有写法
6. 核心功能主要依靠字符串、正则、代码 Diff、文件存在、模型自报或 Linux Mock 判定
7. 使用 testcase 权重、部分分、LLM/Agent Judge 或主观软质量分
8. 环境、Runner、权限、依赖或 Verifier 缺陷被记为模型 0 分
9. Solution、隐藏 Tests、答案或凭据泄漏，或 Agent 能篡改可信评分结果
10. 环境不可恢复、运行有残留、结果不稳定或依赖旧产物
11. 来源、License、隐私、授权或数据权属不清
12. 重复题、表面变体题、冷门薄题，或与申报 Windows 能力实质不符
13. 不满足第八章模型区分度要求，整改后仍无有效区分
14. 无法在约定时间和资源预算内稳定完成判分

---

## 十一、交付完成定义（Definition of Done，第十一章）

单题**同时满足**以下条件才可申报最终验收：

1. 通过 Windows 价值反事实判定
2. 是冻结 Schema 可直接加载运行的标准 Harbor Task
3. 题面清晰、实际下发，且不泄露实现
4. 所有 required testcase 与题面/公开契约双向对应
5. 核心测试验证真实功能和 Windows 机制，接受合理等价实现
6. no-change 独立 3 次均为 0，P2P 均通过且核心 F2P 因目标缺陷失败
7. Golden 独立 3 次均为 1，无 SKIP、MISSING、ERROR 或旧产物复用
8. 正式评分无权重、无部分分、无 LLM/Agent Judge
9. Qwen3.8-Max-0902 与 Opus 5 各 3 次有效运行并满足区分度要求
10. GLM-5.3 与 Kimi K3 至少各有 1 次有效运行，无模型无关 infra/质量问题
11. 干净重建或恢复、清理、回滚和残留检查通过
12. 无 Solution、测试、答案、凭据和评分通道泄漏
13. 来源、授权、污染、版本和变更记录完整
14. 采购方最终复验通过并冻结版本

---

## 十二、验收结论、质保与权属（第十二章）

### 验收结论四态

| 结论 | 处理 |
|---|---|
| **通过** | 计入正式采购数量并冻结版本 |
| **退回修改** | 修订后**重新执行所有受影响环节** |
| **淘汰并替换** | 不计入数量，由供应商补充新题 |
| **暂停批次** | 出现集中性质量、安全、泄漏或版本问题，完成根因整改后恢复 |

### 质保与权属

- 数据、代码、测试、环境定义、Reference Solution、运行记录和衍生成果的使用权与交付范围**以合同为准**
- 供应商须保证来源和授权合法，提供**不少于 90 天**的质量保证期
- 因环境漂移、依赖失效、Evaluator 缺陷、答案泄漏、重复或授权问题导致题目失效时，应**免费修复或等量替换**
- 具体交付批次、日期、基础设施提供方、模型账号/API 费用及付款节点**另行书面确认**
- **本文件冻结的是题目质量、标准 Harbor 交付、二值判分和验收口径，不以排期变化降低标准**

---

## 十三、执行检查清单（速查）

### 阶段一：立意与准入
- [ ] Windows 价值反事实判定通过（换 Linux 会变）
- [ ] 主方向 + 次级标签申报，非 S1–S2 表面题
- [ ] 来源/Repo/Commit/Issue/License/授权/隐私/Lineage/污染/重复 检查完毕

### 阶段二：构题
- [ ] 标准 Harbor 目录：`task.toml` / `instruction.md` / `environment/` / `solution/` / `tests/`
- [ ] `task.toml` 符合冻结 Schema，含身份/版本/资源/超时/入口
- [ ] `instruction.md` 清晰、真实、不泄解法
- [ ] `environment/` 依赖锁定、可恢复、不泄 Solution/隐藏 Tests
- [ ] `solution/` 仅用于 Golden 验证
- [ ] `tests/` 独立程序化 Verifier，含 F2P/P2P

### 阶段三：测试与评分
- [ ] 题面 ↔ testcase 双向映射完整，无越界/相反/绑定内部实现
- [ ] 二值评分：无权重、无部分分、无 LLM Judge
- [ ] 核心断言验证真实功能/Windows 行为/系统终态
- [ ] 异步与负观察有完成回执或健康哨兵
- [ ] 副作用（注册表/服务/证书/ACL 等）可清理可恢复

### 阶段四：对照验证
- [ ] no-change 干净环境 3 次全 0（P2P 全过 + 核心 F2P 失败）
- [ ] Golden 干净环境 3 次全 1（无 SKIP/MISSING/ERROR/旧产物）
- [ ] 反例覆盖：空实现/固定返回/提前退出/硬编码/半修/吞异常/禁用
- [ ] 至少 1 次干净重建或恢复后复验

### 阶段五：多模型
- [ ] Qwen3.8-Max-0902 与 Opus 5 各 3 次有效运行
- [ ] 区分度满足（Opus 严格优，或双 0 时 testcase_pass_sum 严格优）
- [ ] GLM-5.3 与 Kimi K3 各 ≥1 次有效运行
- [ ] 无模型无关 infra/权限/依赖/Verifier 故障

### 阶段六：安全与完整性
- [ ] Solution / 隐藏 Tests / 答案 / 凭据不可见
- [ ] 无网络取答案、本地搜答案、篡改测试或评分
- [ ] Hack 审查四层分级记录完整

### 阶段七：身份与材料
- [ ] 全包统一 `task_id + task_version + task_hash`
- [ ] 镜像另存不可变 Digest（非 tag）
- [ ] 无身份冲突（ID/版本/Hash 一致）
- [ ] `delivery-extras/` 伴随材料齐全
- [ ] `checksums.sha256` 生成
- [ ] Git Tag/Release + 环境 Digest + 批次清单可相互定位

### 阶段八：交付
- [ ] Git 冻结版本为唯一来源
- [ ] 采购方复验通过
- [ ] 版本冻结

---

## 附：14 条一票否决 + 14 条 DoD 对照速记

> **一票否决 = 硬伤**（不可进正式集）
> **DoD = 完整交付标准**（全部满足才可申报验收）
> 两者重叠部分即"绝不可妥协的底线"：Windows 反事实、标准 Harbor、二值判分、
> Golden 3×1 / no-change 3×0、模型区分度、无泄漏、身份一致。
