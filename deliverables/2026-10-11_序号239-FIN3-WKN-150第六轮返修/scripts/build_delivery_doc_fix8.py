# -*- coding: utf-8 -*-
"""重建 FIN3-WKN-150 交付文档（第六轮版），置于批次根目录。

修复要点（对应质检报告第六版第 8 项）：
  - 文档置于**批次根**，不再放在题目目录内；
  - 校正"判据逐字一致 / 本轮未改判据"等与 R27 实改不符的表述；
  - 校正被上一轮批量替换污染的历史章节标注（R27 属 1.0.6→1.0.7）；
  - 当前分数统一为三模型均分 0.6507575758、Oracle 1.000000；
  - 保留真实版本来源（判据版本变更史）与环境变量说明。
"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
SRC = REPO / "harbor-weakness/work_fin-b01_20261006_fix7-150/FIN3-WKN-150/交付文档.md"
DST = REPO / "harbor-weakness/work_fin-b01_20261006_fix8-150/交付文档.md"

SEC_1 = """## 1. 批次信息

| 项 | 值 |
|---|---|
| 批次代号 | `work_fin-b01_20261006_fix8-150`（FIN3-WKN-150 **第六轮：参考生成闭环修复**——按甲方质检报告（序号 239，2026-10-11 快照 `20261011_112005`）的 4 项【待改】完成整改：① 修好参考生成脚本的字符串插值并同步镜像；② 由输入**真实生成**同源 Oracle 产物、补齐执行与判分归档；③ 补 `[scoring] aggregation = "weighted_mean"` 等价配置；④ `交付文档.md` 置于批次根并校正文案。G4 oracle **1.000000**（> 0.85 PASS）；G5 三模型均分 **0.650758**（< 0.70 PASS；按报告第 4 项三模型**无需重跑**，沿用归档值）；`difficulty` 维持 **A1**。判据语义未变（36 条 / 权重 / `S_max = 220`），全量变更史见 §9.1；详见 §3.2.3、§3.2.4 与 §12） |
| 批次根目录 | `work_fin-b01_20261006_fix8-150/`（zip 根即批次目录）；**`交付文档.md` 置于批次根**，四执行体证据 `跑分产物与轨迹/` 归入题目目录 `FIN3-WKN-150/`（按本轮质检报告第 8 项） |
| 领域 / 一级分类 | 金融（FIN） / weakness-driven（弱点定向构造） |
| 供应商代号 | `work_fin`（`[task].name` 的 org 段为 `work_fin`，与批次前缀一致） |
| 题目数 | **1** |
| 打包日期 | 2026-10-11（第六轮：参考生成闭环修复，`[task].version` 1.0.8） |
| 交付口径 | rewardkit 20260913：`tests/rubrics.toml` + `tests/prompt.md` + claude-code agent judge |
| 判分框架 | claude-code CLI **2.1.114**（钉死，不得漂移） |

### 1.1 题目清单

| 题目编号 | 目录 | 难度 | 复杂度 | 参考答案分（G4） | 三模型均分（G5） | 门禁 |
|---|---|---|---|---|---|---|
| FIN3-WKN-150 | `FIN3-WKN-150/` | A1 | C5 | **1.000000** | **0.650758** | **PASS** |

题目信息摘要：

| 项 | 值 |
|---|---|
| `task_id` | `FIN3-WKN-150` |
| `[task].name` | `work_fin/fin3-wkn-150` |
| `[task].version` | `1.0.8` |
| 领域标签 | 私募股权投资 / Pre-IPO 投资定价 / 财务尽调与估值建模 |
| 场景 | 私募股权基金对拟上市公司的 Pre-IPO 投资尽调与估值定价（投资决策备忘录 + 可复算代码 + 配套图表） |
| `weakness_tag` | `W10-大 Workspace 下缺少 Coverage Accounting`、`W04-多要求/多交付物下缺少 Requirement Coverage Accounting`、`W07-长表格/多 Sheet 下的数据覆盖与抗干扰能力弱`、`W11-无据自造数据与口径`、`W12-跨源交叉核对缺失`、`W02-关键冲突下自行选边 / 修改输入`（官方词表逐字全名） |
| `environment_template` | `python3.12-claude2.1.114-rewardkit0.1.7` |
| 交付物 | **7 项必交**（1 份投资决策备忘录 + 1 份可复算代码 + 5 张 PNG 复合图，落 C5 产物上限 4–8 区间；落档依据见 §5.1） |
| 评分项 | 36 条（正 34 / 负 2），`S_max = 220`，CI（weight=10.0）6 条，内容质量正分占比 91.8%；`metadata.scoring.s_max` 已显式声明；运行态 `tests/rubrics.toml` 已补 `[scoring] aggregation = "weighted_mean"`（等价配置，不改变权重、负项解释与评分语义） |

