# deepSWE 生产规则

本文件只适用于 OBM 的 `deepSWE` 题目。若当前 DeepSWE 或 OBM 官方格式已更新，先按新格式修订本文件。

## 任务形态

DeepSWE 面向真实开源仓库中的长链路软件工程任务。DeepSWE 原始任务的内部材料典型包含：

```text
task.toml
instruction.md
environment/
tests/
solution/
```

Agent 只看到题面和工作环境。verifier 在独立、干净的环境中收集并应用 Agent patch。参考 solution 只供本地证明和人工审查，不参与等价比较。

OBM 正式交付结构以当前文档为准。Source 包不提交 `instruction.md`；任务契约放在 `proposal.json` 的自然语言字段中，文件用途总说明放在 `sources/README.md`。`sources/app/README.md` 可补充上游项目说明。至少应能区分：

```text
  proposal.json
  sources/
  README.md     逐项说明 sources 下所有文件用途
  app/          upstream、项目说明、Dockerfile、离线依赖
  skill/        专家 skill
  verifier/     可执行入口、测试、评分配置
  provenance/   来源、提交、许可证和散列
```

不要因为 DeepSWE 原任务包含 `solution/` 就把 solution 放进 OBM 正式提交包；以 OBM 交付规范为准。

## 题目命名

DeepSWE 新题沿用 OBM 的项目级 ID：`YYYY-MM-DD-N`。创建前读取 [task-registry.md](task-registry.md)，使用 `task_registry.py reserve` 在共享文件锁内同步已有题包并占用下一个编号。例如 proposal name 为 `2026-09-22-1-diskcache-lease-queue`。正式 Source 目录和 ZIP 根目录必须使用官方格式 `deepSWE_<proposal_name>`，避免用仓库名替代题目编号。不能由多个窗口分别运行只读编号扫描后自行命名。

## 选题尺度

优先选择需要跨模块理解的 feature 或复杂 bug-fix。合理任务通常同时涉及公开契约、内部状态传播和兼容性，且包含边界或并发行为。

拒绝这些候选：

- 单文件机械修改或补一个判断；
- 从公开 PR、issue 或未来提交改写题面；
- verifier 只能检查文本、符号名或固定输出；
- 需求无法在固定基线和离线环境中稳定复现；
- 必须依赖真实外部服务或易波动的数据；
- 参考实现无法通过原有关键测试。

## 从本地 deepSWE 题库选择任务形态

本地 `Benchmark/deep-swe-main/tasks` 包含完整的 deepSWE 任务样本。生产新题前，先读取 `manifest.json`，再按候选方向抽查不同任务的 `instruction.md` 和 `task.toml`。这里的目的有两个：

1. 了解 deepSWE 任务的实际规模、契约密度、运行环境和 verifier 形态；
2. 从不同主要推理能力中选择新题方向，避免连续题包集中在同一仓库或同一种状态模型上。

manifest 的 `category` 主要是 `feature_request`、`bugfix` 和 `enhancement`，不能用它单独代表任务类型。生产时应建立更细的内部能力分类。可以从以下类型开始，但应根据题库内容扩展：

| 能力类型 | 判断依据 |
| --- | --- |
| API、类型与数据模型 | 公开类型关系、泛型约束、组合规则或数据所有权发生变化 |
| 解析、格式化与协议 | 语法、编码、序列化、请求响应或兼容语义发生变化 |
| 状态机与生命周期 | 状态转移、作用域、历史、撤销、恢复或资源释放是主要难点 |
| 并发与调度 | 排序、队列、优先级、取消、合并、竞争或公平性是主要难点 |
| 持久化与恢复 | 事务、版本、日志、缓存、崩溃切点或跨进程一致性是主要难点 |
| 资源与性能 | 内存、并发度、背压、溢写、复杂度或有界执行是主要难点 |
| 安全与程序分析 | 污点、数据流、策略、权限、检测规则或跨过程分析是主要难点 |
| UI 与运行时事件 | 焦点、观察器、事件顺序、渲染或浏览器兼容行为是主要难点 |

任务可能同时涉及多个类型，应选择决定解法和 verifier 的主要类型。语言和仓库不是任务类型。

连续生产多个题包时，维护一份内部候选矩阵：

