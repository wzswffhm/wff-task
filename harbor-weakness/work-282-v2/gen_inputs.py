#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 FIN3-WKN-152 v2 的 environment/input_files（IPO 定价复核 workspace，50 个输入文件）。

设计原则：
  * 全部数值确定性生成，年度合计与 SEC 摘录精确勾稽；
  * 数据按批次导出，冲突处均有唯一权威出处（Committee_Policy v3 / Source_Index 优先级）；
  * 输入文件本身不作质量标注，复核动作留给 agent。
"""
from __future__ import annotations

import csv
import os
import shutil
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "FIN3-WKN-152", "environment", "input_files")

HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(color="FFFFFF", bold=True)

# ------------------------------------------------------------------ 权威事实
REV22, REV23 = 666.701, 804.029
AD22, AD23 = 652.562, 788.782
OT22, OT23 = 14.139, 15.247
NL22, NL23 = -158.550, -90.824
AE22, AE23 = -108.393, -69.275
SBC22, SBC23 = 55.768, 49.086
RST22, RST23 = 0.0, 8.098
DA22, DA23 = 8.000, 13.702
FCF22, FCF23 = -100.254, -84.838
CASH22, CASH23 = 435.810, 401.176
MS22, MS23 = 830.734, 811.946
GROWTH = 0.22
M_LO, M_MID, M_HI = 4.0, 4.5, 5.0
DISC = 0.125
PRICE = 34.0
PRIMARY, SECONDARY, GS = 15.276527, 6.723473, 3.3
PRE_SH = 143.716563
FEE, FIXED = 0.05, 7.0
NTBV, DIL = 11.17, 21.33


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def wcsv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)


def sheet(ws, rows, widths=None, header=True):
    for r in rows:
        ws.append(r)
    if header:
        for c in ws[1]:
            c.fill, c.font = HDR_FILL, HDR_FONT
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    if widths:
        from openpyxl.utils import get_column_letter
        for i, wd in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = wd


def wbook(path, sheets):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb = Workbook()
    first = True
    for name, rows, widths in sheets:
        ws = wb.active if first else wb.create_sheet()
        ws.title = name
        sheet(ws, rows, widths)
        first = False
    wb.save(path)


# ------------------------------------------------------------------ 月度分解
MON23 = [60.100, 61.250, 63.400, 64.800, 66.100, 67.300,
         68.500, 69.200, 70.100, 71.400, 72.900, 68.979]
MON22 = [50.100, 50.800, 52.300, 53.600, 54.900, 55.700,
         56.400, 57.100, 57.900, 58.600, 59.300, 60.001]
assert abs(sum(MON23) - REV23) < 1e-9, sum(MON23)
assert abs(sum(MON22) - REV22) < 1e-9, sum(MON22)

GEO23 = [("United States", 620.500), ("International", 183.529)]
GEO22 = [("United States", 520.100), ("International", 146.601)]
assert abs(sum(v for _, v in GEO23) - REV23) < 1e-9
assert abs(sum(v for _, v in GEO22) - REV22) < 1e-9


def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)
    n = 0

    # ============================== 根 ==============================
    w(f"{OUT}/00_README.md", """# Reddit, Inc. IPO 定价复核 — 工作资料包（Materials Pack）

**复核时点（as-of）**：2024-03-20，定价委员会正式定价前。
**发行人**：Reddit, Inc.（SEC CIK 0001713445）。
**估值基准**：2024E Revenue；金额单位 USD mm，股份单位 mm shares，价格 USD/share。

本资料包为定价委员会复核工作底稿的资料集，按来源分为 7 个目录：

| 目录 | 内容 | 用途 |
|---|---|---|
| `committee/` | 委员会政策、发行条款、股本快照、委员会邮件 | **控制口径**（与其他材料冲突时以此为准） |
| `sec_filings/` | 截止日前 SEC 材料摘录（S-1/A、修订稿、8-K、附件摘要） | 历史财务与发行机制的权威来源 |
| `financials/` | 财务明细底表（月度收入、分部、SBC、重组、现金流桥、资产负债表） | 明细与年度数核对 |
| `comps/` | 两家承销商各自编制的可比公司表、历史倍数 | peer 倍数交叉验证 |
| `research/` | 卖方研究摘录、市场更新、行业基准 | 背景参考 |
| `internal/` | 内部工作稿、IR 草稿、数据字典、修订记录 | **含未经审计与已废弃材料** |
| `legacy/` | 上一版工作底稿及其说明 | 待复核对象 |

**信息集纪律**：仅可使用 2024-03-20 之前可获得的信息。最终发行价格、发行完成后的 SEC 文件、
上市后交易表现不得进入 Base case，也不得用于反推。

**来源优先级**：同一事实出现在多处时，按 `sec_filings/Source_Index.csv` 的 Priority 列取值；
Priority 相同时以 `committee/Committee_Policy_v3_20240320.xlsx` 指定的口径为准。
""")
    n += 1

    w(f"{OUT}/data_dictionary.md", """# 数据字典（Data Dictionary）

| 字段 / 文件 | 含义 | 单位 | 备注 |
|---|---|---|---|
| `fy` | 财政年度 | — | FY2022 / FY2023 |
| `month` | 自然月 | YYYY-MM | — |
| `revenue_usd_mm` | 收入 | USD mm | 见各表口径说明 |
| `Source_ID` | 来源编号 | — | 对应 `sec_filings/Source_Index.csv` |
| `NTBV/share` | 每股有形账面净值 | USD/share | 仅在假定发行价 $32.50 下测算 |
| `immediate dilution` | 即时稀释 | USD/share | 同上 |

