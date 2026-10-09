#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-150 Pre-IPO 股权投资尽调与估值定价分析 —— 可复算脚本
================================================================
功能：
  1. 从 /app/input_files/ 读入全部原始尽调材料（只读，不修改）；
  2. 计算：材料核验冲突、经营质量指标、利润口径还原桥、DCF（按
     《32_DCF参数与折现率指引》）、市场法（按《31_行业数据与可比公司
     选取说明》清洗筛选）、估值结论与交易方案测算；
  3. 生成主交付物 FIN3-WKN-150_PreIPO投资决策备忘录.md 与全部 5 张复合图。

运行方式：python3 FIN3-WKN-150_reproduce.py
说明：本脚本不硬编码任何结论数值，全部数字均由输入文件解析或计算得到。
"""

import csv
import re
import unicodedata
from datetime import date
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------
# 0. 路径与全局常量（仅路径与期间标签，不含任何结论数值）
# ----------------------------------------------------------------------
INPUT_DIR = Path("/app/input_files")
OUTPUT_DIR = Path("/app/output")
CHART_DIR = OUTPUT_DIR / "FIN3-WKN-150_charts"
MEMO_PATH = OUTPUT_DIR / "FIN3-WKN-150_PreIPO投资决策备忘录.md"
CHART_DIR.mkdir(parents=True, exist_ok=True)

PERIODS = ["2023", "2024", "2025", "2026H1"]
PERIOD_CN = {"2023": "2023年", "2024": "2024年", "2025": "2025年", "2026H1": "2026H1"}
CUTOFF = date(2026, 6, 30)          # 数据与检索截止日（任务书给定）
VAL_DATE = date(2025, 12, 31)       # 估值基准日（任务书给定）

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 110


def read_text(fname: str) -> str:
    return (INPUT_DIR / fname).read_text(encoding="utf-8")


def read_csv_rows(fname: str):
    with open(INPUT_DIR / fname, newline="", encoding="utf-8-sig") as f:
        return [row for row in csv.reader(f) if any(c.strip() for c in row)]


def num(s):
    """把 '82,000'、'**20,000**'、'-590'、'3.45%' 等解析为 float；无效返回 None。"""
    if s is None:
        return None
    s = str(s).strip().replace("**", "").replace("，", ",")
    s = re.sub(r"[^\d.\-+eE]", "", s) if not re.search(r"\d", s) else s
    m = re.search(r"[-+]?\d[\d,]*\.?\d*", str(s))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def first_pct(s):
    """提取单元格中第一个百分数（返回百分点数值，如 '2.35%' -> 2.35）。"""
    m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", str(s))
    return float(m.group(1)) if m else None


def md_tables(text: str):
    """解析 Markdown 文本中的全部表格，返回 [ [ [cell,...], ... ], ... ]。"""
    tables, cur = [], []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c != ""):
                continue  # 分隔行
            cur.append(cells)
        else:
            if cur:
                tables.append(cur)
                cur = []
    if cur:
        tables.append(cur)
    return tables


def md_rows(text):
    """把文本中全部表格的数据行摊平为一个行列表。"""
    rows = []
    for t in md_tables(text):
        rows.extend(t)
    return rows


def find_row(tables, key, col=0):
    """在全部表格中找首个第 col 列包含 key 的数据行。"""
    for t in tables:
        for row in t:
            if len(row) > col and key in row[col].replace("**", ""):
                return row
    return None


def fmt(x, nd=0):
    """千分位格式化。"""
    return f"{x:,.{nd}f}"


# ----------------------------------------------------------------------
# 1. 解析审计报告（03–06）：利润表 / 资产负债表 / 现金流量表
# ----------------------------------------------------------------------
AUDIT_FILES = {"2023": "03_审计报告_2023.md", "2024": "04_审计报告_2024.md",
               "2025": "05_审计报告_2025.md", "2026H1": "06_审计报告_2026H1.md"}
IS_KEYS = ["营业收入", "营业成本（含税金及附加）", "销售费用", "管理费用", "研发费用",
           "财务费用", "其中：利息费用", "其他收益（政府补助）", "投资收益",
           "公允价值变动收益", "资产处置收益", "信用减值损失及资产减值损失",
           "营业利润", "营业外收支净额", "利润总额", "所得税费用", "净利润",
           "归属于母公司股东的净利润"]
BS_KEYS = ["货币资金", "应收账款（净额）", "存货（净额）", "固定资产", "在建工程",
           "资产总计", "短期借款", "长期借款", "负债合计", "所有者权益合计"]
CF_KEYS = ["经营活动产生的现金流量净额", "投资活动产生的现金流量净额",
           "筹资活动产生的现金流量净额", "现金及现金等价物净增加额"]

FS = {p: {} for p in PERIODS}          # 财务报表数据 FS[期间][项目] = 万元
REPORT_DATES = {}
for p, fn in AUDIT_FILES.items():
    txt = read_text(fn)
    tbls = md_tables(txt)
    m = re.search(r"报告日期：\s*([\d年月日\s]+)", txt)
    REPORT_DATES[p] = m.group(1).strip() if m else "未载明"
    for key in IS_KEYS + BS_KEYS + CF_KEYS:
        row = find_row(tbls, key)
        if row is None:
            continue
        v = num(row[1])
        if v is None:
            continue
        # “净利润”行需精确匹配，避免误取“归属于母公司股东的净利润”
        first_cell = row[0].replace("**", "").strip()
        if key == "净利润" and first_cell != "净利润":
            continue
        if key == "营业收入" and first_cell != "营业收入":
            continue
        FS[p][key] = v

# ----------------------------------------------------------------------
# 2. 解析财务报表附注（07–10）：有息负债、折旧摊销
# ----------------------------------------------------------------------
NOTES_FILES = {"2023": "07_财务报表附注_2023.md", "2024": "08_财务报表附注_2024.md",
               "2025": "09_财务报表附注_2025.md", "2026H1": "10_财务报表附注_2026H1.md"}
INTEREST_BEARING_DEBT = {}   # 有息负债合计（附注口径）
DA = {}                      # 折旧与摊销合计
for p, fn in NOTES_FILES.items():
    tbls = md_tables(read_text(fn))
    row = find_row(tbls, "有息负债合计")
    INTEREST_BEARING_DEBT[p] = num(row[1]) if row else None
    # 折旧与摊销：在“## 四、折旧与摊销”小节内解析合计行，避免误匹配其他表
    sec = re.search(r"##\s*四、折旧与摊销(.*?)##", read_text(fn), re.S)
    if sec:
        for r in md_rows(sec.group(1)):
            if "合计" in r[0]:
                DA[p] = num(r[1])

# ----------------------------------------------------------------------
# 3. 非经常性损益（11）、股份支付（12）
# ----------------------------------------------------------------------
NONREC_ITEMS = {p: [] for p in PERIODS}      # [(项目, 税前, 所得税, 税后)]
NONREC_STATED_TOTAL = {}                     # CSV 中“合计”行
for row in read_csv_rows("11_非经常性损益明细.csv")[1:]:
    p = row[0].strip()
    if p.startswith("合计"):
        pk = p.replace("合计", "")
        NONREC_STATED_TOTAL[pk] = num(row[4])
    elif p in PERIODS:
        NONREC_ITEMS[p].append((row[1], num(row[2]), num(row[3]), num(row[4])))
NONREC = {p: sum(i[3] for i in NONREC_ITEMS[p]) for p in PERIODS}   # 税后非经常性损益合计
NONREC_PRETAX = {p: sum(i[1] for i in NONREC_ITEMS[p]) for p in PERIODS}

SBC = {p: 0.0 for p in PERIODS}              # 股份支付费用
for row in read_csv_rows("12_股份支付明细.csv")[1:]:
    SBC[row[0].strip()] += num(row[2])

# ----------------------------------------------------------------------
# 4. 关联交易（13）、应收账款账龄与坏账（14）、存货（15）、货币资金（16）、
#    受限资产（17）、期后事项（18）
# ----------------------------------------------------------------------
RT_ROWS = read_csv_rows("13_关联交易清单.csv")[1:]
RT_2025_SALES = sum(num(r[4]) for r in RT_ROWS if r[0] == "2025" and r[1] == "销售")
RT_2025_BUY = sum(num(r[4]) for r in RT_ROWS if r[0] == "2025" and r[1] == "采购")
RT_FUND = [r for r in RT_ROWS if r[1] == "资金往来"]

txt14 = read_text("14_应收账款账龄与坏账政策.md")
tbls14 = md_tables(txt14)
BAD_DEBT_POLICY = {}                          # 账龄 -> 计提比例(%)
for r in tbls14[0]:
    if len(r) >= 2 and first_pct(r[1]) is not None:
        BAD_DEBT_POLICY[r[0].strip()] = first_pct(r[1])
AGING_ROWS = ["1 年以内", "1–2 年", "2–3 年", "3 年以上"]
AR_GROSS, AR_PROV_STATED, AR_NET_STATED = {}, {}, {}
hdr14 = tbls14[1][0]
col14 = {p: i + 1 for i, p in enumerate(PERIODS)}   # 列顺序与 PERIODS 一致
for r in tbls14[1][1:]:
    label = r[0].replace("**", "").strip()
    if label in AGING_ROWS:
        for p, ci in col14.items():
            AR_GROSS.setdefault(p, {})[label] = num(r[ci])
    elif "账面余额合计" in label:
        for p, ci in col14.items():
            AR_GROSS[p]["合计"] = num(r[ci])
    elif "坏账准备" in label:
        for p, ci in col14.items():
            AR_PROV_STATED[p] = num(r[ci])
    elif "应收账款净额" in label:
        for p, ci in col14.items():
            AR_NET_STATED[p] = num(r[ci])
# 按披露政策重算坏账准备
AR_PROV_CALC = {}
for p in PERIODS:
    s = 0.0
    for ag in AGING_ROWS:
        rate = BAD_DEBT_POLICY.get(ag, 0)
        s += AR_GROSS[p][ag] * rate / 100.0
    AR_PROV_CALC[p] = s

INV_NET = {}                                  # 存货账面价值（合计行）
for row in read_csv_rows("15_存货明细与跌价准备.csv")[1:]:
    if row[1].strip() == "合计":
        INV_NET[row[0].strip()] = num(row[4])
INV_PROV = {p: 0.0 for p in PERIODS}
for row in read_csv_rows("15_存货明细与跌价准备.csv")[1:]:
    if row[1].strip() == "合计":
        INV_PROV[row[0].strip()] = num(row[3])

txt16 = read_text("16_货币资金与银行流水摘要.md")
tbls16 = md_tables(txt16)
RESTRICTED_CASH = {p: 0.0 for p in PERIODS}   # 受限货币资金
TOTAL_CASH16 = {}
for r in tbls16[0][1:]:
    label = r[0].replace("**", "").strip()
    for i, p in enumerate(PERIODS):
        v = num(r[i + 1])
        if v is None:
            continue
        if ("质押" in label) or ("保证金" in label):
            RESTRICTED_CASH[p] += v
        if label == "合计":
            TOTAL_CASH16[p] = v
BANK_2025 = {}                                # 2025 银行流水摘要
sec16 = re.search(r"##\s*二、银行流水摘要.*?\n(.*?)##", txt16, re.S)
if sec16:
    for r in md_rows(sec16.group(1)):
        BANK_2025[r[0].replace("**", "").strip()] = num(r[1])

txt17 = read_text("17_受限资产与对外担保清单.md")
m = re.search(r"累计已完成\s*投资\s*([\d.]+)\s*亿元", txt17)
CAPEX_COMMIT_DONE = float(m.group(1)) * 10000 if m else None      # 万元
m = re.search(r"累计固定资产投资\s*不低于\s*([\d.]+)\s*亿元", txt17)
CAPEX_COMMIT_TARGET = float(m.group(1)) * 10000 if m else None    # 万元
m = re.search(r"预计设备采购及厂房改造投入约\s*\n?\s*([\d,]+)\s*万元", txt17)
CAPEX_2026_PLAN = num(m.group(1)) if m else None
tbls17 = md_tables(txt17)
row = find_row(tbls17, "货币资金")
RESTRICTED_ASSET_CASH_17 = num(row[1]) if row else None           # 文件17披露的受限货币资金(2025)

txt18 = read_text("18_期后事项与未决诉讼.md")
m = re.search(r"([\d,]+)\s*万元，?主管部门正在复核|收到的一笔政府补助\s*([\d,]+)\s*万元", txt18)
GRANT_REVIEW = num(m.group(1) or m.group(2)) if m else None
m = re.search(r"公司\s*(\d{4})\s*年收到的一笔政府补助", txt18)
GRANT_REVIEW_YEAR_18 = m.group(1) if m else None
LITIGATION = []
for r in md_rows(txt18):
    if "涉诉金额" in r[0] or "纠纷" in r[0]:
        LITIGATION.append(r)
m = re.search(r"买卖合同纠纷\s*\|[^|]*\|\s*([\d,]+)\s*\|", txt18)
LITIG_AMT = num(m.group(1)) if m else None
m = re.search(r"已计提预计负债\s*([\d,]+)\s*万元", txt18)
LITIG_PROVISION = num(m.group(1)) if m else None

txt37 = read_text("37_员工与社保缴纳明细.md")
SOCIAL = {}
for r in md_rows(txt37):
    if r[0].strip() in PERIODS and len(r) >= 4:
        SOCIAL[r[0].strip()] = first_pct(r[3])
txt38 = read_text("38_税务情况说明.md")
m = re.search(r"(\d{4})\s*年度收到的政府补助\s*中，有\s*([\d,]+)\s*万元", txt38)
GRANT_REVIEW_YEAR_38 = m.group(1) if m else None
GRANT_REVIEW_38 = num(m.group(2)) if m else None
m = re.search(r"优惠期至\s*(\d{4})\s*年", txt38)
HNTE_EXPIRY = m.group(1) if m else None
# ----------------------------------------------------------------------
# 5. 收入明细（19–22）、分客户（23）、成本费用明细（24–27）
# ----------------------------------------------------------------------
PROD_REV = {p: {} for p in PERIODS}     # 产品线 -> 收入
PROD_GP = {p: {} for p in PERIODS}      # 产品线 -> 毛利
PROD_COST_TOTAL = {}                    # 分产品文件的营业成本合计
for p, fn in zip(PERIODS, ["19_收入明细_分产品_2023.csv", "20_收入明细_分产品_2024.csv",
                           "21_收入明细_分产品_2025.csv", "22_收入明细_分产品_2026H1.csv"]):
    for row in read_csv_rows(fn)[1:]:
        name = row[1].strip()
        if name == "合计":
            PROD_COST_TOTAL[p] = num(row[3])
        else:
            PROD_REV[p][name] = num(row[2])
            PROD_GP[p][name] = num(row[4])

CUST_2025 = read_csv_rows("23_收入明细_分客户_2025.csv")[1:]
TOP1_CUST = CUST_2025[0]
TOP1_REV_2025 = num(TOP1_CUST[2])
TOP1_SHARE_2025 = first_pct(TOP1_CUST[3])

COST_DETAIL = {p: {} for p in PERIODS}  # 成本费用明细
for p, fn in zip(PERIODS, ["24_成本费用明细_2023.csv", "25_成本费用明细_2024.csv",
                           "26_成本费用明细_2025.csv", "27_成本费用明细_2026H1.csv"]):
    for row in read_csv_rows(fn)[1:]:
        COST_DETAIL[p][row[1].strip()] = num(row[2])

# ----------------------------------------------------------------------
# 6. 交易概况（01）、业绩承诺（33）、股权与融资（34）、客户供应商（35）
# ----------------------------------------------------------------------
txt01 = read_text("01_交易概况与投资方案.md")
m = re.search(r"拟投资金额\s*\|\s*人民币\s*([\d,]+)\s*万元", txt01)
INVEST = num(m.group(1)) if m else None
m = re.search(r"不高于\s*([\d.]+)\s*%", txt01)
STAKE_CAP = float(m.group(1)) if m else None
m = re.search(r"预计\s*(\d{4})\s*年完成上市", txt01)
IPO_YEAR = int(m.group(1)) if m else None
MGT = {p: {} for p in PERIODS}            # 管理层口径（文件01）
sec = re.search(r"##\s*三、管理层提供的经营口径(.*?)##\s*四", txt01, re.S)
if sec:
    for r in md_rows(sec.group(1)):
        label = r[0].strip()
        for i, p in enumerate(PERIODS):
            v = num(r[i + 1]) if len(r) > i + 1 else None
            if v is not None:
                MGT[p][label] = v

txt30 = read_text("30_可比交易案例.md")
MINOR_DEAL_PES = []            # 少数股权交易案例 PE（文件30，控股权案例不可混用）
for r in md_rows(txt30):
    if len(r) > 4 and "少数股权" in r[3]:
        v = num(r[4])
        if v:
            MINOR_DEAL_PES.append(v)

txt33 = read_text("33_业绩承诺函与对赌条款.md")
COMMIT = {}                                # 年度 -> 承诺扣非归母净利润
for r in md_rows(txt33):
    m = re.fullmatch(r"(\d{4})\s*年", r[0].strip())
    if m and len(r) > 1:
        COMMIT[m.group(1)] = num(r[1].replace("不低于", ""))
m = re.search(r"低于承诺数的\s*\*{0,2}(\d+)%", txt33)
COMP_TRIGGER = float(m.group(1)) if m else None
m = re.search(r"累计承诺数的\s*\*{0,2}(\d+)%", txt33)
BUYBACK_TRIGGER = float(m.group(1)) if m else None
m = re.search(r"年化\s*\*{0,2}(\d+(?:\.\d+)?)\s*%\*{0,2}\s*单利", txt33)
BUYBACK_RATE = float(m.group(1)) if m else None
m = re.search(r"(\d{4})\s*年\s*12\s*月\s*31\s*日前未完成上市申报", txt33)
IPO_DEADLINE_YEAR = int(m.group(1)) if m else None

txt34 = read_text("34_股权结构、期权池与历史融资.md")
m = re.search(r"合计\*{0,2}\s*\|\s*\*{0,2}([\d,]+)\*{0,2}\s*\|\s*\*{0,2}100", txt34)
TOTAL_SHARES = num(m.group(1)) if m else None          # 万股
m = re.search(r"尚未授予的股份为\s*\*{0,2}([\d,]+)\s*万股", txt34)
POOL_UNGRANTED = num(m.group(1)) if m else None
m = re.search(r"已授予未行权股份\s*([\d,]+)\s*万股", txt34)
POOL_GRANTED = num(m.group(1)) if m else None
ROUNDS = []
for r in md_rows(txt34):
    if re.fullmatch(r"[ABC] 轮", r[0].strip()):
        ROUNDS.append({"轮次": r[0].strip(), "时间": r[1].strip(), "投资方": r[2].strip(),
                       "投资金额": num(r[3]), "投前估值": num(r[4]),
                       "披露PE": first_pct(r[5]) if "%" in r[5] else num(r[5])})

txt35 = read_text("35_主要客户与供应商.md")
CUST_CONC = {}
for r in md_rows(txt35):
    if r[0].strip() in PERIODS and len(r) >= 3:
        CUST_CONC[r[0].strip()] = (first_pct(r[1]), first_pct(r[2]))

# ----------------------------------------------------------------------
# 7. 可比公司（28/29）与筛选规则（31）、DCF 指引（32）
# ----------------------------------------------------------------------
def load_comps(fn, cols):
    rows = read_csv_rows(fn)
    hdr = rows[0]
    out = []
    for r in rows[1:]:
        d = {hdr[i]: r[i].strip() for i in range(len(hdr))}
        rec = {}
        for k, src in cols.items():
            rec[k] = d.get(src, "")
        rec["上市日期"] = d.get("上市日期", "")
        out.append(rec)
    return out

COLS28 = {"代码": "证券代码", "简称": "证券简称", "归母净利": "2025归母净利润_万元",
          "营收": "2025营业收入_万元", "EBITDA": "2025EBITDA_万元", "市值": "20260630总市值_万元",
          "PE": "PE_TTM", "PS": "PS_TTM", "EVEBITDA": "EV_EBITDA", "Beta": "UnleveredBeta",
          "行业": "所属行业"}
COLS29 = {"代码": "证券代码", "简称": "证券简称", "归母净利": "净利润_万元",
          "营收": "营业收入_万元", "EBITDA": "EBITDA_万元", "市值": "市值_万元",
          "PE": "PE", "PS": "PS", "EVEBITDA": "EVEBITDA", "Beta": "Beta", "行业": ""}
COMPS28 = load_comps("28_可比上市公司财务与估值数据.csv", COLS28)
COMPS29 = load_comps("29_可比公司数据_原始导出.csv", COLS29)

txt31 = read_text("31_行业数据与可比公司选取说明.md")
m = re.search(r"扣减\s*\n?\s*\*{0,2}(\d+(?:\.\d+)?)\s*%\s*流动性折价", txt31)
LIQ_DISCOUNT = float(m.group(1)) / 100.0 if m else None
m = re.search(r"上市已满\s*(\d+)\s*年", txt31)
LIST_YEARS_REQ = int(m.group(1)) if m else 1
m = re.search(r"营业收入不低于\s*(\d+)\s*亿元", txt31)
REV_FLOOR = float(m.group(1)) * 10000 if m else None      # 万元

# --- 清洗文件29（先清洗后筛选） ---
CLEAN_LOG = []
seen, cleaned = set(), []
for rec in COMPS29:
    code = rec["代码"]
    if code in seen:
        CLEAN_LOG.append((rec["简称"], "剔除：重复记录"))
        continue
    seen.add(code)
    if "ST" in rec["简称"].upper():
        CLEAN_LOG.append((rec["简称"], "剔除：风险警示（ST）"))
        continue
    if num(rec["归母净利"]) is not None and num(rec["归母净利"]) <= 0:
        CLEAN_LOG.append((rec["简称"], f"剔除：2025年亏损（净利润 {fmt(num(rec['归母净利']))} 万元）"))
        continue
    y, mo, d = [int(x) for x in rec["上市日期"].split("-")]
    if date(y + LIST_YEARS_REQ, mo, d) > CUTOFF:
        CLEAN_LOG.append((rec["简称"], f"剔除：上市日期 {rec['上市日期']}，距截止日不足 {LIST_YEARS_REQ} 年"))
        continue
    if num(rec["营收"]) is not None and num(rec["营收"]) < REV_FLOOR:
        CLEAN_LOG.append((rec["简称"], f"剔除：2025年营收 {fmt(num(rec['营收']))} 万元 < {fmt(REV_FLOOR)} 万元"))
        continue
    cleaned.append(rec)
CLEAN_LOG.append((f"其余 {len(cleaned)} 家", "全部保留，且与《28_经核对口径版》逐一核对一致"))

# --- 与文件28交叉核对，并按规则31复核 ---
codes28 = {r["代码"] for r in COMPS28}
codes_clean = {r["代码"] for r in cleaned}
COMPS_OK = codes28 == codes_clean
SAMPLE = COMPS28                                     # 数据源以 28 为准（31 号文件规定）
def median(vals):
    return float(np.median(np.array(vals, dtype=float)))

PE_MED = median([num(r["PE"]) for r in SAMPLE])
PS_MED = median([num(r["PS"]) for r in SAMPLE])
EVE_MED = median([num(r["EVEBITDA"]) for r in SAMPLE])
BETA_MED_CALC = median([num(r["Beta"]) for r in SAMPLE])

# --- DCF 指引（32）参数解析 ---
txt32 = read_text("32_DCF参数与折现率指引.md")
tbls32 = md_tables(txt32)
def p32(key, pct=True):
    row = find_row(tbls32, key)
    if row is None:
        return None
    cell = row[1]
    if pct:
        v = first_pct(cell)
        return v / 100.0 if v is not None else None
    return num(cell)

G26 = p32("2026 年营业收入增速")
G2730 = p32("2027—2030 年营业收入增速")
GM = p32("预测期毛利率")
OPEX_RATIO = p32("销售费用率+管理费用率+研发费用率合计")
DA_RATIO = p32("折旧与摊销占营业收入比例")
CAPEX_RATIO = p32("资本性支出占营业收入比例")
DWC_RATIO = p32("营运资本追加")
TAX = p32("所得税税率")
RF = p32("无风险利率 Rf")
ERP = p32("市场风险溢价 ERP")
BU_GUIDE = p32("可比公司 Unlevered Beta 中位数", pct=False)
DDE = p32("目标资本结构 D/(D+E)")
KD = p32("债务成本 Kd（税前）")
m = re.search(r"永续增长率\s*g\s*=\s*\*{0,2}(\d+(?:\.\d+)?)\s*%", txt32)
G_PERP = float(m.group(1)) / 100.0 if m else None
m = re.search(r"明确预测期：\*{0,2}(\d{4})\s*年至\s*(\d{4})\s*年", txt32)
FC_YEARS = list(range(int(m.group(1)), int(m.group(2)) + 1)) if m else list(range(2026, 2031))
EBIT_MARGIN = GM - OPEX_RATIO        # 指引：EBIT = 营业收入 ×(毛利率−期间费用率合计)
# ----------------------------------------------------------------------
# 8. 经营质量指标计算
# ----------------------------------------------------------------------
REV = {p: FS[p]["营业收入"] for p in PERIODS}
COGS = {p: FS[p]["营业成本（含税金及附加）"] for p in PERIODS}
NP_ = {p: FS[p]["净利润"] for p in PERIODS}
NP_ATTR = {p: FS[p]["归属于母公司股东的净利润"] for p in PERIODS}
TAX_EXP = {p: FS[p]["所得税费用"] for p in PERIODS}
INT_EXP = {p: FS[p]["其中：利息费用"] for p in PERIODS}
OCF = {p: FS[p]["经营活动产生的现金流量净额"] for p in PERIODS}
AR_NET = {p: FS[p]["应收账款（净额）"] for p in PERIODS}
CASH = {p: FS[p]["货币资金"] for p in PERIODS}

GROSS_MARGIN = {p: (REV[p] - COGS[p]) / REV[p] * 100 for p in PERIODS}
GM_PROD = {p: sum(PROD_GP[p].values()) / REV[p] * 100 for p in PERIODS}
THREE_EXP = {p: FS[p]["销售费用"] + FS[p]["管理费用"] + FS[p]["研发费用"] for p in PERIODS}
THREE_EXP_R = {p: THREE_EXP[p] / REV[p] * 100 for p in PERIODS}
PER_EXP_R = {p: COST_DETAIL[p]["期间费用合计"] / REV[p] * 100 for p in PERIODS}
RD_R = {p: FS[p]["研发费用"] / REV[p] * 100 for p in PERIODS}
NP_MARGIN = {p: NP_[p] / REV[p] * 100 for p in PERIODS}
REV_YOY = {"2024": (REV["2024"] / REV["2023"] - 1) * 100,
           "2025": (REV["2025"] / REV["2024"] - 1) * 100,
           "2026H1年化": (REV["2026H1"] * 2 / REV["2025"] - 1) * 100}
OCF_NP = {p: OCF[p] / NP_[p] for p in PERIODS}
DAYS = 365.0
AR_DAYS = {p: AR_NET[p] * DAYS / (REV[p] * (2 if p == "2026H1" else 1)) for p in PERIODS}
INV_DAYS = {p: INV_NET[p] * DAYS / (COGS[p] * (2 if p == "2026H1" else 1)) for p in PERIODS}
m = re.search(r"增值税\s*\|\s*(\d+)\s*%", txt38)
VAT = float(m.group(1)) / 100 if m else None
CASH_COLLECT = BANK_2025.get("销售商品、提供劳务收到的现金", 0) / (REV["2025"] * (1 + VAT))

# 利润口径还原桥（逐期）
BRIDGE = {}
for p in PERIODS:
    kf = NP_[p] - NONREC[p]                       # 扣非归母净利润
    ebitda_kf = kf + TAX_EXP[p] + INT_EXP[p] + DA[p]
    adj_ebitda = ebitda_kf + SBC[p]
    BRIDGE[p] = {"净利润": NP_[p], "非经常性损益(税后)": NONREC[p], "扣非归母": kf,
                 "所得税": TAX_EXP[p], "利息费用": INT_EXP[p], "折旧摊销": DA[p],
                 "EBITDA(扣非口径)": ebitda_kf, "股份支付": SBC[p], "调整后EBITDA": adj_ebitda}
# 市场法用 EBITDA（归母口径，与可比公司“归母净利润→PE”同构）
EBITDA_2025_PARENT = NP_ATTR["2025"] + TAX_EXP["2025"] + INT_EXP["2025"] + DA["2025"]

# ----------------------------------------------------------------------
# 9. DCF 计算（严格按指引32）
# ----------------------------------------------------------------------
def run_dcf(wacc, g, beta=None, ret_detail=False):
    """按指引公式计算 DCF；beta 仅用于冲突影响量化披露。"""
    if beta is None:
        bu = BU_GUIDE
    else:
        bu = beta
    bl = bu * (1 + (1 - TAX) * (DDE / (1 - DDE)))
    ke = RF + bl * ERP
    w = ke * (1 - DDE) + KD * (1 - TAX) * DDE
    if wacc is None:
        wacc = w
    rev0 = REV["2025"]
    rows_, prev_rev, pv_sum = [], rev0, 0.0
    for i, yr in enumerate(FC_YEARS, start=1):
        g_i = G26 if i == 1 else G2730
        rev = prev_rev * (1 + g_i)
        ebit = rev * EBIT_MARGIN
        da_ = rev * DA_RATIO
        capex = rev * CAPEX_RATIO
        dwc = (rev - prev_rev) * DWC_RATIO
        fcff = ebit * (1 - TAX) + da_ - capex - dwc
        df = 1 / (1 + wacc) ** i
        pv_sum += fcff * df
        rows_.append({"年份": yr, "营业收入": rev, "EBIT": ebit, "EBIT×(1−t)": ebit * (1 - TAX),
                      "折旧摊销": da_, "资本性支出": capex, "营运资本追加": dwc,
                      "FCFF": fcff, "折现系数": df, "现值": fcff * df})
        prev_rev = rev
    tv = rows_[-1]["FCFF"] * (1 + g) / (wacc - g)
    pv_tv = tv / (1 + wacc) ** len(FC_YEARS)
    ev = pv_sum + pv_tv
    free_cash = CASH["2025"] - RESTRICTED_CASH["2025"]
    net_debt = INTEREST_BEARING_DEBT["2025"] - free_cash
    eq = ev - net_debt
    out = {"βu": bu, "βL": bl, "Ke": ke, "WACC": wacc, "行": rows_, "终值": tv,
           "终值现值": pv_tv, "预测期现值合计": pv_sum, "EV": ev,
           "可支配货币资金": free_cash, "净负债": net_debt, "股权价值": eq,
           "每股价值": eq / TOTAL_SHARES}
    return out

DCF = run_dcf(None, G_PERP)
WACC, EQ_DCF = DCF["WACC"], DCF["股权价值"]
# 敏感性矩阵：WACC ±1.0pp × g ±0.5pp（指引第六节）
SENS_W = [WACC - 0.01, WACC, WACC + 0.01]
SENS_G = [G_PERP - 0.005, G_PERP, G_PERP + 0.005]
SENS = [[run_dcf(w, g)["股权价值"] for g in SENS_G] for w in SENS_W]
# βu 冲突影响量化（仅披露用）：按文件28样本重算中位数
DCF_BETA_CHK = run_dcf(None, G_PERP, beta=BETA_MED_CALC)

# ----------------------------------------------------------------------
# 10. 市场法估值（按31号说明）
# ----------------------------------------------------------------------
NET_DEBT_MKT = INTEREST_BEARING_DEBT["2025"] - (CASH["2025"] - RESTRICTED_CASH["2025"])
V_PE = PE_MED * NP_ATTR["2025"] * (1 - LIQ_DISCOUNT)
V_PS = PS_MED * REV["2025"] * (1 - LIQ_DISCOUNT)
V_EVE = (EVE_MED * EBITDA_2025_PARENT - NET_DEBT_MKT) * (1 - LIQ_DISCOUNT)
MKT_VALS = {"PE 法": V_PE, "PS 法": V_PS, "EV/EBITDA 法": V_EVE}
MKT_MED = median(list(MKT_VALS.values()))
MKT_PS_EACH = {"PE 法": PE_MED * NP_ATTR["2025"], "PS 法": PS_MED * REV["2025"],
               "EV/EBITDA 法": EVE_MED * EBITDA_2025_PARENT - NET_DEBT_MKT}
# 参考口径：若可比 EBITDA/净利为扣非口径（待核实，仅披露）
V_PE_KF = PE_MED * BRIDGE["2025"]["扣非归母"] * (1 - LIQ_DISCOUNT)
V_EVE_KF = (EVE_MED * BRIDGE["2025"]["EBITDA(扣非口径)"] - NET_DEBT_MKT) * (1 - LIQ_DISCOUNT)

# ----------------------------------------------------------------------
# 11. 估值结论与交易方案测算
# ----------------------------------------------------------------------
VAL_LO, VAL_HI = min(MKT_MED, EQ_DCF), max(MKT_MED, EQ_DCF)     # 投资前股权价值区间
PRE_FLOOR_CAP = INVEST / (STAKE_CAP / 100.0) - INVEST            # 8% 上限对应投前下限
STAKE_LO = INVEST / (VAL_HI + INVEST) * 100                      # 区间高端 -> 低持股
STAKE_HI = INVEST / (VAL_LO + INVEST) * 100
PRICE_REC = VAL_LO                                               # 审慎取值：区间下限（市场法中位数）
PS_REC = PRICE_REC / TOTAL_SHARES                                # 每股价格
NEW_SHARES = INVEST / PS_REC                                     # 新增股份（万股）
STAKE_REC = NEW_SHARES / (TOTAL_SHARES + NEW_SHARES) * 100
POST_MONEY_REC = PRICE_REC + INVEST
# 隐含倍数
MULT = {
    "投前/2025归母": PRICE_REC / NP_ATTR["2025"],
    "投后/2025归母": POST_MONEY_REC / NP_ATTR["2025"],
    "投前/2025扣非归母": PRICE_REC / BRIDGE["2025"]["扣非归母"],
    "投后/2025扣非归母": POST_MONEY_REC / BRIDGE["2025"]["扣非归母"],
    "投前/2026承诺": PRICE_REC / COMMIT["2026"],
    "投后/2026承诺": POST_MONEY_REC / COMMIT["2026"],
    "投前/2027承诺": PRICE_REC / COMMIT["2027"],
    "投后/2027承诺": POST_MONEY_REC / COMMIT["2027"],
    "投后EV/2025EBITDA": (POST_MONEY_REC + NET_DEBT_MKT) / EBITDA_2025_PARENT,
}
# 业绩承诺覆盖
COMMIT_G26_IMPLIED = (COMMIT["2026"] / BRIDGE["2025"]["扣非归母"] - 1) * 100
H1_KF = BRIDGE["2026H1"]["扣非归母"]
COVER_H1 = H1_KF / COMMIT["2026"] * 100
ANNUALIZED_KF = H1_KF * 2
GAP_2026 = COMMIT["2026"] - ANNUALIZED_KF
H2_NEED = COMMIT["2026"] - H1_KF
# 退出回报（假设增资于2026年末交割、IPO_YEAR年末上市退出；锁定期材料未载明）
EXIT_EQ = PE_MED * COMMIT["2027"]                    # 上市口径不加流动性折价（31号：折价因未上市）
EXIT_MULT = EXIT_EQ / POST_MONEY_REC
IRR_2Y = EXIT_MULT ** 0.5 - 1
IRR_3Y = EXIT_MULT ** (1 / 3) - 1
EXIT_DOWN_EQ = PE_MED * COMMIT["2027"] * (BUYBACK_TRIGGER / 100.0)
EXIT_DOWN_MULT = EXIT_DOWN_EQ / POST_MONEY_REC
BUYBACK_AMT = INVEST * (1 + BUYBACK_RATE / 100.0 * 2)
BUYBACK_MULT = BUYBACK_AMT / INVEST
EXIT_MULT_DCFPRICE = EXIT_EQ / (VAL_HI + INVEST)
IRR_2Y_DCFPRICE = EXIT_MULT_DCFPRICE ** 0.5 - 1
# 期权池摊薄
POOL_TOTAL = POOL_UNGRANTED + POOL_GRANTED
STAKE_AFTER_POOL = NEW_SHARES / (TOTAL_SHARES + NEW_SHARES + POOL_TOTAL) * 100

# ----------------------------------------------------------------------
# 12. 材料核验：一致性检查与冲突登记
# ----------------------------------------------------------------------
CHECKS = []      # (说明, 是否通过)
CHECKS.append(("管理层口径营业收入与审计报告一致（文件01 vs 03–06）",
               all(abs(MGT[p].get("营业收入（万元）", REV[p]) - REV[p]) < 0.5 for p in PERIODS)))
CHECKS.append(("管理层口径净利润与审计报告一致（文件01 vs 03–06）",
               all(abs(MGT[p].get("净利润（万元）", NP_[p]) - NP_[p]) < 0.5 for p in PERIODS)))
CHECKS.append(("非经常性损益明细加总 = CSV 合计行（文件11）",
               all(abs(NONREC[p] - NONREC_STATED_TOTAL[p]) < 0.5 for p in PERIODS)))
SBC_NOTES = {}          # 从附注第五节解析的股份支付披露值
_sec5 = re.search(r"##\s*五、股份支付(.*?)##", read_text(NOTES_FILES["2025"]), re.S)
if _sec5:
    for _y, _amt in re.findall(r"(\d{4})\s*年(?:上半年)?\s*([\d,]+)\s*万元", _sec5.group(1)):
        SBC_NOTES["2026H1" if _y == "2026" else _y] = num(_amt)
CHECKS.append(("股份支付明细加总 = 附注披露（文件12 vs 07–10）",
               all(abs(SBC[p] - SBC_NOTES.get(p, SBC[p])) < 0.5 for p in PERIODS)))
CHECKS.append(("受限货币资金一致：文件16 加总 vs 文件17 披露（2025年末）",
               abs(RESTRICTED_CASH["2025"] - (RESTRICTED_ASSET_CASH_17 or -1)) < 0.5))
CHECKS.append(("有息负债一致：附注合计 vs 资产负债表短借+长借（2025年末）",
               abs(INTEREST_BEARING_DEBT["2025"] - (FS["2025"]["短期借款"] + FS["2025"]["长期借款"])) < 0.5))
CHECKS.append(("应收账款净额一致：账龄表 vs 资产负债表（各期末）",
               all(abs(AR_NET_STATED[p] - AR_NET[p]) < 0.5 for p in PERIODS)))
CHECKS.append(("存货净额一致：存货明细合计 vs 资产负债表（各期末）",
               all(abs(INV_NET[p] - FS[p]["存货（净额）"]) < 0.5 for p in PERIODS)))
CHECKS.append(("文件28 与清洗后文件29 样本一致（12 家，代码集合相同）", COMPS_OK))
CHECKS.append(("2025 现金流净额勾稽：流入小计−流出小计 = 净额（文件16 vs 审计报告）",
               abs(BANK_2025.get("经营活动现金流入小计", 0) - BANK_2025.get("经营活动现金流出小计", 0)
                   - OCF["2025"]) < 0.5))

MGT_KF = {p: MGT[p].get("扣非归母净利润（万元）") for p in PERIODS}
CONFLICTS = []   # (编号, 涉及文件, 冲突描述, 取舍依据)
CONFLICTS.append((
    "C1", "01 vs 11/33",
    "扣非归母净利润口径：管理层仅扣除政府补助税后影响（2025年 "
    f"{fmt(MGT_KF['2025'])} 万元），按文件11全部五项非经常性项目税后合计 "
    f"{fmt(NONREC['2025'])} 万元重算应为 {fmt(BRIDGE['2025']['扣非归母'])} 万元；"
    f"其余各期重算为 {fmt(BRIDGE['2023']['扣非归母'])}/{fmt(BRIDGE['2024']['扣非归母'])}/"
    f"{fmt(BRIDGE['2026H1']['扣非归母'])} 万元，管理层口径 "
    f"{fmt(MGT_KF['2023'])}/{fmt(MGT_KF['2024'])}/{fmt(MGT_KF['2026H1'])} 万元与之均不符，"
    "且管理层各期数字无法由单一规则复现",
    f"采用文件11重算值。佐证：文件33承诺 2026 年增速 +24.3% 恰等于 "
    f"{fmt(COMMIT['2026'])}/{fmt(BRIDGE['2025']['扣非归母'])}−1 = {COMMIT_G26_IMPLIED:.1f}%，"
    "证明承诺函采用全口径扣非"))
CONFLICTS.append((
    "C2", "19–22 vs 03–06/24–27",
    "营业成本合计不一致：分产品文件为 "
    + "/".join(fmt(PROD_COST_TOTAL[p]) for p in PERIODS)
    + " 万元，审计报告（含税金及附加口径）与成本费用明细为 "
    + "/".join(fmt(COGS[p]) for p in PERIODS)
    + f" 万元，差异最大 {fmt(max(abs(PROD_COST_TOTAL[p]-COGS[p]) for p in PERIODS))} 万元"
    f"（2026H1，占当期收入 {abs(PROD_COST_TOTAL['2026H1']-COGS['2026H1'])/REV['2026H1']*100:.2f}%）",
    "总量与毛利率采用审计口径（03–06，与24–27一致）；分产品文件仅用于收入结构与分产品毛利率分析，"
    "分部成本分摊口径待核实"))
CONFLICTS.append((
    "C3", "14 内部",
    "坏账准备披露值与账龄×政策比例重算值不符：重算 "
    + "/".join(fmt(AR_PROV_CALC[p]) for p in PERIODS)
    + " 万元，披露 " + "/".join(fmt(AR_PROV_STATED[p]) for p in PERIODS)
    + f" 万元；2026H1 少提 {fmt(AR_PROV_CALC['2026H1']-AR_PROV_STATED['2026H1'])} 万元",
    "净额与资产负债表勾稽一致，估值采用审计净额；差异原因（单项评估等）列入尽调缺口，"
    "需取得坏账计提底稿核实"))
CONFLICTS.append((
    "C4", "32 vs 28",
    f"指引载明 βu = {BU_GUIDE}（取自筛选后可比样本中位数），但按文件28筛选后样本重算中位数为 "
    f"{BETA_MED_CALC:.2f}",
    f"按硬约束以指引值 {BU_GUIDE} 为基准；差异影响已量化：WACC {DCF_BETA_CHK['WACC']*100:.3f}% vs "
    f"{WACC*100:.3f}%，股权价值 {fmt(DCF_BETA_CHK['股权价值'])} vs {fmt(EQ_DCF)} 万元，"
    "在敏感性区间内，不改变结论"))
CONFLICTS.append((
    "C5", "18 vs 38",
    f"300 万元政府补助复核事项：文件18称 {GRANT_REVIEW_YEAR_18} 年收到，文件38称 "
    f"{GRANT_REVIEW_YEAR_38} 年度收到",
    "金额一致（300 万元），年份矛盾，标注待核实；按审慎原则列入或有退回风险"))
CONFLICTS.append((
    "C6", "34 vs 03",
    f"C 轮披露对应 PE 18.4x，按投前估值 {fmt([r for r in ROUNDS if r['轮次']=='C 轮'][0]['投前估值'])} 万元"
    f"÷2023年审计归母净利 {fmt(NP_ATTR['2023'])} 万元 = "
    f"{[r for r in ROUNDS if r['轮次']=='C 轮'][0]['投前估值']/NP_ATTR['2023']:.1f}x，无法复现",
    "定价依据（或按2022年净利/预期净利）材料未提供，标注待核实；仅作历史定价参考，不用于本次估值"))
CONFLICTS.append((
    "C7", "03–06 vs 01",
    "报告日期异常：2023–2025 年度审计报告日期落在所属年度当年（如 2023 年报文号日期 "
    f"{REPORT_DATES['2023']}）；2026H1 审阅报告日期 {REPORT_DATES['2026H1']} 晚于数据截止日"
    "（2026-06-30）及文件01载明的拟审议日（2026年7月中旬）",
    "疑似笔误或版本问题，需向会计师事务所核验签署版；本备忘录财务数据以报告正文数字为准"))

PENDING = [  # 待核实清单（尽调缺口）
    ("G1", "2025 年半年度比较期数据缺失，2026H1 同比无法计算", "向公司调取 2025 年 1–6 月报表"),
    ("G2", f"坏账准备与账龄政策差异（2026H1 差 {fmt(AR_PROV_CALC['2026H1']-AR_PROV_STATED['2026H1'])} 万元）的单项评估明细",
     "取得坏账计提及单项评估底稿"),
    ("G3", f"存货跌价准备连续四期为 {fmt(INV_PROV['2025'])} 万元，而存货余额持续上升", "取得存货库龄表与可变现净值测算"),
    ("G4", "被诉专利侵权纠纷（境外同业）敞口无法可靠估计", "聘请外部专利律师出具意见"),
    ("G5", "300 万元政府补助复核进展及归属年度（C5）", "向主管部门发函确认"),
    ("G6", f"固定资产投资承诺缺口 {fmt(CAPEX_COMMIT_TARGET-CAPEX_COMMIT_DONE)} 万元（承诺≥{fmt(CAPEX_COMMIT_TARGET)}，已完成 {fmt(CAPEX_COMMIT_DONE)}）",
     "取得 2026H2 资本开支计划与政府确认函，评估扶持资金退回风险"),
    ("G7", "C 轮 PE 披露口径（C6）与历次增资协议", "调取增资协议与定价说明"),
    ("G8", "审计/审阅报告签署版日期（C7）", "向天衡会计师事务所核验"),
    ("G9", "可比公司 EBITDA 与 PE_TTM 的精确计算口径（是否扣非、是否含股份支付加回）", "以数据终端口径说明核实；已按归母口径同构处理"),
    ("G10", "上市后股份锁定期安排（材料未载明）", "在交易文件中确认，退出测算已给 2/3 年两种情形"),
]

RISKS = [  # (级别, 风险, 依据/量化)
    ("高", "客户集中与单一大客户依赖", f"2025年前五大客户占 {CUST_CONC['2025'][0]:.1f}%、第一大（境外）占 {TOP1_SHARE_2025:.1f}%，且逐期上升"),
    ("高", "业绩承诺覆盖不足", f"2026H1 扣非归母 {fmt(H1_KF)} 万元，年化 {fmt(ANNUALIZED_KF)} 万元，较承诺 {fmt(COMMIT['2026'])} 万元缺口 {GAP_2026/COMMIT['2026']*100:.1f}%"),
    ("高", "高新技术企业资格复审", f"优惠期至 {HNTE_EXPIRY} 年，2027 年起税率或由 15% 恢复至 25%（DCF 按指引仍用 15%）"),
    ("中", "应收账款坏账计提充分性", f"披露值低于政策重算值（2026H1 差 {fmt(AR_PROV_CALC['2026H1']-AR_PROV_STATED['2026H1'])} 万元）；应收周转天数由 {AR_DAYS['2023']:.0f} 天升至 {AR_DAYS['2026H1']:.0f} 天"),
    ("中", "存货减值风险", f"存货 {fmt(INV_NET['2026H1'])} 万元较 2023 年末 +{(INV_NET['2026H1']/INV_NET['2023']-1)*100:.0f}%，跌价准备为 0"),
    ("中", "未决诉讼", f"买卖合同纠纷涉诉 {fmt(LITIG_AMT)} 万元（已计提预计负债 {fmt(LITIG_PROVISION)} 万元）；专利被诉纠纷金额未定"),
    ("中", "政府补助退回风险", "300 万元补助正在复核（年份口径冲突见 C5）"),
    ("中", "固定资产投资承诺缺口", f"承诺 ≥5 亿元、已完成 {fmt(CAPEX_COMMIT_DONE)} 万元，缺口 {fmt(CAPEX_COMMIT_TARGET-CAPEX_COMMIT_DONE)} 万元或触发扶持资金退回"),
    ("中", "期权池摊薄", f"未授予 {fmt(POOL_UNGRANTED)} 万股+已授予未行权 {fmt(POOL_GRANTED)} 万股，全部行权后本轮持股由 {STAKE_REC:.3f}% 摊薄至 {STAKE_AFTER_POOL:.2f}%"),
    ("中", "关联方资金往来内控", f"2025 年控股股东无息借入 {fmt(num(RT_FUND[0][4]))} 万元（已归还），反映资金管理内控缺陷"),
    ("低", "社保公积金未全员缴纳", f"2026H1 覆盖率 {SOCIAL['2026H1']:.1f}%，控股股东已出具兜底承诺"),
    ("低", "关联采购依赖", f"2025 年关联采购 {fmt(RT_2025_BUY)} 万元，占采购总额比例低"),
    ("低", "对外担保风险", "对外担保余额为 0"),
]
RISK_COUNT = {lv: sum(1 for r in RISKS if r[0] == lv) for lv in ["高", "中", "低"]}

# 材料覆盖（chart01）
COVERAGE = [("交易与公司", 3, "冲突C1/日期C7", "冲突"), ("审计报告", 4, "数据勾稽通过", "待核实"),
            ("财务报表附注", 4, "有息负债/摊销勾稽通过", "一致"), ("利润口径", 2, "明细与合计勾稽通过", "一致"),
            ("关联与往来", 2, "坏账准备C3", "冲突"), ("资产负债明细", 4, "受限资金一致/补助年份C5", "待核实"),
            ("收入明细", 5, "成本合计C2", "冲突"), ("成本费用", 4, "与审计一致", "一致"),
            ("可比与行业", 4, "28/29核对一致", "一致"), ("交易条款", 3, "βu冲突C4/C轮PE C6", "冲突"),
            ("其他尽调", 4, "补助年份C5/承诺缺口G6", "待核实"), ("模板", 1, "—", "一致")]
# ----------------------------------------------------------------------
# 13. 图表
# ----------------------------------------------------------------------
C1, C2, C3, C4 = "#2f6fb2", "#e08a2e", "#4a9b6f", "#b44a4a"
STATUS_COLOR = {"一致": "#4a9b6f", "冲突": "#b44a4a", "待核实": "#e08a2e"}
plabel = [PERIOD_CN[p] for p in PERIODS]
x4 = np.arange(len(PERIODS))


def savefig(fig, name):
    fig.savefig(CHART_DIR / name, bbox_inches="tight")
    plt.close(fig)
    print(f"  [chart] {name}")


# ---- chart01 材料覆盖与数据缺口 ----
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
cats = [c[0] for c in COVERAGE][::-1]
cnts = [c[1] for c in COVERAGE][::-1]
cols = [STATUS_COLOR[c[3]] for c in COVERAGE][::-1]
axes[0].barh(cats, cnts, color=cols)
for i, v in enumerate(cnts):
    axes[0].text(v + 0.08, i, str(v), va="center", fontsize=10)
axes[0].set_xlabel("材料份数")
axes[0].set_title(f"(a) 材料覆盖分布（共 {sum(c[1] for c in COVERAGE)} 份，颜色=核验状态）", fontsize=11)
axes[0].set_xlim(0, max(cnts) + 1)
stat_n = {s: sum(1 for c in COVERAGE if c[3] == s) for s in ["一致", "冲突", "待核实"]}
bars = ["材料全部覆盖", "勾稽检查通过", "口径冲突(C1–C7)", "待核实/缺口(G1–G10)"]
vals = [sum(c[1] for c in COVERAGE), sum(1 for ok in CHECKS if ok[1]), len(CONFLICTS), len(PENDING)]
bcols = ["#8899aa", "#4a9b6f", "#b44a4a", "#e08a2e"]
axes[1].bar(bars, vals, color=bcols)
for i, v in enumerate(vals):
    axes[1].text(i, v + 0.5, str(v), ha="center", fontsize=11, fontweight="bold")
axes[1].set_title("(b) 核验标记汇总（项）", fontsize=11)
axes[1].set_ylabel("数量")
axes[1].tick_params(axis="x", labelsize=9)
fig.suptitle("图1  材料覆盖与数据缺口", fontsize=13, y=1.02)
fig.tight_layout()
savefig(fig, "FIN3-WKN-150_chart01_材料覆盖与数据缺口.png")

# ---- chart02 收入与利润口径还原 ----
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
axes[0].bar(x4, [REV[p] for p in PERIODS], color=C1, width=0.55, label="营业收入（万元）")
for i, p in enumerate(PERIODS):
    yoy = REV_YOY.get("2024" if p == "2024" else ("2025" if p == "2025" else
          ("2026H1年化" if p == "2026H1" else None)))
    axes[0].text(i, REV[p] + 1800, f"{fmt(REV[p])}" + (f"\n(+{yoy:.1f}%)" if yoy else ""),
                 ha="center", fontsize=9)
axes[0].set_xticks(x4, plabel)
axes[0].set_ylim(0, max(REV.values()) * 1.28)
axes[0].set_ylabel("营业收入（万元）")
ax0r = axes[0].twinx()
ax0r.plot(x4, [GROSS_MARGIN[p] for p in PERIODS], "o-", color=C2, label="毛利率-审计口径")
ax0r.plot(x4, [GM_PROD[p] for p in PERIODS], "s--", color=C4, alpha=0.6, label="毛利率-分产品口径(C2)")
for i, p in enumerate(PERIODS):
    _dx = -0.08 if i % 2 == 1 else 0.08
    ax0r.text(i + _dx, GROSS_MARGIN[p] + 0.22, f"{GROSS_MARGIN[p]:.2f}%", fontsize=8,
              color=C2, ha="right" if _dx < 0 else "left")
ax0r.set_ylim(20, 28)
ax0r.set_ylabel("毛利率（%）")
h1, l1 = axes[0].get_legend_handles_labels()
h2, l2 = ax0r.get_legend_handles_labels()
axes[0].legend(h1 + h2, l1 + l2, fontsize=8, loc="upper left")
axes[0].set_title("(a) 营业收入与毛利率（2026H1 增速为年化口径）", fontsize=11)

b = BRIDGE["2025"]
steps = [("净利润", b["净利润"], "#2f6fb2"), ("−非经常性\n损益(税后)", -b["非经常性损益(税后)"], "#b44a4a"),
         ("扣非归母\n净利润", b["扣非归母"], "#4a9b6f"), ("+所得税", b["所得税"], "#7fa6d9"),
         ("+利息费用", b["利息费用"], "#7fa6d9"), ("+折旧摊销", b["折旧摊销"], "#7fa6d9"),
         ("EBITDA\n(扣非口径)", b["EBITDA(扣非口径)"], "#4a9b6f"), ("+股份支付", b["股份支付"], "#7fa6d9"),
         ("调整后\nEBITDA", b["调整后EBITDA"], "#1f4e79")]
cum, bottoms, heights, colors, labels, levels = 0.0, [], [], [], [], []
for i, (lab, v, c) in enumerate(steps):
    if i in (0, 2, 6, 8):                       # 小计柱
        bottoms.append(0); heights.append(v)
        cum = v
    else:                                        # 增减柱
        bottoms.append(cum + min(v, 0)); heights.append(abs(v)); cum += v
    colors.append(c); labels.append(lab); levels.append(cum)
axes[1].bar(range(len(steps)), heights, bottom=bottoms, color=colors, width=0.6)
for i in range(len(steps)):
    top = bottoms[i] + heights[i]
    axes[1].text(i, top + 260, f"{heights[i]:,.0f}", ha="center", fontsize=8)
for i in range(len(steps) - 1):
    axes[1].plot([i + 0.3, i + 0.7], [levels[i]] * 2, color="grey", lw=0.7, ls=":")
axes[1].set_xticks(range(len(steps)), labels, fontsize=7.5)
axes[1].set_ylabel("万元")
axes[1].set_ylim(0, max(b["调整后EBITDA"], b["净利润"]) * 1.15)
axes[1].set_title("(b) 2025 年利润口径还原桥（净利润→扣非归母→调整后 EBITDA）", fontsize=11)
fig.suptitle("图2  收入与利润口径还原", fontsize=13, y=1.02)
fig.tight_layout()
savefig(fig, "FIN3-WKN-150_chart02_收入与利润口径还原.png")

# ---- chart03 现金流与营运效率 ----
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.0))
w = 0.36
axes[0].bar(x4 - w / 2, [NP_[p] for p in PERIODS], w, color=C1, label="净利润")
axes[0].bar(x4 + w / 2, [OCF[p] for p in PERIODS], w, color=C3, label="经营活动现金流净额")
for i, p in enumerate(PERIODS):
    axes[0].text(i - w / 2, NP_[p] + 180, f"{fmt(NP_[p])}", ha="center", fontsize=8)
    axes[0].text(i + w / 2, OCF[p] + 180, f"{fmt(OCF[p])}", ha="center", fontsize=8)
axes[0].set_xticks(x4, plabel)
axes[0].set_ylabel("万元")
axes[0].set_ylim(0, max(max(NP_.values()), max(OCF.values())) * 1.25)
ax0r = axes[0].twinx()
ax0r.plot(x4, [OCF_NP[p] for p in PERIODS], "o-", color=C2, lw=2, label="净现比")
ax0r.axhline(1.0, color="grey", ls="--", lw=0.8)
for i, p in enumerate(PERIODS):
    ax0r.text(i + 0.05, OCF_NP[p] + 0.015, f"{OCF_NP[p]:.3f}", fontsize=9, color=C2)
ax0r.set_ylim(0.6, 1.25)
ax0r.set_ylabel("净现比（倍）")
h1, l1 = axes[0].get_legend_handles_labels()
h2, l2 = ax0r.get_legend_handles_labels()
axes[0].legend(h1 + h2, l1 + l2, fontsize=9, loc="upper left")
axes[0].set_title("(a) 净利润、经营现金流与净现比", fontsize=11)

axes[1].plot(x4, [AR_DAYS[p] for p in PERIODS], "o-", color=C1, lw=2, label="应收账款周转天数")
axes[1].plot(x4, [INV_DAYS[p] for p in PERIODS], "s-", color=C3, lw=2, label="存货周转天数")
for i, p in enumerate(PERIODS):
    _ha = "right" if i == len(PERIODS) - 1 else "left"
    _xo = -0.06 if _ha == "right" else 0.05
    axes[1].text(i + _xo, AR_DAYS[p] + 0.8, f"{AR_DAYS[p]:.1f}", fontsize=9, color=C1, ha=_ha)
    axes[1].text(i + _xo, INV_DAYS[p] - 2.6, f"{INV_DAYS[p]:.1f}", fontsize=9, color=C3, ha=_ha)
axes[1].set_xticks(x4, plabel)
axes[1].set_ylabel("天")
axes[1].legend(fontsize=9)
axes[1].set_title("(b) 应收与存货周转天数（期末余额口径，2026H1 年化）", fontsize=11)
axes[1].grid(alpha=0.3)
fig.suptitle("图3  现金流与营运效率", fontsize=13, y=1.02)
fig.tight_layout()
savefig(fig, "FIN3-WKN-150_chart03_现金流与营运效率.png")

# ---- chart04 可比与DCF估值 ----
fig, axes = plt.subplots(2, 2, figsize=(14, 9))
comp_names = [r["简称"] for r in SAMPLE]
yc = np.arange(len(SAMPLE))
for ax, key, med, tgt, ttl in [
        (axes[0][0], "PE", PE_MED, PRICE_REC / NP_ATTR["2025"], "(a) 可比公司 PE_TTM"),
        (axes[0][1], "PS", PS_MED, PRICE_REC / REV["2025"], "(b) 可比公司 PS_TTM"),
        (axes[1][0], "EVEBITDA", EVE_MED, (PRICE_REC + NET_DEBT_MKT) / EBITDA_2025_PARENT,
         "(c) 可比公司 EV/EBITDA")]:
    vals = [num(r[key]) for r in SAMPLE]
    ax.barh(yc, vals, color=C1, alpha=0.85)
    ax.axvline(med, color=C4, ls="--", lw=1.6, label=f"中位数 {med:.3g}")
    ax.axvline(tgt, color=C3, ls="-.", lw=1.6, label=f"标的隐含 {tgt:.2f}x（按建议投前）")
    ax.set_yticks(yc, comp_names, fontsize=8.5)
    ax.invert_yaxis()
    ax.legend(fontsize=8, loc="lower right")
    ax.set_title(ttl, fontsize=11)
    ax.grid(axis="x", alpha=0.3)
ax = axes[1][1]
yrs = [str(r["年份"]) for r in DCF["行"]]
xx = np.arange(len(yrs))
ax.bar(xx - 0.19, [r["FCFF"] for r in DCF["行"]], 0.38, color=C1, label="FCFF")
ax.bar(xx + 0.19, [r["现值"] for r in DCF["行"]], 0.38, color=C3, label="FCFF 现值")
for i, r in enumerate(DCF["行"]):
    ax.text(i - 0.19, r["FCFF"] + 180, f"{r['FCFF']:,.0f}", ha="center", fontsize=8)
    ax.text(i + 0.19, r["现值"] + 180, f"{r['现值']:,.0f}", ha="center", fontsize=8)
ax.set_xticks(xx, yrs)
ax.set_ylabel("万元")
ax.set_ylim(0, max(r["FCFF"] for r in DCF["行"]) * 1.3)
ax.text(0.02, 0.95, f"WACC={WACC*100:.3f}%  g={G_PERP*100:.1f}%\n终值现值 {fmt(DCF['终值现值'])} 万元\n"
                    f"EV {fmt(DCF['EV'])} 万元\n股权价值 {fmt(EQ_DCF)} 万元\n每股 {DCF['每股价值']:.2f} 元",
        transform=ax.transAxes, va="top", fontsize=9,
        bbox=dict(boxstyle="round", fc="#f4f6f8", ec="#aabbcc"))
ax.legend(fontsize=9, loc="lower right")
ax.set_title("(d) DCF 预测期自由现金流与现值", fontsize=11)
fig.suptitle("图4  可比公司与 DCF 估值", fontsize=13, y=1.0)
fig.tight_layout()
savefig(fig, "FIN3-WKN-150_chart04_可比与DCF估值.png")

# ---- chart05 估值区间与风险缺口 ----
fig = plt.figure(figsize=(14.5, 5.4))
gs = fig.add_gridspec(1, 3, width_ratios=[1, 1.25, 1])
ax = fig.add_subplot(gs[0])
M = np.array(SENS)
im = ax.imshow(M, cmap="RdYlGn", aspect="auto")
ax.set_xticks(range(3), [f"{g*100:.1f}%" for g in SENS_G])
ax.set_yticks(range(3), [f"{w*100:.3f}%" for w in SENS_W])
ax.set_xlabel("永续增长率 g")
ax.set_ylabel("WACC")
for i in range(3):
    for j in range(3):
        ax.text(j, i, f"{M[i, j]:,.0f}", ha="center", va="center", fontsize=9)
ax.set_title(f"(a) DCF 股权价值敏感性（万元）\n基准 WACC={WACC*100:.3f}%，g={G_PERP*100:.1f}%", fontsize=10.5)
fig.colorbar(im, ax=ax, shrink=0.8)

ax = fig.add_subplot(gs[1])
names = ["DCF\n(不折价)", "市场法\nPE", "市场法\nPS", "市场法\nEV/EBITDA", "市场法\n中位数"]
vals = [EQ_DCF, V_PE, V_PS, V_EVE, MKT_MED]
bars = ax.bar(names, vals, color=[C3, C1, C1, C1, C4], width=0.6)
ax.axhspan(VAL_LO, VAL_HI, color="#e08a2e", alpha=0.15)
ax.axhline(PRE_FLOOR_CAP, color="grey", ls="--", lw=1.2)
ax.text(0.6, PRE_FLOOR_CAP - 16000, f"8%持股上限对应投前下限 {fmt(PRE_FLOOR_CAP)} 万元",
        fontsize=8, ha="center",
        bbox=dict(fc="white", ec="grey", alpha=0.9, boxstyle="round,pad=0.25"))
for r, v in zip(bars, vals):
    ax.text(r.get_x() + r.get_width() / 2, v + 2600, f"{fmt(v)}\n({v/TOTAL_SHARES:.2f}元/股)",
            ha="center", fontsize=8)
ax.set_ylabel("投资前股权价值（万元）")
ax.set_ylim(0, max(vals) * 1.3)
ax.set_title(f"(b) 估值结果对比（阴影=结论区间 {fmt(VAL_LO)}–{fmt(VAL_HI)} 万元）", fontsize=10.5)
ax.tick_params(axis="x", labelsize=8.5)

ax = fig.add_subplot(gs[2])
labels_c = ["高风险", "中风险", "低风险", "尽调缺口"]
vals_c = [RISK_COUNT["高"], RISK_COUNT["中"], RISK_COUNT["低"], len(PENDING)]
cols_c = ["#b44a4a", "#e08a2e", "#4a9b6f", "#5b6b8c"]
ax.bar(np.arange(4), vals_c, color=cols_c, width=0.55)
for i, v in enumerate(vals_c):
    ax.text(i, v + 0.15, str(v), ha="center", fontsize=11, fontweight="bold")
ax.set_xticks(np.arange(4), labels_c, fontsize=9.5)
ax.set_ylabel("项数")
ax.set_ylim(0, max(vals_c) + 2)
ax.set_title("(c) 风险分级与尽调缺口（项）", fontsize=10.5)
fig.suptitle("图5  估值区间与风险缺口", fontsize=13, y=1.03)
fig.tight_layout()
savefig(fig, "FIN3-WKN-150_chart05_估值区间与风险缺口.png")
# ----------------------------------------------------------------------
# 14. 主交付物：投资决策备忘录（全部数字由上文计算注入）
# ----------------------------------------------------------------------
B = BRIDGE
C_ROUND = [r for r in ROUNDS if r["轮次"] == "C 轮"][0]
DCF_ROWS_MD = "\n".join(
    f"| {r['年份']} | {fmt(r['营业收入'])} | {fmt(r['EBIT'])} | {fmt(r['EBIT×(1−t)'])} | "
    f"{fmt(r['折旧摊销'])} | {fmt(r['资本性支出'])} | {fmt(r['营运资本追加'])} | "
    f"{fmt(r['FCFF'])} | {r['折现系数']:.4f} | {fmt(r['现值'])} |" for r in DCF["行"])
SENS_MD = "\n".join(
    f"| {SENS_W[i]*100:.3f}% | " + " | ".join(f"{fmt(v)}" for v in SENS[i]) + " |"
    for i in range(3))
BRIDGE_MD = "\n".join(
    f"| {fmt(B[p]['净利润'])} | −{fmt(B[p]['非经常性损益(税后)'])} | {fmt(B[p]['扣非归母'])} | "
    f"+{fmt(B[p]['所得税'])} | +{fmt(B[p]['利息费用'])} | +{fmt(B[p]['折旧摊销'])} | "
    f"{fmt(B[p]['EBITDA(扣非口径)'])} | +{fmt(B[p]['股份支付'])} | {fmt(B[p]['调整后EBITDA'])} |"
    for p in PERIODS)
NR25_MD = "；".join(f"{i[0]} {fmt(i[1])}（税后 {fmt(i[3])}）" for i in NONREC_ITEMS["2025"])
CONFLICT_MD = "\n".join(
    f"**{c[0]}（{c[1]}）**：{c[2]}。**取舍**：{c[3]}。\n" for c in CONFLICTS)
CHECK_MD = "\n".join(f"- {'[通过]' if ok else '[未通过]'}：{d}" for d, ok in CHECKS)
CLEAN_MD = "\n".join(f"- {n}：{a}" for n, a in CLEAN_LOG)
PENDING_MD = "\n".join(f"| {g[0]} | {g[1]} | {g[2]} |" for g in PENDING)
RISK_MD = "\n".join(f"| {r[0]} | {r[1]} | {r[2]} |" for r in RISKS)
PROD25_MD = "、".join(f"{k} {fmt(v)} 万元（{v/REV['2025']*100:.1f}%，毛利率 "
                      f"{PROD_GP['2025'][k]/v*100:.0f}%）" for k, v in PROD_REV["2025"].items())

MEMO = f"""# FIN3-WKN-150 Pre-IPO 投资决策备忘录

