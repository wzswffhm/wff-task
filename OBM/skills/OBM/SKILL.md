---
name: OBM
description: OBM Source benchmark 题目生产与交付的统一入口，覆盖从选题生产到质检交付的全流程。用户说“生成题包”“生成 OBM 题目”“继续生产”“继续返修”“检查最新结果”“质检”“跑题 N 个”“审查 proposal”“打包”“上传”时调用。内含四套子流程：production（OpenAI 兼容接口版生产，主流程）、production-trae（Trae 手动版生产，备选）、review（proposal 内容审查）、run-qc（本地跑题与质检）。当前完整支持 deepSWE，其他 benchmark 必须先读取对应规范，不能套用 deepSWE 的目录和评分规则。
disable: false
agent_created: true
---

# OBM 题目生产与交付（统一入口）

本 skill 整合 OBM 全流程，供任意 Agentic 环境直接加载使用。先按用户意图路由到对应子流程，再进入该子流程的 SKILL.md 执行。

## 意图路由

| 用户意图 | 子流程 | 入口 |
|---|---|---|
| 生产题包、生成新题、返修、继续生产、打包、上传飞书 | **production**（主流程，OpenAI 兼容接口） | 本文档 |
| 生产题包且必须由用户在 Trae 中手动跑题 | **production-trae**（备选） | `subskills/production-trae/SKILL.md` |
| 审查 proposal、复核交付内容、审计 source 复用 | **review** | `subskills/review/SKILL.md` |
| 质检某个包/目录、跑题 N 个 | **run-qc** | `subskills/run-qc/SKILL.md` |

默认使用 **production**（OpenAI 兼容接口版）。仅当用户明确要求"用 Trae 手动跑"或环境无法调用 API 时，才切换到 `production-trae`。

**两套生产流程互斥**：`production` 与 `production-trae` 的 `references/` 内容不同，不可混用。禁止把另一版的脚本、提示词或流程套进来。两版各自的规范以各自目录内的 `references/` 为准。

## 子流程目录说明

```text
OBM/
├── SKILL.md                    # 本文件：统一入口与路由
├── scripts/                    # production 主流程脚本
├── references/                 # production 主流程规范
├── agents/                     # production 主流程 agent 定义
├── proposal_validator/         # production 主流程 proposal 校验器
└── subskills/
    ├── production-trae/        # Trae 手动版生产（备选）
    ├── review/                 # proposal 内容审查
    └── run-qc/                 # 本地跑题与质检
```

各子流程自带完整的 `scripts/`、`references/`、`SKILL.md`，可独立运行。引用子流程脚本时使用 `OBM_SKILL_DIR/subskills/<名称>/scripts/...`。

## 全局边界

- 不要把 OBM 与 Harbor 生产、Pair-wise GSB 或其他标注项目混用。
- 分析请求只读材料，不修改题包；生产、返修和打包请求才写文件。
- 密钥只从环境变量或配置文件读取，绝不写入命令行、日志、截图或交付 ZIP。
- 独立 verifier 才能决定 solved，模型自报成功或退出码为 0 不能代替 verifier 结果。

以下为 production 主流程正文。使用其他子流程时，转至对应 `SKILL.md`。

---

# OBM 题目生产（production：OpenAI 兼容接口版）

先确认用户要做的是分析、生产、验证、返修还是打包。分析请求只读材料，不修改题包；生产或返修请求才写文件。不要把 OBM 与 Harbor 生产、Pair-wise GSB 或其他标注项目混用。

本 skill 是 OpenAI 兼容接口版，Seed 实验只能调用 `prepare_agent_runs.py`、`launch_seed_background.py`、`monitor_seed_experiment.py` 和 `inspect_seed_status.py` 这套后台流程。禁止打开或操作 Trae，禁止调用 Trae 执行题目，禁止把 `subskills/production-trae`（非 OpenAI 版）流程套进来；看到 Trae、手动 Trae 工作区或前台 Trae 运行要求时，应立即停用该步骤并回到本 skill 的 Seed API 流程。

执行边界：本 skill 只使用本地文件、终端命令、skill 自带脚本、Docker 和 OpenAI 兼容接口。禁止调用 MCP、Computer Use、浏览器自动化、桌面软件、IDE、Trae、飞书网页或其他图形界面。飞书读写只能通过配置核对过的本地 `lark-cli` 命令完成；Seed 定时监听只能由本地后台监控脚本完成，不创建客户端 heartbeat、automation 或其他对话定时任务。

## 选择 benchmark

先确认 benchmark 的规范名称、题目格式、运行器和验收方式。

- `deepSWE`：读取 [references/deepswe.md](references/deepswe.md)，并同时遵守 [references/common.md](references/common.md)。
- 其他 benchmark：只读取 [references/common.md](references/common.md)。再按照 [references/benchmark-template.md](references/benchmark-template.md) 阅读官方文档和本地基准样例，建立单独的 `references/<benchmark>.md` 后再生产。不得推断它使用 DeepSWE 的 F2P/P2P、Harbor 目录或 verifier。

生产新题或新 proposal 时，还要读取 [references/scene-dedup.md](references/scene-dedup.md)。返修现有题目只有在题目场景发生实质变化时才重做场景去重。

生产新题时还必须读取 [references/task-registry.md](references/task-registry.md)。项目内所有窗口共享一个题目登记表，不能依赖当前对话、目录名或人工记忆判断是否已有人生产相同题目。

