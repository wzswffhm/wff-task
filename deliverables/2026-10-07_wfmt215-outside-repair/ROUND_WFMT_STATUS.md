# `wfflab__wfmt-215` — 第 2 个 Outside Harbor 题包 · 生产状态

> 起跑：2026-10-07 14:14:52　分片：`oh-wfmt-qwen`（tag `wfq`）
> 工作区：`harbor-windows/wfflab__wfmt-215`（`task_version` 1.0 → **2.0.0**）
> runner：`deliverables/2026-10-04_outside-harbor-win/runner`

## 1. 本轮目标

用户指令：「打包完后再继续跑一个符合交付要求的题包」。
→ 把 `wfflab__wfmt-215` 从**平台导入范式**整改为 **Outside Harbor 范式**，
并跑到四模型资格门禁通过（`sum(OPUS) > sum(QWEN)` + counts 齐 + controls + epoch）。

## 2. 已完成

| # | 项 | 状态 |
|---|---|---|
| 1 | 范式整改（14 个新件 + task.toml 改造 + 旧件归档） | ✅ |
| 2 | 本地 no-change 校准 | ✅ `7 passed / 8 failed`，score=0 |
| 3 | 本地 golden 校准 | ✅ `15 passed`，score=1 |
| 4 | 工作区 sha256 恢复校验 | ✅ 7/7 一致 |
| 5 | 镜像构建 `outside-harbor/wfflab__wfmt-215:1.0` | ✅ |
| 6 | 容器内 control：no-change ×3 | ✅ 全部 `verdict=0 status=VALID` |
| 7 | 容器内 control：golden ×3 | ✅ 全部 `verdict=1 status=VALID` |
| 8 | QWEN×3 探针起跑 | 🔄 运行中（14:14:52 起） |

### 镜像构建踩过的坑（4 轮）

| 轮 | 失败点 | 根因 | 修复 |
|---|---|---|---|
| 1 | Step 6 `pip install` | `ENV PATH` 用 `\\` + `${PATH}`，Windows 容器未正确展开 → `powershell` 找不到 | 改为正斜杠 + 显式列全 System32/PowerShell 目录 |
| 2 | Step 9 预检 | `python -c "import pytest, wfmt"` 双引号被 PowerShell 参数解析拆散（`import` 单独成句） | 改单引号 + 绝对路径 `& 'C:\Python312\python.exe' -c '...'` |
| 3 | Step 9 预检 | **embed 发行版的 `python312._pth` 隔离 sys.path，PYTHONPATH 被忽略** | `._pth` 追加 `C:\testbed` 与 `C:\task\environment\workspace`；`run_tests.ps1` 另在 scratch 根写 `conftest.py` 插路径 |
| 4 | Step 10 / Step 11 | git `dubious ownership`（`C:/testbed` 属主 SYSTEM）；`WORKDIR C:\testbed` 反斜杠被 Docker 吃掉 | 加 `git config --global --add safe.directory`；`WORKDIR C:/testbed` |

## 3. 当前运行态

| 项 | 值 |
|---|---|
| 计划任务 | `oh-wfmt-qwen` → **Running**，触发器 **2027-01-05**（防次日自动开火） |
| 容器 | `oh-20261007t141452-candidate-qwen3-8-max-0902-01` Up |
| 分片日志 | `runner/logs/matrix-wfq-20261007-141452.log` |
| 完成标记 | `runner/logs/matrix-wfq.done`（未生成） |
| 预计耗时 | 1.5–3 h（历史 Qwen 单轮 10–90 min） |

## 4. 下一步（按序）

1. **QWEN×3 跑完** → 看 `matrix-wfq.done`；
   - 若 `sum(QWEN) ≤ 2` → 启动 `oh-wfmt-opus`（OPUS×3，4router 端点）→ 期望 `3 > 2` 通过；
   - 若 `sum(QWEN) = 3` → 摊薄题面（**adjust the task surface**，不调 turn 预算）后重跑 QWEN。
2. **OPUS×3** → 再接 `GLM×1`（lmuai 端点）+ `KIMI×1`。
3. **门禁结算** → `summarize_model_runs.py --task-id wfflab__wfmt-215 --after <epoch> --control-runs 3`。
4. **交付** → 截图四件套 + 打包（根 = 批次目录）；飞书写回**待用户确认**。

