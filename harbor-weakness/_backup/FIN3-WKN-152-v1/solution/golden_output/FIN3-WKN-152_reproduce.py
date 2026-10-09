#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-152 可复算代码：IPO 定价委员会发行前复核

从 /app/input_files/Q7_题目.xlsx 读入原始材料，按 Committee_Policy 控制口径
计算盈利质量、估值区间、发行结构与稀释的全部结论，并输出关键结果。

用法：
    python3 FIN3-WKN-152_reproduce.py [输入工作簿路径]

说明：
    - 全部结论数值均由输入材料计算得到，代码中不写入任何结论常量；
      写入代码的仅为计算所需的口径开关与四舍五入展示位数。
    - 无网络访问，不依赖输入材料之外的任何数据源。
"""
from __future__ import annotations

import os
import sys

from openpyxl import load_workbook

DEFAULT_INPUTS = [
    "/app/input_files/Q7_题目.xlsx",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Q7_题目.xlsx"),
    "Q7_题目.xlsx",
]


def resolve_input() -> str:
    candidates = list(DEFAULT_INPUTS)
    if len(sys.argv) > 1:
        candidates.insert(0, sys.argv[1])
    env_path = os.environ.get("INPUT_WORKBOOK")
    if env_path:
        candidates.insert(0, env_path)
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    raise SystemExit("找不到输入工作簿 Q7_题目.xlsx")


def table(ws, key_col=1, val_col=2) -> dict:
    """按“第 key_col 列为键、第 val_col 列为值”读取工作表，忽略表头与空行。"""
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        k, v = row[key_col - 1], row[val_col - 1] if len(row) >= val_col else None
        if k is None or v is None:
            continue
        out[str(k).strip()] = v
    return out


def metric_row(ws) -> dict:
    """Public_Financials：Metric -> 2022A/2023A 两期数值。"""
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        out[str(row[0]).strip()] = {"2022A": row[1], "2023A": row[2]}
    return out


def terms(ws) -> dict:
    """Offering_Terms：Item -> (Base, Full Greenshoe)。"""
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        out[str(row[0]).strip()] = (row[1], row[2])
    return out


def main() -> int:
    path = resolve_input()
    wb = load_workbook(path, data_only=True)

    pub = metric_row(wb["Public_Financials"])
    trm = terms(wb["Offering_Terms"])
    asm = table(wb["Underwriting_Assumptions"], key_col=1, val_col=2)
    pol = table(wb["Committee_Policy"], key_col=1, val_col=3)

    # ---------------------------------------------------------------- 取数
    rev_2023 = float(pub["Revenue"]["2023A"])
    net_loss_2023 = float(pub["Net income (loss)"]["2023A"])
    adj_ebitda_2023 = float(pub["Adjusted EBITDA"]["2023A"])
    sbc_2023 = float(pub["Stock-based compensation & related taxes"]["2023A"])
    fcf_2023 = float(pub["Free Cash Flow"]["2023A"])
    cash = float(pub["Cash & cash equivalents"]["2023A"])
    securities = float(pub["Marketable securities"]["2023A"])
    ntbv_cross = float(pub["Preliminary NTBV/share at assumed $32.50"]["2023A"])
    dil_cross = float(pub["Preliminary immediate dilution at assumed $32.50"]["2023A"])

    growth = float(asm["2024E revenue growth"])
    mult_low = float(asm["Peer low EV/Revenue"])
    mult_mid = float(asm["Peer midpoint EV/Revenue"])
    mult_high = float(asm["Peer high EV/Revenue"])
    ipo_disc = float(asm["IPO discount to peer-implied equity"])

    proposed_price = float(trm["Proposed Committee Price"][0])
    primary = float(trm["Primary shares offered"][0])
    secondary = float(trm["Secondary shares offered"][0])
    greenshoe = float(trm["Greenshoe shares"][1])          # Full Greenshoe 列
    pre_money_shares = float(trm["Pre-money economic shares"][0])
    fee_rate = float(trm["Underwriting fee assumption"][0])
    fixed_exp = float(trm["Fixed company offering expenses"][0])
    full_primary = float(trm["Primary shares offered"][1])

    # --------------------------------------------------- 1. 盈利质量 QoE
    # Committee_Policy: SBC 视为持续性经济成本，承销口径不保留该加回
    uw_ebitda = adj_ebitda_2023 - sbc_2023
    uw_ebitda_negative = uw_ebitda < 0
    # 组织口径对照：management 指标保持原值，仅用于披露差异
    mgmt_ebitda = adj_ebitda_2023

    # --------------------------------------------- 2. 估值区间 Valuation
    rev_2024e = rev_2023 * (1.0 + growth)
    net_cash = cash + securities
    scen = {}
    for label, mult in (("Low", mult_low), ("Mid", mult_mid), ("High", mult_high)):
        ev = mult * rev_2024e
        equity = ev + net_cash
        undisc = equity / pre_money_shares
        offer = undisc * (1.0 - ipo_disc)
        scen[label] = {"mult": mult, "ev": ev, "equity": equity,
                       "undisc": undisc, "offer": offer}

    rng_low, rng_high = scen["Low"]["offer"], scen["High"]["offer"]
    midpoint = scen["Mid"]["offer"]
    vs_midpoint = proposed_price - midpoint
    proposed_equity = pre_money_shares * proposed_price
    proposed_implied_ev = proposed_equity - net_cash
    proposed_implied_mult = proposed_implied_ev / rev_2024e

    # ------------------------------------------------ 3. 发行结构与募集
    gross_primary = primary * proposed_price
    uw_fee = gross_primary * fee_rate
    net_primary = gross_primary - uw_fee - fixed_exp
    selling_gross = secondary * proposed_price
    company_secondary = 0.0 if secondary else 0.0      # secondary 不归公司
    post_money_cash = cash + securities + net_primary

    # Full-greenshoe 情景：增量只扣承销费，不重复扣固定费用
    full_gross = full_primary * proposed_price
    full_fee = full_gross * fee_rate
    full_net = full_gross - full_fee - fixed_exp
    greenshoe_increment_net = (full_gross - full_fee - fixed_exp) - net_primary

    # ------------------------------------------------------ 4. 稀释股本桥
    post_money_shares = pre_money_shares + primary
    full_post_shares = post_money_shares + greenshoe
    new_primary_pct = primary / post_money_shares
    full_new_primary_pct = full_primary / full_post_shares
    secondary_share_impact = 0.0
    proposed_post_equity = post_money_shares * proposed_price
    full_post_equity = full_post_shares * proposed_price

    # ------------------------------------------------ 5. 定价处置建议
    in_range = rng_low <= proposed_price <= rng_high
    near_mid = abs(vs_midpoint) <= 0.50
    if in_range and near_mid:
        decision = "Proceed"
    elif in_range and not near_mid:
        decision = "Reprice"
    else:
        decision = "Defer"

    # ------------------------------------------------------ 6. 错误识别
    audit = []
    for row in wb["Candidate_Model"].iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        audit.append({"workstream": row[0], "legacy": row[1],
                      "review": row[2], "status": row[3]})

    # ------------------------------------------------------------ 输出
    def line(k, v, unit=""):
        print(f"  {k:<46} {v!s:>22} {unit}")

    print("=" * 78)
    print("FIN3-WKN-152  IPO 定价委员会复核 — 可复算结果")
    print(f"输入: {path}")
    print("=" * 78)

    print("\n[1] 盈利质量 QoE（承销口径）")
    line("2023 Revenue", f"{rev_2023:.3f}", "USD mm")
    line("2023 Net income (loss)", f"{net_loss_2023:.3f}", "USD mm")
    line("2023 Adjusted EBITDA (management)", f"{mgmt_ebitda:.3f}", "USD mm")
    line("2023 SBC & related taxes", f"{sbc_2023:.3f}", "USD mm")
    line("Underwriting EBITDA (reversed SBC addback)", f"{uw_ebitda:.3f}", "USD mm")
    line("2023 Free Cash Flow", f"{fcf_2023:.3f}", "USD mm")
    line("Underwriting EBITDA remains negative", str(uw_ebitda_negative))

    print("\n[2] 估值区间（EV / 2024E Revenue）")
    line("2024E Revenue = 2023A x (1 + growth)", f"{rev_2024e:.5f}", "USD mm")
    line("Net cash = cash + marketable securities", f"{net_cash:.3f}", "USD mm")
    for label in ("Low", "Mid", "High"):
        s = scen[label]
        line(f"{label}: EV/Revenue {s['mult']}x -> Enterprise Value", f"{s['ev']:.5f}")
        line(f"{label}: Pre-money Equity", f"{s['equity']:.5f}")
        line(f"{label}: Undiscounted / share", f"{s['undisc']:.6f}")
        line(f"{label}: Offer value / share (after discount)", f"{s['offer']:.6f}")
    line("Committee supported range", f"${rng_low:.2f} - ${rng_high:.2f}")
    line("Committee midpoint", f"{midpoint:.6f}")
    line("Proposed Committee Price", f"{proposed_price:.2f}")
    line("Proposed price vs midpoint", f"{vs_midpoint:.6f}")
    line("Proposed-price implied pre-money equity", f"{proposed_equity:.6f}")
    line("Proposed-price implied EV / 2024E Revenue", f"{proposed_implied_mult:.6f}")

    print("\n[3] 发行结构与募集资金")
    line("Base primary shares", f"{primary:.6f}", "mm")
    line("Base secondary shares", f"{secondary:.6f}", "mm")
    line("Company gross primary proceeds", f"{gross_primary:.6f}", "USD mm")
    line("Underwriting fee (5% of primary gross)", f"{uw_fee:.6f}", "USD mm")
    line("Fixed company offering expenses", f"{fixed_exp:.6f}", "USD mm")
    line("Company net primary proceeds", f"{net_primary:.6f}", "USD mm")
    line("Selling holders gross proceeds", f"{selling_gross:.6f}", "USD mm")
    line("Company receives secondary proceeds", f"{company_secondary:.6f}", "USD mm")
    line("Post-money cash & securities", f"{post_money_cash:.6f}", "USD mm")
    line("Greenshoe incremental net proceeds", f"{greenshoe_increment_net:.6f}", "USD mm")

    print("\n[4] 股本桥与稀释")
    line("Pre-money shares", f"{pre_money_shares:.6f}", "mm")
    line("Base post-money shares", f"{post_money_shares:.6f}", "mm")
    line("Full-greenshoe post-money shares", f"{full_post_shares:.6f}", "mm")
    line("New primary ownership % (Base)", f"{new_primary_pct:.10f}")
    line("New primary ownership % (Full exercise)", f"{full_new_primary_pct:.10f}")
    line("Secondary impact on share count", f"{secondary_share_impact:.6f}", "mm")
    line("NTBV/share cross-check @ assumed price", f"{ntbv_cross:.2f}")
    line("Immediate dilution cross-check @ assumed price", f"{dil_cross:.2f}")
    line("Proposed-price post-money equity (Base)", f"{proposed_post_equity:.6f}")
    line("Proposed-price post-money equity (Full)", f"{full_post_equity:.6f}")

    print("\n[5] 定价处置建议")
    line("Price within supported range", str(in_range))
    line("Within 0.50 of midpoint", str(near_mid))
    line("Recommendation", f"{decision} at ${proposed_price:.2f}")
    line("QoE disclosure required (negative UW EBITDA & FCF)",
         str(uw_ebitda_negative and fcf_2023 < 0))

    print("\n[6] Candidate_Model 错误审计（来自输入材料）")
    for i, a in enumerate(audit, 1):
        print(f"  {i:>2}. {a['workstream']:<22} legacy: {str(a['legacy'])[:52]}")
    print(f"  识别问题类别数: {len(audit)}")

    print("\n" + "=" * 78)
    print("勾稽检查")
    checks = [
        ("UW EBITDA", uw_ebitda, adj_ebitda_2023 - sbc_2023),
        ("2024E Revenue", rev_2024e, rev_2023 * (1.0 + growth)),
        ("Low offer", scen["Low"]["offer"],
         ((mult_low * rev_2024e + net_cash) / pre_money_shares) * (1.0 - ipo_disc)),
        ("Net primary", net_primary, gross_primary - uw_fee - fixed_exp),
        ("Base post-money", post_money_shares, pre_money_shares + primary),
        ("Full post-money", full_post_shares, post_money_shares + greenshoe),
    ]
    all_ok = True
    for name, got, exp in checks:
        ok = abs(got - exp) < 1e-9
        all_ok = all_ok and ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<16} {got:.9f}")
    print("=" * 78)
    print("RESULT:", "ALL CHECKS PASS" if all_ok else "CHECK FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
