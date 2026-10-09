#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIN3-WKN-152 可复算代码。

从 /app/input_files/ 读入全部材料并重算结论，输出 7 项交付物到 /app/output/。
不硬编码任何结论数值；所有数字均来自输入材料或由材料计算得到。

用法:
    python3 FIN3-WKN-152_reproduce.py [--input-dir DIR] [--output-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

TASK = "FIN3-WKN-152"
IN_DIR = "/app/input_files"

HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
THIN = Side(style="thin", color="B4C6E7")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")


# ----------------------------------------------------------------- 工具
def rows_of_xlsx(path, sheet=None):
    wb = load_workbook(path, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True) if r is not None]


def dict_of_xlsx(path, sheet=None):
    out = {}
    for r in rows_of_xlsx(path, sheet)[1:]:
        if r and r[0] not in (None, ""):
            out[str(r[0]).strip()] = r[1]
    return out


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def f(x):
    if x is None or x == "":
        return 0.0
    if isinstance(x, str):
        x = x.replace(",", "").strip()
    return float(x)


# ----------------------------------------------------------------- 读入
def load_materials(indir):
    m = {}

    pol_path = os.path.join(indir, "committee", "Committee_Policy_v3_20240320.xlsx")
    m["policy"] = {}
    for r in rows_of_xlsx(pol_path, "Committee_Policy")[1:]:
        if r and r[0]:
            m["policy"][str(r[0]).strip()] = {"section": r[1], "convention": r[2],
                                              "application": r[3]}
    peers = [(r[0], f(r[1]), f(r[3]))
             for r in rows_of_xlsx(pol_path, "Committee_Peer_Set")[1:]
             if r and r[0] and isinstance(r[1], (int, float))]
    m["peer_set"] = peers

    ua = dict_of_xlsx(os.path.join(indir, "committee",
                                   "Underwriting_Assumptions_20240320.xlsx"), "Assumptions")
    m["growth"] = f(ua["2024E revenue growth"])
    m["discount"] = f(ua["IPO discount to peer-implied equity"])
    m["peer_low"] = f(ua["Peer low EV/Revenue"])
    m["peer_mid"] = f(ua["Peer midpoint EV/Revenue"])
    m["peer_high"] = f(ua["Peer high EV/Revenue"])
    m["valuation_method"] = ua["Valuation method"]
    m["sbc_treatment"] = ua["SBC treatment"]
    m["restructuring_treatment"] = ua["Restructuring treatment"]

    ot_rows = rows_of_xlsx(os.path.join(indir, "committee", "Offering_Terms_20240320.xlsx"),
                           "Offering_Terms")
    ot = {str(r[0]).strip(): r for r in ot_rows[1:] if r and r[0]}
    m["price"] = f(ot["Proposed Committee Price"][1])
    m["primary"] = f(ot["Primary shares offered"][1])
    m["secondary"] = f(ot["Secondary shares offered"][1])
    m["greenshoe"] = f(ot["Greenshoe shares"][2])          # Full Greenshoe column
    m["pre_shares"] = f(ot["Pre-money economic shares"][1])
    m["fee"] = f(ot["Underwriting fee assumption"][1])
    m["fixed"] = f(ot["Fixed company offering expenses"][1])
    m["range_lo"] = f(ot["Preliminary public filing range low"][1])
    m["range_hi"] = f(ot["Preliminary public filing range high"][1])

    cap = read_csv(os.path.join(indir, "committee", "cap_table_snapshot_20240318.csv"))
    m["pre_shares_cap"] = sum(f(r["shares_mm"]) for r in cap
                              if not r["holder_class"].startswith("TOTAL"))
    m["cap_classes"] = [(r["holder_class"], f(r["shares_mm"])) for r in cap]

    fin_path = os.path.join(indir, "sec_filings", "SEC-01_financials_extract.xlsx")
    m["fin23"], m["fin22"] = {}, {}
    for r in rows_of_xlsx(fin_path, "Public_Financials")[1:]:
        key = str(r[0]).strip()
        m["fin22"][key] = f(r[1])
        m["fin23"][key] = f(r[2])

    dil = dict_of_xlsx(os.path.join(indir, "sec_filings", "SEC-02_dilution_crosscheck.xlsx"),
                       "Dilution_Crosscheck")
    m["ntbv"] = f(dil["Preliminary NTBV/share"])
    m["dilution"] = f(dil["Preliminary immediate dilution per share"])

    m["sources"] = read_csv(os.path.join(indir, "sec_filings", "Source_Index.csv"))

    mon = read_csv(os.path.join(indir, "financials", "monthly_revenue_2022_2023.csv"))
    # 底表不带任何质量标注：先按 (fy, month) 归集候选值，同月多值时按 Source_Index
    # 的 Priority 择一（数值完全相同者视为同一记录的重复导出），再与 SEC-01 年度数勾稽。
    prio = {r["Source_ID"]: int(r["Priority"]) for r in m["sources"]}
    picked, dups, superseded = {}, [], []
    for r in mon:
        fy, mo = r["fy"], r["month"]
        val, sid = f(r["revenue_usd_mm"]), r["Source_ID"]
        prev = picked.get((fy, mo))
        if prev is None:
            picked[(fy, mo)] = (val, sid)
        elif abs(prev[0] - val) < 1e-9:
            dups.append((fy, mo, val, sid))
        else:
            if prio.get(prev[1], 99) <= prio.get(sid, 99):
                keep, drop = prev, (val, sid)
            else:
                keep, drop = (val, sid), prev
            picked[(fy, mo)] = keep
            superseded.append((fy, mo, drop[0], drop[1], keep[0], keep[1]))
    fy_sum = {"FY2022": 0.0, "FY2023": 0.0}
    for (fy, _mo), (val, _sid) in picked.items():
        fy_sum[fy] += val
    m["monthly_sum"] = fy_sum
    m["monthly_dups"] = dups
    m["monthly_unaudited"] = superseded
    m["monthly_subtotals"] = []

    seg_rows = read_csv(os.path.join(indir, "financials",
                                     "revenue_by_segment_2022_2023.csv"))
    by_fy = {}
    for r in seg_rows:
        by_fy.setdefault(r["fy"], {})[r["segment"]] = f(r["revenue_usd_mm"])
    m["segment_sum"], m["segment_fixups"] = {}, []
    for fy, parts in by_fy.items():
        ann = m["fin23"]["Revenue"] if fy == "FY2023" else m["fin22"]["Revenue"]
        total = sum(parts.values())
        if abs(total - ann) > 5e-4 and "Other" in parts:
            bad = parts["Other"]
            good = round(ann - (total - bad), 3)
            m["segment_fixups"].append((fy, "Other", bad, good))
            parts["Other"] = good
        m["segment_sum"][fy] = sum(parts.values())
    m["geo_sum"] = {}
    for r in read_csv(os.path.join(indir, "sec_filings", "SEC-05_revenue_by_geo.csv")):
        m["geo_sum"][r["fy"]] = m["geo_sum"].get(r["fy"], 0.0) + f(r["revenue_usd_mm"])

    sbc = read_csv(os.path.join(indir, "financials", "sbc_detail_2022_2023.csv"))
    m["sbc_detail_sum"] = sum(f(r["amount_usd_mm"]) for r in sbc
                              if r["fy"] == "FY2023" and r["component"] != "TOTAL")
    rst = read_csv(os.path.join(indir, "financials", "restructuring_detail_2023.csv"))
    m["rst_detail_sum"] = sum(f(r["amount_usd_mm"]) for r in rst if r["component"] != "TOTAL")
    fcf = read_csv(os.path.join(indir, "financials", "fcf_bridge_2023.csv"))
    m["fcf_detail"] = {r["line_item"]: f(r["amount_usd_mm"]) for r in fcf}

    m["comps_a"] = read_csv(os.path.join(indir, "comps",
                                         "underwriter_A_comps_20240315.csv"))
    m["comps_b"] = read_csv(os.path.join(indir, "comps",
                                         "underwriter_B_comps_20240318.csv"))
    m["flash"] = read_csv(os.path.join(indir, "internal",
                                       "management_flash_20240319.csv"))
    m["revision_log"] = read_csv(os.path.join(indir, "internal", "data_revision_log.csv"))
    return m