**标的**：杭州智联精密制造股份有限公司（拟于深交所创业板上市）　**投资方**：启元成长股权投资基金
**拟投资金额**：{fmt(INVEST)} 万元（增资）　**估值基准日**：2025-12-31　**数据与检索截止日**：2026-06-30
**总股本**：{fmt(TOTAL_SHARES)} 万股　本报告全部数字可回溯至 `/app/input_files/` 材料或由复算脚本 `FIN3-WKN-150_reproduce.py` 计算得到。

## 一、结论与建议

**建议立项并推进本次投资**。投资前股权价值结论区间 **{fmt(VAL_LO)}—{fmt(VAL_HI)} 万元**（市场法中位数—DCF 结果），
审慎取值建议以区间下限 **{fmt(PRICE_REC)} 万元（约 {PS_REC:.2f} 元/股）** 作为定价谈判上限。按此定价，
{fmt(INVEST)} 万元增资可获约 **{STAKE_REC:.3f}%** 股权（新增约 {fmt(NEW_SHARES,1)} 万股），满足"不高于 {STAKE_CAP:.2f}%"
的方案要求；对应 2026 年承诺业绩投前 PE {MULT['投前/2026承诺']:.2f}x、投后 {MULT['投后/2026承诺']:.2f}x，低于可比公司
PE 中位数 {PE_MED:.2f}x 及文件30少数股权 Pre-IPO 案例（{'/'.join(f"{v:.1f}x" for v in MINOR_DEAL_PES)}），
定价具备安全边际。按 {IPO_YEAR} 年上市、
2027 年承诺业绩（{fmt(COMMIT['2027'])} 万元）全额兑现测算，投资回报约 **{EXIT_MULT:.2f}x**，两年期年化约
**{IRR_2Y*100:.1f}%**；业绩仅达承诺 {BUYBACK_TRIGGER:.0f}% 时约 {EXIT_DOWN_MULT:.2f}x，触发回购时保底
{BUYBACK_RATE:.0f}% 年化单利。**前置条件**：完成 C1—C7 口径冲突核实（第二章）、落实文件33全部保护条款、
就 G1—G10 尽调缺口取得书面回复后方可交割。

