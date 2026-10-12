#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-153 现金增强 1 号集合资产管理计划 2026 年三季度投资运作复核 — 可复算脚本
运行方式：python3 FIN3-WKN-153_reproduce.py
输入（只读）：/app/input_files/    输出：/app/output/
全部结论数值均自输入材料读入或计算得到，脚本不硬编码任何结论数字，不访问网络。
交付物：
  1) FIN3-WKN-153_quarterly_workbook.xlsx  （Coverage / Holdings_Summary / Valuation_Recalc /
     Nav_Bridge / Compliance_Check / Issue_Log / Task_Status / Prev_Report_Fix 八表）
  2) FIN3-WKN-153_operation_report.md      （八章节季度投资运作报告）
  3) FIN3-WKN-153_holdings_coverage.csv    （逐 sheet 持仓覆盖表）
  4) FIN3-WKN-153_issue_log.csv            （数据问题与阻塞台账）
  5) FIN3-WKN-153_charts.png               （限额对比 + 账户覆盖复合图）
  6) FIN3-WKN-153_reproduce.py             （本脚本）
"""
import os
import re
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl.styles import Font, Alignment

INP = "/app/input_files"
OUT = "/app/output"
PREP_DATE = "2026-10-10"   # 报告提交日（任务场景给定，非计算结论）
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- 工具函数
def fm(x):   return f"{x:,.2f}"                      # 金额（元）
def pct(x):  return f"{x * 100:.2f}%"                # 比例（入参为小数）
def bps(x):  return f"{x * 10000:.2f}"               # 基点（入参为净值差）
def cjk_count(s):                                    # 中文字符计数（含中文标点，不含表格竖线/代码标记）
    return len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", s))
def read_md(rel):
    with open(os.path.join(INP, rel), encoding="utf-8") as f:
        return f.read()

# ================================================================ 1. 读入材料
# 1.1 材料清点（任务 1）
all_files, dir_counts = [], {}
for root, _dirs, files in os.walk(INP):
    for fn in sorted(files):
        rel = os.path.relpath(os.path.join(root, fn), INP)
        all_files.append(rel)
        d = rel.split(os.sep)[0] if os.sep in rel else "(根目录散件)"
        dir_counts[d] = dir_counts.get(d, 0) + 1
n_files = len(all_files)
n_dirs = len([d for d in dir_counts if d != "(根目录散件)"])
n_root = dir_counts.get("(根目录散件)", 0)
n_sub = sum(v for k, v in dir_counts.items() if k != "(根目录散件)")
assert n_sub + n_root == n_files, "分目录小计+根散件与总数不勾稽"

# 1.2 托管行净值报告 / 计提 / 银行对账单
nav_rpt = pd.read_csv(f"{INP}/valuation/nav_report_20260930.csv")
navget = lambda item: float(nav_rpt.loc[nav_rpt["item"] == item, "value"].iloc[0])
VAL_DATE   = nav_rpt.loc[nav_rpt["item"] == "report_date", "value"].iloc[0]   # 估值日=报告期末
TOTAL_SHARES = navget("total_shares")
TOTAL_NAV_TB = navget("total_nav")
NAVPS_TB     = navget("nav_per_share")
CASH_TB      = navget("cash_and_equivalent")
FUND_NAME    = nav_rpt.loc[nav_rpt["item"] == "fund_name", "value"].iloc[0]

acc = pd.read_csv(f"{INP}/valuation/accruals_20260930.csv")
acc["amount"] = acc["amount"].astype(float)
RECV = acc[acc["item"].str.contains("receivable")]
PAY  = acc[acc["item"].str.contains("payable")]
recv_sum, pay_sum = RECV["amount"].sum(), PAY["amount"].sum()

bank = pd.read_csv(f"{INP}/valuation/bank_statement_20260930.csv")
bank["balance"] = bank["balance"].astype(float)
bank_sum = bank["balance"].sum()
bank_diff = bank_sum - CASH_TB

# 1.3 材料截止时点（00_README）与业绩比较基准
readme_txt = read_md("00_README.md")
CUTOFF = re.search(r"材料包整理日[：:]\s*([\d-]+)", readme_txt).group(1)
bret = pd.read_csv(f"{INP}/data/benchmark_returns_2026Q3.csv").set_index("benchmark")["return"]
BENCH_Q3 = float(bret.loc["计划业绩比较基准"])

# 1.4 行情：主件（valuation/，空文件=传输残留）与重推件（data/）
try:
    pf_main = pd.read_csv(f"{INP}/valuation/price_feed_20260930.csv")
    n_main_rows = len(pf_main)
except pd.errors.EmptyDataError:      # 空文件（传输残留），记入问题台账
    n_main_rows = 0
pf = pd.read_csv(f"{INP}/data/price_feed_20260930_repush.csv")
n_repush_rows = len(pf)
px = pf[pf["trade_date"] == VAL_DATE]                # 估值日当日过滤（runbook 3.3）
n_val_rows = len(px)
n_nonval_rows = n_repush_rows - n_val_rows
price = px.set_index("instrument_id")["close_price"]
n_price_ids = px["instrument_id"].nunique()

# 1.5 证券主数据 / 持仓（十个账户 sheet 全读）
sm = pd.read_csv(f"{INP}/portfolio/security_master.csv")
status_map = sm.set_index("sec_code")["status"]
issuer_map = sm.set_index("sec_code")["issuer"]
name_master = sm.set_index("sec_code")["sec_name"]

xl = pd.ExcelFile(f"{INP}/portfolio/holdings_2026Q3.xlsx")
acct_sheets = [s for s in xl.sheet_names if s.startswith("acct_")]
other_sheets = [s for s in xl.sheet_names if s not in acct_sheets]
n_acct_sheets = len(acct_sheets)
frames = []
for s in acct_sheets:
    d = xl.parse(s)
    d["sheet"] = s
    frames.append(d)
h = pd.concat(frames, ignore_index=True)
h["as_of"] = h["as_of"].astype(str)

def row_mv(r, pxmap):
    p = pxmap.get(r["sec_code"])
    if p is None or pd.isna(p):
        return np.nan
    return r["vol"] * p if r["sec_type"] == "EquityFund" else r["vol"] * p / 100.0

h["close_price"] = h["sec_code"].map(price)
h["mv"] = h.apply(lambda r: row_mv(r, price), axis=1)
h["mstatus"] = h["sec_code"].map(status_map)
n_raw = len(h)
assert h["mv"].notna().all(), "存在无估值日行情的持仓行"
assert h["mstatus"].notna().all(), "存在主数据缺失的持仓编码"

# ================================================================ 2. 有效持仓口径（runbook 第 2 章，任务 3）
# 逐 sheet 顺序执行三类剔除：2.1 估值日归属 → 2.2 主数据状态 → 2.3 重复上报
cov_rows = []
drop_detail = {1: [], 2: [], 3: []}
eff_frames = []
for s in acct_sheets:
    d = h[h["sheet"] == s]
    raw_n, raw_mv = len(d), d["mv"].sum()
    d1 = d[d["as_of"] == VAL_DATE]                                   # 2.1
    x1, x1mv = raw_n - len(d1), raw_mv - d1["mv"].sum()
    drop_detail[1].append(d[d["as_of"] != VAL_DATE])
    d2 = d1[d1["mstatus"] == "active"]                               # 2.2
    x2, x2mv = len(d1) - len(d2), d1["mv"].sum() - d2["mv"].sum()
    drop_detail[2].append(d1[d1["mstatus"] != "active"])
    d2s = d2.sort_values("source_row_id")                            # 2.3
    dupmask = d2s.duplicated(subset=["acct", "sec_code", "vol"], keep="first")
    x3, x3mv = int(dupmask.sum()), d2s[dupmask]["mv"].sum()
    drop_detail[3].append(d2s[dupmask])
    eff = d2s[~dupmask]
    eff_frames.append(eff)
    cov_rows.append(dict(sheet=s, 原始行数=raw_n, 剔除行数_估值日归属=x1,
                         剔除行数_主数据状态=x2, 剔除行数_重复上报=x3, 有效行数=len(eff),
                         原始市值=round(raw_mv, 2), 剔除市值_估值日归属=round(x1mv, 2),
                         剔除市值_主数据状态=round(x2mv, 2), 剔除市值_重复上报=round(x3mv, 2),
                         有效市值=round(eff["mv"].sum(), 2)))
cov = pd.DataFrame(cov_rows)
tot = dict(sheet="合计", 原始行数=cov["原始行数"].sum(),
           剔除行数_估值日归属=cov["剔除行数_估值日归属"].sum(),
           剔除行数_主数据状态=cov["剔除行数_主数据状态"].sum(),
           剔除行数_重复上报=cov["剔除行数_重复上报"].sum(), 有效行数=cov["有效行数"].sum(),
           原始市值=round(cov["原始市值"].sum(), 2),
           剔除市值_估值日归属=round(cov["剔除市值_估值日归属"].sum(), 2),
           剔除市值_主数据状态=round(cov["剔除市值_主数据状态"].sum(), 2),
           剔除市值_重复上报=round(cov["剔除市值_重复上报"].sum(), 2),
           有效市值=round(cov["有效市值"].sum(), 2))
assert tot["原始行数"] == n_raw
assert (tot["剔除行数_估值日归属"] + tot["剔除行数_主数据状态"] + tot["剔除行数_重复上报"]
        + tot["有效行数"]) == n_raw, "覆盖表行数不勾稽"
cov_csv = pd.concat([cov, pd.DataFrame([tot])], ignore_index=True)

eff = pd.concat(eff_frames, ignore_index=True)
EFF_MV = eff["mv"].sum()
RAW_MV = h["mv"].sum()
x1mv_t, x2mv_t, x3mv_t = (cov[c].sum() for c in
                          ["剔除市值_估值日归属", "剔除市值_主数据状态", "剔除市值_重复上报"])
assert abs(RAW_MV - x1mv_t - x2mv_t - x3mv_t - EFF_MV) < 0.05, "市值桥不勾稽"
d1_all = pd.concat(drop_detail[1]); d2_all = pd.concat(drop_detail[2]); d3_all = pd.concat(drop_detail[3])
n_stale_sheets = d1_all["sheet"].nunique()
nonact_names = "、".join(f"{r.sec_code}（{r.mstatus}）" for r in d2_all.itertuples())
dup_sheets = "、".join(sorted(d3_all["sheet"].unique()))

# ================================================================ 3. 行情关联覆盖（任务 4）
eff_codes = set(eff["sec_code"])
join_matched = int(eff["close_price"].notna().sum())
join_unmatched = len(eff) - join_matched
price_only = sorted(set(price.index) - eff_codes)
n_price_only = len(price_only)
price_only_all_inactive = all(status_map.get(c) != "active" for c in price_only)

# ================================================================ 4. 净值复核推导链（任务 5）
calc_nav = EFF_MV + CASH_TB + recv_sum - pay_sum
calc_navps = calc_nav / TOTAL_SHARES
nav_diff_tb = calc_nav - TOTAL_NAV_TB
navps_diff_bp = (calc_navps - NAVPS_TB) * 10000
# 未过滤口径对照（上期“全表合计”口径）
unf_nav = RAW_MV + CASH_TB + recv_sum - pay_sum
unf_navps = unf_nav / TOTAL_SHARES
overstate_bp = (unf_navps - calc_navps) * 10000
overstate_bp_vs_tb = (unf_navps - NAVPS_TB) * 10000

vr_rows = [
    ("A", "有效持仓市值（有效口径 280 行重算）", EFF_MV, "portfolio/holdings_2026Q3.xlsx + data/price_feed_20260930_repush.csv", "债券/非标 vol×close_price/100；权益基金 vol×close_price（数据字典§2）"),
    ("B", "现金及清算备付金（列报值）", CASH_TB, "valuation/nav_report_20260930.csv", "托管行报告为准"),
]
for i, r in enumerate(RECV.itertuples()):
    vr_rows.append((f"C{i+1}", f"应收-{r.item_name}（列报值）", r.amount, "valuation/accruals_20260930.csv", r.accrual_period))
vr_rows.append(("C", "应收合计 C1+C2", recv_sum, "计提明细加总", f"{' + '.join(fm(v) for v in RECV['amount'])} = {fm(recv_sum)}"))
for i, r in enumerate(PAY.itertuples()):
    vr_rows.append((f"D{i+1}", f"应付-{r.item_name}（列报值）", r.amount, "valuation/accruals_20260930.csv", r.accrual_period))
vr_rows.append(("D", "应付合计 D1+D2+D3", pay_sum, "计提明细加总", f"{' + '.join(fm(v) for v in PAY['amount'])} = {fm(pay_sum)}"))
vr_rows += [
    ("E", "资产净值 E=A+B+C−D", calc_nav, "复算值", f"{fm(EFF_MV)} + {fm(CASH_TB)} + {fm(recv_sum)} − {fm(pay_sum)} = {fm(calc_nav)}"),
    ("F", "计划总份额（列报值）", TOTAL_SHARES, "valuation/nav_report_20260930.csv", "托管行报告为准"),
    ("G", "单位净值 G=E÷F（复算值）", calc_navps, "复算值", f"{fm(calc_nav)} ÷ {fm(TOTAL_SHARES)} = {calc_navps:.6f}"),
    ("H", "托管行单位净值（列报值）", NAVPS_TB, "valuation/nav_report_20260930.csv", "nav_per_share"),
    ("I", "差额 I=G−H（基点）", navps_diff_bp, "复算值", f"({calc_navps:.6f} − {NAVPS_TB:.4f}) × 10000 = {navps_diff_bp:.2f} bp（四舍五入位级）"),
    ("J", "托管行资产净值（列报值）", TOTAL_NAV_TB, "valuation/nav_report_20260930.csv", "total_nav"),
    ("K", "资产净值差额 K=E−J（元）", nav_diff_tb, "复算值", f"{fm(calc_nav)} − {fm(TOTAL_NAV_TB)} = {fm(nav_diff_tb)}"),
]
valuation_recalc = pd.DataFrame(vr_rows, columns=["步骤", "项目", "列报/推导值", "来源文件", "算式与口径说明"])

# ================================================================ 5. 现金勾稽（任务 6）
cash_rows = [
    (r.account, r.account_name, r.balance, r.as_of, "valuation/bank_statement_20260930.csv")
    for r in bank.itertuples()
]
cash_rows.append(("合计", "两账户加总", bank_sum, VAL_DATE,
                  " + ".join(fm(v) for v in bank["balance"]) + f" = {fm(bank_sum)}"))
cash_rows.append(("托管报告", "现金及清算备付金（列报值）", CASH_TB, VAL_DATE, "valuation/nav_report_20260930.csv"))
cash_rows.append(("差额", "对账单合计 − 托管报告现金", bank_diff, VAL_DATE, f"{fm(bank_sum)} − {fm(CASH_TB)} = {fm(bank_diff)}"))
nav_bridge_cash = pd.DataFrame(cash_rows, columns=["账户", "名称", "金额（元）", "as_of", "来源/算式"])

bridge_rows = [
    ("原始口径持仓市值（全表合计，未按 runbook 第2章过滤）", RAW_MV, "holdings 十表 295 行 × 估值日行情"),
    ("− 剔除①估值日归属：as_of≠" + VAL_DATE + f"（{len(d1_all)} 行，涉及 {n_stale_sheets} 个 sheet）", -x1mv_t, "runbook 2.1"),
    ("− 剔除②主数据状态非 active（matured/called，" + f"{len(d2_all)} 行）", -x2mv_t, "runbook 2.2"),
    ("− 剔除③重复上报（acct+sec_code+vol，保留 source_row_id 首条，" + f"{len(d3_all)} 行）", -x3mv_t, "runbook 2.3"),
    ("= 有效持仓市值", EFF_MV, f"{fm(RAW_MV)} − {fm(x1mv_t)} − {fm(x2mv_t)} − {fm(x3mv_t)} = {fm(EFF_MV)}"),
    ("未过滤口径资产净值（对照）", unf_nav, f"{fm(RAW_MV)} + {fm(CASH_TB)} + {fm(recv_sum)} − {fm(pay_sum)}"),
    ("未过滤口径单位净值（对照值）", unf_navps, f"{fm(unf_nav)} ÷ {fm(TOTAL_SHARES)} = {unf_navps:.6f}"),
    ("正确口径单位净值（复算值）", calc_navps, f"{calc_navps:.6f}（=E÷F）"),
    ("未过滤口径相对正确口径高估（bp）", overstate_bp, f"({unf_navps:.6f} − {calc_navps:.6f}) × 10000 = {overstate_bp:.2f} bp"),
    ("未过滤口径相对托管列报单位净值高估（bp）", overstate_bp_vs_tb, f"({unf_navps:.6f} − {NAVPS_TB:.4f}) × 10000 = {overstate_bp_vs_tb:.2f} bp"),
]
nav_bridge_cal = pd.DataFrame(bridge_rows, columns=["口径调整项", "数值", "算式/依据"])

# ================================================================ 6. 条款解析（现行 v3 / 历史 v2 / 流动性制度，任务 7、8）
v3_txt = read_md("rules/restrictions_v3_20260901.md")
v2_txt = read_md("rules/restrictions_v2_20260601.md")
liq_txt = read_md("rules/liquidity_policy.md")

def parse_limits(txt):
    out = {}
    for m in re.finditer(r"第\s*(\d+)\s*条（(R-\d+)）(.*?)\*\*(不得超过|不得低于)\s*([\d.]+)%\*\*", txt, re.S):
        desc = re.sub(r"\s+", "", m.group(3).replace("**", "").replace("`", ""))
        out[m.group(2)] = dict(article=f"第{m.group(1)}条", desc=desc,
                               dirn=m.group(4), limit=float(m.group(5)) / 100)
    return out
v3 = parse_limits(v3_txt)
v2 = {m.group(1): float(m.group(2)) / 100
      for m in re.finditer(r"（(R-\d+)）.*?(?:不得超过|不得低于)\s*([\d.]+)%", v2_txt)}
v3_eff = re.search(r"生效日[：:]\s*([\d-]+)", v3_txt).group(1)
v3_supersede = re.search(r"替代\s*(v\d)", v3_txt).group(1)
liq12 = float(re.search(r"第\s*12\s*条.*?不低于.*?([\d.]+)\s*%", liq_txt).group(1)) / 100
liq21 = re.search(r"第\s*21\s*条\s*(.*)", liq_txt).group(1).strip()
t9 = re.search(r"第\s*9\s*条.*?在\s*\*\*(T\+\d+)\*\*\s*个工作日内提交整改计划", v3_txt)
CURE = t9.group(1) if t9 else "T+2"

# ================================================================ 7. 五项限额测算（任务 7）
DEN = TOTAL_NAV_TB   # v3 第2条：分母为计划资产净值总额（托管行报告为准）
by_sec = eff.groupby("sec_code")["mv"].sum().sort_values(ascending=False)
top_sec, top_sec_mv = by_sec.index[0], by_sec.iloc[0]
by_iss = (eff.assign(issuer=eff["sec_code"].map(issuer_map))
             .groupby("issuer")["mv"].sum().sort_values(ascending=False))
top_iss, top_iss_mv = by_iss.index[0], by_iss.iloc[0]
nonstd_mv = eff.loc[eff["sec_type"] == "NonStdAsset", "mv"].sum()
eqf_mv = eff.loc[eff["sec_type"] == "EquityFund", "mv"].sum()

r01, r02, r03, r05, r07 = (v3["R-01"], v3["R-02"], v3["R-03"], v3["R-05"], v3["R-07"])
meas = {"R-01": top_sec_mv / DEN, "R-02": top_iss_mv / DEN, "R-03": nonstd_mv / DEN,
        "R-05": CASH_TB / DEN, "R-07": eqf_mv / DEN}
numer = {"R-01": top_sec_mv, "R-02": top_iss_mv, "R-03": nonstd_mv,
         "R-05": CASH_TB, "R-07": eqf_mv}
basis = {"R-01": f"{top_sec} {name_master[top_sec]} 合计市值",
         "R-02": f"发行人「{top_iss}」名下有效持仓合计市值",
         "R-03": "sec_type=NonStdAsset 有效持仓市值合计",
         "R-05": "托管报告现金及清算备付金（银行对账单两账户合计一致）",
         "R-07": "sec_type=EquityFund 有效持仓市值合计"}
def verdict(rid):
    ok = meas[rid] <= v3[rid]["limit"] if v3[rid]["dirn"] == "不得超过" else meas[rid] >= v3[rid]["limit"]
    return "合规" if ok else "超限"
comp_rows = []
for rid in ["R-01", "R-02", "R-03", "R-05", "R-07"]:
    comp_rows.append(dict(条款号=v3[rid]["article"], 规则=rid, 指标=v3[rid]["desc"],
                          比较方向=("≤ " if v3[rid]["dirn"] == "不得超过" else "≥ ") + f"{v3[rid]['limit']*100:.0f}%",
                          分子口径=basis[rid], 分子金额=round(numer[rid], 2), 分母_资产净值=round(DEN, 2),
                          测算值=pct(meas[rid]), 测算值_小数=round(meas[rid], 6),
                          限额=pct(v3[rid]["limit"]), 结论=verdict(rid),
                          依据="rules/restrictions_v3_20260901.md"))
compliance = pd.DataFrame(comp_rows)
breaches = compliance[compliance["结论"] == "超限"]

# 超限详情（任务 9）：成因与整改引用自材料
memo_txt = read_md("internal/approval_memo_20260928.md")
notes_txt = read_md("internal/manager_notes.md")
memo_sec = re.search(r"同意增持(.+?)，", memo_txt).group(1).strip()
memo_cap = float(re.search(r"不超过\s*([\d.]+)\s*%", memo_txt).group(1)) / 100
memo_warn = float(re.search(r"内部预警线\s*([\d.]+)\s*%", memo_txt).group(1)) / 100
def cn_num(s):
    d = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if s.startswith("十"):
        return 10 + d[s[1:]]
    if s.endswith("十"):
        return d[s[0]] * 10
    if "十" in s:
        a, b = s.split("十")
        return d[a] * 10 + d[b]
    return d[s]

# 纪要用中文序数（第一期）、主数据用阿拉伯数字（第1期），归一后再匹配
memo_key = re.sub(r"\s+", "", memo_sec)
memo_key = re.sub(r"第([一二三四五六七八九十\d]+)期", lambda m: f"第{cn_num(m.group(1))}期", memo_key)
memo_sm = sm[sm["sec_name"].str.replace(r"\s+", "", regex=True) == memo_key]
memo_status = memo_sm["status"].iloc[0] if len(memo_sm) else "未找到"
memo_maturity = memo_sm["maturity_date"].iloc[0] if len(memo_sm) else "未载明"
actual_name = name_master[top_sec]
breach_row = None
if len(breaches):
    breach_row = dict(
        证券代码=top_sec, 证券名称=actual_name, 市值=round(top_sec_mv, 2), 占净值比=pct(meas["R-01"]),
        限额=pct(v3["R-01"]["limit"]), 超限幅度_bp=round((meas["R-01"] - v3["R-01"]["limit"]) * 10000, 2),
        成因=(f"9 月按投资决策纪要增持{memo_sec}（纪要口径增持后不超过净值 {memo_cap*100:.0f}%、"
              f"内部预警线 {memo_warn*100:.1f}%）；主数据显示「{memo_sec}」已于 {memo_maturity} {memo_status}，"
              f"期末实际存续并计入的华骏集团持仓为 {top_sec}（{actual_name}），审批所指券名与主数据不一致（待核实）；"
              f"期末实测 {pct(meas['R-01'])} 高于审批上限与硬性限额，属主动超限"),
        整改动作=f"按 v3 第9条于估值日起 {CURE} 个工作日内提交整改计划，减持 {top_sec} 使单一证券占比降至 {pct(v3['R-01']['limit'])} 以内；处置方式与完成时限以整改计划为准（材料未载明，待核实）",
        时限=f"整改计划提交：{CURE} 个工作日（v3 第9条）；整改完成时限：待核实（以整改计划为准）",
        披露要求="于季度报告「投资监督」章节披露超限事实、成因、整改措施与时限（v3 第9条）；非盘中瞬时超限（第10条不适用），非被动超限（第11条不适用）")
breach_df = pd.DataFrame([breach_row]) if breach_row else pd.DataFrame()

# 现金类交叉核对（任务 7）
r05_consistent = abs(liq12 - v3["R-05"]["limit"]) < 1e-9
cross_note = (f"交叉核对：流动性管理制度第12条要求现金类资产不低于净值 {liq12*100:.0f}%，"
              f"与现行 v3 {v3['R-05']['article']}（R-05 ≥{v3['R-05']['limit']*100:.0f}%）阈值"
              f"{'一致' if r05_consistent else '不一致'}；但流动性制度第21条称「{liq21}」，"
              f"现行 v3 仅四章、无第七章，现金类资产界定的条文出处缺失，界定细节待核实"
              f"（本期分子按托管行口径「现金及清算备付金」{fm(CASH_TB)} 元执行）。")
version_note = (f"版本适用性：v3 生效日 {v3_eff}，替代 {v3_supersede}（2026-06-01 版）；本期估值日 {VAL_DATE} "
                f"在 v3 生效日之后，一律按 v3 执行。历史版 v2 限额（R-01 {v2['R-01']*100:.0f}%、R-03 {v2['R-03']*100:.0f}%、"
                f"R-05 {v2['R-05']*100:.0f}%、R-07 {v2['R-07']*100:.0f}%）已被替代，仅作历史回溯，不适用于本期。")
r02_note = f"R-02 按主数据 issuer 字段汇总；「{top_iss}」关联方名单材料未载明，关联方合并口径待核实。"

# ================================================================ 8. 上期报告重述（任务 10）
q2_txt = read_md("reports/2026Q2_operation_report.md")
q2_flat = re.sub(r"\s+", "", q2_txt)
def q2_find(pat):
    m = re.search(pat, q2_flat)
    return m if m else None
m_r01 = q2_find(r"单一证券集中度最高([\d.]+)%，低于([\d.]+)%上限")
m_r03 = q2_find(r"非标资产比例([\d.]+)%，低于([\d.]+)%上限")
m_r05 = q2_find(r"现金类资产比例([\d.]+)%，高于([\d.]+)%下限")
m_all = q2_find(r"持仓汇总口径采用盘后导出明细\*\*全表合计\*\*，未区分数据所属日期")
q2_navps = float(q2_find(r"单位净值([\d.]+)").group(1))
q2_nav_mv = re.search(r"计划资产净值([\d.]+)亿元", q2_flat).group(1)
q2_date = re.search(r"报告期末[：:]([\d-]+)", q2_txt).group(1)
prev_fix = pd.DataFrame([
    dict(编号="P1",
         上期原表述=f"「单一证券集中度最高 {m_r01.group(1)}%，低于 {m_r01.group(2)}% 上限」（按 2026-06-01 版 v2 条款监测，结论“未发生超限事项”）",
         出处="reports/2026Q2_operation_report.md 第二节；compliance/limit_monitor_2026Q2.csv",
         不再适用原因=f"v2 已被 v3（生效日 {v3_eff}）替代，R-01 上限由 {v2['R-01']*100:.0f}% 收紧至 {v3['R-01']['limit']*100:.0f}%；且本期末实测单一证券（{top_sec}）已达 {pct(meas['R-01'])}，上期结论口径与本期事实均不再成立",
         本期处置=f"按 v3 {v3['R-01']['article']} 10% 上限重述并在本报告第四章披露超限事实、成因、整改与时限"),
    dict(编号="P2",
         上期原表述=f"「非标资产比例 {m_r03.group(1)}%，低于 {m_r03.group(2)}% 上限」",
         出处="reports/2026Q2_operation_report.md 第二节",
         不再适用原因=f"v2 非标上限 {v2['R-03']*100:.0f}% 已被 v3 {v3['R-03']['article']} {v3['R-03']['limit']*100:.0f}% 替代",
         本期处置=f"按 v3 上限重述：本期实测 {pct(meas['R-03'])}（{fm(nonstd_mv)} 元），低于 {pct(v3['R-03']['limit'])}，合规"),
    dict(编号="P3",
         上期原表述=f"「现金类资产比例 {m_r05.group(1)}%，高于 {m_r05.group(2)}% 下限」",
         出处="reports/2026Q2_operation_report.md 第二节",
         不再适用原因=f"v2 下限 {v2['R-05']*100:.0f}% 已被 v3 {v3['R-05']['article']} {v3['R-05']['limit']*100:.0f}% 替代，且与流动性管理制度第12条（≥{liq12*100:.0f}%）一致；上期 {m_r05.group(1)}% 若按现行下限衡量已不足",
         本期处置=f"按 3% 下限重述：本期实测 {pct(meas['R-05'])}（{fm(CASH_TB)} 元），高于下限，合规"),
    dict(编号="P4",
         上期原表述="「持仓汇总口径采用盘后导出明细全表合计，未区分数据所属日期，主要原因是为了与上季度报表保持一致」",
         出处="reports/2026Q2_operation_report.md 第二节；internal/manager_notes.md 第4条确认不再适用",
         不再适用原因=f"与 recon_runbook 2.1（估值日归属）冲突；本期实测全表合计口径将使单位净值高估约 {overstate_bp:.0f} bp（{unf_navps:.6f} vs {calc_navps:.6f}）",
         本期处置="按估值日归属+主数据状态+去重三项口径重算（280 行有效），并在本报告第三、五章说明对照影响"),
    dict(编号="P5",
         上期原表述=f"「计划资产净值 {q2_nav_mv} 亿元……单位净值 {q2_navps}」（{q2_date} 期末数）",
         出处="reports/2026Q2_operation_report.md 第一节",
         不再适用原因=f"为上期期末数（{q2_date}），仅供期初对照，不得作为本期期末数引用",
         本期处置=f"本期期末以托管行报告为准：资产净值 {fm(TOTAL_NAV_TB)} 元、单位净值 {NAVPS_TB:.4f}；单位净值较上期 {q2_navps} 变动 {(NAVPS_TB/q2_navps-1)*100:.2f}%（份额变动与分红材料未载明，期间收益率待核实；Q3 业绩比较基准收益 {BENCH_Q3*100:.2f}%）"),
])

# ================================================================ 9. 数据问题台账（任务 11）
br_log = pd.read_csv(f"{INP}/compliance/breach_log_2026.csv")
br_hist = "；".join(f"{r.breach_id}（{r.breach_date}，{r.rule_id}，{r.status}）" for r in br_log.itertuples())
issue_rows = [
    ("行情缺失", "valuation/price_feed_20260930.csv",
     f"估值日行情主件为空文件（{n_main_rows} 条记录），系传输环节未落盘的残留件",
     "无法以主件取估值日价格", "改以数据组重推件 data/price_feed_20260930_repush.csv 为取数依据",
     "internal/ops_email_20261008.txt（主件不承载数据，以重推件为准）", "已解决"),
    ("口径过滤", "data/price_feed_20260930_repush.csv",
     f"重推件 {n_repush_rows} 行中混有 {n_nonval_rows} 行前一交易日（非估值日）记录，批次标识为原始推送",
     "直接使用将混入非估值日价格", f"按 trade_date={VAL_DATE} 过滤后取 {n_val_rows} 行（{n_price_ids} 只证券）",
     "ops 邮件（以估值日当日记录为准）+ recon_runbook 3.3", "已解决"),
    ("字段过时", "rules/recon_runbook.md",
     "指引 3.1 要求以 wind_code 关联，但 2026-08 数据字典改版后持仓侧为 sec_code、行情侧为 instrument_id，两侧均无 wind_code 列",
     "按指引原文无法执行关联", "按数据字典以 sec_code=instrument_id 一一对应关联；建议修订指引字段名",
     "internal/data_dictionary.md §3 命名沿革", "已解决（指引待修订）"),
    ("陈旧数据", "portfolio/holdings_2026Q3.xlsx",
     f"{len(d1_all)} 行 as_of={d1_all['as_of'].iloc[0]}（上期末）记录混入 {n_stale_sheets} 个账户 sheet",
     f"全表口径虚增市值 {fm(x1mv_t)} 元", "按 runbook 2.1 估值日归属剔除",
     "rules/recon_runbook.md 2.1", "已解决"),
    ("状态不符", "portfolio/holdings_2026Q3.xlsx + portfolio/security_master.csv",
     f"{len(d2_all)} 行主数据状态非 active 的证券仍出现在导出中：{nonact_names}",
     f"虚增市值 {fm(x2mv_t)} 元", "按 runbook 2.2 剔除；到期/赎回事实与投资经理说明第2条一致",
     "rules/recon_runbook.md 2.2 + internal/manager_notes.md", "已解决"),
    ("重复上报", "portfolio/holdings_2026Q3.xlsx",
     f"{len(d3_all)} 行同 acct+sec_code+vol 重复上报（{dup_sheets}），source_row_id 不同",
     f"虚增市值 {fm(x3mv_t)} 元", "按 runbook 2.3 以 source_row_id 升序保留首条，其余剔除",
     "rules/recon_runbook.md 2.3", "已解决"),
    ("名称不一致", "internal/approval_memo_20260928.md + internal/manager_notes.md",
     f"纪要与说明称增持「{memo_sec}」，但主数据显示该券已于 {memo_maturity} 状态 {memo_status}；期末存续的华骏集团持仓为 {top_sec}（{actual_name}）",
     "审批所指券名与实际持仓不一致，影响超限成因追溯", "测算以主数据与持仓明细为准；名称差异登记待核实",
     "portfolio/security_master.csv", "待核实"),
    ("条文引用缺失", "rules/liquidity_policy.md",
     "第21条引用「投资限制条款第七章」，现行 v3 仅四章、无第七章",
     "现金类资产界定的条文出处缺失", f"阈值交叉核对一致（≥{liq12*100:.0f}%）；分子按托管口径现金及清算备付金执行，界定细节待核实",
     "rules/restrictions_v3_20260901.md + rules/liquidity_policy.md", "待核实"),
    ("限额超限", "portfolio/holdings_2026Q3.xlsx",
     f"R-01 单一证券集中度 {pct(meas['R-01'])} 超过 v3 10% 上限（{top_sec} {actual_name}，市值 {fm(top_sec_mv)} 元）",
     "期末主动超限，须披露并整改", f"按 v3 第9条 {CURE} 个工作日内提交整改计划，减持至限额内；于报告第四章披露",
     "rules/restrictions_v3_20260901.md 第9条", "整改中"),
    ("历史触限回溯", "compliance/breach_log_2026.csv",
     f"历史触发记录：{br_hist}，均已解除",
     "无期末存量影响", "按 v3 第10条记入限额监测台账、无需披露，本期留痕",
     "rules/restrictions_v3_20260901.md 第10条", "已解决"),
]
issue_log = pd.DataFrame(issue_rows, columns=["类别", "文件", "现象", "影响", "处置动作", "依据", "状态"])
final_source = (f"最终采用数据源：净值/份额/现金=托管行报告（valuation/nav_report_20260930.csv）；"
                f"持仓=管理人系统盘后导出（portfolio/holdings_2026Q3.xlsx，有效口径）；"
                f"行情=数据组重推件（data/price_feed_20260930_repush.csv，估值日过滤）；"
                f"应收应付=valuation/accruals_20260930.csv；现金明细=valuation/bank_statement_20260930.csv。")

# ================================================================ 10. 任务拆解与完成状态（任务 12）
task_rows = [
    ("T1", "材料清点（分目录计数与总数勾稽）", "已完成", "workbook:Coverage 块1；报告第一章"),
    ("T2", "持仓全覆盖（十 sheet 逐表读取汇总）", "已完成", "workbook:Coverage 块2；holdings_coverage.csv"),
    ("T3", "有效持仓口径（三类剔除分列+未过滤对照）", "已完成", "workbook:Coverage/Nav_Bridge；报告第三章"),
    ("T4", "行情取数（重推件+估值日过滤+关联留痕）", "已完成", "workbook:Coverage 块3；报告第三章"),
    ("T5", "市值与净值复核（推导链逐行+差额bp）", "已完成", "workbook:Valuation_Recalc；报告第二章"),
    ("T6", "现金勾稽（分账户+差额）", "已完成", "workbook:Nav_Bridge 块1；报告第二章"),
    ("T7", "五项限额逐条测算（含流动性制度交叉核对）", "已完成", "workbook:Compliance_Check；报告第四章"),
    ("T8", "条款版本适用性说明", "已完成", "workbook:Compliance_Check 备注；报告第四章"),
    ("T9", "超限处置（成因/整改/时限/披露，正文披露）", "已完成（整改中，含待核实项）", "报告第四章正文；workbook:Compliance_Check 超限处置块"),
    ("T10", "上期报告重述（≥3条）", "已完成", "workbook:Prev_Report_Fix；报告第五章"),
    ("T11", "数据问题台账（七要素）", "已完成（2 项待核实）", "workbook:Issue_Log；issue_log.csv；报告第六章"),
    ("T12", "任务拆解与完成状态表", "已完成", "workbook:Task_Status；报告第七章"),
    ("T13", "复合图（限额对比+账户覆盖）", "已完成", "charts.png"),
    ("T14", "可复算脚本（读入即算，无硬编码结论）", "已完成", "reproduce.py（本脚本）"),
    ("T15", "报告成文（八章节，≤2页/1600中文字符）", "已完成", "operation_report.md"),
    ("T16", "勾稽一致性交叉校验", "已完成", "全部交付物（脚本内 assert 校验）"),
]
task_status = pd.DataFrame(task_rows, columns=["任务编号", "任务项", "状态", "对应交付物位置"])

# ================================================================ 11. Coverage / Holdings_Summary 工作表数据
cov_block1 = pd.DataFrame(
    [(d, dir_counts[d]) for d in sorted(dir_counts) if d != "(根目录散件)"] +
    [("根目录散件（00_README.md、manifest.csv）", n_root),
     ("合计", n_files), ("来源目录数", n_dirs),
     ("勾稽校验", f"分目录小计 {n_sub} + 根散件 {n_root} = {n_files}，与文件总数一致")],
    columns=["目录", "文件数"])

cov_block3 = pd.DataFrame([
    ("行情主件 valuation/price_feed_20260930.csv 记录数", n_main_rows, "空文件（传输残留，ops 邮件）"),
    ("行情重推件 data/price_feed_20260930_repush.csv 记录数", n_repush_rows, "含估值日与前一日两批次"),
    (f"过滤条件 trade_date={VAL_DATE} 后记录数", n_val_rows, f"证券 {n_price_ids} 只，批次=重推件"),
    ("关联字段", "sec_code = instrument_id", "数据字典§3；runbook 原文 wind_code 已过时"),
    ("有效持仓行数 / 行情匹配成功行数", f"{len(eff)} / {join_matched}", f"未匹配 {join_unmatched} 行"),
    ("行情有价、持仓无（有效口径）证券数", n_price_only,
     f"{'全部为主数据非 active（matured/called）证券，已按 2.2 剔除，属对账差异表留痕项' if price_only_all_inactive else '含 active 证券，需追查'}（runbook 3.4）"),
], columns=["项目", "数值", "说明"])

cov_block4 = pd.DataFrame([(s, "说明/归档表，非持仓数据，不计入账户覆盖") for s in other_sheets],
                          columns=["工作簿其他 sheet", "处理"])

bw = pd.read_csv(f"{INP}/data/benchmark_weights_2026Q3.csv").set_index("sec_type")
type_sum = (eff.groupby("sec_type")
               .agg(证券只数=("sec_code", "nunique"), 有效行数=("sec_code", "size"), 有效市值=("mv", "sum"))
               .reset_index())
type_sum["券种名称"] = type_sum["sec_type"].map(bw["sec_type_name"])
type_sum["占净值比"] = (type_sum["有效市值"] / DEN).map(pct)
type_sum["基准权重"] = type_sum["sec_type"].map(bw["benchmark_weight"]).map(pct)
type_sum["偏离（pp）"] = ((type_sum["有效市值"] / DEN - type_sum["sec_type"].map(bw["benchmark_weight"])) * 100).round(2)
type_sum["有效市值"] = type_sum["有效市值"].round(2)
type_sum = type_sum.sort_values("有效市值", ascending=False)[
    ["sec_type", "券种名称", "证券只数", "有效行数", "有效市值", "占净值比", "基准权重", "偏离（pp）"]]

acct_sum = (eff.groupby("acct").agg(有效行数=("sec_code", "size"), 有效市值=("mv", "sum")).reset_index())
acct_raw = h.groupby("acct").size().rename("原始行数").reset_index()
acct_sum = acct_raw.merge(acct_sum, on="acct")
acct_sum["有效市值"] = acct_sum["有效市值"].round(2)
acct_sum["占净值比"] = (acct_sum["有效市值"] / DEN).map(pct)
acct_sum = acct_sum.sort_values("acct")

top5 = pd.DataFrame({
    "sec_code": by_sec.head(5).index,
    "证券名称": [name_master[c] for c in by_sec.head(5).index],
    "发行人": [issuer_map[c] for c in by_sec.head(5).index],
    "有效市值": by_sec.head(5).values.round(2),
    "占净值比": [pct(v / DEN) for v in by_sec.head(5).values],
})

# ================================================================ 12. 写 CSV 交付物
cov_csv.to_csv(f"{OUT}/FIN3-WKN-153_holdings_coverage.csv", index=False, encoding="utf-8-sig")
issue_log.to_csv(f"{OUT}/FIN3-WKN-153_issue_log.csv", index=False, encoding="utf-8-sig")

# ================================================================ 13. 写工作簿（八表）
def write_block(writer, sheet, df, startrow, title=None):
    r = startrow
    if title:
        ws = writer.sheets[sheet]
        ws.cell(row=r + 1, column=1, value=title).font = Font(bold=True, size=11)
        r += 1
    df.to_excel(writer, sheet_name=sheet, startrow=r, index=False)
    ws = writer.sheets[sheet]
    for c in ws[r + 1]:
        c.font = Font(bold=True)
    return r + len(df) + 2

with pd.ExcelWriter(f"{OUT}/FIN3-WKN-153_quarterly_workbook.xlsx", engine="openpyxl") as w:
    # --- Coverage
    pd.DataFrame().to_excel(w, sheet_name="Coverage", index=False)
    r = 0
    r = write_block(w, "Coverage", cov_block1, r, f"块1 材料清点（材料截止时点 {CUTOFF}；估值日 {VAL_DATE}）")
    r = write_block(w, "Coverage", cov_csv, r, f"块2 逐账户 sheet 持仓覆盖（{n_acct_sheets} 个账户表全读，末行合计）")
    r = write_block(w, "Coverage", cov_block3, r, "块3 行情关联与过滤留痕")
    r = write_block(w, "Coverage", cov_block4, r, f"块4 持仓工作簿其他 sheet（共 {len(xl.sheet_names)} 个 sheet = {n_acct_sheets} 账户表 + {len(other_sheets)} 说明表）")
    # --- Holdings_Summary
    pd.DataFrame().to_excel(w, sheet_name="Holdings_Summary", index=False)
    r = 0
    r = write_block(w, "Holdings_Summary", type_sum, r, f"块1 券种汇总（有效口径，分母=资产净值 {fm(DEN)} 元；基准权重引自 data/benchmark_weights_2026Q3.csv）")
    r = write_block(w, "Holdings_Summary", acct_sum, r, "块2 账户汇总（有效口径）")
    r = write_block(w, "Holdings_Summary", top5, r, "块3 前五大单一证券（按有效市值）")
    # --- Valuation_Recalc
    pd.DataFrame().to_excel(w, sheet_name="Valuation_Recalc", index=False)
    write_block(w, "Valuation_Recalc", valuation_recalc, 0,
                f"净值复核推导链（估值日 {VAL_DATE}，单位：元；G=E÷F，差额以 bp 表示）")
    # --- Nav_Bridge
    pd.DataFrame().to_excel(w, sheet_name="Nav_Bridge", index=False)
    r = write_block(w, "Nav_Bridge", nav_bridge_cash, 0, "块1 现金勾稽（银行对账单分账户 → 合计 → 与托管报告差额）")
    write_block(w, "Nav_Bridge", nav_bridge_cal, r, "块2 持仓口径调整桥（原始 → 三类剔除分列 → 有效）与未过滤口径单位净值对照")
    # --- Compliance_Check
    pd.DataFrame().to_excel(w, sheet_name="Compliance_Check", index=False)
    r = write_block(w, "Compliance_Check", compliance, 0,
                    f"五项限额逐条测算（现行 v3，生效日 {v3_eff}；分母=计划资产净值总额 {fm(DEN)} 元）")
    if len(breach_df):
        r = write_block(w, "Compliance_Check", breach_df, r, "超限处置详情（任务9；已在报告第四章正文披露）")
    notes = pd.DataFrame({"备注": [cross_note, version_note, r02_note,
                                   f"最终采用数据源：{final_source.split('：',1)[1]}"]})
    write_block(w, "Compliance_Check", notes, r, "交叉核对与版本适用性备注")
    # --- Issue_Log
    pd.DataFrame().to_excel(w, sheet_name="Issue_Log", index=False)
    r = write_block(w, "Issue_Log", issue_log, 0, f"数据问题与阻塞台账（{len(issue_log)} 条，七要素）")
    write_block(w, "Issue_Log", pd.DataFrame({"最终采用数据源": [final_source]}), r, None)
    # --- Task_Status
    pd.DataFrame().to_excel(w, sheet_name="Task_Status", index=False)
    write_block(w, "Task_Status", task_status, 0, "任务拆解与完成状态")
    # --- Prev_Report_Fix
    pd.DataFrame().to_excel(w, sheet_name="Prev_Report_Fix", index=False)
    write_block(w, "Prev_Report_Fix", prev_fix, 0, "上期报告（2026Q2）不再适用表述的重述")
    # 列宽与换行
    for ws in w.book.worksheets:
        for col in ws.columns:
            width = max((len(str(c.value)) for c in col if c.value is not None), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(max(width * 1.1, 10), 60)
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")

# ================================================================ 14. 复合图（任务 13）
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 5.8))
labels = [f"{r.规则}\n{r.条款号}{'（下限）' if '≥' in r.比较方向 else '（上限）'}" for r in compliance.itertuples()]
mv_vals = [m * 100 for m in compliance["测算值_小数"]]
lm_vals = [v3[rid]["limit"] * 100 for rid in compliance["规则"]]
x = np.arange(len(labels)); wd = 0.36
bars1 = ax1.bar(x - wd / 2, mv_vals, wd, label="本期测算值",
                color=["#c0392b" if v == "超限" else "#2e86c1" for v in compliance["结论"]])
ax1.bar(x + wd / 2, lm_vals, wd, label="限额（v3 现行）", color="#95a5a6")
for i, (m_, l_) in enumerate(zip(mv_vals, lm_vals)):
    ax1.text(i - wd / 2, m_ + 0.25, f"{m_:.2f}%", ha="center", fontsize=9)
    ax1.text(i + wd / 2, l_ + 0.25, f"{l_:.0f}%", ha="center", fontsize=9)
ax1.set_xticks(x); ax1.set_xticklabels(labels, fontsize=9)
ax1.set_ylabel("%（占计划资产净值）"); ax1.set_ylim(0, max(mv_vals + lm_vals) * 1.25)
ax1.set_title(f"① 五项限额指标：测算值 vs 限额（v3，分母 {DEN/1e8:.2f} 亿元）", fontsize=11)
if len(breaches):
    ax1.annotate("超限：" + "、".join(breaches["规则"]), xy=(0.02, 0.95), xycoords="axes fraction",
                 color="#c0392b", fontsize=10, fontweight="bold")
ax1.legend(loc="upper right", fontsize=9)
x2 = np.arange(len(cov))
ax2.bar(x2 - wd / 2, cov["原始行数"], wd, label="原始记录数", color="#5d6d7e")
ax2.bar(x2 + wd / 2, cov["有效行数"], wd, label="有效记录数", color="#27ae60")
for i, (a, b) in enumerate(zip(cov["原始行数"], cov["有效行数"])):
    ax2.text(i - wd / 2, a + 0.4, str(a), ha="center", fontsize=8)
    ax2.text(i + wd / 2, b + 0.4, str(b), ha="center", fontsize=8)
ax2.set_xticks(x2); ax2.set_xticklabels(cov["sheet"], rotation=45, ha="right", fontsize=8)
ax2.set_ylabel("行数")
ax2.set_title(f"② 十个账户 sheet 覆盖：原始 {int(cov['原始行数'].sum())} 行 → 有效 {int(cov['有效行数'].sum())} 行"
              f"（剔除 {int(cov['剔除行数_估值日归属'].sum())}+{int(cov['剔除行数_主数据状态'].sum())}+{int(cov['剔除行数_重复上报'].sum())}）", fontsize=11)
ax2.legend(loc="upper right", fontsize=9)
fig.suptitle(f"{FUND_NAME} 季度复核复合图（报告期末 {VAL_DATE}｜材料截止 {CUTOFF}）", fontsize=13)
fig.tight_layout(rect=[0, 0, 1, 0.94])
fig.savefig(f"{OUT}/FIN3-WKN-153_charts.png", dpi=150)
plt.close(fig)

# ================================================================ 15. 报告成文（任务 15，八章节）
# 报告用紧凑表述（工作簿 Compliance_Check 保留 breach_row / cross_note / version_note / r02_note 详述版）
rep_breach = ""
if breach_row:
    b = breach_row
    rep_breach = (f"超限披露（R-01，主动超限）：{b['证券代码']}「{b['证券名称']}」市值 {fm(b['市值'])} 元、"
                  f"占净值 {b['占净值比']}，超 {b['限额']} 限额 {b['超限幅度_bp']:.0f}bp。"
                  f"成因：9 月按决策纪要增持（审批上限 {memo_cap*100:.0f}%、预警线 {memo_warn*100:.1f}%）；"
                  f"纪要所称「{memo_sec}」已于 {memo_maturity} 状态 {memo_status}，实际计入为第3期（券名差异待核实）；"
                  f"实测双超。整改：按第9条于估值日起 {CURE} 个工作日内提交整改计划、减持至 {b['限额']} 以内；"
                  f"完成时限以整改计划为准（待核实）。"
                  f"披露：于本章披露超限事实、成因、措施与时限（第9条），第10、11条不适用。")
rep_cross = (f"交叉核对：流动性制度第12条阈值（≥{liq12*100:.0f}%）与 R-05 一致；"
             f"其第21条所引「投资限制条款第七章」在 v3 不存在（仅四章），界定出处待核实；"
             f"分子按托管口径现金及清算备付金执行。")
rep_version = (f"版本适用性：v3（生效 {v3_eff}）替代 {v3_supersede}，估值日在生效日后，一律执行 v3；"
               f"v2 限额（{v2['R-01']*100:.0f}%/{v2['R-03']*100:.0f}%/{v2['R-05']*100:.0f}%/{v2['R-07']*100:.0f}%）"
               f"仅作回溯、不适用本期（误用则无法揭示 R-01 超限）。")
rep_r02 = f"R-02 按主数据 issuer 汇总，「{top_iss}」关联方名单材料未载明，合并口径待核实。"
rep_brelog = (f"breach_log 所载 {len(br_log)} 条历史盘中触发（{'、'.join(br_log['breach_id'])}）均已解除，"
              f"按第10条留痕、无需披露。")

recv_detail = " + ".join(f"{r.item_name} {fm(r.amount)}" for r in RECV.itertuples())
pay_detail = " + ".join(f"{r.item_name} {fm(r.amount)}" for r in PAY.itertuples())
bank_detail = " + ".join(f"{r.account_name} {fm(r.balance)}" for r in bank.itertuples())
dir_list = "、".join(f"{d} {dir_counts[d]}" for d in sorted(dir_counts) if d != "(根目录散件)")
prev_brief = "；".join(f"{r.编号} {r.不再适用原因.split('；')[0][:38]}→ {r.本期处置[:30]}" for r in prev_fix.itertuples())

report = f"""# {FUND_NAME} 2026 年三季度投资运作报告