"""

SEC_3 = """## 3. 验证结论（已在本地 WSL 内实机跑通）

### 3.1 参考答案预检（G4）

```
harbor trial start -p harbor-tasks-fix8/FIN3-WKN-150 -a oracle \\
  --ve JUDGE_API_KEY=<key> --ve JUDGE_BASE_URL=<url> \\
  --ve JUDGE_MODEL=qwen3.7-plus --ve JUDGE_PROVIDER=anthropic --ve JUDGE_API_PROTOCOL=anthropic
```

| 项 | 结果 | 门槛 | 判定 |
|---|---|---|---|
| `reward` | **1.000000** | **> 0.85** | **PASS** |
| `criteria_counted` | **36** | = 36 | **✅** |
| `verifier_error` | **0** | = 0 | **✅** |

> 36 条判据全部纳入判分（判官逐条 individual 会话），**未满分条目 0 条**。本轮的 Oracle 判定对象是**由参考生成脚本从只读输入真实生成**的七件产物（生成入口、镜像、命令与产物哈希见 §4.2 与 `跑分产物与轨迹/oracle/轨迹/`），不再是复制 golden 的产物。

### 3.2 三模型难度验证（G5）

冻结口径：框架 claude-code **2.1.114**，裁判 **qwen3.7-plus**，每模型 1 次，全程 `--agent-kwarg disallowed_tools=EnterPlanMode,ExitPlanMode` 禁用 Plan Mode。

| 模型 | `reward` | `criteria_counted` | `verifier_error` | 说明 |
|---|---|---|---|---|
| `gpt-5.6-sol` | **0.686364** | 36 | 0 | 7 项交付齐备；未满分 10 条 |
| `claude-opus-4-8` | **0.534091** | 36 | 0 | 7 项交付齐备；未满分 15 条 |
| `qwen3.8-max-0902` | **0.731818** | 36 | 0 | 7 项交付齐备；未满分 8 条 |
| **三模型均分** | **0.650758** | — | — | **< 0.7 门槛 → PASS** |

结论：**三模型均分 0.650758 < 0.70，且三模型均有得分（最低 claude-opus-4-8 = 0.534091 > 0），G5 难度门达标**。按本轮质检报告第 4 项，三模型独立复算为 GPT 151/220 = 0.6863636、Opus 117.5/220 = 0.5340909、Qwen 161/220 = 0.7318182，算术均值 429.5/660 = **0.6507575758**，与本表一致。

> **难度档定档**：实测均分 **0.650758** 落在 **A1 区间 `[0.6, 0.7)`**，故按 06 号文档「申报档须包含实测均分」的口径，`[task].metadata.difficulty = A1` 与实测一致（`task.toml` 三处 `A1`：`difficulty` / `keywords` / `tags`）。

"""

SEC_323_324 = """#### 3.2.3 G5 判分口径披露（2026-10-11 第五轮：退出回报口径整改后判分重跑）

本轮按甲方**复检报告（序号 239）**的 3 项【待改】完成整改，随后对四执行体按 final 题包**重跑判官**。**判据变更如实说明**：本轮**确有判据文本变更**——`R27` 由"固定退出事实基准"改为"**退出回报口径披露正确**"（信息不足结论 / 条件分析双路径），权重 7、条数 36、`S_max = 220` 与其余 35 条均未变（全量变更史见 §9.1）。

**重跑口径**：复用已归档的 Agent 试次交付物（bind mount，**不重跑 Agent**），按 final 题包重跑判官（claude-code **2.1.114** / 裁判 **qwen3.7-plus**，四场 `criteria_counted = 36`、`verifier_error = 0`）。

| 模型 | 上一轮（fix6 / 1.0.6） | 本轮重跑（fix7 / 1.0.7） | 差值 |
|---|---|---|---|
| `oracle`（G4） | 1.000000 | **1.000000** | +0.000000 |
| `qwen3.8-max-0902` | 0.765909 | **0.731818** | -0.034091 |
| `claude-opus-4-8` | 0.573864 | **0.534091** | -0.039773 |
| `gpt-5.6-sol` | 0.654545 | **0.686364** | +0.031819 |
| **G5 三模型均分** | 0.664773 | **0.650758** | -0.014015 |

- **差值来源如实说明**：本轮差异来自三处叠加——(a) **`R27` 判据文本的实体变更**（不再把无据的 2029 年上市退出基准当作既定事实）；(b) **金标退出段与复算脚本的同步修订**；(c) **判官（LLM）逐次采样波动**（历轮同批复跑的极差曾达 0.065）。门禁结论不变：`0.650758 < 0.70` PASS，档位仍为 **A1**。
- **门禁复核**：G4 `1.000000 > 0.85` ✅；G5 `0.650758 < 0.70` ✅（余量 0.049242）；三模型均非零 ✅。

