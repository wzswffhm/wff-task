# FIN3-WKN-152 质检报告

| 项目 | 内容 |
|---|---|
| 题目 / 批次目录 / 版本 | FIN3-WKN-152（Reddit IPO 定价委员会复核）/ `work_fin-b01_20261009-152` / 1.0.0 |
| 申报难度 · 复杂度 / 判据条数 | A1（**未定档**，见 §六） · C3 / 27 条（正分池 153，负分 3 条 −10/−7/−7） |
| 参考解 / 模型实测 / 均值·档位 | oracle **1.000000**（G4 PASS） / qwen3.8-max-0902 **1.000000**；gpt-5.6-sol、claude-opus-4-8 **未跑（端点凭据缺失）** / 三模型均分 **未定** |
| 质检方式 / 日期 | 甲方 weakness-qc 流程：机器门禁 + 判分复算 + 独立重算 + 口径歧义排查 + 结构与安全检查 / 2026-10-09 |
| **质检结论** | **不通过（待补）** —— 0 项必须整改（机械层全绿、G4 PASS）；**G5 三模型未齐（缺 2 个模型端点），难度档位无法判定，且已跑模型满分构成高风险信号**（§六）。补齐三模型并按实测定档后方可申请交付。 |

## 一、结论

**机械与判分层全部通过**：8 项甲方机器门禁 + skill 17 项静态自检全绿；**G4 oracle 预检 PASS（reward = 1.000000、verifier_error = 0、criteria_counted = 27、复算一致、27 条零漂移、零分判据空集）**；判据锚点全部可在 `input_files` 找到唯一出处；独立重算三条卡点链路 11 个复核点全部一致；结构/命名/安全/平台模板全项合规；批次 zip 门禁 **FAIL 合计 0**（14 项全 OK）；历史质检报告 12 类错误逐项规避。

**但不能判定通过**：G5 三模型难度验证只完成 1/3（qwen 已跑、gpt/opus 端点凭据缺失），`check_cross_model_concentration` 因执行体不足无法执行，**难度档位未定**。且 **qwen 实测满分 1.000000** —— 三模型均分 `< 0.70` 要求 gpt + opus **< 1.10**（人均 < 0.55），以当前信号判断**破档风险极高**。按甲方规则「不许把未验证写成通过」，结论为**不通过（待补）**。

## 二、必须整改

（暂无。G4/G5 完成后如未过门槛，按对应门禁升级为必须整改。）

## 三、提示（不影响验收，均不构成退回理由）

1. **平台 `prompt.md` 的 `[How to inspect]` 段写死 `.docx`**，与本题交付物 `.xlsx` / `.md` 不符。该文件为五个平台固定模板之一（2767 B / SHA `960b87b2`），规范要求**逐字复制不得改动**；149/150/151 三题交付物同样非 `.docx`，均以同一模板通过验收。且同 prompt 的 `[Tool usage]` 段已声明 `Work out the approach per file type yourself; nothing here is a required route`，`Fairness anchor` 保证评分严格度不因此放松。**保持原样，不构成退回理由。**
2. **`check_rubric_style` 的 8 条 NOTE**（R02 的 1,600 / R14 的 1,213 / R16 的 106 / R22 的 118.361、486.432、980.915 未在 `input_files` 文本命中；R20/R24 标 Subjective）。前六项均为**计算结果锚点**（材料给出的是 `401.176 + 811.946`、`-69.275 - 49.086` 等原始输入，结果由 `Committee_Policy` 明文公式算出，已在独立重算中验证可唯一推出）；R20/R24 为论证质量与增量贡献类 likert，标 Subjective 与 149/151 同类判据口径一致。**均为待人工确认项，非 FAIL，不构成退回理由。**
3. **`check_instruction_anchors.py` 对本题不适用**：该脚本硬编码甲方自有批次路径（`...\zq-金融-投资研究-20260929\FIN-127-W\instruction.md`），对本题直接 `FileNotFoundError`。gates.md 与 149/150/151 三份质检报告均已判定该脚本「对其他批次不可用，锚点核对必须人工」。已按此**人工核对 27 条判据锚点**，结果见 §四。
4. **判官日志含本机路径 / 不可见空白**（历史题包 `trial.log` 同款）：属 harbor 运行日志自带，具取证价值；152 的**题包文件本身**已全量扫描确认无 U+00A0/U+3000（§四）。**不构成退回理由。**
5. **`artifacts` 重叠警告**：`/logs/artifacts` 与 `/logs/artifacts/output` 触发 harbor `UserWarning`。该写法与 149/150/151 的 `task.toml` 完全一致（`/logs/artifacts/output` 为规范要求的固定项），属已知警告非缺陷。**不构成退回理由。**