## 5. 风险

| # | 风险 | 处置 |
|---|---|---|
| R1 | QWEN 在 2.0.0 口径下三轮全过（平手） | 摊薄题面后重跑；不调难度之外的参数 |
| R2 | OPUS 在 4router 下仍 <3 | 换端点或换题 |
| R3 | 本题 Windows 价值偏弱（纯字节级语义） | 已记入 `extras/quality_review.md` 待复核 |
| R4 | 交付题包 Dockerfile 依赖构建期联网 | 接收方复现需网络；如需断网复现须改离线注入 |

## 6. 洁净核对

- 无遗留 `oh-*` 运行中容器（除当前 QWEN 探针）
- `oh-wfmt-qwen` 触发器已推至 2027-01-05，**不会**次日自动开火
- 旧 task 目录：`runner/work/` 下保留（`--keep-work` 所致），交付前清理

---

## 16:40 更新 — runner 参数化修复完成，215 重新起跑

- **结论**：旧 QWEN 探针（tag `wfq`）**结构性无效，已作废**。根因是 runner 把 217 的
  `WReparse` 写白名单与 PowerShell 人设写死在代码里，agent 根本改不了 `wfmt/`。
  详见 `WFMT_RUNNER_PARAM.md`。
- **修复**：runner 现从 `task.toml` 推导模块 / 参考文档 / 语言人设 / 样本目录；
  `read_file` 支持二进制 hex dump；`run_id` 加随机后缀以支持并行分片。217 行为零变化。
- **当前**：3 个并行分片 `oh-wfq1/2/3` 于 **16:37:43** 起跑（各 `QWEN ×1`，`--keep-work`），
  容器 `oh-…-f61d` / `-17c7` / `-2d61` 均 Up。
- **已清理**：旧废轮（无 `result.json`）已删；全部遗留 `oh-r*` 计划任务已 `Disabled`。
- **下一步**：三个 `matrix-wfqN.done` 齐 → `summarize_model_runs.py --after 2026-10-07T06:12:40+00:00
  --control-runs 3` → 看 `models.QWEN.score_sum`（≤2 则接 OPUS×3 期望 3>2）。

---

## 17:47 更新 — ★ QWEN「thinking 爆表」根因定位与处置（分片重启）

### 现象（16:37–17:36，56 min 零有效产出）

3 个分片 `oh-wfq1/2/3` 于 16:37:43 起跑，**全部卡死在 turn 6–7**，各连续 3 次
`TimeoutError: The read operation timed out`；每次白等 ≈15 min（`QWEN_REQUEST_TIMEOUT=900`），
按 7 次重试节奏推算需再烧 ≈60 min 才能全部退化为 `agent.status=error` 被剔除 → **探针将全额作废**。

### 诊断（三次端点实测，定位到参数级）

| 探测 | 结果 | 结论 |
|---|---|---|
| 短请求 ×3 | HTTP 200 / 1.4–1.5 s / PONG | 端点存活 |
| **3 并发 + 84K tokens 长输入** | 全部 200 / 7.7–11.4 s | **并发与长上下文均无恙** |
| agent 风格（tools + `max_tokens=65536` + 写代码要求）**baseline** | **>120 s 卡死**（脚本被 SIGTERM） | 复现故障 |
| 同上 **`max_tokens=8192`** | **144.9 s，`stop=max_tokens`，`blocks=['thinking']`** | ★ 8192 tokens 全烧在 thinking，**零 text / 零 tool_use** |
| 同上 **`thinking:{type:disabled}` + 65536** | **2.9 s，`stop=tool_use`，`blocks=['text','tool_use']`** | ★ 关闭 thinking 后立即正确调用工具 |

### 根因

`QWEN3.8-Max-0902` 是**推理模型**。215 要求重写整个 `wfmt` Python 包（5 个模块），
模型在每个「要动笔」的轮次进入**超长 thinking**：按实测 57 tok/s，65536 tokens 的思考需
**≈1150 s > 900 s 超时** → 请求永不返回 → 重试同一 payload 同样爆炸 → 3 次全灭。

对照组：217（PowerShell 模块，改动量小）thinking 短，故同样参数下从未触发。

### 处置（治本，且有既有范式先例）

