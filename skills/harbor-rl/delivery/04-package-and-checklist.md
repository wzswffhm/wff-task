# 打包、提交前自检与交付文档

## 0. 静态自检脚本（先跑脚本，再做人工复核）

`scripts/` 下提供两个可直接运行的校验器，覆盖 §3 中所有**可静态验证**的项：

```bash
python3 scripts/check_rubrics.py   <题目目录>/tests/rubrics.toml   # #4 #5 #11（G3 评分器门禁）
python3 scripts/check_package.py   <题目目录>                       # #1 #2 #3 #3b #4b #7 #8 #9 #10 #12 #14 #15
```

两者均以退出码表示结果（0 = 通过），可直接串进打包流水线。
**未能静态验证、必须实机执行的项**：`#6` golden 预检、`#13` 镜像自检、`#16` 本地跑分、`#17` 交付文档。

## 0b. 甲方机器门禁（交付前必跑，**以此为准**，优先级高于 §3 自检）

甲方以两份 skill 承载出题与质检：**生产侧 `weakness-data-construction`（出题+质检共用脚本）** 与
**质检侧 `weakness-qc` v1.0（质检流程）**。脚本与规范原文同源，**门禁以生产侧脚本为准**。

**铁律：不得把甲方脚本复制进本 skill**——甲方文档明确指出，历史上正是两份取值不一致的
`check_complexity.py` 造成误判。只允许调用，不允许复制。

### 一键跑批（本 skill 提供的 wrapper，只编排不复制）

```bash
python3 delivery/scripts/client_gates.py <题目目录> \
    [--zip <批次zip>...] [--runs-dir <跑分产物与轨迹>] [--waive <脚本名>...]
```

- 脚本目录自动探测（`CLIENT_SCRIPTS` 环境变量 > `~/Desktop/weakness-data-construction/scripts`
  > `~/.codex/skills/...`）；每次运行打印甲方脚本 SHA256 用于跨轮次检测脚本漂移；
- 先跑 `check_complexity --self-test`（哨兵）：self-test FAIL = 脚本取值漂移，其结论自动降级为提示；
- 跑分目录自动发现（兄弟批次目录中含 ≥2 执行体 `reward-details.json` 者）；
  **多代批次并存（如 fix5-149/fix6-149）时必须显式 `--runs-dir` 指定正式批次**。

### 必跑清单与 FAIL 分级（按甲方 gates.md，冻结）

| 脚本 | 查什么 | FAIL 档位 |
|---|---|---|
| `validate_task_package.py` | 字段/取值域/权重分布/`weakness_tag`(`^W\d{2}`)/JUDGE_ 未泄漏到 `[environment.env]` | **必须整改**（零重跑） |
| `validate_rubrics.py` | json↔toml 条数/正分池/negate 集合/维度名/内容质量占比/likert 双标度/锚点一致 | **必须整改**（改判据须重跑判官） |
| `check_complexity.py`（先 `--self-test`） | C1–C5 与文件数/产物数自洽 | **脚本口径冲突 → 提示**，以分级表人工判，不得据此判不通过 |
| `check_rubric_style.py --strict` | 提问式判据/模糊量词/表格类定位语/Subjective 误标 | **必须整改**；但**likert 档位锚点内的递进量词**（如「4=个别…3=约半数…2=多数…」）系甲方脚本正则误报，回规范原文复核后可 `--waive`（waiver 在质检报告单列） |
| `check_instruction_anchors.py` | 判据锚点在题面/材料命中 | **对自有批次不可复用**——脚本硬编码甲方批次 FIN-127/128/129-W（见 07-pitfalls B13）；锚点人工逐条核 |
| `check_cross_model_concentration.py` | 「三模型一致未满分」判据权重占比 | ≥25% → 口径歧义排查（提示级，须复核是否判据口径歧义） |
| `check_package_permissions.py` | zip 0755/LF/残留/层级/golden 双份一致 | **必须整改**（零重跑）。注意：该脚本按**批次包**结构校验，对 task/answer 拆分包报 FAIL 属口径不符、非缺陷（见 07-pitfalls B14） |
| `check_batch_quota.py` | 批次配额/14 种 weakness 覆盖/C 档分布 | 单题包口径只出提示，非阻塞 |

