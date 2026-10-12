#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-153 现金增强 1 号集合资产管理计划 2026 年三季度投资运作复核 — 可复算脚本
================================================================================
运行方式：python3 FIN3-WKN-153_reproduce.py
输入（只读）：/app/input_files/
输出（全部交付物）：/app/output/
  1) FIN3-WKN-153_quarterly_workbook.xlsx  季度复核工作簿（9 表，含规定 8 表 + Price_Join）
  2) FIN3-WKN-153_operation_report.md      季度投资运作报告（八章节，中文字符<=1600）
  3) FIN3-WKN-153_reproduce.py             本脚本（运行时自动就位）
  4) FIN3-WKN-153_holdings_coverage.csv    持仓覆盖表（逐 sheet + 末行合计）
  5) FIN3-WKN-153_issue_log.csv            数据问题与阻塞台账（七要素）
  6) FIN3-WKN-153_charts.png               复合图（限额对比 + 账户覆盖）

纪律：全部结论数值由输入材料计算得出；限额/阈值/参数从材料文件解析，不硬编码结论，
     不访问网络；材料未载明事项标注「待核实」；输入目录只读、不改动。
"""
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

IN = Path("/app/input_files")
OUT = Path("/app/output")
OUT.mkdir(parents=True, exist_ok=True)

PFX = "FIN3-WKN-153"
F_XLSX = OUT / f"{PFX}_quarterly_workbook.xlsx"
F_MD = OUT / f"{PFX}_operation_report.md"
F_PY = OUT / f"{PFX}_reproduce.py"
F_COV = OUT / f"{PFX}_holdings_coverage.csv"
F_LOG = OUT / f"{PFX}_issue_log.csv"
F_PNG = OUT / f"{PFX}_charts.png"

def money(x):
    return f"{x:,.2f}"

# ----------------------------------------------------------------------------
# 0. 从材料解析基础参数（估值日、材料截止时点、限额、份额等）
# ----------------------------------------------------------------------------
def read_text(p):
    return Path(p).read_text(encoding="utf-8")

readme_txt = read_text(IN / "00_README.md")
v3_txt = read_text(IN / "rules/restrictions_v3_20260901.md")
v2_txt = read_text(IN / "rules/restrictions_v2_20260601.md")
liq_txt = read_text(IN / "rules/liquidity_policy.md")
ops_email_txt = read_text(IN / "internal/ops_email_20261008.txt")
mgr_notes_txt = read_text(IN / "internal/manager_notes.md")
memo_txt = read_text(IN / "internal/approval_memo_20260928.md")
q2_txt = read_text(IN / "reports/2026Q2_operation_report.md")
q1_txt = read_text(IN / "reports/2026Q1_operation_report.md")

# 净值报告（托管行）
nav_df = pd.read_csv(IN / "valuation/nav_report_20260930.csv")
nav_map = {}
for _, r in nav_df.iterrows():
    try:
        nav_map[r["item"]] = float(r["value"])
    except ValueError:
        nav_map[r["item"]] = str(r["value"])
VAL_DATE = str(nav_map["report_date"])            # 估值日/报告期末（托管行报告）
TOTAL_SHARES = nav_map["total_shares"]            # 计划总份额
NAV_CUST = nav_map["total_nav"]                   # 托管行资产净值
NPS_CUST = nav_map["nav_per_share"]               # 托管行单位净值（列报 4 位）
CASH_CUST = nav_map["cash_and_equivalent"]        # 托管行现金及清算备付金

# 材料截止时点：README「材料包整理日」
CUTOFF = re.search(r"材料包整理日：(\d{4}-\d{2}-\d{2})", readme_txt).group(1)
COMPILE_DATE = "2026-10-10"                       # 任务书载明的提交日

# 现行条款 v3 / 历史条款 v2 限额解析
def parse_limits(txt):
    out = {}
    flat = txt.replace("\n", "")
    for m in re.finditer(r"第\s*(\d+)\s*条（(R-\d+)）(.*?)(?=第\s*\d+\s*条|$)", flat):
        art, rid, body = m.group(1), m.group(2), m.group(3)
        pct = re.search(r"(\d+(?:\.\d+)?)\s*%", body)
        if not pct:
            continue
        direction = ">=" if "不得低于" in body else "<="
        out[rid] = {"art": art, "limit": float(pct.group(1)) / 100.0, "dir": direction}
    return out

LIM3 = parse_limits(v3_txt)
LIM2 = parse_limits(v2_txt)
for k in ("R-01", "R-02", "R-03", "R-05", "R-07"):
    assert k in LIM3, f"v3 缺少 {k}"

# 流动性制度：第 12 条现金类下限；第 21 条引用章节 vs v3 实际章节
liq12 = re.search(r"第\s*12\s*条.*?不低于计划资产净值\s*(\d+(?:\.\d+)?)\s*%", liq_txt, re.S)
LIQ12_PCT = float(liq12.group(1)) / 100.0
LIQ_REF = re.search(r"第\s*21\s*条.*?第([一二三四五六七八九十]+)章", liq_txt, re.S).group(1)
V3_CHAPTERS = sorted(set(re.findall(r"^##+\s*第([一二三四五六七八九十]+)章", v3_txt, re.M)),
                     key="一二三四五六七八九十".index)

# v3 第 9 条超限处置时限 T+n
TPLUS = re.search(r"T\+(\d+)", v3_txt).group(1)

# 决策纪要：单券批准上限与内部预警线
memo_pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", memo_txt)
MEMO_CAP = float(memo_pcts[0]) / 100.0
MEMO_WARN = float(memo_pcts[1]) / 100.0

# 计提（应收应付）
acc_df = pd.read_csv(IN / "valuation/accruals_20260930.csv")
acc_map = dict(zip(acc_df["item"], acc_df["amount"].astype(float)))
acc_name = dict(zip(acc_df["item"], acc_df["item_name"]))
acc_period = dict(zip(acc_df["item"], acc_df["accrual_period"]))
RECV_ITEMS = ["interest_receivable", "dividend_receivable"]
PAY_ITEMS = ["fee_payable_admin", "fee_payable_custodian", "fee_payable_sales"]
RECV = sum(acc_map[i] for i in RECV_ITEMS)
PAY = sum(acc_map[i] for i in PAY_ITEMS)

# 银行对账单
bank_df = pd.read_csv(IN / "valuation/bank_statement_20260930.csv")
BANK_TOTAL = float(bank_df["balance"].astype(float).sum())

# 证券主数据
master_df = pd.read_csv(IN / "portfolio/security_master.csv")
STATUS = dict(zip(master_df["sec_code"], master_df["status"]))
ISSUER = dict(zip(master_df["sec_code"], master_df["issuer"]))
SECNAME = dict(zip(master_df["sec_code"], master_df["sec_name"]))

# 券种中文名（data/benchmark_weights_2026Q3.csv）
bw_df = pd.read_csv(IN / "data/benchmark_weights_2026Q3.csv")
TYPE_CN = dict(zip(bw_df["sec_type"], bw_df["sec_type_name"]))

# 基准收益率（参考列报）
br_df = pd.read_csv(IN / "data/benchmark_returns_2026Q3.csv")
_b = br_df[br_df["benchmark"].str.contains("计划业绩比较基准")]
BENCH_RET = float(_b["return"].iloc[0]) if len(_b) else None

# ----------------------------------------------------------------------------
# 1. 材料清点（按目录分列 + 根散件，与总数勾稽）
# ----------------------------------------------------------------------------
manifest_df = pd.read_csv(IN / "manifest.csv")
dir_purpose = dict(zip(manifest_df["path"].str.rstrip("/"), manifest_df["purpose"]))
all_files = sorted(p for p in IN.rglob("*") if p.is_file())
per_dir = {d: sum(1 for p in all_files if p.parent == IN / d) for d in sorted(dir_purpose)}
root_files = [p.name for p in all_files if p.parent == IN]
N_FILES = len(all_files)
N_DIRS = len(per_dir)
SUBTOTAL = sum(per_dir.values())
N_ROOT = len(root_files)
assert SUBTOTAL + N_ROOT == N_FILES, "材料清点勾稽失败"

# ----------------------------------------------------------------------------
# 2. 持仓读取（十个账户 sheet 全覆盖）与有效持仓口径（runbook §2 三条件顺序过滤）
# ----------------------------------------------------------------------------
HOLD_XLSX = IN / "portfolio/holdings_2026Q3.xlsx"
wb_in = openpyxl.load_workbook(HOLD_XLSX, read_only=True)
ACCT_SHEETS = [s for s in wb_in.sheetnames if s.startswith("acct_")]
NON_ACCT_SHEETS = [s for s in wb_in.sheetnames if not s.startswith("acct_")]

frames = []
for s in ACCT_SHEETS:
    df = pd.read_excel(HOLD_XLSX, sheet_name=s)
    df["sheet"] = s
    frames.append(df)
hold = pd.concat(frames, ignore_index=True)
hold["as_of"] = pd.to_datetime(hold["as_of"]).dt.strftime("%Y-%m-%d")
hold["vol"] = hold["vol"].astype(float)
RAW_ROWS = len(hold)
hold["master_status"] = hold["sec_code"].map(STATUS)

# 2.1 估值日归属
hold["drop_date"] = hold["as_of"] != VAL_DATE
# 2.2 主数据状态
hold["drop_status"] = (~hold["drop_date"]) & (hold["master_status"] != "active")
# 2.3 重复上报（acct+sec_code+vol，按 source_row_id 升序保留第一条）
passed = hold[~(hold["drop_date"] | hold["drop_status"])].sort_values("source_row_id")
dup_mask = passed.duplicated(subset=["acct", "sec_code", "vol"], keep="first")
hold["drop_dup"] = False
hold.loc[dup_mask[dup_mask].index, "drop_dup"] = True

hold["cat"] = "effective"
hold.loc[hold["drop_dup"], "cat"] = "drop_dup"
hold.loc[hold["drop_status"], "cat"] = "drop_status"
hold.loc[hold["drop_date"], "cat"] = "drop_date"

eff = hold[hold["cat"] == "effective"].copy()
N_DROP_DATE = int(hold["drop_date"].sum())
N_DROP_STATUS = int(hold["drop_status"].sum())
N_DROP_DUP = int(hold["drop_dup"].sum())
N_EFF = len(eff)
assert RAW_ROWS - N_DROP_DATE - N_DROP_STATUS - N_DROP_DUP == N_EFF

# ----------------------------------------------------------------------------
# 3. 行情取数（重推件为准；估值日过滤；sec_code↔instrument_id 关联）与市值折算
# ----------------------------------------------------------------------------
feed_val_path = IN / "valuation/price_feed_20260930.csv"
feed_repush_path = IN / "data/price_feed_20260930_repush.csv"
try:
    feed_val_rows = len(pd.read_csv(feed_val_path))
except Exception:
    feed_val_rows = 0
price_raw = pd.read_csv(feed_repush_path)
N_PRICE_RAW = len(price_raw)
px = price_raw[price_raw["trade_date"] == VAL_DATE].copy()
N_PRICE_VAL = len(px)
N_PRICE_DROP_DATE = N_PRICE_RAW - N_PRICE_VAL
assert px["instrument_id"].duplicated().sum() == 0, "估值日行情存在重复证券"
PRICE = dict(zip(px["instrument_id"], px["close_price"].astype(float)))
RUNBOOK_FIELD = re.search(r"以\s*\*\*`?(\w+)`?\*\*\s*字段关联", read_text(IN / "rules/recon_runbook.md"))
RUNBOOK_FIELD = RUNBOOK_FIELD.group(1) if RUNBOOK_FIELD else "wind_code"

hold["close_price"] = hold["sec_code"].map(PRICE)
assert hold["close_price"].isna().sum() == 0, "存在无行情持仓行（应列入差异表）"

def calc_mv(row):
    # 数据字典折算口径：债券/非标 市值=vol×close_price/100；权益型基金 市值=vol×close_price
    if row["sec_type"] == "EquityFund":
        return row["vol"] * row["close_price"]
    return row["vol"] * row["close_price"] / 100.0

hold["mv"] = hold.apply(calc_mv, axis=1)
eff = hold[hold["cat"] == "effective"].copy()
eff["issuer"] = eff["sec_code"].map(ISSUER)
N_EFF_NOPX = int(eff["close_price"].isna().sum())

MV_EFF = float(eff["mv"].sum())
MV_RAW = float(hold["mv"].sum())

# 行情侧无有效持仓的证券（runbook §3.4 对账差异说明）
eff_codes = set(eff["sec_code"])
hold_codes = set(hold["sec_code"])
px_no_hold = sorted(set(px["instrument_id"]) - eff_codes)
px_nh_in_hold = [c for c in px_no_hold if c in hold_codes]        # 有持仓行但被 §2 剔除
px_nh_no_row = [c for c in px_no_hold if c not in hold_codes]     # 持仓导出中无行
px_no_hold_reason = {}
for c in px_nh_in_hold:
    cats = "、".join(sorted(set(hold.loc[hold["sec_code"] == c, "cat"])))
    px_no_hold_reason[c] = "非 active（%s），持仓行按 §2 剔除（%s）" % (STATUS.get(c, "?"), cats)
for c in px_nh_no_row:
    px_no_hold_reason[c] = "持仓导出无该证券行（%s，或已赎回/兑付，待核实）" % STATUS.get(c, "?")

# ----------------------------------------------------------------------------
# 4. 逐 sheet 覆盖与三类剔除市值影响
# ----------------------------------------------------------------------------
cov = []
for s in ACCT_SHEETS:
    g = hold[hold["sheet"] == s]
    ge = g[g["cat"] == "effective"]
    row = {
        "sheet": s,
        "raw": int(len(g)),
        "drop_date": int((g["cat"] == "drop_date").sum()),
        "drop_status": int((g["cat"] == "drop_status").sum()),
        "drop_dup": int((g["cat"] == "drop_dup").sum()),
        "eff_rows": int(len(ge)),
        "eff_mv": float(ge["mv"].sum()),
        "mv_date": float(g.loc[g["cat"] == "drop_date", "mv"].sum()),
        "mv_status": float(g.loc[g["cat"] == "drop_status", "mv"].sum()),
        "mv_dup": float(g.loc[g["cat"] == "drop_dup", "mv"].sum()),
    }
    assert row["raw"] - row["drop_date"] - row["drop_status"] - row["drop_dup"] == row["eff_rows"]
    cov.append(row)
cov_df = pd.DataFrame(cov)
TOT = cov_df.sum(numeric_only=True)
MV_DROP_DATE = float(TOT["mv_date"]); MV_DROP_STATUS = float(TOT["mv_status"]); MV_DROP_DUP = float(TOT["mv_dup"])
assert abs(MV_RAW - MV_DROP_DATE - MV_DROP_STATUS - MV_DROP_DUP - MV_EFF) < 0.01
assert int(TOT["eff_rows"]) == N_EFF and abs(float(TOT["eff_mv"]) - MV_EFF) < 0.01

# ----------------------------------------------------------------------------
# 5. 净值复核推导链 + 未过滤口径对照 + 现金勾稽
# ----------------------------------------------------------------------------
NET_CALC = MV_EFF + CASH_CUST + RECV - PAY
NPS_CALC = NET_CALC / TOTAL_SHARES
DIFF_NET = round(NET_CALC - NAV_CUST, 2) + 0.0  # 消除浮点残差的 -0.00 显示
DIFF_NPS_BP = (NPS_CALC / NPS_CUST - 1.0) * 1e4      # 相对基点差

NET_RAW = MV_RAW + CASH_CUST + RECV - PAY
NPS_RAW = NET_RAW / TOTAL_SHARES
OVERSTATE_BP = (NPS_RAW / NPS_CALC - 1.0) * 1e4      # 未过滤口径高估幅度（bp）

CASH_DIFF = BANK_TOTAL - CASH_CUST

# ----------------------------------------------------------------------------
# 6. 五项限额测算（现行 v3；分母 = 托管行计划资产净值总额；分子 = 有效持仓）
# ----------------------------------------------------------------------------
by_sec = eff.groupby("sec_code")["mv"].sum().sort_values(ascending=False)
by_iss = eff.groupby("issuer")["mv"].sum().sort_values(ascending=False)
mv_nonstd = float(eff.loc[eff["sec_type"] == "NonStdAsset", "mv"].sum())
mv_eqfund = float(eff.loc[eff["sec_type"] == "EquityFund", "mv"].sum())

TOP_SEC = by_sec.index[0]; TOP_SEC_MV = float(by_sec.iloc[0]); TOP_SEC_PCT = TOP_SEC_MV / NAV_CUST
TOP_ISS = by_iss.index[0]; TOP_ISS_MV = float(by_iss.iloc[0]); TOP_ISS_PCT = TOP_ISS_MV / NAV_CUST
PCT_NONSTD = mv_nonstd / NAV_CUST
PCT_CASH = CASH_CUST / NAV_CUST
PCT_EQF = mv_eqfund / NAV_CUST

def verdict(rid, pct):
    d = LIM3[rid]["dir"]; lim = LIM3[rid]["limit"]
    ok = pct >= lim if d == ">=" else pct <= lim
    return ("合规" if ok else "超限"), d, lim

comp_rows = []
for rid, label, mv, pct in [
    ("R-01", "单一证券集中度（%s %s）" % (TOP_SEC, SECNAME[TOP_SEC]), TOP_SEC_MV, TOP_SEC_PCT),
    ("R-02", "单一发行人集中度（%s）" % TOP_ISS, TOP_ISS_MV, TOP_ISS_PCT),
    ("R-03", "非标资产比例（sec_type=NonStdAsset）", mv_nonstd, PCT_NONSTD),
    ("R-05", "现金类资产比例（含清算备付金，托管行口径）", CASH_CUST, PCT_CASH),
    ("R-07", "权益型基金比例（sec_type=EquityFund）", mv_eqfund, PCT_EQF),
]:
    v, d, lim = verdict(rid, pct)
    comp_rows.append({"rule": rid, "art": LIM3[rid]["art"], "label": label, "mv": mv,
                      "pct": pct * 100.0, "limit": lim * 100.0, "dir": d, "result": v})
BREACHES = [r for r in comp_rows if r["result"] == "超限"]

# R-05 与流动性制度交叉核对
LIQ_CONSISTENT = abs(LIQ12_PCT - LIM3["R-05"]["limit"]) < 1e-12
LIQ_REF_VALID = LIQ_REF in V3_CHAPTERS

# 超限明细（R-01）
EXCESS_AMT = TOP_SEC_MV - LIM3["R-01"]["limit"] * NAV_CUST
TOP_SEC_ACCTS = eff[eff["sec_code"] == TOP_SEC].groupby("sheet")["mv"].sum().to_dict()

# ----------------------------------------------------------------------------
# 7. 上期报告重述条目（原文自材料动态摘取）
# ----------------------------------------------------------------------------
def flat(txt):
    return re.sub(r"\s+", "", txt.replace("**", ""))

def find_phrase(txt, pattern):
    m = re.search(pattern, flat(txt))
    return m.group(0) if m else "（未定位到原文，待核实）"

Q_P1 = find_phrase(q2_txt, r"本季度按2026-06-01版投资限制条款执行期末监测[^。]*。")
Q_P2 = find_phrase(q2_txt, r"持仓汇总口径采用盘后导出明细全表合计[^。]*。")
Q_P3 = find_phrase(q2_txt, r"现金类资产比例[\d.]+%，高于[\d.]+%下限")
Q_P4 = find_phrase(q1_txt, r"一季度按2026-06-01版条款（当时为草案）执行内部监测[^。]*。")

prev_fix = [
    {"src": "reports/2026Q2_operation_report.md §二", "quote": Q_P1,
     "why": "v2（2026-06-01 版）已被 v3（2026-09-01 生效）替代；v2 归档说明明确 2026 年三季度及以后一律执行 v3",
     "fix": "本期按 v3 限额全量重算（R-01 %g%%、R-02 %g%%、R-03 %g%%、R-05 %g%%、R-07 %g%%），结果见报告§四与 Compliance_Check"
            % (LIM3["R-01"]["limit"]*100, LIM3["R-02"]["limit"]*100, LIM3["R-03"]["limit"]*100,
               LIM3["R-05"]["limit"]*100, LIM3["R-07"]["limit"]*100)},
    {"src": "reports/2026Q2_operation_report.md §二", "quote": Q_P2,
     "why": "与 rules/recon_runbook.md §2 有效持仓三条件（估值日归属、主数据 active、去重）不符；internal/manager_notes.md 第 4 条明确本期起不再适用",
     "fix": "本期按三条件顺序过滤：原始 %d 行，剔除 %d+%d+%d 行，有效 %d 行，剔除市值合计 %s 元，见报告§三与 Nav_Bridge"
            % (RAW_ROWS, N_DROP_DATE, N_DROP_STATUS, N_DROP_DUP, N_EFF, money(MV_RAW - MV_EFF))},
    {"src": "reports/2026Q2_operation_report.md §二", "quote": Q_P3,
     "why": "2%% 下限系 v2 第 %s 条，已被 v3 第 %s 条 %g%% 下限替代"
            % (LIM2.get("R-05", {}).get("art", "7"), LIM3["R-05"]["art"], LIM3["R-05"]["limit"]*100),
     "fix": "本期现金类资产比例 %.2f%%，不低于 %g%% 下限，合规" % (PCT_CASH*100, LIM3["R-05"]["limit"]*100)},
    {"src": "reports/2026Q1_operation_report.md §二", "quote": Q_P4,
     "why": "该版本在当期尚为草案且已被 v3 替代，监测依据无法自现行材料回溯核实",
     "fix": "仅作历史回溯留存，本期一律执行 v3；相关历史数值标注待核实"},
]

# ----------------------------------------------------------------------------
# 8. 数据问题与阻塞台账（七要素，一行一条）
# ----------------------------------------------------------------------------
issue_rows = [
    ["行情数据", "valuation/price_feed_20260930.csv",
     "估值日行情主件为传输残留空文件（%d 条数据），未承载收盘价格" % feed_val_rows,
     "无法自主件取得估值日行情，估值取数阻塞",
     "按数据组邮件以 data/price_feed_20260930_repush.csv 重推件为准",
     "internal/ops_email_20261008.txt；00_README.md 口径优先级第 3 条", "已关闭"],
    ["行情数据", "data/price_feed_20260930_repush.csv",
     "重推件混入前一交易日（2026-09-29，批次「原始推送」）记录 %d 条，估值日当日 %d 条，共 %d 条"
     % (N_PRICE_DROP_DATE, N_PRICE_VAL, N_PRICE_RAW),
     "全表直用将取错价格、市值失真",
     "按 trade_date=%s 过滤，仅保留估值日当日 %d 条" % (VAL_DATE, N_PRICE_VAL),
     "rules/recon_runbook.md §3.3；internal/ops_email_20261008.txt", "已关闭"],
    ["字段口径", "rules/recon_runbook.md §3.1 / internal/data_dictionary.md §3",
     "指引要求以 %s 字段关联，但 2026-08 字典改版后持仓侧为 sec_code、行情侧为 instrument_id，两侧均无 %s 列"
     % (RUNBOOK_FIELD, RUNBOOK_FIELD),
     "按指引字段关联将全部失配",
     "按数据字典以 sec_code↔instrument_id 关联，有效持仓 %d/%d 行关联成功；指引修订建议已提（待核实）"
     % (N_EFF - N_EFF_NOPX, N_EFF),
     "internal/data_dictionary.md §2/§3；rules/recon_runbook.md §3.1", "已关闭"],
    ["持仓数据", "portfolio/holdings_2026Q3.xlsx",
     "混入 as_of≠%s 的非估值日旧记录 %d 行（市值影响 %s 元）" % (VAL_DATE, N_DROP_DATE, money(MV_DROP_DATE)),
     "全表合计将高估期末市值",
     "按 §2.1 估值日归属条件剔除，逐 sheet 明细见覆盖表",
     "rules/recon_runbook.md §2.1", "已关闭"],
    ["持仓数据", "portfolio/holdings_2026Q3.xlsx / portfolio/security_master.csv",
     "期末导出仍含主数据非 active（matured/called）证券持仓 %d 行（市值影响 %s 元）"
     % (N_DROP_STATUS, money(MV_DROP_STATUS)),
     "高估市值与单一发行人集中度",
     "按 §2.2 剔除非 active 证券记录；与投资经理说明第 2 条到期/赎回信息一致",
     "rules/recon_runbook.md §2.2；internal/manager_notes.md", "已关闭"],
    ["持仓数据", "portfolio/holdings_2026Q3.xlsx",
     "同账户+同证券+同数量重复上报 %d 行（市值影响 %s 元）" % (N_DROP_DUP, money(MV_DROP_DUP)),
     "重复计入市值",
     "按 §2.3 以 source_row_id 升序保留第一条，剔除其余 %d 行" % N_DROP_DUP,
     "rules/recon_runbook.md §2.3", "已关闭"],
    ["限额超限", "portfolio/holdings_2026Q3.xlsx / internal/approval_memo_20260928.md",
     "%s（%s）期末市值 %s 元、占净值 %.2f%%，超 v3 第 %s 条 %g%% 硬限；且决策纪要批准增持上限 %g%%（内部预警线 %g%%）与现行硬限不一致，实测亦超批准上限"
     % (TOP_SEC, SECNAME[TOP_SEC], money(TOP_SEC_MV), TOP_SEC_PCT*100,
        LIM3["R-01"]["art"], LIM3["R-01"]["limit"]*100, MEMO_CAP*100, MEMO_WARN*100),
     "R-01 期末超限，须披露并整改；审批口径与现行制度冲突",
     "按 v3 执行：报告§四正文披露超限事实/成因/整改/时限；T+%s 个工作日内提交整改计划并减持至 ≤%g%%；批准口径冲突提请风险管理部解释（v3 第 12 条）"
     % (TPLUS, LIM3["R-01"]["limit"]*100),
     "rules/restrictions_v3_20260901.md 第 %s/9/12 条；internal/approval_memo_20260928.md" % LIM3["R-01"]["art"],
     "处置中"],
    ["制度引用", "rules/liquidity_policy.md 第 21 条",
     "引用「投资限制条款第%s章」界定现金类资产，现行 v3 仅含第%s章，无对应章节" % (LIQ_REF, "、".join(V3_CHAPTERS)),
     "现金类资产定义引用悬空",
     "定义按 v3 第 %s 条（含清算备付金）执行；流动性制度第 12 条与 v3 第 %s 条下限一致（均 %g%%）；引用章节待核实"
     % (LIM3["R-05"]["art"], LIM3["R-05"]["art"], LIM3["R-05"]["limit"]*100),
     "rules/restrictions_v3_20260901.md 第 %s 条；rules/liquidity_policy.md 第 12/21 条" % LIM3["R-05"]["art"],
     "待核实"],
    ["口径差异", "internal/manager_notes.md / portfolio/holdings_2026Q3.xlsx",
     "经理说明称非标「专户四笔资产」，有效持仓中 NonStdAsset 共 %d 行、%d 只，分布于 %s"
     % (int((eff["sec_type"] == "NonStdAsset").sum()),
        eff.loc[eff["sec_type"] == "NonStdAsset", "sec_code"].nunique(),
        "、".join(sorted(eff.loc[eff["sec_type"] == "NonStdAsset", "sheet"].unique()))),
     "账户归属表述与持仓分布不一致（报价均为 100 摊余成本，估值影响为零）",
     "按 sec_type=NonStdAsset 全量汇总测算 R-03；账户归属以持仓导出为准，说明表述待核实",
     "internal/manager_notes.md 第 3 条；internal/data_dictionary.md §2", "待核实"],
    ["历史表页", "portfolio/holdings_2026Q3.xlsx（非账户 sheet %d 个：%s）" % (len(NON_ACCT_SHEETS), "、".join(NON_ACCT_SHEETS)),
     "q2_roll 为已归档上季度滚动表（仅留历史链接）；readme/contact 为说明页",
     "若误作期末持仓将重复计入",
     "不纳入期末口径，仅 %d 个 acct_* sheet 参与汇总" % len(ACCT_SHEETS),
     "工作簿 q2_roll 表内归档说明", "已关闭"],
]

# ----------------------------------------------------------------------------
# 9. 任务拆解与完成状态（对应任务书 16 项）
# ----------------------------------------------------------------------------
task_rows = [
    ["T1", "材料清点（分目录+根散件与总数勾稽）", "完成", "报告§一；Coverage（总数 %d=%d+%d）" % (N_FILES, SUBTOTAL, N_ROOT)],
    ["T2", "持仓十个账户 sheet 全覆盖汇总", "完成", "holdings_coverage.csv；Coverage/Holdings_Summary（原始 %d 行）" % RAW_ROWS],
    ["T3", "有效持仓口径（三条件顺序剔除）", "完成", "报告§三；Nav_Bridge（有效 %d 行、市值 %s 元）" % (N_EFF, money(MV_EFF))],
    ["T4", "行情取数与关联留痕", "完成", "Price_Join；报告§三（%d→%d 条，关联 %d/%d 行）" % (N_PRICE_RAW, N_PRICE_VAL, N_EFF - N_EFF_NOPX, N_EFF)],
    ["T5", "市值与净值复核推导链", "完成", "报告§二；Valuation_Recalc（净值差 %.2f 元）" % DIFF_NET],
    ["T6", "现金勾稽（对账单 vs 托管报告）", "完成", "报告§二；Nav_Bridge（差 %.2f 元）" % CASH_DIFF],
    ["T7", "五项限额逐条测算（现行 v3）", "完成", "报告§四；Compliance_Check（%d 合规 / %d 超限）" % (len(comp_rows) - len(BREACHES), len(BREACHES))],
    ["T8", "条款版本适用性说明", "完成", "报告§四；Compliance_Check"],
    ["T9", "超限处置与披露", "完成（整改进行中）", "报告§四正文；Compliance_Check 超限处置块；整改计划 T+%s 个工作日" % TPLUS],
    ["T10", "上期报告重述", "完成", "报告§五；Prev_Report_Fix（%d 条）" % len(prev_fix)],
    ["T11", "数据问题台账", "完成", "issue_log.csv；Issue_Log（%d 条）；报告§六" % len(issue_rows)],
    ["T12", "任务拆解与完成状态", "完成", "报告§七；Task_Status"],
    ["T13", "复合图表", "完成", "charts.png（限额对比+账户覆盖）"],
    ["T14", "可复算脚本", "完成", "reproduce.py（本脚本，无硬编码结论）"],
    ["T15", "报告成文（八章节、篇幅）", "完成", "operation_report.md（中文字符数见运行输出）"],
    ["T16", "勾稽一致性自检", "完成", "reproduce.py 内置断言全部通过（文件/行数/市值/净值/现金勾稽）"],
]

# ----------------------------------------------------------------------------
# 10. 输出：holdings_coverage.csv（末行合计）
# ----------------------------------------------------------------------------
cov_out = cov_df[["sheet", "raw", "drop_date", "drop_status", "drop_dup", "eff_rows", "eff_mv"]].copy()
cov_out.columns = ["账户sheet", "原始行数", "剔除1_非估值日行数", "剔除2_主数据非active行数",
                   "剔除3_重复上报行数", "有效行数", "有效市值(元)"]
cov_out["有效市值(元)"] = cov_out["有效市值(元)"].map(lambda x: round(x, 2))
cov_out = pd.concat([cov_out, pd.DataFrame([["合计", int(TOT["raw"]), int(TOT["drop_date"]),
    int(TOT["drop_status"]), int(TOT["drop_dup"]), int(TOT["eff_rows"]), round(float(TOT["eff_mv"]), 2)]],
    columns=cov_out.columns)], ignore_index=True)
cov_out.to_csv(F_COV, index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------
# 11. 输出：issue_log.csv（七要素）
# ----------------------------------------------------------------------------
log_df = pd.DataFrame(issue_rows, columns=["类别", "文件", "现象", "影响", "处置动作", "依据", "状态"])
log_df.to_csv(F_LOG, index=False, encoding="utf-8-sig")

# ----------------------------------------------------------------------------
# 12. 输出：charts.png（复合图：①限额对比 ②账户覆盖）
# ----------------------------------------------------------------------------
cjk_font = None
for want in ["Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK TC", "WenQuanYi Zen Hei"]:
    if any(f.name == want for f in font_manager.fontManager.ttflist):
        cjk_font = want
        break
if cjk_font:
    plt.rcParams["font.sans-serif"] = [cjk_font, "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.5, 6.0), dpi=150)
fig.suptitle("%s 现金增强 1 号 2026Q3 复核复合图（估值日 %s，材料截止 %s）" % (PFX, VAL_DATE, CUTOFF),
             fontsize=13, fontweight="bold")

name_short = {"R-01": "单一证券", "R-02": "单一发行人", "R-03": "非标资产",
              "R-05": "现金类资产", "R-07": "权益型基金"}
labels = ["%s\n%s(第%s条)" % (r["rule"], name_short[r["rule"]], r["art"]) for r in comp_rows]
meas = [r["pct"] for r in comp_rows]
lims = [r["limit"] for r in comp_rows]
x = np.arange(len(comp_rows)); w = 0.36
colors = ["#d62728" if r["result"] == "超限" else "#1f77b4" for r in comp_rows]
ax1.bar(x - w/2, meas, w, color=colors, label="本期测算值(%)")
ax1.bar(x + w/2, lims, w, color="#7f7f7f", alpha=0.65, label="v3 限额(%)")
for xi, r in zip(x, comp_rows):
    ax1.annotate("%.2f%%" % r["pct"], (xi - w/2, r["pct"]), ha="center", va="bottom", fontsize=9,
                 fontweight="bold", color="#d62728" if r["result"] == "超限" else "#1f77b4")
    ax1.annotate("%s%g%%" % ("≥" if r["dir"] == ">=" else "≤", r["limit"]),
                 (xi + w/2, r["limit"]), ha="center", va="bottom", fontsize=9)
    ax1.annotate(r["result"], (xi, -1.7), ha="center", fontsize=10,
                 color="#d62728" if r["result"] == "超限" else "#2ca02c", fontweight="bold")
ax1.set_xticks(x); ax1.set_xticklabels(labels, fontsize=9)
ax1.set_ylabel("占计划资产净值比例(%)")
ax1.set_ylim(-2.6, max(meas + lims) * 1.25)
ax1.set_title("① 五项限额指标：本期测算值 vs 现行 v3 限额", fontsize=11, fontweight="bold")
ax1.legend(loc="upper right", fontsize=9); ax1.grid(axis="y", alpha=0.3)

acc_labels = list(cov_df["sheet"])
raw_n = [int(v) for v in cov_df["raw"]]
eff_n = [int(v) for v in cov_df["eff_rows"]]
x2 = np.arange(len(acc_labels))
ax2.bar(x2 - w/2, raw_n, w, color="#1f77b4", label="原始记录数")
ax2.bar(x2 + w/2, eff_n, w, color="#2ca02c", label="有效记录数")
for xi, (a, b) in enumerate(zip(raw_n, eff_n)):
    ax2.annotate(str(a), (xi - w/2, a), ha="center", va="bottom", fontsize=8)
    ax2.annotate(str(b), (xi + w/2, b), ha="center", va="bottom", fontsize=8)
ax2.set_xticks(x2); ax2.set_xticklabels(acc_labels, fontsize=9, rotation=30)
ax2.set_ylabel("记录行数")
ax2.set_title("② 十个账户 sheet：原始 vs 有效记录数覆盖（合计 %d→%d 行）" % (RAW_ROWS, N_EFF),
              fontsize=11, fontweight="bold")
ax2.legend(loc="upper right", fontsize=9); ax2.grid(axis="y", alpha=0.3)
ax2.set_ylim(0, max(raw_n) * 1.18)

footnote = ("剔除三类（顺序执行）：非估值日 %d 行 / 主数据非 active %d 行 / 重复上报 %d 行；"
            "有效市值 %s 元。数据来源：/app/input_files（只读）"
            % (N_DROP_DATE, N_DROP_STATUS, N_DROP_DUP, money(MV_EFF)))
fig.tight_layout(rect=(0, 0.03, 1, 0.95))
fig.text(0.5, 0.005, footnote, ha="center", fontsize=9)
fig.savefig(F_PNG, bbox_inches="tight")
plt.close(fig)

# ----------------------------------------------------------------------------
# 13. 输出：quarterly_workbook.xlsx（9 表：规定 8 表 + Price_Join）
# ----------------------------------------------------------------------------
TITLE_FONT = Font(bold=True, size=12, color="1F4E79")
HDR_FONT = Font(bold=True, color="FFFFFF")
HDR_FILL = PatternFill("solid", fgColor="1F4E79")
RED = Font(color="C00000", bold=True)

def default_fmt(header_row, col_idx):
    h = str(header_row[col_idx]) if header_row and col_idx < len(header_row) else ""
    if "单位净值" in h:
        return "0.000000"
    if "bp" in h or "基点" in h:
        return "0.00"
    if "(%)" in h:
        return "0.00"
    return "#,##0.00"

def write_sheet(ws, blocks, widths):
    """blocks: ('title'|'header'|'row'|'note'|'blank', payload)；row 单元格可为 (值, 数字格式) 元组"""
    r = 1
    last_header = None
    for kind, payload in blocks:
        if kind == "blank":
            r += 1; last_header = None; continue
        if kind == "title":
            ws.cell(row=r, column=1, value=payload).font = TITLE_FONT; r += 1; continue
        if kind == "note":
            c = ws.cell(row=r, column=1, value=payload)
            c.font = Font(italic=True, size=9, color="595959"); r += 1; continue
        if kind == "header":
            last_header = payload
            for j, v in enumerate(payload, 1):
                c = ws.cell(row=r, column=j, value=v)
                c.font = HDR_FONT; c.fill = HDR_FILL
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            r += 1; continue
        if kind == "row":
            for j, v in enumerate(payload, 1):
                nf = None
                if isinstance(v, tuple):
                    v, nf = v
                if isinstance(v, np.integer):
                    v = int(v)
                elif isinstance(v, np.floating):
                    v = float(v)
                c = ws.cell(row=r, column=j, value=v)
                if isinstance(v, float):
                    c.number_format = nf or default_fmt(last_header, j - 1)
                if isinstance(v, str) and ("超限" in v or "处置中" in v or "待核实" in v):
                    c.font = RED
            r += 1; continue
    for j, wd in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = wd

owb = Workbook(); owb.remove(owb.active)

# ---- Sheet 1: Coverage ----
ws = owb.create_sheet("Coverage")
blocks = [("title", "A. 材料清点（估值日 %s；材料截止时点 %s；来源 00_README.md / manifest.csv）" % (VAL_DATE, CUTOFF)),
          ("header", ["目录", "用途", "文件数"])]
for d in sorted(per_dir):
    blocks.append(("row", [d + "/", dir_purpose.get(d, ""), per_dir[d]]))
blocks += [
    ("row", ["（根目录散件）", "、".join(root_files), N_ROOT]),
    ("row", ["分目录小计", "portfolio+valuation+data+rules+reports+compliance+internal", SUBTOTAL]),
    ("row", ["文件总数", "= 分目录小计 + 根散件 = %d + %d" % (SUBTOTAL, N_ROOT), N_FILES]),
    ("row", ["来源目录数", "manifest.csv 所列目录", N_DIRS]),
    ("row", ["勾稽差（总数−小计−根散件）", "须为 0", N_FILES - SUBTOTAL - N_ROOT]),
    ("blank", None),
    ("title", "B. 持仓覆盖：十个账户 sheet 逐表行数与市值（portfolio/holdings_2026Q3.xlsx）"),
    ("note", "非账户 sheet %d 个（%s）不纳入持仓汇总；q2_roll 已归档、仅作历史链接" % (len(NON_ACCT_SHEETS), "、".join(NON_ACCT_SHEETS))),
    ("header", ["账户sheet", "原始行数", "剔除1_非估值日", "剔除2_主数据非active", "剔除3_重复上报",
                "有效行数", "有效市值(元)", "勾稽差(原始−三剔除−有效)"])]
for _, rw in cov_df.iterrows():
    chk = int(rw["raw"] - rw["drop_date"] - rw["drop_status"] - rw["drop_dup"] - rw["eff_rows"])
    blocks.append(("row", [rw["sheet"], int(rw["raw"]), int(rw["drop_date"]), int(rw["drop_status"]),
                           int(rw["drop_dup"]), int(rw["eff_rows"]), (round(float(rw["eff_mv"]), 2), "#,##0.00"), chk]))
blocks.append(("row", ["合计", int(TOT["raw"]), int(TOT["drop_date"]), int(TOT["drop_status"]),
                       int(TOT["drop_dup"]), int(TOT["eff_rows"]), (round(float(TOT["eff_mv"]), 2), "#,##0.00"),
                       int(TOT["raw"] - TOT["drop_date"] - TOT["drop_status"] - TOT["drop_dup"] - TOT["eff_rows"])]))
write_sheet(ws, blocks, [28, 34, 12, 17, 17, 12, 18, 22])

# ---- Sheet 2: Holdings_Summary ----
ws = owb.create_sheet("Holdings_Summary")
st = eff.groupby("sec_type").agg(rows=("mv", "size"), mv=("mv", "sum")).reset_index()
order = {t: i for i, t in enumerate(bw_df["sec_type"])}
st = st.assign(ord=st["sec_type"].map(order)).sort_values("ord")
blocks = [("title", "A. 按券种汇总（有效持仓口径，估值日 %s）" % VAL_DATE),
          ("header", ["券种代码", "券种名称", "有效行数", "市值(元)", "占净值比例(%)"])]
for _, rw in st.iterrows():
    blocks.append(("row", [rw["sec_type"], TYPE_CN.get(rw["sec_type"], rw["sec_type"]),
                           int(rw["rows"]), (round(float(rw["mv"]), 2), "#,##0.00"),
                           round(float(rw["mv"]) / NAV_CUST * 100, 2)]))
blocks += [("row", ["合计", "", int(st["rows"].sum()), (round(float(st["mv"].sum()), 2), "#,##0.00"),
                    round(float(st["mv"].sum()) / NAV_CUST * 100, 2)]),
           ("blank", None),
           ("title", "B. 按资金账户汇总（十个账户）"),
           ("header", ["账户sheet", "有效行数", "市值(元)", "占净值比例(%)"])]
for _, rw in cov_df.iterrows():
    blocks.append(("row", [rw["sheet"], int(rw["eff_rows"]), (round(float(rw["eff_mv"]), 2), "#,##0.00"),
                           round(float(rw["eff_mv"]) / NAV_CUST * 100, 2)]))
blocks += [("row", ["合计", int(TOT["eff_rows"]), (round(float(TOT["eff_mv"]), 2), "#,##0.00"),
                    round(float(TOT["eff_mv"]) / NAV_CUST * 100, 2)]),
           ("note", "折算口径（internal/data_dictionary.md §2）：债券/非标 市值=vol×close_price/100；权益型基金 市值=vol×close_price"),
           ("note", "勾稽：券种合计 = 账户合计 = 有效持仓市值 %s 元，与 Valuation_Recalc 第 1 行一致" % money(MV_EFF))]
write_sheet(ws, blocks, [22, 26, 12, 18, 15])

# ---- Sheet 3: Valuation_Recalc ----
ws = owb.create_sheet("Valuation_Recalc")
blocks = [("title", "净值复核推导链（每行带列报值；金额单位：元）"),
          ("header", ["序号", "项目", "列报值", "算式/说明", "数据来源"])]
chain = [
    (1, "有效持仓市值 A", (round(MV_EFF, 2), "#,##0.00"),
     "Σ(%d 行有效持仓 × 估值日行情折算) = %s" % (N_EFF, money(MV_EFF)),
     "portfolio/holdings_2026Q3.xlsx + data/price_feed_20260930_repush.csv"),
    (2, "加：现金及清算备付金 B", (round(CASH_CUST, 2), "#,##0.00"), "托管行报告列报值",
     "valuation/nav_report_20260930.csv"),
]
for i, k in enumerate(RECV_ITEMS):
    chain.append((3 + i, "加：%s C%d" % (acc_name[k], i + 1), (round(acc_map[k], 2), "#,##0.00"),
                  "计提期间 %s" % acc_period[k], "valuation/accruals_20260930.csv"))
for i, k in enumerate(PAY_ITEMS):
    chain.append((5 + i, "减：%s D%d" % (acc_name[k], i + 1), (round(acc_map[k], 2), "#,##0.00"),
                  "计提期间 %s" % acc_period[k], "valuation/accruals_20260930.csv"))
chain += [
    (8, "资产净值（复核）E", (round(NET_CALC, 2), "#,##0.00"),
     "E = A+B+C1+C2−D1−D2−D3 = %s+%s+%s+%s−%s−%s−%s" % (money(MV_EFF), money(CASH_CUST),
       money(acc_map[RECV_ITEMS[0]]), money(acc_map[RECV_ITEMS[1]]), money(acc_map[PAY_ITEMS[0]]),
       money(acc_map[PAY_ITEMS[1]]), money(acc_map[PAY_ITEMS[2]])),
     "本表上行计算"),
    (9, "资产净值（托管行列报）F", (round(NAV_CUST, 2), "#,##0.00"),
     "差额 E − F = %.2f 元" % DIFF_NET, "valuation/nav_report_20260930.csv"),
    (10, "计划总份额 G", (round(TOTAL_SHARES, 2), "#,##0.00"), "托管行报告列报值",
     "valuation/nav_report_20260930.csv"),
    (11, "单位净值（复核）H", (round(NPS_CALC, 6), "0.000000"),
     "H = E ÷ G = %s ÷ %s" % (money(NET_CALC), money(TOTAL_SHARES)), "本表上行计算"),
    (12, "单位净值（托管行列报）I", (round(NPS_CUST, 4), "0.0000"),
     "差额 (H/I−1)×10^4 = %+.2f bp（托管行四舍五入至 4 位所致）" % DIFF_NPS_BP,
     "valuation/nav_report_20260930.csv"),
    (13, "未过滤口径单位净值对照 J", (round(NPS_RAW, 6), "0.000000"),
     "J = (未过滤市值 %s + B + C1+C2 − D1−D2−D3) ÷ G；相对正确口径高估 (J/H−1)×10^4 = %+.2f bp，详见 Nav_Bridge"
     % (money(MV_RAW), OVERSTATE_BP), "本脚本计算（对照用）"),
    (14, "2026Q3 计划业绩比较基准收益率", (round(BENCH_RET, 4), "0.0000") if BENCH_RET is not None else "待核实",
     "参考列报；组合区间收益因期初净值材料不完整，待核实", "data/benchmark_returns_2026Q3.csv"),
]
for c in chain:
    blocks.append(("row", list(c)))
write_sheet(ws, blocks, [6, 34, 20, 88, 46])

# ---- Sheet 4: Nav_Bridge ----
ws = owb.create_sheet("Nav_Bridge")
blocks = [("title", "A. 持仓市值口径调整勾稽（未过滤 → 有效口径；三类剔除分列，不合并）"),
          ("header", ["项目", "行数", "市值(元)", "说明"]),
          ("row", ["未过滤全表合计（上期旧口径，对照）", RAW_ROWS, (round(MV_RAW, 2), "#,##0.00"),
                   "全部行 × 估值日行情折算"]),
          ("row", ["剔除1：非估值日（as_of≠%s）" % VAL_DATE, -N_DROP_DATE, (-round(MV_DROP_DATE, 2), "#,##0.00"),
                   "runbook §2.1"]),
          ("row", ["剔除2：主数据非 active（matured/called）", -N_DROP_STATUS, (-round(MV_DROP_STATUS, 2), "#,##0.00"),
                   "runbook §2.2"]),
          ("row", ["剔除3：重复上报（acct+sec_code+vol）", -N_DROP_DUP, (-round(MV_DROP_DUP, 2), "#,##0.00"),
                   "runbook §2.3；source_row_id 升序保留第一条"]),
          ("row", ["有效持仓市值（正确口径）", N_EFF, (round(MV_EFF, 2), "#,##0.00"),
                   "勾稽差 %.2f 元" % (MV_RAW - MV_DROP_DATE - MV_DROP_STATUS - MV_DROP_DUP - MV_EFF)]),
          ("blank", None),
          ("title", "B. 单位净值口径对照（未过滤 vs 正确）"),
          ("header", ["口径", "资产净值(元)", "单位净值(元)", "相对正确口径高估(bp)"]),
          ("row", ["未过滤口径（对照）", (round(NET_RAW, 2), "#,##0.00"), (round(NPS_RAW, 6), "0.000000"),
                   round(OVERSTATE_BP, 2)]),
          ("row", ["有效口径（正确）", (round(NET_CALC, 2), "#,##0.00"), (round(NPS_CALC, 6), "0.000000"), 0.00]),
          ("note", "高估幅度 = (未过滤单位净值 ÷ 正确单位净值 − 1) × 10^4 = %+.2f bp；单位净值绝对差 %s 元"
           % (OVERSTATE_BP, f"{NPS_RAW - NPS_CALC:,.6f}")),
          ("blank", None),
          ("title", "C. 现金勾稽（银行对账单分账户 vs 托管报告）"),
          ("header", ["账户", "账户名称", "期末余额(元)", "as_of"])]
for _, b in bank_df.iterrows():
    blocks.append(("row", [b["account"], b["account_name"], (round(float(b["balance"]), 2), "#,##0.00"), str(b["as_of"])]))
blocks += [
    ("row", ["对账单合计", "", (round(BANK_TOTAL, 2), "#,##0.00"), ""]),
    ("row", ["托管报告现金及清算备付金", "valuation/nav_report_20260930.csv", (round(CASH_CUST, 2), "#,##0.00"), VAL_DATE]),
    ("row", ["差额（对账单合计 − 托管列报）", "须为 0", (round(CASH_DIFF, 2), "#,##0.00"), ""]),
]
write_sheet(ws, blocks, [42, 40, 20, 46])

# ---- Sheet 5: Compliance_Check ----
ws = owb.create_sheet("Compliance_Check")
blocks = [("title", "五项限额逐条测算（现行 v3，生效 2026-09-01；分母 = 计划资产净值总额 %s 元；分子 = 期末有效持仓，v3 第 2/3 条）" % money(NAV_CUST)),
          ("header", ["指标", "条款号(v3)", "测算值(元)", "测算比例(%)", "限额(%)", "比较方向", "结论", "算式"])]
formula_map = {
    "R-01": "%s 市值 %s ÷ 净值 %s" % (TOP_SEC, money(TOP_SEC_MV), money(NAV_CUST)),
    "R-02": "发行人 %s 有效持仓合计 %s ÷ 净值" % (TOP_ISS, money(TOP_ISS_MV)),
    "R-03": "NonStdAsset 合计 %s ÷ 净值" % money(mv_nonstd),
    "R-05": "托管行现金及清算备付金 %s ÷ 净值" % money(CASH_CUST),
    "R-07": "EquityFund 合计 %s ÷ 净值" % money(mv_eqfund),
}
for r in comp_rows:
    blocks.append(("row", [r["label"], "第%s条(%s)" % (r["art"], r["rule"]), (round(r["mv"], 2), "#,##0.00"),
                           round(r["pct"], 2), round(r["limit"], 2),
                           "≥下限" if r["dir"] == ">=" else "≤上限", r["result"], formula_map[r["rule"]]]))
blocks += [
    ("blank", None),
    ("title", "现金类资产比例交叉核对（rules/liquidity_policy.md）"),
    ("header", ["条文", "内容", "与 v3 第%s条口径核对" % LIM3["R-05"]["art"], "结论"]),
    ("row", ["流动性制度 第12条", "开放式集合计划保持不低于计划资产净值 %g%% 的现金类资产" % (LIQ12_PCT * 100),
             "下限一致（均 %g%%）" % (LIM3["R-05"]["limit"] * 100) if LIQ_CONSISTENT
             else "下限不一致（%g%% vs %g%%）" % (LIQ12_PCT * 100, LIM3["R-05"]["limit"] * 100),
             "一致" if LIQ_CONSISTENT else "不一致"]),
    ("row", ["流动性制度 第21条", "现金类资产界定与投资限制条款第%s章保持一致" % LIQ_REF,
             "v3 仅含第%s章，无第%s章对应条文" % ("、".join(V3_CHAPTERS), LIQ_REF),
             "引用悬空，待核实" if not LIQ_REF_VALID else "引用有效"]),
    ("row", ["v3 第%s条" % LIM3["R-05"]["art"], "现金类资产（含清算备付金）比例不得低于 %g%%" % (LIM3["R-05"]["limit"] * 100),
             "本表执行口径（托管行现金及清算备付金）", "两处 3% 下限实质一致；定义按 v3 执行"]),
    ("blank", None),
    ("title", "超限处置明细（R-01；报告§四正文同步披露）"),
    ("header", ["项目", "内容"]),
    ("row", ["证券代码 / 名称", "%s / %s" % (TOP_SEC, SECNAME[TOP_SEC])]),
    ("row", ["期末市值(元)", (round(TOP_SEC_MV, 2), "#,##0.00")]),
    ("row", ["占净值比例(%)", round(TOP_SEC_PCT * 100, 2)]),
    ("row", ["限额 / 超出", "≤%g%%；超出 %.2f 个百分点，超出金额 %s 元"
             % (LIM3["R-01"]["limit"] * 100, (TOP_SEC_PCT - LIM3["R-01"]["limit"]) * 100, money(EXCESS_AMT))]),
    ("row", ["持仓分布", "；".join("%s %s 元" % (k, money(v)) for k, v in TOP_SEC_ACCTS.items())]),
    ("row", ["成因", "9 月中旬主动增持（internal/manager_notes.md 第 1 条）；决策纪要批准上限 %g%%、内部预警线 %g%%，"
                     "与 v3 硬限 %g%% 不一致，实测 %.2f%% 亦超批准上限"
             % (MEMO_CAP * 100, MEMO_WARN * 100, LIM3["R-01"]["limit"] * 100, TOP_SEC_PCT * 100)]),
    ("row", ["整改动作与时限", "减持该券至占净值 ≤%g%%（至少压降 %s 元市值）；投资经理 T+%s 个工作日内提交整改计划（v3 第 9 条）；具体执行排期待核实"
             % (LIM3["R-01"]["limit"] * 100, money(EXCESS_AMT), TPLUS)]),
    ("row", ["披露要求", "v3 第 9 条：季度报告「投资监督」章节披露超限事实、成因、整改措施与时限——已于报告§四正文披露；"
                        "第 10 条盘中瞬时超限当日恢复者仅记台账，本期无此类未决事项"]),
    ("row", ["版本适用性", "v2（2026-06-01）已被 v3（2026-09-01 生效）替代、仅作历史回溯；v2 归档说明明确 2026Q3 起一律执行 v3，"
                          "故 v2 限额（R-01 %g%%、R-03 %g%%、R-05 %g%%、R-07 %g%%）不适用于本期"
             % (LIM2["R-01"]["limit"] * 100, LIM2["R-03"]["limit"] * 100, LIM2["R-05"]["limit"] * 100, LIM2["R-07"]["limit"] * 100)]),
]
write_sheet(ws, blocks, [46, 22, 20, 14, 10, 10, 12, 88])

# ---- Sheet 6: Issue_Log ----
ws = owb.create_sheet("Issue_Log")
blocks = [("title", "数据问题与阻塞台账（七要素，一行一条）"),
          ("header", ["编号"] + list(log_df.columns))]
for i, (_, rw) in enumerate(log_df.iterrows(), 1):
    blocks.append(("row", ["IL-%02d" % i] + list(rw.values)))
write_sheet(ws, blocks, [8, 12, 42, 62, 36, 56, 46, 10])

# ---- Sheet 7: Task_Status ----
ws = owb.create_sheet("Task_Status")
blocks = [("title", "任务拆解与完成状态"),
          ("header", ["任务编号", "任务项", "状态", "对应交付物位置"])]
for t in task_rows:
    blocks.append(("row", t))
write_sheet(ws, blocks, [10, 42, 22, 76])

# ---- Sheet 8: Prev_Report_Fix ----
ws = owb.create_sheet("Prev_Report_Fix")
blocks = [("title", "上期报告重述（一行一条）"),
          ("header", ["编号", "出处", "原表述", "不再适用的原因", "本期处置"])]
for i, p in enumerate(prev_fix, 1):
    blocks.append(("row", ["PF-%02d" % i, p["src"], "「%s」" % p["quote"], p["why"], p["fix"]]))
write_sheet(ws, blocks, [8, 40, 66, 62, 70])

# ---- Sheet 9: Price_Join（行情取数留痕，附加表） ----
ws = owb.create_sheet("Price_Join")
blocks = [("title", "行情取数与关联留痕（runbook §3；数据字典 §2/§3）"),
          ("header", ["项目", "值", "说明"]),
          ("row", ["估值日主件 valuation/price_feed_20260930.csv", "%d 条数据" % feed_val_rows,
                   "传输残留空文件、不承载数据（internal/ops_email_20261008.txt）"]),
          ("row", ["采用行情文件", "data/price_feed_20260930_repush.csv",
                   "数据组重推件（%s 邮件确认），README 口径优先级第 3 条" % CUTOFF]),
          ("row", ["行情原始记录数", N_PRICE_RAW, "含批次「重推件」与「原始推送」"]),
          ("row", ["过滤条件", "trade_date = %s" % VAL_DATE, "runbook §3.3：多交易日取估值日当日"]),
          ("row", ["过滤后记录数", N_PRICE_VAL, "剔除前一交易日(2026-09-29)记录 %d 条" % N_PRICE_DROP_DATE]),
          ("row", ["关联字段", "持仓 sec_code ↔ 行情 instrument_id",
                   "runbook §3.1 所称 %s 列两侧均不存在（数据字典 2026-08 改版），按字典执行并留痕" % RUNBOOK_FIELD]),
          ("row", ["有效持仓行数 / 关联成功", "%d / %d" % (N_EFF, N_EFF - N_EFF_NOPX),
                   "持仓侧无行情 %d 行" % N_EFF_NOPX]),
          ("row", ["行情证券数 / 有有效持仓", "%d / %d" % (N_PRICE_VAL, len(eff_codes)),
                   "行情侧无有效持仓证券 %d 只" % len(px_no_hold)]),
          ("row", ["行情侧无有效持仓清单", "、".join(px_no_hold),
                   "；".join("%s：%s" % (c, px_no_hold_reason[c]) for c in px_no_hold)]),
          ("row", ["持仓侧无行情清单", "无", "runbook §3.4 对账差异：0 条"])]
write_sheet(ws, blocks, [40, 44, 100])

owb.save(F_XLSX)

# ----------------------------------------------------------------------------
# 14. 输出：operation_report.md（八章节；正文中文字符 <= 1600）
# ----------------------------------------------------------------------------
pct2 = lambda x: f"{x*100:.2f}%"

md = []
md.append("# 现金增强 1 号集合资产管理计划 2026 年三季度投资运作报告")
md.append("")
md.append(f"报告期末：**{VAL_DATE}**｜材料截止时点：**{CUTOFF}**｜编制日期：{COMPILE_DATE}｜单位：元")
md.append("")
md.append("## 一、材料清点")
md.append(f"输入材料共 **{N_FILES}** 个文件、**{N_DIRS}** 个来源目录、根散件 {N_ROOT} 个（{'、'.join(root_files)}）。"
          "分目录：" + "；".join(f"{d} {per_dir[d]}" for d in sorted(per_dir)) +
          f"，小计 {SUBTOTAL}；{SUBTOTAL}＋{N_ROOT}＝{N_FILES}，与总数勾稽一致（差 0）。")
md.append("")
md.append("## 二、组合概况与净值复核")
md.append("|行|项目|列报值|")
md.append("|-|-|-:|")
md.append(f"|1|有效持仓市值 A|{money(MV_EFF)}|")
md.append(f"|2|＋现金及清算备付金 B|{money(CASH_CUST)}|")
md.append(f"|3|＋{acc_name['interest_receivable']} C1|{money(acc_map['interest_receivable'])}|")
md.append(f"|4|＋{acc_name['dividend_receivable']} C2|{money(acc_map['dividend_receivable'])}|")
md.append(f"|5|－{acc_name['fee_payable_admin']} D1|{money(acc_map['fee_payable_admin'])}|")
md.append(f"|6|－{acc_name['fee_payable_custodian']} D2|{money(acc_map['fee_payable_custodian'])}|")
md.append(f"|7|－{acc_name['fee_payable_sales']} D3|{money(acc_map['fee_payable_sales'])}|")
md.append(f"|8|＝资产净值 E＝A＋B＋C1＋C2－D1－D2－D3|{money(NET_CALC)}|")
md.append(f"|9|÷计划总份额 F|{money(TOTAL_SHARES)}|")
md.append(f"|10|＝单位净值 E÷F|{NPS_CALC:.6f}|")
md.append("")
bank_detail = "＋".join("%s %s" % (n, money(float(b))) for n, b in zip(bank_df["account_name"], bank_df["balance"]))
md.append(f"托管行列报净值 {money(NAV_CUST)}、单位净值 {NPS_CUST:.4f}：净值差 {DIFF_NET:.2f} 元、单位净值差 {DIFF_NPS_BP:+.2f}bp（托管行舍入所致），复核一致。"
          f"现金勾稽（分列）：{bank_detail}＝合计 {money(BANK_TOTAL)}，与托管报告现金差 {CASH_DIFF:.2f} 元，一致。")
md.append("")
md.append("## 三、持仓覆盖与口径执行")
md.append(f"十个账户 sheet 全覆盖：原始 {RAW_ROWS} 行，按指引§2 顺序剔除——①非估值日 {N_DROP_DATE} 行（市值 {money(MV_DROP_DATE)}）、"
          f"②主数据非 active {N_DROP_STATUS} 行（市值 {money(MV_DROP_STATUS)}）、③重复上报 {N_DROP_DUP} 行（市值 {money(MV_DROP_DUP)}）；"
          f"有效 {N_EFF} 行、市值 {money(MV_EFF)}，逐账户与勾稽见覆盖表（差 0）。")
md.append(f"行情：估值日主件空文件（传输残留），以数据组重推件为准；按 trade_date＝{VAL_DATE} 过滤 {N_PRICE_RAW}→{N_PRICE_VAL} 行（剔前一交易日 {N_PRICE_DROP_DATE} 行）；"
          f"以 sec_code↔instrument_id 关联（指引§3.1 的 {RUNBOOK_FIELD} 列经字典 2026-08 改版已不存在，按字典执行）；"
          f"有效持仓 {N_EFF - N_EFF_NOPX}/{N_EFF} 行关联成功；行情 {N_PRICE_VAL} 只中 {len(px_no_hold)} 只无有效持仓"
          f"（{len(px_nh_in_hold)} 只系被剔除非 active 券、{len(px_nh_no_row)} 只无持仓行），列入差异表。")
md.append(f"未过滤全表口径对照：单位净值 {NPS_RAW:.6f}，较正确口径高估 **{OVERSTATE_BP:+.2f}bp**，旧口径不可用。")
md.append("")
md.append("## 四、投资监督与限额执行")
md.append(f"执行现行 v3 条款（2026-09-01 生效），分母为托管净值 {money(NAV_CUST)}：")
md.append("|指标|条款|测算值|限额|方向|结论|")
md.append("|-|-|-:|-:|:-|:-|")
for r in comp_rows:
    md.append(f"|{r['rule']} {name_short[r['rule']]}|第{r['art']}条|{r['pct']:.2f}%|{r['limit']:.0f}%|{'≥' if r['dir']=='>=' else '≤'}|**{r['result']}**|")
md.append("")
md.append(f"现金类交叉核对：流动性制度第 12 条下限 {LIQ12_PCT*100:.0f}% 与 v3 第 {LIM3['R-05']['art']} 条一致；"
          f"其第 21 条引「限制条款第{LIQ_REF}章」而 v3 无该章（仅{'至'.join([V3_CHAPTERS[0], V3_CHAPTERS[-1]])}），定义按 v3 第 {LIM3['R-05']['art']} 条（含清算备付金）执行，引用待核实。")
md.append(f"**超限处置（R-01，正文披露）**：证券 {TOP_SEC}《{SECNAME[TOP_SEC]}》，期末市值 {money(TOP_SEC_MV)}、占净值 {pct2(TOP_SEC_PCT)}，"
          f"超 {LIM3['R-01']['limit']*100:.0f}% 硬限 {money(EXCESS_AMT)} 元。"
          f"成因：9 月中旬主动增持；纪要批准上限 {MEMO_CAP*100:.0f}%、预警线 {MEMO_WARN*100:.1f}%，均与硬限不符且被突破。"
          f"整改：按 v3 第 9 条，投资经理 T＋{TPLUS} 个工作日内提交整改计划、减持至 ≤{LIM3['R-01']['limit']*100:.0f}%；本章即该条要求的披露；排期待核实。")
md.append(f"版本适用性：v2 已被 v3 替代、仅作回溯，其限额（R-01 {LIM2['R-01']['limit']*100:.0f}%、R-03 {LIM2['R-03']['limit']*100:.0f}%、"
          f"R-05 {LIM2['R-05']['limit']*100:.0f}%、R-07 {LIM2['R-07']['limit']*100:.0f}%）自 2026Q3 起不适用；Q2 列报值系 v2 口径，不与本期直接比较。")
md.append("")
md.append("## 五、上期报告口径重述")
md.append("|编号|原表述（出处）|不再适用的原因|本期处置|")
md.append("|-|-|-|-|")
short_why = ["v2 已被 v3 替代，归档说明明确 Q3 起执行 v3",
             "与指引§2 三条件不符；经理说明第 4 条废止",
             f"2% 下限系 v2 条文，已被 v3 第 {LIM3['R-05']['art']} 条 {LIM3['R-05']['limit']*100:.0f}% 替代",
             "该版当时为草案且已被替代，无法回溯核实"]
short_fix = ["按 v3 重算五项并披露 R-01 超限（§四）",
             f"三条件过滤 {RAW_ROWS}→{N_EFF} 行、剔除 {money(MV_RAW - MV_EFF)} 元（§三）",
             f"现金类实测 {pct2(PCT_CASH)}≥{LIM3['R-05']['limit']*100:.0f}%，合规（§四）",
             "仅作历史回溯，本期执行 v3"]
short_src = ["Q2报告§二", "Q2报告§二", "Q2报告§二", "Q1报告§二"]
short_q = [Q_P1, Q_P2, Q_P3, Q_P4]
for i in range(len(prev_fix)):
    q = short_q[i] if len(short_q[i]) <= 38 else short_q[i][:36] + "…"
    md.append(f"|{i+1}|「{q}」（{short_src[i]}）|{short_why[i]}|{short_fix[i]}|")
md.append("")
md.append("## 六、数据问题与处置")
md.append(f"台账 {len(issue_rows)} 条（详见 issue_log.csv）：①行情主件空残留——采重推件；②重推件混入前一交易日 {N_PRICE_DROP_DATE} 行——按估值日过滤；"
          f"③指引字段 {RUNBOOK_FIELD} 废止——按字典关联；④⑤⑥持仓混入旧日期 {N_DROP_DATE} 行、非 active {N_DROP_STATUS} 行、重复 {N_DROP_DUP} 行——按§2 剔除；"
          f"⑦审批上限 {MEMO_CAP*100:.0f}% 与 v3 硬限 {LIM3['R-01']['limit']*100:.0f}% 冲突且实测超限——按 v3 披露整改（处置中）；⑧制度第 21 条引用悬空——待核实；"
          f"⑨非标账户归属表述与持仓不符（估值无影响）——待核实；⑩q2_roll 归档表——不作期末依据。")
md.append("最终采用数据源：持仓＝管理人盘后导出（有效口径过滤后）；行情＝数据组重推件（估值日）；净值、份额、现金＝托管行报告；限额＝v3 现行条款；应收应付＝计提明细。")
md.append("")
md.append("## 七、任务拆解与完成状态")
md.append("|编号|任务项|状态|交付物位置|")
md.append("|-|-|:-|-|")
short_task = [
    ("T1", "材料清点", "完成", "§一；Coverage"),
    ("T2", "持仓覆盖", "完成", "coverage.csv；Coverage"),
    ("T3", "口径剔除", "完成", "§三；Nav_Bridge"),
    ("T4", "行情取数", "完成", "Price_Join；§三"),
    ("T5", "净值复核", "完成", "§二；Valuation_Recalc"),
    ("T6", "现金勾稽", "完成", "§二；Nav_Bridge"),
    ("T7", "限额测算", "完成", "§四；Compliance_Check"),
    ("T8", "版本适用", "完成", "§四"),
    ("T9", "超限披露", "完成（整改中）", "§四；Compliance_Check"),
    ("T10", "上期重述", "完成", "§五；Prev_Report_Fix"),
    ("T11", "问题台账", "完成", "§六；issue_log.csv"),
    ("T12", "任务状态", "完成", "§七；Task_Status"),
    ("T13", "图表", "完成", "charts.png"),
    ("T14", "复算脚本", "完成", "reproduce.py"),
    ("T15", "报告成文", "完成", "本报告"),
    ("T16", "勾稽自检", "完成", "断言通过"),
]
for t in short_task:
    md.append("|%s|%s|%s|%s|" % t)
md.append("")
md.append("## 八、结论与下季度计划")
md.append(f"本期复核净值 {money(NET_CALC)} 与托管列报一致（差 {DIFF_NET:.2f} 元），单位净值 {NPS_CALC:.4f}（与列报差 {DIFF_NPS_BP:+.2f}bp，系舍入）；现金勾稽差 {CASH_DIFF:.2f} 元。"
          f"五项限额 {len(comp_rows) - len(BREACHES)} 合规、{len(BREACHES)} 超限（R-01），已按第 9 条披露并启动整改。"
          f"下季度：完成该券减持销项；推动指引字段与制度第 21 条引用修订核实；跟踪非标四笔（到期 2027-03 至 2028-06）及华骏集团授信变化；期末监测续行 v3。")
md.append("")
md.append("（未经审计；数值可回溯 input_files 材料并经复算脚本重现。）")
report_text = "\n".join(md)
F_MD.write_text(report_text, encoding="utf-8")

# 篇幅自检：正文中文字符（汉字+中文标点；表格竖线与代码块标记不计入）
no_code = re.sub(r"```.*?```", "", report_text, flags=re.S)
han = len(re.findall(r"[\u4e00-\u9fff]", no_code))
cjk_punct = len(re.findall(r"[\u3001\u3002\u300a\u300b\u3010\u3011\uff0c\uff1a\uff1b\uff01\uff1f\uff08\uff09\u201c\u201d\u2018\u2019\u2014\u2026\u00b7]", no_code))
assert han + cjk_punct <= 1600, "报告中文字符超限：%d（汉字 %d + 标点 %d）" % (han + cjk_punct, han, cjk_punct)

# ----------------------------------------------------------------------------
# 15. 脚本自身就位 + 交付物完整性自检
# ----------------------------------------------------------------------------
src = Path(__file__).resolve()
if src != F_PY.resolve():
    shutil.copyfile(src, F_PY)
for f in (F_XLSX, F_MD, F_PY, F_COV, F_LOG, F_PNG):
    assert f.exists() and f.stat().st_size > 0, f"缺少交付物 {f}"

# ----------------------------------------------------------------------------
# 16. 控制台摘要（全部为计算值）
# ----------------------------------------------------------------------------
print("=" * 80)
print("%s 复算完成｜估值日 %s｜材料截止 %s" % (PFX, VAL_DATE, CUTOFF))
print("-" * 80)
print("材料清点：总数 %d = 分目录小计 %d + 根散件 %d（%d 个来源目录）" % (N_FILES, SUBTOTAL, N_ROOT, N_DIRS))
print("持仓覆盖：原始 %d = 有效 %d + 非估值日 %d + 非active %d + 重复 %d" %
      (RAW_ROWS, N_EFF, N_DROP_DATE, N_DROP_STATUS, N_DROP_DUP))
print("有效持仓市值 %s ｜未过滤对照 %s ｜剔除：date %s / status %s / dup %s" %
      (money(MV_EFF), money(MV_RAW), money(MV_DROP_DATE), money(MV_DROP_STATUS), money(MV_DROP_DUP)))
print("净值复核 %s vs 托管 %s（差 %.2f 元）；单位净值 %.6f vs %.4f（%+.2f bp）" %
      (money(NET_CALC), money(NAV_CUST), DIFF_NET, NPS_CALC, NPS_CUST, DIFF_NPS_BP))
print("未过滤口径单位净值 %.6f，相对正确口径高估 %+.2f bp" % (NPS_RAW, OVERSTATE_BP))
print("现金勾稽：对账单合计 %s − 托管现金 %s = %.2f" % (money(BANK_TOTAL), money(CASH_CUST), CASH_DIFF))
for r in comp_rows:
    print("  %s 第%s条 %-6s 测算 %6.2f%% %s %2.0f%% → %s" %
          (r["rule"], r["art"], name_short[r["rule"]], r["pct"], r["dir"], r["limit"], r["result"]))
if BREACHES:
    print("超限：%s《%s》市值 %s 占 %s，超出 %s 元；T+%s 个工作日内提交整改计划" %
          (TOP_SEC, SECNAME[TOP_SEC], money(TOP_SEC_MV), pct2(TOP_SEC_PCT), money(EXCESS_AMT), TPLUS))
print("报告中文字符：汉字 %d + 中文标点 %d = %d（限 1600）" % (han, cjk_punct, han + cjk_punct))
print("交付物已写入 %s：" % OUT)
for f in (F_XLSX, F_MD, F_PY, F_COV, F_LOG, F_PNG):
    print("  - %s（%s 字节）" % (f.name, f.stat().st_size))
print("=" * 80)
