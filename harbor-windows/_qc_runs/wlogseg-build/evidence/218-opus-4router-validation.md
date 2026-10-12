# wfflab__wlogseg-218 · Opus 5 补跑（4router.net）与区分度准入

日期：2026-10-12　执行：本机真实 Windows Runtime（非 Docker、非 Linux Mock）

## 一、本轮补的是什么

218 题包的模型验证此前只完成 **Qwen3.8-Max-0902 ×3 / GLM-5.3 ×1 / Kimi K3 ×1**，
**Opus 5 ×3 缺失**（`extras/model_runs/` 下无 `opus-5/`），因此区分度无法判定。
本轮按用户指定端点 **`https://4router.net`（模型名 `claude-opus-5`）** 补齐三轮并重算准入。

## 二、端点实测：两种「不是模型能力」的故障

4router.net 在账号池拥塞时不会回 5xx，而是给两种伪信号，**若按正常响应处理会把端点故障
记成模型无改动（0 分）**：

| 形态 | 表现 | 误判后果 |
|---|---|---|
| **HTTP 200 伪响应** | 200 + 文本 `[No upstream account is currently available. Please retry later.]`（或「⚠️ 上游模型未返回任何内容…」），`stop_reason=end_turn`、`output_tokens=0`、无 `tool_use` | agent 主循环直接结束 → `invalid_reason=agent_produced_no_change` |
| **心跳挂起** | 连接建立、SSE 心跳持续但无内容，**read timeout 永不触发**（实测非流式/流式都可挂 >9 分钟；215 上正常首步仅 4–8 秒） | 单轮无限等待，墙钟被白耗 |

**首次尝试（15:47 启动）三轮全 INVALID，墙钟合计仅 1.5 分钟** —— 「太快 + 零输出」即端点伪响应。

## 三、harness 侧修复（只动调用层，不动题面 / 测试 / 判分 / 身份）

| 层 | 位置 | 修复 |
|---|---|---|
| 判定 | `skills/harbor-windows/scripts/agent_harness.py` → `_upstream_unavailable()` | 无 `tool_use` 且（text 命中账号池/空响应提示，或 无 text 且 `output_tokens==0`）→ 判伪响应；有真实 `tool_use` 一律放行 |
| 请求 | 同上 → `run_agent()` 请求循环 | 伪响应整轮重试，`HARBOR_WINDOWS_UPSTREAM_RETRIES`（本次 8）；传输异常仍按 `HARBOR_WINDOWS_AGENT_STEP_RETRIES`（本次 6）重试 |
| 传输 | 同上 → `_post()` | 新增**整次请求墙钟上限**（本次 `OPUS_REQUEST_TIMEOUT=240`）：`iter_lines` 内检查 deadline，超时抛 `TimeoutError` 交上层重试 —— 这是心跳挂起的唯一有效兜底（read timeout 对它无效） |

> 修复不触碰 `task_version` / `task_hash` / rubric / epoch，属传输与调用层；
> 已在 `skills/harbor-windows/references/08-model-validation.md` §7.15 留档。
> 同源坑补记：`judge_runs.py` 调用裸名 `powershell` 会在最小 PATH 下 `WinError 2`，
> 已改为绝对路径 `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe`。

## 四、Opus ×3 运行结果（4router.net）

| run | agent 状态 | 墙钟 | 步数 | 输出 tokens | 补丁字节 | 判分 | 逐项 |
|---|---|---|---|---|---|---|---|
| run-1 | VALID | 1028 s | 36 | 17 756 | 17 423 | 0 | 23/25 |
| run-2 | VALID | 750 s | 28 | 19 381 | 38 919 | 0 | 24/25 |
| run-3 | VALID | 729 s | 38 | 19 794 | 17 844 | 0 | 23/25 |

判分：`tests/test.ps1`（本机真实 Windows Runtime，`run_tests.ps1` 注入式隐藏套件），
逐轮 `run_validity=VALID`、`patch_applied=true`，证据在 `extras/model_runs/_judge/opus_5_r*__verifier/`。

三轮共同的失败项是同一批 F2P 难点：

- `f2p-truncated-segment-body-reports-truncated`（3/3 失败）
- `f2p-index-entry-mismatch-reports-structure`（run-1、run-3 失败）

对照：Kimi K3 在同一题 25/25 全过、Golden 为 1，说明该难点**可解**，非题面/测试缺陷。

## 五、区分度准入（全模型汇总）

| 模型 | 有效轮次 | score_sum | testcase_pass_sum | 状态 |
|---|---|---|---|---|
| Qwen3.8-Max-0902 | 3/3 | 0 | 33 | READY |
| **Opus 5 @ 4router.net** | **3/3** | **0** | **70** | **READY** |
| GLM-5.3 | 1/1 | 0 | 23 | READY |
| Kimi K3 | 1/1 | 1 | 25 | READY |

```
条件 1: Opus5.model_score_sum(0) > Qwen.model_score_sum(0)   → 不成立
条件 2: 双 0 且 Opus5.testcase_pass_sum(70) > Qwen(33)        → 成立
```

**准入结论：PASS（条件 2）**。无 INVALID 运行，8 轮（Qwen×3 + Opus×3 + GLM×1 + Kimi×1）全部 VALID。

## 六、复现命令

```powershell
$py = 'C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe'
# 1) 从 runner/.env.local 还原 4router 端点并探活（凭据只落 %TEMP%）
& $py harbor-windows\_qc_runs\wlogseg-build\opus_4router_probe.py
# 2) Opus ×3（带轮次级重跑；全 VALID 后自动同步进题包）
$env:HARBOR_WINDOWS_AGENT_STEP_RETRIES='6'; $env:HARBOR_WINDOWS_UPSTREAM_RETRIES='8'
& $py -u harbor-windows\_qc_runs\wlogseg-build\run_opus218.py --attempts 6 --runs 3 --sync
# 3) 判分回填 + 区分度
& $py harbor-windows\_qc_runs\wlogseg-build\judge_runs.py --task harbor-windows\wfflab__wlogseg-218-v1.0.0-delivery --models opus-5
& $py harbor-windows\_qc_runs\wlogseg-build\score_218.py
```

## 七、本步之后的待办（不在本轮范围）

`jobs/<job-id>/{agent,verifier}` 证据落盘、`_index` 登记、打交付 ZIP、飞书回写、git 提交。