本 skill 不绑定任何固定工作区路径。执行生产命令前进入用户当前项目根目录，以下内容统一以 `.` 表示该根目录。项目文件、登记表和题包路径都使用相对路径。skill 自带脚本通过 `OBM_SKILL_DIR` 引用，该变量指向当前安装的 `obm-task-production-openai` skill 目录。

运行脚本前统一选择 Python 解释器。项目虚拟环境必须优先使用，以保证 Seed SDK 和截图依赖可用；没有项目虚拟环境时才回退到系统 Python。注意 Windows 下解释器位于 `.venv/Scripts/python.exe`，Linux/macOS 位于 `.venv/bin/python`：

```bash
if [ -x ./.venv/Scripts/python.exe ]; then
  OBM_PYTHON=./.venv/Scripts/python.exe
elif [ -x ./.venv/bin/python ]; then
  OBM_PYTHON=./.venv/bin/python
else
  OBM_PYTHON=python3
fi
```

后续命令中的`$OBM_PYTHON`都指这个解释器。`prepare_agent_runs.py`、`run_seed_experiment.py`和`capture_final_check.py`会通过同一个解释器继续调用子脚本，不得混用系统 Python。

如果用户给出的规范、质检反馈或表格与本 skill 不一致，以当前项目的权威规范为准，并更新相应 reference。

## 工作方式

