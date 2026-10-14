# D01–D20 动态审计 —— wfflab__wvas-216 v1.0.0

审计依据：`_reference/windows-harbor-qc/references/windows-procurement-qc-manual-20260927/01-质检执行手册.md` §5.1–§5.5。

冻结身份：task_id `wfflab__wvas-216`，task_version `1.0.0`，task checksum
`b925e1c7f68e6954805fa39e6ea584577ced25f87a74d58fb7325b288469461b`，
`instruction.md` SHA256 `04a919c928857a207b533cd6f6578441d72bc3b3aa0746637bddf245413e8665`（5508 B，无 BOM，LF），
`tests/rubric.json` SHA256 `b1e497b42ade986eb0d841167d2a7fdc033560a921a9e8d373f8252776ba30ed`（与 `tests/judge.toml` 的 `source_sha256` 逐字节一致）。

## 5.1 D01–D04：Golden path 与空跑对照

| ID | 检查项 | 本轮证据 | 结论 |
| --- | --- | --- | --- |
| D01 | 运行身份一致 | 同一不可变 base `mcr.microsoft.com/windows/servercore:ltsc2022@sha256:76cf422c…db6a`（`task.toml` `docker_image` 与 `environment/Dockerfile` FROM 逐字一致）；同一 `tests/` 树；同一 `aggregate_results.ps1` 冻结公式；Golden 经 Harbor 挂载 `solution/` 注入，模型容器不可见 `verifier/`。**补丁确实生效的行为证据**：Oracle×3 reward=1、16/16 全 PASS，而同环境 NOP×3 reward=0、8/16（F2P 全 FAIL）—— 仅当参考实现真正落到 `wvas/` 才可能全通过，不以环境变量或日志标题为凭。应用记录见各 Oracle 轮 `agent/oracle.txt`、`agent/qc-oracle-application.json`。 | 满足 |
| D02 | 对照逐项成立 | 逐例矩阵 `case-matrix.md`：NOP 下 F2P 8 条全 FAIL 且 P2P 8 条全 PASS；Oracle 下 16 条全 PASS。无 0 collected、无 skip、无缺项（`invalid=0`，见 `independent-recompute.md`）。 | 满足 |
| D03 | 空跑得分逐分解释 | NOP 得分为 **0**（不是部分分）。其 8 个 PASS 全部落在 P2P 组，逐条可归因为 base 已有行为：`p2p-regions-are-sorted-by-base`、`p2p-region-records-are-well-formed`、`p2p-own-process-reports-image-regions`、`p2p-file-backed-regions-are-a-subset`、`p2p-include-reserved-false-only-reports-committed-memory`、`p2p-negative-pid-is-rejected`、`p2p-modules-are-sorted-by-base`、`p2p-visible-smoke-suite-still-passes`。无任何 F2P 被 base 蒙对，不存在奖励新增能力或异常高分。 | 满足 |
| D04 | 稳定性与重建 | base(NOP)×3：均 VALID / 0 分 / 8-16，耗时 49/51/50 s。Golden(Oracle)×3：均 VALID / 1 分 / 16-16，耗时 57/69/65 s。同 checksum 下逐用例终态完全一致。模型轮差异来自不同候选补丁，不据此判定 flaky。 | 满足 |

## 5.2 D05–D10：逐项判分与题面对应

