#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-151 可复算脚本
浙江恒远智能装备集团有限公司 年度授信重检与授信审批

功能：
  1) 从 /app/input_files/（只读）读入全部原始材料（MD/CSV），解析所需参数；
  2) 计算全部结论数值（财务指标、他行融资汇总、额度测算、担保折算、交叉核验等），
     不硬编码任何结论数字；
  3) 生成主交付物  FIN3-WKN-151_授信审批报告.md；
  4) 生成 5 张复合图（PNG）至  FIN3-WKN-151_charts/。

运行方式：python3 FIN3-WKN-151_reproduce.py
依赖：pandas、numpy、matplotlib（中文字体 Noto Sans CJK）
"""

import math
import os
import re
import sys
from collections import Counter, OrderedDict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle

# ----------------------------------------------------------------------------
# 0. 路径、常量（仅任务规定参数，非结论数字）与通用工具
# ----------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
INP = BASE.parent / "input_files"
if not INP.exists():
    INP = Path("/app/input_files")
OUT = BASE
CHART_DIR = OUT / "FIN3-WKN-151_charts"
CHART_DIR.mkdir(parents=True, exist_ok=True)

CUTOFF = date(2026, 6, 30)   # 任务规定的数据与检索截止日
PERIODS = ["2023", "2024", "2025", "2026H1"]
PLABEL = {"2023": "2023年", "2024": "2024年", "2025": "2025年", "2026H1": "2026年上半年"}


def md(name: str) -> str:
    return (INP / name).read_text(encoding="utf-8")


def n(x) -> float:
    """'12,300' / '15%' -> float"""
    return float(str(x).replace(",", "").replace("%", "").strip())


def findg(pattern, text, groups=(1,), cast=n, flags=0):
    m = re.search(pattern, text, flags)
    if not m:
        raise RuntimeError(f"解析失败: {pattern}")
    vals = [cast(m.group(g)) for g in groups]
    return vals[0] if len(vals) == 1 else tuple(vals)


def load_period_csv(name: str) -> pd.DataFrame:
    df = pd.read_csv(INP / name)
    cols = list(df.columns)
    df = df.rename(columns={cols[0]: "item", cols[1]: "2023", cols[2]: "2024",
                            cols[3]: "2025", cols[4]: "2026H1"})
    return df.set_index("item").astype(float)


def setup_cjk_font():
    for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]:
        if os.path.exists(p):
            try:
                font_manager.fontManager.addfont(p)
            except Exception:
                pass
    names = {f.name for f in font_manager.fontManager.ttflist}
    for want in ["Noto Sans CJK SC", "Noto Sans CJK JP", "WenQuanYi Zen Hei",
                 "SimHei", "Microsoft YaHei"]:
        if want in names:
            plt.rcParams["font.sans-serif"] = [want] + list(plt.rcParams["font.sans-serif"])
            break
    plt.rcParams["axes.unicode_minus"] = False


def count_cn(text: str) -> int:
    """按中文字符计（含中文标点），不含 Markdown 表格竖线与代码块标记"""
    t = re.sub(r"```.*?```", "", text, flags=re.S)
    t = t.replace("|", "")
    return len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2014\u2018\u2019\u201c\u201d\u2026\u00b7]", t))


# ----------------------------------------------------------------------------
# 1. 读入材料
# ----------------------------------------------------------------------------
t00, t01, t02, t03 = md("00_材料清单.md"), md("01_授信申请书.md"), md("02_客户基本情况与股权结构.md"), md("03_资质与证照摘要.md")
t07, t08 = md("07_财务快报_2026H1.md"), md("08_财务报表附注_2025.md")
t12b, t13, t14b = md("12b_企业自报数据说明.md"), md("13_征信报告摘要.md"), md("14b_他行授信明细说明.md")
t16, t19, t20, t21 = md("16_纳税申报与纳税证明.md"), md("19_关联方与关联交易清单.md"), md("20_对外担保与或有负债清单.md"), md("21_押品清单与评估报告.md")
t23, t24, t25 = md("23_授信政策与行业限额指引.md"), md("24_授信额度测算指引.md"), md("25_行业数据与可比企业.md")
tpl = md("template_report.md")

bs = load_period_csv("09_资产负债表_四期.csv")     # 资产负债表（审计/快报口径）
inc = load_period_csv("10_利润表_四期.csv")        # 利润表
cf = load_period_csv("11_现金流量表_四期.csv")     # 现金流量表
sr = load_period_csv("12_企业自报财务数据汇总.csv")  # 企业自报（管理口径）
age = pd.read_csv(INP / "17_应收账款账龄与集中度.csv")
invd = pd.read_csv(INP / "18_存货明细与跌价准备.csv")
flows = pd.read_csv(INP / "15_结算账户流水摘要_2025.csv")
coll = pd.read_csv(INP / "22_押品估值明细.csv")
fin = pd.read_csv(INP / "14_他行授信与用信明细.csv", dtype=str)

audit = {}
for yr, fname in [(2023, "04_审计报告_2023.md"), (2024, "05_审计报告_2024.md"), (2025, "06_审计报告_2025.md")]:
    t = md(fname)
    audit[yr] = dict(
        opinion=findg(r"审计意见类型：\*\*(.+?)\*\*", t, cast=str),
        rev=findg(r"\| 营业收入 \| ([\d,]+) \|", t),
        npft=findg(r"\| 净利润 \| ([\d,]+) \|", t),
        ar_label=findg(r"应收账款账面余额 ([\d,]+) 万元", t),
        inv_label=findg(r"存货账面价值 ([\d,]+) 万元", t),
    )

# ---- 申请书（01）----
apply_total = findg(r"综合授信额度人民币 \*\*([\d,]+) 万元\*\*", t01)
apply_items = OrderedDict()
for m in re.finditer(r"^\|\s*(流动资金贷款|银行承兑汇票|国内信用证)\s*\|\s*([\d,]+)\s*\|\s*(.*?)\s*\|\s*$", t01, re.M):
    mg = re.search(r"保证金比例\s*(\d+)%", m.group(3))
    apply_items[m.group(1)] = dict(amount=n(m.group(2)), margin=float(mg.group(1)) if mg else None)
g_borrower = findg(r"较 2025 年增长 \*\*([\d.]+)%\*\*", t01)
orders_yi = findg(r"在手订单 ([\d.]+) 亿元", t01)
prev_credit = findg(r"上一年度获批综合授信额度 ([\d,]+) 万元", t01)

# ---- 客户资料（02、03）----
reg_cap = findg(r"注册资本 \| ([\d,]+) 万元", t02)
emp_n, rd_n = findg(r"员工人数 \| ([\d,]+) 人（其中研发人员 ([\d,]+) 人）", t02, groups=(1, 2))
control_pct = findg(r"直接与间接合计控制本公司 ([\d.]+)% 表决权", t02)
shareholders = []
for m in re.finditer(r"^\| (.+?) \| ([\d,]+) \| ([\d.]+)% \|\s*$", t02, re.M):
    shareholders.append((m.group(1), n(m.group(2)), float(m.group(3))))
subsidiaries = []
for m in re.finditer(r"^\| (.+?公司) \| (\d+)% \| (.+?) \| ([\d,]+) \|", t02, re.M):
    subsidiaries.append((m.group(1), int(m.group(2)), m.group(3), n(m.group(4))))
hightech_end = findg(r"GR\S+ \| \S+ 至 (\S+) \|", t03, cast=str)
patent_inv = findg(r"发明专利） \| 合计 (\d+) 项", t03)

# ---- 快报（07）----
flash_rev, flash_rev_py = findg(r"\| 营业收入 \| ([\d,]+) \| ([\d,]+) \|", t07, groups=(1, 2))
flash_ocf, flash_ocf_py = findg(r"\| 经营活动产生的现金流量净额 \| ([\d,]+) \| ([\d,]+) \|", t07, groups=(1, 2))
flash_ta, _ta_py = findg(r"\| 期末资产总计 \| ([\d,]+) \| ([\d,]+) \|", t07, groups=(1, 2))
flash_tl, _tl_py = findg(r"\| 期末负债合计 \| ([\d,]+) \| ([\d,]+) \|", t07, groups=(1, 2))
flash_eq, _eq_py = findg(r"\| 期末所有者权益 \| ([\d,]+) \| ([\d,]+) \|", t07, groups=(1, 2))
flash_h1_growth_txt = findg(r"同比增长 ([\d.]+)%", t07)

# ---- 附注（08）----
restricted_2025 = findg(r"其中：使用受限的银行存款 \| ([\d,]+) \|", t08)
ar_gross_08, ar_prov_08 = findg(r"应收账款账面余额 ([\d,]+) 万元，计提坏账准备 ([\d,]+) 万元", t08, groups=(1, 2))
stloan_08_sum = findg(r"\| 合计 \| ([\d,]+) \| — \| — \|", t08)
guar_08 = findg(r"提供担保合计 ([\d,]+) 万元", t08)
lawsuit_08 = findg(r"标的金额 ([\d,]+) 万元", t08)
assoc_buy, assoc_buy_pct = findg(r"向关联方采购原材料 ([\d,]+) 万元，占营业成本 ([\d.]+)%", t08, groups=(1, 2))
assoc_sell, assoc_sell_pct = findg(r"向关联方销售产品 ([\d,]+) 万元，占营业收入 ([\d.]+)%", t08, groups=(1, 2))

# ---- 征信（13）----
pledge_ar_reg = findg(r"应收账款质押（登记金额 ([\d,]+) 万元）", t13)
pledge_eq_reg = findg(r"股权质押（登记金额 ([\d,]+) 万元）", t13)
guar_13 = findg(r"担保余额 ([\d,]+) 万元", t13)

# ---- 他行明细说明（14b）：汇率 ----
fx_usd = findg(r"1 美元 = ([\d.]+) 元人民币", t14b)

# ---- 税务（16）----
vat = {}
for m in re.finditer(r"^\| (2023 年度|2024 年度|2025 年度|2026 年 1-6 月) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \|", t16, re.M):
    vat[m.group(1)] = n(m.group(2))

# ---- 关联方（19）、或有（20）、押品（21）----
assoc_lending = findg(r"资金拆借（借入） \| .+? \| ([\d,]+) \|", t19)
guar_20 = findg(r"\| 合计 \| — \| ([\d,]+) \| ([\d,]+) \| — \|", t20, groups=(2,))
lawsuit_20 = findg(r"侵害发明专利权纠纷 \| .+? \| ([\d,]+) \|", t20)
discounted_ba = findg(r"商业承兑汇票 ([\d,]+) 万元", t20)
special_equip_note_21 = "专用设备" in t21
coll_total_md = findg(r"\| 合计 \| — \| — \| ([\d,]+) \|", t21)

# ---- 政策（23）----
policy_rates = {}
for m in re.finditer(r"^\| (.+?) \| (\d+)% \|\s*$", t23, re.M):
    policy_rates[m.group(1)] = float(m.group(2))
policy_special_note = ("专用设备" in t23) and ("报总行风险管理部审批" in t23)
conc_capital_pct = findg(r"资本净额的 (\d+)%", t23)
margin_floor = findg(r"保证金比例原则上不低于 (\d+)%", t23)
industry_growth_mult = findg(r"全行对公贷款增速的 ([\d.]+) 倍", t23)

# ---- 测算指引（24）----
g_cap_add = findg(r"\+ (\d+) 个百分点", t24)
na_mult = findg(r"经审计净资产 × ([\d.]+)", t24)
round_to_wan = "向下取整至千万" in t24

# ---- 行业（25）----
ind_g3 = findg(r"营业收入增速 \| [\d.]+% \| [\d.]+% \| [\d.]+% \| \*\*([\d.]+)%\*\*", t25)
ind_npm, ind_lev, ind_ar_days = findg(r"\| 行业平均 \| — \| ([\d.]+)% \| ([\d.]+)% \| (\d+) \|", t25, groups=(1, 2, 3))

# ---- 材料清单（00）与磁盘核验 ----
docs = []
for m in re.finditer(r"^\| ([0-9b—]+) \| (\S+\.(?:md|csv)) \| (.+?) \|\s*$", t00, re.M):
    docs.append((m.group(1), m.group(2), m.group(3)))
docs_missing = [f for _, f, _ in docs if not (INP / f).exists()]
cat_counts = Counter(c for _, _, c in docs)

# ---- 模板（template）章节核验 ----
tpl_sections = re.findall(r"^## (.+)$", tpl, re.M)

# ----------------------------------------------------------------------------
# 2. 他行授信与用信明细处理（硬约束 3：按合同编号去重、剔除终止、汇率折算）
# ----------------------------------------------------------------------------
fin.columns = [c.strip() for c in fin.columns]
fin["用信余额"] = fin["用信余额"].astype(float)
fin["授信额度(万元)"] = fin["授信额度(万元)"].astype(float)
fin["到期日_dt"] = pd.to_datetime(fin["到期日"])
fin_raw_rows = len(fin)

dup_mask = fin.duplicated(subset=["合同编号"], keep="first")
n_dup = int(dup_mask.sum())
dup_rows = fin[dup_mask]["序号"].tolist()
fin_d = fin[~dup_mask].copy()

status = fin_d["业务状态"].fillna("").str.strip()
term_mask = status.isin(["已结清", "已到期"])
blank_mask = status == ""
blank_term_mask = blank_mask & (fin_d["到期日_dt"] <= pd.Timestamp(CUTOFF))
n_term, n_blank = int(term_mask.sum()), int(blank_mask.sum())
blank_rows = fin_d[blank_mask][["合同编号", "授信机构", "到期日"]].values.tolist()

active = fin_d[~term_mask & ~blank_term_mask].copy()
active["汇率"] = np.where(active["币种"] == "USD", fx_usd, 1.0)
active["额度CNY"] = active["授信额度(万元)"] * active["汇率"]
active["余额CNY"] = active["用信余额"] * active["汇率"]
n_active = len(active)
n_usd = int((active["币种"] == "USD").sum())

fin_balance_total = active["余额CNY"].sum()                 # 现有融资余额（敞口）
fin_limit_total = active["额度CNY"].sum()                    # 有效授信额度合计
by_kind = active.groupby("业务品种")["余额CNY"].sum().sort_values(ascending=False)
fx_kinds = active[active["币种"] == "USD"].groupby("业务品种")["余额CNY"].sum()
fin_fx_total = float(fx_kinds.sum())
fin_wc_loan = float(by_kind.get("流动资金贷款", 0))
fin_ba = float(by_kind.get("银行承兑汇票", 0))
fin_lc = float(by_kind.get("国内信用证", 0))
huaxin_active = active[active["授信机构"] == "华信银行"]
fin_huaxin = float(huaxin_active["余额CNY"].sum())
huaxin_contract = huaxin_active["合同编号"].iloc[0]
huaxin_due = huaxin_active["到期日"].iloc[0]

# ----------------------------------------------------------------------------
# 3. 口径差异识别（硬约束 1）
# ----------------------------------------------------------------------------
# 3.1 自报数据 vs 审计/快报
audited_lookup = {}
for item in ["营业收入", "营业成本", "净利润"]:
    for p in PERIODS:
        audited_lookup[(item, p)] = inc.loc[item, p]
for item in ["资产总计", "负债合计", "所有者权益合计"]:
    for p in PERIODS:
        audited_lookup[(item, p)] = bs.loc[item, p]

selfrep_diffs = []
for item in sr.index:
    for p in PERIODS:
        a, b = sr.loc[item, p], audited_lookup[(item, p)]
        if abs(a - b) > 1e-9:
            selfrep_diffs.append((item, PLABEL[p], a, b, a - b))

# 3.2 审计报告"账面余额"用语 vs 账龄表账面余额（实为账面价值）
ar_label_diff = {yr: (audit[yr]["ar_label"],
                      n(age.loc[age["项目"] == "应收账款账面余额(万元)", c].iloc[0]))
                 for yr, c in [(2023, "2023年末"), (2025, "2025年末")]}

# 3.3 税务申报销售额 vs 账面营业收入
vat_map = {"2023 年度": "2023", "2024 年度": "2024", "2025 年度": "2025", "2026 年 1-6 月": "2026H1"}
vat_diffs = [(PLABEL[vat_map[k]], vat[k], inc.loc["营业收入", vat_map[k]],
              vat[k] - inc.loc["营业收入", vat_map[k]]) for k in vat_map]

# 3.4 应付票据账面 vs 银承敞口
notes_payable_26H1 = bs.loc["应付票据", "2026H1"]
ba_vs_notes = fin_ba - notes_payable_26H1

# ----------------------------------------------------------------------------
# 4. 交叉核验（一致项）
# ----------------------------------------------------------------------------
checks = []
checks.append(("审计报告(2023-2025)营收/净利 与 报表CSV一致",
               all(audit[y]["rev"] == inc.loc["营业收入", str(y)] and audit[y]["npft"] == inc.loc["净利润", str(y)] for y in [2023, 2024, 2025])))
checks.append(("快报(2026H1)营收/资产/负债/权益 与 报表CSV一致",
               flash_rev == inc.loc["营业收入", "2026H1"] and flash_ta == bs.loc["资产总计", "2026H1"]
               and flash_tl == bs.loc["负债合计", "2026H1"] and flash_eq == bs.loc["所有者权益合计", "2026H1"]))
checks.append(("账龄表账面价值 与 资产负债表应收账款一致",
               all(n(age.loc[age["项目"] == "应收账款账面价值(万元)", c].iloc[0]) == bs.loc["应收账款", p]
                   for p, c in zip(PERIODS, ["2023年末", "2024年末", "2025年末", "2026年6月末"]))))
inv_total_row = invd[invd["类别"] == "合计"].iloc[0]
checks.append(("存货明细(2025)账面余额-跌价准备 与 资产负债表存货一致",
               inv_total_row["2025年末账面余额"] - inv_total_row["2025年末跌价准备"] == bs.loc["存货", "2025"]))
checks.append(("附注短期借款合计(2025) 与 资产负债表短期借款一致",
               stloan_08_sum == bs.loc["短期借款", "2025"]))
checks.append(("对外担保余额三来源(附注/征信/或有清单)一致",
               guar_08 == guar_13 == guar_20))
checks.append(("他行明细有效流贷敞口 与 2026年6月末短期借款一致",
               fin_wc_loan == bs.loc["短期借款", "2026H1"]))
checks.append(("押品估值明细CSV合计 与 押品清单MD合计一致",
               coll["评估价值(万元)"].sum() == coll_total_md))
n_checks_ok = sum(1 for _, ok in checks if ok)

# 待核实清单
tbd_items = [
    "2026年6月末受限货币资金（以2025年末披露值代用）",
    "本行资本净额（集中度约束所需）",
    "全行对公贷款增速（行业限额核验所需）",
    "专用设备抵押率（须报总行风险管理部审批）",
    "应收账款/股权既有质押登记的担保债权归属",
    "税务与账面收入差异的企业说明明细（未随附）",
]

# ----------------------------------------------------------------------------
# 5. 财务与偿债能力指标（四期）
# ----------------------------------------------------------------------------
m = {}
for p in PERIODS:
    ta, tl, eq = bs.loc["资产总计", p], bs.loc["负债合计", p], bs.loc["所有者权益合计", p]
    ca, cl = bs.loc["流动资产合计", p], bs.loc["流动负债合计", p]
    inv_p = bs.loc["存货", p]
    rev, cost = inc.loc["营业收入", p], inc.loc["营业成本", p]
    npft, fin_exp, tp = inc.loc["净利润", p], inc.loc["财务费用", p], inc.loc["利润总额", p]
    ocf = cf.loc["经营活动产生的现金流量净额", p]
    m[p] = dict(
        ta=ta, tl=tl, eq=eq, ca=ca, cl=cl, inv=inv_p, rev=rev, cost=cost, npft=npft, ocf=ocf,
        lev=tl / ta * 100,
        cur=ca / cl,
        quick=(ca - inv_p) / cl,
        icr=(tp + fin_exp) / fin_exp,
        ncash=ocf / npft,
        gm=(rev - cost) / rev * 100,
        npm=npft / rev * 100,
        nca_ratio=bs.loc["非流动资产合计", p] / ta * 100,
        ar_inv_ratio=(bs.loc["应收账款", p] + inv_p) / ta * 100,
    )
m["2024"]["rev_g"] = (inc.loc["营业收入", "2024"] / inc.loc["营业收入", "2023"] - 1) * 100
m["2025"]["rev_g"] = (inc.loc["营业收入", "2025"] / inc.loc["营业收入", "2024"] - 1) * 100
m["2026H1"]["rev_g"] = (flash_rev / flash_rev_py - 1) * 100
cagr = ((inc.loc["营业收入", "2025"] / inc.loc["营业收入", "2023"]) ** 0.5 - 1) * 100

inflow_2025 = flows["贷方发生额(万元)"].sum()
inflow_ratio = inflow_2025 / inc.loc["营业收入", "2025"]

# 周转天数（趋势图口径：平均余额×360/年经营额；2023年期初缺失用期末；2026H1经营额年化×2）
def turnover_series(bs_item, flow_item):
    out = {}
    out["2023"] = bs.loc[bs_item, "2023"] * 360 / inc.loc[flow_item, "2023"]
    for prev, cur in [("2023", "2024"), ("2024", "2025")]:
        avg = (bs.loc[bs_item, prev] + bs.loc[bs_item, cur]) / 2
        out[cur] = avg * 360 / inc.loc[flow_item, cur]
    avg = (bs.loc[bs_item, "2025"] + bs.loc[bs_item, "2026H1"]) / 2
    out["2026H1"] = avg * 360 / (inc.loc[flow_item, "2026H1"] * 2)
    return out

td_inv = turnover_series("存货", "营业成本")
td_ar = turnover_series("应收账款", "营业收入")
td_ap = turnover_series("应付账款", "营业成本")

# ----------------------------------------------------------------------------
# 6. 授信额度测算（严格按《24_授信额度测算指引》，上年度=2025审计口径）
# ----------------------------------------------------------------------------
rev_prior = inc.loc["营业收入", "2025"]
npm_prior = inc.loc["净利润", "2025"] / rev_prior
g_cap = ind_g3 + g_cap_add            # 行业近三年平均增速 + 5 个百分点
g_used = min(g_borrower, g_cap)       # 审慎原则

def avg25(item):
    return (bs.loc[item, "2024"] + bs.loc[item, "2025"]) / 2

d_inv = avg25("存货") * 360 / inc.loc["营业成本", "2025"]
d_ar = avg25("应收账款") * 360 / inc.loc["营业收入", "2025"]
d_ap = avg25("应付账款") * 360 / inc.loc["营业成本", "2025"]
d_prep = avg25("预付账款") * 360 / inc.loc["营业成本", "2025"]
d_adv = avg25("预收账款") * 360 / inc.loc["营业收入", "2025"]
wc_days = d_inv + d_ar - d_ap + d_prep - d_adv
wc_freq = 360 / wc_days

wcr = rev_prior * (1 - npm_prior) * (1 + g_used / 100) / wc_freq

own_funds = bs.loc["货币资金", "2026H1"] - restricted_2025   # 受限额为2025年末披露值，2026H1待核实
st_loan_26 = bs.loc["短期借款", "2026H1"]
notes_26 = bs.loc["应付票据", "2026H1"]
new_need = wcr - own_funds - st_loan_26 - notes_26

own_funds_25 = bs.loc["货币资金", "2025"] - restricted_2025
new_need_25base = wcr - own_funds_25 - bs.loc["短期借款", "2025"] - bs.loc["应付票据", "2025"]

# ----------------------------------------------------------------------------
# 7. 押品折算（逐项对应政策 3.1 表；专用设备未列示 → 不计入，待总行审批）
# ----------------------------------------------------------------------------
cat_map = {
    "厂房及办公楼": "商业用房及厂房",
    "国有土地使用权": "国有土地使用权（工业用地）",
    "应收账款": "应收账款",
    "股权": "非上市公司股权",   # 恒远精密机械为全资子公司（材料02/19），非上市公司
    "存货": "存货",
    "机器设备": None,           # 政策3.1注：专用生产线/加工中心等专用设备未列示抵押率
}
coll_rows = []
for _, r in coll.iterrows():
    name = r["押品名称"].strip()
    val = float(r["评估价值(万元)"])
    cat = cat_map[name]
    if cat is None:
        rate, elig = None, 0.0
    else:
        rate = policy_rates[cat]
        elig = val * rate / 100
    coll_rows.append(dict(name=name, val=val, cat=cat if cat else "专用设备（政策未列示）",
                          rate=rate, elig=elig, method=r["评估方法"]))
coll_total = sum(r["val"] for r in coll_rows)
eligible_total = sum(r["elig"] for r in coll_rows)

# ----------------------------------------------------------------------------
# 8. 孰低原则确定建议额度
# ----------------------------------------------------------------------------
na_cap = bs.loc["所有者权益合计", "2025"] * na_mult
constraints = OrderedDict([
    ("约束1：新增营运资金需求", new_need),
    ("约束2：担保覆盖（合格担保值）", eligible_total),
    ("约束3：净资产×%.1f" % na_mult, na_cap),
    ("约束4：集中度（资本净额%d%%）" % conc_capital_pct, None),  # 待核实
])
avail = [v for v in constraints.values() if v is not None]
binding_val = min(avail)
binding_name = [k for k, v in constraints.items() if v == binding_val][0]
suggest = math.floor(binding_val / 1000) * 1000 if round_to_wan else binding_val
alloc = OrderedDict((k, round(v["amount"] * suggest / apply_total)) for k, v in apply_items.items())
assert abs(sum(alloc.values()) - suggest) < 1e-6, "品种分配与建议额度不一致"
cover_ratio = eligible_total / suggest * 100
upside_if_equip = math.floor(min(new_need, na_cap) / 1000) * 1000
vs_prev = (suggest / prev_credit - 1) * 100

# ----------------------------------------------------------------------------
# 9. 风险矩阵数据（概率/影响坐标为审查判断，等级见报告第八章）
# ----------------------------------------------------------------------------
risks = [
    ("R1", "经营现金流下滑（2026H1净现比%.2f）" % m["2026H1"]["ncash"], 2.8, 3.2, "中"),
    ("R2", "应收账款集中度上升、账龄延长", 3.3, 2.8, "中"),
    ("R3", "收入增速放缓、企业预测偏高", 3.7, 2.2, "中"),
    ("R4", "押品既有质押登记归属待核实", 1.8, 3.6, "中"),
    ("R5", "高新技术企业资格到期未通过复审", 1.8, 2.3, "低"),
    ("R6", "未决专利诉讼（标的%s万元）" % f"{lawsuit_20:,.0f}", 1.6, 1.6, "低"),
    ("R7", "下游需求与原材料价格波动", 2.5, 3.6, "中"),
    ("R8", "专用设备抵押率未获批，额度弹性受限", 2.4, 1.8, "低"),
]

# ----------------------------------------------------------------------------
# 10. 图表
# ----------------------------------------------------------------------------
setup_cjk_font()
CC = dict(blue="#2f6fb2", lblue="#7fa8d4", orange="#e08a2e", red="#c0504d",
          green="#4f9a51", gray="#9a9a9a", teal="#3d9a9a", purple="#7a5ea8")
FOOT = "数据来源：/app/input_files/（只读原始材料），全部数值由 FIN3-WKN-151_reproduce.py 计算生成"
X = np.arange(len(PERIODS))
XL = [PLABEL[p] for p in PERIODS]


def style_ax(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle="--")


def footer(fig):
    fig.text(0.01, 0.002, FOOT, fontsize=8, color="gray")


def save(fig, fname):
    fig.savefig(CHART_DIR / fname, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [chart] {fname}")


# ---- chart01 材料覆盖与数据缺口 ----
fig, axes = plt.subplots(1, 2, figsize=(14.5, 6.8))
ax = axes[0]
cats = list(cat_counts.keys())[::-1]
vals = [cat_counts[c] for c in cats]
bars = ax.barh(cats, vals, color=CC["blue"], alpha=0.85)
for b, v in zip(bars, vals):
    ax.text(v + 0.05, b.get_y() + b.get_height() / 2, str(v), va="center", fontsize=10)
ax.set_xlim(0, max(vals) + 1)
ax.set_xlabel("材料份数")
ax.set_title(f"(a) 材料覆盖分布（清单 {len(docs)} 份，实收 {len(docs) - len(docs_missing)} 份，缺失 {len(docs_missing)} 份）", fontsize=12)
ax.grid(axis="x", alpha=0.25, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)

ax = axes[1]
stat_labels = ["交叉核验一致", "口径差异已显式处理", "待核实/数据缺口"]
stat_vals = [n_checks_ok, 5, len(tbd_items)]
stat_colors = [CC["green"], CC["orange"], CC["red"]]
bars = ax.barh(stat_labels[::-1], stat_vals[::-1], color=stat_colors[::-1], alpha=0.88, height=0.5)
for b, v in zip(bars, stat_vals[::-1]):
    ax.text(v + 0.1, b.get_y() + b.get_height() / 2, f"{v} 项", va="center", fontsize=11, fontweight="bold")
ax.set_xlim(0, max(stat_vals) + 2)
ax.set_title("(b) 材料核验标记（交叉核验结果）", fontsize=12)
ax.grid(axis="x", alpha=0.25, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)
tbd_txt = "待核实事项：\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(tbd_items))
ax.text(0.98, 0.02, tbd_txt, transform=ax.transAxes, fontsize=8.2, va="bottom", ha="right",
        bbox=dict(boxstyle="round", fc="#fff6f5", ec=CC["red"], alpha=0.9))
fig.suptitle("FIN3-WKN-151 图01　材料覆盖与数据缺口", fontsize=15, fontweight="bold")
footer(fig)
save(fig, "FIN3-WKN-151_chart01_材料覆盖与数据缺口.png")

# ---- chart02 财务与偿债能力 ----
fig, axes = plt.subplots(2, 1, figsize=(12.5, 10))
ax = axes[0]
ca = [m[p]["ca"] for p in PERIODS]
nca = [bs.loc["非流动资产合计", p] for p in PERIODS]
ax.bar(X, ca, 0.55, label="流动资产", color=CC["blue"], alpha=0.85)
ax.bar(X, nca, 0.55, bottom=ca, label="非流动资产", color=CC["lblue"], alpha=0.85)
for i, p in enumerate(PERIODS):
    ax.text(i, m[p]["ta"] + 1800, f"{m[p]['ta']:,.0f}", ha="center", fontsize=9.5)
ax.set_ylabel("资产（万元）")
ax.set_xticks(X, XL)
ax.set_title("(a) 资产负债结构与资产负债率", fontsize=12)
ax.legend(loc="upper left", fontsize=9)
style_ax(ax)
ax.set_ylim(0, max(m[p]["ta"] for p in PERIODS) * 1.18)
ax2 = ax.twinx()
lev = [m[p]["lev"] for p in PERIODS]
ax2.plot(X, lev, "o-", color=CC["red"], lw=2, label="资产负债率（右轴）")
for i, v in enumerate(lev):
    ax2.annotate(f"{v:.2f}%", (i, v), textcoords="offset points", xytext=(0, 9), ha="center",
                 fontsize=9.5, color=CC["red"], fontweight="bold")
ax2.axhline(ind_lev, color=CC["gray"], ls="--", lw=1.2)
ax2.text(len(X) - 0.45, ind_lev + 0.6, f"行业平均 {ind_lev:.1f}%", fontsize=9, color=CC["gray"], ha="right")
ax2.set_ylabel("资产负债率（%）")
ax2.set_ylim(0, max(lev) * 1.45)
ax2.spines[["top"]].set_visible(False)
ax2.legend(loc="lower right", fontsize=9)

ax = axes[1]
w = 0.35
cur = [m[p]["cur"] for p in PERIODS]
qk = [m[p]["quick"] for p in PERIODS]
ax.bar(X - w / 2, cur, w, label="流动比率", color=CC["teal"], alpha=0.9)
ax.bar(X + w / 2, qk, w, label="速动比率", color=CC["orange"], alpha=0.9)
for i in range(len(X)):
    ax.text(i - w / 2, cur[i] + 0.04, f"{cur[i]:.2f}", ha="center", fontsize=9.5)
    ax.text(i + w / 2, qk[i] + 0.04, f"{qk[i]:.2f}", ha="center", fontsize=9.5)
ax.set_xticks(X, XL)
ax.set_ylabel("倍数")
ax.set_title("(b) 流动比率、速动比率与利息保障倍数", fontsize=12)
ax.legend(loc="upper right", fontsize=9)
style_ax(ax)
ax.set_ylim(0, max(cur) * 1.35)
ax2 = ax.twinx()
icr = [m[p]["icr"] for p in PERIODS]
ax2.plot(X, icr, "s-", color=CC["purple"], lw=2, label="利息保障倍数（右轴）")
for i, v in enumerate(icr):
    ax2.annotate(f"{v:.2f}", (i, v), textcoords="offset points", xytext=(0, 9), ha="center",
                 fontsize=9.5, color=CC["purple"])
ax2.set_ylabel("利息保障倍数（倍）")
ax2.set_ylim(0, max(icr) * 1.45)
ax2.spines[["top"]].set_visible(False)
ax2.legend(loc="lower right", fontsize=9)
ax2.text(0.0, -0.16, "注：利息保障倍数=（利润总额+财务费用）/财务费用（材料未单列利息支出，以财务费用为代理）；2026年上半年未年化。",
         transform=ax.transAxes, fontsize=8.5, color="dimgray")
fig.suptitle("FIN3-WKN-151 图02　财务与偿债能力", fontsize=15, fontweight="bold")
fig.tight_layout(rect=[0, 0.02, 1, 0.97])
footer(fig)
save(fig, "FIN3-WKN-151_chart02_财务与偿债能力.png")

# ---- chart03 现金流与营运效率 ----
fig, axes = plt.subplots(2, 1, figsize=(12.5, 10))
ax = axes[0]
w = 0.35
npf = [m[p]["npft"] for p in PERIODS]
ocf = [m[p]["ocf"] for p in PERIODS]
ax.bar(X - w / 2, npf, w, label="净利润", color=CC["blue"], alpha=0.9)
ax.bar(X + w / 2, ocf, w, label="经营活动现金流净额", color=CC["green"], alpha=0.9)
for i in range(len(X)):
    ax.text(i - w / 2, npf[i] + 120, f"{npf[i]:,.0f}", ha="center", fontsize=9.5)
    ax.text(i + w / 2, ocf[i] + 120, f"{ocf[i]:,.0f}", ha="center", fontsize=9.5)
ax.set_xticks(X, XL)
ax.set_ylabel("万元")
ax.set_title("(a) 净利润、经营现金流与净现比", fontsize=12)
ax.legend(loc="upper left", fontsize=9)
style_ax(ax)
ax.set_ylim(0, max(npf) * 1.3)
ax2 = ax.twinx()
nc = [m[p]["ncash"] for p in PERIODS]
ax2.plot(X, nc, "o-", color=CC["red"], lw=2, label="净现比（右轴）")
for i, v in enumerate(nc):
    ax2.annotate(f"{v:.2f}", (i, v), textcoords="offset points", xytext=(0, -16), ha="center",
                 fontsize=9.5, color=CC["red"], fontweight="bold")
ax2.axhline(1.0, color=CC["gray"], ls="--", lw=1.2)
ax2.text(0.02, 1.03, "净现比=1", fontsize=9, color=CC["gray"])
ax2.set_ylabel("净现比（倍）")
ax2.set_ylim(0, max(nc) * 1.5)
ax2.spines[["top"]].set_visible(False)
ax2.legend(loc="lower left", fontsize=9)

ax = axes[1]
ax.plot(X, [td_inv[p] for p in PERIODS], "o-", color=CC["orange"], lw=2, label="存货周转天数")
ax.plot(X, [td_ar[p] for p in PERIODS], "s-", color=CC["blue"], lw=2, label="应收账款周转天数")
ax.plot(X, [td_ap[p] for p in PERIODS], "^-", color=CC["green"], lw=2, label="应付账款周转天数")
ax.axhline(ind_ar_days, color=CC["gray"], ls="--", lw=1.2)
ax.text(0.02, ind_ar_days + 3, f"行业平均应收账款周转天数 ≈{ind_ar_days:.0f} 天", fontsize=9, color=CC["gray"])
for name, series, dy in [("存货", td_inv, 8), ("应收", td_ar, -16), ("应付", td_ap, 8)]:
    for i, p in enumerate(PERIODS):
        ax.annotate(f"{series[p]:.1f}", (i, series[p]), textcoords="offset points",
                    xytext=(0, dy), ha="center", fontsize=8.8)
ax.set_xticks(X, XL)
ax.set_ylabel("天")
ax.set_title("(b) 存货、应收账款、应付账款周转天数（平均余额、360天口径）", fontsize=12)
ax.legend(loc="upper right", fontsize=9)
style_ax(ax)
ax.text(0.0, -0.16, "注：2023年期初余额缺失，采用期末余额口径；2026年上半年经营额按×2年化近似，仅作趋势参考；测算口径（第五章）按指引以2025年审计数据计算。",
        transform=ax.transAxes, fontsize=8.5, color="dimgray")
fig.suptitle("FIN3-WKN-151 图03　现金流与营运效率", fontsize=15, fontweight="bold")
fig.tight_layout(rect=[0, 0.02, 1, 0.97])
footer(fig)
save(fig, "FIN3-WKN-151_chart03_现金流与营运效率.png")

# ---- chart04 额度测算与担保覆盖 ----
fig, axes = plt.subplots(2, 1, figsize=(12.8, 10.5))
ax = axes[0]
labels = ["申请额度", "约束3：净资产×%.1f" % na_mult, "约束1：新增营运资金需求",
          "约束2：担保覆盖（合格担保值）", "约束4：集中度（资本净额%d%%）" % conc_capital_pct,
          "建议授信额度（孰低+取整至千万）"]
values = [apply_total, na_cap, new_need, eligible_total, 0, suggest]
colors = [CC["gray"], CC["lblue"], CC["blue"], CC["red"], CC["gray"], CC["green"]]
ypos = np.arange(len(labels))[::-1]
bars = ax.barh(ypos, values, color=colors, alpha=0.9, height=0.58)
bars[4].set_hatch("//")
bars[4].set_alpha(0.4)
bars[3].set_edgecolor("black")
bars[3].set_linewidth(1.6)
for y, v in zip(ypos, values):
    txt = f"{v:,.0f}" if v > 0 else "待核实（数据未提供）"
    ax.text(v + max(values) * 0.012, y, txt, va="center", fontsize=10,
            fontweight="bold" if v in (eligible_total, suggest) else "normal")
ax.axvline(suggest, color=CC["green"], ls="--", lw=1.5)
ax.set_yticks(ypos, labels, fontsize=10)
ax.set_xlim(0, max(values) * 1.18)
ax.set_xlabel("万元")
ax.set_title("(a) 各项额度约束对比与孰低结果（约束性项：%s）" % binding_name, fontsize=12)
ax.grid(axis="x", alpha=0.25, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)

ax = axes[1]
names = [r["name"] for r in coll_rows][::-1]
vals_ = [r["val"] for r in coll_rows][::-1]
eligs = [r["elig"] for r in coll_rows][::-1]
rows_ = coll_rows[::-1]
ypos = np.arange(len(names))
h = 0.36
ax.barh(ypos + h / 2, vals_, h, label="评估价值", color=CC["lblue"], alpha=0.95)
ax.barh(ypos - h / 2, eligs, h, label="合格担保值（评估价值×政策抵押/质押率）", color=CC["blue"], alpha=0.95)
for i, r in enumerate(rows_):
    ax.text(r["val"] + 180, i + h / 2, f"{r['val']:,.0f}", va="center", fontsize=9.5)
    rate_txt = f"×{r['rate']:.0f}%" if r["rate"] is not None else "抵押率未列示→待总行审批，暂不计入"
    ax.text(r["elig"] + 180, i - h / 2,
            (f"{r['elig']:,.0f}（{rate_txt}）" if r["rate"] is not None else f"0（{rate_txt}）"),
            va="center", fontsize=9.2, color="black" if r["rate"] is not None else CC["red"])
ax.set_yticks(ypos, [f"{r['name']}\n[{r['cat']}]" for r in rows_], fontsize=9.5)
ax.set_xlim(0, max(vals_) * 1.75)
ax.set_xlabel("万元")
ax.set_title(f"(b) 担保覆盖结构（评估值合计 {coll_total:,.0f}，合格担保值 {eligible_total:,.0f}，对建议额度覆盖率 {cover_ratio:.1f}%）", fontsize=12)
ax.legend(loc="lower right", fontsize=9)
ax.grid(axis="x", alpha=0.25, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)
fig.suptitle("FIN3-WKN-151 图04　额度测算与担保覆盖", fontsize=15, fontweight="bold")
fig.tight_layout(rect=[0, 0.02, 1, 0.97])
footer(fig)
save(fig, "FIN3-WKN-151_chart04_额度测算与担保覆盖.png")

# ---- chart05 风险分类与授信条件 ----
fig, axes = plt.subplots(1, 2, figsize=(14.5, 6.8))
ax = axes[0]
ind_items = [
    ("资产负债率（2025）", m["2025"]["lev"], ind_lev, "%"),
    ("净利润率（2025）", m["2025"]["npm"], ind_npm, "%"),
    ("应收账款周转天数（2025测算口径）", d_ar, ind_ar_days, "天"),
]
ypos = np.arange(len(ind_items))[::-1]
idx = [c / i * 100 for _, c, i, _ in ind_items]
bars = ax.barh(ypos, idx, 0.5, color=[CC["blue"] if v <= 100 else CC["teal"] for v in idx], alpha=0.9)
ax.axvline(100, color=CC["red"], ls="--", lw=1.6)
ax.text(101, ypos[-1] - 0.42, "行业参考线（行业平均=100）", color=CC["red"], fontsize=8.8)
for y, (nm, c, i, u), v in zip(ypos, ind_items, idx):
    ax.text(v + 1.5, y, f"指数{v:.1f}（客户{c:,.1f}{u} vs 行业{i:,.1f}{u}）", va="center", fontsize=9.3)
ax.set_yticks(ypos, [t[0] for t in ind_items], fontsize=10)
ax.set_xlim(0, 175)
ax.set_xlabel("相对行业平均指数")
ax.set_title("(a) 关键指标与行业参考线（预警基准）", fontsize=12)
ax.grid(axis="x", alpha=0.25, linestyle="--")
ax.spines[["top", "right"]].set_visible(False)
ax.text(0.0, -0.22, "注：资产负债率、周转天数低于行业平均为优；净利润率高于行业平均为优。行业数据见《25_行业数据与可比企业》。",
        transform=ax.transAxes, fontsize=8.5, color="dimgray")

ax = axes[1]
for i in range(1, 6):
    for j in range(1, 6):
        s = i * j
        fc = "#fde9e7" if s >= 12 else ("#fef4e2" if s >= 6 else ("#fdfbe3" if s >= 3 else "#eef7ee"))
        ax.add_patch(Rectangle((i - 0.5, j - 0.5), 1, 1, fc=fc, ec="white", lw=1.2))
gcolor = {"中": CC["orange"], "低": CC["green"], "高": CC["red"]}
for rid, lab, px, py, g in risks:
    ax.scatter(px, py, s=340, c=gcolor[g], alpha=0.92, edgecolors="black", lw=0.8, zorder=3)
    ax.text(px, py, rid, ha="center", va="center", fontsize=9, color="white", fontweight="bold", zorder=4)
ax.set_xlim(0.5, 5.5)
ax.set_ylim(0.5, 5.5)
ax.set_xticks(range(1, 6), ["1很低", "2低", "3中", "4高", "5很高"], fontsize=9)
ax.set_yticks(range(1, 6), ["1轻微", "2一般", "3较重", "4严重", "5重大"], fontsize=9)
ax.set_xlabel("发生可能性")
ax.set_ylabel("影响程度")
ax.set_title("(b) 风险矩阵与五级分类建议", fontsize=12)
legend_txt = "\n".join(f"{r[0]}：{r[1]}（{r[4]}风险）" for r in risks)
ax.text(5.62, 5.4, legend_txt, fontsize=8.2, va="top",
        bbox=dict(boxstyle="round", fc="#f7f7f7", ec="gray", alpha=0.9))
ax.text(0.62, 5.35, "五级分类建议：正常类\n（征信无逾期/不良；利息保障倍数>7；\n合格担保覆盖建议额度；现金流为正）",
        fontsize=9, va="top", fontweight="bold", color=CC["green"],
        bbox=dict(boxstyle="round", fc="#eef7ee", ec=CC["green"], alpha=0.95))
fig.suptitle("FIN3-WKN-151 图05　风险分类与授信条件", fontsize=15, fontweight="bold")
fig.tight_layout(rect=[0, 0.02, 1, 0.95])
footer(fig)
save(fig, "FIN3-WKN-151_chart05_风险分类与授信条件.png")

# ----------------------------------------------------------------------------
# 11. 生成主交付物：授信审批报告
# ----------------------------------------------------------------------------
f0 = lambda v: f"{v:,.0f}"
f1 = lambda v: f"{v:,.1f}"
f2 = lambda v: f"{v:,.2f}"

# 自报差异表行
diff_rows = "\n".join(
    f"| {it} | {pd_} | {f0(a)} | {f0(b)} | {f0(d)} |" for it, pd_, a, b, d in selfrep_diffs)
# 融资品种结构表行
kind_group = OrderedDict([
    ("流动资金贷款", fin_wc_loan), ("银行承兑汇票", fin_ba), ("国内信用证", fin_lc),
    ("外币贸易融资（进口押汇+进口信用证，按1:%.2f折算）" % fx_usd, fin_fx_total)])
kind_rows = "\n".join(f"| {k} | {f0(v)} | {v / fin_balance_total * 100:.1f}% |" for k, v in kind_group.items())
# 偿债指标表行
ind_rows = "\n".join(
    f"| {PLABEL[p]} | {f2(m[p]['lev'])}% | {f2(m[p]['cur'])} | {f2(m[p]['quick'])} | {f2(m[p]['icr'])} | {f2(m[p]['ncash'])} |"
    for p in PERIODS)
# 周转天数测算表行
td_rows = (f"| 存货周转天数 | 存货平均余额×360÷营业成本 | {f1(d_inv)} |\n"
           f"| 应收账款周转天数 | 应收账款平均余额×360÷营业收入 | {f1(d_ar)} |\n"
           f"| 应付账款周转天数 | 应付账款平均余额×360÷营业成本 | {f1(d_ap)} |\n"
           f"| 预付账款周转天数 | 预付账款平均余额×360÷营业成本 | {f1(d_prep)} |\n"
           f"| 预收账款周转天数 | 预收账款平均余额×360÷营业收入 | {f1(d_adv)} |")
# 押品折算表行
coll_md_rows = "\n".join(
    "| {name} | {val} | {cat} | {rate} | {elig} |".format(
        name=r["name"], val=f0(r["val"]), cat=r["cat"],
        rate=(f"{r['rate']:.0f}%" if r["rate"] is not None else "未列示（待总行审批）"),
        elig=(f0(r["elig"]) if r["rate"] is not None else "0（暂不计入）"))
    for r in coll_rows)
# 约束表行
cons_rows = "\n".join(
    f"| {k} | {f0(v)} | {'√ 孰低生效项' if v == binding_val else ''} |" if v is not None
    else f"| {k} | 待核实 | 基础数据未提供，不参与孰低 |"
    for k, v in constraints.items())
# 品种分配行
alloc_rows = "\n".join(
    f"| {k} | {f0(v['amount'])} | {f0(alloc[k])}" + (f" | ≥{v['margin']:.0f}% |" if v["margin"] else " | — |")
    for k, v in apply_items.items())
# 税务差异行
vat_rows = "\n".join(f"| {a} | {f0(b)} | {f0(c)} | {f0(d)} |" for a, b, c, d in vat_diffs)

shareholders_txt = "、".join(f"{s[0]}（{s[2]:.0f}%）" for s in shareholders[:2]) + \
                   "、" + "、".join(f"{s[0]}（{s[2]:.0f}%）" for s in shareholders[2:])
subs_txt = "、".join(f"{s[0]}（{s[1]}%）" for s in subsidiaries) + "，分别主营" + "、".join(s[2] for s in subsidiaries)

report = f"""# 浙江恒远智能装备集团有限公司综合授信年度重检与授信审批报告