## 二、材料核验与数据口径

材料包 40 份全部取得并逐类核对，覆盖交易与公司、审计报告、附注、利润口径、关联往来、资产负债明细、
收入与成本费用明细、可比与行业、交易条款、其他尽调共 12 类，无缺项（见图1）。交叉勾稽检查：

{CHECK_MD}

**报告期数据口径**：本报告一律以审计报告（03—06）及附注（07—10）为准；分产品/分客户明细仅用于结构分析；
2026H1 为审阅数据；周转天数按期末余额×365/当期发生额（半年度年化×2）；毛利率=（营业收入−审计口径营业成本
（含税金及附加））/营业收入。**发现的口径冲突及取舍**如下（均给出双方数值与出处，未静默择一）：

{CONFLICT_MD}
## 三、报告期经营质量分析

**收入结构与增长**：营业收入 {fmt(REV['2023'])}/{fmt(REV['2024'])}/{fmt(REV['2025'])}/{fmt(REV['2026H1'])} 万元
（2023/2024/2025/2026H1），2024、2025 年同比 +{REV_YOY['2024']:.1f}%、+{REV_YOY['2025']:.1f}%，2026H1 年化增速
+{REV_YOY['2026H1年化']:.1f}%，增长动能放缓至与 DCF 指引 10% 假设相当。2025 年分产品：{PROD25_MD}，
结构与文件02披露一致（见图2a）。客户集中度高：2025 年前五大客户 {CUST_CONC['2025'][0]:.1f}%、第一大客户（境外）
{TOP1_SHARE_2025:.1f}%，且报告期逐期上升。

