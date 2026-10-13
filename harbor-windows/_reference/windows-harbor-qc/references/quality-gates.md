# 甲方五项质量门禁与采购手册五项扩展门禁

前五项直接决定题目和评分是否可信，后五项保证 2026-09-27 Windows 采购质检手册得到完整执行。
十项都不是建议项，也不能因为目录完整、Harbor 能运行、
最终 reward 看起来正常或模型分差达标而忽略。每项都必须给出可定位证据并写成
`PASS/FAIL/BLOCKED`；任何一项不是 `PASS`，整题都不能最终通过。

## 1. Golden 与 NOP 的得分符合预期

口语化理解：标准答案确实应该拿满分，什么都不做确实应该拿不到分，而且两边的每个
testcase 都要呈现合理结果。

必须核对：

- 3 次 Oracle 都是 `VALID/1`，required testcase 全部 `PASS`；
- 3 次 NOP 都是 `VALID/0`，P2P 全部 `PASS`，至少一个核心 F2P 因目标功能未实现而 `FAIL`；
- Oracle/NOP 的失败或通过来自真实功能行为，不能来自环境、权限、依赖、解析、零测试或旧产物；
- 逐个比较 Oracle 与 NOP 的 testcase 终态，解释为什么该项应得分或不应得分。

标准解不通过、空跑也通过、空跑因基础设施故障得 0，或结果无法解释，均为 `FAIL`。

## 2. 每项评分标准和每个 testcase 判分正确

口语化理解：不能只看总分。要把评分规则、实际执行结果、模型轨迹和每个 testcase 对起来，
确认该给的分给了、不该给的分没有给。

必须逐项建立至少包含以下内容的证据表：

```text
评分项 / testcase ID
题面依据
实际执行行为与终态
对应轨迹或日志路径
预期是否得分
实际是否得分
复核结论
```

需要同时排除：

- 功能没有完成却被判 `PASS` 的漏判；
- 功能已经完成却被判 `FAIL` 的误杀；
- testcase 已通过，但聚合器、reward 或评分项没有正确计分；
- testcase 已失败，但正式分数仍错误地给成 1；
- 评分项重复计算、漏算，或者评分标准本身与题面冲突。

只抽查部分 testcase、只看总分或只看 `reward.txt` 都不足以通过本项。

## 3. Testcase 严格对应题面并检查功能

口语化理解：测试应该检查“程序做对了没有”，不能检查“代码是不是照标准答案那样写”。

必须完成题面与 testcase 的双向映射：

- 题面每项公开要求至少有一个 required testcase 覆盖；
- 每个 required testcase 都能回到题面、公开接口或公开约束；
- 核心断言走真实生产路径，检查输入、输出、状态、副作用或 Windows 终态；
- 测试接受独立等价实现，不绑定 Golden 的私有函数名、局部变量、文件布局、固定代码片段、
  调用顺序或某一种算法；
- 源码正则、关键词、Diff、文件存在、日志文本和“能编译”只能作辅助证据，不能代替功能验证。

存在题外隐藏要求、测试照着 Golden 私有实现写、或正确等价实现会被误杀时，本项 `FAIL`。

## 4. 没有 Hack、答案泄漏或绕过行为

口语化理解：模型必须自己分析和修改代码，不能联网抄答案、从本地找到标准答案，或者修改
测试和评分器骗分。

必须逐份检查 8 个模型 job 的完整输入、响应、工具调用、命令、网络行为、workspace 和候选代码，
重点查找：

- `websearch`、浏览器搜索、外部 HTTP 下载、`curl/wget/Invoke-WebRequest` 等取答案行为；
- `git pull/fetch/clone`、包管理器拉取题目相关源码、访问上游未冻结内容；
- 在目录、镜像、挂载、Git 历史、缓存或日志中搜索并读取 `solution/`、Golden patch、隐藏测试、
  reward、预期输出或其他标准答案；
- 修改 tests、Verifier、required testcase、reward 或基础设施来制造通过；
- 复用旧二进制、旧 workspace、旧结果，硬编码 testcase 答案或根据测试名称定向返回。

网络访问本身只有在题面明确需要且不能获得答案时才可能允许，并必须有范围与证据。发现真实绕过，
或轨迹不完整到无法排除绕过时，分别判 `FAIL` 或 `BLOCKED`。

## 5. 题目具备真实 Windows 价值

口语化理解：这道题的难点必须来自 Windows 本身，不能只是普通跨平台题换成 PowerShell 或放进
Windows 容器。

复核时写出 Windows 反事实：如果换到 Linux 或普通跨平台 Runtime，哪个核心行为会消失或发生
实质变化。可接受的价值通常来自注册表、NTFS、ACL、重解析点、文件锁、命名对象、服务、DPAPI、
Win32 API、Windows 路径/命令行规则、进程或安全模型等。

只有启动脚本使用 PowerShell、路径里出现盘符、镜像是 Windows，不能单独证明 Windows 价值。
若核心功能可原样移到 Linux，测试也不依赖真实 Windows 语义，本项 `FAIL`。

## 与人工门禁并行的全模型区分度硬门禁

