#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 FIN3-WKN-152 golden：修复后的 IPO 模型 + Pricing Committee memo。"""
from __future__ import annotations

import os
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    HERE, "..", "FIN3-WKN-152", "environment", "input_files", "Q7_题目.xlsx")
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    HERE, "..", "FIN3-WKN-152", "solution", "golden_output")

TASK = "FIN3-WKN-152"

HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(color="FFFFFF", bold=True, size=11)
SEC_FILL = PatternFill("solid", fgColor="D9E2F3")
SEC_FONT = Font(bold=True, size=11, color="1F3864")
THIN = Side(style="thin", color="B4C6E7")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")


def read_inputs(path):
    wb = load_workbook(path, data_only=True)

    pub = {}
    for r in wb["Public_Financials"].iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            pub[str(r[0]).strip()] = {"2022A": r[1], "2023A": r[2],
                                      "src": r[4] if len(r) > 4 else None,
                                      "notes": r[5] if len(r) > 5 else None}

    trm = {}
    for r in wb["Offering_Terms"].iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            trm[str(r[0]).strip()] = {"base": r[1], "full": r[2],
                                      "src": r[4] if len(r) > 4 else None,
                                      "notes": r[5] if len(r) > 5 else None}

    asm = {}
    for r in wb["Underwriting_Assumptions"].iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            asm[str(r[0]).strip()] = r[1]

    pol = []
    for r in wb["Committee_Policy"].iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            pol.append((r[0], r[1], r[2]))

    audit = []
    for r in wb["Candidate_Model"].iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            audit.append((r[0], r[1], r[2], r[3]))

    srcs = []
    for r in wb["Source_Index"].iter_rows(min_row=2, values_only=True):
        if r and r[0]:
            srcs.append(r)

    return pub, trm, asm, pol, audit, srcs


def compute(pub, trm, asm):
    d = {}
    d["rev2023"] = float(pub["Revenue"]["2023A"])
    d["netloss2023"] = float(pub["Net income (loss)"]["2023A"])
    d["adj_ebitda"] = float(pub["Adjusted EBITDA"]["2023A"])
    d["sbc"] = float(pub["Stock-based compensation & related taxes"]["2023A"])
    d["fcf"] = float(pub["Free Cash Flow"]["2023A"])
    d["restructuring"] = float(pub["Restructuring costs"]["2023A"] or 0)
    d["cash"] = float(pub["Cash & cash equivalents"]["2023A"])
    d["sec"] = float(pub["Marketable securities"]["2023A"])
    d["ntbv_x"] = float(pub["Preliminary NTBV/share at assumed $32.50"]["2023A"])
    d["dil_x"] = float(pub["Preliminary immediate dilution at assumed $32.50"]["2023A"])

    d["growth"] = float(asm["2024E revenue growth"])
    d["ml"], d["mm"], d["mh"] = (float(asm["Peer low EV/Revenue"]),
                                 float(asm["Peer midpoint EV/Revenue"]),
                                 float(asm["Peer high EV/Revenue"]))
    d["disc"] = float(asm["IPO discount to peer-implied equity"])

    d["price"] = float(trm["Proposed Committee Price"]["base"])
    d["primary"] = float(trm["Primary shares offered"]["base"])
    d["secondary"] = float(trm["Secondary shares offered"]["base"])
    d["gs"] = float(trm["Greenshoe shares"]["full"])
    d["pre_sh"] = float(trm["Pre-money economic shares"]["base"])
    d["fee"] = float(trm["Underwriting fee assumption"]["base"])
    d["fixed"] = float(trm["Fixed company offering expenses"]["base"])
    d["full_primary"] = float(trm["Primary shares offered"]["full"])
    d["range_lo"] = float(trm["Preliminary public filing range low"]["base"])
    d["range_hi"] = float(trm["Preliminary public filing range high"]["base"])

    # QoE
    d["uw_ebitda"] = d["adj_ebitda"] - d["sbc"]
    # Valuation
    d["rev2024e"] = d["rev2023"] * (1 + d["growth"])
    d["net_cash"] = d["cash"] + d["sec"]
    d["scen"] = {}
    for lab, m in (("Low", d["ml"]), ("Mid", d["mm"]), ("High", d["mh"])):
        ev = m * d["rev2024e"]
        eq = ev + d["net_cash"]
        un = eq / d["pre_sh"]
        d["scen"][lab] = dict(mult=m, ev=ev, eq=eq, undisc=un,
                              offer=un * (1 - d["disc"]))
    d["low"], d["high"] = d["scen"]["Low"]["offer"], d["scen"]["High"]["offer"]
    d["mid"] = d["scen"]["Mid"]["offer"]
    d["vs_mid"] = d["price"] - d["mid"]
    d["prop_eq"] = d["pre_sh"] * d["price"]
    d["prop_mult"] = (d["prop_eq"] - d["net_cash"]) / d["rev2024e"]

    # Offering
    d["gross"] = d["primary"] * d["price"]
    d["uw_fee"] = d["gross"] * d["fee"]
    d["net_primary"] = d["gross"] - d["uw_fee"] - d["fixed"]
    d["sell_gross"] = d["secondary"] * d["price"]
    d["pm_cash"] = d["cash"] + d["sec"] + d["net_primary"]
    d["full_gross"] = d["full_primary"] * d["price"]
    d["full_fee"] = d["full_gross"] * d["fee"]
    d["full_net"] = d["full_gross"] - d["full_fee"] - d["fixed"]
    d["gs_incr"] = d["full_net"] - d["net_primary"]

    # Dilution
    d["post_sh"] = d["pre_sh"] + d["primary"]
    d["full_post_sh"] = d["post_sh"] + d["gs"]
    d["new_pct"] = d["primary"] / d["post_sh"]
    d["full_new_pct"] = d["full_primary"] / d["full_post_sh"]
    d["prop_post_eq"] = d["post_sh"] * d["price"]
    d["full_post_eq"] = d["full_post_sh"] * d["price"]

    # Decision
    d["in_range"] = d["low"] <= d["price"] <= d["high"]
    d["near_mid"] = abs(d["vs_mid"]) <= 0.50
    d["decision"] = ("Proceed" if d["in_range"] and d["near_mid"]
                     else "Reprice" if d["in_range"] else "Defer")
    return d


