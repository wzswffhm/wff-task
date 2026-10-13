# 无效槽位说明（wfflab__wchunk-216）

本文件与 `invalid-slots.json` 是**同一份口径**的两种呈现：机器可读版供下游过滤，
本文件供人读。二者都只是**注解层**——`jobs/` 下的原始试次记录与日志保持原样，未被改写。

对应质检条目：`ZQ004-02｜证据不足｜Kimi 0 分混入 API 配额失败`。

## 结论（本归档：task_version 1.2.1）

**本归档无无效槽位。** 1.2.1 返修的 14 轮重跑全部 `run_validity=VALID`，
其中 Kimi K3 一轮为 `verdict=1`，是**正常求解结果**，不是配额失败后的占位 0 分。

因此 `invalid-slots.json` 的 `slots` 为空数组——统计时无需排除任何试次。

| 试次 | 角色 | verdict | 有效性 |
| --- | --- | --- | --- |
| `task__IDQfkzs` | candidate / kimi-k3 | `1` | `VALID` |

## 历史记录（上一版归档 task_version 1.2.0，已由重跑替代）

1.2.0 归档中曾有 1 条 Kimi 试次因**供应商配额**失败，当时未被重跑：

| 项 | 值 |
| --- | --- |
| 试次目录 | `jobs/task__5Bygi5c`（**不在当前归档中**） |
| original_job_id | `74f9dd1b-95d6-540b-bc70-7b3bdf5cb1a4` |
| 模型 | `kimi-k3`（alias `KIMI`，role candidate） |
| 状态 | `error` —— HTTP 429 `AccountQuotaExceeded`（周额度用尽） |
| 起止 | `2026-10-11T03:44:49.400+08:00` → `2026-10-11T04:46:26+08:00` |
| 失败前 | 7 turns / 19 tool_calls（模型确实在作答，不是立即失败） |
| 归档 reward | `0.0` ——**失败路径写出的占位值，不是能力测量** |
| 处置 | 已按下方规则在**同一计划槽位**重跑：`20261013T145609-candidate-kimi-k3-01-c194` → `verdict=1` |

该历史条目原样保留在 `invalid-slots.json` 的 `superseded_history` 中备查，
**不计入本次统计**。

## 为什么不按 0 分计

1. 失败发生在**供应商配额**，与候选实现无关；
2. 归档 `reward=0.0` 由 runner 的失败分支写出，verifier 从未对候选修订跑过；
3. 质检口径与 `VALIDATION.md` 一票否决第 14 条均禁止把环境/基础设施缺陷记为模型 0 分。

## 重试与替代规则（统一口径）

- 无效槽位**绑定原计划槽位**（同 alias、同一次、同顺序位置），替代不会给该模型加权；
- 只有传输/配额/超时类失败才重试；**我方环境缺陷**（镜像、挂载、权限、runner bug）
  先修复，再整槽重跑；
- 重试是**全新试次**，不从失败答案续跑，也不合并进无效记录；
- 每个替代试次保留自己的起止时间与 runner 身份。

## runner 身份口径

归档字段 `runner_sha256_at_archive` 只表示**归档时**的 `runner.py` 版本。
1.2.0 旧轮执行时的 runner 版本没有随轮次记录，因此不声称它等于执行时版本；
自 1.2.1 起，runner 在每次运行时会把 `run_time_identity`（task_hash / image digest /
捕获时间）与该轮的 `task_identity.json` 一并写入，**执行时身份不再缺失**。
