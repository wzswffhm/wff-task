## 16 次独立难度样本集（最高优先级）

一次难度 job 固定运行 **16 个独立 Docker Trial**，16 个 trial 必须使用同一份冻结的
`instruction.md`、workspace、tests 与镜像修订。培训手册明确“根据电脑配置推荐并发执行”，
示例为最多 4 个 Trial 同时运行；本机按用户当前指示使用 **16 路并发**：

```bash
--n-attempts 16 --n-concurrent 16 --n-concurrent-agents 16 --max-retries 3 --agent-setup-timeout-multiplier 3
```

### 任务运行时限（硬规则）

Harbor 任务、Verifier 和环境构建**不得设置固定时间上限**。`task.toml` 中不得出现
`[agent].timeout_sec`、`[verifier].timeout_sec` 或 `build_timeout_sec`；启动命令和本地
监督脚本也不得通过 `timeout`、`gtimeout`、watchdog 或到时 `kill` 提前结束 trial。测试脚本
同样不得给任务主体测试设置 `subprocess.run(timeout=...)` 一类上限。

运行中的容器应当等待 Agent、Verifier 和结果写入流程自然结束。仅当 Docker/Harbor 已明确报告
基础设施错误，或用户明确要求停止时，才允许清理对应容器；不得把“运行较久”当作停止理由。
网络请求、依赖下载等第三方客户端自身的连接超时不属于 Harbor 任务时限，但不能用它们包装或终止
整个 trial。

一个可交付的难度候选 job 必须启动并收集 16 条独立 Trial。最终交付样本集从 `16×N` 个已结束
job 中**各条正常完成且有 `reward.txt` 的 Trial** 选择恰好 16 条：`reward<1` 至少 13 条，且
`reward=1` 至少 1 条。某些 Trial 的 timeout、cancel、缺 reward 或 agent/verifier/setup 基础设施
错误只排除对应 Trial；同一 job 里其他正常完成且有 reward 的 Trial 仍可进入候选池。完整批次和
异常 Trial 必须保留并在 manifest 中逐条标记，不能把异常 Trial 当作分数。

**批次闭环（不得早停）：** 每个 job 必须让 16 个独立 Trial 以同一冻结提示词完整结束，再读取全部 trial
的终态和 reward。可连续完成多个完整 job（`16×N`）；交付时允许跨 job 选出 16 条，但必须保留每个原始 job 完整数据，并在 `difficulty-manifest.json` 明示这是一份跨 job 的选样集、列出每条来源和确定性选样规则。不得删除、隐藏或改写未入选/失败 Trial，也不得把选样集伪称为一个原始 16-trial job。

每完成一批，更新 `difficulty-manifest.json`：批次目录、16 个 trial ID、reward、终态、是否有效、
冻结修订 hash、镜像 digest 和完整原始数据位置。任务级 manifest 必须列出所有 batch；选样完成后新增 `selected_trials`（恰好 16 条，每条含 source_job、trial_id、reward、terminal、selected_reason）和 `selection_rule`。不得把未入选批次从任务级记录抹掉。

**交付选样优先级：** 在满足恰好 16 条、`reward<1` 至少 13 条且 `reward=1` 至少 1 条的前提下，
按确定性顺序优先选择尽可能多的正常 `reward=0` Trial；至少保留一条正常 `reward=1`。timeout、缺
reward、429 等 verifier 基础设施异常不可当作 0 分补入。manifest 的 `selection_rule` 必须如实写明
该“最大化 reward=0、保留至少一条 reward=1”的规则和各条来源。

### 新批次前后汇报（硬规则）

每次启动新的 16-trial job 前，先向用户简短汇报一次真实采集状态：已完成的有效 batch、当前
候选池 `reward<1` / `reward=1` 数量、距离最终 16 条（`<1`≥13、`=1`≥1）还差多少，以及即将
启动的 job 名称、16 路并发和复用的镜像。批次自然完成后，再汇报本批完整 16 条的 reward 分布、
异常数及累计候选池；不得只报部分已完成 trial。基础设施作废批次也要说明其真实原因，但不得将其
计入候选池。

每次重启 batch 可以复用同一 Docker 镜像，前提是修订 hash 不变；启动前必须验证：

1. `docker image inspect <image>` 成功并记录 image ID/digest；
2. 以该镜像验证项目的最小构建/测试命令、Agent CLI 版本、RewardKit 可执行；
3. Dockerfile、workspace、tests、solution、instruction 的冻结 hash 与校准一致。

任一项变化（含 Dockerfile）→ 镜像不可复用，先重新构建并重新跑 baseline+oracle。修订未变时，
下一批**必须复用**先前通过验证的镜像，不重新拉取或构建；但每次启动前仍必须重复上述验证并记录
结果。推荐运行参数为 `--no-force-build`；若 inspect 或最小验证失败，则停止复用、重建并重校准。