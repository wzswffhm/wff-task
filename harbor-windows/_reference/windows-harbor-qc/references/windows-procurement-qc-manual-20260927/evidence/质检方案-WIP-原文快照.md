# 质检方案-WIP

# 一、流程：标注项目中的质检流程

现有标注项目全流程，不同项目可能有少量差异，但整体流程大同小异；和现有流程相比，质检人员/验收人员和领域专家是不同的人承担了，因此新的流程有如下变动

*   更早的参与到项目中，了解项目的全貌；而不是中途缺人后作为“人力资源”再加入
    
*   角色转换，从执行角色转变成owner角色，负责质检的全流程设计，而不是机械的执行人员
    
*   质检专家作为数据交付的守门员，**必须**参与领域专家的每一次数据交付，为交付结果最终签字盖章
    

质检涉及的数据来源，除了标注平台的标注项目外，还包含了外采的数据集。因此，非常有必要将质检的流程，产品和平台从标注项目中独立出来，供多个来源共用。

![image](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/a/RM0e40vYLsMe5YQa/a57b63f09d3643baa06ceb0bfecb6b490521.png)

# 二、内容：质检清单checklist

为了降低单个task质检的时间，提升整体dataset质检的效率，质检工作主要围绕着质检清单_**checklist**_展开。质检清单由质检项_**checkitem**_组成，_**checkitem**_是质检执行和复用的最小单位，每个_**checkitem**_之间不互相依赖，包含了如下核心内容

*   检查项描述：对于质检项内容的描述
    
*   检查项分类：对于质检项内容的一个大致分类
    
*   检查对象：质检进行需要针对哪些文件，目录等信息
    
*   检查方式：用什么方式进行质检，具体枚举如下
    
*   检查标准：pass和fail的标准
    

**检查项描述**

一段简短明确的文字描述该检查项在检查什么内容

**检查项分类**

检查项的一个分类方法。参考Mercor的分类法，结合项目中的分类，将检查项分为：

*   格式合规/Format Compliance：对目录layout，文件内容格式的检查
    
*   题目质量/Qustion Design：针对题目质量的检查
    
    *   任务有效性/Specificity：题目是否是明确无歧义的，指令是否是自包含的
        
    *   任务可解性/Solvability：验证 Oracle 方案确实能完成任务，且方式是真实可行的
        
    *   任务完整性/Integrity: 没有答案泄露；NOP全部失败，确保任务无法被"不真正完成"地通过
        
*   环境校验/Environment：确保 Docker 环境确定性、自包含、可复现
    
*   验证器/Verifier&Verdict: 验证测试套件本身的正确性和设计原则，确保Verifier的结果符合难度要求
    

**检查对象**

检查的对象，大致可以分为对task的检查，和对jobs的检查，以及task-jobs交叉验证。比如habor格式的校验，针对的task目录layout的检查。为了更好的执行检查，方便转换成程序或者rubric，原则上每个检查项需要指定具体的检查对象。

**检查方式**

原则：尽量将质检的工作左移，将问题暴露在更早的阶段；尽量使用执行快成本低的方式进行检查：能够使用程序校验的，使用程序校验，否则，优先考虑LLM辅助，减少人工质检的工作量，将人的精力消费在更重要的工作上

*   程序性检查：也称静态检查，机械性检查，确定性的检查。指那些实现方式可以转换成脚本或者程序的检查。执行快，成本低，结果确定
    
*   LLM-as-a-Judge：借助LLM或Agent来协助质检。为了解决LLM可能的幻觉问题，得到可靠的结论，可能会使用多模型针对一个问题分别判断，取一致结果；如果结果不一致，则由人工质检兜底。这种检查方式执行速度略慢，有API调用成本，结果可能需要人工进行判读
    
*   人工Review：程序和大模型无法进行辅助判断，需要人工进行质检操作。可能需要多人互相review，做出最终的质检判断。这种检查方式最慢，需要消耗大量人工时间，但结果也比较可靠
    

**检查标准**

详细描述本检查项的检查内容，如何判断检查项是否检查通过。程序性检查通过此描述转换成代码；LLM-as-a-Judge根据此作为判断Pass/Fail的rubric。

## 格式合规 / Format Compliance

