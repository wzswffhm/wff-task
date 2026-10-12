---
name: obm-question-production
description: 执行 OBM Source 基准题的候选筛选、提案撰写、验证器建设、no-skill/with-skill 跑分、独立质检和通过后打包。用户要求 OBM 刷题、找题、跑题、跑分、质检或交付 proposal.json 与 sources 时使用；仅讨论通用 benchmark 或只解一道现成题时不使用。
---

# OBM 刷题工作流

以 `D:\hc\obm\需求\OBM Source 收集说明书-正式.md` 为本项目的权威需求来源，并使用 `D:\hc\obm\质检工具\obm-review-skills` 的当前最新版规则。每次开始任务时重新记录两者的版本、修改时间和 SHA-256；若质检工具内置说明书与外部正式需求冲突，以用户指定的外部正式需求为准，并在审查证据中明确记录差异。开始一次实际生产前，完整读取 [requirements-and-gates.md](references/requirements-and-gates.md) 与 [project-defaults.md](references/project-defaults.md)。用户只要求设计或检查流程时，不启动题目建设、模型运行或外部提交。

## 固定目录

- 所有下载、解压目录、Git 镜像与工作副本、Docker 构建上下文、依赖缓存、模型轨迹、运行日志、截图草稿、质检报告和其他临时文件必须放入 `D:\hc\obm\cache`。不得在项目根目录、`skills` 或 `result` 中生成临时文件。
- 每个通过“数据质量评价”第一条及最终提交检查的题目使用稳定的 `<task-id>`，正式结果写入 `D:\hc\obm\result\<task-id>\`。该目录至少包含：最终 ZIP、最终检测截图、交付索引 `README.md` 和最终 SHA-256 清单。ZIP 内仍只包含需求规定的同名外层目录、`proposal.json` 与 `sources\`；`sources` 非空时必须包含 `sources\README.md`。
- 未通过第一条硬门禁的候选只能留在 `cache`，不能在 `result` 创建占位目录或半成品。第二条属于内部检测和质量激励目标；未达成、未完成或结果不确定必须如实记录，但不阻止第一条已通过的数据进入 `result` 或提交飞书。
- skill 自身及其支持文件只放入 `D:\hc\obm\skills\obm-question-production`。
- 不把失败候选、运行日志、标准答案、隐藏检查或质检报告混入最终压缩包。

## 提案与冻结边界

最新需求与用户确认允许 AI 协助或生成自然语言内容。可以根据实际题目撰写、修订完整 `proposal.json`，包括 `expert_experience_skill`，但必须使用自然、口语化且能由真实工程证据支持的表达；不得凭空声称人工签字、专家履历或独立质检通过。用户指定的准确接收模板只有 `A_modification_idea`、`B_modification_details`、`C_agent_task`、`D_task_difficulties`；解题限制并入公开题面和 `C_agent_task`，不得再输出旧 `D_solution_constraints` / `E_task_difficulties`。

### 语言与口语化硬门禁

- `expert_experience_skill` 必须全部使用中文撰写。代码符号、命令、路径、API 名称、错误码和必要的英文专有名词可以原样保留，但解释、步骤、判断依据和经验总结必须是中文。
- `proposal.json` 中面向人的正文，包括四个接收字段、来源说明、验证思路和 `expert_experience_skill`，都必须像资深工程师在交接题目：句子自然，有具体动作、边界和原因，允许长短句混用，避免论文腔和模板腔。
- 禁止明显的 AI 痕迹：不要反复使用“本题旨在”“综上所述”“需要注意的是”“能够有效”“具有重要意义”等套话；不要把同一意思换词重复三遍；不要堆叠“系统、机制、能力、场景、质量”等抽象名词而不说明实际怎么做；不要伪造人工审核、专家签字、运行结果或来源事实。
- 写完后逐字段朗读式复核：删掉空泛的开场，补上真实对象、操作顺序、失败边界和可观察结果；如果一句话脱离本题仓库仍然成立，就优先改成和具体模块、数据、接口或故障绑定的说法。内容必须与 `sources`、公开题面和 verifier 逐条对得上，不能为了口语化牺牲技术准确性。
- 发现 `expert_experience_skill` 含有整段英文解释、隐藏测试名、固定答案、私有路径或参考实现细节时，候选不得进入跑分；先在 `cache` 修订并重新冻结哈希。

人类提交后运行结构校验并记录 `proposal.json` 与完整交付树的 SHA-256。任何正文或 `sources` 变化都会使旧的跑分和质检证据失效，必须重新冻结版本并完整重跑。运行证据路径必须位于 `D:\hc\obm\cache`。

## 当前默认配置

本批次以本地 `main.zip` 为权威版本，不要求 release tag 或远端 commit 对齐。默认优先使用 `deep-swe-main.zip`、金融领域、Python、内存数据库或 NoSQL、资深后端工程师画像和最终四字段模板。ProgramBench 的题目语言禁止 Python，必须从 `task.yaml`、镜像文档或真实仓库验证语言后才可纳入候选。首候选的能力锚点、资源预算与待补信息见 [project-defaults.md](references/project-defaults.md)。

只有进入跑分前才强制要求 no-skill/with-skill 运行器和独立质检方式均可调用。本批次的 runner 是官方 Trae CLI，provider/model ID 为 `doubao` / `doubao-seed-evolving`，通过 Agent Plan 的 `https://ark.cn-beijing.volces.com/api/plan/v3/` 接入；安装、隔离、配置、轨迹口径和 Windows/Linux 限制见 [trae-runner.md](references/trae-runner.md)。在 API 可调用、Linux 隔离环境可用且提案版本已冻结前，停止在运行准备检查点，不得产生模拟跑分。