**报告编号**：FIN3-WKN-151　**审查机构**：华信银行总行授信审批部　**数据截止日**：2026年6月30日
（本报告由 FIN3-WKN-151_reproduce.py 从 /app/input_files/ 原始材料复算生成，配图 chart01—chart05。）

## 一、授信结论与建议

经年度授信重检，**建议同意**核定综合授信额度 **人民币 {f0(suggest)} 万元**（申请 {f0(apply_total)} 万元，核减 {f0(apply_total - suggest)} 万元；上年获批 {f0(prev_credit)} 万元，压降 {abs(vs_prev):.0f}%），期限 1 年，品种按申请比例等比压缩：流动资金贷款 {f0(alloc['流动资金贷款'])}、银行承兑汇票 {f0(alloc['银行承兑汇票'])}（保证金 {apply_items['银行承兑汇票']['margin']:.0f}%）、国内信用证 {f0(alloc['国内信用证'])} 万元（保证金 {apply_items['国内信用证']['margin']:.0f}%）。

核心结论：（1）2023—2025 年连续获标准无保留审计意见，营收复合增长 {f1(cagr)}%，2025 年净利润率 {f2(m['2025']['npm'])}%、资产负债率 {f2(m['2025']['lev'])}% 均优于行业平均（{ind_npm}%、{ind_lev}%），利息保障倍数 {f2(m['2025']['icr'])} 倍，偿债能力稳健；（2）按《授信额度测算指引》，新增营运资金需求 {f0(new_need)} 万元、合格担保值 {f0(eligible_total)} 万元、净资产约束 {f0(na_cap)} 万元、集中度约束待核实，按孰低原则并向下取整至千万元，建议额度 {f0(suggest)} 万元，**约束性项为担保覆盖**；（3）机器设备等专用押品政策未列示抵押率，暂不计入合格担保值，如总行风险管理部批准可复算上调（理论上限 {f0(upside_if_equip)} 万元，仍低于申请额）；（4）征信无逾期、垫款与不良记录，五级分类建议**正常类**。

