# OBM 本批次默认配置

## 权威输入

- 需求：`D:\hc\obm\需求\OBM Source 收集说明书-正式.md`
- 质检工具：`D:\hc\obm\质检工具\obm-review-skills`（每次开始时读取 `VERSION` 并核验 `SHA256SUMS`）
- 视频：`D:\hc\obm\OBMsource.mp4`
- 专家画像：`D:\hc\obm\OBM 招募画像-对外.md`
- Benchmark 目录：`D:\hc\obm\Benchmark`
- Benchmark 解压工作区：`D:\hc\obm\cache\benchmark-workspaces`
- 本地质检配置：`D:\hc\obm\cache\benchmark-workspaces\benchmark-locations.local.json`
- DeepSWE 本地包：`D:\hc\obm\Benchmark\deep-swe-main.zip`
- DeepSWE ZIP SHA-256：`047878e8294978ad24868aafca1e8236fcd440252aaa057f352cb7d2eb155df3`

本地 ZIP 是本批次权威版本，不要求关联 release tag 或远端 commit。开始候选工作时重新计算 SHA-256；哈希变化即视为新版本，旧检索记录和旧跑分不能直接复用。

当前工作区已准备 DeepSWE、SWE-Marathon、FrontierSWE、ProgramBench 和一份未定版本的 Terminal Bench 语料。未定版本 Terminal Bench 只参加全语料 Source 复用扫描，不能作为 `terminal_bench3` 或 `terminal_bench4` 的 related task 解析源。当前优先 DeepSWE，因此该限制不阻断首题生产。

质检证据采集必须显式传入：

```powershell
--workspace D:\hc\obm\cache\benchmark-workspaces `
--config D:\hc\obm\cache\benchmark-workspaces\benchmark-locations.local.json `
--governing-document 'D:\hc\obm\需求\OBM Source 收集说明书-正式.md'
```

## 用户确认的选择

| 配置项 | 当前值 |
| --- | --- |
| benchmark | `deepSWE`（来源包 `deep-swe-main.zip`） |
| domain | `Operations/Finance/Ledger Reconciliation` |
| language | Python |
| storage | 优先 SQLite `:memory:` 或抽象的内存存储；确有工程必要时使用开源 NoSQL |
| expert persona | 资深后端工程师，且最终人工作者应能说明复杂代码库与账务一致性经验 |
| proposal type | A：新建离线多模块 Python repo + 原创新需求 |
| allow_network | `false` |
| proposal template | `A_modification_idea` + `B_modification_details` + `C_agent_task` + `D_task_difficulties` |
| commercial software | 避免 |
| completion | 每次正式生产至少产出并上传 1 个完整达标作业；候选失败后自动继续，直到成功或触发明确硬阻断/硬上限 |

`domain`、`proposal_type` 和 `allow_network` 是当前推荐元数据。写入后还须按接收方映射工具核对。

## 首候选能力锚点

- `related_question`：`sqlite-utils-safe-import-checkpoints`
- 选择依据：它是 DeepSWE 中的 Python 题，使用嵌入式数据库，考察跨 API/CLI 的事务检查点、写后不变量验证、失败后的精确回滚和持久化状态管理。
- 差异化方向：金融账务/清算中的批次幂等、借贷平衡、冲正、乱序事件、不可变审计和确定性重放。不得复用原题的安全导入 API、测试、solution、patch 或只替换业务名词。
- 预期形态：提供一个离线、多模块 Python 后端脚手架，默认以内存数据库运行；让 agent 在既有接口和兼容性约束下完成原创跨模块功能。具体题面、验证方案、难点和专家经验写入 Step 4 交付并与 sources 保持一致。

候选检索只能读取 benchmark 的 `instruction.md` 和 `task.toml`。不得读取同一任务目录下的测试、solution、patch 或其他可能泄漏实现的信息。

## 内部预检配置

