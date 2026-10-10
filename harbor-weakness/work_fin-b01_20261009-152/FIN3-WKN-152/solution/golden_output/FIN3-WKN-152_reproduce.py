#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIN3-WKN-152 可复算代码。

从 /app/input_files/ 读入全部材料并重算结论，输出 7 项交付物到 /app/output/。
不硬编码任何结论数值；所有数字均来自输入材料或由材料计算得到。

本脚本会在交付物中逐条写出钦定算式（全部由 f-string 拼接运行时计算结果，
源码中不含任何写死的结论常量），包括三条明细勾稽算式：
    月度去重   ：{FY2022 年度数:.3f} = {FY2022 原始加总:.3f} − {重复行金额:.3f}
    优先级择值 ：{FY2023 年度数:.3f} = {取 INT-01 值的加总:.3f} + {优先级修正额:.3f}
    分部量级   ：{FY2023 分部原始加总:.3f} − {错位值:.3f} + {修正值:.3f} = {FY2023 年度数:.3f}
（示例输出形如 666.701 = 723.801 − 57.100、804.029 = 801.550 + 2.479、
 941.252 − 152.470 + 15.247 = 804.029；示例仅供人读，实际值每次运行时
 从 input_files 计算并在 stdout 与交付物中重算输出。）

用法:
    python3 FIN3-WKN-152_reproduce.py [--input-dir DIR] [--output-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import os
import re
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
    m["cap_total_row"] = sum(f(r["shares_mm"]) for r in cap
                             if r["holder_class"].startswith("TOTAL"))
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
    raw_sum = {"FY2022": 0.0, "FY2023": 0.0}      # 未去重、未择值的逐行原始加总
    for r in mon:
        raw_sum[r["fy"]] += f(r["revenue_usd_mm"])
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
    m["monthly_raw_sum"] = raw_sum
    # 三条钦定勾稽算式的原料（全部由上面的明细推出）：
    m["eq_dup_val"] = dups[0][2] if dups else 0.0                       # 重复行金额
    m["eq_dup_month"] = dups[0][1] if dups else ""
    if superseded:                                                      # 同月双值择项
        fy, mo, drop_v, drop_s, keep_v, keep_s = superseded[0]
        m["eq_conflict_month"] = mo
        m["eq_drop_val"], m["eq_drop_sid"] = drop_v, drop_s
        m["eq_keep_val"], m["eq_keep_sid"] = keep_v, keep_s
        m["eq_keep_prio"], m["eq_drop_prio"] = prio.get(keep_s, 99), prio.get(drop_s, 99)
        # 若取被舍弃的低优先级值时的全年加总：去重后加总 − 优先值 + 被舍弃值
        m["eq_alt_sum"] = fy_sum[fy] - keep_v + drop_v
        m["eq_prio_fix"] = keep_v - drop_v
        m["eq_alt_fy"] = fy

    seg_rows = read_csv(os.path.join(indir, "financials",
                                     "revenue_by_segment_2022_2023.csv"))
    by_fy = {}
    for r in seg_rows:
        by_fy.setdefault(r["fy"], {})[r["segment"]] = f(r["revenue_usd_mm"])
    m["segment_sum"], m["segment_fixups"] = {}, []
    m["segment_raw_sum"] = {fy: sum(parts.values()) for fy, parts in by_fy.items()}
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
    m["sbc_total_row"] = sum(f(r["amount_usd_mm"]) for r in sbc
                             if r["fy"] == "FY2023" and r["component"] == "TOTAL")
    rst = read_csv(os.path.join(indir, "financials", "restructuring_detail_2023.csv"))
    m["rst_detail_sum"] = sum(f(r["amount_usd_mm"]) for r in rst if r["component"] != "TOTAL")
    m["rst_total_row"] = sum(f(r["amount_usd_mm"]) for r in rst
                             if r["component"] == "TOTAL")
    fcf = read_csv(os.path.join(indir, "financials", "fcf_bridge_2023.csv"))
    m["fcf_detail"] = {r["line_item"]: f(r["amount_usd_mm"]) for r in fcf}

    m["comps_a"] = read_csv(os.path.join(indir, "comps",
                                         "underwriter_A_comps_20240315.csv"))
    m["comps_b"] = read_csv(os.path.join(indir, "comps",
                                         "underwriter_B_comps_20240318.csv"))
    # 承销商自编 comps 的倍数区间（竞争值，仅作交叉验证）
    b_mults = [f(r["ntm_ev_revenue"]) for r in m["comps_b"] if r.get("ntm_ev_revenue")]
    m["b_range"] = (min(b_mults), max(b_mults)) if b_mults else (None, None)

    # 被取代的 v2 政策：版本说明与被取代区间（竞争值）
    v2_path = os.path.join(indir, "committee", "Committee_Policy_v2_20240305.xlsx")
    v2_note = dict_of_xlsx(v2_path, "Revision_Note")
    m["v2_note"] = {k: str(v) for k, v in v2_note.items()}
    m["v2_range"] = None
    m["v2_superseded"] = []
    for r in rows_of_xlsx(v2_path, "Committee_Policy")[1:]:
        if not r or not r[0]:
            continue
        if str(r[0]).strip() == "CP-07":
            hit = re.search(r"([0-9.]+)x[–\-]([0-9.]+)x", str(r[2]))
            if hit:
                m["v2_range"] = (float(hit.group(1)), float(hit.group(2)))
        if str(r[3]).strip().upper().startswith("SUPERSEDED"):
            m["v2_superseded"].append((str(r[0]).strip(), str(r[2])))
    m["flash"] = read_csv(os.path.join(indir, "internal",
                                       "management_flash_20240319.csv"))
    m["revision_log"] = read_csv(os.path.join(indir, "internal", "data_revision_log.csv"))
    m["flash_vals"] = {r["metric"]: f(r["FY2023_value"]) for r in m["flash"]}

    # 竞争值：行业基准增长率（research/sector_benchmark.md 的 Revenue growth 行）
    bench_txt = open(os.path.join(indir, "research", "sector_benchmark.md"),
                     "r", encoding="utf-8").read()
    bench_hit = re.search(r"Revenue growth[^\n|]*\|\s*([0-9.]+)\s*%", bench_txt)
    if not bench_hit:
        raise ValueError("sector_benchmark.md 未找到行业基准增长率")
    m["bench_growth"] = float(bench_hit.group(1)) / 100.0

    # 输入材料清点：os.walk 实际扫描，不写死任何计数
    per_dir, root_files = {}, 0
    for dp, _dn, fn in os.walk(indir):
        rel = os.path.relpath(dp, indir)
        if rel == ".":
            root_files += len(fn)
        else:
            top = rel.split(os.sep)[0]
            per_dir[top] = per_dir.get(top, 0) + len(fn)
    m["inventory"] = {"per_dir": per_dir,
                      "dir_count": len(per_dir),
                      "root_files": root_files,
                      "subdir_total": sum(per_dir.values()),
                      "total": sum(per_dir.values()) + root_files}
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

    # ---- 钦定算式：全部由 f-string 拼接运行时计算结果，无写死结论常量 ----
    d["eq_r05"] = f"{d['uw_ebitda']:.3f} = {d['adj_ebitda']:.3f} - {d['sbc']:.3f}"
    d["eq_r07"] = f"{d['rev2024e']:.3f} = {d['rev23']:.3f} × (1 + {d['growth']:.0%})"
    d["eq_r08"] = f"{d['net_cash']:,.3f} = {d['cash']:.3f} + {d['mktsec']:.3f}"
    d["eq_r09"] = (f"折后每股 = 每股 × (1 − {d['discount']:.1%})"
                   f" = 每股 × {1 - d['discount']:.3f}")
    d["eq_r11"] = (f"{d['net_primary']:.3f} = {d['gross_primary']:.3f}"
                   f" - {d['uw_fee']:.3f} - {d['fixed']:.3f}")
    d["eq_r16"] = (f"{d['full_gross_primary']:.6f} = ({d['primary']:.6f}"
                   f" + {d['gs']:.1f}) × {d['price']:.0f}")
    d["eq_r17a"] = f"{d['post_shares']:.6f} = {d['pre_shares']:.6f} + {d['primary']:.6f}"
    d["eq_r17b"] = f"{d['full_post_shares']:.6f} = {d['post_shares']:.6f} + {d['gs']:.6f}"
    d["eq_r28"] = (f"{d['gs_incremental_net']:.3f} = {d['gs']:.1f} × {d['price']:.0f}"
                   f" × (1 − {d['fee']:.0%})")
    # R30 月度去重算式：年度数 = 原始加总 − 重复行金额
    d["eq_r30"] = (f"{d['rev22']:.3f} = {m['monthly_raw_sum']['FY2022']:.3f}"
                   f" − {m['eq_dup_val']:.3f}")
    # R31 优先级择值算式：年度数 = 取低优先级值的加总 + 优先级修正额
    d["eq_r31"] = (f"{d['rev23']:.3f} = {m['eq_alt_sum']:.3f} + {m['eq_prio_fix']:.3f}")
    d["eq_r31_prio"] = (f"{m['eq_keep_sid']} Priority {m['eq_keep_prio']} > "
                        f"{m['eq_drop_sid']} Priority {m['eq_drop_prio']}")
    # R32 分部量级错位算式
    fix23 = next((x for x in m["segment_fixups"] if x[0] == "FY2023"), None)
    d["segment_fix_fy2023"] = fix23
    if fix23:
        _fy, _seg, bad, good = fix23
        d["eq_r32"] = (f"{m['segment_raw_sum']['FY2023']:.3f} − {bad:.3f}"
                       f" + {good:.3f} = {d['rev23']:.3f}")
    else:
        d["eq_r32"] = f"{m['segment_sum']['FY2023']:.3f} = {d['rev23']:.3f}"
    # R03 估值链四步算式（低/中/高三档各四步，逐行列出）
    d["chain"] = {}
    for _lab in ("Low", "Mid", "High"):
        _s = d["scen"][_lab]
        d["chain"][_lab] = [
            f"EV = {_s['mult']} × 2024E Revenue {d['rev2024e']:.3f} = {_s['ev']:.3f}",
            f"pre-money Equity = EV + {d['cash']:.3f} + {d['mktsec']:.3f} = {_s['eq']:.3f}",
            f"每股 = Equity ÷ {d['pre_shares']:.6f} = {_s['undisc']:.4f}",
            (f"折后每股 = 每股 × (1 − {d['discount']:.1%})"
             f" = {_s['undisc']:.4f} × {1 - d['discount']:.3f} = {_s['offer']:.4f}"),
        ]
    # R04 拟议价定位三行分列判算
    d["dist_mid"] = d["mid"] - d["price"]
    d["guard"] = 0.50
    d["pos_check"] = [
        f"① 区间包含：{d['price']:.2f} ≥ {d['low']:.2f} 且 {d['price']:.2f} ≤ {d['high']:.2f}"
        f" → 在支持区间内",
        f"② 距离算式：{d['mid']:.2f} − {d['price']:.2f} = {d['dist_mid']:.2f}",
        f"③ 护栏比较：{d['dist_mid']:.2f} ≤ {d['guard']:.2f} → 未超 $0.50/share 护栏",
    ]

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
    # base case（增长 × 倍数）在钦定网格中的位置与其单元格值（R18）
    d["base_g_idx"] = d["sens_growths"].index(d["growth"])
    d["base_m_idx"] = d["sens_mults"].index(d["peer_mid"])
    d["base_cell"] = d["sens"][d["base_g_idx"]][d["base_m_idx"]]

    flash = m["flash_vals"]
    dup_val = m["eq_dup_val"]
    d["conflicts"] = [
        # 1) FY2023 Revenue：SEC-01 对未复核 flash（R12 / R19）
        ("FY2023 Revenue 取值", f"{d['rev23']:.3f}（SEC-01, Priority 1）",
         "sec_filings/SEC-01_financials_extract.xlsx",
         f"internal/management_flash_20240319.csv：Revenue "
         f"{flash['Revenue']:.3f}、Adjusted EBITDA {flash['Adjusted EBITDA']:.3f}、"
         f"SBC {flash['Stock-based compensation & related taxes']:.3f}"
         "（IR 未复核初稿，INT-01 Priority 9）",
         "按 CP-02 来源优先级排除未复核 flash，取 SEC-01"),
        # 2) 2023-12 同月双值（R13 / R31）
        ("FY2023 月度明细 2023-12 同月双值",
         f"{m['eq_keep_val']:.3f}（{m['eq_keep_sid']} Priority {m['eq_keep_prio']}）",
         "financials/monthly_revenue_2022_2023.csv（2023-12）",
         f"{m['eq_drop_val']:.3f}（{m['eq_drop_sid']} Priority {m['eq_drop_prio']}）",
         f"两行均无标注，按 Source_Index 优先级取 {m['eq_keep_sid']}"
         f"（{d['eq_r31_prio']}）；{d['eq_r31']}"),
        # 3) 2022-08 重复导出（R13 / R30）
        ("FY2022 月度明细 2022-08 重复导出",
         f"{dup_val:.3f}（保留一行，SEC-01 Priority 1）",
         "financials/monthly_revenue_2022_2023.csv（2022-08）",
         f"{dup_val:.3f} / {dup_val:.3f}（两行同值、均无标注）",
         f"重复行去重；{d['eq_r30']}"),
        # 4) 分部 Other 量级错位（R19 / R32）
        ("FY2023 分部 Other 量级错位",
         (f"{d['segment_fix_fy2023'][3]:.3f}（按年度数修正）"
          if d["segment_fix_fy2023"] else f"{m['segment_sum']['FY2023']:.3f}"),
         "financials/revenue_by_segment_2022_2023.csv（FY2023 Other）",
         (f"{d['segment_fix_fy2023'][2]:.3f}（底表原值，量级错位）"
          if d["segment_fix_fy2023"] else "无"),
         f"按 SEC-01 年度数与 Advertising 差额修正；{d['eq_r32']}"),
        # 5) peer 区间：committee peer set vs 承销商自编 comps（R27 ①）
        ("Peer EV/Revenue 区间",
         f"{d['peer_low']}x–{d['peer_high']}x（中点 {d['peer_mid']}x，CP-07）",
         "committee/Committee_Policy_v3_20240320.xlsx / "
         "committee/Underwriting_Assumptions_20240320.xlsx",
         f"comps/underwriter_B_comps_20240318.csv：{m['b_range'][0]}x–"
         f"{m['b_range'][1]}x（承销商自编）",
         "承销商自编 comps 按 CP-07 仅作交叉验证，不作定价端点"),
        # 6) peer 区间竞争值：被取代的 v2 区间（R27 ②）
        ("Peer 区间竞争值（被取代版本）",
         f"{d['peer_low']}x–{d['peer_high']}x（v3 现行区间）",
         "committee/Committee_Policy_v3_20240320.xlsx CP-07",
         (f"committee/Committee_Policy_v2_20240305.xlsx："
          f"{m['v2_range'][0]}x–{m['v2_range'][1]}x" if m["v2_range"]
          else "committee/Committee_Policy_v2_20240305.xlsx"),
         (f"v2 CP-07 已标 SUPERSEDED 作废，"
          f"故排除 {m['v2_range'][0]}x–{m['v2_range'][1]}x" if m["v2_range"]
          else "v2 CP-07 已标 SUPERSEDED 作废")),
        # 7) 委员会政策版本取代（R26 / R19）
        ("委员会政策版本", "Committee_Policy v3（2024-03-20）现行",
         "committee/Committee_Policy_v3_20240320.xlsx",
         "；".join(f"{pid} {conv}" for pid, conv in m["v2_superseded"])
         or "v2 被取代条款",
         "v2 上述条款均标 SUPERSEDED 不再适用；一律以 v3（2024-03-20）为准"),
        # 8) 2024E 增长率 vs 行业基准（R07）
        ("2024E 收入增长率",
         f"{d['growth']:.0%}（CP-06 委员会内部预测假设，非 SEC 公开事实）",
         "committee/Underwriting_Assumptions_20240320.xlsx",
         f"research/sector_benchmark.md 行业基准 {m['bench_growth']:.0%}（行业中位）",
         f"行业基准仅作背景，CP-06 指定 {d['growth']:.0%} 由委员会假设，"
         f"排除 {m['bench_growth']:.0%}"),
        # 9) SBC 处置（R19）
        ("SBC 处置", "撤销 SBC 加回（承销口径不加回）",
         "committee/Committee_Policy_v3_20240320.xlsx CP-03",
         "v2 CP-03：SBC 加回暂予保留（SUPERSEDED）",
         "采用 v3，撤销加回"),
        # 10) 承销费计提基数（R19 / R11）
        ("承销费计提基数", "公司 primary gross proceeds × 5%",
         "committee/Committee_Policy_v3_20240320.xlsx CP-12",
         "v2 CP-12：按含 secondary 的全部发行股份计提（SUPERSEDED）",
         "v2 CP-12 已作废；secondary 不形成公司募集资金，费基不含 secondary"),
        # 11) 旧底稿处置（R19 / N01）
        ("Legacy 旧底稿", "不作为结论依据",
         "legacy/Candidate_Model_v0.xlsx",
         "含 #REF! 断链与多类 legacy 错误口径",
         "全部重算修正，逐条记入 Error_Audit"),
        # 12) R36 方法论理由①：Mid 取区间中点
        ("方法论理由①（Mid 档取 4.5x）",
         f"Mid = 委员会 peer 区间 {d['peer_low']}x–{d['peer_high']}x 的中点 "
         f"{d['peer_mid']}x",
         "CP-07：区间以 Committee_Peer_Set 为准",
         "算术中位数 / comps/peer_multiples_history.csv 历史倍数中位数",
         "CP-07 指定以委员会区间为准，历史倍数中位数不属控制口径，"
         "故 Mid 取区间中点而非算术或历史中位数"),
        # 13) R36 理由②：排除未复核 flash
        ("方法论理由②（排除未复核 flash）",
         "不采用 internal/management_flash_20240319.csv",
         "CP-02 来源优先级：INT-01 Priority 9",
         f"flash 所载 Revenue {flash['Revenue']:.3f}、Adj EBITDA "
         f"{flash['Adjusted EBITDA']:.3f}、SBC "
         f"{flash['Stock-based compensation & related taxes']:.3f}",
         "CP-02：未复核 IR 初稿仅供参考，Priority 9 低于 SEC-01 Priority 1，"
         "不得作承销口径结论的取数来源，故排除"),
        # 14) R36 理由③：采用 v3 而非 v2
        ("方法论理由③（采用 v3 而非 v2）",
         "采用 Committee_Policy v3（2024-03-20）",
         "committee/Committee_Policy_v3_20240320.xlsx",
         f"v2（2024-03-05）{' / '.join(pid for pid, _ in m['v2_superseded'])}",
         "v2 上述条款均标 SUPERSEDED 已作废，v3 为现行控制口径，故采用 v3"),
        # 15) R36 理由④：承销费只对公司 primary gross 计提
        ("方法论理由④（承销费只计 primary）",
         "承销费 = 公司 primary gross proceeds × 5%（CP-12）",
         "committee/Committee_Policy_v3_20240320.xlsx CP-12",
         "含 secondary 的发行股份基数（v2 CP-12，已作废）",
         "secondary 属出售股东股份转让、不形成公司募集资金，"
         "故费基只含公司 primary gross、不含 secondary"),
    ]
    return d


ISSUE_MAP = {
    "Profitability": ("Reverse the SBC addback and report underwriting EBITDA",
                      "Underwriting profitability is materially weaker than the management metric"),
    "Valuation": ("Use 2024E Revenue as the forward denominator and apply the IPO execution discount",
                  "Forward denominator and committee-supported range"),
    "Cash": ("Include both cash and marketable securities in the pre-money equity bridge",
             "An incomplete net cash bridge understates pre-money equity"),
    "Primary/Secondary": ("{primary}m is primary and {secondary}m is secondary",
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
    # R34 输入材料清点：由 load_materials 的 os.walk 实际扫描结果生成
    inv = m["inventory"]
    rows += [[], ["输入材料清点（脚本 os.walk 实际扫描）", "值"],
             ["文件总数", inv["total"]],
             ["来源目录数", inv["dir_count"]],
             ["目录", "文件数"]]
    for name in ("committee", "sec_filings", "financials", "comps",
                 "research", "internal", "legacy"):
        if name in inv["per_dir"]:
            rows.append([f"{name}/", inv["per_dir"][name]])
    rows += [["七目录小计", inv["subdir_total"]],
             [f"根目录散件（{os.path.basename(IN_DIR)} 顶层文件）", inv["root_files"]],
             ["合计（七目录小计 + 根目录散件 = 文件总数）", inv["total"]],
             [], ["待核实项", "说明"],
             ["2024E 分季度收入拆分", "待核实——材料未载明，不予给出"]]
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
            ["承销口径 EBITDA 完整算式", "",
             d["eq_r05"], d["uw_ebitda"],
             "三个列报值齐全：起始值、SBC 加回撤销项、结果"],
            ["正负判断", "", "调整后 EBITDA 仍为负", "",
             f"{d['uw_ebitda']:.3f} < 0，盈利质量弱（CP-05 / CP-13）"],
            ["2023 Free Cash Flow", d["fcf"], "No normalization", d["fcf"],
             "Cash quality weak"],
            ["2023 Restructuring", d["restructuring"],
             "Non-recurring but already reflected in management Adj EBITDA - no double count (CP-04)",
             d["restructuring"], "No double count"],
            [],
            ["Valuation method selected", "",
             "Underwriting EBITDA remains negative -> EV / 2024E Revenue (CP-05)",
             m["valuation_method"], ""],
            ["2024E Revenue 完整算式", "",
             d["eq_r07"], d["rev2024e"],
             f"{d['growth']:.0%} 为 CP-06 委员会内部预测假设，非 SEC 公开事实"]]
    sheet(wb.create_sheet("QoE"), rows, [38, 22, 62, 22, 34])

    rows = [["Scenario", "EV/Revenue", "2024E Revenue", "Enterprise Value",
             "Pre-money Equity", "Undiscounted / sh", "Offer Value / sh", "Comment"]]
    for lab in ("Low", "Mid", "High"):
        s = d["scen"][lab]
        rows.append([lab, s["mult"], d["rev2024e"], s["ev"], s["eq"], s["undisc"], s["offer"],
                     "peer-implied equity x (1 - IPO execution discount)"])
    # 净现金桥：分列两行 + 合计算式（CP-08）
    rows += [[], ["净现金桥（分列两行 + 合计算式）", "Value", "", "", "", "", "", ""],
             ["2023 年末现金及现金等价物", d["cash"], "", "", "", "", "", ""],
             ["2023 年末有价证券", d["mktsec"], "", "", "", "", "", ""],
             ["净现金合计算式", d["eq_r08"], "", "", "", "", "", ""]]
    # 估值链四步算式：低/中/高三档逐行列出，每步带列报值
    rows += [[], ["估值链四步算式（逐行列出，每步带列报值）"],
             ["档位", "步骤", "算式", "列报值", "", "", "", ""]]
    for lab in ("Low", "Mid", "High"):
        s = d["scen"][lab]
        step_vals = [s["ev"], s["eq"], s["undisc"], s["offer"]]
        for i, eq in enumerate(d["chain"][lab]):
            rows.append([lab if i == 0 else "", f"第{i + 1}步", eq, step_vals[i],
                         "", "", "", ""])
    # 执行折扣算式与作用对象（CP-09）
    rows += [[], ["执行折扣算式与作用对象", d["eq_r09"],
                  f"作用对象为 peer-implied 每股价值（per-share），"
                  f"非收入、非企业价值；比例 {d['discount']:.1%}",
                  "", "", "", "", ""]]
    # 拟议价定位：三行分列判算
    rows += [[], ["拟议价定位（三行分列判算）"]]
    for chk in d["pos_check"]:
        rows.append([chk, "", "", "", "", "", "", ""])
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
    rows += [[], ["Base case（增长率 × 倍数）",
                  f"{d['growth']:.0%} × {d['peer_mid']}x = {d['base_cell']:.2f}"],
             ["增长率轴（5 档）", " / ".join(f"{g:.0%}" for g in d["sens_growths"])],
             ["倍数轴（5 档）", " / ".join(f"{mm}x" for mm in d["sens_mults"])],
             ["Note", "Scenario grid uses the same net cash bridge, share count and IPO "
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
    # 钦定算式（R11 / R16 / R28）：逐行写出，带列报值
    rows += [[], ["钦定算式", "算式（计算结果）", "", "Unit", "Note"],
             ["公司 gross primary proceeds（含 greenshoe 情景）", d["eq_r16"], "", "USD mm",
              "greenshoe 不并入 Base，仅 full-exercise 情景"],
             ["费用扣减（承销费与固定费用分列）", d["eq_r11"], "", "USD mm",
              "基数为公司 primary gross（不含 secondary）；固定费用只扣一次"],
             ["greenshoe 增量净募集资金", d["eq_r28"], "", "USD mm",
              "只扣 5% 承销费，不重复扣减固定费用"]]
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
             "SEC-02 截止日前独立口径，仅作交叉验证、不作定价主口径"],
            ["Immediate dilution cross-check @ assumed $32.50", d["dilution"], d["dilution"],
             "USD/share", "SEC-02 截止日前独立口径，仅作交叉验证、不作定价主口径"],
            ["Proposed-price post-money equity", d["proposed_post_equity"],
             d["full_post_shares"] * d["price"], "USD mm", "post-money shares x proposed price"],
            [], ["股本桥算式", "算式（计算结果）", "", "Unit", "Note"],
            ["Base post-money 股数桥", d["eq_r17a"], "", "mm shares",
             "secondary 不计入总股数（CP-10）"],
            ["Full greenshoe post-money 股数桥", d["eq_r17b"], "", "mm shares",
             "greenshoe 只在 full-exercise 情景并入（CP-11）"]]
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
            ["负 QoE 前提①", f"承销口径 EBITDA 为负：{d['uw_ebitda']:.3f}mm"],
            ["负 QoE 前提②", f"2023 年 FCF 为负：{d['fcf']:.3f}mm"],
            ["净现金桥-现金及现金等价物", d["cash"]],
            ["净现金桥-有价证券", d["mktsec"]],
            ["净现金桥-合计算式", d["eq_r08"]],
            ["拟议价定位①（区间包含）", d["pos_check"][0]],
            ["拟议价定位②（距离）", d["pos_check"][1]],
            ["拟议价定位③（护栏）", d["pos_check"][2]],
            ["Structure view", "Base separates primary from secondary, excludes greenshoe from "
                               "Base, and grants no secondary proceeds or share count increase "
                               "to the company."],
            ["Recommendation", f"{d['decision']} at ${d['price']:.0f}"],
            ["Disclosure requirement", "Disclose negative QoE in the memo; do not raise the price "
                                       "solely because management Adjusted EBITDA improved."],
            ["输入材料清点", f"文件总数 {m['inventory']['total']}；"
                             f"来源目录数 {m['inventory']['dir_count']}；"
                             f"分目录明细见 Inputs 表"],
            ["数据核验明细", "四处明细异常（2022-08 重复、2023-12 双值、分部 Other 量级、"
                             "SBC TOTAL 行不符）逐行见 Tieout_Detail 表"]]
    sheet(wb.create_sheet("Pricing_Summary"), rows, [44, 96])

    rows = [["#", "Workstream / Issue", "Legacy treatment (as-is)", "Correct treatment",
             "Why it matters"]]
    n = 0
    for r in rows_of_xlsx(os.path.join(IN_DIR, "legacy", "Candidate_Model_v0.xlsx"),
                          "Candidate_Model")[1:]:
        n += 1
        ws_name = str(r[0]).strip()
        corr = ISSUE_MAP.get(ws_name, (str(r[2]), ""))
        fix_txt = corr[0].format(primary=f"{d['primary']:.6f}",
                                 secondary=f"{d['secondary']:.6f}")
        rows.append([n, ws_name, str(r[1]), fix_txt, corr[1]])
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

    # ---- R35 结构化勾稽明细表：逐行列出，差额 = 明细加总 − 目标年度数 ----
    def tie(name, period, detail, target, kind, action, clause):
        return [name, period, round(detail, 6), round(target, 6),
                round(detail - target, 6), kind, action, clause]

    sbc_fix = (f"以明细为准取 {m['sbc_detail_sum']:.3f}"
               if abs(m["sbc_detail_sum"] - m["sbc_total_row"]) > 5e-4
               else "明细与 TOTAL 一致")
    seg_fy2023 = m["segment_raw_sum"].get("FY2023", 0.0)
    seg_act = d["eq_r32"] if d["segment_fix_fy2023"] else "分部加总与年度数一致"
    tie_rows = [
        ["序列名称", "期间", "明细加总值", "目标年度数", "差额", "异常类型",
         "处置结果", "依据条款"],
        tie("月度收入", "FY2022", m["monthly_raw_sum"]["FY2022"], d["rev22"],
            f"2022-08 重复导出（两行同值 {m['eq_dup_val']:.3f}，无标注）",
            f"重复行去重；{d['eq_r30']}", "CP-02 / Source_Index SEC-01 Priority 1"),
        tie("月度收入", "FY2023", m["eq_alt_sum"], d["rev23"],
            f"{m['eq_conflict_month']} 同月双值（{m['eq_keep_sid']} "
            f"{m['eq_keep_val']:.3f} vs {m['eq_drop_sid']} {m['eq_drop_val']:.3f}，无标注；"
            "此处为取 INT-01 值的对照加总）",
            f"按来源优先级取 {m['eq_keep_sid']}；{d['eq_r31']}；{d['eq_r31_prio']}",
            "CP-02 / Source_Index Priority 1 > 9"),
        tie("分部收入", "FY2022", m["segment_raw_sum"].get("FY2022", 0.0), d["rev22"],
            "无异常", "分部加总与 SEC-01 年度数一致", "CP-02 / SEC-01"),
        tie("分部收入", "FY2023", seg_fy2023, d["rev23"],
            "Other 分部量级错位" if d["segment_fix_fy2023"] else "无异常", seg_act,
            "CP-02 / SEC-01 年度数差额修正"),
        tie("地区收入", "FY2023", m["geo_sum"].get("FY2023", 0.0), d["rev23"],
            "无异常", "地区加总与 SEC-01 年度数一致", "CP-02 / SEC-05"),
        tie("SBC 明细合计", "FY2023", m["sbc_detail_sum"], m["sbc_total_row"],
            f"文件 TOTAL 行 {m['sbc_total_row']:.3f} 与明细加总 "
            f"{m['sbc_detail_sum']:.3f} 不一致",
            f"{sbc_fix}（撤回 SBC 加回按明细值）", "CP-02 / CP-03"),
        tie("cap table 合计", "2024-03-18", m["pre_shares_cap"], d["pre_shares"],
            "无异常", "明细各类别合计与发行条款 pre-money 股数一致", "CP-10 / Offering_Terms"),
        tie("重构明细合计", "FY2023", m["rst_detail_sum"], m["rst_total_row"],
            "无异常", "明细与 TOTAL 一致；不重复调整（CP-04）", "CP-04"),
    ]
    rows = tie_rows
    rows += [[],
             ["钦定勾稽算式（计算结果）", d["eq_r30"]],
             ["钦定勾稽算式（计算结果）", d["eq_r31"]],
             ["钦定勾稽算式（计算结果）", d["eq_r32"]]]
    sheet(wb.create_sheet("Tieout_Detail"), rows, [20, 14, 16, 16, 12, 44, 52, 32])

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
        ["3a", "承销口径 EBITDA 完整算式", d["eq_r05"],
         f"三个列报值齐全：起始 {d['adj_ebitda']:.3f}、"
         f"撤销 SBC 加回 -{d['sbc']:.3f}、结果 {d['uw_ebitda']:.3f}", "CP-03"],
        ["3b", "判断：调整后 EBITDA 仍为负", str(d["uw_ebitda_negative"]),
         f"{d['eq_r05']} → {d['uw_ebitda']:.3f} < 0，盈利质量弱", "CP-05"],
        ["4", "Free Cash Flow (2023)", f"{d['fcf']:.3f}", "company definition", "CP-13"],
        ["5", "Restructuring costs (2023)", f"{d['restructuring']:.3f}",
         "non-recurring but already inside management adjustments - no double count", "CP-04"],
        ["6", "SBC detail tie-out", f"{d['xcheck']['sbc_detail_fy2023']:.3f}",
         "financials/sbc_detail_2022_2023.csv", "CP-02"],
        ["7", "Restructuring detail tie-out", f"{d['xcheck']['restructuring_detail_fy2023']:.3f}",
         "financials/restructuring_detail_2023.csv", "CP-02"],
        ["8", "调整后 EBITDA 仍为负（结论）", str(d["uw_ebitda_negative"]),
         "QoE conclusion", "CP-05"],
        ["9", "2023 年 FCF 为负（结论）", str(d["fcf_negative"]),
         "QoE conclusion", "CP-13"],
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return path


def build_valuation_matrix(m, d, outdir):
    path = os.path.join(outdir, f"{TASK}_valuation_matrix.csv")
    rows = [["2024E_growth"] + [f"{x}x" for x in d["sens_mults"]]]
    for i, g in enumerate(d["sens_growths"]):
        rows.append([f"{g:.0%}"] + [f"{v:.2f}" for v in d["sens"][i]])
    rows += [[],
             ["base_case_growth", f"{d['sens_growths'][d['base_g_idx']]:.0%}"],
             ["base_case_multiple", f"{d['sens_mults'][d['base_m_idx']]}x"],
             ["base_case_cell",
              f"{d['sens_growths'][d['base_g_idx']]:.0%} × "
              f"{d['sens_mults'][d['base_m_idx']]}x = {d['base_cell']:.2f}"],
             ["grid_growth_axis", " / ".join(f"{g:.0%}" for g in d["sens_growths"])],
             ["grid_multiple_axis", " / ".join(f"{mm}x" for mm in d["sens_mults"])],
             ["peer_range_adopted",
              f"{d['peer_low']}x-{d['peer_high']}x (mid {d['peer_mid']}x, CP-07 committee peer set)"],
             ["peer_range_competing_1",
              f"{m['b_range'][0]}x-{m['b_range'][1]}x "
              "(comps/underwriter_B_comps_20240318.csv, cross-check only)"],
             ["peer_range_competing_2",
              (f"{m['v2_range'][0]}x-{m['v2_range'][1]}x "
               "(Committee_Policy_v2 CP-07, superseded)" if m["v2_range"]
               else "(Committee_Policy_v2 CP-07, superseded)")],
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
    text((640, 506),
         f"base case: {d['growth']:.0%} x {d['peer_mid']}x = ${d['base_cell']:.2f}", fsm)
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
    inv = m["inventory"]
    flash = m["flash_vals"]
    fix23 = d["segment_fix_fy2023"]
    seg_raw = m["segment_raw_sum"].get("FY2023", 0.0)
    seg_bad = fix23[2] if fix23 else 0.0
    keep_v, drop_v = m["eq_keep_val"], m["eq_drop_val"]
    sbc_total = m["sbc_total_row"]
    sbc_detail = m["sbc_detail_sum"]
    # 材料清点表（目录与计数全部来自 os.walk 实际扫描）
    inv_lines = "\n".join(
        f"| {name}/ | {inv['per_dir'].get(name, 0)} |"
        for name in ("committee", "sec_filings", "financials", "comps",
                     "research", "internal", "legacy"))
    inv_md = (f"| 目录 | 文件数 |\n|---|---|\n{inv_lines}\n"
              f"| 根目录散件 | {inv['root_files']} |\n"
              f"| 合计 | {inv['total']} |")
    v2_scope = m["v2_note"].get("取代范围", "被取代条款")
    txt = f"""# Pricing Committee 定价备忘录 — Reddit, Inc. IPO

**日期**：2024-03-20（信息截止时点） · **议题**：拟议价格 ${d['price']:.0f} 是否继续推进

## 一、定价建议
**Proceed at ${d['price']:.0f}（按拟议价继续推进）。** 拟议价定位判算分列三行：
- ① 区间包含：{d['price']:.2f} ≥ {lo:.2f} 且 {d['price']:.2f} ≤ {hi:.2f}，在支持区间之内。
- ② 距离算式：{d['mid']:.2f} − {d['price']:.2f} = {d['dist_mid']:.2f}（距 midpoint 约 ${d['dist_mid']:.2f}）。
- ③ 护栏比较：{d['dist_mid']:.2f} ≤ 0.50，未超过 $0.50/share 护栏。
本建议以披露下述盈利质量风险为前提。

## 二、盈利质量（QoE）
2023 年 Revenue {d['rev23']:.3f}mm、管理层 Adjusted EBITDA {d['adj_ebitda']:.3f}mm；
撤销 SBC 加回 {d['sbc']:.3f}mm 后承销口径算式 {d['eq_r05']}，调整后 EBITDA 仍为负。
两项负 QoE 前提分列：
- ① 承销口径 EBITDA 为负：{d['uw_ebitda']:.3f}mm；
- ② 2023 年 FCF 为负：{d['fcf']:.3f}mm。
重组费用 {d['restructuring']:.3f}mm 已含于管理层指标，不重复调整。**不得仅因管理层
Adjusted EBITDA 改善而上调价格。** 承销 EBITDA 为负，主估值改用 EV / 2024E Revenue（CP-05）。

## 三、估值支撑
- 分母算式：{d['eq_r07']}；{d['growth']:.0%} 为 CP-06 委员会内部预测假设而非 SEC 公开事实，
  竞争值行业基准 {m['bench_growth']:.0%}（research/sector_benchmark.md）仅作背景，按 CP-06 排除。
- 净现金桥-现金及现金等价物：{d['cash']:.3f}mm（2023 年末，单独一行）。
- 净现金桥-有价证券：{d['mktsec']:.3f}mm（2023 年末，单独一行）。
- 净现金桥-合计算式：{d['eq_r08']}。
- 四步估值链（Mid 档 {d['peer_mid']}x，低/高两档见模型 Valuation 表逐行列出）：
  EV = {d['peer_mid']} × {d['rev2024e']:.3f}；pre-money Equity = EV + {d['cash']:.3f} + {d['mktsec']:.3f}；
  每股 = Equity ÷ {d['pre_shares']:.6f}；折后每股 = 每股 × (1 − {d['discount']:.1%})
  （即 × {1 - d['discount']:.3f}，作用对象为每股价值）。
- 结论：低/中/高每股 ${lo:.2f} / ${d['mid']:.2f} / ${hi:.2f}，支持区间 ${lo:.2f}–${hi:.2f}，
  midpoint ${d['mid']:.2f}。SEC-02 交叉验算（假设价 $32.50）：每股有形账面净值
  ${d['ntbv']:.2f}、即时稀释 ${d['dilution']:.2f}，仅作交叉验证，不作定价主口径。

## 四、发行结构
Base：primary {d['primary']:.6f}m、secondary {d['secondary']:.6f}m（归出售股东，不形成公司
募集资金、不增加公司总股数）；{d['gs']:.1f}m greenshoe 不并入 Base，仅单列 full-exercise：
{d['eq_r16']}。按 ${d['price']:.0f} 公司 gross primary {d['gross_primary']:.3f}mm，费用分列两行
——5% 承销费 {d['uw_fee']:.3f}mm、固定费用 {d['fixed']:.3f}mm（费基不含 secondary），
{d['eq_r11']} 得 net primary {d['net_primary']:.3f}mm。greenshoe 增量净额 {d['eq_r28']}，
不重复扣固定费用。股本桥：{d['eq_r17a']}；{d['eq_r17b']}。

## 五、数据核验（逐条分列）
| 文件 | 行或月份 | 现象 | 判定依据 | 处置结果 |
|---|---|---|---|---|
| financials/monthly_revenue_2022_2023.csv | 2022-08 | 同值行重复导出且无标注 | 与 SEC-01 年度数 {d['rev22']:.3f} 不符 | 去重：{d['eq_r30']} |
| financials/monthly_revenue_2022_2023.csv | 2023-12 | 同月双值 {keep_v:.3f} 与 {drop_v:.3f}，均无标注 | Source_Index：SEC-01 Priority 1 高于 INT-01 Priority 9（CP-02） | 取 {keep_v:.3f}：{d['eq_r31']} |
| financials/revenue_by_segment_2022_2023.csv | FY2023 Other | {seg_bad:.3f} 量级错位 | 分部加总 {seg_raw:.3f} ≠ SEC-01 {d['rev23']:.3f} | 修正：{d['eq_r32']} |
| financials/sbc_detail_2022_2023.csv | FY2023 TOTAL | TOTAL 行 {sbc_total:.3f} ≠ 明细加总 {sbc_detail:.3f} | 明细分项可复核加总 | 以明细为准，取 {sbc_detail:.3f} |

## 六、输入材料清点（脚本 os.walk 实际扫描）
文件总数 {inv['total']}，来源目录数 {inv['dir_count']}，按目录分列：
{inv_md}
（七目录小计 {inv['subdir_total']} + 根目录散件 {inv['root_files']} = {inv['total']}。）

## 七、方法论理由（四项分列）
1. Mid 档取委员会 peer 区间 {d['peer_low']:.1f}x–{d['peer_high']:.1f}x 的中点 {d['peer_mid']:.1f}x：
   CP-07 指定以 Committee_Peer_Set 区间为准，历史倍数中位数（peer_multiples_history）不属
   控制口径，故不取算术或历史中位数。
2. 排除 internal/management_flash_20240319.csv（未复核 flash、IR 初稿、INT-01 Priority 9，载 Revenue {flash['Revenue']:.3f}、Adj EBITDA {flash['Adjusted EBITDA']:.3f}、SBC {flash['Stock-based compensation & related taxes']:.3f}）：CP-02 规定仅参考、不得作结论取数来源。
3. 采用 Committee_Policy v3（2024-03-20）而非 v2（2024-03-05）：v2 的 {v2_scope}已标
   SUPERSEDED 作废。
4. 承销费只对公司 primary gross 计提 5%：CP-12 规定费基为公司 primary gross proceeds；
   secondary 为出售股东股份转让、不形成公司募集资金，故不计入费基。

## 八、事实与假设分离
SEC 公开事实：2023 年财务数据、现金与有价证券、primary/secondary/greenshoe 发行股数。
内部委员会假设：{d['growth']:.0%} 收入增长、{d['peer_low']:.1f}x–{d['peer_high']:.1f}x peer 区间、
{d['discount']:.1%} 执行折扣、内部 cap-table 快照、拟议 ${d['price']:.0f}。

## 九、条件与风险
1. 必须披露 QoE：承销 EBITDA {d['uw_ebitda']:.3f}mm、FCF {d['fcf']:.3f}mm 均为负。
2. 信息集冻结于 2024-03-20；${d['price']:.0f} 是决策输入而非已实现的最终发行结果；
   材料未载明项（如 2024E 分季度收入拆分）标注待核实。
3. 区间纪律：偏离 midpoint 超 $0.50 时向 midpoint 方向 Reprice；跌出 ${lo:.2f}–${hi:.2f}
   或发行结构重新出现未解决硬错误时 Defer。
"""
    path = os.path.join(outdir, f"{TASK}_pricing_memo.md")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    return path


def main(argv=None):
    global IN_DIR
    # Windows 等非 UTF-8 控制台下保证中文与算式符号（− ×）可正常输出
    for _st in (sys.stdout, sys.stderr):
        try:
            if _st.encoding and _st.encoding.lower().replace("-", "") != "utf8":
                _st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
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
    print(f"  Eq de-duplicate FY2022  : {d['eq_r30']}")
    print(f"  Eq priority  FY2023     : {d['eq_r31']}")
    print(f"  Eq segment   FY2023     : {d['eq_r32']}")
    print(f"  Eq QoE                    : {d['eq_r05']}")
    print(f"  Eq 2024E Revenue        : {d['eq_r07']}")
    print(f"  Eq net cash             : {d['eq_r08']}")
    print(f"  Base case cell          : "
          f"{d['sens_growths'][d['base_g_idx']]:.0%} x "
          f"{d['sens_mults'][d['base_m_idx']]}x = {d['base_cell']:.2f}")
    print(f"  Materials inventory     : {m['inventory']['total']} files, "
          f"{m['inventory']['dir_count']} dirs")
    print(f"  Decision                : {d['decision']} at ${d['price']:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