一次正式生产任务的默认完成条件是至少生成 1 个通过“数据质量评价”第一条和最终提交检查的作业，成功写入 `result\<task-id>` 并完成飞书上传回读。默认情况下，第二条是应尽力追求的质量激励目标，不是完成或提交的硬前置。候选若未通过第一条，则自动回到选题阶段；第一条已通过但第二条未达成时，保留真实动态结果并继续交付，不把它误判为失败。

如果用户针对当前批次明确要求“第二条必须达标”“只交付第二条通过的数据”或同等意思，则本批次切换为 `item2_required`：每个正式结果都必须有同一冻结哈希下有效的 no-skill 与 with-skill 证据，并满足说明书第二条的任一分支；`not_met`、`inconclusive`、`not_run` 和基础设施中断都不能进入 `result` 或上传飞书。候选未达标时先判断能否在不读取隐藏 verifier 失败细节的前提下修订公开题面或中文专家经验；任何修订都创建新的 candidate ID、重新冻结并完整重跑两臂。无法合规修订时废弃并换题，直到达到用户指定数量，或遇到用户设定的成本/时间硬上限。

若凭据、基础设施、磁盘或用户设定的成本/时间硬上限阻止继续，则保持任务未完成并报告阻断，不虚构达标结果。每个候选使用独立 ID 和 `cache\runs\<run-id>\candidates\<candidate-id>`，保留来源、命令、配置、日志、退出码、轮次、时长、模型身份和产物哈希。

## 流量与并发策略

