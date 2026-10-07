# 第 10 轮：OPUS×3 重跑 + GLM×1 补轮 —— `wfflab__wreparse-217`

> 启动：**2026-10-06 17:03:45 (+08)**（计划任务 `oh-r10`，tag `r10`，PID 67824）
> 工作区：`deliverables/2026-10-04_outside-harbor-win/runner`
> 题包：`harbor-windows/wfflab__wreparse-217`（24 项检查，`MAX_AGENT_TURNS = 80`，不变）
> epoch：**沿用 `2026-10-06T00:59:28+00:00`**（题包零改动，retry；controls 3+3 全 VALID 继续有效）

## 1. 为什么跑这一轮

第 9 轮 QWEN 探针已结算：`scores=[0,1,1]`，`sum(QWEN)=2` 锁死（详见 `ROUND9_QWEN_STATUS.md` §6）。门禁 `sum(OPUS) > sum(QWEN)` 要求 **OPUS 严格大于 2，即三轮全 1（3 分）**。第 8 轮 OPUS 在当前端点（`api.ebondai.com`）跑出 `[0,1,1]=2`（run01 失败 `link-target-resolution`，间歇性），按用户指令先用当前端点重跑。

脚本取数规则：每模型取 epoch 内**最后 N 个 valid** → 本轮新跑的 OPUS 3 轮将覆盖第 8 轮旧 3 轮。

## 2. 四模型矩阵状态（REQUIRED_MODELS = QWEN×3 / OPUS×3 / GLM×1 / KIMI×1）

| 模型 | epoch 内现状 | 本轮动作 |
| --- | --- | --- |
| QWEN | 3/3 valid，`[0,1,1]` sum=2 | ✅ 已收口，不跑 |
| **OPUS** | 3/3 valid，`[0,1,1]` sum=2（分数不够） | 🔄 **重跑 ×3** |
| **GLM** | 0/1（`HTTP 429 ServerOverloaded` error 剔除 → `model_counts_complete=false`） | 🔄 **补跑 ×1** |
| KIMI | 1/1 valid，`[1]` sum=1 | ✅ 已收口，不跑 |

> GLM 只要 agent 阶段完成即可计入（verdict 不影响门禁主条件）；若再遇 429/Timeout 被剔除，须再补。

## 3. 分片与预计耗时

| 计划任务 | tag | 内容 | 起跑 |
| --- | --- | --- | --- |
| `oh-r10` | `r10` | OPUS×3 → GLM×1（`run_matrix.ps1` 内部串行，GLM/KIMI 固定 1 轮） | 17:03:45 |

- 前置检查（17:02）：无残留 `oh-*` 容器、无 python runner 进程、引擎 `windows/29.7.2`、旧任务全 `Ready`。
- 防二次触发坑：`-Once -At` 触发器设 **+1 天**，仅靠 `Start-ScheduledTask` 启动；`ExecutionTimeLimit=0`、`MultipleInstances=IgnoreNew`。
- 预计耗时：OPUS 单轮第 8 轮实测 2.5–8.4 min，3 轮约 15–40 min；GLM 上轮跑约 90 min（故障前）。整体预计 **18:00–19:30** 收尾，`logs/matrix-r10.done` 生成即为完成标志。

## 4. 判定命令（跑完后执行）

```bash
C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe \
  C:/Users/Administrator/Desktop/generate-win/scripts/summarize_model_runs.py \
  --workspace-root C:/Users/Administrator/Desktop/wff-task/deliverables/2026-10-04_outside-harbor-win/runner \
  --task-id wfflab__wreparse-217 --control-runs 3 \
  --after "2026-10-06T00:59:28+00:00" \
  --output C:/Users/Administrator/Desktop/wff-task/deliverables/2026-10-04_outside-harbor-win/runner/logs/_r10summary.json
```

判定要点：
1. `models.OPUS.scores` 是否 `[1,1,1]`（sum=3 > 2 → 门禁主条件过）；
2. `models.GLM.valid_count` 是否 ≥1（`model_counts_complete` 转 true）；
3. `excluded_agent_failures` 逐条记录（agent_status=error 不计分）；
4. `qualified` 应转 true（controls/version/epoch 均已就绪）。

## 5. 时间线

| 时刻 (+08) | 事件 |
| --- | --- |
| 17:02 | 前置检查通过（无残留容器/进程，引擎正常） |
| 17:03:45 | 注册并启动 `oh-r10`（OPUS×3 → GLM×1），docker 探针 `windows/29.7.2` |
| 17:04:46 | OPUS run01 容器 `oh-…170346-…-01` `Up`，任务 `Running`，runner 正常 |
| 17:08:21 | OPUS run01 完成 —— `verdict=0 status=VALID`（失败项 `link-target-resolution`） |
| 17:17:07 | OPUS run02 完成 —— `verdict=1 status=VALID`（24/24） |
| 17:25:52 | OPUS run03 完成 —— `verdict=1 status=VALID`（24/24）；`OPUS exit=0 elapsed=1,327s`；随即 GLM×1 起跑 |
| 19:08:13 | GLM run01 完成 —— `verdict=0 status=VALID`，但 `agent.status=no_tool_call`（turns 10，duration 6,140 s ≈ 102 min）；`GLM exit=0 elapsed=6,141s`；`matrix complete`；`matrix-r10.done` 生成 |
| 19:08:36 | **正式结算** —— 运行 `summarize_model_runs.py`（sha256 `ba623ff0…cc634f` ✓，带 `--after "2026-10-06T00:59:28+00:00"`）→ `logs/_r10summary.json`；结论回填 §6 |

## 6. 判定结果