| ID | 检查项描述 | 检查项分类 | 检查范围 | 检查对象 | 检查方式 | Pass 标准 | Fail 标准 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FC-01 | 检查任务说明文件是否存在 | 格式合规 / Format Compliance | Task | `instruction.md` 的文件路径 | 程序性检查 | `instruction.md` 存在且为普通文件 | 文件缺失或路径不是普通文件 |
| FC-02 | 检查任务说明文件是否非空 | 格式合规 / Format Compliance | Task | `instruction.md` 的文件大小和正文 | 程序性检查 | 文件包含至少一个非空白字符 | 文件大小为零或正文仅含空白字符 |
| FC-03 | 检查任务说明文件是否可解析为文本 | 格式合规 / Format Compliance | Task | `instruction.md` 的字节内容和项目规定编码 | 程序性检查 | 文件可按项目规定编码完整解码 | 解码失败或包含导致正文无法读取的损坏内容 |
| FC-04 | 检查 `test.sh` 是否只位于测试目录 | 格式合规 / Format Compliance | Task | 仓库内所有名为 `test.sh` 的文件 | 程序性检查 | 所有 `test.sh` 均位于 `tests/` 目录或其子目录 | 任一 `test.sh` 位于 `tests/` 外 |
| FC-05 | 检查 `checks.py` 是否只位于测试目录 | 格式合规 / Format Compliance | Task | 仓库内所有名为 `checks.py` 的文件 | 程序性检查 | 所有 `checks.py` 均位于 `tests/` 目录或其子目录 | 任一 `checks.py` 位于 `tests/` 外 |
| FC-06 | 检查 `judge.toml` 是否存在 | 格式合规 / Format Compliance | Task | 仓库内所有名为 `judge.toml` 的文件 | 程序性检查 | 至少存在一个 `judge.toml` | 仓库内不存在 `judge.toml` |
| FC-07 | 检查 `judge.toml` 是否只位于测试目录 | 格式合规 / Format Compliance | Task | 仓库内所有名为 `judge.toml` 的文件 | 程序性检查 | 所有 `judge.toml` 均位于 `tests/` 目录或其子目录 | 任一 `judge.toml` 位于 `tests/` 外 |
| FC-08 | 检查 Rubrics 配置文件的 TOML 语法是否可解析 | 格式合规 / Format Compliance | Task | `tests/**/judge.toml` | 程序性检查 | TOML 语法合法，可被标准解析器加载 | TOML 语法错误或无法解析 |
| FC-09 | 检查 Rubrics 配置的必要字段是否可读取 | 格式合规 / Format Compliance | Task | `tests/**/judge.toml` 中 Rubric 条目和权重字段 | 程序性检查 | Rubric 条目和权重字段符合项目 Schema，可被质检程序读取 | Rubric 条目结构损坏、字段类型错误或关键字段缺失 |
| FC-10 | 检查 verifier 中 reward 文件命名是否符合白名单 | 格式合规 / Format Compliance | Jobs | `jobs/**/verifier/` 下名称含 `reward` 的文件 | 程序性检查 | reward 相关文件名只出现 `reward-details.json`、`reward.json`、`reward.txt` | 出现白名单之外的 reward 命名文件 |
| FC-11 | 检查最终质检报告文件是否存在 | 格式合规 / Format Compliance | Jobs | 项目配置指定的最终质检报告路径 | 程序性检查 | 指定路径存在一个普通文件 | 指定路径缺失或不是普通文件 |
| FC-12 | 检查最终质检报告是否使用 Markdown 扩展名 | 格式合规 / Format Compliance | Jobs | 最终质检报告文件名 | 程序性检查 | 文件扩展名为 `.md` | 文件扩展名不是 `.md` |
| FC-13 | 检查最终质检报告正文是否可读取 | 格式合规 / Format Compliance | Jobs | 最终质检报告的字节内容 | 程序性检查 | 正文可作为 UTF-8 文本完整解码 | 正文无法作为 UTF-8 文本完整解码 |

## 题目质量 / Question Design — 任务有效性 / Specificity

| ID | 检查项描述 | 检查项分类 | 检查范围 | 检查对象 | 检查方式 | Pass 标准 | Fail 标准 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QD-SP-01 | 检查任务目标是否明确且无歧义 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 的目标描述 | LLM-as-a-Judge | 能唯一理解最终要解决的问题和期望结果 | 存在多个合理但互斥的目标解释，或无法确定最终目标 |
| QD-SP-02 | 检查任务约束是否明确 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 的限制条件 | LLM-as-a-Judge | 技术、资源、行为和禁止事项等强制约束均清晰可识别 | 关键约束缺失、互相冲突或只能依赖猜测 |
| QD-SP-03 | 检查验收标准是否明确 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 的验收描述 | LLM-as-a-Judge | 每个强制目标都有可观察、可判定的成功条件 | 存在强制目标但没有可判断的完成标准 |
| QD-SP-04 | 检查必需产物是否完整声明 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 中的文件、服务和输出要求 | LLM-as-a-Judge | 所有必需创建或修改的产物均已说明；需要固定时给出文件名、路径和格式 | verifier 依赖某个必需产物，但题面未声明该产物 |
| QD-SP-05 | 检查是否明确要求运行产物 | 题目质量 / Question Design — 任务有效性 / Specificity | Task-Jobs 交叉 | `instruction.md` 与运行型测试 | LLM-as-a-Judge | 若测试要求执行脚本、启动服务或产生运行结果，题面明确要求相应动作 | 题面只要求编写产物，测试却强制要求运行或启动 |
| QD-SP-06 | 检查外部接口契约是否完整 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 中 CLI、API、端点、参数、返回值和退出码要求 | LLM-as-a-Judge | 涉及外部接口时，所有被 verifier 强制使用的契约均已明确；不涉及时为 N/A | verifier 强制未在题面定义的参数、端点、返回形式或退出码 |
| QD-SP-07 | 检查结构化输出 Schema 是否完整 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 中 JSON、CSV 或 API 输出要求 | LLM-as-a-Judge | 涉及结构化输出时，字段名、必填性、数据类型及必要顺序已明确；不涉及时为 N/A | 测试固定结构化输出细节，但题面未定义对应 Schema |
| QD-SP-08 | 检查示例的约束性质是否明确 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 中全部示例及其上下文 | LLM-as-a-Judge | 不含示例，或每个示例均能明确判断为参考性或强制性 | 任一示例是否必须严格遵循无法从题面确定 |
| QD-SP-09 | 检查题面是否以要求而非操作步骤表达 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 正文 | LLM-as-a-Judge | 题面主要描述目标、限制和验收标准，由模型自行制定方案 | 题面主要由“第一步、第二步”等可直接照抄的操作流程组成 |
| QD-SP-10 | 检查题面是否泄露完成任务的具体命令 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 中命令行片段 | LLM-as-a-Judge | 只提供必要接口约束，不提供足以直接完成任务的命令序列 | 给出关键命令或完整命令序列，模型无需自行探索 |
| QD-SP-11 | 检查题面是否泄露具体代码修复方案 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | `instruction.md` 中类、函数、代码位置、补丁、算法或实现逻辑 | LLM-as-a-Judge | 可说明问题范围或必要接口契约，但不提供可直接照搬的完整补丁、算法或关键修复逻辑 | 直接给出完整补丁、足以照搬的算法或关键修复逻辑，或同时指定精确修改位置与实现方式 |
| QD-SP-12 | 检查任务是否保留自主探索空间 | 题目质量 / Question Design — 任务有效性 / Specificity | Task-Jobs 交叉 | `instruction.md`、初始仓库，以及参考解法或成功 `agent/trajectory.json` | LLM-as-a-Judge | 模型需要自行决定至少一个关键操作或策略，并通过观察、推理、试验或调整完成；最终正确答案唯一时也可通过 | 题面已给出完整固定路线，模型无需作任何实质判断 |
| QD-SP-13 | 检查任务是否为单命令机械任务 | 题目质量 / Question Design — 任务有效性 / Specificity | Task-Jobs 交叉 | `instruction.md`，以及参考解法或成功 `agent/trajectory.json` 的操作序列 | LLM-as-a-Judge | 完成任务需要多个有意义的操作或决策 | 一条显而易见的命令即可完整达到目标 |
| QD-SP-14 | 检查任务是否只是纯重复操作 | 题目质量 / Question Design — 任务有效性 / Specificity | Task | 题面要求的操作集合 | LLM-as-a-Judge | 操作之间包含状态观察、推理、异常处理或策略变化 | 仅重复创建、复制、改名等同类操作，无额外推理价值 |
| QD-SP-15 | 检查典型解法是否存在过高的操作复杂度 | 题目质量 / Question Design — 任务有效性 / Specificity | Task-Jobs 交叉 | 参考解法或成功轨迹中的有意义操作 | LLM-as-a-Judge | 典型解法不超过 15 个有意义操作，或超出时有与任务价值相称的必要性 | 明显超过 15 个有意义操作且主要增加机械负担或不可控性 |
| QD-SP-16 | 检查任务是否具备可观察的中间产出 | 题目质量 / Question Design — 任务有效性 / Specificity | Task-Jobs 交叉 | instruction、成功轨迹、文件、服务状态和日志 | LLM-as-a-Judge | 多阶段任务的关键阶段能通过文件、响应、状态或日志观察；单阶段任务合理时为 N/A | 多阶段任务没有任何可观察中间状态，导致过程无法诊断 |
| QD-SP-17 | 检查基线模型成绩是否表明任务过易 | 题目质量 / Question Design — 任务有效性 / Specificity | Jobs | 最新完整批次中项目指定版本的 Qwen、Opus 程序化成绩及运行次数 | 程序性检查 | 两类模型的有效结果均达到最少轮数，且未同时满分或同时达到项目配置的“接近满分”阈值 | 两类模型的有效结果均达到最少轮数，且同时满分或同时达到“接近满分”阈值 |
| QD-SP-18 | 检查典型解法是否因操作过少而缺乏挑战 | 题目质量 / Question Design — 任务有效性 / Specificity | Task-Jobs 交叉 | 参考解法或成功轨迹中的有意义操作 | LLM-as-a-Judge | 典型解法至少包含 5 个有意义操作，或 2–4 个操作但仍需要实质推理、诊断或决策 | 典型解法仅含 2–4 个简单操作且缺乏实质推理、诊断或决策 |

