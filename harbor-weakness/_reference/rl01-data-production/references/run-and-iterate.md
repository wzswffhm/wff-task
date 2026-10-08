# 串行跑分与迭代门禁（harbor + claude-code）

本文件是「题包出完 → 定难度档」这一段的执行口径。核心是**逐档放行**：一档不达标就停下来改题，
不要把多个模型档同时开跑（同时开跑等于把难度信号混在一起，改完还得全部重跑）。

## 一、四档放行门禁（顺序固定，不得调换）

| 档 | 执行体 | 命令 | 门槛 | 不合格时的动作 |
|---|---|---|---|---|
| ① | oracle（参考解） | `harbor run -p <批次目录> -a oracle -n <题数>` | 参考分 **> 0.85** | 多半是判据与参考答案对不上：先查 `reward-details.json` 里参考解掉分的条目的 reasoning |
| ② | qwen3.8-max-0902 | `... -a claude-code -m qwen3.8-max-0902 -n <题数>` | 三题均值 **< 0.7** | 先改 `rubrics.json`（见第三节），重跑该档 |
| ③ | claude-opus-4-8 | `... -a claude-code -m claude-opus-4-8 -n <题数>` | 均值 **< 0.7**，且**原则上不低于 qwen** | 同上；若 opus 反而低于 qwen 超过 0.05，先排查判官波动 / 题面歧义，再决定是否放行 |
| ④ | gpt-5.6-sol | `... -a claude-code -m gpt-5.6-sol -n <题数>` | 均值 **< 0.7** | 同上 |

配套要求：

- 每档**三题并行**（`-n` = 题数），但**不同档之间串行**。
- oracle 不产生 agent 轨迹；其余四档产物都要带**原生轨迹**归档。
- 参考解与三模型的全部分数、逐条判分明细（`reward.json` / `reward-details.json`）随包提交。

## 二、harbor 实跑要点（踩过的坑）

1. **`-p` 是数据集目录，不是单题目录**。harbor 会遍历该目录的子目录找 task；
   传单题目录会报 `Either datasets or tasks must be provided`（或 `0 tasks available`）。
   正确用法：把 `<批次目录>` 传给 `-p`，用 `-i/--include-task-name` 过滤要跑的题。
2. **中文包必须开 UTF-8 模式**。harbor 读 `task.toml` 用系统默认编码，中文 Windows 上会抛
   `UnicodeDecodeError` 并被静默吞掉（表现为"识别不到 task"）。跑之前设
   `PYTHONUTF8=1`（`PYTHONIOENCODING=utf-8` 一并设更稳）。
3. **Dockerfile 里的 `apt-get install` 别写成一条**。一次装 `libreoffice-* + fonts-noto-cjk`
   会让 dpkg 解包峰值触发 OOM（`cannot allocate memory` / `Killed`）。拆成两条事务，
   依赖集合保持不变；临时构建也可以 `FROM <同模板构建好的镜像>` 复用环境层。
4. **镜像拉不动时换镜像源**：`docker pull docker.m.daocloud.io/<repo>:<tag>` 之后
   `docker tag` 成本地名（`docker.io/library/...` 直连常被墙）。
5. **claude-code 只吃 anthropic 协议（`/v1/messages`）**。三家的接入方式要分别确认：
   - qwen3.8-max-0902：走 anthropic 风格网关的 `/v1/messages`；
   - claude-opus-4-8：确认所用 key 所在 group **允许** `/v1/messages`（有的 key 只开
     `/v1/chat/completions`，会报 `This group does not allow /v1/messages dispatch`）；
   - gpt-5.6-sol：若 key 不支持 `/v1/messages`，在本机起一个 **anthropic→openai 协议转换代理**
     （litellm proxy 即可），让 claude-code 指向 `http://host.docker.internal:<port>`。
   判官凭据通过 job 的 env 注入（`JUDGE_API_KEY` / `JUDGE_BASE_URL`），不要写进题包。
6. **Docker daemon 半死**（`docker version` 通但 `pull/build` 返回 500）：`wsl --shutdown`
   → 重启 Docker Desktop → 等 `docker version` 出号 → 重挂未完成的 job。

## 三、判分节奏与耗时预期

- rewardkit 是**每条 criterion 一个独立 judge 会话**（`mode = "individual"`），judge 侧由
  claude-code 驱动、串行执行。单条 30 s–3 min，因此单题 40 条 ≈ 25–80 min，60+ 条更久。
- agent 侧（claude-code 解题）单题通常 20–60 min。
- 因此**一轮完整跑分 = 4 档 × (agent + verifier)**，量级是 6–12 小时；排期要按这个量级报，
  不要按"几分钟出分"预期。
- 判断"卡住"还是"在跑"：看 `agent/claude-code.txt` 是否还在增长、容器内是否有
  `claude -p ...` judge 进程；只看 `reward.json` 会误判——`test.sh` 开头的 fail-closed 占位
  （`verifier_error=1`）在真正判完前一直存在。

## 四、不达标时的整改顺序（严格按此优先级）

1. **改 `rubrics.json`**（首选，代价最小）：合并重复项、拆分笼统项、调整 `weight`
   （关键结论/指令给 10，重要依据/规范给 7，细枝末节给 3）、收紧或放宽 `levels` 档位描述。
   - 注意规范红线：`weight` 只能取 `{±10, ±7, ±3}`；至少 2 条 `+10`；内容质量维度正分
     ≥ 全部正分的 30%；**不要用 `+3` 堆叠**；`+10` 占比不宜 > 60%（会稀释区分度）。
   - **不要**靠题面歧义、无法验证的要求或互相矛盾的约束压分（属 hack，人工质检直接打回）。
2. **改参考答案**（次选）：仅当参考解自身不达标、或判据要求的内容参考解确实没写时才动。
3. **改题面**（最后手段）：题面一改，该档的 agent 必须重跑（前一轮产物作废）。
4. 每次改完判据 → **重跑该档判分**；agent 产物在没有改题面的前提下可以沿用
   （见 [revision-and-qc.md](revision-and-qc.md) 第二节）。

## 五、判据锚点必须可溯源（改完判据必查）

**硬规则：判据不得要求题面没有的东西。** 每条 criterion 的要求都要能在
`instruction.md`（或题面明确要求遵守的 `environment/skills/<name>/SKILL.md`）里找到依据。

自查方式（两种任选或都做）：

```bash
python scripts/check_rubric_grounding.py <task-dir> [...]   # 抽取硬锚点(数字要求/编号体系/表头列名/文件名)回查题面
```

或人工把每条判据的"要求"对照题面三类段落（任务说明 / 产出要求 / 硬约束）过一遍。

发现判据超出题面时，二选一：

- **删掉该条判据**（推荐）：判据变了要重跑判分，但 agent 产物不变；
- **把要求补进题面**：题面变了，该档 agent 必须重跑。

典型超范围情形（都实际发生过）：判据要求"给出可核查的外部案例来源"，而题面写的是
"只能依据提供的材料、不得引入材料以外的判例"——这类**判据与题面互相矛盾**，必须优先处理。

## 六、产物归档

跑完全部四档后，按执行体归档：

```
跑分产物与轨迹/<题目编号>/
├── oracle/{output/, reward.json, reward-details.json}          # 无轨迹
└── <模型名>/{output/, reward.json, reward-details.json,
              轨迹/{trajectory.json, claude-code.txt}}          # 原生 agent 轨迹
```

归档后重打交付 zip：`solve.sh` / `test.sh` 必须 LF + 0755；zip 内权限位要复核
（Windows 压缩容易把 `external_attr` 写成 0）。