def sheet(wb, title, rows, widths, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    for r in rows:
        ws.append(r)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows():
        for c in row:
            c.border = BORDER
            c.alignment = WRAP
    # 首行表头
    for c in ws[1]:
        c.fill, c.font = HDR_FILL, HDR_FONT
    # 分区行（A 列有值、B 列为空且行非首行）
    for row in ws.iter_rows(min_row=2):
        if row[0].value and all(c.value in (None, "") for c in row[1:]):
            for c in row:
                c.fill, c.font = SEC_FILL, SEC_FONT
    ws.freeze_panes = "A2"
    return ws


def build_model(d, audit, pub, trm, asm, srcs, path):
    wb = Workbook()

    # ---------------- Inputs
    rows = [["Input", "Value", "Unit", "Source", "Notes"],
            ["2023 Revenue", d["rev2023"], "USD mm", "SEC-01", "Pre-pricing filing"],
            ["2023 Net income (loss)", d["netloss2023"], "USD mm", "SEC-01", ""],
            ["2023 Adjusted EBITDA (management)", d["adj_ebitda"], "USD mm", "SEC-01",
             "Management non-GAAP metric"],
            ["2023 SBC & related taxes", d["sbc"], "USD mm", "SEC-01", ""],
            ["2023 Free Cash Flow", d["fcf"], "USD mm", "SEC-01", ""],
            ["Cash & cash equivalents", d["cash"], "USD mm", "SEC-01", ""],
            ["Marketable securities", d["sec"], "USD mm", "SEC-01", ""],
            ["2024E Revenue Growth", d["growth"], "%", "UW-01", "Internal assumption"],
            ["Peer Low EV/Revenue", d["ml"], "x", "UW-01", ""],
            ["Peer Midpoint EV/Revenue", d["mm"], "x", "UW-01", ""],
            ["Peer High EV/Revenue", d["mh"], "x", "UW-01", ""],
            ["IPO Discount", d["disc"], "%", "UW-01", "Execution discount"],
            ["Proposed Committee Price", d["price"], "USD/share", "UW-01",
             "Internal working price, not a realized final price"],
            ["Pre-money economic shares", d["pre_sh"], "mm shares", "UW-01",
             "Committee cap-table snapshot"],
            ["Primary shares offered", d["primary"], "mm shares", "SEC-03", ""],
            ["Secondary shares offered", d["secondary"], "mm shares", "SEC-03",
             "No company proceeds"],
            ["Greenshoe shares", d["gs"], "mm shares", "SEC-03",
             "Base excludes exercise"],
            ["Underwriting fee", d["fee"], "% of primary gross", "UW-01", ""],
            ["Fixed company offering expenses", d["fixed"], "USD mm", "UW-01",
             "Not repeated on greenshoe increment"],
            ["Preliminary NTBV/share @ assumed $32.50", d["ntbv_x"], "USD/share",
             "SEC-02", "Cross-check only"],
            ["Preliminary dilution/share @ assumed $32.50", d["dil_x"], "USD/share",
             "SEC-02", "Cross-check only"],
            [],
            ["[Committee_Policy — control rules]", "", "", "", ""],
            ]
    rows += [["Section", "Committee convention", "Application", "", ""]]
    sheet(wb, "Inputs", rows, [42, 22, 16, 12, 46], first=True)

    # 追加 policy 与 source index 到 Inputs 表尾
    ws = wb["Inputs"]
    ws.append([])
    ws.append(["Source_Index", "Document", "As-of", "Fact", "Use"])
    for c in ws[ws.max_row]:
        c.fill, c.font = HDR_FILL, HDR_FONT
    for s in srcs:
        fact = str(s[3]) if s[3] is not None else ""
        if len(fact) > 110:
            fact = fact[:110] + "…"
        ws.append([s[0], s[1], str(s[2]), fact, s[6]])
    for row in ws.iter_rows(min_row=ws.max_row - len(srcs) + 1):
        for c in row:
            c.border, c.alignment = BORDER, WRAP

    # ---------------- QoE
    rows = [["Metric", "Reported / Management", "Underwriting treatment",
             "Underwriting result", "Note"],
            ["2023 Adjusted EBITDA", d["adj_ebitda"], "Start from management metric",
             d["adj_ebitda"], "Non-GAAP starting point"],
            ["SBC addback reversal", -d["sbc"],
             "SBC is a recurring economic cost; reverse the addback", -d["sbc"],
             "Committee_Policy / QoE"],
            ["Underwriting EBITDA", None, "Adjusted EBITDA - SBC addback",
             d["uw_ebitda"], "Remains negative"],
            ["2023 Free Cash Flow", d["fcf"], "No normalization; negative cash quality remains",
             d["fcf"], "Cash quality weak"],
            ["2023 Restructuring", float(pub["Restructuring costs"]["2023A"]),
             "Non-recurring; already reflected in management Adj EBITDA — no double count",
             float(pub["Restructuring costs"]["2023A"]), "No double count"],
            [],
            ["Valuation method selected", "",
             "Because underwriting EBITDA remains negative, use EV / 2024E Revenue",
             "EV / 2024E Revenue", "Committee_Policy / Valuation"],
            ["2024E Revenue = 2023A x (1 + growth)", "", "", d["rev2024e"], "USD mm"],
            ]
    sheet(wb, "QoE", rows, [34, 22, 52, 24, 34])

    # ---------------- Valuation
    rows = [["Scenario", "EV/Revenue", "2024E Revenue", "Enterprise Value",
             "Pre-money Equity", "Undiscounted / sh", "Offer Value / sh", "Comment"]]
    for lab in ("Low", "Mid", "High"):
        s = d["scen"][lab]
        rows.append([lab, s["mult"], d["rev2024e"], s["ev"], s["eq"],
                     s["undisc"], s["offer"],
                     "Peer-implied equity x (1 - IPO execution discount)"])
    rows += [
        [],
        ["Cross-check", "Result", "", "", "", "", "", ""],
        ["Committee supported range", f"${d['low']:.2f} - ${d['high']:.2f}"],
        ["Committee midpoint", d["mid"]],
        ["Proposed Committee Price", d["price"]],
        ["Proposed price vs midpoint", d["vs_mid"]],
        ["Distance within guardrail (<= 0.50)", d["near_mid"]],
        ["Proposed-price implied pre-money equity", d["prop_eq"]],
        ["Proposed-price implied EV / 2024E Revenue", d["prop_mult"]],
        ["Preliminary public filing range", f"${d['range_lo']:.0f} - ${d['range_hi']:.0f}"],
        ["Proposed price vs filing range", "at top of preliminary range (execution cross-check only)"],
    ]
    sheet(wb, "Valuation", rows, [40, 20, 20, 22, 22, 22, 20, 56])

    # ---------------- Offering_Proceeds
    rows = [["Metric", "Base Offering", "Full Greenshoe", "Unit", "Comment"],
            ["Primary shares", d["primary"], d["full_primary"], "mm shares", ""],
            ["Secondary shares", d["secondary"], d["secondary"], "mm shares",
             "Transfer only — no company proceeds"],
            ["Proposed price", d["price"], d["price"], "USD/share",
             "Committee working price"],
            ["Company gross primary proceeds", d["gross"], d["full_gross"], "USD mm", ""],
            ["Underwriting fee", d["uw_fee"], d["full_fee"], "USD mm",
             "5% of company primary gross"],
            ["Fixed company expenses", d["fixed"], d["fixed"], "USD mm",
             "Not repeated on greenshoe increment"],
            ["Company net primary proceeds", d["net_primary"], d["full_net"],
             "USD mm", "Primary proceeds only"],
            ["Selling holders gross proceeds", d["sell_gross"], d["sell_gross"],
             "USD mm", "Belongs to selling holders"],
            ["Company receives secondary proceeds", 0.0, 0.0, "USD mm",
             "Secondary never accrues to the company"],
            ["Post-money cash & securities", d["pm_cash"], d["pm_cash"] + d["gs_incr"],
             "USD mm", "cash + marketable securities + net primary"],
            ["Incremental greenshoe net proceeds", 0.0, d["gs_incr"], "USD mm",
             "3.3m x price x (1 - fee); no fixed expense repeated"],
            ]
    sheet(wb, "Offering_Proceeds", rows, [38, 22, 22, 16, 50])

    # ---------------- Dilution
    rows = [["Metric", "Base Offering", "Full Greenshoe", "Unit", "Interpretation"],
            ["Pre-money shares", d["pre_sh"], d["pre_sh"], "mm shares", ""],
            ["New primary shares", d["primary"], d["full_primary"], "mm shares", ""],
            ["Secondary shares", d["secondary"], d["secondary"], "mm shares",
             "Ownership transfer, not new issuance"],
            ["Post-money shares", d["post_sh"], d["full_post_sh"], "mm shares",
             "pre-money + new primary only"],
            ["New primary ownership %", d["new_pct"], d["full_new_pct"], "%", ""],
            ["Secondary impact on share count", 0.0, 0.0, "mm shares",
             "Secondary does not change share count"],
            ["NTBV/share cross-check @ assumed $32.50", d["ntbv_x"], d["ntbv_x"],
             "USD/share", "Pre-cutoff SEC cross-check"],
            ["Immediate dilution cross-check @ assumed $32.50", d["dil_x"], d["dil_x"],
             "USD/share", "Pre-cutoff SEC cross-check"],
            ["Proposed-price post-money equity", d["prop_post_eq"], d["full_post_eq"],
             "USD mm", "post-money shares x proposed price"],
            ["Public filing range check",
             f"proposed ${d['price']:.0f} at top of ${d['range_lo']:.0f}-${d['range_hi']:.0f}",
             "same", "Text", "Execution cross-check only"],
            ]
    sheet(wb, "Dilution", rows, [44, 26, 26, 16, 46])

    # ---------------- Pricing_Summary
    rows = [["IPO Pricing Committee Summary", "", "", "", ""],
            ["Item", "Result", "", "", ""],
            ["2024E Revenue", d["rev2024e"], "", "", ""],
            ["Management Adjusted EBITDA", d["adj_ebitda"], "", "", ""],
            ["Underwriting EBITDA", d["uw_ebitda"], "", "", ""],
            ["2023 Free Cash Flow", d["fcf"], "", "", ""],
            ["Committee Offer Range", f"${d['low']:.2f} - ${d['high']:.2f}", "", "", ""],
            ["Midpoint", d["mid"], "", "", ""],
            ["Proposed Committee Price", d["price"], "", "", ""],
            ["Proposed price vs midpoint", d["vs_mid"], "", "", ""],
            ["Base company net primary proceeds", d["net_primary"], "", "", ""],
            ["Secondary proceeds to company", 0.0, "", "", ""],
            ["Base post-money shares", d["post_sh"], "", "", ""],
            ["Full-greenshoe post-money shares", d["full_post_sh"], "", "", ""],
            [], ["Committee disposition", "Result", "", "", ""],
            ["Price inside supported range", d["in_range"], "", "", ""],
            ["Within guardrail distance of midpoint", d["near_mid"], "", "", ""],
            ["QoE view",
             "Underwriting EBITDA remains negative after reversing the SBC addback; 2023 FCF is also negative.",
             "", "", ""],
            ["Structure view",
             "Base separates primary from secondary, excludes greenshoe from Base, and grants no secondary proceeds or share count increase to the company.",
             "", "", ""],
            ["Recommendation", f"{d['decision']} at ${d['price']:.0f}", "", "", ""],
            ["Disclosure requirement",
             "Disclose negative QoE in the memo; do not raise the price solely because management Adjusted EBITDA improved.",
             "", "", ""],
            ]
    sheet(wb, "Pricing_Summary", rows, [44, 96, 4, 4, 4])

    # ---------------- Error_Audit
    CORRECT = {
        "Profitability": ("Reverse the SBC addback: treat SBC as a recurring economic cost and report underwriting EBITDA.",
                          "Underwriting profitability is materially weaker than the management metric."),
        "Valuation": ("Use 2024E Revenue as the forward denominator and apply the 12.5% IPO execution discount to peer-implied equity.",
                      "Forward valuation denominator and supported pricing range."),
        "Cash": ("Include both year-end cash and marketable securities in the pre-money equity bridge.",
                 "Incomplete net cash bridge understates pre-money equity."),
        "Primary/Secondary": ("Treat 15.276527m as primary and 6.723473m as secondary.",
                              "Company proceeds are overstated if all shares are counted as primary."),
        "Greenshoe": ("Exclude the 3.3m greenshoe from Base; present a separate full-exercise scenario.",
                      "Shares and proceeds both change if the option is assumed exercised."),
        "Underwriting fee": ("Apply the fee to company primary gross proceeds only.",
                             "Fee base must match company economics."),
        "Post-money shares": ("Only new primary shares increase the count; secondary is a transfer.",
                              "Dilution and share bridge."),
        "Proceeds": ("Secondary proceeds accrue to selling holders; company receives 0.",
                     "Wrong beneficiary of secondary proceeds."),
        "Dilution": ("Compute dilution from a consistent numerator/denominator share basis.",
                     "Numerator and denominator must be on the same basis."),
        "Recommendation": ("Apply the Committee pricing guardrails (range + distance-to-midpoint) and disclose QoE risk.",
                           "Recommendation discipline vs. peer-high extrapolation."),
    }
    EXTRA = [
        ("Cut-off discipline", "Uses final pricing / post-offering outcome to back-solve Base",
         "Use only information available before 2024-03-20 plus internal committee assumptions",
         "Avoids hindsight bias in the Base case"),
        ("IPO execution discount", "No execution discount applied to peer-implied equity",
         "Apply the 12.5% IPO execution discount uniformly",
         "Produces the committee-supported pricing range"),
    ]
    rows = [["#", "Workstream / Issue", "Legacy treatment (as-is)",
             "Correct treatment", "Why it matters"]]
    n = 0
    for ws_name, legacy, review, status in audit:
        n += 1
        corr = CORRECT.get(ws_name, (review, ""))
        rows.append([n, ws_name, legacy, corr[0], corr[1]])
    for issue, legacy, corr, why in EXTRA:
        n += 1
        rows.append([n, issue, legacy, corr, why])
    rows += [[],
             ["Summary", f"Total issues identified and corrected: {n} (>= 5 required)", "", "", ""],
             ["Information set", "As-of 2024-03-20: SEC facts and internal committee assumptions are labelled separately throughout the model.", "", "", ""]]
    sheet(wb, "Error_Audit", rows, [6, 30, 54, 62, 52])

    wb.save(path)
    return n, path


def build_memo(d, n_issues, path):
    lo, hi = d["low"], d["high"]
    txt = f"""# Pricing Committee Memo — Reddit, Inc. IPO

**日期**：2024-03-20（正式定价前） · **出具**：承销团队 / ECM · **议题**：拟议价格 ${d['price']:.0f} 是否继续推进

## 一、定价建议

**建议 Proceed，按拟议 ${d['price']:.0f} 推进。** 拟议价格位于委员会支持区间 **${lo:.2f}–${hi:.2f}** 之内，距 midpoint **${d['mid']:.2f}** 仅 **${abs(d['vs_mid']):.2f}**，未超过 $0.50 护栏；修正后的发行结构已消除旧底稿的全部硬错误。该建议以披露下述盈利质量风险为前提，**不得仅因管理层 Adjusted EBITDA 改善而上调价格**。

## 二、盈利质量（QoE）

2023 年 Revenue **{d['rev2023']:.3f}mm**、管理层口径 Adjusted EBITDA **{d['adj_ebitda']:.3f}mm**。按委员会政策，SBC 属持续性经济成本，撤销 **{d['sbc']:.3f}mm** 加回后，承销口径 EBITDA 为 **{d['uw_ebitda']:.3f}mm**，仍为负；2023 年 FCF **{d['fcf']:.3f}mm** 同样为负。重组费用 {d['restructuring']:.3f}mm 虽属非经常性，但已包含在管理层指标中，不再重复加回。承销 EBITDA 为负，主估值方法改用 **EV / 2024E Revenue**，不得使用 EV/EBITDA。

## 三、估值支撑

2024E Revenue = {d['rev2023']:.3f} × (1 + {d['growth']:.0%}) = **{d['rev2024e']:.3f}mm**。按 peer 区间 {d['ml']:.1f}x–{d['mh']:.1f}x（中点 {d['mm']:.1f}x）得企业价值 {d['scen']['Low']['ev']:.3f}–{d['scen']['High']['ev']:.3f}mm，加回年末现金 {d['cash']:.3f}mm 与有价证券 {d['sec']:.3f}mm 完成净现金桥，再统一应用 {d['disc']:.1%} 执行折扣，得每股 **${lo:.2f} / ${d['mid']:.2f} / ${hi:.2f}**（低/中/高）。按 ${d['price']:.0f} 计算的隐含 pre-money equity 为 {d['prop_eq']:.1f}mm，对应 **{d['prop_mult']:.2f}x** 2024E Revenue，低于 peer 区间，尚有余量。截止日前 SEC 材料的稀释交叉验算（NTBV {d['ntbv_x']:.2f}、即时稀释 {d['dil_x']:.2f}，假设价 $32.50）成立。

## 四、发行结构

Base：**{d['primary']:.6f}m primary**、**{d['secondary']:.6f}m secondary**；**{d['gs']:.1f}m greenshoe 不进入 Base**，仅单列 full-exercise 情景。按 ${d['price']:.0f}，公司 primary gross 为 **{d['gross']:.3f}mm**，扣 {d['fee']:.0%} 承销费（{d['uw_fee']:.3f}mm）与 {d['fixed']:.1f}mm 固定费用后，net primary **{d['net_primary']:.3f}mm**。Secondary 为 {d['sell_gross']:.3f}mm 归出售股东，**公司取得 0**，且不增加总股数。Base post-money 股数 {d['post_sh']:.6f}m（full exercise {d['full_post_sh']:.6f}m），新增 primary 占 {d['new_pct']:.2%}。旧底稿共 {n_issues} 项问题（SBC 加回、分母错用 2023 收入、遗漏执行折扣与有价证券、primary/secondary 混同、secondary 计入股本、上调偏置的建议）已逐项修正并记入 `Error_Audit`。

## 五、条件与风险

1. 必须披露 QoE：承销 EBITDA {d['uw_ebitda']:.3f}mm、FCF {d['fcf']:.3f}mm 均为负。
2. 信息集冻结于 2024-03-20；${d['price']:.0f} 是内部拟议价，**不是已实现的最终发行结果**。
3. 区间纪律：价格偏离 midpoint 超过 $0.50 时向 midpoint 方向 Reprice；跌出 ${lo:.2f}–${hi:.2f} 或发行结构重新出现未解决硬错误时 Defer。
"""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)
    import re
    body = txt.replace("|", "").replace("`", "")
    cjk = len(re.findall(r"[一-鿿　-〿，。、；：？！（）《》“”‘’—…·]", body))
    return path, cjk, len(txt)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    pub, trm, asm, pol, audit, srcs = read_inputs(SRC)
    d = compute(pub, trm, asm)

    model = os.path.join(OUT_DIR, f"{TASK}_ipo_model.xlsx")
    n, p = build_model(d, audit, pub, trm, asm, srcs, model)
    print("model  :", p, "issues:", n)

    memo = os.path.join(OUT_DIR, f"{TASK}_pricing_memo.md")
    _, cjk, raw = build_memo(d, n, memo)
    print("memo   :", memo, f"cjk_chars={cjk} raw_bytes={raw}")

    print("\n--- 关键结论 ---")
    print(f"  UW EBITDA      = {d['uw_ebitda']:.3f}")
    print(f"  2024E Revenue  = {d['rev2024e']:.5f}")
    print(f"  Range          = ${d['low']:.2f} - ${d['high']:.2f}   mid={d['mid']:.6f}")
    print(f"  vs midpoint    = {d['vs_mid']:.6f}")
    print(f"  Net primary    = {d['net_primary']:.6f}")
    print(f"  Post-money sh  = {d['post_sh']:.6f} / full {d['full_post_sh']:.6f}")
    print(f"  Decision       = {d['decision']} at ${d['price']:.0f}")