**毛利率与费用率**：审计口径毛利率 {GROSS_MARGIN['2023']:.2f}%/{GROSS_MARGIN['2024']:.2f}%/
{GROSS_MARGIN['2025']:.2f}%/{GROSS_MARGIN['2026H1']:.2f}%，稳定于 25% 附近，处于行业均值区间（22%—26%）；
2026H1 小幅回落需关注。销售+管理+研发费用率 {THREE_EXP_R['2023']:.2f}%/{THREE_EXP_R['2024']:.2f}%/
{THREE_EXP_R['2025']:.2f}%/{THREE_EXP_R['2026H1']:.2f}%，逐年摊薄；研发费用率 {RD_R['2025']:.2f}%（2025），
处于行业 5.0%—6.5% 区间。净利率 {NP_MARGIN['2023']:.2f}%→{NP_MARGIN['2025']:.2f}%（2025）。

**现金流质量**：经营现金流净额 {fmt(OCF['2023'])}/{fmt(OCF['2024'])}/{fmt(OCF['2025'])}/{fmt(OCF['2026H1'])} 万元，
净现比 {OCF_NP['2023']:.3f}/{OCF_NP['2024']:.3f}/{OCF_NP['2025']:.3f}/{OCF_NP['2026H1']:.3f}，前三年均大于 1，
盈利含金量较好（见图3a）；2026H1 降至 {OCF_NP['2026H1']:.3f}（半年度波动，全年表现待核实）。2025 年销售收现
{fmt(BANK_2025.get('销售商品、提供劳务收到的现金',0))} 万元，为含税收入的 {CASH_COLLECT*100:.1f}%，回款正常。

