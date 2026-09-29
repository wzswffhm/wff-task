---
name: harbor-skill
description: >-
  Harbor Coding RL 出题到交付全流程（选题、Oracle、Reward Kit rubrics、baseline/oracle 校准、
  难度门、打 zip、飞书字段/状态/附件自动回写）；整题交付完成后自动开下一题连续作业。
  Use when the user mentions harbor-skill, Harbor 出题/交付/打 zip、飞书回写/提交、
  连续开题、难度门、quality.toml、rewardkit、baseline/oracle、或飞书作业编号 zq*。
---

# Harbor Skill

**质检实锤反面教材（禁止重演）：** `zq2026080704332-file-storage-c-bugfix`
（难度门曾跑通，但质检 **核心结论：不通过**）。两条 P0：

1. **校准缺失 —— 无 Oracle/baseline**（上传包 `jobs/` 里必须能看到，且本地确已跑通；**smoke 可不跑**）
2. **rubrics 完全缺失 —— `quality.toml` 仅 `[quality] version=1` 空壳，未接入 rewardkit**

后续每题：**这两条绝不能再出现**；命中任一条 → 禁止打 zip / 禁止提交 / 禁止开下一题。

**默认模式：连续作业。** 当前题完整交付后，自动查找下一题：**标注员=林丹** 且 **状态=已领取**；有则开做，**没有则停止（禁止刷飞书空等）**。用户说停也停。

权威文档冲突时：`Coding ENV 作业培训手册` > `Harbor培训手册` > 旧本地习惯。
本 skill 对「真实 rubrics + rewardkit」与「baseline + oracle 证据进 zip」为硬门禁；上传 `jobs/` = **baseline（或 nop）+ oracle + 最终成功难度门**（**smoke 可选**；失败 rounds / 辅助目录不进包）。

## 提示词 level 策略（硬规则）

培训里 instruction 有 **level0–level4**，本 skill **一律直接从 level4 开做**，不走 level0→1→2→3 递进。

| 阶段 | 做法 |
|------|------|
| 出题 | 只写 / 只交付 **level4** 提示词（即 `instruction.md`）；禁止先从低 level 试水再升级 |
| 校准（baseline / oracle；**smoke 可不跑**） | 用该 level4 提示词验证 |
| **校准不通过** | **直接换题重新开始**（换 feature / 换模块 / 换仓）；禁止降到 level3 及以下「凑过」；禁止同题反复磨低难度文案 |
| **校准通过** | 说明题目没问题 → **锁定该 level4 提示词**，用它跑难度门 16 轮 |
| 16 轮中满分 ≥4 | 立刻杀 job → **换题重开**（已是 level4，不再同题降 level / 同义改写拖延） |
| 16 轮有效满分 =0 | **难度门失败** → **换题重开**（甲方确认：全 0 不达标） |

「验证」在本条 = **baseline + Oracle**（同一冻结修订；**smoke 非必须**）。校准过了再开 16；没过就换题，不要在低 level 上浪费轮次。

**换题 / 换仓目录铁律：** 凡因错误、校准失败、难度门失败等需要 **重新选项目** 开做时，**禁止覆盖旧目录**——必须按下方「任务目录命名」**新建带时间戳的目录**再从头做。

## 任务目录命名（硬规则）

现有命名基式（不变）：

```text
<作业ID>-<领域或仓库语义>-<语言>-<题型>
例：zq2026080704332-file-storage-c-bugfix
```

### 何时必须新建目录

任一情况导致 **重新选项目 / 整题作废重开**（含但不限于：baseline/oracle 校准失败、难度门满分 ≥4 或满分 =0、Oracle/环境/验证失败后换仓、选题作废），一律：

1. **保留**旧 `task/<旧目录>/` 不删不改名（可另拷 `_failed_project_backups/`）
2. **新建**目录，名称 = **基式 + `-` + 时间戳（精确到分）**

```text
task/<作业ID>-<语义>-<语言>-<题型>-<YYYYMMDD-HHMM>/
例：task/zq2026080704332-file-storage-c-bugfix-20260809-0006/
```

时间戳用本地时间，格式 **`YYYYMMDD-HHMM`**（例 `20260809-0006`）。同一分钟内若冲突，在分后再加后缀 `-2`、`-3`。