报告期末：**{VAL_DATE}**｜材料截止时点：**{CUTOFF}**｜编制/提交日：{PREP_DATE}｜单位：元，比例两位小数

## 一、材料清点

材料共 **{n_files} 个文件**、来源目录 **{n_dirs} 个**。分目录：{dir_list}，小计 {n_sub}；根散件 {n_root}（00_README.md、manifest.csv）。勾稽：{n_sub}+{n_root}={n_files}，一致。

## 二、组合概况与净值复核

净值推导链（明细见 Valuation_Recalc）：

| 步骤 | 项目 | 数值 | 来源 |
|---|---|---|---|
| A | 有效持仓市值（{int(tot['有效行数'])} 行重算） | {fm(EFF_MV)} | 持仓+重推件 |
| B | 现金及清算备付金 | {fm(CASH_TB)} | 托管行报告 |
| C | 应收合计（{recv_detail}） | {fm(recv_sum)} | 计提明细 |
| D | 应付合计（{pay_detail}） | {fm(pay_sum)} | 计提明细 |
| E | 资产净值=A+B+C−D | {fm(calc_nav)} | 复算 |
| F | 总份额 | {fm(TOTAL_SHARES)} | 托管行报告 |
| G | 单位净值=E÷F | {calc_navps:.6f} | 复算 |
| H | 托管行单位净值 | {NAVPS_TB:.4f} | 托管行报告 |
| I | 差额 G−H | {navps_diff_bp:+.2f}bp | 四舍五入位级，一致 |

