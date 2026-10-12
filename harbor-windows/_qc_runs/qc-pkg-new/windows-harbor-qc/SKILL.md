---
name: windows-harbor-qc
description: 质检直接 Harbor Windows 作业目录或 ZIP，执行标准 Task/14 jobs/四模型/Oracle/NOP 门禁，并按 Windows 采购质检手册完成 WIP 94 项、D01–D20、逐 testcase 证据链、Hack 和独立复算审计。用于交付验收；不用于出题、调用模型或自动返修。
---

# Windows Harbor QC

对正式作业包执行完整只读质检。默认不修改题包、不返修、不操作飞书，也不调用模型 API。

先读 [references/standard-layout.md](references/standard-layout.md)、
[references/checklist.md](references/checklist.md) 和
[references/quality-gates.md](references/quality-gates.md)。需要快速确认某项是否应当驳回时，查阅
[references/rule-matrix.md](references/rule-matrix.md)。每次正式质检还必须阅读
[references/procurement-manual-integration.md](references/procurement-manual-integration.md)，并按其中
链接的 2026-09-27 采购质检手册原文完成 WIP 94 项与 D01–D20 审计。然后从 Skill 根目录执行：

```powershell
.\scripts\run_delivery_qc.ps1 `
  -InputPath D:\path\delivery.zip `
  -OutPath D:\path\qc-result
```

首次运行会在结果目录生成 `quality-review-template.json`，且在十项人工证据未提供前最终结论为
`BLOCKED`。填完模板后必须换一个新的空结果目录重新执行：

```powershell
.\scripts\run_delivery_qc.ps1 `
  -InputPath D:\path\delivery.zip `
  -OutPath D:\path\qc-final `
  -QualityReview D:\path\quality-review.json