首次开做也建议直接带时间戳，便于与后续重试统一排序；至少 **每一次重开必须带新时间戳**。

### 默认成功目录（查询约定）

同一 `作业ID` 下可能有多份目录。用户默认：

**时间戳最新（字典序最大的 `-YYYYMMDD-HHMM`）的那份 = 当前成功 / 默认查阅对象。**

Agent 汇报、打 zip、飞书回写时，以该最新目录为准；不要把旧失败目录当交付源。旧目录仅作对照与备份。

### 禁止

- 在旧目录里「清空重做」冒充新项目  
- 无时间戳覆盖：`rm -rf` 同名目录再 init  
- 交付时上传非最新时间戳目录（除非用户明确点名某一旧版）

## 难度门铁律（最高优先级之一）

**有效终态下 `reward = 1.0` 的次数必须为 1–3（甲方确认：全 0 也不过门；≥4 过易也不过）。**

提示词固定为 **level4**；过易（≥4）或过难（满分=0）都 **换题**，不是把 16 轮跑完装样子，也不是退回 level0–3。

| 情况 | 立刻做什么 |
|------|------------|
| 后台扫到有效 `reward=1.0` 累计 **= 4**（或 ≥4） | **马上杀 job**，不要再跑剩余 trial |
| 跑满 16 后有效满分 **= 0** | **难度门失败** → **换题重新开始**（甲方确认：全 0 不达标） |
| 杀停 / 全 0 之后 | **换题重新开始**（换 feature / 模块 / 大型仓；同仓勿打同一模块） |
| 继续空跑完 16 / 再打包再交 / 降到更低 level 凑数 | **禁止**——后面全是浪费时间 |

监控：最多 16 次；**每分钟**扫已完成 `reward.txt`；每出现一次有效 `1.0`，通过数 +1。始终 &lt;4 才跑满 16，再按总数验收（须 **1–3**；**=0 或 ≥4 都失败并换题**）。超时导致的 0 不算有效样本，整 job 作废重跑。

**不要：** 满分已到 4 还心存侥幸「再看看」；不要把「16 轮全 0」当过门；不要只同义改写 prompt；不要退回 level0–3；不要用超时刷低分冒充够难。

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

另加：**最终通过难度门**的那一个成功 job（例如 `qwen-difficulty-16c8`；历史包可为 `16c4`）。

#### 全量本地备份 → 再打精简上传包

打 zip / 上传**之前**：

1. **先把当前 task 目录全量复制一份留作备用**（含全部 `jobs/`：校准、成功难度门、失败试验等）。  
   推荐路径：`task/_full_job_backups/<作业ID>/<task-name>-full-<YYYYMMDD-HHMM>/`  
   （**绝不进上传 zip / 不传飞书**）
2. 备份完成并确认可还原后，再做 **提交用精简包**：`jobs/` **必须保留**  
   `baseline|nop` + `oracle` + **一个**成功难度门；若已跑过 smoke 可一并打进，**未跑则不要为凑包去补跑**。删掉失败难度 rounds / 辅助目录。

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

## 提示词 / instruction.md：禁止 AI 痕迹（硬规则）

`instruction.md`（及飞书「instruction.md文本内容」）必须像 **真人工程师随手提需求**，不能像模型生成说明书。质检会盯文风；有 AI 腔直接不过。

**要写成这样：**

- 2–3 段口语化短文：现状哪里不对 / 要什么行为 / 兼容边界
- 具体、可观察（「点名 GPT 时盘前结构要变」），少形容词
- 语气像 issue / 同事留言，允许略不整齐，但意思清楚

**禁止（AI 痕迹）：**

- 编号验收清单、同义反复、「请确保 / ensure / properly / robustly / comprehensively」堆砌
- 泄露隐藏测试、权重、文件路径清单、补丁做法、参考实现
- 套话：`综上所述`、`值得注意的是`、`充分说明`、`显著提升`、`建议进一步优化`、`in summary`、`overall`、`it is worth noting`
- 空洞大词：`全面`、`完善的解决方案`、`高质量实现`、`端到端保障`
- Markdown 教程腔：过多标题层级、emoji、漂亮但假的「任务目标/约束/验收标准」模板骨架