| 配置项 | 当前值 |
| --- | --- |
| provider / model ID | `doubao` / `doubao-seed-evolving`；Agent Plan 使用 `https://ark.cn-beijing.volces.com/api/plan/v3`，Coding Plan 使用 `https://ark.cn-beijing.volces.com/api/coding/v3`。必须根据 Key 所属套餐做最小鉴权探测，不能互换或回退到 `/api/v3` |
| runner | 官方 Trae CLI `0.1.0`，固定源码提交 `e839e559ac61bdd0e057c375dd1dee391fee797d` |
| Trae step 上限 | no-skill 与 with-skill 均为 120；`--max-steps` 不能强制最少步数 |
| no-skill 最小轮次 | 100 |
| 第一条交付硬门禁 | 格式、内容相关性、原创性、可解性、verifier 质量、反泄漏及最新版 checker 全部通过 |
| 任务价值目标 | no-skill 在至少 100 轮后仍失败，或只能在 `>100` 轮后通过；未达成不阻止第一条合格数据提交 |
| skill 效果目标 | no-skill 失败且 with-skill 通过；或两者均通过且轮次或时长至少降低 30%；未达成不阻止提交 |
| 改善目标 | 50% |
| agent timeout | 10800 秒 |
| verifier timeout | 1800 秒 |
| environment | Linux 容器、2 CPU、1536 MB 内存、0 GPU、无网络；本机 Docker Hyper-V VM 总内存为 2048 MB，两个评分臂与 verifier 使用相同显式上限 |

Trae 轨迹中的 `agent_steps` 数组长度是本批次的轮次口径，`llm_interactions` 数量用于交叉检查；轨迹根字段 `execution_time` 是时长口径。Trae 自报 `success` 只表示 agent 宣称完成，不能替代独立 verifier。该版本没有 CLI 随机 seed 参数，因此不能声称固定了采样 seed。

本机已将 Windows 可执行文件安装到 `C:\Users\Administrator\.local\bin\trae-cli.exe`，隔离运行时为 Python `3.12.13`。官方默认安装遗漏了 CLI 启动路径直接导入的 evaluation 依赖，当前工具环境额外安装 `docker 7.2.0` 与 `pexpect 4.9.0`。正式运行使用 Linux runner 镜像 `obm-trae-runner:0.1.0-e839e559-jsonrepair4` 和 task 镜像 `obm-task-python-git:3.12-v2`，并连接外部创建的无网络 task container；运行前必须建立干净的 Git 基线。该 runner 还按 edit 子命令过滤参数并对传给容器 shell 的值做标准 quoting，避免无关可选字段破坏合法编辑调用。详细安装和运行约束见 [trae-runner.md](trae-runner.md)。

轮次降低率为 `(no_skill_turns - with_skill_turns) / no_skill_turns`；时长降低率同理。两组均通过时，任一有效指标达到 0.30 即可记录第二条目标达成，0.50 是努力目标。no-skill 未解决而 with-skill 解决属于更强的定性改善分支。整个第二条是内部检测和质量激励，不是第一条合格数据的打包或上传硬门禁。

## 进入跑分前仍需确认

1. 冻结完整 `proposal.json` 与 `sources`，尤其核对 `proposal_verify` 和 `expert_experience_skill`。若用户要求审批，当前审定入口是 `D:\hc\obm\proposal.human-review.json`；用户已明确本批次不再要求人工撰写。
2. Doubao Agent Plan 凭据已验证可以调用 `doubao-seed-evolving`，并使用 Windows DPAPI 保存为当前用户绑定的密文 `C:\Users\Administrator\.config\obm\ark-agent-plan.dpapi`。正式运行通过 `scripts\invoke-trae-with-ark-key.ps1` 临时注入 `DOUBAO_API_KEY` / `ARK_API_KEY`；不得把明文写入配置、命令行、日志、截图或交付包。

试标数据交付表、专家证明、签字和工时不属于本工作流的 ZIP 生成范围，不作为本地打包的前置项。
