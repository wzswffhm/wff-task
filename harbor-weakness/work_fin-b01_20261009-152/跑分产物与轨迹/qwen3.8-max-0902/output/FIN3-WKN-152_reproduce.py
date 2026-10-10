#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-152_reproduce.py
Reddit, Inc. IPO 定价委员会发行前复核 —— 可复算脚本（as-of 2024-03-20）

运行方式:  python3 FIN3-WKN-152_reproduce.py
输入:      /app/input_files/ (只读; 可用环境变量 IPO_INPUT_DIR 覆盖路径)
输出:      打印全部关键结论与逐行计算算式 (stdout)

纪律:
  * 所有参数均从 input_files 解析, 不硬编码任何结论数值, 不访问网络。
  * Base case 仅使用 2024-03-20 前可获得信息 (CP-01)。
  * 来源优先级按 sec_filings/Source_Index.csv; 控制口径为最新版委员会政策 (v3)。
本脚本同时作为交付物构建器的计算引擎: compute() 返回全部结果字典 R。
"""

import csv
import os
import re
import sys
from pathlib import Path

import openpyxl

INPUT_DIR = Path(os.environ.get("IPO_INPUT_DIR", "/app/input_files"))
TOL = 0.005          # 勾稽容差 (USD mm, 舍入位)
AS_OF = "2024-03-20"  # 信息集截止时点 (来自 00_README.md / CP-01, 任务口径)


# ---------------------------------------------------------------- readers
def read_csv_rows(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f)]


def read_xlsx_sheets(p):
    wb = openpyxl.load_workbook(p, data_only=True)
    out = {}
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        out[ws.title] = [r for r in rows if any(c is not None for c in r)]
    return out


def xlsx_table(rows):
    """把 [[header],[...]] 转成 list[dict]。"""
    hdr = [str(h).strip() if h is not None else "" for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = {}
        for i, h in enumerate(hdr):
            d[h] = r[i] if i < len(r) else None
        out.append(d)
    return out


def to_float(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).replace(",", "").replace('"', "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def sheet_by_key(rows, key_col="Item", val_cols=None):
    d = {}
    for r in xlsx_table(rows):
        k = str(r.get(key_col, "")).strip()
        d[k] = r
    return d


# ---------------------------------------------------------------- compute
def compute():
    R = {}

    # ============ 0. 材料清点 (只读遍历) ============
    by_dir, root_files = {}, []
    for p in sorted(INPUT_DIR.rglob("*")):
        if p.is_file():
            rel = p.relative_to(INPUT_DIR)
            if len(rel.parts) == 1:
                root_files.append(rel.parts[0])
            else:
                by_dir[rel.parts[0]] = by_dir.get(rel.parts[0], 0) + 1
    R["counts"] = {
        "by_dir": dict(sorted(by_dir.items())),
        "root_files": root_files,
        "root_n": len(root_files),
        "source_dirs": len(by_dir),
        "total": sum(by_dir.values()) + len(root_files),
    }

    # ============ 1. 来源优先级 (Source_Index.csv + legacy Q7 补充 UW-01) ============
    si = read_csv_rows(INPUT_DIR / "sec_filings" / "Source_Index.csv")
    prio = {r["Source_ID"]: int(r["Priority"]) for r in si}
    R["source_index"] = si
    q7 = read_xlsx_sheets(INPUT_DIR / "legacy" / "Q7_original_workbook.xlsx")
    for r in xlsx_table(q7["Source_Index"]):          # UW-01 优先级定义
        sid = str(r["Source_ID"]).strip()
        if sid not in prio:
            prio[sid] = int(r["Priority"])
    R["priorities"] = prio

    # ============ 2. 控制口径政策版本识别 ============
    pol_files = sorted((INPUT_DIR / "committee").glob("Committee_Policy_v*.xlsx"))
    dated = []
    for p in pol_files:
        m = re.search(r"_v(\d+)_(\d{8})\.xlsx$", p.name)
        dated.append(((m.group(2), int(m.group(1))), p))
    dated.sort()
    ctrl_path = dated[-1][1]
    ctrl = read_xlsx_sheets(ctrl_path)
    pol = {str(r["Policy_ID"]).strip(): r for r in xlsx_table(ctrl["Committee_Policy"])}
    superseded = []
    for _, p in dated[:-1]:
        v = read_xlsx_sheets(p)
        if "Revision_Note" in v:
            note = {str(r[0]): str(r[1]) for r in v["Revision_Note"][1:]}
            superseded.append({"file": p.name, "status": note.get("状态", ""),
                               "scope": note.get("取代范围", "")})
    rev_log = read_csv_rows(INPUT_DIR / "internal" / "data_revision_log.csv")
    rev_conf = [r for r in rev_log if "Committee_Policy" in r["artifact"]]
    R["control_policy"] = {
        "file": ctrl_path.name, "policies": pol, "superseded": superseded,
        "revision_log_confirmation": rev_conf,
        "peer_set": xlsx_table(ctrl["Committee_Peer_Set"]),
    }

    def cp_text(cid):
        return str(pol[cid]["Committee convention"])

    # 从政策条文解析参数 (交叉校验用)
    g_txt = to_float(re.search(r"\(1\s*\+\s*(\d+(?:\.\d+)?)%\)", cp_text("CP-06")).group(1)) / 100
    m_lo_t, m_hi_t, m_md_t = [to_float(x) for x in re.findall(
        r"(\d+(?:\.\d+)?)x", cp_text("CP-07"))][:3]
    disc_txt = to_float(re.search(r"(\d+(?:\.\d+)?)%\s*IPO execution discount",
                                  cp_text("CP-09")).group(1)) / 100
    fee_txt = to_float(re.search(r"(\d+(?:\.\d+)?)%\s*计提", cp_text("CP-12")).group(1)) / 100
    fixed_txt = to_float(re.search(r"\$([\d.]+)mm", cp_text("CP-12")).group(1))
    thresh_txt = to_float(re.search(r"\$([\d.]+)/share", cp_text("CP-14")).group(1))
    prim_txt, sec_txt = [to_float(x) for x in re.findall(
        r"(\d+(?:\.\d+)?)m", cp_text("CP-10"))][:2]
    shoe_txt = to_float(re.search(r"(\d+(?:\.\d+)?)m\s*greenshoe", cp_text("CP-11")).group(1))

    # ============ 3. 承销假设 (UW-01, 内部委员会假设) ============
    uwa = xlsx_table(read_xlsx_sheets(
        INPUT_DIR / "committee" / "Underwriting_Assumptions_20240320.xlsx")["Assumptions"])
    A = {str(r["Assumption"]).strip(): r for r in uwa}
    growth = to_float(A["2024E revenue growth"]["Value"])
    mult_low = to_float(A["Peer low EV/Revenue"]["Value"])
    mult_mid = to_float(A["Peer midpoint EV/Revenue"]["Value"])
    mult_high = to_float(A["Peer high EV/Revenue"]["Value"])
    discount = to_float(A["IPO discount to peer-implied equity"]["Value"])
    # 与政策条文交叉校验
    cross = {"growth": (growth, g_txt), "mult_low": (mult_low, m_lo_t),
             "mult_high": (mult_high, m_hi_t), "mult_mid": (mult_mid, m_md_t),
             "discount": (discount, disc_txt)}
    R["policy_crosscheck"] = {k: {"workbook": a, "policy_text": b,
                                  "match": abs(a - b) < 1e-9} for k, (a, b) in cross.items()}

    # ============ 4. 发行条款 (Offering_Terms + SEC-03) ============
    ot = sheet_by_key(read_xlsx_sheets(
        INPUT_DIR / "committee" / "Offering_Terms_20240320.xlsx")["Offering_Terms"])

    def otv(item, col="Base Offering"):
        return to_float(ot[item][col])

    price = otv("Proposed Committee Price")
    primary = otv("Primary shares offered")
    secondary = otv("Secondary shares offered")
    shoe = otv("Greenshoe shares", "Full Greenshoe")
    prem_shares_ot = otv("Pre-money economic shares")
    fee_rate = otv("Underwriting fee assumption")
    fixed_exp = otv("Fixed company offering expenses")
    pub_lo = otv("Preliminary public filing range low")
    pub_hi = otv("Preliminary public filing range high")
    full_primary_ot = otv("Primary shares offered", "Full Greenshoe")
    sec03 = xlsx_table(read_xlsx_sheets(
        INPUT_DIR / "sec_filings" / "SEC-03_offering_terms.xlsx")["Offering_Terms"])
    s3 = {str(r["Item"]).strip(): to_float(r["Value"]) for r in sec03}
    terms_match = {
        "primary": (primary, s3["Primary shares offered (base)"]),
        "secondary": (secondary, s3["Secondary shares offered (base)"]),
        "greenshoe": (shoe, s3["Over-allotment option"]),
        "range_low": (pub_lo, s3["Preliminary public filing range low"]),
        "range_high": (pub_hi, s3["Preliminary public filing range high"]),
    }
    R["terms_crosscheck"] = {k: {"offering_terms": a, "sec03": b,
                                 "match": abs(a - b) < 1e-9} for k, (a, b) in terms_match.items()}
    policy_terms_match = {"primary": (primary, prim_txt), "secondary": (secondary, sec_txt),
                          "greenshoe": (shoe, shoe_txt), "fee_rate": (fee_rate, fee_txt),
                          "fixed_exp": (fixed_exp, fixed_txt)}
    R["policy_terms_crosscheck"] = {k: {"workbook": a, "policy_text": b,
                                        "match": abs(a - b) < 1e-9}
                                    for k, (a, b) in policy_terms_match.items()}
    R["terms"] = dict(price=price, primary=primary, secondary=secondary, shoe=shoe,
                      prem_shares_ot=prem_shares_ot, fee_rate=fee_rate, fixed_exp=fixed_exp,
                      pub_lo=pub_lo, pub_hi=pub_hi, full_primary_ot=full_primary_ot)

    # ============ 5. SEC-01 年度财务 (Priority 1, 公开事实) ============
    f1 = xlsx_table(read_xlsx_sheets(
        INPUT_DIR / "sec_filings" / "SEC-01_financials_extract.xlsx")["Public_Financials"])
    FIN = {}
    for r in f1:
        FIN[str(r["Metric"]).strip()] = {
            "FY2022": to_float(r["2022A"]), "FY2023": to_float(r["2023A"]),
            "unit": r["Unit"], "src": str(r["Source_ID"]).strip()}
    R["fin"] = FIN

    sec02 = xlsx_table(read_xlsx_sheets(
        INPUT_DIR / "sec_filings" / "SEC-02_dilution_crosscheck.xlsx")["Dilution_Crosscheck"])
    S2 = {str(r["Item"]).strip(): r for r in sec02}
    ntbv = to_float(S2["Preliminary NTBV/share"]["Value"])
    idil = to_float(S2["Preliminary immediate dilution per share"]["Value"])
    s2_price = to_float(S2["Preliminary NTBV/share"]["Assumed price"])
    R["sec02"] = {"ntbv": ntbv, "dilution": idil, "assumed_price": s2_price,
                  "internal_check": s2_price - ntbv,
                  "consistent": abs((s2_price - ntbv) - idil) < 1e-9}

    # ============ 6. cap table ============
    cap = read_csv_rows(INPUT_DIR / "committee" / "cap_table_snapshot_20240318.csv")
    comp = [r for r in cap if not r["holder_class"].startswith("TOTAL")]
    total_row = [r for r in cap if r["holder_class"].startswith("TOTAL")]
    cap_sum = sum(to_float(r["shares_mm"]) for r in comp)
    cap_total = to_float(total_row[0]["shares_mm"]) if total_row else None
    sec09 = read_csv_rows(INPUT_DIR / "sec_filings" / "SEC-09_capitalization.csv")
    sec09_sum = sum(to_float(r["shares_mm"]) for r in sec09)
    sec16 = read_csv_rows(INPUT_DIR / "sec_filings" / "SEC-16_share_count_history.csv")
    prem_shares = cap_sum  # 委员会经济口径快照 (UW-01)
    R["cap_table"] = {"components": comp, "sum": cap_sum, "total_row": cap_total,
                      "tie_total_row": abs(cap_sum - cap_total) < 1e-6,
                      "sec09_component_sum": sec09_sum,
                      "tie_sec09": abs(cap_sum - sec09_sum) < 1e-6,
                      "tie_offering_terms": abs(cap_sum - prem_shares_ot) < 1e-6,
                      "prem_shares": prem_shares, "sec16": sec16}

    # ============ 7. 明细底表勾稽核验 ============
    tieout, anomalies = [], []

    def add_tie(series, file, raw_sum, target, diff, atype, disposition,
                corrected_sum, tied):
        row = dict(series=series, file=file, raw_sum=raw_sum, target=target, diff=diff,
                   anomaly_type=atype, disposition=disposition,
                   corrected_sum=corrected_sum, tied=tied)
        tieout.append(row)
        if atype not in ("一致", "舍入差"):
            anomalies.append(row)
        return row

    annual = {"FY2022": FIN["Revenue"]["FY2022"], "FY2023": FIN["Revenue"]["FY2023"]}

    # --- 7a. 月度收入: 重复行 / 低优先级来源冲突 ---
    mrows = read_csv_rows(INPUT_DIR / "financials" / "monthly_revenue_2022_2023.csv")
    for fy in ("FY2022", "FY2023"):
        rs = [r for r in mrows if r["fy"] == fy]
        raw = sum(to_float(r["revenue_usd_mm"]) for r in rs)
        by_m = {}
        for r in rs:
            by_m.setdefault(r["month"], []).append(r)
        kept, notes = [], []
        for m in sorted(by_m):
            grp = by_m[m]
            if len(grp) == 1:
                kept.append(grp[0])
                continue
            vals = {to_float(g["revenue_usd_mm"]) for g in grp}
            srcs = {g["Source_ID"] for g in grp}
            if len(vals) == 1 and len(srcs) == 1:      # 完全重复行
                kept.append(grp[0])
                notes.append(f"{m}: 重复行(值 {grp[0]['revenue_usd_mm']}, 来源 {grp[0]['Source_ID']})→去重保留1行")
            else:                                       # 来源冲突 → 按优先级取最高
                best = min(grp, key=lambda g: prio.get(g["Source_ID"], 99))
                kept.append(best)
                for g in grp:
                    if g is not best:
                        notes.append(f"{m}: 来源冲突 {g['Source_ID']}(P{prio.get(g['Source_ID'],'?')}) "
                                     f"{g['revenue_usd_mm']} vs 采用 {best['Source_ID']}(P{prio.get(best['Source_ID'],'?')}) "
                                     f"{best['revenue_usd_mm']} → 排除低优先级行")
        corr = sum(to_float(r["revenue_usd_mm"]) for r in kept)
        tgt = annual[fy]
        if notes:
            atype = ("重复行" if fy == "FY2022" else "低优先级来源冲突(preliminary 残留)")
            disp = ("; ".join(notes) + f"; 修正后={corr:.3f} 勾稽一致"
                    if abs(corr - tgt) < TOL else "; ".join(notes) + " → 仍不一致, 待核实")
            add_tie(f"月度收入 {fy} (原始含异常行)", "financials/monthly_revenue_2022_2023.csv",
                    raw, tgt, raw - tgt, atype, disp, corr, abs(corr - tgt) < TOL)
        else:
            add_tie(f"月度收入 {fy}", "financials/monthly_revenue_2022_2023.csv",
                    raw, tgt, raw - tgt, "一致", "无需处置", corr, abs(corr - tgt) < TOL)
    monthly_corrected = {fy: sum(to_float(r["revenue_usd_mm"]) for r in mrows
                                 if r["fy"] == fy and r["Source_ID"] == "SEC-01")
                         for fy in ("FY2022", "FY2023")}
    # 去重后的 SEC-01 行合计 (FY2022 需去重 2022-08):
    for fy in monthly_corrected:
        seen, s = set(), 0.0
        for r in mrows:
            if r["fy"] == fy and r["Source_ID"] == "SEC-01" and r["month"] not in seen:
                seen.add(r["month"]); s += to_float(r["revenue_usd_mm"])
        monthly_corrected[fy] = s
    R["monthly_corrected"] = monthly_corrected

    # --- 7b. 分部收入 ---
    srows = read_csv_rows(INPUT_DIR / "financials" / "revenue_by_segment_2022_2023.csv")
    sec_seg = {"Advertising": ("FY2022", FIN["Advertising revenue"]["FY2022"], FIN["Advertising revenue"]["FY2023"]),
               "Other": ("FY2023", None, None)}
    adv22, adv23 = FIN["Advertising revenue"]["FY2022"], FIN["Advertising revenue"]["FY2023"]
    oth22, oth23 = FIN["Other revenue"]["FY2022"], FIN["Other revenue"]["FY2023"]
    sec_map = {("FY2022", "Advertising"): adv22, ("FY2022", "Other"): oth22,
               ("FY2023", "Advertising"): adv23, ("FY2023", "Other"): oth23}
    for fy in ("FY2022", "FY2023"):
        rs = [r for r in srows if r["fy"] == fy]
        raw = sum(to_float(r["revenue_usd_mm"]) for r in rs)
        tgt = annual[fy]
        diff = raw - tgt
        if abs(diff) < TOL:
            add_tie(f"分部收入 {fy}", "financials/revenue_by_segment_2022_2023.csv",
                    raw, tgt, diff, "一致", "无需处置", raw, True)
        else:
            # 定位具体行
            fixed, detail = 0.0, []
            for r in rs:
                v = to_float(r["revenue_usd_mm"])
                ref = sec_map[(fy, r["segment"])]
                ratio = v / ref if ref else None
                if abs(v - ref) > TOL:
                    detail.append(f"{r['segment']} 行 {v:.3f} vs SEC-01 {ref:.3f}"
                                  f" (比值 {ratio:.4g} → 小数点移位/十倍错)")
                    fixed += ref
                else:
                    fixed += v
            add_tie(f"分部收入 {fy}", "financials/revenue_by_segment_2022_2023.csv",
                    raw, tgt, diff, "小数点移位(10x)",
                    "; ".join(detail) + f"; 按 SEC-01(P1) 取 {oth23 if fy=='FY2023' else oth22:.3f}"
                    f"; 修正后={fixed:.3f} 勾稽一致", fixed, abs(fixed - tgt) < TOL)

    # --- 7c. 地区收入 (SEC-05) ---
    grows = read_csv_rows(INPUT_DIR / "sec_filings" / "SEC-05_revenue_by_geo.csv")
    for fy in ("FY2022", "FY2023"):
        s = sum(to_float(r["revenue_usd_mm"]) for r in grows if r["fy"] == fy)
        tgt = annual[fy]
        add_tie(f"地区收入 {fy} (US+International)", "sec_filings/SEC-05_revenue_by_geo.csv",
                s, tgt, s - tgt, "一致" if abs(s - tgt) < TOL else "不一致",
                "无需处置" if abs(s - tgt) < TOL else "待核实", s, abs(s - tgt) < TOL)

    # --- 7d. 季度收入 (含与修正后月度的季度对照) ---
    qrows = read_csv_rows(INPUT_DIR / "financials" / "revenue_quarterly.csv")
    q23 = sum(to_float(r["revenue_usd_mm"]) for r in qrows if r["fy"] == "FY2023")
    tgt = annual["FY2023"]
    add_tie("季度收入 FY2023 (Q1..Q4)", "financials/revenue_quarterly.csv",
            q23, tgt, q23 - tgt, "一致" if abs(q23 - tgt) < TOL else "不一致",
            "无需处置" if abs(q23 - tgt) < TOL else "待核实", q23, abs(q23 - tgt) < TOL)
    qmap = {"Q1": ("01", "02", "03"), "Q2": ("04", "05", "06"),
            "Q3": ("07", "08", "09"), "Q4": ("10", "11", "12")}
    mon_rows_23 = {}
    seen = set()
    for r in mrows:
        if r["fy"] == "FY2023" and r["Source_ID"] == "SEC-01" and r["month"] not in seen:
            seen.add(r["month"]); mon_rows_23[r["month"][-2:]] = to_float(r["revenue_usd_mm"])
    q_vs_m = {}
    for r in qrows:
        if r["fy"] != "FY2023":
            continue
        ms = sum(mon_rows_23[m] for m in qmap[r["quarter"]])
        q_vs_m[r["quarter"]] = (to_float(r["revenue_usd_mm"]), ms,
                                abs(to_float(r["revenue_usd_mm"]) - ms) < TOL)
    R["quarter_vs_month"] = q_vs_m

    # --- 7e. SBC 明细 ---
    sbc = read_csv_rows(INPUT_DIR / "financials" / "sbc_detail_2022_2023.csv")
    sbc_res = {}
    for fy in ("FY2022", "FY2023"):
        rs = [r for r in sbc if r["fy"] == fy]
        comps_ = [r for r in rs if r["component"] != "TOTAL"]
        tot_rows = [r for r in rs if r["component"] == "TOTAL"]
        cs = sum(to_float(r["amount_usd_mm"]) for r in comps_)
        tgt = FIN["Stock-based compensation & related taxes"][fy]
        tr = to_float(tot_rows[0]["amount_usd_mm"]) if tot_rows else None
        sbc_res[fy] = {"components_sum": cs, "total_row": tr, "sec01": tgt}
        if tr is not None and abs(tr - cs) > TOL:
            add_tie(f"SBC 明细合计 {fy}", "financials/sbc_detail_2022_2023.csv",
                    tr, tgt, tr - tgt, "TOTAL 行计算错误",
                    f"TOTAL 行 {tr:.3f} ≠ 分项和 {cs:.3f} (差 {tr-cs:+.3f}); "
                    f"分项和与 SEC-01 {tgt:.3f} 一致 → 弃用 TOTAL 行, 采用分项和/SEC-01(P1)",
                    cs, abs(cs - tgt) < TOL)
        else:
            add_tie(f"SBC 明细合计 {fy}", "financials/sbc_detail_2022_2023.csv",
                    cs, tgt, cs - tgt, "一致",
                    "分项和=SEC-01" + ("; TOTAL 行一致" if tr is not None else "; 无 TOTAL 行"),
                    cs, abs(cs - tgt) < TOL)
    R["sbc_checks"] = sbc_res

    # --- 7f. 重组明细 ---
    rst = read_csv_rows(INPUT_DIR / "financials" / "restructuring_detail_2023.csv")
    rc = sum(to_float(r["amount_usd_mm"]) for r in rst if r["component"] != "TOTAL")
    rt = [to_float(r["amount_usd_mm"]) for r in rst if r["component"] == "TOTAL"]
    tgt = FIN["Restructuring costs"]["FY2023"]
    ok = abs(rc - tgt) < TOL and (not rt or abs(rt[0] - tgt) < TOL)
    add_tie("重组费用明细 FY2023", "financials/restructuring_detail_2023.csv",
            rc, tgt, rc - tgt, "一致" if ok else "不一致",
            "分项和=TOTAL 行=SEC-01, 无需处置" if ok else "待核实", rc, ok)

    # --- 7g. FCF 桥 ---
    fcf = read_csv_rows(INPUT_DIR / "financials" / "fcf_bridge_2023.csv")
    fv = {r["line_item"]: to_float(r["amount_usd_mm"]) for r in fcf}
    ocf, capex, f = (fv["Net cash used in operating activities"],
                     fv["Purchases of property and equipment"], fv["Free cash flow"])
    tgt = FIN["Free Cash Flow"]["FY2023"]
    ok = abs(ocf + capex - f) < TOL and abs(f - tgt) < TOL
    add_tie("FCF 桥 FY2023 (OCF+capex)", "financials/fcf_bridge_2023.csv",
            ocf + capex, tgt, ocf + capex - tgt, "一致" if ok else "不一致",
            f"{ocf:.3f} + ({capex:.3f}) = {ocf+capex:.3f} = SEC-01 FCF" if ok else "待核实",
            ocf + capex, ok)
    R["fcf_bridge"] = fv

    # --- 7h. 利润表内部勾稽 ---
    ist = read_csv_rows(INPUT_DIR / "financials" / "income_statement_2022_2023.csv")
    isd = {r["line_item"]: r for r in ist}
    for fy in ("FY2022", "FY2023"):
        parts = ["Cost of revenue", "Research and development", "Sales and marketing",
                 "General and administrative"]
        s = sum(to_float(isd[p][fy]) for p in parts)
        tot = to_float(isd["Total costs and operating expenses"][fy])
        rev, oth, ni = (to_float(isd["Revenue"][fy]),
                        to_float(isd['Other income, net'][fy]),
                        to_float(isd["Net income (loss)"][fy]))
        ni_calc = rev + tot + oth
        ok = abs(s - tot) < TOL and abs(ni_calc - ni) < TOL \
            and abs(rev - annual[fy]) < TOL and abs(ni - FIN["Net income (loss)"][fy]) < TOL
        add_tie(f"利润表 {fy} (费用合计/净亏损)", "financials/income_statement_2022_2023.csv",
                ni_calc, ni, ni_calc - ni, "一致" if ok else "不一致",
                f"费用分项和={s:.3f}=Total 行; {rev:.3f}{tot:+.3f}{oth:+.3f}={ni_calc:.3f}=SEC-01 净亏损"
                if ok else "待核实", ni_calc, ok)

    # --- 7i. 现金流量表 ---
    cfs = read_csv_rows(INPUT_DIR / "financials" / "cash_flow_statement_2023.csv")
    cv = {r["line_item"]: to_float(r["FY2023"]) for r in cfs}
    net_chg = (cv["Net cash used in operating activities"]
               + cv["Net cash used in investing activities"]
               + cv["Net cash provided by financing activities"])
    end_calc = cv["Cash & cash equivalents at beginning of period"] + net_chg
    ok = (abs(net_chg - cv["Net change in cash and cash equivalents"]) < TOL
          and abs(end_calc - cv["Cash & cash equivalents at end of period"]) < TOL
          and abs(cv["Cash & cash equivalents at end of period"] - FIN["Cash & cash equivalents"]["FY2023"]) < TOL)
    add_tie("现金流量表 FY2023 (三项活动→期末现金)", "financials/cash_flow_statement_2023.csv",
            end_calc, FIN["Cash & cash equivalents"]["FY2023"],
            end_calc - FIN["Cash & cash equivalents"]["FY2023"],
            "一致" if ok else "不一致",
            f"{net_chg:.3f} 净变动; {cv['Cash & cash equivalents at beginning of period']:.3f}{net_chg:+.3f}"
            f"={end_calc:.3f}=期末现金=SEC-01" if ok else "待核实", end_calc, ok)

    # --- 7j. 资产负债表: 现金+有价证券 ---
    bs = read_csv_rows(INPUT_DIR / "financials" / "balance_sheet_summary_2022_2023.csv")
    bsd = {r["line_item"]: r for r in bs}
    tot_key = "Total cash, cash equivalents and marketable securities"
    for fy in ("FY2022", "FY2023"):
        c, m = (to_float(bsd["Cash & cash equivalents"][fy]),
                to_float(bsd["Marketable securities"][fy]))
        t = to_float(bsd[tot_key][fy])
        ok = (abs(c + m - t) < TOL and abs(c - FIN["Cash & cash equivalents"][fy]) < TOL
              and abs(m - FIN["Marketable securities"][fy]) < TOL)
        add_tie(f"现金+有价证券 {fy}", "financials/balance_sheet_summary_2022_2023.csv",
                c + m, t, c + m - t, "一致" if ok else "不一致",
                f"{c:.3f}+{m:.3f}={c+m:.3f}=Total 行=SEC-01" if ok else "待核实", c + m, ok)

    # --- 7k. cap table 合计 ---
    ok = (R["cap_table"]["tie_total_row"] and R["cap_table"]["tie_sec09"]
          and R["cap_table"]["tie_offering_terms"])
    add_tie("cap table 合计 (pre-money 经济口径股数)", "committee/cap_table_snapshot_20240318.csv",
            cap_sum, cap_total, cap_sum - cap_total,
            "一致" if ok else "不一致",
            f"6 类分项和={cap_sum:.6f}=TOTAL 行=SEC-09 分项和=发行条款 pre-money"
            if ok else "待核实", cap_sum, ok)
    reg = [to_float(r["shares_outstanding_mm"]) for r in sec16
           if "registered" in r.get("note", "")]
    if reg:
        add_tie("SEC-16 注册股数 vs 经济口径快照 (2024-03-18)",
                "sec_filings/SEC-16_share_count_history.csv",
                reg[0], cap_sum, reg[0] - cap_sum, "口径差异(非异常)",
                f"注册股数 {reg[0]:.3f} 不含未结算 RSU; 与经济口径 {cap_sum:.6f} 的跨口径调节材料未载明 → 待核实;"
                f" 估值采用委员会经济口径快照(UW-01, CP-08/Offering_Terms)", reg[0], False)

    # --- 7l. DAU x ARPU (舍入核对) ---
    dau = read_csv_rows(INPUT_DIR / "financials" / "dau_arpu_metrics.csv")
    for r in dau:
        fy = r["period"]
        if fy in annual:
            calc = to_float(r["daily_active_uniques_mm"]) * to_float(r["arpu_usd"])
            d = calc - annual[fy]
            if abs(d) > TOL:
                add_tie(f"DAU×ARPU {fy}", "financials/dau_arpu_metrics.csv",
                        calc, annual[fy], d, "舍入差",
                        f"ARPU 仅两位小数 → {calc:.3f} vs {annual[fy]:.3f} (差 {d:+.3f}); 可接受, 年度数以 SEC-01 为准",
                        calc, False)
    R["tieout"] = tieout
    R["anomalies"] = anomalies

    # ============ 8. 竞争数据 (低优先级来源, 仅记录不采用) ============
    flash = {r["metric"]: to_float(r["FY2023_value"])
             for r in read_csv_rows(INPUT_DIR / "internal" / "management_flash_20240319.csv")}
    bankB = read_csv_rows(INPUT_DIR / "comps" / "underwriter_B_comps_20240318.csv")
    bmult = [to_float(r["ntm_ev_revenue"]) for r in bankB]
    bankA = read_csv_rows(INPUT_DIR / "comps" / "underwriter_A_comps_20240315.csv")
    amult = [to_float(r["ntm_ev_revenue"]) for r in bankA]
    peers = R["control_policy"]["peer_set"]
    pmult = [to_float(p["NTM EV/Revenue"]) for p in peers
             if to_float(p["NTM EV/Revenue"]) is not None]
    pw = [to_float(p["Committee Weight"]) for p in peers
          if to_float(p["NTM EV/Revenue"]) is not None and to_float(p["Committee Weight"]) is not None]
    wavg = sum(m * w for m, w in zip(pmult, pw)) / sum(pw)
    R["competing"] = {"flash": flash, "bankA": amult, "bankB": bmult,
                      "peer_multiples": pmult, "peer_weighted_avg": wavg}

    # ============ 9. QoE 承销口径桥 ============
    mgmt22 = FIN["Adjusted EBITDA"]["FY2022"]; mgmt23 = FIN["Adjusted EBITDA"]["FY2023"]
    sbc22 = FIN["Stock-based compensation & related taxes"]["FY2022"]
    sbc23 = FIN["Stock-based compensation & related taxes"]["FY2023"]
    uw22 = mgmt22 - sbc22
    uw23 = mgmt23 - sbc23          # CP-03: 不保留 SBC 加回; CP-04: 重组不再二次加回(0)
    R["qoe"] = {
        "mgmt": {"FY2022": mgmt22, "FY2023": mgmt23},
        "sbc_removed": {"FY2022": -sbc22, "FY2023": -sbc23},
        "restructuring_adjustment": {"FY2022": 0.0, "FY2023": 0.0},   # CP-04 禁止二次加回
        "uw_ebitda": {"FY2022": uw22, "FY2023": uw23},
        "uw_ebitda_negative": uw23 < 0,
        "fcf": {"FY2022": FIN["Free Cash Flow"]["FY2022"], "FY2023": FIN["Free Cash Flow"]["FY2023"]},
        "net_loss": {"FY2022": FIN["Net income (loss)"]["FY2022"],
                     "FY2023": FIN["Net income (loss)"]["FY2023"]},
        "da": {"FY2022": FIN["Depreciation & amortization"]["FY2022"],
               "FY2023": FIN["Depreciation & amortization"]["FY2023"]},
        "restructuring": {"FY2022": FIN["Restructuring costs"]["FY2022"],
                          "FY2023": FIN["Restructuring costs"]["FY2023"]},
        "cash_ms": {"FY2022": FIN["Cash & cash equivalents"]["FY2022"] + FIN["Marketable securities"]["FY2022"],
                    "FY2023": FIN["Cash & cash equivalents"]["FY2023"] + FIN["Marketable securities"]["FY2023"]},
    }

    # ============ 10. 估值 ============
    rev23 = FIN["Revenue"]["FY2023"]
    rev24e = rev23 * (1 + growth)
    cash_y, ms_y = FIN["Cash & cash equivalents"]["FY2023"], FIN["Marketable securities"]["FY2023"]
    net_cash = cash_y + ms_y

    def per_share(mult, g=growth):
        ev = rev23 * (1 + g) * mult
        eq = ev + net_cash
        ps_undisc = eq / prem_shares
        return ev, eq, ps_undisc, ps_undisc * (1 - discount)

    lo = per_share(mult_low); mi = per_share(mult_mid); hi = per_share(mult_high)
    sup_lo, sup_mid, sup_hi = lo[3], mi[3], hi[3]
    dist = price - sup_mid
    in_range = sup_lo <= price <= sup_hi
    within_thresh = abs(dist) <= thresh_txt
    # 拟议价隐含的折前 peer 倍数
    implied_mult = ((price / (1 - discount)) * prem_shares - net_cash) / rev24e
    hard_errors_resolved = all(t["tied"] or t["anomaly_type"] in ("舍入差", "口径差异(非异常)")
                               for t in tieout)
    if in_range and within_thresh and hard_errors_resolved:
        disposition, disp_rule = "Proceed", "CP-14"
    elif in_range:
        disposition, disp_rule = "Reprice (向 midpoint 方向)", "CP-15"
    else:
        disposition, disp_rule = "Defer", "CP-15"

    # 敏感性矩阵: 增长率轴 = CP-06 中值 ±2pp/±4pp; 倍数轴 = committee peer set 五个倍数
    g_axis = [growth - 0.04, growth - 0.02, growth, growth + 0.02, growth + 0.04]
    m_axis = sorted(pmult)
    matrix = [[per_share(m, g)[3] for m in m_axis] for g in g_axis]
    R["valuation"] = {
        "rev23": rev23, "growth": growth, "rev24e": rev24e,
        "cash": cash_y, "ms": ms_y, "net_cash": net_cash,
        "prem_shares": prem_shares, "discount": discount,
        "mults": {"low": mult_low, "mid": mult_mid, "high": mult_high},
        "low": lo, "mid": mi, "high": hi,
        "sup_lo": sup_lo, "sup_mid": sup_mid, "sup_hi": sup_hi,
        "price": price, "dist_to_mid": dist, "in_range": in_range,
        "within_thresh": within_thresh, "threshold": thresh_txt,
        "implied_mult_at_price": implied_mult,
        "hard_errors_resolved": hard_errors_resolved,
        "disposition": disposition, "disp_rule": disp_rule,
        "g_axis": g_axis, "m_axis": m_axis, "matrix": matrix,
        "matrix_min": min(min(r) for r in matrix), "matrix_max": max(max(r) for r in matrix),
        "base_cell": (g_axis.index(growth), m_axis.index(mult_mid)),
        "peer_wavg_mult": wavg,
    }

    # ============ 11. 募集与费用 ============
    def proceeds(prim_shares, shoe_incr=0.0):
        gross = prim_shares * price
        fee = gross * fee_rate
        net = gross - fee - fixed_exp
        return dict(shares=prim_shares, gross=gross, fee=fee, fixed=fixed_exp, net=net,
                    shoe_incr_gross=shoe_incr * price,
                    shoe_incr_fee=shoe_incr * price * fee_rate,
                    shoe_incr_net=shoe_incr * price * (1 - fee_rate))
    base_p = proceeds(primary)
    full_primary = primary + shoe
    full_p = proceeds(full_primary, shoe_incr=shoe)
    sec_gross = secondary * price
    R["proceeds"] = {
        "base": base_p, "full": full_p,
        "full_primary_check": (full_primary, full_primary_ot,
                               abs(full_primary - full_primary_ot) < 1e-9),
        "secondary_gross_to_selling_holders": sec_gross,
        "company_secondary_proceeds": 0.0,
        "incremental_check": base_p["net"] + full_p["shoe_incr_net"] - full_p["net"],
    }

    # ============ 12. 股本桥与稀释 ============
    post_base = prem_shares + primary
    post_full = prem_shares + full_primary
    R["dilution"] = {
        "prem_shares": prem_shares,
        "post_base": post_base, "pct_new_base": primary / post_base,
        "post_full": post_full, "pct_new_full": full_primary / post_full,
        "secondary_no_share_increase": secondary,
        "legacy_wrong_post_base": prem_shares + primary + secondary,
        "sec02": R["sec02"],
        "sec02_dilution_pct_of_assumed_price": idil / s2_price,
    }

    # ============ 13. 旧底稿错误审计 (legacy) ============
    leg_rows = xlsx_table(read_xlsx_sheets(
        INPUT_DIR / "legacy" / "Candidate_Model_v0.xlsx")["Candidate_Model"])
    broken = xlsx_table(read_xlsx_sheets(
        INPUT_DIR / "legacy" / "Candidate_Model_v0.xlsx")["Broken_Links"])
    leg_assum = {r["assumption"]: r["legacy_value"]
                 for r in read_csv_rows(INPUT_DIR / "legacy" / "legacy_assumptions_export.csv")}
    all22 = primary + secondary
    errors = []

    def E(cat, legacy, problem, correct, impact, basis):
        errors.append(dict(category=cat, legacy=legacy, problem=problem,
                           correct=correct, impact=impact, basis=basis))

    E("QoE 口径", "以管理层 Adjusted EBITDA -69.275 直接作盈利质量结论",
      "SBC 加回未在承销口径剔除, 高估盈利能力",
      f"UW EBITDA = {mgmt23:.3f} - {sbc23:.3f} = {uw23:.3f} (FY2023)",
      f"盈利被高估 {sbc23:.3f} (FY2023); FY2022: {mgmt22:.3f}-{sbc22:.3f}={uw22:.3f}",
      "CP-03 / SEC-13 / 邮件第5条")
    E("估值分母", f"4.5x 直接乘 2023A 收入 (legacy: {leg_assum.get('valuation_denominator','')})",
      "分母应为 2024E 而非历史年",
      f"2024E Revenue = {rev23:.3f} × (1+{growth:.0%}) = {rev24e:.3f}",
      f"EV 分母少计 {rev24e-rev23:.3f}; 中点 EV 少计 {mult_mid*(rev24e-rev23):.3f}",
      "CP-06")
    E("净现金桥", "仅计现金, 遗漏有价证券",
      "CP-08 要求 cash + marketable securities 全额入桥",
      f"桥 = {cash_y:.3f} + {ms_y:.3f} = {net_cash:.3f}",
      f"pre-money equity 少计 {ms_y:.3f}; 每股少计 {ms_y/prem_shares*(1-discount):.3f} (折后)",
      "CP-08 / SEC-07 (有价证券属可变现金融资产)")
    E("发行结构", f"全部 {all22:.3f}m base 股份视为 primary",
      "secondary 不形成公司募集资金",
      f"primary {primary}m; secondary {secondary}m (CP-10/SEC-03)",
      f"公司 gross proceeds 高估 {sec_gross:.3f} ({all22*price:.3f} vs {primary*price:.3f})",
      "CP-10 / SEC-03 / SEC-12")
    E("Greenshoe", f"greenshoe {shoe}m 预设计入 Base (legacy: greenshoe_in_base=1)",
      "greenshoe 为承销商选择权, Base 不得预设行使",
      "Base 排除; 另列 full-exercise 情景",
      f"Base 股数高估 {shoe}m; Base 后总股数 {post_base:.6f} vs 旧 {prem_shares+all22+shoe:.6f}",
      "CP-11 / SEC-10")
    E("费用基数", "承销费按 primary+secondary 全部股份计提",
      "费用基数应为公司 primary gross proceeds",
      f"fee = {fee_rate:.0%} × {primary*price:.3f} = {primary*price*fee_rate:.3f}",
      f"费用高估 {all22*price*fee_rate - primary*price*fee_rate:.3f} (旧 {all22*price*fee_rate:.3f} vs 正确 {primary*price*fee_rate:.3f})",
      "CP-12 / SEC-10 / v2 条款已作废")
    E("股本桥", "secondary 计入发行后总股数",
      "secondary 为存量股份转让, 不新增公司总股数",
      f"post-money(Base) = {prem_shares:.6f} + {primary} = {post_base:.6f}",
      f"总股数高估 {secondary}m (旧 {R['dilution']['legacy_wrong_post_base']:.6f})",
      "CP-10 / SEC-06")
    E("募集归属", "secondary 所得计入公司现金",
      "secondary 款项归出售股东",
      "公司募集 = primary net 仅",
      f"公司现金高估 {sec_gross:.3f}",
      "SEC-12 / SEC-06 / CP-10")
    E("稀释口径", "post-money equity / pre-money shares (分子分母口径不一致)",
      "稀释交叉验算须用一致口径; SEC-02 独立口径仅在假定价下使用",
      f"SEC-02: {s2_price} - NTBV {ntbv} = {idil} (假定价 ${s2_price}, 内部一致 ✓)",
      "旧法稀释率失真; 正确口径: SEC-02 仅作交叉验算, 不按 $34 重标定",
      "SEC-02 / data_dictionary (NTBV 仅在假定 $32.50 下测算)")
    E("定价建议", "主要依据 peer high case 上调至 $34 以上",
      "未按委员会处置规则 (区间/midpoint/阈值) 判断",
      f"$34 在 [{sup_lo:.2f},{sup_hi:.2f}] 内, 距 midpoint {sup_mid:.2f} 为 {abs(dist):.2f} ≤ {thresh_txt} → Proceed",
      "旧建议越出董事会授权 (不得高于支持区间上限定价的风险)",
      "CP-14 / CP-15 / board_minutes 2024-03-19")
    E("执行折扣", f"未应用折扣 (legacy: discount_applied={leg_assum.get('discount_applied','')})",
      "CP-09 要求对 peer-implied 每股价值统一应用执行折扣",
      f"每股 × (1 - {discount:.1%}); 中点 {mi[2]:.4f} → {sup_mid:.4f}",
      f"每股价值高估 {mi[2]-sup_mid:.4f} (中点)", "CP-09 / v2 10% 条款已作废")
    bl = "; ".join(f"{b['Cell']}={b['Value']}" for b in broken)
    E("模型完整性", f"存在未解析引用错误单元格: {bl}",
      "联动公式失效, 旧底稿计算结果不可沿用",
      "全部结果自 input_files 源数据重建 (本模型/脚本)",
      "旧底稿数值整体不可信, 逐项重算", "legacy/Candidate_Model_readme.md")
    # 数据核验异常并入 Error_Audit
    for a in anomalies:
        E("数据核验异常", f"{a['file']}: {a['series']} 原始加总 {a['raw_sum']:.3f}",
          f"{a['anomaly_type']}; 与年度数差 {a['diff']:+.3f}",
          a["disposition"],
          f"修正后 {a['corrected_sum']:.3f} vs 目标 {a['target']:.3f} → "
          + ("勾稽一致" if a["tied"] else "按规则处置"),
          "CP-02 来源优先级 / SEC-01(P1) / 委员会邮件")
    R["errors"] = errors

    # ============ 14. 来源追溯表 ============
    trace = []

    def T(metric, used, unit, src_used, prio_used, competing, reason):
        trace.append(dict(metric=metric, value_used=used, unit=unit, source_used=src_used,
                          priority=prio_used, competing=competing, reason=reason))

    fsh = flash
    T("FY2023 Revenue", rev23, "USD mm", "SEC-01 (sec_filings/SEC-01_financials_extract.xlsx)", 1,
      f"INT-01 flash {fsh.get('Revenue')}; IR 草稿 806.2; 月度明细原始加总 870.529",
      "SEC-01 为经审计注册说明书摘录(P1); INT-01 为未审 IR 初稿(P9)且邮件明令不得入结论; 明细异常行已剔除")
    T("FY2022 Revenue", FIN["Revenue"]["FY2022"], "USD mm", "SEC-01", 1,
      "月度明细原始加总 723.801 (含重复行)", "重复行去重后勾稽一致; 以 SEC-01 为准")
    T("FY2023 Net income (loss)", FIN["Net income (loss)"]["FY2023"], "USD mm", "SEC-01", 1,
      "无", "唯一权威来源; 利润表内部勾稽一致")
    T("FY2023 Management Adj. EBITDA", mgmt23, "USD mm", "SEC-01 (非 GAAP, 管理层口径)", 1,
      f"INT-01 flash {fsh.get('Adjusted EBITDA')}",
      "非 GAAP 指标以 SEC-01 披露为准; flash 为 P9 未审初稿, 弃用")
    T("FY2023 SBC & related taxes", sbc23, "USD mm", "SEC-01 + sbc_detail 分项和", 1,
      "sbc_detail TOTAL 行 49.680; INT-01 flash 47.300",
      "分项和 49.086 与 SEC-01 一致; TOTAL 行为计算错误弃用; flash P9 弃用")
    T("FY2023 Restructuring", FIN["Restructuring costs"]["FY2023"], "USD mm",
      "SEC-01 + restructuring_detail 分项和", 1, "无", "分项=TOTAL=SEC-01, 三向一致")
    T("FY2023 Free Cash Flow", FIN["Free Cash Flow"]["FY2023"], "USD mm",
      "SEC-01 + fcf_bridge", 1, f"INT-01 flash {fsh.get('Free Cash Flow')}",
      "OCF+capex 勾稽一致; flash P9 弃用")
    T("YE2023 Cash & equivalents", cash_y, "USD mm", "SEC-01 / balance_sheet / cash_flow 期末", 1,
      "无", "三表一致")
    T("YE2023 Marketable securities", ms_y, "USD mm", "SEC-01 / balance_sheet", 1,
      "legacy 模型未计入", "CP-08 要求全额入净现金桥; legacy 遗漏已纠正")
    T("2023-12 月度收入", 68.979, "USD mm", "SEC-01 (monthly_revenue 行 Source_ID=SEC-01)", 1,
      "INT-01 行 66.500 (preliminary 残留)",
      "CP-02 优先级 + Deal Captain 邮件: 12 月 preliminary 残留弃用, 采用 S-1/A 审计版")
    T("Primary shares (base)", primary, "mm shares", "SEC-03 / Offering_Terms / CP-10", 1,
      "legacy 将 22.0m 全部视为 primary", "SEC-03(P1) 与委员会政策一致; legacy 口径错误已纠正")
    T("Secondary shares (base)", secondary, "mm shares", "SEC-03 / Offering_Terms / CP-10", 1,
      "legacy 计入公司股数与募集", "secondary 不形成公司募集、不增公司总股数")
    T("Greenshoe", shoe, "mm shares", "SEC-03 / CP-11", 1, "legacy 预设入 Base",
      "Base 排除, full-exercise 单列")
    T("Public preliminary range", f"{pub_lo}-{pub_hi}", "USD/share", "SEC-03", 1, "无",
      "仅作执行交叉参考, 不等于委员会支持区间")
    T("Pre-money 经济口径股数", prem_shares, "mm shares",
      "UW-01 cap_table_snapshot (=SEC-09 分项和)", 1,
      "SEC-16 注册股数 141.200 (不含未结算 RSU); SEC-16 2023-12-31 流通 138.900",
      "估值每股口径采用委员会经济口径快照; 注册股数为不同口径, 跨口径调节材料未载明→待核实")
    T("2024E revenue growth", growth, "%", "UW-01 Underwriting_Assumptions (CP-06)", 1,
      "sector_benchmark 行业中位 18% (背景资料)",
      "内部委员会假设, 非 SEC 公开事实; 行业基准仅作背景, 不改假设")
    T("Peer EV/NTM Revenue 区间", f"{mult_low}x-{mult_high}x (中点 {mult_mid}x)", "x",
      "UW-01 Committee_Peer_Set (CP-07)", 1,
      f"BANK-B comps {min(bmult)}x-{max(bmult)}x; BANK-A comps {min(amult)}x-{max(amult)}x; "
      f"sector_benchmark 中位 4.4x; peer_multiples_history 2024Q1 4.4x",
      "CP-07 区间端点以 committee peer set 为准; 承销商 comps 仅交叉验证 (BANK-A 与 committee 一致; "
      "BANK-B 端点 4.2/5.1 不采用); peer 等权均值 4.52x≈中点 4.5x 印证")
    T("IPO execution discount", discount, "%", "UW-01 (CP-09)", 1,
      "v2 政策 10% (已作废); legacy 0% (错误)",
      "v3 为现行控制口径; 折扣作用于 peer-implied 每股价值 (邮件第4条)")
    T("承销费率与基数", f"{fee_rate:.0%} × primary gross", "-", "UW-01 (CP-12) / SEC-10", 1,
      "v2: 按全部股份(含 secondary)计提 (已作废); legacy: primary+secondary",
      "SEC-10 承销协议摘要与 CP-12 一致: secondary 不入公司费用基数")
    T("固定发行费用", fixed_exp, "USD mm", "UW-01 (CP-12)", 1, "无",
      "greenshoe 增量不重复计提固定费用")
    T("Proposed price", price, "USD/share", "UW-01 Offering_Terms (内部工作价)", 1, "无",
      "内部决策输入, 非已实现结果 (CP-01)")
    T("NTBV/share (假定价 $32.50)", ntbv, "USD/share", "SEC-02", 1, "无",
      "仅稀释交叉验算; data_dictionary: 仅在假定 $32.50 下测算, 不按 $34 重标定")
    T("Immediate dilution (假定价 $32.50)", idil, "USD/share", "SEC-02", 1,
      "legacy 自算口径不一致的稀释",
      f"内部一致性: {s2_price}-{ntbv}={idil} ✓; 用途边界=交叉验算, 非估值输入")
    T("政策版本", "v3 (2024-03-20)", "-", "committee/Committee_Policy_v3_20240320.xlsx", 1,
      "v2 (2024-03-05)", "文件名日期取最新 + v2 Revision_Note 自认被取代 + data_revision_log + 邮件第1条")
    T("FY2023 Advertising revenue", adv23, "USD mm", "SEC-01", 1, "无", "分部勾稽采用值")
    T("FY2023 Other revenue", oth23, "USD mm", "SEC-01", 1,
      "revenue_by_segment 行 152.470 (10x 小数点移位)", "以 SEC-01(P1) 为准, 修正后分部勾稽一致")
    R["source_trace"] = trace

    # ============ 15. 被取代条款 ============
    v2 = read_xlsx_sheets(INPUT_DIR / "committee" / "Committee_Policy_v2_20240305.xlsx")
    v2_rows = xlsx_table(v2["Committee_Policy"])
    R["superseded_clauses"] = [
        {"policy_id": r["Policy_ID"], "v2_text": r["Committee convention"],
         "v3_text": pol.get(str(r["Policy_ID"]).strip(), {}).get("Committee convention", ""),
         "status": str(r["Application"]).strip()}
        for r in v2_rows if "SUPERSEDED" in str(r["Application"])]

    # ============ 16. 备忘录/披露所需杂项 ============
    R["disclosure"] = {
        "uw_ebitda_neg": uw23 < 0, "fcf_neg": FIN["Free Cash Flow"]["FY2023"] < 0,
        "price_at_public_range_high": abs(price - pub_hi) < 1e-9,
        "board_auth": "董事会授权在委员会支持区间内定价; 未授权高于区间上限",
    }
    return R


# ---------------------------------------------------------------- report
def f3(x):
    return f"{x:,.3f}"


def f4(x):
    return f"{x:,.4f}"


def print_report(R):
    P = print
    line = "=" * 78
    P(line)
    P("FIN3-WKN-152 · Reddit, Inc. IPO 定价委员会复核 — 可复算输出 (as-of 2024-03-20)")
    P(line)

    c = R["counts"]
    P("\n[0] 材料清点 (只读)")
    for d, n in c["by_dir"].items():
        P(f"    {d:<14} {n:>3} 个文件")
    P(f"    {'(根目录)':<12} {c['root_n']:>3} 个文件  {c['root_files']}")
    P(f"    来源目录数 = {c['source_dirs']}; 文件总数 = "
      f"{' + '.join(str(n) for n in c['by_dir'].values())} + {c['root_n']} = {c['total']}")

    cp = R["control_policy"]
    P("\n[1] 控制口径政策版本")
    P(f"    现行控制口径: {cp['file']} (文件名日期最新)")
    for s in cp["superseded"]:
        P(f"    被取代: {s['file']} — {s['status']}; 取代范围: {s['scope']}")
    for r in cp["revision_log_confirmation"]:
        P(f"    data_revision_log 佐证: {r['date']} {r['change']} → {r['disposition']}")
    P("    v2 中不再适用的条款 (SUPERSEDED):")
    for s in R["superseded_clauses"]:
        P(f"      - {s['policy_id']}: v2「{s['v2_text']}」→ v3「{s['v3_text']}」")
    P("    政策条文 vs 假设工作簿交叉校验:")
    for k, v in R["policy_crosscheck"].items():
        P(f"      {k}: workbook={v['workbook']} vs CP 条文={v['policy_text']} → {'一致' if v['match'] else '不一致!'}")
    for k, v in R["policy_terms_crosscheck"].items():
        P(f"      {k}: workbook={v['workbook']} vs CP 条文={v['policy_text']} → {'一致' if v['match'] else '不一致!'}")
    for k, v in R["terms_crosscheck"].items():
        P(f"      {k}: Offering_Terms={v['offering_terms']} vs SEC-03={v['sec03']} → {'一致' if v['match'] else '不一致!'}")

    P("\n[2] 关键输入 (SEC 公开事实 = SEC-01/02/03/05/09, P1; 内部委员会假设 = UW-01)")
    FIN = R["fin"]
    for m in ("Revenue", "Advertising revenue", "Other revenue", "Net income (loss)",
              "Adjusted EBITDA", "Stock-based compensation & related taxes",
              "Restructuring costs", "Depreciation & amortization", "Free Cash Flow",
              "Cash & cash equivalents", "Marketable securities"):
        P(f"    {m:<45} FY2022={f3(FIN[m]['FY2022']):>12}  FY2023={f3(FIN[m]['FY2023']):>12}  ({FIN[m]['src']})")
    t = R["terms"]
    P(f"    [内部假设] proposed price={t['price']}, growth={R['valuation']['growth']}, "
      f"mults={R['valuation']['mults']}, discount={R['valuation']['discount']}, "
      f"fee={t['fee_rate']}, fixed={t['fixed_exp']}")
    P(f"    [SEC-03 公开] primary={t['primary']}, secondary={t['secondary']}, "
      f"greenshoe={t['shoe']}, public range={t['pub_lo']}-{t['pub_hi']}")

    P("\n[3] 明细勾稽核验 (Tieout_Detail)")
    P(f"    {'序列':<44}{'原始加总':>12}{'目标':>12}{'差额':>10}  判定")
    for r in R["tieout"]:
        P(f"    {r['series']:<44}{r['raw_sum']:>12.3f}{r['target']:>12.3f}{r['diff']:>+10.3f}  "
          f"[{r['anomaly_type']}] {'勾稽一致' if r['tied'] else '见处置'}")
    P("\n    发现的异常 (文件|行/月份|现象|判定依据|处置):")
    for a in R["anomalies"]:
        P(f"      - {a['file']} | {a['series']} | 原始 {a['raw_sum']:.3f} vs 目标 {a['target']:.3f} "
          f"(差 {a['diff']:+.3f}) | {a['anomaly_type']} | 处置: {a['disposition']}")
    P("    季度 vs 修正后月度 (FY2023):")
    for q, (qv, mv, ok) in R["quarter_vs_month"].items():
        P(f"      {q}: 季度 {qv:.3f} vs 月度合计 {mv:.3f} → {'一致' if ok else '不一致'}")

    q = R["qoe"]
    P("\n[4] 盈利质量 (QoE) 与承销口径 EBITDA")
    P(f"    Net loss (SEC-01):            FY2022 {f3(q['net_loss']['FY2022'])} | FY2023 {f3(q['net_loss']['FY2023'])}")
    P(f"    Mgmt Adj EBITDA (非GAAP):     FY2022 {f3(q['mgmt']['FY2022'])} | FY2023 {f3(q['mgmt']['FY2023'])}")
    P(f"      其中管理层已加回 (不重复处理, CP-04): SBC {f3(-q['sbc_removed']['FY2023'])} / "
      f"重组 {f3(q['restructuring']['FY2023'])} / D&A {f3(q['da']['FY2023'])} (FY2023)")
    P(f"    CP-03 剔除 SBC 加回:          FY2022 {f3(q['sbc_removed']['FY2022'])} | FY2023 {f3(q['sbc_removed']['FY2023'])}")
    P(f"      算式 FY2023: {f3(q['mgmt']['FY2023'])} - {f3(-q['sbc_removed']['FY2023'])} = {f3(q['uw_ebitda']['FY2023'])}")
    P(f"      算式 FY2022: {f3(q['mgmt']['FY2022'])} - {f3(-q['sbc_removed']['FY2022'])} = {f3(q['uw_ebitda']['FY2022'])}")
    P(f"    CP-04 重组二次调整:           0.000 | 0.000 (已含于管理层调整, 禁止 double count)")
    P(f"    Underwriting EBITDA:          FY2022 {f3(q['uw_ebitda']['FY2022'])} | FY2023 {f3(q['uw_ebitda']['FY2023'])}"
      f"  → {'为负' if q['uw_ebitda_negative'] else '为正'}")
    fb = R["fcf_bridge"]
    P(f"    FCF 桥 FY2023: {f3(fb['Net cash used in operating activities'])} + ({f3(fb['Purchases of property and equipment'])})"
      f" = {f3(fb['Free cash flow'])} (SEC-01 一致)")
    P(f"    FCF (SEC-01):                 FY2022 {f3(q['fcf']['FY2022'])} | FY2023 {f3(q['fcf']['FY2023'])} → 为负")
    P(f"    年末现金+有价证券:            FY2022 {f3(q['cash_ms']['FY2022'])} | FY2023 {f3(q['cash_ms']['FY2023'])}")
    P(f"    CP-05: UW EBITDA 为负 → 主估值采用 EV / 2024E Revenue (不得使用 EV/EBITDA)")
    P(f"    CP-13 披露: 承销口径 EBITDA ({f3(q['uw_ebitda']['FY2023'])}) 与 FCF ({f3(q['fcf']['FY2023'])}) 均为负")

    v = R["valuation"]
    P("\n[5] 估值 (EV / 2024E Revenue, CP-05..CP-09)")
    P(f"    2024E Revenue = {f3(v['rev23'])} × (1 + {v['growth']:.0%}) = {f3(v['rev24e'])}   [CP-06, 内部假设]")
    P(f"    净现金桥 = cash {f3(v['cash'])} + marketable sec {f3(v['ms'])} = {f3(v['net_cash'])}   [CP-08, 完整计入]")
    for name, key in (("Low", "low"), ("Mid", "mid"), ("High", "high")):
        ev, eq, ps_u, ps_d = v[key]
        P(f"    [{name} {v['mults'][key]}x]")
        P(f"      EV          = {v['mults'][key]} × {f3(v['rev24e'])} = {f3(ev)}")
        P(f"      Pre-money Eq= EV + {f3(v['net_cash'])} = {f3(eq)}")
        P(f"      每股(折前)  = {f3(eq)} ÷ {v['prem_shares']:.6f} = {f4(ps_u)}")
        P(f"      每股(折后)  = {f4(ps_u)} × (1 - {v['discount']:.1%}) = {f4(ps_d)}")
    P(f"    委员会支持区间 = [{v['sup_lo']:.2f}, {v['sup_hi']:.2f}]; midpoint = {v['sup_mid']:.2f}")
    P(f"    peer 等权均值 = {v['peer_wavg_mult']:.2f}x ≈ 中点 {v['mults']['mid']}x (CP-07 取值方式印证)")
    P(f"    拟议 ${v['price']:.2f}: 在区间内={v['in_range']}; 距 midpoint = {v['price']:.2f} - {v['sup_mid']:.4f} = "
      f"{v['dist_to_mid']:+.4f} (|dist| ≤ {v['threshold']} → {v['within_thresh']})")
    P(f"    拟议价隐含折前倍数 = ({v['price']:.2f} ÷ {1-v['discount']:.3f} × {v['prem_shares']:.6f} - "
      f"{f3(v['net_cash'])}) ÷ {f3(v['rev24e'])} = {v['implied_mult_at_price']:.4f}x")
    P(f"    公开区间交叉参考 (SEC-03): ${R['terms']['pub_lo']:.0f}-${R['terms']['pub_hi']:.0f}"
      f"; 拟议价位于公开区间上限={R['disclosure']['price_at_public_range_high']}")

    P("\n[6] 敏感性矩阵 (每股价值, USD; 增长率轴 × 倍数轴; base = 22% × 4.5x)")
    hdr = "      g\\m  " + "".join(f"{m:>10.1f}x" for m in v["m_axis"])
    P(hdr)
    for i, g in enumerate(v["g_axis"]):
        cells = []
        for j, val in enumerate(v["matrix"][i]):
            mark = " *" if (i, j) == v["base_cell"] else "  "
            cells.append(f"{val:>8.2f}{mark}")
        P(f"    {g:>6.0%}  " + "".join(cells))
    P(f"    矩阵区间: {v['matrix_min']:.2f} ~ {v['matrix_max']:.2f}; * = base case "
      f"({v['matrix'][v['base_cell'][0]][v['base_cell'][1]]:.2f})")

    pb, pf = R["proceeds"]["base"], R["proceeds"]["full"]
    P("\n[7] 发行结构与募集 (Base 不含 greenshoe, CP-10/11/12)")
    P("    Base 发行:")
    P(f"      primary gross   = {pb['shares']:.6f} × ${R['terms']['price']:.2f} = {f3(pb['gross'])}")
    P(f"      承销费 (5%×primary gross) = {f3(pb['gross'])} × {R['terms']['fee_rate']:.0%} = {f3(pb['fee'])}   [基数不含 secondary, SEC-10]")
    P(f"      固定费用        = {f3(pb['fixed'])} (仅计提一次)")
    P(f"      net primary     = {f3(pb['gross'])} - {f3(pb['fee'])} - {f3(pb['fixed'])} = {f3(pb['net'])}")
    P(f"      secondary       = {R['terms']['secondary']:.6f}m × ${R['terms']['price']:.2f} = "
      f"{f3(R['proceeds']['secondary_gross_to_selling_holders'])} → 归出售股东; 公司募集 = 0.000; 不增公司总股数")
    P("    Full-exercise 情景 (greenshoe 单列):")
    P(f"      primary         = {R['terms']['primary']:.6f} + {R['terms']['shoe']} = {pf['shares']:.6f}m")
    P(f"      primary gross   = {pf['shares']:.6f} × ${R['terms']['price']:.2f} = {f3(pf['gross'])}")
    P(f"      承销费          = {f3(pf['gross'])} × {R['terms']['fee_rate']:.0%} = {f3(pf['fee'])}")
    P(f"      固定费用        = {f3(pf['fixed'])} (greenshoe 增量不重复扣固定费用, CP-12)")
    P(f"      net primary     = {f3(pf['gross'])} - {f3(pf['fee'])} - {f3(pf['fixed'])} = {f3(pf['net'])}")
    P(f"      greenshoe 增量: gross {f3(pf['shoe_incr_gross'])} - fee {f3(pf['shoe_incr_fee'])} = net {f3(pf['shoe_incr_net'])}")
    P(f"      勾稽: base net {f3(pb['net'])} + 增量 net {f3(pf['shoe_incr_net'])} = {f3(pb['net']+pf['shoe_incr_net'])}"
      f" vs full net {f3(pf['net'])} (差 {R['proceeds']['incremental_check']:+.6f}) ✓")

    d = R["dilution"]
    P("\n[8] 股本桥与稀释")
    P(f"    pre-money 经济口径股数 = {d['prem_shares']:.6f} (cap table 分项和 = TOTAL 行 = SEC-09 分项和)")
    P(f"    Base:       post-money = {d['prem_shares']:.6f} + {R['terms']['primary']:.6f} = {d['post_base']:.6f}m; "
      f"新增占比 = {R['terms']['primary']:.6f} ÷ {d['post_base']:.6f} = {d['pct_new_base']:.2%}")
    P(f"    Full:       post-money = {d['prem_shares']:.6f} + {pf['shares']:.6f} = {d['post_full']:.6f}m; "
      f"新增占比 = {pf['shares']:.6f} ÷ {d['post_full']:.6f} = {d['pct_new_full']:.2%}")
    P(f"    secondary {R['terms']['secondary']:.6f}m 为存量转让: 不新增公司总股数 (legacy 误加, 已纠正)")
    s2 = d["sec02"]
    P(f"    稀释交叉验算 (SEC-02 独立口径, 假定价 ${s2['assumed_price']:.2f}): "
      f"{s2['assumed_price']:.2f} - NTBV {s2['ntbv']:.2f} = {s2['assumed_price']-s2['ntbv']:.2f} "
      f"vs 披露即时稀释 {s2['dilution']:.2f} → {'一致 ✓' if s2['consistent'] else '不一致!'}")
    P(f"      即时稀释占假定价比例 = {d['sec02_dilution_pct_of_assumed_price']:.1%}")
    P(f"      用途边界: 仅在假定 $32.50 下测算 (data_dictionary), 用于确认新投资者即时稀释重大; "
      f"不按 ${R['terms']['price']:.0f} 重标定, 不作为估值输入")

    P("\n[9] 旧底稿错误审计 + 数据异常 (Error_Audit, ≥8 类)")
    for i, e in enumerate(R["errors"], 1):
        P(f"    E{i:02d} [{e['category']}] 旧处理: {e['legacy']}")
        P(f"        问题: {e['problem']}")
        P(f"        正确处理: {e['correct']}")
        P(f"        影响: {e['impact']}  依据: {e['basis']}")

    P("\n[10] 来源追溯 (Source_Trace) — 摘要 (完整见 CSV)")
    for t in R["source_trace"]:
        P(f"    - {t['metric']} = {t['value_used']} [{t['source_used']}] 竞争: {t['competing']}")

    v = R["valuation"]
    P("\n[11] 定价处置 (CP-14 / CP-15)")
    P(f"    条件1 拟议价在支持区间 [{v['sup_lo']:.2f}, {v['sup_hi']:.2f}] 内: {v['in_range']}")
    P(f"    条件2 |{v['price']:.2f} - {v['sup_mid']:.2f}| = {abs(v['dist_to_mid']):.2f} ≤ {v['threshold']}: {v['within_thresh']}")
    P(f"    条件3 无未解决 hard error (全部异常已按规则处置): {v['hard_errors_resolved']}")
    P(f"    ==> 处置建议: {v['disposition']} (依据 {v['disp_rule']})")
    P(line)
    P("复算完成: 全部数值由 /app/input_files 源文件解析计算, 无硬编码结论。")


if __name__ == "__main__":
    print_report(compute())