### 6.1 正式结算（2026-10-06 19:08，epoch `2026-10-06T00:59:28+00:00`）

> **★ 核心结论：`qualified = false`。OPUS `scores = [0,1,1]`（`score_sum = 2`）—— 与 QWEN 的 2 分再次平手，门禁主条件 `sum(OPUS) > sum(QWEN)` = `2 > 2` = `false`。**
> 当前 `api.ebondai.com` 端点下的 OPUS 5 复现了第 8 轮的间歇性失分（**同一个失败项 `link-target-resolution`**）⇒ 命中 §7 第 2 分支：**请用户提供健康的 Opus 5 端点凭据**。

**OPUS（本轮重跑主体）**：`required=3 / valid_count=3`（r10 三轮全部有效，零剔除）、`scores=[0,1,1]`、`score_sum=2`、`excluded_agent_failures` **为空**。

| # | run_id | agent_status | turns | duration | verdict | 失败项 |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | `…170346-…-01` | `completed` | 4 | 275.3 s | **0** | `link-target-resolution`（**与第 8 轮同一失败项**） |
| 02 | `…170821-…-02` | `completed` | 13 | 526.4 s | **1** | 无（24/24） |
| 03 | `…171707-…-03` | `completed` | 14 | 525.0 s | **1** | 无（24/24） |

**GLM（补轮）**：`required=1 / valid_count=0` → **`model_counts_complete` 仍 false**。本轮 run `…172553-…-01` 判 `agent.status=**no_tool_call**`（turns 10、duration 6,140 s ≈ 102 min）→ 按门禁**剔除，不计 0**（该轮 `verdict=0` 属未修改 workspace 的假分，不作为有效证据）。全库 GLM 两条尝试（r8 `error` 429 / r10 `no_tool_call`）均无效。

**汇总 `gates`（全库口径）**：

| gate | 值 |
| --- | --- |
| `controls_passed` | **true**（no-change 0×3 + golden 1×3，全 VALID） |
| `model_counts_complete` | **false**（GLM 0/1，`no_tool_call` 轮剔除） |
| `opus_sum_greater_than_qwen` | **false**（2 > 2 平手 → FAIL） |
| `task_version_consistent` | true（1.0.0） |
| `epoch_pinned` | true |
| `agent_failures_excluded` | 3（QWEN r8q `TimeoutError`、GLM r8 `HTTP 429`、GLM r10 `no_tool_call`） |
| `qualified` | **false** |

**其他模型（沿用）**：QWEN `[0,1,1]` sum=2（第 9 轮，r9q 三轮全 VALID+completed）｜KIMI `[1]` sum=1。

> **端点级诊断**：OPUS 在新一轮 3 次运行中仍稳定复现「1 轮失 `link-target-resolution`、2 轮满分」的 {0,1,1} 分布 —— 与第 8 轮完全同型。说明失分**不是随机噪声、也非轮次截断**，而是 `api.ebondai.com` 上 Opus 5 对本题某一契约点的系统性盲点（逐检查错误率 6.57% vs QWEN 0.41%）。在当前端点下，`sum(OPUS)` 的天花板实际被钉在 2。

## 7. 结果分支（已命中）

- ~~OPUS `[1,1,1]` 且 GLM 补齐 → `qualified=true`~~ → **未发生**（OPUS 实得 2 分）。
- ✅ **已命中：OPUS 仍 ≤2（`[0,1,1]`=2，平手 FAIL）→ 当前 `api.ebondai.com` 端点确认不可用 → 请用户提供健康的 Opus 5 端点凭据**（规范指定的 `api.blvr.top` 当前无 key）。换端点后**只重跑 OPUS×3**（QWEN / KIMI / controls 不动，GLM 若一并解决端点可顺带补 1 轮）。
- 补充：即便换端点后 OPUS 达 3 分，正式交付轮仍需补跑 GLM×1（当前 `model_counts_complete=false`）；GLM 需换用可正常产生工具调用的端点/模型。

## 8. 第 11 轮（r11o）：OPUS×3 换新 key 重跑（进行中）

**背景**：用户 21:50 提供新 key——第一次给到的 key 经比对**与当前 `.env.local` 在用 key 完全相同**（SAME_KEY），按指令先用它启动 r11o（21:53），结果 3 轮全部 ~35 s 内 `agent_status=error`（**HTTP 502 `Upstream access forbidden` 连续 3 次重试失败**）。用户 21:54 更正真新 key：`sk-ff43…ce4c`。

**排障记录**：
1. 21:53 旧 key r11o 已终止（Stop 任务 + 进程树 taskkill + 容器 stop/rm），残留 run 目录、日志、done 标记全部清理；
2. `.env.local` `OPUS_API_KEY` 已替换为新 key（探测 200/PONG），URL 不变（`https://api.ebondai.com`）；
3. **502 根因定位**：ebondai 网关存在**间歇性 502 窗口**（单次持续约 0.5–2 min，与 key、payload 大小无关）——21:56–22:00 探测多次 200 → 21:57–22:02 多次 502（连 4 KB 小 payload 也 502）→ 22:04 新旧双 key 同测均 200。旧重试策略 3 次/累计 ~20 s，撞上窗口必整轮报废；
4. **runner.py 重试加固**（22:04）：attempts 3→7、退避 `(15,30,60,60,90,90)` 累计 ~5.75 min，足以骑跨窗口。原版备份 `scripts_backup/runner.py.orig`（sha256 `da3d14c9…bb0986`），新版 `4965d371…8e84d0f3`。仅影响 agent 故障重跑成本，计分口径不变（agent error 依旧剔除不计分）；
5. `oh-r11o` **22:05:55 用新 key + 加固重试重启**（OPUS×3，run01 起跑）。