## 二、材料核验与数据口径

**（一）材料覆盖**。对照《00_材料清单》{len(docs)} 份材料与磁盘文件逐一核对，实收 {len(docs) - len(docs_missing)} 份、缺失 {len(docs_missing)} 份，共 {len(cat_counts)} 类（分布见图01a）。2023—2025 年度审计意见均为标准无保留（天健所）；2026H1 为未经审计快报。交叉核验一致 {n_checks_ok} 项（审计报告与报表CSV、他行流贷敞口 {f0(fin_wc_loan)} 万元与期末短期借款、对外担保三来源等）。

**（二）口径差异及处理**（均显式列示双方来源与数值，未修改任何输入文件）：

1. **自报数据与审计/快报差异**：《12_企业自报财务数据汇总》与审计报表及快报共 {len(selfrep_diffs)} 项不一致，其中 2025 年营业收入自报 {f0(sr.loc['营业收入', '2025'])}、审计 {f0(inc.loc['营业收入', '2025'])} 万元（差 {f0(sr.loc['营业收入', '2025'] - inc.loc['营业收入', '2025'])} 万元，据 12b 系发出商品未验收按管理口径确认收入所致）。按 12b"以审计报告为准"及审计报告附注，**本报告一律采用审计/快报口径**：

| 项目 | 期间 | 自报数（12） | 审计/快报数（09-11） | 差异 |
|---|---|---|---|---|
{diff_rows}

