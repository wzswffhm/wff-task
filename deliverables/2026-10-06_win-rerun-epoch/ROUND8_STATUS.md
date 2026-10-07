# 第 8 轮：题面加固后的重跑（`wfflab__wreparse-217`）

> 启动：**2026-10-06 08:59:28 (+08)** ／ `epoch_utc = 2026-10-06T00:59:28+00:00`
> 工作区：`deliverables/2026-10-04_outside-harbor-win/runner`
> 题包：`harbor-windows/wfflab__wreparse-217`（`runner/tasks/` 以 junction 指向它，改动即时生效）
> 依据：`generate-win/references/qualification-gates.md`、`skills/harbor-windows/references/08-model-validation.md`

## 0. 为什么必须重跑

1. **规范强制**：上一轮把 `tests/**` 从 **16 项加固到 24 项**（把契约已声明、原检查未覆盖的行为纳入评测），属 `qualification-gates.md` 意义上的 **material change**。第 7 轮的全部证据与 controls 因此作废，**必须开新 epoch 重跑全套**。
2. **用户指令**：持续推进，直至满足交付标准。

## 1. 本轮的两个变量（相对第 7 轮）

| 项 | 第 7 轮 | 第 8 轮 | 理由 |
| --- | --- | --- | --- |
| `tests/` 检查数 | 16 | **24** | 契约 `REPARSE-CONTRACT.md` 已声明但从未被考的行为：`canonical` 卷根保留／尾分隔符、`Errors` 稳定排序、reparse 记录 `Depth`、`Walker` 边界等 8 条 |
| `runner.py` `MAX_AGENT_TURNS` | 24 | **80** | 24 已被第 7 轮**证伪**为无效杠杆（OPUS 自然收敛 8/10/13 轮不受影响；QWEN 两次撞上限**仍各得 1.0**），且该参数**不入交付物**（四件套 ZIP 无 turn 字段）→ 退役，回归中性上限 |

> 除这两项外，端点、模型、环境、依赖、评分规则、工具权限（含 `run_shell`）与第 7 轮完全一致 —— 满足 08-model-validation「Golden／no-change／候选必须使用**同一** base、环境、依赖、测试树、评分规则和资源预算」。

## 2. 分片与 epoch 归属

`epoch_utc = 2026-10-06T00:59:28+00:00` —— 四个分片**全部**起于此之后，本轮到目前是单一 epoch。

| 计划任务 | tag | 分片内容 | 单轮预计耗时 |
| --- | --- | --- | --- |
| `oh-r8-qwen` | `r8q` | QWEN × 3 | 50–56 min/轮（80 轮跑满，历史实测 2931 / 3366 s）|
| `oh-r8-opus` | `r8o` | OPUS × 3 | 5–15 min/轮（自然收敛 8–22 轮）|
| `oh-r8-aux` | `r8a` | GLM × 1、KIMI × 1（8.3 体检）| 10–20 min |
| `oh-r8-ctrl` | `r8c` | no-change × 3 + golden × 3 | 合计 ≈ 2 min（不走 agent）|

并发是**刻意的**：QWEN（阿里云 MAAS）／OPUS（ebondai）／GLM+KIMI（火山方舟）分属三个不同上游 key，互不饿死；`glm-5.3` 与 `kimi-k3` 共用火山方舟 key，故二者在同一分片内**串行**。

## 3. 启动前的端点探测（`probe_endpoints.py`）

| 端点 | HTTP | 结果 | 判定 |
| --- | --- | --- | --- |
| **OPUS** `api.ebondai.com`（`claude-opus-5`） | 200 | 正文 `PONG`，`stop_reason=end_turn`，4.4 s | ✅ 可用 |
| QWEN 阿里云 MAAS（`qwen3.8-max-0902`） | 200 | 返回 thinking 块（探针 `max_tokens=16` 被 thinking 吃光，非端点问题）| ✅ 可用 |
| GLM 火山方舟（`glm-5.3`） | 200 | 同上（`max_tokens` 过小）| ✅ 可用 |
| KIMI 火山方舟（`kimi-k3`） | — | 探针脚本 bug（`KIMI_EXTRA_JSON` 为 dict 注入 header），已由分片实跑验证 | ⏳ |
| `api.blvr.top`（规范指定 Opus）| — | `HARBOR_WINDOWS_BLVR_KEY` 为空，无凭据 | ❌ 不可用 |
| `HARBOR_WINDOWS_ALIYUN_KEY` | **401** `InvalidApiKey` | 该环境键已失效（runner 用的是 `.env.local` 的 `QWEN_API_KEY`，有效）| ❌ 失效 |

