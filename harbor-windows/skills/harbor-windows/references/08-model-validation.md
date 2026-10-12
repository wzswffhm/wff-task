# 08 · 多模型验证与稳定性

来源：规范第七章、第八章

---

## 一、冻结条件（8.1）

所有比较必须使用**相同的**：

- Harbor Task 版本
- Harness 版本
- Windows 环境
- 工具权限
- 网络策略
- 资源预算
- 采样配置

> **环境恢复后再开始下一次独立运行。**

---

## 二、主要模型（8.2）

**Qwen3.8-Max-0902 与 Opus 5 每题各独立运行 3 次。**

- 只统计 **VALID** 运行
- **INVALID 必须查明原因并补跑**

### 指标定义

| 指标 | 定义 | 取值范围 |
|---|---|---|
| `model_score_sum` | 同一模型 3 次二值正式分数之和 | **0–3** |
| `testcase_pass_sum` | 同一模型 3 次运行中 required testcase 的 PASS 数量总和 | 仅用于**双方正式分均为 0** 时比较，不形成部分分 |

### 单题准入（满足任一）

```
条件 1：Opus5.model_score_sum > Qwen3.8-Max-0902.model_score_sum
条件 2：两者 model_score_sum = 0
        且 Opus5.testcase_pass_sum > Qwen3.8-Max-0902.testcase_pass_sum
```

**不满足准入的情况**：
- 两者正式分和**相同且不全为 0**
- 双方均为 0 但 testcase 表现**没有严格区分**

→ **该题区分度不满足准入要求，应分析后整改或替换。**

### 红线

> **模型门槛不能覆盖数据质量门槛。**
> 即使满足上述分差，存在题面歧义、不可解约束、错误测试、环境故障、薄题、答案泄漏或
> Windows 价值不足时**仍不得验收**。
>
> **不得为制造分差而增加题面未声明要求、错误隐藏测试或冷门单点陷阱。**

---

## 三、辅助模型（8.3）

**GLM-5.3 与 Kimi K3 每题至少完成 1 次有效运行**，主要确认：

1. Agent 能正常进入、读取和修改工作区
2. 构建、测试和结果采集链路可运行
3. 不存在**模型无关**的 infra、权限、依赖或 Verifier 质量问题

**不要求**：
- GLM-5.3、Kimi K3 与 Qwen/Opus 形成固定排名
- 各跑 3 次

**异常处理**：
- 因**题目或基础设施**问题无法完成有效运行 → **必须先修复**
- 属**模型自身能力失败**且运行链路有效 → 可按真实结果记录

---

## 四、Golden / no-change 稳定性（第七章）

### 4.1 同一身份运行（7.1）

Golden、no-change 和模型候选必须使用**同一** base、环境、依赖、测试树、评分规则和资源预算。

> Golden 必须有**直接证据**证明参考解已实际应用，不能只依赖环境变量、任务名称或日志标题。

### 4.2 Golden path（7.2）

干净环境下必须满足：

- 所有 required F2P 与 P2P **执行且 PASS**
- **正式分数为 1**
- **无 SKIP、MISSING、ERROR、旧产物复用或隐藏环境依赖**
- 最终补丁、测试树、环境和日志身份**可以核对**

> Reference Solution **不是天然真值**。若 Golden 与题面冲突、只适配某种内部写法或破坏既有行为，
> 应修复题目、测试或参考解，**不得为保证 Golden=1 而修改题意**。

### 4.3 no-change 与错误反例（7.3）

干净环境下必须满足：

- **P2P 全部通过**
- **至少一个核心 F2P 因目标缺陷失败**
- **正式分数为 0**
- 失败原因**不是**依赖缺失、测试语法、环境未就绪或其他基础设施问题

> 由于采用**全有或全无的二值评分，空跑不得出现非零正式分数。**

除 no-change 外，还应按题目风险验证反例：

- 空实现
- 固定返回
- 提前退出
- 硬编码
- 只修一半
- 吞异常
- 禁用功能

### 4.4 稳定性（7.4）

提交验收前至少完成：

| 检查 | 要求 |
|---|---|
| no-change 独立运行 | **3 次，结果均为 0** |
| Golden 独立运行 | **3 次，结果均为 1** |
| 干净环境重建/恢复复验 | 至少 **1 次** |
| required testcase 集合与终态 | 每次一致，无**非模型原因**抖动 |
| 清理或快照恢复 | **无影响后续运行的残留** |

