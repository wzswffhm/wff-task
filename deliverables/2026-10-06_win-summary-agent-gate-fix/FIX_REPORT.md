# FIX_REPORT — 汇总门禁修正：Agent 阶段故障的运行不得计分

> 执行时间：2026-10-06 08:22
> 涉及工具：`C:\Users\Administrator\Desktop\generate-win\scripts\summarize_model_runs.py`、`make_evidence_images.py`
> 关联题包：`harbor-windows/wfflab__wreparse-217`（本轮**题包零写入**）
> 备份：本目录 `scripts/summarize_model_runs.py.orig`（sha256 `f8b1af5a…4552fa`）、`make_evidence_images.py.orig`

## 0. 结论

| 项 | 结果 |
| --- | --- |
| 门禁脚本 | ✅ 已修正：`valid_scored_result()` 现在同时校验 **agent 阶段**与 verifier 阶段 |
| 证据脚本 | ✅ 已同步：新增 `Agent fail` 列 + `Epoch pinned` / `Agent-stage failures excluded` 行 |
| 第 7 轮判定 | ⛔ **不通过**（`qualified=false`），两种口径一致——原判"通过"确认为假阳性 |
| 交付动作 | 不打包、不写飞书（本轮 ZIP 与截图仅存档，不作为交付物） |
| 题包改动 | **零**（仅读取） |

## 1. 缺陷描述

### 1.1 现象

`summarize_model_runs.py` 输出 `opus_sum_greater_than_qwen=true`、`qualified=true`，但其中 QWEN 的 0 分并非候选失败，而是**上游超时**。

### 1.2 根因

原 `valid_scored_result()` **只校验 verifier 层**：

```python
report.status == "VALID" and verdict in (0, 1) and report.score == verdict
and report.task_id == item.task_id and report.task_version == item.task_version
and bool(item.test_log_sha256)
```

**完全不看 `agent.status`。** 当 agent 因 `TimeoutError` 在 turn 8 死亡时，verifier 仍会照常评估**未被修改的 workspace** 并输出自洽的 `VALID + verdict=0`，于是这道 0 分被当作合法成绩吸收进 `score_sum`，凭空造出"区分度"。

### 1.3 规范依据

`generate-win/SKILL.md` 第 151 行（原文）：

> Provider, authentication, gateway, malformed-response, environment, runner, and verifier-infrastructure failures **are not valid scored runs. Diagnose and retry them; do not turn them into score `0`.** Candidate compile/test failures are score `0` when the verifier itself completed normally.

关键区分：**候选自身**编译/测试失败 = 合法 0 分；**基础设施/上游**故障 = 无效运行，必须重跑。

## 2. 修改内容

| # | 位置 | 修改 |
| --- | --- | --- |
| 1 | 模块顶部 | 新增 `SCORED_AGENT_STATUSES = frozenset({"completed", "max_turns"})` + 模块 docstring 说明两阶段校验语义 |
| 2 | 新增 `agent_failure()` | 对 `mode == "candidate"` 的运行，返回未达计分态的详情；`no-change` / `golden` **豁免**（controls 不经过 agent） |
| 3 | `valid_scored_result()` | 首行加入 `if agent_failure(item): return False` |
| 4 | `model_summary[model]` | 新增 `excluded_agent_failures`（含 `exclusion.agent_status` / `turns` / `summary`）；`invalid_attempts` 排除已归入前者的条目，避免重复计数 |
| 5 | `gates` | 新增 `epoch_pinned`、`agent_failures_excluded` |
| 6 | **`qualified` 计算** | **纳入 `epoch_ok = bool(after)`** —— 未固定 qualification epoch 时**直接拒判**（`qualified=false`），不再只是警告 |
| 7 | 收尾 | 未传 `--after` 打印 `[error]` 说明拒判原因与规范出处；有故障剔除时打印重跑提示（均走 stderr，**不改退出码语义**：0 = qualified / 2 = not） |
| 8 | **`compact()`** | 逐条补 `task_id` / `task_version` —— 满足 `qualification-gates.md:44`「record their run IDs, **task version**, verdict, duration, **agent status**, and verifier-log hash」 |
| 9 | `make_evidence_images.py` | 分数表新增 `Agent fail` 列；底部新增 `Epoch pinned` 与 `Agent-stage failures excluded (not scored)` 行 |

**状态映射语义**（`runner.py` 实际取值域）：

| agent.status | 含义 | 是否计分 |
| --- | --- | --- |
| `completed` | 模型自行收尾 | ✅ 计分（含候选编译/测试失败 → 0 分） |
| `max_turns` | 用尽**已声明**的轮次预算 | ✅ 计分（属候选表现） |
| `error` | provider / gateway / 超时 / runner 异常 | ⛔ 不计分，须重跑 |
| `no_tool_call` | 模型从未发出工具调用（malformed response） | ⛔ 不计分，须重跑 |
| `None`（candidate） | 记录残缺 / runner 中断 | ⛔ 不计分，须重跑 |