**结论**：Opus 端点当前**活着**，重跑不会因端点死掉而白费。

## 4. 诚实的前置预测与风险（必须在判定时对照）

第 7 轮实现（`runner/work/<run_id>/case/environment/workspace/WReparse/`，`-KeepWork` 落盘）已被**离线复评**过一次，用加固后的 24 项检查：

| 口径 | sum(OPUS) | sum(QWEN) | 门禁 |
| --- | --- | --- | --- |
| 原 16 项（第 7 轮容器实跑）| 3 | 3 | ❌ 平手 |
| 严格契约 24 项（第 7 轮实现离线复评）| **1** | **2** | ❌ **反向落后** |

失败点：`Get-WReparseCanonicalPath('C:\')` —— **OPUS 3 轮里 2 轮返回 `'C:'`**，违反契约 §5.1「卷根保留其形态」；QWEN 两个有效轮全对。

据此**预判本轮仍不通过**，理由：

- **QWEN 的天花板问题未解**：QWEN 在 80/72/40 轮共 4 次运行**全部 1.0**，对轮次预算不敏感；加固后离线复评其 2 个有效轮**仍满分**。若再次 3/3 满分，门禁不等式退化为 `sum(OPUS) > 3`，**数学无解**（每轮上限 1.0）。
- **加固只会扩大 QWEN 优势**：题面越严格，Opus 端点的相对得分越低（BLOCKER §9 已给直接证据）。

**本轮真正要回答的问题**：在恢复 80 轮后，OPUS 能否把 `C:\` 卷根这类契约违规也修对（即"严格口径下的 1 分是否只是被 24 轮截断的产物"）。这是第 7 轮数据无法回答的唯一悬念。

## 5. 判定命令（跑完后执行）

```powershell
$py = "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
$sk = "C:\Users\Administrator\Desktop\generate-win"
$rn = "C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner"

# 必须带 --after（新脚本下不传即拒判），pin 到本轮 epoch
& $py "$sk\scripts\summarize_model_runs.py" --workspace-root $rn --task-id wfflab__wreparse-217 `
      --control-runs 3 --after "2026-10-06T00:59:28+00:00" --output "$rn\logs\_r8summary.json"
```

判定要点（均须逐条核）：
1. `gates.controls_passed` — controls 3+3 全 VALID，且 `no-change=0 / golden=1`；
2. `gates.model_counts_complete` — QWEN 3 / OPUS 3 / GLM 1 / KIMI 1；
3. `gates.agent_failures_excluded` — 逐条列出被剔除的 `error` / `no_tool_call` 运行（**这些不计分，须重跑**）；
4. `gates.opus_sum_greater_than_qwen` — 目标 `true`。

## 6. 时间线

| 时刻 (+08) | 事件 |
| --- | --- |
| 08:56 | 前置检查：无遗留 `run_matrix` / `runner.py` 进程、无残留 `oh-*` 容器 |
| 08:57 | 端点探针：OPUS 可用 |
| 08:58 | `runner.py` `MAX_AGENT_TURNS` 24 → 80；新增 `shard-controls.ps1` |
| 08:59:28 | **epoch 起点**；注册并启动 4 个分片，容器全部 Up |
| 09:00:30 | controls 第一遍完成（no-change 0/0/0、golden 1/1/1，全 VALID）|
| 09:03:23 | controls 第二遍完成（同上）—— 见 §8 的重复原因 |
| 09:04:07 | **`opus-01` 完成：24 项中 FAIL 1 项 → `verdict=0`**（见 §7）|
| 09:15:04 | `matrix-r8o.done` —— **OPUS 3/3 完成**（`[0,1,1]`，sum=2）|
| 10:33:41 | `matrix-r8a.done` —— GLM 唯一轮 `error`(HTTP 429)、KIMI 1 轮 `verdict=1` |
| 11:17:47 | `matrix-r8q.done` —— **QWEN 3 轮收尾**（两轮 25/31 轮满分，第三轮 `TimeoutError` 剔除）|
| 12:18 | 四分片全 DONE，汇总判定 **`qualified=false`**（见 §9）|

