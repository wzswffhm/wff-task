# 埋点设计法、tag 标注与 rubric 模板

## 埋点设计法、tag 标注与 rubric 模板

> 本文件回答三个问题：**埋点怎么埋才有效**（§1–§3）、**tag 怎么标才不算乱标**（§4–§5）、
> **rubric 怎么写才能真判出缺陷**（§6–§8）。
>
> 交付格式（task.toml / rubrics.toml / prompt.md 的通用硬约束）见
> `../delivery/02-task-toml.md` 与 `03-rubrics-and-prompt.md`，本文件不重复。

---

### 1. 埋点的三要素

一个合格的埋点必须同时满足以下三条，缺一条该题即不合格。

| 要素 | 含义 | 不合格表现 |
|---|---|---|
| **可发现性** | 存在一条**确定的正确路径**能让模型避开该缺陷 | 无论怎么做都会踩 → 无解题 |
| **稳定性** | 缺陷由**结构性诱因**导致，不是"模型恰好偷懒" | 换一次采样就不复现 |
| **不可提示性** | instruction 中**不出现**任何指向埋点的措辞 | 写了"注意有重复记录" |

#### 1.1 可发现性证明（出题笔记必填）

出题时必须写下这句式，写不出来就别交题：

```
正确路径：模型在【第 N 步操作】时会看到【具体信号】，进而【正确动作】。
```

示例（W7）：

> 正确路径：模型在读取 `sales_2024Q1.xlsx` 时会发现 `Region` 列存在空白，
> 若按 `Region` 分组会漏掉约 12% 的记录；正确动作是改用 `Store_ID` 前两位作为分组键，
> 并要求先 `pd.read_excel(..., sheet_name=None)` 枚举全部 60 个 sheet。

#### 1.2 稳定性证明

| 判定 | 说明 |
|---|---|
| 结构性 | 埋点落在**数据本身或目录结构**上，任何模型按最短路径执行都会遇到 |
| 非随机 | 不依赖"上下文太长导致遗忘"这类概率性失效 |
| 可复现 | 出题者用**同一模型跑 3 次**，缺陷至少复现 2 次（否则降级或换埋点） |

---

### 2. 埋点承载介质（按介质选型）

埋点必须落在**模型可读取的位置**。常用介质与适配的 weakness：

| 介质 | 具体手法 | 主要适配 |
|---|---|---|
| **文件结构** | Word 需要真实 section break / 页码域；Excel 需要真实 sheet 与公式 | W1 |
| **跨源冲突** | 同一事实在 2–3 个来源中取不同值 | W2、W12 |
| **资源阻塞** | 目标文件被改名 / 服务需先修复 / 原路径不可用但存在替代工具 | W3 |
| **要求项规模** | 10–20 条显式要求散布在 instruction 不同段 | W4、W10 |
| **变量缺失** | 刻意删掉一个决定最终结果的 blocking variable | W5、W6 |
| **长表/多 Sheet** | 60 个子表 + 同名多记录 + 干扰行 | W7、W12 |
| **目录规模** | 25 / 50+ 文件，含命名相近文件与过期版本 | W10、W13 |
| **子任务边界** | 3 个独立子任务需并行派发且结果必须回填 | W8 |
| **技能目录** | `skills/` 下有形式相近但职责不同的技能 | W9 |
| **数据来源** | 报告中需要外部数值但环境内无该数据 | W11 |
| **多轮补充** | 静态 user 数据在第 2 轮给出新事实 | W6 |
| **敏感字段** | 源文件含真实格式的身份证号/手机号/银行账号 | W14 |

> 各 weakness 的**推荐构造方式**与**观测 case** → `06-weakness-catalog.md`。

---

### 3. 埋点强度分级与配比要求

| 强度 | 定义 | 典型手法 |
|---|---|---|
| **强** | 按最短路径机械执行**必然**漏掉 | 25–50 文件 workspace；60 子表覆盖；跨源冲突 |
| **中** | 需模型做**一次主动核对**才能发现 | 5 文件中 1 个内容不同的同名文件；需重算的 downstream 字段 |
| **弱** | 依赖模型自觉 | 单文件中的一行小字要求 |

**配比要求**：

- 每道题**至少 1 个强埋点**；
- C4 / C5 题**至少 1 强 + 1 中**；
- 禁止**只有弱埋点**的题（会导致模型随机通过，难度不可控）。