> 各底表按不同批次导出并多次修订，同一序列可能混有来自不同来源、不同时点的记录。
> 取数时以 `sec_filings/Source_Index.csv` 的来源优先级与 SEC 摘录的年度数为准。
""")
    n += 1

    # ============================== committee ==============================
    wbook(f"{OUT}/committee/Committee_Policy_v3_20240320.xlsx", [
        ("Committee_Policy", [
            ["Policy_ID", "Section", "Committee convention", "Application"],
            ["CP-01", "Information set",
             "Base case 仅使用 2024-03-20 前可获得的信息。最终定价、发行完成后的 SEC 文件、"
             "上市后交易表现和其他后续结果不进入 Base。", "As-of discipline"],
            ["CP-02", "Source priority",
             "同一事实有多个来源时，按 Source_Index 的 Priority 升序取值（1 为最高）；"
             "内部工作稿、IR 草稿、未经审计 flash 与承销商各自编制的可比公司表均为**参考材料**，"
             "不得作为承销口径结论的取数来源。", "Conflict resolution"],
            ["CP-03", "QoE",
             "Management Adjusted EBITDA 作为起点；SBC 视为持续性经济成本，承销口径不保留该加回。",
             "Underwriting EBITDA"],
            ["CP-04", "QoE",
             "2023 restructuring 可视为非经常性，但已包含在 management Adjusted EBITDA 调整中，"
             "不再重复处理（不得二次加回）。", "No double count"],
            ["CP-05", "Valuation",
             "若 Underwriting EBITDA 仍为负，主估值采用 EV / 2024E Revenue；不得使用 EV/EBITDA。",
             "Primary method"],
            ["CP-06", "Forecast",
             "2024E Revenue = 2023A Revenue × (1 + 22%)。22% 为委员会内部预测假设，"
             "非 SEC 公开事实。", "Forward denominator"],
            ["CP-07", "Valuation",
             "Peer EV/NTM Revenue 区间以 Committee_Peer_Set 为准（4.0x–5.0x，中点 4.5x）；"
             "承销商各自编制的 comps 仅作参考，不改变区间端点。", "Pricing range"],
            ["CP-08", "Valuation",
             "Pre-money Equity = Enterprise Value + year-end cash + marketable securities。",
             "Net cash bridge"],
            ["CP-09", "Valuation",
             "对 peer-implied undiscounted equity value/share 统一应用 12.5% IPO execution discount。",
             "Execution discount"],
            ["CP-10", "Offering",
             "Base primary 15.276527m；secondary 6.723473m。Secondary 不形成公司募集资金，"
             "也不增加公司总股数。", "Primary / secondary"],
            ["CP-11", "Offering",
             "3.3m greenshoe 为承销商选择权。Base 不预设 exercise；另列 full-exercise 情景。",
             "Greenshoe"],
            ["CP-12", "Fees",
             "承销费按公司 primary gross proceeds 的 5% 计提；固定 company expenses 为 $7.0mm。"
             "Greenshoe 增量只扣 5% fee，不重复扣固定费用。", "Net proceeds"],
            ["CP-13", "Disclosure",
             "QoE 风险（承销口径 EBITDA 与 FCF 均为负）须在备忘录中明确披露。",
             "Disclosure"],
            ["CP-14", "Committee disposition",
             "若拟议价格位于委员会支持区间内、距 midpoint 不超过 $0.50/share，"
             "且发行结构不存在未解决的 hard error，则建议 Proceed。", "Proceed"],
            ["CP-15", "Committee disposition",
             "若价格仍在支持区间内但距 midpoint 超过 $0.50/share，建议向 midpoint 方向 Reprice；"
             "若超出支持区间或结构问题未解决，则建议 Defer。", "Reprice / Defer"],
        ], [10, 20, 96, 22]),
        ("Committee_Peer_Set", [
            ["Peer", "NTM EV/Revenue", "Profitability", "Committee Weight", "Notes"],
            ["Peer A", M_LO, "Positive EBITDA", 0.2, "Lower growth"],
            ["Peer B", 4.3, "Positive EBITDA", 0.2, "Mature platform"],
            ["Peer C", M_MID, "Near breakeven", 0.2, "Closest monetization profile"],
            ["Peer D", 4.8, "Positive EBITDA", 0.2, "Higher margin"],
            ["Peer E", M_HI, "Positive EBITDA", 0.2, "Higher growth"],
            ["Range (low / high)", f"{M_LO}x / {M_HI}x", "", "", "CP-07 控制区间端点"],
        ], [24, 16, 20, 18, 34]),
    ])
    n += 1

    wbook(f"{OUT}/committee/Committee_Policy_v2_20240305.xlsx", [
        ("Committee_Policy", [
            ["Policy_ID", "Section", "Committee convention", "Application"],
            ["CP-01", "Information set", "Base case 仅使用委员会会议日之前可获得的信息。", "As-of discipline"],
            ["CP-03", "QoE", "Management Adjusted EBITDA 作为起点；SBC 加回暂予保留，待审计确认。",
             "SUPERSEDED"],
            ["CP-07", "Valuation", "Peer EV/NTM Revenue 区间 3.5x–5.5x。", "SUPERSEDED"],
            ["CP-09", "Valuation", "IPO discount 暂定 10%。", "SUPERSEDED"],
            ["CP-12", "Fees", "承销费按全部发行股份（含 secondary）的 5% 计提。", "SUPERSEDED"],
        ], [10, 20, 70, 20]),
        ("Revision_Note", [
            ["Item", "Note"],
            ["版本", "v2（2024-03-05）"],
            ["状态", "**已被 v3（2024-03-20）取代**"],
            ["取代范围", "CP-03 SBC 处理、CP-07 peer 区间、CP-09 执行折扣、CP-12 费用计提基数"],
            ["处置", "复核一律以 Committee_Policy_v3_20240320.xlsx 为准；本文件仅供版本溯源。"],
        ], [16, 96]),
    ])
    n += 1

    wbook(f"{OUT}/committee/Offering_Terms_20240320.xlsx", [
        ("Offering_Terms", [
            ["Item", "Base Offering", "Full Greenshoe", "Unit", "Source_ID", "Notes"],
            ["Proposed Committee Price", PRICE, PRICE, "USD/share", "UW-01",
             "Internal working price; not an actual final price"],
            ["Primary shares offered", PRIMARY, 18.576527, "mm shares", "SEC-03",
             "Full exercise adds 3.3m primary shares"],
            ["Secondary shares offered", SECONDARY, SECONDARY, "mm shares", "SEC-03",
             "No company proceeds"],
            ["Greenshoe shares", 0, GS, "mm shares", "SEC-03", "Base excludes exercise"],
            ["Pre-money economic shares", PRE_SH, PRE_SH, "mm shares", "UW-01",
             "Committee cap-table snapshot"],
            ["Preliminary public filing range low", 31, 31, "USD/share", "SEC-03",
             "Execution cross-check only"],
            ["Preliminary public filing range high", 34, 34, "USD/share", "SEC-03",
             "Execution cross-check only"],
            ["Underwriting fee assumption", FEE, FEE, "% primary gross", "UW-01",
             "Applies to company primary economics"],
            ["Fixed company offering expenses", FIXED, FIXED, "USD mm", "UW-01",
             "Do not repeat on greenshoe increment"],
            ["Company receives secondary proceeds?", 0, 0, "0=No", "SEC-03", ""],
            ["Greenshoe treatment in Base", 0, 1, "0=exclude; 1=full exercise", "UW-01", ""],
            ["Decision price status", "Proposed / under review", "Proposed / under review", "Text",
             "UW-01", "Decision input, not future realized result"],
        ], [34, 16, 16, 24, 12, 44]),
    ])
    n += 1

    wbook(f"{OUT}/committee/Underwriting_Assumptions_20240320.xlsx", [
        ("Assumptions", [
            ["Assumption", "Value", "Unit", "Policy_ID", "Note"],
            ["2024E revenue growth", GROWTH, "%", "CP-06", "UW forecast assumption"],
            ["Peer low EV/Revenue", M_LO, "x", "CP-07", "Committee peer set"],
            ["Peer midpoint EV/Revenue", M_MID, "x", "CP-07", "Committee peer set"],
            ["Peer high EV/Revenue", M_HI, "x", "CP-07", "Committee peer set"],
            ["IPO discount to peer-implied equity", DISC, "%", "CP-09", "Execution discount"],
            ["SBC treatment", "Recurring economic cost", "Text", "CP-03",
             "Do NOT add back for underwriting EBITDA"],
            ["Restructuring treatment", "Non-recurring; allow addback", "Text", "CP-04",
             "Already reflected in management Adj EBITDA"],
            ["Valuation method", "EV / 2024E Revenue", "Text", "CP-05",
             "Because underwriting EBITDA remains negative"],
        ], [38, 24, 10, 12, 44]),
    ])
    n += 1

    ct = [
        ("Class A common stock", 40.000000, "SEC-09"),
        ("Class B common stock", 70.000000, "SEC-09"),
        ("Series A preferred (as-converted)", 15.000000, "SEC-09"),
        ("Series B preferred (as-converted)", 10.000000, "SEC-09"),
        ("RSUs vested and unsettled", 5.716563, "UW-01"),
        ("Options in the money", 3.000000, "UW-01"),
    ]
    tot = sum(v for _, v, _ in ct)
    assert abs(tot - PRE_SH) < 1e-9, tot
    wcsv(f"{OUT}/committee/cap_table_snapshot_20240318.csv",
         ["holder_class", "shares_mm", "Source_ID", "as_of", "note"],
         [[k, f"{v:.6f}", s, "2024-03-18", "pre-money economic shares"]
          for k, v, s in ct] + [["TOTAL_pre_money_economic_shares", f"{tot:.6f}", "UW-01",
                                 "2024-03-18", "committee cap-table snapshot"]])
    n += 1

    w(f"{OUT}/committee/committee_email_thread.txt", """From: Head of ECM