```text
参考 deepSWE 任务 | 主要能力类型 | 新上游仓库 | 新需求场景 | 独立状态模型 | 独立 verifier 行为
```

默认优先选择不同的主要能力类型和不同的上游仓库。没有用户指定时，不要连续复用上一题的仓库或基础提交。若确有理由复用同一仓库，必须在场景去重记录中说明为什么新题需要不同的状态模型、冲突处理和验证设计。

候选矩阵同时写入项目共享登记表。每次开始生产前先同步并读取登记表中的活动记录；占位成功后才能创建正式工作目录。这样其他窗口能看到尚未打包的候选题，而不是等到 `proposal.json` 出现后才发现重复。

参考题只用于确定任务形态和质量尺度。禁止复制或改写原题的需求、`solution/`、测试断言、隐藏用例或文件级实现路线。不能把原题换一个仓库、语言或接口名后当成新题。新题应从另一个真实、可验证的软件需求出发，`related_question` 只记录核心能力关联。

## 生产前的场景去重

DeepSWE 新题在选定仓库和实现路线前，先读取 [scene-dedup.md](scene-dedup.md)。从当前项目根目录使用 `./Benchmark/deep-swe-main/tasks/manifest.json` 和全部 `tasks/*/instruction.md` 作为原始题库；同时扫描当前项目中已有的 deepSWE proposal、登记记录和题包。若用户项目采用其他 benchmark 相对路径，先在项目内定位后使用该相对路径。只检查任务目录名或仓库名不够。

内部 `scene-profile.json` 应使用简洁英文描述，便于与 DeepSWE 英文题面做文本召回。运行 `scripts/check_scene_overlap.py` 后，至少人工复核：

- 排名最靠前的 20 道题；
- 同一上游仓库的全部题；
- 即使文本相似度不高，但共享同一状态机、并发模型、恢复语义、解析协议或验证目标的题。

文本召回扫描全部 113 道本地题目，但它不能识别所有跨领域同构场景。最终必须做“去掉专有名词后是否仍是同一任务”的改名测试。若核心工作流、状态变化、失败恢复和 verifier 判定仍基本一致，不能生产。

## 环境

训练平台是 Linux 终端，不提供 GPU。题目不能依赖 Windows 专属能力或 GPU 才能完成的流程。

固定仓库 URL、基础提交、语言、许可证和资源限制。Agent 环境应是可提交的 Git 工作树，能够从基线导出二进制安全的 patch。

`allow_network: false` 时：

- 固定基础镜像摘要；
- 将 wheel、npm cache、Go modules、Cargo vendor 或对应语言依赖放入构建上下文；
- 安装命令使用离线模式；
- Dockerfile 不在构建期执行 `apt-get update`、`git clone`、`curl`、`wget` 或在线包管理；
- 使用 `docker build --network=none` 实际验证，不凭 Dockerfile 目测判断。

基础镜像本身由运行平台预先获取不等于题目允许联网。记录镜像名和摘要。

## 任务契约

`proposal.json` 中官方模板的 `proposal.C_agent_task` 和 `D_task_difficulties` 共同承载公开任务契约，应足以让 Agent 完成任务，包括：

- 新增或改变的公开类型、函数和配置；
- 输入、输出、排序、状态和错误语义；
- 并发、进程、持久化或资源生命周期要求；
- 与旧 API 组合时的行为；
- 参数边界及网络限制；
- 必须保留的原有行为。

不要在正式包中新增 `instruction.md` 来重复这份契约，也不要写测试名称、内部表结构、具体私有函数或参考 patch 的修改顺序。

## verifier

DeepSWE verifier 至少包含两类证据：

- F2P：基线失败，正确实现通过，证明新增行为；
- P2P：基线和正确实现均通过，保护关键旧行为。

评分要求：

- 缺失的白名单测试按失败处理；
- skipped 不算通过；
- 重复 node id 取最差状态；
- Agent patch 无法应用时给出结构化失败；
- 测试 patch 从干净 HEAD 注入；
- verifier 保存原始输出、结构化报告和二元结果；
- reward 只有在所有必需 F2P 和 P2P 通过时为 1。

最低验证矩阵：

