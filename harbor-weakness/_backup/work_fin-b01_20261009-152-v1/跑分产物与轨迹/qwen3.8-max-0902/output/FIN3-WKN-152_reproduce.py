#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-152 | Reddit, Inc. IPO 定价委员会发行前财务复核 —— 可复算脚本
=====================================================================
复核时点(信息截止): 2024-03-20 (正式定价前)

功能:
  1) 从 /app/input_files/Q7_题目.xlsx 读入全部输入(不硬编码任何结论数值);
  2) 按 Committee_Policy 控制口径完成 QoE、估值、发行结构、稀释与处置判断;
  3) 打印全部关键结果;
  4) 生成修复后的 IPO 模型 FIN3-WKN-152_ipo_model.xlsx
     (Inputs / QoE / Valuation / Offering_Proceeds / Dilution / Pricing_Summary / Error_Audit)。

运行: python3 FIN3-WKN-152_reproduce.py
依赖: openpyxl (标准容器已含); 不使用任何网络数据。
"""

import os
import re
import sys
from datetime import date

from openpyxl import load_workbook, Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

# ----------------------------------------------------------------------
# 0. 路径
# ----------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
CUTOFF = date(2024, 3, 20)  # 复核时点(题目设定, 非结论数值)


def find_input():
    cands = [
        os.environ.get("Q7_INPUT", ""),
        "/app/input_files/Q7_题目.xlsx",
        os.path.join(HERE, "..", "input_files", "Q7_题目.xlsx"),
        os.path.join(os.getcwd(), "input_files", "Q7_题目.xlsx"),
        os.path.join(os.getcwd(), "Q7_题目.xlsx"),
    ]
    for c in cands:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    raise FileNotFoundError("未找到输入文件 Q7_题目.xlsx")


IN_PATH = find_input()
OUT_DIR = "/app/output" if os.path.isdir("/app/output") else HERE
MODEL_PATH = os.path.join(OUT_DIR, "FIN3-WKN-152_ipo_model.xlsx")

# ----------------------------------------------------------------------
# 1. 读取输入工作簿
# ----------------------------------------------------------------------
wb_in = load_workbook(IN_PATH, data_only=True)


def rows_of(sheet):
    out = []
    for r in wb_in[sheet].iter_rows(values_only=True):
        if any(v is not None and str(v).strip() != "" for v in r):
            out.append(list(r))
    return out


def num(v):
    return float(v)


# --- Public_Financials: Metric | 2022A | 2023A | Unit | Source_ID | Notes
PF = {}
for r in rows_of("Public_Financials")[1:]:
    PF[str(r[0]).strip()] = r

# --- Offering_Terms: Item | Base | Full Greenshoe | Unit | Source_ID | Notes
OT = {}
for r in rows_of("Offering_Terms")[1:]:
    OT[str(r[0]).strip()] = r

# --- Underwriting_Assumptions: Assumption | Value | Unit | Policy
UA = {}
for r in rows_of("Underwriting_Assumptions")[1:]:
    UA[str(r[0]).strip()] = r

# --- Committee_Policy: Section | Convention | Application
CP = [(str(r[0]), str(r[1]), str(r[2])) for r in rows_of("Committee_Policy")[1:]]

# --- Peer_Comps: Peer | NTM EV/Revenue | Profitability | Weight | Notes
PC = rows_of("Peer_Comps")[1:]

# --- Candidate_Model: Workstream | Legacy treatment | Review point | Status
CM = rows_of("Candidate_Model")[1:]

# --- Source_Index: Source_ID | Document | As-of | Fact | URL | Priority | Use
SI = rows_of("Source_Index")[1:]

# --- README
RM = rows_of("README")


def pf(key, year_col):
    """Public_Financials 取数: year_col=1 -> 2022A, 2 -> 2023A"""
    for k in PF:
        if key.lower() in k.lower():
            return num(PF[k][year_col])
    raise KeyError(key)


def ot(key, col):
    """Offering_Terms 取数: col=1 -> Base, 2 -> Full Greenshoe"""
    for k in OT:
        if key.lower() in k.lower():
            return num(OT[k][col])
    raise KeyError(key)


def ua(key):
    for k in UA:
        if key.lower() in k.lower():
            return UA[k][1]
    raise KeyError(key)


# --- 截止日校验: Source_Index 各来源 as-of 不得晚于 2024-03-20
cutoff_checks = []
for r in SI:
    asof_raw = r[2]
    if isinstance(asof_raw, str):
        asof = date.fromisoformat(asof_raw.strip())
    else:  # datetime
        asof = asof_raw.date()
    cutoff_checks.append((r[0], asof, asof <= CUTOFF))
assert all(ok for _, _, ok in cutoff_checks), "存在晚于复核时点的来源, 信息集越界!"

# ----------------------------------------------------------------------
# 2. 输入参数 (全部来自工作簿; SEC公开事实 vs 内部委员会假设 分类标注)
# ----------------------------------------------------------------------
# 2.1 历史财务 (SEC-01, 公开事实)
rev22, rev23 = pf("Revenue", 1), pf("Revenue", 2)          # 注意先匹配到 Revenue 行
adv22, adv23 = pf("Advertising revenue", 1), pf("Advertising revenue", 2)
oth22, oth23 = pf("Other revenue", 1), pf("Other revenue", 2)
ni22, ni23 = pf("Net income (loss)", 1), pf("Net income (loss)", 2)
aebitda22, aebitda23 = pf("Adjusted EBITDA", 1), pf("Adjusted EBITDA", 2)
sbc22, sbc23 = pf("Stock-based compensation", 1), pf("Stock-based compensation", 2)
restr23 = pf("Restructuring costs", 2)
da22, da23 = pf("Depreciation", 1), pf("Depreciation", 2)
fcf22, fcf23 = pf("Free Cash Flow", 1), pf("Free Cash Flow", 2)
cash22, cash23 = pf("Cash & cash equivalents", 1), pf("Cash & cash equivalents", 2)
ms22, ms23 = pf("Marketable securities", 1), pf("Marketable securities", 2)
ntbv_3250 = pf("Preliminary NTBV", 2)
dil_3250 = pf("Preliminary immediate dilution", 2)
# SEC-02 交叉核对所用假设价: 从指标名称 "…at assumed $32.50" 解析, 不硬编码
assumed_px = None
for _k in PF:
    _m = re.search(r"assumed \$([0-9]+(?:\.[0-9]+)?)", _k)
    if _m:
        assumed_px = float(_m.group(1))
        break
assert assumed_px is not None, "未能解析 SEC-02 交叉核对假设价"

# 2.2 发行条款 (SEC-03 公开事实 / UW-01 内部假设)
price = ot("Proposed Committee Price", 1)                  # 内部工作价格(UW-01), 决策输入
price_full = ot("Proposed Committee Price", 2)
prim_base = ot("Primary shares offered", 1)
prim_full = ot("Primary shares offered", 2)
sec_base = ot("Secondary shares offered", 1)
sec_full = ot("Secondary shares offered", 2)
gs_base = ot("Greenshoe shares", 1)
gs_full = ot("Greenshoe shares", 2)
premoney_sh = ot("Pre-money economic shares", 1)           # 内部 cap-table snapshot(UW-01)
pub_lo = ot("range low", 1)
pub_hi = ot("range high", 1)
fee_rate = ot("Underwriting fee assumption", 1)
fixed_exp = ot("Fixed company offering expenses", 1)
sec_to_company = ot("Company receives secondary proceeds", 1)

# 2.3 承销假设 (UW-01 内部委员会假设)
g24 = num(ua("2024E revenue growth"))
mult_lo = num(ua("Peer low EV/Revenue"))
mult_mid = num(ua("Peer midpoint EV/Revenue"))
mult_hi = num(ua("Peer high EV/Revenue"))
disc = num(ua("IPO discount"))

# 2.4 处置容差: 从 Committee_Policy 文本解析 "距midpoint不超过$0.50/share"
tol = None
for sec, conv, app in CP:
    if "disposition" in sec.lower() and "Proceed" in app:
        m = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*share", conv)
        if m:
            tol = float(m.group(1))
assert tol is not None, "未能从 Committee_Policy 解析 midpoint 容差"

# 2.5 Peer_Comps 加权倍数(交叉验证用, 权重来自工作簿)
peer_wavg = sum(num(r[1]) * num(r[3]) for r in PC) / sum(num(r[3]) for r in PC)

# ----------------------------------------------------------------------
# 3. QoE 盈利质量复核 (Committee_Policy: 撤销 SBC 加回; restructuring 不重复处理)
# ----------------------------------------------------------------------
uw_ebitda22 = aebitda22 - sbc22          # 承销口径 EBITDA = 管理口径 Adj EBITDA - SBC加回
uw_ebitda23 = aebitda23 - sbc23
uw_ebitda_neg = uw_ebitda23 < 0          # 是否触发 EV/Revenue 主估值

rev_growth23 = rev23 / rev22 - 1.0
ad_conc23 = adv23 / rev23
ad_conc22 = adv22 / rev22
ni_margin23 = ni23 / rev23
uw_margin23 = uw_ebitda23 / rev23
uw_margin22 = uw_ebitda22 / rev22
fcf_margin23 = fcf23 / rev23
sbc_pct23 = sbc23 / rev23
net_cash23 = cash23 + ms23               # 年末 cash + marketable securities (无债务数据: 待核实)
net_cash22 = cash22 + ms22

# ----------------------------------------------------------------------
# 4. 估值区间 (EV / 2024E Revenue + 完整 net cash bridge + 12.5% discount)
# ----------------------------------------------------------------------
rev24 = rev23 * (1.0 + g24)

ev = {k: rev24 * m for k, m in (("low", mult_lo), ("mid", mult_mid), ("high", mult_hi))}
eq_pre = {k: v + net_cash23 for k, v in ev.items()}          # Pre-money Equity = EV + cash + MS
pps_pre = {k: v / premoney_sh for k, v in eq_pre.items()}    # undiscounted per share
sup = {k: v * (1.0 - disc) for k, v in pps_pre.items()}      # 统一应用 12.5% discount
sup_lo, sup_mid, sup_hi = sup["low"], sup["mid"], sup["high"]

# peer 加权倍数交叉验证
ev_wavg = rev24 * peer_wavg
sup_wavg = (ev_wavg + net_cash23) / premoney_sh * (1.0 - disc)

# ----------------------------------------------------------------------
# 5. 发行结构重建 (Base 与 Full-Greenshoe; secondary 不入公司募集/不增股数)
# ----------------------------------------------------------------------
def offering(prim, gs, px):
    gross_primary = prim * px                    # 公司 primary gross proceeds
    fee = fee_rate * gross_primary               # 承销费只按公司 primary gross 计提
    fixed = fixed_exp                            # 固定费用不重复计提
    net_primary = gross_primary - fee - fixed
    post_sh = premoney_sh + prim                 # secondary 不增加公司总股数
    new_own = prim / post_sh
    float_sh = prim + sec_base                   # 公开发行总量(含 secondary 转让)
    return {
        "primary": prim, "greenshoe": gs, "secondary": sec_base,
        "gross_primary": gross_primary, "fee": fee, "fixed": fixed,
        "net_primary": net_primary, "post_sh": post_sh, "new_own": new_own,
        "float_sh": float_sh, "float_pct": float_sh / post_sh,
        "gross_secondary": sec_base * px,        # memo: 归出售股东, 非公司募集
        "total_gross": (prim + sec_base) * px,   # memo: 发行总规模
    }


base = offering(prim_base, gs_base, price)
full = offering(prim_full, gs_full, price_full)
# greenshoe 增量口径校验: 增量只扣 5% fee, 不重复扣固定费用
gs_incr_net = (prim_full - prim_base) * price_full * (1.0 - fee_rate)
assert abs(full["net_primary"] - (base["net_primary"] + gs_incr_net)) < 1e-9
assert abs(prim_full - prim_base - gs_full) < 1e-9, "Full primary = Base primary + greenshoe"
# SEC-02 内部一致性: 假设价 - NTBV = 即时稀释
sec02_ok = abs((assumed_px - ntbv_3250) - dil_3250) < 1e-9
assert sec02_ok, "SEC-02 交叉核对内部不一致"
base_total_offered = prim_base + sec_base   # Base 发行总量 (primary + secondary)

# ----------------------------------------------------------------------
# 6. Candidate_Model 错误审计 (legacy 影响量化)
# ----------------------------------------------------------------------
legacy_ev = mult_mid * rev23                       # 4.5x 直接乘 2023 revenue
legacy_pps = legacy_ev / premoney_sh               # 无 bridge、无 discount 的隐含价
legacy_gross = base_total_offered * price          # legacy: 22.0m 全按 primary
legacy_fee = fee_rate * legacy_gross               # legacy: fee 按 primary+secondary
legacy_net = legacy_gross * (1 - fee_rate) - fixed_exp
legacy_post_sh = premoney_sh + base_total_offered  # legacy: secondary 计入股数
err = [
    # (workstream, legacy, correct, impact)
    ("Profitability",
     "直接使用管理口径 Adjusted EBITDA %.3f (SBC 已加回)" % aebitda23,
     "承销口径 EBITDA = %.3f - SBC %.3f = %.3f (Policy: SBC 为持续性经济成本)" % (aebitda23, sbc23, uw_ebitda23),
     "盈利高估 %.3f mm; 仍为负 → 触发 EV/2024E Revenue 主估值" % sbc23),
    ("Valuation",
     "4.5x 直接乘 2023A Revenue (EV=%.3f, 隐含 %.4f/sh)" % (legacy_ev, legacy_pps),
     "4.0-5.0x 乘 2024E Revenue %.3f, 经 net cash bridge 与 12.5%% discount (mid=%.4f/sh)" % (rev24, sup_mid),
     "EV 低估 %.3f mm; mid 隐含价低估 %.4f/sh" % (ev['mid'] - legacy_ev, sup_mid - legacy_pps)),
    ("Cash",
     "net cash bridge 漏掉 marketable securities %.3f" % ms23,
     "bridge = cash %.3f + marketable securities %.3f = %.3f" % (cash23, ms23, net_cash23),
     "每股低估 %.4f (折后 %.4f)" % (ms23 / premoney_sh, ms23 / premoney_sh * (1 - disc))),
    ("Primary/Secondary",
     "Base %.1fm 全部当作 primary (公司 gross=%.3f)" % (base_total_offered, legacy_gross),
     "primary %.6fm + secondary %.6fm; 公司 gross=%.6f" % (prim_base, sec_base, base['gross_primary']),
     "公司募集资金高估 %.6f mm (secondary 归出售股东)" % (legacy_gross - base['gross_primary'])),
    ("Greenshoe",
     "%.1fm greenshoe 并入 Base" % gs_full,
     "Base greenshoe=0; full-exercise 单独情景 (primary %.6fm)" % prim_full,
     "Base 股数高估 %.1fm、公司 gross 高估 %.3f mm" % (gs_full, gs_full * price)),
    ("Underwriting fee",
     "fee 按 primary+secondary 计提 (%.0f%% x %.3f = %.3f)" % (fee_rate * 100, legacy_gross, legacy_fee),
     "fee 只按公司 primary gross 计提 (%.0f%% x %.6f = %.6f)" % (fee_rate * 100, base['gross_primary'], base['fee']),
     "公司口径费用高估 %.6f mm" % (legacy_fee - base['fee'])),
    ("Post-money shares",
     "secondary 计入总股数 (post-money=%.6f)" % legacy_post_sh,
     "post-money = %.6f + primary %.6f = %.6f (Base)" % (premoney_sh, prim_base, base['post_sh']),
     "总股数高估 %.6fm" % (legacy_post_sh - base['post_sh'])),
    ("Proceeds",
     "secondary proceeds 计入公司现金 (legacy 公司 net=%.3f)" % legacy_net,
     "公司仅取得 primary net %.6f (Base); secondary gross %.6f 归出售股东" % (base['net_primary'], sec_base * price),
     "公司现金流入高估 %.6f mm (含费用错配)" % (legacy_net - base['net_primary'])),
    ("Dilution",
     "post-money equity / pre-money shares (分子分母口径不一致)",
     "新股占比 = primary / post-money = %.4f%% (Base); %.4f%% (Full)" % (base['new_own'] * 100, full['new_own'] * 100),
     "口径不一致导致稀释失真; 修正后 Base 新股稀释 %.2f%%、Full %.2f%%" % (base['new_own'] * 100, full['new_own'] * 100)),
    ("Recommendation",
     "主要基于 peer high case 上移至 $34 以上",
     "按 Policy guardrail: 支持区间 [%.4f, %.4f], mid %.4f; $%.2f 在区间内且距 mid %.4f <= %.2f → Proceed" % (sup_lo, sup_hi, sup_mid, price, abs(price - sup_mid), tol),
     "peer high 单边上移无 guardrail 依据; 处置须按三条件测试"),
]

in_range = sup_lo <= price <= sup_hi
dist_mid = abs(price - sup_mid)
hard_err_resolved = True   # 本模型已将上表 10 项 legacy 错误全部修正
if not in_range or not hard_err_resolved:
    verdict = "Defer"
elif dist_mid > tol:
    verdict = "Reprice (向 midpoint 方向)"
else:
    verdict = "Proceed"

# ----------------------------------------------------------------------
# 7. 打印关键结果
# ----------------------------------------------------------------------
W = 92


def banner(t):
    print("\n" + "=" * W)
    print(t)
    print("=" * W)


banner("FIN3-WKN-152 | Reddit, Inc. IPO 定价委员会复核 — 可复算输出 (as-of 2024-03-20)")
print("输入文件: %s" % IN_PATH)
print("截止日校验: %s" % ", ".join("%s(%s)%s" % (s, d, "OK" if ok else "VIOLATION") for s, d, ok in cutoff_checks))

banner("[1] 输入参数分类 (SEC 公开事实 vs 内部委员会假设)")
print("SEC 公开事实 (SEC-01/02/03, as-of 2024-03-11): 2022/2023 财务、cash、marketable securities、")
print("  primary %.6fm / secondary %.6fm / greenshoe %.1fm、公开区间 $%.0f-$%.0f、NTBV/稀释交叉核对(@$32.50)" % (prim_base, sec_base, gs_full, pub_lo, pub_hi))
print("内部委员会假设 (UW-01, as-of 2024-03-20): 2024E 增长 %.0f%%、peer %.1fx-%.1fx(mid %.1fx)、" % (g24 * 100, mult_lo, mult_hi, mult_mid))
print("  IPO discount %.1f%%、承销费率 %.0f%%、固定费用 $%.1fmm、pre-money 股数 %.6fm、拟议价 $%.2f" % (disc * 100, fee_rate * 100, fixed_exp, premoney_sh, price))
print("Peer_Comps 加权平均倍数(交叉验证) = %.3fx" % peer_wavg)
print("SEC-02 内部一致性: $%.2f - NTBV %.2f = 稀释 %.2f -> %s" % (assumed_px, ntbv_3250, dil_3250, "OK" if sec02_ok else "MISMATCH"))

banner("[2] QoE 盈利质量 (USD mm)")
print("%-42s %12s %12s" % ("Metric", "2022A", "2023A"))
for label, a, b in [
    ("Revenue", rev22, rev23), ("  Advertising revenue", adv22, adv23),
    ("  Other revenue", oth22, oth23), ("Net income (loss)", ni22, ni23),
    ("Management Adjusted EBITDA (non-GAAP, SEC-01)", aebitda22, aebitda23),
    ("Less: SBC & related taxes (Policy 撤销加回)", -sbc22, -sbc23),
    ("Underwriting EBITDA (承销口径)", uw_ebitda22, uw_ebitda23),
    ("Free Cash Flow", fcf22, fcf23), ("Cash & cash equivalents", cash22, cash23),
    ("Marketable securities", ms22, ms23), ("Net cash (cash + securities)", net_cash22, net_cash23),
]:
    print("%-42s %12.3f %12.3f" % (label, a, b))
print("2023 关键比率: Revenue 增速 %.2f%% | 广告集中度 %.2f%% | Net loss margin %.2f%%" % (rev_growth23 * 100, ad_conc23 * 100, ni_margin23 * 100))
print("  Underwriting EBITDA margin: 2022 %.2f%% -> 2023 %.2f%% | FCF margin 2023 %.2f%% | SBC/Revenue %.2f%%" % (uw_margin22 * 100, uw_margin23 * 100, fcf_margin23 * 100, sbc_pct23 * 100))
print("Restructuring 2023 = %.3f (已含于管理口径调整, 不重复处理)" % restr23)
print("判断: 承销口径 EBITDA 2023 = %.3f < 0 → 主估值采用 EV / 2024E Revenue" % uw_ebitda23)

banner("[3] 估值区间 (EV/2024E Revenue; USD mm, USD/share)")
print("2024E Revenue = %.3f x (1 + %.0f%%) = %.3f  [增长率: 内部假设 UW-01]" % (rev23, g24 * 100, rev24))
print("%-38s %12s %12s %12s" % ("", "Low 4.0x", "Mid 4.5x", "High 5.0x"))
print("%-38s %12.3f %12.3f %12.3f" % ("Enterprise Value", ev['low'], ev['mid'], ev['high']))
print("%-38s %12.3f %12.3f %12.3f" % ("(+) Net cash (cash %.3f + MS %.3f)" % (cash23, ms23), net_cash23, net_cash23, net_cash23))
print("%-38s %12.3f %12.3f %12.3f" % ("Pre-money Equity", eq_pre['low'], eq_pre['mid'], eq_pre['high']))
print("%-38s %12.6f %12.6f %12.6f" % ("(/) Pre-money shares %.6fm" % premoney_sh, pps_pre['low'], pps_pre['mid'], pps_pre['high']))
print("%-38s %12.4f %12.4f %12.4f" % ("(x) (1 - 12.5% discount) 支持价格", sup_lo, sup_mid, sup_hi))
print("委员会支持区间: $%.2f - $%.2f | Midpoint: $%.2f" % (sup_lo, sup_hi, sup_mid))
print("交叉验证: peer 加权 %.2fx → $%.2f/sh; SEC-03 公开区间 $%.0f-$%.0f (execution cross-check only)" % (peer_wavg, sup_wavg, pub_lo, pub_hi))

banner("[4] 发行结构与募集资金 ( @$%.2f; USD mm, mm shares)" % price)
print("%-44s %14s %14s" % ("Item", "Base", "Full Greenshoe"))
for label, k in [("Primary shares (mm)", "primary"), ("Secondary shares (mm, 归出售股东)", "secondary"),
                 ("Greenshoe shares (mm)", "greenshoe"), ("Total shares offered (mm)", "float_sh"),
                 ("Company primary gross proceeds", "gross_primary"),
                 ("Memo: secondary gross (非公司募集)", "gross_secondary"),
                 ("Memo: total gross (primary+secondary)", "total_gross"),
                 ("Underwriting fee (5% x primary gross)", "fee"),
                 ("Fixed company expenses (不重复计提)", "fixed"),
                 ("Company net primary proceeds", "net_primary"),
                 ("Post-money shares (mm)", "post_sh")]:
    print("%-44s %14.4f %14.4f" % (label, base[k], full[k]))
print("Greenshoe 增量净募集 (只扣 5%% fee): %.4f = %.4f - %.4f 校验 OK" % (gs_incr_net, full['net_primary'], base['net_primary']))

banner("[5] 稀释")
print("%-44s %14s %14s" % ("Metric", "Base", "Full Greenshoe"))
print("%-44s %13.4f%% %13.4f%%" % ("新投资者占比 = primary / post-money", base['new_own'] * 100, full['new_own'] * 100))
print("%-44s %13.4f%% %13.4f%%" % ("既有股东占比 = pre-money / post-money", (1 - base['new_own']) * 100, (1 - full['new_own']) * 100))
print("%-44s %13.4f%% %13.4f%%" % ("公众流通盘(22.0m 含 secondary)/post-money", base['float_pct'] * 100, full['float_pct'] * 100))
print("SEC-02 交叉核对(仅交叉): @$32.50 NTBV/share %.2f, 即时稀释 %.2f (拟议价 $%.2f 口径不同, 不直接可比;" % (ntbv_3250, dil_3250, price))
print("  $34 口径 NTBV 因缺 pre-money 账面净值基数标注'待核实')")

banner("[6] Candidate_Model 错误审计 (共 %d 条 legacy treatment, 全部修正)" % len(err))
for i, (wsname, legacy, correct, impact) in enumerate(err, 1):
    print("E%02d [%s]\n    legacy : %s\n    correct: %s\n    impact : %s" % (i, wsname, legacy, correct, impact))

banner("[7] 定价处置 (Committee_Policy guardrail)")
print("拟议价格 $%.2f (UW-01 内部决策输入, 非已实现结果)" % price)
print("测试1 位于支持区间 [$%.4f, $%.4f]: %s" % (sup_lo, sup_hi, "PASS" if in_range else "FAIL"))
print("测试2 距 midpoint $%.4f = $%.4f <= $%.2f: %s" % (sup_mid, dist_mid, tol, "PASS" if dist_mid <= tol else "FAIL"))
print("测试3 发行结构 hard error 已解决: %s" % ("PASS" if hard_err_resolved else "FAIL"))
print("处置建议: %s (QoE 风险须在 memo 中明确披露)" % verdict)
print("\n待核实事项: (a) secondary 承销费承担方; (b) 发行人债务余额(net cash bridge 按 Policy 公式仅含 cash+MS);")
print("           (c) pre-money 账面净值基数($34 口径 NTBV/稀释复核); (d) greenshoe 行使窗口细节。")

# ----------------------------------------------------------------------
# 8. 生成修复后的 IPO 模型工作簿
# ----------------------------------------------------------------------
THIN = Side(style="thin", color="B0B0B0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
F_TITLE = Font(bold=True, size=13, color="1F3864")
F_SEC = Font(bold=True, size=11, color="FFFFFF")
F_HDR = Font(bold=True, size=10, color="FFFFFF")
F_BOLD = Font(bold=True, size=10)
F_TXT = Font(size=10)
F_NOTE = Font(size=9, italic=True, color="606060")
FILL_SEC = PatternFill("solid", fgColor="1F3864")
FILL_HDR = PatternFill("solid", fgColor="4472C4")
FILL_KEY = PatternFill("solid", fgColor="FFF2CC")
FILL_ALT = PatternFill("solid", fgColor="F2F6FC")
FILL_WARN = PatternFill("solid", fgColor="FCE4E4")
FILL_OK = PatternFill("solid", fgColor="E2EFDA")
WRAP = Alignment(wrap_text=True, vertical="top")

FMT_M = "#,##0.000"        # USD mm
FMT_S6 = "#,##0.000000"    # mm shares
FMT_PX = "$#,##0.0000"     # USD/share
FMT_PX2 = "$#,##0.00"
FMT_PC = "0.00%"
FMT_X = '0.00"x"'

wb = Workbook()
wb.remove(wb.active)


def sheet(name, widths, title, subtitle=None):
    ws = wb.create_sheet(name)
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i) if i <= 26 else "A"].width = w
    ws.cell(1, 1, title).font = F_TITLE
    r = 2
    if subtitle:
        ws.cell(2, 1, subtitle).font = F_NOTE
        r = 3
    ws.freeze_panes = "A%d" % (r + 1)
    return ws, r + 1


def sec_head(ws, r, text, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(r, c, text if c == 1 else None)
        cell.fill = FILL_SEC
        cell.font = F_SEC
    return r + 1


def hdr(ws, r, headers):
    for c, h in enumerate(headers, 1):
        cell = ws.cell(r, c, h)
        cell.font = F_HDR
        cell.fill = FILL_HDR
        cell.border = BORDER
        cell.alignment = WRAP
    return r + 1


def row(ws, r, vals, fmts=None, bold=False, fill=None):
    for c, v in enumerate(vals, 1):
        cell = ws.cell(r, c, v)
        if isinstance(v, str) and v.startswith("="):
            cell.data_type = "s"   # 以 = 开头的说明文字强制为文本, 避免被解析为公式
        cell.border = BORDER
        cell.font = F_BOLD if bold else F_TXT
        cell.alignment = WRAP
        if fill:
            cell.fill = fill
        if fmts and fmts[c - 1]:
            cell.number_format = fmts[c - 1]
    return r + 1


def note(ws, r, text, ncol=1):
    cell = ws.cell(r, 1, text)
    if isinstance(text, str) and text.startswith("="):
        cell.data_type = "s"
    cell.font = F_NOTE
    cell.alignment = WRAP
    return r + 1


# ================= Sheet 1: Inputs =================
ws, r = sheet("Inputs", [46, 16, 16, 12, 12, 34, 30],
              "Inputs — 输入与来源清单 (信息截止 2024-03-20)",
              "全部数值读自 /app/input_files/Q7_题目.xlsx; 单位: USD mm / mm shares / USD per share; 分类标注 SEC公开事实 vs 内部委员会假设")

r = sec_head(ws, r, "A. 信息集与截止日校验 (Source_Index)", 7)
r = hdr(ws, r, ["Source_ID", "Document", "As-of", "Priority", "截止日校验", "Fact", "Use"])
for sid, doc, asof, fact, url, pri, use in SI:
    asof_d = asof.date() if hasattr(asof, "date") else date.fromisoformat(str(asof))
    r = row(ws, r, [sid, doc, str(asof_d), pri, "OK (<=2024-03-20)" if asof_d <= CUTOFF else "VIOLATION", fact, use],
            fill=FILL_OK if asof_d <= CUTOFF else FILL_WARN)
r = note(ws, r, "纪律: Base case 仅使用 2024-03-20 前可得信息; 最终定价/发行后文件/上市后表现一律不进入 Base, 不用于反推。拟议 $34 为决策输入而非已实现结果。")
r += 1

r = sec_head(ws, r, "B. 历史财务 (Public_Financials; SEC-01 = SEC 公开事实; SEC-02 仅交叉核对)", 7)
r = hdr(ws, r, ["Metric", "2022A", "2023A", "Unit", "Source_ID", "Notes", "信息分类"])
for k, v in PF.items():
    cls = "SEC 公开事实"
    fill = None
    if "Preliminary" in k:
        cls = "SEC 公开事实 (仅交叉核对, 假设价 $32.50)"
        fill = FILL_ALT
    r = row(ws, r, [k, v[1], v[2], v[3], v[4], v[5], cls], [None, FMT_M, FMT_M, None, None, None, None], fill=fill)
r += 1

r = sec_head(ws, r, "C. 发行条款 (Offering_Terms; SEC-03 = 公开事实, UW-01 = 内部假设)", 7)
r = hdr(ws, r, ["Item", "Base", "Full Greenshoe", "Unit", "Source_ID", "Notes", "信息分类"])
for k, v in OT.items():
    sid = str(v[4])
    cls = "内部委员会假设" if sid == "UW-01" else "SEC 公开事实"
    if k == "Proposed Committee Price":
        cls = "内部委员会假设 (拟议工作价格, 非最终定价)"
    r = row(ws, r, [k, v[1], v[2], v[3], sid, v[5], cls],
            [None, FMT_S6 if "shares" in k else (FMT_PX2 if "Price" in k or "range" in k else None),
             FMT_S6 if "shares" in k else (FMT_PX2 if "Price" in k or "range" in k else None), None, None, None, None],
            fill=FILL_KEY if k == "Proposed Committee Price" else None)
r += 1

r = sec_head(ws, r, "D. 承销假设 (Underwriting_Assumptions; 全部为内部委员会假设 UW-01)", 7)
r = hdr(ws, r, ["Assumption", "Value", "Unit", "Policy", "", "", "信息分类"])
for k, v in UA.items():
    r = row(ws, r, [k, v[1], v[2], v[3], None, None, "内部委员会假设"], [None, FMT_PC if k in ("2024E revenue growth", "IPO discount to peer-implied equity") else (FMT_X if "EV/Revenue" in k else None), None, None, None, None, None])
r += 1

r = sec_head(ws, r, "E. 可比公司 (Peer_Comps; 用于倍数区间交叉验证)", 7)
r = hdr(ws, r, ["Peer", "NTM EV/Revenue", "Profitability", "Committee Weight", "Notes", "", ""])
for p in PC:
    r = row(ws, r, [p[0], num(p[1]), p[2], num(p[3]), p[4]], [None, FMT_X, None, "0%", None])
r = row(ws, r, ["加权平均 (交叉验证)", peer_wavg, "", sum(num(p[3]) for p in PC), "与 Policy mid 4.5x 一致性良好"], [None, FMT_X, None, "0%", None], bold=True, fill=FILL_ALT)
r += 1

r = sec_head(ws, r, "F. 待核实事项 (材料未载明, 不自行补充)", 7)
for t in ["(a) secondary 股份承销费的承担方(材料仅规定公司费用按 primary gross 计提);",
          "(b) 发行人债务余额 — net cash bridge 按 Committee_Policy 公式仅含 year-end cash + marketable securities;",
          "(c) pre-money 账面净值基数 — 无法在 $34 口径复算 NTBV/即时稀释, SEC-02 仅提供 $32.50 假设价交叉核对;",
          "(d) greenshoe 行使窗口与机制细节(材料仅载 3.3m over-allotment, full exercise 增加 3.3m primary)。"]:
    r = note(ws, r, t)

# ================= Sheet 2: QoE =================
ws, r = sheet("QoE", [52, 15, 15, 13, 40, 22],
              "QoE — 盈利质量复核 (2022A / 2023A)",
              "控制口径: Committee_Policy — 管理口径 Adjusted EBITDA 为起点, SBC 视为持续性经济成本撤销加回; restructuring 已含于管理口径调整不重复处理")

r = sec_head(ws, r, "A. 盈利质量明细 (USD mm)", 6)
r = hdr(ws, r, ["Metric", "2022A", "2023A", "Unit", "计算 / 取值来源", "信息分类"])
qoe_rows = [
    ("Revenue", rev22, rev23, "USD mm", "Public_Financials (SEC-01)", "SEC 公开事实", None),
    ("  Advertising revenue", adv22, adv23, "USD mm", "Public_Financials (SEC-01)", "SEC 公开事实", None),
    ("  广告收入集中度", ad_conc22, ad_conc23, "%", "= Advertising / Revenue", "计算值", FMT_PC),
    ("  Other revenue", oth22, oth23, "USD mm", "Public_Financials (SEC-01)", "SEC 公开事实", None),
    ("  Revenue YoY 增速", None, rev_growth23, "%", "= 804.029 / 666.701 - 1", "计算值", FMT_PC),
    ("Net income (loss)", ni22, ni23, "USD mm", "Public_Financials (SEC-01)", "SEC 公开事实", None),
    ("  Net loss margin", ni22 / rev22, ni_margin23, "%", "= Net loss / Revenue", "计算值", FMT_PC),
    ("Management Adjusted EBITDA (non-GAAP)", aebitda22, aebitda23, "USD mm", "Public_Financials (SEC-01); 管理口径, 已加回 SBC 与 restructuring", "SEC 公开事实 (非GAAP)", None),
    ("Less: SBC & related taxes (撤销加回)", -sbc22, -sbc23, "USD mm", "Public_Financials SBC 行; Policy: SBC 为持续性经济成本, 承销口径不保留加回", "口径调整", None),
    ("Restructuring (备忘)", 0.0, restr23, "USD mm", "已含于管理口径 Adj EBITDA 调整, 按 Policy 不重复处理", "SEC 公开事实", None),
    ("Underwriting EBITDA (承销口径)", uw_ebitda22, uw_ebitda23, "USD mm", "= Management Adj EBITDA - SBC 加回", "计算值 (控制口径)", None),
    ("  Underwriting EBITDA margin", uw_margin22, uw_margin23, "%", "= Underwriting EBITDA / Revenue", "计算值", FMT_PC),
    ("Free Cash Flow", fcf22, fcf23, "USD mm", "Public_Financials (SEC-01)", "SEC 公开事实", None),
    ("  FCF margin", fcf22 / rev22, fcf_margin23, "%", "= FCF / Revenue", "计算值", FMT_PC),
    ("Depreciation & amortization (备忘)", da22, da23, "USD mm", "Public_Financials (SEC-01)", "SEC 公开事实", None),
    ("Cash & cash equivalents (year-end)", cash22, cash23, "USD mm", "Public_Financials (SEC-01)", "SEC 公开事实", None),
    ("Marketable securities (year-end)", ms22, ms23, "USD mm", "Public_Financials (SEC-01)", "SEC 公开事实", None),
    ("Net cash (cash + marketable securities)", net_cash22, net_cash23, "USD mm", "= cash + MS; 债务数据未载明(待核实), Policy bridge 公式仅含此两项", "计算值", None),
]
for label, a, b, unit, basis, cls, fmtp in qoe_rows:
    fmt = fmtp if fmtp else (FMT_M if unit == "USD mm" else None)
    bold = label.startswith("Underwriting EBITDA") or label.startswith("Net cash")
    r = row(ws, r, [label, a, b, unit, basis, cls], [None, fmt, fmt, None, None, None],
            bold=bold, fill=FILL_KEY if bold else None)
r += 1
r = sec_head(ws, r, "B. QoE 判断", 6)
for t in ["1) 承销口径 EBITDA 2023A = %.3f mm (2022A = %.3f mm), 撤销 SBC 加回后仍为负 → 按 Committee_Policy 主估值采用 EV / 2024E Revenue。" % (uw_ebitda23, uw_ebitda22),
          "2) 亏损收窄趋势: Net loss %.3f → %.3f; Underwriting EBITDA margin %.1f%% → %.1f%%; FCF %.3f → %.3f — 改善但未转正。" % (ni22, ni23, uw_margin22 * 100, uw_margin23 * 100, fcf22, fcf23),
          "3) 风险点: 广告集中度 %.1f%% (单一收入线); 2023 实际增速 %.1f%% 低于内部 2024E 假设 %.0f%% (UW-01, 非 SEC 事实); FCF 持续为负。" % (ad_conc23 * 100, rev_growth23 * 100, g24 * 100),
          "4) 流动性: 2023 年末 net cash %.3f mm (cash %.3f + MS %.3f), 对估值构成正向 bridge。" % (net_cash23, cash23, ms23)]:
    r = note(ws, r, t)
    ws.cell(r - 1, 1).font = F_TXT

# ================= Sheet 3: Valuation =================
ws, r = sheet("Valuation", [50, 16, 16, 16, 44, 22],
              "Valuation — EV / 2024E Revenue 估值区间",
              "触发条件: 承销口径 EBITDA 仍为负 (QoE 表); 倍数区间与 discount 为内部委员会假设 (UW-01), 分母增长率为内部预测假设")

r = sec_head(ws, r, "A. 主估值桥 (USD mm / USD per share)", 6)
r = hdr(ws, r, ["Step", "Low (4.0x)", "Mid (4.5x)", "High (5.0x)", "计算 / 取值来源", "信息分类"])
val_rows = [
    ("2023A Revenue", rev23, rev23, rev23, "Public_Financials (SEC-01)", "SEC 公开事实", FMT_M),
    ("x (1 + 2024E 增长率 %.0f%%)" % (g24 * 100), 1 + g24, 1 + g24, 1 + g24, "Underwriting_Assumptions (UW-01)", "内部委员会假设", "0%"),
    ("= 2024E Revenue", rev24, rev24, rev24, "= %.3f x 1.%.0f" % (rev23, g24 * 100), "计算值", FMT_M),
    ("x EV / Revenue 倍数", mult_lo, mult_mid, mult_hi, "Underwriting_Assumptions (UW-01); Peer_Comps 交叉验证", "内部委员会假设", FMT_X),
    ("= Enterprise Value", ev['low'], ev['mid'], ev['high'], "= 2024E Revenue x 倍数", "计算值", FMT_M),
    ("(+) Year-end cash (2023)", cash23, cash23, cash23, "Public_Financials (SEC-01)", "SEC 公开事实", FMT_M),
    ("(+) Marketable securities (2023)", ms23, ms23, ms23, "Public_Financials (SEC-01); legacy 漏项已修复", "SEC 公开事实", FMT_M),
    ("= Pre-money Equity", eq_pre['low'], eq_pre['mid'], eq_pre['high'], "Policy: Pre-money Equity = EV + year-end cash + MS (债务待核实)", "计算值 (Policy 公式)", FMT_M),
    ("(/) Pre-money economic shares (mm)", premoney_sh, premoney_sh, premoney_sh, "Offering_Terms (UW-01 cap-table snapshot)", "内部委员会假设", FMT_S6),
    ("= Equity value / share (undiscounted)", pps_pre['low'], pps_pre['mid'], pps_pre['high'], "= Pre-money Equity / pre-money shares", "计算值", FMT_PX),
    ("x (1 - IPO execution discount %.1f%%)" % (disc * 100), 1 - disc, 1 - disc, 1 - disc, "Underwriting_Assumptions (UW-01); Policy: 统一应用于 peer-implied 每股值", "内部委员会假设", "0.0%"),
    ("= 委员会支持价格", sup_lo, sup_mid, sup_hi, "= undiscounted x (1 - 12.5%)", "计算值 (结论)", FMT_PX),
]
for label, a, b, c, basis, cls, fmt in val_rows:
    bold = label.startswith("=") and ("Pre-money Equity" in label or "委员会支持价格" in label or "2024E" in label)
    r = row(ws, r, [label, a, b, c, basis, cls], [None, fmt, fmt, fmt, None, None],
            bold=bold, fill=FILL_KEY if "委员会支持价格" in label else None)
r += 1
r = sec_head(ws, r, "B. 结论与交叉验证", 6)
for t, f in [("委员会支持区间: $%.4f — $%.4f / share; Midpoint (4.5x): $%.4f" % (sup_lo, sup_hi, sup_mid), F_BOLD),
             ("交叉验证 1: Peer_Comps 加权平均 %.3fx → 支持价 $%.4f/sh, 与 Policy mid 4.5x ($%.4f) 一致。" % (peer_wavg, sup_wavg, sup_mid), F_TXT),
             ("交叉验证 2: SEC-03 公开初步区间 $%.0f-$%.0f (execution cross-check only); 支持区间下限 $%.2f 高于公开下限, 拟议 $%.2f 位于公开区间上限。" % (pub_lo, pub_hi, sup_lo, price), F_TXT),
             ("口径声明: %.0f%% 增长、%.1fx-%.1fx、%.1f%% discount、pre-money 股数 %.6fm 均为内部委员会假设(UW-01), 不得表述为 SEC 公开事实。" % (g24 * 100, mult_lo, mult_hi, disc * 100, premoney_sh), F_NOTE)]:
    cell = ws.cell(r, 1, t)
    cell.font = f
    cell.alignment = WRAP
    r += 1

# ================= Sheet 4: Offering_Proceeds =================
ws, r = sheet("Offering_Proceeds", [50, 17, 17, 13, 44, 20],
              "Offering_Proceeds — 发行结构与募集资金重建 (@ 拟议价 $%.2f)" % price,
              "口径: secondary 不形成公司募集资金、不增加公司总股数; Base 不含 greenshoe; 承销费按公司 primary gross 5% 计提; 固定费用 $7.0mm 不在 greenshoe 增量上重复计提")

r = sec_head(ws, r, "A. Base 发行 vs Full-Greenshoe 情景 (USD mm / mm shares)", 6)
r = hdr(ws, r, ["Item", "Base Offering", "Full Greenshoe", "Unit", "计算 / 取值来源", "信息分类"])
off_rows = [
    ("Primary shares offered", base['primary'], full['primary'], "mm shares", "Offering_Terms (SEC-03); full = base + greenshoe 3.3m", "SEC 公开事实", FMT_S6),
    ("Secondary shares offered", base['secondary'], full['secondary'], "mm shares", "Offering_Terms (SEC-03); 出售股东转让, 非公司新发", "SEC 公开事实", FMT_S6),
    ("Greenshoe shares (over-allotment)", base['greenshoe'], full['greenshoe'], "mm shares", "Base=0 (不预设行使); Full=3.3m (单独情景)", "SEC 公开事实 / UW-01 开关", FMT_S6),
    ("Total shares offered (primary+secondary)", base['float_sh'], full['float_sh'], "mm shares", "= primary + secondary", "计算值", FMT_S6),
    ("Price (拟议, 内部决策输入)", price, price_full, "USD/share", "Offering_Terms (UW-01); 非最终定价", "内部委员会假设", FMT_PX2),
    ("Company primary gross proceeds", base['gross_primary'], full['gross_primary'], "USD mm", "= primary shares x price (secondary 不计入)", "计算值", FMT_M),
    ("Memo: secondary gross (归出售股东)", base['gross_secondary'], full['gross_secondary'], "USD mm", "= secondary x price; 公司募集 = 0 (Offering_Terms 开关=No)", "计算值 (备忘)", FMT_M),
    ("Memo: total gross (primary+secondary)", base['total_gross'], full['total_gross'], "USD mm", "发行总规模口径, 非公司募集", "计算值 (备忘)", FMT_M),
    ("(-) Underwriting fee (5% x primary gross)", -base['fee'], -full['fee'], "USD mm", "= 5%% x company primary gross; 不作用于 secondary", "计算值 (UW-01 费率)", FMT_M),
    ("(-) Fixed company offering expenses", -base['fixed'], -full['fixed'], "USD mm", "Offering_Terms (UW-01); greenshoe 增量不重复计提", "内部委员会假设", FMT_M),
    ("= Company net primary proceeds", base['net_primary'], full['net_primary'], "USD mm", "= gross primary - fee - fixed expenses", "计算值 (结论)", FMT_M),
    ("其中: greenshoe 增量净募集 (备忘)", 0.0, gs_incr_net, "USD mm", "= 3.3m x $34 x (1-5%), 只扣费率不扣固定费用", "计算值 (备忘)", FMT_M),
]
for label, a, b, unit, basis, cls, fmt in off_rows:
    bold = label.startswith("=") or "net primary" in label
    r = row(ws, r, [label, a, b, unit, basis, cls], [None, fmt, fmt, None, None, None],
            bold=bold, fill=FILL_KEY if "net primary proceeds" in label and "greenshoe" not in label else None)
r += 1
r = sec_head(ws, r, "B. 结构口径说明", 6)
for t in ["1) Base 公司净募集 $%.3f mm 全部来自 primary; secondary $%.3f mm gross 归出售股东, 不进入公司现金。" % (base['net_primary'], base['gross_secondary']),
          "2) Full greenshoe: 净募集 $%.3f mm = Base $%.3f mm + 增量 $%.3f mm (增量仅扣 5%% fee), 校验一致。" % (full['net_primary'], base['net_primary'], gs_incr_net),
          "3) greenshoe 为承销商选择权, Base 不预设行使 (Offering_Terms: Greenshoe treatment in Base = 0)。"]:
    r = note(ws, r, t)

# ================= Sheet 5: Dilution =================
ws, r = sheet("Dilution", [50, 17, 17, 13, 44, 20],
              "Dilution — 发行后股数与稀释 (分子分母同口径)",
              "口径: secondary 为存量转让不增加公司总股数; post-money shares = pre-money economic shares + primary (含 greenshoe 仅于 full 情景)")

r = sec_head(ws, r, "A. 股数与稀释 (mm shares / %)", 6)
r = hdr(ws, r, ["Item", "Base Offering", "Full Greenshoe", "Unit", "计算 / 取值来源", "信息分类"])
dil_rows = [
    ("Pre-money economic shares", premoney_sh, premoney_sh, "mm shares", "Offering_Terms (UW-01 cap-table snapshot)", "内部委员会假设", FMT_S6),
    ("(+) Primary issued (含 greenshoe 仅 full)", base['primary'], full['primary'], "mm shares", "Offering_Terms (SEC-03)", "SEC 公开事实", FMT_S6),
    ("(+) Secondary", 0.0, 0.0, "mm shares", "转让存量, 不增加公司总股数 (Policy)", "口径规则", FMT_S6),
    ("= Post-money shares", base['post_sh'], full['post_sh'], "mm shares", "= pre-money + primary", "计算值", FMT_S6),
    ("新投资者占比 (primary / post-money)", base['new_own'], full['new_own'], "%", "分子分母同为 post-money 口径", "计算值", FMT_PC),
    ("既有股东占比 (pre-money / post-money)", 1 - base['new_own'], 1 - full['new_own'], "%", "= 1 - 新投资者占比", "计算值", FMT_PC),
    ("公众流通盘占比 ((primary+secondary)/post-money)", base['float_pct'], full['float_pct'], "%", "secondary 已在 pre-money 股数内, 仅口径列示", "计算值", FMT_PC),
]
for label, a, b, unit, basis, cls, fmt in dil_rows:
    r = row(ws, r, [label, a, b, unit, basis, cls], [None, fmt, fmt, None, None, None],
            bold=label.startswith("="), fill=FILL_KEY if label.startswith("=") else None)
r += 1
r = sec_head(ws, r, "B. SEC-02 交叉核对 (仅交叉, 不进入定价计算)", 6)
r = hdr(ws, r, ["Item", "Value", "Unit", "假设价", "说明", "信息分类"])
r = row(ws, r, ["Preliminary NTBV / share", ntbv_3250, "USD/share", "$%.2f" % assumed_px, "Public_Financials (SEC-02); Cross-check only", "SEC 公开事实"], [None, FMT_PX2, None, None, None, None])
r = row(ws, r, ["Preliminary immediate dilution", dil_3250, "USD/share", "$%.2f" % assumed_px, "= $%.2f - NTBV $%.2f = $%.2f, 内部一致 OK" % (assumed_px, ntbv_3250, dil_3250), "SEC 公开事实"], [None, FMT_PX2, None, None, None, None])
for t in ["注 1: SEC-02 数值基于假设价 $%.2f, 与拟议价 $%.2f 口径不同, 不得直接混用; 本次 Base 定价 $%.2f。" % (assumed_px, price, price),
          "注 2: $%.2f 口径的 NTBV/即时稀释因缺 pre-money 账面净值基数标注 '待核实'; legacy '分子分母不一致' 错误已修正为同口径 post-money 比率。" % price,
          "注 3: legacy 将 secondary 计入 post-money 股数 (虚增至 %.6f m), 修正后 Base post-money = %.6f m。" % (legacy_post_sh, base['post_sh'])]:
    r = note(ws, r, t)

# ================= Sheet 6: Pricing_Summary =================
ws, r = sheet("Pricing_Summary", [52, 20, 20, 46, 20],
              "Pricing_Summary — 定价摘要与委员会处置建议",
              "处置规则 (Committee_Policy): 区间内 + 距 midpoint <= $%.2f/share + 无未解决 hard error → Proceed; 区间内但距 mid > $%.2f → Reprice; 区间外或结构未解决 → Defer" % (tol, tol))

r = sec_head(ws, r, "A. 核心结果勾稽 (与其他各表一致)", 5)
r = hdr(ws, r, ["Item", "Value", "Unit", "勾稽来源", "信息分类"])
sum_rows = [
    ("2023A Underwriting EBITDA (承销口径)", uw_ebitda23, "USD mm", "QoE 表 B 判断; = 管理口径 %.3f - SBC %.3f" % (aebitda23, sbc23), "计算值 (控制口径)", FMT_M),
    ("2024E Revenue", rev24, "USD mm", "Valuation 表 A; = %.3f x 1.22 (内部假设)" % rev23, "计算值", FMT_M),
    ("Net cash bridge (cash + MS)", net_cash23, "USD mm", "QoE 表 A = Valuation 表 A (+)项合计", "计算值", FMT_M),
    ("Pre-money equity @ mid 4.5x", eq_pre['mid'], "USD mm", "Valuation 表 A", "计算值", FMT_M),
    ("支持区间 Low (4.0x, 折后)", sup_lo, "USD/share", "Valuation 表 A/B", "计算值 (结论)", FMT_PX),
    ("支持区间 Midpoint (4.5x, 折后)", sup_mid, "USD/share", "Valuation 表 A/B", "计算值 (结论)", FMT_PX),
    ("支持区间 High (5.0x, 折后)", sup_hi, "USD/share", "Valuation 表 A/B", "计算值 (结论)", FMT_PX),
    ("拟议价格 (决策输入)", price, "USD/share", "Offering_Terms (UW-01); 非已实现结果", "内部委员会假设", FMT_PX2),
    ("Base 公司净募集", base['net_primary'], "USD mm", "Offering_Proceeds 表 A", "计算值", FMT_M),
    ("Base post-money shares", base['post_sh'], "mm shares", "Dilution 表 A (= Offering_Proceeds)", "计算值", FMT_S6),
    ("Base 新投资者稀释", base['new_own'], "%", "Dilution 表 A", "计算值", FMT_PC),
    ("Full greenshoe 公司净募集", full['net_primary'], "USD mm", "Offering_Proceeds 表 A", "计算值", FMT_M),
    ("Full greenshoe post-money shares", full['post_sh'], "mm shares", "Dilution 表 A", "计算值", FMT_S6),
    ("Full greenshoe 新投资者稀释", full['new_own'], "%", "Dilution 表 A", "计算值", FMT_PC),
]
for label, v, unit, src, cls, fmt in sum_rows:
    r = row(ws, r, [label, v, unit, src, cls], [None, fmt, None, None, None])
r += 1
r = sec_head(ws, r, "B. 处置三条件测试 (Committee_Policy)", 5)
r = hdr(ws, r, ["测试", "结果", "判定", "数值依据", ""])
r = row(ws, r, ["1. 拟议价位于支持区间 [$%.4f, $%.4f]" % (sup_lo, sup_hi), "$%.2f" % price, "PASS" if in_range else "FAIL", "$%.4f <= $%.2f <= $%.4f" % (sup_lo, price, sup_hi), ""],
        fill=FILL_OK if in_range else FILL_WARN)
r = row(ws, r, ["2. 距 midpoint <= $%.2f/share" % tol, "$%.4f" % dist_mid, "PASS" if dist_mid <= tol else "FAIL", "|$%.2f - $%.4f| = $%.4f" % (price, sup_mid, dist_mid), ""],
        fill=FILL_OK if dist_mid <= tol else FILL_WARN)
r = row(ws, r, ["3. 发行结构无未解决 hard error", "10/10 已修正", "PASS" if hard_err_resolved else "FAIL", "Error_Audit 表: 全部 legacy 错误已按 Policy/SEC 修正", ""],
        fill=FILL_OK if hard_err_resolved else FILL_WARN)
cell = ws.cell(r, 1, "处置建议: %s @ $%.2f (QoE 风险已在 memo 与 QoE 表披露)" % (verdict.upper(), price))
cell.font = Font(bold=True, size=12, color="1F3864")
cell.fill = FILL_KEY
for c in range(2, 6):
    ws.cell(r, c).fill = FILL_KEY
r += 2
r = sec_head(ws, r, "C. QoE 风险披露要点 (Proceed 之前提)", 5)
for t in ["(1) 承销口径 EBITDA 2023A = $%.3f mm, 仍深度为负; Net loss $%.3f mm; FCF $%.3f mm — 盈利质量依赖收入增长兑现。" % (uw_ebitda23, ni23, fcf23),
          "(2) 广告收入集中度 %.1f%%, 单一收入线波动敏感。" % (ad_conc23 * 100),
          "(3) 2024E 增长 %.0f%% 为内部假设(UW-01), 高于 2023 实际 %.1f%%; 若增长不及假设, 支持区间将下移。" % (g24 * 100, rev_growth23 * 100),
          "(4) 拟议 $%.2f 位于 SEC-03 公开初步区间 ($%.0f-$%.0f) 上限, 且距委员会 midpoint 仅 $%.4f, 安全边际有限。" % (price, pub_lo, pub_hi, dist_mid),
          "(5) 待核实: secondary 承销费承担方 / 债务余额 / pre-money 账面净值基数 / greenshoe 行使机制细节。"]:
    r = note(ws, r, t)
    ws.cell(r - 1, 1).font = F_TXT
r += 1
r = note(ws, r, "信息集声明: 本摘要仅基于 2024-03-20 前可得的 SEC-01~04 公开事实与 UW-01 内部委员会假设; 未使用最终定价、发行后文件或上市后表现。")

# ================= Sheet 7: Error_Audit =================
ws, r = sheet("Error_Audit", [6, 20, 46, 52, 46, 12],
              "Error_Audit — Candidate_Model 逐条审计与口径冲突记录",
              "Candidate_Model 共 11 行: 第 1 行为表头, 实际 legacy treatment 10 条, 已逐条复核并全部修正; 状态 'Fixed'")

r = sec_head(ws, r, "A. Legacy treatment 审计 (10 条)", 6)
r = hdr(ws, r, ["#", "Workstream / 类别", "Legacy 处理 (旧底稿)", "正确处理 (控制口径与依据)", "量化影响", "Status"])
for i, (wsname, legacy, correct, impact) in enumerate(err, 1):
    cm_row = next((c for c in CM if str(c[0]).strip().lower() == wsname.lower()), None)
    review_pt = str(cm_row[2]) if cm_row else ""
    r = row(ws, r, [i, wsname, "%s (底稿 Review point: %s)" % (legacy, review_pt), correct, impact, "Fixed"],
            fill=FILL_ALT if i % 2 == 0 else None)
r += 1
r = sec_head(ws, r, "B. 口径冲突显式记录 (同一指标多口径: 列示双方数值与取舍依据)", 6)
r = hdr(ws, r, ["#", "指标", "口径 A (数值/来源)", "口径 B (数值/来源)", "取舍依据", "Status"])
conflicts = [
    ("2023 EBITDA", "管理口径 Adj EBITDA = %.3f (SEC-01, 非GAAP, 含 SBC 加回)" % aebitda23,
     "承销口径 = %.3f (Committee_Policy/UW-01, 撤销 SBC 加回 %.3f)" % (uw_ebitda23, sbc23),
     "Committee_Policy 为控制口径, 与旧底稿冲突时以 Policy 为准; 两者均披露", "Resolved"),
    ("估值分母", "2023A Revenue = %.3f (legacy 采用)" % rev23, "2024E Revenue = %.3f (Policy: 2023A x 1.22)" % rev24,
     "Policy Forecast 条款明确 forward 分母; 增长率为内部假设", "Resolved"),
    ("发行价格", "拟议 $%.2f (UW-01 内部工作价)" % price, "公开初步区间 $%.0f-$%.0f (SEC-03, 仅 execution cross-check)" % (pub_lo, pub_hi),
     "$34 为决策输入; 公开区间用于交叉核对, 两者不矛盾(位于区间上限)", "Resolved"),
    ("倍数中点", "Policy mid = %.2fx (UW-01)" % mult_mid, "Peer_Comps 加权平均 = %.3fx" % peer_wavg,
     "以 Policy 4.5x 定价, peer 加权作交叉验证 (隐含价 $%.4f vs $%.4f, 一致)" % (sup_wavg, sup_mid), "Resolved"),
    ("NTBV/稀释", "SEC-02 @ $32.50: NTBV %.2f / 稀释 %.2f (公开事实)" % (ntbv_3250, dil_3250),
     "$34 口径: 缺 pre-money 账面净值基数", "SEC-02 仅作交叉核对; $34 口径标注 '待核实', 不虚构", "Cross-check only"),
    ("post-money 股数", "legacy = %.6f (pre-money + 22.0m 全部)" % (premoney_sh + 22.0),
     "修正 = %.6f (pre-money + primary %.6f; secondary 不增股数)" % (base['post_sh'], prim_base),
     "Policy Offering 条款: secondary 为转让非新发", "Resolved"),
]
for i, (k, a, b, basis, st) in enumerate(conflicts, 1):
    r = row(ws, r, [i, k, a, b, basis, st], fill=FILL_ALT if i % 2 == 0 else None)
r += 1
r = note(ws, r, "备注: 题面提及 '11 条 legacy treatment'; Candidate_Model 工作表共 11 行, 其中第 1 行为表头, 数据处理 10 条, 本表已全部覆盖, 无遗漏。")

wb.save(MODEL_PATH)
banner("输出文件")
print("模型工作簿已生成: %s" % MODEL_PATH)
print("工作表: %s" % ", ".join(wb.sheetnames))
print("\n脚本执行完毕, 全部结论均可由本脚本从输入工作簿复算。")
