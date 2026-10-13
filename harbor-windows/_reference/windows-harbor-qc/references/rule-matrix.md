# Windows Harbor 最新质检规则矩阵

本表用于快速判定，完整执行细节见 `checklist.md`。发生规则冲突时，以本表和直接 Harbor
标准目录为准，不再使用旧 Demo 包装格式。

## 必须失败

| 检查项 | 判定 |
|---|---|
| ZIP 唯一根目录名称与 ZIP 文件名去掉 `.zip` 后不完全一致 | `FAIL` |
| 根目录未直接包含 `task.toml`、`instruction.md`、`environment/`、`solution/`、`tests/`、`jobs/` | `FAIL` |
| 使用 `outside_harbor/`、`outside_harbor-assets/` 等旧 Demo 包装层 | `FAIL` |
| `task.toml` 的 instruction/workspace/setup/test/golden 入口缺失、越界或指向未交付文件 | `FAIL` |
| `solution/` 缺少可由标准 OracleAgent 调用的 `solve.ps1` 或 `solve.bat` | `FAIL` |
| 测试入口引用未交付文件，或 required testcase 少于 5 条 | `FAIL` |
| `jobs/` 不是规定数量的原生 Harbor job：**必需** Qwen×3、Opus×3、Oracle×3、NOP×3（12 个）；GLM×1、Kimi×1 自 2026-10-13 起可选（含则为 14 个） | `FAIL` |
| 任一 job 缺少规定的原始 config/lock/result/log/verifier/reward/trajectory 文件 | `FAIL` |
| 任一模型运行不是 `VALID`、不是二值 0/1、testcase 集合不完整或 Task Hash 不一致 | `FAIL` |
| Opus 总分低于 Qwen | `FAIL` |
| Opus 与 Qwen 总分相等，但 Opus 的 `testcase_pass_sum` 没有严格高于 Qwen，且全部规定模型运行（必需 6 次；含可选 GLM/Kimi 为 8 次）并非全部 `VALID/0` | `FAIL` |
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

## 必须 BLOCKED

| 检查项 | 判定 |
|---|---|
| 未冻结当前题的版本、Hash、测试树、评分公式、镜像或运行批次身份 | `BLOCKED` |
| WIP 94 项未完整登记，或 N/A 没有适用性依据 | `BLOCKED` |
| D01–D20 未完整审计，或只有汇总报告没有原始证据 | `BLOCKED` |
| 轨迹、原始日志、候选 SHA、required testcase 终态或评分条件缺失，无法闭合逐项证据链 | `BLOCKED` |
| 运行因环境、权限、依赖、解析、零测试、401/429 或中断而无效 | `INVALID/BLOCKED`，可信分数为 `null` |
| 无法从 required testcase 和冻结公式独立复算正式分数 | `BLOCKED` |

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
| Qwen 三次与 Opus 三次同时全部 `VALID/1`（或 8 次规定模型运行全部满分） | 不单独 `FAIL`（2026-10-12 放宽）；按 `testcase_pass_sum` 判据裁决，并必须记录 `qwen_opus_full_score` / `all_models_full_score` |
| 泛化描述“每模型运行次数不足” | 不单独使用该措辞；若少于固定 14 个 job，按目录和原始证据缺件失败 |
| 历史问题库记录某题曾经存在缺陷 | 只作风险提示；必须用当前版本证据确认 |
| 执行时间较长，但未超过冻结预算且无超时或死锁证据 | 不单独失败 |

## 模型平分判定

先分析 Qwen、Opus、GLM、Kimi 的全部规定运行。当 Qwen 与 Opus 的三次 `model_score_sum`
相等时，比较相同 required testcase 集合上的 `testcase_pass_sum`：Opus 严格高于 Qwen 则区分度
门禁通过；小于或等于则失败，但下述全模型有效零分例外仍然保留。**总分相等不限于双方均为 0**：
Qwen 三次与 Opus 三次同时全部 `VALID/1`（正式分顶格）时同样走本判据——「双方同时三轮满分」
本身不再出局，但必须由 testcase 颗粒度严格分开两者，否则仍判失败。`qwen_opus_full_score`
与 `all_models_full_score` 必须记录进报告，用于说明判分颗粒度是否足以区分主模型，不再单独否决。

## 合法的零分平局例外

只有全部规定模型运行（必需 Qwen×3 + Opus×3 共 6 次；含可选 GLM×1 + Kimi×1 则 8 次）全部是 `VALID/0` 时，即使 Opus 的
`testcase_pass_sum` 没有严格高于 Qwen，也允许 `Opus = Qwen = 0`。如果不满足该例外且
Opus/Qwen 总分相等，则必须由 Opus 更高的 testcase 累计通过数打破平局。

## 真实执行要求

- Docker 必须处于 Windows Containers 模式；Linux、WSL 或模拟执行不能代替。
- Oracle 和 NOP 默认各独立运行 3 次，每轮使用新 job 和干净环境。
- 每轮固定 `--n-attempts 1 --n-concurrent 1 --max-retries 0`。
- 运行失败不得盲目重复并覆盖原证据；先判定为题包失败或环境阻塞。
- Oracle 截图应来自 Harbor CLI/控制台原始输出，并显示任务、Agent、轮次和 `VALID/1`。
- 自动门禁全部通过但没有完成十项人工质量复核，最终结论为 `BLOCKED`，不得写成 `PASS`。

## 返修原因写法

只记录本次检查实际证实的问题。每条原因至少引用一项可定位证据：ZIP 成员路径、Task
文件及行、job 目录、`result.json`、verifier 报告、CLI 日志或 testcase ID。不得添加未执行
的推测，也不得把本表“仅提示或人工复核”项目写成必须返修项。
