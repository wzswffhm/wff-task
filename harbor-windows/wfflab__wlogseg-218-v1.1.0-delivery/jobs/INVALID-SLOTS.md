# 无效槽位说明（wfflab__wlogseg-218）

本文件与 `invalid-slots.json` 是**同一份口径**的两种呈现：机器可读版供下游过滤，
本文件供人读。二者都只是**注解层**——`jobs/` 下的原始试次记录与日志保持原样，未被改写。

## 结论（本归档：task_version 1.1.0）

**本归档无无效槽位。** 14 轮全部 `run_validity=VALID`，reward 均落在 {0,1}，
没有出现供应商配额、限流、传输或超时失败，也没有出现 `error` 状态。

因此 `invalid-slots.json` 的 `slots` 为空数组——统计时无需排除任何试次。

| 轮次 | 角色 | reward | 有效性 |
| --- | --- | --- | --- |
| `ctl-nop-1` | nop | 0 | VALID |
| `ctl-nop-2` | nop | 0 | VALID |
| `ctl-nop-3` | nop | 0 | VALID |
| `ctl-oracle-1` | oracle | 1 | VALID |
| `ctl-oracle-2` | oracle | 1 | VALID |
| `ctl-oracle-3` | oracle | 1 | VALID |
| `model-glm-1` | model | 0 | VALID |
| `model-kimi-1` | model | 0 | VALID |
| `model-opus-1` | model | 0 | VALID |
| `model-opus-2` | model | 0 | VALID |
| `model-opus-3` | model | 0 | VALID |
| `model-qwen-1` | model | 0 | VALID |
| `model-qwen-2` | model | 0 | VALID |
| `model-qwen-3` | model | 0 | VALID |

## 为什么不把失败轮按 0 分计（统一口径）

1. 供应商配额 / 限流 / 传输 / 超时失败与候选实现无关；
2. 失败路径写出的 `reward=0` 是占位值，verifier 未对候选修订真正跑过；
3. 甲方要求第 2 条与本项目验收一票否决条款均禁止把环境/基础设施缺陷记为模型 0 分。

## 重试与替代规则（统一口径）

- 无效槽位**绑定原计划槽位**（同 alias、同一次、同顺序位置），替代不给该模型加权；
- 只有传输/配额/超时类失败才重试；**我方环境缺陷**先修复，再整槽重跑；
- 重试是**全新试次**，不从失败答案续跑，也不合并进无效记录；
- 每个替代试次保留自己的起止时间与 runner 身份。

## runner 身份口径

本轮每次运行的执行时 runner 版本由 harness 记录在对应试次的
`agent/model-result.json` 的 `runner_sha256` 字段中；归档值即执行时的同一文件。
系统库/容器侧身份（`task_checksum`、镜像 digest）由每轮的 `result.json` 与 `lock.json` 固化。