## 四、已核实通过项

### 4.1 机器门禁（甲方生产侧脚本，原始输出留档 `outputs/152-门禁原始输出.txt`）

| 脚本 | 结果 | 关键读数 |
|---|---|---|
| `validate_task_package.py` | **PASS** | 内容质量正分占比 90%；27 条 / 正分池 153 / 负分 3 / +10 ×3 |
| `validate_rubrics.py` | **PASS（FAIL 合计 0，20 项 OK）** | json↔toml 条数 27 一致、negate 集合 3 条一致、正分池 153 == `s_max`、likert 双标度与锚点一致、**条数 27 ≥ A1 下限 25**、无 NBSP/全角空格、LF、prompt+criteria 17 KB < 100 KB |
| `check_complexity.py --self-test` | **PASS** | 取值映射与分级表一致（产物区间按并集） |
| `check_complexity.py` | **PASS** | `文件数=1→C1  产物数=3→['C2','C3']  声明=C3`（产物数支持申报档，符合 gates.md §3.2 规则 3） |
| `check_rubric_style.py --strict` | **PASS（FAIL 合计 0）** | 提问式/量词/措辞 0 条；8 条 NOTE 见 §三.2 |
| `check_instruction_anchors.py` | **不适用**（脚本硬编码甲方批次） | 转人工核，见 §四.3 |
| `check_cross_model_concentration.py` | **未验证** | 需 G5 跑分产物 |
| `check_batch_quota.py` | **PASS** | 单题包进度提示，非阻塞 |
| skill `check_rubrics.py` | **PASS（G3 全通过）** | 27 条、S_max 153、CI 3 条、内容质量 90.2%、gradient levels 比例键校验通过 |
| skill `check_package.py`（17 项） | **PASS** | 12 项 OK；#6/#13/#16/#17 须实机执行（#13 镜像自检已另行通过） |

### 4.2 独立重算关键链路（不引用金标，只读 `environment/input_files/`）