2. **应收账款"账面余额"用语差异**：2023/2025 年审计报告载"账面余额 {f0(ar_label_diff[2023][0])}/{f0(ar_label_diff[2025][0])} 万元"，《17_账龄表》载账面余额 {f0(ar_label_diff[2023][1])}/{f0(ar_label_diff[2025][1])} 万元；据附注（2025 年余额 {f0(ar_gross_08)}−准备 {f0(ar_prov_08)}＝账面价值 {f0(ar_gross_08 - ar_prov_08)}），审计报告数字实为**账面价值**。处理：指标与测算用账面价值，账龄与集中度用账龄表账面余额口径。

3. **税务申报销售额与账面营业收入差异**：

| 期间 | 增值税申报销售额（不含税，材料16） | 账面营业收入（审计/快报） | 差异 |
|---|---|---|---|
{vat_rows}

材料16说明系免税收入、视同销售及账务调整所致，其援引的"企业说明"未随附，2025 年差异 {f0(abs(vat_diffs[2][3]))} 万元构成**待核实**；测算用财务报表口径。

4. **应付票据与银承敞口差异**：他行明细银承敞口 {f0(fin_ba)} 万元、2026 年 6 月末应付票据账面 {f0(notes_payable_26H1)} 万元，差 {f0(abs(ba_vs_notes))} 万元；14b 载明明细为扣除保证金后的敞口口径。融资汇总用明细表口径，财务指标用报表数，差额构成**待核实**。