### C1–C5 判定口径（脚本 FAIL 时按此裁决，冻结自甲方 gates.md §三）

| 列 | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| 文件数 | 2 | 5 | 10 | 25 | 50+ |
| Requirement | 3 | 6 | 10 | 15 | 20 |
| **输出产物数** | **1–2** | **2–3** | **3–4** | **4–6** | **4–8** |
| Evidence hop | 1 | 2 | 3 | 4 | 5 |
| 工具种类数 | 1 | 2 | 3 | 4 | 5+ |

- 产物数是**区间且相邻档重叠**：4 属 C3/C4/C5；5–6 属 C4/C5；2 属 C1/C2；
- 申报档高于文件数档：产物数支持即通过（**不得为凑档补输入材料**——那是改题，作废已跑产物）；
- 申报档低于文件数档：低报，必须整改；
- 只有"申报档高于**全部**指标支持上限"才判虚标；单项不齐 = 提示 + 人工核 evidence-hop。

### 质检报告

按甲方模板（三档结论：必须整改 / 提示 / 已核实通过），报告落 **`outputs/`（不进题包目录）**；
判分复算与独立重算要求见 `06-model-validation.md` §7。

## 1. 打包命名

| 场景 | 命名规则 | 示例 |
|---|---|---|
| 单题 | `供应商名字 + 领域 + 一级分类 + 时间` | `xx-金融-投资银行-20260807` |
| 多题（批次） | `供应商名字 + 领域 + 批次 + 时间` | — |

**按领域分别提交压缩包。**

## 2. 目录层级（固定）

```
供应商名字+领域+一级分类+时间/          ← 批次目录
├── 交付文档.md                        ← 环境变量配置说明等（必交，放批次根）
├── FIN-T2-001/                        ← 题目目录（= 题目编号）
│   ├── instruction.md
│   ├── task.toml
│   ├── rubrics.json
│   ├── environment/
│   ├── solution/
│   └── tests/
├── FIN-T2-002/
└── ...
```

**不得多套一层，也不得把题目目录平铺在 zip 根下。**

## 3. 提交前自检 17 项