写完自检：把品牌名抹掉后，读起来应像真人提的需求，而不是 ChatGPT 任务卡。

**level 口径：** 只产出 **level4** 作为交付 `instruction.md`。校准不过 → 换题；校准过 → 该文锁定跑 16 轮。不要维护/交付 level0–3 递进稿来「找难度」。

更多对照见 [references/instruction-style.md](references/instruction-style.md)。

## 22 注意事项（培训截图 a–I）

完整条文：[references/notes-22.md](references/notes-22.md)。摘要：

| 项 | 要求 | 本 skill 状态 |
|----|------|----------------|
| **a** | 扩展包全部 `==` 钉版本（pytest / rewardkit / mini-swe-agent / litellm 等） | **已录入** notes-22 |
| **B** | `test.sh` 加 `--ctrf`；镜像装 `pytest-json-ctrf==0.3.5` | **已录入** |
| **C** | macOS 打包前清 `.DS_Store` | **已录入**（checklist/zip exclude） |
| **D** | tests 用 `test_outputs.py`+`test.sh`，不要 `checks.py`；另保留 `quality.toml` | **已录入**（改名口径） |
| **E** | `jobs/` 要上传（baseline+oracle + 成功难度门；smoke 可选） | **已录入** |
| **F** | 指定 openai/anthropic baseurl + `qwen3.8-max` | **已录入** |
| **G** | 提示词无 AI 痕迹 | **已录入** |
| **H** | 同项目多题勿打同一模块；提示词高质量 | **已录入** |
| **I** | 任务类型与提示词一致 | **已录入** |

## 质检分数要求（4.2 / 5.2）

完整表：[references/qc-scores.md](references/qc-scores.md)。

**关键指标（4.2）**

| 指标 | 理想范围 |
|------|----------|
| 平均通过率（有效 Trial 平均 reward） | **0.3 – 0.7** |
| 任务难度分布 | 正态分布 |
| 评分一致性 | 低方差 |
| Agent 区分度 | 有显著差异 |

**分数解读（5.2）**：0.9–1.0 优秀可直接用；0.7–0.89 良好微调；0.5–0.69 需改进；0.3–0.49 重大修改；0.0–0.29 严重问题建议重写。交付目标综合分 **≥ 0.7**。

## 需要注意的情况（必读）

完整踩坑录：[references/pitfalls.md](references/pitfalls.md)。下列为高频卡点，出题时默认按此预防。

### 环境 / 网络：多用国内镜像，禁止空等

直连 Ubuntu / npm / nodejs.org / GitHub / PyPI 极易卡死。Dockerfile 与拉源码 **默认国内镜像 + 重试**：

- **apt**：阿里云 `mirrors.aliyun.com`（含 `ubuntu-ports`）；`Acquire::Retries=5`
- **Node/npm**：`npmmirror.com`（`NVM_NODEJS_ORG_MIRROR` + `NPM_CONFIG_REGISTRY`）；node 包也从 npmmirror 下 tar
- **GitHub**：`gh` tarball / 可用加速（如 `ghfast.top` 前缀）；clone 卡住就换镜像或浅拉，**数分钟无进度立刻换路**
- **uv/PyPI/rewardkit**：国内 index；镜像 **build 期预热** `uvx ... rewardkit --help`，避免 verifier 首次下载超时
- **运行时**：OrbStack（非 Desktop）；并发高时清理 Docker 网络/残留容器，防止网桥耗尽

### 中文与 locale

`LANG=C.UTF-8`、`LC_ALL=C.UTF-8` 写入 Dockerfile 与 `task.toml` 的 environment/agent env；否则中文 instruction 会变成 `???`。

### 选题 / 难度（失败工程经验）