1. 固定 benchmark、需求范围和交付物。生产 deepSWE 新题时，先读取本地题库的 manifest，并从不同能力类型中选取可参考的任务形态；参考的是任务尺度、契约写法和 verifier 形态，不复制原题需求、测试或 solution。先把候选题写成内部场景档案，不创建正式题包。
2. 运行 `scripts/task_registry.py sync`，读取项目级共享登记表。候选场景明确后，在创建正式工作目录前运行 `scripts/task_registry.py reserve`，原子分配 `YYYY-MM-DD-N` 并登记仓库、基础提交、能力类型、场景摘要和场景指纹。多窗口不得使用只读编号结果自行命名。
3. 对 benchmark 全量题库、登记表中的活动记录、飞书 `scene_dedup` 共享记录，以及项目内既有 proposal、工作目录、交付包执行场景去重。检查场景目标、参与者与对象、工作流、状态模型、失败恢复和 verifier 行为，并保存 `scene-overlap-review.md`。结论形成后必须读取 [references/scene-dedup.md](references/scene-dedup.md)，运行 `scripts/register_scene_dedup.py` 把同一结论双写到本地共享登记表和项目飞书配置（`feishu-gsb.toml`，位于项目根目录或 `--config` 指定路径）的 `scene_dedup` 表，飞书 `标注员` 使用已验证用户的 `open_id`。只有飞书写入及读回核对成功后，`distinct` 才能更新为 `candidate`；`high-risk` 和 `duplicate` 登记后更新为 `rejected`，更换场景并重新占位。不得只保存本地记录或只写飞书。
4. 选择真实上游仓库和历史提交，确认许可证、构建方式、测试入口及离线可行性。批量或连续生产时，默认切换上游仓库和核心能力类型；只有能够证明场景、状态模型和 verifier 目标独立时，才继续复用同一仓库。
5. 先写外部行为契约，再写参考实现和 verifier。题面不泄漏内部实现路线。生产新的 deepSWE 题包时，按 [references/deepswe.md](references/deepswe.md) 的覆盖要求设计 F2P、P2P：两类各至少 71 个有效、互不重复的测试节点；数量不够时先扩展真实行为覆盖或更换题目，不能靠重复用例凑数。
6. 从行为契约提取 solution constraints 和 task difficulties。前者写进官方 C_agent_task，后者按条目写进 D_task_difficulties；两者不能混写。`proposal.json` 中所有面向人的说明都必须是自然中文，句子要直接、好读，不能出现英文说明、中英夹杂或模板化的 AI 套话。
7. 编写题目专属专家 skill，并完成“难点—skill—验证”逐项映射。正式包中的 `sources/skill/SKILL.md` 必须使用自然、口语化的中文撰写，像有经验的工程师在讲自己会怎么分析、哪里最容易出错、先做什么再检查什么。不得交付英文正文、翻译腔、论文腔或“本文将、综上所述、值得注意的是、旨在、至关重要”一类模板化表达。API 名、代码、命令、文件路径、YAML 字段和必须精确保留的错误字面值可以使用英文，但必须放进反引号或代码块。proposal、verifier 和 skill 必须由专家人工撰写和复核，不能把 AI 自动生成内容直接作为交付物。
8. 按 benchmark 的正式结构整理提交包。DeepSWE Source 包不提交 `instruction.md`；题目契约按官方模板写入 `proposal.json` 的 A/B/C/D 字段，`sources/README.md` 必须逐项说明包内文件用途。`sources/app/README.md` 可以作为上游项目说明，但不能替代根目录 README。先运行 `scripts/check_proposal_language.py` 和 `scripts/check_skill_language.py`，再运行 skill 内置的 `proposal_validator/validate_proposals.py`、`check_package.py`、实际构建和 verifier。新 deepSWE 题包还要核对 `config.json` 中两类去重后的节点 ID 各不少于 71 个，并用实际收集和 NOP/Oracle 结果确认它们都运行且分类正确；静态检查通过不等于达到此门槛。正式包生成后用登记时返回的 `reservation_id` 把状态更新为 `packaged` 并记录包路径。
9. 正式包生成后，为 Seed API 对照实验准备 no-skill 和 with-skill 两套干净仓库、提示词及运行记录。deepSWE 读取 [references/agent-workflow.md](references/agent-workflow.md)，使用 `scripts/prepare_agent_runs.py`。API 配置只从项目根目录的 `model.env` 或显式 `--env-file` 读取，不复制进题包、工作区、提示词或日志。
10. 使用 `scripts/launch_seed_background.py` 在独立后台会话中启动 `scripts/monitor_seed_experiment.py`，不得让当前 Codex 回合阻塞等待 Seed。`prepare_agent_runs.py --run-seed` 默认后台启动并立即返回；no-skill 和 with-skill 都由同一个后台监控器每 300 秒（5 分钟）读取一次实验阶段、Docker Agent 进度、两侧实时轮次和 verifier 结果。后台运行期间只让监控器自己定时读取状态；不要创建 MCP、客户端 heartbeat、automation 或其他对话定时任务。需要查看时运行一次 `scripts/inspect_seed_status.py`，不读取完整日志。with-skill 没通过时必须先分析本轮结果和缺口，再修改专家 skill，并从同一 upstream 的全新工作区重跑，不能直接重跑或沿用旧工作区。终态后按结果继续：通过则收尾；`needs_skill_revision` 则按该返修流程重跑；`needs_task_hardening` 则返修题目并重跑两侧；基础设施错误先诊断，修复后使用新目录重试，连续三次同因错误才停止。除非缺少用户授权、外部凭证或发生连续三次同因基础设施错误，不得只报告“需要返修”后停住等待用户。必须先运行 no-skill，完成后用独立 verifier 判分。只有 no-skill 的 `reward=0` 才运行 with-skill；no-skill 的 `reward=1` 表示题目不够难，应停止本轮、返修题目并从同一新基线重新生成两套目录。硬验收始终是 no-skill `reward=0`、with-skill `reward=1`。轮次偏好默认是 no-skill 至少 101 轮、with-skill 接近 70 轮（默认 60–80）；未达到只产生调优告警，不能代替或推翻 verifier 结果，也不得通过空转凑轮次。API 错误、监控超时、工具崩溃和 verifier 基础设施错误不能算 no-skill 失败。
11. no-skill 失败而 with-skill 也失败时，不能直接重跑。必须读取本轮 `EXPERIMENT_RESULT.json`、`TURN_STATS.json`、`API_RUN.json`、`TRANSCRIPT.jsonl`、`PROGRESS.json`、`VERIFICATION.json` 和 verifier 日志，在本轮运行目录生成 `WITH_SKILL_GAP_ANALYSIS.md`，逐项记录失败行为、日志证据、已完成部分、缺失能力和下一条可迁移 skill 经验。确认缺口后返修中文 `sources/skill/SKILL.md`，只能增加题目难点对应的方法，不能写入隐藏测试、固定失败输入、私有符号、上一轮断言或文件级答案。skill 改完后，马上执行中文、泄漏、题包和难点映射检查，从同一干净 upstream 新建版本化 with-skill 工作区并重跑；只改 skill 时可以复用上一轮有效的 no-skill `reward=0` 证据。下一轮仍失败时继续执行同一分析闭环，不得泛泛重跑。不得把返修留到下一次人工“继续”消息。若题目、题面、upstream 或 verifier 有变化，则 no-skill 和 with-skill 都必须重跑。
12. 只有 `EXPERIMENT_RESULT.json` 明确记录 no-skill `reward=0`、with-skill `reward=1`，`TURN_STATS.json` 已统计两侧轮次，并且正式静态检查、NOP、Oracle、离线构建和泄漏检查全部通过，题目才完成。轮次偏好字段仅作运行分析，不影响通过判定；若未达偏好，应分析题目是否过快暴露关键路径或专家 skill 是否过于冗长，但不能为了命中数字篡改实验。监控器在严格对照通过后自动调用 `scripts/finalize_seed_delivery.py`，依次完成最终质检、仪表盘截图和正式 ZIP 打包；任一步失败都按基础设施或交付失败停止，不得上传。
13. 最终交付到飞书时读取 [references/feishu-submission.md](references/feishu-submission.md)，使用项目飞书配置（`feishu-gsb.toml`）中的唯一 CLI 和 `submission` 目标配置。场景去重使用同一配置文件中的 `scene_dedup` 目标，但它发生在正式生产前，两张表和两套字段不得混用。每次写入前先运行 `lark-cli auth status --json --verify`，核对返回的 `appId` 和 `openId` 与配置一致，再解析并核对 Base、表、视图、字段类型和选项。所有写入使用 `--as user`，人员字段写入配置中已验证用户的 `open_id`。账号不一致、链接无权访问或目标未核对时不得写入，也不得改用网页或 bot 身份。
14. 飞书提交采用可续传流程。先按正式题包文件夹名查询 `题目名or编号`，存在同名记录时继续该记录，不重复新增；不存在时创建一行并填写题目名、`关联benchmark=deepSWE` 和 `标注人`。随后分别把正式题包 ZIP 上传到 `交付压缩包`，把对应的 `FINAL_CHECK.png` 上传到 `最终检测skill的检测结果截图`。两个附件写入成功并读回核对后，最后把 `状态` 更新为 `待质检`。不得上传 API 密钥、`model.env`、Seed 完整轨迹、私有 verifier 日志、参考答案或内部工作目录。

