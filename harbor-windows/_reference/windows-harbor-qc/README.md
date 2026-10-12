# windows-harbor-qc

可直接分发的 Harbor Windows 作业质检 Skill。它检查直接 Harbor Task 根目录和 14 个原始 job，并在本地 Windows Docker 中真实执行 Oracle/NOP。它不会调用模型、修复题包或修改飞书。

规则基线：2026-10-12。

判定口径以 `references/rule-matrix.md` 为快速索引，以 `references/checklist.md` 为完整规则。不得使用旧 Demo 目录规则覆盖本包内的直接 Harbor 标准。

## 依赖

- Windows 主机；
- Docker 已切换到 Windows Containers，`docker info --format "{{.OSType}}"` 返回 `windows`；
- 可执行的 Harbor CLI；
- Python 3.11 或更高版本；
- 题包声明的 Windows 镜像、离线依赖、权限和资源。

## 一键质检

在解压后的 Skill 根目录运行：

```powershell
.\scripts\run_delivery_qc.ps1 `
  -InputPath D:\deliveries\task.zip `
  -OutPath D:\qc\task-result `
  -QualityReview D:\qc\task-quality-review.json
```

输出目录必须为空或不存在。默认 Oracle/NOP 各独立运行 3 次；严格稳定性复验可加 `-Attempts 6`。需要强制重建镜像时加 `-ForceBuild`。首次运行可以不传 `-QualityReview`，入口会生成 `quality-review-template.json`，但最终结论会保持 `BLOCKED`；逐项补全证据后，在新的空结果目录重新运行并传入该文件，十项全部 `PASS` 才能得到最终 `PASS`。

正式交付内应包含：

```text
<压缩包文件名去掉 .zip>/
  task.toml
  instruction.md
  environment/
  solution/
  tests/
  jobs/
    config.json / lock.json / result.json / job.log
    <Qwen 三个 Harbor job>
    <Opus 三个 Harbor job>
    <GLM 一个 Harbor job>
    <Kimi 一个 Harbor job>
    <Oracle 三个 Harbor job>
    <NOP 三个 Harbor job>
```

例如 `windows-demo-v1.zip` 的唯一最外层文件夹必须是 `windows-demo-v1/`；名称不一致、
根部散放文件或多个顶层目录均不通过。

不使用 Demo 的 `outside_harbor/`、`outside_harbor-assets/`，也不要求或接受
`model-evidence.json` 作为原始 jobs 的替代品。校验器直接读取每个 Harbor job 的
`result.json`、`agent/trajectory.jsonl`、模型来源、verifier 结果、reward 和 Task checksum。

## 结果

- `report.md`：最终人读结论；
- `report.json`：完整结构化结论；
- `delivery-layout.json`：直接 Harbor Task 目录和身份；
- `model-gate.json`：3/3/1/1 模型运行和准入结果；先比较 Opus/Qwen 三次正式分数总和，总分相等时允许由更高的 Opus testcase 累计通过数打破平局；规定的 8 次模型运行全部 `VALID/0` 时仍允许零分平局；
- `model-jobs.json`：14 个 Harbor job 的分类、文件和结果完整性；
- `harbor/`：真实 Oracle/NOP 报告、命令、原始 CLI 日志和 job 证据。

退出码：`0=PASS`、`1=FAIL`、`2=BLOCKED`。

required testcase 少于 5 条失败，5–27 条正常，超过 27 条只产生人工范围复核警告。Dockerfile `FROM` 未 pin digest、缺少 `evidence/` 或 `metadata/`、`task.toml` 缺 network policy、GLM 1 而 Opus 0，都不能单独触发返修。泛化的“模型运行次数不足”也不单独使用；若 `jobs/` 缺少固定 14 个原生 Harbor job，则按标准目录和原始证据缺件失败。

脚本会额外要求 `quality-review.json`，用于记录十项人工质量硬门禁：原有甲方五项
（Golden/NOP 预期、逐评分项和逐 testcase 判分、题面与功能测试一致性、Hack/答案泄漏、
Windows 价值），以及采购手册新增的范围与身份冻结、WIP 94 项、D01–D20、独立复算、证据与
整改复验闭环。模板见 `quality-review-template.json`、`references/quality-gates.md` 和
`references/procurement-manual-integration.md`。自动门禁全部通过但未提供十项证据时，最终结论
为 `BLOCKED`。人工复核只能降级自动结论，不能把 `FAIL/BLOCKED` 升级为通过。

模型区分度是与十项人工复核并行的自动硬门禁。脚本分析 Qwen×3、Opus×3、GLM×1、Kimi×1
全部结果；Qwen 与 Opus 同时三轮满分时直接失败，8 次运行全部满分时明确标记为全模型满分题并
拒收。未触发满分拒绝时，继续应用 Opus/Qwen 总分与 testcase 累计通过数规则。

不通过原因必须基于本次真实检查证据，不得复制其他题目的返修模板。每条原因应定位到 ZIP 成员、Task 文件、Harbor job、verifier 报告或 testcase；建议项与硬门禁分开写。

## 分发边界

ZIP 内不包含 API key、飞书 token、`.env`、本机缓存或真实作业证据。Skill 只用 Python 标准库和本机 Docker/Harbor，可复制到其他 Windows 主机使用。