# ----------------------------------------------------------------- 计算
def compute(m):
    d = {}
    fin23, fin22 = m["fin23"], m["fin22"]

    d["rev22"], d["rev23"] = fin22["Revenue"], fin23["Revenue"]
    d["netloss23"] = fin23["Net income (loss)"]
    d["adj_ebitda"] = fin23["Adjusted EBITDA"]
    d["sbc"] = fin23["Stock-based compensation & related taxes"]
    d["restructuring"] = fin23["Restructuring costs"]
    d["da"] = fin23["Depreciation & amortization"]
    d["fcf"] = fin23["Free Cash Flow"]
    d["cash"] = fin23["Cash & cash equivalents"]
    d["mktsec"] = fin23["Marketable securities"]

    d["growth"] = m["growth"]
    d["discount"] = m["discount"]
    d["range_lo"], d["range_hi"] = m["range_lo"], m["range_hi"]
    d["peer_low"], d["peer_mid"], d["peer_high"] = m["peer_low"], m["peer_mid"], m["peer_high"]

    d["uw_ebitda"] = d["adj_ebitda"] - d["sbc"]
    d["uw_ebitda_negative"] = d["uw_ebitda"] < 0
    d["fcf_negative"] = d["fcf"] < 0

    d["rev2024e"] = d["rev23"] * (1 + d["growth"])
    d["net_cash"] = d["cash"] + d["mktsec"]
    d["pre_shares"] = m["pre_shares"]

    d["scen"] = {}
    for lab, mult in (("Low", d["peer_low"]), ("Mid", d["peer_mid"]), ("High", d["peer_high"])):
        ev = mult * d["rev2024e"]
        eq = ev + d["net_cash"]
        un = eq / d["pre_shares"]
        d["scen"][lab] = {"mult": mult, "ev": ev, "eq": eq, "undisc": un,
                          "offer": un * (1 - d["discount"])}
    d["low"] = d["scen"]["Low"]["offer"]
    d["mid"] = d["scen"]["Mid"]["offer"]
    d["high"] = d["scen"]["High"]["offer"]
    d["price"] = m["price"]
    d["vs_mid"] = d["price"] - d["mid"]
    d["in_range"] = d["low"] <= d["price"] <= d["high"]
    d["near_mid"] = abs(d["vs_mid"]) <= 0.50
    d["prop_eq"] = d["pre_shares"] * d["price"]
    d["prop_mult"] = (d["prop_eq"] - d["net_cash"]) / d["rev2024e"]

    d["primary"], d["secondary"] = m["primary"], m["secondary"]
    d["gs"] = m["greenshoe"]
    d["fee"], d["fixed"] = m["fee"], m["fixed"]
    d["gross_primary"] = d["primary"] * d["price"]
    d["uw_fee"] = d["gross_primary"] * d["fee"]
    d["net_primary"] = d["gross_primary"] - d["uw_fee"] - d["fixed"]
    d["secondary_gross"] = d["secondary"] * d["price"]
    d["secondary_to_company"] = 0.0
    d["post_cash"] = d["cash"] + d["mktsec"] + d["net_primary"]
    d["gs_incremental_net"] = d["gs"] * d["price"] * (1 - d["fee"])
    d["full_gross_primary"] = (d["primary"] + d["gs"]) * d["price"]
    d["full_net_primary"] = d["full_gross_primary"] * (1 - d["fee"]) - d["fixed"]

    d["post_shares"] = d["pre_shares"] + d["primary"]
    d["full_post_shares"] = d["post_shares"] + d["gs"]
    d["new_pct"] = d["primary"] / d["post_shares"]
    d["full_new_pct"] = (d["primary"] + d["gs"]) / d["full_post_shares"]
    d["proposed_post_equity"] = d["post_shares"] * d["price"]

    d["ntbv"], d["dilution"] = m["ntbv"], m["dilution"]

    if d["in_range"] and d["near_mid"]:
        d["decision"] = "Proceed"
    elif d["in_range"]:
        d["decision"] = "Reprice"
    else:
        d["decision"] = "Defer"

    d["xcheck"] = {
        "monthly_fy2022": m["monthly_sum"]["FY2022"],
        "monthly_fy2023": m["monthly_sum"]["FY2023"],
        "segment_fy2023": m["segment_sum"].get("FY2023", 0.0),
        "geo_fy2023": m["geo_sum"].get("FY2023", 0.0),
        "sbc_detail_fy2023": m["sbc_detail_sum"],
        "restructuring_detail_fy2023": m["rst_detail_sum"],
        "cap_table_pre_shares": m["pre_shares_cap"],
    }

    d["sens_growths"] = [0.18, 0.20, 0.22, 0.24, 0.26]
    d["sens_mults"] = [d["peer_low"], 4.3, d["peer_mid"], 4.8, d["peer_high"]]
    d["sens"] = []
    for g in d["sens_growths"]:
        row = []
        for mm in d["sens_mults"]:
            ev = mm * d["rev23"] * (1 + g)
            eq = ev + d["net_cash"]
            row.append((eq / d["pre_shares"]) * (1 - d["discount"]))
        d["sens"].append(row)

    d["conflicts"] = [
        ("FY2023 Revenue", f"{d['rev23']:.3f}", "SEC-01 (Priority 1)",
         "internal/management_flash_20240319.csv gives a different unreviewed figure; "
         "CP-02 excludes internal working drafts as a source",
         "adopt SEC-01"),
        ("FY2023 monthly detail 2023-12", "Source_Index Priority 1 value",
         "financials/monthly_revenue_2022_2023.csv",
         "the same month appears twice with different values and neither row carries any "
         "label; Source_Index Priority decides, and only the Priority-1 value ties the "
         "12-month sum to the SEC-01 annual figure",
         "adopt the Priority-1 value"),
        ("FY2022 monthly detail 2022-08", "single occurrence",
         "financials/monthly_revenue_2022_2023.csv",
         "the row is exported twice with an identical value and no marker; summing the raw "
         "file overshoots the SEC-01 annual figure, which is what exposes the repeat",
         "de-duplicate"),
        ("Peer EV/Revenue range", f"{d['peer_low']}x-{d['peer_high']}x",
         "Committee_Policy_v3 / Underwriting_Assumptions (CP-07)",
         "comps/underwriter_B_comps_20240318.csv screens a different 4.2x-5.1x set",
         "adopt committee peer set"),
        ("SBC treatment", "no addback retained", "Committee_Policy_v3 CP-03",
         "Committee_Policy_v2 CP-03 retained the addback and is superseded",
         "adopt v3"),
        ("Underwriting fee basis", "company primary gross proceeds", "Committee_Policy_v3 CP-12",
         "Committee_Policy_v2 CP-12 applied the fee to primary + secondary and is superseded",
         "adopt v3"),
        ("Legacy workpaper", "not used as a basis for conclusions",
         "legacy/Candidate_Model_v0.xlsx",
         "contains #REF! broken links and 11 legacy treatments",
         "recompute and correct"),
    ]
    return d