- 使用哈希寻址缓存：相同 Benchmark ZIP、Git 对象、Docker 基础层和依赖锁文件命中缓存时不重复下载。远程仓库先用 API/网页做轻量公开历史预检，候选通过后再进行一次浅克隆或按需稀疏检出；需要完整历史证明时才补充 fetch。
- 先做便宜门禁：语言、许可证、公开 solution、历史 commit/PR、Benchmark 复用、schema、相关度和静态可行性全部通过后才调用模型。no-skill 若在 100 轮内通过，标记第二条目标未达成；为节约流量，默认不再支付没有机会改变该结论的 with-skill 费用，但候选仍可按第一条合格数据提交。
- 模型请求只发送公开题面、必要仓库上下文和对应 Skill，不发送隐藏 verifier、无关日志、完整 Benchmark 语料或重复上下文。优先复用服务端支持的上下文缓存，但 no-skill 与 with-skill 的隔离边界不得因缓存而泄漏 Skill。
- GitHub 搜索、哈希、解压、静态扫描和互不写同一路径的候选预检可以有限并行；默认并发 2，内存允许时最多 4。
- no-skill、with-skill、独立 verifier 和最终质检默认串行。不得同时跑同一候选的两条模型臂；这会造成 CPU、内存、限流和缓存争用，破坏公平对照。在硬件资源充足、每个容器有独立且相同资源配额并完成小规模校准后，才允许不同候选并行跑分，且一旦已有候选进入动态门禁，停止启动新的昂贵候选。

## 执行状态机