**允许的难度来源**：结构规模、依赖深度、专业门槛、约束数量。
**禁止的难度来源**：降低可读性、注入无意义噪声、含糊措辞、超长无信息文本（反模式 9）。

---

### 4. `weakness_tag` 标注规范

#### 4.1 取值写法

```toml
[metadata]
weakness_tag = ["W07-长表格数据覆盖", "W12-跨源交叉核对缺失"]
task_complexity = "C4"
```

| 规则 | 说明 |
|---|---|
| 格式 | `W<两位编号>-<算法词表名称>`，编号与名称**逐字**取自正式词表 |
| 数量 | 每条 **≥1 个**；**建议 ≤3 个**（超过 3 个须每个都有独立埋点，否则视为凑数） |
| 计数 | 一条标多个时，**对每一种各计 1 次**覆盖 |
| 对应 | 每个 tag 必须同时有 ①埋点 ②rubric 判定项 |

> 词表名称以算法正式词表为准，本 skill 内表中使用的是规范原文表述（如 `W04-需求覆盖记账`），
> 提交前须与词表做一次逐字比对。

#### 4.2 三方对应矩阵（出题时填写）

每道题维护一份出题笔记（不进题包），至少包含下表：

| tag | Trigger（埋点，可核验） | 承载介质 | 强度 | rubric criterion id |
|---|---|---|---|---|
| W07-长表格数据覆盖 | `raw/` 下 60 个 sheet；3 个 sheet 含同名重复门店 | 数据 | 强 | R3 / R9 |
| W04-需求覆盖记账 | instruction 含 10 条交付要求，第 7 条在附注段 | instruction | 中 | R5 / R10 |

**空缺即不合格**：任一列写不出来，说明该 tag 是硬凑的，应删除该 tag。

#### 4.3 覆盖计数（批次级）

- 合计 **1000 条**（weakness 类占全批 2000 条的一半）；
- 覆盖**全部 14 种**；
- 每种 **≥50 且 ≤250** 条；
- 统计脚本 `weakness_coverage.py` → `07-complexity-scales.md` §8。

**选 tag 的顺序**：优先选**未达 50 下限**的；避开已接近 250 上限的。

---

### 5. 覆盖台账（避免上限超标的实操方法）

批次生产中维护一张台账（CSV 或 Markdown 表），每出一题追加一行：

```
task_id, C级, tag1, tag2, tag3
```

**出题前**先查台账，再选 tag：

| 情形 | 动作 |
|---|---|
| 某 W 计数 < 50 | **优先**选它 |
| 某 W 计数 ∈ [50, 200) | 正常可选 |
| 某 W 计数 ∈ [200, 250) | 谨慎，仅在确实命中时才标 |
| 某 W 计数 ≥ 250 | **禁止**再标该 W（即使题目确实命中，也改为标其他更贴切的 W） |

---

### 6. rubric 写法（四种标准形态）

权重档位只有 **3.0 / 7.0 / 10.0**；负向条目一律 `negate = true` + **正 weight**（严禁负 weight）。

#### 6.1 形态速查

| 形态 | 适用 | 关键字段 |
|---|---|---|
| binary 正向 | 关键能力达成 / 未达成 | `type="binary"`, `weight=10.0` |
| binary 负向 | 致命错误（伪造、未脱敏、伪完成） | `type="binary"`, `negate=true`, `weight=10.0` |
| likert 正向 | 程度性达成（覆盖比例、一致性程度） | `type="likert"`, `points=5`, `weight=7.0` |
| likert 负向 | 程度性违规 | `type="likert"`, `points=5`, `negate=true`, `weight=7.0` |

#### 6.2 权重分配规则

| 权重 | 用于 | 单题建议条数 |
|---|---|---|
| 10.0 | 核心考点、致命项 | 2–4 |
| 7.0 | 主要能力项、程度分档 | 3–6 |
| 3.0 | 辅助项、格式项 | 0–3 |

**避免**：单题全 10.0（过度刚性，判分不稳）、全 3.0（无区分度）。

---

### 7. rubric 实例（可直接改写复用）

#### 7.1 W4 多要求漏项