Sent: 2024-03-20 08:12
Subject: RE: Reddit pricing — final pre-committee checklist

1) 一律以 Committee_Policy v3（今天这版）为准。v2 里 SBC 保留加回、10% discount、
   费用按全部股份计提那几条都已作废，不要再引用。
2) Peer 区间就用 committee peer set 的 4.0x–5.0x。两家承销商各自那份 comps 只是
   交叉验证用，不要拿其中一份去改区间端点。
3) Management 周一发的 flash（3/19）是 IR 口径的初稿，数字还没过审，
   不要进 QoE 结论，也不要进估值分母。
4) 12.5% 是执行折扣，作用在 peer-implied equity value/share 上，不是乘在收入或 EV 上。
5) SBC 是持续性经济成本，承销口径不保留加回；restructuring 已经在 management 的
   调整里了，不要再动一次。
6) memo 里必须把承销口径 EBITDA 和 FCF 都是负数这件事写清楚。
7) 3/20 之后的东西我们一概不知道，也不要让底稿里出现。

—— Head of ECM

From: Deal Captain
Sent: 2024-03-19 22:40
Subject: RE: IR flash

IR flash 收到了，先放着。周一那份是 preliminary，别混进委员会材料。
明细底表里 12 月那条是 preliminary 的残留，审计版在 S-1/A 里，用审计版。

From: IR
Sent: 2024-03-19 19:05
Subject: Draft talking points