训练平台是 Linux 终端且不提供 GPU；题目必须能在 Linux、无 GPU、固定资源和指定网络策略下完成，不能依赖 Windows 专属能力。

## 参考 deepSWE 题库选题

本地 `Benchmark/deep-swe-main` 既是去重语料，也是 deepSWE 任务形态的参考库。生产新题时应读取 `tasks/manifest.json`，并按需查看不同任务的 `instruction.md` 和 `task.toml`，了解真实题目的规模、公开契约、环境约束和验证方式。

不要只按 manifest 中的 `feature_request`、`bugfix` 或 `enhancement` 分类选题。这些标签过粗。应按主要推理能力划分任务类型，例如：

- API、类型系统和数据模型；
- 解析、格式化、序列化和协议语义；
- 状态机、生命周期和历史恢复；
- 并发、调度、队列和取消传播；
- 持久化、事务、缓存和崩溃恢复；
- 资源控制、性能和有界执行；
- 安全分析、污点传播和策略执行；
- UI、浏览器事件和可观察行为。

这份类型表用于扩大选题范围，不是固定枚举。类型判断应落在任务的核心状态、冲突关系和 verifier 行为上，不能只看语言、仓库名或公开 API 名称。

连续生产多个题包时，先建立内部选题清单，至少记录“参考任务、能力类型、候选上游仓库、候选场景、与参考任务的实质差异”。默认选择不同能力类型和不同上游仓库，避免多个题包共享相同代码基线。用户明确指定同一仓库时可以复用，但每道题仍须单独通过场景去重。

deepSWE 原题只能作为题型和质量参考。不得把原题换仓库、换语言或换接口后重新包装；不得复制其 `solution/`、隐藏测试、固定断言或实现路线。`related_question` 可以指向能力上相关的原题，但新题必须来自新的真实软件需求，并具有独立的行为契约和 verifier。

## 场景内容去重

场景去重是新题生产的前置门槛。改仓库、语言、API 名、数据格式或测试输入不能让重复场景变成新题。比较时忽略这些表面差异，重点判断：

- 最终要解决的问题和成功条件；
- 谁对什么对象执行哪些操作，操作顺序如何；
- 状态、所有权、排序、持久化或生命周期如何变化；
- 并发、冲突、失败和恢复怎样影响结果；
- verifier 实际区分哪些正确与错误行为。

先建立 `scene-profile.json`，再运行：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/check_scene_overlap.py" \
  --candidate ./work/candidates/example/scene-profile.json \
  --benchmark-root ./Benchmark/deep-swe-main/tasks \
  --project-root .
```

脚本只负责扫描全量语料和召回相近题，不能代替语义判断。必须阅读召回结果、同仓库题目及同能力族题目，并保存内部 `scene-overlap-review.md`。结论只能是 `distinct`、`high-risk` 或 `duplicate`。`high-risk` 和 `duplicate` 都不能进入正式生产；修改候选场景后要重新运行并复核。

结论形成后必须运行 `scripts/register_scene_dedup.py`。该命令按 `题目编号` 在已核对的飞书去重表中创建或续写唯一记录，填写`核心场景`、`对比题面`、`去重判断`、`判断依据`、`标注员`、`题目编号`和`题面`，读回核对后保存本地 `scene-dedup-record.json`，并把飞书 `record_id`、结论和本地路径写入 `work/task-registry.json`。不得手工把登记表状态改为 `candidate` 来绕过双写。

如果把两道题的仓库名、类型名和接口名替换成通用名后，核心工作流、状态转移、失败恢复和验证目标仍基本相同，应判为重复。完整方法和记录格式见 [references/scene-dedup.md](references/scene-dedup.md)。

## 新题命名

所有新题使用同一个 proposal ID：`YYYY-MM-DD-N`。日期取创建题目当天的本地日期，`N` 是该日期在当前项目中已有题目和活动占位之后的下一个正整数。正式提交包根目录和压缩包遵守官方命名 `<benchmark>_<proposal_name>`，其中 `<proposal_name>` 必须以该 ID 开头，例如 `deepSWE_2026-09-22-1-click-parameter-snapshot`。

例如当天没有题目时使用 `2026-09-22-1`，当天已有 `2026-09-22-1` 和 `2026-09-22-2` 时使用 `2026-09-22-3`。不要使用旧的自定义名称代替 ID，也不要把不同日期的编号连续累加。

候选场景明确后，运行原子占位命令：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/task_registry.py" reserve \
  --root . \
  --benchmark deepSWE \
  --slug short-description \
  --repository owner/repository \
  --base-commit COMMIT \
  --capability-type capability-family \
  --scene-summary "Concise scene summary" \
  --scene-profile ./work/candidates/short-description/scene-profile.json
```

`scripts/next_task_id.py` 只能用于只读预览，不能用于正式生产占号。正式编号必须由共享登记表在文件锁内分配，否则多个窗口可能得到同一个编号。

如果题目需要更长的展示标题，把 ID 放在 proposal name 最前面，例如 `deepSWE_2026-09-22-1-diskcache-leased-work-queue`；同一题的目录和压缩包必须同名。