- **必须选大型项目**：优先中大型、活跃、可完整构建的真实工程（多模块/多目录、非玩具仓、非单文件工具集）。拒绝迷你 demo、作业级小仓、明星数很少且体量极小的仓。成功范例量级：`exfatprogs` 一类生产级工具；失败侧多为过小/过易缺陷仓。
- 功能点本身也要够重：跨文件 feature / 非单点常量修补；oracle patch 宜有实质体量（数百行级更稳），避免十行级小修。
- 小修复、单点校验很容易 16 次里满分 ≥4（曾挂：genext2fs、lwext4 journal 等）→ **直接换题/换仓**（已是 level4，不降 level）
- 同概念约 3 轮仍触线 → 备份到 `task/_failed_project_backups/<作业ID>/`，不要死磕
- 飞书题型/领域/语言与 `task.toml` 必须一致（改 feature 要同步改表）
- **领域/子领域只能用官方枚举**（计算产品 / 存储 / 数据库及其子领域原文），见 [references/domain-taxonomy.md](references/domain-taxonomy.md)；禁止自造「云存储」「文件系统」等近义说法
- workspace 可裁剪无关子树，但选题起点必须是大型项目，不能用小仓凑合

### 评测监控（勿误判）

- 勿只看 `qwen-code.txt` 体积断定卡死（session/token 可能仍在跑）
- 宣称 SUCCESS 但缺少 `reward.txt` / `reward_files` 不足 → **无效**，当基础设施失败
- **超时导致的 `reward=0` 不算有效难度样本**：timeout/cancel 等 → **整 job 作废重跑**
- **难度门早停（硬规则，必须照做）**：
  1. Harbor 按计划最多跑 **16** 次（`--n-attempts 16`，并发 **8**）
  2. 后台 **每分钟**扫一遍已完成 trial 的 `reward.txt`
  3. 每出现一次有效终态 `reward=1`，通过数 +1
  4. **一旦通过数 ≥ 4**：立刻杀 job 提前停，然后 **改题/换仓**（勿等 16 轮结束）
  5. 若始终 &lt; 4：跑完 16 次，再按总数验收——有效满分必须在 **1–3**（**=0 过难失败换题；≥4 过易早停换题**）
- 长跑控制器用持久后台 + 单实例锁，防 IDE 收割会话
- 有效样本须正常跑完 verifier 并写出 reward；超时 0 不计入通过数，且污染整 job

### 评分与交付

- 先接 rewardkit/真实 rubrics，再跑校准与难度门（后补会作废轨迹）
- zip 的 `jobs/` **必须含** baseline/nop + oracle + 成功难度门（**smoke 可选**）；禁止空壳 `quality.toml` / 未接 rewardkit
- 改 tests/environment/instruction/solution → 整轮重跑

## 默认生产画像

除非用户当场覆盖：

- 根目录：`/Users/zhangzhi/Desktop/harbor`；任务在 `task/<作业ID>-<语义>-<语言>-<题型>[-YYYYMMDD-HHMM]/`
- 换题/验证失败重选项目 → **必须新建带分钟时间戳的目录**；同作业 ID 下 **最新时间戳 = 默认成功目录**
- Harbor `0.20.0`；容器 **OrbStack**（`docker context show` → `orbstack`）
- 提示词：**直接 level4**；baseline/oracle 不过 → 换题重开（新时间戳目录；**smoke 可不跑**）；校准过 → 锁定该提示词跑 16
- 难度门：有效 `reward=1.0` 必须在 **1–3**；**=0 跑满后换题**；**≥4 立刻杀 job 并换题**（新时间戳目录；已是 level4，不降 level）；每分钟扫 `reward.txt`；超时 0 分 job 作废重跑
- 质检综合分目标 **≥ 0.7**（5.2 分数解读）；关键指标见 [references/qc-scores.md](references/qc-scores.md)（与文档 Ideal 通过率冲突时，**以本条满分 1–3 / 全0或≥4 换题为准**）
- 默认模型：`qwen3.8-max`
- OpenAI 兼容 Base：`https://llm-sn32yenb08wvkx41.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- Anthropic 兼容 Base：`https://dashscope.aliyuncs.com/apps/anthropic`
- 扩展依赖全部钉版本 + `pytest-json-ctrf` + test `--ctrf`（[notes-22.md](references/notes-22.md)）
- API：只从环境 / `--ae` 注入；永不写入任务文件、聊天、zip
- 中文 instruction：`LANG=C.UTF-8`；依赖与拉仓走国内镜像
- 失败工程备份：`task/_failed_project_backups/<作业ID>/`；全量 jobs 备份：`task/_full_job_backups/<作业ID>/`（均不进上传 zip）

