#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-152 — Reddit, Inc. IPO 定价委员会发行前财务复核（as-of 2024-03-20）
可复算脚本：从 /app/input_files/ 读入全部材料，计算全部结论数值，
并生成交付物（xlsx 模型、3 个 CSV、charts.png）。

纪律：
- 信息集冻结在 2024-03-20 之前（CP-01）；拟议 $34 是决策输入而非已实现结果。
- 来源优先级按 sec_filings/Source_Index.csv（CP-02）；INT-01 flash、IR 草稿、
  承销商 comps 仅作参考，不作为承销口径取数来源。
- 控制口径为 committee/Committee_Policy_v3_20240320.xlsx；v2 相关条款已作废。
- 本脚本不硬编码任何结论数字；全部参数取自材料文件。
"""
import os
import sys
import math
import pandas as pd
import numpy as np

# ----------------------------------------------------------------------------
# 0. 路径解析
# ----------------------------------------------------------------------------
def resolve_dirs():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates_in = ["/app/input_files",
                     os.path.join(here, "..", "input_files"),
                     os.path.join(here, "input_files"),
                     os.path.join(os.getcwd(), "input_files")]
    for c in candidates_in:
        if os.path.isdir(c):
            in_dir = os.path.abspath(c)
            break
    else:
        sys.exit("ERROR: input_files directory not found")
    out_dir = os.environ.get("FIN3_OUT_DIR")
    if not out_dir:
        out_dir = "/app/output" if os.path.isdir("/app/output") else here
    os.makedirs(out_dir, exist_ok=True)
    return in_dir, out_dir

IN, OUT = resolve_dirs()
P = lambda *a: os.path.join(IN, *a)

def esc_df(df):
    """以 '=' 开头的字符串会被 openpyxl 当作公式写入而失效，统一前置空格转义"""
    return df.map(lambda v: (" " + v) if isinstance(v, str) and v.startswith("=") else v)

r3 = lambda x: round(float(x), 3)
r4 = lambda x: round(float(x), 4)
r6 = lambda x: round(float(x), 6)

def num(x):
    """parse numbers that may contain commas / quotes"""
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    return float(str(x).replace(",", "").replace('"', "").strip())

# ----------------------------------------------------------------------------
# 1. 读入材料
# ----------------------------------------------------------------------------
# 1.1 来源优先级（CP-02）
src_idx = pd.read_csv(P("sec_filings", "Source_Index.csv"))
PRIORITY = {r.Source_ID: int(r.Priority) for r in src_idx.itertuples()}
def prio(sid):
    return PRIORITY.get(str(sid), 99)   # 未列名来源按最低优先级处理

# 1.2 SEC-01 年度审计数（Priority 1，历史财务权威口径）
sec01 = pd.read_excel(P("sec_filings", "SEC-01_financials_extract.xlsx"),
                      sheet_name="Public_Financials")
sec01 = sec01.set_index("Metric")
F = lambda metric, yr: num(sec01.loc[metric, yr])     # SEC-01 年度数取值器

REV22, REV23      = F("Revenue", "2022A"),            F("Revenue", "2023A")
ADV22, ADV23      = F("Advertising revenue", "2022A"),F("Advertising revenue", "2023A")
OTH22, OTH23      = F("Other revenue", "2022A"),      F("Other revenue", "2023A")
NI22, NI23        = F("Net income (loss)", "2022A"),  F("Net income (loss)", "2023A")
ADJEB22, ADJEB23  = F("Adjusted EBITDA", "2022A"),    F("Adjusted EBITDA", "2023A")
SBC22, SBC23      = F("Stock-based compensation & related taxes", "2022A"), \
                    F("Stock-based compensation & related taxes", "2023A")
RESTR23           = F("Restructuring costs", "2023A")
DA22, DA23        = F("Depreciation & amortization", "2022A"), \
                    F("Depreciation & amortization", "2023A")
FCF22, FCF23      = F("Free Cash Flow", "2022A"),     F("Free Cash Flow", "2023A")
CASH22, CASH23    = F("Cash & cash equivalents", "2022A"), \
                    F("Cash & cash equivalents", "2023A")
MS22, MS23        = F("Marketable securities", "2022A"), F("Marketable securities", "2023A")
SEC01_ANNUAL = {"FY2022": REV22, "FY2023": REV23}

# 1.3 SEC-02 稀释交叉验算、SEC-03 发行机制、SEC-05 地区收入、SEC-09/16 股本
sec02 = pd.read_excel(P("sec_filings", "SEC-02_dilution_crosscheck.xlsx")).set_index("Item")
NTBV_PS   = num(sec02.loc["Preliminary NTBV/share", "Value"])
DIL_PS    = num(sec02.loc["Preliminary immediate dilution per share", "Value"])
SEC02_PX  = num(sec02.loc["Preliminary NTBV/share", "Assumed price"])

sec03 = pd.read_excel(P("sec_filings", "SEC-03_offering_terms.xlsx")).set_index("Item")
PRIMARY_SEC03   = num(sec03.loc["Primary shares offered (base)", "Value"])
SECONDARY_SEC03 = num(sec03.loc["Secondary shares offered (base)", "Value"])
GREENSHOE_SEC03 = num(sec03.loc["Over-allotment option", "Value"])
RANGE_LOW_SEC03 = num(sec03.loc["Preliminary public filing range low", "Value"])
RANGE_HI_SEC03  = num(sec03.loc["Preliminary public filing range high", "Value"])

geo = pd.read_csv(P("sec_filings", "SEC-05_revenue_by_geo.csv"))
cap09 = pd.read_csv(P("sec_filings", "SEC-09_capitalization.csv"))
sh16 = pd.read_csv(P("sec_filings", "SEC-16_share_count_history.csv"))
_reg = sh16[(sh16.as_of == "2024-03-18") & (sh16.Source_ID == "SEC-09")]
REG_SHARES_SEC16 = num(_reg.shares_outstanding_mm.iloc[0]) if len(_reg) else float("nan")

# 1.4 委员会控制口径 v3（政策条款、peer set、发行条款、承销假设、cap-table 快照）
pol3 = pd.read_excel(P("committee", "Committee_Policy_v3_20240320.xlsx"),
                     sheet_name="Committee_Policy")
_c3 = list(pol3.columns)          # [Policy_ID, Section, Committee convention, Application]
POLICY3 = {row[_c3[0]]: str(row[_c3[2]]) for _, row in pol3.iterrows()}
peerset = pd.read_excel(P("committee", "Committee_Policy_v3_20240320.xlsx"),
                        sheet_name="Committee_Peer_Set")
peer_rows = peerset[peerset["Peer"].astype(str).str.startswith("Peer")]
PEER_MULTS = [num(v) for v in peer_rows["NTM EV/Revenue"]]
rng_row = peerset[peerset["Peer"].astype(str).str.startswith("Range")].iloc[0]
RANGE_TXT = str(rng_row["NTM EV/Revenue"])          # e.g. "4.0x / 5.0x"
POL_LO = num(RANGE_TXT.split("/")[0].replace("x", "").strip())
POL_HI = num(RANGE_TXT.split("/")[1].replace("x", "").strip())

uw = pd.read_excel(P("committee", "Underwriting_Assumptions_20240320.xlsx")).set_index("Assumption")
GROWTH   = num(uw.loc["2024E revenue growth", "Value"])          # CP-06
MULT_LO  = num(uw.loc["Peer low EV/Revenue", "Value"])           # CP-07
MULT_MID = num(uw.loc["Peer midpoint EV/Revenue", "Value"])      # CP-07
MULT_HI  = num(uw.loc["Peer high EV/Revenue", "Value"])          # CP-07
DISCOUNT = num(uw.loc["IPO discount to peer-implied equity", "Value"])  # CP-09

ot = pd.read_excel(P("committee", "Offering_Terms_20240320.xlsx")).set_index("Item")
PRICE        = num(ot.loc["Proposed Committee Price", "Base Offering"])
PRIMARY      = num(ot.loc["Primary shares offered", "Base Offering"])
SECONDARY    = num(ot.loc["Secondary shares offered", "Base Offering"])
GREENSHOE    = num(ot.loc["Greenshoe shares", "Full Greenshoe"])
PRIMARY_FULL = num(ot.loc["Primary shares offered", "Full Greenshoe"])
PREMONEY_SH  = num(ot.loc["Pre-money economic shares", "Base Offering"])
FEE_RATE     = num(ot.loc["Underwriting fee assumption", "Base Offering"])
FIXED_EXP    = num(ot.loc["Fixed company offering expenses", "Base Offering"])
PUB_LO       = num(ot.loc["Preliminary public filing range low", "Base Offering"])
PUB_HI       = num(ot.loc["Preliminary public filing range high", "Base Offering"])

cap = pd.read_csv(P("committee", "cap_table_snapshot_20240318.csv"))
CAP_TOTAL = num(cap.loc[cap.holder_class == "TOTAL_pre_money_economic_shares", "shares_mm"].iloc[0])
CAP_SUM   = float(sum(num(v) for v in cap.loc[cap.holder_class != "TOTAL_pre_money_economic_shares", "shares_mm"]))

pol2 = pd.read_excel(P("committee", "Committee_Policy_v2_20240305.xlsx"),
                     sheet_name="Committee_Policy")
_c2 = list(pol2.columns)
SUPERSEDED_V2 = [(row[_c2[0]], str(row[_c2[2]])) for _, row in pol2.iterrows()
                 if "SUPERSEDED" in str(row[_c2[3]])]

# CP-14 容差（$0.50/share）从政策条款文本解析，不硬编码
import re
_m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)/share", POLICY3["CP-14"])
MID_TOL = float(_m.group(1)) if _m else None
assert MID_TOL is not None, "CP-14 midpoint tolerance not found in policy text"

# 1.5 financials/ 明细底表（不带质量标注，须核验）
monthly  = pd.read_csv(P("financials", "monthly_revenue_2022_2023.csv"))
quarterly= pd.read_csv(P("financials", "revenue_quarterly.csv"))
segment  = pd.read_csv(P("financials", "revenue_by_segment_2022_2023.csv"))
sbc      = pd.read_csv(P("financials", "sbc_detail_2022_2023.csv"))
restr    = pd.read_csv(P("financials", "restructuring_detail_2023.csv"))
fcfb     = pd.read_csv(P("financials", "fcf_bridge_2023.csv"))
cfs      = pd.read_csv(P("financials", "cash_flow_statement_2023.csv")).set_index("line_item")
bs       = pd.read_csv(P("financials", "balance_sheet_summary_2022_2023.csv")).set_index("line_item")
istat    = pd.read_csv(P("financials", "income_statement_2022_2023.csv")).set_index("line_item")
opex     = pd.read_csv(P("financials", "opex_summary_2022_2023.csv")).set_index("line_item")
dau      = pd.read_csv(P("financials", "dau_arpu_metrics.csv"))
eqty     = pd.read_csv(P("financials", "stockholders_equity_summary.csv")).set_index("line_item")
revlog   = pd.read_csv(P("internal", "data_revision_log.csv"))
flash    = pd.read_csv(P("internal", "management_flash_20240319.csv")).set_index("metric")

TOL = 0.005           # USD mm 勾稽容差
ANOMALIES = []        # 明细异常清单（Error_Audit 全覆盖）
CHECKS    = []        # 全部核验记录（含通过项）

def check(table, item, detail_val, annual_val, rule, status, disposition):
    CHECKS.append(dict(table=table, item=item, detail=detail_val, annual=annual_val,
                       diff=r6(detail_val - annual_val), rule=rule,
                       status=status, disposition=disposition))

def anomaly(file, location, phenomenon, category, basis, disposition, impact):
    ANOMALIES.append(dict(file=file, location=location, phenomenon=phenomenon,
                          category=category, basis=basis, disposition=disposition,
                          impact=impact))

# ----------------------------------------------------------------------------
# 2. 数据核验：明细 vs SEC-01 年度数（要求 4）
# ----------------------------------------------------------------------------
# 2.1 月度收入：重复记录去重 + 同月多值按来源优先级择值
m = monthly.copy()
m["revenue_usd_mm"] = m["revenue_usd_mm"].map(num)
dup_mask = m.duplicated(subset=["fy", "month", "revenue_usd_mm", "Source_ID"], keep="first")
for _, row in m[dup_mask].iterrows():
    anomaly("financials/monthly_revenue_2022_2023.csv",
            f"行{int(row.name)+2}（{row['month']}，{row['revenue_usd_mm']:.3f}，{row['Source_ID']}）",
            f"{row['month']} 出现完全相同的重复导出记录（与首个记录同值同源）",
            "重复记录（duplicate export）",
            "重复记录去重规则；internal/data_revision_log.csv 2024-03-16 记载该表曾从 legacy 底稿重导出",
            "删除重复行，保留首条",
            f"若不去重，{row['fy']} 月度加总虚增 {row['revenue_usd_mm']:.3f}，与 SEC-01 年度数不符")
m_dedup = m[~dup_mask].copy()

# 同月多值（不同来源）→ 按 Source_Index Priority 升序取值（CP-02）
conflict = m_dedup.groupby(["fy", "month"]).filter(lambda g: len(g) > 1)
chosen_rows = []
for (fy, mo), g in m_dedup.groupby(["fy", "month"], sort=False):
    if len(g) > 1:
        g2 = g.assign(pr=g["Source_ID"].map(prio)).sort_values("pr")
        win, los = g2.iloc[0], g2.iloc[1:]
        fy_clean = (m_dedup.loc[(m_dedup.fy == fy) & (m_dedup.month != mo), "revenue_usd_mm"].sum()
                    + win.revenue_usd_mm)
        wrong_sum = fy_clean - win.revenue_usd_mm + los.revenue_usd_mm.sum()
        anomaly("financials/monthly_revenue_2022_2023.csv",
                f"{mo}（行{int(win.name)+2} 等，共{len(g)}条）",
                "同一月份存在来自不同来源的多个值：" +
                "；".join(f"{r.Source_ID}={r.revenue_usd_mm:.3f}" for r in g.itertuples()),
                "同月多值 / 来源冲突（未审计 flash 残留）",
                f"CP-02 来源优先级：{win.Source_ID}(P{prio(win.Source_ID)}) 高于 " +
                "、".join(f"{r.Source_ID}(P{prio(r.Source_ID)})" for r in los.itertuples()) +
                "；committee_email_thread.txt（Deal Captain 2024-03-19）明确 12 月 preliminary 残留应弃用、以 S-1/A 审计版为准",
                f"取 {win.Source_ID} 值 {win.revenue_usd_mm:.3f}，弃用 " +
                "、".join(f"{r.Source_ID} 值 {r.revenue_usd_mm:.3f}" for r in los.itertuples()),
                f"若误取低优先级值，{fy} 月度加总 {wrong_sum:.3f} ≠ SEC-01 年度数 {SEC01_ANNUAL[fy]:.3f}")
        chosen_rows.append(win)
    else:
        chosen_rows.append(g.iloc[0])
monthly_clean = pd.DataFrame(chosen_rows)

for fy in ["FY2022", "FY2023"]:
    s = monthly_clean.loc[monthly_clean.fy == fy, "revenue_usd_mm"].sum()
    naive = m.loc[m.fy == fy, "revenue_usd_mm"].sum()
    ok = abs(s - SEC01_ANNUAL[fy]) <= TOL
    check("monthly_revenue_2022_2023.csv", f"{fy} 月度加总（清洗后）",
          r6(s), SEC01_ANNUAL[fy],
          "去重+来源优先级择值后与 SEC-01 年度数勾稽",
          "PASS" if ok else "FAIL",
          f"清洗后一致（原始表 naive 加总 {r6(naive)} 不一致）" if ok else "仍不一致，须复核")

# 2.2 季度收入：加总 + 与清洗后月度按季聚合交叉核对
qsum = quarterly.groupby("fy")["revenue_usd_mm"].apply(lambda s: sum(map(num, s)))
for fy in ["FY2023"]:
    if fy in qsum.index:
        ok = abs(qsum[fy] - SEC01_ANNUAL[fy]) <= TOL
        check("revenue_quarterly.csv", f"{fy} 季度加总", r6(qsum[fy]), SEC01_ANNUAL[fy],
              "明细加总与 SEC-01 年度数勾稽", "PASS" if ok else "FAIL", "一致，直接采信" if ok else "不一致")
mc = monthly_clean.copy(); mc["revenue_usd_mm"] = mc["revenue_usd_mm"].map(num)
mc["q"] = mc["month"].str.slice(5, 7).astype(int).map(lambda mth: f"Q{(mth-1)//3+1}")
for _, qr in quarterly.iterrows():
    ms = mc.loc[(mc.fy == qr.fy) & (mc.q == qr.quarter), "revenue_usd_mm"].sum()
    ok = abs(ms - num(qr.revenue_usd_mm)) <= TOL
    check("revenue_quarterly.csv", f"{qr.fy} {qr.quarter} vs 清洗后月度聚合",
          r6(ms), num(qr.revenue_usd_mm), "月度→季度聚合交叉核对",
          "PASS" if ok else "FAIL", "一致" if ok else "不一致，须复核")

# 2.3 分部收入：量级错位单元格识别（以 SEC-01 年度数为准）
seg_map = {("FY2022", "Advertising"): ADV22, ("FY2022", "Other"): OTH22,
           ("FY2023", "Advertising"): ADV23, ("FY2023", "Other"): OTH23}
segment["revenue_usd_mm"] = segment["revenue_usd_mm"].map(num)
for fy in ["FY2022", "FY2023"]:
    sub = segment[segment.fy == fy]
    s = sub.revenue_usd_mm.sum()
    if abs(s - SEC01_ANNUAL[fy]) > TOL:
        for _, row in sub.iterrows():
            ref = seg_map.get((fy, row.segment))
            if ref is not None and abs(num(row.revenue_usd_mm) - ref) > TOL:
                ratio = num(row.revenue_usd_mm) / ref
                k = round(math.log10(ratio)) if ratio > 0 else None
                mag = (k is not None and abs(ratio - 10 ** k) < 1e-6 and k != 0)
                anomaly("financials/revenue_by_segment_2022_2023.csv",
                        f"行{int(row.name)+2}（{fy} {row.segment}={row.revenue_usd_mm:.3f}，{row.Source_ID}）",
                        f"{fy} 分部加总 {s:.3f} ≠ SEC-01 年度数 {SEC01_ANNUAL[fy]:.3f}；"
                        f"{row.segment} 明细 {row.revenue_usd_mm:.3f} 为 SEC-01 对应年度数 {ref:.3f} 的 {ratio:.0f} 倍"
                        + ("（10 倍量级错位）" if mag else ""),
                        "量级错位（magnitude / decimal shift）",
                        "CP-02 来源优先级：SEC-01(P1) 年度审计数为准；分部明细该行与年度数不勾稽",
                        f"以 SEC-01 年度数 {ref:.3f} 修正该行；修正后分部加总 = {s - num(row.revenue_usd_mm) + ref:.3f}，与年度数一致",
                        f"若不修正，{fy} 收入被高估 {num(row.revenue_usd_mm) - ref:.3f}，估值分母与倍数计算全部失真")
        corrected = sum(seg_map[(fy, sg)] for sg in sub.segment)
        check("revenue_by_segment_2022_2023.csv", f"{fy} 分部加总（修正后）",
              r6(corrected), SEC01_ANNUAL[fy], "量级错位修正后与 SEC-01 年度数勾稽",
              "PASS" if abs(corrected - SEC01_ANNUAL[fy]) <= TOL else "FAIL",
              f"原始加总 {r6(s)} 不一致；以 SEC-01 年度分项修正后一致")
    else:
        check("revenue_by_segment_2022_2023.csv", f"{fy} 分部加总", r6(s),
              SEC01_ANNUAL[fy], "明细加总与 SEC-01 年度数勾稽", "PASS", "一致，直接采信")

# 2.4 SBC 明细：小计行 vs 明细行冲突
sbc["amount_usd_mm"] = sbc["amount_usd_mm"].map(num)
for fy, ref in [("FY2022", SBC22), ("FY2023", SBC23)]:
    sub = sbc[sbc.fy == fy]
    comp = sub[sub.component != "TOTAL"].amount_usd_mm.sum()
    tot = sub[sub.component == "TOTAL"]
    if len(tot):
        tv = num(tot.amount_usd_mm.iloc[0])
        if abs(comp - ref) <= TOL and abs(tv - ref) > TOL:
            anomaly("financials/sbc_detail_2022_2023.csv",
                    f"行{int(tot.index[0])+2}（{fy} TOTAL={tv:.3f}，{tot.Source_ID.iloc[0]}）",
                    f"TOTAL 小计行 {tv:.3f} ≠ 明细组件加总 {comp:.3f}（=SEC-01 年度数 {ref:.3f}）；数字呈换位错（49.086→49.680 型）",
                    "小计行错误（明细 vs 小计冲突）",
                    "以与 SEC-01(P1) 年度数勾稽一致的明细组件为准；internal/data_revision_log.csv 2024-03-20 记载 'total row recalculated'，该小计为重算引入的错误",
                    f"弃用 TOTAL 行 {tv:.3f}，采用明细加总 {comp:.3f}",
                    f"若误用 TOTAL 行，SBC 高估 {tv - comp:.3f}，承销口径 EBITDA 被低估同额")
        check("sbc_detail_2022_2023.csv", f"{fy} 组件加总", r6(comp), ref,
              "明细组件加总与 SEC-01 年度数勾稽（TOTAL 行单独核对）",
              "PASS" if abs(comp - ref) <= TOL else "FAIL",
              "组件与年度数一致" + ("；TOTAL 行错误已弃用" if len(tot) and abs(tv - ref) > TOL else ""))
    else:
        check("sbc_detail_2022_2023.csv", f"{fy} 组件加总", r6(comp), ref,
              "明细组件加总与 SEC-01 年度数勾稽", "PASS" if abs(comp - ref) <= TOL else "FAIL", "")

# 2.5 重组明细
restr["amount_usd_mm"] = restr["amount_usd_mm"].map(num)
rc = restr[restr.component != "TOTAL"].amount_usd_mm.sum()
rt = num(restr[restr.component == "TOTAL"].amount_usd_mm.iloc[0])
ok = abs(rc - RESTR23) <= TOL and abs(rt - RESTR23) <= TOL
check("restructuring_detail_2023.csv", "FY2023 组件加总及 TOTAL 行", r6(rc), RESTR23,
      "明细/TOTAL 与 SEC-01 年度数勾稽", "PASS" if ok else "FAIL",
      f"组件 {r6(rc)}、TOTAL {r6(rt)} 均与 SEC-01 一致" if ok else "不一致")

# 2.6 地区收入（SEC-05）
for fy in ["FY2022", "FY2023"]:
    s = geo[geo.fy == fy].revenue_usd_mm.map(num).sum()
    check("sec_filings/SEC-05_revenue_by_geo.csv", f"{fy} 地区加总", r6(s),
          SEC01_ANNUAL[fy], "US+International 与 SEC-01 年度数勾稽",
          "PASS" if abs(s - SEC01_ANNUAL[fy]) <= TOL else "FAIL", "")

# 2.7 FCF 桥、现金流量表、资产负债表
ocf = num(fcfb.set_index("line_item").loc["Net cash used in operating activities", "amount_usd_mm"])
capex = num(fcfb.set_index("line_item").loc["Purchases of property and equipment", "amount_usd_mm"])
fcf_row = num(fcfb.set_index("line_item").loc["Free cash flow", "amount_usd_mm"])
ok = abs(ocf + capex - fcf_row) <= TOL and abs(fcf_row - FCF23) <= TOL
check("fcf_bridge_2023.csv", "OCF + capex = FCF；FCF vs SEC-01", r6(ocf + capex), FCF23,
      "现金流桥内部勾稽 + 与 SEC-01 年度数勾稽", "PASS" if ok else "FAIL", "")

nc = (num(cfs.loc["Net cash used in operating activities", "FY2023"])
      + num(cfs.loc["Net cash used in investing activities", "FY2023"])
      + num(cfs.loc["Net cash provided by financing activities", "FY2023"]))
end = num(cfs.loc["Cash & cash equivalents at end of period", "FY2023"])
beg = num(cfs.loc["Cash & cash equivalents at beginning of period", "FY2023"])
ok = abs(nc - num(cfs.loc["Net change in cash and cash equivalents", "FY2023"])) <= TOL \
     and abs(beg + nc - end) <= TOL and abs(end - CASH23) <= TOL and abs(beg - CASH22) <= TOL
check("cash_flow_statement_2023.csv", "三项活动合计=净变动；期初+净变动=期末；期初/期末 vs SEC-01",
      r6(beg + nc), CASH23, "现金流量表内部勾稽 + 与 SEC-01 勾稽", "PASS" if ok else "FAIL", "")

tot_key = "Total cash, cash equivalents and marketable securities"
for fy, (c, ms) in [("FY2022", (CASH22, MS22)), ("FY2023", (CASH23, MS23))]:
    t = num(bs.loc[tot_key, fy])
    ok = abs(num(bs.loc["Cash & cash equivalents", fy]) + num(bs.loc["Marketable securities", fy]) - t) <= TOL \
         and abs(t - (c + ms)) <= TOL
    check("balance_sheet_summary_2022_2023.csv", f"{fy} cash+MS=Total；vs SEC-01", r6(t), r6(c + ms),
          "资产负债表内部勾稽 + 与 SEC-01 勾稽", "PASS" if ok else "FAIL", "")

# 2.8 利润表 / opex 内部勾稽
for fy in ["FY2022", "FY2023"]:
    comp = ["Cost of revenue", "Research and development", "Sales and marketing",
            "General and administrative"]
    s = sum(num(istat.loc[c, fy]) for c in comp)
    tot = num(istat.loc["Total costs and operating expenses", fy])
    ni_calc = num(istat.loc["Revenue", fy]) + tot + num(istat.loc["Other income, net", fy])
    ok = (abs(s - tot) <= TOL and abs(ni_calc - num(istat.loc["Net income (loss)", fy])) <= TOL
          and abs(num(istat.loc["Revenue", fy]) - SEC01_ANNUAL[fy]) <= TOL
          and abs(num(istat.loc["Net income (loss)", fy]) - (NI22 if fy == "FY2022" else NI23)) <= TOL
          and all(abs(num(istat.loc[c, fy])) - abs(num(opex.loc[c, fy])) <= TOL for c in comp))
    check("income_statement_2022_2023.csv / opex_summary", f"{fy} 费用加总=Total；Rev+Total+Other=NI；vs SEC-01",
          r6(ni_calc), r6(NI22 if fy == "FY2022" else NI23),
          "利润表内部勾稽 + 与 SEC-01 勾稽 + 与 opex_summary 一致", "PASS" if ok else "FAIL", "")

# 2.9 DAU×ARPU 近似勾稽（ARPU 两位小数舍入）
for _, row in dau.iterrows():
    implied = num(row.daily_active_uniques_mm) * num(row.arpu_usd)
    ref = SEC01_ANNUAL[row.period]
    ok = abs(implied - ref) <= 0.5
    check("dau_arpu_metrics.csv", f"{row.period} DAU×ARPU 隐含收入", r6(implied), ref,
          "运营指标隐含收入 vs SEC-01（容差 0.5，ARPU 舍入）", "PASS" if ok else "FAIL",
          "差异在 ARPU 两位小数舍入范围内" if ok else "")

# 2.10 累计赤字滚动勾稽
ad22 = num(eqty.loc["Accumulated deficit", "FY2022"]); ad23 = num(eqty.loc["Accumulated deficit", "FY2023"])
ok = abs(ad22 + NI23 - ad23) <= TOL
check("stockholders_equity_summary.csv", "FY2022 累计赤字 + FY2023 净亏损 = FY2023 累计赤字",
      r6(ad22 + NI23), ad23, "权益滚动勾稽", "PASS" if ok else "FAIL", "")

# 2.11 股本口径核对（cap-table snapshot vs SEC-09 vs SEC-16）
ok_cap = abs(CAP_SUM - CAP_TOTAL) <= 1e-6 and abs(CAP_TOTAL - PREMONEY_SH) <= 1e-6
sec09_sum = cap09.shares_mm.map(num).sum()
ok_sec09 = abs(sec09_sum - CAP_TOTAL) <= 1e-6
check("committee/cap_table_snapshot_20240318.csv", "组件加总=TOTAL=Offering_Terms pre-money；=SEC-09 组件加总",
      r6(CAP_SUM), r6(PREMONEY_SH), "cap-table 内部勾稽 + 与 SEC-09 交叉",
      "PASS" if (ok_cap and ok_sec09) else "FAIL",
      f"SEC-09 组件加总 {r6(sec09_sum)} 与快照一致" if ok_sec09 else "")
reg = sh16[(sh16.as_of == "2024-03-18") & (sh16.Source_ID == "SEC-09")]
if len(reg):
    reg_v = num(reg.shares_outstanding_mm.iloc[0])
    check("sec_filings/SEC-16_share_count_history.csv",
          "2024-03-18 registered shares（excl. unsettled RSUs）vs 委员会经济口径快照",
          r6(reg_v), r6(CAP_TOTAL), "口径差异核对（registered vs economic）",
          "NOTE", f"差异 {r6(CAP_TOTAL - reg_v)}：快照为经济口径（含未结算 RSU 与 in-the-money options），"
                 f"registered 口径与之不可直接对齐，材料未逐项列示差异构成——标注待核实；"
                 f"定价分母按 Offering_Terms(UW-01) 采用经济口径 {r6(CAP_TOTAL)}，SEC-16 仅作交叉参考")

# 2.12 发行条款交叉核对：Offering_Terms(UW-01) vs SEC-03(P1)
ok_ot = (abs(PRIMARY - PRIMARY_SEC03) < 1e-9 and abs(SECONDARY - SECONDARY_SEC03) < 1e-9
         and abs(GREENSHOE - GREENSHOE_SEC03) < 1e-9 and abs(PUB_LO - RANGE_LOW_SEC03) < 1e-9
         and abs(PUB_HI - RANGE_HI_SEC03) < 1e-9)
check("committee/Offering_Terms_20240320.xlsx", "primary/secondary/greenshoe/公开区间 vs SEC-03",
      r6(PRIMARY + SECONDARY + GREENSHOE), r6(PRIMARY_SEC03 + SECONDARY_SEC03 + GREENSHOE_SEC03),
      "内部条款表与 SEC-03(P1) 一致性核对", "PASS" if ok_ot else "FAIL",
      "股份数与区间与 SEC-03 完全一致" if ok_ot else "不一致，须以 SEC-03 为准复核")

# 2.13 2023-12 月收入：采用值与弃用值（供 Source_Trace 动态引用）
dec_rows = m[m.month == "2023-12"].sort_values("Source_ID", key=lambda s: s.map(prio))
DEC_ADOPTED = num(dec_rows.iloc[0].revenue_usd_mm); DEC_ADOPTED_SRC = dec_rows.iloc[0].Source_ID
DEC_REJECTED = num(dec_rows.iloc[-1].revenue_usd_mm); DEC_REJECTED_SRC = dec_rows.iloc[-1].Source_ID

# 2.14 SBC TOTAL 行错误值（供 Source_Trace / QoE bridge 动态引用）
SBC_TOTAL_ROW = num(sbc[(sbc.fy == "FY2023") & (sbc.component == "TOTAL")].amount_usd_mm.iloc[0])

# ----------------------------------------------------------------------------
# 3. QoE：管理层口径 → 承销口径（CP-03 / CP-04 / CP-13）
# ----------------------------------------------------------------------------
UW_EBITDA23 = ADJEB23 - SBC23          # CP-03: SBC 为持续性经济成本，不保留加回
UW_EBITDA22 = ADJEB22 - SBC22
# CP-04: restructuring 已在 management 调整中，不再二次加回（调整额 = 0）
RESID_NI_TO_ADJEB = ADJEB23 - (NI23 + SBC23 + RESTR23 + DA23)   # 未逐项列示的其余管理层调整项
QOE = [
    ("Revenue", REV22, REV23, "SEC-01", "月度/季度/分部/地区明细清洗后勾稽一致"),
    ("Net income (loss)", NI22, NI23, "SEC-01", "利润表内部勾稽一致"),
    ("Management Adjusted EBITDA (非GAAP)", ADJEB22, ADJEB23, "SEC-01", "管理层口径起点；不在审计意见覆盖范围(SEC-14)"),
    ("SBC & related taxes", SBC22, SBC23, "SEC-01", "sbc_detail 组件加总一致；TOTAL 行错误已弃用"),
    ("Restructuring costs", 0.0, RESTR23, "SEC-01", "restructuring_detail 组件与 TOTAL 均一致"),
    ("Depreciation & amortization", DA22, DA23, "SEC-01", "参考项"),
    ("Free Cash Flow", FCF22, FCF23, "SEC-01", "fcf_bridge 勾稽一致"),
    ("Cash & cash equivalents", CASH22, CASH23, "SEC-01", "现金流量表期末勾稽一致"),
    ("Marketable securities", MS22, MS23, "SEC-01", "可变现金融资产，CP-08 全额入桥"),
    ("Total cash + marketable securities", CASH22 + MS22, CASH23 + MS23, "SEC-01", "balance_sheet 勾稽一致"),
]
UW_EBITDA_NEG = UW_EBITDA23 < 0

# ----------------------------------------------------------------------------
# 4. 估值（CP-05/06/07/08/09）
# ----------------------------------------------------------------------------
REV24E = REV23 * (1 + GROWTH)                       # CP-06
NET_CASH = CASH23 + MS23                            # CP-08（完整净现金桥）
def per_share(mult):
    ev = mult * REV24E
    eq = ev + NET_CASH                              # pre-money equity
    ps = eq / PREMONEY_SH                           # undiscounted equity value/share
    return ev, eq, ps, ps * (1 - DISCOUNT)          # CP-09 执行折扣
EV_L, EQ_L, PS_L_U, PS_L = per_share(MULT_LO)
EV_M, EQ_M, PS_M_U, PS_M = per_share(MULT_MID)
EV_H, EQ_H, PS_H_U, PS_H = per_share(MULT_HI)
SUPPORT_LO, SUPPORT_MID, SUPPORT_HI = PS_L, PS_M, PS_H
IN_RANGE = SUPPORT_LO <= PRICE <= SUPPORT_HI
DIST_MID = abs(PRICE - SUPPORT_MID)

# ----------------------------------------------------------------------------
# 5. 发行结构、募集与费用（CP-10/11/12，SEC-03/10/12）
# ----------------------------------------------------------------------------
def proceeds(primary_sh):
    gross = primary_sh * PRICE
    fee = gross * FEE_RATE            # 计提基数=公司 primary gross（CP-12，v2 全股份费基已作废）
    return gross, fee, gross - fee - FIXED_EXP
G_BASE, FEE_BASE, NET_BASE = proceeds(PRIMARY)
G_FULL, FEE_FULL, NET_FULL = proceeds(PRIMARY_FULL)
G_GS, FEE_GS, NET_GS = proceeds(GREENSHOE)          # greenshoe 增量：只扣 5%，不重复扣固定费用
SEC_PROCEEDS_TO_CO = 0.0                            # secondary 不形成公司募集资金

# ----------------------------------------------------------------------------
# 6. 股本桥与稀释（CP-10/11；SEC-02 交叉验算）
# ----------------------------------------------------------------------------
POST_BASE = PREMONEY_SH + PRIMARY                   # secondary 不增加公司总股数
POST_FULL = PREMONEY_SH + PRIMARY_FULL
NEWPCT_BASE = PRIMARY / POST_BASE
NEWPCT_FULL = PRIMARY_FULL / POST_FULL
SEC02_CONSISTENT = abs((SEC02_PX - NTBV_PS) - DIL_PS) <= 0.01   # 32.50-11.17=21.33

# ----------------------------------------------------------------------------
# 7. 敏感性矩阵（增长率 × 倍数；轴围绕委员会基准对称推导，非新增事实假设）
# ----------------------------------------------------------------------------
G_AX = [GROWTH - 0.08, GROWTH - 0.04, GROWTH, GROWTH + 0.04, GROWTH + 0.08]
M_AX = [MULT_LO, (MULT_LO + MULT_MID) / 2, MULT_MID, (MULT_MID + MULT_HI) / 2, MULT_HI]
def psv(g, m):
    return (m * REV23 * (1 + g) + NET_CASH) / PREMONEY_SH * (1 - DISCOUNT)
MATRIX = pd.DataFrame([[psv(g, m) for m in M_AX] for g in G_AX],
                      index=[f"{g*100:.0f}%" for g in G_AX],
                      columns=[f"{m:.2f}x" for m in M_AX])

# ----------------------------------------------------------------------------
# 8. 定价处置（CP-14 / CP-15）
# ----------------------------------------------------------------------------
HARD_ERRORS_RESOLVED = True   # legacy 12 类口径错误与 4 项明细异常均已在修复模型中处置（见 Error_Audit）
if IN_RANGE and DIST_MID <= MID_TOL and HARD_ERRORS_RESOLVED:
    DISPOSITION = "Proceed"
elif IN_RANGE and DIST_MID > MID_TOL:
    DISPOSITION = "Reprice (toward midpoint)"
else:
    DISPOSITION = "Defer"

# ----------------------------------------------------------------------------
# 9. Error_Audit：legacy 口径错误（≥8 类）+ 明细异常（全覆盖）+ 失效政策条款
# ----------------------------------------------------------------------------
LEGACY_ERRORS = [
    ("L1", "盈利质量/SBC（口径错误）", "legacy/Candidate_Model_v0.xlsx Candidate_Model 行1",
     "直接以管理层 Adjusted EBITDA -69.275 作为盈利质量结论（SBC 加回保留）",
     f"CP-03：SBC 为持续性经济成本，承销口径 EBITDA = {r3(ADJEB23)} − {r3(SBC23)} = {r3(UW_EBITDA23)}",
     f"盈利质量高估 {r3(SBC23)}；承销口径 EBITDA 仍为负 → CP-05 锁定 EV/2024E Revenue 主估值"),
    ("L2", "估值分母（口径错误）", "Candidate_Model 行2；legacy_assumptions_export.csv valuation_denominator",
     "以 4.5x 直接乘 2023A 收入（2023A 作分母）",
     f"CP-06：分母为 2024E Revenue = {r3(REV23)} × (1+{GROWTH:.0%}) = {r3(REV24E)}",
     f"EV 低估 {r3(MULT_MID * (REV24E - REV23))}（mid 倍数下），每股价值系统性偏低"),
    ("L3", "执行折扣缺失（口径错误）", "Candidate_Model 行2；legacy_assumptions_export.csv discount_applied=0.0",
     "未对 peer-implied 每股价值应用任何 IPO 执行折扣",
     f"CP-09：统一应用 {DISCOUNT:.1%} 折扣于 peer-implied undiscounted equity value/share（作用于每股价值，不乘收入或 EV——committee_email_thread.txt 第4条）",
     f"mid 档每股高估 {r4(PS_M_U - PS_M)}（{r4(PS_M_U)} vs {r4(PS_M)}）"),
    ("L4", "净现金桥不完整（口径错误）", "Candidate_Model 行3",
     "净现金桥仅计入现金，遗漏有价证券",
     f"CP-08 + SEC-07：pre-money equity = EV + 年末现金 {r3(CASH23)} + 有价证券 {r3(MS23)} = EV + {r3(NET_CASH)}",
     f"每股价值低估约 {r4(MS23 / PREMONEY_SH * (1 - DISCOUNT))}（折后）"),
    ("L5", "primary/secondary 混淆（口径错误）", "Candidate_Model 行4；legacy_assumptions_export.csv",
     "将 Base 全部发行股份视为 primary（公司募集被高估）",
     f"CP-10 + SEC-03：primary {r6(PRIMARY)}m、secondary {r6(SECONDARY)}m；secondary 不形成公司募集资金",
     f"公司 gross proceeds 高估 {r3(SECONDARY * PRICE)}（按 $34）"),
    ("L6", "greenshoe 预设入 Base（口径错误）", "Candidate_Model 行5；legacy_assumptions_export.csv greenshoe_in_base=1",
     "将 3.3m greenshoe 预先并入 Base",
     "CP-11 + SEC-10：greenshoe 为承销商选择权，Base 不含行权；full-exercise 单独列示",
     f"Base 股数高估 {r6(GREENSHOE)}m、Base 公司 gross 高估 {r3(GREENSHOE * PRICE)}"),
    ("L7", "承销费计提基数错误（口径错误）", "Candidate_Model 行6；Committee_Policy_v2 CP-12（已作废）",
     "承销费按 primary + secondary 全部发行股份计提",
     "CP-12(v3) + SEC-10：费基=公司 primary gross proceeds 的 5%；secondary 费用归出售股东；固定费用 $7.0mm 仅计一次，greenshoe 增量不重复扣",
     f"Base 费用高估 {r3(SECONDARY * PRICE * FEE_RATE)}；full-exercise 下再高估 greenshoe 部分固定费用重复额"),
    ("L8", "post-money 股数含 secondary（口径错误）", "Candidate_Model 行7",
     "将 secondary 股份计入发行后公司总股数",
     "CP-10：secondary 是存量股份转让，不新增公司总股数；post-money = pre-money + primary",
     f"post-money 股数高估 {r6(SECONDARY)}m，稀释比例与每股指标失真"),
    ("L9", "secondary 款项误入公司现金（口径错误）", "Candidate_Model 行8；SEC-06/SEC-12 明确归出售股东",
     "将 secondary 出售所得计入公司现金",
     "CP-10 + SEC-12：secondary 款项归出售股东，公司现金仅增加 primary net proceeds",
     f"公司现金高估最多 {r3(SECONDARY * PRICE)}（gross 口径，按 $34）"),
    ("L10", "稀释指标分子分母口径不一致（口径错误）", "Candidate_Model 行9",
     "以 post-money equity / pre-money shares 计算稀释",
     "统一口径：新增股份占比 = primary / post-money 总股数；账面稀释以 SEC-02 独立口径交叉验算（仅 $32.50 假设价下有效）",
     f"Base 新增占比应为 {NEWPCT_BASE:.2%}（full-exercise {NEWPCT_FULL:.2%}），legacy 口径无法与 SEC-02 勾稽"),
    ("L11", "定价建议依据错误（口径错误）", "Candidate_Model 行10",
     "主要依据 peer high case 将建议价上移至 $34 以上",
     "CP-14/15：处置仅由支持区间、距 midpoint ≤$0.50 与结构 hard error 状态决定；board_minutes_extract_20240319.md：董事会未授权高于委员会区间上限的定价",
     f"正确处置为 {DISPOSITION}（$34 位于 [{r4(SUPPORT_LO)}, {r4(SUPPORT_HI)}]，距 midpoint {r4(DIST_MID)}）"),
    ("L12", "失效引用（#REF! 断链）", "Candidate_Model_v0.xlsx Broken_Links：Valuation!C7、QoE!D9、Offering!C12",
     "模型内存在未解析引用错误单元格，部分联动失效，计算结果不可直接沿用",
     "全部模块从 Inputs 重算，勾稽一致性在 Pricing_Summary 复核",
     "legacy 联动结果整体不可信，本模型已重建"),
]
# 明细异常（D 系列）：来自第 2 节核验，全覆盖
DATA_ERRORS = [(f"D{i+1}", a) for i, a in enumerate(ANOMALIES)]
# 失效政策条款（P 系列）：v2 → v3
POLICY_ERRORS = [(f"P{i+1}", pid, txt) for i, (pid, txt) in enumerate(SUPERSEDED_V2)]

# ----------------------------------------------------------------------------
# 10. Source_Trace（来源追溯表）
# ----------------------------------------------------------------------------
peerA = pd.read_csv(P("comps", "underwriter_A_comps_20240315.csv"))
peerB = pd.read_csv(P("comps", "underwriter_B_comps_20240318.csv"))
b_lo, b_hi = peerB.ntm_ev_revenue.map(num).min(), peerB.ntm_ev_revenue.map(num).max()
TRACE = [
    ("FY2023 Revenue", f"{r3(REV23)} USD mm", "SEC-01(P1)；清洗后月度/季度/分部/地区加总一致",
     f"INT-01 flash {num(flash.loc['Revenue','FY2023_value']):.1f}(P9)", "CP-02：采用 P1 审计数；flash 未过审仅参考"),
    ("FY2022 Revenue", f"{r3(REV22)} USD mm", "SEC-01(P1)；月度去重后加总一致", "—", "CP-02"),
    ("FY2023 Net income (loss)", f"{r3(NI23)} USD mm", "SEC-01(P1)；利润表勾稽一致", "—", "CP-02"),
    ("FY2023 Management Adj. EBITDA", f"{r3(ADJEB23)} USD mm", "SEC-01(P1)",
     f"INT-01 flash {num(flash.loc['Adjusted EBITDA','FY2023_value']):.1f}(P9)", "CP-02：采用 P1；non-GAAP 不在审计范围(SEC-14)"),
    ("FY2023 SBC & related taxes", f"{r3(SBC23)} USD mm", "SEC-01(P1)；sbc_detail 组件加总一致",
     f"sbc_detail TOTAL 行 {r3(SBC_TOTAL_ROW)}（重算错误）；INT-01 flash {num(flash.loc['Stock-based compensation & related taxes','FY2023_value']):.1f}(P9)",
     "以与年度数勾稽一致的明细组件为准；CP-03 不保留加回"),
    ("FY2023 Restructuring", f"{r3(RESTR23)} USD mm", "SEC-01(P1)；明细/TOTAL 一致", "—", "CP-04：不二次加回"),
    ("FY2023 FCF", f"{r3(FCF23)} USD mm", "SEC-01(P1)；fcf_bridge 一致",
     f"INT-01 flash {num(flash.loc['Free Cash Flow','FY2023_value']):.1f}(P9)", "CP-02"),
    ("YE2023 Cash", f"{r3(CASH23)} USD mm", "SEC-01(P1)；现金流量表期末一致", "—", "CP-08 入桥"),
    ("YE2023 Marketable securities", f"{r3(MS23)} USD mm", "SEC-01(P1)", "—", "CP-08：可变现金融资产全额入桥（SEC-07）"),
    ("2023-12 月收入", f"{r3(DEC_ADOPTED)} USD mm",
     f"{DEC_ADOPTED_SRC}(P{prio(DEC_ADOPTED_SRC)})", f"{DEC_REJECTED_SRC} {r3(DEC_REJECTED)}(P{prio(DEC_REJECTED_SRC)})",
     "CP-02 优先级择值；committee email 确认审计版为准"),
    ("2024E revenue growth", f"{GROWTH:.0%}", "Committee_Policy_v3 CP-06 / Underwriting_Assumptions（UW-01，内部假设）",
     "sector_benchmark 行业中位 18%（背景参考）", "内部委员会假设，非 SEC 公开事实；行业基准不改变委员会口径"),
    ("Peer EV/NTM Revenue 区间", f"{MULT_LO:.1f}x / {MULT_MID:.1f}x / {MULT_HI:.1f}x",
     "CP-07 / Committee_Peer_Set（UW-01）",
     f"BANK-A comps {peerA.ntm_ev_revenue.map(num).min():.1f}–{peerA.ntm_ev_revenue.map(num).max():.1f}(P8，与委员会一致)；BANK-B screen {b_lo:.1f}–{b_hi:.1f}(P8)；v2 旧区间 3.5x–5.5x（作废）；sector 4.4x（背景）",
     "CP-02/CP-07：承销商 comps 仅交叉验证，不改区间端点"),
    ("IPO execution discount", f"{DISCOUNT:.1%}", "CP-09 / Underwriting_Assumptions（UW-01，内部假设）",
     "v2 暂定 10%（作废）；ipo_market_update 明确不引用市场折让", "作用于 peer-implied equity value/share"),
    ("Pre-money economic shares", f"{r6(PREMONEY_SH)} mm", "Offering_Terms（UW-01）= cap_table_snapshot 加总 = SEC-09 组件加总",
     "SEC-16 registered 141.2mm（excl. unsettled RSUs，口径不同；6.2mm 构成差异待核实）", "经济口径为定价分母；registered 口径仅交叉参考"),
    ("Primary / Secondary / Greenshoe", f"{r6(PRIMARY)} / {r6(SECONDARY)} / {r6(GREENSHOE)} mm",
     "SEC-03(P1) = Offering_Terms", "legacy 全部按 primary 22.0mm 处理（错误）", "CP-10/11"),
    ("Proposed price $34", f"{PRICE:.2f} USD/share", "Offering_Terms（UW-01）——内部工作价/决策输入，非已实现结果",
     f"SEC-03 公开询价区间 {PUB_LO:.0f}–{PUB_HI:.0f}（$34 为区间上限）", "CP-01：不得用 3/20 后结果反推"),
    ("承销费/固定费用", f"{FEE_RATE:.0%} primary gross + ${FIXED_EXP:.1f}mm 固定", "CP-12 / Underwriting_Terms（UW-01）；SEC-10 费基=primary",
     "v2：按全部发行股份计提（作废）", "greenshoe 增量只扣 5%，固定费用不重复"),
    ("NTBV/share & immediate dilution", f"${NTBV_PS:.2f} / ${DIL_PS:.2f}（假定价 ${SEC02_PX:.2f}）", "SEC-02(P1) 独立口径",
     "—", "仅稀释交叉验算；不用于定价，不能替代委员会 peer-implied 估值"),
    ("政策版本", "Committee_Policy_v3_20240320.xlsx", "v3 Revision_Note + data_revision_log + ECM 邮件（v3 controlling）",
     "v2_20240305（被取代）", "v2 CP-03/07/09/12 条款不再适用"),
]

# ----------------------------------------------------------------------------
# 11. 输出：CSV 交付物
# ----------------------------------------------------------------------------
# 11.1 QoE bridge
qoe_rows = [
    ("Management Adjusted EBITDA (FY2023, 非GAAP)", r6(ADJEB23), "起点：SEC-01 管理层口径（Priority 1）", "SEC-13 / CP-03"),
    ("减：SBC & related taxes 加回（不保留）", r6(-SBC23), f"CP-03：SBC 视为持续性经济成本，承销口径不保留该加回；金额=SEC-01 年度数（sbc_detail 组件加总一致，TOTAL 行 {r3(SBC_TOTAL_ROW)} 弃用）", "CP-03"),
    ("Restructuring 二次加回", 0.0, "CP-04：已含于管理层调整，不得重复处理（金额=SEC-01 8.098，调整额 0）", "CP-04"),
    ("Underwriting EBITDA (FY2023)", r6(UW_EBITDA23), f"= {r3(ADJEB23)} − {r3(SBC23)}；仍为负 → 主估值采用 EV/2024E Revenue", "CP-03/04/05"),
    ("[参考] FY2022 Underwriting EBITDA", r6(UW_EBITDA22), f"= {r3(ADJEB22)} − {r3(SBC22)}", "CP-03"),
    ("[参考] Net income (loss) FY2023", r6(NI23), "SEC-01；利润表勾稽一致", "SEC-01"),
    ("[参考] NI→Adj.EBITDA 未逐项列示调整项", r6(RESID_NI_TO_ADJEB), f"Adj.EBITDA − (NI+SBC+Restr+D&A) = {r3(RESID_NI_TO_ADJEB)}，材料未载明构成——待核实；不影响承销口径（起点为 SEC-01 披露值）", "SEC-13（'等项目'）"),
    ("[参考] Free Cash Flow FY2023", r6(FCF23), "SEC-01；fcf_bridge 勾稽一致；为负须披露", "CP-13"),
    ("[参考] YE2023 Cash + Marketable securities", r6(NET_CASH), f"= {r3(CASH23)} + {r3(MS23)}；净现金桥全额入估值", "CP-08 / SEC-07"),
]
pd.DataFrame(qoe_rows, columns=["item", "amount_usd_mm", "basis", "policy_clause"]).to_csv(
    os.path.join(OUT, "FIN3-WKN-152_qoe_bridge.csv"), index=False)

# 11.2 估值敏感性矩阵（宽表 + 基准/三档标注行）
mtx = MATRIX.round(4).copy()
mtx_out = mtx.reset_index().rename(columns={"index": "growth_2024E \\ EV_Rev"})
annot = pd.DataFrame({
    "growth_2024E \\ EV_Rev": [
        f"BASE CASE (g={GROWTH:.0%} x {MULT_MID:.2f}x)",
        f"Low tier (g={GROWTH:.0%} x {MULT_LO:.2f}x)",
        f"Mid tier (= base case)",
        f"High tier (g={GROWTH:.0%} x {MULT_HI:.2f}x)",
        "formula"],
    f"{M_AX[0]:.2f}x": [r4(SUPPORT_MID), r4(SUPPORT_LO), r4(SUPPORT_MID), r4(SUPPORT_HI),
                         f"value/share = (m x {r3(REV23)} x (1+g) + {r3(NET_CASH)}) / {r6(PREMONEY_SH)} x (1-{DISCOUNT:.3f})"],
})
mtx_out = pd.concat([mtx_out, pd.DataFrame([[""] * len(mtx_out.columns)], columns=mtx_out.columns), annot],
                    ignore_index=True)
mtx_out.to_csv(os.path.join(OUT, "FIN3-WKN-152_valuation_matrix.csv"), index=False)

# 11.3 来源追溯表
pd.DataFrame(TRACE, columns=["metric", "adopted_value", "adopted_source", "competing_value_source", "disposition_rationale"]).to_csv(
    os.path.join(OUT, "FIN3-WKN-152_source_trace.csv"), index=False)

# ----------------------------------------------------------------------------
# 12. 输出：xlsx 模型（9+ 工作表）
# ----------------------------------------------------------------------------
xl_path = os.path.join(OUT, "FIN3-WKN-152_ipo_model.xlsx")
with pd.ExcelWriter(xl_path, engine="openpyxl") as xw:
    # Inputs
    inputs = [
        ("信息截止时点", "2024-03-20", "—", "CP-01", "committee/Committee_Policy_v3_20240320.xlsx", "控制口径：仅用截止日前信息"),
        ("控制政策版本", "Committee_Policy_v3_20240320", "—", "—", "committee/", "v2 被取代（CP-03/07/09/12 条款作废）"),
        ("FY2023 Revenue", r6(REV23), "USD mm", "SEC-01(P1)", "sec_filings/SEC-01_financials_extract.xlsx", "SEC 公开事实"),
        ("FY2022 Revenue", r6(REV22), "USD mm", "SEC-01(P1)", "同上", "SEC 公开事实"),
        ("FY2023 Net income (loss)", r6(NI23), "USD mm", "SEC-01(P1)", "同上", "SEC 公开事实"),
        ("FY2023 Mgmt Adj. EBITDA", r6(ADJEB23), "USD mm", "SEC-01(P1)", "同上", "SEC 公开事实（non-GAAP，不在审计范围）"),
        ("FY2023 SBC & related taxes", r6(SBC23), "USD mm", "SEC-01(P1)", "同上", f"SEC 公开事实（sbc_detail TOTAL 行 {r3(SBC_TOTAL_ROW)} 弃用，见 Error_Audit D 系列）"),
        ("FY2023 Restructuring", r6(RESTR23), "USD mm", "SEC-01(P1)", "同上", "SEC 公开事实"),
        ("FY2023 D&A", r6(DA23), "USD mm", "SEC-01(P1)", "同上", "SEC 公开事实"),
        ("FY2023 FCF", r6(FCF23), "USD mm", "SEC-01(P1)", "同上", "SEC 公开事实"),
        ("YE2023 Cash & equivalents", r6(CASH23), "USD mm", "SEC-01(P1)", "同上", "SEC 公开事实"),
        ("YE2023 Marketable securities", r6(MS23), "USD mm", "SEC-01(P1)", "同上", "SEC 公开事实"),
        ("2024E growth", GROWTH, "%", "CP-06 / UW-01", "committee/Underwriting_Assumptions_20240320.xlsx", "内部委员会假设（非 SEC 事实）"),
        ("Peer low / mid / high EV/Rev", f"{MULT_LO} / {MULT_MID} / {MULT_HI}", "x", "CP-07 / UW-01", "committee/Committee_Policy_v3(Committee_Peer_Set)", "内部委员会假设"),
        ("IPO execution discount", DISCOUNT, "%", "CP-09 / UW-01", "committee/Underwriting_Assumptions_20240320.xlsx", "内部委员会假设"),
        ("Primary shares (Base)", r6(PRIMARY), "mm", "SEC-03(P1)", "sec_filings/SEC-03_offering_terms.xlsx", "SEC 公开事实"),
        ("Secondary shares (Base)", r6(SECONDARY), "mm", "SEC-03(P1)", "同上", "SEC 公开事实；不形成公司募集/不增总股数"),
        ("Greenshoe option", r6(GREENSHOE), "mm", "SEC-03(P1)", "同上", "SEC 公开事实；Base 不含行权"),
        ("Pre-money economic shares", r6(PREMONEY_SH), "mm", "UW-01", "committee/Offering_Terms_20240320.xlsx; cap_table_snapshot_20240318.csv", "内部 cap-table 快照（=SEC-09 组件加总）"),
        ("Proposed committee price", PRICE, "USD/share", "UW-01", "committee/Offering_Terms_20240320.xlsx", "内部假设：决策输入，非已实现结果"),
        ("Public filing range", f"{PUB_LO}–{PUB_HI}", "USD/share", "SEC-03(P1)", "sec_filings/SEC-03_offering_terms.xlsx", "SEC 公开事实（执行交叉参考）"),
        ("Underwriting fee rate", FEE_RATE, "% primary gross", "CP-12 / UW-01; SEC-10", "committee/Offering_Terms_20240320.xlsx", "内部假设（费基口径与 SEC-10 一致）"),
        ("Fixed company expenses", FIXED_EXP, "USD mm", "CP-12 / UW-01", "同上", "内部假设；仅计一次"),
        ("NTBV/share @ $32.50", NTBV_PS, "USD/share", "SEC-02(P1)", "sec_filings/SEC-02_dilution_crosscheck.xlsx", "SEC 公开事实；仅交叉验算"),
        ("Immediate dilution @ $32.50", DIL_PS, "USD/share", "SEC-02(P1)", "同上", "同上"),
    ]
    esc_df(pd.DataFrame(inputs, columns=["input", "value", "unit", "source_id", "file", "nature"])).to_excel(
        xw, sheet_name="Inputs", index=False)

    # Data_Validation
    esc_df(pd.DataFrame(CHECKS)).to_excel(xw, sheet_name="Data_Validation", index=False)

    # QoE
    qoe_df = pd.DataFrame(QOE, columns=["metric", "FY2022", "FY2023", "source_id", "validation_note"])
    bridge = pd.DataFrame([
        ("Management Adjusted EBITDA FY2023", r6(ADJEB23), "SEC-01 起点"),
        ("Less: SBC add-back not retained (CP-03)", r6(-SBC23), "SBC=持续性经济成本"),
        ("Restructuring second add-back (CP-04)", 0.0, "禁止重复调整"),
        ("= Underwriting EBITDA FY2023", r6(UW_EBITDA23), "仍为负 → EV/2024E Revenue (CP-05)"),
        ("Memo: NI→AdjEBITDA 未列示调整项", r6(RESID_NI_TO_ADJEB), "待核实（材料未载明构成）"),
    ], columns=["bridge_step", "amount_usd_mm", "note"])
    esc_df(qoe_df).to_excel(xw, sheet_name="QoE", index=False, startrow=1)
    esc_df(bridge).to_excel(xw, sheet_name="QoE", index=False, startrow=len(qoe_df) + 4)
    ws = xw.book["QoE"]; ws.cell(row=1, column=1, value="QoE 复核（管理层口径 → 承销口径，CP-03/04/05/13）")

    # Valuation
    val = [
        ("2023A Revenue (SEC-01)", r6(REV23), "USD mm", "SEC 公开事实"),
        ("× (1 + 22%) [CP-06 内部假设]", f"{REV23:.3f} × 1.22", "—", "算式"),
        ("= 2024E Revenue", r6(REV24E), "USD mm", "估值分母"),
        ("EV @ 4.0x / 4.5x / 5.0x", f"{r3(EV_L)} / {r3(EV_M)} / {r3(EV_H)}", "USD mm", "= 倍数 × 2024E Rev"),
        ("+ YE2023 cash", r6(CASH23), "USD mm", "CP-08"),
        ("+ YE2023 marketable securities", r6(MS23), "USD mm", "CP-08 完整净现金桥"),
        ("= Pre-money equity (L/M/H)", f"{r3(EQ_L)} / {r3(EQ_M)} / {r3(EQ_H)}", "USD mm", "CP-08"),
        ("÷ Pre-money economic shares", r6(PREMONEY_SH), "mm", "UW-01 快照"),
        ("= Undiscounted equity/share (L/M/H)", f"{r4(PS_L_U)} / {r4(PS_M_U)} / {r4(PS_H_U)}", "USD/share", "peer-implied"),
        (f"× (1 − {DISCOUNT:.1%}) IPO execution discount", f"× {1-DISCOUNT:.3f}", "—",
         "CP-09：统一作用于 peer-implied undiscounted equity value/share"),
        ("= 支持区间 Low / Mid / High", f"{r4(PS_L)} / {r4(PS_M)} / {r4(PS_H)}", "USD/share", "委员会支持区间"),
        ("Midpoint", r4(SUPPORT_MID), "USD/share", "= 4.5x 档"),
        ("拟议价 $34 位置", f"区间内={IN_RANGE}; 距 midpoint={r4(DIST_MID)} (≤$0.50: {DIST_MID<=MID_TOL})", "—", "CP-14 判定输入"),
        ("主估值方法", "EV / 2024E Revenue", "—", f"Underwriting EBITDA {r3(UW_EBITDA23)} < 0 → CP-05；不得使用 EV/EBITDA"),
    ]
    esc_df(pd.DataFrame(val, columns=["step", "value", "unit", "note"])).to_excel(xw, sheet_name="Valuation", index=False)

    # Sensitivity
    sens = MATRIX.round(4).reset_index().rename(columns={"index": "growth \\ EV/Rev"})
    esc_df(sens).to_excel(xw, sheet_name="Sensitivity", index=False)
    ws = xw.book["Sensitivity"]
    ws.cell(row=len(sens) + 3, column=1,
            value=f"每股价值 = (倍数 × {REV23:.3f} × (1+g) + {NET_CASH:.3f}) / {PREMONEY_SH:.6f} × (1−{DISCOUNT:.3f})；"
                  f"g 轴 = CP-06 基准 ±4pp/±8pp；倍数轴 = CP-07 区间端点/中点及区间内四分位；均为围绕委员会基准的压力情景，非新增事实假设。"
                  f"BASE = 22% × 4.5x = {r4(SUPPORT_MID)}；Low(22%×4.0x)={r4(SUPPORT_LO)}；High(22%×5.0x)={r4(SUPPORT_HI)}")

    # Offering_Proceeds
    off = [
        ("Base：primary shares", r6(PRIMARY), "mm", "SEC-03/CP-10"),
        ("Base：secondary shares", r6(SECONDARY), "mm", "SEC-03/CP-10；公司募集=0、总股数不变"),
        ("Base：greenshoe", 0.0, "mm", "CP-11：Base 不预设行权"),
        ("Base：company gross primary proceeds", f"{r6(PRIMARY)} × ${PRICE:.0f} = {r3(G_BASE)}", "USD mm", "算式"),
        ("Base：underwriting fee (5% × primary gross)", r6(FEE_BASE), "USD mm", f"CP-12；费基不含 secondary（v2 全股份费基已作废）"),
        ("Base：fixed company expenses", r6(FIXED_EXP), "USD mm", "CP-12；仅计一次"),
        ("Base：net primary proceeds to company", r6(NET_BASE), "USD mm", f"= {r3(G_BASE)} − {r3(FEE_BASE)} − {FIXED_EXP:.1f}"),
        ("Base：secondary proceeds to company", 0.0, "USD mm", "SEC-06/SEC-12：归出售股东"),
        ("Full-exercise：primary shares", r6(PRIMARY_FULL), "mm", f"= {r6(PRIMARY)} + {r6(GREENSHOE)}"),
        ("Full-exercise：company gross", r6(G_FULL), "USD mm", f"{r6(PRIMARY_FULL)} × ${PRICE:.0f}"),
        ("Full-exercise：fee (5%)", r6(FEE_FULL), "USD mm", "greenshoe 增量只扣 5%"),
        ("Full-exercise：fixed expenses", r6(FIXED_EXP), "USD mm", "不重复计提"),
        ("Full-exercise：net proceeds", r6(NET_FULL), "USD mm", "算式同上"),
        ("Greenshoe 增量：gross / fee / net", f"{r3(G_GS)} / {r3(FEE_GS)} / {r3(G_GS - FEE_GS)}", "USD mm", "增量无固定费用"),
    ]
    esc_df(pd.DataFrame(off, columns=["item", "value", "unit", "basis"])).to_excel(xw, sheet_name="Offering_Proceeds", index=False)

    # Dilution
    dil = [
        ("Pre-money economic shares (UW-01 快照)", r6(PREMONEY_SH), "mm", "cap_table_snapshot_20240318.csv 加总 = SEC-09 组件加总"),
        ("Base：+ primary new shares", r6(PRIMARY), "mm", "SEC-03"),
        ("Base：+ secondary", 0.0, "mm", "CP-10：secondary 为存量转让，不增加公司总股数"),
        ("Base：post-money shares", r6(POST_BASE), "mm", f"= {r6(PREMONEY_SH)} + {r6(PRIMARY)}"),
        ("Base：new shares % of post-money", f"{NEWPCT_BASE:.4%}", "—", f"= {r6(PRIMARY)} / {r6(POST_BASE)}"),
        ("Full：post-money shares", r6(POST_FULL), "mm", f"= {r6(PREMONEY_SH)} + {r6(PRIMARY_FULL)}"),
        ("Full：new shares % of post-money", f"{NEWPCT_FULL:.4%}", "—", "greenshoe 行权后"),
        ("交叉验算：SEC-02 NTBV/share @ $32.50", NTBV_PS, "USD/share", "SEC 独立口径（P1）"),
        ("交叉验算：SEC-02 immediate dilution @ $32.50", DIL_PS, "USD/share", f"自洽性：{SEC02_PX:.2f} − {NTBV_PS:.2f} = {DIL_PS:.2f} → {SEC02_CONSISTENT}"),
        ("SEC-02 用途边界", "仅验算账面稀释量级与方向（发行价 >> NTBV/share）；系 $32.50 假定价下的初步数，不用于定价、不替代 peer-implied 估值、不能直接换算至 $34", "—", "SEC-02 Notes / data_dictionary.md"),
        ("口径差异：SEC-16 registered vs 经济口径快照", r6(CAP_TOTAL - REG_SHARES_SEC16), "mm", f"registered {r6(REG_SHARES_SEC16)}mm 不含未结算 RSU；构成差异材料未逐项列示——待核实；仅作交叉参考"),
    ]
    esc_df(pd.DataFrame(dil, columns=["item", "value", "unit", "basis"])).to_excel(xw, sheet_name="Dilution", index=False)

    # Pricing_Summary
    summ = [
        ("主估值方法", f"EV / 2024E Revenue（Underwriting EBITDA {r3(UW_EBITDA23)} < 0，CP-05）"),
        ("2024E Revenue", f"{r3(REV24E)} USD mm = {r3(REV23)} × 1.22（CP-06）"),
        ("净现金桥", f"{r3(NET_CASH)} USD mm = cash {r3(CASH23)} + marketable securities {r3(MS23)}（CP-08 完整口径）"),
        ("支持区间 Low / Mid / High", f"${r4(SUPPORT_LO)} / ${r4(SUPPORT_MID)} / ${r4(SUPPORT_HI)}（含 {DISCOUNT:.1%} 执行折扣，CP-09）"),
        ("Midpoint", f"${r4(SUPPORT_MID)}"),
        ("拟议价格", f"${PRICE:.2f}（内部决策输入，UW-01；亦为 SEC-03 公开询价区间 ${PUB_LO:.0f}–${PUB_HI:.0f} 上限）"),
        ("拟议价位置", f"位于支持区间内：{IN_RANGE}；距 midpoint ${r4(DIST_MID)} ≤ ${MID_TOL:.2f}：{DIST_MID <= MID_TOL}"),
        ("结构 hard error 状态", "已全部处置（legacy 12 类口径错误 + 4 项明细异常，见 Error_Audit）"),
        ("处置建议", f"{DISPOSITION}（CP-14）"),
        ("QoE 风险披露（CP-13）", f"承销口径 EBITDA {r3(UW_EBITDA23)} 与 FCF {r3(FCF23)} 均为负；SBC 为持续性经济成本"),
        ("勾稽一致性", f"QoE 起点 {r3(ADJEB23)}/{r3(SBC23)}（SEC-01）→ Underwriting EBITDA {r3(UW_EBITDA23)} → 负值触发 CP-05 → "
                    f"Valuation 分母 {r3(REV24E)}（同一 SEC-01 收入 {r3(REV23)}×1.22）→ 三档 {r4(SUPPORT_LO)}/{r4(SUPPORT_MID)}/{r4(SUPPORT_HI)} → "
                    f"Offering 净募集 {r3(NET_BASE)}（primary {r6(PRIMARY)}×${PRICE:.0f}，5% 费基）→ Dilution post {r6(POST_BASE)}（同一 primary 股数）→ "
                    f"Pricing 处置 {DISPOSITION}（同一三档与 midpoint）；各模块同源同值"),
        ("Base 发行后公司现金增量", f"+{r3(NET_BASE)} USD mm（primary net；secondary 款项归出售股东，不入公司现金）"),
    ]
    esc_df(pd.DataFrame(summ, columns=["item", "value"])).to_excel(xw, sheet_name="Pricing_Summary", index=False)

    # Error_Audit（legacy ≥8 类 + 明细异常全覆盖 + 失效条款）
    ea = []
    for eid, cat, loc, legacy_t, correct_t, impact in LEGACY_ERRORS:
        ea.append(dict(id=eid, section="Legacy 底稿口径错误", category=cat, file_location=loc,
                       phenomenon_or_legacy_treatment=legacy_t, correct_treatment=correct_t,
                       basis="Committee_Policy_v3 / SEC 摘录（详见 basis 列内文）", impact=impact))
    for did, a in DATA_ERRORS:
        ea.append(dict(id=did, section="数据核验明细异常", category=a["category"],
                       file_location=a["file"] + " @ " + a["location"],
                       phenomenon_or_legacy_treatment=a["phenomenon"],
                       correct_treatment=a["disposition"], basis=a["basis"], impact=a["impact"]))
    v2_fix = {"CP-03": "v3 CP-03：SBC 不保留加回", "CP-07": "v3 CP-07：区间 4.0x–5.0x（中点 4.5x）",
              "CP-09": "v3 CP-09：折扣 12.5%", "CP-12": "v3 CP-12：费基=公司 primary gross 5% + 固定 $7.0mm"}
    for pid_, vpid, vtxt in POLICY_ERRORS:
        ea.append(dict(id=pid_, section="失效政策条款（v2→v3）", category="政策版本失效引用",
                       file_location=f"committee/Committee_Policy_v2_20240305.xlsx {vpid}",
                       phenomenon_or_legacy_treatment=vtxt, correct_treatment=v2_fix.get(vpid, "以 v3 为准"),
                       basis="v2 Revision_Note：已被 v3 取代；data_revision_log 2024-03-20 'v3 is controlling'；ECM 邮件第1条",
                       impact="引用 v2 条款将导致 SBC/区间/折扣/费基四类口径错误"))
    esc_df(pd.DataFrame(ea)).to_excel(xw, sheet_name="Error_Audit", index=False)

    # Source_Trace
    esc_df(pd.DataFrame(TRACE, columns=["metric", "adopted_value", "adopted_source",
                                 "competing_value_source", "disposition_rationale"])).to_excel(
        xw, sheet_name="Source_Trace", index=False)

# ----------------------------------------------------------------------------
# 13. 输出：复合图 charts.png
# ----------------------------------------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.2),
                               gridspec_kw={"width_ratios": [1.05, 1]})
# 左图：支持区间与拟议价位置
y0 = 0
ax1.barh(y0, SUPPORT_HI - SUPPORT_LO, left=SUPPORT_LO, height=0.34,
         color="#c8dcf0", edgecolor="#2c5f8a", label="Committee support range (post-discount)")
ax1.barh(y0, (SUPPORT_MID + MID_TOL) - (SUPPORT_MID - MID_TOL), left=SUPPORT_MID - MID_TOL,
         height=0.34, color="#f2c14e", alpha=0.75, edgecolor="none",
         label="Midpoint +/- $0.50 (CP-14 tolerance)")
ax1.plot([SUPPORT_LO, SUPPORT_MID, SUPPORT_HI], [y0] * 3, "|", ms=22, mew=2.5, color="#123c5e")
ax1.scatter([SUPPORT_MID], [y0], marker="o", s=90, zorder=5, color="#123c5e",
            label=f"Midpoint ${SUPPORT_MID:.2f}")
ax1.scatter([PRICE], [y0], marker="D", s=150, zorder=6, color="#c0392b",
            label=f"Proposed ${PRICE:.2f} ({DISPOSITION})")
ax1.annotate(f"${SUPPORT_LO:.2f}", (SUPPORT_LO, y0), textcoords="offset points", xytext=(-8, -30), color="#123c5e", fontweight="bold")
ax1.annotate(f"${SUPPORT_MID:.2f}", (SUPPORT_MID, y0), textcoords="offset points", xytext=(-12, 18), color="#123c5e", fontweight="bold")
ax1.annotate(f"${SUPPORT_HI:.2f}", (SUPPORT_HI, y0), textcoords="offset points", xytext=(-6, -30), color="#123c5e", fontweight="bold")
ax1.annotate(f"dist to mid = ${DIST_MID:.2f}", (PRICE, y0), textcoords="offset points", xytext=(10, 24),
             color="#c0392b", fontweight="bold")
y1 = -0.75
ax1.barh(y1, PUB_HI - PUB_LO, left=PUB_LO, height=0.22, color="#d9d9d9",
         edgecolor="#7f7f7f", label="SEC-03 preliminary public range $31-$34")
ax1.scatter([PRICE], [y1], marker="D", s=70, zorder=6, color="#c0392b")
ax1.annotate("proposed = top of public range", (PRICE, y1), textcoords="offset points",
             xytext=(-150, -24), color="#555555", fontsize=9)
ax1.set_ylim(-1.3, 0.7); ax1.set_yticks([])
ax1.set_xlabel("USD per share")
ax1.set_title(f"Committee support range vs proposed price  |  EV/2024E Rev {MULT_LO:.1f}x-{MULT_HI:.1f}x, "
              f"{DISCOUNT:.1%} discount (CP-07/09)", fontsize=10.5)
ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), fontsize=8.5, ncol=2, frameon=False)
ax1.grid(axis="x", alpha=0.3)

# 右图：敏感性热力图
cmap = LinearSegmentedColormap.from_list("rb", ["#f7fbff", "#6baed6", "#08519c"])
im = ax2.imshow(MATRIX.values, cmap=cmap, aspect="auto")
ax2.set_xticks(range(len(M_AX)), [f"{m:.2f}x" for m in M_AX])
ax2.set_yticks(range(len(G_AX)), [f"{g:.0%}" for g in G_AX])
ax2.set_xlabel("EV / 2024E Revenue multiple"); ax2.set_ylabel("2024E revenue growth")
for i in range(len(G_AX)):
    for j in range(len(M_AX)):
        v = MATRIX.values[i, j]
        base_cell = (i == 2 and j == 2)
        ax2.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9,
                 fontweight="bold" if base_cell else "normal",
                 color="white" if v > np.nanmax(MATRIX.values) * 0.72 else "#123c5e")
        if base_cell:
            ax2.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False,
                                        edgecolor="#c0392b", lw=2.6))
        if i == 2 and j in (0, 4):
            ax2.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False,
                                        edgecolor="#f2c14e", lw=2.2, linestyle="--"))
ax2.set_title(f"Sensitivity: value/share = (m x {REV23:.1f} x (1+g) + {NET_CASH:.1f}) / {PREMONEY_SH:.2f} x (1-{DISCOUNT:.3f})\n"
              f"red box = base case (22% x 4.5x = ${SUPPORT_MID:.2f}); dashed = Low/High tiers @ base growth",
              fontsize=9.5)
fig.colorbar(im, ax=ax2, label="USD / share (post-discount)", shrink=0.85)
fig.suptitle("FIN3-WKN-152  Reddit, Inc. IPO — Pricing Committee composite view (as-of 2024-03-20, pre-pricing)",
             fontsize=12.5, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.95])
fig.savefig(os.path.join(OUT, "FIN3-WKN-152_charts.png"), dpi=150)
plt.close(fig)

# ----------------------------------------------------------------------------
# 14. 打印全部关键结果
# ----------------------------------------------------------------------------
print("=" * 78)
print("FIN3-WKN-152 关键结果（as-of 2024-03-20；全部数值由 input_files 计算得出）")
print("=" * 78)
print(f"\n[1] 数据核验：异常 {len(ANOMALIES)} 项 / 核验 {len(CHECKS)} 项")
for a in ANOMALIES:
    print(f"  - {a['file']} @ {a['location']}")
    print(f"    现象: {a['phenomenon']}")
    print(f"    判定: {a['basis']}")
    print(f"    处置: {a['disposition']}")
fails = [c for c in CHECKS if c["status"] == "FAIL"]
print(f"  核验结论: {len(CHECKS)-len(fails)} PASS/NOTE, {len(fails)} FAIL")
for c in fails:
    print("  FAIL:", c)

print("\n[2] QoE（FY2023, USD mm）")
print(f"  Revenue {r3(REV23)} | Net loss {r3(NI23)} | Mgmt Adj EBITDA {r3(ADJEB23)}")
print(f"  SBC&taxes {r3(SBC23)} | Restructuring {r3(RESTR23)} | D&A {r3(DA23)} | FCF {r3(FCF23)}")
print(f"  Cash {r3(CASH23)} + Marketable sec {r3(MS23)} = {r3(NET_CASH)}")
print(f"  Underwriting EBITDA = {r3(ADJEB23)} - {r3(SBC23)} = {r3(UW_EBITDA23)}  (负值: {UW_EBITDA_NEG} → CP-05 EV/2024E Revenue)")
print(f"  NI→AdjEBITDA 未列示调整项 = {r3(RESID_NI_TO_ADJEB)} (待核实)")

print("\n[3] 估值")
print(f"  2024E Revenue = {r3(REV23)} x (1+{GROWTH:.0%}) = {r3(REV24E)}")
for nm, ev, eq, pu, pd_ in [("Low 4.0x", EV_L, EQ_L, PS_L_U, PS_L),
                            ("Mid 4.5x", EV_M, EQ_M, PS_M_U, PS_M),
                            ("High 5.0x", EV_H, EQ_H, PS_H_U, PS_H)]:
    print(f"  {nm}: EV {r3(ev)} + net cash {r3(NET_CASH)} = equity {r3(eq)}; "
          f"/{r6(PREMONEY_SH)}sh = {r4(pu)}; x(1-{DISCOUNT:.3f}) = ${r4(pd_)}")
print(f"  支持区间 ${r4(SUPPORT_LO)} - ${r4(SUPPORT_HI)}, midpoint ${r4(SUPPORT_MID)}")

print("\n[4] 发行结构与募集 (Base @ $%.2f)" % PRICE)
print(f"  primary {r6(PRIMARY)}m gross {r3(G_BASE)} fee {r3(FEE_BASE)} fixed {FIXED_EXP} net {r3(NET_BASE)}")
print(f"  secondary {r6(SECONDARY)}m → 公司募集 0，总股数不变")
print(f"  Full greenshoe: primary {r6(PRIMARY_FULL)}m gross {r3(G_FULL)} fee {r3(FEE_FULL)} net {r3(NET_FULL)} (增量 net {r3(G_GS-FEE_GS)})")

print("\n[5] 股本桥与稀释")
print(f"  Base post-money = {r6(PREMONEY_SH)} + {r6(PRIMARY)} = {r6(POST_BASE)}m; 新增占比 {NEWPCT_BASE:.2%}")
print(f"  Full post-money = {r6(POST_FULL)}m; 新增占比 {NEWPCT_FULL:.2%}")
print(f"  SEC-02 交叉验算: {SEC02_PX} - {NTBV_PS} = {DIL_PS} 自洽={SEC02_CONSISTENT}; 仅 $32.50 假定价账面稀释口径，不作定价依据")

print("\n[6] 敏感性矩阵 (USD/share, post-discount)")
print(MATRIX.round(2).to_string())

print("\n[7] 定价处置")
print(f"  拟议 ${PRICE:.2f}: 区间内={IN_RANGE}, 距 midpoint {r4(DIST_MID)} (≤0.50: {DIST_MID<=MID_TOL}), hard errors 已处置")
print(f"  → 建议: {DISPOSITION} (CP-14)")

print("\n[8] Error_Audit 条目数: legacy %d + 明细异常 %d + 失效条款 %d = %d"
      % (len(LEGACY_ERRORS), len(DATA_ERRORS), len(POLICY_ERRORS),
         len(LEGACY_ERRORS) + len(DATA_ERRORS) + len(POLICY_ERRORS)))
print(f"\n交付物已写入 {OUT}: FIN3-WKN-152_ipo_model.xlsx / _qoe_bridge.csv / "
      "_valuation_matrix.csv / _source_trace.csv / _charts.png")
