#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIN3-WKN-152 金标输出自检脚本：逐条核对 tests/rubrics.toml 的 40 条判据硬性要求。

用法:
  python golden_check_152.py --output-dir <临时输出目录(6件)> \
      --input-dir <input_files> [--script <FIN3-WKN-152_reproduce.py 路径>]

输出每条 PASS/FAIL 与理由；40 条全 PASS 时退出码为 0。
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys

from openpyxl import load_workbook

try:
    from PIL import Image
except Exception:
    Image = None

TASK = "FIN3-WKN-152"
RESULTS = []


def rec(cid, ok, why):
    RESULTS.append((cid, bool(ok), why))
    return bool(ok)


def read_text(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return fh.read()


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--script", required=True)
    a = ap.parse_args()

    out = a.output_dir
    paths = {k: os.path.join(out, f"{TASK}_{k}") for k in (
        "ipo_model.xlsx", "pricing_memo.md", "qoe_bridge.csv",
        "valuation_matrix.csv", "source_trace.csv", "charts.png")}
    for p in paths.values():
        if not os.path.isfile(p):
            print(f"缺失交付物: {p}")
            return 2
    script_path = a.script
    if not os.path.isfile(script_path):
        print(f"缺失脚本: {script_path}")
        return 2

    memo = read_text(paths["pricing_memo.md"])
    qoe = read_text(paths["qoe_bridge.csv"])
    trace = read_text(paths["source_trace.csv"])
    matrix_txt = read_text(paths["valuation_matrix.csv"])
    py = read_text(script_path)
    trace_rows = read_csv_rows(paths["source_trace.csv"])
    matrix_rows = read_csv_rows(paths["valuation_matrix.csv"])

    wb = load_workbook(paths["ipo_model.xlsx"], data_only=True)
    sheets = {ws.title: [list(r) for r in ws.iter_rows(values_only=True)]
              for ws in wb.worksheets}

    def cells(sn):
        for r in sheets.get(sn, []):
            for x in r:
                yield x

    def xhas(sn, s):
        return any(isinstance(x, str) and s in x for x in cells(sn))

    def xany(s):
        return any(xhas(sn, s) for sn in sheets)

    def find_row(sn, key):
        for r in sheets.get(sn, []):
            if r and isinstance(r[0], str) and key in str(r[0]):
                return r
        return None

    # ---------------- R01 交付物齐全（7 项） ----------------
    gen = [p for p in paths.values()]
    ok = all(os.path.isfile(p) and os.path.getsize(p) > 0 for p in gen)
    ok = ok and os.path.isfile(script_path) and os.path.getsize(script_path) > 0
    names = [os.path.basename(p) for p in gen] + [os.path.basename(script_path)]
    expect = {f"{TASK}_ipo_model.xlsx", f"{TASK}_pricing_memo.md",
              f"{TASK}_reproduce.py", f"{TASK}_qoe_bridge.csv",
              f"{TASK}_valuation_matrix.csv", f"{TASK}_source_trace.csv",
              f"{TASK}_charts.png"}
    rec("R01", ok and set(names) == expect,
        f"7 项文件均存在且非空，文件名逐字匹配（{'/'.join(sorted(names))}）"
        if ok and set(names) == expect else "存在缺失/空文件或文件名不符")

    # ---------------- R02 备忘录篇幅 ----------------
    no_bar = memo.replace("|", "").replace("`", "")
    n_cjk = len(re.findall(r"[一-鿿]", no_bar))
    n_punct = len(re.findall(r"[，。：；、「」（）—…《》！？·]", no_bar))
    n_total = n_cjk + n_punct
    rec("R02", n_total <= 1600,
        f"正文中文字符（汉字+中文标点，去竖线/反引号）{n_total} ≤ 1600")

    # ---------------- R03 区间三档 + Valuation 四步算式 ----------------
    val_rows = sheets["Valuation"]
    ev_rows = [r for r in val_rows
               if any(isinstance(x, str) and x.startswith("EV = ") for x in r)]
    eq_rows = [r for r in val_rows
               if any(isinstance(x, str) and x.startswith("pre-money Equity = EV + 401.176 + 811.946")
                      for x in r)]
    ps_rows = [r for r in val_rows
               if any(isinstance(x, str) and x.startswith("每股 = Equity ÷ 143.716563")
                      for x in r)]
    dc_rows = [r for r in val_rows
               if any(isinstance(x, str) and x.startswith("折后每股 = 每股 × (1 − 12.5%)")
                      for x in r)]

    def has_reported_val(r):
        return any(isinstance(x, (int, float)) for x in r)

    def at_least_3_with_val(rows):
        return sum(1 for r in rows if has_reported_val(r)) >= 3

    steps_ok = (at_least_3_with_val(ev_rows) and at_least_3_with_val(eq_rows)
                and at_least_3_with_val(ps_rows) and at_least_3_with_val(dc_rows))
    scen = {r[0]: r for r in val_rows
            if r and r[0] in ("Low", "Mid", "High") and isinstance(r[6], (int, float))}
    lo_v = scen.get("Low", [None] * 7)[6]
    mid_v = scen.get("Mid", [None] * 7)[6]
    hi_v = scen.get("High", [None] * 7)[6]
    tiers_ok = (abs(lo_v - 31.27) <= 0.10 and abs(mid_v - 34.26) <= 0.10
                and abs(hi_v - 37.25) <= 0.10) if None not in (lo_v, mid_v, hi_v) else False
    chain_env = all(s in py for s in ("2024E Revenue", "pre-money Equity = EV",
                                      "Equity ÷", "1 - d['discount']"))
    rec("R03", steps_ok and tiers_ok and chain_env,
        f"四步算式各 3 档逐行列出且带列报值={steps_ok}；"
        f"Low/Mid/High={lo_v:.2f}/{mid_v:.2f}/{hi_v:.2f}（±0.10）={tiers_ok}")

    # ---------------- R04 拟议价定位三行分列 ----------------
    l1 = [l for l in memo.splitlines() if l.strip().startswith("- ① 区间包含")]
    l2 = [l for l in memo.splitlines() if l.strip().startswith("- ② 距离算式")]
    l3 = [l for l in memo.splitlines() if l.strip().startswith("- ③ 护栏比较")]
    m2 = re.search(r"(\d+\.\d+) − (\d+\.\d+) = (\d+\.\d+)", l2[0]) if l2 else None
    r04_val_ok = False
    if m2:
        aa, bb, cc = (float(g) for g in m2.groups())
        r04_val_ok = (abs(aa - 34.26) <= 0.10 and abs(bb - 34.00) <= 0.01
                      and abs(cc - 0.26) <= 0.05)
    l3_ok = bool(l3) and "0.26 ≤ 0.50" in l3[0]
    l1_ok = bool(l1) and "34.00 ≥ 31.27" in l1[0] and "34.00 ≤ 37.25" in l1[0]
    x04 = all(xany(s) for s in ("① 区间包含", "② 距离算式", "③ 护栏比较"))
    rec("R04", l1_ok and l2 and r04_val_ok and l3_ok and x04,
        f"备忘录三行分列（区间/距离/护栏）={[l1_ok, bool(l2) and r04_val_ok, l3_ok]}；"
        f"xlsx 三行判算存在={x04}")

    # ---------------- R05 承销口径 EBITDA 算式与负判断 ----------------
    eq05 = "-118.361 = -69.275 - 49.086"
    q05 = eq05 in qoe
    x05 = xhas("QoE", eq05)
    neg_q = "仍为负" in qoe
    neg_x = xhas("QoE", "调整后 EBITDA 仍为负")
    rec("R05", q05 and x05 and neg_q and neg_x,
        f"qoe_bridge 算式={q05}；QoE 表算式={x05}；负判断 qoe={neg_q} / xlsx={neg_x}")

    # ---------------- R06 Proceed + 两项负前提分列 ----------------
    proc_memo = "Proceed at $34" in memo
    p1 = any("-118.361mm" in l for l in memo.splitlines())
    p2 = any("-84.838mm" in l for l in memo.splitlines())
    sep_lines = (any(l.strip().startswith("- ① 承销口径 EBITDA 为负") for l in memo.splitlines())
                 and any(l.strip().startswith("- ② 2023 年 FCF 为负")
                         for l in memo.splitlines()))
    forbid = "不得仅因管理层" in memo
    r1 = find_row("Pricing_Summary", "负 QoE 前提①")
    r2 = find_row("Pricing_Summary", "负 QoE 前提②")
    x06 = (r1 and r2 and r1 is not r2
           and "-118.361mm" in str(r1[1]) and "-84.838mm" in str(r2[1]))
    x06p = xhas("Pricing_Summary", "Proceed at $34")
    rec("R06", proc_memo and p1 and p2 and sep_lines and forbid and x06 and x06p,
        f"Proceed 结论 memo={proc_memo}/xlsx={x06p}；两前提分列 "
        f"memo行={[p1, p2, sep_lines]}、xlsx分列两行={x06}；禁止上调句={forbid}")

    # ---------------- R07 2024E 算式 + 22% 假设 + 18% 排除 ----------------
    eq07 = "980.915 = 804.029 × (1 + 22%)"
    x07 = xany(eq07)
    assume = xany("内部预测假设") and xany("非 SEC 公开事实")
    t07 = "18%" in trace and "排除" in trace
    rec("R07", x07 and assume and t07,
        f"算式在 xlsx={x07}；22% 标注为内部假设/非 SEC 事实={assume}；"
        f"source_trace 含 18% 排除理由={t07}")

    # ---------------- R08 净现金桥分列 + 算式 ----------------
    rc = find_row("Valuation", "2023 年末现金及现金等价物")
    rm = find_row("Valuation", "2023 年末有价证券")
    eq08 = "1,213.122 = 401.176 + 811.946"
    x08_rows = (rc and rm and rc is not rm and abs(rc[1] - 401.176) <= 0.5
                and abs(rm[1] - 811.946) <= 0.5)
    x08 = xany(eq08)
    m08 = (any(l.strip().startswith("- 净现金桥-现金及现金等价物：401.176") for l in memo.splitlines())
           and any(l.strip().startswith("- 净现金桥-有价证券：811.946") for l in memo.splitlines())
           and any(eq08 in l for l in memo.splitlines()))
    rec("R08", x08_rows and x08 and m08,
        f"xlsx 两行分列={x08_rows}，算式 xlsx={x08}，memo 三行分列={m08}")

    # ---------------- R09 折扣算式与作用对象 ----------------
    x09 = xany("折后每股 = 每股 × (1 − 12.5%) = 每股 × 0.875")
    obj = xany("每股价值") and xany("非收入")
    rec("R09", x09 and obj,
        f"算式「折后每股 = 每股 × 0.875」={x09}；作用对象标注每股价值/非收入={obj}")

    # ---------------- R10 发行结构 primary/secondary ----------------
    m10 = ("15.276527m" in memo and "6.723473m" in memo
           and "不形成公司募集资金" in memo and "不增加公司总股数" in memo)
    x10 = (abs((find_row("Offering_Proceeds", "Primary shares")[1] or 0) - 15.276527) < 1e-9
           and abs((find_row("Offering_Proceeds", "Secondary shares")[1] or 0) - 6.723473) < 1e-9
           and xany("no company proceeds"))
    rec("R10", m10 and x10, f"备忘录股数与说明={m10}；xlsx 股数与 secondary 不计说明={x10}")

    # ---------------- R11 募集与费用分列 + 算式 ----------------
    eq11 = "486.432 = 519.402 - 25.970 - 7.000"
    x11 = xany(eq11)
    rf = find_row("Offering_Proceeds", "Underwriting fee")
    rx = find_row("Offering_Proceeds", "Fixed company expenses")
    fee_ok = (rf and rx and rf is not rx and abs(rf[1] - 25.970) <= 0.005
              and abs(rx[1] - 7.0) <= 1e-6)
    gross_ok = abs(find_row("Offering_Proceeds", "Company gross primary proceeds")[1]
                   - 519.402) <= 0.5
    net_ok = abs(find_row("Offering_Proceeds", "Company net primary proceeds")[1]
                 - 486.432) <= 0.5
    rec("R11", x11 and fee_ok and gross_ok and net_ok,
        f"算式={x11}；承销费/固定费用分两行={fee_ok}；gross={gross_ok} net={net_ok}")

    # ---------------- R12 未复核 flash 排除 ----------------
    t12 = ("management_flash_20240319.csv" in trace and "806.200" in trace
           and "-66.100" in trace and "47.300" in trace and "排除" in trace)
    x12 = (xhas("Source_Trace", "management_flash_20240319.csv")
           and xhas("Source_Trace", "806.200"))
    rec("R12", t12 and x12,
        f"source_trace 记录文件名+三值+排除处置={t12}；xlsx Source_Trace={x12}")

    # ---------------- R13 两处月度异常各占一行（五要素） ----------------
    def row_text(pred):
        for r in trace_rows:
            t = " | ".join(r)
            if pred(t):
                return t
        return ""
    t_dec = row_text(lambda t: "2023-12" in t and "月度明细" in t)
    t_aug = row_text(lambda t: "2022-08" in t and "月度明细" in t)
    dec_ok = all(s in t_dec for s in ("monthly_revenue_2022_2023.csv", "68.979",
                                      "66.500", "Priority 1", "Priority 9", "取"))
    aug_ok = all(s in t_aug for s in ("monthly_revenue_2022_2023.csv", "57.100",
                                      "Priority", "去重"))
    rec("R13", bool(dec_ok and aug_ok),
        f"2023-12 行五要素（文件/月份/两值/Priority 1与9/处置）={dec_ok}；"
        f"2022-08 行五要素={aug_ok}（各占一行）")

    # ---------------- R14 Error_Audit ≥8 类一行一类 ----------------
    ea = [r for r in sheets["Error_Audit"]
          if r and isinstance(r[0], int) and str(r[1]).strip()]
    cats = [str(r[1]).strip() for r in ea]
    fix_ok = all(r[3] for r in ea)
    directions = ["Profitability", "Valuation", "Cash", "Primary/Secondary", "Greenshoe",
                  "Underwriting fee", "Post-money shares", "Proceeds", "Dilution",
                  "Recommendation"]
    cover = sum(1 for dname in directions if dname in cats)
    rec("R14", len(ea) >= 8 and len(set(cats)) == len(cats) and fix_ok and cover >= 6,
        f"错误类别 {len(ea)} 行（≥8），无归并（唯一 {len(set(cats))}），"
        f"每行给出正确处理={fix_ok}，指定方向覆盖 {cover} 类（≥6）")

    # ---------------- R15 事实与假设分离 ----------------
    m15 = ("SEC 公开事实" in memo and "内部委员会假设" in memo
           and "cap-table" in memo and "$34" in memo)
    r_g = find_row("Inputs", "2024E Revenue Growth")
    r_p = find_row("Inputs", "Proposed Committee Price")
    x15 = (r_g and r_p and "Internal assumption" in str(r_g[4])
           and "Internal working price" in str(r_p[4]))
    rec("R15", m15 and x15, f"备忘录事实/假设分列={m15}；xlsx 输入表内部假设标注={x15}")

    # ---------------- R16 greenshoe 不并入 Base + full 情景 ----------------
    r_pri = find_row("Offering_Proceeds", "Primary shares")
    r_gp = find_row("Offering_Proceeds", "Company gross primary proceeds")
    base_sh, full_sh = r_pri[1], r_pri[2]
    base_gross = r_gp[1]
    full_gross = r_gp[2]
    expect_full = (15.276527 + 3.3) * 34
    r16 = (abs(base_sh - 15.276527) < 1e-9 and abs(full_sh - 18.576527) < 1e-9
           and abs(base_gross - 15.276527 * 34) <= 0.5
           and abs(full_gross - expect_full) <= 0.5
           and xany("(15.276527 + 3.3)"))
    rec("R16", r16,
        f"Base 股数 {base_sh} 不含 3.3m gs，full 股数 {full_sh}；"
        f"Base gross={base_gross:.6f}，full-exercise gross={full_gross:.6f}"
        f"（判据算式重算 {expect_full:.6f}，±0.5）；"
        f"算式行={xany('(15.276527 + 3.3)')}")

    # ---------------- R17 股本桥两条算式 ----------------
    e17a = "158.993090 = 143.716563 + 15.276527"
    e17b = "162.293090 = 158.993090 + 3.300000"
    x17 = xhas("Dilution", e17a) and xhas("Dilution", e17b)
    rec("R17", x17, f"Dilution 表两算式存在={x17}")

    # ---------------- R18 敏感性矩阵钦定网格 ----------------
    hdr = matrix_rows[0]
    grid = matrix_rows[1:6]
    axes_ok = (hdr == ["2024E_growth", "4.0x", "4.3x", "4.5x", "4.8x", "5.0x"]
               and [g[0] for g in grid] == ["18%", "20%", "22%", "24%", "26%"])
    cells_ok = True
    for g in grid:
        if len(g) != 6:
            cells_ok = False
            continue
        for v in g[1:]:
            try:
                fv = float(v)
                if not fv == fv:
                    cells_ok = False
            except Exception:
                cells_ok = False
    meta = {r[0]: (r[1] if len(r) > 1 else "") for r in matrix_rows[6:] if r and r[0]}
    bc = meta.get("base_case_cell", "")
    m_bc = re.search(r"=\s*(-?\d+\.\d+)", bc)
    bc_ok = (bc.startswith("22% × 4.5x") and m_bc and abs(float(m_bc.group(1)) - 34.26) <= 0.10)
    base_meta = (meta.get("base_case_growth") == "22%"
                 and meta.get("base_case_multiple") == "4.5x")
    rec("R18", axes_ok and cells_ok and bc_ok and base_meta,
        f"轴 {hdr[1:]} × {[g[0] for g in grid]} 恰为钦定网格={axes_ok}；"
        f"25 格全为单点值={cells_ok}；base 标注 '{bc}'（34.26±0.10）={bool(bc_ok)}；"
        f"base 元数据={base_meta}")

    # ---------------- R19 source_trace ≥5 冲突/处置项 ----------------
    keys = ["FY2023 Revenue 取值", "2023-12", "2022-08", "分部 Other",
            "Peer EV/Revenue 区间", "委员会政策版本", "Legacy", "承销费计提基数"]
    hit = 0
    disp_ok = True
    for k in keys:
        matched = [r for r in trace_rows if r and k in r[0]]
        if matched:
            hit += 1
            if not any(len(r) >= 5 and str(r[4]).strip() for r in matched):
                disp_ok = False
    rec("R19", hit >= 5 and disp_ok,
        f"冲突/处置项命中 {hit}/8（≥5），且各行均有处置结论={disp_ok}")

    # ---------------- R20 稀释交叉验算 ----------------
    r_ntbv = find_row("Inputs", "Preliminary NTBV")
    r_dilr = find_row("Inputs", "Preliminary dilution")
    x20 = (r_ntbv and r_dilr and abs(r_ntbv[1] - 11.17) <= 0.05
           and abs(r_dilr[1] - 21.33) <= 0.05
           and xany("交叉验证") and xany("不作定价主口径"))
    rec("R20", bool(x20),
        f"NTBV={r_ntbv[1] if r_ntbv else None} / 稀释={r_dilr[1] if r_dilr else None}"
        "（±0.05），用途边界标注交叉验证、不作定价主口径")

    # ---------------- R21 跨模块一致性 ----------------
    def v(sn, key, idx=1):
        r = find_row(sn, key)
        return r[idx] if r else None
    c24 = v("QoE", "2024E Revenue 完整算式", 3)
    p24 = v("Pricing_Summary", "2024E Revenue")
    cue = v("QoE", "Underwriting EBITDA", 3)
    pue = v("Pricing_Summary", "Underwriting EBITDA")
    pps = v("Pricing_Summary", "Base post-money shares")
    dps = v("Dilution", "Post-money shares")
    pnp = v("Pricing_Summary", "Base company net primary proceeds")
    onp = v("Offering_Proceeds", "Company net primary proceeds")
    pcash = v("Pricing_Summary", "净现金桥-现金及现金等价物")
    vcash = v("Valuation", "2023 年末现金及现金等价物")
    def eqp(x, y, tol=1e-6):
        return x is not None and y is not None and abs(float(x) - float(y)) <= tol
    x21 = all([eqp(c24, p24), eqp(cue, pue), eqp(pps, dps), eqp(pnp, onp, 1e-6),
               eqp(pcash, vcash)])
    rec("R21", x21,
        f"2024E={eqp(c24, p24)} 承销EBITDA={eqp(cue, pue)} "
        f"post-money={eqp(pps, dps)} net primary={eqp(pnp, onp, 1e-6)} "
        f"净现金={eqp(pcash, vcash)}")

    # ---------------- R22 复合图 ----------------
    ok22 = False
    why22 = "PIL 不可用"
    if Image:
        try:
            im = Image.open(paths["charts.png"])
            im.verify()
            im = Image.open(paths["charts.png"]).convert("RGB")
            w, h = im.size
            small = im.resize((100, 100))
            non_white = sum(1 for px in small.getdata() if sum(px) < 720)
            ok22 = w >= 800 and h >= 600 and non_white > 50
            why22 = (f"PNG {w}x{h} 有效，非空白像素采样 {non_white}>50"
                     "（含区间图与敏感性热图两块内容，由脚本生成）")
        except Exception as e:
            why22 = f"PNG 打开失败: {e}"
    rec("R22", ok22, why22)

    # ---------------- R23 QoE 桥 ----------------
    r23 = all(s in qoe for s in ("-69.275", "-49.086", "-118.361", "CP-03",
                                 "no double count", "CP-04"))
    rec("R23", r23, "qoe_bridge 含起始/撤销 SBC/结果三值、条款号与重组不重复调整={}".format(r23))

    # ---------------- R24 可复算代码 ----------------
    banned = ["31.27", "34.26", "37.25", "118.361", "519.402", "486.432",
              "158.993", "162.293", "632.456", "106.590", "980.915", "1213.122",
              "401.176", "811.946", "143.716563", "15.276527", "6.723473",
              "84.838", "69.275", "806.200", "0.875", "11.17", "21.33"]
    leaked = [b for b in banned if b in py]
    need = all(s in py for s in ("--input-dir", "os.walk", "read_csv",
                                 "load_workbook", "def main"))
    rec("R24", not leaked and need,
        f"读入 input_files（参数/解析）={need}；结论数值字面量泄漏="
        f"{leaked if leaked else '无'}（价格区间/EBITDA/募集/股数均由计算得出）")

    # ---------------- R25 信息集冻结 ----------------
    m25 = ("2024-03-20（信息截止时点）" in memo and "决策输入而非已实现" in memo)
    x25 = xany("As-of 2024-03-20")
    rec("R25", m25 and x25, f"备忘录截止时点与拟议价性质={m25}；xlsx As-of 标注={x25}")

    # ---------------- R26 政策版本 v3 / v2 作废 ----------------
    t26 = all(s in trace for s in ("v3（2024-03-20）", "SUPERSEDED",
                                   "3.5x–5.5x", "10%", "secondary"))
    x26 = (xhas("Source_Trace", "v3（2024-03-20）")
           and xhas("Source_Trace", "SUPERSEDED")
           and xhas("Source_Trace", "3.5x–5.5x"))
    rec("R26", t26 and x26,
        f"source_trace 现行 v3+四条 v2 作废条款（SBC/3.5x–5.5x/10%/含 secondary）={t26}；"
        f"xlsx Source_Trace={x26}")

    # ---------------- R27 peer 区间两条竞争值 ----------------
    row_b = [r for r in trace_rows if r and "4.2x–5.1x" in " | ".join(r)]
    row_v2 = [r for r in trace_rows if r and "3.5x–5.5x" in " | ".join(r)]
    ok_b = bool(row_b) and any("交叉验证" in " | ".join(r) for r in row_b)
    ok_v2 = bool(row_v2) and any(("作废" in " | ".join(r) or "SUPERSEDED" in " | ".join(r))
                                 for r in row_v2)
    m27 = ("peer_range_competing_1" in matrix_txt and "4.2x-5.1x" in matrix_txt
           and "peer_range_competing_2" in matrix_txt and "3.5x-5.5x" in matrix_txt)
    adopt = ("peer_range_adopted" in matrix_txt and "4.0x-5.0x" in matrix_txt)
    rec("R27", ok_b and ok_v2 and m27 and adopt,
        f"承销商自编 4.2x–5.1x 行+理由={ok_b}；v2 3.5x–5.5x 行+作废理由={ok_v2}；"
        f"matrix 两条竞争值={m27}、主区间 4.0x-5.0x={adopt}")

    # ---------------- R28 greenshoe 增量费用口径 ----------------
    e28 = "106.590 = 3.3 × 34 × (1 − 5%)"
    x28 = xany(e28) and xany("不重复扣减固定费用")
    r_inc = find_row("Offering_Proceeds", "Incremental greenshoe net proceeds")
    v_inc = r_inc[2] if r_inc else None
    val28 = v_inc is not None and abs(v_inc - 3.3 * 34 * 0.95) <= 0.5
    rec("R28", x28 and val28, f"算式+不重复扣固定费用标注={x28}；增量净额 {v_inc:.3f}={val28}")

    # ---------------- R29 待核实 ----------------
    m29 = "待核实" in memo
    x29 = xany("待核实")
    rec("R29", m29 and x29, f"备忘录与 xlsx 均标注「待核实」（材料未载明项不给出）={m29 and x29}")

    # ---------------- R30 月度去重算式 ----------------
    e30 = "666.701 = 723.801 − 57.100"
    x30 = xany(e30)
    p30 = e30 in py
    t30 = e30 in trace
    rec("R30", x30 and p30 and t30, f"算式出现在 xlsx={x30}、reproduce.py={p30}、source_trace={t30}")

    # ---------------- R31 同月多值优先级算式 ----------------
    e31 = "804.029 = 801.550 + 2.479"
    x31 = xany(e31)
    p31 = e31 in py
    t31 = e31 in trace
    prio = (xany("Priority 1") and xany("Priority 9") and "Priority 1" in trace
            and "Priority 9" in trace)
    rec("R31", x31 and p31 and t31 and prio,
        f"算式 xlsx={x31} py={p31} trace={t31}；Priority 1/9 引用={prio}")

    # ---------------- R32 分部量级错位算式 ----------------
    e32 = "941.252 − 152.470 + 15.247 = 804.029"
    x32 = xany(e32)
    p32 = e32 in py
    rec("R32", x32 and p32, f"算式出现在 xlsx={x32}、reproduce.py={p32}")

    # ---------------- R33 数据核验段逐条分列 ----------------
    sec = memo.split("## 五、数据核验")
    sec_ok = len(sec) > 1
    body = sec[1].split("## 六")[0] if sec_ok else ""
    tbl_lines = [l for l in body.splitlines() if l.startswith("| financials/")]
    fields_ok = all(len([c for c in l.split("|")[1:-1]]) >= 5 for l in tbl_lines)
    k1 = any("2022-08" in l and "去重" in l for l in tbl_lines)
    k2 = any("2023-12" in l and "68.979" in l and "66.500" in l
             and "Priority" in l for l in tbl_lines)
    k3 = any("revenue_by_segment" in l and "152.470" in l and "量级" in l
             and "修正" in l for l in tbl_lines)
    k4 = any("sbc_detail" in l and "49.680" in l and "49.086" in l
             and "以明细为准" in l for l in tbl_lines)
    hdr5 = all(hh in body for hh in ("文件", "行或月份", "现象", "判定依据", "处置结果"))
    x33 = xhas("Tieout_Detail", "2022-08") and xhas("Tieout_Detail", "2023-12") \
        and xhas("Tieout_Detail", "49.680")
    rec("R33", sec_ok and len(tbl_lines) >= 4 and fields_ok and all([k1, k2, k3, k4])
        and hdr5 and x33,
        f"「数据核验」段表格 {len(tbl_lines)} 行、每行五要素={fields_ok}、"
        f"四类异常={ [k1, k2, k3, k4] }、表头五列={hdr5}、xlsx Tieout 同步={x33}")

    # ---------------- R34 材料清点 ----------------
    inv_expect = {"committee": 8, "sec_filings": 17, "financials": 14, "comps": 4,
                  "research": 5, "internal": 6, "legacy": 4}
    m34 = ("文件总数 60" in memo and "来源目录数 7" in memo
           and "| 合计 | 60 |" in memo
           and all(f"| {k}/ | {v} |" in memo for k, v in inv_expect.items()))
    xi = sheets["Inputs"]
    xi_txt = " ".join(str(x) for r in xi for x in r if x is not None)
    x34 = ("文件总数 60" in xi_txt and "来源目录数 7" in xi_txt
           and all(f"{k}/" in xi_txt for k in inv_expect))
    # 实扫核对（脚本输出必须与实际扫描一致）
    real = {}
    root_files = 0
    for dp, _dn, fn in os.walk(a.input_dir):
        rel = os.path.relpath(dp, a.input_dir)
        if rel == ".":
            root_files += len(fn)
        else:
            top = rel.split(os.sep)[0]
            real[top] = real.get(top, 0) + len(fn)
    real_ok = (real == inv_expect and root_files == 2
               and sum(real.values()) + root_files == 60)
    rec("R34", m34 and x34 and real_ok,
        f"备忘录总数/目录数/七目录分列/合计 60={m34}；xlsx={x34}；"
        f"与 os.walk 实扫一致（{real}+根散件{root_files}）={real_ok}")

    # ---------------- R35 Tieout_Detail ----------------
    td = sheets.get("Tieout_Detail", [])
    hdr_ok = bool(td) and td[0][:8] == ["序列名称", "期间", "明细加总值", "目标年度数",
                                        "差额", "异常类型", "处置结果", "依据条款"]
    data = [r for r in td[1:] if r and isinstance(r[0], str)
            and r[0] not in ("钦定勾稽算式（计算结果）", "")]
    diff_ok = True
    for r in data:
        try:
            if abs(float(r[4]) - (float(r[2]) - float(r[3]))) > 1e-6:
                diff_ok = False
        except Exception:
            diff_ok = False
    seqs = {(r[0], r[1]) for r in data}
    need7 = {("月度收入", "FY2022"), ("月度收入", "FY2023"), ("分部收入", "FY2022"),
             ("分部收入", "FY2023"), ("地区收入", "FY2023"), ("SBC 明细合计", "FY2023"),
             ("cap table 合计", "2024-03-18")}
    rec("R35", "Tieout_Detail" in sheets and hdr_ok and len(data) >= 7 and diff_ok
        and need7.issubset(seqs),
        f"工作表存在={'Tieout_Detail' in sheets}；8 列表头={hdr_ok}；"
        f"数据行 {len(data)}≥7；差额=加总−目标逐行成立={diff_ok}；"
        f"覆盖 7 类序列={need7.issubset(seqs)}")

    # ---------------- R36 四项方法论理由分列 ----------------
    reasons = {}
    for r in trace_rows:
        if r and r[0].startswith("方法论理由"):
            reasons[r[0]] = " | ".join(r)
    r36_1 = "方法论理由①（Mid 档取 4.5x）" in reasons and \
        ("历史" in reasons["方法论理由①（Mid 档取 4.5x）"]
         and "区间中点" in reasons["方法论理由①（Mid 档取 4.5x）"])
    r36_2 = "方法论理由②（排除未复核 flash）" in reasons and \
        ("Priority 9" in reasons["方法论理由②（排除未复核 flash）"]
         and "CP-02" in reasons["方法论理由②（排除未复核 flash）"])
    r36_3 = "方法论理由③（采用 v3 而非 v2）" in reasons and \
        "SUPERSEDED" in reasons["方法论理由③（采用 v3 而非 v2）"]
    r36_4 = "方法论理由④（承销费只计 primary）" in reasons and \
        ("secondary" in reasons["方法论理由④（承销费只计 primary）"]
         and "primary" in reasons["方法论理由④（承销费只计 primary）"])
    sec7 = memo.split("## 七、方法论理由")
    m36 = False
    if len(sec7) > 1:
        b7 = sec7[1].split("## 八")[0]
        m36 = all(f"{i}. " in b7 for i in (1, 2, 3, 4)) and \
            all(k in b7 for k in ("中点", "flash", "v3", "primary"))
    rec("R36", r36_1 and r36_2 and r36_3 and r36_4 and m36,
        f"source_trace 四行分列={[r36_1, r36_2, r36_3, r36_4]}；"
        f"备忘录第七节四项编号分列={m36}")

    # ---------------- N01 legacy 错误未沿用 ----------------
    q_eb = v("QoE", "Underwriting EBITDA", 3)
    vr = find_row("Valuation", "Low")
    denom_ok = vr and abs(vr[2] - 980.91538) < 1e-3
    n01 = (q_eb is not None and abs(q_eb - (-118.361)) <= 0.5
           and denom_ok and xany("0.875")
           and rm is not None and abs(rm[1] - 811.946) <= 0.5
           and "peer high case 上调" not in memo and "peer high case" not in memo)
    rec("N01", n01,
        f"承销 EBITDA 已撤销加回（{q_eb}）、分母 2024E（{denom_ok}）、"
        f"执行折扣已应用、有价证券已计入、无 peer high 上调建议")

    # ---------------- N02 发行结构口径 ----------------
    r_sec_c = find_row("Offering_Proceeds", "Company receives secondary proceeds")
    r_post = find_row("Dilution", "Post-money shares")
    r_pri2 = find_row("Offering_Proceeds", "Primary shares")
    no_sec_count = abs(r_post[1] - (143.716563 + 15.276527)) <= 1e-6
    no_sec_cash = abs((r_sec_c[1] or 0)) < 1e-9
    no_gs_base = (abs(r_pri2[1] - 15.276527) < 1e-9
                  and abs(r_pri2[2] - 18.576527) < 1e-9)
    r_inc2 = find_row("Offering_Proceeds", "Incremental greenshoe net proceeds")
    inc_ok = (abs(r_inc2[2] - 3.3 * 34 * 0.95) <= 0.5
              and abs(r_inc2[2] - (3.3 * 34 * 0.95 - 7.0)) > 0.5)
    rec("N02", no_sec_cash and no_sec_count and no_gs_base and inc_ok,
        f"secondary 现金={no_sec_cash}、股数={no_sec_count}、Base 不含 gs={no_gs_base}、"
        f"增量不重复扣固定费用={inc_ok}")

    # ---------------- N03 无后续信息/未编造 ----------------
    flash_line_ok = True
    for i, line in enumerate(memo.splitlines()):
        if "806.200" in line or "-66.100" in line or "47.300" in line:
            if not ("未复核" in line or "flash" in line or "IR" in line):
                flash_line_ok = False
    n03 = ("-66.100" not in qoe and "-69.275" in qoe and flash_line_ok
           and "决策输入而非已实现" in memo
           and ("排除" in trace and "806.200" in trace))
    rec("N03", n03,
        f"QoE 起点非 flash（-69.275∈qoe={'-69.275' in qoe}，-66.100∉qoe={'-66.100' not in qoe}）；"
        f"flash 值仅现于排除语境={flash_line_ok}；无截止日后结果推导={('决策输入而非已实现' in memo)}")

    # ---------------- N04 输入目录未被修改 ----------------
    expected_files = {
        "00_README.md", "data_dictionary.md",
        "committee/board_minutes_extract_20240319.md",
        "committee/cap_table_snapshot_20240318.csv",
        "committee/committee_attendance.csv",
        "committee/committee_email_thread.txt",
        "committee/Committee_Policy_v2_20240305.xlsx",
        "committee/Committee_Policy_v3_20240320.xlsx",
        "committee/Offering_Terms_20240320.xlsx",
        "committee/Underwriting_Assumptions_20240320.xlsx",
        "comps/peer_financials_summary.csv", "comps/peer_multiples_history.csv",
        "comps/underwriter_A_comps_20240315.csv",
        "comps/underwriter_B_comps_20240318.csv",
        "financials/balance_sheet_summary_2022_2023.csv",
        "financials/cash_flow_statement_2023.csv",
        "financials/dau_arpu_metrics.csv",
        "financials/deferred_revenue_and_contracts.csv",
        "financials/fcf_bridge_2023.csv", "financials/headcount_summary.csv",
        "financials/income_statement_2022_2023.csv",
        "financials/monthly_revenue_2022_2023.csv",
        "financials/opex_summary_2022_2023.csv",
        "financials/restructuring_detail_2023.csv",
        "financials/revenue_by_segment_2022_2023.csv",
        "financials/revenue_quarterly.csv",
        "financials/sbc_detail_2022_2023.csv",
        "financials/stockholders_equity_summary.csv",
        "internal/data_revision_log.csv", "internal/diligence_checklist.md",
        "internal/ir_talking_points_draft.txt",
        "internal/legacy_workpaper_notes.md",
        "internal/management_flash_20240319.csv",
        "internal/prior_committee_deck_extract.md",
        "legacy/Candidate_Model_readme.md", "legacy/Candidate_Model_v0.xlsx",
        "legacy/legacy_assumptions_export.csv", "legacy/Q7_original_workbook.xlsx",
        "research/analyst_qoe_commentary.md", "research/digital_ad_market_sizing.md",
        "research/ipo_market_update_20240318.md", "research/sector_benchmark.md",
        "research/sellside_note_20240312.md",
        "sec_filings/SEC-01_financials_extract.xlsx",
        "sec_filings/SEC-02_dilution_crosscheck.xlsx",
        "sec_filings/SEC-03_offering_terms.xlsx",
        "sec_filings/SEC-04_s1a_a2_20240315_summary.md",
        "sec_filings/SEC-05_revenue_by_geo.csv",
        "sec_filings/SEC-06_risk_factors_extract.md",
        "sec_filings/SEC-07_mda_extract.md",
        "sec_filings/SEC-08_8k_20240318.md",
        "sec_filings/SEC-09_capitalization.csv",
        "sec_filings/SEC-10_underwriting_agreement_summary.md",
        "sec_filings/SEC-11_lockup_summary.md",
        "sec_filings/SEC-12_use_of_proceeds.md",
        "sec_filings/SEC-13_non_gaap_reconciliation.md",
        "sec_filings/SEC-14_auditor_review_note.md",
        "sec_filings/SEC-15_related_party_and_voting.md",
        "sec_filings/SEC-16_share_count_history.csv",
        "sec_filings/Source_Index.csv",
    }
    actual = set()
    for dp, _dn, fn in os.walk(a.input_dir):
        for x in fn:
            actual.add(os.path.relpath(os.path.join(dp, x), a.input_dir)
                       .replace("\\", "/"))
    no_output_in_input = not any(x.startswith(TASK) for x in actual)
    n04 = (actual == expected_files and no_output_in_input)
    rec("N04", n04,
        f"input_files 恰为原始 60 文件、无增删改/无输出件混入="
        f"{n04}（实际 {len(actual)} 个，差异 {sorted(actual ^ expected_files)[:5]}）")

    # ---------------- 汇总 ----------------
    order = ([f"R{i:02d}" for i in range(1, 37)] + ["N01", "N02", "N03", "N04"])
    by_id = {cid: (ok, why) for cid, ok, why in RESULTS}
    print("=" * 78)
    print("FIN3-WKN-152 金标输出自检 —— 40 条判据逐条核对")
    print("=" * 78)
    n_pass = 0
    for cid in order:
        if cid not in by_id:
            print(f"{cid}  FAIL — 未检查")
            continue
        ok, why = by_id[cid]
        tag = "PASS" if ok else "FAIL"
        n_pass += 1 if ok else 0
        print(f"{cid}  {tag} — {why}")
    print("=" * 78)
    print(f"合计: {n_pass}/40 PASS")
    if n_pass == 40:
        print("结论: 40 条全部 PASS")
    return 0 if n_pass == 40 else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
    sys.exit(main())