## 必须遵守的边界

- `related_question` 表示与原 benchmark 题目的能力关联，不要求使用相同仓库或环境。
- `related_question` 不能作为场景原创性的证据。能力相关的两道题仍要证明业务或工程场景、状态模型和验证目标存在实质差异。
- `related_question` 必须存在于项目内离线 benchmark 映射；`domain` 必须以该题在映射中的官方分类前缀开头，不能只写自定义领域名。
- 专家 skill 可以降低分析难度，但不能包含参考实现、隐藏测试名称、固定测试输入、上一轮失败点或文件级答案提示。
- 正式包中的专家 `SKILL.md` 必须是中文文档。标题、frontmatter 的 `description`、经验说明、分析方法和验证思路都要使用中文；`name`、API/类型/库名、代码、命令、路径、配置键和错误字面值等技术标识可以保留英文。不得用整段英文正文配少量中文说明规避检查。
- `proposal.json` 的官方字段名、枚举值、`domain`、`related_question`、仓库 URL 和提交散列按规范保留；A/B/C/D、`proposal_sources`、`proposal_scene`、`proposal_verify` 和 `expert_experience_skill` 中面向人的文字必须是中文。技术标识只能放在反引号、代码块或 URL 中，不能直接混在中文说明里。
- proposal 和专家 skill 都要像人写的。优先用短句和明确动作，直接说“先做什么、为什么、哪里容易错、怎么验证”。不要使用“本文将、以下将、综上所述、值得注意的是、需要注意的是、旨在、通过上述、至关重要、不可或缺、显著提升、全面提升”等模板化套话，也不要堆砌“确保、完善、增强、优化”却不说明具体对象和行为。
- no-skill 失败后，不得把该失败用例改写成 targeted hint 再称为有效 with-skill 结果。只改 skill 时可以复用散列一致且 verifier `reward=0` 的 no-skill 证据，但 with-skill 必须从干净基线重跑；题目、题面、upstream 或 verifier 变化后两侧都要重跑。
- no-skill 与 with-skill 仓库必须从同一份 upstream 归档创建，具有相同 Git HEAD 和干净工作树。两边不能互相复制 Agent 修改、缓存、测试产物或对话结论。
- 两份 Agent 提示词的任务契约必须一致。with-skill 只能在相同题面后增加提交包中的专家经验，不得增加参考实现、隐藏测试、固定输入、失败断言或上一轮运行结果。
- verifier 验证公开行为，不比较 Agent patch 与参考 patch，不依赖 Agent 工作目录残留。
- `allow_network: false` 时，构建和测试所需依赖必须随包提供或已在固定镜像中；实际用禁网构建验证。
- 正式提交包不放 `instruction.md`、参考答案、运行轨迹、验证输出、Git 历史、缓存或密钥，除非当前 OBM 规范明确要求。
- 不要把题面、Harbor 数据、Agent 运行目录或与 proposal 无关的材料放进正式包；官方要求的最小结构是 `proposal.json` 和 `sources/`，其中必须有 `sources/README.md`。
- 题目必须来自三种官方造题方式之一：真实 Repo/Source 加新需求、现有软件/System 加新目标，或专家日常工作任务。不能从公开 commit、PR、issue 或可直接搜索的 solution 反推。
- 每道新题必须先写入项目级共享登记表。不得删除其他窗口的活动占位，不得复用已有 `reserved`、`candidate` 或 `packaged` 记录的 slug 或场景指纹。
- 每次场景去重结论都必须同时保存在本地和配置指定的飞书去重表；`distinct`、`high-risk`、`duplicate` 都要登记。飞书记录必须包含已验证用户的`标注员`，同一`题目编号`只能续写，不能重复建行。

## 难点与专家 skill 的对应门槛

在写完 proposal 后，逐条读取官方模板中的 `D_task_difficulties`。每条难点必须在题目 skill 中有一段具体经验，至少回答：

1. 需要建立什么模型、状态或关系；
2. 哪些操作、阶段或模块会发生冲突；
3. 如何检查设计是否正确；
4. 哪类测试能区分正确实现和常见错误实现。

“检查事务边界”“维护不变量”“增加并发测试”只能作为共同方法，不能代替题目特有经验。例如题目同时要求优先级、FIFO 和延迟可见，skill 应说明候选集合、排序键、不可见任务是否参与排序，以及重新投递时保持哪一个顺序标识。

提交前制作一份内部映射表：

```text
难点原文 | skill 对应章节 | 给出的具体经验 | verifier 对应行为 | 是否泄漏答案
```

任一难点只有通用建议、没有对应章节或无法指出验证行为时，停止交付并补写 skill。

专家 skill 的正文必须用中文表达。引用上游 API、代码符号或协议术语时，可以保留原始英文并在中文句子中说明其含义。Markdown 标题也必须包含中文，不要使用纯英文标题。完成后运行：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/check_proposal_language.py" \
  ./output/deepSWE_YYYY-MM-DD-N-description/proposal.json

"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/check_skill_language.py" \
  ./output/deepSWE_YYYY-MM-DD-N-description/sources/skill/SKILL.md