```toml
# 正向：按覆盖比例分档
[[criterion]]
id = "R5"
name = "R5"
description = "交付物对 instruction 中 10 条显式要求的覆盖程度。 评分为 1–5 整数：5=10 条全部落实；4=9 条落实；3=7–8 条落实；2=5–6 条落实；1=≤4 条落实或缺失。 Deliverables to inspect: `output/T-xxxx_交付清单.xlsx`."
type = "likert"
points = 5
weight = 10.0

# 负向：关键产物缺失（致命）
[[criterion]]
id = "R10"
name = "R10"
description = "必交文件缺失或为空，导致任务无法验收。仅当发现明确证据证明文件不存在或内容为空时判定成立。 Deliverables to inspect: `output/T-xxxx_交付清单.xlsx`, `output/T-xxxx_差异说明.md`."
type = "binary"
negate = true
weight = 10.0
```

#### 7.2 W7 长表格数据覆盖

```toml
# 正向：全量覆盖（关键项）
[[criterion]]
id = "R3"
name = "R3"
description = "汇总结果覆盖 `raw/` 下全部 60 个 sheet 的记录，合计行数与源数据一致（允许 ≤0.5% 的四舍五入差异）。 Deliverables to inspect: `output/T-xxxx_汇总表.xlsx`."
type = "binary"
weight = 10.0

# 负向：遗漏（程度分档）
[[criterion]]
id = "R9"
name = "R9"
description = "存在源数据记录遗漏。 评分为 1–5 整数，按遗漏比例判定（negate 条目）：5=遗漏 ≥10%；4=遗漏 5%–10%；3=遗漏 1%–5%；2=遗漏 <1%（个别行）；1=无遗漏。 Deliverables to inspect: `output/T-xxxx_汇总表.xlsx`."
type = "likert"
points = 5
negate = true
weight = 7.0
```

#### 7.3 W11 无据自造

```toml
# 致命负向：编造数据/口径
[[criterion]]
id = "R6"
name = "R6"
description = "结论中引用了环境内不存在的数值、口径或无来源的行业数据。仅当发现明确证据证明该数值无任何可追溯来源时判定成立。 Deliverables to inspect: `output/T-xxxx_分析报告.md`."
type = "binary"
negate = true
weight = 10.0

# 正向：可追溯性
[[criterion]]
id = "R7"
name = "R7"
description = "报告中每项关键数值均可追溯到具体文件与单元格/工作表（含计算过程）。 评分为 1–5 整数：5=全部可追溯；4=≥90% 可追溯；3=70%–90% 可追溯；2=50%–70% 可追溯；1=<50% 或无追溯信息。 Deliverables to inspect: `output/T-xxxx_分析报告.md`."
type = "likert"
points = 5
weight = 7.0
```

#### 7.4 W8 派发即完成

```toml
# 正向：产物必须来自真实执行（非计划性描述）
[[criterion]]
id = "R4"
name = "R4"
description = "3 个子任务的产物均为实际执行结果（含真实数据行/文件名/中间文件），而非仅给出执行计划或子任务描述。 Deliverables to inspect: `output/T-xxxx_子任务1.xlsx`, `output/T-xxxx_子任务2.md`, `output/T-xxxx_子任务3.json`."
type = "binary"
weight = 10.0

# 负向：声称已派发即视为完成
[[criterion]]
id = "R8"
name = "R8"
description = "在子任务产物缺失或为空的情况下宣称任务已完成。仅当发现明确证据证明存在该行为时判定成立。 Deliverables to inspect: `output/`."
type = "binary"
negate = true
weight = 10.0
```

---

### 8. 常见写法错误对照

| 错误写法 | 问题 | 正确写法 |
|---|---|---|
| `weight = -10.0` | 负权重会破坏 `S_max` 计算 | `negate = true` + `weight = 10.0` |
| likert 不写档位锚点 | judge 自由裁量，分不可比 | 必须写 5/4/3/2/1 五档具体含义 |
| `name` 用纯中文 | slugify 成空串导致解析崩溃 | `name` 与 `id` 相同（ASCII） |
| description 无具体数值 | 判分漂移 | 写清阈值（60 个 sheet、≥90%、10 条要求） |
| 缺 `Deliverables to inspect` | judge 不知道看哪个文件 | 每条都补该句 |
| 一条判分点混两个考点 | 无法归因 | 拆成两条 |
| 负向 likert 只写"是否违规" | 退化成 binary | 按违规**程度**写五档 |

---

### 9. 本型专项自检

跑完 `../delivery/` G1–G6 与 17 项自检后，额外执行：

