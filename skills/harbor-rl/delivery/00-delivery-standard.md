# 交付标准总纲（rewardkit 20260913）
> **内联说明**：本文件原为独立 skill `harbor-rewardkit`，现并入本 skill 的 `delivery/`，使技能包**自包含**。
> 同一内容在 `harbor-rl/delivery/` 与 `harbor-weakness/delivery/` **各存一份，须逐字一致**；规范更新时须同步两处（校验 `diff -r skills/harbor-rl/delivery skills/harbor-weakness/delivery`）。


按《外发版-评测题包交付规范（rewardkit）20260913》生产与交付外发评测题包。
本 skill 是**交付实现层的公共底座**；具体题型的构造方法见对应题型 skill（见文末「与其他 skill 的关系」）。

**一句话定位**：把一道已经设计好的题（题面、源文件、参考答案、判分要点），封装成平台可直接判分的五件套，并通过六道门验证。

## 用途与触发条件

触发词：rewardkit / rubrics.toml / prompt.md / rubrics.json / claude-code judge / individual 模式 /
golden 预检 / verifier_error / 三模型跑分 / 交付文档.md / 外发评测题包 / 供应商题包 / 打包提交。

## ⚠️ 与 harbor-sota 的口径差异（不得混用）

| 项 | `harbor-sota`（旧版 v4 / 20260808） | **本 skill（rewardkit / 20260913）** |
|---|---|---|
| 评分器 | `tests/graded/judge.toml` + `tests/gating/gating.toml` | **`tests/rubrics.toml` + `tests/prompt.md`** |
| 判官形态 | Judge 模型一次性读文件 | **claude-code agent judge，逐条独立会话（`mode = "individual"`）** |
| criterion 类型 | 仅 binary | **binary + likert（points = 5，须写 5/4/3/2/1 锚点）** |
| 扣分写法 | 负向 weight | **`negate = true` + 正 weight（禁止负 weight）** |
| 参考答案位置 | `tests/golden_output/` | **`tests/__golden_output/`** |
| 预检标准 | Oracle ≥ 0.7、空产物 ≤ 0.10 | **参考答案 > 0.85** |
| 难度验证 | SOTA 三家均分分档 | **三模型（gpt-5.6-sol / opus-4-8 / qwen3.8-max0902）均分 < 0.7 且至少一个模型有得分** |
| 额外必交 | — | **`rubrics.json`、`tests/prompt.md`** |

> 同一批次内**不可混用**两套口径。

## 交付标准（G1–G6，任一不过禁止打包提交）

> **编号说明**：`G1–G6` 是**本 skill 为便于索引而归纳的门禁编号**，
> 规范原文（《评测题包交付规范（rewardkit）20260913》§7「验收标准」+ §8「打包与提交」）**未使用该编号体系**。
> 引用与讨论时须注明"归纳编号"，避免被误当作官方术语。
>
> **与之并列但不属本编号体系的两项**：① **人工质检**（考察题目真实性、参考答案合理性、打分项设计合理性、是否 hack —— 出自领域规范，一经发现**直接打回**）；② **AI 机检**（AI 质检题目质量 / 打分项质量 / AI 总分检查）。