| 复核点 | 材料出处 | 我的独立复算 | 判据锚点 | 结论 |
|---|---|---|---|---|
| 承销口径 EBITDA | `Committee_Policy/QoE`「SBC 视为持续性经济成本，承销口径不保留该加回」+ `Public_Financials` −69.275 / 49.086 | −69.275 − 49.086 = **−118.361** | R06：−118.361 ±0.5 | **一致** |
| 估值方法切换 | `Committee_Policy/Valuation`「若 Underwriting EBITDA 仍为负，主估值采用 EV / 2024E Revenue」 | EBITDA < 0 → **EV / 2024E Revenue** | R13：EV / 2024E Revenue | **一致** |
| 2024E Revenue | `Committee_Policy/Forecast`「2024E = 2023A × (1 + 22%)」 | 804.029 × 1.22 = **980.91538** | R07：980.915 ±1 | **一致** |
| 净现金桥 | `Committee_Policy/Valuation`「Equity = EV + year-end cash + marketable securities」 | 401.176 + 811.946 = **1,213.122** | R14：1,213.122 ±0.5 | **一致** |
| 三档每股价格 | `Committee_Policy/Valuation` 5/6/7/8/9 五条连写 | **31.274653 / 34.260742 / 37.246831** | R08、R04：31.27 / 34.26 / 37.25 各 ±0.10 | **一致** |
| 定价处置 | `Committee_Policy/Committee disposition`（in_range ∧ \|Δmid\|≤0.50 → Proceed） | 34 ∈ [31.27, 37.25]、\|Δ\|=0.2607 ≤ 0.50 → **Proceed** | R03：Proceed at $34 | **一致** |
| 公司 gross primary | `Offering_Terms` 15.276527m × $34 | **519.401918** | R09：519.402 ±0.5 | **一致** |
| 公司 net primary | `Committee_Policy/Fees`「5% fee + 7.0mm 固定」 | 519.401918 − 25.970096 − 7 = **486.431822** | R10：486.432 ±0.5 | **一致** |
| 股本桥 | `Committee_Policy/Offering`「secondary 不增加公司总股数」 | 143.716563 + 15.276527 = **158.993090**；full = **162.293090** | R11、R16 各 ±0.005 | **一致** |
| greenshoe 增量净募集 | `Committee_Policy/Fees`「增量只扣 5% fee，不重复扣固定费用」 | 3.3 × 34 × 0.95 = **106.590** | R16：106.590 ±1 | **一致** |
| 稀释交叉验算 | `Public_Financials` SEC-02（NTBV 11.17 / dilution 21.33 @ $32.50） | 直接取自材料 | R21：11.17 / 21.33 各 ±0.10 | **一致** |

**三条卡点链路**（决定正分池 R03–R17 共 124 / 153 = **81%** 权重）：QoE 链 → 估值链 → 发行与股本链，逐环复算全部一致。

### 4.3 判据锚点人工核（替代不适用的 `check_instruction_anchors`）

- **20 个数值锚点在 `input_files` 原文命中 20/20**（804.029、−90.824、−69.275、49.086、−84.838、0.22、4/4.5/5、401.176、811.946、15.276527、6.723473、3.3、143.716563、0.05、7、34、11.17、21.33 等）；
- 9 个计算类锚点（−118.361、980.915、31.27/34.26/37.25、519.402、486.432、158.993090、162.293090、106.590、Proceed）**材料无原文，但均可由 `Committee_Policy` 单一条款唯一推出**，推导式已在 §四.2 列出；
- 27 条判据的术语出处已逐条比对 `instruction.md`。

### 4.4 口径歧义与金标自洽（pitfall 案例 2/3/4）

- **案例 2**（难度被口径歧义撑着）：全部判据换算可由 `input_files` 单一条款唯一推出，无「同一事实两处互斥表述」；
- **案例 3**（金标自身不自洽）：金标由脚本从输入逐项计算生成，无「成对调整一端扣一端不扣」的情形；判据容差为 ±0.5mm / ±0.10 / ±0.005，非 ±0.01 锚死；
- **案例 4**（规则文件条文矛盾）：`Committee_Policy` 13 条相互引用的条款已沿边界情形走查（price = 34 区间内且 \|Δmid\|=0.26 < 0.50；price 落区间下沿 31.27 仍 in_range；超出则 Defer），各条可同时满足、无互斥读法。

### 4.5 结构、命名与安全（G1/G2/G6）