---

## 五、运行记录归档

位置：`delivery-extras/tasks/<task-id>/model_runs/<model>/`

每次运行须记录：

| 字段 | 说明 |
|---|---|
| 配置 | Task 版本、Harness、环境、工具权限、网络策略、资源预算、采样参数 |
| 真实模型标识 | 精确到版本号 |
| 运行状态 | VALID / INVALID / PENDING / CANCELLED |
| 逐 testcase 结果 | PASS / FAIL / SKIP / MISSING / ERROR / NOT_RUN |
| 轨迹 | 完整 execution trajectory |
| 最终补丁 | 模型产出的 patch |
| 耗时 | 总时长与各阶段 |
| Badcase 归因 | 失败根因分析 |

### 跨运行晋升证据字段

来自 `grade.py` 的 `run_evidence`，用于证明required 3 base + 3 oracle runs：

```
run_id
source_commit
image_digest
log_sha256
spec_sha256
test_patch_sha256
```

> 单份报告无法自证 3+3 次运行；这些字段用于让**跨运行晋升校验器**确认证据完整。

---

## 六、区分度计算示例

```python
# 3 次运行结果
qwen_scores = [0, 1, 0]          # model_score_sum = 1
opus_scores = [1, 1, 1]          # model_score_sum = 3

# 条件 1 成立
assert opus_sum(3) > qwen_sum(1)   # 通过区分度

# 若双 0 场景
qwen_scores = [0, 0, 0]          # model_score_sum = 0
opus_scores = [0, 0, 0]          # model_score_sum = 0
qwen_pass_sum = 12               # 3 次 required PASS 总数
opus_pass_sum = 15               # 条件 2：15 > 12 → 通过区分度
```

---

## 七、自动化执行（`scripts/run_model_validation.py`）

规范要求 4 个模型、共 8 次调用（Qwen 3 + Opus 3 + GLM 1 + Kimi 1）并计算区分度。
手工执行易漏、易算错，统一用脚本完成。

### 7.1 端点与模型

协议均为 **Anthropic Messages**：`POST {base_url}/v1/messages`。
凭据存放在**仓库外**的用户级文件 `~/.workbuddy/harbor-windows-endpoints.json`（不入库），
交由 `--config` 传入；下表的 `base_url` 均**不含 `/v1`**（脚本会自行拼接 `/v1/messages`）。

| key | label | base_url | model | 鉴权头 | 次数 | 角色 |
|---|---|---|---|---|---|---|
| `qwen3.8-max` | Qwen3.8-Max-0902 | `https://llm-cz4pcezs463b102x.cn-beijing.maas.aliyuncs.com/apps/anthropic` | `qwen3.8-max-0902` | `x-api-key` | 3 | primary |
| `opus-5` | Opus 5 | `https://api.ebondai.com` | `claude-opus-5` | `x-api-key` | 3 | primary |
| `glm-5.3` | GLM-5.3 | `https://ark.cn-beijing.volces.com/api/coding` | `glm-5.3` | **`Authorization`** | 1 | auxiliary |
| `kimi-k3` | Kimi K3 | `https://ark.cn-beijing.volces.com/api/coding` | `kimi-k3` | **`Authorization`** | 1 | auxiliary |

关键参数（均在端点 JSON 内固化）：

| key | `max_tokens` | `request_timeout` | 备注 |
|---|---|---|---|
| qwen3.8-max | 65536 | **300** | ⚠️ **推理模型**：大改动量题上 thinking 会吃光**时间**预算（65536 tok ≈ 1150 s > 900 s → 请求永不返回）。**建议配 `thinking:{type:"disabled"}`**，详见 §7.10 |
| opus-5 | 16000 | 默认 | ebondai 官方给的 baseURL 带 `/v1`，这里**必须去掉** |
| glm-5.3 | 65536 | 1800 | **绝不要传 `thinking` 字段**（enabled → 强制深度推理吃光预算；disabled → 400） |
| kimi-k3 | 32000 | — | 可传 `thinking.type=disabled` 关闭思考，更快更稳 |