```

两个检查都会拒绝未包裹的英文说明、模板化 AI 套话和过长的书面句子；专家经验还必须有“我会、我一般、先、再、遇到、最容易、不要、可以”等自然表达。检查未通过时不得打包，也不得准备 with-skill Agent 运行。

## 工具和检查

先运行 skill 内置的 proposal validator，检查严格 JSON 字段、题包根目录命名、`related_question` 是否存在以及 `domain` 是否匹配 benchmark 映射。`OBM_SKILL_DIR` 指向当前安装的 skill 目录：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/proposal_validator/validate_proposals.py" \
  ./output/deepSWE_YYYY-MM-DD-N-proposal-name
```

再对 deepSWE 提交包运行 skill 内置 checker：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/check_package.py" <folder-or-zip> --benchmark deepSWE
```

静态检查不能替代 Docker 和 verifier 实跑。检查完成后还要执行 benchmark reference 中的验证矩阵。

正式包通过 NOP/Oracle 后，为 Seed API Agent 准备并运行对照目录：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/prepare_agent_runs.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-description \
  --run-root ./work/YYYY-MM-DD-N-description/agent-runs \
  --run-seed \
  --env-file ./model.env \
  --model doubao-seed-evolving \
  --max-turns 120 \
  --poll-seconds 300 \
  --target-no-skill-min-turns 101 \
  --target-with-skill-turns 70 \
  --target-with-skill-tolerance 10
```

该命令必须生成：

```text
agent-runs/
  no-skill/
    repo/
    PROMPT.md
    RUN_RECORD.md
  with-skill/
    repo/
    PROMPT.md
    RUN_RECORD.md
    seed-output/
    verification/
  BASELINE.json
  EXPERIMENT_RESULT.json
```

如果目标目录已存在，先判断其中是否已有 Agent 结果；不得覆盖或清理已有运行。完整准备、执行和回收规则见 [references/agent-workflow.md](references/agent-workflow.md)。这些目录属于内部验证材料，不进入正式 OBM ZIP。

如果材料已经存在但尚未执行，使用监控器启动实验，不直接裸跑编排器：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/launch_seed_background.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-description \
  --run-root ./work/YYYY-MM-DD-N-description/agent-runs \
  --env-file ./model.env \
  --model doubao-seed-evolving \
  --max-turns 120 \
  --poll-seconds 300 \
  --target-no-skill-min-turns 101 \
  --target-with-skill-turns 70 \
  --target-with-skill-tolerance 10
```

命令返回 `BACKGROUND_RUN.json`、后台 PID、日志路径和精简状态命令后，不使用阻塞式 shell 等待，也不在当前回合反复读取进度文件。监控器在后台按 `--poll-seconds` 自己轮询；需要查看时只运行一次返回的 `status_command`。终态后读取必要的最终 JSON，继续返修或收尾。不得把客户端、MCP 或对话定时任务当作 Seed 监控器。

Seed 通过 OpenAI 兼容接口调用。编排器向模型提供受限的文件、补丁和命令工具；文件工具只能访问对应 `repo`，命令在题目 app Docker 镜像中以 `--network=none` 运行，只挂载当前 repo，不挂载 `model.env`、正式题包或 verifier。模型不能看到私有测试和上一轮 verifier 失败详情。

Seed 轮次由 `run_seed_agent.py` 每轮更新到 `PROGRESS.json`，监控器汇总到 `TURN_STATS.json`。no-skill 和 with-skill 仍须分别由 verifier 判定 `reward=0` 和 `reward=1`。默认偏好 no-skill 至少 101 轮、with-skill 70±10 轮；不满足偏好只写告警，不写入 `needs_turn_profile`，也不阻止最终质检或上传。不能修改停止条件、插入无意义工具调用或要求模型空转来人为达到轮次目标。

需要手动查看时只运行一次精简状态命令：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/inspect_seed_status.py" \
  --run-root ./work/YYYY-MM-DD-N-description/agent-runs
```

只有调试监控器本身时才给 `prepare_agent_runs.py` 增加 `--foreground`；正常生产禁止以前台阻塞方式等待 Seed。

`run_seed_experiment.py` 的退出状态用于驱动返修：

- `0`：no-skill `reward=0` 且 with-skill `reward=1`；
- `20`：no-skill 通过，需要提升题目难度；
- `21`：with-skill 未通过，需要返修专家 skill；
- `22`：API、Docker、工具或 verifier 基础设施错误，不能判断题目或 skill 质量。
- `23`：保留作旧版本兼容码；当前流程不因轮次范围退出。

每次返修使用新的版本化实验目录，不覆盖旧证据。同一基础设施错误连续出现三次时停止自动重试并报告。no-skill 通过后的返修应增加真实的状态组合、冲突关系、失败恢复或资源边界，并同步更新 proposal、参考实现、verifier 和 skill；不得只增加冷僻固定输入、缩短时限或依赖偶然超时制造失败。场景目标或核心状态模型发生实质变化时，重新执行场景去重并更新登记表。

只修改专家 skill 后，可以把上一轮 `EXPERIMENT_RESULT.json` 传给 `--accepted-no-skill-result`，复用其中有真实运行记录且 `reward=0` 的 no-skill 证据。脚本会核对 upstream、基线 HEAD、proposal、任务契约、no-skill 提示词、verifier、模型和运行参数；任何一项变化都会拒绝复用。

实验通过后，监控器默认自动生成最终检查截图并打包。需要单独重现该阶段时运行：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/capture_final_check.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-description \
  --experiment-result ./work/YYYY-MM-DD-N-description/agent-runs/EXPERIMENT_RESULT.json \
  --output-dir ./work/YYYY-MM-DD-N-description/final-check \
  --benchmark deepSWE
