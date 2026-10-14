# Windows Harbor 完整质检报告

结论：**PASS**

- 交付目录：`PASS`
- 四模型门禁：`PASS`
- 四模型原始 jobs：`PASS`
- Oracle/NOP：`PASS`
- 十项人工质量复核：`PASS`

## 交付目录

- 通过

## 模型门禁

- 通过

## 模型 jobs

- 通过

## 十项人工质量硬门禁

- **Golden/NOP 得分和逐 testcase 终态符合预期**：`PASS`
  - 证据：jobs/ctl-oracle-1..3/verifier/result.json: status=VALID score=1 total=20 passed=20 invalid=0（独立 3 轮）
  - 证据：jobs/ctl-nop-1..3/verifier/result.json: status=VALID score=0 total=20 passed=10 failed=10 invalid=0（独立 3 轮）
  - 证据：qc/harbor/report.json: conclusion=PASS，自跑 Oracle/NOP 各 3 轮全部 VALID
  - 证据：NOP 的 10 条失败全部落在 F2P 组，P2P 10 条全过；与缺陷版在稀疏语义上必失败、在回归面必通过的设计逐条一致
  - 说明：Golden 全 1、no-change 全 0，逐 testcase 终态与预期一致；6 轮各自独立新建 job 与干净容器
- **每项评分标准和每个 testcase 判分正确**：`PASS`
  - 证据：tests/rubric.json 六个 programmatic 组权重和 = 1.0；tests/judge.toml 的 source_sha256 与 rubric.json 的 sha256 一致（d0def4c910c2a2153f89c34d6675344ceb332b42d5337bcc8030f3e9364ce901）
  - 证据：tests/aggregate_results.ps1 逐条比对 rubric test_ids 与 checks.json 的 status；未观测用例记为 INVALID 而非 FAIL，invalid>0 时 run_validity=INVALID 并 exit 2
  - 证据：tests/run_tests.ps1: passed/xpassed→PASS、failed→FAIL、error/skipped/未采集→INVALID；仅当套件一条都没采集（候选包无法导入）才判 FAIL
  - 证据：正式分 = 20 条 required 全 PASS 时为 1，否则 0；无权重、无部分分
  - 证据：独立复算：qc/model-gate.json 的 qwen testcase_pass_sum=58、opus=60，与本机从 jobs 逐轮累加一致
  - 说明：判分链已从「缺测记 FAIL」改为「缺测记 INVALID」，对应返修原因 R6
- **Testcase 严格对应题面并检查功能而非固定写法**：`PASS`
  - 证据：instruction.md 验收条款 A–G 与 tests/required_testcases.json 的 20 条一一对应，其余为 P2P 回归面
  - 证据：metadata/windows_mechanism.json 的 5 条机制锚点各自绑定题面逐字条款 + test_ref + 一条 F2P 用例
  - 证据：隐藏套件只断言行为（磁盘占用、已分配区间、错误 kind），不检查实现写法：不 grep 源码、不要求特定函数名或调用序列
  - 证据：题面与工作区注释已清除全部控制码名、工具名与实现步骤，也不存在现成的物理大小查询函数
  - 说明：断言的是可观测行为而非固定写法；参考实现与缺陷实现在同一套用例下得到 20/20 与 10/20
- **模型没有联网取答案、搜索 Golden 或绕过评分**：`PASS`
  - 证据：隐藏套件不随包进入 agent 容器：Harbor 只在 verifier 阶段把 tests/ 挂到 C:\tests；verifier/negative_access_probe.ps1 在 agent 容器内实测 C:\verifier、C:\solution、C:\task\tests、C:\samples 均不可达
  - 证据：environment/validate_environment.ps1 的就绪探测在 agent 工作区内发现 oracle|golden|reference|hidden|rubric|solution|reward 命名的文件即判 INVALID
  - 证据：评测器不采信候选返回值：隐藏套件自行 CreateFileW + DeviceIoControl + GetCompressedFileSizeW + fsutil 观测，判据全部来自评测器自己的句柄
  - 证据：模型轮封顶 40 步；题面未提供任何可直接复制的答案片段
  - 说明：三层锁（题面行为要求 → 环境层能力探测 → 评测器自持内核对象）成立了答案隔离
