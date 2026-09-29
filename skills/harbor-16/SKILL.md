---
name: Harbor 16
description: >-
  Harbor Coding RL 出题到交付全流程（选题、Oracle、Reward Kit rubrics、baseline/oracle 校准、
  难度门、打 zip、飞书回写）；支持 16 路并发完整批次、跨完整批次的透明选样与本地证据留存。
  Use when the user mentions harbor-skill, Harbor 出题/交付/打 zip、飞书回写/提交、
  连续开题、挂机、16 容器批次、难度样本集、quality.toml、rewardkit、baseline/oracle、或飞书作业编号 zq*。
---

# Harbor Skill

## 评测真实性（不可绕过）

难度 batch、reward、trajectory 和 verifier 结果是评测证据。不得为了满足目标比例而删除、
隐藏、改写正常完成的 trial，或将筛选样本伪装为单次完整评测结果；也不得把超时或基础设施
错误伪装成模型得分。每批的 16 条 trial 都必须在本地保留原始终态、reward 和来源，并在
`difficulty-manifest.json` 中如实记录。最终 zip 若仅展示入选样本，必须附上全量 batch 索引、
明确的筛选规则和每条入选来源；全量原始 job 留在本地备份，供复核。

需要变更提示词、题目、验证器或环境时，必须新建修订、重新校准并重新跑完整 batch；不能在同一
修订内根据结果回溯性筛选以达成配额。无法如实满足外部要求时，停止提交并报告实际分布。

**质检实锤反面教材（禁止重演）：** `zq2026080704332-file-storage-c-bugfix`
（难度门曾跑通，但质检 **核心结论：不通过**）。两条 P0：

1. **校准缺失 —— 无 Oracle/baseline**（上传包 `jobs/` 里必须能看到，且本地确已跑通；**smoke 可不跑**）
2. **rubrics 完全缺失 —— `quality.toml` 仅 `[quality] version=1` 空壳，未接入 rewardkit**

后续每题：**这两条绝不能再出现**；命中任一条 → 禁止打 zip / 禁止提交 / 禁止开下一题。

**默认模式：挂机连续作业（无需确认）。**  
成功一题并飞书回传「已提交」后 → **立刻**领下一题开做，**禁止**问用户「要不要做下一题」。  
当前题失败（校准/难度门/环境等）→ **按本 skill 规则自动**重开时间戳目录或换仓换题，**禁止**问用户「重跑还是换项目」；**同一作业 ID 做到成功交付为止**，再领下一题。  
循环直到飞书上 **没有**「标注员=向威 且 状态=已领取」的可执行题 → 停止。用户明确说停也停。  
**挂机刷题：一直做，不要停；不要等确认。**

权威文档冲突时：`Coding ENV 作业培训手册` > `Harbor培训手册` > 旧本地习惯。当前培训手册规定 Nop baseline=0、Oracle=1；smoke 建议执行一次但不是交付门槛。难度验收按 4×4 取样：可完成 `16×N` 条独立 Trial，在所有正常完成且有 reward 的 Trial 中选出 16 条；入选集必须 `reward<1` 至少 13 条且 `reward=1` 至少 1 条。每一条必须在 manifest 中保留来源 job、trial ID、reward 和终态，不能伪称为同一 job。

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
    └── <agent>-difficulty-16c16/