| 检查 | 结果 |
|---|---|
| 五件套齐备 | OK（instruction / task.toml / rubrics.json / environment / solution / tests） |
| `requirements.txt` | OK（0 B 空文件） |
| 交付物文件名**六处**逐字节一致 | OK（instruction、`deliverables.path`、`artifacts`、两份 `golden_output/`、27 条 criterion description，3 个文件全对齐） |
| `task_id` 三处一致 | OK（目录 `FIN3-WKN-152` / `[metadata].task_id` / `[task].name = work_fin/fin3-wkn-152`） |
| **`Deliverables to inspect` 逐项列完整路径** | **OK —— 27/27 条逐项列出，无目录级兜底（规避 267-F01 硬伤）** |
| golden 双份逐字节一致 | OK（3 文件，`solution/golden_output` == `tests/__golden_output`） |
| **平台固定模板 5 文件逐字节** | **OK**：Dockerfile 1554/`537d196a`、solve.sh 97/`3f26ac81`、finalize.py 12331/`f528b27f`、prompt.md 2767/`960b87b2`、test.sh 3352/`5920c204` —— 与 148/149/150/151 官方原件完全一致 |
| 换行 | OK（solve.sh / test.sh 均 LF，CRLF=0） |
| 残留扫描 | OK（无 `.git`/`__pycache__`/`.venv`/`__MACOSX`/`.DS_Store`/`reward*.json`/`logs`/`jobs`） |
| 不可见空白 U+00A0/U+3000 | **OK（修复后全包 0 命中）** —— 初检在 `pricing_memo.md` L3 发现 2 处 U+3000，已改为普通空格并重新生成 golden 双份 |
| 密钥/token 扫描 | OK（题包内无 `sk-`/`Bearer`；唯一命中为平台 `test.sh` 的变量赋值 `ANTHROPIC_AUTH_TOKEN="${...:-...}"`，系模板原文非密钥，且与 148–151 同哈希） |
| `JUDGE_*` 泄漏到 `[environment].env` | OK（0 项；`[verifier.env]` 8 项均为 `JUDGE_`/`EVAL_`/`LITELLM_` 前缀且可选项带 `${VAR:-默认值}`） |
| 内网信息 / 脱敏边界 | OK（题包内无内网域名、无本机绝对路径、无受限资料标识） |

### 4.6 镜像与环境（G4①②）

| 项 | 结果 |
|---|---|
| `docker build` | PASS（5 s，layer cache 命中；镜像 `fin3-wkn-152:local` 3.37 GB） |
| 镜像自检末行 `OK` | **PASS**（exit 0）：Python 3.12.15 / bash 5.2.37 / node v20.19.2 / **claude 2.1.114** / rewardkit 0.1.7 / markitdown / openpyxl·docx·pptx·pypdf / `pip check` / `agent` 可写 `/app/output` |
| 额外自检 | `input_files` 对 `agent` 只读 ✓；输入工作簿 8 个工作表可读 ✓ |

### 4.8 G4 参考解预检（判分证据，evidence-checks §1.1–§1.3）

| 检查 | 结果 | 门槛 | 判定 |
|---|---|---|---|
| `reward` | **1.000000** | > 0.85 | **PASS** |
| `verifier_error` | **0** | = 0 | **PASS** |
| `criteria_counted` | **27 / 27** | = 27 | **PASS** |
| `reward.txt` == `reward.json.reward` | `1.0` == `1.0` | 一致 | **PASS** |
| 按 rewardkit 公式复算 | `(Σ正 w·v − Σneg w·(1−v)) / Σ正w` = **1.000000** | 与 reward.json 一致 | **PASS** |
| description / weight / negate 与现行 toml | **27 条零漂移** | 零漂移 | **PASS** |
| 未满分 / 零分判据 | **0 条 / 0 条（空集）** | — | **PASS** |
| `reward_exit_message.json` | 成功路径已由 finalize.py 删除 | 应不存在 | **PASS**（fail-closed 语义正确） |
| 轨迹框架 | oracle 为 harbor 内置 agent，**无 claude-code 轨迹属设计使然**，已在 `轨迹/说明.txt` 如实注明 | 三模型才需 claude-code | 豁免（同 149/151 口径） |

试次 `FIN3-WKN-152__Sa7ciyW`（15:56:42 → 16:25，约 29 分钟）。

> **复算侧自纠**：首轮核验脚本报「N01/N02/N03 weight 漂移」，经排查系**我方脚本 bug** ——
> 误把 toml 的 `negate` 条目转成负 weight 比较，而 reward-details 记录的是正数 weight + 独立 negate 标记。
> 修正后零漂移 PASS。此例印证 evidence-checks §2.4「写出与预期不符的结果时，先怀疑自己的实现」。

### 4.9 G5 已完成部分（qwen3.8-max-0902）