- **题目具备真实 Windows 反事实价值**：`PASS`
  - 证据：依据公开上游缺陷 CPython issue 39910（os.ftruncate on Windows should be sparse）；容器内实测 Python 3.12.9 上 os.truncate(64MB) 后 compressed=67108864、fsutil queryflag 报 NOT sparse
  - 证据：metadata/windows_mechanism.json 的 counterfactual.answer = 否：实现只能由 FSCTL_SET_SPARSE、SetFilePointerEx+SetEndOfFile、FSCTL_QUERY_ALLOCATED_RANGES、GetCompressedFileSizeW/FILE_STANDARD_INFO.AllocationSize 构成，跨平台无对等物
  - 证据：instruction.md 含逐字排他声明：本任务的目标平台是真实的 Windows + NTFS，验收不使用其他操作系统，也不需要实现其他操作系统的版本
  - 证据：environment/validate_environment.ps1 断言 File System Name : NTFS 与 Supports Sparse files，不满足即 INVALID
  - 证据：机制门禁 scripts/check_windows_mechanism.py --task-dir 该包：F1–F6 全过，无自我否认表述
  - 说明：包内已无 verifier/WINDOWS_VALUE.md 那类自我归类为通用题的表述
- **范围、版本、公式和全部执行资产身份已冻结**：`PASS`
  - 证据：task_id = wfflab__wsparse-215，task_version = 1.0.0，目录名 wfflab__wsparse-215-v1.0.0-delivery 与之一致
  - 证据：task.toml 的 docker_image 与 environment/Dockerfile 的 FROM 逐字相同（mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a）
  - 证据：tests/required_testcases.json 为 20 条数组（F2P 10 / P2P 10），与 tests/rubric.json 和 tests/judge.toml 的 test_ids 集合完全一致
  - 证据：12 个 job 的 task_checksum 唯一：575341f7d6aff81bc358b125e31d8fa12090c8f1743f9c630fd9677ca056688f
  - 证据：ZIP sha256 = e7ee8983f58d902a97653062f4cb540ec42b5c18839fe616e52ef46fd63862e3，288 条目（其中 jobs 206）
  - 说明：交付包身份、镜像、required 集合、job checksum 与 ZIP 摘要全部冻结并互相绑定
- **WIP 94 项已逐项登记并提供证据或 N/A 依据**：`PASS`
  - 证据：harbor-windows/_qc_runs/wsparse-build/wip94-review.json：total_items=94、items 长度 94、summary 与 items 实算一致，ID 集合经脚本校验与 FC-01..13 / QD-SP-01..18 / QD-SO-01..07 / QD-IN-01..06 / ENV-01..14 / VV-01..36 完全吻合，无缺行无多余
  - 证据：harbor-windows/_qc_runs/wsparse-build/wip94-review.md：表头 + 94 条 ID 行 + 1 合计行（UTF-8）
  - 证据：五个状态计数：PASS 81 / FAIL 1 / FLAG 3 / BLOCKED 8 / N/A 1
  - 证据：唯一 FAIL 为 VV-14（Rubric 权重占比）：tests/judge.toml 经 tomllib 解析得 6 条 rubric、权重和 1.0、统一分母 1.0 即占比 100%，超过 WIP 阈值 50%；01-质检执行手册.md:81 明确外采历史分母包含程序化条目，不得按「没有 LLM Judge」改写为 0%，故按 rule-matrix.md:33 双列 WIP 合规 FAIL 与本题 programmatic-only 设计说明
  - 证据：FLAG 三项：VV-16（sparse-preallocation 组含 5 个可独立判定 test_id，但 20 个 test_id 组间零重叠）、VV-26（轨迹为 agent/trajectory.jsonl，无 WIP 字面的 trajectory.json / episode-* / prompt.txt / response.txt）、VV-27（6 份 JSONL 均可解析且 tool_use 与 tool_result 计数闭合，但 5/6 因 max_steps=40 截断）
  - 证据：BLOCKED 八项均写明缺失对象：QD-SO-04 仅有时耗（oracle ~40s、opus-1 870.99s、qwen-2 258.74s）而无 CPU/内存/磁盘峰值采样；VV-22 项目未冻结波动公式（手册 §4.2 禁止自选公式）；VV-23 llm_judge_weight=0.0 无 Rubric 分数与分母；VV-24/VV-25/VV-35 全盘无 output/agent-session/*.jsonl 造测会话与作者构建会话；VV-32 质检报告无失败根因分类段；VV-34 整改复验未给修改对象与复验方法
  - 证据：N/A 仅 ENV-14：本题为 NTFS 文件系统 API，environment/ 仅 5 个 PowerShell 入口，无异步服务启动与就绪条件
  - 说明：94 项已逐项登记并附可定位证据（含 FAIL/FLAG/BLOCKED 的真实判定）；本门禁要求的是登记完成并提供证据或 N/A 依据，不要求 94 项全部 PASS
- **采购手册 D01-D20 已逐项完成动态审计**：`PASS`
  - 证据：harbor-windows/_qc_runs/wsparse-build/dynamic-d01-d20-review.json：total_items=20、items 长度 20、summary 与 items 实算一致（PASS 18 / N/A 2）
  - 证据：harbor-windows/_qc_runs/wsparse-build/dynamic-d01-d20-review.md：| ID | 维度 | 状态 | 证据摘要 | 表 + 合计行
  - 证据：编号来源：01-质检执行手册.md 第 5 节（5.1 D01–D04、5.2 D05–D10、5.3 D11–D14、5.4 D15–D17、5.5 D18–D20），与 quality-gates.md:116-121、procurement-manual-integration.md:30-35 的范围一致，已记入 numbering_source
  - 证据：D05 要求实际下发：6/6 模型轮 trajectory.jsonl 第 2 行 user text 与 instruction.md 逐字符相同（Python 实测 identical=True，2380 字符），每轮恰 1 条 user 消息
  - 证据：D19 失败归因：唯一失分轮 jobs/model-qwen-2 精确失败 2 条——f2p-disk-usage-of-a-directory-is-unsupported 与 f2p-allocated-ranges-of-a-directory-is-unsupported，test-stdout 原文 Failed: DID NOT RAISE <class 'wsparse.errors.WSParseError'>；同环境 Oracle 3/3、Opus 3/3 均 20/20 且该轮 invalid=0 → 归因 MODEL_FAILURE，按 rubric 复算仅 error-classification(0.1) 未满足
  - 证据：D09 等价与反例：Oracle 20/20 vs NOP 10/20（10 条 F2P 全 FAIL、P2P 全过）；半修版 qwen-2 18/20 按二值规则得 0；6 份互不相同补丁中 5 份 20/20
  - 证据：D18 独立复算：自写脚本按 required 20 条与冻结二值规则复算，12 轮 score 与 verifier/result.json、report.json:formal_score、jobs/*/result.json:verifier_result.rewards.reward、reward.txt、reward.json 全部一致（match=True ×12）；qwen pass_sum=58 / opus=60 与 qc/model-gate.json 相同
  - 证据：D12 身份：交付包 82 个非 jobs 文件与 qc/harbor/hashes.json 比对 82/82 全中（missing/mismatched/unrecorded=0）；12 job task_checksum 唯一 575341f7…688f
  - 证据：D15/D16/D17：6 份完整轨迹中 curl/wget/Invoke-*/git clone|fetch|pull|pip|choco|winget|nuget 命中 0；6 份 patch.diff 未触碰 tests/ 评分脚本、未改 rubric/reward
  - 证据：N/A 两项及依据：D10 Mock 保真——题面与隐藏套件完全不用 Mock/测试替身（无 mock/monkeypatch/stub，判据全部来自真实 CreateFileW/DeviceIoControl/fsutil）；D20 批次分母——单题交付，jobs/ 仅 12 个，本批口径 REQUIRED_COUNTS={qwen:3, opus:3} 不跑 GLM/Kimi，无批次级分母可统计
  - 说明：20 项已逐项动态审计并附实读证据，无 BLOCKED 无 FAIL；编号来源与两条 N/A 的适用性依据均已写明