#### 3.2.4 G5 判分口径披露（2026-10-11 第六轮：参考生成闭环修复后重判 Oracle）

本轮按**质检报告（序号 239，快照 `20261011_112005`）**的 4 项【待改】完成整改，其中第 5/6 项要求"修好参考生成脚本后**从输入生成**完整同源参考产物，并补齐可核验的执行/判分归档"。

**重判范围（如实说明）**：本轮改动的是**参考实现与配置**（`reproduce.py` 字符串插值、两份 golden 的备忘录、`tests/rubrics.toml` 的 `[scoring]` 等价配置），**未改动任何判据文本、权重、负向标记与分档阈值**。因此：

| 执行体 | 是否本轮重判 | 分数 | 依据 |
|---|---|---|---|
| `oracle`（G4） | **是**（产物已重新生成，须重新判分归档） | **1.000000** | 36 条 `criteria_counted = 36`、`verifier_error = 0` |
| `qwen3.8-max-0902` | 否（沿用 fix7 归档值） | **0.731818** | 质检报告第 4 项确认该值可由正负签名权重独立复算，判据未变 |
| `claude-opus-4-8` | 否（沿用 fix7 归档值） | **0.534091** | 同上 |
| `gpt-5.6-sol` | 否（沿用 fix7 归档值） | **0.686364** | 同上 |

- **三模型均分未变**：`(0.731818 + 0.534091 + 0.686364) / 3 = 0.650758`，与质检报告第 4 项独立复算的 429.5/660 一致；门禁 `0.650758 < 0.70` PASS，档位 **A1**。
- **Oracle 判定对象已更换**：见 §4.2——本轮 Oracle 产物由 `reproduce.py` 在判分镜像内从 40 份只读输入**真实生成**，并与两份 golden 同源一致（备忘录 sha256 `72b47a936dd9…`）；`solution/solve.sh` 仍为平台固定模板（97 B / sha256 `3f26ac81cb1c4583…`，与同批次其他题逐字节一致），本轮未改动。

"""

SEC_4 = """## 4. 跑分归档（题目目录内 `FIN3-WKN-150/跑分产物与轨迹/`）

> 按本轮质检报告第 8 项：`交付文档.md` 置于**批次根目录**；四执行体证据归入题目目录，使 zip 顶层同名目录下的第二层仅为独立题目目录。四执行体统一使用 `output/` 目录。

```
work_fin-b01_20261006_fix8-150/            ← 批次目录（zip 顶层）
├── 交付文档.md                             ← 批次根（本轮按报告第 8 项置于此）
└── FIN3-WKN-150/                           ← 第二层：唯一题目目录
    ├── instruction.md / task.toml / rubrics.json
    ├── environment/ solution/ tests/       ← 五件套
    └── 跑分产物与轨迹/
        ├── oracle/               { output/, 轨迹/, reward.json, reward-details.json }
        ├── gpt-5.6-sol/          { output/, 轨迹/{claude-code.txt,trajectory.json}, reward.json, reward-details.json }
        ├── claude-opus-4-8/      { … }
        ├── qwen3.8-max-0902/     { … }
        └── summary.json
```

### 4.1 归档说明（重要）

1. **四执行体统一 `output/`**：均以 `output/` 承载 7 项交付物（备忘录 + 复算代码 + 5 张复合图）。
2. **分数文件按 06 号文档原名归档**：`reward.json` / `reward-details.json` 为验收口径要求的原名；中间产物不归档。
3. **Oracle 产物为真实生成**：本轮 Oracle 的七件产物由参考生成脚本从只读输入生成（§4.2），生成执行证据随包归档；三模型候选产物按报告第 4 项复用 fix7 归档，**不重跑 Agent**。
4. **轨迹已脱敏**：`轨迹/` 内的 claude-code 日志含运行期凭据与不可见空白（U+3000/U+00A0），已按自检要求统一替换为 `<REDACTED_CREDENTIAL>` / 普通空格。
5. **目录与模型名口径**：oracle 归档于 `oracle/`；模型目录名与 `task.toml` / 运行时模型 ID 逐字一致（`qwen3.8-max-0902` 为官方模型名）。

### 4.2 Oracle 参考生成闭环（本轮核心整改，对应报告第 5/6 项）