> ⚠️ 三类坑：
> ① aliyun 的 base_url **必须带 `/apps/anthropic` 后缀**，去掉后 `/v1/messages` 返回 404；
> ② **方舟（GLM/Kimi）只认 `Authorization: Bearer`**，传 `x-api-key` 会 401；
> ③ 方舟模型 id 必须**小写连字符**（`glm-5.3` / `kimi-k3`），写成 `Kimi K3` 会 404。
>
> ⚠️ 超时与静默的区分：aliyun 单请求上限 900 s、方舟 1800 s，且方舟强制深度推理时单步可达数分钟。
> 轨迹文件 mtime 长时间不更新**不等于进程已死**；判断存活性要看本机 `python.exe` 是否还在（见 7.4）。

### 7.2 命令

```bash
pip install httpx

# 全量（不传 --only 时按端点顺序串行跑完全部）
python -u scripts/run_model_validation.py \
    --tasks <题包目录> --out <题包类型目录> --layout flat \
    --config ~/.workbuddy/harbor-windows-endpoints.json

# 分片并行：把 4 个模型拆成 4 个独立进程，各写自己的日志
for M in opus-5 qwen3.8-max glm-5.3 kimi-k3; do
  python -u scripts/run_model_validation.py --only "$M" --skip-existing \
      --tasks <题包目录> --out <题包类型目录> --layout flat \
      --config ~/.workbuddy/harbor-windows-endpoints.json > "log-$M.txt" 2>&1 &
done
wait

# 冒烟（每模型 1 次，仅验证连通性）
python -u scripts/run_model_validation.py --tasks <题包目录> --smoke

# 平台回填分数后只算区分度
python -u scripts/run_model_validation.py --score-only --out <题包类型目录> --layout flat
```

**必须加 `-u`**：脚本输出重定向到文件时默认块缓冲，日志会长时间为空，无法判断进度。

可调项：`--only` / `--run-index` / `--skip-existing` / `--agent-max-steps`，
环境变量 `HARBOR_WINDOWS_MAX_TOKENS` / `TIMEOUT_SEC` / `MAX_RETRIES` / `ENDPOINTS_JSON`。

### 7.3 脚本职责边界（重要）

| 脚本负责 | 脚本**不**负责 |
|---|---|
| 发起 4 模型调用、重试 | 在真实 Windows Runtime 执行 F2P/P2P |
| 保存轨迹、补丁、token、耗时 | 产出正式分（`score`） |
| 区分 VALID / INVALID 并归因 | 判定 Golden / no-change |
| 计算 `model_score_sum` / `testcase_pass_sum` | |
| 给出条件 1 / 条件 2 准入结论 | |

因此 `per_testcase.json` 初值为 `NOT_RUN`、`report.json.score` 初值为 `null`，
**必须由平台 harness（`test.ps1` + `grade.py`）执行后回填**，再跑 `--score-only`。

> 这条分工是刻意设计：规范禁止用 Linux Mock 替代真实 Windows Runtime，
> 故模型调用层与评测执行层必须分离，不能由本脚本伪造分数。

### 7.4 VALID / INVALID 判定

脚本按响应内容自动分类：

| 分类 | 触发 | 结果 | 是否重试 |
|---|---|---|---|
| `credential_rejected` | `API-key is blocked` / `Invalid token` | **INVALID** | 否（重试无意义） |
| `auth_failed` | HTTP 401 / 403 | **INVALID** | 否 |
| `rate_limited` | 429 / `rate limit` | **INVALID** | 是 |
| `quota_exhausted` | `insufficient` / `balance` | **INVALID** | 是 |
| `network_timeout` / `network_error` | 超时 / DNS / SSL | **INVALID** | 是 |
| `model_unavailable` | `model not found` | **INVALID** | 否 |
| `upstream_5xx` | HTTP ≥ 500 | **INVALID** | 是 |
| `model_overloaded` / `context_overflow` | 显式过载/超长 | VALID（按真实结果记录） | 是 |
| 成功 | HTTP 200 | VALID | — |

失效运行会写 `error.json` 与 `badcase_attribution.md`，并在 `meta.json` 标 `retest_required: true`。

### 7.5 准入判定状态机

```
有效运行 < 3            → 待定（blocking: insufficient_valid_runs）
存在 INVALID 未补跑      → 待定（blocking: invalid_runs_not_retested）
3 次有效但分数未回填     → 待定（blocking: scores_not_filled）
─────────────────────────────────────────────
否则按条件 1 / 条件 2 判定 → True / False
```

