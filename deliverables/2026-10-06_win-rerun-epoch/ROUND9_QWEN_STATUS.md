# 第 9 轮（QWEN 探针）：单独压测 QWEN 天花板 —— `wfflab__wreparse-217`

> 启动：**2026-10-06 12:49:25 (+08)**
> 工作区：`deliverables/2026-10-04_outside-harbor-win/runner`
> 题包：`harbor-windows/wfflab__wreparse-217`（24 项检查，`MAX_AGENT_TURNS = 80`）
> 上游任务说明：用户指令 —— **"先测 qwen 的；qwen 没有全满分，再找我提供新 opus 端点"**

## 0. 为什么要单独测 QWEN

第 8 轮的判定是 `qualified=false`，两条独立原因：

1. **OPUS 2 = QWEN 2 平手**（门禁要求 `sum(OPUS) > sum(QWEN)`，平手即 FAIL）；
2. **QWEN 有效轮不足**（3 轮中第 3 轮被 `TimeoutError` 掐断并剔除，只剩 2 个有效轮）。

第 8 轮已知的 QWEN 有效轮**两轮都是 1.0**（25 / 31 轮自然收敛）。若 QWEN 的 3 个有效轮全部满分，则 `sum(QWEN) = 3` —— 而每轮上限是 1，门禁退化为 `sum(OPUS) > 3`，**数学上无解**。

> 所以本轮的唯一目的是：**把 QWEN 的 3 个有效轮跑齐，检验它到底是不是恒满分。**
> - 若**存在任何一轮 < 1** → `sum(QWEN) ≤ 2`，此时若有健康的 Opus 5 端点（OPUS 拿 3），门禁**可通过** → **再找用户要端点凭据**；
> - 若**三轮全满分** → 在当前 Opus 端点下这道题**不可通过** → 唯一出路是**换题**。

## 1. 本轮变量（相对第 8 轮）

| 项 | 第 8 轮 | 第 9 轮 | 说明 |
| --- | --- | --- | --- |
| 题包 `tests/` | 24 项 | **24 项（不变）** | 本轮**不加固**、不引入新变量 |
| `MAX_AGENT_TURNS` | 80 | **80（不变）** | 保持第 8 轮基线 |
| 模型范围 | QWEN+OPUS+GLM+KIMI | **仅 QWEN** | 用户指令：先只测 QWEN |
| 轮数 | 3 | **3** | 门禁标准口径 |

> 除模型范围外，端点、环境、依赖、评分规则、工具权限与第 8 轮**完全一致** —— 满足 `08-model-validation.md` 的「同一 base／环境／依赖／测试树／评分规则」要求。

## 2. epoch 归属

**沿用第 8 轮 epoch：`2026-10-06T00:59:28+00:00`。**

理由：题包**零改动**（仍 24 项），本轮只是**补跑第 8 轮被剔除的故障轮 + 增加 QWEN 样本**，属 `qualification-gates.md` 意义上的 *retry*，而非 material change，因此**不新建 epoch**。controls（第 8 轮 09:00–09:03 跑，no-change 0 + golden 1，3+3 全 VALID）在本 epoch 内**继续有效，无需重跑**。

## 3. 分片

| 计划任务 | tag | 内容 | 起跑 |
| --- | --- | --- | --- |
| `oh-r9-qwen` | `r9q` | **QWEN × 3** | 12:49:25 |

**未启动** OPUS / GLM / KIMI / controls 分片（按用户指令，只测 QWEN）。

> ⚠️ 编排坑已规避：本次注册任务时把 `-Once -At` 触发器设到 **+1 天**，只靠 `Start-ScheduledTask` 启动 —— 避免第 8 轮出现过的「触发器二次执行」（详见 `ROUND8_STATUS.md` §8）。

## 4. 判定命令（跑完后执行）

```powershell
$py = "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
$sk = "C:\Users\Administrator\Desktop\generate-win"
$rn = "C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner"

& $py "$sk\scripts\summarize_model_runs.py" --workspace-root $rn --task-id wfflab__wreparse-217 `
      --control-runs 3 --after "2026-10-06T00:59:28+00:00" --output "$rn\logs\_r9summary.json"