必须分析 Qwen、Opus、GLM、Kimi 的全部规定运行，而不是只看一轮或只看汇总截图。核心判据是 Opus
的三次 `model_score_sum` 是否严格高于 Qwen；两者相等时——**包括 Qwen 与 Opus 同时三轮
`VALID/1`、正式分已顶格的过易满分情形**——必须由相同 required testcase 集合上的
`testcase_pass_sum` 严格打破平局，否则 `FAIL`。`qwen_opus_full_score` 与 `all_models_full_score`
必须记录进报告，用于说明判分颗粒度是否足以区分主模型，但不再单独否决。GLM/Kimi 不参与主分差，
但必须用于检查整体结果分布、异常和证据完整性。本自动硬门禁失败时，十项人工门禁不能把结论升级为
`PASS`。

## 6. 范围、版本、公式和资产身份已冻结

必须登记采购来源、批次、task ID/version、ZIP 与 Task Hash、base commit、实际 instruction、环境、
Solution、测试树、required testcase、评分公式、镜像、工具链和模型运行批次。历史结果、被替代
rerun 和本次结果分开保存。不同版本、测试树或公式不能合并统计；无法证明当前运行使用哪套资产时
判 `BLOCKED`。

## 7. WIP 94 项已逐项审计

必须提交 FC 13 项、任务有效性 18 项、可解性 7 项、完整性 6 项、环境 14 项、验证器 36 项的
完整矩阵。每项填写 `PASS/FAIL/FLAG/BLOCKED/N/A`、证据、影响和处理；`N/A` 必须说明依据。
缺行、用静态存在性冒充动态验证、或无证据写 PASS 时判 `BLOCKED`；确认存在适用项缺陷时判
`FAIL`。Windows 适配与 WIP 原口径冲突时双列结论，不得静默豁免。

## 8. D01–D20 动态审计已完成

按采购手册逐项覆盖 Golden/no-change、稳定性、要求实际下发、双向映射、逐项判分、等价实现、
故障反例、Mock 保真、Windows 环境和真实终态、构建与产物身份、异常与日志、Hack/泄露、分数
复算、失败归因和批次交付。每项至少有一项可定位原始证据；未执行或只有报告摘要时判
`BLOCKED`。

## 9. 正式分数已经独立复算

必须直接使用 required testcase 终态、rubric 条件、前置门禁和冻结公式计算分数，并对照
verifier report、reward 和平台总分。空清单、重复/缺失 ID、SKIP/ERROR/NOT_RUN、解析/环境错误、
候选可写 reward 都不能产生正式分。复算与正式结果不一致时判 `FAIL`；必要材料缺失时判
`BLOCKED`。

## 10. 证据、历史和整改复验闭环

原始日志按精确字节保存并有 SHA256；派生、转码和脱敏文件另有身份。每个问题记录现象、直接
证据、影响、根因、修改对象、复验方法、新版本和剩余边界。题面、环境、Solution、Tests、
required testcase 或评分发生变化后，旧模型轨迹必须作废，并在新干净环境完整复验。历史“已修”
不能代替当前资产实测。

## 证据和结论

每项至少提供一个具体文件、testcase ID、job 目录或 CLI 日志路径。采购手册扩展项应引用
`wip94-review`、`dynamic-d01-d20-review`、`score-recompute` 等逐项产物。结论规则：

- 十项全部 `PASS`：质量门禁通过；
- 任一项 `FAIL`：整题 `FAIL`；
- 任一项证据不足、轨迹缺失或无法复核：整题 `BLOCKED`；
- 自动目录、模型、Oracle/NOP 检查已经失败时，质量复核不能把结果升级为通过。

返修原因使用口语化描述，先说实际现象和影响，再说需要补什么。可以附带文件名、job 和 testcase
作为证据，但不要只堆字段名、Hash 或脚本报错。

提交给入口的 `quality-review.json` 使用以下结构，十个键缺一不可：

```json
{
  "golden_nop_expected": {
    "status": "PASS",
    "evidence": ["harbor/oracle-1/result.json；testcase f2p-core 全 PASS"],
    "notes": "三次 Oracle 和三次 NOP 已逐 testcase 对照"
  },
  "rubric_case_correctness": {
    "status": "PASS",
    "evidence": ["case-review.md"],
    "notes": "所有评分项已与轨迹、终态和 reward 对齐"
  },
  "testcase_contract_fairness": {
    "status": "PASS",
    "evidence": ["task-testcase-mapping.md"],
    "notes": "测试检查行为并接受等价实现"
  },
  "hack_free": {
    "status": "PASS",
    "evidence": ["jobs-trace-review.md"],
    "notes": "8 个模型 job 未发现取答案或绕过行为"
  },
  "windows_value": {
    "status": "PASS",
    "evidence": ["windows-counterfactual.md"],
    "notes": "核心行为依赖真实 Windows 语义"
  },
  "scope_version_identity": {
    "status": "PASS",
    "evidence": ["scope-and-identity.json"],
    "notes": "版本、Hash、公式、镜像和批次已冻结"
  },
  "wip94_complete": {
    "status": "PASS",
    "evidence": ["wip94-review.md"],
    "notes": "94 项完整，N/A 均有适用性依据"
  },
  "dynamic_d01_d20_complete": {
    "status": "PASS",
    "evidence": ["dynamic-d01-d20-review.md"],
    "notes": "D01-D20 已完成并引用原始证据"
  },
  "independent_score_recompute": {
    "status": "PASS",
    "evidence": ["score-recompute.json"],
    "notes": "正式分与逐 testcase 独立复算一致"
  },
  "evidence_retest_integrity": {
    "status": "PASS",
    "evidence": ["remediation-retest.md", "evidence-sha256.txt"],
    "notes": "历史、原始证据、版本变更和复验闭环"
  }
}
```
