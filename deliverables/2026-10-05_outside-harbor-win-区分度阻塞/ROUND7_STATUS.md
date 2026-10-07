# ROUND7_STATUS — `wfflab__wreparse-217` 第 7 轮模型矩阵状态简报

> 首次收口：2026-10-06 02:05　内容合规性复核：2026-10-06 08:20（结论撤回）　**门禁修正复评：2026-10-06 08:22（判定确立）**
> 工作区：`deliverables/2026-10-04_outside-harbor-win/runner`
> 题包：`harbor-windows/wfflab__wreparse-217`（全程**未修改题包任何文件**）
> 第 7 轮 tag：`q7` / `o7`，23:20:59 起跑，02:02:20 收尾
> **本轮唯一变量：`MAX_AGENT_TURNS` 80 → 24**

## 0. 结论（修正版，覆盖 02:05 的初版）

> ⛔ **原判"第 7 轮通过（OPUS 3 > QWEN 2）"作废。** 该结论只满足「分数门禁的字面算术」，**不满足交付标准的内容要求**，且分差本身建立在一个**按规范不得计分**的上游故障上。

> ✅ **门禁脚本已按规范修正（2026-10-06 08:22），复评判定：`qualified = false`（两种口径一致）。**
> 修正后 `valid_scored_result()` 同时校验 agent 阶段（`SKILL.md:151`），3 条上游故障运行被正确剔除；QWEN 的合法成绩恢复为 **3**（三轮合法满分）→ `3 > 3` 不成立 → **区分度不达标**。
> 修复详情见 `deliverables/2026-10-06_win-summary-agent-gate-fix/FIX_REPORT.md`。
>
> **本轮的"不通过"是确定结论，不再有悬念**：原判"通过"完全依赖那道被误计分的超时故障轮。

**两条独立缺陷，任一条都足以否定本轮通过：**

| # | 缺陷 | 证据 |
| --- | --- | --- |
| **①** | **分差来自 provider 故障分**。QWEN 的 0 分不是候选失败，是上游 3 次超时导致 agent 在 turn 8 掐断，verifier 对**未修改的 workspace** 判 0 | `agent.summary = "model error: TimeoutError: The read operation timed out"`；`agent.log` 连续 3 条 `!! model call attempt N failed: TimeoutError`；turn 8 时仍在 `list_dir`，**一次 `write_file` 都没发生** |
| **②** | **制造分差的变量不在交付物里**。`MAX_AGENT_TURNS = 24` 是**本地评测脚手架**的私有常量 | `runner.py:59`（不在 ZIP 内）；`task.toml [agent]` 只有 `timeout_sec`，**无 turn 字段**；`instruction.md` grep turn/budget **零命中**；ZIP 内容仅 `environment/ instruction.md task.toml tests/` |

**规范依据**（`generate-win/SKILL.md`）：
- **第 151 行**：「Provider, authentication, gateway, malformed-response, environment, runner, and verifier-infrastructure failures **are not valid scored runs. Diagnose and retry them; do not turn them into score `0`.**」→ run02 属 provider 故障，**不得计 0**。
- **第 162 行**：区分度不足的整改手段是「**adjust the task surface** or choose a new non-duplicate candidate」→ **不含**调整 runner 的步数预算。
- 另有 `skills/harbor-windows/SKILL.md:188`：「**模型门槛不能覆盖数据质量门槛，不得为造分差增加未声明要求或冷门陷阱**」；同一文档第 182-186 行亦强调验证分工的边界，反对用脚手架侧手段替代题目本身的难度。

**若按规范剔除故障轮并重跑**：QWEN 在 24 轮预算下 run01/run03 **均满分**，重跑大概率仍为 1 → `sum(QWEN) = 3 = sum(OPUS) = 3` → **平手 → 不通过**。

---

## 1. 已核实的事实（数据本身有效，仅结论需修正）

### 1.1 o7 — OPUS ×3（✅ 全 `VALID`）

| run_id | verdict | test.report.status | agent.turns | agent.status | duration |
| --- | --- | --- | --- | --- | --- |
| `20261005T232059-candidate-opus-5-01` | 1 | VALID | 10 | completed | 400.7s |
| `20261005T232740-candidate-opus-5-02` | 1 | VALID | 13 | completed | 1102.3s |
| `20261005T234602-candidate-opus-5-03` | 1 | VALID | 8 | completed | 451.7s |

→ `sum(OPUS) = 3`，三轮**全部自然收敛**（8–13 轮），合规。

### 1.2 q7 — QWEN ×3

| run_id | verdict | test.report.status | agent.turns | agent.status | 合规性 |
| --- | --- | --- | --- | --- | --- |
| `20261005T232059-…qwen-01` | 1 | VALID | 24 | max_turns | ✅ 合规（用尽预算后被 verifier 判分） |
| `20261005T235615-…qwen-02` | **0** | VALID | 8 | **error** | ⛔ **provider 故障分，应剔除重跑** |
| `20261006T004405-…qwen-03` | 1 | VALID | 24 | max_turns | ✅ 合规 |