```

判定要点：
1. `models.QWEN.valid_count` 是否 = **3**（若又出现 `error` 故障轮 → 仍是 spec 定义的"无效运行"，须重跑，**不得计 0**）；
2. `models.QWEN.scores` —— **本轮要回答的核心问题**：是否 `[1,1,1]`；
3. `models.QWEN.excluded_agent_failures` —— 若有，逐条记录 `agent_status` 与 `summary`；
4. 注意：脚本取每模型**最后 N 个 valid**，故新跑的 3 轮（12:49+）会覆盖第 8 轮的旧 2 轮。

## 5. 时间线

| 时刻 (+08) | 事件 |
| --- | --- |
| 12:48 | 前置检查：无遗留 `run_matrix` / `runner.py` 进程、无残留 `oh-*` 容器；引擎 `windows/29.7.2` |
| 12:49:07 | 确认题包 24 项、`MAX_AGENT_TURNS = 80`、`runner/tasks` junction 正常 |
| 12:49:25 | 注册并启动 `oh-r9-qwen`（QWEN×3），容器 Up |
| 13:34:05 | **run01 完成** — agent `completed`／turns=32／tool_calls=45；**verdict=0**（`status=VALID`，weighted=0.2，checks 12/24）；run02 随即起跑 |
| 14:30 | **本轮自动化巡检** — `matrix-r9q.done` **未生成**；run02 进行中（Windows 容器 `oh-…-02` **Up 57 min**，agent 已至 **turn 16/80**，14:29:52 仍在写 `Walker.ps1`）；run03 **未起**。**未启动任何新分片**（遵守同 key 串行约束） |
| 14:43:10 | **run02 完成** — agent `completed`／turns=23／tool_calls=32；**verdict=1**（`status=VALID`，weighted=**1.0**，checks **24/24**，0 失败），duration 4144.7 s（≈69 min）；run03 随即起跑 |
| 15:28 | **二次巡检** — `matrix-r9q.done` **仍未生成**；run03 进行中（容器 `oh-…-03` **Up 46 min**，agent 至 turn 8+，正处理 `environment/workspace` 探索阶段）。**未启动任何新分片** |
| 15:34 | **三次巡检** — `matrix-r9q.done` **仍未生成**；run03 进行中（容器 `oh-…-03` **Up 50 min**，agent 仅至 **turn 9/80**，15:33:44 仍在写 `agent.log`，正读 `docs/REPARSE-CONTRACT.md` 第 79–152 行）。runner 存活：计划任务 `oh-r9-qwen` `State=Running`、`python.exe` PID 66728（12:49:26 起）。`TimeoutError` 计数**仍为 3**（未新增）。**未启动任何新分片** |
| 15:40 | **四次巡检** — `matrix-r9q.done` **仍未生成**；run03 推进至 **turn 15/80**（15:39:16 仍在写日志，正改写 `WReparse/Audit.ps1`：实现稳定归并排序与序数比较），`TimeoutError` **仍 3 次未新增**。**未启动任何新分片** |

> ⚠️ **run03 端点抖动告警**：run03 `agent.log` 已出现 **3 次** `!! model call attempt N failed: TimeoutError: The read operation timed out`（turn 6 一次、turn 8 连续两次）。若重试耗尽被掐断，run03 将被记为 `agent.status=error` → 按门禁**剔除**（不得计 0），有效轮退化为 2 个。目前容器仍 `Up`、日志仍在写，**尚未中断**。

**运行器存活核对（14:30）**：`oh-r9-qwen` 计划任务 `State=Running`；Windows 侧 `python.exe` (PID 66728, `runner.py … --models QWEN --keep-work`) 与两层 powershell 包装器均存活 → **runner 正常，非中断**。

> ⚠️ 巡检坑：本题 runner 用的是 **Windows Docker Desktop 上下文**（`docker ps` 见 `oh-…-02` `Up`）。若误在 **WSL 内** 执行 `docker ps -a` 会得到**空列表**，从而**误判 runner 已死**。核对容器状态务必在 Windows 侧 `docker ps`。

**预计完成**：QWEN 单轮实测 21–56 min（第 8 轮 25 轮 21 min、31 轮 56 min），3 轮串行约 **1.5–2.5 h** → 预计 **14:20–15:20** 收尾。
**修订（14:30 观测）**：run02 明显偏慢（56 min 才到 turn 16，约 3.5 min/turn）→ 单轮可能拉长到 ~1.5–2 h，收尾乐观估计顺延至 **16:00–18:00**，仍在 automation 窗口（`validUntil 22:00`）内。

### 5.1 已完成轮次初步观察（run01）—— **合法计分的 0 分**

| 字段 | 值 |
| --- | --- |
| run_id | `20261006T124926-candidate-qwen3.8-max-0902-01` |
| `agent.status` | **`completed`**（32 轮，未触 80 上限；非 `error` / `no_tool_call`） |
| `agent.turns` / `tool_calls` | 32 / 45 |
| `agent.changed_workspace` | `true`（模块 5 文件确已改写，13:14–13:31 落盘） |
| `duration_seconds` | 2678.8（≈44.6 min） |
| `verdict` / `status` | **0** / **`VALID`** |
| `weighted_score` | 0.2 |
| `checks` | **12 / 24 通过**（12 失败） |
| 失败项 | `traversal-safety`(0.2)、`containment`(0.15)、`link-target-resolution`(0.15)、`entry-classification`(0.2)、`enumeration`(0.1) 五条 rubric 全失；`determinism`/`accounting`/`diagnostics` 通过 |

**0 分性质判定：真实实现缺口，非 harness 误判、非 provider 故障。** 依据：失败详情呈「`record plain.txt / hardlink.txt / link-in / link-rel … is missing`」+「未产生 `too_deep` / `cycle` / `broken_target` 错误」——即产出的报告**基本无 records、无 errors**；而 schema 类检查（`schema-version-is-reported`、`error-list-is-stably-sorted`、`records-are-sorted-by-contract-order`、`report-is-byte-identical`、`canonical-path-*` 等）仍 PASS，说明报告**存在且可解析**，只是缺内容 → 属候选产物自身缺陷，按门禁口径 **必须计 0**，**不得剔除**。

> **初步结论（待 run02/run03 收口后由 §6 正式结算）**：QWEN 已出现 **1 个 `VALID` + `agent completed` 的 0 分轮**，只要该轮计入，则 `sum(QWEN) ≤ 2` —— 已命中用户条件分支「**存在任一有效轮 verdict=0**」。若 run02/run03 再出现 0，结论只会更稳固。这与第 8 轮"QWEN 有效轮两轮全 1.0、天花板恒 3"的假设**相反**。

### 5.2 收尾时间线（含末次复核）

| 时刻 (+08) | 事件 |
| --- | --- |
| 15:40 | **四次巡检** — `matrix-r9q.done` 仍未生成；run03 推进至 turn 15/80（15:39:16 仍在写日志，正改写 `WReparse/Audit.ps1`：实现稳定归并排序与序数比较），`TimeoutError` 仍 3 次未新增。**未启动任何新分片** |
| 16:15:38 | **分片完成** — run03 `verdict=1 status=VALID`（turn 44，duration 5548.5 s ≈ 92.5 min，agent `completed`）；`QWEN exit=0 elapsed=12,373s`；`matrix-r9q.done` 生成 |
| 16:28 | **正式结算** — 运行 `summarize_model_runs.py`（sha256 `ba623ff0…cc634f` ✓，带 `--after "2026-10-06T00:59:28+00:00"`）→ `logs/_r9summary.json`；结论回填 §6 |
| **19:08** | **收口复核（本自动化末次触发）** — 复核 `matrix-r9q.done` 已存在（16:15:38）、`logs/_r9summary.json` 与 §6 判定齐备且数据一致（`models.QWEN.scores=[0,1,1]`、`score_sum=2`、`valid_count=3`）→ 确认第 9 轮**已收口**。本次未启动任何新分片、未改动题包任何文件。同期第 10 轮（OPUS×3+GLM×1）已于 19:08:13 跑完，独立结算详见 `ROUND10_OPUS_GLM_STATUS.md` |

## 6. 判定结果

### 6.1 正式结算（2026-10-06 16:28，epoch `2026-10-06T00:59:28+00:00`）

> **★ 核心结论："QWEN 是否 3 轮全满分" →  否。`scores = [0, 1, 1]`，`score_sum = 2`。**
> run01 是合法 0 分（VALID + agent completed，不可剔除）⇒ 命中用户条件分支「**存在任一有效轮 verdict=0**」→ 下一步：**请用户提供健康的 Opus 5 端点凭据**，再跑 OPUS×3 完成门禁。
> 第 8 轮"QWEN 天花板恒 3、门禁数学无解"的推断**被证伪** —— QWEN 实际存在 0 分波动（85 轮样本中 3 个 valid 轮 = [0,1,1]）。

**QWEN（本轮探针主体）**：`required=3 / valid_count=3`（r9q 三轮全部有效，无剔除）、`scores=[0,1,1]`、`score_sum=2`、`excluded_agent_failures`（r9q 范围内）**为空**。

| # | run_id | agent_status | turns | duration | verdict | checks | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | `…124926-…-01` | `completed` | 32 | 2678.8 s | **0** | 12/24 | 失败：traversal-safety / containment / link-target-resolution / entry-classification / enumeration（真实实现缺口，合法计 0） |
| 02 | `…133405-…-02` | `completed` | 23 | 4144.7 s | **1** | 24/24 | 全过 |
| 03 | `…144310-…-03` | `completed` | 44 | 5548.5 s | **1** | 24/24 | 全过（曾 3 次端点 Timeout，均重试成功，未影响计分） |

> 脚本全库口径备注：QWEN epoch 内 `valid_count=5 / attempt_count=6`（含第 8 轮 2 个 valid 轮与 1 个 error 轮），按"每模型最后 N 个 valid"取数规则，`selected` 即本轮 r9q 三轮 —— 探针结论不受旧轮次污染。

**汇总 `gates`（全库口径，供参考；本轮非交付轮）**：

| gate | 值 |
| --- | --- |
| `controls_passed` | **true**（no-change 0×3 + golden 1×3，全 VALID） |
| `model_counts_complete` | false（GLM 0/1，其轮次 `agent.status=error` 剔除） |
| `opus_sum_greater_than_qwen` | **false**（2 > 2 平手 → FAIL） |
| `task_version_consistent` | true（1.0.0） |
| `epoch_pinned` | true |
| `agent_failures_excluded` | 2（QWEN 第 8 轮 TimeoutError 轮、GLM HTTP 429 轮，均不计分） |
| `qualified` | **false** |

**其他模型（第 8 轮遗留，沿用）**：OPUS `[0,1,1]` sum=2（run01 失败项 `link-target-resolution`，turns 8）｜KIMI `[1]` sum=1｜GLM 0/1（error 剔除）。

**门禁走向预演（供下一步参考）**：`sum(QWEN)=2` 已锁死。若换健康 Opus 5 端点后 OPUS 三轮全 1 → `3 > 2` **可通过**；OPUS 复现 2 分 → `2 > 2` 仍 FAIL。另需注意 GLM 缺轮（`model_counts_complete=false`）在正式结算轮须补跑 1 轮。

## 7. 下一步（按用户指令的条件分支 — 已命中第一分支）

- ✅ **已命中：「QWEN 未能全满分（run01 = 合法 0 分）」→ `sum(QWEN) = 2` → 请用户提供健康的 Opus 5 端点凭据**（规范指定的 `api.blvr.top` 当前无 key；`api.ebondai.com` 逐检查错误率 6.57% vs QWEN 0.41%），随后跑 OPUS×3 完成门禁。若 OPUS 三轮全 1 → `3 > 2` 通过；若仍 2 分 → 平手 FAIL，届时改**换题**。
- ~~若 QWEN 三轮全满分~~ → 未发生（已被本轮证伪），换题分支暂不触发。
- 补充：正式交付轮还需补跑 GLM×1（第 8 轮轮次被 error 剔除，`model_counts_complete=false`）。