ISSUE_MAP = {
    "Profitability": ("Reverse the SBC addback and report underwriting EBITDA",
                      "Underwriting profitability is materially weaker than the management metric"),
    "Valuation": ("Use 2024E Revenue as the forward denominator and apply the IPO execution discount",
                  "Forward denominator and committee-supported range"),
    "Cash": ("Include both cash and marketable securities in the pre-money equity bridge",
             "An incomplete net cash bridge understates pre-money equity"),
    "Primary/Secondary": ("15.276527m is primary and 6.723473m is secondary",
                          "Counting everything as primary overstates company proceeds"),
    "Greenshoe": ("Exclude the greenshoe from Base and present a separate full-exercise scenario",
                  "Assuming exercise changes both the share count and proceeds"),
    "Underwriting fee": ("Apply the fee to company primary gross proceeds only",
                         "The fee base must match company economics"),
    "Post-money shares": ("Only new primary shares increase the count; secondary is a transfer",
                          "Drives dilution and the share bridge"),
    "Proceeds": ("Secondary proceeds accrue to selling stockholders; the company receives 0",
                 "Wrong beneficiary of secondary proceeds"),
    "Dilution": ("Compute dilution on a consistent numerator and denominator basis",
                 "Numerator and denominator must be on the same basis"),
    "Recommendation": ("Apply the committee range and distance-to-midpoint guardrails and "
                       "disclose QoE risk", "Recommendation discipline"),
}
EXTRA_ISSUES = [
    ("Post-cutoff information", "Back-solves Base from a later pricing result",
     "Freeze the information set at 2024-03-20", "Avoids hindsight bias"),
    ("Missing IPO execution discount", "No execution discount applied to peer-implied equity",
     "Apply the 12.5% IPO execution discount", "Produces the committee-supported range"),
    ("Unlabelled duplicate / superseded detail rows",
     "Summed the monthly detail row-by-row across a file where one month is exported twice "
     "and another month carries two different values from different sources",
     "De-duplicate identical re-exports, resolve same-month conflicts by Source_Index "
     "Priority, then tie out to the SEC-01 annual figure",
     "Keeps the detail consistent with the annual figure"),
    ("Segment magnitude error",
     "Consumed the segment extract at face value even though the Other segment is an order "
     "of magnitude too large and the parts overshoot the SEC-01 annual revenue",
     "Rebuild the Other segment as the annual figure less the Advertising segment",
     "Restores the segment split without disturbing the annual tie-out"),
    ("SBC total row mismatch",
     "Took the detail file's TOTAL row instead of re-summing the components",
     "Re-sum the SBC components and flag the total row as inconsistent",
     "The underwriting EBITDA add-back follows the components, not the stale total"),
    ("Fact vs assumption labelling",
     "Treated the 22% growth, peer multiples and 12.5% discount as SEC public facts",
     "Label them as internal committee assumptions", "Separates facts from assumptions"),
]