**缺陷（报告第 5 项）**：`solution/golden_output/FIN3-WKN-150_reproduce.py` 中"退出回报测算与信息边界"段的 4 个字符串片段缺少 `f` 前缀，运行时会输出字面占位符 `{med_pe:.2f}`、`{fm(promise["2027"])}`、`{fm(mcap_ipo)}`、`{stake_mid * 100:.2f}%`、`{fm(exit_val)}`、`{multiple:.2f}`、`{irr * 100:.1f}%`，与归档 golden 中已展开的 `16.12 / 18000 / 290160 / 6.50% / 18873 / 1.26 / 8.0%` 不符，即"报告与生成脚本不相符"。

**处置**：
1. **最小修正字符串插值**：为上述 4 个片段补 `f` 前缀（不改动任何数值、措辞与判据），`tests/__golden_output/` 的镜像同步为**逐字节一致**（sha256 `8fbdca952fc3…`）。
2. **从输入真实生成**：在判分镜像 `fin3-wkn-150:local` 内以只读方式挂载 `environment/input_files/`（40 份材料），执行
   `python3 /solution/golden_output/FIN3-WKN-150_reproduce.py /app/input_files /app/output`，
   产出 1 份备忘录 + 1 份复算代码 + 5 张 PNG，共 **7 项**。
3. **生成结果驱动的三处参考实现修正（R11 / R19 / R32 闭环）**：逐轮重判把「判据明确要求、金标未明写」的缺陷逐处暴露并补齐——(a) `R11`（扣非归母净利润还原）要求列示报告期**四期**非经常性损益（税后），金标此前只有 2025 年的 2,550；核对《11_非经常性损益明细.csv》后补列 2023 年 1,564、2024 年 1,768、2025 年 2,550、2026 年上半年 1,088。(b) `R19`（净负债口径）要求**明确指出**货币资金总额与有息负债构成，金标此前只给受限额与合计；补写「货币资金总额 25,000 万元（使用受限 3,500 万元、可自由支配 21,500 万元）」与「有息负债 20,000 万元（短期借款 12,000 万元 + 长期借款 8,000 万元）」。(c) `R32`（不硬编码结论）要求由脚本从输入材料计算出结论数值，原脚本把总股本 12,000 万股与第一大客户占比 36% 写成常量；现改为总股本从《34_股权结构、期权池与历史融资.md》股权结构表的合计行读取、客户集中度从《23_收入明细_分客户_2025.csv》按营业收入降序计算（口径不变，结果仍为 12,000 万股与 36.0%）。三处修正**只把脚本已算出的、输入材料中已有的数据写入正文或改为读入**，不改动任何结论数值、不引入新参数。
4. **两份 golden 与生成结果同源**：生成的备忘录（17,312 B，sha256 `72b47a936dd9…`）同步覆盖 `solution/golden_output/` 与 `tests/__golden_output/`，三处（含 Oracle 归档 `output/`）**逐字节一致**；5 张 PNG 与既有 golden 逐字节相同。
5. **执行证据随包归档**：`跑分产物与轨迹/oracle/轨迹/` 下新增 `generation.log`（脚本完整 stdout）、`generation.json`（命令 / 镜像 / 返回码 / 耗时）、`generated_manifest.json`（7 件产物尺寸与 sha256），使"从输入生成"可被独立复核。
6. **平台模板未改动**：`solution/solve.sh` 属平台固定模板（97 B / sha256 `3f26ac81cb1c4583…`），本轮**刻意保持原样**，生成闭环由上述执行归档承载，避免破坏平台模板一致性。

"""

SEC_5 = """## 5. 交付清单

| # | 内容 | 位置（批次内） |
|---|---|---|
| 1 | 交付文档（本文件） | `work_fin-b01_20261006_fix8-150/交付文档.md`（**批次根**） |
| 2 | 跑分产物与轨迹（四执行体 + summary） | `work_fin-b01_20261006_fix8-150/FIN3-WKN-150/跑分产物与轨迹/` |
| 3 | 题目 FIN3-WKN-150（五件套） | `work_fin-b01_20261006_fix8-150/FIN3-WKN-150/` |

题包五件套：`instruction.md` / `task.toml` / `rubrics.json` / `environment/`（Dockerfile + requirements.txt + input_files/）/ `solution/`（solve.sh + golden_output/）/ `tests/`（test.sh + finalize.py + rubrics.toml + prompt.md + __golden_output/）。

"""

SEC_91 = """### 9.1 判据版本变更史（真实变更全量登记）

> 本节逐版登记 `tests/rubrics.toml`（运行态）与 `rubrics.json`（设计态）的真实变更，凡涉及判据变更的版本对均在此显式登记，避免"判据未变"的笼统表述与实证冲突。