## 题目质量 / Question Design — 任务可解性 / Solvability

| ID | 检查项描述 | 检查项分类 | 检查范围 | 检查对象 | 检查方式 | Pass 标准 | Fail 标准 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QD-SO-01 | 检查任务要求是否可以同时满足 | 题目质量 / Question Design — 任务可解性 / Solvability | Task | `instruction.md` 的全部目标和约束 | LLM-as-a-Judge | 不同要求之间逻辑兼容，存在同时满足的状态 | 存在互斥要求或必然导致失败的约束组合 |
| QD-SO-02 | 检查完成任务所需的本地输入是否存在 | 题目质量 / Question Design — 任务可解性 / Solvability | Task | 题面引用的输入文件、初始代码、数据和配置路径 | 程序性检查 | 每个必需本地输入均在初始环境中存在 | 任一必需本地输入缺失 |
| QD-SO-03 | 检查完成任务所需权限是否可用 | 题目质量 / Question Design — 任务可解性 / Solvability | Task-Jobs 交叉 | 目标容器中的文件权限、服务访问探针、凭据注入状态和实际执行日志 | 程序性检查 | 所有必需操作均可在已授予权限下执行，且不依赖题面未声明的特权 | 必需操作因缺少文件权限、服务权限、凭据或未声明特权而无法执行 |
| QD-SO-04 | 检查任务资源需求是否在项目预算内 | 题目质量 / Question Design — 任务可解性 / Solvability | Task-Jobs 交叉 | 参考执行的 CPU、内存、磁盘、网络和耗时峰值，以及项目资源上限 | 程序性检查 | 参考执行的各项资源消耗均不超过项目配置上限 | 任一资源消耗超过项目配置上限 |
| QD-SO-05 | 检查 Oracle 或参考方案是否能在目标环境成功执行 | 题目质量 / Question Design — 任务可解性 / Solvability | Task-Jobs 交叉 | `solution/`（如有）、项目认可的其他可执行证据、目标容器、参考执行日志、verifier 结果和项目通过线 | 程序性检查 | 至少一种项目认可的可执行证据在目标环境完成运行并达到项目通过线 | 全部获认可且可用的证据均已执行，但均无法运行或未达到项目通过线 |
| QD-SO-06 | 检查参考方案是否依赖答案硬编码或 verifier 漏洞 | 题目质量 / Question Design — 任务可解性 / Solvability | Task-Jobs 交叉 | `solution/`、参考运行轨迹、最终产物和 verifier | LLM-as-a-Judge | 参考方案通过真实计算或实现产生结果，不依赖固定答案、伪造状态或 verifier 漏洞 | 主要通过 `echo` 固定结果、硬编码答案、伪造状态或利用 verifier 漏洞获得通过 |
| QD-SO-07 | 检查完成状态是否可以被客观观察 | 题目质量 / Question Design — 任务可解性 / Solvability | Task | 最终产物、服务行为、响应和日志要求 | LLM-as-a-Judge | 成功状态可以通过具体文件内容、接口行为、状态或日志确认 | 目标仅为“完成、优化、改进”等抽象表述，无客观完成证据 |