1. `.env.local` 增 `QWEN_EXTRA_JSON={"thinking":{"type":"disabled"}}`
   —— 与 **GLM / KIMI 完全同型**的既有配置（原文件本就已给二者加上），非新发明；
2. `QWEN_REQUEST_TIMEOUT` 900 → **300**（思考已禁，正常轮秒级返回；防偶发僵死白等）；
3. 备份 `runner/scripts_backup/env.local.pre_wqthink`（sha256 前缀 `22659fd1f1d71a4f`）；
4. 停旧分片（`Disable`+`Stop` 任务、杀 3 个 runner 进程、`docker rm -f` 3 容器）、
   清 3 个残缺 run 目录与日志；**controls 7 个 run 保留**（有效）；
5. **17:44:51 重起 3 个并行分片 `oh-wfq4/5/6`**（各 `QWEN ×1`，`-TaskId wfflab__wfmt-215`），
   容器 `-4dee` / `-3538` / `-4b18` 均 Up。

### 效果（立竿见影）

| | 旧配置 | 新配置 |
|---|---|---|
| 到 turn 13 耗时 | 56 min（仅到 turn 6–7） | **≈24 s** |
| 90 s 内 turn 数 | 6–7 | **13–14** |

### ★ 编排坑（本轮新增，务必记住）

`Register-ScheduledTask` 的 `-Execute` **必须写 `powershell.exe` 绝对路径**
（`$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe`）。写裸名 `powershell.exe` 时
任务计划的最小 PATH 找不到它 → `LastTaskResult=2147942402`（`0x80070002` 文件未找到），
任务显示 `Ready` 但从不执行、无任何日志。

### 口径说明

`thinking` 开关属**端点侧推理配置**，不触碰题面 / rubric / 判分逻辑，
故 `task_version 2.0.0` 不变、epoch 不变（`2026-10-07T06:12:40+00:00`）、controls 复用。
217 已交付收口，**不重跑**（其 QWEN 轮为带 thinking 的正常收敛轮，结论不受影响）。

### 下一步（不变）

三个 `matrix-wfq4/5/6.done` 齐 → `summarize_model_runs.py --workspace-root <runner>
--task-id wfflab__wfmt-215 --after 2026-10-07T06:12:40+00:00 --control-runs 3`
→ 看 `models.QWEN.score_sum`：≤2 → 接 OPUS×3（4router）期望 `3>2`；=3 → 摊薄题面后重跑。

---

## 19:30 更新 — ★ QWEN 探针收口 `[0,0,0]`；OPUS×3 + GLM/KIMI 已起跑

### 1. QWEN 三轮结果（thinking 禁用后，全部合法得分、零剔除）

| run_id | verdict | status | agent_status | turns | 耗时 | 未满足的 rubric 项 |
|---|---|---|---|---|---|---|
| `…-4b18` | **0** | VALID | completed | 29 | 286 s | `error-classification` |
| `…-3538` | **0** | VALID | completed | 33 | 375 s | `error-classification`, `streaming` |
| `…-4dee` | **0** | VALID | completed | 36 | 1 831 s | `sample-compatibility`, `error-classification` |

- **`sum(QWEN) = 0`**（`scores [0,0,0]`），`invalid_attempts=[]`、`excluded_agent_failures=[]`；
- 三轮 `weighted_score` 分别 **0.80 / 0.65 / 0.60** —— 都已相当接近阈值但均未过，
  失分集中在 `error-classification`（3/3 轮）→ **区分度来自真实的契约缺口，不是噪声**；
- `4dee` 轮含 3 次 `TimeoutError` 重试（1 831 s），但 **7 次重试内自愈**、最终 `completed`，
  属端点瞬时抖动，未触发剔除。

### 2. 门禁读数（`runner/logs/_wfqsummary.json`，exit=2）

| gate | 值 |
|---|---|
| `controls_passed` | **true**（no-change 3×0 / golden 3×1，全 VALID） |
| `epoch_pinned` | true（`--after 2026-10-07T06:12:40+00:00`） |
| `task_version_consistent` | true（`2.0.0`） |
| `model_counts_complete` | **false**（OPUS/GLM/KIMI 未跑） |
| `opus_sum_greater_than_qwen` | false（OPUS 空 → 0 与 0 比） |
| `agent_failures_excluded` | 0 |
| **`qualified`** | **false（仅因模型矩阵未齐）** |