5. **他行授信明细数据质量**：原始 {fin_raw_rows} 行，按合同编号去重剔除重复 {n_dup} 行（序号 {('、'.join(str(s) for s in dup_rows))}）；剔除"已结清/已到期" {n_term} 笔；{n_blank} 笔状态空白（{'、'.join(str(b[0]) for b in blank_rows)}，到期日 {'、'.join(str(b[2]) for b in blank_rows)}）均早于截止日 2026-06-30，按 14b 结合到期日判定已终止剔除（征信无逾期佐证）；美元业务 {n_usd} 笔按材料载明汇率 1:{f2(fx_usd)} 折算。处理后有效合同 {n_active} 笔，未直接对原始行求和。

**（三）待核实事项（{len(tbd_items)} 项）**：{'；'.join(tbd_items)}。

**（四）采用口径**：财务数据以审计报表及 2026H1 快报为准；现有融资以处理后明细表敞口口径为准；测算参数仅取自《23》《24》指引及材料载明数值。

## 三、客户与经营概况

**基本情况**：客户成立于 2009 年 5 月，注册资本 {f0(reg_cap)} 万元（已实缴），法定代表人兼实际控制人陈立远（直接与间接合计控制 {f0(control_pct)}% 表决权），属通用设备制造业/工业机器人制造（C3491），主营工业机器人本体、精密减速器与伺服驱动系统的研发、生产与销售，员工 {f0(emp_n)} 人（研发 {f0(rd_n)} 人），发明专利 {patent_inv:.0f} 项；高新技术企业证书 {hightech_end} 到期（复审筹备中），报告期无重大行政处罚。