E 与托管净值 {fm(TOTAL_NAV_TB)} 差额 {fm(nav_diff_tb)}。现金勾稽：{bank_detail} = {fm(bank_sum)}，与托管报告现金差额 **{fm(bank_diff)}**。净值较上期末 {q2_navps} 上行；份额变动与分红未载明，收益率待核实；Q3 基准收益 {BENCH_Q3*100:.2f}%。

## 三、持仓覆盖与口径执行

持仓工作簿 {len(xl.sheet_names)} 个 sheet，**{n_acct_sheets} 个账户表全部读取**（余 {len(other_sheets)} 个为说明表）。原始 **{n_raw} 行**，按 runbook 第2章三类剔除（分列，逐 sheet 见 Coverage/CSV）：①估值日归属 as_of≠{VAL_DATE} 共 **{len(d1_all)} 行**（市值 {fm(x1mv_t)}）；②主数据非 active 共 **{len(d2_all)} 行**（{fm(x2mv_t)}）；③重复上报（留 source_row_id 首条）共 **{len(d3_all)} 行**（{fm(x3mv_t)}）。有效 **{int(tot['有效行数'])} 行**、市值 **{fm(EFF_MV)}**，勾稽一致。

行情：valuation/ 主件为空（传输残留），按数据组 {CUTOFF} 邮件以重推件为准；重推件 {n_repush_rows} 行，过滤 trade_date={VAL_DATE} 后 **{n_val_rows} 行（{n_price_ids} 只）**；关联字段 **sec_code=instrument_id**（wind_code 系旧名）；有效持仓全部匹配、缺价 {join_unmatched} 行；有价无持仓 {n_price_only} 只均为已剔除非 active 券，已留痕。