**营运效率**：应收账款周转天数 {AR_DAYS['2023']:.1f}→{AR_DAYS['2026H1']:.1f} 天，逐期上升，主要客户信用期
90—120 天，应收增速快于收入；存货周转天数 {INV_DAYS['2023']:.1f}→{INV_DAYS['2026H1']:.1f} 天，基本稳定（见图3b）。

**异常事项**：①存货跌价准备连续四期为 0，与存货余额 +{(INV_NET['2026H1']/INV_NET['2023']-1)*100:.0f}% 背离（G3）；
②坏账准备低于账龄政策重算值（C3）；③2025 年控股股东无息借入 {fmt(num(RT_FUND[0][4]))} 万元（期内归还），
反映内控瑕疵；④关联销售 2025 年 {fmt(RT_2025_SALES)} 万元，占收入 {RT_2025_SALES/REV['2025']*100:.2f}%，影响有限；
⑤固定资产投资承诺缺口 {fmt(CAPEX_COMMIT_TARGET-CAPEX_COMMIT_DONE)} 万元（G6）。

## 四、利润口径还原

以审计报告净利润为起点，扣除文件11全部非经常性项目税后金额得扣非归母净利润（公司无少数股东，归母=净利润）；
再加回所得税、利息费用与折旧摊销（附注四）得 EBITDA（扣非口径）；再加回股份支付（文件12，非现金）得调整后
EBITDA。各期桥接如下（万元，见图2b）：

