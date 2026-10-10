# -*- coding: utf-8 -*-
"""152 v4 判据重构：按 qwen 八类弱点植入压分要求，双文件同步（toml + json）。

设计原则（公平性）：
  - 答案锚点（数值/算式/网格）只写进判据（判官看），不进题面；
  - 判据要求的"格式/口径/呈现方式"必须同步写进题面（否则模型无法知晓，不公允）；
  - 模式对应：6=钦定推导等式、2=显式陈述、1=分列禁合并、7=精确计数、
              5=全矩阵小容差、4=唯一结论选边、3=钦定口径。
"""
import json
import pathlib
import re
import shutil
import sys
from datetime import datetime

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
TOML = TASK / "tests" / "rubrics.toml"
JSONF = TASK / "rubrics.json"
BK = TASK.parent / "_backup" / "FIN3-WKN-152-rubrics-v3-20261010"

DRY = "--dry-run" in sys.argv

# ─────────────────────────────────────────────────────────────
# 一、改写现有判据（只改 description，weight 全部保持不变）
# ─────────────────────────────────────────────────────────────
REWRITE = {
"R03": """委员会支持价格区间正确：Low / Mid / High 三档每股价值分别约为 **$31.27 / $34.26 / $37.25**（各允许 ±$0.10），支持区间约为 **$31.27 – $37.25**，midpoint 约为 **$34.26**（允许 ±$0.10）。且估值链推导必须在 `FIN3-WKN-152_ipo_model.xlsx` 的 `Valuation` 表中**逐行分列写出下列四步算式（每步须带列报值，不得只给最终结果、不得把多步合并成一句）**：`EV = 倍数 × 2024E Revenue 980.915`、`pre-money Equity = EV + 401.176 + 811.946`、`每股 = Equity ÷ 143.716563`、`折后每股 = 每股 × (1 − 12.5%)`。任一档位偏差超过 ±$0.10、或未加回有价证券、或未应用执行折扣、或上述四步算式有任一步缺失或未写出列报值，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_pricing_memo.md`, `/app/output/FIN3-WKN-152_valuation_matrix.csv`.""",

"R04": """拟议价定位正确：明确说明拟议价格 **$34** 位于委员会支持区间 **$31.27–$37.25** 之内，距 midpoint **$34.26** 约 **$0.26**（允许 ±$0.05），且未超过 $0.50/share 的护栏。该定位必须**同时给出三行分列的判算**：①区间包含关系（34 ≥ 31.27 且 34 ≤ 37.25）；②距离算式 `34.26 − 34.00 = 0.26`；③护栏比较 `0.26 ≤ 0.50`。只给结论而未给出上述任一行判算、或把三者合并成一句话、或把拟议价判为超出区间，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_pricing_memo.md`, `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",

"R05": """承销口径盈利质量计算正确：按控制口径撤销 SBC 加回后，承销口径 Underwriting EBITDA 约为 **-118.361mm**（允许 ±0.5mm）。该结果必须在 `FIN3-WKN-152_qoe_bridge.csv` 与 `ipo_model.xlsx` 的 `QoE` 表中**写出完整算式 `-118.361 = -69.275 - 49.086`**（三个列报值齐全，不得只给 -118.361 一个结果数），并据此**明确写出「调整后 EBITDA 仍为负」这一判断**。若直接沿用 -69.275mm、或采用加回后的正数、或未写出上述三项列报值的算式、或未明确写出正负判断结论，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_qoe_bridge.csv`.""",

"R06": """定价处置建议正确：明确给出 **Proceed at $34** 的处置结论（按拟议 $34 继续推进）。该结论必须**分列写出两项负 QoE 前提**（缺任一项即不满足）：①承销口径 EBITDA 为负（-118.361mm）；②2023 年 FCF 为负（-84.838mm）；并明确写出不得仅因管理层 Adjusted EBITDA 改善而上调价格。若给出 Reprice 或 Defer、或未给出明确处置结论、或两项负 QoE 前提只写出其中一项、或把两项合并为一句含糊表述，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_pricing_memo.md`, `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",

"R07": """2024E Revenue 计算正确：按 2023A Revenue 804.029mm × (1 + 22%) 计算，约为 **980.915mm**（允许 ±1mm），且须**写出完整算式 `980.915 = 804.029 × (1 + 22%)`**；并说明 22% 为控制口径规定的内部预测假设而非 SEC 公开事实，同时给出其竞争值（行业基准 18%）被排除的理由。若沿用 2023 年收入作估值分母、或结果偏差超过 ±1mm、或未写出上述算式、或把 22% 标注为 SEC 公开数据、或未给出 18% 被排除的理由，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_source_trace.csv`.""",

"R08": """净现金桥完整：pre-money equity 的净现金桥须**分列两行**给出 2023 年末现金及现金等价物 **401.176mm** 与有价证券 **811.946mm**，再给出合计 **1213.122mm**（允许 ±0.5mm），并**写出算式 `1,213.122 = 401.176 + 811.946`**。把两项合并为一行「净现金 1213.122」、仅计入现金、遗漏有价证券、或把有价证券以其它名目重复计入，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_pricing_memo.md`.""",

"R09": """执行折扣应用正确：对 peer-implied 的**每股价值**统一应用控制口径规定的 **12.5%** IPO execution discount，并**写出算式 `折后每股 = 每股 × 0.875`** 同时标明作用对象为「每股价值」而非收入或企业价值。未应用折扣、把折扣乘在收入或企业价值上、使用被取代的旧版折扣比例（10%）、或未写出上述算式与作用对象，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",

"R11": """募集与费用计算正确：按 $34 计算，公司 Base **gross primary proceeds 约为 519.402mm**（允许 ±0.5mm）。费用扣减必须**分列两行**——①5% 承销费 **25.970mm**、②固定 company expenses **7.000mm**——并写出算式 `486.432 = 519.402 - 25.970 - 7.000`，得到 **net primary proceeds 约为 486.432mm**（允许 ±0.5mm）；承销费计提基数为公司 primary gross proceeds（不含 secondary）。把两项费用合并为一行、把 secondary 计入费用基数、固定费用重复计提、或结果偏差超过容差，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",

"R13": """明细底表与年度数勾稽处置正确：识别出 `financials/monthly_revenue_2022_2023.csv` 中的两处未标注记录异常——FY2022 的 2022-08 月被重复导出（两行数值相同）、FY2023 的 2023-12 月同时存在 SEC-01(68.979) 与 INT-01(66.500) 两个不同来源值——并说明处置方式（重复行去重、同月多值按来源优先级择值），使处理后月度明细加总与年度数 **804.029mm / 666.701mm** 一致。两处异常必须在 `source_trace.csv` 中**各占一行**给出：文件名、月份、两个冲突值、来源优先级条款（Source_Index 的 Priority 号）、处置结果；缺任一行或任一要素即不满足。未识别任一异常、或直接对全部明细行求和导致与年度数不符，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_source_trace.csv`.""",

"R14": """旧底稿错误识别与修正充分：逐条复核 `input_files` 的 `legacy/` 目录，在 `Error_Audit` 模块中记录问题类别、原有处理、正确处理与影响，**合计不少于 8 类，且必须一行一类逐行列出（表格式），不得把同类错误归并成一行、不得用概括性叙述替代逐条记录**；须覆盖以下方向中的至少 6 类——SBC 处理、以 2023 年收入作估值分母、遗漏执行折扣、遗漏有价证券、primary/secondary 混淆、greenshoe 预先并入 Base、承销费计提基数错误、secondary 增加总股数、secondary 所得计入公司现金、稀释分子分母口径不一致、依据 peer high case 上调价格。识别类别少于 8 类、出现归并、或只罗列未给出正确处理，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",

"R17": """股本桥与稀释正确：Base post-money 股数为 **158.993090m**（允许 ±0.001mm），full greenshoe exercise 后为 **162.293090m**（允许 ±0.001mm），secondary 不计入总股数；并**写出算式 `158.993090 = 143.716563 + 15.276527`** 与 `162.293090 = 158.993090 + 3.300000`。把 secondary 加入总股数、未写出上述两条算式、或 post-money 股数偏差超过容差，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",

"R18": """敏感性矩阵正确：`FIN3-WKN-152_valuation_matrix.csv` 给出 **2024E 增长率 × EV/Revenue 倍数** 的 5×5 每股价值矩阵，**增长率轴必须恰为 18% / 20% / 22% / 24% / 26%，倍数轴必须恰为 4.0x / 4.3x / 4.5x / 4.8x / 5.0x**（缺任一档、或自选其它网格点即使仍是 5×5 也不满足），并标注 base case（22% × 4.5x）。矩阵须与该 base case 的净现金桥、股数与 12.5% 执行折扣口径一致；base case 单元格数值约为 **$34.26**（允许 ±$0.10）；**25 个单元格须全部有值，不得留空或以区间代替单点值**。维度不足、网格点不符、有空格、或 base case 数值不符，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_valuation_matrix.csv`, `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",

"R27": """peer 倍数区间取值正确：主估值采用控制口径指定的 committee peer set 区间 **4.0x–5.0x**（中点 4.5x）。`source_trace.csv` 中须**分别给出两条竞争值及其排除理由**：①`comps/underwriter_B_comps_20240318.csv` 的 4.2x–5.1x（承销商自编，仅作交叉验证）；②被取代的 v2 区间 3.5x–5.5x（条款已作废）。缺任一条竞争值记录或其排除理由、或采用 4.2x–5.1x 作为定价区间端点、或使用历史倍数中位数作为区间，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_valuation_matrix.csv`, `/app/output/FIN3-WKN-152_source_trace.csv`.""",

"R30": """月度明细去重核验：`financials/monthly_revenue_2022_2023.csv` 中 FY2022 的 2022-08 记录被重复导出（两行数值完全相同且**无任何标注**）。须发现该重复，将其去重，使 FY2022 月度明细加总勾稽到 SEC 摘录的年度数 **666.701**，并**写出算式 `666.701 = 723.801 − 57.100`**（重复行金额）。未发现重复、或加总仍为 723.801、或未写出上述算式、或用任何方式使 FY2022 勾稽失败，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_reproduce.py`, `/app/output/FIN3-WKN-152_source_trace.csv`.""",

"R31": """同月多值按来源优先级择值：`financials/monthly_revenue_2022_2023.csv` 中 FY2023 的 2023-12 同时存在两个**无标注**的不同数值（SEC-01 的 68.979 与 INT-01 的 66.500）。须按 `sec_filings/Source_Index.csv` 的来源优先级（SEC-01 Priority 1 > INT-01 Priority 9）取 SEC-01 值，使 FY2023 加总勾稽到 **804.029**，并**写出算式 `804.029 = 801.550 + 2.479`**（优先级修正额）及 Priority 1 / Priority 9 的条款引用。未识别该冲突、或取用 INT-01 的 66.500（加总 801.550）、或未写出算式与 Priority 引用，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_reproduce.py`, `/app/output/FIN3-WKN-152_source_trace.csv`.""",

"R32": """分部收入量级错位核验：`financials/revenue_by_segment_2022_2023.csv` 中 FY2023 的 Other 分部被写成 152.470（量级错位，应为 15.247），导致分部加总 941.252 ≠ SEC-01 年度收入 804.029。须发现该量级错位，按年度数与 Advertising 分部差额修正 Other 分部为 **15.247**，使分部加总勾稽到 804.029，且**写出算式 `941.252 − 152.470 + 15.247 = 804.029`**。未发现、直接采信 152.470、未写出该算式、或加总不平，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_reproduce.py`.""",

"R33": """数据核验段落完备：备忘录含「数据核验」段落，**逐条（一行一条）分列**列出核验中发现的**全部**明细异常，每条给出（文件、行或月份、现象、判定依据、处置结果）五个要素，且至少覆盖以下四处——①2022-08 重复导出行去重；②2023-12 两个不同来源值按优先级择值；③FY2023 分部 Other 量级错位修正；④`financials/sbc_detail_2022_2023.csv` 的 TOTAL 行 49.680 与明细加总 49.086 不一致（以明细为准）。四条必须**分别成行**（把四处合并成一段叙述、或覆盖少于四处、或只列现象不给判定依据与处置、或缺少任一五要素），即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_pricing_memo.md`, `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",
}

# ─────────────────────────────────────────────────────────────
# 二、新增判据（qwen 弱点：模式7 精确计数 / 模式8 结构化增量 / 模式2 显式陈述）
# ─────────────────────────────────────────────────────────────
NEW = [
{"id": "R34", "name": "输入材料清点与覆盖核验", "weight": 7.0, "type": "binary",
 "dimension": "内容质量-事实忠实性", "criterion_type": "correctness", "criterion_necessity": "重要",
 "description": """输入材料清点正确：交付物中明确给出 `/app/input_files/` 的**文件总数 60** 与**来源目录数 7**，并**按目录分列七个目录的文件数**（`committee/` 8、`sec_filings/` 17、`financials/` 14、`comps/` 4、`research/` 5、`internal/` 6、`legacy/` 4），七行合计等于 60。总数或目录数错误、缺任一目录的分项计数、分项合计与总数不符（差 1 即不满足）、或只给总数未分列目录，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`, `/app/output/FIN3-WKN-152_pricing_memo.md`.""",
 "levels": None},

{"id": "R35", "name": "勾稽明细工作表（结构化增量交付）", "weight": 7.0, "type": "binary",
 "dimension": "内容质量-分析与论证质量", "criterion_type": "correctness", "criterion_necessity": "重要",
 "description": """交付结构化勾稽明细：`FIN3-WKN-152_ipo_model.xlsx` 中须含独立工作表 **`Tieout_Detail`**（名称可微调但须能辨识为「勾稽明细」），**逐行列出**每一项勾稽：序列名称、期间、明细加总值、目标年度数、差额、异常类型、处置结果、依据条款；至少覆盖月度收入 FY2022/FY2023、分部收入 FY2022/FY2023、地区收入 FY2023、SBC 明细合计、cap table 合计共 **7 行**，且 `差额 = 明细加总 − 目标年度数` 各行均须有值。缺该工作表、行数少于 7、以正文叙述替代表格、或任一行差额缺失，即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_ipo_model.xlsx`.""",
 "levels": None},

{"id": "R36", "name": "方法论理由显式陈述", "weight": 7.0, "type": "binary",
 "dimension": "内容质量-分析与论证质量", "criterion_type": "correctness", "criterion_necessity": "重要",
 "description": """方法论理由已显式写出：交付物（备忘录或 `source_trace.csv`）中须**明确写出下列四项理由**（隐含可推、或仅给数值结论而不写理由，均不满足）：①为何以委员会 peer 区间中点 4.5x 而非算术/历史中位数作 Mid 档；②为何排除 `internal/management_flash_20240319.csv` 的未复核 flash 数据（来源优先级 CP-02 / Priority 9）；③为何采用 Committee_Policy **v3** 而非 v2（条款作废）；④为何承销费只对公司 primary gross 计提而不含 secondary。四项须**分列写出**（合并成一段泛述即不满足），缺任一项即不满足。 Deliverables to inspect: `/app/output/FIN3-WKN-152_pricing_memo.md`, `/app/output/FIN3-WKN-152_source_trace.csv`.""",
 "levels": None},
]

# ─────────────────────────────────────────────────────────────
print("=" * 100)
print("0) 备份与前置校验")
print("=" * 100)
raw_toml = TOML.read_text(encoding="utf-8")
j = json.loads(JSONF.read_text(encoding="utf-8"))
old_items = {i["id"]: i for i in j["items"]}
t = tomllib.loads(raw_toml)
old_crit = {c["id"]: c for c in t["criterion"]}
print(f"  toml 判据 {len(old_crit)} 条 / json items {len(old_items)} 条")
assert set(old_crit) == set(old_items), "两文件 ID 不一致"
print(f"  REWRITE 覆盖 {len(REWRITE)} 条，全部存在于现有判据: {set(REWRITE) <= set(old_crit)}")
print(f"  NEW 新增 {len(NEW)} 条，ID 无冲突: {not (set(n['id'] for n in NEW) & set(old_crit))}")

if DRY:
    print("\n--dry-run：列出将发生的变更")
    for cid, nd in REWRITE.items():
        od = old_crit[cid]["description"]
        print(f"  改写 {cid}: {len(od)} -> {len(nd)} 字符")
    pos = [c for c in t["criterion"] if not c.get("negate")]
    s_old = sum(float(c["weight"]) for c in pos)
    s_new = s_old + sum(float(n["weight"]) for n in NEW)
    print(f"  新增 {len(NEW)} 条 w=7.0 × {len(NEW)} -> S_max {s_old} -> {s_new}")
    print(f"  判据总数 {len(old_crit)} -> {len(old_crit)+len(NEW)}")
    sys.exit(0)

if not BK.exists():
    BK.mkdir(parents=True)
    shutil.copy2(TOML, BK / "rubrics.toml")
    shutil.copy2(JSONF, BK / "rubrics.json")
    print(f"  [备份] {BK}")
else:
    print(f"  [备份已存在] {BK}")

print()
print("=" * 100)
print("1) 写 tests/rubrics.toml")
print("=" * 100)
out = raw_toml
for cid, nd in REWRITE.items():
    od = old_crit[cid]["description"]
    if od not in out:
        print(f"  [!!] {cid} 原描述未在 toml 原文中找到，跳过")
        continue
    out = out.replace(od, nd, 1)
    print(f"  [OK] 改写 {cid} ({len(od)} -> {len(nd)} 字)")

# 追加新判据（在 criterion 数组末尾）
new_toml_blocks = []
for n in NEW:
    desc = n["description"].replace('"', '\\"')
    name = n["name"].replace('"', '\\"')
    new_toml_blocks.append(
        f'[[criterion]]\nid = "{n["id"]}"\nname = "{name}"\n'
        f'"{"" if False else ""}type = "{n["type"]}"\nweight = {n["weight"]}\n'
        f'description = """{n["description"]}"""\n'
    )
# 更稳妥：在 scoring 段之前插入
m = re.search(r"\n\[\[criterion\]\]", out)
if not m:
    print("  [!!] 未找到 criterion 数组锚点")
    sys.exit(1)
# 找到 criterion 段结束：第一个 criterion 项之后、名字不是 criterion 的顶层段
heads = [(mm.start(), mm.group(2)) for mm in
         re.finditer(r"^\[(\[?)([A-Za-z_]+)\1\]", out, re.M)]
first_crit = next((s for s, n in heads if n == "criterion"), None)
seg_end = len(out)
if first_crit is not None:
    for s, n in heads:
        if s > first_crit and n != "criterion":
            seg_end = s
            break
print(f"  段头: {[(n, s) for s, n in heads]}  -> 插入位置 {seg_end}")
insert = ""
for n in NEW:
    insert += (f'\n[[criterion]]\nid = "{n["id"]}"\n'
               f'name = "{n["name"]}"\n'
               f'type = "{n["type"]}"\n'
               f'weight = {n["weight"]}\n'
               f'description = """\n{n["description"]}\n"""\n')
out = out[:seg_end] + insert + out[seg_end:]
TOML.write_text(out, encoding="utf-8", newline="\n")
print(f"  [写出] {TOML}  {TOML.stat().st_size:,} B")

print()
print("=" * 100)
print("2) 校验 toml 可解析 + 判据数")
print("=" * 100)
t2 = tomllib.loads(TOML.read_text(encoding="utf-8"))
crit2 = t2["criterion"]
print(f"  判据 {len(crit2)} 条")
ids2 = [c["id"] for c in crit2]
assert len(ids2) == len(set(ids2)), "ID 重复"
print(f"  ID 唯一 OK；含新判据: {[i for i in ids2 if i in ('R34','R35','R36')]}")
for cid in REWRITE:
    c = next(x for x in crit2 if x["id"] == cid)
    assert c["description"] == REWRITE(cid) if False else (c["description"] == REWRITE[cid]), f"{cid} 未生效"
print(f"  REWRITE 全部生效 OK")
s2 = sum(float(c["weight"]) for c in crit2 if not c.get("negate"))
neg2 = [c["id"] for c in crit2 if c.get("negate")]
print(f"  S_max = {s2}  负分 {neg2}")

print()
print("=" * 100)
print("3) 同步 rubrics.json")
print("=" * 100)
for cid, nd in REWRITE.items():
    old_items[cid]["description"] = nd
# 新增
for n in NEW:
    old_items[n["id"]] = {
        "id": n["id"], "description": n["description"], "dimension": n["dimension"],
        "criterion_type": n["criterion_type"], "criterion_necessity": n["criterion_necessity"],
        "type": n["type"], "weight": n["weight"],
    }
j["items"] = list(old_items.values())
md = j["metadata"]
md["scoring"]["s_max"] = s2
md["criteria_count"] = len(j["items"])
# CI 保持 R03-R06
md["critically_important_ids"] = [i for i in md.get("critically_important_ids", []) if i in old_items]
# 重算内容质量正分占比（粗算：正分权重 / 总正分权重）
pos_w = sum(i["weight"] for i in j["items"] if i["weight"] > 0)
cq = sum(i["weight"] for i in j["items"] if i["weight"] > 0 and i.get("dimension", "").startswith("内容质量"))
j["_distribution_check"]["content_quality_positive_share"] = round(cq / pos_w, 3)
j["_distribution_check"]["critically_important_ge_2"] = len(md["critically_important_ids"]) >= 2
JSONF.write_text(json.dumps(j, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"  [写出] {JSONF}  {JSONF.stat().st_size:,} B")
print(f"  items {len(j['items'])} 条  s_max {md['scoring']['s_max']}  criteria_count {md['criteria_count']}")
print(f"  内容质量正分占比 {j['_distribution_check']['content_quality_positive_share']}")

print()
print("=" * 100)
print("4) 双文件一致性")
print("=" * 100)
jt = {c["id"]: c for c in tomllib.loads(TOML.read_text(encoding="utf-8"))["criterion"]}
jj = {i["id"]: i for i in j["items"]}
print(f"  ID 集合一致: {set(jt) == set(jj)}  (toml {len(jt)} / json {len(jj)})")
bad = [k for k in jt if jt[k]["description"] != jj[k]["description"]]
print(f"  description 一致: {not bad}  {'不一致: '+str(bad) if bad else ''}")
badw = [k for k in jt if float(jt[k]["weight"]) != float(jj[k]["weight"])]
print(f"  weight 一致: {not badw}  {'不一致: '+str(badw) if badw else ''}")
print()
print(">>> 判据重构完成")
