# OBM 共用规则

## 先判断用户要什么

用户可能只要求分析文档、检查结果或判断是否满足标准。此时只读，不创建题目、不修复、不重新打包。只有用户明确要求生产、修改、验证或打包时才执行对应操作。

不要因为工作区中存在其他项目就读取或套用它们。先从用户给出的 benchmark、文档和路径确定范围。

## 新题 ID

每道新题先在项目级共享登记表中原子预留唯一 ID，格式为 `YYYY-MM-DD-N`。`YYYY-MM-DD` 是创建当天的本地日期，`N` 从该日期的 `1` 开始。编号分配同时考虑当前项目的题目目录、工作目录、交付目录、压缩包和其他窗口尚未完成的活动占位。不要覆盖已有目录、文件、压缩包或占位。

先读取 [task-registry.md](task-registry.md)，同步已有题并执行占位。正式生产必须使用：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/task_registry.py" reserve \
  --root . \
  --benchmark BENCHMARK \
  --slug SHORT-NAME \
  --repository OWNER/REPOSITORY \
  --capability-type CAPABILITY \
  --scene-summary "SCENE SUMMARY"
```

`next_task_id.py` 只是只读预览工具，不具备并发占位能力。


题目内部任务标识使用同一个 ID。正式提交包根目录和 ZIP 文件名遵守官方 `<benchmark>_<proposal_name>` 格式，其中 proposal name 使用 `YYYY-MM-DD-N-short-description`，不要把日期或编号放到末尾。

## 选题与原创性

题目应来自真实的软件工程场景，能在固定历史版本上实现和验证。选择仓库时检查：

- 许可证允许使用和分发；
- 历史提交可复现，需求在该提交中尚不存在；
- 没有公开 issue、PR 或后续提交直接给出同一答案；
- 本地可以构建并运行关键测试；
- 依赖和镜像可以满足网络限制；
- 修改需要理解真实架构，不是补一个常量或单个条件。

`related_question` 记录与原 benchmark 题目的能力关联。关联应落在核心能力上，例如状态机、并发恢复、解析语义或跨模块契约，而不是只因为语言、仓库或领域相同。
`related_question` 必须能在项目提供的离线 benchmark 映射中找到；`domain` 必须以该题映射中的官方分类前缀开头，不能只写自定义领域。

## 场景原创性

生产新题或新 proposal 前，按 [scene-dedup.md](scene-dedup.md) 建立候选场景档案，并与两类材料比对：

- 当前 benchmark 的全量题面、清单和可见验证说明；
- 项目内既有 proposal、工作目录、交付目录和压缩包中的题目材料。
- 项目共享登记表中其他窗口已登记的 `reserved`、`candidate` 和 `packaged` 场景。

场景原创性看核心因果结构，不看名称。换仓库、语言、协议名、类型名、数据格式或测试值仍可能是同一道题。至少比较场景目标、参与者与对象、工作流、状态模型、冲突与恢复、可观察结果和 verifier 行为。

有效去重记录应列出最相近的已有题、相同点、实质差异和判断依据。只有 `distinct` 可以继续生产。`high-risk` 不是有条件通过；应修改候选场景并从头复核。自动相似度只用于召回，不得把低分当成原创性证明。

## proposal 内容

以当前 OBM 文档的 schema 为准。常见字段包括：

```json
{
  "benchmark": "...",
  "domain": "Level 1/Level 2/Level 3",
  "related_question": "original-benchmark-task-id",
  "proposal_type": "A",
  "allow_network": false,
  "proposal": {
    "A_modification_idea": "...",
    "B_modification_details": "...",
    "C_agent_task": "...",
    "D_task_difficulties": ["..."]
  },
  "proposal_sources": "...",
  "proposal_scene": "...",
  "proposal_verify": "...",
  "expert_experience_skill": "..."
}
```

官方模板要求按 A、B、C、D 顺序组织 proposal，难点字段使用 `D_task_difficulties`。解题限制应写在 `C_agent_task` 中，不要自行新增 `D_solution_constraints` 或 `E_task_difficulties` 作为交付必填字段。`domain` 使用规范要求的英文层级和半角 `/`，benchmark 枚举大小写必须与规范完全一致。

字段分工：

- modification idea：一句话说明要改变什么；
- modification details：列出对外能力和组合行为；
- agent task：Agent 可执行的任务、解题限制和题面路径；
- task difficulties：真正需要推理的技术难点，不复述功能清单；
- sources：仓库、提交、许可证、离线依赖和原创性；
- verify：可执行验证方式、F2P/P2P 或该 benchmark 对应的评分证据；
- expert skill：skill 路径、作用范围和不泄漏声明。

## 题面、参考实现和 verifier

题面描述可观察行为：公开 API、输入输出、状态、错误、并发、持久化、兼容性和资源限制。避免指定内部文件、私有函数或最短实现路线。

先完成参考实现再定稿 verifier。参考实现用于证明题目可解和帮助审查，不能成为评分时的等价标准。

verifier 应满足：

- 基础版本在新增行为上失败；
- 参考实现通过新增行为和关键回归测试；
- 修改测试、跳过测试或伪造输出不能得分；
- 结果缺失、测试未运行或报告损坏按失败处理；
- 输出结构化分数和可定位的失败原因；
- 从干净环境应用 Agent patch，不使用 Agent 运行后的缓存或生成物。

## 专家 skill

专家 skill 传递解决同类问题的专业经验，不是缩写版答案。它应围绕当前题目的难点组织，而不是复制一份通用开发流程。

正式提交的 `sources/skill/SKILL.md` 必须使用中文撰写。frontmatter 的 `description`、Markdown 标题、经验说明、决策方法和验证思路都要使用中文。以下内容可以保留英文：frontmatter 的 `name`、API 和类型名、库名、代码、命令、文件路径、配置字段、协议关键字，以及必须精确保留的错误字面值。技术标识应放在中文句子中解释，不能出现纯英文说明段落，也不能用少量中文包裹主要为英文的正文。

逐难点映射时，检查三件事：

- 覆盖：每条 task difficulty 有明确章节；
- 有用：章节提供会改变 Agent 决策的具体模型或检查方法；
- 安全：章节不暴露参考实现、测试名称、固定断言或上一轮失败点。

如果一段内容可以原样放进任何编程题的 skill，它通常不够具体。若内容直接告诉 Agent 修改哪个私有函数、使用哪张内部表或处理某个隐藏用例，它又过于具体。

## Agent workflow

对照实验使用相同的：

- 上游提交和干净工作树；
- Agent 模型、系统提示和工具权限；
- 时间、轮次、资源和网络限制；
- 题面、公开文件和 verifier；
- 评分脚本及通过标准。

唯一变量是是否提供专家 skill。保留每次运行的起止时间、轨迹、提交、patch、F2P/P2P 或对应指标、二元结果及失败原因。

有效证据使用严格的失败变通过判定：指定 Seed 在 no-skill 下由 verifier 判定 `reward=0`；with-skill 从相同干净基线运行并由 verifier 判定 `reward=1`。轮次只作为可选运行信息。API 错误、工具异常、Docker 故障或 verifier 基础设施错误都不能算 no-skill 失败，也不能用人工补丁或定向修改后的 skill 伪造对照结果。

## 质检清单

交付前核对：

- benchmark 枚举和 domain 格式；
- 场景去重覆盖 benchmark 全量题库和项目内既有题目，结论为 `distinct`；
- proposal 使用当前 schema；
- proposal、verifier、skill 由专家人工撰写和复核，不能直接提交 AI 自动生成内容；
- 专家 `SKILL.md` 通过中文检查：中文标题和中文正文完整，技术标识之外没有英文段落；
- 正式包包含根目录 `sources/README.md`，逐项说明 `sources` 下每个文件的用途；不放题面、Harbor 数据和无关运行材料；
- 所有路径实际存在，skill 没有引用旧题面文件名；
- verifier 有真实执行入口，不只有说明文档；
- 离线任务不运行 `apt-get`、在线 `pip install`、`git clone`、`curl` 或 `wget`；
- upstream 归档散列可复算；
- 包内无 solution、隐藏凭据、`.git`、缓存和本地运行输出；
- 每条难点在 skill 中逐项对应；
- no-skill 与 with-skill 没有基线污染；
- ZIP 只有一个题目根目录，能正常解压。

## 常见质检维度

提交前从质检人的角度单独复核：

- 垂直领域：新题与关联题是否共享真正的领域对象和工程语境，不能只因为语言相同；
- 核心能力：两题是否需要相同的主要推理能力，相关度说明要指出共享的状态、协议或架构问题；
- Source 复用：是否只复用了允许复用的上游材料，是否把原题答案、测试或专有结构带入新题；
- 行为级 Verify：verifier 是否运行真实行为，能否拒绝硬编码、跳过、伪造和未执行测试；
- 难点与 skill：每条难点是否有具体经验，不能用通用流程笼统代替；
- skill 泄漏：是否出现文件级答案、内部符号、隐藏测试、固定输入或上一轮失败点；
- 独立 checker：静态检查、禁网构建、NOP 和 Oracle 是否由可重复命令独立完成。
- 官方 `proposal_validator/validate_proposals.py` 通过，且与 benchmark 映射中的题目 ID、domain 前缀和 package 根目录命名一致。

官方拒收条件包括：proposal 矛盾或无解；由公开 commit/PR/issue 或可搜索 solution 倒推；只改 benchmark 名称、数字或固定输入；verifier 复制已有 tests；专家无法解释 verifier/test 或题目解法；skill 只有通用 coding 流程；skill 泄漏测试或答案。

相关度百分比不是自行声明。先写事实依据，再由质检标准判断。若核心能力只有外围技术栈相同，不应选择该 related question。