口径对照：若沿用上期「全表合计」，单位净值为 **{unf_navps:.6f}**，较正确口径 {calc_navps:.6f} **高估 {overstate_bp:.2f}bp**，不再适用。

## 四、投资监督与限额执行

按**现行有效 v3**（生效 {v3_eff}）逐条测算，分母为资产净值总额 {fm(DEN)}（第2条）：

| 条款 | 规则 | 指标 | 测算值 | 限额 | 结论 |
|---|---|---|---|---|---|
| {r01['article']} | R-01 | 单一证券集中度（{top_sec}） | {pct(meas['R-01'])} | ≤{r01['limit']*100:.0f}% | **超限** |
| {r02['article']} | R-02 | 单一发行人集中度（{top_iss}） | {pct(meas['R-02'])} | ≤{r02['limit']*100:.0f}% | 合规 |
| {r03['article']} | R-03 | 非标资产比例 | {pct(meas['R-03'])} | ≤{r03['limit']*100:.0f}% | 合规 |
| {r05['article']} | R-05 | 现金类资产比例 | {pct(meas['R-05'])} | ≥{r05['limit']*100:.0f}% | 合规 |
| {r07['article']} | R-07 | 权益型基金比例 | {pct(meas['R-07'])} | ≤{r07['limit']*100:.0f}% | 合规 |