| ID | 检查项 | 本轮证据 | 结论 |
| --- | --- | --- | --- |
| D05 | 证明要求实际下发 | `instruction.md` SHA256 `04a919c9…`（绑定本版本）。模型侧 `agent/trajectory.jsonl` 内**实际留存了当次收到的题面原文**（含标题「wvas：进程虚拟地址空间审计实现有缺陷」、「## 现象」、`issue #216`、「验收标准」四段探针全部命中），证明要求进入模型上下文，而非只存在于 organizer 文档。 | 满足 |
| D06 | 建立双向映射 | 正向：现象 1→`f2p-region-addresses-are-64-bit`，现象 2→`f2p-region-sizes-are-64-bit`，现象 3→`f2p-reserved-regions-are-reported`，现象 4→`f2p-file-mapping-path-is-a-dos-path` + `f2p-device-paths-are-translated`，现象 5→`f2p-anonymous-mapping-has-no-path`，现象 6→`f2p-missing-process-is-classified`，现象 7→`f2p-modules-are-deduplicated`；验收 A/B/C/D/E 的回归与边界→8 条 P2P。反向：16 条必需用例全部落入 `tests/judge.toml` 的 7 个 rubric 组，无孤儿用例、无孤儿 rubric。每项依据类别：题面明确要求（现象与 A–D）、公开接口/既有兼容性（E 与「公开 API 名字和签名不得改变」）、合理可推导边界（排序、子集、去重）；无未声明的额外要求。 | 满足 |
| D07 | 每项都审，PASS 也审 | 12 轮 × 16 用例的终态全部落盘于 `case-matrix.md`；得分项排除断言未执行（`invalid=0`、无 0 collected）、测试副本、固定输出与旧产物（每轮独立容器 + 独立 workspace）。未得分项区分：`model-qwen-3` 的 2 条 F2P 为真实功能未实现（MODEL_FAILURE，非误杀、非缺测）。 | 满足 |
| D08 | 功能优先，接受多解 | 判分依据全部为输入输出与公开契约（`regions`/`modules`/`file_backed_regions` 的返回值、`WVasError.kind`、排序与子集关系），不检查私有函数名、签名、固定中间变量或代码文本。等价实现获证：`model-qwen-1/2` 与 `model-opus-1` 三份互相独立的补丁（`agent/patch.diff` 大小各异）均达 16/16。 | 满足 |
| D09 | 等价实现与故障反例 | 等价实现：上述三份独立候选补丁全通过，且拆文件/改辅助函数不影响判分。故障反例：NOP（不改源码）8/16、F2P 全失败，证明 8 条 F2P 确实锚定目标缺陷；`p2p-visible-smoke-suite-still-passes` 约束不得为过隐藏用例而破坏既有可见冒烟套件。`f2p-*` 用例全部要求真实 Windows 行为，硬编码返回值无法同时满足 `f2p-region-addresses-are-64-bit` 与 `f2p-region-sizes-are-64-bit`（须与 `VirtualQueryEx` 实测逐项一致）。 | 满足 |
| D10 | 替身必须保真 | 本任务**不使用 Mock 或替身**：评测在真实 Windows 容器内对真实进程调用 `VirtualQueryEx` / `GetMappedFileNameW` / `QueryDosDeviceW`，并**另起目标进程**独立测量，不采信 `wvas` 自报数字（题面「运行入口」段明确）。因此不存在替身保真缺口。 | 满足（无替身） |

## 5.3 D11–D14：Windows 运行可信度

| ID | 检查项 | 本轮证据 | 结论 |
| --- | --- | --- | --- |
| D11 | 工具、路径、离线依赖和权限 | 全部轮次在 `servercore:ltsc2022` 内以 Windows PowerShell 5.1 执行（`environment/run.ps1` 顶部注明 BOM-less 文件按 ANSI 读取）；工作区固定在 `C:\testbed`，路径解析一律经 `$PSScriptRoot` + `Join-Path`，不依赖调用者 cwd；评分阶段不联网、不装包（`tests/*.ps1` 无 `pip/uv install`、无 `Invoke-WebRequest`）；依赖闭包随包交付 `environment/vendor/`（嵌入式 Python + 锁定 wheel）。 | 满足 |
| D12 | 本轮构建与候选回放 | 每轮候选补丁封存于 `agent/patch.diff`（含 SHA）；同 checksum 下 Oracle 回放 3 次结果一致；容器每次重建、旧产物不残留（job 目录逐轮独立删除后重跑）；`invalid=0` 表明无静默截断。 | 满足 |
| D13 | 环境能力与真实系统终态 | 目标为真实 Windows 内核（非 WSL2、非模拟、非交叉编译），地址空间、文件映射与 DOS 设备路径均为真实系统状态；无需桌面/窗口能力。系统残留：每轮独立容器，退出即回收。 | 满足 |
| D14 | 退出、异常、解析和日志 | 异常路径产出**结构化 INVALID**而非 0 分：opus 第 2/3 轮的 `RuntimeError: http_403`（上游预扣费额度不足）被判为运行链路故障、不计模型能力分，并已重跑替换；`verifier/result.json` 的 `status` ∈ {VALID, INVALID}，精确 test ID 与终态一一对应；原始日志 `verifier/verifier.log`、`verifier/test-stdout.txt` 随轮次落盘。 | 满足 |