→ 合法口径下 QWEN 已有 **2 个**有效轮（均满分），第 3 轮因故障作废。

---

## 2. 脚本盲区（根因，可复用教训）—— ✅ 已于 2026-10-06 08:22 修复

`generate-win/scripts/summarize_model_runs.py` 的 `valid_scored_result()` **只检查 verifier 层**：

```
report.status == "VALID" and verdict in (0,1) and report.score == verdict
and report.task_id/version 匹配 and test_log_sha256 存在
```

**完全不检查 `agent.status`**。于是 `agent.status == "error"`（provider 故障）的运行被当作合法 0 分吸收进 `score_sum`。

全库扫描（`runs/wfflab__wreparse-217`，共 51 份 `result.json`；`agent.status` 分布 = `completed 19 / max_turns 11 / error 2 / no_tool_call 1 / None 18`）：

| 模型 | run | verdict | agent.status | summary |
| --- | --- | --- | --- | --- |
| QWEN | `20261005T235615-…-02`（第 7 轮） | 0 | error | `model error: TimeoutError: The read operation timed out` |
| GLM | `20261005T163942-…glm-5.3-01` | 0 | error | `model error: TimeoutError: The read operation timed out` |
| KIMI | `20261005T133112-…kimi-k3-01` | 0 | no_tool_call | 输出正文但未发工具调用（malformed response） |

**共 3 例，均被计为合法分**（2 例上游超时 + 1 例 malformed response）。GLM / KIMI 只作可运行性体检、不参与区分度判定，故影响较小，但属同类缺陷。

> ✅ **修法已实施**（2026-10-06 08:22）：`valid_scored_result()` 增加 `agent.status ∈ {completed, max_turns}` 判据，把 `error` / `no_tool_call` / `None` 排除出计分集合；controls（不经过 agent）豁免。回归验证未误伤任何 `completed` / `max_turns` 运行。详见 `FIX_REPORT.md`。

---

## 3. 「24 轮」作为区分度手段的实质问题

`runner.py:48-59` 的注释把步数预算称为 **"a first-class part of the task"**，设计依据是：

> OPUS finishes in 4 / 16 / 14 turns, QWEN needs 31 / 72 / 42. The two distributions do not overlap. 24 sits in the gap.

**本轮实测否证了该设计依据**：

| 项 | 设计假设 | 第 7 轮实测 |
| --- | --- | --- |
| OPUS | 4 / 16 / 14 轮 | 10 / 13 / 8（一致 ✅） |
| QWEN | **31 / 72 / 42 轮** | **24 / 8 / 24** |
| QWEN 结果 | 因超预算被截断而失分 | **两轮截断后仍各拿满分**；唯一的 0 分来自上游故障，**与轮数无关** |

即：**24 轮既没有卡住 QWEN（截断后仍满分），也没有产生有效难度信号**。全库 QWEN candidate 中 `verdict=1` 共 8 次，`verdict=0` 仅 1 次（即上述故障轮）——**天花板效应严重，区分度不具稳健性。**

**且即便 24 轮真能区分，也无法交付**：接收方拿到的是四件套 ZIP（不含 runner），`task.toml` 也无 turn 字段 → 接收方按自身 harness 的默认预算运行，该参数**不会随包传递**，区分度在接收方环境下不复现。

---

## 4. 汇总口径（保留证据）

### 4.1 修正前（有缺陷的门禁）

| 口径 | `--after` | QWEN sum | OPUS sum | `opus_sum_greater_than_qwen` | qualified | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| A 无 | — | 2（含故障轮） | 3 | true | true | 02:05 初版据此判"通过"——**未识别故障轮** |
| A′ 无（q7 未跑完时） | — | 2（混入第 6 轮） | 3 | true | true | **假阳性**（历史轮次凑数） |
| B 带 epoch | `15:20:59Z` | 2 | 3 | true | false | controls 被过滤 |

### 4.2 修正后（权威口径，2026-10-06 08:22 复评）

| 口径 | `--after` | QWEN sum / valid | OPUS sum / valid | 故障剔除 | controls | `opus>qwen` | qualified |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **A 全库**（权威"最佳证据"） | — | **3**（3/3 合法） | **3**（3/3） | **3** | 3+3 ✅ | **false** | ⛔ **false** |
| B 第 7 轮 pinned | `15:20:59Z` | 2（2/3，1 条故障剔除） | 3（3/3） | 1 | 0 ❌ | false | ⛔ **false** |

- **A 口径**：四模型齐全、controls 3+3 通过，但有**两项**不满足：① **区分度**（3 = 3 平手）—— 本轮最本质的失败原因；② 未固定 qualification epoch（跨轮次混选，违反 `qualification-gates.md`「Only results created after that timestamp may enter the official set」）。
- **B 口径**：第 7 轮**不构成完整 epoch** —— controls 最后一次运行在 `10-05 14:30`、GLM 在 `21:31`、KIMI 在 `21:38`，**均早于 23:20:59 的起跑时刻**，故 pinned 口径下这三项全为空。
- 两个口径的 `qualified` 均为 **false**，且**各有独立的失败理由** —— 无论从哪个角度判定，本轮都不可交付。

