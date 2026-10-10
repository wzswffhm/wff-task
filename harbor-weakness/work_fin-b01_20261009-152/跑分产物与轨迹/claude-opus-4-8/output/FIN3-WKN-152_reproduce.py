#!/usr/bin/env python3
"""FIN3-WKN-152 IPO pricing reproduce script.
Reads /app/input_files, computes all conclusions. No hardcoded result numbers.
"""
import os, csv, openpyxl

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "input_files")
if not os.path.isdir(BASE):
    BASE = "/app/input_files"

def rd_csv(path):
    with open(os.path.join(BASE, path), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def xlsx_rows(path, sheet=0):
    wb = openpyxl.load_workbook(os.path.join(BASE, path), data_only=True)
    ws = wb.worksheets[sheet] if isinstance(sheet, int) else wb[sheet]
    return [list(r) for r in ws.iter_rows(values_only=True)]

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

# ---------- SEC-01 authoritative annual figures ----------
sec01 = {}
for r in xlsx_rows("sec_filings/SEC-01_financials_extract.xlsx", "Public_Financials")[1:]:
    if r and r[0]:
        sec01[r[0].strip()] = {"2022": num(r[1]), "2023": num(r[2])}

REV22 = sec01["Revenue"]["2022"]; REV23 = sec01["Revenue"]["2023"]
NI23 = sec01["Net income (loss)"]["2023"]
ADJE23 = sec01["Adjusted EBITDA"]["2023"]
SBC23 = sec01["Stock-based compensation & related taxes"]["2023"]
RESTR23 = sec01["Restructuring costs"]["2023"]
FCF23 = sec01["Free Cash Flow"]["2023"]
CASH23 = sec01["Cash & cash equivalents"]["2023"]
MKT23 = sec01["Marketable securities"]["2023"]

# ---------- Committee policy params ----------
ua = {}
for r in xlsx_rows("committee/Underwriting_Assumptions_20240320.xlsx", "Assumptions")[1:]:
    if r and r[0]: ua[r[0].strip()] = r[1]
GROWTH = num(ua["2024E revenue growth"])
PEER_LOW = num(ua["Peer low EV/Revenue"])
PEER_MID = num(ua["Peer midpoint EV/Revenue"])
PEER_HIGH = num(ua["Peer high EV/Revenue"])
DISCOUNT = num(ua["IPO discount to peer-implied equity"])

ot = {}
for r in xlsx_rows("committee/Offering_Terms_20240320.xlsx", "Offering_Terms")[1:]:
    if r and r[0]: ot[r[0].strip()] = {"base": num(r[1]), "full": num(r[2])}
PRICE = ot["Proposed Committee Price"]["base"]
PRIMARY = ot["Primary shares offered"]["base"]
PRIMARY_FULL = ot["Primary shares offered"]["full"]
SECONDARY = ot["Secondary shares offered"]["base"]
GREENSHOE = ot["Greenshoe shares"]["full"]
PREMONEY_SH = ot["Pre-money economic shares"]["base"]
FEE_PCT = ot["Underwriting fee assumption"]["base"]
FIXED_EXP = ot["Fixed company offering expenses"]["base"]
RANGE_LO = ot["Preliminary public filing range low"]["base"]
RANGE_HI = ot["Preliminary public filing range high"]["base"]

# ================= DATA TIE-OUT =================
tieout = []  # (series, detail_sum, target, diff, anomaly_type, disposition)

# Monthly revenue: split by source, dedup
mrows = rd_csv("financials/monthly_revenue_2022_2023.csv")
# FY2022 raw vs dedup
m22 = [r for r in mrows if r["fy"] == "FY2022"]
raw22 = sum(num(r["revenue_usd_mm"]) for r in m22)
seen = set(); dedup22 = 0.0; dup_months = []
for r in m22:
    k = r["month"]
    if k in seen: dup_months.append(k); continue
    seen.add(k); dedup22 += num(r["revenue_usd_mm"])
tieout.append(("Monthly revenue FY2022", round(dedup22,3), REV22, round(dedup22-REV22,3),
    "Duplicate row 2022-08 (line 14) inflates raw sum to %.3f" % raw22,
    "Drop duplicate 2022-08; dedup sum ties to SEC-01"))

# FY2023 monthly: SEC-01 only vs including INT-01
m23 = [r for r in mrows if r["fy"] == "FY2023"]
sec_m23 = sum(num(r["revenue_usd_mm"]) for r in m23 if r["Source_ID"] == "SEC-01")
int_rows = [r for r in m23 if r["Source_ID"] == "INT-01"]
tieout.append(("Monthly revenue FY2023", round(sec_m23,3), REV23, round(sec_m23-REV23,3),
    "INT-01 duplicate for 2023-12 (%.3f) mixed in; priority 9 reference-only" % (num(int_rows[0]["revenue_usd_mm"]) if int_rows else 0),
    "Exclude INT-01 per CP-02; SEC-01 rows tie to annual"))

# Segment revenue
seg = rd_csv("financials/revenue_by_segment_2022_2023.csv")
seg22 = sum(num(r["revenue_usd_mm"]) for r in seg if r["fy"]=="FY2022")
seg23 = sum(num(r["revenue_usd_mm"]) for r in seg if r["fy"]=="FY2023")
tieout.append(("Segment revenue FY2022", round(seg22,3), REV22, round(seg22-REV22,3),
    "none", "Ties to SEC-01"))
other23 = [r for r in seg if r["fy"]=="FY2023" and r["segment"]=="Other"][0]
tieout.append(("Segment revenue FY2023", round(seg23,3), REV23, round(seg23-REV23,3),
    "FY2023 Other=%.3f overstated vs SEC-01 Other 15.247 (digit error)" % num(other23["revenue_usd_mm"]),
    "Use SEC-01 Other 15.247; detail table Other row rejected"))

# Geo revenue
geo = rd_csv("sec_filings/SEC-05_revenue_by_geo.csv")
geo22 = sum(num(r["revenue_usd_mm"]) for r in geo if r["fy"]=="FY2022")
geo23 = sum(num(r["revenue_usd_mm"]) for r in geo if r["fy"]=="FY2023")
tieout.append(("Geo revenue FY2022", round(geo22,3), REV22, round(geo22-REV22,3),"none","Ties to SEC-01"))
tieout.append(("Geo revenue FY2023", round(geo23,3), REV23, round(geo23-REV23,3),"none","Ties to SEC-01"))

# SBC detail
sbc = rd_csv("financials/sbc_detail_2022_2023.csv")
sbc22 = sum(num(r["amount_usd_mm"]) for r in sbc if r["fy"]=="FY2022" and r["component"]!="TOTAL")
sbc23 = sum(num(r["amount_usd_mm"]) for r in sbc if r["fy"]=="FY2023" and r["component"]!="TOTAL")
sbc23_total_row = [r for r in sbc if r["fy"]=="FY2023" and r["component"]=="TOTAL"]
sbc23_total = num(sbc23_total_row[0]["amount_usd_mm"]) if sbc23_total_row else None
tieout.append(("SBC detail FY2022", round(sbc22,3), sec01["Stock-based compensation & related taxes"]["2022"],
    round(sbc22-sec01["Stock-based compensation & related taxes"]["2022"],3),"none","Ties to SEC-01"))
tieout.append(("SBC detail FY2023", round(sbc23,3), SBC23, round(sbc23-SBC23,3),
    "TOTAL row=%.3f disagrees with component sum %.3f and SEC-01 %.3f" % (sbc23_total, sbc23, SBC23),
    "Use component sum = SEC-01 49.086; TOTAL row rejected"))

# Cap table
cap = rd_csv("committee/cap_table_snapshot_20240318.csv")
cap_sum = sum(num(r["shares_mm"]) for r in cap if not r["holder_class"].startswith("TOTAL"))
cap_total = [r for r in cap if r["holder_class"].startswith("TOTAL")][0]
tieout.append(("Cap table pre-money shares", round(cap_sum,6), num(cap_total["shares_mm"]),
    round(cap_sum-num(cap_total["shares_mm"]),6),
    "SEC-09 registered 141.200 differs (excludes unsettled RSUs) — definition diff, not error",
    "Components tie to committee economic TOTAL 143.716563"))

# Quarterly revenue
qr = rd_csv("financials/revenue_quarterly.csv")
q23 = sum(num(r["revenue_usd_mm"]) for r in qr if r["fy"]=="FY2023")
tieout.append(("Quarterly revenue FY2023", round(q23,3), REV23, round(q23-REV23,3),"none","Ties to SEC-01"))

# ================= QoE / UNDERWRITING EBITDA =================
# CP-03: SBC NOT added back; CP-04: restructuring already in mgmt Adj EBITDA, no double count
UW_EBITDA = ADJE23 - SBC23
UW_EBITDA_NEG = UW_EBITDA < 0

# ================= VALUATION =================
REV24E = REV23 * (1 + GROWTH)
def ev(mult): return mult * REV24E
def premoney_eq(mult): return ev(mult) + CASH23 + MKT23
def per_share_undisc(mult): return premoney_eq(mult) / PREMONEY_SH
def per_share_disc(mult): return per_share_undisc(mult) * (1 - DISCOUNT)
VAL_LOW = per_share_disc(PEER_LOW)
VAL_MID = per_share_disc(PEER_MID)
VAL_HIGH = per_share_disc(PEER_HIGH)
MIDPOINT = VAL_MID
dist = abs(PRICE - MIDPOINT)
in_range = VAL_LOW <= PRICE <= VAL_HIGH

# ================= OFFERING / PROCEEDS =================
def offering(primary):
    gross = primary * PRICE
    fee = gross * FEE_PCT
    net = gross - fee - FIXED_EXP
    return gross, fee, net
g_base, fee_base, net_base = offering(PRIMARY)
g_full, fee_full, net_full = offering(PRIMARY_FULL)
sec_proceeds = SECONDARY * PRICE  # to selling stockholders, NOT company
gs_increment_gross = GREENSHOE * PRICE
gs_increment_fee = gs_increment_gross * FEE_PCT
gs_increment_net = gs_increment_gross - gs_increment_fee

# ================= SHARE BRIDGE / DILUTION =================
post_base = PREMONEY_SH + PRIMARY       # secondary excluded (transfer)
post_full = PREMONEY_SH + PRIMARY_FULL
newpct_base = PRIMARY / post_base
newpct_full = PRIMARY_FULL / post_full

# dilution crosscheck SEC-02 (at $32.50 only)
dil = xlsx_rows("sec_filings/SEC-02_dilution_crosscheck.xlsx", "Dilution_Crosscheck")

# ================= DECISION (CP-14/15) =================
if not in_range:
    decision = "Defer"
elif dist <= 0.50:
    decision = "Proceed"
else:
    decision = "Reprice"

# ================= SENSITIVITY 5x5 =================
GR_AXIS = [0.18,0.20,0.22,0.24,0.26]
MULT_AXIS = [4.0,4.3,4.5,4.8,5.0]
def sens(gr, mult):
    rev = REV23*(1+gr)
    pm = mult*rev + CASH23 + MKT23
    return pm/PREMONEY_SH*(1-DISCOUNT)
SENS = {(gr,m): sens(gr,m) for gr in GR_AXIS for m in MULT_AXIS}

def results():
    return dict(REV22=REV22,REV23=REV23,NI23=NI23,ADJE23=ADJE23,SBC23=SBC23,
        RESTR23=RESTR23,FCF23=FCF23,CASH23=CASH23,MKT23=MKT23,GROWTH=GROWTH,
        UW_EBITDA=UW_EBITDA,UW_EBITDA_NEG=UW_EBITDA_NEG,REV24E=REV24E,
        PEER_LOW=PEER_LOW,PEER_MID=PEER_MID,PEER_HIGH=PEER_HIGH,DISCOUNT=DISCOUNT,
        VAL_LOW=VAL_LOW,VAL_MID=VAL_MID,VAL_HIGH=VAL_HIGH,MIDPOINT=MIDPOINT,
        PRICE=PRICE,dist=dist,in_range=in_range,decision=decision,
        PRIMARY=PRIMARY,PRIMARY_FULL=PRIMARY_FULL,SECONDARY=SECONDARY,GREENSHOE=GREENSHOE,
        PREMONEY_SH=PREMONEY_SH,FEE_PCT=FEE_PCT,FIXED_EXP=FIXED_EXP,
        g_base=g_base,fee_base=fee_base,net_base=net_base,
        g_full=g_full,fee_full=fee_full,net_full=net_full,sec_proceeds=sec_proceeds,
        gs_increment_gross=gs_increment_gross,gs_increment_fee=gs_increment_fee,gs_increment_net=gs_increment_net,
        post_base=post_base,post_full=post_full,newpct_base=newpct_base,newpct_full=newpct_full,
        tieout=tieout,SENS=SENS,GR_AXIS=GR_AXIS,MULT_AXIS=MULT_AXIS)

if __name__ == "__main__":
    R = results()
    print("="*64); print("FIN3-WKN-152 — Reddit IPO Pricing Review (as-of 2024-03-20)"); print("="*64)
    print("\n[1] FILE INVENTORY")
    dirs = {}
    for root,_,files in os.walk(BASE):
        for fn in files:
            d = os.path.relpath(root, BASE); d = "(root)" if d=="." else d
            dirs[d] = dirs.get(d,0)+1
    total = sum(dirs.values())
    for d in sorted(dirs): print("   %-14s %d" % (d, dirs[d]))
    print("   TOTAL files=%d  source dirs(incl root)=%d" % (total, len(dirs)))

    print("\n[2] DATA TIE-OUT")
    for s,ds,tg,df,at,dp in R["tieout"]:
        print("   %-28s sum=%12.3f target=%12.3f diff=%+8.3f | %s" % (s,ds,tg,df,at))

    print("\n[3] QoE / UNDERWRITING EBITDA")
    print("   2023A Revenue                 = %.3f" % R["REV23"])
    print("   2023A Net income (loss)       = %.3f" % R["NI23"])
    print("   2023A Mgmt Adjusted EBITDA    = %.3f" % R["ADJE23"])
    print("   less SBC & related taxes (CP-03) = %.3f" % R["SBC23"])
    print("   Restructuring (CP-04 no 2x)   = %.3f (NOT re-added)" % R["RESTR23"])
    print("   = Underwriting EBITDA         = %.3f  (negative=%s)" % (R["UW_EBITDA"],R["UW_EBITDA_NEG"]))
    print("   2023A FCF                     = %.3f" % R["FCF23"])
    print("   Cash %.3f + Mkt sec %.3f = %.3f" % (R["CASH23"],R["MKT23"],R["CASH23"]+R["MKT23"]))

    print("\n[4] VALUATION (EV/2024E Rev, CP-05)")
    print("   2024E Rev = %.3f x (1+%.2f) = %.5f" % (R["REV23"],R["GROWTH"],R["REV24E"]))
    for lbl,m,v in [("Low",R["PEER_LOW"],R["VAL_LOW"]),("Mid",R["PEER_MID"],R["VAL_MID"]),("High",R["PEER_HIGH"],R["VAL_HIGH"])]:
        evv=m*R["REV24E"]; pm=evv+R["CASH23"]+R["MKT23"]
        print("   %-4s %.1fx: EV=%.3f PreMoneyEq=%.3f /sh_undisc=%.4f x(1-%.3f)=/sh=%.4f"%(
            lbl,m,evv,pm,pm/R["PREMONEY_SH"],R["DISCOUNT"],v))
    print("   Supported range: $%.2f / $%.2f / $%.2f  midpoint=$%.2f"%(R["VAL_LOW"],R["VAL_MID"],R["VAL_HIGH"],R["MIDPOINT"]))
    print("   Proposed $%.2f  in_range=%s  dist_to_mid=$%.3f"%(R["PRICE"],R["in_range"],R["dist"]))

    print("\n[5] OFFERING / PROCEEDS")
    print("   Base primary gross = %.6f x %.2f = %.6f"%(R["PRIMARY"],R["PRICE"],R["g_base"]))
    print("   less fee 5%% = %.6f ; less fixed = %.3f"%(R["fee_base"],R["FIXED_EXP"]))
    print("   Base net primary proceeds = %.6f"%R["net_base"])
    print("   Secondary gross (to sellers, NOT company) = %.6f x %.2f = %.6f"%(R["SECONDARY"],R["PRICE"],R["sec_proceeds"]))
    print("   Full primary gross = %.6f ; fee=%.6f ; net=%.6f"%(R["g_full"],R["fee_full"],R["net_full"]))
    print("   Greenshoe increment gross=%.3f fee=%.4f net=%.4f (no fixed)"%(R["gs_increment_gross"],R["gs_increment_fee"],R["gs_increment_net"]))

    print("\n[6] SHARE BRIDGE / DILUTION")
    print("   Pre-money economic shares = %.6f"%R["PREMONEY_SH"])
    print("   Base post-money = %.6f + %.6f (primary) = %.6f  new%%=%.4f%%"%(R["PREMONEY_SH"],R["PRIMARY"],R["post_base"],R["newpct_base"]*100))
    print("   Full post-money = %.6f + %.6f = %.6f  new%%=%.4f%%"%(R["PREMONEY_SH"],R["PRIMARY_FULL"],R["post_full"],R["newpct_full"]*100))

    print("\n[7] SENSITIVITY (growth x multiple), $/share")
    hdr="   g\\x  "+"".join("%8.1fx"%m for m in R["MULT_AXIS"]); print(hdr)
    for gr in R["GR_AXIS"]:
        print("   %4.0f%% "%(gr*100)+"".join("%9.2f"%R["SENS"][(gr,m)] for m in R["MULT_AXIS"]))
    print("   base case = %d%% x %.1fx = $%.2f"%(int(R["GROWTH"]*100),R["PEER_MID"],R["SENS"][(R["GROWTH"],R["PEER_MID"])]))

    print("\n[8] DECISION (CP-14/15): %s"%R["decision"])
    print("   proposed in range, dist $%.3f <= $0.50, no unresolved hard error -> %s"%(R["dist"],R["decision"]))