```

同作业多目录示例：

```text
task/zq…-file-storage-c-bugfix/                 # 旧尝试（保留）
task/zq…-file-storage-c-bugfix-20260809-0012/   # 更新 → 默认当成功查阅
```

## 端到端顺序（不得跳步）

1. **Docker 环境清理**（清自身网络池/残留容器）→ **选题钉 commit（大型项目）** → 领域/子领域落在 [domain-taxonomy.md](references/domain-taxonomy.md) → 写 **level4** `instruction.md`（**无 AI 痕迹**、不泄题；不写 level0–3）→ `task.toml` 元数据对齐飞书字段。
2. **环境**：Dockerfile 装齐构建依赖 + `python3` + pinned `uv`/`uvx` + 预热 `harbor-rewardkit`；**apt/npm/node/PyPI/GitHub 走国内镜像**；只 `COPY workspace/`。
3. **Oracle + Verifier**：`solve.sh` 可复现；`test_outputs.py`（勿用 `checks.py`）+ `--ctrf`；**先写好 quality.toml 并接入 test.sh**；扩展包全部钉版本（见 notes-22 a/B）。
4. **冻结合修订**（对 `instruction.md`/`task.toml`/`environment/`/`solution/`/`tests/` 做哈希记录）。
5. **校准**（同一修订、level4 提示词）：baseline=0 → Oracle=1（含 quality 证据）。**smoke 可不跑**。baseline/oracle **任一不过 → 换题**：保留旧目录，**新建 `…-YYYYMMDD-HHMM/`**，**先 Docker 清理再**从第 1 步重来（不降 level）。
6. **难度门**：校准已通过 → 锁定**当前 level**（默认 level4），每个 job 完整运行 16 次 Docker trial（当前 `--n-concurrent 16 --n-concurrent-agents 16`）。每个 job 同一提示词；启动前复用并验证同一镜像，记录 digest 与冻结 hash。job 完成后保留全量 jobs 和完整 manifest；可继续 `16×N`，直到候选池能透明选出 16 条（`<1`≥13、`=1`≥1），并将其来源写入 `selected_trials`。超时污染 → 保留故障信息、清理并修环境重跑（不据此改提示词）。
7. **改 tests/environment/instruction/solution 任一文件** → 旧 jobs 全部作废 → **Docker 清理后**从第 4 步重来（若改的是换题/换仓，**新建时间戳目录**从第 1 步）。
8. **打 zip** 前跑 [references/delivery-checklist.md](references/delivery-checklist.md)；P0 未过则停止。
9. **飞书自动回写**（对照成功题 `zq2026080704332` 人工项）：按 [references/feishu-delivery.md](references/feishu-delivery.md) 写入文本字段、上传 zip、改 `状态=已提交`；公式校验须 ✅。
10. **完整完成后** → 进入「连续作业循环」，自动开下一题（除非用户叫停）。

## 连续作业循环（默认开启 · 挂机不停）

目标：一道题完整闭环并飞书「已提交」后，**零确认**立刻开下一道；当前题失败则按规则自动换仓/重开直到成功。适合夜间挂机。

### 什么叫「完整完成」（全部满足才算）

- [ ] P0-1：本地已跑通 baseline/oracle（**smoke 可选**）；**上传 zip 的 `jobs/` 含齐** baseline|nop + oracle + 成功难度门  
- [ ] P0-2：真实 `quality.toml` + `test.sh` 已接 rewardkit；Oracle 有 quality 证据；**非** `[quality] version=1` 空壳  
- [ ] 难度门：每个 job 的 16 条均完整结束；manifest 保留所有 trial 的真实结果；`selected_trials` 恰好 16 条、逐条标明来源 job/trial，且 `<1`≥13、`=1`≥1；无超时/缺 reward 被纳入候选  
- [ ] delivery-checklist 自检 PASS；zip 已生成且路径告知用户  
- [ ] **飞书自动回写完成**（见 [references/feishu-delivery.md](references/feishu-delivery.md)）：  
      `标注员`=当前账号；四列元数据 + instruction/toml 终稿；公式 ✅；  
      zip 已上传（仅 1 个）；`状态=已提交`；`修改日期`已更新；**未写 `标注日期`**；未改 `质检员`

**不算完成、不得开下一题：** 只过难度门但未打合规 zip；P0 未过；飞书未回写成功。

### 成功后立刻做（零确认领下一题）

1. **短汇报当前题**（路径、难度门 pass 数、zip、飞书已提交）——一两句，**不要停下来等人回话**。  
2. **立刻拉下一题**（飞书硬条件）：
   - **标注员 = 向威**
   - **状态 = 已领取**
   - 仍待交付（非「已提交」等）
3. **有题 →** **先 Docker 环境清理** → 马上开做（新建 `…-YYYYMMDD-HHMM/`，端到端第 1 步），**禁止**询问「是否继续 / 要不要下一题」。  
4. **无题 →** 短报「飞书无向威+已领取可执行作业，挂机循环结束」→ **停止**；**禁止**无题时反复刷飞书空等。  
5. 循环：成功交卷 → 领下一题 → … → 直到飞书无可领题或用户说停。

### 失败时立刻做（零确认，同一作业做到成功）

校准失败 / 冻结修订变更 / 环境失败导致需换项目时：

1. **不要问用户**——按本 skill：保留旧目录 → **新建时间戳目录** → **先 Docker 环境清理** → 仅在校准/题目/验证器或环境失效时换 feature/模块/仓 → 从第 1 步重来。  
2. 候选池还不够最终配额时，复用镜像并继续完整 16 次 job，**不要**直接跳下一飞书题。  
3. **仍属同一飞书作业 ID**，直到本题成功交付。  
4. 仅基础设施硬阻断才停并说明。

### 中途换仓 ≠ 完成

难度门/校准失败换工程：**当前会话**继续同一作业 ID；最新时间戳目录 = 默认成功查阅对象。

### 何时才允许停

| 条件 | 行为 |
|------|------|
| 飞书没有「向威 + 已领取」可执行题 | **停止**（唯一正常收工条件） |
| 用户说：停 / 先别开新题 / 做完这题停 | 交付后（或立刻）结束循环 |
| 鉴权失败 / 缺 Key / 宿主机明显不可用 | 停并说明；**不要**假装在做 |

**禁止：** 成功交卷后停下来等确认；失败后停下来问策略；无题时轮询刷表。

详表：[references/continuous-queue.md](references/continuous-queue.md)。

## 与旧 skill / 旧 rule 的关系

- `harbor-annotation`：可参考环境与文风；**zip 的 jobs 策略以本 skill 为准（baseline+oracle + 成功难度门；smoke 可选）**。
- 仓库 `.cursor/rules/harbor-delivery-jobs.mdc` 必须与本 skill 一致。
- 旧习惯「zip 只留难度门、校准不进包」**已作废**。
- 旧习惯「smoke 必须跑 / 必须进包」**已作废**——现行可不跑。

## 详细规则索引（按需读取，勿全量加载）

| 参考文件 | 何时读取 |
|---|---|
| references/sampling-constraints.md | 难度门：16 次独立样本集、任务运行时限、新批次前后汇报 |
| references/level-strategy.md | 提示词 level 策略（默认 level4，何时新建修订） |
| references/task-dir-naming.md | 任务目录命名、重开时间戳目录、默认成功目录约定 |
| references/sampling-selection.md | 16×N 候选池筛选铁律、manifest 记录要求 |
| references/p0-gates.md | 打 zip 前 P0-1/P0-2 硬门禁、quality.toml 骨架、test.sh 约定 |
| references/prompt-no-ai.md | 写 instruction.md 文风硬规则与自检清单 |
| references/ops-notes.md | 环境/网络镜像、Docker 清理、中文 locale、选题/难度、评测监控、评分交付 |
| references/feishu-backfill.md | 飞书自动回写字段与禁止项 |
| references/zip-rules.md | 打 zip 顺序、必须/可选/禁止项 |
| references/antipatterns.md | 质检挂/空耗时间的反模式清单 |
| references/notes-22.md | 22 注意事项全文（培训截图 a–I） |
| references/qc-scores.md | 质检分数 4.2/5.2 全文 |
| references/delivery-checklist.md | 打 zip 前 checklist |
| references/verifier-rewardkit.md | verifier / rewardkit 命令细节 |
| references/instruction-style.md | instruction 文风对照示例 |
| references/continuous-queue.md | 连续作业循环细节 |
| references/domain-taxonomy.md | 领域/子领域分类表 |