## 标准目录

```text
task/<作业ID>-<语义>-<语言>-<题型>-<YYYYMMDD-HHMM>/   # 重开必带时间戳；同 ID 最新戳=默认成功
├── instruction.md
├── task.toml
├── environment/Dockerfile
├── environment/workspace/   # 无 .git / 无 solution / 无 tests
├── solution/solve.sh
├── solution/oracle.patch    # 若用 patch 方案
├── tests/test.sh
├── tests/test_outputs.py   # 不要用 checks.py（注意事项 D）
├── tests/quality.toml      # 质检仍要真实 rubrics
└── jobs/                # 上传 zip 必须含：baseline|nop + oracle + 成功难度门（smoke 可选）
    ├── baseline/   # 或 nop/
    ├── oracle/
    ├── qwen-smoke*/          # 可选
    └── <agent>-difficulty-16c8/
```

同作业多目录示例：

```text
task/zq…-file-storage-c-bugfix/                 # 旧尝试（保留）
task/zq…-file-storage-c-bugfix-20260809-0012/   # 更新 → 默认当成功查阅
```

## 端到端顺序（不得跳步）

1. **选题钉 commit（大型项目）** → 领域/子领域落在 [domain-taxonomy.md](references/domain-taxonomy.md) → 写 **level4** `instruction.md`（**无 AI 痕迹**、不泄题；不写 level0–3）→ `task.toml` 元数据对齐飞书字段。
2. **环境**：Dockerfile 装齐构建依赖 + `python3` + pinned `uv`/`uvx` + 预热 `harbor-rewardkit`；**apt/npm/node/PyPI/GitHub 走国内镜像**；只 `COPY workspace/`。
3. **Oracle + Verifier**：`solve.sh` 可复现；`test_outputs.py`（勿用 `checks.py`）+ `--ctrf`；**先写好 quality.toml 并接入 test.sh**；扩展包全部钉版本（见 notes-22 a/B）。
4. **冻结合修订**（对 `instruction.md`/`task.toml`/`environment/`/`solution/`/`tests/` 做哈希记录）。
5. **校准**（同一修订、level4 提示词）：baseline=0 → Oracle=1（含 quality 证据）。**smoke 可不跑**。baseline/oracle **任一不过 → 换题**：保留旧目录，**新建 `…-YYYYMMDD-HHMM/`**，从第 1 步重来（不降 level）。
6. **难度门**：校准已通过 → **锁定该 level4 提示词**跑 16。`reward=1.0` 次数必须在 **1–3**。每分钟扫 `reward.txt`；**一到 4 立刻杀 job → 换题**；跑满后 **满分=0 也换题**（甲方确认）。新建时间戳目录重开——拖完剩余轮次或降 level 是浪费。超时污染 → 整 job 作废重跑。
7. **改 tests/environment/instruction/solution 任一文件** → 旧 jobs 全部作废 → 从第 4 步重来（若改的是换题/换仓，**新建时间戳目录**从第 1 步）。
8. **打 zip** 前跑 [references/delivery-checklist.md](references/delivery-checklist.md)；P0 未过则停止。
9. **飞书自动回写**（对照成功题 `zq2026080704332` 人工项）：按 [references/feishu-delivery.md](references/feishu-delivery.md) 写入文本字段、上传 zip、改 `状态=已提交`；公式校验须 ✅。
10. **完整完成后** → 进入「连续作业循环」，自动开下一题（除非用户叫停）。

## 飞书自动标注（替代手工）

对照成功题 `zq2026080704332` 行上实际填写项；**交付时默认全部自动写，不留给用户填表**：

1. **`标注员`（标注人）**：写成当前 `lark-cli auth` 用户（`[{"id":"<openId>"}]`）；开做认领与交卷都要有  
2. `instruction.md文本内容`、`task.toml 文本内容`：本题终稿全文（禁止贴错题）  
3. `任务类型` / `应用领域` / `子领域` / `编程语言`：与 toml 一致，保证公式 ✅  
4. `harbor format task（Zip文件包）`：只挂 1 个合规 zip  
5. `状态`：开做→`已领取`；交卷→`已提交`  
6. `修改日期`：每次回写/重传时更新  