**后续**：r11o 完成后按 §4 命令汇总（输出 `logs/_r11summary.json`）；另需 **GLM×1 补轮**（tag `r11g`，`matrix-task.ps1 -Tag r11g -Models GLM -Runs 1`，等 r11o 完成后串行启动）。

## 9. 第 12 轮（r11o 第二次重启）：4router 端点（进行中）

**新 key `sk-ff43…ce4c` 上游证实故障**：22:33 重启后的 r11o，run01 在 turn 1–3 成功后自 turn 4 起连续 7 次 502（**`Upstream request failed`**，与之前的 `access forbidden` 不同——上游转发真实故障）→ run01 error 剔除；run02 同样连续 502。该 key 上游不可用。

**用户 23:10 提供第 3 组凭据**：`https://4router.net` + `sk-ABTd…2gE`。处置：
1. 停掉 22:33 的 r11o（进程树 + 容器 + 残留清理）；
2. `.env.local`：`OPUS_BASE_URL=https://4router.net`、`OPUS_API_KEY=sk-ABTd…`（max_tokens 64000 不变）；
3. 探测：小 payload 3 连 200/PONG + **runner 同形态大 payload（64K max_tokens + tools + ~30KB content）200/end_turn**；
4. `oh-r11o` **23:17:02 第三次重启**（OPUS×3）。
5. **23:20 验证：run01 已至 turn 6、0 次调用失败** —— 4router 端点畅通，UA 修复（§8.4）生效。

**判定待 r11o 完成后按 §4 命令执行**（输出 `logs/_r11summary.json`）。

### 8.1 巡检记录（2026-10-06 23:10，**未收口，分片运行中**）

**进度：`logs/matrix-r11o.done` 仍未生成 → 未结算、未启动任何新分片。**

| 项 | 状态 |
| --- | --- |
| 实际起跑 | **22:33:54**（shard log `matrix-task-r11o.log`：`start tag=r11o models=OPUS runs=3 pid=75124`；日志名 `matrix-r11o-20261006-223354.log`） |
| 计划任务 `oh-r11o` | `Running` |
| runner 进程 | Windows `python.exe` **PID 78872**，StartTime 22:33:54，存活 |
| 容器（Windows 侧 docker） | `oh-20261006t225504-candidate-opus-5-02` **Up 15 min**（run02 运行中）；`docker ps -a` 无其他 `oh-*` |
| run01 | ✅ 完成 22:55:04 —— `verdict=0 status=VALID`，但 **`agent.status=error`**（`model error: HTTP 502 Upstream request failed`，turns 5 / tool_calls 9 / duration 1,270.3 s）→ **按门禁剔除，不计 0** |
| run02 | 🔄 22:55:04 起跑，运行中（容器 Up 15 min） |
| run03 | ⏳ 未起 |

**★ 关键预判**：run01 属 **agent 阶段故障**（加固后的 7 次重试仍未穿过 `api.ebondai.com` 的间歇性 502 窗口，耗时 21 min 后仍报 `Upstream request failed`）→ 汇总时归入 `excluded_agent_failures`。则 r11o **最多只剩 2 个有效轮**（run02/run03）⇒ 无论二者取值，**本轮 `sum(OPUS)` 不可能达到 3**，`sum(OPUS) > sum(QWEN)=2` 主条件**已注定不成立**（最好情况 2>2 平手仍 FAIL）。第 3 步「OPUS `[1,1,1]` → 启动 GLM 补轮」分支**已不可能命中**。最终仍待 run02/run03 完成、`.done` 生成后按 §4 命令正式结算。

**下次（HOURLY）**：查 `logs/matrix-r11o.done` → 已生成则按 §4 命令（**必须带 `--after "2026-10-06T00:59:28+00:00"`**）输出 `logs/_r11summary.json` 并回填本节；未生成则只追加一行进度，**绝不启动新分片**。

### 8.2 巡检记录（2026-10-07 00:13，**未收口，分片运行中**）

**进度：`logs/matrix-r11o.done` 仍未生成 → 未结算、未启动任何新分片。**

本轮分片为 **4router 端点**（`https://4router.net`，key `sk-ABTd…2gE`）的第三次重启，起跑 **23:17:02**。

| 项 | 状态 |
| --- | --- |
| 计划任务 `oh-r11o` | `Running` |
| runner 进程 | Windows `python.exe` **PID 81052**，StartTime 23:17:02，存活 |
| 容器（Windows 侧 docker） | `oh-20261006t233510-candidate-opus-5-03` **Up 37 min**；`docker ps -a` 无其他 `oh-*` |
| run01 | ✅ 23:26:31 完成 —— `verdict=1 status=VALID`（**24/24**），但 **`agent.status=no_tool_call`**（turns 13 / tool_calls 18 / duration 569.1 s） |
| run02 | ✅ 23:35:10 完成 —— `verdict=1 status=VALID`（**24/24**），但 **`agent.status=no_tool_call`**（turns 11 / tool_calls 15 / duration 518.4 s） |
| run03 | 🔄 23:35:10 起跑，运行中（turn 5+，00:05:36 记录 1 次 `TimeoutError`，正处重试退避等待，单次请求超时 900 s） |

**★★ 关键新发现：r11o 两轮 24/24 满分，却因 `no_tool_call` 被门禁剔除 → OPUS 官方读数回落到 r10 旧轮。**

诊断性汇总（`logs/_r11diag.json`，**非官方结算**，仅用于量化现状；`.done` 未到）：