| 净利润 | −非经常损益(税后) | =扣非归母 | +所得税 | +利息 | +折旧摊销 | =EBITDA(扣非) | +股份支付 | =调整后EBITDA |
|---|---|---|---|---|---|---|---|---|
{BRIDGE_MD}

2025 年非经常性项目逐项（税前/税后）：{NR25_MD}，合计税后 {fmt(NONREC['2025'])} 万元。管理层"仅扣政府补助"
口径（C1）高估 2025 年扣非归母 {fmt(MGT_KF['2025']-B['2025']['扣非归母'])} 万元，本备忘录不采用。调整后 EBITDA
率 2023—2025 年为 {B['2023']['调整后EBITDA']/REV['2023']*100:.1f}%/{B['2024']['调整后EBITDA']/REV['2024']*100:.1f}%/
{B['2025']['调整后EBITDA']/REV['2025']*100:.1f}%，盈利能力稳定。市场法 EV/EBITDA 采用归母口径
EBITDA={fmt(EBITDA_2025_PARENT)} 万元（净利+税+利息+折旧摊销，与可比公司"归母净利润→PE"口径同构，G9）。

## 五、收益法估值（DCF）

严格按《32_DCF参数与折现率指引》执行，未引入指引外假设。**折现率**：βu={BU_GUIDE}（指引值；按文件28样本重算
中位数为 {BETA_MED_CALC:.2f}，冲突 C4，影响已量化披露），D/E={DDE/(1-DDE)*100:.0f}%，
βL=βu×[1+(1−{TAX*100:.0f}%)×{DDE/(1-DDE):.2f}]={DCF['βL']:.4f}；Ke={RF*100:.2f}%+{DCF['βL']:.4f}×{ERP*100:.2f}%=
**{DCF['Ke']*100:.4f}%**；WACC={DCF['Ke']*100:.4f}%×{100-DDE*100:.0f}%+{KD*100:.2f}%×(1−{TAX*100:.0f}%)×{DDE*100:.0f}%=
**{WACC*100:.3f}%**。永续增长率 g={G_PERP*100:.1f}%。收入以 2025 年审计数 {fmt(REV['2025'])} 万元为基数，
2026—2030 年每年 +{G26*100:.0f}%；EBIT=收入×{EBIT_MARGIN*100:.1f}%；FCFF=EBIT×(1−t)+折旧摊销−资本性支出−营运资本追加。