**不要写：** `标注日期`（成功题为空，用户要求不填）；**不要写/清空：** `质检员`。  
「提交」按钮 API 不可用时以 `状态=已提交` 为准；若流程仍要点按钮再提示用户。

鉴权失败或无写权限时：**停在回写步骤并说明**，不要假装已提交后去开下一题。详表见 [references/feishu-delivery.md](references/feishu-delivery.md)。

## 连续作业循环（默认开启）

目标：一道题从选题到 zip **完整闭环**后，立刻开下一道，形成流水线，减少空等。

### 什么叫「完整完成」（全部满足才算）

- [ ] P0-1：本地已跑通 baseline/oracle（**smoke 可选**）；**上传 zip 的 `jobs/` 含齐** baseline|nop + oracle + 成功难度门  
- [ ] P0-2：真实 `quality.toml` + `test.sh` 已接 rewardkit；Oracle 有 quality 证据；**非** `[quality] version=1` 空壳  
- [ ] 难度门：有效满分 **1–3**；**=0 或 ≥4** 均不算过门（须换题）；无超时污染  
- [ ] delivery-checklist 自检 PASS；zip 已生成且路径告知用户  
- [ ] **飞书自动回写完成**（见 [references/feishu-delivery.md](references/feishu-delivery.md)）：  
      `标注员`=当前账号；四列元数据 + instruction/toml 终稿；公式 ✅；  
      zip 已上传（仅 1 个）；`状态=已提交`；`修改日期`已更新；**未写 `标注日期`**；未改 `质检员`

**不算完成、不得开下一题：** 只过难度门但未打合规 zip；P0 未过；飞书未回写成功；用户明确要求先质检/先改再交。

### 完成后立刻做（自动，无需用户再说「开新题」）

1. **短汇报当前题**（路径、难度门 pass 数、zip 路径、飞书已提交）——一两句。  
2. **拉下一题**（飞书筛选，硬条件，缺一不可）：
   - **标注员 = 林丹**
   - **状态 = 已领取**
   - 在仍待交付的作业中取一条（未交 zip / 非「已提交」等按表内可执行含义）
   - 用户本会话若给过明确 `zq*` 队列：仅当该 ID 也满足上述两条件才可开；否则跳过并说明  
3. **若没有满足条件的作业**：短报「无林丹+已领取可执行作业，连续循环停止」→ **立刻停**，**禁止**反复刷飞书/空等重试。  
4. 下一题开做：确认飞书该行已是林丹 + 已领取（不必再抢未领取池）；新建 `task/<新作业ID>-…-YYYYMMDD-HHMM/`。  
5. **从端到端第 1 步重来**（选题→环境→rubrics→校准→难度门→zip→**飞书回写**），仍遵守 P0、目录命名与 pitfalls。  
6. 循环直到：无更多「林丹 + 已领取」作业 / 用户说停 / 飞书鉴权失败需人处理。

### 中途换仓 ≠ 完成

难度门失败 / 校准失败换工程：备份可选；**新建带分钟时间戳的 task 目录**；**仍在当前会话**继续同一作业 ID，**不要**跳到下一飞书题。同 ID 下最新时间戳目录 = 默认成功查阅对象。

### 何时暂停连续循环

- **没有**标注员=林丹且状态=已领取的可执行作业（默认停，不刷表）  
- 用户说：停、先别开新题、等质检、先交再做  
- 需要林丹等账号重新授权、或缺 API Key  
- 宿主机 Docker/磁盘/配额明显撑不住  
- 下一题字段不清且用户未回复关键信息  

暂停时说明卡在哪；有新的「林丹 + 已领取」或用户点名后再恢复，**禁止后台轮询刷飞书**。

详表：[references/continuous-queue.md](references/continuous-queue.md)。

## 打 zip 规则

Staging 后打包，zip 根目录必须是单一 `<task-name>/`。

**打包顺序（强制）：**

1. 难度门通过且 checklist 将 PASS 时 → **先全量备份**到  
   `task/_full_job_backups/<作业ID>/<task-name>-full-<时间戳>/`  
   （整题目录拷贝，含全部 jobs；密钥仍勿外传）