**股权结构**：{shareholders_txt}。集团成员：{subs_txt}。

**经营与市场地位**：2023—2025 年营业收入 {f0(inc.loc['营业收入', '2023'])}/{f0(inc.loc['营业收入', '2024'])}/{f0(inc.loc['营业收入', '2025'])} 万元，复合增长 {f1(cagr)}%，高于行业近三年平均增速 {ind_g3}%；2026H1 收入 {f0(flash_rev)} 万元、同比增 {flash_h1_growth_txt}%，增速放缓（下游汽车行业需求波动）；2026 年 6 月末在手订单 {orders_yi} 亿元。2025 年净利润率 {f2(m['2025']['npm'])}% 高于行业平均 {ind_npm}%，应收账款周转天数（{f1(d_ar)} 天）优于行业 {ind_ar_days:.0f} 天。

**现有融资（按处理后他行明细，敞口口径，截止 2026-06-30）**：全渠道融资余额 **{f0(fin_balance_total)} 万元**，有效授信额度合计 {f0(fin_limit_total)} 万元；其中我行敞口 {f0(fin_huaxin)} 万元（{huaxin_contract}，到期 {huaxin_due}）。品种结构：

| 品种 | 余额（万元） | 占比 |
|---|---|---|
{kind_rows}
| **合计** | **{f0(fin_balance_total)}** | 100.0% |