## 7. 早期决定性信号（09:04–09:07，OPUS 前两轮）

| run | turns | agent.status | verdict | 24 项检查 |
| --- | --- | --- | --- | --- |
| `…085931-candidate-opus-5-01` | 8 | completed | **0** | FAIL 1 项 |
| `…090407-candidate-opus-5-02` | 4 | completed | **1** | 全过 |

唯一失败项：

```text
Get-WReparseCanonicalPath('C:\') returned 'C:'; a volume root keeps its trailing separator
```

**如何解读（关键）**：

1. 该项**正是上一轮新增的 8 项之一**（`canonical-path-keeps-volume-root`）；OPUS 在**原有 16 项上全部通过**。
2. 但它在两轮之间**不稳定**：`opus-01` 违规、`opus-02` 正确。所以这不是"OPUS 完全不会"，而是**间歇性契约违规**——这与离线复评（第 7 轮 3 份实现中 2 份违规）的结论方向一致，只是强度略弱。
3. 二值判分放大了代价：**1 项错 = 整轮 0 分**。OPUS 已经丢掉 1 轮，故本轮 `sum(OPUS) ≤ 2`。

**数学后果**：只要 QWEN 拿到 ≥2（其历史为 4/4 满分，加固后离线复评 2/2 满分），**门禁必 fail**。若 QWEN 也失手到 ≤1，才有理论上的可能——但那是低概率分支，须以实跑为准。

**对上一轮动作的归因**：题面加固**没有**降低 QWEN 的天花板，却给 OPUS 增加了新的归零机会（新增项每轮都可能独立触发）。在"门禁要求 `sum(OPUS) > sum(QWEN)`"的方向上，加固是**负向**的。这再次印证 BLOCKER §9：**提高题面严格度不是有效杠杆**。

## 8. 已知的编排瑕疵（不影响结论，但须记录）

`shard-controls.ps1` 被启动了**两次**：一次是我的 `Start-ScheduledTask`（08:59:31），一次是注册时写入的 `-Once -At` 触发器（09:02:28）。controls 只需 <1 分钟，故第二次未落在 `MultipleInstances=IgnoreNew` 的保护窗口内，于是跑了两遍，产出 **12 个** controls run（两组各 3 no-change + 3 golden）。**两组全部 VALID，取值一致**（no-change=0、golden=1），故对判定无影响，反而可作稳定性冗余证据。

> 三个模型分片未受影响：QWEN/OPUS/GLM 首轮耗时远超 2 分钟，09:02:28 的触发器命中时任务仍在 `Running`，被 `IgnoreNew` 丢弃。

## 9. 判定结果（2026-10-06 12:18，四分片全部 DONE）

**`qualified = false`**。汇总命令（带 `--after`，脚本 sha256 = `ba623ff0…cc634f`）：

```text
gates = {
  "controls_passed": true,          // no-change 0/0/0 + golden 1/1/1，3+3 全 VALID
  "model_counts_complete": false,   // QWEN 仅 2/3 有效轮、GLM 0/1
  "opus_sum_greater_than_qwen": false,
  "task_version_consistent": true,  // ["1.0.0"]
  "epoch_pinned": true,             // 2026-10-06T00:59:28+00:00
  "agent_failures_excluded": 2,
  "qualified": false
}
exit code = 2
```

### 9.1 逐 run 明细

| 模型 | valid | scores | sum | run | turns | agent.status | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **OPUS** | **3/3** | `[0, 1, 1]` | **2** | `085931-…-01` | 8 | completed | **0** |
| | | | | `090407-…-02` | 4 | completed | 1 |
| | | | | `090642-…-03` | 12 | completed | 1 |
| **QWEN** | **2/3** | `[1, 1]` | **2** | `085931-…-01` | 25 | completed | 1 |
| | | | | `092012-…-02` | 31 | completed | 1 |
| | | | | `101657-…-03` | 8 | **error** | ~~0~~ 剔除 |
| GLM | 0/1 | `[]` | 0 | `085931-glm-5.3-01` | 10 | **error** | ~~0~~ 剔除 |
| KIMI | 1/1 | `[1]` | 1 | `102942-kimi-k3-01` | 8 | completed | 1 |

### 9.2 两条被剔除的故障轮（**不计分，非候选失败**）