| 状态 | 预期 |
| --- | --- |
| NOP / 原始基线 | 至少一个 F2P 失败，reward=0 |
| Oracle / 参考实现 | 所有 F2P、P2P 通过，reward=1 |
| no-skill Agent | 记录真实结果，不人工补丁 |
| with-skill Agent | 从相同干净基线运行，记录真实结果 |

若 Agent 自己写的测试通过，但私有 F2P 未全过，仍视为未解决。

## deepSWE 专家 skill 写法

先从 `D_task_difficulties` 建立逐项映射，再写正文。正文可以共享一小段共同方法，但主体要按题目难点分节。

正式包中的 `sources/skill/SKILL.md` 必须是中文文档。frontmatter 的 `description` 和所有 Markdown 标题使用中文，经验正文、状态模型、冲突分析和验证方法也用中文表达。`name`、API/类型/库名、代码、命令、路径、配置键和必须精确保留的错误字面值可以保留英文，但不能用英文句子或英文段落代替中文解释。

每个难点章节建议包含：

- 契约模型：哪些事实需要持久化，哪些状态由事实推导；
- 冲突关系：哪些操作会争用相同状态或使旧凭据失效；
- 决策方法：如何选择事务边界、排序键、所有权或恢复语义；
- 反例历史：给出抽象的操作交错或崩溃切点，不使用隐藏测试值；
- 验证思路：说明应构造哪类行为序列，不写测试名和答案代码。

例如任务包含“优先级 + FIFO + 延迟可见”，不能只写“维护排序不变量”。应要求 Agent 分别定义：可见候选集合、候选排序键、同优先级的稳定标识、延迟任务何时进入候选集合，以及重新投递是否复用原始顺序标识。

任务包含幂等键时，应说明 key 在各公开状态中的所有权、重复提交返回什么、终态是否保留映射、哪种删除会释放 key，以及并发重复提交如何收敛为单一事实。

## Agent 对照实验

DeepSWE 的 no-skill 和 with-skill 目录必须来自同一基础提交。不要复制上一轮工作树后继续修改，也不要保留 `.git` 之外的缓存、数据库或测试产物。

当前生产流程使用 `Doubao-Seed-Evolving`。Codex 只用 `prepare_trae_runs.py` 生成两套干净工作区和提示词，不启动或操作 Trae。用户手动在 no-skill 工作区运行题目，再使用 `grade_manual_trae.py --mode no-skill` 生成 patch 和独立 verifier 结果；只有 no-skill `reward=0` 才继续手动运行 with-skill，并使用同一脚本的 `--mode with-skill` 判分。用户完成 with-skill 且独立 verifier 为 `reward=1` 后，Codex 才能做最终质检、打包和上传。专家 skill 只作为 with-skill 提示词上下文，不安装为 Trae 项目级 skill。该流程不需要 `TRAE_RUN.json`、`MONITOR_REQUEST.json` 或窗口绑定。

skill 可以根据题目契约预先编写和迭代，但如果它是在观察 no-skill 的具体失败后修改的，新增内容必须保持为可迁移的专业方法。若直接指向失败断言、特定输入或漏掉的分支，该轮证据无效，应重新设计 skill 并从干净基线运行。

结果报告至少记录：

```text
模型和 Agent
基线提交
Agent 提交
网络、时限和轮次限制
F2P 通过数 / 总数
P2P 通过数 / 总数
binary reward
运行轮次与耗时
失败原因
skill 版本散列
```

## 提交前实跑

按题包实际命令执行，至少完成：

1. upstream 归档散列校验；
2. Agent Docker `--network=none` 构建；
3. verifier Docker `--network=none` 构建；
4. NOP 运行并确认 reward=0；
5. Oracle 运行并确认 reward=1；
6. 专家 skill 的难点映射人工复核；
7. 运行 `scripts/check_skill_language.py`，确认专家 skill 为中文文档；
8. ZIP 完整性、权限、泄漏和隐藏文件扫描。

9. 核对题目目录和压缩包均以 `YYYY-MM-DD-N` ID 开头，`N` 按项目历史持续累加，且没有覆盖旧题。

10. 核对 `scene-overlap-review.md` 的最终结论为 `distinct`，候选场景定稿后没有发生未复核的实质变化。

不得只根据过去的 Agent 结果推断新打包版本仍能运行。环境、测试或 schema 改动后要重跑受影响的验证。