2. 再从备份或当前目录 **staging 精简包**：`jobs/` 拷齐  
   **baseline|nop + oracle + 一个成功难度门**（已有 smoke 可附带；未跑可不含）
3. 脱敏精简包内 API key → 打 zip → **打包后自检**（见下）→ 飞书只上传该精简 zip

**必须打进上传 zip：**

- 题目五件套 + `tests/{test.sh,test_outputs.py,quality.toml}`（**真实 rubrics，非空壳**）
- `jobs/baseline` 或 `jobs/nop`
- `jobs/oracle`（含 quality / rewardkit 执行证据）
- 最终通过的难度门目录（整次 job，含全部 trials / `result.json`）

**可选打进上传 zip：**

- `jobs/*smoke*`（跑过则建议带上；**未跑不要求补跑**）

**禁止打进上传 zip：**

- `_auto_loop_state`、`_archive*`、`_full_job_backups`、失败难度 rounds
- `scripts/` 本地控制器、`_failed_project_backups/`
- `.git`、密钥、宿主机绝对路径、嵌套 zip
- 空壳 `quality.toml` 或未调用 rewardkit 的 `test.sh`

**打包后硬自检（任一条失败 = 禁止上传）：**

```bash
# baseline + oracle 必须在 zip 内（smoke 不检查）
unzip -l "$ZIP" | rg -q 'jobs/(baseline|nop)/' || { echo 'FAIL P0-1 baseline'; exit 1; }
unzip -l "$ZIP" | rg -q 'jobs/oracle/' || { echo 'FAIL P0-1 oracle'; exit 1; }
# 禁止空壳 quality（与质检 P0-2 对齐）
unzip -p "$ZIP" '*/tests/quality.toml' | rg -q '\[\[criterion\]\]' \
  || { echo 'FAIL P0-2 empty quality.toml'; exit 1; }
unzip -p "$ZIP" '*/tests/test.sh' | rg -q 'harbor-rewardkit' \
  || { echo 'FAIL P0-2 no rewardkit'; exit 1; }
```

## 反模式（质检挂 / 空耗时间）

1. **上传 zip 不含 baseline/oracle**（校准硬伤）——必须跑通且进包；**smoke 可不跑**。
2. 手册写「quality.toml 不用编写」就提交 `[quality] version=1`（同题质检 P0-2）。
3. `test.sh` 只 `pytest` 写 reward，从未 `uvx ... rewardkit`。
4. 先跑完全部难度门，再补 rewardkit → 轨迹与最终 tests 不一致，证据作废。
5. 只看 `qwen-code.txt` 体积判断卡死（session/token 可能仍在跑）。
6. Dockerfile/拉仓直连国外源，卡数十分钟还不切国内镜像。
7. 满分已到 4 还不杀 job、不换题，或退回 level0–3 凑难度，继续空耗 16 轮或拿去交付。
8. 从 level0 试做再往上升级；校准不过还死磕同题低 level。
9. 无 reward 文件却当 SUCCESS / 过门。
10. 把 **超时导致的 0 分** 算进难度门有效样本（必须作废整 job 重跑）。
11. `instruction.md` 带 AI 腔（清单腔、确保/全面/综上所述、假 PRD 模板）——必须重写成人口语需求。
12. 只过难度门就交卷，跳过 baseline/oracle 或空壳 rubrics「回头再补」。
13. 验证失败 / 换仓后覆盖旧 `task/` 目录，或不带 `-YYYYMMDD-HHMM` 时间戳新建目录。

更多见 [references/pitfalls.md](references/pitfalls.md)。

## 与旧 skill / 旧 rule 的关系

- `harbor-annotation`：可参考环境与文风；**zip 的 jobs 策略以本 skill 为准（baseline+oracle + 成功难度门；smoke 可选）**。
- 仓库 `.cursor/rules/harbor-delivery-jobs.mdc` 必须与本 skill 一致。
- 旧习惯「zip 只留难度门、校准不进包」**已作废**。
- 旧习惯「smoke 必须跑 / 必须进包」**已作废**——现行可不跑。