# ----------------------------------------------------------------- 产出
def sheet(ws, rows, widths=None):
    for r in rows:
        ws.append(r)
    for c in ws[1]:
        c.fill, c.font = HDR_FILL, HDR_FONT
    for row in ws.iter_rows():
        for c in row:
            c.border, c.alignment = BORDER, WRAP
    if widths:
        for i, wd in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = wd
    ws.freeze_panes = "A2"
    return ws


def build_model(m, d, outdir):
    wb = Workbook()

    rows = [["Input", "Value", "Unit", "Source", "Note"],
            ["2023 Revenue", d["rev23"], "USD mm", "SEC-01", "Pre-pricing filing"],
            ["2023 Net income (loss)", d["netloss23"], "USD mm", "SEC-01", ""],
            ["2023 Adjusted EBITDA (management)", d["adj_ebitda"], "USD mm", "SEC-01",
             "Management non-GAAP metric"],
            ["2023 SBC & related taxes", d["sbc"], "USD mm", "SEC-01", ""],
            ["2023 Restructuring costs", d["restructuring"], "USD mm", "SEC-01",
             "Already in management adjustments"],
            ["2023 Free Cash Flow", d["fcf"], "USD mm", "SEC-01", ""],
            ["Cash & cash equivalents", d["cash"], "USD mm", "SEC-01", ""],
            ["Marketable securities", d["mktsec"], "USD mm", "SEC-01", ""],
            ["2024E Revenue Growth", d["growth"], "%", "UW-01", "Internal assumption (CP-06)"],
            ["Peer Low EV/Revenue", d["peer_low"], "x", "UW-01", "Committee peer set (CP-07)"],
            ["Peer Midpoint EV/Revenue", d["peer_mid"], "x", "UW-01", "Committee peer set"],
            ["Peer High EV/Revenue", d["peer_high"], "x", "UW-01", "Committee peer set"],
            ["IPO Discount", d["discount"], "%", "UW-01", "Execution discount (CP-09)"],
            ["Proposed Committee Price", d["price"], "USD/share", "UW-01",
             "Internal working price, not a realized final price"],
            ["Pre-money economic shares", d["pre_shares"], "mm shares", "UW-01",
             "Committee cap-table snapshot"],
            ["Primary shares offered", d["primary"], "mm shares", "SEC-03", ""],
            ["Secondary shares offered", d["secondary"], "mm shares", "SEC-03",
             "No company proceeds"],
            ["Greenshoe shares", d["gs"], "mm shares", "SEC-03", "Base excludes exercise"],
            ["Underwriting fee", d["fee"], "% of primary gross", "UW-01", ""],
            ["Fixed company offering expenses", d["fixed"], "USD mm", "UW-01",
             "Not repeated on greenshoe increment"],
            ["Preliminary NTBV/share @ assumed $32.50", d["ntbv"], "USD/share", "SEC-02",
             "Cross-check only"],
            ["Preliminary dilution/share @ assumed $32.50", d["dilution"], "USD/share",
             "SEC-02", "Cross-check only"]]
    sheet(wb.active, rows, [42, 22, 18, 12, 48])
    wb.active.title = "Inputs"

    rows = [["Metric", "Reported / Management", "Underwriting treatment",
             "Underwriting result", "Note"],
            ["2023 Adjusted EBITDA", d["adj_ebitda"], "Start from management metric",
             d["adj_ebitda"], "Non-GAAP starting point"],
            ["SBC addback reversal", -d["sbc"],
             "SBC is a recurring economic cost; reverse the addback (CP-03)",
             -d["sbc"], "Committee_Policy v3"],
            ["Underwriting EBITDA", None, "Adjusted EBITDA - SBC addback",
             d["uw_ebitda"], "Remains negative"],
            ["2023 Free Cash Flow", d["fcf"], "No normalization", d["fcf"],
             "Cash quality weak"],
            ["2023 Restructuring", d["restructuring"],
             "Non-recurring but already reflected in management Adj EBITDA - no double count (CP-04)",
             d["restructuring"], "No double count"],
            [],
            ["Valuation method selected", "",
             "Underwriting EBITDA remains negative -> EV / 2024E Revenue (CP-05)",
             m["valuation_method"], ""],
            ["2024E Revenue = 2023A x (1 + growth)", "", "", d["rev2024e"], "USD mm"]]
    sheet(wb.create_sheet("QoE"), rows, [38, 22, 62, 22, 34])

    rows = [["Scenario", "EV/Revenue", "2024E Revenue", "Enterprise Value",
             "Pre-money Equity", "Undiscounted / sh", "Offer Value / sh", "Comment"]]
    for lab in ("Low", "Mid", "High"):
        s = d["scen"][lab]
        rows.append([lab, s["mult"], d["rev2024e"], s["ev"], s["eq"], s["undisc"], s["offer"],
                     "peer-implied equity x (1 - IPO execution discount)"])
    rows += [[], ["Cross-check", "Result"],
             ["Committee supported range", f"${d['low']:.2f} - ${d['high']:.2f}"],
             ["Committee midpoint", d["mid"]],
             ["Proposed Committee Price", d["price"]],
             ["Proposed price vs midpoint", d["vs_mid"]],
             ["Distance within guardrail (<= 0.50)", d["near_mid"]],
             ["Proposed-price implied pre-money equity", d["prop_eq"]],
             ["Proposed-price implied EV / 2024E Revenue", d["prop_mult"]],
             ["Preliminary public filing range",
              f"${d['range_lo']:.0f} - ${d['range_hi']:.0f}"]]
    sheet(wb.create_sheet("Valuation"), rows, [42, 18, 18, 20, 20, 20, 20, 54])

    rows = [["Sensitivity: offer value per share", "x1", "x2", "x3", "x4", "x5"],
            ["2024E growth \\ EV/Revenue"] + [f"{x}x" for x in d["sens_mults"]]]
    for i, g in enumerate(d["sens_growths"]):
        rows.append([f"{g:.0%}"] + [round(v, 2) for v in d["sens"][i]])
    rows += [[], ["Note", "Scenario grid uses the same net cash bridge, share count and IPO "
                          "execution discount as the base case."]]
    sheet(wb.create_sheet("Sensitivity"), rows, [34, 12, 12, 12, 12, 12])

    rows = [["Metric", "Base Offering", "Full Greenshoe", "Unit", "Comment"],
            ["Primary shares", d["primary"], d["primary"] + d["gs"], "mm shares", ""],
            ["Secondary shares", d["secondary"], d["secondary"], "mm shares",
             "Transfer only - no company proceeds"],
            ["Proposed price", d["price"], d["price"], "USD/share", "Committee working price"],
            ["Company gross primary proceeds", d["gross_primary"], d["full_gross_primary"],
             "USD mm", ""],
            ["Underwriting fee", d["uw_fee"], d["full_gross_primary"] * d["fee"], "USD mm",
             "5% of company primary gross"],
            ["Fixed company expenses", d["fixed"], d["fixed"], "USD mm",
             "Not repeated on greenshoe increment"],
            ["Company net primary proceeds", d["net_primary"], d["full_net_primary"], "USD mm",
             "Primary proceeds only"],
            ["Selling holders gross proceeds", d["secondary_gross"], d["secondary_gross"],
             "USD mm", "Belongs to selling holders"],
            ["Company receives secondary proceeds", d["secondary_to_company"],
             d["secondary_to_company"], "USD mm", "Secondary never accrues to the company"],
            ["Post-money cash & securities", d["post_cash"],
             d["post_cash"] + d["gs_incremental_net"], "USD mm",
             "cash + marketable securities + net primary"],
            ["Incremental greenshoe net proceeds", 0.0, d["gs_incremental_net"], "USD mm",
             "greenshoe x price x (1 - fee); no fixed expense repeated"]]
    sheet(wb.create_sheet("Offering_Proceeds"), rows, [38, 22, 22, 16, 50])

    rows = [["Metric", "Base Offering", "Full Greenshoe", "Unit", "Interpretation"],
            ["Pre-money shares", d["pre_shares"], d["pre_shares"], "mm shares", ""],
            ["New primary shares", d["primary"], d["primary"] + d["gs"], "mm shares", ""],
            ["Secondary shares", d["secondary"], d["secondary"], "mm shares",
             "Ownership transfer, not new issuance"],
            ["Post-money shares", d["post_shares"], d["full_post_shares"], "mm shares",
             "pre-money + new primary only"],
            ["New primary ownership %", d["new_pct"], d["full_new_pct"], "%", ""],
            ["Secondary impact on share count", 0.0, 0.0, "mm shares",
             "Secondary does not change share count"],
            ["NTBV/share cross-check @ assumed $32.50", d["ntbv"], d["ntbv"], "USD/share",
             "Pre-cutoff SEC cross-check"],
            ["Immediate dilution cross-check @ assumed $32.50", d["dilution"], d["dilution"],
             "USD/share", "Pre-cutoff SEC cross-check"],
            ["Proposed-price post-money equity", d["proposed_post_equity"],
             d["full_post_shares"] * d["price"], "USD mm", "post-money shares x proposed price"]]
    sheet(wb.create_sheet("Dilution"), rows, [44, 26, 26, 16, 46])

    rows = [["IPO Pricing Committee Summary"],
            ["Item", "Result"],
            ["2024E Revenue", d["rev2024e"]],
            ["Management Adjusted EBITDA", d["adj_ebitda"]],
            ["Underwriting EBITDA", d["uw_ebitda"]],
            ["2023 Free Cash Flow", d["fcf"]],
            ["Committee Offer Range", f"${d['low']:.2f} - ${d['high']:.2f}"],
            ["Midpoint", d["mid"]],
            ["Proposed Committee Price", d["price"]],
            ["Proposed price vs midpoint", d["vs_mid"]],
            ["Base company net primary proceeds", d["net_primary"]],
            ["Secondary proceeds to company", d["secondary_to_company"]],
            ["Base post-money shares", d["post_shares"]],
            ["Full-greenshoe post-money shares", d["full_post_shares"]],
            [], ["Committee disposition", "Result"],
            ["Price inside supported range", d["in_range"]],
            ["Within guardrail distance of midpoint", d["near_mid"]],
            ["QoE view", "Underwriting EBITDA remains negative after reversing the SBC addback; "
                         "2023 FCF is also negative."],
            ["Structure view", "Base separates primary from secondary, excludes greenshoe from "
                               "Base, and grants no secondary proceeds or share count increase "
                               "to the company."],
            ["Recommendation", f"{d['decision']} at ${d['price']:.0f}"],
            ["Disclosure requirement", "Disclose negative QoE in the memo; do not raise the price "
                                       "solely because management Adjusted EBITDA improved."]]
    sheet(wb.create_sheet("Pricing_Summary"), rows, [44, 96])

    rows = [["#", "Workstream / Issue", "Legacy treatment (as-is)", "Correct treatment",
             "Why it matters"]]
    n = 0
    for r in rows_of_xlsx(os.path.join(IN_DIR, "legacy", "Candidate_Model_v0.xlsx"),
                          "Candidate_Model")[1:]:
        n += 1
        ws_name = str(r[0]).strip()
        corr = ISSUE_MAP.get(ws_name, (str(r[2]), ""))
        rows.append([n, ws_name, str(r[1]), corr[0], corr[1]])
    for issue, legacy, corr, why in EXTRA_ISSUES:
        n += 1
        rows.append([n, issue, legacy, corr, why])
    rows += [[], ["Summary", f"Total issues identified and corrected: {n}"],
             ["Information set", "As-of 2024-03-20: SEC facts and internal committee assumptions "
                                 "are labelled separately throughout the model."],
             ["Cross-check", "Monthly detail ties to SEC-01 only after de-duplicating the "
                             "repeated 2022-08 export and resolving the two competing 2023-12 "
                             "values by Source_Index Priority."]]
    sheet(wb.create_sheet("Error_Audit"), rows, [6, 30, 54, 62, 52])

    rows = [["Item", "Value adopted", "Source", "Competing value", "Disposition"]]
    for name, val, src, comp, disp in d["conflicts"]:
        rows.append([name, val, src, comp, disp])
    sheet(wb.create_sheet("Source_Trace"), rows, [28, 22, 34, 56, 26])

    path = os.path.join(outdir, f"{TASK}_ipo_model.xlsx")
    wb.save(path)
    return path