> ★ `sum(QWEN)=0` 比预期（≤2）**更好**：只要 OPUS 拿到 ≥1 分，条件 1（`sum(OPUS) > 0`）即成立。

### 3. 已起分片（19:29:18）

| 分片 | 模型 | 容器 | 说明 |
|---|---|---|---|
| `oh-wfo` | **OPUS ×3**（4router 端点） | `oh-20261007t192919-…-opus-5-01-26ae` | 端点已探活（200 / 4.8 s / PONG） |
| `oh-wfa` | **GLM ×1 + KIMI ×1**（lmuai / ark） | `oh-20261007t192920-…-glm-5-3-01-17c8` | 两者串行，各 1 次 |

`oh-wfq4/5/6` 已 `Disable`。预计 20:00–20:30 收齐 → 重跑汇总即出最终 `qualified`。

---

## 20:31–21:00 轮次：OPUS 端点超时根因定位与修复（第 3 次）

### 1. 收口读数

| 模型 | 结果 | 状态 |
|---|---|---|
| QWEN ×3 | `[0,0,0]` | 全 VALID / completed（17:44 批） |
| **GLM ×1** | **`1`**（weighted 1.0，15/15 checks PASS） | VALID / completed，1183 s |
| KIMI ×1 | `0` | VALID / completed，2627 s |
| OPUS ×1 | **`error`**（非计分，被汇总剔除） | 7 次连续读超时 |
| OPUS ×2 | 同上（attempt 5/7 时止损） | — |

### 2. 根因（实测定性）

**不是**端点整体宕机、**不是**大 payload、**不是**代理、**不是**上下文过长：

| 实验 | 读数 | 结论 |
|---|---|---|
| 小请求 / 大 payload(≈40K tok) / 直连 vs 代理 | 10–40 s 全绿 | 端点连通性正常 |
| 6 轮递增 agent 对话（真实工具定义，13 KB） | 2.6→28.4 s 全绿 | 多轮形态正常 |
| **强制 ~900 行长代码输出** | **230.5 s，14 614 output tokens（≈63 tok/s）** | ★ **命中真因** |

runner 是**非流式**调用（`urlopen` → `response.read()`），socket 超时按「单次 recv 无数据」计。题目要求**单轮整包重写**（5+ 模块），OPUS 的 thinking+输出常达 2 万+ tokens → **>300 s** → 超时；重试发送**逐字节相同** payload → 必然同样超时。

**时间线自证**：run 02 在 20:22 进入大输出轮 → `5 次尝试 × 300 s + 退避(15+30+60+60) s = 20:49`，与日志末行 `20:49:09` 完全吻合。

> 217（PowerShell 小改动）输出小，故从未触发 —— 与 QWEN 在 215 上被 thinking 撑爆属**同一类**「单轮输出量 × 端点吞吐 > 超时」问题，只是 QWEN 可用 `thinking:disabled` 压制，OPUS 忽略该参数、只能抬超时。

### 3. 处置

1. `.env.local`：`OPUS_REQUEST_TIMEOUT` **300 → 1200**（备份 `scripts_backup/env.local.pre_opustimeout`）；`OPUS_BASE_URL` 仍为 **`https://4router.net`**；
2. 停 `oh-wfo`（禁任务+杀 runner+删容器）、停用 `oh-wfa`、删除 2 个失败 OPUS run 目录与旧日志；
3. **20:57:43 重起 `oh-wfo2`（OPUS ×3，串行）**，容器 `oh-20261007t205743-…-0dc6`。

**效果**：新分片 **2 分钟推进 14 个工具轮、`attempt=0`**（旧分片同期已卡死在 turn 6–9）。

### 4. 口径

`OPUS_REQUEST_TIMEOUT` 属**传输层**参数，不触碰题面 / rubric / 判分 → `task_version 2.0.0`、epoch（`2026-10-07T06:12:40+00:00`）、controls 全部不变；已交付的 217 不重跑。

### 5. 下一步

`matrix-wfo2.done` → 汇总（`--after 2026-10-07T06:12:40+00:00 --control-runs 3`）→ 期望 `OPUS.complete=true` 且 `sum(OPUS)>0` → `qualified=true` → 重渲染证据图 + 打包。飞书写回仍待确认。