> `generate-win/SKILL.md:153` 要求「Run `summarize_model_runs.py` **with the qualification epoch**」；第 232 行要求「every selected Oracle/NOP result has matching … **current qualification epoch**」。即 **controls 与模型矩阵应在同一 epoch 内**。第 7 轮只跑了模型矩阵，controls / GLM / KIMI 沿用旧轮次——虽然 `MAX_AGENT_TURNS` 对 controls 无影响（`no-change`/`golden` 模式**不经过 agent**，见 `runner.py:769-774`），但 epoch 一致性仍不满足规范字面要求。

> `generate-win/SKILL.md:153` 要求「Run `summarize_model_runs.py` **with the qualification epoch**」；第 232 行要求「every selected Oracle/NOP result has matching … **current qualification epoch**」。即 **controls 与模型矩阵应在同一 epoch 内**。第 7 轮只跑了模型矩阵，controls 沿用第 4 轮（14:28/14:29）——虽然 `MAX_AGENT_TURNS` 对 controls 无影响（`no-change`/`golden` 模式**不经过 agent**，见 `runner.py:769-774`），但 epoch 一致性仍不满足规范字面要求。**补跑 3+3 controls 成本极低（约 90 秒），应补。**

---

## 5. 已产出产物（现行状态）

| 文件 | 状态 |
| --- | --- |
| `evidence/score_summary.png`、`oracle_nop_controls.png` | ✅ **已于 08:23 用修正后门禁重新渲染**（显示 `NOT READY`、新增 `Agent fail` 列、`Agent-stage failures excluded: 3`），取代此前基于口径 A 的旧图 |
| `evidence/model_runs_summary_r7.json` | ⚠️ 仍是**修正前**口径 A 的原始快照，**仅作历史记录**；权威数据见 `deliverables/2026-10-06_win-summary-agent-gate-fix/evidence/summary_all_unpinned.json` |
| `package/wfflab__wreparse-217-v1.0.0.zip` | ⛔ **不对外提交**。ZIP 结构本身合规（单一 root、恰好四件套、21 文件哈希与源一致、sha256 `0c13cccf…b403b405`），但本轮未通过资格门禁 |

**本轮无交付物** —— 按规范不打包、不写飞书。

题包 `harbor-windows/wfflab__wreparse-217/**` **零写入**（已用 mtime 核验：最新为 10-05 14:15，无 10-06 写入）。

---

## 6. 建议的下一步（待用户决策）

1. ✅ **脚本盲区已修**（2026-10-06 08:22）：`valid_scored_result()` 现同时校验 `agent.status ∈ {completed, max_turns}`，`error` / `no_tool_call` / `None` 一律不计分；证据截图同步新增 `Agent fail` 列。详见 `FIX_REPORT.md`。
2. ✅ **无需重跑即可定论**（节省约 2 小时）：全库 QWEN **合法**计分轮共 8 个、`verdict` **全部为 1**（唯一那个 0 分正是被剔除的超时故障轮）。即"QWEN 天花板 = 3"已被反复证实，重跑第 3 个名额只会再得 1 分 → `3 = 3` 平手是稳定结论，不是运气问题。
   > 若后续仍需一个形式完整的 epoch（controls + 四模型同批），再补 3+3 controls + GLM/KIMI 体检即可；但这**不会改变判定结果**。
3. **整改方向**（规范第 162 行）：**adjust the task surface** —— 当前题面对 QWEN 过易（历史近乎全满分）。可选项：
   - 提高 `docs/REPARSE-CONTRACT.md` 行为规格的复杂度与边界密度（**必须同步提高 `tests/rubric.json` 覆盖**，且不得增加未声明要求）；
   - 或按规范「choose a new non-duplicate candidate」换题。
   - ⛔ **不建议**继续下调 `MAX_AGENT_TURNS` 来制造分差：既不入交付物，又接近「为造分差增加未声明要求」的红线；第 7 轮已实测它**卡不住 QWEN**（截断后仍满分）。
4. **飞书写回继续暂停**（本轮未通过，无交付物可写）。

> **补充**：关于"候选模块导入失败是否应把 INVALID 归一到 0 分"—— 本轮全库 7 条 `INVALID` 的原因**全部**是 `verifier produced no result.json`（infrastructure），**无一例**候选产物损坏；按 `SKILL.md:151` 的判据（verifier 是否正常完成），正确处置是重跑而非计 0。若将来真的出现候选导致的 verifier 崩溃，正解是**在 verifier 内 try/except 包裹候选产物导入并输出 `VALID + verdict=0`**，而非在 runner/汇总层做笼统归一。详见 `FIX_REPORT.md` §5。

---

*本简报只读取日志、`result.json` 与规范原文；对 `harbor-windows/wfflab__wreparse-217` **未做任何写入**。*