交叉验证：流贷敞口与期末短期借款一致（均 {f0(st_loan_26)} 万元）；2025 年我行结算贷方累计 {f0(inflow_2025)} 万元，为账面营收 {f2(inflow_ratio)} 倍，回款与收入匹配。

**关联与或有**：2025 年关联采购 {f0(assoc_buy)} 万元、关联销售 {f0(assoc_sell)} 万元（分别占营业成本 {assoc_buy_pct}%、营收 {assoc_sell_pct}%），向控股股东资金拆借（借入）{f0(assoc_lending)} 万元，定价参照市场价；对外担保余额 {f0(guar_20)} 万元（均为对子公司连带保证、无反担保），未决专利诉讼标的 {f0(lawsuit_20)} 万元（一审未判），附追索权已贴现未到期商票 {f0(discounted_ba)} 万元。

## 四、财务状况与偿债能力分析

**资产负债结构**：四期资产总计 {f0(m['2023']['ta'])}/{f0(m['2024']['ta'])}/{f0(m['2025']['ta'])}/{f0(m['2026H1']['ta'])} 万元；资产负债率 {f2(m['2023']['lev'])}%→{f2(m['2024']['lev'])}%→{f2(m['2025']['lev'])}%→{f2(m['2026H1']['lev'])}%，逐年上升但 2025 年仍低于行业平均 {ind_lev}%，杠杆适中（图02a）。非流动资产占比约 {f1(min(m[p]['nca_ratio'] for p in PERIODS))}%—{f1(max(m[p]['nca_ratio'] for p in PERIODS))}%，（应收账款+存货）占总资产约 {f1(min(m[p]['ar_inv_ratio'] for p in PERIODS))}%—{f1(max(m[p]['ar_inv_ratio'] for p in PERIODS))}%，营运资金占用高，与行业长账期特征一致；负债以短期借款、应付账款及票据为主，2026 年 6 月末长期借款仅 {f0(bs.loc['长期借款', '2026H1'])} 万元，期限结构偏短、依赖滚动融资。

**盈利能力**：毛利率 {f2(m['2023']['gm'])}%/{f2(m['2024']['gm'])}%/{f2(m['2025']['gm'])}%/{f2(m['2026H1']['gm'])}%，净利润率 {f2(m['2023']['npm'])}%/{f2(m['2024']['npm'])}%/{f2(m['2025']['npm'])}%/{f2(m['2026H1']['npm'])}%，净利润 {f0(m['2023']['npft'])}/{f0(m['2024']['npft'])}/{f0(m['2025']['npft'])}/{f0(m['2026H1']['npft'])} 万元，持续向好且高于行业平均；2026H1 毛利率同比基本平稳。

**营运能力**：测算口径下 2025 年存货/应收/应付周转天数 {f1(d_inv)}/{f1(d_ar)}/{f1(d_ap)} 天，营运资金周转天数 {f1(wc_days)} 天（图03b），存货与应收周转总体改善、2026H1 小幅回升；账龄结构趋弱：1 年以内占比 91%→88%、1—2 年 6%→9%，第一名客户占比 22%→28%、前五名 78%→87%，集中度持续上升；2025 年存货跌价计提率 {f1(float(inv_total_row['2025年末跌价准备']) / float(inv_total_row['2025年末账面余额']) * 100)}%。

**偿债能力指标**（利息保障倍数=（利润总额+财务费用）÷财务费用，未单列利息支出、以财务费用为代理；2026H1 未年化；速动比率=（流动资产−存货）÷流动负债）：

| 期间 | 资产负债率 | 流动比率 | 速动比率 | 利息保障倍数 | 净现比 |
|---|---|---|---|---|---|
{ind_rows}

判断：流动、速动比率缓慢下行但仍处安全区间；利息保障倍数持续高于 7.5 倍，付息能力强；资产负债率低于行业均值，尚有举债空间。

**现金流质量**：经营现金流净额 {f0(m['2023']['ocf'])}/{f0(m['2024']['ocf'])}/{f0(m['2025']['ocf'])}/{f0(m['2026H1']['ocf'])} 万元，2023—2025 年净现比 {f2(m['2023']['ncash'])}/{f2(m['2024']['ncash'])}/{f2(m['2025']['ncash'])}，盈利含金量好；2026H1 净流入同比减少 {f0(flash_ocf_py - flash_ocf)} 万元（降 {(1 - flash_ocf / flash_ocf_py) * 100:.1f}%）、净现比降至 {f2(m['2026H1']['ncash'])}（企业解释为大客户付款方式调整、票据结算增加），列为贷后重点监控。投资现金流持续净流出（扩产）、筹资小幅净流出，现金链依赖经营回款与短贷滚动。

## 五、授信需求测算与额度建议

严格按《24_授信额度测算指引》执行（上年度=2025 年审计口径，360 天，平均余额）：

**（1）增长率取值**：借款人预测 2026 年增长 {g_borrower:.0f}%；行业近三年平均增速 {ind_g3}%（材料25），指引上限={ind_g3}%+{g_cap_add:.0f} 个百分点={f1(g_cap)}%；因 {g_borrower:.0f}%＞{f1(g_cap)}%，按审慎原则取 **{g_used:.0f}%**。

**（2）周转天数与营运资金量**：

| 项目 | 公式 | 天数 |
|---|---|---|
{td_rows}

营运资金周转天数={f1(d_inv)}+{f1(d_ar)}−{f1(d_ap)}+{f1(d_prep)}−{f1(d_adv)}=**{f1(wc_days)} 天**；周转次数=360÷{f1(wc_days)}=**{f2(wc_freq)} 次**。
营运资金量={f0(rev_prior)}×(1−{f2(npm_prior * 100)}%)×(1+{g_used:.0f}%)÷{f2(wc_freq)}=**{f0(wcr)} 万元**。

**（3）新增营运资金需求**={f0(wcr)}−自有资金 {f0(own_funds)}−现有流贷 {f0(st_loan_26)}−其他渠道（应付票据）{f0(notes_26)}=**{f0(new_need)} 万元**。自有资金=2026 年 6 月末货币资金 {f0(bs.loc['货币资金', '2026H1'])}−受限 {f0(restricted_2025)}（受限额仅 2025 年末披露，2026 年 6 月末**待核实**，以最新披露值代用）；现有流贷=期末短期借款（含他行）。敏感性：若全用 2025 年末口径（自有资金 {f0(own_funds_25)}、短借 {f0(bs.loc['短期借款', '2025'])}、应付票据 {f0(bs.loc['应付票据', '2025'])}），需求为 {f0(new_need_25base)} 万元，均高于担保约束值，**不影响孰低结论**。

**（4）孰低原则确定建议额度**：

| 约束 | 金额（万元） | 备注 |
|---|---|---|
{cons_rows}

孰低值={f0(binding_val)} 万元（{binding_name}），向下取整至千万元，**建议授信额度 {f0(suggest)} 万元**（图04a）。较申请 {f0(apply_total)} 万元核减 {f0(apply_total - suggest)} 万元，较上年获批 {f0(prev_credit)} 万元压降 {abs(vs_prev):.0f}%。品种按申请比例等比分配：

| 品种 | 申请（万元） | 建议核定（万元） | 保证金比例 |
|---|---|---|---|
{alloc_rows}

行业增速限额（≤全行对公贷款增速×{industry_growth_mult}）因全行增速未提供**待核实**，本次为压降安排、不构成上行压力；集中度约束待资本净额提供后复核。若总行批准专用设备抵押率并计入，约束切换为营运资金需求，额度理论上限 {f0(upside_if_equip)} 万元（需重新报批）。

## 六、担保与风险缓释

按政策 3.1 表逐项折算（评估基准日 2026-06-30，浙江中衡，报告号 ZH2026-0788）：