| 检查 | 结果 |
|---|---|
| `reward` | **1.000000** |
| `criteria_counted` / `verifier_error` | 27 / 0 |
| 复算一致性 | **1.000000 一致 ✓** |
| 与现行判据零漂移 | **27 条 ✓** |
| 未满分 / 零分判据 | 0 / 0 |
| 轨迹框架 | `claude-code` + `qwen3.8-max-0902`，`--disallowedTools EnterPlanMode,ExitPlanMode` 生效 |
| 交付物 | 3 项齐全（xlsx 26,431 B / md 4,056 B / py 50,131 B），模型结论 `Proceed @ $34.00`、区间 `[$31.27, $37.25]`、midpoint `$34.26`、净募集 `486.4` 均与金标吻合 |

试次 `FIN3-WKN-152__vFbfvgm`（16:40 → 17:37）。

### 4.10 跑分归档与批次打包

| 项 | 结果 |
|---|---|
| 归档结构 | `跑分产物与轨迹/{oracle,qwen3.8-max-0902}/{output/,轨迹/,reward.json,reward-details.json}` + `summary.json`，与 149/151 验收口径一致 |
| 归档脱敏 | **无密钥命中 ✓**、**U+00A0/U+3000 零命中 ✓**（轨迹 940 KB + 655 KB 全量处理） |
| `oracle/轨迹/说明.txt` | 已补（oracle 无 claude-code 轨迹的取证说明，对应 149 提示 4） |
| 批次 zip | 31 entries / 524 KB，层级根正确、无残留 |
| **`check_package_permissions` 批次包** | **FAIL 合计 0（14 项全 OK）**：五件套 6 + 权限位/LF + golden 双份 + 无残留 + 交付文档 + 含跑分产物 |

### 4.11 历史质检报告错误规避对照（本报告核心复查项）

| # | 历史错误（来源） | 152 规避情况 |
|---|---|---|
| 1 | **267-F01（高/FAIL）**：`Deliverables to inspect` 未逐项覆盖交付物完整路径 | ✅ 27/27 条逐项列出完整文件路径，0 目录级兜底 |
| 2 | **267-R01（中/REVIEW）**：飞书「类型」字段为空 | ✅ 序号 282 的「类型」已为 `weakness` |
| 3 | **267-N01（提示）**：版本号与批次目录 `_fix<N>` 未同步 | ✅ 152 为新题 `version=1.0.0`，无返修轮次，不涉及 |
| 4 | **149-fix1 必修 #4 / 150·151 提示 2**：`prompt.md` 与平台模板非逐字节（2385 vs 2767） | ✅ **初检发现我方写成 3351 B，已用平台原件逐字节替换**，5 文件哈希全对齐 |
| 5 | **150·151 提示 2**：注释行含 `negate = true` 字面串，被甲方文本正则误吞 → 假 FAIL | ✅ 注释行已避免该字面串（仅 description 内保留，151 已验收版同款），`validate_rubrics` FAIL=0 |
| 6 | **149 返修 #2**：zip 内 `solve.sh`/`test.sh` 缺 0755 | ✅ **已验证**：打包显式写 `external_attr = 0o755`，门禁实测「权限 0o755 带可执行位 + LF」OK |
| 7 | **149 返修 #1 / fix3 必修 #1**：zip 层级错误（平铺或多套一层） | ✅ **已验证**：批次包顶层仅 `work_fin-b01_20261009-152`、拆分包顶层仅 `FIN3-WKN-152`，门禁「层级根正确」 |
| 8 | **149 提示 3 / 151 提示 4**：轨迹含不可见空白 | ✅ 题包 0 命中；**跑分轨迹（940 KB + 655 KB）归档时全量脱敏，复扫 0 命中** |
| 9 | **151 提示 1 / pitfall 案例 9**：难度均值余量薄 | ⚠ **升级为风险**：qwen 实测 **1.0 满分**，三模型均分 `< 0.70` 要求 gpt+opus `< 1.10`（人均 <0.55），破档风险极高；三模型未齐，**档位未定**（§六） |
| 10 | **pitfall 案例 6**：`weakness_tag` 编号不合规 | ✅ `W02/W07/W12` 满足 `^W\d{2}`，逐字用官方词表全名 |
| 11 | **pitfall 案例 2**：难度被口径歧义撑着 | ✅ §四.4 全项排查通过；`check_cross_model_concentration` 因执行体不足（仅 qwen）**未验证** |
| 12 | **149 返修 #4**：跑分产物目录/命名不符验收口径 | ✅ **已归档**：`跑分产物与轨迹/{oracle,qwen…}/{output/,轨迹/,reward*.json}` + `summary.json`，含 `oracle/轨迹/说明.txt` |