```

只有 `FINAL_CHECK.json` 的 `ok` 为 `true` 才能把 `FINAL_CHECK.png` 作为通过证据。PNG 使用 1440 宽的仪表盘布局（高度随内容动态），展示四项主检查、四张指标卡（校验错误、阻断项、质检项目通过、人工复核提醒）、Seed 对照证据和证据散列。Seed 面板必须展示 F2P/P2P 真实明细（`passed/expected`，由 `capture_final_check.py` 从两侧 `verification/VERIFIER_RUN.log` 的 grader JSON 块解析），不得用轮次数或问号代替。"需要处理"（黄色待复核）区段只在检查输出存在真实 `[WARN]` 提醒时渲染，内容为提示原文，不得在无提醒时展示。某侧轮次达到偏好时才在截图中显示该侧真实轮次；未达标侧不显示轮次数值。未达标轮次只保留在 `TURN_STATS.json` 中。必须同时保留 `FINAL_CHECK.txt` 和原始 JSON，不能用手工编辑图片替代命令结果。在 Windows 宿主机上，`capture_final_check.py` 与 `build_delivery_zip.py` 会自动把 `check_package.py` 的题包检查与 ZIP 自检放进 Linux 容器执行（镜像可用 `OBM_CHECK_IMAGE` 覆盖），无需人工干预；PNG 变更后必须重跑收尾链，因为 `screenshot_sha256` 与 `FINAL_CHECK.json` 绑定。

完整自动收尾也可单独执行：

```bash
"$OBM_PYTHON" "$OBM_SKILL_DIR/scripts/finalize_seed_delivery.py" \
  --task-dir ./output/deepSWE_YYYY-MM-DD-N-description \
  --run-root ./work/YYYY-MM-DD-N-description/agent-runs