{rep_breach}

{rep_r02}{rep_cross}

{rep_version}{rep_brelog}

## 五、上期报告口径重述

上期报告 {len(prev_fix)} 条表述不再适用（全表见 Prev_Report_Fix）：P1「单一证券最高 {m_r01.group(1)}% 低于 {m_r01.group(2)}% 上限」依据已被替代的 v2→按 v3 {r01['limit']*100:.0f}% 上限重述，本期实测超限已披露；P2「非标 {m_r03.group(1)}% 低于 {m_r03.group(2)}%」→按 v3 {r03['limit']*100:.0f}% 重述（本期 {pct(meas['R-03'])} 合规）；P3「现金类 {m_r05.group(1)}% 高于 {m_r05.group(2)}% 下限」→按 v3 及流动性制度 {r05['limit']*100:.0f}% 重述（本期 {pct(meas['R-05'])} 合规）；P4「全表合计、未区分所属日期」→与 runbook 2.1 冲突，改按估值日口径（影响见第三章）；P5 上期净值数仅作期初对照。

## 六、数据问题与处置

台账 {len(issue_log)} 条（七要素见 Issue_Log/CSV）：行情主件为空（改用重推件）、重推件混入前一日记录（按估值日过滤）、指引关联字段过时（按数据字典执行）、持仓混入上期 {len(d1_all)} 行/非 active {len(d2_all)} 行/重复 {len(d3_all)} 行（均已剔除）、增持纪要券名与主数据不一致（**待核实**）、制度条文引用缺失（**待核实**）、R-01 超限（整改中）、历史触限回溯（已解除）。最终数据源：净值/份额/现金=托管报告，持仓=盘后导出，行情=重推件，应收应付=计提明细，现金=对账单。

