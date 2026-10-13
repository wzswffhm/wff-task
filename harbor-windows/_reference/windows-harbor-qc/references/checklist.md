# 直接 Harbor Windows 质检清单

本清单是 `scripts/run_qc.py` 的判定依据，也是人工复核报告的最小范围。静态检查通过不等于题目通过；动态 Oracle/NOP 门禁、测试公平性和证据闭合必须全部满足。

本清单还必须与 [采购手册接入规则](procurement-manual-integration.md) 一起执行。采购手册要求的
WIP 94 项、D01–D20、逐评分项证据链、Hack 事实等级和独立复算未完成时，最终只能判
`BLOCKED`。

## 1. 标准目录和职责

输入为 ZIP 时，压缩包内必须只有一个最外层作业文件夹；该文件夹名称必须与压缩包文件名
去掉末尾 `.zip` 后完全一致（包括大小写、空格、标点和版本后缀）。例如
`windows-demo-v1.zip` 内的最外层文件夹必须是 `windows-demo-v1/`。根目录名称不一致、ZIP
根部直接散放文件，或同时存在多个顶层目录，均判为不通过。

压缩包内的同名最外层文件夹就是正式 Harbor Task 根目录，必须直接包含：

```text
task.toml
instruction.md
environment/
solution/
tests/
jobs/
```

不使用 `outside_harbor/`、`outside_harbor-assets/`、平台 JSON 或其他 Demo 包装层。
`task.toml` 的 `[task]` 必须直接声明 `id/name`、`version`、`instruction`、`workspace`、
`setup`、`test`、`golden`，并且所有入口都指向当前根目录内实际交付的文件或目录。

每个发现的 Task 根目录必须至少包含：

```text
task.toml
instruction.md
environment/
  adapter.toml
  Dockerfile
  prepare.ps1
  validate_environment.ps1
  run.ps1
  restore.ps1
  cleanup.ps1
tests/
  test.ps1
  run_tests.ps1
  aggregate_results.ps1
  judge.toml
  rubric.json
  required_testcases.json
solution/
  README.md
  solve.ps1 或 solve.bat
```

`source.json` 为可选的来源追踪文件，存在时必须可解析且声明身份不能与
`task.toml`、`rubric.json` 冲突；缺失本身不作为质检卡点。

`test.bat`、`run_matrix.ps1`、探针和 fixtures 可以按需存在，但不能被入口调用却不交付。`solution/` 是 Golden 入口，必须存在；不能因为普通 Agent 不应看到它就把组织方题包里的参考解删掉。

职责边界：`instruction.md` 只写参与者可见的行为契约；`environment/` 只准备和恢复真实环境；`tests/` 执行独立客观验证和汇总；`solution/` 提供幂等、可执行参考解。测试、Solution、答案、凭据和 reward 不得通过 workspace、镜像、挂载、Git 历史、缓存或日志泄漏给 Agent。

## 2. 安全解包和身份

ZIP 必须拒绝绝对路径、盘符、`..`、空路径、Windows 保留名、尾随点/空格、ADS 冒号路径、符号链接、大小写冲突、重复成员、路径越界、异常压缩比、过大成员数和过大展开体积。原 ZIP Hash、Task 文件 Hash、同名根目录、`task.toml` 的 `task_id`、`[task].version`、可选 `source.json` 的 `task_id` 和 `rubric.json` 的身份必须一致；顶层 `version` 是格式 Schema 版本，不能误当 Task 版本。镜像必须可追踪，不能用 `latest`。

若交付 `source.json`，建议记录来源类型、License、Lineage、授权和污染风险；字段缺失作为人工复核警告。

## 3. 题面、测试和 Windows 价值

本节与 [quality-gates.md](quality-gates.md) 中的十项人工质量门禁同为硬性要求。目录、
模型分差和 Oracle/NOP 总分通过，不能替代逐评分项、逐 testcase 和逐模型轨迹复核。

- 每个计分 testcase 都能双向追溯到题面/公开契约；不能新增未声明要求或与题面相反的约束。
- 核心断言触发真实生产路径、输入输出、异常、状态、副作用或 Windows 终态；支持独立等价实现。
- 源码正则、关键词、Patch Diff、文件/进程/端口存在、日志文本、编译成功和模型自报只能作辅助证据。
- P2P 与修改范围相关，初始状态必须通过；核心 F2P 必须由目标缺陷导致初始失败，Golden 后通过。
- 真实运行必须使用 Windows Runtime；不能用 Linux Mock、WSL 结果或普通跨平台逻辑冒充 Windows 专项价值。
- `prepare`、`restore`、`cleanup` 可重复执行，清除旧构建、旧结果和系统残留；异步/子进程必须有完成回执或健康哨兵。
- 网络策略、权限、镜像版本、架构、Locale、Shell/Runtime、依赖、CPU/内存和超时必须可复现并可审计。
- 必须逐项核对 Golden 与 NOP 的 testcase 结果是否符合预期；标准解不得分、空跑得分，或空跑因基础设施错误得到 0，均失败。
- 必须把每项评分标准、每个 testcase 的实际执行、轨迹和得分对应起来，排除误杀、漏判、漏计分和错误聚合。
- 必须逐份检查 8 个模型 job 是否通过 Web Search、外部下载、`git pull/fetch/clone`、搜索 Golden patch/隐藏测试/reward、修改测试或 Verifier、复用旧产物等方式绕过任务。
- 必须写出 Windows 反事实；仅使用 PowerShell、盘符或 Windows 镜像不足以证明 Windows 专项价值。