## 题目质量 / Question Design — 任务完整性 / Integrity

| ID | 检查项描述 | 检查项分类 | 检查范围 | 检查对象 | 检查方式 | Pass 标准 | Fail 标准 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QD-IN-01 | 检查题面、示例和初始环境是否泄露最终答案 | 题目质量 / Question Design — 任务完整性 / Integrity | Task | `instruction.md`、示例、fixtures、注释、环境文件和初始代码 | LLM-as-a-Judge | 无法直接读取、复制或简单拼接出最终答案 | 任一材料包含可直接提交的最终答案或等价结果 |
| QD-IN-02 | 检查模型运行时是否无法读取测试目录 | 题目质量 / Question Design — 任务完整性 / Integrity | Task | Dockerfile、构建上下文、镜像文件清单和挂载配置 | 程序性检查 | 模型运行环境中不存在或无权限读取 `tests/` | 模型可直接读取测试代码、断言或预期值 |
| QD-IN-03 | 检查模型运行时是否无法读取参考解法 | 题目质量 / Question Design — 任务完整性 / Integrity | Task | Dockerfile、构建上下文、镜像文件清单和挂载配置 | 程序性检查 | 模型运行环境中不存在或无权限读取 `solution/` | 模型可直接读取参考解法或答案文件 |
| QD-IN-04 | 检查 NOP 或空实现是否不能通过任务 | 题目质量 / Question Design — 任务完整性 / Integrity | Task-Jobs 交叉 | 项目配置的 NOP 集合、verifier 和 NOP 对照运行结果 | 程序性检查 | 所有配置的 NOP/空实现最终 reward 均低于项目通过线，且不能伪装为真实完成 | 任一 NOP/空实现达到通过线，或获得项目定义的异常高 reward |
| QD-IN-05 | 检查硬编码预期结果是否无法绕过任务 | 题目质量 / Question Design — 任务完整性 / Integrity | Task-Jobs 交叉 | verifier、固定输出/伪造文件对照实现 | 程序性检查 | 仅打印固定值、伪造状态或复制预期文本不能通过核心验证 | 不实现核心功能，仅硬编码预期结果即可通过 |
| QD-IN-06 | 检查测试与答案相关材料是否不会通过其他路径暴露 | 题目质量 / Question Design — 任务完整性 / Integrity | Task | 环境变量、构建缓存、历史文件、日志、临时目录和版本控制残留 | 程序性检查 | 不存在模型可访问的预期答案、测试快照或历史 solution 残留 | 可通过环境变量、缓存、日志、Git 历史或临时文件获取答案 |

## 环境校验 / Environment

| ID | 检查项描述 | 检查项分类 | 检查范围 | 检查对象 | 检查方式 | Pass 标准 | Fail 标准 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ENV-01 | 检查 Docker 技术栈与题面设定是否一致 | 环境校验 / Environment | Task | 从 Dockerfile 提取的基础镜像与运行时版本，以及 `instruction.md` 的技术栈要求 | LLM-as-a-Judge | 语言、框架和主要运行时版本与题面要求兼容 | Docker 环境与题面指定技术栈或版本不兼容 |
| ENV-02 | 检查初始代码库与题面描述是否一致 | 环境校验 / Environment | Task | `instruction.md`、初始 codebase 的模块、文件和服务 | LLM-as-a-Judge | 题面引用的模块、文件、接口和初始问题均真实存在 | 题面建立在不存在或明显不同的代码结构上 |
| ENV-03 | 检查必要工具是否已预装且可执行 | 环境校验 / Environment | Task | 从题面和测试提取的必需工具清单，以及目标容器中的 PATH 与命令探测结果 | LLM-as-a-Judge | 每个完成或验证任务所必需的工具均可执行；题面明确要求模型安装的工具除外 | 任一必需工具缺失、不可执行或不在 PATH，且题面未要求模型安装 |
| ENV-04 | 检查应用级依赖版本是否锁定 | 环境校验 / Environment | Task | requirements、lockfile、Dockerfile、npm/Maven/Gradle 等应用依赖配置 | 程序性检查 | 构建或测试会解析的应用级依赖均使用精确版本或有效锁文件；apt 等系统包仅在项目另有要求时纳入 | 任一构建或测试使用的应用级依赖无版本约束且不存在有效锁文件 |
| ENV-05 | 检查核心任务和验证是否可离线运行 | 环境校验 / Environment | Task-Jobs 交叉 | Dockerfile、任务代码、`tests/test.sh`、`tests/checks.py` 和网络调用日志 | 程序性检查 | 不访问公网也能完成核心任务和全部验证 | 必须从公网下载文件、安装软件或调用不可控外部服务 |
| ENV-06 | 检查结果是否不依赖系统当前时间 | 环境校验 / Environment | Task-Jobs 交叉 | 任务代码、测试代码、时间读取和时间断言 | 程序性检查 | 时间已冻结或注入，或断言与当前日期、时区和运行时刻无关 | 相同解法因当前日期、时区或时间戳变化得到不同结果 |
| ENV-07 | 检查随机行为是否固定 | 环境校验 / Environment | Task-Jobs 交叉 | 任务代码、测试代码、随机数和抽样配置 | 程序性检查 | 随机 seed 固定，或 reward 对随机结果不敏感 | 相同解法因未固定随机数得到不同 reward |
| ENV-08 | 检查并发共享状态是否采用可靠同步或隔离机制 | 环境校验 / Environment | Task-Jobs 交叉 | 并发代码、共享文件、锁、进程间状态和对应运行日志 | LLM-as-a-Judge | 所有并发共享状态均通过锁、原子操作、资源隔离或等价机制控制 | 存在未受控的共享状态或竞态窗口，可能改变验证结果 |
| ENV-09 | 检查相同环境和解法的重复执行结果是否一致 | 环境校验 / Environment | Jobs | 同一解法在相同环境下的多次运行日志、测试结果和 reward | 程序性检查 | 达到项目配置的最少复跑次数，且结果、关键断言和 reward 一致 | 重复运行出现时而通过时而失败、端口冲突、顺序相关或 reward 不一致 |
| ENV-10 | 检查工作目录与路径解析是否一致 | 环境校验 / Environment | Task | `instruction.md`、Dockerfile、tests 和脚本中的工作目录声明与路径引用 | 程序性检查 | 每个相对路径均从声明的工作目录解析到预期产物；必要的绝对路径彼此不冲突 | 同一产物因基准目录不一致解析到不同位置，或路径在目标环境中不存在 |
| ENV-11 | 检查 `test.sh` 是否不会现场安装软件 | 环境校验 / Environment | Task | `tests/**/test.sh` | 程序性检查 | 仅使用环境预装工具，不执行联网或临时软件安装 | 在测试阶段执行 curl 管道安装、`pip install` 等现场安装操作 |
| ENV-12 | 检查仅供 verifier 使用的依赖是否与模型环境隔离 | 环境校验 / Environment | Task | 从测试代码提取的依赖、任务需求、Dockerfile、任务镜像和 verifier 依赖层 | LLM-as-a-Judge | 仅为测试或评分服务的依赖只存在于 verifier 侧；任务实现本身需要的依赖不受此限制 | 与任务实现无关、仅供测试或评分使用的工具或库暴露给模型 |
| ENV-13 | 检查超时配置是否覆盖合理执行时间 | 环境校验 / Environment | Task-Jobs 交叉 | timeout 配置、参考解法与稳定成功轨迹的实测耗时分布 | 程序性检查 | timeout 不低于项目配置的耗时分位数和安全余量，且不会误杀合理解法 | timeout 低于配置基线，或稳定正确解法因时间不足被终止 |
| ENV-14 | 检查服务启动是否使用可验证的就绪条件 | 环境校验 / Environment | Task-Jobs 交叉 | 服务启动脚本、健康检查、轮询条件、固定 sleep 和启动日志 | LLM-as-a-Judge | 不涉及异步服务启动时为 N/A；涉及异步启动时，后续测试由端口、接口、进程状态或等价健康信号触发 | 异步服务启动后仅依赖固定 sleep 即开始测试，未验证服务是否真正可用 |