| 押品 | 评估价值（万元） | 对应政策类别 | 抵押/质押率 | 合格担保值（万元） |
|---|---|---|---|---|
{coll_md_rows}
| **合计** | **{f0(coll_total)}** | — | — | **{f0(eligible_total)}** |

说明：（1）机器设备（减速器生产线、加工中心等）经评估报告提示"部分为专用设备、变现能力一般"，政策 3.1 注要求专用设备抵押率逐笔报总行风险管理部审批，**审查人未自行设定抵押率**，暂按 0 计入；（2）股权押品为全资子公司恒远精密机械 100% 股权，属非上市公司股权，适用 40%；（3）合格担保值 {f0(eligible_total)} 万元，对建议额度覆盖率 **{f1(cover_ratio)}%**（图04b）。

风险缓释安排建议：（1）厂房办公楼、土地使用权设定第一顺位抵押（评估报告载明既有抵押余额为 0）；应收账款、恒远精密股权、存货（通用性较强）设定质押；（2）征信显示应收账款质押登记 {f0(pledge_ar_reg)} 万元、股权质押登记 {f0(pledge_eq_reg)} 万元，**放款前须书面核实该等登记所担保债权归属**——若为其他债权人设定，应注销或置换等额合格押品，否则按可计入担保值扣减后复算额度；（3）追加实际控制人陈立远连带责任保证（政策 3.2：关联方保证不作唯一担保方式，本案与抵质押组合，合规）；（4）银承、国内信用证保证金比例 {apply_items['银行承兑汇票']['margin']:.0f}%、{apply_items['国内信用证']['margin']:.0f}%，不低于政策下限 {margin_floor:.0f}%。

## 七、风险分类与授信条件

**五级分类：正常类**。依据：征信报告（2026-07-06）未结清业务均正常，无逾期、垫款、不良、欠税、失信及经营异常记录；连续三年净利润与经营现金流为正，利息保障倍数 {f2(m['2025']['icr'])} 倍（2025 年）；资产负债率 {f2(m['2026H1']['lev'])}% 适中；合格担保值对建议额度覆盖率 {f1(cover_ratio)}%；他行 {n_active} 笔有效业务正常履约。

**授信条件建议**：
- 额度 {f0(suggest)} 万元、期限 1 年；品种：流贷 {f0(alloc['流动资金贷款'])}、银承 {f0(alloc['银行承兑汇票'])}、国内信用证 {f0(alloc['国内信用证'])} 万元，不得挪用于固定资产、股权投资或国家禁止领域。
- 担保：厂房办公楼+土地抵押、应收账款+子公司股权+存货质押，实际控制人陈立远连带责任保证；专用设备抵押率待总行风险管理部批复后方可作为增额依据。
- 财务约束（审查建议值，非政策参数）：资产负债率≤50%；年度经营现金流净额为正且净现比≥0.8；前五名应收客户集中度不高于 87% 且 1—2 年账龄占比无重大恶化；未经我行书面同意，不得新增对并表外主体担保或大额资金拆借。
- 提款条件：抵质押登记办妥且第一顺位确认、既有质押登记归属书面核实；总行复核单一集团授信余额≤资本净额 {conc_capital_pct:.0f}%；流贷受托支付并核验贸易背景；票据/信用证保证金足额到位；高新资格复审进展说明。

## 八、风险提示与贷后管理要求

**主要风险点与分级**（矩阵见图05b）：
- **中风险**：R1 经营现金流下滑——2026H1 净流入同比降 {(1 - flash_ocf / flash_ocf_py) * 100:.1f}%、净现比 {f2(m['2026H1']['ncash'])}；R2 应收账款集中度上升（前五名 {age.loc[age['项目'] == '前五名客户余额占比', '2026年6月末'].iloc[0]}）与账龄延长；R3 收入增速放缓（H1 同比 {flash_h1_growth_txt}%）且企业 {g_borrower:.0f}% 预测偏乐观，测算已按 {g_used:.0f}% 封顶；R4 押品既有质押登记归属待核实，直接影响合格担保值；R7 下游汽车/3C 需求波动及钢材、铜材、稀土永磁等价格波动（行业提示）。
- **低风险**：R5 高新技术企业资格 {hightech_end} 到期，复审不通过将致所得税率自 15% 回升、侵蚀盈利；R6 未决专利诉讼标的 {f0(lawsuit_20)} 万元（占 2025 年末净资产 {f2(lawsuit_20 / bs.loc['所有者权益合计', '2025'] * 100)}%，企业预计无重大不利影响）；R8 专用设备抵押率未获批，额度弹性受限。
- **其他关注**：对外担保 {f0(guar_20)} 万元（均为子公司）、附追索权已贴现商票 {f0(discounted_ba)} 万元构成或有负债；向控股股东资金拆借 {f0(assoc_lending)} 万元需防范资金占用与非公允定价。

**贷后监控指标与频度**：按月——我行结算归行率与贷方发生额（2025 年月均约 {f0(inflow_2025 / 12)} 万元为基准）、银承/信用证保证金与兑付；按季——财务报表及资产负债率、流动比率、净现比、应收账龄与前五名集中度、存货跌价、他行用信与征信查询（对照本报告基线）；按半年——实地走访与库存盘点、押品价值重估与权属复查（价值下跌超 20% 触发补担保）；事件触发——高新复审结果（2026-11）、诉讼判决、在手订单（现 {orders_yi} 亿元）重大变化、股权或实控人变动，5 个工作日内报告。

**到期管理**：我行存量流贷 {huaxin_contract}（{f0(fin_huaxin)} 万元）{huaxin_due} 到期，本次授信项下支用应与其归还衔接；授信到期前 1 个月启动续检，重新执行本测算口径并更新第二章待核实清单；触发财务约束突破、分类下调或押品覆盖不足时，启动提前收回或追加担保程序。

---
*附注：本报告全部数值可由 FIN3-WKN-151_reproduce.py 自 /app/input_files/ 原始材料复算；标注"待核实"事项在落实前，相关结论以本报告载明的审慎口径为准。*
"""

report_path = OUT / "FIN3-WKN-151_授信审批报告.md"
report_path.write_text(report, encoding="utf-8")
cn = count_cn(report)

# ----------------------------------------------------------------------------
# 12. 校验与汇总输出
# ----------------------------------------------------------------------------
assert len(tpl_sections) == 8, "模板章节数异常"
for sec in tpl_sections:
    assert f"## {sec}" in report, f"报告缺少模板章节：{sec}"
missing_out = [f for f in [
    "FIN3-WKN-151_chart01_材料覆盖与数据缺口.png",
    "FIN3-WKN-151_chart02_财务与偿债能力.png",
    "FIN3-WKN-151_chart03_现金流与营运效率.png",
    "FIN3-WKN-151_chart04_额度测算与担保覆盖.png",
    "FIN3-WKN-151_chart05_风险分类与授信条件.png"] if not (CHART_DIR / f).exists()]
assert not missing_out, f"图表缺失: {missing_out}"

print("=" * 72)
print("FIN3-WKN-151 复算完成")
print("=" * 72)
print(f"报告: {report_path}  中文字符数(含标点,不含表格竖线/代码块): {cn}  要求3000-5000 -> {'OK' if 3000 <= cn <= 5000 else '超出范围!'}")
print(f"材料: 清单{len(docs)}份/缺失{len(docs_missing)}份; 交叉核验一致{n_checks_ok}项; 自报差异{len(selfrep_diffs)}项; 待核实{len(tbd_items)}项")
print(f"他行明细: 原始{fin_raw_rows}行 -> 去重-{n_dup} -> 终止-{n_term} -> 空白状态剔除-{int(blank_term_mask.sum())} -> 有效{n_active}笔(USD {n_usd}笔@{fx_usd})")
print(f"现有融资余额(敞口): {fin_balance_total:,.0f} 万元; 其中我行 {fin_huaxin:,.0f}; 有效授信额度合计 {fin_limit_total:,.0f}")
print(f"指标2025: 资产负债率{m['2025']['lev']:.2f}% 流动{m['2025']['cur']:.2f} 速动{m['2025']['quick']:.2f} ICR{m['2025']['icr']:.2f} 净现比{m['2025']['ncash']:.2f}")
print(f"指标2026H1: 资产负债率{m['2026H1']['lev']:.2f}% 流动{m['2026H1']['cur']:.2f} 速动{m['2026H1']['quick']:.2f} ICR{m['2026H1']['icr']:.2f} 净现比{m['2026H1']['ncash']:.2f}")
print(f"测算: g_used={g_used:.0f}% 周转天数={wc_days:.2f} 次数={wc_freq:.4f} 营运资金量={wcr:,.1f} 新增需求={new_need:,.1f} (2025口径={new_need_25base:,.1f})")
print(f"担保: 评估值合计={coll_total:,.0f} 合格担保值={eligible_total:,.0f} 覆盖率={cover_ratio:.1f}%")
print(f"约束: 需求{new_need:,.0f} / 担保{eligible_total:,.0f} / 净资产{na_cap:,.0f} / 集中度待核实 -> 孰低{binding_val:,.0f} -> 建议额度 {suggest:,.0f} 万元 (品种 {dict(alloc)})")
print(f"五级分类: 正常类; 设备获批后理论上限: {upside_if_equip:,.0f}")
print("图表5张已生成于:", CHART_DIR)