## 3. 修正前后对比（同一份数据）

```
修正前（口径 A，无 --after）:  gates.qualified = true    ← 假阳性
修正后（口径 A，无 --after）:  gates.qualified = false   ← 如实
```

| 指标 | 修正前 | 修正后 |
| --- | --- | --- |
| QWEN `score_sum` | 3（[1,2 轮 + 故障 0 分被计入]） | 3（[1,1,1]，剔除故障后仍由 3 个**合法**满分轮构成） |
| OPUS `score_sum` | 3 | 3 |
| `opus_sum_greater_than_qwen` | true（因 QWEN 被故障分压低到 2） | **false**（3 > 3 不成立） |
| 被剔除的故障运行 | 未统计 | **3 条**（QWEN / GLM / KIMI 各 1） |

**被重新归类为"不计分"的 3 条运行**：

| 模型 | run_id | 原判 | agent.status | 故障摘要 |
| --- | --- | --- | --- | --- |
| QWEN | `20261005T235615-candidate-qwen3.8-max-0902-02` | 0 分（计分） | `error` | `model error: TimeoutError: The read operation timed out` |
| GLM | `20261005T163942-candidate-glm-5.3-01` | 0 分（计分） | `error` | `model error: TimeoutError: The read operation timed out` |
| KIMI | `20261005T133112-candidate-kimi-k3-01` | 0 分（计分） | `no_tool_call` | 模型输出正文却未发工具调用 |

> 剔除 KIMI / GLM 的故障轮后，二者**仍有合法计分轮**（GLM `132138` max_turns → 0；KIMI `213151` completed → 1），故 `complete=true` 不受影响。

## 4. 回归验证

- `py_compile` 通过（两个脚本）；
- 全库 51 份 `result.json` 重跑，`excluded_agent_failures` 恰为上述 3 条，无误伤（`completed` 19 条、`max_turns` 11 条全部保留计分）；
- controls（`no-change` 7 条 / `golden` 7 条，`agent` 字段为 `None`）**未被误剔除**，`controls_passed` 仍为 `true`——验证 controls 豁免逻辑正确；
- 7 条 `report.status=INVALID` 记录的 `task_id` 均为 `None`（runner 崩溃残缺记录），在加载阶段即被 `task_id` 过滤，不计入任何口径，行为不变。

## 5. 「候选模块导入失败 → INVALID 归一为 0 分」的分析结论

**结论：本轮不适用，且不应在 runner / 汇总层做笼统归一。**

**（1）本轮实证**：全库 7 条 `INVALID` 的 `reason` **全部**是 `verifier produced no result.json` —— 即 verifier 自身未产出结果，属**评测基础设施异常**，**没有一例**是"候选模块导入失败"。

**（2）规范判据**（`SKILL.md:151`）是「**the verifier itself completed normally**」：

- verifier 正常完成 + 候选失败 → 合法 0 分；
- verifier 未能完成 → 基础设施异常 → 不计分、重跑。

（3）**当前 INVALID 归属**：按上述判据，本轮 7 条 INVALID 属"verifier 未完成"→ 正确处置是**重跑**（脚本已把 `INVALID` 排除出计分集合），**不是**归一为 0 分。

**（4）若将来真出现"候选产物损坏导致 verifier 无法执行"**，正确的修法是**改 verifier，而不是改 runner / 汇总层**：

- ✅ 在 verifier 内**包裹候选产物的导入/编译步骤**（try/except），捕获后输出 `status=VALID, verdict=0, reason="candidate artifact failed to import"` —— 使 verifier **正常完成**并判候选不合格，天然满足规范"verifier completed normally"的条件；
- ⛔ **不要**在 runner 或汇总层做 `INVALID → 0` 的笼统转换，理由有三：
  1. 汇总层只看得到 `status`，**看不到失败发生在候选代码还是评测代码**，无法可靠归因；
  2. 笼统归一必然把**真正的 verifier 基础设施故障**（如 pytest 缺失、容器 OOM）也计成候选的 0 分，**直接违反 `SKILL.md:151`**；
  3. 归因所需的上下文只有 verifier 自己持有，把归因下沉到 verifier 是**唯一**能同时满足"候选失败计 0"与"基础设施故障不计分"的方案。

即：**归因发生在 verifier 内部，语义是"verifier 正常完成 + 判 0"，而不是"把 INVALID 改写成 0"。**

## 6. 影响面

