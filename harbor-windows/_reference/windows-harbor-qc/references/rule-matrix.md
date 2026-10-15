# Windows Harbor 最新质检规则矩阵

本表用于快速判定，完整执行细节见 `checklist.md`。发生规则冲突时，以本表和直接 Harbor
标准目录为准，不再使用旧 Demo 包装格式。新增口径见 [current-project-policy.md](current-project-policy.md)。

## 必须失败

| 检查项 | 判定 |
|---|---|
| ZIP 唯一根目录名称与 ZIP 文件名去掉 `.zip` 后不完全一致 | `FAIL` |
| 根目录未直接包含 `task.toml`、`instruction.md`、`environment/`、`solution/`、`tests/`、`jobs/` | `FAIL` |
| 使用 `outside_harbor/`、`outside_harbor-assets/` 等旧 Demo 包装层 | `FAIL` |
| `task.toml` 的 instruction/workspace/setup/test/golden 入口缺失、越界或指向未交付文件 | `FAIL` |
| `solution/` 缺少可由标准 OracleAgent 调用的 `solve.ps1` 或 `solve.bat` | `FAIL` |
| 测试入口引用未交付文件，或 required testcase 少于 5 条 | `FAIL` |
| `jobs/` 不是 14 个原生 Harbor job：Qwen×3、Opus×3、GLM×1、Kimi×1、Oracle×3、NOP×3 | `FAIL` |
| 任一 job 缺少规定的原始 config/lock/result/log/verifier/reward/trajectory 文件 | `FAIL` |
| 任一模型运行不是 `VALID`、不是二值 0/1、testcase 集合不完整或 Task Hash 不一致 | `FAIL` |
| Qwen 三次与 Opus 三次同时全部 `VALID/1`；8 次规定模型运行全部满分时须同时标记全模型满分 | `FAIL`，题目过易 |
| Qwen 正式分数总和不严格低于 Opus（包含全零、非零平分和 Opus testcase 更多的平分） | `FAIL` |
| Oracle 任一轮不是 `VALID/1` 或 required testcase 未全 PASS | `FAIL` |
| NOP 任一轮不是 `VALID/0`、P2P 未全 PASS，或没有核心 F2P FAIL | `FAIL` |
| 缺测试、构建、环境、权限或解析故障被写成正式 reward 0 | `FAIL`，应为 `INVALID/BLOCKED` |
| 提示词非自然中文口语表达，或人为添加“中文口语化提示：”前缀 | `FAIL` |
| Solution、隐藏测试、reward 或凭据泄漏给模型；轨迹含真实密钥 | `FAIL` |
| 题面、环境、solution、tests 或评分修改后仍复用旧轨迹 | `FAIL` |
| Golden/NOP 的得分或逐 testcase 终态与预期不一致 | `FAIL` |
| 任一评分项或 testcase 出现误杀、漏判、漏计分、错误聚合 | `FAIL` |
| Testcase 与题面不对应，包含题外隐藏要求，或绑定 Golden 私有代码写法 | `FAIL` |
| 模型通过联网、Web Search、git 拉取、搜索 Golden/隐藏测试/reward、修改测试/Verifier 或复用旧产物绕过任务 | `FAIL` |
| 题目核心功能没有真实 Windows 反事实价值 | `FAIL` |
| WIP 94 项中有适用检查项确认失败 | `FAIL`；同时保留 Windows 适配结论 |
| D01–D20 中确认存在 Golden/no-change、测试公平性、环境可信度、Hack、计分或批次缺陷 | `FAIL` |
| 独立复算与 verifier/reward/平台正式分不一致 | `FAIL` |
| 核心测试只接受 Golden 私有函数、固定代码文本/布局/调用方式，等价实现被误杀 | `FAIL` |
| 镜像配置冲突；确认远端镜像不存在或甲方无拉取权限，且无目标认可的替代交付方式 | `FAIL`，镜像交付问题 |
| 目标不允许现场构建，交付仅能依赖作者本机镜像或 Dockerfile | `FAIL`，镜像交付问题 |
| 在目标同等 Windows/架构/隔离方式下确认无法启动或执行题目 | `FAIL`，环境交付问题 |
| 实际运行镜像早于 Windows 2019/build 17763，或使用 Nano Server、Server Core、自定义裁剪系统 | `FAIL` |
| 当前题目实际执行使用非嵌套虚拟化环境 | `FAIL`；物理机 Hyper-V 或单层 VM 不算嵌套 |
| 实际用到的工具依赖作者宿主/手工安装，Dockerfile 不能复现其安装或基础内置验证；成品容器功能失败 | `FAIL` |
| 题目只是调用 PowerShell/Windows 工具或生成 BAT，核心行为没有真实 Windows 专项语义 | `FAIL` |

