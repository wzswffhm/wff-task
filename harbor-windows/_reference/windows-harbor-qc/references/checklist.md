# Outside Harbor Windows 质检清单

本清单是 `scripts/run_qc.py` 的判定依据，也是人工复核报告的最小范围。静态检查通过不等于题目通过；动态 Oracle/NOP 门禁、测试公平性和证据闭合必须全部满足。

## 1. 标准目录和职责

每个发现的 Task 根目录必须至少包含：

```text
task.toml
source.json
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

`test.bat`、`run_matrix.ps1`、探针和 fixtures 可以按需存在，但不能被入口调用却不交付。`solution/` 是 Golden 入口，必须存在；不能因为普通 Agent 不应看到它就把组织方题包里的参考解删掉。

职责边界：`instruction.md` 只写参与者可见的行为契约；`environment/` 只准备和恢复真实环境；`tests/` 执行独立客观验证和汇总；`solution/` 提供幂等、可执行参考解。测试、Solution、答案、凭据和 reward 不得通过 workspace、镜像、挂载、Git 历史、缓存或日志泄漏给 Agent。

## 2. 安全解包和身份

ZIP 必须拒绝绝对路径、盘符、`..`、空路径、Windows 保留名、尾随点/空格、ADS 冒号路径、符号链接、大小写冲突、重复成员、路径越界、异常压缩比、过大成员数和过大展开体积。原 ZIP Hash、每个 Task 的文件 Hash、任务目录名、`task.toml` 的 `task_id`、`source.json` 的 `task_id` 和 `rubric.json` 的身份必须一致；版本和镜像必须可追踪，不能用 `latest`。

`source.json` 应记录来源类型、License、Lineage、授权和污染风险。缺少这些字段至少是人工复核警告，不能把来源不明的题目直接纳入正式集。

## 3. 题面、测试和 Windows 价值

- 每个计分 testcase 都能双向追溯到题面/公开契约；不能新增未声明要求或与题面相反的约束。
- 核心断言触发真实生产路径、输入输出、异常、状态、副作用或 Windows 终态；支持独立等价实现。
- 源码正则、关键词、Patch Diff、文件/进程/端口存在、日志文本、编译成功和模型自报只能作辅助证据。
- P2P 与修改范围相关，初始状态必须通过；核心 F2P 必须由目标缺陷导致初始失败，Golden 后通过。
- 真实运行必须使用 Windows Runtime；不能用 Linux Mock、WSL 结果或普通跨平台逻辑冒充 Windows 专项价值。
- `prepare`、`restore`、`cleanup` 可重复执行，清除旧构建、旧结果和系统残留；异步/子进程必须有完成回执或健康哨兵。
- 网络策略、权限、镜像版本、架构、Locale、Shell/Runtime、依赖、CPU/内存和超时必须可复现并可审计。

## 4. 二值评分和 INVALID 门禁

`required_testcases.json` 必须是唯一、稳定的 testcase 集合，且同时包含 `F2P` 和 `P2P`。每项终态只能是 `PASS` 或 `FAIL` 才能进入正式评分。

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

## 7. 一票否决

Windows 反事实价值不足、标准 Harbor 无法加载、Solution 缺失、Golden 不稳定、NOP/P2P/F2P 门禁失败、测试绑定 Golden 私有写法、基础设施故障被记成模型 0、答案/测试/凭据泄漏、环境不可恢复、旧产物污染、来源授权不清、重复/薄题、无法在预算内稳定运行，任一项都不能进入正式集。修复后必须提升版本和 Hash，在新的干净结果目录完整复验。

