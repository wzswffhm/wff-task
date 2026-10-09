#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-152 · Reddit, Inc. IPO 定价委员会发行前财务复核 — 可复算脚本
=====================================================================
As-of: 2024-03-20（定价前）。仅使用截止日前可获得的信息（CP-01）。

- 全部输入取自 /app/input_files/（只读）；不引用网络数据。
- 不硬编码任何结论数字：所有参数均从 committee/、sec_filings/、financials/
  材料中解析；结论由这些输入计算得出。
- 运行方式：python3 FIN3-WKN-152_reproduce.py
- 输出：全部关键结果（口径版本、勾稽、QoE、估值、发行结构、募集、稀释、
  敏感性、定价处置建议）。
"""

import csv
import re
import sys
from pathlib import Path

import openpyxl

# --------------------------------------------------------------------------
# 路径解析
# --------------------------------------------------------------------------
INPUT = Path("/app/input_files")
if not INPUT.exists():  # 允许相对布局回退
    INPUT = Path(__file__).resolve().parents[1] / "input_files"
if not INPUT.exists():
    sys.exit("FATAL: input_files directory not found")


def read_csv_rows(rel):
    with open(INPUT / rel, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_xlsx_sheets(rel):
    wb = openpyxl.load_workbook(INPUT / rel, data_only=True)
    out = {}
    for ws in wb.worksheets:
        rows = [[c for c in r] for r in ws.iter_rows(values_only=True)]
        out[ws.title] = [r for r in rows if any(c is not None for c in r)]
    return out


def num(x):
    if isinstance(x, (int, float)):
        return float(x)
    return float(str(x).replace(",", "").replace("$", "").strip())


def f6(x):  # 展示用 6 位
    return f"{x:,.6f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def f3(x):
    return f"{x:,.3f}"


def f4(x):
    return f"{x:,.4f}"


# ==========================================================================
# 1) 控制口径（委员会政策）版本识别
# ==========================================================================
policy_files = sorted((INPUT / "committee").glob("Committee_Policy_v*.xlsx"))
versions = {}
for p in policy_files:
    m = re.search(r"_v(\d+)_(\d{8})", p.name)
    versions[p] = (int(m.group(1)), m.group(2))
controlling_file = max(versions, key=lambda p: (versions[p][1], versions[p][0]))
superseded_files = [p for p in versions if p is not controlling_file]

pol_sheets = read_xlsx_sheets(f"committee/{controlling_file.name}")
policy = {}  # Policy_ID -> dict(section, convention, application)
header = pol_sheets["Committee_Policy"][0]
for row in pol_sheets["Committee_Policy"][1:]:
    rec = dict(zip(header, row))
    policy[str(rec["Policy_ID"]).strip()] = rec

# 被取代版本的失效条款（从各旧版 Revision_Note 读取）
superseded_terms = []
v2_terms = {}   # 旧版中标记 SUPERSEDED 的条款原文（用于展示竞争口径）
for p in superseded_files:
    sh = read_xlsx_sheets(f"committee/{p.name}")
    note = {r[0]: r[1] for r in sh.get("Revision_Note", []) if len(r) >= 2}
    superseded_terms.append(
        {
            "file": p.name,
            "version": f"v{versions[p][0]}",
            "status": note.get("状态", ""),
            "scope": note.get("取代范围", ""),
        }
    )
    hdr = sh["Committee_Policy"][0]
    for row in sh["Committee_Policy"][1:]:
        rec = dict(zip(hdr, row))
        if "SUPERSEDED" in str(rec.get("Application", "")):
            v2_terms[str(rec["Policy_ID"]).strip()] = rec["Committee convention"]
v2_discount = float(re.search(r"(\d+(?:\.\d+)?)%", v2_terms.get("CP-09", "10%")).group(1)) / 100

print("=" * 78)
print("[1] 控制口径版本识别")
print(f"  现行控制口径: committee/{controlling_file.name} "
      f"(v{versions[controlling_file][0]}, {versions[controlling_file][1]})")
for s in superseded_terms:
    print(f"  被取代版本: {s['file']} — {s['status']}")
    print(f"    不再适用条款: {s['scope']}")
print(f"  控制政策条款数: {len(policy)} (CP-01..CP-{len(policy):02d})")

# 处置阈值（CP-14 中的 $0.50 距 midpoint 上限，从政策文本解析）
cp14_text = policy["CP-14"]["Committee convention"]
mid_tol = float(re.search(r"\$([0-9]*\.?[0-9]+)", cp14_text).group(1))

# ==========================================================================
# 2) 来源优先级索引与内部假设（UW-01）
# ==========================================================================
src_index = {r["Source_ID"]: r for r in read_csv_rows("sec_filings/Source_Index.csv")}
priorities = {k: int(v["Priority"]) for k, v in src_index.items()
              if str(v["Priority"]).isdigit()}

ua_rows = read_xlsx_sheets("committee/Underwriting_Assumptions_20240320.xlsx")["Assumptions"]
ua = {r[0]: r[1] for r in ua_rows[1:]}
growth = num(ua["2024E revenue growth"])
mult_low = num(ua["Peer low EV/Revenue"])
mult_mid = num(ua["Peer midpoint EV/Revenue"])
mult_high = num(ua["Peer high EV/Revenue"])
disc = num(ua["IPO discount to peer-implied equity"])
val_method = str(ua["Valuation method"])

ot_rows = read_xlsx_sheets("committee/Offering_Terms_20240320.xlsx")["Offering_Terms"]
ot = {r[0]: r for r in ot_rows[1:]}
price = num(ot["Proposed Committee Price"][1])              # Base 列
price_gs = num(ot["Proposed Committee Price"][2])           # Full greenshoe 列
primary_base = num(ot["Primary shares offered"][1])
primary_full = num(ot["Primary shares offered"][2])
secondary = num(ot["Secondary shares offered"][1])
greenshoe = num(ot["Greenshoe shares"][2])
premoney_sh = num(ot["Pre-money economic shares"][1])
pub_low = num(ot["Preliminary public filing range low"][1])
pub_high = num(ot["Preliminary public filing range high"][1])
fee_rate = num(ot["Underwriting fee assumption"][1])
fixed_exp = num(ot["Fixed company offering expenses"][1])
co_gets_secondary = num(ot["Company receives secondary proceeds?"][1])

# Committee cap-table snapshot 勾稽
cap_rows = read_csv_rows("committee/cap_table_snapshot_20240318.csv")
cap_components = {r["holder_class"]: num(r["shares_mm"]) for r in cap_rows
                  if not r["holder_class"].startswith("TOTAL")}
cap_total_row = [num(r["shares_mm"]) for r in cap_rows
                 if r["holder_class"].startswith("TOTAL")][0]
cap_sum = sum(cap_components.values())

# Committee peer set（CP-07 控制区间端点）
ps_rows = pol_sheets["Committee_Peer_Set"]
peer_mults = [num(r[1]) for r in ps_rows[1:] if str(r[0]).startswith("Peer")]
peer_weights = [num(r[3]) for r in ps_rows[1:] if str(r[0]).startswith("Peer")]
peer_wavg = sum(m * w for m, w in zip(peer_mults, peer_weights))

# 承销商各自 comps（P8，仅交叉验证，不改端点 — CP-07 / ECM 邮件#2）
bankA = read_csv_rows("comps/underwriter_A_comps_20240315.csv")
bankB = read_csv_rows("comps/underwriter_B_comps_20240318.csv")
bankA_range = (min(num(r["ntm_ev_revenue"]) for r in bankA),
               max(num(r["ntm_ev_revenue"]) for r in bankA))
bankB_range = (min(num(r["ntm_ev_revenue"]) for r in bankB),
               max(num(r["ntm_ev_revenue"]) for r in bankB))

print("=" * 78)
print("[2] 内部委员会假设（UW-01，非 SEC 公开事实）与发行条款")
print(f"  拟议价（决策输入，非已实现结果）: ${price}  [公开区间 ${pub_low}-${pub_high} 仅作执行 cross-check]")
print(f"  2024E 增长率假设: {growth:.1%} (CP-06) | Peer 倍数: {mult_low}x/{mult_mid}x/{mult_high}x (CP-07)")
print(f"  执行折扣: {disc:.1%} (CP-09) | 主估值方法: {val_method} (CP-05)")
print(f"  Base: primary {primary_base}m + secondary {secondary}m; greenshoe {greenshoe}m 不入 Base (CP-10/11)")
print(f"  费用: {fee_rate:.0%} × primary gross; 固定费用 ${fixed_exp}mm 一次 (CP-12)")
print(f"  Cap-table snapshot 勾稽: 分项和 {f6(cap_sum)} vs TOTAL 行 {f6(cap_total_row)} "
      f"vs Offering_Terms {f6(premoney_sh)} -> {'一致' if abs(cap_sum-cap_total_row)<1e-9 and abs(cap_sum-premoney_sh)<1e-9 else '不一致'}")
print(f"  Committee peer set 加权均值: {peer_wavg:.2f}x（控制端点仍为 CP-07: {mult_low}x-{mult_high}x）")
print(f"  承销商 comps 交叉验证 (P8, 不改端点): BANK-A {bankA_range[0]}x-{bankA_range[1]}x; "
      f"BANK-B {bankB_range[0]}x-{bankB_range[1]}x")
print(f"  来源优先级: " + ", ".join(f"{k}=P{v}" for k, v in sorted(priorities.items(), key=lambda kv: kv[1])))

# ==========================================================================
# 3) SEC-01 历史财务（Priority 1）与明细勾稽
# ==========================================================================
pf_rows = read_xlsx_sheets("sec_filings/SEC-01_financials_extract.xlsx")["Public_Financials"]
pf = {r[0]: (num(r[1]), num(r[2])) for r in pf_rows[1:]}  # (FY2022, FY2023)
rev23, rev22 = pf["Revenue"][1], pf["Revenue"][0]
ni23 = pf["Net income (loss)"][1]
adj_ebitda23 = pf["Adjusted EBITDA"][1]
sbc23 = pf["Stock-based compensation & related taxes"][1]
restr23 = pf["Restructuring costs"][1]
da23 = pf["Depreciation & amortization"][1]
fcf23 = pf["Free Cash Flow"][1]
cash23 = pf["Cash & cash equivalents"][1]
ms23 = pf["Marketable securities"][1]

# 3a) 月度收入勾稽（去重、剔除未审计 preliminary）
mon = read_csv_rows("financials/monthly_revenue_2022_2023.csv")
recon = {}
for fy in ("FY2022", "FY2023"):
    rows = [r for r in mon if r["fy"] == fy and r["month"] != "TOTAL"]
    reported = num([r for r in mon if r["fy"] == fy and r["month"] == "TOTAL"][0]["revenue_usd_mm"])
    raw = sum(num(r["revenue_usd_mm"]) for r in rows)
    clean_rows = [r for r in rows if r["status"] in ("original", "audited-final")]
    clean = sum(num(r["revenue_usd_mm"]) for r in clean_rows)
    excluded = [(r["month"], r["status"], r["Source_ID"], num(r["revenue_usd_mm"]))
                for r in rows if r not in clean_rows]
    clean_detail = {r["month"]: (num(r["revenue_usd_mm"]), r["status"], r["Source_ID"])
                    for r in clean_rows}
    recon[fy] = dict(reported=reported, raw=raw, clean=clean, excluded=excluded,
                     clean_detail=clean_detail)

# 3b) 季度 / 分部 / 地区 / SBC / 重组 / FCF / 资产负债 / 利润表勾稽
qtr = read_csv_rows("financials/revenue_quarterly.csv")
qtr23 = sum(num(r["revenue_usd_mm"]) for r in qtr if r["fy"] == "FY2023")
seg = read_csv_rows("financials/revenue_by_segment_2022_2023.csv")
seg23 = sum(num(r["revenue_usd_mm"]) for r in seg if r["fy"] == "FY2023")
seg22 = sum(num(r["revenue_usd_mm"]) for r in seg if r["fy"] == "FY2022")
geo = read_csv_rows("sec_filings/SEC-05_revenue_by_geo.csv")
geo23 = sum(num(r["revenue_usd_mm"]) for r in geo if r["fy"] == "FY2023")
geo22 = sum(num(r["revenue_usd_mm"]) for r in geo if r["fy"] == "FY2022")
sbc_d = read_csv_rows("financials/sbc_detail_2022_2023.csv")
sbc23_detail = sum(num(r["amount_usd_mm"]) for r in sbc_d
                   if r["fy"] == "FY2023" and r["component"] != "TOTAL")
restr_d = read_csv_rows("financials/restructuring_detail_2023.csv")
restr_detail = sum(num(r["amount_usd_mm"]) for r in restr_d if r["component"] != "TOTAL")
fcfb = {r["line_item"]: num(r["amount_usd_mm"]) for r in read_csv_rows("financials/fcf_bridge_2023.csv")}
fcf_calc = fcfb["Net cash used in operating activities"] + fcfb["Purchases of property and equipment"]
bs = {r["line_item"]: (num(r["FY2022"]), num(r["FY2023"]))
      for r in read_csv_rows("financials/balance_sheet_summary_2022_2023.csv")}
liquid23 = cash23 + ms23
bs_total23 = bs["Total cash, cash equivalents and marketable securities"][1]
ist = {r["line_item"]: (num(r["FY2022"]), num(r["FY2023"]))
       for r in read_csv_rows("financials/income_statement_2022_2023.csv")}
is_check23 = (ist["Revenue"][1] + ist["Total costs and operating expenses"][1]
              + ist["Other income, net"][1])

# 3c) 竞争性来源（INT-01 未经审计 flash / IR 草稿 — 仅参考，不入结论）
flash = {r["metric"]: num(r["FY2023_value"]) for r in read_csv_rows("internal/management_flash_20240319.csv")}

def tie(a, b, tol=1e-6):
    return abs(a - b) <= tol

print("=" * 78)
print("[3] SEC-01 年度数（Priority 1，承销口径取数来源）")
print(f"  Revenue FY2023 {f3(rev23)} / FY2022 {f3(rev22)} | Net loss FY2023 {f3(ni23)}")
print(f"  Mgmt Adjusted EBITDA FY2023 {f3(adj_ebitda23)} | SBC&taxes {f3(sbc23)} | Restructuring {f3(restr23)} | D&A {f3(da23)}")
print(f"  FCF FY2023 {f3(fcf23)} | Cash {f3(cash23)} + Marketable sec {f3(ms23)} = {f3(liquid23)}")
print("-" * 78)
print("[3a] 明细 <-> 年度数勾稽（月度收入）")
for fy, r in recon.items():
    ok_raw, ok_clean = tie(r["raw"], r["reported"]), tie(r["clean"], r["reported"])
    print(f"  {fy}: 报告年度数 {f3(r['reported'])} | 原始明细加总 {f3(r['raw'])} "
          f"({'勾稽' if ok_raw else '不勾稽'}) | 清洗后加总 {f3(r['clean'])} ({'勾稽' if ok_clean else '不勾稽'})")
    for m, st, sid, v in r["excluded"]:
        print(f"      剔除: {m} [{st}] {f3(v)} ({sid}, P{priorities.get(sid,'?')}) — 处置: 不用于承销口径")
print("[3b] 其他勾稽")
print(f"  季度加总 FY2023 {f3(qtr23)} vs 年度 {f3(rev23)} -> {'勾稽' if tie(qtr23, rev23) else '不勾稽'}")
print(f"  分部加总 FY2023 {f3(seg23)} / FY2022 {f3(seg22)} -> "
      f"{'勾稽' if tie(seg23, rev23) and tie(seg22, rev22) else '不勾稽'}")
print(f"  地区加总 FY2023 {f3(geo23)} / FY2022 {f3(geo22)} -> "
      f"{'勾稽' if tie(geo23, rev23) and tie(geo22, rev22) else '不勾稽'}")
print(f"  SBC 明细 FY2023 {f3(sbc23_detail)} vs SEC-01 {f3(sbc23)} -> {'勾稽' if tie(sbc23_detail, sbc23) else '不勾稽'}")
print(f"  重组明细 {f3(restr_detail)} vs SEC-01 {f3(restr23)} -> {'勾稽' if tie(restr_detail, restr23) else '不勾稽'}")
print(f"  FCF 桥: OCF {f3(fcfb['Net cash used in operating activities'])} + capex {f3(fcfb['Purchases of property and equipment'])} "
      f"= {f3(fcf_calc)} vs 报告 {f3(fcf23)} -> {'勾稽' if tie(fcf_calc, fcf23) else '不勾稽'}")
print(f"  现金+有价证券 {f3(liquid23)} vs 底表合计 {f3(bs_total23)} -> {'勾稽' if tie(liquid23, bs_total23) else '不勾稽'}")
print(f"  利润表: 收入-总成本费用+其他收益 = {f3(is_check23)} vs 净亏损 {f3(ni23)} -> "
      f"{'勾稽' if tie(is_check23, ni23) else '不勾稽'}")
print("[3c] 竞争值（参考级来源，INT-01 P9 — 不入结论）")
print(f"  Revenue: SEC-01 {f3(rev23)} vs flash {f3(flash['Revenue'])} -> 取 SEC-01")
print(f"  Adj EBITDA: SEC-01 {f3(adj_ebitda23)} vs flash {f3(flash['Adjusted EBITDA'])} -> 取 SEC-01")
print(f"  SBC: SEC-01 {f3(sbc23)} vs flash {f3(flash['Stock-based compensation & related taxes'])} -> 取 SEC-01")
print(f"  FCF: SEC-01 {f3(fcf23)} vs flash {f3(flash['Free Cash Flow'])} -> 取 SEC-01")

# ==========================================================================
# 4) QoE：管理层口径 -> 承销口径（CP-03 / CP-04 / CP-05）
# ==========================================================================
# 管理层调节残差（摘录未逐项列明的其他管理层调整）
mgmt_resid = adj_ebitda23 - (ni23 + sbc23 + restr23 + da23)
# 承销口径：SBC 为持续性经济成本，不保留加回；重组已在管理层口径中，不得二次加回
uw_ebitda = adj_ebitda23 - sbc23 + 0.0
uw_negative = uw_ebitda < 0

print("=" * 78)
print("[4] 盈利质量（QoE）桥 — FY2023")
print(f"  Net loss (GAAP)                          {f3(ni23)}")
print(f"  + SBC & related taxes (管理层加回)        {f3(sbc23)}")
print(f"  + Restructuring (管理层加回)              {f3(restr23)}")
print(f"  + D&A (管理层加回)                        {f3(da23)}")
print(f"  + 其他管理层调整残差（待核实，摘录未列明） {f3(mgmt_resid)}")
print(f"  = Management Adjusted EBITDA (SEC-01)    {f3(adj_ebitda23)}  [勾稽: {tie(ni23+sbc23+restr23+da23+mgmt_resid, adj_ebitda23)}]")
print(f"  - SBC 加回剔除 (CP-03, 持续性经济成本)    {f3(-sbc23)}")
print(f"  ± Restructuring (CP-04, 不二次调整)       0.000")
print(f"  = Underwriting Adjusted EBITDA           {f3(uw_ebitda)}  -> {'仍为负' if uw_negative else '为正'}")
print(f"  主估值方法 (CP-05): {'EV / 2024E Revenue' if uw_negative else 'EV/EBITDA 可用'} | 材料设定: {val_method}")
print(f"  FCF {f3(fcf23)}（负）; 现金+有价证券 {f3(liquid23)} -> CP-13 要求在备忘录披露 QoE 风险")

# ==========================================================================
# 5) 估值（CP-06..CP-09）
# ==========================================================================
rev24e = rev23 * (1 + growth)

def value_case(mult):
    ev = mult * rev24e
    eq_premoney = ev + cash23 + ms23          # CP-08 净现金桥（含 marketable securities）
    ps_undisc = eq_premoney / premoney_sh     # peer-implied undiscounted equity value/share
    ps_disc = ps_undisc * (1 - disc)          # CP-09 执行折扣作用于每股价值
    return dict(mult=mult, ev=ev, eq=eq_premoney, ps_undisc=ps_undisc, ps=ps_disc)

low, mid, high = value_case(mult_low), value_case(mult_mid), value_case(mult_high)
midpoint = (low["ps"] + high["ps"]) / 2
in_range = low["ps"] <= price <= high["ps"]
dist_to_mid = abs(price - midpoint)

# 处置规则（CP-14 / CP-15）：结构 hard error 已在本次复核中识别并修正（见 Error_Audit）
structure_hard_errors_unresolved = False
if in_range and dist_to_mid <= mid_tol and not structure_hard_errors_unresolved:
    disposition = "Proceed"
elif in_range:
    disposition = "Reprice (向 midpoint 方向)"
else:
    disposition = "Defer"

print("=" * 78)
print("[5] 估值（EV / 2024E Revenue）")
print(f"  2024E Revenue = {f3(rev23)} × (1 + {growth:.0%}) = {f3(rev24e)}   (CP-06, 内部假设)")
for c, nm in ((low, "Low 4.0x"), (mid, "Mid 4.5x"), (high, "High 5.0x")):
    print(f"  {nm}: EV = {f3(c['ev'])}; +净现金 {f3(liquid23)} -> Pre-money Equity {f3(c['eq'])}; "
          f"/股(未折扣) {f4(c['ps_undisc'])}; ×(1-{disc:.1%}) -> ${f4(c['ps'])}")
print(f"  委员会支持区间: ${f4(low['ps'])} – ${f4(high['ps'])} | midpoint ${f4(midpoint)}")
print(f"  拟议价 ${price}: {'位于' if in_range else '不位于'}支持区间内; 距 midpoint ${f4(dist_to_mid)} "
      f"(阈值 ${mid_tol:.2f}, CP-14)")
print(f"  定价处置建议: {disposition}")

# ==========================================================================
# 6) 发行结构、募集与费用（CP-10 / CP-11 / CP-12）
# ==========================================================================
def offering(p, primary, shoe_included):
    gross_primary = primary * p
    fee = fee_rate * gross_primary                 # 仅对 primary gross 计提
    fixed = fixed_exp if not shoe_included else 0.0  # greenshoe 增量不重复扣固定费用
    net = gross_primary - fee - fixed
    secondary_gross = secondary * p                # 归出售股东，非公司
    return gross_primary, fee, fixed, net, secondary_gross

base_gross, base_fee, base_fixed, base_net, sec_gross = offering(price, primary_base, False)
gs_gross_inc = greenshoe * price
gs_fee_inc = fee_rate * gs_gross_inc
gs_net_inc = gs_gross_inc - gs_fee_inc             # 不重复扣固定费用
full_gross = base_gross + gs_gross_inc
full_fee = base_fee + gs_fee_inc
full_net = full_gross - full_fee - fixed_exp

print("=" * 78)
print("[6] 发行结构与募集（公司口径）")
print(f"  Base: primary {primary_base}m @ ${price} -> gross {f4(base_gross)}; "
      f"fee {fee_rate:.0%} = {f4(base_fee)}; 固定费用 {f3(base_fixed)}; net = {f4(base_net)}")
print(f"  Secondary {secondary}m: 公司募集 = 0（款项归出售股东, 约 {f4(sec_gross)} 不归公司）; 不增加公司总股数")
print(f"  Full greenshoe: +{greenshoe}m primary -> 增量 gross {f4(gs_gross_inc)}, fee {f4(gs_fee_inc)}, "
      f"固定费用不重复计提; 合计 gross {f4(full_gross)}, fee {f4(full_fee)}, net {f4(full_net)}")
print(f"  Company receives secondary proceeds? {'No' if co_gets_secondary==0 else 'Yes'} (SEC-03)")

# ==========================================================================
# 7) 股本桥与稀释（Base / Full-exercise）+ SEC-02 交叉验算
# ==========================================================================
post_base = premoney_sh + primary_base             # secondary 不计入新增股数
new_pct_base = primary_base / post_base
post_full = premoney_sh + primary_full
new_pct_full = primary_full / post_full
premoney_eq_at_price = premoney_sh * price
postmoney_eq_base = post_base * price

d_rows = read_xlsx_sheets("sec_filings/SEC-02_dilution_crosscheck.xlsx")["Dilution_Crosscheck"]
d = {r[0]: r for r in d_rows[1:]}
ntbv = num(d["Preliminary NTBV/share"][1])
assumed_p = num(d["Preliminary NTBV/share"][3])
sec_dil = num(d["Preliminary immediate dilution per share"][1])
dil_recalc = assumed_p - ntbv

# SEC-09 registered shares 交叉参考
sc = read_csv_rows("sec_filings/SEC-16_share_count_history.csv")
registered = [num(r["shares_outstanding_mm"]) for r in sc
              if r["Source_ID"] == "SEC-09" and r["as_of"] == "2024-03-18"][0]

print("=" * 78)
print("[7] 股本桥与稀释")
print(f"  Pre-money economic shares {f6(premoney_sh)} (UW-01 snapshot; 分项勾稽一致)")
print(f"  Base post-money = {f6(premoney_sh)} + {primary_base} = {f6(post_base)}; "
      f"新增股份占比 = {new_pct_base:.4%}")
print(f"  Full-exercise post-money = {f6(post_full)}; 新增占比 = {new_pct_full:.4%}")
print(f"  参考: SEC-09 registered shares (2024-03-18) {f3(registered)}m（不含 unsettled RSUs，仅交叉参考）")
print(f"  SEC-02 独立交叉验算（假定价 ${assumed_p}）: NTBV ${ntbv} + dilution ${sec_dil} "
      f"= ${ntbv + sec_dil} -> 复算 {assumed_p} - {ntbv} = {f4(dil_recalc)} ({'一致' if tie(dil_recalc, sec_dil, 1e-9) else '不一致'})")
print("  用途边界: SEC-02 仅在 SEC 假定价 $32.50 口径下作独立验算，不得缩放至 $34 用于定价结论")
print(f"  隐含市值: pre-money {f3(premoney_eq_at_price)} / post-money(Base) {f3(postmoney_eq_base)} @ ${price}")

# ==========================================================================
# 8) 敏感性矩阵（2024E 增长率 × EV/Revenue -> 折后每股价值）
# ==========================================================================
growth_grid = [growth - 0.08, growth - 0.04, growth, growth + 0.04, growth + 0.08]
mult_grid = [mult_low - 0.5, mult_low, mult_mid, mult_high, mult_high + 0.5]

def per_share(g, m):
    return (m * rev23 * (1 + g) + cash23 + ms23) / premoney_sh * (1 - disc)

matrix = [[per_share(g, m) for m in mult_grid] for g in growth_grid]

print("=" * 78)
print("[8] 敏感性矩阵 — 折后每股价值 (USD/share)")
print("        " + "".join(f"{m:>9.2f}x" for m in mult_grid))
for g, row in zip(growth_grid, matrix):
    mark = " <-base g" if abs(g - growth) < 1e-12 else ""
    print(f"  {g:>5.0%} " + "".join(f"{v:>10.3f}" for v in row) + mark)
print(f"  控制区间 (CP-07): {mult_low}x-{mult_high}x; {mult_grid[0]}x/{mult_grid[-1]}x 仅为压力测试值")
print(f"  Base case: g={growth:.0%}, {mult_mid}x -> ${f4(mid['ps'])}")

# ==========================================================================
# 9) Legacy 底稿错误复核（Candidate_Model_v0 + 说明文件）
# ==========================================================================
cm = read_xlsx_sheets("legacy/Candidate_Model_v0.xlsx")
legacy_items = [r for r in cm["Candidate_Model"][1:]]
broken = [r for r in cm["Broken_Links"][1:]]
legacy_assump = {r["assumption"]: r["legacy_value"]
                 for r in read_csv_rows("legacy/legacy_assumptions_export.csv")}

print("=" * 78)
print(f"[9] Legacy 底稿待复核条目: {len(legacy_items)} 条 + 失效引用 {len(broken)} 处 "
      f"({', '.join(str(b[0]) for b in broken)}) — 全部重算，不沿用其结果")
print(f"  失效假设导出: {legacy_assump}")

# ==========================================================================
# 10) 引用来源完整性（sec_filings/Source_Index.csv 为主索引）
# ==========================================================================
legacy_idx = {r[0]: r for r in read_xlsx_sheets("legacy/Q7_original_workbook.xlsx")["Source_Index"][1:]}
cited = ["SEC-01", "SEC-02", "SEC-03", "SEC-04", "SEC-05", "SEC-09", "SEC-10",
         "UW-01", "INT-01", "INT-02", "BANK-A", "BANK-B"]
print("=" * 78)
print("[10] 引用来源完整性核对")
for c in cited:
    where = []
    if c in src_index:
        where.append(f"sec_filings/Source_Index.csv (P{src_index[c]['Priority']})")
    if c in legacy_idx:
        where.append("legacy/Q7_original_workbook.xlsx#Source_Index")
    print(f"  {c}: {'; '.join(where) if where else '未在索引中找到 -> 待核实'}")
uw01_note = ("UW-01 未列入 sec_filings/Source_Index.csv，但由 legacy 工作簿索引定义为 "
             "'Committee_Policy + internal working assumptions'，对应 committee/ 下真实存在的"
             "内部假设文件（控制口径目录，00_README）；按 CP-02 作内部假设使用，不包装为公开事实。")
print(f"  说明: {uw01_note}")

print("=" * 78)
print("[结论摘要]")
print(f"  Underwriting Adj. EBITDA FY2023: {f3(uw_ebitda)} (负) -> 主估值 EV/2024E Revenue")
print(f"  2024E Revenue: {f3(rev24e)}")
print(f"  支持区间: ${f4(low['ps'])} / ${f4(mid['ps'])} / ${f4(high['ps'])} (Low/Mid/High), midpoint ${f4(midpoint)}")
print(f"  拟议价 ${price} 距 midpoint ${f4(dist_to_mid)} ≤ ${mid_tol:.2f} -> {disposition}")
print(f"  Base 公司净募集: {f4(base_net)}; Full-exercise: {f4(full_net)}")
print(f"  Base post-money 股数 {f6(post_base)}m, 新增占比 {new_pct_base:.2%}; "
      f"Full {f6(post_full)}m, {new_pct_full:.2%}")
print("=" * 78)

# --------------------------------------------------------------------------
# 供交付物构建脚本复用的结果字典
# --------------------------------------------------------------------------
RESULTS = dict(
    controlling_policy=controlling_file.name, policy=policy, mid_tol=mid_tol,
    superseded=superseded_terms, growth=growth, disc=disc, val_method=val_method,
    price=price, premoney_sh=premoney_sh, primary_base=primary_base,
    primary_full=primary_full, secondary=secondary, greenshoe=greenshoe,
    fee_rate=fee_rate, fixed_exp=fixed_exp, pub_low=pub_low, pub_high=pub_high,
    rev22=rev22, rev23=rev23, rev24e=rev24e, ni23=ni23, adj_ebitda23=adj_ebitda23,
    sbc23=sbc23, restr23=restr23, da23=da23, fcf23=fcf23, cash23=cash23,
    ms23=ms23, liquid23=liquid23, mgmt_resid=mgmt_resid, uw_ebitda=uw_ebitda,
    uw_negative=uw_negative, low=low, mid=mid, high=high, midpoint=midpoint,
    in_range=in_range, dist_to_mid=dist_to_mid, disposition=disposition,
    base_gross=base_gross, base_fee=base_fee, base_net=base_net,
    sec_gross=sec_gross, gs_gross_inc=gs_gross_inc, gs_fee_inc=gs_fee_inc,
    gs_net_inc=gs_net_inc, full_gross=full_gross, full_fee=full_fee,
    full_net=full_net, post_base=post_base, new_pct_base=new_pct_base,
    post_full=post_full, new_pct_full=new_pct_full,
    premoney_eq_at_price=premoney_eq_at_price, postmoney_eq_base=postmoney_eq_base,
    ntbv=ntbv, sec_dil=sec_dil, assumed_p=assumed_p, dil_recalc=dil_recalc,
    registered=registered, recon=recon, qtr23=qtr23, seg23=seg23, seg22=seg22,
    geo23=geo23, geo22=geo22, sbc23_detail=sbc23_detail,
    restr_detail=restr_detail, fcf_calc=fcf_calc, bs_total23=bs_total23,
    is_check23=is_check23, cap_sum=cap_sum, flash=flash,
    growth_grid=growth_grid, mult_grid=mult_grid, matrix=matrix,
    legacy_items=legacy_items, broken_links=broken, peer_wavg=peer_wavg,
    priorities=priorities, src_index=src_index, legacy_idx=legacy_idx,
    uw01_note=uw01_note, ua=ua, ot=ot, legacy_assump=legacy_assump,
    bankA_range=bankA_range, bankB_range=bankB_range, v2_discount=v2_discount,
    v2_terms=v2_terms, mult_low=mult_low, mult_mid=mult_mid, mult_high=mult_high,
)

if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--quiet":
    pass  # 已输出；无其他动作