## 必须 BLOCKED

| 检查项 | 判定 |
|---|---|
| 未冻结当前题的版本、Hash、测试树、评分公式、镜像或运行批次身份 | `BLOCKED` |
| WIP 94 项未完整登记，或 N/A 没有适用性依据 | `BLOCKED` |
| D01–D20 未完整审计，或只有汇总报告没有原始证据 | `BLOCKED` |
| 轨迹、原始日志、候选 SHA、required testcase 终态或评分条件缺失，无法闭合逐项证据链 | `BLOCKED` |
| 运行因环境、权限、依赖、解析、零测试、401/429 或中断而无效 | `INVALID/BLOCKED`，可信分数为 `null` |
| 无法从 required testcase 和冻结公式独立复算正式分数 | `BLOCKED` |
| 缺少 `image_delivery`，或远端拉取、甲方权限、目标兼容、新容器启动和任务执行证据不完整 | `BLOCKED` |
| 质检机网络/账号权限故障、仓库临时不可用，或未知甲方宿主/架构/隔离方式 | `BLOCKED`；不能直接认定镜像未发布或记模型 0 |
| 缺少镜像实际版本、家族/基础来源或工具安装与真实功能证据；新增两个结构化复核项未完成 | `BLOCKED` |
| 缺少外层 VM、扩展暴露、内层启动、当前 jobs 绑定证据或 nested_virtualization 项 | `BLOCKED` |

## 仅提示或人工复核

| 检查项 | 判定 |
|---|---|
| `source.json` 缺失 | 允许；存在时必须有效且身份一致 |
| required testcase 为 5–27 条 | 正常 |
| required testcase 超过 27 条 | 仅提示人工复核范围、重复度和预算 |
| Dockerfile `FROM` 未 pin SHA-256 digest | 不单独失败；仍禁止 `latest` |
| 缺少顶层 `evidence/` | 不单独失败 |
| 缺少顶层 `metadata/` | 不单独失败 |
| `task.toml` 缺 network policy 字段 | 不单独失败 |
| GLM 得分高于 Opus | 不因该现象单独失败；仍执行 Opus/Qwen 主分差门禁 |
| 泛化描述“每模型运行次数不足” | 不单独使用该措辞；若少于固定 14 个 job，按目录和原始证据缺件失败 |
| 历史问题库记录某题曾经存在缺陷 | 只作风险提示；必须用当前版本证据确认 |
| 执行时间较长，但未超过冻结预算且无超时或死锁证据 | 不单独失败 |
| 镜像使用短名，或 Windows build 与宿主数字不同 | 不单独失败；实测仓库解析、实际隔离方式和目标兼容性；仍须满足镜像最低版本和完整系统规则 |
| 合格且兼容的完整 Windows 2019/2022 镜像未使用 2025 | 不因非 2025 单独失败；2025 为优先项 |

## 当前模型区分度口径（2026-10-15）

同一冻结题目的 Qwen、Opus 各三轮全部 VALID 后，必须严格满足
`Qwen model_score_sum < Opus model_score_sum`。正式分数平分一律失败，Opus testcase 表现更强
也不能挽救平局；全零平局和双方全满分失败。旧平分二级判据与全零例外取消，历史题目的旧结论
保留为历史记录，不据此改写当前原始分数。

## 真实执行要求

- 必须按 [nested-virtualization-gate.md](nested-virtualization-gate.md) 证明实际嵌套执行，不能以 Hyper-V 参数或 CPU 支持代替。

- 镜像交付按 [image-delivery-gate.md](image-delivery-gate.md) 单独核验；本地 Oracle/NOP PASS 不替代甲方可获取和可运行的证据。
- Docker 必须处于 Windows Containers 模式；Linux、WSL 或模拟执行不能代替。
- Oracle 和 NOP 默认各独立运行 3 次，每轮使用新 job 和干净环境。
- 每轮固定 `--n-attempts 1 --n-concurrent 1 --max-retries 0`。
- 运行失败不得盲目重复并覆盖原证据；先判定为题包失败或环境阻塞。
- Oracle 截图应来自 Harbor CLI/控制台原始输出，并显示任务、Agent、轮次和 `VALID/1`。
- 自动门禁全部通过但没有完成十四项人工质量复核，最终结论为 `BLOCKED`，不得写成 `PASS`。

## 返修原因写法

只记录本次检查实际证实的问题。每条原因至少引用一项可定位证据：ZIP 成员路径、Task
文件及行、job 目录、`result.json`、verifier 报告、CLI 日志或 testcase ID。不得添加未执行
的推测，也不得把本表“仅提示或人工复核”项目写成必须返修项。