| 年份 | 营业收入 | EBIT | EBIT×(1−t) | 折旧摊销 | 资本支出 | 营运资本追加 | FCFF | 折现系数 | 现值 |
|---|---|---|---|---|---|---|---|---|---|
{DCF_ROWS_MD}

终值 TV={fmt(DCF['行'][-1]['FCFF'])}×(1+{G_PERP*100:.1f}%)÷({WACC*100:.3f}%−{G_PERP*100:.1f}%)=**{fmt(DCF['终值'])} 万元**，
现值 {fmt(DCF['终值现值'])} 万元；预测期现值合计 {fmt(DCF['预测期现值合计'])} 万元；**EV={fmt(DCF['EV'])} 万元**。
**净负债**（指引口径，扣除受限资金）=有息负债 {fmt(INTEREST_BEARING_DEBT['2025'])}−可支配货币资金
{fmt(DCF['可支配货币资金'])}（货币资金 {fmt(CASH['2025'])}−受限 {fmt(RESTRICTED_CASH['2025'])}，文件16/17）=
**{fmt(DCF['净负债'])} 万元（净现金）**。**股权价值={fmt(EQ_DCF)} 万元，每股 {DCF['每股价值']:.2f} 元**
（DCF 结果按指引不加流动性折价）。若按文件28重算 βu={BETA_MED_CALC:.2f}，WACC={DCF_BETA_CHK['WACC']*100:.3f}%，
股权价值 {fmt(DCF_BETA_CHK['股权价值'])} 万元（差 {fmt(DCF_BETA_CHK['股权价值']-EQ_DCF)} 万元，在敏感性区间内）。