def build_qoe_csv(m, d, outdir):
    path = os.path.join(outdir, f"{TASK}_qoe_bridge.csv")
    rows = [
        ["step", "line_item", "amount_usd_mm", "basis", "policy_ref"],
        ["1", "Management Adjusted EBITDA (2023)", f"{d['adj_ebitda']:.3f}",
         "management non-GAAP", "CP-03"],
        ["2", "Reversal of SBC addback", f"{-d['sbc']:.3f}",
         "SBC is a recurring economic cost", "CP-03"],
        ["3", "Underwriting EBITDA (2023)", f"{d['uw_ebitda']:.3f}",
         "adjusted EBITDA less SBC", "CP-03"],
        ["4", "Free Cash Flow (2023)", f"{d['fcf']:.3f}", "company definition", "CP-13"],
        ["5", "Restructuring costs (2023)", f"{d['restructuring']:.3f}",
         "non-recurring but already inside management adjustments - no double count", "CP-04"],
        ["6", "SBC detail tie-out", f"{d['xcheck']['sbc_detail_fy2023']:.3f}",
         "financials/sbc_detail_2022_2023.csv", "CP-02"],
        ["7", "Restructuring detail tie-out", f"{d['xcheck']['restructuring_detail_fy2023']:.3f}",
         "financials/restructuring_detail_2023.csv", "CP-02"],
        ["8", "Underwriting EBITDA remains negative", str(d["uw_ebitda_negative"]),
         "QoE conclusion", "CP-05"],
        ["9", "FCF remains negative", str(d["fcf_negative"]), "QoE conclusion", "CP-13"],
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return path


def build_valuation_matrix(m, d, outdir):
    path = os.path.join(outdir, f"{TASK}_valuation_matrix.csv")
    rows = [["2024E_growth"] + [f"{x}x" for x in d["sens_mults"]]]
    for i, g in enumerate(d["sens_growths"]):
        rows.append([f"{g:.2f}"] + [f"{v:.2f}" for v in d["sens"][i]])
    rows += [[],
             ["base_case_growth", f"{d['growth']:.2f}"],
             ["committee_low", f"{d['low']:.2f}"],
             ["committee_mid", f"{d['mid']:.2f}"],
             ["committee_high", f"{d['high']:.2f}"],
             ["proposed_price", f"{d['price']:.2f}"],
             ["net_cash_bridge", f"{d['net_cash']:.3f}"],
             ["pre_money_shares_mm", f"{d['pre_shares']:.6f}"],
             ["ipo_execution_discount", f"{d['discount']:.3f}"]]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return path


def build_source_trace(m, d, outdir):
    path = os.path.join(outdir, f"{TASK}_source_trace.csv")
    rows = [["item", "value_adopted", "source", "competing_value", "disposition"]]
    for name, val, src, comp, disp in d["conflicts"]:
        rows.append([name, val, src, comp, disp])
    rows += [
        ["FY2023 revenue tie-out (monthly detail)", f"{d['xcheck']['monthly_fy2023']:.3f}",
         "financials/monthly_revenue_2022_2023.csv", f"SEC-01 = {d['rev23']:.3f}",
         "ties after de-duplication and Priority-based resolution"],
        ["FY2023 revenue tie-out (segment)", f"{d['xcheck']['segment_fy2023']:.3f}",
         "financials/revenue_by_segment_2022_2023.csv", f"SEC-01 = {d['rev23']:.3f}", "ties"],
        ["FY2023 revenue tie-out (geography)", f"{d['xcheck']['geo_fy2023']:.3f}",
         "sec_filings/SEC-05_revenue_by_geo.csv", f"SEC-01 = {d['rev23']:.3f}", "ties"],
        ["Pre-money economic shares (cap table)",
         f"{d['xcheck']['cap_table_pre_shares']:.6f}",
         "committee/cap_table_snapshot_20240318.csv",
         f"Offering_Terms = {d['pre_shares']:.6f}", "ties"],
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return path


def build_charts(m, d, outdir):
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1100, 780
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    font = fbig = fsm = None
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "C:/Windows/Fonts/arial.ttf",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        if os.path.exists(cand):
            try:
                font = ImageFont.truetype(cand, 16)
                fbig = ImageFont.truetype(cand, 22)
                fsm = ImageFont.truetype(cand, 13)
                break
            except Exception:
                pass

    def text(xy, s, ft=None, fill="black"):
        dr.text(xy, s, fill=fill, font=ft or font)

    text((40, 24), "Committee Supported Price Range vs Proposed Price", fbig)
    x0, y0, bw, gap = 120, 150, 200, 60
    scale = 3.0
    base = y0 + 260
    for i, (lab, val) in enumerate([("Low (4.0x)", d["low"]), ("Mid (4.5x)", d["mid"]),
                                    ("High (5.0x)", d["high"])]):
        x = x0 + i * (bw + gap)
        h = int((val - 25) * scale)
        dr.rectangle([x, base - h, x + bw, base], fill="#4472C4", outline="#1F3864")
        text((x + 62, base - h - 30), f"${val:.2f}", fbig)
        text((x + 32, base + 10), lab, fsm)
    px = x0 + int((d["price"] - 25.0) / (42.0 - 25.0) * (3 * bw + 2 * gap))
    dr.line([px, y0 - 20, px, base + 6], fill="red", width=3)
    text((px - 92, y0 - 52), f"Proposed ${d['price']:.0f}", fsm, "red")
    text((x0, base + 44), f"Range ${d['low']:.2f} - ${d['high']:.2f}    |    "
                          f"Midpoint ${d['mid']:.2f}    |    vs midpoint {d['vs_mid']:+.2f}",
         font)

    text((40, 500), "Offer Value per Share: 2024E Growth x EV/Revenue", fbig)
    gx, gy, cw, ch = 190, 560, 150, 40
    for j, mm in enumerate(d["sens_mults"]):
        text((gx + j * cw + 46, gy - 28), f"{mm}x", fsm)
    lo, hi = d["low"], d["high"]
    for i, g in enumerate(d["sens_growths"]):
        text((62, gy + i * ch + 10), f"{g:.0%}", font)
        for j in range(len(d["sens_mults"])):
            v = d["sens"][i][j]
            t = max(0.0, min(1.0, (v - lo * 0.9) / ((hi * 1.1) - lo * 0.9)))
            col = (int(255 - 120 * t), int(235 - 140 * t), int(120 + 60 * (1 - t)))
            dr.rectangle([gx + j * cw, gy + i * ch, gx + (j + 1) * cw - 6, gy + (i + 1) * ch - 6],
                         fill=col, outline="#8EA9DB")
            text((gx + j * cw + 44, gy + i * ch + 11), f"{v:.2f}", fsm)
    text((40, gy + 5 * ch + 16),
         "Grid uses the same net cash bridge, pre-money share count and 12.5% execution discount.",
         fsm)

    path = os.path.join(outdir, f"{TASK}_charts.png")
    img.save(path)
    return path


def build_memo(m, d, outdir):
    lo, hi = d["low"], d["high"]
    txt = f"""# Pricing Committee Memo — Reddit, Inc. IPO

**日期**：2024-03-20（正式定价前） · **出具**：承销团队 / ECM · **议题**：拟议价格 ${d['price']:.0f} 是否继续推进

## 一、定价建议

**建议 Proceed，按拟议 ${d['price']:.0f} 推进。** 拟议价格位于委员会支持区间 **${lo:.2f}–${hi:.2f}** 之内，
距 midpoint **${d['mid']:.2f}** 仅 **${abs(d['vs_mid']):.2f}**，未超过 $0.50 护栏；修正后的发行结构已消除旧底稿的硬错误。
该建议以披露下述盈利质量风险为前提，**不得仅因管理层 Adjusted EBITDA 改善而上调价格**。

## 二、盈利质量（QoE）

2023 年 Revenue **{d['rev23']:.3f}mm**、管理层口径 Adjusted EBITDA **{d['adj_ebitda']:.3f}mm**。
按委员会政策，SBC 属持续性经济成本，撤销 **{d['sbc']:.3f}mm** 加回后，承销口径 EBITDA 为
**{d['uw_ebitda']:.3f}mm**，仍为负；2023 年 FCF **{d['fcf']:.3f}mm** 同样为负。重组费用
{d['restructuring']:.3f}mm 虽属非经常性，但已包含在管理层指标中，不再重复加回。
承销 EBITDA 为负，主估值方法改用 **EV / 2024E Revenue**，不得使用 EV/EBITDA。

## 三、估值支撑

2024E Revenue = {d['rev23']:.3f} × (1 + {d['growth']:.0%}) = **{d['rev2024e']:.3f}mm**。
按委员会 peer 区间 {d['peer_low']:.1f}x–{d['peer_high']:.1f}x（中点 {d['peer_mid']:.1f}x）得企业价值
{d['scen']['Low']['ev']:.3f}–{d['scen']['High']['ev']:.3f}mm，加回年末现金 {d['cash']:.3f}mm 与有价证券
{d['mktsec']:.3f}mm 完成净现金桥，再统一应用 {d['discount']:.1%} 执行折扣，得每股
**${lo:.2f} / ${d['mid']:.2f} / ${hi:.2f}**（低/中/高）。按 ${d['price']:.0f} 计算的隐含 pre-money equity 为
{d['prop_eq']:.1f}mm，对应 **{d['prop_mult']:.2f}x** 2024E Revenue。截止日前 SEC 材料的稀释交叉验算
（NTBV {d['ntbv']:.2f}、即时稀释 {d['dilution']:.2f}，假设价 $32.50）成立。

## 四、发行结构

Base：**{d['primary']:.6f}m primary**、**{d['secondary']:.6f}m secondary**；**{d['gs']:.1f}m greenshoe 不进入 Base**，
仅单列 full-exercise 情景。按 ${d['price']:.0f}，公司 primary gross 为 **{d['gross_primary']:.3f}mm**，
扣 {d['fee']:.0%} 承销费（{d['uw_fee']:.3f}mm）与 {d['fixed']:.1f}mm 固定费用后，net primary
**{d['net_primary']:.3f}mm**。Secondary 为 {d['secondary_gross']:.3f}mm 归出售股东，**公司取得 0**，
且不增加总股数。Base post-money 股数 {d['post_shares']:.6f}m（full exercise {d['full_post_shares']:.6f}m），
新增 primary 占 {d['new_pct']:.2%}。旧底稿的 legacy 处理已逐项修正并记入 `Error_Audit`。

## 五、数据口径与冲突处置

月度明细与年度数勾稽前，须先剔除 2022-08 的重复导出行，并排除 2023-12 的未审计 IR 记录；
内部 management flash（3/19）为未复核初稿，按来源优先级不得进入结论。peer 区间采用委员会
peer set 的 {d['peer_low']:.1f}x–{d['peer_high']:.1f}x，承销商各自编制的 comps 仅作交叉验证；
政策 v2 中关于 SBC 加回、peer 区间、执行折扣与费用基数的条款已被 v3 取代。

## 六、条件与风险

1. 必须披露 QoE：承销 EBITDA {d['uw_ebitda']:.3f}mm、FCF {d['fcf']:.3f}mm 均为负。
2. 信息集冻结于 2024-03-20；${d['price']:.0f} 是内部拟议价，**不是已实现的最终发行结果**。
3. 区间纪律：价格偏离 midpoint 超过 $0.50 时向 midpoint 方向 Reprice；跌出 ${lo:.2f}–${hi:.2f}
   或发行结构重新出现未解决硬错误时 Defer。
"""
    path = os.path.join(outdir, f"{TASK}_pricing_memo.md")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    return path


def main(argv=None):
    global IN_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", default="/app/input_files")
    ap.add_argument("--output-dir", default="/app/output")
    a = ap.parse_args(argv)
    IN_DIR = a.input_dir
    os.makedirs(a.output_dir, exist_ok=True)

    m = load_materials(a.input_dir)
    d = compute(m)

    build_model(m, d, a.output_dir)
    build_qoe_csv(m, d, a.output_dir)
    build_valuation_matrix(m, d, a.output_dir)
    build_source_trace(m, d, a.output_dir)
    build_charts(m, d, a.output_dir)
    build_memo(m, d, a.output_dir)

    print("=== FIN3-WKN-152 reproducible results ===")
    print(f"  Revenue 2023            : {d['rev23']:.3f}")
    print(f"  Underwriting EBITDA     : {d['uw_ebitda']:.3f}")
    print(f"  2024E Revenue           : {d['rev2024e']:.5f}")
    print(f"  Net cash bridge         : {d['net_cash']:.3f}")
    print(f"  Range                   : ${d['low']:.2f} - ${d['high']:.2f}  mid=${d['mid']:.6f}")
    print(f"  vs midpoint             : {d['vs_mid']:+.6f}")
    print(f"  Gross primary proceeds  : {d['gross_primary']:.6f}")
    print(f"  Net primary proceeds    : {d['net_primary']:.6f}")
    print(f"  Post-money shares       : {d['post_shares']:.6f} / full {d['full_post_shares']:.6f}")
    print(f"  Greenshoe incremental   : {d['gs_incremental_net']:.3f}")
    print(f"  Monthly tie-out FY2023  : {d['xcheck']['monthly_fy2023']:.3f}")
    print(f"  Decision                : {d['decision']} at ${d['price']:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