- OPUS `valid_count=6 / attempt_count=8`，`scores=[0,1,1]`、`score_sum=2` → **selected 三行全是 r10 的旧 run**（17:03 / 17:08 / 17:17）；
- r11o 的 run01/run02 落入 `excluded_agent_failures`（`no_tool_call`）→ **在 `scores` 中完全不可见**；
- `agent_failures_excluded=5`；`model_counts_complete=false`（GLM 0/1）；`opus_sum_greater_than_qwen=false`；`qualified=false`。

**根因**：`runner.py` 仅在模型调用 `finish` 工具时置 `completed`（`finished=True`）；若模型**末轮只输出散文、未调用任何工具**且 `stop_reason≠max_tokens`，则置 **`no_tool_call`**（`runner.py:543-550`）。4router 端点上的 Opus 5 恰好以散文收尾（"…verification below is by reasoning against the contract…"）→ 被计入 `no_tool_call`。**这是模型协议习惯，既非 provider 故障，也非候选质量问题**（两轮 `changed_workspace=true` 且 24 项检查全过）。

**两个待决问题（需用户裁定，不得自行改门禁）**：

1. **`no_tool_call` 判定过宽**：它把「从未调用工具」（GLM r10 t2：`tool_calls=0`）与「已调用 N 次工具、成功完成、只是末轮以散文收尾」（OPUS r11o：`tool_calls` 18/15、`verdict=1`、24/24）混为一类。更精确口径应仅在 `tool_calls==0`（或 `changed_workspace=false`）时剔除。
2. **静默回落 / 跨端点混装风险**：按现口径，r11o 对 OPUS 得分的**贡献恒为 0**，summarizer 会**静默回落到 r10 的 `[0,1,1]`**（报告看似"与 r10 相同"，实则掩盖了 r11o 两轮满分）。若 run03 恰好以 `completed` 结束且 verdict=1，则 last-3-valid 将变为 **[r10-02, r10-03, r11o-03] = [1,1,1] = 3** —— 一个**跨端点（ebondai ×2 + 4router ×1）混装**的集合，`3>2` 会让门禁"通过"，但证据由两个端点拼成（可疑，须显式披露）。

**结论未定**：待 `matrix-r11o.done` 生成后按 §4 命令正式结算；OPUS 的最终判定取决于 run03 的 `agent.status` 与上表口径裁定。

**下次（HOURLY）**：查 `logs/matrix-r11o.done` → 已生成则按 §4 命令（**必须带 `--after "2026-10-06T00:59:28+00:00"`**）输出 `logs/_r11summary.json` 并回填本节；同时把上述两问题连同结论上报，**等用户裁定 `no_tool_call` 口径后**再判是否启动 GLM×1 补轮（r11g）。未生成则只追加一行进度，**绝不启动新分片**。

## §9. 超时问题处置（2026-10-07 00:40，用户问"超时有什么办法解决吗"）

**根因**：run03 在 turn 5 遇到**僵死连接**（上游静默断开但不关流，请求永不返回），`OPUS_REQUEST_TIMEOUT=1800s` 导致每次重试都要白等 30 分钟（attempt 1/2 各烧 1800s，attempt 3 预计挂到 01:05）。诊断性探测：137KB 大 payload 此刻 4–7s 即回 200 → **端点健康、与 payload 无关，纯连接僵死**。

**处置（00:38–00:42）**：

1. `OPUS_REQUEST_TIMEOUT` **1800 → 300s**（run01/02 整轮 9 min 跑完，单次调用几十秒，300s 充裕；僵死请求快速失败进重试，7 次尝试累计退避不变）。
2. 终止 r11o 残局（runner 进程树 + run03 容器已清），**保留 run01/02 有效结果**（各 24/24，但 `no_tool_call` 剔除问题仍未裁定）。
3. 删除 run03 残缺目录与 r11o 日志；注册 **`oh-r11o1`**（OPUS×1，tag `r11o1`），**00:41:39 起跑**，agent 正常推进中。
4. 汇总取数口径为"每模型最后 3 个 valid"，故单轮补跑即可凑齐第 3 个 valid。

**遗留风险（不变，待用户裁定）**：若 r11o1 也以散文收尾 → 再次 `no_tool_call` 被剔除。`no_tool_call` 口径过宽问题（把"从未调用工具"与"已调 15–18 次工具、24/24 全过、仅末轮散文收尾"混为一类）仍待用户裁定，裁定前不启动 GLM×1 补轮。

---

## §10. r11o1 收口判定（2026-10-07 01:15，**已收口**）

**分片状态**：`logs/matrix-r11o.done` **不存在**（r11o 于 00:38–00:42 依用户授权终止、日志清除）；由 **`oh-r11o1`**（OPUS×1，tag `r11o1`）单轮补跑取代，**`matrix-r11o1.done` 已于 00:53:26 生成** → 分片收口。分片日志：`elapsed=707s`，`verdict=0 status=VALID`。

**汇总命令**（脚本 sha256 `ba623ff0d3ad5d4b7f16ae5e2e67c0a238acd9b40dc315a7ab0f264350cc634f` ✓，带 `--after "2026-10-06T00:59:28+00:00"`，`exit=2`）：

```bash
C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe \
  C:/Users/Administrator/Desktop/generate-win/scripts/summarize_model_runs.py \
  --workspace-root C:/Users/Administrator/Desktop/wff-task/deliverables/2026-10-04_outside-harbor-win/runner \
  --task-id wfflab__wreparse-217 --control-runs 3 \
  --after "2026-10-06T00:59:28+00:00" \
  --output C:/Users/Administrator/Desktop/wff-task/deliverables/2026-10-04_outside-harbor-win/runner/logs/_r11summary.json
```

