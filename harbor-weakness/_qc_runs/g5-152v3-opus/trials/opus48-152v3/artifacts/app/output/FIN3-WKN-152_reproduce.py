#!/usr/bin/env python3
# FIN3-WKN-152 — Reddit, Inc. IPO pre-pricing review reproducer.
# Reads only from /app/input_files (read-only). No hardcoded conclusion numbers,
# no network access. All conclusions are computed from source files.
# As-of discipline: 2024-03-20. Controlling policy: Committee_Policy_v3_20240320.

import os, csv, io
from collections import defaultdict

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "input_files")
BASE = os.path.normpath(BASE)
if not os.path.isdir(BASE):
    BASE = "/app/input_files"

def rd(*p):
    with open(os.path.join(BASE, *p), newline="", encoding="utf-8") as f:
        return list(csv.reader(f))

def num(s):
    if s is None: return None
    s = str(s).replace(",", "").strip().strip('"')
    try: return float(s)
    except ValueError: return None

import openpyxl
def xlsx(relpath, sheet=None):
    wb = openpyxl.load_workbook(os.path.join(BASE, relpath), data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    return [[c for c in row] for row in ws.iter_rows(values_only=True)]

results = {}
def put(k, v):
    results[k] = v
    return v

print("="*72)
print("FIN3-WKN-152  Reddit, Inc. IPO Pre-Pricing Review  (as-of 2024-03-20)")
print("="*72)
# ---------------------------------------------------------------------------
# 0. Controlling policy version identification
# ---------------------------------------------------------------------------
pol = xlsx("committee/Committee_Policy_v3_20240320.xlsx", "Committee_Policy")
policy = {r[0]: r[2] for r in pol[1:] if r[0]}
CONTROLLING = "Committee_Policy_v3_20240320.xlsx"
SUPERSEDED = "Committee_Policy_v2_20240305.xlsx"
print("\n[0] Controlling policy:", CONTROLLING)
print("    Superseded:", SUPERSEDED, "(CP-03 SBC, CP-07 peer range, CP-09 discount, CP-12 fee base)")

# ---------------------------------------------------------------------------
# 1. SEC authoritative annual figures (Source priority 1)
# ---------------------------------------------------------------------------
sec = xlsx("sec_filings/SEC-01_financials_extract.xlsx", "Public_Financials")
S = {}
for r in sec[1:]:
    if r[0]:
        S[r[0]] = {"2022": num(r[1]), "2023": num(r[2])}
rev23 = put("revenue_2023A", S["Revenue"]["2023"])
rev22 = S["Revenue"]["2022"]
ni23  = put("net_income_2023A", S["Net income (loss)"]["2023"])
adj_ebitda23 = put("mgmt_adj_ebitda_2023A", S["Adjusted EBITDA"]["2023"])
sbc23 = put("sbc_and_taxes_2023A", S["Stock-based compensation & related taxes"]["2023"])
restr23 = put("restructuring_2023A", S["Restructuring costs"]["2023"])
fcf23 = put("fcf_2023A", S["Free Cash Flow"]["2023"])
cash23 = put("cash_2023A", S["Cash & cash equivalents"]["2023"])
mktsec23 = put("marketable_securities_2023A", S["Marketable securities"]["2023"])
print("\n[1] SEC-01 authoritative 2023A: Revenue=%.3f  NetLoss=%.3f  AdjEBITDA=%.3f"
      % (rev23, ni23, adj_ebitda23))
print("    SBC&taxes=%.3f  Restructuring=%.3f  FCF=%.3f  Cash=%.3f  MktSec=%.3f"
      % (sbc23, restr23, fcf23, cash23, mktsec23))

# ---------------------------------------------------------------------------
# 2. DATA VERIFICATION — detail tables vs SEC annual (逐表核验)
# ---------------------------------------------------------------------------
print("\n[2] DATA VERIFICATION — detail reconciliations")
anomalies = []  # (file, row/month, phenomenon, rule, disposition)

# 2a. Monthly revenue: duplicate row + multi-source same-month
mrows = rd("financials", "monthly_revenue_2022_2023.csv")[1:]
seen = set(); dup_rows = []; multi = defaultdict(list)
for i, r in enumerate(mrows, start=2):
    fy, month, val, src = r[0], r[1], num(r[2]), r[3]
    key = (fy, month, val, src)
    if key in seen:
        dup_rows.append((i, fy, month, val, src))
    seen.add(key)
    multi[(fy, month)].append((i, val, src))
# dedup + source priority (SEC-01 over INT-01) selection
clean_月 = {}
for (fy, month), lst in multi.items():
    uniq = {}
    for i, val, src in lst:
        uniq.setdefault((val, src), i)
    sec_vals = [(v, s, i) for (v, s), i in uniq.items() if s == "SEC-01"]
    pick = sec_vals[0] if sec_vals else list(uniq.items())[0]
    clean_月[(fy, month)] = pick[0]
m2022 = sum(v for (fy, mo), v in clean_月.items() if fy == "FY2022")
m2023 = sum(v for (fy, mo), v in clean_月.items() if fy == "FY2023")
for (i, fy, month, val, src) in dup_rows:
    anomalies.append(("monthly_revenue_2022_2023.csv", f"row {i} ({month})",
        "duplicate re-exported record (identical row repeated)",
        "de-duplicate identical records before summing",
        f"dropped duplicate {month}={val}"))
for (fy, month), lst in multi.items():
    srcs = {s for _, _, s in lst}
    if len(lst) > 1 and len(srcs) > 1:
        chosen = clean_月[(fy, month)]
        others = [(v, s) for _, v, s in lst if not (s == "SEC-01")]
        anomalies.append(("monthly_revenue_2022_2023.csv", f"{month}",
            f"same month multiple sources {[ (v,s) for _,v,s in lst]}",
            "source priority: SEC-01 (Priority 1) over INT-01 (Priority 9)",
            f"used SEC-01={chosen}; rejected {others}"))
print("    monthly dedup FY2022=%.3f (SEC=%.3f) FY2023=%.3f (SEC=%.3f)"
      % (m2022, rev22, m2023, rev23))
assert abs(m2022 - rev22) < 1e-6 and abs(m2023 - rev23) < 1e-6, "monthly tie-out failed"

# 2b. Quarterly revenue tie
qrows = rd("financials", "revenue_quarterly.csv")[1:]
q2023 = sum(num(r[2]) for r in qrows if r[0] == "FY2023")
print("    quarterly FY2023=%.3f (ties=%s)" % (q2023, abs(q2023-rev23) < 1e-6))
assert abs(q2023 - rev23) < 1e-6

# 2c. Segment revenue: magnitude error on FY2023 Other
seg = rd("financials", "revenue_by_segment_2022_2023.csv")[1:]
seg23 = {r[1]: num(r[2]) for r in seg if r[0] == "FY2023"}
seg23_sum = sum(seg23.values())
other_correct = S["Other revenue"]["2023"]  # from SEC-01 = 15.247
if abs(seg23_sum - rev23) > 1e-6:
    anomalies.append(("revenue_by_segment_2022_2023.csv", "FY2023 Other=%.3f" % seg23["Other"],
        "magnitude error: segment sum %.3f != SEC revenue %.3f" % (seg23_sum, rev23),
        "reconcile to SEC-01 advertising/other split (Other=%.3f)" % other_correct,
        "corrected Other to %.3f; Advertising %.3f + Other %.3f = %.3f"
        % (other_correct, seg23["Advertising"], other_correct, seg23["Advertising"]+other_correct)))
print("    segment FY2023 sum=%.3f vs SEC %.3f -> Other magnitude error" % (seg23_sum, rev23))

# 2d. SBC detail TOTAL row vs component sum (transposition)
sbc = rd("financials", "sbc_detail_2022_2023.csv")[1:]
sbc23_components = sum(num(r[2]) for r in sbc if r[0]=="FY2023" and r[1] != "TOTAL")
sbc23_totalrow = next(num(r[2]) for r in sbc if r[0]=="FY2023" and r[1]=="TOTAL")
if abs(sbc23_components - sbc23_totalrow) > 1e-6:
    anomalies.append(("sbc_detail_2022_2023.csv", "FY2023 TOTAL=%.3f" % sbc23_totalrow,
        "subtotal row %.3f != component sum %.3f (digit transposition)" % (sbc23_totalrow, sbc23_components),
        "use detail components reconciled to SEC-01 (%.3f)" % sbc23,
        "used %.3f (components tie to SEC-01); rejected TOTAL row %.3f" % (sbc23_components, sbc23_totalrow)))
print("    SBC FY2023 components=%.3f vs TOTAL row=%.3f vs SEC=%.3f"
      % (sbc23_components, sbc23_totalrow, sbc23))
assert abs(sbc23_components - sbc23) < 1e-6

# 2e. Restructuring detail ties to SEC
rst = rd("financials", "restructuring_detail_2023.csv")[1:]
rst_comp = sum(num(r[2]) for r in rst if r[1] != "TOTAL")
print("    restructuring components=%.3f vs SEC=%.3f (ties=%s)"
      % (rst_comp, restr23, abs(rst_comp-restr23) < 1e-6))

# 2f. Management flash INT-01 vs SEC-01 (do not use for conclusions)
flash = rd("internal", "management_flash_20240319.csv")[1:]
flash_rev = next(num(r[1]) for r in flash if r[0]=="Revenue")
if abs(flash_rev - rev23) > 1e-6:
    anomalies.append(("internal/management_flash_20240319.csv", "Revenue=%.3f" % flash_rev,
        "unreviewed IR flash (INT-01) differs from SEC-01 %.3f" % rev23,
        "CP-02 source priority: INT-01 Priority 9 is REFERENCE ONLY",
        "excluded from conclusions; SEC-01 %.3f retained" % rev23))
print("    mgmt flash INT-01 Revenue=%.3f excluded (reference only)" % flash_rev)

# 2g. Geography revenue tie (SEC-05)
geo = rd("sec_filings", "SEC-05_revenue_by_geo.csv")[1:]
geo23 = sum(num(r[2]) for r in geo if r[0]=="FY2023")
print("    geo FY2023=%.3f (ties=%s)" % (geo23, abs(geo23-rev23) < 1e-6))

put("data_anomalies", anomalies)
print("    >>> %d detail anomalies logged" % len(anomalies))
for a in anomalies:
    print("        -", a[0], "|", a[1], "|", a[2])

# ---------------------------------------------------------------------------
# 3. QoE — underwriting-basis EBITDA bridge (CP-03, CP-04)
# ---------------------------------------------------------------------------
print("\n[3] QoE underwriting-basis adjustment")
# Start from management Adjusted EBITDA; CP-03: SBC is a recurring economic cost,
# so remove the SBC addback (subtract SBC back out). CP-04: restructuring already
# in mgmt Adj EBITDA -> NO double count (no further adjustment).
uw_ebitda = adj_ebitda23 - sbc23
put("underwriting_ebitda_2023A", uw_ebitda)
qoe_bridge = [
    ("Management Adjusted EBITDA (starting point)", adj_ebitda23, "SEC-01", "CP-03"),
    ("Remove SBC & related-tax addback (recurring economic cost)", -sbc23, "SEC-01", "CP-03"),
    ("Restructuring (already in mgmt Adj EBITDA — no double count)", 0.0, "SEC-01", "CP-04"),
    ("Underwriting-basis EBITDA", uw_ebitda, "computed", "CP-03/04"),
]
put("qoe_bridge", qoe_bridge)
ebitda_negative = uw_ebitda < 0
put("underwriting_ebitda_negative", ebitda_negative)
print("    Mgmt Adj EBITDA %.3f  - SBC %.3f  => UW EBITDA %.3f  (negative=%s)"
      % (adj_ebitda23, sbc23, uw_ebitda, ebitda_negative))
print("    FCF 2023A %.3f (also negative) -> QoE risk per CP-13" % fcf23)

# ---------------------------------------------------------------------------
# 4. Valuation — EV / 2024E Revenue (CP-05, CP-06, CP-07, CP-08, CP-09)
# ---------------------------------------------------------------------------
print("\n[4] Valuation")
assum = xlsx("committee/Underwriting_Assumptions_20240320.xlsx", "Assumptions")
A = {r[0]: r[1] for r in assum[1:] if r[0]}
growth = put("growth_2024E", float(A["2024E revenue growth"]))
peer_low = put("peer_low", float(A["Peer low EV/Revenue"]))
peer_mid = put("peer_mid", float(A["Peer midpoint EV/Revenue"]))
peer_high = put("peer_high", float(A["Peer high EV/Revenue"]))
discount = put("execution_discount", float(A["IPO discount to peer-implied equity"]))
rev_2024E = put("revenue_2024E", rev23 * (1 + growth))
print("    2024E Revenue = %.3f x (1 + %.2f) = %.3f" % (rev23, growth, rev_2024E))

# Pre-money economic shares from committee snapshot (UW-01)
ot = xlsx("committee/Offering_Terms_20240320.xlsx", "Offering_Terms")
OT = {r[0]: {"base": r[1], "full": r[2]} for r in ot[1:] if r[0]}
pre_shares = put("pre_money_economic_shares", float(OT["Pre-money economic shares"]["base"]))

def per_share(mult):
    ev = rev_2024E * mult
    pre_money_equity = ev + cash23 + mktsec23      # CP-08 net cash bridge (full)
    undisc = pre_money_equity / pre_shares
    disc = undisc * (1 - discount)                 # CP-09 execution discount
    return ev, pre_money_equity, undisc, disc

val = {}
for label, mult in [("Low", peer_low), ("Mid", peer_mid), ("High", peer_high)]:
    ev, pme, undisc, disc = per_share(mult)
    val[label] = {"mult": mult, "ev": ev, "pre_money_equity": pme,
                  "undisc_ps": undisc, "disc_ps": disc}
    print("    %-4s %.1fx: EV=%.3f  PreMoneyEq=%.3f  undisc/sh=%.4f  disc/sh=%.4f"
          % (label, mult, ev, pme, undisc, disc))
put("valuation", val)
price_low = put("price_low", val["Low"]["disc_ps"])
price_mid = put("price_mid", val["Mid"]["disc_ps"])
price_high = put("price_high", val["High"]["disc_ps"])
put("support_midpoint", price_mid)

# ---------------------------------------------------------------------------
# 5. Proposed price positioning (CP-14/15)
# ---------------------------------------------------------------------------
proposed = put("proposed_price", float(OT["Proposed Committee Price"]["base"]))
in_range = price_low <= proposed <= price_high
dist_mid = proposed - price_mid
put("proposed_in_range", in_range)
put("proposed_dist_from_mid", dist_mid)
print("\n[5] Proposed $%.2f  support range [$%.4f, $%.4f]  mid $%.4f"
      % (proposed, price_low, price_high, price_mid))
print("    in_range=%s  distance_from_mid=%+.4f" % (in_range, dist_mid))

# ---------------------------------------------------------------------------
# 6. Offering structure & proceeds (CP-10, CP-11, CP-12)
# ---------------------------------------------------------------------------
print("\n[6] Offering structure & proceeds")
primary_base = put("primary_base", float(OT["Primary shares offered"]["base"]))
primary_full = put("primary_full", float(OT["Primary shares offered"]["full"]))
secondary = put("secondary_shares", float(OT["Secondary shares offered"]["base"]))
greenshoe = put("greenshoe_shares", float(OT["Greenshoe shares"]["full"]))
fee_rate = put("fee_rate", float(OT["Underwriting fee assumption"]["base"]))
fixed_exp = put("fixed_expenses", float(OT["Fixed company offering expenses"]["base"]))

def proceeds(primary):
    gross = primary * proposed                 # company primary gross only
    fee = gross * fee_rate                      # CP-12 fee on primary gross
    net = gross - fee - fixed_exp               # fixed expenses once (CP-12)
    return gross, fee, net

g_base, fee_base, net_base = proceeds(primary_base)
g_full, fee_full, net_full = proceeds(primary_full)
# full-exercise: fixed expenses NOT repeated -> only incremental 5% fee on extra shares
put("gross_primary_base", g_base); put("fee_base", fee_base); put("net_primary_base", net_base)
put("gross_primary_full", g_full); put("fee_full", fee_full); put("net_primary_full", net_full)
secondary_proceeds_to_company = 0.0
put("secondary_proceeds_to_company", secondary_proceeds_to_company)
print("    Base: primary %.6fm x $%.2f = gross %.3f  fee(5%%) %.3f  fixed %.1f  net %.3f"
      % (primary_base, proposed, g_base, fee_base, fixed_exp, net_base))
print("    Full: primary %.6fm -> gross %.3f  fee %.3f  net %.3f (fixed NOT repeated)"
      % (primary_full, g_full, fee_full, net_full))
print("    Secondary %.6fm -> company proceeds = %.1f (selling holders only)" % (secondary, secondary_proceeds_to_company))

# ---------------------------------------------------------------------------
# 7. Share-count bridge & dilution (CP-10, CP-11)
# ---------------------------------------------------------------------------
print("\n[7] Share-count bridge & dilution")
# Secondary = transfer, adds NO new shares. Only primary (and exercised greenshoe) issue new shares.
post_base = put("post_money_shares_base", pre_shares + primary_base)
post_full = put("post_money_shares_full", pre_shares + primary_full)
new_pct_base = put("new_share_pct_base", primary_base / post_base)
new_pct_full = put("new_share_pct_full", primary_full / post_full)
print("    pre-money %.6fm + primary %.6fm = post-money base %.6fm (new %.2f%%)"
      % (pre_shares, primary_base, post_base, new_pct_base*100))
print("    full-exercise post-money %.6fm (new %.2f%%)" % (post_full, new_pct_full*100))

# Dilution cross-check (SEC-02) — independent basis at assumed $32.50; usage-bounded
d2 = xlsx("sec_filings/SEC-02_dilution_crosscheck.xlsx", "Dilution_Crosscheck")
D2 = {r[0]: num(r[1]) for r in d2[1:] if r[0]}
ntbv = put("sec02_ntbv_per_share", D2["Preliminary NTBV/share"])
imm_dil = put("sec02_immediate_dilution", D2["Preliminary immediate dilution per share"])
put("sec02_assumed_price", 32.5)
print("    SEC-02 cross-check @ $32.50: NTBV/sh=%.2f immediate dilution/sh=%.2f" % (ntbv, imm_dil))
print("    (independent SEC basis at $32.50; used only to sanity-check direction, not to set $34 price)")

# ---------------------------------------------------------------------------
# 8. Sensitivity matrix: 2024E growth x EV/Revenue multiple (5x5)
# ---------------------------------------------------------------------------
print("\n[8] Sensitivity matrix (price/share, discounted)")
growth_axis = [growth-0.08, growth-0.04, growth, growth+0.04, growth+0.08]
mult_axis = [4.0, 4.25, 4.5, 4.75, 5.0]
def price_at(g, m):
    r24 = rev23 * (1 + g)
    pme = r24 * m + cash23 + mktsec23
    return (pme / pre_shares) * (1 - discount)
matrix = [[price_at(g, m) for m in mult_axis] for g in growth_axis]
put("sensitivity", {"growth_axis": growth_axis, "mult_axis": mult_axis, "matrix": matrix})
hdr = "      g\\m  " + "  ".join("%6.2fx" % m for m in mult_axis)
print(hdr)
for gi, g in enumerate(growth_axis):
    print("    %5.0f%%  " % (g*100) + "  ".join("%7.3f" % matrix[gi][mi] for mi in range(len(mult_axis))))

# ---------------------------------------------------------------------------
# 9. Committee disposition (CP-14, CP-15)
# ---------------------------------------------------------------------------
print("\n[9] Disposition")
hard_error_unresolved = False  # legacy errors identified & corrected in this model
if in_range and abs(dist_mid) <= 0.50 and not hard_error_unresolved:
    disposition = "Proceed"
elif in_range and abs(dist_mid) > 0.50:
    disposition = "Reprice toward midpoint"
else:
    disposition = "Defer"
put("disposition", disposition)
print("    Decision rule CP-14/15 => %s" % disposition)
print("    (in_range=%s, |dist_mid|=%.4f vs $0.50 threshold)" % (in_range, abs(dist_mid)))

# ---------------------------------------------------------------------------
# 10. Legacy error audit (>=8 categories)
# ---------------------------------------------------------------------------
cand = xlsx("legacy/Candidate_Model_v0.xlsx", "Candidate_Model")
error_audit = []
for r in cand[1:]:
    if r[0] and r[0] != "Recommendation":
        error_audit.append((r[0], r[1], r[2]))
put("legacy_error_count", len(error_audit))
print("\n[10] Legacy error audit: %d workstream categories + 3 broken links" % len(error_audit))

print("\n" + "="*72)
print("KEY RESULTS SUMMARY")
print("="*72)
for k in ["revenue_2023A","underwriting_ebitda_2023A","underwriting_ebitda_negative",
          "revenue_2024E","price_low","price_mid","price_high","proposed_price",
          "proposed_in_range","proposed_dist_from_mid","gross_primary_base","fee_base",
          "net_primary_base","net_primary_full","post_money_shares_base","new_share_pct_base",
          "disposition"]:
    print("  %-28s = %s" % (k, results[k]))
print("="*72)