> `--score-only` 退出码：`0` 无明确失败（含"待定"）／`1` 存在明确"不通过"。
> 把"待定"与"不通过"分开，是为了避免"分数还没回填"被误报成"区分度不合格"。

### 7.6 输出

```
delivery-extras/
├── model_summary.csv                # 各模型 runs/valid/invalid/score_sum
├── model_validation_report.md       # 区分度准入表 + 逐模型状态
├── model_validation_summary.json    # 机器可读
└── tasks/<task-id>/model_runs/<model>/run-N/
    ├── meta.json                    # 状态/耗时/token/归因/retest_required
    ├── response.md                  # 原始回复
    ├── patch.diff                   # 提取的补丁
    ├── per_testcase.json            # 逐 testcase（待平台回填）
    ├── report.json                  # 正式分（待平台回填）
    └── badcase_attribution.md       # 失败归因
```

### 7.7 权限配置模板

`scripts/model_endpoints.template.json` 提供端点和凭据字段模板。
复制为 `model_endpoints.local.json` 并填 Key（该名已在 `.gitignore` 中，不会入库）。

### 7.8 断点续跑与存活判定（长耗时运行的必备操作）

`--skip-existing`：某 run 的 `meta.json` 已存在且状态为 `VALID`/`INVALID` 时直接跳过。
被外部终止的运行**不会写 `meta.json`**，因此会被自动重跑，不会把半成品当成结果。
耗时可达 1–2 小时的批次务必带上此参数。

> ⚠️ **后台 shell 会在会话切换时被回收**：把分片运行挂在会话的后台任务里，
> 一旦会话被重建（例如长对话被压缩后继续），子进程可能连同 shell 一起被杀，
> 且不会写任何 `meta.json`。症状是**所有模型同时静默**（不是单个模型卡住），
> 与「某个模型自身很慢」的形态明显不同。
>
> 判定顺序：
> 1. `tasklist /FI "IMAGENAME eq python.exe"` —— 一个进程都没有就说明进程已死，与端点无关；
> 2. 用 `curl --max-time 20 -X POST {base_url}/v1/messages` 探端点，**无鉴权返回 401 即为正常**；
> 3. 确认端点正常后，带 `--skip-existing` 重启分片即可，已完成的 run 不会被重跑。

> ⚠️ **不要用 `nohup ... &` 启动长任务**（2026-10-01 实测第二次踩坑）：
> 在 shell 里 `nohup python ... & echo pid=$!` 会让**该工具调用立即返回**，
> 被 `&` 放到后台的 python 会随这次调用的 shell 一起被回收 —— 判据同样是
> `tasklist` 里 python 归零、且轨迹文件时间戳冻结。
>
> 正确做法：用 agent 工具**自带的**后台执行能力（`run_in_background`）直接跑前台 python 命令，
> 让工具持有该进程，不要自己 `&`、不要 `nohup`。
>
> 排查"是否只是变慢而不是死了"：看该 run 的 `trajectory-run-N.jsonl` 的 **mtime**。
> mtime 在推进 = 还在跑；mtime 冻结（本次冻结了约 75 分钟）且 `tasklist` 无 python = 已死。

### 7.9 Agent 命令挂死：`subprocess.run(timeout=)` 的管道 EOF 陷阱（必须知道）

**症状**：单个模型的 run **长时间静默**（十几分钟到无限），但
`tasklist` 里该 worker 进程还在、**没有任何子进程**、**没有活动 TCP 连接**，
CPU 增量恒为 `0.000s`。轨迹文件停在某个 `run_command` 的 assistant 步，一直没有对应的
`tool_result`。**不会自我恢复**，端点超时机制也救不了（它根本不在 API 调用里）。

**根因**：`agent_harness._t_run_command` 早期用
`subprocess.run(cmd, shell=True, capture_output=True, timeout=N)`。
当被执行的命令留下**持有 stdout 管道的后代**（agent 写探针脚本的典型形态：
`python probe.py` 内部又 `Popen` 了一个长跑子进程），超时分支里 CPython 会调用
**不带超时的** `process.communicate()` 去回收，而管道 EOF 要等所有继承写端的后代退出
—— 于是永久阻塞。

**修复**（已在 `agent_harness.py` 落地）：把输出重定向到**临时文件**而不是管道，
`Popen(...).wait(timeout)` 超时后先 `taskkill /F /T` 收整棵树再 `wait`。
文件没有管道 EOF 语义，超时可靠返回，且顺带能保留截止前的部分输出。