| 门 | 标准 | 验证方式 |
|---|---|---|
| **G1 结构门** | 五件套齐全：`instruction.md` / `task.toml` / `rubrics.json` / `environment/`(Dockerfile + requirements.txt + input_files/) / `solution/`(solve.sh + golden_output/) / `tests/`(test.sh + finalize.py + rubrics.toml + prompt.md + __golden_output/)；`requirements.txt` 无依赖也交空文件；`solve.sh`/`test.sh` 为 **LF 且带可执行位** | 目录与文件检查 |
| **G2 内容门** | 交付物文件名**六处逐字节一致**（instruction.md / `deliverables.path` / `artifacts` / `solution/golden_output/` / `tests/__golden_output/` / criterion description）；`task_id` **三处一致**（目录名、`[metadata].task_id`、`[task].name` 的 name 段）；全包无真实密钥 | 逐字节比对 |
| **G3 评分器门** | `weight` 仅 `3.0/7.0/10.0`、**无负 weight**；`type` 仅 `binary/likert`；likert 均显式 `points = 5` 且 description 含 **5/4/3/2/1 锚点**；每条 criterion 有 `name` 且**等于 `id`**；description 含 `Deliverables to inspect:` 路径清单；`prompt.md` 含 `{criteria}` 且 prompt + 全部 description **< 100 KB**；Critically Important **≥2 条**；内容质量维度正分 **≥30%**；"总是需要"维度已覆盖 | 解析 rubrics.toml 统计 |
| **G4 判分门** | ① **golden 预检**：`harbor run -p <题目目录> -a oracle` → 主分 **> 0.85** 且 `verifier_error = 0`；② 镜像自检末行打印 `OK`（`claude --version` 含 `2.1.114`）；③ 人为制造失败（清空 `JUDGE_API_KEY`）时 `reward_exit_message.json` 出现且 `exit_code` 归类正确 | harbor CLI + docker |
| **G5 难度门** | Claude code 框架下，`gpt-5.6-sol` / `claude-opus-4-8` / `qwen3.8-max0902` 各跑 1 次，裁判 `qwen3.7-plus`：三模型均分 **< 0.7** 且**至少一个模型有得分**；按等级核对 A1∈[0.6,0.7) / A2∈[0.5,0.6) / A3<0.5 | 跑分轨迹留档 |
| **G6 洁净门** | 无 `.git/`、`__pycache__/`、`.venv/`、`__MACOSX/`、`.DS_Store`、`reward.json`、`logs/`、`jobs/`；全 UTF-8、单文件名 ≤200 字节、无符号链接；批次→题目→五件套层级正确；批次根含 `交付文档.md` | 17 项自检 |

## 端到端流程（不得跳步）

```
1. 冻结口径  → 2. 落五件套骨架 → 3. 写 instruction.md → 4. 写 task.toml（+ rubrics.json）
→ 5. 写 environment/（Dockerfile + requirements.txt + input_files/ [+ skills/]）
→ 6. 写 solution/（solve.sh + golden_output/，并复制一份到 tests/__golden_output/）
→ 7. 复制固定模板 tests/test.sh + tests/finalize.py → 8. 写 tests/rubrics.toml + tests/prompt.md
→ 9. 镜像构建与自检 → 10. golden 预检 → 11. 三模型难度验证 → 12. 17 项自检 → 13. 打包提交
```

### 1. 冻结口径

开工前一次性确认并记录：规范版本（rewardkit 20260913）、`harbor-rewardkit` 版本（`0.1.7`）、
`claude-code` 版本（`2.1.114`）、待测模型三元组、裁判模型、等级区间、批次命名与供应商代号。
**版本变更后不得与旧跑分直接比较。**

### 2. 落五件套骨架

目录名 = **题目编号**（如 `FIN1-SKLII-DEP-001/`）。骨架可从 `assets/` 复制：

```bash
cp -r <skill>/assets/task.toml.template   <题号>/task.toml
cp    <skill>/assets/rubrics.toml.template <题号>/tests/rubrics.toml
cp    <skill>/assets/prompt.md.template    <题号>/tests/prompt.md
cp    <skill>/templates/test.sh            <题号>/tests/test.sh
cp    <skill>/templates/finalize.py        <题号>/tests/finalize.py
cp    <skill>/assets/Dockerfile.template   <题号>/environment/Dockerfile
: > <题号>/environment/requirements.txt          # 无依赖也交空文件
```

### 3. 写 instruction.md

- **自包含**：Agent 只能看到 instruction.md、`/app/input_files/` 与镜像内预装工具/技能。
- 源文件路径固定 `/app/input_files/`（**只读**），交付路径固定 `/app/output/`。
- 显式分段：业务场景与角色 → 可用源文件（表格式，逐文件列出字段/口径）→ 交付物要求（表格式：文件名/是否必交/说明）→ **硬约束独立段落**（禁止项、文件名要求不得藏在括号内）。
- 有 Skill 时：列出全部可用技能的名称、适用描述、容器内 `SKILL.md` 的**绝对路径**，说明脚本相对路径基准目录；**不得**泄露 `expected_skill_dependencies` 的必需技能身份与干扰项身份。
- **不得泄露评分信息**：不出现 rubric 条目、golden 内容或"评分将检查……"式提示。
- 与 Rubric 对齐：rubric 每条显式要求都能在任务书找到出处。

### 4. 写 task.toml + rubrics.json