## 验证器 / Verifier & Verdict

| ID | 检查项描述 | 检查项分类 | 检查范围 | 检查对象 | 检查方式 | Pass 标准 | Fail 标准 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VV-01 | 检查题面每项明确要求是否都有验证覆盖 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | instruction 要求、程序化测试和 Rubrics 的映射 | LLM-as-a-Judge | 每项明确功能或约束至少由一个有效测试或 Rubric 覆盖 | 任一明确要求完全没有对应验证 |
| VV-02 | 检查每条强制断言是否能追溯到题面 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 程序化测试断言、Rubric 条目和 `instruction.md` | LLM-as-a-Judge | 每条会影响 reward 的强制要求都有明确题面依据 | 测试或 Rubric 强制题面未提出的要求 |
| VV-03 | 检查测试是否与题面要求一致 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | `instruction.md` 与全部测试期望 | LLM-as-a-Judge | 测试期望与题面要求语义一致 | 任一测试要求与题面明确要求相反或互斥 |
| VV-04 | 检查测试是否不绑定未声明的内部实现细节 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 对变量名、函数名、调用顺序、算法和内部结构的断言 | LLM-as-a-Judge | 等价正确实现均可通过，除非题面明确限定实现方式 | 测试写死题面未规定的内部实现细节 |
| VV-05 | 检查测试是否不强制未声明的文件名或路径 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 从测试中程序提取的文件名、目录和路径断言，以及 `instruction.md` | LLM-as-a-Judge | 被强制检查的文件名和路径均能在题面中找到明确语义依据 | 测试固定题面未声明的文件名或路径 |
| VV-06 | 检查测试是否不强制未声明的字面值或顺序 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 固定字符串、列顺序、输出格式和 shebang 等断言 | LLM-as-a-Judge | 只约束题面明确要求的字面值、格式或顺序 | 因未声明的字符串、顺序或表现形式误杀正确实现 |
| VV-07 | 检查核心功能是否通过行为而非静态存在性验证 | 验证器 / Verifier & Verdict | Task | `checks.py`、原生 UT、`test.sh` | LLM-as-a-Judge | 核心要求通过输入输出、接口、状态或副作用等功能性断言验证 | 核心功能仅靠文件、函数或符号存在判定 |
| VV-08 | 检查核心功能是否不依赖关键词或正则匹配判定 | 验证器 / Verifier & Verdict | Task | grep、regex、字符串搜索类测试 | LLM-as-a-Judge | 关键词或正则只作辅助证据，最终验证真实行为或语义结果 | 找到某个字符串、注解或函数名即判定核心功能通过 |
| VV-09 | 检查主要正常路径是否被测试 | 验证器 / Verifier & Verdict | Task | 全部程序化测试用例 | LLM-as-a-Judge | 每个主要成功场景至少有一个有效测试 | 任一主要正常流程没有测试 |
| VV-10 | 检查关键边界条件是否被测试 | 验证器 / Verifier & Verdict | Task | 全部程序化测试用例和题面边界 | LLM-as-a-Judge | 与任务相关的空值、极值、重复调用或容量边界得到覆盖 | 明显可能改变正确性的关键边界完全未验证 |
| VV-11 | 检查关键异常路径是否被测试 | 验证器 / Verifier & Verdict | Task | 全部程序化测试用例和失败处理要求 | LLM-as-a-Judge | 关键非法输入、拒绝逻辑或失败行为得到覆盖 | 只测试 happy path，关键错误场景完全未验证 |
| VV-12 | 检查程序化验证 Case 数量是否合规 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 测试框架实际收集结果、`ctrf.json` 或项目指定的等价 Case 清单 | 程序性检查 | 按项目指定口径统计的独立程序化 Case 数量满足 **5 ≤ case ≤ 20** | Case 数量少于 5 或多于 20 |
| VV-13 | 检查是否至少存在一条 Rubric | 验证器 / Verifier & Verdict | Task | `tests/**/judge.toml` | 程序性检查 | Rubric 条目数 **≥ 1** | Rubric 条目数为 0 |
| VV-14 | 检查 Rubrics 权重占比是否合规 | 验证器 / Verifier & Verdict | Task | `tests/**/judge.toml`、总 reward 配置和项目定义的权重分母 | 程序性检查 | 按项目统一分母计算的 Rubrics 权重占比 **≤ 50%** | 按统一分母计算的 Rubrics 权重占比 **\> 50%** |
| VV-15 | 检查是否优先使用程序化验证 | 验证器 / Verifier & Verdict | Task | 程序化测试与 Rubrics 的职责分配 | LLM-as-a-Judge | 可确定性验证的功能由程序测试承担，Rubric 只补充代码质量、设计等难以程序化的维度 | 将可稳定自动验证的核心功能交给主观评分 |
| VV-16 | 检查每条 Rubric 是否具有原子性 | 验证器 / Verifier & Verdict | Task | `judge.toml` 中每条 Rubric | LLM-as-a-Judge | 每条只检查一个独立质量点 | 单条同时检查两个或更多可独立判定的要求 |
| VV-17 | 检查每条 Rubric 是否针对当前任务定制 | 验证器 / Verifier & Verdict | Task | Rubric description 与 `instruction.md` | LLM-as-a-Judge | 描述直接对应当前任务的具体功能、约束或质量目标 | 使用可套用到任意任务的通用模板，或内容与当前任务无关 |
| VV-18 | 检查不同 Rubrics 是否互不重叠 | 验证器 / Verifier & Verdict | Task | 全部 Rubrics 两两比较 | LLM-as-a-Judge | 每个质量点只被一个 Rubric 计分 | 两条或以上 Rubric 对同一质量点重复加分或扣分 |
| VV-19 | 检查 Rubric 评分锚点是否事实明确 | 验证器 / Verifier & Verdict | Task | Rubric description 和各分数档位 | LLM-as-a-Judge | 每个分数档对应可观察、可区分的事实条件 | 仅使用“较好、合理、优秀”等模糊描述，无明确评分边界 |
| VV-20 | 检查每个 Rubric 的 Explicit/Implicit 分类是否正确 | 验证器 / Verifier & Verdict | Task | `judge.toml` 中每条 Rubric description | LLM-as-a-Judge | 逐条依据评估含义分类：Explicit 判断“做了什么、是否满足明确要求”，Implicit 判断“如何做、做得多好”；不要求源文件预置标签 | 依据标签机械分类、分类含义颠倒，或无法用 description 解释分类 |
| VV-21 | 检查 Explicit/Implicit 数量统计是否准确 | 验证器 / Verifier & Verdict | Task | 每条 Rubric 的分类产物、Rubric 总清单和质检报告统计 | 程序性检查 | 两类计数之和等于 Rubric 总数，且分别与逐条分类产物一致 | 漏计、重复计数、总数不一致或逐条分类产物与汇总不一致 |
| VV-22 | 检查程序化 reward 是否稳定 | 验证器 / Verifier & Verdict | Jobs | 最新批次同模型多轮程序化 reward | 程序性检查 | 达到项目配置的最少轮数，且按统一公式计算的波动 **≤ 30%** | 按统一公式计算的波动 **\> 30%** |
| VV-23 | 检查 Rubrics reward 是否稳定 | 验证器 / Verifier & Verdict | Jobs | 最新批次同模型多轮 Rubrics reward | 程序性检查 | 达到项目配置的最少轮数，且按统一公式计算的波动 **≤ 30%** | 按统一公式计算的波动 **\> 30%** |
| VV-24 | 检查标注员是否在写测试前设计过具体用例 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 全部 `output/agent-session/<project>/*.jsonl`，以及首次写入测试文件的时间点 | LLM-as-a-Judge | 完整轨迹中没有测试文件写入时为 N/A；存在写入时，首次写入前至少描述过一个具体行为及其期望结果或拒绝条件 | 完整轨迹中存在测试文件写入，但此前只有“根据 instruction 生成/覆盖单测”等泛化委托，或只选择 AI 推荐方案 |
| VV-25 | 检查造测轨迹是否为迎合特定模型结果而循环修改测试 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 全部 `output/agent-session/<project>/*.jsonl`、测试文件 Write/Edit 时间线、模型运行记录和测试结果 | 人工 Review | 在完整且预处理成功的轨迹中，修改可追溯到预先定义的需求、用例或已确认的测试缺陷 | 人工根据完整轨迹确认存在反复运行特定模型并持续修改测试以使其输出通过，且修改削弱公平性或泛化性 |
| VV-26 | 检查模型执行轨迹文件是否齐全 | 验证器 / Verifier & Verdict | Jobs | 项目配置要求的 `agent/trajectory.json`、`agent/episode-*/prompt.txt`、`response.txt` 和 `result.json` | 程序性检查 | 项目规定的轨迹文件和 episode 文件全部存在 | 任一必需轨迹文件或关键 episode 文件缺失 |
| VV-27 | 检查模型执行轨迹是否形成闭合执行序列 | 验证器 / Verifier & Verdict | Jobs | `agent/trajectory.json`、episode 顺序、工具调用配对和结束状态 | 程序性检查 | 轨迹可解析，episode 顺序连续，工具调用均闭合，并存在正常结束或明确失败状态 | 轨迹损坏、轮次断裂、工具调用未闭合或不存在结束状态 |
| VV-28 | 检查 verifier 结果文件是否齐全 | 验证器 / Verifier & Verdict | Jobs | 项目配置要求的 `verifier/reward.txt`、`reward.json`、`test-stdout.txt`、`ctrf.json` 等结果文件 | 程序性检查 | 项目规定的全部 verifier 结果文件均存在 | 任一必需结果文件缺失 |
| VV-29 | 检查 verifier 结果文件是否可解析 | 验证器 / Verifier & Verdict | Jobs | 已存在的 reward、测试输出、CTRF 和评分结果文件及其项目 Schema | 程序性检查 | 每个结果文件均可按对应格式和项目 Schema 完整解析 | 任一结果文件语法损坏、字段类型错误或无法按 Schema 解析 |
| VV-30 | 检查最终 reward 是否与验证证据一致 | 验证器 / Verifier & Verdict | Jobs | `reward.txt`、`reward.json`、测试输出、CTRF、Rubric 评分和项目计分公式 | 程序性检查 | 最终 reward 可由程序化测试和 Rubric 结果按项目公式完整推导 | 按项目公式重算的 reward 与最终记录不一致，或存在无证据得分 |
| VV-31 | 检查最终质检结论是否引用必要证据 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 最终质检报告，以及对应 reward、失败断言、执行轨迹、题面、测试、环境和稳定性证据 | LLM-as-a-Judge | 每项失败、Flag 或归因均引用足以支持该结论的直接证据 | 仅凭 reward=0、timeout、parse error 或 unset 下结论，未核对失败断言和执行轨迹 |
| VV-32 | 检查失败根因分类是否合理 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | 最终质检报告的根因分类及其引用证据 | LLM-as-a-Judge | 根因归入 Prompt、Test/Env、Rubrics、测试可信度、结果不稳定或模型能力；只有题面清晰、测试公平且环境稳定时才归为模型能力 | 根因分类与证据矛盾，遗漏结果不稳定，或在前置条件未满足时归为模型能力 |
| VV-33 | 检查模型与 reward 统计是否使用最新完整批次 | 验证器 / Verifier & Verdict | Jobs | 项目批次清单、批次完整性规则、模型得分和轨迹时间 | 程序性检查 | 按项目完整性规则选出时间最新的完整批次，并仅用该批次统计和归因 | 使用旧批次、未完成批次或混合不同批次数据得出结论 |
| VV-34 | 检查最终质检结论是否包含可执行的整改与复验信息 | 验证器 / Verifier & Verdict | Jobs | 最终质检报告中的失败项、Flag、修改对象和复验建议 | LLM-as-a-Judge | 无失败或 Flag 时为 N/A；否则每项均说明需修改的 Prompt/Test/Env/Rubric/数据对象和可执行复验方法 | 存在失败或 Flag，但未说明修改对象或如何复验 |
| VV-35 | 检查构建轨迹证据是否足以审查造测意图 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | `output/agent-session/<project>/*.jsonl` 的文件清单、来源路径、解析日志和预处理结果 | 程序性检查 | 全部构建会话文件来自规定目录、可解析，且按本 Checklist 的预处理规则成功生成审查输入 | 使用了当前质检会话等错误来源，JSONL 无法解析，或预处理规则执行失败 |
| VV-36 | 检查模型是否实际生成或修改了题面要求的最终产物 | 验证器 / Verifier & Verdict | Task-Jobs 交叉 | `instruction.md` 的必需产物、模型结束前后的文件差异、服务状态、输出日志和模型最终声明 | LLM-as-a-Judge | 每个必需产物均有文件、服务状态、响应或日志等直接证据，不依赖模型是否口头声明完成 | 直接检查确认任一必需产物不存在、未发生要求的修改，或要求运行的服务处于不可用状态 |