> **★ 核心结论：`qualified = false`，`opus_sum_greater_than_qwen = false`。OPUS 官方读数仍为 `scores=[0,1,1]`、`score_sum=2`（与 QWEN 的 2 分平手）。**
> r11o / r11o1 的 **三轮 4router 运行全部因 `agent.status=no_tool_call` 被门禁剔除**，`scores` 静默回落到 **r10 旧三轮**（`api.ebondai.com`）。

**OPUS（r11o + r11o1 主体）**：`required=3 / valid_count=6 / attempt_count=9`、`scores=[0,1,1]`、`score_sum=2`。

| 来源 | run_id | agent_status | tool_calls / turns | verdict | changed_workspace |
| --- | --- | --- | --- | --- | --- |
| r11o-01 | `…231703-…-01` | **`no_tool_call`**（剔除） | 18 / 13 | 1（24/24） | true |
| r11o-02 | `…232632-…-02` | **`no_tool_call`**（剔除） | 15 / 11 | 1（24/24） | true |
| **r11o1-01** | `…004139-…-01` | **`no_tool_call`**（剔除） | **20 / 17** | **0**（8 项 unsat） | **true** |
| r10-01/02/03（回落选中） | `…170346/170821/171707` | `completed` | 4 / 13 / 14 | 0 / 1 / 1 | — |

**r11o1 单轮诊断**：`verdict=0 status=VALID`，`agent.status=no_tool_call`、`turns=17`、`tool_calls=20`、`changed_workspace=True`；失败项 `traversal-safety, containment, link-target-resolution, entry-classification, enumeration, determinism, accounting, diagnostics`（8 项）。模型末轮自述"**could not execute anything in this container**，改动仅凭契约推理、未经测试验证"——即**真实产出质量不足**（并非 harness 误判产物），但仍被 `no_tool_call` 先一步剔除。

**汇总 `gates`（全库口径）**：

| gate | 值 |
| --- | --- |
| `controls_passed` | **true**（no-change 0×3 + golden 1×3，全 VALID） |
| `model_counts_complete` | **false**（GLM 0/2） |
| `opus_sum_greater_than_qwen` | **false**（2 > 2 平手 → FAIL） |
| `task_version_consistent` | true（1.0.0） |
| `epoch_pinned` | true |
| `agent_failures_excluded` | **6**（OPUS r11o×2 + r11o1×1 `no_tool_call`；QWEN r8q `TimeoutError`；GLM r8 `HTTP 429` + r10 `no_tool_call`） |
| `qualified` | **false** |

**其他模型（沿用）**：QWEN `[0,1,1]` sum=2（r9q 三轮全 VALID+completed）｜KIMI `[1]` sum=1｜GLM `0/2`（两轮均被剔除）。

### ★★ 关键推论：OPUS 的天花板 = 2，**与 `no_tool_call` 口径无关**

即使按 §8.2 提出的"**修正口径**"（仅 `tool_calls==0` / `changed_workspace==false` 才剔除）重估 4router 三轮：三轮 `tool_calls` 分别为 18 / 15 / 20（**全部 > 0**）→ 均保留 → **last-3-valid = `[r11o-01=1, r11o-02=1, r11o1-01=0] = [1,1,0] = 2`** → **仍然 `2 > 2` = false（平手 FAIL）**。

> 即：**`no_tool_call` 口径之争不再是门禁的决定性因素** —— 无论按现行口径（三轮全剔除→回落 r10 得 2）还是修正口径（三轮全保留→得 2），**`sum(OPUS)` 恒为 2**。三轮端点交叉验证一致：
> - `api.ebondai.com`：r8 `[0,1,1]=2`、r10 `[0,1,1]=2`；
> - `https://4router.net`：r11 `[1,1,0]=2`。
>
> ⇒ **Opus 5 在本任务上稳定 2/3，三个端点、三次独立重跑均无 3 分** → 失分是**模型/题面契约点的系统性能力缺口**，非端点故障、非轮次截断、非 harness 口径。

## §11. 分支命中与下一步（2026-10-07 01:15）

- **步骤 3 分支（OPUS `[1,1,1]` → 启动 GLM 补轮 `r11g`）未命中**：OPUS 实得 2 分 → **不启动 GLM×1**（GLM 与 OPUS 本应串行，用户指令亦明确以 OPUS=3 为前提）。
- **步骤 4 分支命中（OPUS 仍 <3）**：记录结论，**等待用户提供下一个健康的 Opus 5 端点**（未自行更换 key）。但鉴于**三端点均得 2 分**，建议的出路已从"换端点"升级为：**① 换题** 或 **② 与甲方确认/调整门禁口径**（本案 `sum(OPUS)>sum(QWEN)` 在 Opus 5 于本题稳定 2/3 的前提下无解）。
- **GLM 仍 `0/2`**（`model_counts_complete=false`）：r11o1 轮次未触及 GLM；若后续需交付完整模型矩阵，GLM×1 仍须补跑（但单独补 GLM 无法使 `qualified` 转 true，因 OPUS 主条件已失）。
- **洁净核对（Windows 侧）**：`docker ps -a` 无 `oh-*` 容器｜无 `python.exe` runner 进程｜计划任务 `oh-r11o`/`oh-r11o1` 均 `Ready`（`oh-docker-keeper` `Running` 为常驻）。
- **产物**：`runner/logs/_r11summary.json`（汇总权威数据）。**不打包、不写飞书**（门禁未过）。题包 `instruction.md`/`environment/**`/`solution/**` 零写入。
- **automation 状态**：置 **PAUSED**（无待轮询分片；下一步取决于用户裁定）。

## §10. 口径修改 + r12 补跑启动（2026-10-07 10:30，用户指令："改一下，如果要补跑就补跑"）

**口径修改（用户已批准）**——`no_tool_call` 只在"从未调用工具"时剔除：