- **书写顺序强制**：`schema_version` → `artifacts` → `[task]` → `[metadata]` → `[[metadata.deliverables]]` → `[agent]` → `[verifier]` → `[verifier.env]` → `[environment]`。
- 全字段说明与模板 → `02-task-toml.md`。
- `artifacts` 由 `required = true` 的 `deliverables.path` 加 `/app/output/` 前缀**机械展开**，另固定含 `/logs/artifacts/output`。
- **禁止**：`[environment]` 写 `workdir`；`[environment].env` 出现 `JUDGE_*` 或凭证。
- `rubrics.json` = 原始评分细则（与 `rubrics.toml` 的 `id` 一一对应，便于人工追溯）。

### 5. 写 environment/

- Dockerfile 每题一个，**全部走官方源**（Debian / registry.npmjs.org / pypi.org），**禁止任何国内镜像源**。
- 关键三块：`python:3.12-slim` 基座 + `claude-code@2.1.114` 预装 + `harbor-rewardkit[all]==0.1.7` 与解析库。
- `input_files/` → `/app/input_files/` 且 `chmod -R a-w`；`/app/output` 属 `agent` 可写；`WORKDIR /app`。
- 有 skill 时 `COPY skills/ /skills/`，并保证**实际 Agent 用户**可读、脚本可执行。
- 完整模板与自检命令 → `05-environment-and-solve.md`。

### 6. 写 solution/

```bash
#!/bin/bash
set -euo pipefail
mkdir -p /app/output
cp -R /solution/golden_output/. /app/output/
```

- 参考答案文件名/格式/数量与 instruction.md 及 `[[metadata.deliverables]]` **严格一致**。
- 须满足全部正分项、**不得命中任何 negate 条目**。
- `solution/golden_output/` 与 `tests/__golden_output/` **内容一致且均不为空**。

### 7. 复制平台固定模板

`tests/test.sh` 与 `tests/finalize.py` **逐字复制、含注释一并保留、不得改动**（见 `templates/`）。
供应商只负责 `rubrics.toml` 与 `prompt.md` 的内容。

> ⚠️ **模板一致性提示**：`templates/` 下的两份文件系从规范附录 A 抽取还原，已修正一处 PDF 提取导致的注释 `#` 缺失。
> 平台下发官方模板时，**以官方原件为准**；替换后须复核 `bash -n tests/test.sh` 与 `python3 -m py_compile tests/finalize.py`。

### 8. 写 tests/rubrics.toml + tests/prompt.md

- `rubrics.toml`：`judge = "claude-code"`、`prompt_template = "prompt.md"`、`model = "qwen3.7-plus"`、
  `timeout = 7200`、`mode = "individual"`、`weight = 1.0`；每条 criterion 写 `id` / `name`（= id）/
  `description`（含 `Deliverables to inspect:` 清单）/ `type` / `weight` / 可选 `negate`。
- `prompt.md`：**必须保留 `{criteria}` 占位符**，且不得删改 `Material map` / `Reference-solution policy` /
  `Fairness anchor` 三段；工具提示保持"提示"而非"强制"。
- 编写细则（字段约束、权重档位、likert 锚点写法、维度体系） → `03-rubrics-and-prompt.md`。

### 9. 镜像构建与自检

```bash
docker build -t <tag> environment/
docker run --rm --network none <tag> bash -lc '
  python3 -V && bash --version | head -1 && node -v &&
  claude --version | grep -q 2.1.114 &&
  rewardkit --help >/dev/null && markitdown --help >/dev/null &&
  python3 -c "import openpyxl, docx, pptx, pypdf" &&
  pip show harbor-rewardkit | grep ^Version: && pip check &&
  id agent && su agent -c "touch /app/output/.w && rm /app/output/.w" && echo OK'
```

**末行打印 `OK` 才算通过。**

### 10. golden 预检

```bash
export JUDGE_API_KEY=... JUDGE_BASE_URL=...     # 本地自测自己导；task.toml 里保持 ${VAR:-} 占位
harbor run -p <题目目录> -a oracle
```

主分 **> 0.85** 且 **`verifier_error = 0`**。不达标视为 Rubric 写歪，整题退回重写。

### 11. 三模型难度验证（G5）

见 `06-model-validation.md`。要点：Claude code 框架；三模型各 1 次；裁判 `qwen3.7-plus`；
均分 < 0.7 且至少一个模型有得分；**跑分产物与轨迹随题提交**。

### 12. 提交前 17 项自检

逐项跑 `04-package-and-checklist.md` 的 17 项；有 Skill 的题另跑 skill 专项检查。

### 13. 打包提交