| `[task].version` | 批次 | 判据（`tests/rubrics.toml` / `rubrics.json`）变更 | 是否重跑判官 |
|---|---|---|---|
| 1.0.1 → 1.0.2 | `work_fin-b01_20261005_fix-150` | **R01**：5 张图名称由"去前缀简写"改为**全名**（含 `FIN3-WKN-150_` 前缀与 `.png`），与 `instruction.md` / `task.toml` 逐字一致 | 是（三模型 regrade，见 §3.2.1） |
| 1.0.2 → 1.0.3 | `work_fin-b01_20261006_fix3-150` | **设计态 `rubrics.json`**：`N01/N02` 补 `"negate": true`（与运行态 TOML 对齐）；**运行态判据文本未变** | 否（G5 不重跑；oracle 重跑见 §7） |
| 1.0.3 → 1.0.4 | `work_fin-b01_20261006_fix4-150` | **无**（该轮整改为 βu 取指引值、第九章并入八章、字数与折价口径说明，见 §7） | 否 |
| 1.0.4 → 1.0.5 | `work_fin-b01_20261006_fix5-150` | **R30、R31**：锚点 4 的量词"个别"改为**数量阈值**（"1 项" / "1 处"），双文件逐字同步 | 是（四执行体重跑，见 §9） |
| 1.0.5 → 1.0.6 | `work_fin-b01_20261006_fix6-150` | **无**——判据与 1.0.5 逐字一致（该轮只修金标利润桥与包内权限，见 §10） | 是（金标修订后四执行体重判） |
| 1.0.6 → 1.0.7 | `work_fin-b01_20261006_fix7-150` | **R27（实体变更）**：由"固定退出事实基准"改为"**退出回报口径披露正确**"（信息不足结论 / 条件分析双路径）；条数 36、权重 7、`S_max = 220` 与其余 35 条未变 | 是（四执行体重跑，见 §11） |
| 1.0.7 → 1.0.8 | `work_fin-b01_20261006_fix8-150`（本轮） | **判据语义无变更**；新增 `[scoring] aggregation = "weighted_mean"` **等价配置**（不改动权重、负向解释、分档阈值与任何 `description`）。另修参考实现 `reproduce.py` 的字符串插值与两份 golden | 是（**仅重判 Oracle**；三模型按报告第 4 项无需重跑） |

**口径澄清**：

1. 判据的**不变项**：条数恒为 **36**、`id` 集合不变、正/负权重与 `negate` 标记不变、`S_max` 恒为 **220**、分档阈值不变。故历轮分数差异**不构成难度档位变化**（`difficulty` 恒为 `A1`）。
2. **1.0.6 → 1.0.7 确有 `R27` 实体变更**，本轮文档已如实登记（此前 `work_fin-b01_20261006_fix7-150` 批次的交付文档曾误记为"判据逐字未变"，本次一并更正）。
3. **1.0.7 → 1.0.8 未改判据语义**：仅补 `[scoring]` 等价配置与修正参考实现，三模型无需重跑。
4. 每次变更后 `rubrics.json`（设计态）与 `tests/rubrics.toml`（运行态）均**逐字同步**，`check_package.py` #4b（设计态/运行态判分定义一致性）通过。

"""

SEC_12 = """

## 12. 第六轮整改记录（2026-10-11，批次 `work_fin-b01_20261006_fix8-150`，`[task].version` 1.0.8）

> 依据飞书《序号239_质检报告 (3).md》（快照 `20261011_112005`；检查对象 `work_fin-b01_20261006_fix7-150.zip`，
> SHA-256 `36b416bcdd4cb4791715a91b06a6c6c84a23b09bb44307f17bc63322e02386f8`）。报告共 10 条：
> 6 条【正确】、**4 条【待改】**（第 5、6、7、8 项）。整改范围原文：「修复参考生成并补齐 Oracle 闭环，
> 重判受影响项；补等价 scoring 配置及根文档一致性。无需修改题面或业务输入、无需重跑三模型 agent。」

### 12.1 四项【待改】整改对照