草稿里几个数还是早上的版本，等审计版出来再定。不要外发。
""")
    n += 1

    # ============================== sec_filings ==============================
    wcsv(f"{OUT}/sec_filings/Source_Index.csv",
         ["Source_ID", "Document", "As-of", "Fact", "URL", "Priority", "Use"],
         [
             ["SEC-01", "Reddit S-1/A (preliminary prospectus)", "2024-03-11",
              "2022/2023 financials; cash; marketable securities; management non-GAAP metrics",
              "https://www.sec.gov/Archives/edgar/data/1713445/000162828024010137/reddit-sx1a1.htm",
              1, "Historical financials / QoE"],
             ["SEC-02", "Reddit S-1/A (preliminary prospectus)", "2024-03-11",
              "Preliminary NTBV and dilution cross-check at assumed $32.50",
              "https://www.sec.gov/Archives/edgar/data/1713445/000162828024010137/reddit-sx1a1.htm",
              1, "Dilution cross-check"],
             ["SEC-03", "Reddit S-1/A / preliminary prospectus", "2024-03-11",
              "15.276527m primary; 6.723473m secondary; 3.3m over-allotment option; "
              "public price range $31-$34",
              "https://www.sec.gov/Archives/edgar/data/1713445/000162828024010137/reddit-sx1a1.htm",
              1, "Offering mechanics"],
             ["SEC-04", "Reddit S-1/A Amendment No. 2", "2024-03-15",
              "Latest pre-cutoff filing available to committee",
              "https://www.sec.gov/Archives/edgar/data/1713445/000162828024011448/reddit-sx1a2.htm",
              1, "Cut-off validation"],
             ["SEC-05", "Reddit S-1/A Amendment No. 2", "2024-03-15",
              "Revenue by geography (US / International)",
              "https://www.sec.gov/Archives/edgar/data/1713445/000162828024011448/reddit-sx1a2.htm",
              1, "Revenue cross-check"],
             ["SEC-09", "Reddit S-1/A (preliminary prospectus)", "2024-03-11",
              "Capitalization table at filing",
              "https://www.sec.gov/Archives/edgar/data/1713445/000162828024010137/reddit-sx1a1.htm",
              1, "Cap table"],
             ["SEC-10", "Reddit S-1/A (preliminary prospectus)", "2024-03-11",
              "Underwriting agreement summary: over-allotment option; fee basis",
              "https://www.sec.gov/Archives/edgar/data/1713445/000162828024010137/reddit-sx1a1.htm",
              1, "Fee basis"],
             ["INT-01", "Management flash (IR working draft)", "2024-03-19",
              "Unreviewed management flash — superseded by SEC-01",
              "internal", 9, "REFERENCE ONLY — do not use for conclusions"],
             ["INT-02", "Legacy workpaper Candidate_Model v0", "2024-03-18",
              "Prior-round working draft",
              "internal", 9, "OBJECT OF REVIEW"],
             ["BANK-A", "Underwriter A comparable company analysis", "2024-03-15",
              "Underwriter's own comp set",
              "internal", 8, "Cross-check only (CP-07)"],
             ["BANK-B", "Underwriter B comparable company analysis", "2024-03-18",
              "Underwriter's own comp set",
              "internal", 8, "Cross-check only (CP-07)"],
         ])
    n += 1

    wbook(f"{OUT}/sec_filings/SEC-01_financials_extract.xlsx", [
        ("Public_Financials", [
            ["Metric", "2022A", "2023A", "Unit", "Source_ID", "Notes"],
            ["Revenue", REV22, REV23, "USD mm", "SEC-01", "Pre-pricing filing"],
            ["Advertising revenue", AD22, AD23, "USD mm", "SEC-01", ""],
            ["Other revenue", OT22, OT23, "USD mm", "SEC-01", ""],
            ["Net income (loss)", NL22, NL23, "USD mm", "SEC-01", ""],
            ["Adjusted EBITDA", AE22, AE23, "USD mm", "SEC-01", "Management non-GAAP metric"],
            ["Stock-based compensation & related taxes", SBC22, SBC23, "USD mm", "SEC-01", ""],
            ["Restructuring costs", RST22, RST23, "USD mm", "SEC-01", ""],
            ["Depreciation & amortization", DA22, DA23, "USD mm", "SEC-01", ""],
            ["Free Cash Flow", FCF22, FCF23, "USD mm", "SEC-01", ""],
            ["Cash & cash equivalents", CASH22, CASH23, "USD mm", "SEC-01", ""],
            ["Marketable securities", MS22, MS23, "USD mm", "SEC-01", ""],
        ], [42, 14, 14, 12, 12, 34]),
        ("Notes", [
            ["Item", "Note"],
            ["Basis", "Numbers as presented in the preliminary prospectus (S-1/A) dated 2024-03-11."],
            ["Non-GAAP", "Adjusted EBITDA is a management-defined non-GAAP measure."],
            ["FCF", "Free cash flow as defined by the company (operating cash flow less capex)."],
            ["Currency", "All amounts in USD millions unless stated otherwise."],
        ], [18, 96]),
    ])
    n += 1

    wbook(f"{OUT}/sec_filings/SEC-02_dilution_crosscheck.xlsx", [
        ("Dilution_Crosscheck", [
            ["Item", "Value", "Unit", "Assumed price", "Source_ID"],
            ["Preliminary NTBV/share", NTBV, "USD/share", 32.50, "SEC-02"],
            ["Preliminary immediate dilution per share", DIL, "USD/share", 32.50, "SEC-02"],
        ], [46, 14, 14, 16, 12]),
    ])
    n += 1

    wbook(f"{OUT}/sec_filings/SEC-03_offering_terms.xlsx", [
        ("Offering_Terms", [
            ["Item", "Value", "Unit", "Source_ID", "Notes"],
            ["Primary shares offered (base)", PRIMARY, "mm shares", "SEC-03", ""],
            ["Secondary shares offered (base)", SECONDARY, "mm shares", "SEC-03",
             "Selling stockholders only"],
            ["Over-allotment option", GS, "mm shares", "SEC-03",
             "Exercisable by underwriters; not included in base"],
            ["Preliminary public filing range low", 31, "USD/share", "SEC-03", ""],
            ["Preliminary public filing range high", 34, "USD/share", "SEC-03", ""],
        ], [40, 14, 14, 12, 40]),
    ])
    n += 1

    w(f"{OUT}/sec_filings/SEC-04_s1a_a2_20240315_summary.md", """# SEC-04 · S-1/A Amendment No. 2 — Summary Extract

**Filing date**: 2024-03-15（截止日前可获得的最后一版注册说明书修订稿）
**用途**: cut-off validation（用于确认信息集截点，不改变 SEC-01 的历史财务数值）

## 本次修订涉及事项

1. 更新了风险因素章节的表述，未修改 2022/2023 历史财务数据。
2. 补充了按地区（United States / International）划分的收入构成，见 `SEC-05_revenue_by_geo.csv`。
3. 明确 over-allotment option 为 3.3m shares，由承销商选择行使，**不构成 base offering**。
4. 未披露任何定价结果；定价区间仍为 $31–$34（preliminary public filing range）。

## 委员会要点

* 截止日校验：本修订稿日期 2024-03-15 早于复核时点 2024-03-20，属可用信息集。
* 历史财务数值仍以 SEC-01（2024-03-11 S-1/A）所载为准；两份文件在 2022/2023 年度数上一致。
""")
    n += 1

    wcsv(f"{OUT}/sec_filings/SEC-05_revenue_by_geo.csv",
         ["fy", "geography", "revenue_usd_mm", "Source_ID"],
         [["FY2022", g, f"{v:.3f}", "SEC-05"] for g, v in GEO22] +
         [["FY2023", g, f"{v:.3f}", "SEC-05"] for g, v in GEO23])
    n += 1

    w(f"{OUT}/sec_filings/SEC-06_risk_factors_extract.md", """# SEC-06 · Risk Factors — Extract

* 公司自成立以来持续经营亏损，2022 年与 2023 年均为净亏损；无法保证未来能够实现或维持盈利。
* 公司的非 GAAP 财务指标（如 Adjusted EBITDA）由管理层定义，与其他公司口径可能不可比。
* 若股权激励的规模或价格发生变动，将对经营业绩产生重大影响。
* 本次发行存在 primary 与 secondary 两部分；**出售股东出售股份所得款项归出售股东，公司不取得该部分款项**。
* 承销商持有超额配售选择权（over-allotment option），其行使将增加发行在外股份数量。
""")
    n += 1

    w(f"{OUT}/sec_filings/SEC-07_mda_extract.md", """# SEC-07 · MD&A — Extract