## 统计摘要

| 分类 | Checkitem 数量 |
| --- | --- |
| 格式合规 / Format Compliance | 13 |
| 题目质量 — 任务有效性 / Specificity | 18 |
| 题目质量 — 任务可解性 / Solvability | 7 |
| 题目质量 — 任务完整性 / Integrity | 6 |
| 环境校验 / Environment | 14 |
| 验证器 / Verifier & Verdict | 36 |
| **合计** | **94** |

| 主检查方式 | Checkitem 数量 |
| --- | --- |
| 程序性检查 | 44 |
| LLM-as-a-Judge | 49 |
| 人工 Review | 1 |
| **合计** | **94** |

程序性检查占约 46.8%，直接人工 Review 仅 1 项。LLM-as-a-Judge 项默认多模型一致后自动通过或失败，仅冲突项转人工，因此人工负担主要集中在少数造测意图争议和复杂归因案例。

**checklist -> pipeline**

checklist的内容可以转成质检的pipeline。通常来说，将一个检查点转换为pipeline中的一个算子，再用一个入口脚本串联起所有的算子节点。pipeline的组织方式，可以将程序性检查放到前端，LLM-as-a-Judge放到后端。

# 三、操作：质检项目SOP

标注项目只是质检数据来源之一，因此，非常有必要将质检的流程从标注平台解耦出来，独立成单独的流程或产品，供多个质检项目使用。等到后续质检流程成熟后，再考虑集成到各个数据源处。