| # | 质检条目（原文要点） | 处置 | 闭环证据 |
|---|---|---|---|
| 5 | `reproduce.py` 第 830—838 行的 `A(...)` 参数是普通字符串而非 f-string，输出字面占位符；gold 备忘录第 121 行却已展开。请**最小修正字符串插值并同步镜像**，再**从输入生成**完整同源参考产物；不能仅手工改 memo 或复制 gold 冒充生成成功 | 为缺失 `f` 前缀的 4 个片段补 `f`（`{med_pe:.2f}`、`{fm(promise["2027"])}`、`{fm(mcap_ipo)}`、`{stake_mid*100:.2f}%`、`{fm(exit_val)}`、`{multiple:.2f}`、`{irr*100:.1f}%` 全部正常插值）；`tests/__golden_output/` 镜像同步；随后在判分镜像内由脚本从 40 份只读输入生成产物；生成结果驱动补全 `R11` 所需的四期非经常性损益后再次生成，并以最终生成结果更新两份 golden | 脚本两份逐字节一致（sha256 `8fbdca952fc3…`）；生成产物无任何 `{…}` 占位符残留；生成备忘录 17,312 B / sha256 `72b47a936dd9…`，与 `solution/golden_output`、`tests/__golden_output`、`oracle/output` **四处逐字节一致**；四期非经常性损益 1,564 / 1,768 / 2,550 / 1,088、扣非归母 7,021 / 9,231 / 12,070 / 6,137、货币资金总额 25,000（受限 3,500 / 可支配 21,500）与有息负债 20,000（短期 12,000 + 长期 8,000）均已明写；5 张 PNG 与既有 golden 逐字节相同 |
| 6 | 原 Oracle 七件产物逐字节等于提交 gold，但第 5 项证明报告与生成脚本不相符，**尚不能验收参考生成闭环**；请补齐可核验的**完整新 Oracle 实际生成产物及执行/判分归档**，否则实际生成后重判 Oracle 与受影响项 | 在 `fin3-wkn-150:local` 内真实执行生成（只读挂载输入、输出至 `/app/output`），得到七件产物；执行命令、镜像、返回码、耗时、脚本 stdout 与 7 件产物 sha256 全部随包归档；据此重判 Oracle，并据 `R11` 判 0 的真实反馈补全金标后再次生成、再次重判，直至闭环 | 归档 `跑分产物与轨迹/oracle/轨迹/`：`generation.log`、`generation.json`、`generated_manifest.json`、`说明.txt`；容器返回码 0、耗时约 3 s；Oracle 重判 `reward = 1.000000`、`criteria_counted = 36`、`verifier_error = 0`（见 §3.2.4） |
| 7 | `tests/rubrics.toml` 缺规范要求的 `[scoring] aggregation="weighted_mean"`；补齐等价配置并重跑静态/项目门禁，**不改变原权重、负项解释或评分语义** | 在 `tests/rubrics.toml` 末尾追加 `[scoring]` / `aggregation = "weighted_mean"` 两行（与同批次 FIN3-WKN-149 写法一致），未触碰任何 `[[criterion]]` | `tomllib` 解析得 36 条 criterion 不变、`scoring = {'aggregation': 'weighted_mean'}`；`check_rubrics.py` **[PASS]**（36 条 / 正 34 负 2 / `S_max 220.0` / CI 6 条 / 内容质量正分 91.8%）；`check_package.py` **[PASS]** |
| 8 | 批次根目录缺 `交付文档.md`（现置于题目内）；并应校正文案——其中仍写均值 `0.664773` 及"判据逐字一致 / 本轮未改判据"，与当前 `0.6507575758` 及 `R27` 实改不符。保留真实版本来源与环境变量说明，不另增加报告附件 | 将交付文档置于**批次根**（题目目录内不再放置）；重写当前状态章节：批次 `fix8-150`、版本 `1.0.8`、Oracle `1.000000`、三模型均分 `0.650758`；更正被上一轮批量替换污染的历史标注（`R27` 变更归入 `1.0.6 → 1.0.7`，并在 §9.1 显式登记）；保留 §2 环境变量表与 §3.4 平台模板对齐说明 | 本文件 §1 / §1.1 / §3 / §4 / §5 / §9.1 / §10 / §11 / §12 数值与版本标注一致；zip 顶层第二层仅 `FIN3-WKN-150/`，交付文档位于顶层；未新增任何报告附件 |

### 12.2 六项【正确】（不重复退回，本轮未改动）