**排查工具**（本机 `wmic` 已被移除，PowerShell 通道可能不可用）：

```bash
# 列出进程树 + 完整命令行（纯 ctypes，不依赖 wmic / PowerShell）
python scripts/list_processes.py --filter python --tree
python scripts/list_processes.py --kill-tree <PID>     # 精确杀掉一棵树
```

判定阻塞 vs 空转：对可疑 PID 取两次 `GetProcessTimes` 的 CPU 增量。
**增量恒为 0 = 阻塞死锁**（必须重启）；有增长 = 只是慢。

回归验证脚本：`python scripts/verify_cmd_timeout_fix.py`
（A 段证明旧实现 45s 不返回；B 段证明新实现 10.6s 返回且无遗留后代；C 段证明普通命令无回归）。

### 7.10 Qwen 端点：thinking 会吃光**时间**预算（2026-10-07 实证）

**症状**：QWEN 在 agent 循环里**长时间零进展** —— 日志停在某轮之后，连续
`!! model call attempt N failed: TimeoutError: The read operation timed out`；
每次重试白等满 `request_timeout`（900 s），7 次重试 ≈105 min 后才整轮 `agent.status=error` 被剔除。
**重试同一 payload 同样爆炸**，不会自愈。

**三步定性**（探测脚本模板见 `scripts/qwen_probe.py`）：

| 探测 | 期望读数 | 含义 |
|---|---|---|
| 短请求 ×1 | 200 / ~1.5 s | 端点存活 |
| **3 并发 + ~84K tokens 长输入** | 全 200 / 8–11 s | 并发与长上下文**无恙** |
| **带 `tools` + `max_tokens=65536` 的 agent 风格请求** | **卡死 >120 s** | 复现故障 |
| 同上，`max_tokens=8192` | `stop_reason=max_tokens`，`blocks=['thinking']` | ★ 全部 token 烧在思考，**零 text / 零 tool_use** |
| 同上，加 `thinking:{type:"disabled"}` | **~2.9 s**，`stop_reason=tool_use` | ★ 关闭即恢复 |

**根因**：`qwen3.8-max-0902` 是**推理模型**。「重写大代码量」类题（如 wfmt-215 要重写 5 个模块的
Python 包）会让它每轮进入超长 thinking；65536 tok @≈57 tok/s ≈ **1150 s > 900 s 超时** → 请求永不返回。
**改动量小的题**（217 的 PowerShell 模块）thinking 短，故同一参数从不触发 —— 是
「任务改动量 × 推理模型 thinking 长度」的耦合，不是端点故障。

**处置**：给该模型加 `thinking: {type: "disabled"}`
（runner 侧即 `QWEN_EXTRA_JSON={"thinking":{"type":"disabled"}}`），并把 `request_timeout` 降到 **300**。
实证效果：同一请求由卡死 → **2.9 s 返回正确 `tool_use`**；分片跑到 turn 13 的耗时由 56 min → **≈24 s**。

> 关闭 reasoning **不触碰题面 / rubric / 判分逻辑**，故 task_version、epoch、controls 均无需变更；
> 已在别的 epoch 收口的题（如 217）**不必重跑**。

> ⚠️ `thinking.disabled` 的支持性**按端点而异**：本项 aliyun `apps/anthropic` 端点**接受**；
> 方舟（ark）的 GLM 传 disabled 会 **400**（见 §7.1 备注）。

### 7.11 计划任务 `-Execute` 必须写绝对路径（2026-10-07 实证）

用 `Register-ScheduledTask` 托管长耗时分片时，`-Execute` 写裸名 `powershell.exe` 会失败：
任务计划的**最小 PATH** 找不到它 → `LastTaskResult = 2147942402`（`0x80070002` 文件未找到），
任务显示 `State=Ready` 却**从不执行、不写任何日志**（极易误判为"脚本没跑"）。