## 4. 二值评分和 INVALID 门禁

`required_testcases.json` 必须是唯一、稳定的 testcase 集合，且同时包含 `F2P` 和 `P2P`。每项终态只能是 `PASS` 或 `FAIL` 才能进入正式评分。

testcase 数量规则：少于 5 条是硬性不通过；5–27 条正常；超过 27 条仅提示人工复核范围、重复度和执行预算，不因数量本身返修。

```text
VALID/1: 所有 required F2P 和 P2P 都 PASS
VALID/0: required 集合完整有效，至少一个 required testcase FAIL
INVALID: 缺失、重复、SKIP、ERROR、NOT_RUN、解析错误、授权/Runner/环境故障或正式分数与 reward/report 不一致
```

不得用 `reward=0` 把 `INVALID` 转成 `VALID/0`；不得缩小分母、删除失败 testcase、使用权重/部分分/LLM Judge 或主观软分。`score`、verifier report、逐项终态和 Harbor reward 必须互相一致。

## 5. Oracle/NOP 动态门禁

每轮必须是独立的 Harbor 调用、新 job 名和干净环境：

```text
--n-attempts 1 --n-concurrent 1 --max-retries 0
```

默认 Oracle 3 轮和 NOP 3 轮；严格模式可使用 6 轮。全部 required 结果和原始 job/trial/verifier 文件都要保留。

- Oracle：每轮完整执行、`VALID/1`、无旧产物复用；参考解必须真实应用，不能只看环境变量、任务名或日志标题。
- NOP：每轮完整执行、`VALID/0`、P2P 全 PASS、至少一个核心 F2P FAIL；失败原因必须是目标功能缺陷，不是依赖/环境/测试故障。
- 三轮（或指定轮数）中任一 BLOCKED/INVALID、缺 testcase、旧结果复用、P2P 失败或 F2P 没有失败，整体不通过。
- 完成一次干净重建/恢复并确认清理无残留；高风险题还应验证空实现、固定返回、提前退出、只修一半、吞异常和硬编码反例。

## 6. 证据和报告

质检结果放在题包外，至少包含：

- 原始输入 Hash、完整成员/Task 清单、Task/Environment/Tests/Solution Hash；
- Docker/Windows/Harbor 版本和实际镜像、架构、隔离、网络、挂载信息；
- 每次 Harbor CLI 命令、开始结束时间、job/trial/result/verifier 原文；
- required testcase 清单、逐项状态、正式 `VALID/score`、reward 一致性；
- Oracle/NOP 的稳定性门禁、失败归因、环境/题包/测试/模型区分；
- 题面与 testcase 双向映射、等价实现审查、答案泄漏/Hack 检查、来源授权和版本变更。

Oracle 的截图应截 Harbor CLI/控制台原始输出，必须能看到任务、Agent、轮次和 `VALID/1` 结果；手工制作的分数截图不算证据。报告不得写入 API key、Feishu token、`.env` 或其他凭据。

## 7. 四模型轨迹与区分度

`jobs/` 必须直接交付规定数量的 Harbor job 目录（**2026-10-13 起：必需 12 个**；含可选 GLM/Kimi 为 14 个），并保留 `jobs/config.json`、`jobs/lock.json`、
`jobs/result.json`、`jobs/job.log`。子 job 按自身元数据分类，不依赖文件夹名称；**必需**部分为：

- Qwen3.8-Max-0902：3 次；
- Opus 5：3 次；
- GLM-5.3：1 次（**自 2026-10-13 起可选**）；
- Kimi K3：1 次（**自 2026-10-13 起可选**）。
- Oracle：3 次；
- NOP：3 次。

每个 job 至少包含 `config.json`、`lock.json`、`result.json`、`trial.log`、
`artifacts/manifest.json`、`verifier/result.json`、`verifier/reward.txt`、
`verifier/test-stdout.txt`、`verifier/verifier.log`。模型 job 还必须包含
`agent/model-result.json`、`agent/trajectory.jsonl`；Oracle job 还必须包含
`agent/oracle.txt`、`agent/qc-oracle-application.json`。不得使用人工整理的分数 JSON 代替
Harbor 原始 job。