| # | 质检条目 | 本轮处置 |
|---|---|---|
| 1 | 元数据明确为 weakness，绑定 W10/W04/W07/W11/W12/W02；40 份材料覆盖、审计/管理口径、扣非与股份支付、可比样本筛选、参数边界和申报/退出区分均有真实触发点；正分池 220、负池 17，比例 7.73% 符合要求 | 未改动 `weakness_tag`、判据池结构与权重 |
| 2 | 题面及候选输入与已核版一致；材料可读、声明虚拟重建；八章备忘录、五图、复算代码及只读输入约束明确；未因原生轨迹固定文件名或目录深度增加门槛 | 未改动题面、输入与只读约束 |
| 3 | 上轮 `R27` 无依据退出时点/回报口径**已实际改正**；gold 报告及 36 项四臂判分明细采用修后描述；利润桥新增非经常性损益还原步骤；DCF 约 8.174% WACC、226,700.12 万元股权价值等业务链无新增矛盾 | 未再修改 `R27` 文本与金标业务数值 |
| 4 | GPT/Opus/Qwen 均保留真实工具轨迹与七项作答文件（90/20/43 步）；各自 36 条 description 与 rubrics 逐项一致、无单项 error；签名权重独立复算 GPT 151/220、Opus 117.5/220、Qwen 161/220，均值 429.5/660 = 0.6507575758 < 0.7 且不全零，`A1` 正确；单模型高于 0.7 不构成返修；判官理解偏差不要求原样重跑、不手改原分 | 三模型产物、轨迹与分数**原样保留**；未重跑 Agent、未修改任何归档分数 |
| 9 | 甲方原静态工具先行运行，原始输出保存在 `client_static_a_current`（11 条原始发现）；F06 命中正式四臂证据不作退回；R14/R16 的目录与文件名拆开书写仍可定位必交物，不据此新增路径字符串门槛；实际剩余静态问题为第 7、8 项 | 未修改甲方工具；第 7/8 项已按 §12.1 闭环 |
| 10 | 最终 ZIP CRC 正常，唯一顶层目录与 ZIP 去扩展名一致；`solve.sh`/`test.sh` 为 LF 与 0755；原包与交付物字段保留，本轮只替换主报告附件，机器报告及检查明细不上传 | 三包重打包并复核：顶层唯一 `work_fin-b01_20261006_fix8-150/`、第二层唯一 `FIN3-WKN-150/`、`.sh` 均为 `0755`、全部 LF、CRC 正常；飞书仅替换三附件字段，未上传机器报告或检查明细 |

### 12.3 本轮判分与同步

- **判分范围**：仅重判 **Oracle**（产物已重新生成）；三模型按报告第 4 项**无需重跑**，沿用 fix7 归档分数。
- **判分结果**：`oracle` **1.000000**（36 条全满分，未满分 0 条）；`qwen3.8-max-0902` **0.731818**；`gpt-5.6-sol` **0.686364**；`claude-opus-4-8` **0.534091**；三模型均分 **0.650758 < 0.70**（PASS）。
- **难度同步**：0.650758 ∈ `[0.6, 0.7)` → **A1**，`task.toml` 三处 `A1` 一致，**无需改动**；`summary.json` 的 `declared_difficulty = A1`。
- **归档同步**：`_rejudge_fix8/oracle/verifier/{reward.json, reward-details.json}` 按原名同步进 `跑分产物与轨迹/oracle/`；`summary.json` 的 `round` → `fix8(reference-generation-closure)+rejudge`、`task_version` → `1.0.8`、`mean = 0.650758`、`gate_pass = true`，并新增 4 条 `invalid_runs` 留痕（fix7 轮四场分数）。
- **飞书回写（本轮）**：附件字段按「先删旧、再传新」替换为 fix8 批次三个 zip（交付物 → `work_fin-b01_20261006_fix8-150.zip`、`FIN3-WKN-150_task.zip`、`FIN3-WKN-150_answer.zip`），三字段复核为**恰好 1 个文件**；`题目难度 fldYA4iRaD` 维持 **`A1`**；**状态字段 `fldKFzG0cA` 不做改动**（仍为「待返修」，由质检方流转）；序号、工作表、报告字段均不动，且**不新增报告附件**。
- **自检**：`check_rubrics.py` **[PASS]**；`check_package.py` **[PASS]**（含 #4b 设计态/运行态一致、#9 无 `_rejudge` / `__pycache__` 残留）。

**改动判据**：**无实体变更**（仅补 `[scoring] aggregation = "weighted_mean"` 等价配置）；参考实现与两份 golden 的修订不影响既有判据语义，故三模型无需重跑。

**重跑方式**：WSL Ubuntu 独立 Docker Engine，镜像 `fin3-wkn-150:local`，judge `qwen3.7-plus`，claude-code 2.1.114；Oracle 复用其真实生成产物，三模型复用现有归档候选交付物。

"""

FOOTER = """---