- 层级固定「批次目录 → 题目目录 → 五件套」，**不得多套一层、不得平铺在 zip 根**。
- 单题命名 `供应商+领域+一级分类+时间`；批次 zip 命名 `供应商+领域+批次+时间`；**按领域分别打包**。
- 批次根目录放 `交付文档.md`（环境变量配置说明，见 `04-package-and-checklist.md`）。
- 返修：`[task].version` 补丁号递增，只重交修订题，批次目录名加 `_fix<N>`，供应商代号不变。

## 标准目录（交付形态）

```text
<批次目录：供应商名+领域+一级分类+时间>/
├── 交付文档.md                       # 环境变量配置说明（必交）
└── <题目编号>/                       # 目录名 = 题目编号
    ├── instruction.md                # 任务书（仅接受此文件名，≤1 MiB）
    ├── task.toml                     # 配置+元数据+交付物清单（≤1 MiB）
    ├── rubrics.json                  # 原始评分细则
    ├── environment/
    │   ├── Dockerfile                # 单文件含全部依赖
    │   ├── requirements.txt          # 无依赖交空文件
    │   ├── skills/                   # 有 Skill 时提供，与 metadata.skill_set 对应
    │   └── input_files/              # 源文件 → /app/input_files（只读）
    ├── solution/
    │   ├── solve.sh                  # Oracle 入口
    │   └── golden_output/            # 专家标准答案
    └── tests/
        ├── test.sh                   # 固定模板（逐字复制）
        ├── finalize.py               # 固定模板（逐字复制）
        ├── rubrics.toml              # 计分 Rubric（≤2 MiB）
        ├── prompt.md                 # 评分 agent 提示词，含 {criteria}
        ├── __golden_output/          # 参考答案副本（供判官对照）
        └── __assets/                 # 可选：评分侧基准材料
```

## 评分机制速记

```
S_max（满分基准） = Σ 全部正向条目的 weight        ← 负向条目不进分母
分子             = Σ 正向 weight × value − Σ 负向 weight × (1 − value)
主分 reward      = clip(分子 / S_max, 0, 1)
```

- `value`：binary → 0/1；likert → judge 输出 1–5 整数，归一化 `(raw−1)/4`（1→0、2→0.25、3→0.5、4→0.75、5→1）；`negate = true` 自动翻转（完全没违规 = 1.0）。
- **扣分只能 `negate = true` + 正 weight**；写负 weight 会被平台判为异常剔除并记 `verifier_error = 1`，扣分静默失效、整次评分作废。

### 判分可靠性契约（防"静默 0 分"）

| 文件 | 语义 |
|---|---|
| `reward.json.reward` | 主分；**评分不可用时刻意记 0** |
| `reward.json.verifier_error` | **1 = 本次评分不可信**（判官限额/超时/评分器异常）→ 应**重评**而非记零分 |
| `reward.txt` | 单一数值，与 `reward.json` 的 reward 一致 |
| `reward-details.json` | 逐条明细（审计件），缺失不影响主分 |
| `reward_exit_message.json` | **仅评分不可用时存在**；成功则由 finalize.py 删除 fail-closed 占位 |

## 反模式（禁止）

1. 五件套缺件（尤其 `requirements.txt` 空文件、`rubrics.json`、`prompt.md`、`tests/__golden_output/`）。
2. 改动平台固定模板 `test.sh` / `finalize.py`。
3. 权重用 `3.0/7.0/10.0` 以外的值、写负数 weight、用 binary/likert 之外的类型。
4. likert 条目不写 `points = 5` 或不给 5/4/3/2/1 档位锚点；锚点写成 0–1 小数。
5. criterion 不写 `name`（纯中文 description 会 slugify 成空串 → Reward Kit 解析崩溃）。
6. description 未写 `Deliverables to inspect:` 交付物完整路径。
7. `prompt.md` 删掉 `{criteria}` / `Material map` / `Reference-solution policy` / `Fairness anchor`。
8. `[environment]` 写 `workdir`；写 `network_mode = "no-network"`（claude-code 框架会 AgentSetupTimeoutError）。
9. `[environment].env` 出现 `JUDGE_*`、凭证或评分相关信息。
10. 交付物文件名六处不一致；文件名含日期/时间戳/版本号动态成分；`required = true` 用 glob。
11. 题包内出现真实密钥/token（须用占位符并在任务书说明）。
12. Dockerfile 使用国内镜像源。
13. zip 含 `.git/`、`__pycache__/`、`.venv/`、`__MACOSX/`、`.DS_Store`、`reward.json`、`logs/`、`jobs/`、嵌套 zip、符号链接。
14. 打包层级错误（平铺或多套一层）；按题而非按领域打包。
15. 未跑 golden 预检或 Oracle ≤0.85 仍提交；未提供跑分轨迹。
16. 同一批次混用 `harbor-sota`（judge.toml + gating.toml）与本规范口径。
17. toml / prompt.md 携带不可见空白（U+00A0 / U+3000）导致整题判分不可用。