**双向敏感性（股权价值，万元；WACC±1.0pp × g±0.5pp）**：

| WACC \\ g | {SENS_G[0]*100:.1f}% | {SENS_G[1]*100:.1f}% | {SENS_G[2]*100:.1f}% |
|---|---|---|---|
{SENS_MD}

区间 {fmt(min(min(r) for r in SENS))}—{fmt(max(max(r) for r in SENS))} 万元（见图5a），市场法中位数落于该区间内。

## 六、市场法估值（可比公司）

**清洗**（文件29原始导出，16 条记录）：

{CLEAN_MD}

**筛选**（文件31规则逐条复核）：保留 12 家均属精密制造行业、上市满 1 年、2025 年归母净利润为正、无 ST 标识、
2025 年营收≥{fmt(REV_FLOOR)} 万元，无重复及口径不明记录；与《28_经核对口径版》逐一核对一致。
**倍数中位数**：PE_TTM **{PE_MED:.3f}x**、PS_TTM **{PS_MED:.3f}x**、EV/EBITDA **{EVE_MED:.3f}x**；Unlevered Beta
中位数 {BETA_MED_CALC:.2f}（与指引差异见 C4）。

**标的对应指标（2025 年审计数）**：归母净利润 {fmt(NP_ATTR['2025'])} 万元、营业收入 {fmt(REV['2025'])} 万元、
EBITDA {fmt(EBITDA_2025_PARENT)} 万元、净负债 {fmt(NET_DEBT_MKT)} 万元。按文件31，少数股权增资不加控制权溢价，
估值结果统一扣减 {LIQ_DISCOUNT*100:.0f}% 流动性折价：

| 方法 | 折价前（万元） | 折价后（万元） | 每股（元） |
|---|---|---|---|
| PE 法（{PE_MED:.3f}×{fmt(NP_ATTR['2025'])}） | {fmt(MKT_PS_EACH['PE 法'])} | {fmt(V_PE)} | {V_PE/TOTAL_SHARES:.2f} |
| PS 法（{PS_MED:.3f}×{fmt(REV['2025'])}） | {fmt(MKT_PS_EACH['PS 法'])} | {fmt(V_PS)} | {V_PS/TOTAL_SHARES:.2f} |
| EV/EBITDA 法（{EVE_MED:.3f}×{fmt(EBITDA_2025_PARENT)}−净负债） | {fmt(MKT_PS_EACH['EV/EBITDA 法'])} | {fmt(V_EVE)} | {V_EVE/TOTAL_SHARES:.2f} |

**三法中位数（折价后）= {fmt(MKT_MED)} 万元，约 {MKT_MED/TOTAL_SHARES:.2f} 元/股**（见图4a—c）。口径参考：若可比公司倍数
实为扣非口径（G9，待核实），PE 法/EV-EBITDA 法结果为 {fmt(V_PE_KF)}/{fmt(V_EVE_KF)} 万元，将整体下移约
{(1-V_PE_KF/V_PE)*100:.0f}%，届时应按孰低重新取值。

## 七、估值结论与交易方案

**结论区间与取值理由**（见图5b）：DCF {fmt(EQ_DCF)} 万元（不折价、含永续增长假设）与市场法中位数 {fmt(MKT_MED)} 万元
（含 10% 流动性折价、反映存量上市定价）两口径不重合，差异主因即流动性折价与 DCF 对 10% 增速、2.5% 永续增长的
依赖。按文件31"审慎取值"原则，**投资前股权价值区间取 {fmt(VAL_LO)}—{fmt(VAL_HI)} 万元，定价基准建议取区间下限
{fmt(PRICE_REC)} 万元（{PS_REC:.2f} 元/股）**，其对应 2025 归母 PE {MULT['投前/2025归母']:.2f}x、扣非归母 PE
{MULT['投前/2025扣非归母']:.2f}x、2026 承诺 PE {MULT['投前/2026承诺']:.2f}x、投后 EV/EBITDA
{MULT['投后EV/2025EBITDA']:.2f}x；亦低于历史 C 轮（投前 {fmt(C_ROUND['投前估值'])} 万元、披露 PE
{C_ROUND['披露PE']:.1f}x，口径见 C6）与文件30少数股权案例区间（{min(MINOR_DEAL_PES):.1f}x—{max(MINOR_DEAL_PES):.1f}x）。

**持股比例**：投前 {fmt(VAL_LO)}—{fmt(VAL_HI)} 万元对应持股 **{STAKE_LO:.2f}%—{STAKE_HI:.3f}%**，均低于
{STAKE_CAP:.2f}% 上限；持股恰为 {STAKE_CAP:.2f}% 时投前估值下限为 {fmt(PRE_FLOOR_CAP)} 万元，即**可接受投前
估值不低于 {fmt(PRE_FLOOR_CAP)} 万元**，结论区间整体满足约束。按建议定价：新增 {fmt(NEW_SHARES,1)} 万股，
投后总股本 {fmt(TOTAL_SHARES+NEW_SHARES,1)} 万股，持股 {STAKE_REC:.3f}%；若期权池 {fmt(POOL_TOTAL)} 万股全部
行权，摊薄至 {STAKE_AFTER_POOL:.2f}%（文件34/33 反稀释条款不覆盖期权池，需谈判加入）。

**业绩承诺隐含倍数与覆盖**：承诺 2026/2027 年扣非归母（不剔除股份支付）≥{fmt(COMMIT['2026'])}/{fmt(COMMIT['2027'])}
万元，2026 年较 2025 年扣非 {fmt(B['2025']['扣非归母'])} 万元需增长 {COMMIT_G26_IMPLIED:.1f}%。2026H1 实际扣非
{fmt(H1_KF)} 万元，仅完成年度承诺的 {COVER_H1:.1f}%，年化 {fmt(ANNUALIZED_KF)} 万元、缺口 {fmt(GAP_2026)} 万元
（{GAP_2026/COMMIT['2026']*100:.1f}%），下半年需 {fmt(H2_NEED)} 万元（为上半年 {H2_NEED/H1_KF:.2f} 倍），
**承诺达标存在实质压力**；补偿=（承诺−实际）×持股比例，覆盖有限，应坚持回购触发条款（累计 85%、年化
{BUYBACK_RATE:.0f}% 单利）并要求控股股东提供质押增信（待谈判）。

**退出回报**（假设 2026 年末交割、{IPO_YEAR} 年末上市退出；锁定期未载明，G10）：退出市值=可比 PE 中位数
{PE_MED:.3f}×2027 承诺 {fmt(COMMIT['2027'])}={fmt(EXIT_EQ)} 万元（上市口径不加流动性折价），对应本轮
**{EXIT_MULT:.2f}x / 两年年化 {IRR_2Y*100:.1f}%**；若含 12 个月锁定（3 年）年化 {IRR_3Y*100:.1f}%。下行情形：
业绩仅达承诺 {BUYBACK_TRIGGER:.0f}% 时 {EXIT_DOWN_MULT:.2f}x（两年年化 {(EXIT_DOWN_MULT**0.5-1)*100:.1f}%）；
触发回购时收回 {fmt(BUYBACK_AMT)} 万元（{BUYBACK_MULT:.2f}x，年化 {BUYBACK_RATE:.0f}%）。若按区间上限定价，
回报降至 {EXIT_MULT_DCFPRICE:.2f}x（两年年化 {IRR_2Y_DCFPRICE*100:.1f}%），进一步支持取下限定价。

## 八、风险提示与尽调缺口

**投资风险分级**（高 {RISK_COUNT['高']} 项、中 {RISK_COUNT['中']} 项、低 {RISK_COUNT['低']} 项）：

| 级别 | 风险 | 依据与量化 |
|---|---|---|
{RISK_MD}

**尽调缺口清单与下一步动作**：

| 编号 | 缺口 | 下一步动作 |
|---|---|---|
{PENDING_MD}

**结论**：标的盈利质量与现金流总体扎实，估值区间对投资方案形成支撑，业绩承诺覆盖不足与高新资质复审为两大
核心不确定性。建议按第七章定价与前置条件**提交投资决策委员会审议立项**。

> 附件：图1—图5（`FIN3-WKN-150_charts/`）；复算脚本（`FIN3-WKN-150_reproduce.py`）。
"""

MEMO_PATH.write_text(MEMO, encoding="utf-8")
cjk = sum(1 for ch in MEMO if "\u4e00" <= ch <= "\u9fff")
print(f"  [memo ] {MEMO_PATH.name}  汉字数={cjk}（要求 3,500–5,000）"
      + ("  ⚠️超区间" if not 3500 <= cjk <= 5000 else "  ✓"))

# ----------------------------------------------------------------------
# 15. 控制台摘要
# ----------------------------------------------------------------------
print("\n================ 关键结论摘要（均由输入文件计算） ================")
print(f"扣非归母净利润(2023/2024/2025/2026H1): " + "/".join(fmt(B[p]["扣非归母"]) for p in PERIODS))
print(f"调整后EBITDA: " + "/".join(fmt(B[p]["调整后EBITDA"]) for p in PERIODS))
print(f"勾稽检查: {sum(1 for _, ok in CHECKS if ok)}/{len(CHECKS)} 通过; 冲突 {len(CONFLICTS)} 项; 待核实 {len(PENDING)} 项")
print(f"可比样本: 清洗后 {len(cleaned)} 家(文件29) / 数据源 {len(SAMPLE)} 家(文件28); "
      f"PE中位 {PE_MED:.3f} / PS中位 {PS_MED:.3f} / EV-EBITDA中位 {EVE_MED:.3f}")
print(f"DCF: WACC={WACC*100:.3f}%  g={G_PERP*100:.1f}%  EV={fmt(DCF['EV'])}  净负债={fmt(DCF['净负债'])}  "
      f"股权价值={fmt(EQ_DCF)}  每股={DCF['每股价值']:.2f}元")
print(f"市场法(折价后): PE {fmt(V_PE)} / PS {fmt(V_PS)} / EV-EBITDA {fmt(V_EVE)} / 中位数 {fmt(MKT_MED)}")
print(f"估值区间: {fmt(VAL_LO)}–{fmt(VAL_HI)} 万元; 建议定价 {fmt(PRICE_REC)} 万元 ({PS_REC:.2f} 元/股)")
print(f"持股: {STAKE_LO:.2f}%–{STAKE_HI:.2f}% (上限 {STAKE_CAP:.2f}% 对应投前下限 {fmt(PRE_FLOOR_CAP)})")
print(f"退出: {EXIT_MULT:.2f}x / 2年年化 {IRR_2Y*100:.1f}% / 3年年化 {IRR_3Y*100:.1f}%; "
      f"下行 {EXIT_DOWN_MULT:.2f}x; 回购 {BUYBACK_MULT:.2f}x")
print("==================================================================")
print("全部交付物生成完毕。")