```powershell
# 正确
$ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
New-ScheduledTaskAction -Execute $ps -Argument "-NoProfile -ExecutionPolicy Bypass -File `"<script>`" -Tag ... "
```

> 同源坑（§7.9 已记）：在 5.1 子进程里裸写 `powershell.exe` 同样 `CommandNotFoundException`。
> **凡由 Task Scheduler / 子进程拉起的 PowerShell，一律用绝对路径。**

---

### 7.12 「单轮大输出」撞传输层超时（2026-10-07 实证，**通用**）

**症状**：某个模型（此处 Opus 5 @ `4router.net`）在 agent 跑到第 6–9 轮后，
**连续 7 次 `TimeoutError: The read operation timed out`**，整轮被判 `agent.status=error` 而**被汇总剔除**
（不是 0 分，是**不计分**）→ `model_counts_complete=false` → 门禁挂。

**排除项（都实测过，全绿，别浪费时间）**：端点宕机（小请求 10 s）、大 payload（≈40K tokens 输入 33 s）、
代理（直连/代理同速）、多轮上下文（6 轮递增对话 2.6→28 s）、工具 schema、`max_tokens=64000`。

**真因**：runner 是**非流式**调用（`urlopen(...)` → `response.read()`），超时按「单次 recv 无数据」计算。
若题目要求**单轮整包重写**（多文件），模型的 thinking + 输出可达 **2 万+ tokens**；
实测该端点吞吐 **≈63 tok/s**（14 614 output tokens → **230.5 s**）→ 一旦跨过 `REQUEST_TIMEOUT`（当时 300 s）
即整包丢弃；**重试发送逐字节相同的 payload → 必然同样超时**，7 次重试全灭。

> 自证方法：`尝试次数 × REQUEST_TIMEOUT + Σ退避 == 该轮墙钟耗时`（本例 `5×300 + 165 = 20:49`，与日志末行吻合）。

**判定口诀**：**「小请求秒回、长输出必挂、同 payload 反复挂」→ 传输层超时，不是端点坏、不是题太难。**

**修复（按性价比排序）**：
1. **抬 `REQUEST_TIMEOUT`**：按 `max_tokens / 端点吞吐(≈60 tok/s) × 2` 取，例 `64000/60×2 ≈ 2100 s`，
   实用值 **1200 s**（本例）。改 `*_REQUEST_TIMEOUT` 属传输层，**不动 task_version / rubric / epoch**。
2. 若模型支持（如 Qwen），优先 `EXTRA_JSON={"thinking":{"type":"disabled"}}` 压制 thinking（§7.10）。
3. 出题侧规避：单轮改动量别设计成"一次重写 5+ 个模块"，或明确要求**一次一个文件**。

> **★ 后续修正（2026-10-07 21:20，勿再照抄第 1 条）**：把 `4router.net` 的 `OPUS_REQUEST_TIMEOUT`
> 抬到 **1200 s 后仍然失败** —— 该轮 `attempt 1` 恰好耗满 1200 s 才报错（20:57:43 起跑 →
> 21:22:13 记 `attempt 1 failed`），说明**该端点在长输出形态下无解**，抬超时只是把单次等待
> 从 300 s 拉长到 1200 s（更慢地失败）。**"抬超时"仅在端点本身健康、只是慢时有效**；
> 若抬到 2× 仍撞墙，应判定**端点不适配该负载**，直接换端点（本例换 `api.ebondai.com` 并按
> §7.13 收敛 `max_tokens` 后跑通）。**先做 §7.13 的交叉实验定量，再决定是抬超时还是换端点。**

**排障顺序（照做，勿跳）**：① 短请求探活 → ② 长输出测吞吐（`output_tokens / 秒`）→ ③ 算
`预估最长单轮 tokens / 吞吐` 与 `REQUEST_TIMEOUT` 比大小 → ④ 不足则抬超时 → ⑤ 重跑，别再调难度/turn。

### 7.13 网关「非流式响应时长硬墙」与 `max_tokens` 收敛（2026-10-07 实证，**通用**）

**症状**：`api.ebondai.com` 上**非流式**请求**固定 126 s 整**报 `HTTP 502 Bad Gateway`，
与小请求秒回（3.7 s）形成鲜明对比。抬 `REQUEST_TIMEOUT` **无用**（墙在网关侧，不在客户端）。

**定性交叉实验**（同一 key / 同一 model，逐项单变量）：

| 用例 | 结果 |
|---|---|
| `max_tokens=8192` + 短回复（PONG） | OK **4.0 s**，out=5 |
| `max_tokens=64000` + 短回复 | OK **6.3 s**，out=5 |
| `max_tokens=8192` + 写 200 行代码 | OK **102.0 s**，out=8192，`stop=max_tokens` |
| `max_tokens=32000` + 写 200 行代码 | OK **117.4 s**，out=9723，`stop=end_turn` |
| `max_tokens=64000` + 写 200/400 行 | **FAIL 126.1 / 127.0 s → 502** |
| `max_tokens=8192` + `thinking:{"type":"disabled"}` | OK 101.8 s，输出**逐 token 与基线相同** |

**结论**：
1. 吞吐 **≈ 80 tok/s**；**非流式安全区 ≈ 9 500 output tokens ≈ 120 s**，越过即 126 s 被网关切断。
2. **`max_tokens` 越大越危险** —— 它是"放任模型写多久"的闸门，不是无害上限。设成 64000 等于
   允许模型一直写到撞墙；设成 8192 则模型到点即停（`stop=max_tokens`），**反而安全**。
   → **`max_tokens` 应按「单轮真实最大输出 × 1.2」取，而不是按端点上限取。**
3. 该端点 `claude-opus-5` **无 thinking**（开/关输出逐 token 相同），故无需 `EXTRA_JSON` 压制。
4. `REQUEST_TIMEOUT` 应**略高于网关墙**（例 180 s）：让网关的 502 先返回并被 runner 捕获快速重试，
   而不是本地空等到 1200 s。

**流式可绕过硬墙**（实测）：同端口 `"stream": true` 请求，900 行输出 → **OK 639.9 s**
（首字节 97.3 s，2.2 MB）。即 126 s 是「**非流式响应总时长**」限制，不是端点能力上限。
若题目确实需要单轮超大输出，可在 runner 侧改流式；否则优先按第 2 条收敛 `max_tokens`。

**★ UA 陷阱（同源）**：该端点前挂 Cloudflare，`python-urllib` 默认 UA 被拦 →
`HTTP 403 error code: 1010`（**不是**鉴权失败，别误判为 key 无效）。
所有自研探测脚本必须带 `User-Agent: Mozilla/5.0`；curl 默认 UA 不受影响，
故「curl 通、python 不通」时先查 UA。

**排障口诀（先在端点侧定量，再动 runner）**：短请求探活 → 固定时长 502 即"网关硬墙" →
做 `max_tokens × 输出长度` 交叉实验定安全区 → 收敛 `max_tokens` → `REQUEST_TIMEOUT` 设墙值 + 50%。

### 7.14 流式是「单轮大输出」的正解（2026-10-07 定论，**替代 §7.12 第 1 条**）

§7.12/§7.13 的"抬超时 / 收敛 `max_tokens`"都是**绕**，本节的**流式改造是正解**，已在 `wfflab__wfmt-215` 打通。

**做法**：`runner.py` 已内置流式。`call()` 里 `stream = bool(cfg["stream"])`，为真则 body 带
`"stream": True` + `headers["accept"]="text/event-stream"`，走 `_read_stream()`；
**SSE 解析**：逐行取 `data:` → `json.loads` → 按 `type` 归并
（`content_block_start` 建块、`text_delta` 拼文本、**`input_json_delta` 拼 tool_use 的 partial_json 并在
`content_block_stop` 一次 `json.loads`**、`message_delta` 取 `stop_reason`/`usage`），
返回结构与非流式**逐字节兼容**，agent 主循环零改动。开启方式：`.env.local` 加 `<ALIAS>_STREAM=1`。

**为什么它是正解**：流式下"单次 recv 无数据"永不发生（字节持续到达），**既绕开客户端 `REQUEST_TIMEOUT`，
又绕开网关的"非流式响应总时长"硬墙**（§7.13 的 126 s 只针对非流式）。

**4router.net + 流式实测（`_probe4r.py`，全绿）**：

| 用例 | 结果 |
|---|---|
| 非流式小请求 | OK 2.3 s，PONG |
| 非流式 + tool_use | OK 2.7 s |
| **流式 + tool_use** | OK（SSE 事件流正常） |
| **流式 + `max_tokens=32000` 大输出** | OK **167.9 s / 289 KB**（无余额/墙钟问题） |

> ★ **§7.12「4router 长输出无解」的结论作废**：当时是**非流式**调用；同一端点在**流式**下完全可用。
> 换端点前**先开流式**，别再把健康端点评为"不适配"。同理 §7.13 的 ebond 126 s 墙，流式可绕过
> （但 ebond 该 key 后来**余额耗尽 403 INSUFFICIENT_BALANCE**，属账户问题，与流式无关）。

**结局佐证（215 资格门禁）**：OPUS×3 流式 @4router → `[1,1,0]=2`，QWEN `[0,0,0]`、GLM `[1]`、KIMI `[0]`
→ `qualified=true`；此前非流式 @4router 恒 `agent.status=error` 被剔除。

**新排障顺序（取代 §7.12 第五节）**：① 短请求探活 → ② **直接开 `<ALIAS>_STREAM=1` 重跑** →
③ 仍失败再测吞吐/抬超时/禁 thinking → ④ 最后才考虑换端点。**`agent.status=error` 先怀疑传输层，别先怀疑难度。**

---

## 八、多模型自检

```
[ ] Qwen3.8-Max-0902 独立运行 3 次（全 VALID）
[ ] Opus 5 独立运行 3 次（全 VALID）
[ ] model_score_sum 计算正确
[ ] 区分度满足（条件 1 或条件 2）
[ ] 无 INVALID 未补跑
[ ] GLM-5.3 ≥1 次有效运行
[ ] Kimi K3 ≥1 次有效运行
[ ] 无模型无关 infra/权限/依赖/Verifier 故障
[ ] Golden 3×1，无 SKIP/MISSING/ERROR/旧产物
[ ] no-change 3×0，P2P 全过 + 核心 F2P 失败
[ ] 至少 1 次干净重建/恢复复验
[ ] 运行记录与证据字段齐全
[ ] 正式分已由平台 harness 回填（非脚本伪造）
```

---

## 九、离线复评：改完 `tests/**` 后免重跑（2026-10-06 实证）

**要解决的问题**：按交付规范 `qualification-gates.md` §Repair semantics，任何题面变更（instruction / workspace / environment / test / rubric / judge / Golden）都会 **invalidate 之前的 controls 与模型得分**，必须开新 epoch **重跑整套**（QWEN×3 + OPUS×3 + GLM×1 + KIMI×1 + controls 3+3，实测量级数小时）。于是"只改一处检查、想知道效果"的代价极高，容易退化成凭猜测改题面。

**关键事实**：本地 runner 带 `-KeepWork` 时（`run.ps1` / `run_matrix.ps1` 均传该开关），**模型在容器内改完的 workspace 会落盘**：

```text
<runner>/work/<run_id>/case/environment/workspace/WReparse/   # 模型改完之后的实现
<runner>/work/<run_id>/view/environment/                      # 候选可见视图（仅 instruction.md + environment）
```

`case/` 是完整任务树（instruction.md + task.toml + source.json + environment/ + tests/ + solution/ + results/）。
**判据**：文件体积明显大于原始 candidate，例如 `PathSemantics.ps1` 3414 → 4166 字节。

**离线复评流程**（全程用临时副本，**绝不碰原题包**）：

1. `Copy-Item -Recurse` 把**当前**题包（含新 tests）复制到临时目录；
2. 用 `work/<run_id>/case/environment/workspace/WReparse` 以 `robocopy /MIR` 覆盖 `environment/workspace/WReparse`；
3. 跑 `<tmp>/environment/run.ps1 -TaskRoot <tmp>`（**必须用 `powershell.exe` 5.1 绝对路径**，见下）；
4. 读 `<tmp>/results/result.json` 的 `verdict`、`results/checks.json` 的逐项状态，即可算出新口径得分。

**可信度已验证**：新口径下"原检查项"的通过/失败与当时**容器实跑逐项吻合**，包括"agent 死在上游超时、从未改代码"那轮，复评得到与原始 candidate 一致的失败集。

**用法边界**：离线复评只用于**预判**（值不值得付重跑成本、要不要换题），**不能替代**规范要求的容器 controls / 模型矩阵证据 —— 正式资格判定仍须真实重跑，并在证据里标明 epoch。

**本机跑 Windows 题的三个硬要求**：

- `powershell.exe` 必须用绝对路径 `$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe`。在 5.1 子进程里裸写 `powershell.exe` 会 `CommandNotFoundException`（PATH 解析问题，实测踩过）。
- 经 PowerShell 工具执行时**看不到 stdout**，一律 `& <exe> ... *> <file>` 重定向后再读文件。
- fixture 需要 junction / 符号链接 / 硬链接：管理员权限 + `cmd /c mklink /D` 即可（junction 与硬链接本就不需提权）；`prepare.ps1` 会先清理重建，可反复跑。