- 该脚本是**全批次共用**的资格门禁 → 本次修正惠及后续所有题包轮次，任何 `agent.status=error/no_tool_call/None` 的运行今后都会显式暴露而非静默计分；
- 新增字段（`excluded_agent_failures`、`epoch_pinned`、`agent_failures_excluded`）为**向后兼容的增量**，不改动任何既有字段名与语义 → 下游消费者（截图脚本等）无需同步改造即可继续工作；
- 未传 `--after` 时只打印 `[error]` 到 stderr 并把 `qualified` 压为 `false`，**退出码语义不变**（0 = qualified / 2 = not qualified）；
- ✅ **向后兼容**：`--after` 仍为可选参数，既有调用点（如 `resume-after-reboot.ps1:115`，本就带 `--after $epoch`）无需改造；未带 epoch 的旧调用（如 `BLOCKER.md:160` 的历史复现命令）今后只会得到 `qualified=false` + 明确报错，**不会静默放行**。

---

## 7. 与 `generate-win` 交付标准的符合性对照

`generate-win` 的交付标准由 `SKILL.md` 与 `references/*.md` 共同构成。逐条对照如下。

### 7.1 `references/qualification-gates.md`

| 规范条款 | 原文要点 | 脚本现状 |
| --- | --- | --- |
| §Qualification epoch（第 3 行） | 「Only results created after that timestamp may enter the official set」 | ✅ 未固定 epoch → **拒判**（`epoch_pinned=false` ⇒ `qualified=false`） |
| §Controls（第 8-9 行） | NOP 3 次 `VALID+verdict=0`；Oracle 3 次 `VALID+verdict=1` | ✅ 已有校验（`controls_ok`） |
| §Controls（第 10 行） | 「A screenshot or aggregate summary **never replaces** the raw result / verifier log / task identity / task version / epoch evidence」 | ✅ 每条 selected 记录 `result_path` + `task_id` + `task_version` + `test_log_sha256`，可回溯原始 `result.json` |
| §Controls（第 12 行） | 「An `INVALID` control … Repair it; **do not count it as `0`**」 | ✅ `INVALID` 不入 `selected` ⇒ `len != required` ⇒ `controls_ok=false`（作为故障暴露而非 0 分） |
| §Model matrix（第 33 行） | 「Provider/authentication/gateway failures and verifier-infrastructure failures **are not valid scores and must be retried**」 | ✅ `agent_failure()` 把这些归入 `excluded_agent_failures`，不计分 |
| §Repair semantics（第 37 行） | provider 修复可只重跑缺失项 | ✅ 故障运行单列清单，支持定向重跑 |
| §Evidence（第 44 行） | 「Select result files **deterministically** and record their run IDs, **task version**, verdict, duration, **agent status**, and verifier-log hash」 | ✅ 选中规则确定（mtime 排序取末 N 个 valid）；**六项证据字段逐条齐全** |

### 7.2 `generate-win/SKILL.md`

| 规范条款 | 原文要点 | 脚本现状 |
| --- | --- | --- |
| 第 109 行 | 「distinguish **functional failures (`0`)** from **infrastructure failures (`INVALID`)**」 | ✅ 0/1 = 合法候选结果；`INVALID` 与 agent 故障均不计分 |
| 第 132 行 | 「**Never mix results from different task versions or epochs**」 | ✅ `task_version_consistent` 校验 + epoch 过滤（拒判兜底） |
| 第 151 行 | 「Provider, authentication, gateway, malformed-response, environment, runner, and verifier-infrastructure failures are not valid scored runs … **do not turn them into score `0`**」 | ✅ 本次修复的核心 |
| 第 153 行 | 「Run `summarize_model_runs.py` **with the qualification epoch**」 | ✅ 不传 epoch 即 `qualified=false`（强制调用者固定 epoch） |
| 第 232 行 | 「every selected Oracle/NOP result has matching task ID/version, **current qualification epoch**」 | ✅ 逐条 `task_id`/`task_version` + epoch 过滤 |
| 第 234-236 行 | Qwen 3 / Opus 3 / GLM 1 / Kimi 1，且 `Opus score sum > Qwen score sum` | ✅ `REQUIRED_MODELS` = `{QWEN:3, OPUS:3, GLM:1, KIMI:1}`；`opus_sum_greater_than_qwen` |
| 第 240 行 | 「both screenshots derive from the selected result files」 | ✅ 截图由 summary JSON 渲染，JSON 由 `result.json` 生成 |

### 7.3 尚未由本脚本覆盖（属其它阶段职责，非遗漏）

| 规范条款 | 归属阶段 |
| --- | --- |
| 完整本地任务树结构、`source.json` / `solution/**` 齐备 | §4 结构校验（`validate_requirement_conformance.py` + runner 结构校验） |
| 四件套 ZIP 只含 `task.toml`/`instruction.md`/`environment/`/`tests/`，且全新解压校验 | §7 `package_harbor.ps1` |
| 飞书建行 / 附件 / 回读校验 | §9 `upload_feishu.ps1` |
| 「至多三个完整整改循环」的计数 | §6 人工流程 |

**结论：本次修正后，`summarize_model_runs.py` 对 `qualification-gates.md` 与 `SKILL.md` 第 5 节的全部资格判定条款均已覆盖，无剩余偏差。**