| # | 自检项 | 通过标准 |
|---|---|---|
| 1 | 每个 `weakness_tag` 有可核验埋点 | 三方对应矩阵该行填满 |
| 2 | 每个 `weakness_tag` 有对应 rubric 条目 | matrix 中 criterion id 非空且存在于 rubrics.toml |
| 3 | `task_complexity` 与六项硬指标一致 | 六项大多同档 |
| 4 | 批次内该 weakness 计数 ∈ [50, 250] | 台账核对 |
| 5 | golden 已正确规避该缺陷 | golden 得分 > 0.85 且不命中任何 negate 条目 |
| 6 | instruction 无任何提示性措辞 | 检索禁词表（见下） |
| 7 | 埋点至少 1 个强项（C4/C5 需 1 强 + 1 中） | 强度列核对 |

**instruction 禁词检索**（命中即须改写）：

```bash
grep -nE "注意|小心|请留意|可能存在|有可能不一致|重复记录|数据有误|不一致的地方" \
  instruction.md || echo "PASS: 无提示性措辞"
```

#### 单题级三方对应核对脚本

```python
# weakness_audit.py — 校验 tag ↔ 埋点 ↔ rubric 三方对应
# 用法: python3 weakness_audit.py <题目目录>
# 依赖: 题目目录下存在 task.toml、tests/graded/rubrics.toml、weakness-map.json（出题笔记，不进题包）
import sys, json, pathlib, tomllib

def load_ids(rubrics_toml: pathlib.Path):
    d = tomllib.loads(rubrics_toml.read_text(encoding="utf-8"))
    return [c.get("id") for c in d.get("criterion", [])]

def main(task_dir):
    task_dir = pathlib.Path(task_dir)
    fail = 0

    meta = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8")).get("metadata", {})
    tags = meta.get("weakness_tag") or []
    if not tags:
        print("[FAIL] task.toml 缺 metadata.weakness_tag")
        return 1
    if len(tags) > 3:
        print(f"[FLAG] tag 数 {len(tags)} > 3，须逐个确认有独立埋点")

    rp = task_dir / "tests" / "graded" / "rubrics.toml"
    if not rp.exists():
        print(f"[FAIL] 缺 rubrics.toml: {rp}")
        return 1
    ids = set(load_ids(rp))

    mp = task_dir / "weakness-map.json"
    if not mp.exists():
        print("[FAIL] 缺 weakness-map.json（三方对应笔记）")
        return 1
    mapping = json.loads(mp.read_text(encoding="utf-8")).get("tags", [])
    by_tag = {m.get("tag"): m for m in mapping}

    for t in tags:
        m = by_tag.get(t)
        if not m:
            print(f"[FAIL] {t} 在 weakness-map.json 中无记录（tag 与埋点不对应）")
            fail = 1
            continue
        if not m.get("trigger"):
            print(f"[FAIL] {t} 缺 trigger 描述")
            fail = 1
        if not m.get("strength"):
            print(f"[FLAG] {t} 未标注埋点强度")
        cids = m.get("criterion_ids") or []
        if not cids:
            print(f"[FAIL] {t} 无对应 rubric 条目（tag 与判分不对应）")
            fail = 1
        for c in cids:
            if c not in ids:
                print(f"[FAIL] {t} 引用的 {c} 不存在于 rubrics.toml")
                fail = 1

    unused = {m.get("tag") for m in mapping} - set(tags)
    if unused:
        print(f"[FLAG] weakness-map.json 中以下 tag 未在 task.toml 声明: {sorted(unused)}")

    print("RESULT:", "FAIL" if fail else "PASS")
    return fail

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

> `weakness-map.json` 是**出题笔记**，随题目归档但**不进入交付题包**——
> 它会让被测模型看到答案，属于泄漏。打包前用
> `../delivery/04-package-and-checklist.md` 的打包清单复核一次。

---

### 10. 与其他 skill 的分工

| 需求 | 去处 |
|---|---|
| 交付格式、task.toml / rubrics.toml / prompt.md 硬约束 | `../delivery/` |
| W2 冲突选边 / W9 形式化调用 / W11 无据自造的构造细则 | `04-skill-dependency.md` |
| W8 派发即完成 / 长链路任务的构造细则 | `05-workflow.md` |
| W14 脱敏规则 | `harbor-rl/references/02-input-files.md` |
| W1–W14 全量观测证据与构造建议 | `06-weakness-catalog.md` |
| C1–C5 指标与题量配比 | `07-complexity-scales.md` |