```

该脚本先生成 `FINAL_CHECK.txt`、`FINAL_CHECK.json` 和 `FINAL_CHECK.png`，检查通过后再构建与题包目录同名的 ZIP，并对 ZIP 重新运行 `check_package.py`。已有截图、JSON 或 ZIP 时拒绝覆盖。

## 官方质量门槛

首轮格式通过不等于可以交付。以下任一情况都应拒绝验收并返修：proposal 自相矛盾或不存在可行解；从公开 commit、PR、issue 或可搜索 solution 倒推任务；只改 benchmark 名称、数字或固定输入制造新题；verifier 只是复制已有测试；专家说不清 verifier/test 为什么存在或不知道题目如何完成；skill 只是通用 coding 流程；skill 泄漏 verifier、测试或答案。

还必须用实际 Seed API Agent workflow 证明 proposal/verifier 和 skill 有价值。本流程采用严格的失败变通过门槛：no-skill 由 verifier 判定 `reward=0`；with-skill 从相同基线运行并得到 `reward=1`。轮次默认按 no-skill 至少 101、with-skill 70±10 统计偏好，但不作为验收范围。API 失败、超时或基础设施异常都不能代替 verifier 失败。没有完整运行记录时，只能说“未验证”，不能声称满足门槛。

## 完成标准

- proposal 按官方顺序包含 A/B/C/D，难点字段使用 `D_task_difficulties`；枚举、domain 和路径引用符合当前规范；
- proposal validator 通过：根目录为 `<benchmark>_<proposal_name>`，proposal name 以日期 ID 开头，`related_question` 和 `domain` 与离线 benchmark 映射一致；
- DeepSWE 正式包不含 `sources/app/instruction.md`，且 `sources/README.md` 逐项说明文件用途；上游项目说明可放在 `sources/app/README.md`；
- 场景档案已与 benchmark 全量题库及项目内既有题目比对，结论为 `distinct`；本地 `scene-overlap-review.md`、`scene-dedup-record.json` 和共享登记表均已保存，飞书去重表存在同一`题目编号`的唯一记录，`标注员`为配置中已验证用户且读回核对通过；
- 题目在共享登记表中有唯一 `reservation_id`，编号没有与其他活动记录冲突，最终状态和正式包路径已更新；
- 题目需求、参考实现、verifier 和专家 skill 相互一致；
- `sources/skill/SKILL.md` 的标题、说明和经验正文为中文，技术标识之外没有英文段落；
- `proposal.json` 的所有可读说明为自然中文，技术标识均已用反引号、代码块或 URL 隔离，没有英文说明、中英夹杂和模板化 AI 套话；
- `sources/skill/SKILL.md` 使用口语化的工程经验表达，能直接读出“先做什么、哪里容易错、怎么检查”，没有翻译腔、论文腔和 AI 模板句；
- 基础版本失败、参考实现通过，原有关键行为不退化；
- 新生产的 deepSWE 题包中，F2P、P2P 各至少有 71 个有效且互不重复的测试节点；已核对实际收集与 NOP/Oracle 结果，没有用重复参数、拆分同一断言或无关测试凑数；旧题包不因这条新增目标被追溯判为失败；
- 已提供可直接交给外部 Agent 的 no-skill 与 with-skill 仓库和提示词；两套仓库 HEAD、文件树和初始工作树一致，唯一实验变量是专家 skill；
- `EXPERIMENT_RESULT.json` 记录 API 模型、提示词散列、基线 HEAD、轮次、耗时、patch 散列以及两侧 verifier 结果；no-skill `reward=0`，with-skill `reward=1`；
- 每次 with-skill 失败都保留本轮 `WITH_SKILL_GAP_ANALYSIS.md`，并能看到对应的新 skill 版本、新工作区和下一轮运行目录；没有失败分析和版本化返修记录，不得宣称已完成；
- 定时监控已持续到实验结束，`MONITOR_STATUS.jsonl`、`SEED_EXPERIMENT.log`、`EXPERIMENT_PROGRESS.json` 和 `TURN_STATS.json` 均存在；轮次统计来自实时轨迹或 `API_RUN.json`，默认偏好 no-skill 至少 101 轮、with-skill 70±10 轮，未命中时已有调优说明但不改变严格 reward 结论；
- Seed 由 `BACKGROUND_RUN.json` 记录的独立后台进程执行；后台监控器按 `--poll-seconds` 轮询并写入状态文件，当前对话不创建定时任务、不打开其他软件；
- 自动收尾已生成状态为 `passed` 的 `FINALIZATION_RESULT.json`，质检截图和正式 ZIP 均与本轮实验散列绑定；
- Seed 命令工具在禁网 Docker 中运行，API 凭证没有进入题包、repo、提示词、轨迹、patch 或上传材料；
- `FINAL_CHECK.json` 为通过状态，并保留未编辑的 `FINAL_CHECK.txt` 与 1440 宽仪表盘 `FINAL_CHECK.png`；截图展示四张指标卡，F2P/P2P 为从 verifier 日志解析的真实明细，"需要处理"区段仅在存在真实 `[WARN]` 提醒时出现，只有达到偏好的 Seed 侧才显示实际轮次；
- 每条任务难点均有题目专属 skill 经验；
- 离线构建、可执行 verifier、泄漏扫描和压缩包完整性均通过；
- 正式 ZIP 与题包目录同名，只包含正式交付包，不包含 no-skill、with-skill、Agent 输出、验证日志、密钥或内部工作目录；ZIP 已由自动收尾脚本再次通过 `check_package.py`；
- 只有用户提供飞书链接且 CLI 身份、Base、表、视图、字段类型和选项均核对无误后才上传；同名记录只续传，不重复建行；
- `交付压缩包` 和 `最终检测skill的检测结果截图`附件均已读回核对，`标注人`是配置中已验证用户的账号，最后才把状态改为`待质检`。

## Windows 宿主机注意事项

训练与验收平台是 Linux；在 Windows 宿主机生产时，以下差异已由脚本兼容层或工作区模板处理，但必须知道它们的存在，出现异常时按对应条目排查：

- **可执行位**：Windows 文件系统 `st_mode` 恒 0o666，无法表达 POSIX exec 位。`capture_final_check.py` 与 `build_delivery_zip.py` 已内置 Windows 分支，把 `check_package.py` 的题包检查与 ZIP 自检放进 Linux 容器（挂载题包/ZIP 目录与 skill 根，镜像默认 digest 固定的 `python` 镜像，可用 `OBM_CHECK_IMAGE` 覆盖）；ZIP 写入时对 `sources/verifier/test.sh`、`sources/verifier/grader.py` 强制 0o755，其余文件 0o644。手动复检也应在容器内执行，不要在宿主机直接跑 `check_package.py`。
- **Agent 补丁落盘**：`run_seed_agent.py::write_patch` 必须以 `newline=""` 写文件；Windows 文本模式会把 `\n` 翻译成 `\r\n`，导致容器内 LF 树 `git apply` 失败，双侧出现"假 0"。verifier 侧 `grader.py` 还应对补丁做 CRLF→LF 归一兜底。
- **上游归档**：构建 `upstream.tar.gz` 与 test.patch 时使用 `git -c core.autocrlf=false archive`，diff 类产物生成后做 CRLF→LF 归一；Windows checkout 会在容器内留下 100755 索引污染，app 镜像构建需 `git config core.filemode false` 并对已暂存文件 `update-index --chmod=-x` 后再提交。核对行尾必须用 Python `open('rb')` 或容器内 `od -c`，Git Bash 的 `cat -A` 因 MSYS 文本模式不可信。
- **Shell 路径转换**：Git Bash 下向 docker 传 `/container/path` 参数必须设 `MSYS_NO_PATHCONV=1`，否则被改写为 Windows 盘符路径；从 Python `subprocess` 调用 docker 不受影响。
- **中文字体**：渲染仪表盘依赖系统中文字体；Windows 使用 `C:/Windows/Fonts/msyh.ttc` 等，缺字体时 PIL 默认字体渲染中文为方块。
- **lark-cli**：Windows 上必须用直连 `node` 的转发可执行（shim），不能让 Python 经 `cmd.exe` 调 `lark-cli.cmd`——URL 中的 `&` 会被拆断，JSON 载荷会被拆成位置参数。
- **后台监控器**：分离式孙进程可能随任务结束被沙箱回收。启动后必须确认 `SEED_EXPERIMENT.log` 存在且 `MONITOR_STATUS.jsonl` 在增长，不能只信 `BACKGROUND_RUN.json` 的 PID。
- **目录清理**：删除工具可能拦截递归删除；归档旧产物用重命名（加轮次后缀），不删除既有证据。