## 收入

2023 年收入较 2022 年增长，主要由广告业务驱动。收入按地区划分见 `SEC-05_revenue_by_geo.csv`。

## 股权激励

公司以股权激励作为主要薪酬工具，2022 年与 2023 年均确认了金额重大的股权激励及相关税费。
管理层在非 GAAP 调整中将该项加回；**该加回为管理层口径定义，不代表该项成本未发生**。

## 重组

2023 年公司实施了人员与办公场所重组，确认了相关费用。管理层在非 GAAP 调整中已考虑该等费用的
影响，因此**不应对同一笔费用再次进行调整或加回**。

## 流动性与资本资源

2023 年末公司持有现金及现金等价物与有价证券。**有价证券属于公司可变现金融资产**，
在评估股权价值时应与现金一并考虑。
""")
    n += 1

    w(f"{OUT}/sec_filings/SEC-08_8k_20240318.md", """# SEC-08 · Form 8-K (2024-03-18) — Extract

* 公司公告了与本次发行相关的治理安排变更。
* 未披露任何与 2022/2023 历史财务数据相关的修订。
* 未披露定价结果。

> 注：本 8-K 日期为 2024-03-18，早于复核时点，属可用信息集；但其中**不含财务数据**。
""")
    n += 1

    wcsv(f"{OUT}/sec_filings/SEC-09_capitalization.csv",
         ["class", "shares_mm", "as_of", "Source_ID"],
         [[k.replace(" (as-converted)", ""), f"{v:.6f}", "2024-03-11", "SEC-09"] for k, v, _ in ct])
    n += 1

    w(f"{OUT}/sec_filings/SEC-10_underwriting_agreement_summary.md", """# SEC-10 · Underwriting Agreement — Summary

* **Over-allotment option**: 3.3m shares，由承销商在发行完成后按约定窗口选择行使，
  不构成 base offering 的组成部分。
* **Underwriting discount**: 按**公司本次发行所发售股份（primary）**的总募集金额计提；
  secondary 股份由出售股东承担相应费用安排，**不构成公司的手续费基数**。
* **Company expenses**: 公司承担与本次发行相关的固定费用。
* 承销商可选择全额或部分行使超额配售选择权；行使部分的费用按同一费率计提，
  不产生额外的固定费用。
""")
    n += 1

    w(f"{OUT}/sec_filings/SEC-11_lockup_summary.md", """# SEC-11 · Lock-up Arrangements — Summary

* 董事、高管及主要股东适用自发行定价日起的锁定期安排。
* 锁定期安排**不改变 base offering 的股份数量**，也不改变 primary 与 secondary 的划分。
* 锁定期安排的例外情形仅涉及少量股份，对本次定价复核的股份桥不构成影响。
""")
    n += 1

    w(f"{OUT}/sec_filings/SEC-12_use_of_proceeds.md", """# SEC-12 · Use of Proceeds — Extract

公司预计将本次发行**primary 股份**所得净额用于一般公司用途，包括营运资金、潜在收购与研发投入。
**公司不会取得 secondary 股份出售所得款项**；该等款项归属出售股东。
""")
    n += 1

    w(f"{OUT}/sec_filings/SEC-13_non_gaap_reconciliation.md", """# SEC-13 · Non-GAAP Reconciliation — Extract

公司披露的非 GAAP 指标以净亏损为起点，逐项调整股权激励及相关税费、重组费用、
折旧与摊销等项目后得到 Adjusted EBITDA。