```

Python 等价入口：

```powershell
python scripts\run_delivery_qc.py --input D:\path\delivery.zip --out D:\path\qc-result
```

总入口按顺序完成以下硬门禁：

1. 安全解压；ZIP 内必须只有一个最外层作业文件夹，且其名称与 ZIP 文件名去掉 `.zip` 后完全一致。该文件夹本身就是 Harbor Task 根目录，必须直接包含 `task.toml`、`instruction.md`、`environment/`、`solution/`、`tests/`、`jobs/`。不接受 `outside_harbor/`、`outside_harbor-assets/` 等 Demo 包装层。
2. 检查 Task 的 `instruction.md + task.toml + environment/ + solution/ + tests/`、所有入口实际引用文件、固定镜像和测试协议。`source.json` 可有可无；存在时必须有效且身份一致。required testcase 少于 5 条失败，5–27 条正常，超过 27 条只提示人工复核。
3. 直接读取 `jobs/` 中 14 个 Harbor job：Qwen 3 次、Opus 3 次、GLM 1 次、Kimi 1 次、Oracle 3 次、NOP 3 次。模型 job 必须含 `agent/model-result.json` 与 `agent/trajectory.jsonl`；所有 job 必须含原始 `result.json`、verifier 结果、reward 和日志。
4. 模型准入先拒绝过易满分题：Qwen 三次和 Opus 三次同时全部 `VALID/1` 时直接失败；8 次规定模型运行全部满分时也必须明确记录为全模型满分失败。其余情况比较三次正式分数总和：`Opus model_score_sum > Qwen model_score_sum` 时通过；两者总分相等时，继续比较逐 testcase 的累计通过数，只有 `Opus testcase_pass_sum > Qwen testcase_pass_sum` 才通过。规定的 8 次模型运行全部 `VALID/0` 时，即使 testcase 累计通过数也未拉开差距，零分平局仍允许通过。Opus 总分低于 Qwen，或总分相等且 Opus testcase 累计通过数没有严格高于 Qwen（且不满足全模型有效零分例外）时失败。GLM/Kimi 不参与主分差，GLM 高于 Opus本身不触发返修，但必须纳入全模型结果分布分析，且所有原始轨迹必须完整有效。
5. 在 Windows Containers 模式下真实调用 Harbor。Oracle 默认独立 3 次且全部 `VALID/1`；NOP 默认独立 3 次且全部 `VALID/0`，每轮 P2P 全 PASS、至少一个核心 F2P FAIL。

每轮 Harbor 参数固定为 `--n-attempts 1 --n-concurrent 1 --max-retries 0`。缺测试、零测试、构建失败、`SKIP/ERROR/NOT_RUN`、解析错误、权限或环境故障必须判为 `INVALID/BLOCKED`，不能生成正式 0 分。不得减少 required 清单、替换原始 jobs、复用旧 Task 轨迹或通过修改输入消除失败。

模型 jobs 必须保留模型/提供商、中文口语化原始提示词、原始响应、候选代码或补丁、`trajectory.jsonl`、`verifier/result.json`、`reward.txt`、逐 testcase 终态、时间和 Task checksum。提示词不得添加“中文口语化提示：”前缀。发现凭据、Solution/测试泄漏、Hash 不一致或缺少原始文件时失败。

以下项目不得单独作为返修理由：Dockerfile 的 `FROM` 未 pin SHA-256 digest；缺少顶层 `evidence/` 或 `metadata/`；`task.toml` 缺 network policy 字段；全部规定模型运行均有效且全 0；泛化的“每模型运行次数不足”；GLM 为 1 而 Opus 为 0。这里的“运行次数不足”豁免不取消标准目录门禁：`jobs/` 少于规定的 14 个原生 Harbor job，仍按目录/证据缺件判定失败。

写不通过原因时只写真实触发的硬门禁，附文件、job 和 testcase 证据。不要把建议项包装成必改项，也不要因为另一个门禁已经失败就追加未经验证的模板化原因。

结果目录必须为空或不存在。最终读取 `report.md` 和 `report.json`；`harbor/` 下保留真实命令、CLI 日志和 job/verifier 原文。Oracle 截图应从 Harbor CLI/控制台原始输出截取。

自动入口完成后，必须按 [references/quality-gates.md](references/quality-gates.md)、
[references/manual-review.md](references/manual-review.md) 和采购手册完成十项人工硬门禁，并提交
结构化 `quality-review.json`。原有五项分别是：Golden/NOP 是否按预期得分；每项评分标准和每个 testcase
是否判分正确；testcase 是否严格对应题面并检查功能；是否存在联网取答案、搜索 Golden、修改
测试/Verifier 等 Hack；是否具备真实 Windows 价值。每项都必须逐项给出 job、轨迹、testcase 或
日志证据。新增五项分别是：范围/版本/公式和资产身份冻结；WIP 94 项完整登记；D01–D20 动态审计；
从 required testcase 独立复算分数；证据、历史与整改复验闭环。缺少任一项时，自动门禁即使全部
通过，最终结论也只能是 `BLOCKED`；任一人工项
失败则最终为 `FAIL`。人工复核不能把自动脚本的 `FAIL/BLOCKED` 改成 `PASS`。

十项人工门禁之外还必须执行全模型区分度硬门禁：分析 Qwen、Opus、GLM、Kimi 的全部规定运行；
Qwen 与 Opus 同时三轮满分或 8 次模型运行全部满分时，题目过易，最终不得通过。

运行时必须分开记录质检项、testcase 观察和运行有效性。环境、依赖、权限、解析、零测试或证据
故障为 `INVALID/BLOCKED` 且可信分数为 `null`，不得按模型 0 分处理。核心测试必须接受等价实现；
每个得分和扣分都要闭合“实际下发要求 → assertion/rubric → 候选 SHA → Windows 实际执行 →
testcase 终态 → 完整轨迹 → 独立复算”。

返修原因必须使用口语化描述：先说明实际发生了什么、为什么影响结果，再说明应怎样修复；技术
路径、job 名和 testcase ID 作为证据附在描述中，不能只堆字段名、Hash 或错误代码。

结论只有：

- `PASS`：直接 Harbor 目录、测试、14 个 jobs、模型准入、Oracle/NOP、WIP 94 项、D01–D20 和人工语义复核全部通过；
- `FAIL`：作业包、测试或模型准入不满足；
- `BLOCKED`：Docker/Harbor/Windows 运行依赖或必要证据不足，无法完成真实质检。

修改题面、环境、solution、tests、required testcase 或评分后，旧模型轨迹全部作废。提升版本和 Hash，在新的空结果目录重跑完整质检。