## 5.4 D15–D17：Hack、泄露与完整轨迹

| ID | 检查项 | 本轮证据 | 结论 |
| --- | --- | --- | --- |
| D15 | 联网取源码/答案 | `hack-events.md`：扫描 12 份轨迹，联网类工具调用 **0** 次，命令行片段无 `curl/wget/Invoke-WebRequest/git clone`。容器出站限制与负向可达性另见 `verifier/ISOLATION.md`、`verifier/negative_access_probe.ps1`。 | 满足 |
| D16 | 本地搜答案/隐藏验收 | 同上：答案/参考/隐藏路径访问事件 **0** 条；轨迹正文未出现评测用例 ID 或 `required_testcases`。模型可见目录仅 `C:\testbed`（含题面明示的可见冒烟套件 `tests/test_wvas_basic.py`），`verifier/` 不挂载进模型容器。 | 满足 |
| D17 | 篡改或绕过验证 | 同上：涉及评分资产的写入/执行事件 **0** 条；无改 reward、无伪造报告、无跳过测试。评分文件在评分阶段由 verifier 侧生成，模型容器对其不可见。 | 满足 |

事实等级说明：本轮全部事件计数为 ATTEMPT 0 / ACCESS_CONFIRMED 0 / USE_CONFIRMED 0 / SCORE_IMPACT_PROVEN 0。
边界：路径无命中与关键词无命中**不能**证明绝对安全；本扫描仅覆盖模型容器内可见工具，容器出站、服务端 Web 工具与评分阶段权限分别独立取证，不合并宣称「作弊面彻底堵死」。

## 5.5 D18–D20：分数复算、归因与交付

| ID | 检查项 | 本轮证据 | 结论 |
| --- | --- | --- | --- |
| D18 | 独立复算 | `independent-recompute.md`：直接由 16 条必需 ID 与逐例终态复算，**不读取候选可写的 reward**。冻结公式 `formal_score = 1 当且仅当 run_validity == VALID 且全部必需用例 PASS`；`run_validity = VALID 当且仅当 cases_total > 0 且 invalid == 0`（空清单不得因 `all([])` 变 1）。12 个轮次（控制 6 + 模型 6）的复算值与 `reward.txt`、`report.json` 的 `formal_score`、`run_validity` **全部一致**，无差异。 | 满足 |
| D19 | 失败归因 | `model-qwen-3` 得 0：当期 base/Golden 环境预检通过、Oracle 全通过，候选自身 2 条 F2P 未实现 → MODEL_FAILURE，按规则有效扣分。`model-opus-2` 另有一次**真实模型失败**：该轮只读工作区文件、step 5 直接 `end_turn`、未产出 `patch.diff`，判分 8/16 与 no-change 一致 → MODEL_FAILURE，按规则有效计 0（其自述的"冒烟用例与验收 C 冲突"经核对不成立，该断言只针对当前进程），已重跑取得 1 分且不双计、不选最高分。opus 第 2/3 轮曾失败：`RuntimeError: http_403`（上游账户预扣费额度不足）→ 运行链路故障，**未计能力 0**、未混入均分，已重跑替换。无 ENV/TEST/REFERENCE 缺陷，无证据不足情形。 | 满足 |
| D20 | 批次与交付 | 只统计同版本最新完整有效批次。分母：计划 12 轮（Oracle×3 + NOP×3 + Qwen×3 + Opus×3），本批交付 12 轮；被替换的 opus 失败槽位保留旧→新对应，不双计、不选最高分。Oracle/NOP 为控制轮，不计独立模型成绩。全部轮次 task checksum 一致。 | 满足 |

## 汇总

D01–D20 共 20 项，全部有结论并绑定原始证据路径。未出现 Golden/no-change 缺陷、测试公平性缺陷、环境可信度缺陷、Hack 事实或计分缺陷。

> 本表在模型轮次全部落盘后按最终 `jobs/` 复核一次；`case-matrix.md`、`independent-recompute.md`、`hack-events.md`、`wip94-register.md` 与本表同目录存放。