## Verification（交付前必跑）

1. `04-package-and-checklist.md` 的 17 项自检全过。
2. **甲方机器门禁全跑**（`04-package-and-checklist.md` §0b，**以此为准**）：
   `client_gates.py` 一键跑 validate_task_package / validate_rubrics / check_complexity(先 self-test) /
   check_rubric_style --strict / 集中度 / 打包权限 / 批次配额，结论 0 必须整改
   （脚本口径冲突按甲方分级表降为提示/waive，waiver 在质检报告单列）。
3. `bash -n tests/test.sh` 与 `python3 -m py_compile tests/finalize.py` 通过；两者与官方模板逐字节比对。
4. rubrics.toml 用脚本统计：条数、`name == id`、weight 集合、likert 锚点、Critically Important ≥2、内容质量锚点 ≥30%、"总是需要"维度覆盖。
5. **判分复算**（`06-model-validation.md` §7）：各执行体按 rewardkit 公式复算与 reward.json 一致，
   description/weight 与现行 rubrics.toml 零漂移（漂移即重跑判官）。
6. G4 记录留档：oracle 主分、`verifier_error`、镜像自检 `OK`。
7. G5 记录留档：三模型分数、均分、是否有模型得分、**距 0.7 的余量**。
8. 解压 zip 复核层级与无残留后提交。

## 参考文件索引

| 文件 | 内容 |
|---|---|
| `01-bundle-structure.md` | 题包结构、组件清单、容器内路径与可见性、资源上限 |
| `02-task-toml.md` | task.toml schema 1.4 完整模板、逐字段说明、deliverables 五条命名规则 |
| `03-rubrics-and-prompt.md` | rubrics.toml 字段约束、权重档位、likert 锚点、prompt.md 六规则与模板、维度体系、Rubric 五项准则 |
| `04-package-and-checklist.md` | 打包命名、目录层级、提交前 17 项自检、**甲方机器门禁（§0b，以此为准）**、返修、交付文档与环境变量模板 |
| `05-environment-and-solve.md` | Dockerfile 完整模板、镜像硬性要求与自检、solution/solve.sh 要求 |
| `06-model-validation.md` | 三模型难度验证流程、等级区间、跑分轨迹留档要求 |
| `07-pitfalls.md` | 高频故障与踩坑录（含"静默 0 分"成因与排查） |
| `08-skill-packaging.md` | `environment/skills/` 技能包封装规范（目录结构、SKILL.md 写法、任务书入口、装配与自检） |
| `templates/test.sh` | 平台固定模板（附录 A.1，逐字复制） |
| `templates/finalize.py` | 平台固定模板（附录 A.2，逐字复制） |
| `assets/task.toml.template` | task.toml 1.4 起手模板 |
| `assets/rubrics.toml.template` | rubrics.toml 起手模板（含 binary/likert/negate 三种写法） |
| `assets/prompt.md.template` | prompt.md 起手模板（含四段必留内容） |
| `assets/Dockerfile.template` | Dockerfile 起手模板（官方源 + 三块预装） |
| `assets/rubrics.json.template` | rubrics.json 起手模板 |

## 与其他 skill 的关系

| skill | 关系 |
|---|---|
| `harbor-rl` | 题型 skill ①：法律领域常规办公题，交付环节依赖本 skill |
| `harbor-weakness` | 题型 skill ②：金融领域（专项 1000 条 + Weakness 1000 条），交付环节依赖本 skill |
| `harbor-sota` | 旧版外发规范（v4 / judge.toml + gating.toml），**口径不同，不得混用** |
| `harbor-windows` | Windows 专项 Coding Bench（二值判分），**口径不同，不得混用** |
| `wff-workspace-discipline` | 产物落盘位置约束（题包放类型目录，解析产出放 `deliverables/`） |
