## P0 硬门禁（打 zip 前必须全过，否则禁止交付）

对照质检单 `zq2026080704332` 的两类不通过原因；任一条命中即 **FAIL，禁止打包/提交**：

### P0-1 校准必须跑通，且必须打进上传 zip（smoke 可选）

> 质检曾挂：校准缺失 —— 无 Oracle/baseline（旧单亦提 smoke；**本 skill 现行：smoke 可以不跑、可不进包**）

本地评测（同一冻结修订）**必须**跑通，并且 **提交 zip 的 `jobs/` 里必须能直接看到** 下列目录：

| 门 | 典型目录名 | 必须？ | 必须结果 |
|----|------------|--------|----------|
| baseline | `jobs/baseline` 或 `jobs/nop` | **必须** | `reward=0` |
| Oracle | `jobs/oracle` | **必须** | `reward=1`，且 verifier 证明 **Reward Kit / quality 已执行** |
| smoke | `jobs/qwen-smoke*` 或 `jobs/*-smoke*` | **可选** | 若跑了：真实 Agent 完整跑完、无基础设施异常；**不跑不阻断交付** |

另加：`jobs/selected-trials/` 下恰好 16 条入选难度 Trial，和 `difficulty-manifest.json` 的跨 job 选样来源清单。

#### 全量本地备份 → 再打精简上传包

打 zip / 上传**之前**：

1. **先把当前 task 目录全量复制一份留作备用**（含全部 `jobs/`：校准、成功难度门、失败试验等）。  
   推荐路径：`task/_full_job_backups/<作业ID>/<task-name>-full-<YYYYMMDD-HHMM>/`  
   （**绝不进上传 zip / 不传飞书**）
2. 备份完成并确认可还原后，再做 **提交用精简包**：`jobs/` **必须保留**  
   `baseline|nop` + `oracle` + `selected-trials/` 下恰好 16 条入选 Trial；复制时保留原始 job/trial 标识，提交 manifest 的 `selected_trials` 必须给出 source_job、trial_id、reward、terminal 和 selected_reason。若已跑过 smoke 可一并打进，  
   **未跑则不要为凑包去补跑**。未入选/失败 job 不进上传包，但完整原始数据必须留在本地全量备份和任务级 manifest 中；不得把 `selected-trials/` 伪称为单一原始 job。

提交 zip / 飞书附件里 **必须删除、不要打进包**：

- 失败的难度门、旧 rounds、超时作废的 job
- `_auto_loop_state`、`_archive*`、`_full_job_backups` 等本地辅助目录

**禁止：** 只交难度门、把 baseline/oracle 留在本地「自己知道就行」——质检只看上传包。  
**禁止：** 用难度门里某个 trial 冒充未跑过的 baseline/oracle。全量备份仅本地备用。  
**允许：** 跳过 smoke，直接在 baseline+oracle 通过后进难度门。

### P0-2 rubrics / rewardkit 不可缺失

> 质检原文：rubrics 完全缺失 —— quality.toml 仅 `[quality] version=1` 空壳, 未接入 rewardkit

**禁止交付** 若出现任一情况：

- `tests/quality.toml` 只有 `[quality]` / `version = 1` 或等价空壳
- 无 `[judge]` + 至少 2 条任务相关 `[[criterion]]`
- `tests/test.sh` **未调用** `uvx --from harbor-rewardkit==<pin> rewardkit ...`
- 镜像无 `uv`/`uvx`，或未预热 pinned rewardkit（导致 verifier 基础设施失败）
- Oracle `reward=1` 但无 quality 分量 / judge 未真正跑过（确定性失败应短路，**不得**在 nop 失败时调 judge）

打包前对 **即将上传的 zip** 再验一遍：解压后 `quality.toml` 仍非空壳、`test.sh` 仍含 rewardkit；Oracle job 日志能证明 quality 跑过。

最小合法 `quality.toml` 骨架（criterion 必须改成本题语义，禁止照抄空话）：

```toml
[judge]
judge = "anthropic/qwen3-max"
reasoning_effort = "none"
files = ["/app/<实际改动路径>"]

[[criterion]]
name = "behavior_contract"
description = "本题可观察行为/兼容边界（写具体，不写套话）"
type = "binary"
weight = 2.0

[[criterion]]
name = "fix_locality"
description = "改动应落在相关模块，无无关大面积 churn / 旁路作弊"
type = "likert"
points = 5
weight = 1.0

[scoring]
aggregation = "weighted_mean"
```

`test.sh` 约定：

1. 先跑确定性检查（pytest / `@criterion` 程序化部分）。
2. 失败 → 写 `reward=0`，**不调** judge。
3. 成功 → 调 pinned `rewardkit`；按项目要求聚合（常见程序化 60% + quality 40%，以当批文档为准），写入 `/logs/verifier/reward.txt` 或 flat `reward.json`。

详情与命令见 [references/verifier-rewardkit.md](references/verifier-rewardkit.md)。