*文档生成：2026-10-05（FIN3-WKN-150 返修版 1.0.2）；2026-10-06 更新为质检整改版 1.0.3（批次 work_fin-b01_20261006_fix3-150）；2026-10-09 更新为第二轮质检整改版 1.0.4（批次 work_fin-b01_20261006_fix4-150），同日按甲方质检报告（序号 239）完成 5 项【待改】整改并重跑判官，形成第三轮 1.0.5（批次 work_fin-b01_20261006_fix5-150，见 §9）；2026-10-10 按甲方复检报告（序号 239）完成 3 项【待改】整改并重跑四执行体判官，形成第四轮 1.0.6（批次 work_fin-b01_20261006_fix6-150，见 §10）；2026-10-11 按甲方质检报告（序号 239，快照 20261011_112005）完成退出回报口径整改并重跑四执行体判官，形成第五轮 1.0.7（批次 work_fin-b01_20261006_fix7-150，见 §11）；同日按同轮质检报告完成参考生成闭环修复、补 [scoring] 等价配置、交付文档置于批次根并重判 Oracle，形成第六轮 1.0.8（批次 work_fin-b01_20261006_fix8-150，见 §12）。验证环境：WSL Ubuntu + harbor 0.22.0 + docker 29.1.3（含 compose v2）；判分在 WSL Ubuntu 独立 Docker Engine 执行。*
"""


def cut(text: str, start: str, end: str) -> tuple[str, str, str]:
    """返回 (前段, 命中区间, 后段)；找不到时抛错。"""
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[:i], text[i:j], text[j:]


def main() -> int:
    doc = SRC.read_text(encoding="utf-8")

    # §1：从 "## 1. 批次信息" 到 "## 2. 环境变量表"
    before, _, after = cut(doc, "## 1. 批次信息", "## 2. 环境变量表")
    doc = before + SEC_1 + after

    # §3：从 "## 3. 验证结论" 到 "## 4. 跑分归档"
    before, mid, after = cut(doc, "## 3. 验证结论", "## 4. 跑分归档")
    keep_33 = mid[mid.index("### 3.3 静态自检"):]           # §3.3 + §3.4 原文保留
    # §3.2.1 / §3.2.2 为历史判分披露（v2→regrade、第三轮 fix5），保留原文以维持证据链
    hist = mid[mid.index("#### 3.2.1 G5 判分口径披露"):mid.index("#### 3.2.3 G5 判分口径披露")]
    sec33 = keep_33.replace(
        "`check_rubrics.py harbor-weakness/FIN3-WKN-150/tests/rubrics.toml` → **`[PASS]`**"
        "（36 条 / 正 34 负 2 / `S_max 220.0` / CI 6 条 / 内容质量正分 91.8% / gradient 比例键校验通过）",
        "`check_rubrics.py harbor-weakness/work_fin-b01_20261006_fix8-150/FIN3-WKN-150/tests/rubrics.toml` → "
        "**`[PASS]`**（36 条 / 正 34 负 2 / `S_max 220.0` / CI 6 条 / 内容质量正分 91.8% / gradient 比例键校验通过）"
    ).replace(
        "`check_package.py harbor-weakness/FIN3-WKN-150` → **`[PASS]`**",
        "`check_package.py harbor-weakness/work_fin-b01_20261006_fix8-150/FIN3-WKN-150` → **`[PASS]`**"
    )
    doc = before + SEC_3 + hist + SEC_323_324 + sec33 + after

    # §4：到 "## 5. 交付清单"
    before, _, after = cut(doc, "## 4. 跑分归档", "## 5. 交付清单")
    doc = before + SEC_4 + after

    # §5：到 "### 5.1"
    before, _, after = cut(doc, "## 5. 交付清单", "### 5.1")
    doc = before + SEC_5 + after

    # §9.1：到 "## 10. "
    before, _, after = cut(doc, "### 9.1 判据版本变更史", "## 10. ")
    doc = before + SEC_91 + after

    # §10 历史标注修复（该区间内还原为 fix6 / 1.0.6）
    i = doc.index("## 10. ")
    j = doc.index("## 11. ", i)
    seg = doc[i:j]
    seg = seg.replace("work_fin-b01_20261006_fix7-150", "work_fin-b01_20261006_fix6-150")
    seg = seg.replace("1.0.7", "1.0.6")
    seg = seg.replace("第五轮：退出回报口径整改后判分重跑", "第四轮：复检整改后判分重跑")
    seg = seg.replace("fix7(exit-assumption-remediation)+rejudge", "fix6(qc3-remediation)+rejudge")
    doc = doc[:i] + seg + doc[j:]

    # 页脚替换 + 追加 §12
    before, _, _ = cut(doc, "---\n\n*文档生成：", "验证环境：WSL Ubuntu")
    tail_start = doc.index("验证环境：WSL Ubuntu")
    doc = doc[:doc.index("---\n\n*文档生成：")] + SEC_12 + FOOTER

    dst = DST
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(doc, encoding="utf-8", newline="\n")
    print(f"written {dst}  ({dst.stat().st_size:,} B, {len(doc.splitlines())} lines)")
    for token in ["0.664773", "本轮未改判据", "1.0.8", "0.650758", "72b47a936dd9", "第六轮"]:
        print(f"  {token:14s} 出现 {doc.count(token)} 次")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