| 模型 | run | agent.status | summary |
| --- | --- | --- | --- |
| QWEN | `20261006T101657-…-03` | error | `model error: TimeoutError: The read operation timed out` |
| GLM | `20261006T085931-glm-5.3-01` | error | `model error: HTTP 429: {"error":{"code":"ServerOverloaded",…}}` |

QWEN `…-03` 的 `agent.log` 显示：`turn 7` 只读完 `instruction.md` / `REPARSE-CONTRACT.md` 就被连续 3 次 `TimeoutError` 掐断（`tool_calls=14`，**一次 `write_file` 都没发生**），verifier 于是对**未修改的 workspace** 判 0 —— 与第 7 轮 QWEN `235615` 完全同类。若沿用旧版脚本，这一轮又会被当成合法 0 分。

**关于"INVALID 归一为 0 分"**：本轮 `invalid_attempts` **全为空**，**0 例 INVALID** —— 两例故障都发生在 **agent 层**（上游超时 / 429），不是 verifier 层。所以该议题**本轮仍不适用**；且即便要做，正解仍是**改 verifier**（try/except 包裹候选产物导入后输出 `VALID + verdict=0`），而非在汇总层笼统归一 —— 后者会把真正的 verifier 故障（pytest 缺失、容器 OOM）也计成候选的 0 分，直接违反 `SKILL.md:151`。

### 9.3 ★ 硬结论：本轮 **不必重跑** 即已定论 FAIL

| 量 | 值 | 是否还有变动空间 |
| --- | --- | --- |
| `sum(OPUS)` | **2** | ❌ **零** —— OPUS 3 轮全部 `completed`，无故障可剔除、无轮可补 |
| `sum(QWEN)` 当前 | 2（2 轮） | 补上第 3 轮后 ∈ `{2, 3}` |
| 门禁不等式 | `2 > 2` ❌ ／ `2 > 3` ❌ | **两种情形均 false** |

**无论 QWEN 第 3 轮重跑得 0 还是 1，判定都是 `false`。** 这是本轮的确定性结论，可据此省掉一轮 QWEN 重跑（约 1 小时）。

### 9.4 §4 悬念的回答：OPUS 的失分**不是**轮次截断的产物

| 问题 | 实测答案 |
| --- | --- |
| 24 轮是否截断过 QWEN？ | **是** —— 80 轮下 QWEN 自然收敛于 **25 / 31** 轮（第 7 轮 24 轮上限恰在其下）|
| 截断是否影响 QWEN 得分？ | **否** —— 第 7 轮被截断的两轮仍各得 1.0；本轮不截断仍是 1.0 |
| OPUS 在 80 轮下能否修好 `C:\` 卷根？ | **不稳定** —— `opus-01`（8 轮）仍返回 `'C:'` 而 `verdict=0`；`opus-02/03` 正确 |

即：**OPUS 在充足轮次下仍会按 `canonical` 卷根项失分**，属真实契约盲点（间歇性），与轮次预算无关。这**再次否证**"提高题面严格度能改善区分度"——它只给 OPUS 增加归零机会。

### 9.5 产物

| 文件 | 说明 |
| --- | --- |
| `evidence/score_summary.png`、`oracle_nop_controls.png` | 由实际 `_r8summary.json` 渲染，**NOT READY** |
| `evidence/model_runs_summary_r8.json` | 汇总原始 JSON，可回溯每条 run 的 `task_id`/`task_version`/`agent_status`/`duration`/`test_log_sha256` |

**未产出**：四件套 ZIP（门禁未过）、飞书写回（按要求一律不执行）。题包 `instruction.md` / `environment/**` / `solution/**` 仍零写入（本轮只改过 `tests/**` 3 个文件，属上一轮已交付的加固，本轮未再动）。

### 9.6 下一步建议（不变）

门的性质已经很清楚：**QWEN 在这道题上的天花板恒为满分，而门禁要求 OPUS 严格反超** —— 在当前 Opus 端点下这道题在数学上不可通过。可选路径只有两条：

1. **取得健康的 Opus 5 端点凭据**（规范指定的 `api.blvr.top` 无 key；`api.ebondai.com` 逐检查错误率显著偏高）—— 外部动作；
2. **换题**（`harbor-windows/` 另选一道）。

⛔ **不建议**继续加固题面或调整 `MAX_AGENT_TURNS`：前者已由第 7 轮离线复评 + 第 8 轮实跑双重否证，后者已退役且不入交付物。