| # | 检查项 |
|---|---|
| 1 | 五件套齐全；`environment/requirements.txt` 即使无依赖也已交**空文件** |
| 2 | `solution/solve.sh`、`tests/test.sh` 为 **LF 换行且带可执行位** |
| 3 | 交付物文件名在**六处逐字节一致**：`instruction.md`、`deliverables.path`、`artifacts`、两份 `golden_output/`、`criterion description` 的交付物清单 |
| 4 | 满足打分项条数下限、**Critically Important ≥2 条**、**内容质量锚点 ≥30%**、"总是需要"的维度已覆盖；设计态 `rubrics.json` 与运行态 `tests/rubrics.toml` 的**判据 id 集合、负向集合、正分池 `S_max` 一致**，且 `rubrics.json` 的负向项**同时写**负 `weight` 与 `"negate": true`（双标记，`check_package.py` **#4b** 校验） |
| 5 | `weight` 只出现 `3.0` / `7.0` / `10.0`；**无负数 weight**；`type` 只出现 `binary` / `likert`；likert 条目均显式写 `points = 5` 且 description 含 **5/4/3/2/1 档位锚点**；设计态 `rubrics.json` 中每个 `gradient` 条目的 `levels` 键**必须恰为比例键 `0/0.25/0.5/0.75/1`**（`check_rubrics.py` 已校验），**不得写成判官侧整数 `5/4/3/2/1`**，也不得只写成键名列表 |
| 6 | 本地跑通 golden 预检：**Oracle > 0.85，且 `verifier_error = 0`** |
| 7 | `task_id` 在**目录名、`[metadata].task_id`、`[task].name` 的 name 段三处一致**（按小写连字符规则归一化后比较）；`[task].name` 的 org 段与批次目录前缀为同一代号 |
| 8 | 题包任何位置**无真实密钥 / token / 凭证**；需要时用占位符（如 `<API_KEY>`）并在任务书说明。`[environment].env` 中**不得出现凭证或评分相关信息** |
| 9 | 无残留：`.git/`、`__pycache__/`、`.venv/`、`__MACOSX/`、`.DS_Store`，以及本地跑测产生的 `reward.json` / `reward-details.json` / `logs/` / `jobs/` |
| 10 | 所有文件名 **UTF-8**、单个 ≤200 字节、**禁止符号链接**；整包 ≤20 GB |
| 11 | `rubrics.toml`：`judge = "claude-code"`，每条 criterion 均有 `name` 且与 `id` 相同，description 带交付物路径清单 |
| 12 | `tests/prompt.md` 存在且含 `{criteria}` 占位符；`prompt.md` + 全部 description 总量 **< 100 KB** |
| 13 | 镜像自检末行打印 **`OK`**：`claude --version` 输出含 `2.1.114` |
| 14 | **toml / prompt.md 中无不可见空白**（U+00A0 不换行空格、全角空格 U+3000 等 —— 编辑器粘贴中文文案时易带入，会导致 TOML 解析失败、整题判分不可用） |
| 15 | `[verifier.env]` 中 judge 变量均为 `JUDGE_` 前缀且可选项带 `${VAR:-默认值}`；**`JUDGE_*` 未出现在 `[environment].env`**；`[environment].env` 满足最小必要原则 |
| 16 | 本地跑完评分后 `/logs/verifier/reward.txt` 为单一数值且与 `reward.json` 的 `reward` 一致；`reward-details.json` 同时出现在 `/logs/verifier/` 与其 `graded/` 子目录且内容一致；成功时**不存在** `reward_exit_message.json`，人为制造失败（如清空 `JUDGE_API_KEY`）时该文件**出现**且 `exit_code` 归类正确 |
| 17 | 批次根目录含交付文档（见 §4），环境变量表覆盖**全部实际使用的变量** |

### 有 Skill / Workflow 的题目另检查

- `skill_set` 与技能目录、任务书入口、Dockerfile 复制路径**三处一致**；
- 两个预期依赖集合满足**子集关系**（`expected_skill_dependencies ⊆ skill_set`，`expected_tool_dependencies ⊆ tool_set`）；
- 以**实际 Agent 用户**验证技能可读、脚本可运行、SOP 的条件分支及复核说明完整。

> 该检查属于**环境与说明自检**，**不增加过程评分**，也不替代原有 golden 预检。

## 4. 交付文档（`交付文档.md`，放批次根目录）

逐项说明：
1. Key 值；
2. 是否必选，可选项写明默认值（数字型说明取值范围与单位；枚举型逐个说明枚举值含义）；
3. 与其他变量的联动关系。

本规范标准题包的**基线表**如下，题包若有增补变量须一并列入：