## 五、重跑影响说明

| 已发生改动 | 影响 | 是否需重跑 |
|---|---|---|
| `prompt.md` 由自写版（3351 B）替换为平台原件（2767 B） | 判官提示词变更（**判分前**改动，尚未产生任何判分证据） | **无需回溯重跑** —— G4 尚未产出有效判分，按平台原件执行首次判分 |
| `rubrics.toml` R20「个别」→量化表述、R23「单元格」→「关键数值」 | 同上，判分前改动 | **无需回溯**，G4 按现行判据执行 |
| `pricing_memo.md` 移除 2 处 U+3000 并重生成 golden 双份 | 金标内容仅去不可见空白，数值与结论零变化 | **无需回溯**（判分前） |

> 以上三处均发生在 G4 首次有效判分之前，不存在「判据变了却沿用旧判分」的 case（evidence-checks §1.5 不适用）。G4 完成后若再改判据/金标，须按重跑决策表执行。

## 六、质检边界（未验证项，不计入通过）

**已移出本表（本轮已完成并核实通过）**：G4 oracle 预检 ✅、判分证据核验（oracle + qwen 双执行体复算一致 / 零漂移）✅、`check_package_permissions` 批次包 FAIL=0 ✅、镜像自检 ✅、跑分归档 ✅。

| 未验证项 | 现状与原因 | 由谁补 |
|---|---|---|
| **G5 三模型难度验证（2/3 未跑）** | `gpt-5.6-sol`、`claude-opus-4-8` 的 agent 侧端点（base_url / api_key）本机未找到——`.wff-creds/judge.env` 仅含判官凭据；`model_endpoints.local.json` 模型集为 qwen3.8-max / opus-5 / glm-5.3 / kimi-k3，与所需不匹配。qwen 已跑 ✅ | **需用户/甲方提供 agent 侧模型凭据** |
| **难度定档（A1 是否成立）** | 三模型未齐无法计算均值；**且 qwen 实测 1.000000 满分**，`均值<0.70` 要求 `gpt+opus < 1.10`（人均 <0.55），**破档风险极高**。若最终破档，属**必须整改**，须按「补难度」处置（改判据/加难点，非补数据），并按重跑决策表执行 | 凭据到位后跑完 G5；破档则回生产侧整改 |
| `check_cross_model_concentration`（≥25% 口径歧义信号） | 已执行，脚本报 `可用执行体不足（找到 ['qwen3.8-max-0902']）` —— 需 ≥2 个模型 | G5 补齐后重跑 |
| 金标排版观感、参考答案专业正确性人检、trigger 行为学验证 | 甲方规则明示需人检 | 人检 |
| `交付文档.md` 批次内容表的三模型分/均值/难度档 | G4 分数与 qwen 分数已回填；均值与档位待 G5 | G5 后回填 |
| `task.toml` 的 `difficulty` 申报值校正 | 当前申报 A1，与实测档位的一致性**未验证** | G5 定档后核对（149-fix1 必修 #1 同款） |

---

*质检执行：2026-10-09；流程依据 `C:\Users\Administrator\Desktop\weakness-qc\SKILL.md` v1.0 + `references/{gates,evidence-checks,pitfall-cases,report-template}.md`；脚本来源 `harbor-weakness\_reference\weakness-data-construction\scripts`（生产侧，未复制）。*