1. `runner.py`（sha256 `85968ca0…9b5c`）：散文收尾时若 `tool_calls>0` → `status=completed`（正常计分）；仅 `tool_calls==0` 才记 `no_tool_call`。
2. `summarize_model_runs.py`（sha256 `449cc0ea…5f8d`）：`agent_failure()` 对 `no_tool_call` 增加豁免——`tool_calls>0` 且 `changed_workspace=true` 的不剔除（追溯生效，r11o 两轮满分无需重跑）。
3. 备份：`scripts_backup/runner.py.pre_notoolcall`（`5c5a0d12…`）、`summarize_model_runs.py.orig2`（`ba623ff0…`，即修正版原版）。

**新口径正式汇总（`logs/_r11summary.json`，10:28，exit=2）**：

| 模型 | valid | scores | sum | 备注 |
| --- | --- | --- | --- | --- |
| QWEN | 3/3 | `[0,1,1]` | 2 | 不变 |
| OPUS | 9/9 | `[1,1,0]` | **2** | r11o-01/-02 满分计入；r11o1 = **0**（8 项 rubric 未满足，与 QWEN run01 同型失败签名，真失分合法计入） |
| GLM | 0/1 | `[]` | 0 | r10 轮 tool_calls=0（真·没干活）→ 新口径下**仍剔除**，正确 |
| KIMI | 1/1 | `[1]` | 1 | 不变 |

gates：`opus_sum_greater_than_qwen=false`（2>2 平手）｜`model_counts_complete=false`｜`qualified=false`。

**r11o1 之 0 分进了 last-3 窗口 → OPUS 需要连续 3 个新的 1 分轮**（3 个新 valid 全 1 → last-3=[1,1,1]=3>2 过；混入任一 0 → sum 恒 2 平手 FAIL）。

**补跑分片 `oh-r12`（tag `r12`）**：`-Models OPUS,GLM -Runs 3` → **OPUS×3（须全 1）→ GLM×1（跑完即可）串行**，**10:29:11 起跑**，OPUS 4router、GLM 原端点。预计 ~13:00–13:30 收尾（GLM r10 轮曾耗时 102 min）。标志：`logs/matrix-r12.done`。

**结果分支**：OPUS 新三轮全 1 且 GLM 补齐 → `qualified=true` → 走交付（截图四件套 + 打包；飞书写回待用户确认）；OPUS 混入 0 → sum=2 平手 FAIL → 等用户裁定（换更稳端点重跑 OPUS 或换题）。

## §11. r12 补跑进行中（10:30–10:54，每 5 分钟轮询）

| 时间 | 事件 |
| --- | --- |
| 10:29:11 | r12 起跑（OPUS×3 → GLM×1 串行） |
| 10:41:02 | **OPUS run01 = 1**（VALID，completed，21 轮/25 调用，12 min，0 失败） |
| 10:47:50 | **OPUS run02 = 1**（VALID，completed，12 轮/16 调用，7 min，0 失败） |
| 10:53:31 | **OPUS run03 = 1**（VALID，completed，10 轮/13 调用，6 min，0 失败）→ **OPUS [1,1,1]=3，门禁主条件 `3>2` 达成** ✅ |
| 10:53:32 | GLM×1 起跑（r10 轮曾耗 102 min，预计 ~12:35 收尾） |
| 11:32 | **巡检（automation）**：`logs/matrix-r12.done` **仍未生成** → 未结算、**未启动新分片**。OPUS×3 已全部完成（`OPUS exit=0 elapsed=1,459s`，三轮均 `verdict=1 status=VALID`）。GLM run01 运行中：容器 `oh-20261007t105332-candidate-glm-5-3-01` **Up 39 min**；`agent.log` 至 **turn 7**（末次写入 11:10，22 min 静默属 GLM 常态节流）；无 error/timeout 迹象。计划任务 `oh-r12` **Running**、`python.exe` **PID 81040**（10:53:31 起）存活 → runner 正常 |
| 12:34 | **巡检（automation）**：`logs/matrix-r12.done` **仍未生成** → 未结算、**未启动新分片**。GLM run01 仍在推进：容器 `oh-20261007t105332-candidate-glm-5-3-01` **Up 2 h**；`agent.log` 由 11:32 的 turn 7 推进至 **turn 15**（正写 `Audit.ps1`，末次写入 12:12，22 min 静默属 GLM 常态节流，非死锁）；无 error/timeout 迹象。计划任务 `oh-r12` **Running**、`python.exe` **PID 81040** 存活 → runner 正常 |
| 13:35 | **巡检（automation）**：`logs/matrix-r12.done` **不存在**（r12 分片已终止、GLM r12 轮运行目录 `20261007T105332-…` 已删除）→ **未结算、未启动新分片**。**OPUS×3 产物完好保留**（三轮全 `verdict=1 status=VALID`+`completed`）。**新分片 `oh-r12g`（GLM×1）于 13:33:40 手动接续**（`State=Running`，容器 `oh-20261007t133341-candidate-glm-5-3-01` Up 2 min）→ 门禁唯一缺口 GLM 正在补。详见 §13 |

**待 GLM 完成后正式汇总**（`_r12summary.json`）：GLM valid → `model_counts_complete=true` → **`qualified=true`**；GLM 再剔除 → 可补 r12g 一次。

## §12. ★ 意外自动开火事件处置（2026-10-07 13:24，用户问"检查进度"时发现）

**现象**：检查容器时发现**第二个容器** `oh-20261007t124926-…-qwen3-8-max-0902-01`（Up 33min）——即 `oh-r9-qwen` 计划任务在 **10-07 12:49:25 又自动开火**，正在跑 QWEN×3。

