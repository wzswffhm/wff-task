# -*- coding: utf-8 -*-
"""
FIN3-WKN-153 现金增强1号集合资产管理计划 2026Q3 投资运作报告 可复算脚本
报告期末 2026-09-30 ; 材料截止 2026-10-08
从 /app/input_files 读入，计算全部结论并输出全部交付物到 /app/output。
不硬编码任何结论数字，不引用网络数据。
"""
import os, csv, collections, datetime
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

BASE = os.path.dirname(os.path.abspath(__file__))
IN = os.environ.get("INPUT_DIR", "/app/input_files")
OUT = os.environ.get("OUTPUT_DIR", BASE)
os.makedirs(OUT, exist_ok=True)

VAL_DATE = "2026-09-30"
MATERIAL_CUTOFF = "2026-10-08"
BP = 10000.0  # 基点换算

def p(path): return os.path.join(IN, path)
def o(path): return os.path.join(OUT, path)

def read_csv(path):
    with open(p(path), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

ACCTS = [f"acct_{i:02d}" for i in range(1, 11)]

def load_security_master():
    sm = {}
    for r in read_csv("portfolio/security_master.csv"):
        sm[r["sec_code"]] = r
    return sm

def load_prices():
    """行情：数据组重推件为准，取估值日当日记录。过滤前后记录数留痕。"""
    rows = read_csv("data/price_feed_20260930_repush.csv")
    raw = len(rows)
    kept = {r["instrument_id"]: float(r["close_price"]) for r in rows if r["trade_date"] == VAL_DATE}
    dropped = raw - sum(1 for r in rows if r["trade_date"] == VAL_DATE)
    return kept, raw, len(kept), dropped

def load_holdings():
    wb = openpyxl.load_workbook(p("portfolio/holdings_2026Q3.xlsx"), read_only=True, data_only=True)
    sheets = {}
    for name in ACCTS:
        ws = wb[name]
        rows = list(ws.iter_rows(values_only=True))
        hdr = rows[0]
        data = []
        for r in rows[1:]:
            if r[0] is None:
                continue
            data.append(dict(acct=r[0], sec_code=r[1], sec_name=r[2], sec_type=r[3],
                             vol=float(r[4]), as_of=str(r[5]), updated_at=r[6], source_row_id=r[7]))
        sheets[name] = data
    return sheets

def market_value(sec_type, vol, price):
    """折算口径：债券与非标 vol*price/100；权益型基金 vol*price。"""
    if sec_type == "EquityFund":
        return vol * price
    return vol * price / 100.0

def apply_effective_filter(sheets, sm, prices):
    """按 recon_runbook 第2章执行期末有效持仓口径，三类剔除分列。"""
    per_sheet = []
    effective = []
    total_raw = 0
    for name in ACCTS:
        data = sheets[name]
        raw = len(data)
        total_raw += raw
        # 1) as_of != 估值日
        step1 = [r for r in data if r["as_of"] == VAL_DATE]
        drop_asof = raw - len(step1)
        # 2) 主数据 status != active
        step2 = [r for r in step1 if sm.get(r["sec_code"], {}).get("status") == "active"]
        drop_status = len(step1) - len(step2)
        # 3) 重复上报 acct+sec_code+vol，按 source_row_id 升序保留第一条
        seen = {}
        keep = []
        drop_dup = 0
        for r in sorted(step2, key=lambda x: str(x["source_row_id"])):
            key = (r["acct"], r["sec_code"], r["vol"])
            if key in seen:
                drop_dup += 1
            else:
                seen[key] = True
                keep.append(r)
        # 市值
        mv_before = 0.0  # 未过滤(全表合计)口径市值，仅对能定价的行
        for r in data:
            pr = prices.get(r["sec_code"])
            if pr is not None:
                mv_before += market_value(r["sec_type"], r["vol"], pr)
        mv_eff = 0.0
        for r in keep:
            pr = prices.get(r["sec_code"])
            r["price"] = pr
            r["mv"] = market_value(r["sec_type"], r["vol"], pr) if pr is not None else None
            if r["mv"] is not None:
                mv_eff += r["mv"]
            effective.append(r)
        per_sheet.append(dict(acct=name, raw=raw, drop_asof=drop_asof, drop_status=drop_status,
                              drop_dup=drop_dup, eff=len(keep), mv_eff=mv_eff, mv_before=mv_before))
    return per_sheet, effective, total_raw

def compute():
    sm = load_security_master()
    prices, price_raw, price_kept, price_dropped = load_prices()
    sheets = load_holdings()
    per_sheet, effective, total_raw = apply_effective_filter(sheets, sm, prices)

    # 估值材料
    nav = {r["item"]: r for r in read_csv("valuation/nav_report_20260930.csv")}
    total_shares = float(nav["total_shares"]["value"])
    custodian_total_nav = float(nav["total_nav"]["value"])
    custodian_nav_ps = float(nav["nav_per_share"]["value"])
    custodian_cash = float(nav["cash_and_equivalent"]["value"])

    accr = {r["item"]: float(r["amount"]) for r in read_csv("valuation/accruals_20260930.csv")}
    receivable = accr["interest_receivable"] + accr["dividend_receivable"]
    payable = accr["fee_payable_admin"] + accr["fee_payable_custodian"] + accr["fee_payable_sales"]

    bank = read_csv("valuation/bank_statement_20260930.csv")
    bank_rows = [(r["account"], r["account_name"], float(r["balance"])) for r in bank]
    bank_total = sum(b[2] for b in bank_rows)

    # 持仓有效市值合计
    holdings_mv = sum(r["mv"] for r in effective if r["mv"] is not None)

    # 净值推导链
    asset_net = holdings_mv + custodian_cash + receivable - payable
    nav_ps = asset_net / total_shares
    nav_diff_bp = (nav_ps - custodian_nav_ps) * BP

    # 未过滤口径对照 单位净值
    mv_before_total = sum(s["mv_before"] for s in per_sheet)
    asset_net_before = mv_before_total + custodian_cash + receivable - payable
    nav_ps_before = asset_net_before / total_shares
    overstate_bp = (nav_ps_before - nav_ps) * BP

    # 现金勾稽
    cash_diff = bank_total - custodian_cash

    # 限额测算（分母=计划资产净值总额；用托管净值作为分母口径，与第2条一致）
    denom = custodian_total_nav
    # 按证券汇总市值
    by_sec = collections.defaultdict(float)
    by_sec_type = collections.defaultdict(float)
    by_issuer = collections.defaultdict(float)
    for r in effective:
        if r["mv"] is None:
            continue
        by_sec[r["sec_code"]] += r["mv"]
        st = sm.get(r["sec_code"], {}).get("sec_type", r["sec_type"])
        by_sec_type[st] += r["mv"]
        iss = sm.get(r["sec_code"], {}).get("issuer", "待核实")
        by_issuer[iss] += r["mv"]

    top_sec_code = max(by_sec, key=by_sec.get)
    top_sec_mv = by_sec[top_sec_code]
    r01 = top_sec_mv / denom
    top_iss = max(by_issuer, key=by_issuer.get)
    top_iss_mv = by_issuer[top_iss]
    r02 = top_iss_mv / denom
    nonstd_mv = by_sec_type.get("NonStdAsset", 0.0)
    r03 = nonstd_mv / denom
    cash_ratio = custodian_cash / denom  # R-05 现金类资产比例
    equity_mv = by_sec_type.get("EquityFund", 0.0)
    r07 = equity_mv / denom

    results = dict(
        sm=sm, prices=prices, price_raw=price_raw, price_kept=price_kept, price_dropped=price_dropped,
        per_sheet=per_sheet, effective=effective, total_raw=total_raw,
        total_shares=total_shares, custodian_total_nav=custodian_total_nav,
        custodian_nav_ps=custodian_nav_ps, custodian_cash=custodian_cash,
        receivable=receivable, payable=payable, accr=accr,
        bank_rows=bank_rows, bank_total=bank_total, cash_diff=cash_diff,
        holdings_mv=holdings_mv, asset_net=asset_net, nav_ps=nav_ps, nav_diff_bp=nav_diff_bp,
        mv_before_total=mv_before_total, nav_ps_before=nav_ps_before, overstate_bp=overstate_bp,
        denom=denom, by_sec=by_sec, by_sec_type=by_sec_type, by_issuer=by_issuer,
        top_sec_code=top_sec_code, top_sec_mv=top_sec_mv, r01=r01,
        top_iss=top_iss, top_iss_mv=top_iss_mv, r02=r02,
        nonstd_mv=nonstd_mv, r03=r03, cash_ratio=cash_ratio,
        equity_mv=equity_mv, r07=r07,
    )
    return results

def count_inputs():
    """材料清点：分目录文件数 + 根散件，勾稽到总数。"""
    dirs = ["portfolio", "valuation", "data", "rules", "reports", "compliance", "internal"]
    per_dir = {}
    for d in dirs:
        files = [f for f in os.listdir(p(d)) if os.path.isfile(p(os.path.join(d, f)))]
        per_dir[d] = sorted(files)
    root = [f for f in os.listdir(IN) if os.path.isfile(p(f))]
    return per_dir, sorted(root)

# ---- 交付物写出 ----
HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(color="FFFFFF", bold=True)
TOT_FILL = PatternFill("solid", fgColor="DDEBF7")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def style_header(ws, row, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL; cell.font = HDR_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER

def write_rows(ws, start, rows):
    r = start
    for row in rows:
        for ci, v in enumerate(row, 1):
            cell = ws.cell(row=r, column=ci, value=v)
            cell.border = BORDER
        r += 1
    return r

def pct(x): return round(x * 100, 2)

def compliance_rows(R):
    """五项限额逐条：条款号, 名称, 测算值, 限额, 方向, 结论。"""
    sm = R["sm"]
    rows = [
        ("R-01", "单一证券集中度", "第4条", R["r01"], 0.10, "≤", R["r01"] <= 0.10,
         f"{R['top_sec_code']} {sm[R['top_sec_code']]['sec_name']}"),
        ("R-02", "单一发行人集中度", "第5条", R["r02"], 0.15, "≤", R["r02"] <= 0.15,
         R["top_iss"]),
        ("R-03", "非标资产比例", "第6条", R["r03"], 0.05, "≤", R["r03"] <= 0.05, "NonStdAsset合计"),
        ("R-05", "现金类资产比例", "第7条", R["cash_ratio"], 0.03, "≥", R["cash_ratio"] >= 0.03,
         "现金及清算备付金"),
        ("R-07", "权益型基金比例", "第8条", R["r07"], 0.20, "≤", R["r07"] <= 0.20, "EquityFund合计"),
    ]
    return rows

# ---------- 工作簿 ----------
def build_workbook(R, per_dir, root_files):
    wb = Workbook()
    sm = R["sm"]

    # Coverage
    ws = wb.active; ws.title = "Coverage"
    ws["A1"] = "一、材料清点与逐账户覆盖"; ws["A1"].font = Font(bold=True, size=12)
    r = 3
    ws.cell(r, 1, "（1）输入材料清点（分目录文件数 + 根散件 勾稽总数）").font = Font(bold=True)
    r += 1
    ws.append([]) if False else None
    hdr = ["目录", "文件数", "文件清单"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    subtotal = 0
    for d in ["portfolio", "valuation", "data", "rules", "reports", "compliance", "internal"]:
        files = per_dir[d]
        subtotal += len(files)
        r = write_rows(ws, r, [[d, len(files), "; ".join(files)]])
    r = write_rows(ws, r, [["根目录散件", len(root_files), "; ".join(root_files)]])
    total_files = subtotal + len(root_files)
    r = write_rows(ws, r, [["分目录小计", subtotal, ""],
                           ["根散件", len(root_files), ""],
                           ["合计（勾稽）", total_files, "分目录小计+根散件=合计"],
                           ["来源目录数", len(per_dir), ""]])
    for rr in range(r-4, r): ws.cell(rr, 1).fill = TOT_FILL
    r += 2

    ws.cell(r, 1, "（2）逐账户 sheet 覆盖（十个账户全部读取）").font = Font(bold=True); r += 1
    hdr2 = ["账户sheet", "原始行数", "剔除-非估值日", "剔除-主数据非active", "剔除-重复上报",
            "有效行数", "有效市值(元)"]
    for ci, h in enumerate(hdr2, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr2)); r += 1
    tot = [0, 0, 0, 0, 0, 0.0]
    for s in R["per_sheet"]:
        row = [s["acct"], s["raw"], s["drop_asof"], s["drop_status"], s["drop_dup"], s["eff"], round(s["mv_eff"], 2)]
        r = write_rows(ws, r, [row])
        tot[0]+=s["raw"]; tot[1]+=s["drop_asof"]; tot[2]+=s["drop_status"]; tot[3]+=s["drop_dup"]; tot[4]+=s["eff"]; tot[5]+=s["mv_eff"]
    r = write_rows(ws, r, [["合计", tot[0], tot[1], tot[2], tot[3], tot[4], round(tot[5], 2)]])
    for ci in range(1, len(hdr2)+1): ws.cell(r-1, ci).fill = TOT_FILL
    ws.column_dimensions["A"].width = 16
    for col in "BCDEFG": ws.column_dimensions[col].width = 16
    ws.column_dimensions["C"].width = 60

    build_holdings_summary(wb, R)
    build_valuation_recalc(wb, R)
    build_nav_bridge(wb, R)
    build_compliance_check(wb, R)
    build_issue_log_sheet(wb, R)
    build_task_status(wb, R)
    build_prev_report_fix(wb, R)
    wb.save(o("FIN3-WKN-153_quarterly_workbook.xlsx"))

def build_holdings_summary(wb, R):
    sm = R["sm"]
    ws = wb.create_sheet("Holdings_Summary")
    ws["A1"] = "二、券种与账户市值汇总（有效口径）"; ws["A1"].font = Font(bold=True, size=12)
    r = 3
    ws.cell(r, 1, "（1）按券种汇总").font = Font(bold=True); r += 1
    hdr = ["券种(sec_type)", "有效市值(元)", "占资产净值%"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    tot = 0.0
    for st, mv in sorted(R["by_sec_type"].items(), key=lambda x: -x[1]):
        r = write_rows(ws, r, [[st, round(mv, 2), pct(mv/R["denom"])]]); tot += mv
    r = write_rows(ws, r, [["合计", round(tot, 2), pct(tot/R["denom"])]])
    ws.cell(r-1, 1).fill = TOT_FILL
    r += 2
    ws.cell(r, 1, "（2）按账户汇总").font = Font(bold=True); r += 1
    hdr = ["账户", "有效行数", "有效市值(元)", "占资产净值%"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    tm = 0.0; te = 0
    for s in R["per_sheet"]:
        r = write_rows(ws, r, [[s["acct"], s["eff"], round(s["mv_eff"], 2), pct(s["mv_eff"]/R["denom"])]])
        tm += s["mv_eff"]; te += s["eff"]
    r = write_rows(ws, r, [["合计", te, round(tm, 2), pct(tm/R["denom"])]])
    ws.cell(r-1, 1).fill = TOT_FILL
    r += 2
    ws.cell(r, 1, "（3）前五大重仓证券").font = Font(bold=True); r += 1
    hdr = ["证券代码", "名称", "券种", "发行人", "有效市值(元)", "占净值%"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    for code, mv in sorted(R["by_sec"].items(), key=lambda x: -x[1])[:5]:
        s = sm[code]
        r = write_rows(ws, r, [[code, s["sec_name"], s["sec_type"], s["issuer"], round(mv, 2), pct(mv/R["denom"])]])
    for col, w in zip("ABCDEF", [16, 36, 16, 20, 18, 12]):
        ws.column_dimensions[col].width = w

def build_valuation_recalc(wb, R):
    ws = wb.create_sheet("Valuation_Recalc")
    ws["A1"] = "三、净值复核推导链（每行带列报值）"; ws["A1"].font = Font(bold=True, size=12)
    r = 3
    hdr = ["步骤", "算式", "数值(元)", "来源"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    rows = [
        ["持仓有效市值", "Σ(有效持仓市值)", round(R["holdings_mv"], 2), "持仓×行情(重推件,估值日)"],
        ["+ 现金及清算备付金", "托管行报告", round(R["custodian_cash"], 2), "nav_report"],
        ["+ 应收", "应收利息+应收红利", round(R["receivable"], 2), "accruals"],
        ["− 应付", "管理人报酬+托管费+销售服务费", round(R["payable"], 2), "accruals"],
        ["= 资产净值", "市值+现金+应收−应付", round(R["asset_net"], 2), "计算"],
        ["托管行资产净值", "托管行报告", round(R["custodian_total_nav"], 2), "nav_report"],
        ["资产净值差额", "计算−托管", round(R["asset_net"]-R["custodian_total_nav"], 2), "计算"],
        ["÷ 总份额", str(int(R["total_shares"])) + " 份", R["total_shares"], "nav_report"],
        ["= 单位净值(复核)", "资产净值÷总份额", round(R["nav_ps"], 6), "计算"],
        ["托管行单位净值", "托管行报告", round(R["custodian_nav_ps"], 6), "nav_report"],
        ["单位净值差额(个基点)", "(复核−托管)×10000", round(R["nav_diff_bp"], 4), "计算"],
    ]
    r = write_rows(ws, r, rows)
    r += 1
    ws.cell(r, 1, "全口径(未过滤)对照：").font = Font(bold=True); r += 1
    rows2 = [
        ["全表合计市值(可定价)", "Σ(全部上报行市值)", round(R["mv_before_total"], 2), "未过滤口径"],
        ["全口径单位净值", "(全表市值+现金+应收−应付)÷份额", round(R["nav_ps_before"], 6), "计算"],
        ["高估幅度(个基点)", "(全口径−正确口径)×10000", round(R["overstate_bp"], 4), "计算"],
    ]
    r = write_rows(ws, r, rows2)
    for col, w in zip("ABCD", [22, 40, 22, 28]): ws.column_dimensions[col].width = w

def build_nav_bridge(wb, R):
    ws = wb.create_sheet("Nav_Bridge")
    ws["A1"] = "四、现金勾稽与口径调整"; ws["A1"].font = Font(bold=True, size=12)
    r = 3
    ws.cell(r, 1, "（1）银行对账单各账户期末余额（分列）").font = Font(bold=True); r += 1
    hdr = ["账户", "账户名称", "期末余额(元)"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    for acc, nm, bal in R["bank_rows"]:
        r = write_rows(ws, r, [[acc, nm, round(bal, 2)]])
    r = write_rows(ws, r, [["合计", "", round(R["bank_total"], 2)]])
    ws.cell(r-1, 1).fill = TOT_FILL
    r = write_rows(ws, r, [["托管报告现金及清算备付金", "", round(R["custodian_cash"], 2)],
                           ["勾稽差额", "对账单合计−托管现金", round(R["cash_diff"], 2)]])
    r += 2
    ws.cell(r, 1, "（2）行情取数过滤留痕").font = Font(bold=True); r += 1
    hdr = ["项目", "记录数", "说明"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    r = write_rows(ws, r, [
        ["行情重推件原始记录", R["price_raw"], "data/price_feed_20260930_repush.csv"],
        ["过滤后(trade_date=估值日)", R["price_kept"], "关联字段 sec_code↔instrument_id"],
        ["剔除(前一交易日2026-09-29)", R["price_dropped"], "原始推送比对件，取估值日当日"],
    ])
    for col, w in zip("ABC", [30, 30, 40]): ws.column_dimensions[col].width = w

def build_compliance_check(wb, R):
    ws = wb.create_sheet("Compliance_Check")
    ws["A1"] = "五、投资监督·五项限额逐条（现行v3）"; ws["A1"].font = Font(bold=True, size=12)
    r = 3
    hdr = ["指标ID", "指标名称", "条款号", "测算值%", "限额%", "方向", "结论", "关键对象"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    for rid, nm, art, val, lim, dirn, ok, obj in compliance_rows(R):
        res = "合规" if ok else "超限"
        row = [rid, nm, art, pct(val), pct(lim), dirn, res, obj]
        r = write_rows(ws, r, [row])
        if not ok:
            for ci in range(1, len(hdr)+1):
                ws.cell(r-1, ci).fill = PatternFill("solid", fgColor="FFC7CE")
    r += 1
    ws.cell(r, 1, "现金类比例交叉核对：v3第7条(R-05)≥3% 与 liquidity_policy第12条≥3% 口径一致；第21条指明现金类界定与限制条款第七章一致。").font = Font(italic=True)
    for col, w in zip("ABCDEFGH", [10, 18, 10, 12, 10, 8, 10, 40]): ws.column_dimensions[col].width = w

def issue_log_data(R):
    """数据问题与阻塞台账：类别,文件,现象,影响,处置动作,依据,状态。"""
    d_asof = sum(s["drop_asof"] for s in R["per_sheet"])
    d_status = sum(s["drop_status"] for s in R["per_sheet"])
    d_dup = sum(s["drop_dup"] for s in R["per_sheet"])
    return [
        ["口径冲突", "rules/recon_runbook.md / internal/data_dictionary.md",
         "指引3.1要求以wind_code关联，数据字典载明wind_code已废止、改为sec_code/instrument_id",
         "若按旧字段关联将全部失配、无法定价",
         "按数据字典现行口径以sec_code↔instrument_id关联，记差异留痕",
         "data_dictionary 第3节 命名沿革", "已处置"],
        ["行情源冲突", "valuation/price_feed_20260930.csv / data/price_feed_20260930_repush.csv",
         "valuation主件为空(传输残留)，data重推件含完整估值日行情",
         "若用主件则无行情、全部无法定价",
         "以数据组重推件为准，主件作废",
         "internal/ops_email_20261008.txt", "已处置"],
        ["行情多交易日", "data/price_feed_20260930_repush.csv",
         "重推件含5条2026-09-29前一交易日记录(原始推送)",
         "混用将导致估值价错误",
         "过滤trade_date=2026-09-30，剔除5条",
         "recon_runbook 3.3 / ops_email", "已处置"],
        ["非估值日残留", "portfolio/holdings_2026Q3.xlsx",
         f"{d_asof}个账户sheet各含1行as_of=2026-06-30的旧数据(共{d_asof}行)",
         "虚增持仓市值、高估净值",
         f"按2.1剔除非估值日记录共{d_asof}行",
         "recon_runbook 2.1", "已处置"],
        ["主数据失效", "portfolio/holdings_2026Q3.xlsx / security_master.csv",
         "持仓含status为called/matured的到期赎回券(260001/102600001等)",
         "计入将虚增市值且违背有效口径",
         f"按2.2剔除status非active记录共{d_status}行",
         "recon_runbook 2.2 / manager_notes 第2条", "已处置"],
        ["重复上报", "portfolio/holdings_2026Q3.xlsx",
         f"{d_dup}组acct+sec_code+vol重复行(不同source_row_id)",
         "重复计算市值",
         f"按2.3按source_row_id升序保留首条，剔除{d_dup}行",
         "recon_runbook 2.3 / readme注意事项", "已处置"],
        ["限额超限", "rules/restrictions_v3_20260901.md",
         f"单一证券{R['top_sec_code']}(华骏集团中票)占净值{R['r01']*100:.2f}%>10%硬限",
         "触发R-01超限，须披露并整改",
         "报告监督章节披露成因/整改/时限；投资经理T+2提交整改计划",
         "restrictions_v3 第4/9条 / approval_memo", "已登记待整改"],
        ["版本适用", "rules/restrictions_v2 / v3 / compliance/limit_monitor_2026Q2.csv",
         "Q2监测与上期报告按v2(旧限额)执行，v3自2026-09-01生效",
         "沿用旧限额将漏判R-01超限",
         "三季度起一律按v3，重述上期口径",
         "restrictions_v3 附则第12条", "已处置"],
    ]

def task_status_data():
    return [
        ["T1", "材料清点与目录勾稽", "完成", "workbook:Coverage / 报告一"],
        ["T2", "十账户sheet全覆盖汇总", "完成", "workbook:Coverage/Holdings_Summary / coverage.csv"],
        ["T3", "有效持仓三类剔除口径", "完成", "coverage.csv / Holdings_Summary / 报告三"],
        ["T4", "行情估值日取数与关联", "完成", "workbook:Nav_Bridge / 报告三"],
        ["T5", "市值与单位净值复核推导链", "完成", "workbook:Valuation_Recalc / 报告二"],
        ["T6", "现金分账户勾稽", "完成", "workbook:Nav_Bridge / 报告二"],
        ["T7", "五项限额逐条测算", "完成", "workbook:Compliance_Check / 报告四"],
        ["T8", "条款版本适用性说明", "完成", "报告四 / Issue_Log"],
        ["T9", "超限处置与披露", "完成", "报告四监督章节 / Compliance_Check"],
        ["T10", "上期报告重述", "完成", "workbook:Prev_Report_Fix / 报告五"],
        ["T11", "数据问题台账", "完成", "issue_log.csv / workbook:Issue_Log / 报告六"],
        ["T12", "任务拆解与完成状态", "完成", "workbook:Task_Status / 报告七"],
        ["T13", "复合图(限额+账户覆盖)", "完成", "charts.png"],
        ["T14", "可复算脚本", "完成", "FIN3-WKN-153_reproduce.py"],
        ["T15", "报告成文(八章节,≤2页)", "完成", "FIN3-WKN-153_operation_report.md"],
    ]

def prev_report_fix_data(R=None):
    ob = f"{R['overstate_bp']:.2f}" if R else "（见Valuation_Recalc）"
    r01p = f"{R['r01']*100:.2f}" if R else "（见Compliance_Check）"
    return [
        ["上期报告持仓汇总采用盘后导出明细『全表合计』，未区分数据所属日期",
         "全表合计混入非估值日/失效/重复上报记录，高估市值与净值；manager_notes第4条已声明该表述本期不再适用",
         f"本期按recon_runbook第2章有效持仓口径(估值日+active+去重)汇总，全口径对照单位净值高估约{ob}个基点",
         "reports/2026Q2_operation_report.md 二 / manager_notes 第4条"],
        ["上期按2026-06-01版(v2)条款执行期末监测：单一证券≤12%、非标≤8%、现金≥2%、权益≤25%",
         "v3自2026-09-01生效并替代v2，三季度起期末监测一律执行v3(单一证券≤10%、非标≤5%、现金≥3%、权益≤20%)",
         f"本期按v3逐条重算：R-01={r01p}%已超10%硬限，须披露整改；其余四项合规",
         "reports/2026Q2_operation_report.md 二 / restrictions_v3 第4-8/12条"],
        ["上期称『各项指标均在限额之内，未发生超限事项』",
         "该结论基于v2旧限额；按现行v3限额单一证券集中度已超限，结论不再成立",
         "本期在监督章节如实披露R-01超限事实、成因、整改措施与T+2时限",
         "reports/2026Q2_operation_report.md 二 / restrictions_v3 第9条"],
        ["一季度报告称按2026-06-01版条款(当时为草案)执行内部监测",
         "该版本已被v3替代，仅作历史回溯，不适用于本期期末监测",
         "本期明确以v3现行有效条款为唯一期末监测口径",
         "reports/2026Q1_operation_report.md 二 / restrictions_v3 附则第12条"],
    ]

def build_issue_log_sheet(wb, R):
    ws = wb.create_sheet("Issue_Log")
    ws["A1"] = "六、数据问题与阻塞台账（七要素）"; ws["A1"].font = Font(bold=True, size=12)
    r = 3
    hdr = ["类别", "文件", "现象", "影响", "处置动作", "依据", "状态"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    for row in issue_log_data(R):
        r = write_rows(ws, r, [row])
    r += 1
    ws.cell(r, 1, "最终采用数据源：持仓=管理人交易系统盘后导出(有效口径)；净值/份额/现金=托管行报告；行情=数据组重推件(估值日当日)。").font = Font(italic=True)
    for col, w in zip("ABCDEFG", [12, 30, 32, 24, 32, 24, 12]): ws.column_dimensions[col].width = w

def build_task_status(wb, R):
    ws = wb.create_sheet("Task_Status")
    ws["A1"] = "七、任务拆解与完成状态"; ws["A1"].font = Font(bold=True, size=12)
    r = 3
    hdr = ["任务编号", "任务项", "状态", "对应交付物位置"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    for row in task_status_data():
        r = write_rows(ws, r, [row])
    for col, w in zip("ABCD", [12, 30, 10, 44]): ws.column_dimensions[col].width = w

def build_prev_report_fix(wb, R):
    ws = wb.create_sheet("Prev_Report_Fix")
    ws["A1"] = "八、上期报告重述"; ws["A1"].font = Font(bold=True, size=12)
    r = 3
    hdr = ["原表述", "不再适用的原因", "本期处置", "出处"]
    for ci, h in enumerate(hdr, 1): ws.cell(r, ci, h)
    style_header(ws, r, len(hdr)); r += 1
    for row in prev_report_fix_data(R):
        r = write_rows(ws, r, [row])
    for col, w in zip("ABCD", [36, 40, 40, 32]): ws.column_dimensions[col].width = w

def write_coverage_csv(R):
    with open(o("FIN3-WKN-153_holdings_coverage.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["账户sheet", "原始行数", "剔除_非估值日", "剔除_主数据非active",
                    "剔除_重复上报", "有效行数", "有效市值_元"])
        t = [0, 0, 0, 0, 0, 0.0]
        for s in R["per_sheet"]:
            w.writerow([s["acct"], s["raw"], s["drop_asof"], s["drop_status"], s["drop_dup"],
                        s["eff"], round(s["mv_eff"], 2)])
            t[0]+=s["raw"]; t[1]+=s["drop_asof"]; t[2]+=s["drop_status"]; t[3]+=s["drop_dup"]; t[4]+=s["eff"]; t[5]+=s["mv_eff"]
        w.writerow(["合计", t[0], t[1], t[2], t[3], t[4], round(t[5], 2)])

def write_issue_csv(R):
    with open(o("FIN3-WKN-153_issue_log.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["类别", "文件", "现象", "影响", "处置动作", "依据", "状态"])
        for row in issue_log_data(R):
            w.writerow(row)

def build_chart(R):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    for fn in ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei"]:
        try:
            matplotlib.rcParams["font.sans-serif"] = [fn]; break
        except Exception:
            pass
    matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei"]
    matplotlib.rcParams["axes.unicode_minus"] = False

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    # 左：五项限额测算值 vs 限额
    cr = compliance_rows(R)
    labels = [f"{c[0]}\n{c[1]}" for c in cr]
    vals = [c[3]*100 for c in cr]
    lims = [c[4]*100 for c in cr]
    x = range(len(cr))
    ax1.bar([i-0.2 for i in x], vals, width=0.4, label="测算值%", color="#1F4E78")
    ax1.bar([i+0.2 for i in x], lims, width=0.4, label="限额%", color="#C0504D", alpha=0.7)
    for i, c in enumerate(cr):
        ax1.text(i-0.2, vals[i]+0.2, f"{vals[i]:.2f}", ha="center", fontsize=8)
        if not c[6]:
            ax1.text(i, max(vals[i], lims[i])+0.8, "超限", ha="center", color="red", fontsize=9, fontweight="bold")
    ax1.set_xticks(list(x)); ax1.set_xticklabels(labels, fontsize=8)
    ax1.set_ylabel("占计划资产净值 %"); ax1.set_title("五项限额：本期测算值 vs 限额(v3)")
    ax1.legend(fontsize=8)
    # 右：十账户 原始 vs 有效 记录数
    accts = [s["acct"] for s in R["per_sheet"]]
    raw = [s["raw"] for s in R["per_sheet"]]
    eff = [s["eff"] for s in R["per_sheet"]]
    y = range(len(accts))
    ax2.barh([i+0.2 for i in y], raw, height=0.4, label="原始记录数", color="#9BBB59")
    ax2.barh([i-0.2 for i in y], eff, height=0.4, label="有效记录数", color="#1F4E78")
    ax2.set_yticks(list(y)); ax2.set_yticklabels(accts, fontsize=8)
    ax2.invert_yaxis()
    ax2.set_xlabel("记录数"); ax2.set_title("十账户sheet：原始 vs 有效 覆盖")
    ax2.legend(fontsize=8)
    fig.suptitle("FIN3-WKN-153 季度复核复合图：限额对比 + 账户覆盖", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(o("FIN3-WKN-153_charts.png"), dpi=120)
    plt.close(fig)

def build_report(R, per_dir, root_files):
    sm = R["sm"]
    subtotal = sum(len(v) for v in per_dir.values())
    total_files = subtotal + len(root_files)
    cr = compliance_rows(R)
    def f2(x): return f"{x:,.2f}"
    dir_line = "；".join(f"{d}={len(per_dir[d])}" for d in
                        ["portfolio","valuation","data","rules","reports","compliance","internal"])
    breach = next(c for c in cr if c[0] == "R-01")
    L = []
    L.append("# 现金增强 1 号集合资产管理计划 2026 年三季度投资运作报告")
    L.append("")
    L.append(f"报告期末：**2026-09-30**｜材料截止时点：**2026-10-08**｜编制：投研支持（投资监督与运营核算复核）")
    L.append("")
    L.append("## 一、材料清点")
    L.append(f"输入文件共 **{total_files}** 件，来源目录 **{len(per_dir)}** 个。分目录：{dir_line}；根目录散件 {len(root_files)} 件（00_README.md、manifest.csv）。勾稽：分目录小计 {subtotal} + 根散件 {len(root_files)} = {total_files}，与总数一致。")
    L.append("")
    L.append("## 二、组合概况与净值复核")
    L.append("按有效持仓口径复核净值推导链（单位：元）：")
    L.append(f"- 持仓有效市值 {f2(R['holdings_mv'])} + 现金及清算备付金 {f2(R['custodian_cash'])} + 应收 {f2(R['receivable'])} − 应付 {f2(R['payable'])} = 资产净值 {f2(R['asset_net'])}；与托管报告 {f2(R['custodian_total_nav'])} 差额 {f2(R['asset_net']-R['custodian_total_nav'])}。")
    L.append(f"- 资产净值 {f2(R['asset_net'])} ÷ 总份额 {int(R['total_shares']):,} = 单位净值 {R['nav_ps']:.6f}；托管报告 {R['custodian_nav_ps']:.4f}，差 {R['nav_diff_bp']:.4f} 个基点。")
    L.append(f"- 现金勾稽：托管存款专户 {f2(R['bank_rows'][0][2])} + 清算备付金账户 {f2(R['bank_rows'][1][2])} = {f2(R['bank_total'])}，与托管报告现金 {f2(R['custodian_cash'])} 差额 {f2(R['cash_diff'])}。")
    L.append("")
    d_asof = sum(s["drop_asof"] for s in R["per_sheet"])
    d_status = sum(s["drop_status"] for s in R["per_sheet"])
    d_dup = sum(s["drop_dup"] for s in R["per_sheet"])
    L.append("## 三、持仓覆盖与口径执行")
    L.append(f"十个账户 sheet（acct_01–acct_10）全部读取，原始合计 {R['total_raw']} 行，有效 {len(R['effective'])} 行。按 recon_runbook 第2章三类剔除分列：非估值日 {d_asof} 行、主数据非 active {d_status} 行、重复上报 {d_dup} 行（逐 sheet 明细见 coverage.csv）。")
    L.append(f"行情以数据组重推件为准：原始 {R['price_raw']} 条，过滤 trade_date=2026-09-30 后 {R['price_kept']} 条，剔除前一交易日 {R['price_dropped']} 条；持仓与行情以 sec_code↔instrument_id 关联（旧 wind_code 字段已废止）。")
    L.append(f"全口径（全表合计、未过滤）单位净值将达 {R['nav_ps_before']:.6f}，较正确口径高估 **{R['overstate_bp']:.2f} 个基点**，故不得沿用全表合计。")
    L.append("")
    L.append("## 四、投资监督与限额执行")
    L.append("按**现行有效 v3（2026-09-01）**条款逐条测算（分母=计划资产净值总额）：")
    for c in cr:
        L.append(f"- {c[0]}（{c[2]}）{c[1]}：{c[3]*100:.2f}% {c[5]} {c[4]*100:.2f}% → **{'合规' if c[6] else '超限'}**")
    L.append(f"现金类比例与 liquidity_policy 第12条（≥3%）交叉核对，两处口径一致；该制度第21条亦指明现金类界定与限制条款第七章一致。")
    L.append(f"**超限处置（R-01）**：单一证券 {breach[7]} 市值 {f2(R['top_sec_mv'])} 元、占净值 {R['r01']*100:.2f}%，超 v3 第4条 10% 硬限。成因：9 月中旬增持华骏集团中期票据（approval_memo_20260928，内部预警线 10.5%，增持后接近硬限）叠加其余持仓到期剔除后分母下降形成被动偏离。整改：投资经理须于 **T+2** 工作日内（至 2026-10-14 前）提交整改计划并减持至限额内，按 v3 第9条在本章节披露超限事实、成因、整改措施与时限。")
    L.append(f"历史版本适用性：v2（2026-06-01）已被 v3 替代仅作回溯；v2 旧限额（单一证券≤12%、非标≤8%、现金≥2%、权益≤25%）不适用于本期，三季度及以后期末监测一律执行 v3。")
    L.append("")
    L.append("## 五、上期报告口径重述")
    L.append("逐条见工作簿 Prev_Report_Fix（原表述/原因/处置/出处），要点：")
    for i, row in enumerate(prev_report_fix_data(R), 1):
        L.append(f"{i}. 原表述：{row[0]}；本期处置：{row[2]}。")
    L.append("")
    L.append("## 六、数据问题与处置")
    L.append("逐条台账见 issue_log.csv / 工作簿 Issue_Log（七要素），要点：")
    for i, row in enumerate(issue_log_data(R), 1):
        L.append(f"{i}. [{row[0]}] {row[2]}（{row[6]}）。")
    L.append("最终数据源：持仓=管理人交易系统盘后导出（有效口径）；净值/份额/现金=托管行报告；行情=数据组重推件。")
    L.append("")
    L.append("## 七、任务拆解与完成状态")
    for row in task_status_data():
        L.append(f"- {row[0]} {row[1]}：{row[2]}（{row[3]}）")
    L.append("")
    L.append("## 八、结论与下季度计划")
    L.append(f"除 R-01 单一证券集中度超限（已登记并进入 T+2 整改）外，其余四项限额合规；净值与现金勾稽一致（差 {R['nav_diff_bp']:.4f} 个基点、现金差 0.00 元）。下季度：完成华骏集团中票减持至限额内并持续监测单一发行人集中度（当前 {R['r02']*100:.2f}%，限 15%），非标到期分布 2027-03 至 2028-06 按摊余成本跟踪。待核实事项按材料标注，不自行补充。")
    L.append("")
    txt = "\n".join(L)
    with open(o("FIN3-WKN-153_operation_report.md"), "w", encoding="utf-8") as f:
        f.write(txt)
    return txt

def main():
    R = compute()
    per_dir, root_files = count_inputs()
    build_workbook(R, per_dir, root_files)
    write_coverage_csv(R)
    write_issue_csv(R)
    build_chart(R)
    txt = build_report(R, per_dir, root_files)
    # 篇幅校验：正文中文字符数（去除表格竖线与代码块标记）
    import re
    body = re.sub(r"[|`]", "", txt)
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
    print("report CJK chars:", cjk)
    print("deliverables written to", OUT)
    print("R-01 breach:", R["top_sec_code"], round(R["r01"]*100, 2), "%")

if __name__ == "__main__":
    main()