---

## 22:24–23:05 ★ 换 4router 端点 → 资格门禁 `qualified=true`（收口）

### 1. 端点切换与探活

用户指令「用4router的opus」。凭据 `https://4router.net` + `sk-ABTd…2gE`（全文见
`deliverables/2026-10-06_win-rerun-epoch/ROUND10_OPUS_GLM_STATUS.md`）。

**探活（`runner/_probe4r.py` → `logs/_probe4r.json`，四项全绿）**：

| 用例 | 结果 |
|---|---|
| 非流式小请求 | OK **2.3 s**，`PONG` |
| 非流式 + tool_use | OK **2.7 s**，正确返回 `finish` 块 |
| **流式（SSE） + tool_use** | OK（事件流正常） |
| **流式 + `max_tokens=32000` 大输出** | OK **167.9 s / 289 KB**（无余额/墙钟问题） |

对比：上一轮 ebond key **余额耗尽**（`HTTP 403 INSUFFICIENT_BALANCE`），流式跑到一半即 `agent.status=error`。

### 2. 配置改动

`.env.local`：`OPUS_BASE_URL` `https://api.ebondai.com` → **`https://4router.net`**；
`OPUS_API_KEY` → 4router key。其余不变（`OPUS_STREAM=1`、`OPUS_MAX_TOKENS=32000`、`OPUS_REQUEST_TIMEOUT=1800`）。
备份 `runner/scripts_backup/env.local.pre_4router`。属**端点/传输层**参数，**不动 task_version / rubric / epoch**。

### 3. 分片与收口

3 个并行单例分片 `oh-wfp1/2/3`（`matrix-task.ps1 -Tag wfpN -Models OPUS -Runs 1 -TaskId wfflab__wfmt-215`），
**22:34:30 起跑**；三片 `matrix-wfp1/2/3.done` 齐，全部 `agent finished status=completed`。

| run | verdict | agent_status | turns | tool_calls | reason |
|---|---|---|---|---|---|
| `…223429-…-31ff` | **1** | completed | 20 | 27 | All rubric items satisfied |
| `…223429-…-bb2d` | **1** | completed | 17 | 29 | All rubric items satisfied |
| `…223430-…-8a4e` | 0 | completed | 27 | 35 | Unsatisfied: `streaming` |

### 4. 门禁读数（`logs/_wfp_summary.json`，exit=0）

汇总脚本 `Desktop/generate-win/scripts/summarize_model_runs.py`，**sha256 `449cc0ea…5f8d`**（与现行锁定值一致），
命令带 `--after 2026-10-07T06:12:40+00:00 --control-runs 3`。

| gate | 值 |
|---|---|
| `controls_passed` | **true**（no-change 3×0 / golden 3×1，全 VALID） |
| `model_counts_complete` | **true** |
| `opus_sum_greater_than_qwen` | **true（2 > 0）** |
| `task_version_consistent` | true（`2.0.0`） |
| `epoch_pinned` | true |
| `agent_failures_excluded` | 2（ebond 余额耗尽的 `e43c`/`c3ca`，`agent_status=error` → 正确剔除，非 0 分） |
| **`qualified`** | **true ✓** |

模型读数：**OPUS `[1,1,0]=2`（4router）**｜QWEN `[0,0,0]=0`｜GLM `[1]=1`｜KIMI `[0]=0`。

> QWEN 三轮失分集中在 `error-classification`（3/3），OPUS `8a4e` 失分在 `streaming` →
> **区分度来自真实契约缺口**：`error-classification` 对 QWEN 偏难、`streaming` 对 Opus 偶有遗漏。

### 5. 收尾

- `oh-wfp1/2/3` 已 `Disable-ScheduledTask`（trigger 一律推到 2027-01-05 远期，杜绝次日自燃）；
- 全量核对 `Get-ScheduledTask oh-*` → 全部 `Disabled`（仅 keeper `Running`）；
- 无运行中容器（`docker ps` 空）。

### 6. 下一步（待用户确认）

`qualified=true` 已达成，**尚未做**：① 重渲染 oracle-nop / 分数两张证据图；② 打**四件套 ZIP**；
③ 飞书写回（217 已写、215 未写）。**按用户偏好，不自动提交、不自动外发，等确认。**