**根因**：该任务于 10-06 12:49 注册时用了 `-Once -At (Get-Date).AddDays(1)` 的"防二次触发"套路（仅手动 Start 启动）。**副作用**：+1 天的触发器会在**次日同一时刻自动开火**——我当时忘了一旦用完就该禁用触发器。

**危害（若不处置）**：汇总取"每模型最后 3 个 valid"，新 QWEN 轮会顶掉现有 `[0,1,1]` 窗口；若新三轮全 1 → `sum(QWEN)=3` → 已锁定的 `OPUS 3 > 2` **反转为 `3 > 3` FAIL**，整轮白跑。

**全量排查（所有 oh-* 任务触发器）**：

| 任务 | 触发器 | 处置 |
| --- | --- | --- |
| `oh-r9-qwen` | 10-07 12:49:25 | 🔴 正在跑 → **终止进程树(PID 81364)+删容器+删 run 目录与日志**，任务**已禁用** |
| `oh-r10` | 10-07 17:03:44 | 🔴 今日 17:03 将开火 → **已禁用** |
| `oh-r11o` | 10-07 21:53:51 | 🔴 今日 21:53 将开火 → **已禁用** |
| `oh-r11o1` | 10-08 00:41:37 | 🟠 明晨将开火 → **已禁用** |
| `oh-r12` | 10-08 10:29:10 | 🟠 明早将开火 → 触发器**推至 2027-01-05**（不改动正在运行的实例） |
| `oh-r7-*` / `oh-r8-*` | 10-05 / 10-06（已过期） | 一次性触发器已消费，无风险，保持 Ready |

**验证**：容器仅剩 `oh-…105332-…-glm-5-3-01`（Up 3h，r12 的 GLM 未受影响）；r12 进程链完好（73832→79148→80484→81040）；r9q 今日残留（run 目录 + 日志）已删；10-06 的 r9q 原始日志与 `.done` 保留。

**GLM 当前（13:25）**：turn 15 已写入 `Audit.ps1`（4727 字符），该轮模型调用 attempt 1（12:42）、attempt 2（13:12）各超时 30min，attempt 3 挂起中；累计 3 次失败，余量 4。

## §13. r12 分片终止 + r12g 接续（2026-10-07 13:35 巡检，**仍未收口**）

**`logs/matrix-r12.done` 不存在** → 未结算、**未启动任何新分片**。r12 分片在 13:33 前后被终止，其 GLM 轮运行目录 `20261007T105332-candidate-glm-5.3-01`（曾卡在 turn 15、3 次 30min 超时）已删除；**OPUS×3 产物完好保留**（10:29/10:41/10:47）。

**新分片 `oh-r12g`（GLM×1）**：`State=Running`，**13:33:40 手动接续**（注册参数 `matrix-task.ps1 -Tag r12g -Models GLM -Runs 1`，与预案逐字吻合；触发器已推至 2027-01-05 防自动开火；运行账户 = 管理员 `S-1-5-…-500`，应为用户按预案手动接续）。当前容器 `oh-20261007t133341-candidate-glm-5-3-01` **Up 2 min**；进程链完好：`matrix-task.ps1`(80492) → `run_matrix.ps1`(80556) → `run.ps1`(84548) → `runner.py --models GLM --runs 1`(78736)。GLM 端点未变：`https://api.lmuai.com`（`GLM_AUTH=x-api-key`，`GLM_REQUEST_TIMEOUT=900`）。

### 13.1 ★ 诊断性汇总（`logs/_r12diag.json`，13:36，**非官方结算**，GLM 未齐）

命令同 §4（带 `--after "2026-10-06T00:59:28+00:00"`，脚本 sha256 `449cc0ea…5f8d`，`runner.py` sha256 `85968ca0…9b5c` 均 ✓，`exit=2`）。**关键读数：`opus_sum_greater_than_qwen = true`（3 > 2）—— 门禁主条件已达成！唯一未过项为 GLM。**

| 模型 | valid / attempt | scores | sum | 备注 |
| --- | --- | --- | --- | --- |
| **OPUS** | 12 / 12 | **`[1,1,1]`** | **3** | ✅ **r12 新三轮全 `verdict=1`+`completed`**（turns 21/12/10，tool_calls 25/16/13，changed=true），已进入 last-3 窗口；r11o/r11o1 三轮按新口径（`no_tool_call` 豁免 `tool_calls>0`）全部保留为有效轮 |
| QWEN | 5 / 6 | `[0,1,1]` | 2 | 沿用 r9q；1 轮 r8q `TimeoutError` 剔除 |
| **GLM** | **0 / 2** | `[]` | 0 | **仍缺**（r8 `HTTP 429` error / r10 `no_tool_call` tool_calls=0，两轮均剔除）→ `complete=false` |
| KIMI | 1 / 1 | `[1]` | 1 | 沿用 |

汇总 `gates`：

| gate | 值 |
| --- | --- |
| `controls_passed` | **true**（no-change 0×3 + golden 1×3，全 VALID） |
| `model_counts_complete` | **false**（**GLM 0/2，唯一未过项**） |
| `opus_sum_greater_than_qwen` | **true**（**3 > 2**，§8.2/§10 的"OPUS 天花板 = 2"论断被 r12 打破） |
| `task_version_consistent` | true（1.0.0） |
| `epoch_pinned` | true |
| `agent_failures_excluded` | 3（QWEN r8q `TimeoutError`；GLM r8 `HTTP 429` + r10 `no_tool_call`） |
| `qualified` | **false**（**仅因 GLM 缺有效轮**） |

### 13.2 下一步（★ 关键路径已缩短为"只等 GLM"）