8 次模型运行必须全部 `VALID`，分数必须为二值 `0/1`，逐 testcase 集合与当前
`required_testcases.json` 完全一致。每份 job 必须保留模型和提供商、中文口语化原始提示词、
原始响应、候选补丁、trajectory、verifier report/reward、Task checksum 和运行时间。
提示词不得人为加“中文口语化提示：”前缀。

正式区分度按以下顺序判断：

```text
Opus model_score_sum > Qwen model_score_sum
```

正式区分度：若 Opus 的 `model_score_sum` 严格高于 Qwen 则通过；若两者总分相等，则使用同一 required testcase 集合上的累计通过数作为二级判据，只有 `Opus testcase_pass_sum > Qwen testcase_pass_sum` 才通过。总分相等**不限于双方均为 0**：Qwen 三次与 Opus 三次同时全部 `VALID/1`（正式分顶格）时同样走本判据，此时「双方同时三轮满分」本身不再出局，但必须由 testcase 颗粒度把两者严格分开，否则仍判不通过。若两者总分相等且 testcase 累计通过数也未严格拉开，则失败；唯一例外是 8 次模型运行全部有效且全部为 0，此时零分平局不因区分度单独返修。`qwen_opus_full_score` 与 `all_models_full_score` 必须记录进报告以说明判分颗粒度，但不再单独否决。GLM/Kimi 不参与主模型分差，GLM 1 而 Opus 0 本身不触发返修，但要纳入全模型结果分布分析；缺少规定 job、运行无效或原始证据不完整仍然不通过。`INVALID`、基础设施失败或缺结果不能按 0 分计入。

每个运行必须绑定当前 `task_id + task_version + task_hash`；所有 Harbor `task_checksum`
必须一致，并等于从当前交付 Task 目录重新计算的 checksum。仅重新生成 evidence 索引不能
让旧轨迹变成有效轨迹。题面、环境、solution、tests、required testcase 或评分修改后，旧轨迹全部作废。

## 8. 不单独触发返修的项目

下列发现可以写成信息或建议，但不得单独作为 `FAIL` 或返修理由：

- Dockerfile 的 `FROM` 未 pin SHA-256 digest；仍禁止浮动 `latest`。
- 缺少顶层 `evidence/` 目录。
- 缺少顶层 `metadata/` 目录。
- `task.toml` 缺 network policy 字段。
- 规定的 8 次模型运行全部 `VALID/0`，因此 Opus 0 = Qwen 0。
- 泛化的“每模型运行次数不足”。固定的 14 个原生 Harbor job 仍是标准目录硬门禁；缺任一规定 job 应写成目录/原始证据缺件。
- GLM 为 1、Opus 为 0；GLM 不参与 Opus/Qwen 主分差。
- testcase 超过 27 条；仅人工复核，少于 5 条才硬失败。

## 9. 一票否决

Windows 反事实价值不足、标准 Harbor 无法加载、Solution 缺失、Golden 不稳定、NOP/P2P/F2P 门禁失败、测试绑定 Golden 私有写法、基础设施故障被记成模型 0、答案/测试/凭据泄漏、环境不可恢复、旧产物污染、来源授权不清、重复/薄题、无法在预算内稳定运行，任一项都不能进入正式集。修复后必须提升版本和 Hash，在新的干净结果目录完整复验。

此外，十项人工质量复核缺失或证据不足时只能判 `BLOCKED`，不能签发最终 `PASS`。任一项
确认失败时，整题判 `FAIL`。

## 10. 采购手册完整性门禁

- 先冻结范围、版本、Task/ZIP/测试/公式/环境/运行批次身份；不同身份的结果不得混算。
- WIP 94 项必须全部留行，状态为 `PASS/FAIL/FLAG/BLOCKED/N/A`；N/A 给出依据。
- D01–D20 必须逐项执行或明确 BLOCKED，不能用总分或自动脚本摘要代替。
- 每个得分和未得分项都闭合“要求—断言—候选—执行—终态—轨迹—复算”证据链。
- 同时审查等价实现与故障反例，禁止测试只认 Golden 私有写法。
- Hack 事件区分 ATTEMPT、ACCESS_CONFIRMED、USE_CONFIRMED、SCORE_IMPACT_PROVEN。
- 正式分从 required testcase 和冻结公式独立复算；INVALID 的可信分数为 null。
- timeout、missing、parse error 必须继续查根因，不直接归为模型失败。
- 改题面、环境、Solution、Tests、required testcase 或评分后提升版本/Hash，旧轨迹作废并干净复验。
- 历史问题用于防复发，不得未经当前证据直接写成返修原因。