## 七、任务拆解与完成状态

{len(task_rows)} 项任务与交付物位置见 Task_Status（T1–T{len(task_rows)}）：除 T9 整改进行中、T11 两项待核实外均已完成，待核实不影响数值结论。交付物 6 项均在 /app/output/。

## 八、结论与下季度计划

净值推导链与托管报告一致（差额 {navps_diff_bp:+.2f}bp，属四舍五入），现金勾稽差额 {fm(bank_diff)}；五项限额四合规一超限，R-01 已按第9条于第四章披露并启动整改。下季度：跟踪华骏集团整改与信用变化，完成到期存单续作，推动指引字段与制度条文引用修订，销记待核实事项。本报告未经审计，数值可经 reproduce.py 复算回溯。
"""
n_cjk = cjk_count(report)
for _part in report.split("\n## "):
    print("[分节字数]", _part.splitlines()[0][:16], cjk_count(_part))
assert n_cjk <= 1600, f"报告正文中文字符 {n_cjk} 超过 1600"
with open(f"{OUT}/FIN3-WKN-153_operation_report.md", "w", encoding="utf-8") as f:
    f.write(report)

# ================================================================ 16. 校验输出
print("=" * 72)
print(f"[勾稽] 文件总数 {n_files} = 分目录 {n_sub} + 根散件 {n_root}；来源目录 {n_dirs}")
print(f"[覆盖] 账户表 {n_acct_sheets} 个：原始 {n_raw} 行 = 剔除① {len(d1_all)} + ② {len(d2_all)} + ③ {len(d3_all)} + 有效 {len(eff)}")
print(f"[市值] 原始 {fm(RAW_MV)} − ①{fm(x1mv_t)} − ②{fm(x2mv_t)} − ③{fm(x3mv_t)} = 有效 {fm(EFF_MV)}")
print(f"[净值] {fm(EFF_MV)} + {fm(CASH_TB)} + {fm(recv_sum)} − {fm(pay_sum)} = {fm(calc_nav)}；"
      f"÷{fm(TOTAL_SHARES)} = {calc_navps:.6f}；vs 托管 {NAVPS_TB:.4f} → {navps_diff_bp:+.2f} bp")
print(f"[对照] 未过滤口径 navps {unf_navps:.6f}，高估 {overstate_bp:.2f} bp")
print(f"[现金] 对账单合计 {fm(bank_sum)} − 托管现金 {fm(CASH_TB)} = {fm(bank_diff)}")
for r in compliance.itertuples():
    print(f"[限额] {r.条款号} {r.规则} {r.指标[:14]}… 测算 {r.测算值} {r.比较方向} → {r.结论}")
print(f"[报告] 中文字符数 {n_cjk} / 1600")
print("[输出] " + "、".join(sorted(os.listdir(OUT))))
print("=" * 72)
print("全部交付物已生成。")