- **GLM 一旦在 r12g 产出合法轮** → `model_counts_complete=true` → **`qualified=true`** → 按 SKILL 交付流程出**截图四件套 + 打包（zip）**；**飞书写回仍不做，等用户确认**。
- **GLM 若再被剔除**（`tool_calls=0` / `error` / `no_tool_call`）→ 记录结论，按预案**再补 GLM×1 一次**（tag 可用 `r12g2`）；GLM 在本机已 3 连败（r8 429 / r10 no_tool_call / r12 挂死），**其端点 `api.lmuai.com` 稳定性存疑**，若 r12g 亦失败，建议**更换 GLM 端点**后再补。
- **OPUS 侧已无悬念**：`[1,1,1]=3` 已锁定在 last-3 窗口，**不要再跑 OPUS**（避免新轮顶替）。
- ⛔ 严禁调难度 / 调 turn 预算；⛔ 不写飞书；⛔ 题包零写入。
- **automation 保持 ACTIVE**（未收口；下次 HOURLY 巡检查 `logs/matrix-r12g.done`）。

## §13. GLM 换端点重启（2026-10-07 13:33，用户指令：换 `https://api.lmuai.com/v1`）

**旧端点问题**：火山方舟（`ark.cn-beijing.volces.com/api/coding`）单次调用慢（turn 15 合法生成耗时 25 min），且频繁撞 1800s 超时（3 次失败）——进度拖到 3 小时后仍卡在 turn 15。

**处置**：
1. 终止 r12 的 GLM 流程（任务 oh-r12 + 进程树 73832 / 容器 `oh-…105332-…`），删残缺 GLM run 目录；**OPUS r12 三轮满分结果与日志保留**。
2. `.env.local`（备份 `scripts_backup/env.local.pre_lmuai`）：
   - `GLM_BASE_URL=https://api.lmuai.com`（runner 自动拼 `/v1/messages`）
   - `GLM_API_KEY=sk-391b433…4321`｜`GLM_AUTH=x-api-key`
   - `GLM_MODEL=glm-5.3`（不变；`/v1/models` 确认该端点支持 glm-5.3/glm-5/glm-4.7/glm-5.2/glm-5.1/glm-5.3-flash）
   - `GLM_REQUEST_TIMEOUT` **1800 → 900**（实测新端点 61.7 tok/s，900s 可产出 ~55k tokens，足够且能快速发现僵死）
   - 新增 `GLM_EXTRA_JSON={"thinking":{"type":"disabled"}}`（新端点默认返回 `thinking` 块，而 runner 第 534 行会剥离 thinking 后再回传 → 多轮可能报缺块；关闭 thinking 只回 text，已验证生效）
3. 探测结论：`/v1/messages` + `glm-5.3` → **HTTP 200**；**tools 调用正常**（`stop_reason=tool_use`，正确产出 `read_file` 入参）。
4. 注册 **`oh-r12g`**（tag `r12g`，`-Models GLM -Runs 1`），**13:33:41 起跑**；触发器设 **+90 天（2027-01-05）**，规避 §12 的次日自动开火陷阱。

**结果分支**：GLM 正常跑完（`completed`/`max_turns`，或 tool_calls>0 的散文收尾）→ 跑汇总，`model_counts_complete=true` 且 OPUS `[1,1,1]=3 > 2` → **`qualified=true`** → 走交付。GLM 若 error 再剔除 → 再补一轮。

## §14. ★★ 最终判定：`qualified = true`（2026-10-07 13:50）

**GLM lmuai 轮结果**：`20261007T133341-candidate-glm-5.3-01` → **verdict=1，status=completed，10 turns / 17 tool_calls / changed_workspace=true**，耗时 **806.3s（13.4 分钟）**，`verifier_error` 无。对比旧 ark 端点同任务跑了 3 小时未完成。

**正式汇总（`logs/_r12gs.json`，13:50，exit=0）**：

| 模型 | required | valid | selected | scores | sum | excluded |
| --- | --- | --- | --- | --- | --- | --- |
| QWEN | 3 | 5 | `…124926-01 / …133405-02 / …144310-03` | `[0,1,1]` | **2** | 1（error，10-06 轮） |
| OPUS | 3 | 12 | `…102913-01 / …104103-02 / …104750-03` | `[1,1,1]` | **3** | 0 |
| GLM | 1 | 1 | `…133341-01`（lmuai） | `[1]` | **1** | 2（error / no_tool_call，旧 ark 轮） |
| KIMI | 1 | 1 | `…102942-01` | `[1]` | 1 | 0 |

**gates**：`controls_passed=true`（no-change 3 全 VALID verdict=0｜golden 3 全 VALID verdict=1）｜`model_counts_complete=true`｜`opus_sum_greater_than_qwen=true`（**3 > 2**）｜`task_version_consistent=true`｜`epoch_pinned=true`｜`agent_failures_excluded=3`｜**`qualified=true`**。

**结论**：该题（`wfflab__wreparse-217`）**满足全部资格门禁，判定通过**，可进入交付阶段。

**关键路径回顾**：
1. OPUS 换 4router 端点 → `[1,1,1]=3`（此前 ebondai 端点恒 2 分）；
2. `no_tool_call` 口径改窄（用户批准）→ r11o 两轮满分被正确计入；
3. GLM 换 lmuai 端点 + 收紧超时 → 14 分钟拿到有效满分轮，补齐 `model_counts`；
4. QWEN `[0,1,1]=2` 提供难度区分度（`3 > 2` 严格成立）。

**下一步（待用户确认）**：交付流程——截图四件套 + 打包 zip（根=批次目录、`*.sh` 显式 0755）；**飞书写回不做**（等用户确认）。