> 该表为**管理层口径**的调节过程。承销口径是否保留其中某项加回，
> 由 `committee/Committee_Policy_v3_20240320.xlsx` 决定，**不沿用管理层口径**。
""")
    n += 1

    # ============================== financials ==============================
    # 月度收入明细：同一序列多批次来源并存，不作质量标注
    rows = []
    for i, v in enumerate(MON22, 1):
        rows.append(["FY2022", f"2022-{i:02d}", f"{v:.3f}", "SEC-01"])
    rows.append(["FY2022", "2022-08", f"{MON22[7]:.3f}", "SEC-01"])
    for i, v in enumerate(MON23, 1):
        rows.append(["FY2023", f"2023-{i:02d}", f"{v:.3f}", "SEC-01"])
    rows.append(["FY2023", "2023-12", "66.500", "INT-01"])
    wcsv(f"{OUT}/financials/monthly_revenue_2022_2023.csv",
         ["fy", "month", "revenue_usd_mm", "Source_ID"], rows)
    n += 1

    # 分部收入明细
    wcsv(f"{OUT}/financials/revenue_by_segment_2022_2023.csv",
         ["fy", "segment", "revenue_usd_mm", "Source_ID"],
         [["FY2022", "Advertising", f"{AD22:.3f}", "SEC-01"],
          ["FY2022", "Other", f"{OT22:.3f}", "SEC-01"],
          ["FY2023", "Advertising", f"{AD23:.3f}", "SEC-01"],
          ["FY2023", "Other", "152.470", "SEC-01"]])
    n += 1

    wcsv(f"{OUT}/financials/revenue_quarterly.csv",
         ["fy", "quarter", "revenue_usd_mm", "Source_ID"],
         [["FY2023", "Q1", f"{sum(MON23[:3]):.3f}", "SEC-01"],
          ["FY2023", "Q2", f"{sum(MON23[3:6]):.3f}", "SEC-01"],
          ["FY2023", "Q3", f"{sum(MON23[6:9]):.3f}", "SEC-01"],
          ["FY2023", "Q4", f"{sum(MON23[9:]):.3f}", "SEC-01"]])
    n += 1

    sbc23 = [("RSU settlement", 38.500), ("Stock option exercises", 5.200),
             ("Employee stock purchase plan", 1.900), ("Payroll taxes on equity awards", 3.486)]
    sbc22 = [("RSU settlement", 42.000), ("Stock option exercises", 6.500),
             ("Employee stock purchase plan", 1.800), ("Payroll taxes on equity awards", 5.468)]
    assert abs(sum(v for _, v in sbc23) - SBC23) < 1e-9
    assert abs(sum(v for _, v in sbc22) - SBC22) < 1e-9
    wcsv(f"{OUT}/financials/sbc_detail_2022_2023.csv",
         ["fy", "component", "amount_usd_mm", "Source_ID"],
         [["FY2022", k, f"{v:.3f}", "SEC-01"] for k, v in sbc22] +
         [["FY2023", k, f"{v:.3f}", "SEC-01"] for k, v in sbc23] +
         [["FY2023", "TOTAL", "49.680", "SEC-01"]])
    n += 1

    rst = [("Workforce reduction severance", 5.998), ("Office consolidation", 1.400),
           ("Other exit costs", 0.700)]
    assert abs(sum(v for _, v in rst) - RST23) < 1e-9
    wcsv(f"{OUT}/financials/restructuring_detail_2023.csv",
         ["fy", "component", "amount_usd_mm", "Source_ID", "note"],
         [["FY2023", k, f"{v:.3f}", "SEC-01", ""] for k, v in rst] +
         [["FY2023", "TOTAL", f"{RST23:.3f}", "SEC-01",
           "already reflected in management Adjusted EBITDA adjustments"]])
    n += 1

    wcsv(f"{OUT}/financials/fcf_bridge_2023.csv",
         ["line_item", "amount_usd_mm", "Source_ID", "note"],
         [["Net cash used in operating activities", "-52.026", "SEC-01", ""],
          ["Purchases of property and equipment", "-32.812", "SEC-01",
           "presented as capex outflow"],
          ["Free cash flow", f"{FCF23:.3f}", "SEC-01", "operating cash flow less capex"]])
    n += 1

    wcsv(f"{OUT}/financials/balance_sheet_summary_2022_2023.csv",
         ["line_item", "FY2022", "FY2023", "unit", "Source_ID"],
         [["Cash & cash equivalents", f"{CASH22:.3f}", f"{CASH23:.3f}", "USD mm", "SEC-01"],
          ["Marketable securities", f"{MS22:.3f}", f"{MS23:.3f}", "USD mm", "SEC-01"],
          ["Total cash, cash equivalents and marketable securities",
           f"{CASH22 + MS22:.3f}", f"{CASH23 + MS23:.3f}", "USD mm", "SEC-01"]])
    n += 1

    wcsv(f"{OUT}/financials/opex_summary_2022_2023.csv",
         ["line_item", "FY2022", "FY2023", "unit", "Source_ID"],
         [["Cost of revenue", "149.000", "119.900", "USD mm", "SEC-01"],
          ["Research and development", "327.700", "438.400", "USD mm", "SEC-01"],
          ["Sales and marketing", "219.100", "196.300", "USD mm", "SEC-01"],
          ["General and administrative", "147.300", "158.900", "USD mm", "SEC-01"],
          ["Total costs and operating expenses", "843.100", "913.500", "USD mm", "SEC-01"]])
    n += 1

    wcsv(f"{OUT}/financials/income_statement_2022_2023.csv",
         ["line_item", "FY2022", "FY2023", "unit", "Source_ID"],
         [["Revenue", f"{REV22:.3f}", f"{REV23:.3f}", "USD mm", "SEC-01"],
          ["Cost of revenue", "-149.000", "-119.900", "USD mm", "SEC-01"],
          ["Research and development", "-327.700", "-438.400", "USD mm", "SEC-01"],
          ["Sales and marketing", "-219.100", "-196.300", "USD mm", "SEC-01"],
          ["General and administrative", "-147.300", "-158.900", "USD mm", "SEC-01"],
          ["Total costs and operating expenses", "-843.100", "-913.500", "USD mm", "SEC-01"],
          ["Other income, net", "17.849", "18.647", "USD mm", "SEC-01"],
          ["Net income (loss)", f"{NL22:.3f}", f"{NL23:.3f}", "USD mm", "SEC-01"]])
    n += 1

    wcsv(f"{OUT}/financials/cash_flow_statement_2023.csv",
         ["line_item", "FY2023", "unit", "Source_ID"],
         [["Net cash used in operating activities", "-52.026", "USD mm", "SEC-01"],
          ["Net cash used in investing activities", "-45.100", "USD mm", "SEC-01"],
          ["Net cash provided by financing activities", "62.492", "USD mm", "SEC-01"],
          ["Net change in cash and cash equivalents", "-34.634", "USD mm", "SEC-01"],
          ["Cash & cash equivalents at beginning of period", f"{CASH22:.3f}", "USD mm", "SEC-01"],
          ["Cash & cash equivalents at end of period", f"{CASH23:.3f}", "USD mm", "SEC-01"]])
    n += 1

    wcsv(f"{OUT}/financials/deferred_revenue_and_contracts.csv",
         ["line_item", "FY2022", "FY2023", "unit", "Source_ID"],
         [["Deferred revenue", "12.400", "15.100", "USD mm", "SEC-01"],
          ["Remaining performance obligations", "98.200", "121.500", "USD mm", "SEC-01"]])
    n += 1

    wcsv(f"{OUT}/financials/stockholders_equity_summary.csv",
         ["line_item", "FY2022", "FY2023", "unit", "Source_ID"],
         [["Total stockholders' equity", "-412.300", "-498.700", "USD mm", "SEC-01"],
          ["Accumulated deficit", "-1,208.400", "-1,299.224", "USD mm", "SEC-01"]])
    n += 1

    wcsv(f"{OUT}/financials/headcount_summary.csv",
         ["period", "headcount", "note"],
         [["2022-12-31", 2013, ""], ["2023-06-30", 2061, "pre-restructuring"],
          ["2023-12-31", 1894, "post-restructuring"]])
    n += 1

    wcsv(f"{OUT}/financials/dau_arpu_metrics.csv",
         ["period", "daily_active_uniques_mm", "arpu_usd", "Source_ID"],
         [["FY2022", 100.0, 6.67, "SEC-01"], ["FY2023", 108.5, 7.41, "SEC-01"]])
    n += 1

    # ============================== comps ==============================
    wcsv(f"{OUT}/comps/underwriter_A_comps_20240315.csv",
         ["peer", "ntm_ev_revenue", "profitability", "note"],
         [["Peer A", "4.0", "Positive EBITDA", "Cross-check only"],
          ["Peer B", "4.3", "Positive EBITDA", ""],
          ["Peer C", "4.5", "Near breakeven", ""],
          ["Peer D", "4.8", "Positive EBITDA", ""],
          ["Peer E", "5.0", "Positive EBITDA", ""]])
    n += 1

    wcsv(f"{OUT}/comps/underwriter_B_comps_20240318.csv",
         ["peer", "ntm_ev_revenue", "profitability", "note"],
         [["Comparable 1", "4.2", "Positive EBITDA", "Underwriter B screen"],
          ["Comparable 2", "4.4", "Positive EBITDA", "Underwriter B screen"],
          ["Comparable 3", "4.6", "Near breakeven", "Underwriter B screen"],
          ["Comparable 4", "4.9", "Positive EBITDA", "Underwriter B screen"],
          ["Comparable 5", "5.1", "Positive EBITDA", "Underwriter B screen"]])
    n += 1

    wcsv(f"{OUT}/comps/peer_multiples_history.csv",
         ["quarter", "median_ntm_ev_revenue", "note"],
         [["2023Q1", "3.6", ""], ["2023Q2", "3.9", ""], ["2023Q3", "4.1", ""],
          ["2023Q4", "4.3", ""], ["2024Q1", "4.4", "pre-pricing"]])
    n += 1

    # ============================== research ==============================
    w(f"{OUT}/research/sellside_note_20240312.md", """# Sell-side Note Extract — Digital Advertising Platforms (2024-03-12)