| Key | 必选 | 默认值 | 类型/取值 | 说明与联动 |
|---|---|---|---|---|
| `JUDGE_API_KEY` | 是 | —（运行环境注入） | string | judge 网关 key。`test.sh` 派生为 `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` |
| `JUDGE_BASE_URL` | 是 | —（运行环境注入） | string(URL) | judge 网关地址，可带 `/v1` 后缀（test.sh 负责剥除后派生 `ANTHROPIC_BASE_URL` 等） |
| `JUDGE_MODEL` | 否 | `qwen3.7-plus` | string(LiteLLM 模型串) | 裁判模型。经 `REWARDKIT_MODEL` 运行时覆盖 `rubrics.toml` 的 `model`；`JUDGE_API_PROTOCOL=openai` 时同时决定降级 LLM judge 的模型串 |
| `JUDGE_PROVIDER` | 否 | `anthropic` | 枚举 `anthropic` / `openai` | 信息性声明，不改变行为 |
| `JUDGE_API_PROTOCOL` | 否 | `anthropic` | 枚举 `anthropic` / `openai` | `anthropic` = claude-code agent judge（默认链路）；`openai` = 降级为 openai 协议 LLM judge（test.sh 设 `REWARDKIT_JUDGE=openai/<JUDGE_MODEL>` 覆盖 judge 类型，`prompt.md` 的工具提示随之不生效） |
| `EVAL_API_KEY` / `EVAL_API_BASE` | 否 | 空 | string | 旧环境兼容兜底；`JUDGE*` 已注入时被忽略（test.sh 里 `JUDGE*` 优先） |
| `LITELLM_DROP_PARAMS` | 否 | `true` | bool 字符串 | 网关兼容开关，照抄 |

> **必须如实说明的限制**：judge 会话超时（`rubrics.toml` `timeout = 7200`，单位秒）与 verifier 总超时（`task.toml` `[verifier].timeout_sec = 18000`）**不经环境变量配置**——rewardkit 无对应的运行时覆盖钩子，**调整须改 toml 并重新交付**。

> **`test.sh` 派生并导出的变量（非 `[verifier.env]` 直配项，交付文档须如实列出）**：`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_API_KEY`、`ANTHROPIC_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_API_BASE`、`OPENAI_BASE_URL`。其中 `OPENAI_API_KEY` 回落到 `JUDGE_API_KEY`，`OPENAI_API_BASE` 与 `OPENAI_BASE_URL` 均回落到 `JUDGE_BASE_URL`（二者同源，带 `/v1` 后缀时由 SDK 侧处理）。质检会核对交付文档是否覆盖**全部实际使用**的变量——漏列即按 `DELIVERY-DOC` 记必修项（FIN3-WKN-150 实例）。

## 5. 提交与返修

- 整批打包成**一个 zip** 发给对接人，随件注明**批次目录名与题目数**，并附交付文档（放批次根目录）。
- **返修重交**：
  - 修订题目的 `[task].version` **递增补丁号**（`1.0.0` → `1.0.1`）；
  - **只重交修订过的题目目录**；
  - 批次目录名沿用原名加 `_fix<N>`（`work_b01_20260805_fix1`），zip 名同步；
  - **供应商代号不随返修变更**。

## 6. 打包后硬复核

```bash
# 解压后复核层级
unzip -l <batch>.zip | head -50

# 静态自检（脚本，见 §0）
python3 scripts/check_rubrics.py <题目目录>/tests/rubrics.toml
python3 scripts/check_package.py <题目目录>

# 甲方机器门禁（§0b，交付前必跑，以此为准）
python3 scripts/client_gates.py <题目目录> --zip <批次zip> \
    --runs-dir <正式批次的跑分产物与轨迹> --waive check_rubric_style.py

# 残留扫描
find . -name ".git" -o -name "__pycache__" -o -name ".venv" -o -name "__MACOSX" \
       -o -name ".DS_Store" -o -name "reward.json" -o -name "reward-details.json" \
       -o -name "jobs" -o -name "logs" | grep -v "^$"

# 符号链接扫描（不应有输出）
find . -type l

# 不可见空白扫描（不应有输出）
grep -rlP "[\x{00A0}\x{3000}]" --include="*.toml" --include="*.md" .

# 文件名长度
find . -type f -printf '%f\n' | awk '{ if (length($0) > 200) print "TOO LONG: " $0 }'

# 密钥扫描
grep -rniE "(sk-[a-zA-Z0-9]{16,}|api[_-]?key\s*=\s*[\"'][^\"'$]{16,})" . \
  --include="*.toml" --include="*.md" --include="*.sh" --include="*.py" | grep -v '\${'
```
