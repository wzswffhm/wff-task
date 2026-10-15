---
name: windows-harbor-qc
description: 质检直接 Harbor Windows 作业目录或 ZIP，检查镜像远端交付与目标环境兼容、标准 Task/jobs/模型/Oracle/NOP 门禁，并按 Windows 采购质检手册完成 WIP 94 项、D01–D20、逐 testcase 证据链、Hack 和独立复算审计。用于交付验收；不用于调用模型或自动返修。
---

# Windows Harbor QC

对正式作业包执行完整只读质检。默认不修改题包、不返修、不操作飞书，也不调用模型 API。

先读 [references/standard-layout.md](references/standard-layout.md)、
[references/checklist.md](references/checklist.md) 和
[references/quality-gates.md](references/quality-gates.md)。需要快速确认某项是否应当驳回时，查阅
[references/rule-matrix.md](references/rule-matrix.md)。每次正式质检还必须阅读
[references/procurement-manual-integration.md](references/procurement-manual-integration.md)，并按其中
链接的 2026-09-27 采购质检手册原文完成 WIP 94 项与 D01–D20 审计。还必须阅读
[references/image-delivery-gate.md](references/image-delivery-gate.md)，核实镜像远端拉取、甲方权限、
目标环境兼容、新容器启动和同镜像 Harbor 执行；本地缓存或本地构建成功不能代替交付证明。
还必须阅读 [references/current-project-policy.md](references/current-project-policy.md)。当前项目
要求镜像不早于 2019、优先 2025，Nano Server 和 Server Core 都禁止；任务实际使用工具必须在
Dockerfile 可复现配置并在成品容器验证。还必须阅读
[references/nested-virtualization-gate.md](references/nested-virtualization-gate.md)，实际使用嵌套虚拟化
并保留外层 VM、扩展暴露、内层启动和当前 jobs 的原始证据。六项简化检查全部达标，并继续完成其余完整质检门禁。
然后从 Skill 根目录执行：

```powershell
.\scripts\run_delivery_qc.ps1 `
  -InputPath D:\path\delivery.zip `
  -OutPath D:\path\qc-result
```

首次运行会在结果目录生成 `quality-review-template.json`，且在十四项人工证据未提供前最终结论为
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
4. 主模型必须具备正式分数区分度：同一冻结 Task 的 Qwen、Opus 各三轮全部 VALID，必须满足
   `Qwen model_score_sum < Opus model_score_sum`。正式总分相等时，即使 Opus testcase 累计通过更多
   也不能通过；全零平局和双方全满分均失败。testcase 仍逐项分析，但不用于挽救平局。GLM/Kimi
   不参与主分差，保留本次用户授权的模型范围和完整原始证据要求。此规则替代旧平分二级判据和全零例外。
5. 在 Windows Containers 模式下真实调用 Harbor。Oracle 默认独立 3 次且全部 `VALID/1`；NOP 默认独立 3 次且全部 `VALID/0`，每轮 P2P 全 PASS、至少一个核心 F2P FAIL。
6. 镜像交付、版本/完整系统、工具和实际嵌套虚拟化门禁：填入 `quality-review.json.image_delivery`、
   `windows_image_policy`、`toolchain_in_image`、`nested_virtualization` 和实际原始证据。缺少此项或证据不足，
   自动检查即使全部通过也只能为 `BLOCKED`；确认交付配置/目标环境缺陷则为 `FAIL`。短名不能直接
   判定未发布，完整仓库地址不能直接判定可拉取，质检机网络/权限故障不能当成模型 0 分。

每轮 Harbor 参数固定为 `--n-attempts 1 --n-concurrent 1 --max-retries 0`。缺测试、零测试、构建失败、`SKIP/ERROR/NOT_RUN`、解析错误、权限或环境故障必须判为 `INVALID/BLOCKED`，不能生成正式 0 分。不得减少 required 清单、替换原始 jobs、复用旧 Task 轨迹或通过修改输入消除失败。

模型 jobs 必须保留模型/提供商、中文口语化原始提示词、原始响应、候选代码或补丁、`trajectory.jsonl`、`verifier/result.json`、`reward.txt`、逐 testcase 终态、时间和 Task checksum。提示词不得添加“中文口语化提示：”前缀。发现凭据、Solution/测试泄漏、Hash 不一致或缺少原始文件时失败。

以下项目不得单独作为返修理由：Dockerfile 的 `FROM` 未 pin SHA-256 digest；缺少顶层 `evidence/` 或 `metadata/`；`task.toml` 缺 network policy 字段；泛化的“每模型运行次数不足”；GLM 为 1 而 Opus 为 0。这里的“运行次数不足”豁免不取消标准目录门禁：`jobs/` 少于规定的 14 个原生 Harbor job，仍按目录/证据缺件判定失败。

写不通过原因时只写真实触发的硬门禁，附文件、job 和 testcase 证据。不要把建议项包装成必改项，也不要因为另一个门禁已经失败就追加未经验证的模板化原因。

结果目录必须为空或不存在。最终读取 `report.md` 和 `report.json`；`harbor/` 下保留真实命令、CLI 日志和 job/verifier 原文。Oracle 截图应从 Harbor CLI/控制台原始输出截取。

自动入口完成后，必须按 [references/quality-gates.md](references/quality-gates.md)、
[references/manual-review.md](references/manual-review.md) 和采购手册完成十四项人工硬门禁，并提交
结构化 `quality-review.json`。原有五项分别是：Golden/NOP 是否按预期得分；每项评分标准和每个 testcase
是否判分正确；testcase 是否严格对应题面并检查功能；是否存在联网取答案、搜索 Golden、修改
测试/Verifier 等 Hack；是否具备真实 Windows 价值。每项都必须逐项给出 job、轨迹、testcase 或
日志证据。新增五项分别是：范围/版本/公式和资产身份冻结；WIP 94 项完整登记；D01–D20 动态审计；
从 required testcase 独立复算分数；证据、历史与整改复验闭环。第十一项为镜像远端交付与甲方目标
环境验证，第十二项为完整系统与镜像最低版本，第十三项为 Dockerfile 工具配置和成品功能，
第十四项为实际嵌套虚拟化拓扑与运行证据。不改变 WIP 94 项的原编号和数量。缺少任一项时，自动门禁即使全部
通过，最终结论也只能是 `BLOCKED`；任一人工项
失败则最终为 `FAIL`。人工复核不能把自动脚本的 `FAIL/BLOCKED` 改成 `PASS`。

十四项人工门禁之外还必须执行全模型区分度硬门禁：分析 Qwen、Opus、GLM、Kimi 的全部规定运行；
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