* 行业估值中枢在 4.0x–5.0x NTM EV/Revenue 区间，个股差异主要由增速与利润率决定。
* 部分平台公司 EBITDA 尚未转正，卖方普遍采用 EV/Revenue 而非 EV/EBITDA 进行相对估值。
* 本摘录为第三方观点，**不构成委员会口径**；peer 区间仍以 committee peer set 为准。
""")
    n += 1

    w(f"{OUT}/research/ipo_market_update_20240318.md", """# IPO Market Update (2024-03-18)

* 本季度科技类发行人定价普遍较 peer 隐含价值存在折让，折让幅度视发行规模与市场情绪而定。
* 委员会对本次发行采用的执行折扣为内部假设，**不引用本文件中的任何市场折让比例**。
* 本文件不含发行人财务数据。
""")
    n += 1

    w(f"{OUT}/research/sector_benchmark.md", """# Sector Benchmark Extract

| 指标 | 行业中位 | 说明 |
|---|---|---|
| NTM EV/Revenue | 4.4x | 样本为上市数字广告平台 |
| Revenue growth (YoY) | 18% | 行业中位 |

> 行业基准仅作背景；本次 2024E 增长率假设由委员会指定。
""")
    n += 1

    w(f"{OUT}/research/analyst_qoe_commentary.md", """# Analyst Commentary — Quality of Earnings

* 对以股权激励为主要薪酬工具的发行人，卖方分析通常会将股权激励视为**持续性成本**，
  在评估可持续盈利能力时不作加回。
* 重组费用一般被视为非经常性项目，但若管理层在其非 GAAP 指标中已作调整，
  再次调整会导致重复计算。
""")
    n += 1

    # ============================== internal（干扰 / 参考） ==============================
    wcsv(f"{OUT}/internal/management_flash_20240319.csv",
         ["metric", "FY2023_value", "unit", "note"],
         [["Revenue", "806.200", "USD mm", "IR working draft"],
          ["Adjusted EBITDA", "-66.100", "USD mm", "IR working draft"],
          ["Stock-based compensation & related taxes", "47.300", "USD mm",
           "IR working draft"],
          ["Free Cash Flow", "-82.400", "USD mm", "IR working draft"]])
    n += 1

    w(f"{OUT}/internal/ir_talking_points_draft.txt", """IR TALKING POINTS (DRAFT — NOT FOR COMMITTEE)

这些数字取自周一早上 IR 内部初稿，尚未经审计与财务复核，请勿用于委员会材料。

- 收入：806.2mm（初稿）
- Adjusted EBITDA：-66.1mm（初稿）
- SBC：47.3mm（初稿）

最终口径以注册说明书所载数据为准。
""")
    n += 1

    wcsv(f"{OUT}/internal/data_revision_log.csv",
         ["date", "artifact", "change", "disposition"],
         [["2024-03-16", "financials/monthly_revenue_2022_2023.csv",
           "re-exported from legacy workpaper", "logged"],
          ["2024-03-19", "financials/revenue_by_segment_2022_2023.csv",
           "segment extract refreshed", "logged"],
          ["2024-03-20", "committee/Committee_Policy",
           "v2 superseded by v3", "v3 is controlling"]])
    n += 1

    w(f"{OUT}/internal/legacy_workpaper_notes.md", """# Legacy Workpaper Notes（上一版底稿说明）

上一版底稿 `legacy/Candidate_Model_v0.xlsx` 存在下列已知处理，**不应默认正确**：

1. 以管理层 Adjusted EBITDA 直接作为盈利质量结论。
2. 以 2023 年收入作为估值分母。
3. 净现金桥仅计入现金，遗漏有价证券。
4. 将全部发行股份视为 primary。
5. 将 greenshoe 预设计入 Base。
6. 承销费按 primary + secondary 全部股份计提。
7. 将 secondary 股份计入发行后总股数。
8. 将 secondary 所得款项计入公司现金。
9. 稀释指标分子分母口径不一致。
10. 定价建议主要依据 peer high case 上调。
11. 模型内存在未解析的引用错误单元格，导致部分联动失效。

复核时应逐条判断上述处理是否成立，并在模型中记录所发现的问题与正确处理。
""")
    n += 1

    w(f"{OUT}/internal/prior_committee_deck_extract.md", """# Prior Committee Deck Extract（上一次会议材料摘录）

* 上次会议讨论了发行规模区间与投资者反馈，未形成定价结论。
* 上次会议采用的政策版本为 v2，该版本关于 SBC、peer 区间、执行折扣与费用基数的条款
  已被 v3 取代。