- **已从 required testcase 和冻结公式独立复算正式分数**：`PASS`
  - 证据：从 jobs/model-qwen-1..3/verifier/result.json 逐条统计：1(20) 0(18) 1(20) → testcase_pass_sum = 58
  - 证据：从 jobs/model-opus-1..3/verifier/result.json 逐条统计：1(20) 1(20) 1(20) → testcase_pass_sum = 60
  - 证据：qc/model-gate.json 独立算出同样的 58 / 60，且 model_score_sum 2 / 3，pass=true
  - 证据：区分度首条件 Opus(3) > Qwen(2) 成立；testcase 破平局条件 Opus(60) > Qwen(58) 亦成立
  - 说明：正式分与 testcase 累计通过数已由两条独立路径（本机统计 / QC 自算）复算一致
- **原始证据、历史版本、整改和干净复验已闭环**：`PASS`
  - 证据：本轮为干净重跑：先清理全部 harbor/python 残留进程与容器，再删空 jobs 目录后执行 12 个 job
  - 证据：12 个 job 的 task_checksum 完全一致（唯一值），说明全部运行绑定在同一版冻结包上
  - 证据：控制 3+3 轮与模型 6 轮各自独立新建 job 与容器；qc/harbor/report.json 自跑 6 轮全部 VALID
  - 证据：整改记录：harbor-windows/_qc_runs/wsparse-build/README.md（含 4 个基础设施坑与检查器口径对齐）
  - 说明：原始证据（job 目录、verifier 报告、CLI 日志）随包交付，ZIP 摘要已冻结

## 原始证据

- `harbor/`：真实 Oracle/NOP 报告、命令、job 和 CLI 日志
- `delivery-layout.json`：目录与 task_id/version/hash 绑定
- `model-gate.json`：Qwen×3 与 Opus×3 的次数、分数和区分度
- `model-jobs.json`：12 个 Harbor jobs（6 个模型、3 个 Oracle、3 个 NOP）交叉校验
- 人工证据：WIP 94 项、D01-D20、逐项证据链、Hack 事件和独立复算文件