质检的过程和结果同样重要，因此，除了最终的结果数据，还需要将尽可能多的过程数据保留下来，供后续分析优化使用。数据可以通过git项目的方式保留下来，也方便不同角色之间协同。

git仓库即为质检项目的交付物，代码和数据共存于一个repo。

```shell
qc-example
├── .agent/                                     # Agent 工具配置
│   └── skills -> ../skills                     # 指向公共 skills 目录
├── .claude/                                    # Claude 工具配置
│   └── skills -> ../skills                     # 指向公共 skills 目录
├── dataset/                                    # 数据集与检查结果
│   ├── task-dfe34d/                            # dfe34d 任务数据
│   │   ├── jobs/                               # 作业运行数据
│   │   ├── task/                               # 任务定义与资源
│   │   ├── check-result.20260906235306.json    # 历史检查结果
│   │   ├── check-result.20260907015306.json    # 历史检查结果
│   │   └── check-result.json                   # 最新检查结果
│   ├── task-qd23wa2/                           
│   └── check-result.json                       # 数据集级检查结果
├── checkers/                                   # 各个检查项
│   ├── check_task_layout.py                    # 检查harbor task目录结构
│   ├── check_task_toml.py                      # 检查task.toml内部格式
│   └── __init__.py                             
├── skills/                                     # Skills 定义
├── .gitignore                                  # ignore文件
├── .env                                        # 本地环境变量，配置CC的ak或者oss的ak/sk信息
├── .env.example                                # 环境变量示例
├── .python-version                             # Python 版本声明
├── checklist.json                              # 质量检查项配置
├── dataset.json                                # 数据集配置或索引
├── main.py                                     # 主程序入口
├── pipeline.py                                 # 流水线组装，收集直接结果，产出质检报告
├── prepare-dataset.py                          # 数据集准备模块，负责pipeline运行前环境准备
├── pyproject.toml                              # 项目及依赖配置
├── README.md                                   # 项目使用说明
└── uv.lock                                     # uv 依赖锁定文件
```

