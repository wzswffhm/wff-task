# 机器门禁清单与冲突处理

## 一、脚本位置与优先级

| 来源 | 路径 | 用途 |
|---|---|---|
| **生产侧（以此为准）** | `${CODEX_HOME:-~/.codex}/skills/weakness-data-construction/scripts/` | 出题与质检共用，脚本与规范原文同源 |
| 通用质检侧 | `${CODEX_HOME:-~/.codex}/skills/rl01-task-qc/scripts/` | 与生产侧同源；多一个 `qc_check.py` 一键门禁 + 汇总报告 |

**不要在本 skill 里复制脚本**——历史上正是因为存在两份取值不一致的 `check_complexity.py` 才造成误判。
直接调用生产侧脚本；若要做批量一键，用质检侧的 `qc_check.py`。

## 二、必跑清单

```bash
S=${CODEX_HOME:-$HOME/.codex}/skills

python "$S/weakness-data-construction/scripts/validate_task_package.py" <task-dir>
python "$S/weakness-data-construction/scripts/validate_rubrics.py"        <task-dir>
python "$S/weakness-data-construction/scripts/check_complexity.py" --self-test   # 先自检
python "$S/weakness-data-construction/scripts/check_complexity.py"        <task-dir>
python "$S/weakness-data-construction/scripts/check_rubric_style.py"      <task-dir> --strict
python "$S/weakness-data-construction/scripts/check_instruction_anchors.py" <task-dir>
python "$S/weakness-data-construction/scripts/check_cross_model_concentration.py" <task-dir>
python "$S/weakness-data-construction/scripts/check_package_permissions.py" <zip 或目录>
python "$S/weakness-data-construction/scripts/check_batch_quota.py"       <批次目录>
```

| 脚本 | 查什么 | FAIL 意味着 |
|---|---|---|
| `validate_task_package.py` | 字段、取值域、权重分布、`weakness_tag` 编号格式（`^W\d{2}`）、JUDGE_ 变量未泄漏到 `[environment.env]` | 元数据不合规 → 必须整改（通常零重跑） |
| `validate_rubrics.py` | json↔toml 条数/正分池/negate 集合一致、维度名、内容质量占比、likert 双标度、锚点一致性 | 判据不合规 → 必须整改（改判据需重跑判官） |
| `check_complexity.py` | C1–C5 与文件数/产物数是否自洽（见第三节，**此脚本历史上有过取值缺陷**） | 先按第三节排除脚本口径问题，再决定是否算题包缺陷 |
| `check_rubric_style.py --strict` | 提问式判据、模糊量词、表格类定位语、`Subjective` 误标 | 措辞不合规 → 必须整改 |
| `check_instruction_anchors.py` | 判据锚点是否能在题面/材料命中 | 命中缺失 → 逐条人工核（可能只是表述差异） |
| `check_cross_model_concentration.py` | 「三模型一致未满分」判据的权重占比 | ≥25% → 按口径歧义排查（参见案例 2/3） |
| `check_package_permissions.py` | zip 内 0755/LF、残留、层级、golden 双份一致 | 打包缺陷 → 必须整改（零重跑） |
| `check_batch_quota.py` | 批次级配额、14 种 weakness 覆盖、C 档分布 | 单题包通常只出提示，非阻塞 |

## 三、C1–C5 判定口径（易错点，务必按此执行）

### 3.1 分级表原文

| 列 | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| 文件数 | 2 | 5 | 10 | 25 | 50+ |
| Requirement | 3 | 6 | 10 | 15 | 20 |
| **输出产物数** | **1–2** | **2–3** | **3–4** | **4–6** | **4–8** |
| Evidence hop | 1 | 2 | 3 | 4 | 5 |
| 工具种类数 | 1 | 2 | 3 | 4 | 5+ |

**产物数是区间且相邻档重叠**：4 同时属 C3/C4/C5；5–6 同时属 C4/C5；2 同时属 C1/C2。

### 3.2 判定规则

1. 文件数 → 取满足 floor 的**最高**档；
2. 产物数 → 取区间**包含**该数值的**全部**档（并集，可重叠）；
3. 申报档**高于**文件数档：只要产物数支持该档即**通过**（多产物/大项目例外），
   不要求把输入材料补到 25/50 个文件——补材料属**改题**，会作废已跑产物；
4. 申报档**低于**文件数档：低报，必须整改；
5. 多指标（文件数/产物数/Requirement/工具种类）不一致时，**综合看**：
   只有"申报档高于全部指标的支持上限"才算虚标；单项低于申报档只是**提示**，需人工核 evidence-hop。

### 3.3 脚本与规范冲突的处置（**历史真实误判**）

生产侧 `check_complexity.py` 曾把产物区间写窄（`5–6 → 仅 C4`，丢掉 C5），导致
「6 个交付物 + 申报 C5」被误判 FAIL，质检报告据此写成"必须改成 C4"——**这是误判**。

遇到该情形：

1. 先跑 `check_complexity.py --self-test`（v2.4 起支持）。若报 FAIL，说明脚本取值漂移，
   **以分级表为准**；
2. 报告里单列「脚本口径与规范冲突」小节，附**脚本原始输出**与**人工判据**（分级表区间 + 该题实测）；
3. 结论写「待人工核 / 提示」，**不得据此判题包不通过**；
4. 把脚本缺陷记进交付说明，供平台修正。

实测对照（同一份题包、两种取值）：

```
6 个产物 + 申报 C5：  旧脚本(5–6→仅C4) FAIL ｜ 按分级表取并集 PASS
8 个产物 + 申报 C5：  两种取值均 PASS（8 只属 C5）
6 个产物 + 申报 C4：  两种取值均 PASS
```

### 3.4 什么才算真的档位问题

- 申报档高于**全部**指标支持的上限 → 虚标，必须整改；
- 申报档低于**全部**指标支持的下限 → 低报，必须整改；
- 其余（单项不齐）→ 提示，写清各指标的实测值，交甲方或人工裁决。

## 四、门禁 FAIL 的分级

| 情形 | 结论档位 |
|---|---|
| 元数据字段/编号/取值不合规、权重分布不满足、negate 表达错误 | 必须整改（多为零重跑） |
| zip 权限位/LF/残留/golden 不一致 | 必须整改（零重跑） |
| 脚本 FAIL 但属脚本口径与规范冲突 | **提示 / 待人工核**，不得判不通过 |
| 脚本 FAIL 且规范原文确认不合规 | 必须整改 |

## 五、批量质检

用质检侧的 `qc_check.py` 跑批次目录，它会把逐题门禁结论与待人工项汇总成报告：

```bash
python "$S/rl01-task-qc/scripts/qc_check.py" <批次目录> --zip <交付 zip> --out <报告目录>
```

报告默认写到 `<目标>_qc/`；**质检报告落 `outputs/`，不要写进题包目录**。