1. **选题与原创性预检。** 只读取本地 benchmark 中的题面和任务配置来理解真实能力；不得为选题读取其中的 solution、tests、patch 或提交差异。保存本地 ZIP 的 SHA-256、候选来源 URL/许可证及检索记录。拒绝从公开 commit/PR、已有 patch、现成 solution 或仅改名改数字的公开题倒推任务。
2. **原创提案检查点。** 依据来源事实、能力映射和风险撰写 `proposal.json`，检查题面、验证描述与专家经验是否一致；需要用户另行审批时按其要求暂停。
3. **建设离线题目与 verifier。** 在候选缓存中构建 `sources/`。验证器应检查外部可观察行为、关键边界和反作弊条件，且不得只是复制已有 tests。先做一遍“公开契约投影”：verifier 断言的每个固定字段名、返回对象层级、状态值、幂等键组成、重放语义、异常类型、排序规则和性能上限，都必须能从公开题面直接推出；不得只在 verifier 或参考实现里出现。题面可以隐藏具体样例、随机种子和测试组合，但不能隐藏实现者必须猜中的 JSON key、返回形状或业务规则。`expert_experience_skill` 只能讲解决难点所需的领域经验，不能泄漏 verifier、隐藏样例、预期输出或测试实现。
4. **静态初验与冻结。** 先运行当前最新版 `obm-review-skills\scripts\validate_proposals.py`、Source 复用扫描、Git 公开历史检查、双相关度审查和 verifier/Skill 审查。静态初验通过后才冻结题面、Source、verifier、Skill、容器、输入、资源限制和完整交付树哈希；确认任务有可能解、无自相矛盾、资源可离线复现、难点与专家经验逐项对应、交付结构准确。
5. **no-skill 跑分。** 使用全新 `seed` 会话，不注入专家经验，不暴露 verifier 或 with-skill 轨迹。Trae 的 `--max-steps` 是上限而不是最小轮次；本批次设为 120，以便观测“超过 100 轮才通过”。若 baseline 在 100 轮以内通过 verifier，记录第二条目标未达成；若未通过但轨迹不足 100 个 `agent_steps`，记录第二条证据不足。两种结果都不推翻已经通过的第一条。保存所有实际证据。
6. **with-skill 跑分。** 当 no-skill 结果仍有机会满足第二条时，使用相同冻结题目、准确模型 ID、120-step 上限、资源和验证口径，仅增加冻结的 `expert_experience_skill`，并通过独立 verifier。以 Trae 轨迹的 `agent_steps` 数组长度计轮次，以 `llm_interactions` 数量交叉检查。no-skill 未解决而 with-skill 解决视为目标达成主分支；两组均解决时，no-skill 必须超过 100 轮，并且 with-skill 的轮次或时长至少降低 30%，目标为 50%。没有达到时标记 `not_met` 或 `inconclusive`。默认批次不得据此阻止第一条合格数据提交；`item2_required` 批次则必须返修为新候选或换题，不能打包提交。
7. **最终质检。** 对冻结版本重新运行最新版 `validate_proposals.py`、`git_provenance.py`、`obm_inventory.py`，基于 `evidence.json` 完成审查，再运行 `validate_review_payload.py` 与 `sha256_manifest.py`。第一条涉及的格式、内容相关性、原创性、可解性、verifier 质量和反泄漏审查必须全部通过；第二条动态结果单独记录为 `met`、`not_met`、`inconclusive` 或 `not_run`。不能把单次自动命令冒充完整质检。
8. **截图与打包。** 在 `cache` 生成截图草稿，截图必须显示题目 ID、质检工具版本、最终命令、退出码、结论、执行时间和交付哈希，并确保没有凭据。通过后将最终 ZIP、PNG、结果索引 `README.md` 和 SHA-256 清单原子复制到 `result\<task-id>\`。ZIP 内从同名外层目录开始，且该目录顶层只有 `proposal.json` 和 `sources/`。
9. **上传与回读。** 将 ZIP 和最终截图上传作业表；`题目名or编号` 使用 ZIP 文件名去后缀，填写真实 `关联benchmark`，状态设为 `待质检`，不填写甲方结论。上传后回读记录确认附件、名称和状态。

## 失败与重试

- 运行器崩溃、网络中断、磁盘不足等基础设施故障不算题目质检失败。修复环境后可对同一冻结哈希重跑，并保留失败日志。
- 格式或 README 等不改变题目语义的问题可以在 `cache` 修复后重新质检。修改题面、Skill、Verifier 或 Source 会使动态证据失效，必须重新冻结并完整重跑。发现公开已有解、Benchmark 任务特有数据复用或 Skill 泄漏时，直接废弃候选并创建新的 candidate ID。
- 单个候选未通过第一条时，在 `cache` 写明失败门禁并继续下一个候选。默认批次中，第一条通过而第二条未达成时不再强制换题，可进入最终质检、打包和提交；`item2_required` 批次中，第二条未达成的候选只能留在 `cache`，必须返修成新候选或换题。
- 结束状态只能是：至少一个作业有第一条完整 PASS/ACCEPT 证据、成功生成 `result\<task-id>` 并完成上传回读；或因明确的硬阻断/硬上限保持“未完成”。第二条的状态必须另行说明。禁止把“脚本能运行”“自测通过”或“看起来合理”表述成质检通过。

## 使用脚本

先校验候选结构：

```powershell
& .\scripts\validate-proposal.ps1 -ProjectDir <candidate-delivery-dir>
```

质检通过后打包：

```powershell
& .\scripts\package-result.ps1 -ProjectDir <candidate-delivery-dir> -QualityDecision <quality-decision.json> -ProposalName <new-proposal-slug> -TaskId <task-id> -FinalScreenshot <cache-path-to-final-qc.png>
```

仅使用接收方确认的四字段模板。正式校验入口是 `D:\hc\obm\质检工具\obm-review-skills`；不要再调用已废弃的 `proposal_validator` 或 `obm_delivery_qc` 目录。自动脚本只能提供结构和证据包，不能单独证明任务真正有价值。完整结果 ZIP 应包含同名最外层目录，且隐藏文件不得丢失。

Trae 运行结束后，用轨迹统计脚本生成不带判定的事实摘要；`agent_reported_success` 不能代替独立 verifier：

```powershell
& .\scripts\summarize-trae-trajectory.ps1 -TrajectoryFile <trajectory.json> -OutputFile <trajectory-summary.json>
```

运行最新版 inventory 时必须使用本批次缓存工作区，并显式绑定最新正式需求：

```powershell
python D:\hc\obm\质检工具\obm-review-skills\scripts\obm_inventory.py `
  --root <candidate-or-batch> `
  --workspace D:\hc\obm\cache\benchmark-workspaces `
  --config D:\hc\obm\cache\benchmark-workspaces\benchmark-locations.local.json `
  --governing-document 'D:\hc\obm\需求\OBM Source 收集说明书-正式.md' `
  --upstream-report <validator-report.json> `
  --output-dir <cache-review-output>
```