## 初始化项目

从一个基础git项目中fork出对应质检项目的git项目，项目统一放置在[quality-check-coding](https://code.alibaba-inc.com/quality-check-coding)代码组，以`qc-${projectName}`格式命名。基础项目中带着固定的目录结构，一份基础的checklist，以及checklist对应的pipeline。后续的更改在此代码库上进行修改。

## 数据准备

主要准备数据集的task数据和jobs数据。其中在标注项目中，jobs数据由标注人员提供，可以直接利用；否则，需要自己进行rollout。由于最终的数据交付要经过AP（AgentPlatform）平台，如果需要自己rollout，可以直接上AP上进行。

## 完善checklist和pipeline

尽管初始化项目带着一份基础的checklist和pipeline，每个项目可能有自己的要求，因此可针对项目需求，对checklist进行增加，删除，修改，并更新到pipeline中。

## 打包预检工具包

对于标注项目，需要提供一份预检的工具包给到领域专家，交付给标注人员使用。预检工具包需包含所有程序性检查，LLM-as-a-Judge类检查可酌情添加。

## 运行质检pipeline

针对准备好的数据，批量（采购数据）或者增量（标注项目）运行质检pipeline，得到对应task的质检报告。质检报告不能覆盖，需保留每次运行的记录，供后续分析使用。

pipeline运行分为两阶段，第一阶段为程序性检查，第二阶段为LLM-as-a-Judge检查。如果第一阶段没有全部通过，那么不用进行第二阶段的检查。

pipeline使用到的AK，涉及到项目成本核算，需归属到具体标注项目，找对应项目的领域专家分配。

## 质检反馈

分析对应的质检报告，将对应的质检意见，反馈到对应系统。

## 数据交付

数据集交付时，除了数据外，还需交付一份数据集质量报告。

## 项目复盘

针对项目运行中增加或者改动的检查点，判断是否需要同步到第一步中的基础git项目。

# 四、后续安排

*   平台打通：标注平台和质检pipeline，质检pipeline和AP平台
    
*   跑通MVP：在一个项目上跑通整个流程，先沉淀出质检的基建(v1)
    
*   更详细的一些设计：比如每一个checker，比如质检报告
    
*   其他工具的开发：checklist编辑，质检报告的查看，报表系统等
    

# 参考资料

[请至钉钉文档查看附件《\[EXT\] APEX Code Offerings\_Terminal Bench Pro.pdf》。](https://alidocs.dingtalk.com/i/nodes/oP0MALyR8kzGnoOwFDymDN90J3bzYmDO?cid=367008725:6763975620&corpId=dingd8e1123006514592&iframeQuery=anchorId%3DX02mtq1kptkgxpqn4bgkht&utm_medium=im_card&utm_scene=team_space&utm_source=im)

[请至钉钉文档查看附件《\[OTS\] Codebase QnA onboarding doc .pdf》。](https://alidocs.dingtalk.com/i/nodes/oP0MALyR8kzGnoOwFDymDN90J3bzYmDO?cid=367008725:6763975620&corpId=dingd8e1123006514592&iframeQuery=anchorId%3DX02mtq1kpseojpmq5oazd&utm_medium=im_card&utm_scene=team_space&utm_source=im)

[请至钉钉文档查看附件《\[EXT\] APEX Code Offerings\_Terminal Bench Science.pdf》。](https://alidocs.dingtalk.com/i/nodes/oP0MALyR8kzGnoOwFDymDN90J3bzYmDO?cid=367008725:6763975620&corpId=dingd8e1123006514592&iframeQuery=anchorId%3DX02mtq1kpschynbf8bbucr&utm_medium=im_card&utm_scene=team_space&utm_source=im)

*   habor内置的质检工具 `harbor check <task>`的实现
    
*   AoneBench项目组质检方案：[《AoneBench Java 单测类质检流程演进与 Skill 分享》](https://alidocs.dingtalk.com/i/nodes/R1zknDm0WR6XzZ4LtzEnG1l3WBQEx5rG)
    
*   外采数据质检流程：[《外采数据质检流程》](https://alidocs.dingtalk.com/i/nodes/20eMKjyp810mMdK4HrOanPYPJxAZB1Gv)
    
*   现有标注项目流程梳理
    

![image](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/a/RM0e40vYLsMe5YQa/2fb47131aabc41c8b14f55521ac84b3d0521.png)