* 本次复核须以 v3 为准。
""")
    n += 1

    # ============================== legacy ==============================
    wb = Workbook()
    ws = wb.active
    ws.title = "Candidate_Model"
    sheet(ws, [
        ["Workstream", "Legacy treatment", "Review point", "Status"],
        ["Profitability", f"Uses management Adjusted EBITDA {AE23:.3f}",
         "SBC addback needs underwriting adjustment", "Review"],
        ["Valuation", "Applies 4.5x directly to 2023 revenue",
         "Update denominator to 2024E and apply IPO discount", "Review"],
        ["Cash", "Excludes marketable securities", "Net cash bridge is incomplete", "Review"],
        ["Primary/Secondary", "Treats all 22.0m base shares as primary",
         "Company proceeds are overstated", "Review"],
        ["Greenshoe", "Includes 3.3m shares in Base", "Option should be separated from Base",
         "Review"],
        ["Underwriting fee", "Applies fee to primary + secondary",
         "Fee base does not match company economics", "Review"],
        ["Post-money shares", "Adds secondary shares to share count",
         "Secondary is a transfer, not a new issuance", "Review"],
        ["Proceeds", "Adds secondary proceeds to company cash", "Wrong beneficiary", "Review"],
        ["Dilution", "Uses post-money equity / pre-money shares",
         "Numerator and denominator are inconsistent", "Review"],
        ["Recommendation", "Moves above $34 based mainly on the peer high case",
         "Does not reflect Committee pricing guardrails or QoE", "Review"],
    ], [22, 52, 56, 12])
    ws2 = wb.create_sheet()
    ws2.title = "Broken_Links"
    sheet(ws2, [
        ["Cell", "Formula", "Value"],
        ["Valuation!C7", "=#REF!*D7", "#REF!"],
        ["QoE!D9", "=#REF!+D8", "#REF!"],
        ["Offering!C12", "=#REF!-$D$4", "#REF!"],
    ], [16, 24, 12])
    os.makedirs(f"{OUT}/legacy", exist_ok=True)
    wb.save(f"{OUT}/legacy/Candidate_Model_v0.xlsx")
    n += 1

    w(f"{OUT}/legacy/Candidate_Model_readme.md", """# legacy/Candidate_Model_v0.xlsx — 说明

本文件为上一轮的工作底稿，含 2 个工作表：

* `Candidate_Model`：11 条历史处理及其 review point（与 `internal/legacy_workpaper_notes.md` 对应）。
* `Broken_Links`：若干 `#REF!` 单元格，**说明该底稿的部分联动公式已失效**；
  不得直接沿用其计算结果，须重新计算。

本底稿中的任何数值均不作为结论依据。
""")
    n += 1

    wcsv(f"{OUT}/legacy/legacy_assumptions_export.csv",
         ["assumption", "legacy_value", "note"],
         [["valuation_denominator", "2023A revenue", "legacy; superseded"],
          ["discount_applied", "0.0", "legacy; superseded"],
          ["fee_base", "primary+secondary", "legacy; superseded"],
          ["greenshoe_in_base", "1", "legacy; superseded"]])
    n += 1

    # ============================== 补充材料 ==============================
    w(f"{OUT}/committee/board_minutes_extract_20240319.md", """# Board Minutes Extract — 2024-03-19

* 董事会确认本次发行结构为 primary + secondary 两部分，over-allotment option 由承销商选择行使。
* 董事会授权管理层在委员会支持的价格区间内推进定价；**未授权任何高于区间上限的定价**。
* 董事会要求 QoE 相关风险在委员会材料中如实披露。
* 本纪要**不含**任何历史财务数据或预测数字。
""")
    n += 1

    wcsv(f"{OUT}/committee/committee_attendance.csv",
         ["role", "attendee", "present"],
         [["Chair", "Head of ECM", "yes"], ["Member", "Deal Captain", "yes"],
          ["Member", "Research", "yes"], ["Member", "Legal", "yes"],
          ["Secretary", "Syndicate", "yes"]])
    n += 1

    w(f"{OUT}/sec_filings/SEC-14_auditor_review_note.md", """# SEC-14 · Auditor Review Note — Extract

* 注册说明书所载 2022 与 2023 年度财务数据已经审计。
* 管理层的非 GAAP 指标（Adjusted EBITDA）**不在审计意见覆盖范围内**。
* 本说明用于确认 SEC-01 数据的可用性；**不提供任何新的财务数值**。
""")
    n += 1

    w(f"{OUT}/sec_filings/SEC-15_related_party_and_voting.md", """# SEC-15 · Related Party and Voting Structure — Extract

* 公司采用双重股权结构，Class B 普通股每股享有更高投票权。
* 双重股权结构**不影响 primary 与 secondary 的股份划分**，也不改变发行后总股数的计算方式。
* 本次发行不涉及关联方认购安排。
""")
    n += 1

    wcsv(f"{OUT}/sec_filings/SEC-16_share_count_history.csv",
         ["as_of", "shares_outstanding_mm", "Source_ID", "note"],
         [["2022-12-31", "118.400000", "SEC-01", "actual"],
          ["2023-12-31", "138.900000", "SEC-01", "actual"],
          ["2024-03-18", f"{PRE_SH:.6f}", "UW-01", "committee cap-table snapshot (economic)"],
          ["2024-03-18", "141.200000", "SEC-09", "registered shares, excludes unsettled RSUs"]])
    n += 1

    wcsv(f"{OUT}/comps/peer_financials_summary.csv",
         ["peer", "ntm_revenue_usd_mm", "ebitda_margin", "revenue_growth", "source"],
         [["Peer A", "1,240", "12%", "14%", "Underwriter A"],
          ["Peer B", "2,880", "22%", "9%", "Underwriter A"],
          ["Peer C", "1,650", "1%", "26%", "Underwriter A"],
          ["Peer D", "3,410", "28%", "11%", "Underwriter A"],
          ["Peer E", "980", "16%", "31%", "Underwriter A"]])
    n += 1

    w(f"{OUT}/research/digital_ad_market_sizing.md", """# Digital Advertising Market Sizing — Extract

* 全球数字广告支出中期维持中个位数至低双位数增长。
* 本文件为行业宏观资料，**不含发行人财务数据**，亦不构成对发行人未来收入的预测。
""")
    n += 1

    w(f"{OUT}/internal/diligence_checklist.md", """# 复核清单（工作稿）

- [ ] 确认信息集截止日与来源优先级
- [ ] 明细底表与年度数勾稽
- [ ] 承销口径盈利质量还原
- [ ] 估值分母与方法选择
- [ ] 净现金桥完整性
- [ ] 发行结构（primary / secondary / greenshoe）
- [ ] 费用与净募集
- [ ] 股本桥与稀释
- [ ] 各模块勾稽一致性
- [ ] 定价处置建议与 QoE 披露

> 本清单为提示性工作稿，**不构成对材料的补充说明**。
""")
    n += 1

    q7 = os.path.join(HERE, "..", "work-282-reddit-ipo", "Q7_题目.xlsx")
    if os.path.isfile(q7):
        os.makedirs(f"{OUT}/legacy", exist_ok=True)
        shutil.copyfile(q7, f"{OUT}/legacy/Q7_original_workbook.xlsx")
        n += 1

    print(f"[OK] input_files generated: {n} files/dirs at {os.path.abspath(OUT)}")


if __name__ == "__main__":
    build()
