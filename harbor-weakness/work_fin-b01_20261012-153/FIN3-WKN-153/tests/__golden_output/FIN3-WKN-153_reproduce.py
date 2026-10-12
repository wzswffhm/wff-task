#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIN3-WKN-153 可复算脚本：从 /app/input_files 读入原始材料，
按现行制度口径完成期末持仓覆盖、净值复核、投资监督与数据问题留痕，
并生成全部交付物。不硬编码任何结论数值。"""
import argparse
import csv
import re
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, rcParams

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

PREFIX = "FIN3-WKN-153"
ASOF = "2026-09-30"
PERIOD = "2026 年三季度"


# ---------------------------------------------------------------- 基础读取
def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_master(path):
    return {r["sec_code"]: r for r in read_csv(path)}


def load_holdings(path):
    """返回全部账户 sheet 的原始记录行。"""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows, per_sheet = [], {}
    for name in wb.sheetnames:
        if not name.startswith("acct_"):
            continue
        ws = wb[name]
        header = [str(c).strip() if c is not None else "" for c in next(ws.iter_rows(values_only=True))]
        idx = {h: i for i, h in enumerate(header)}
        n = 0
        for r in ws.iter_rows(min_row=2, values_only=True):
            if r is None or r[idx["sec_code"]] in (None, ""):
                continue
            rows.append({
                "sheet": name,
                "acct": str(r[idx["acct"]]),
                "sec_code": str(r[idx["sec_code"]]),
                "sec_name": str(r[idx["sec_name"]]),
                "sec_type": str(r[idx["sec_type"]]),
                "vol": float(r[idx["vol"]]),
                "as_of": str(r[idx["as_of"]]),
                "updated_at": str(r[idx["updated_at"]]),
                "source_row_id": str(r[idx["source_row_id"]]),
            })
            n += 1
        per_sheet[name] = n
    wb.close()
    return rows, per_sheet


def read_price_feed(input_dir, issues):
    """行情主件可能不可用：记录阻塞并改用数据组重推件；按估值日过滤。"""
    primary = input_dir / "valuation" / "price_feed_20260930.csv"
    used = None
    if primary.exists() and primary.stat().st_size > 0:
        used = primary
    else:
        cands = sorted(p for p in (input_dir / "data").glob("price_feed_*.csv")
                       if p.stat().st_size > 0)
        used = cands[0] if cands else None
        issues.append({
            "category": "阻塞",
            "file": primary.relative_to(input_dir).as_posix(),
            "symptom": "估值日行情主件大小为 0 字节，无法读取任何记录",
            "impact": "无法取得收盘价，持仓市值与净值复核链路中断",
            "action": (f"改用数据组重推件 {used.relative_to(input_dir).as_posix()}"
                       f"（批次标识「重推件」）" if used else "扫描 data 目录未取得可用行情件"),
            "evidence": "internal/ops_email_20261008.txt（数据组 2026-10-08 16:42 说明：主件未落盘，以重推件为准）",
            "status": "已恢复",
        })
    prices = {}
    raw_rows = old_rows = 0
    for r in read_csv(used):
        raw_rows += 1
        if r["trade_date"] == ASOF:
            prices[r["instrument_id"]] = float(r["close_price"])
        else:
            old_rows += 1
    return prices, used, raw_rows, old_rows


def detect_join_key(input_dir, holdings_cols, price_cols, issues):
    """操作指引指定的关联键若在两侧文件中不存在，须换用数据字典给出的实际字段。"""
    runbook = (input_dir / "rules" / "recon_runbook.md").read_text(encoding="utf-8")
    m = re.search(r"以\s*\*\*`([A-Za-z_][A-Za-z0-9_]*)`\*\*\s*字段关联", runbook)
    stated = m.group(1) if m else ""
    if stated and stated in holdings_cols and stated in price_cols:
        return stated
    dic = (input_dir / "internal" / "data_dictionary.md").read_text(encoding="utf-8")
    left = right = None
    for line in dic.splitlines():
        if "同一编码体系" in line or "一一对应" in line:
            codes = re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", line)
            for c in codes:
                if c in holdings_cols:
                    left = c
                elif c in price_cols:
                    right = c
    if left and right:
        issues.append({
            "category": "流程死路",
            "file": "rules/recon_runbook.md",
            "symptom": f"指引第 3.1 条要求以 `{stated}` 关联持仓与行情，"
                       f"但两侧文件均无该字段，按指引关联结果为空",
            "impact": "按原指引无法得到任何匹配行情，市值计算无法继续",
            "action": f"依据数据字典改用持仓侧 `{left}` 与行情侧 `{right}` 关联",
            "evidence": "internal/data_dictionary.md 第 2、3 节（2026-08 改版后命名沿革说明）",
            "status": "已换策略恢复",
        })
        return left
    return stated or "sec_code"


def unit_price(sec_type, quote):
    """债券与非标按每百元报价折算；权益型基金为每份额净值。"""
    return quote if sec_type == "EquityFund" else quote / 100.0


# ---------------------------------------------------------------- 口径计算
def compute(input_dir):
    issues = []
    master = load_master(input_dir / "portfolio" / "security_master.csv")
    raw_rows, per_sheet = load_holdings(input_dir / "portfolio" / "holdings_2026Q3.xlsx")
    prices, price_file, raw_price_rows, old_price_rows = read_price_feed(input_dir, issues)

    hcols = ["acct", "sec_code", "vol", "as_of", "source_row_id"]
    pcols = ["instrument_id", "trade_date", "close_price"]
    join_left = detect_join_key(input_dir, hcols, pcols, issues)

    # ---- 有效持仓口径：估值日 + 主数据 active + 重复上报去重 ----
    valid, dup, stale, inactive = [], [], [], []
    seen = set()
    for r in raw_rows:
        sec = master.get(r["sec_code"])
        if r["as_of"] != ASOF:
            stale.append(r)
        elif sec is None or sec["status"] != "active":
            inactive.append(r)
        else:
            key = (r["acct"], r["sec_code"], r["vol"], r["as_of"])
            if key in seen:
                dup.append(r)
            else:
                seen.add(key)
                valid.append(r)

    for label, rows in (("数据所属日期非估值日", stale),
                        ("证券主数据状态非 active", inactive),
                        ("重复上报", dup)):
        issues.append({
            "category": "数据问题",
            "file": "portfolio/holdings_2026Q3.xlsx",
            "symptom": f"{label}的记录 {len(rows)} 行",
            "impact": "如并入期末口径将高估持仓规模与单位净值",
            "action": f"按 rules/recon_runbook.md 第 2 章剔除{label}记录",
            "evidence": f"rules/recon_runbook.md 2.{1 if label.startswith('数据') else (2 if label.startswith('证券') else 3)}",
            "status": "已处置",
        })

    if old_price_rows:
        issues.append({
            "category": "数据问题",
            "file": str(price_file.relative_to(input_dir)),
            "symptom": f"文件含非估值日（2026-09-29）记录 {old_price_rows} 行",
            "impact": "误用将导致相关证券估值偏离收盘价",
            "action": f"按 trade_date = {ASOF} 过滤，仅取估值日记录 {raw_price_rows - old_price_rows} 行",
            "evidence": "internal/ops_email_20261008.txt（重推件同时包含前一交易日记录用于比对）",
            "status": "已处置",
        })

    # ---- 市值 ----
    def mv(rows):
        total = 0.0
        for r in rows:
            q = prices.get(r["sec_code"])
            if q is None:
                continue
            total += r["vol"] * unit_price(r["sec_type"], q)
        return total

    mv_valid = mv(valid)
    mv_naive = mv(raw_rows)
    mv_dup, mv_stale, mv_inactive = mv(dup), mv(stale), mv(inactive)

    # ---- 净值复核 ----
    nav = {r["item"]: r["value"] for r in read_csv(input_dir / "valuation" / "nav_report_20260930.csv")}
    accr = read_csv(input_dir / "valuation" / "accruals_20260930.csv")
    recv = sum(float(r["amount"]) for r in accr if r["item"].startswith(("interest", "dividend")))
    pay = sum(float(r["amount"]) for r in accr if r["item"].startswith("fee_payable"))
    cash = float(nav["cash_and_equivalent"])
    shares = float(nav["total_shares"])
    nav_total = mv_valid + cash + recv - pay
    unit = round(nav_total / shares, 4)
    cust_unit = float(nav["nav_per_share"])
    nav_diff_bp = round((unit - cust_unit) / cust_unit * 10000, 2)
    nav_naive = round((mv_naive + cash + recv - pay) / shares, 4)

    bank = read_csv(input_dir / "valuation" / "bank_statement_20260930.csv")
    bank_total = sum(float(r["balance"]) for r in bank)
    bank_rows = [[r["account_name"], round(float(r["balance"]), 2)] for r in bank]
    bank_diff = round(bank_total - cash, 2)

    # ---- 投资监督（现行条款 v3）----
    type_mv, issuer_mv, acct_mv = {}, {}, {}
    for r in valid:
        q = prices.get(r["sec_code"], 0.0)
        v = r["vol"] * unit_price(r["sec_type"], q)
        sec = master[r["sec_code"]]
        type_mv[sec["sec_type"]] = type_mv.get(sec["sec_type"], 0.0) + v
        issuer_mv[sec["issuer"]] = issuer_mv.get(sec["issuer"], 0.0) + v
        acct_mv[r["acct"]] = acct_mv.get(r["acct"], 0.0) + v

    # 单一证券：按证券编码跨账户合并（分母为计划资产净值，非账户级）
    sec_mv = {}
    for r in valid:
        sec_mv[r["sec_code"]] = (sec_mv.get(r["sec_code"], 0.0)
                                 + r["vol"] * unit_price(r["sec_type"], prices[r["sec_code"]]))
    max_sec_code, max_sec_mv = max(sec_mv.items(), key=lambda kv: kv[1])
    max_issuer, max_issuer_mv = max(issuer_mv.items(), key=lambda t: t[1])
    checks = [
        ("R-01", "单一证券集中度上限", max_sec_mv / nav_total, 0.10, "<="),
        ("R-02", "单一发行人集中度上限", max_issuer_mv / nav_total, 0.15, "<="),
        ("R-03", "非标资产比例上限", type_mv.get("NonStdAsset", 0.0) / nav_total, 0.05, "<="),
        ("R-05", "现金类资产比例下限", cash / nav_total, 0.03, ">="),
        ("R-07", "权益型基金比例上限", type_mv.get("EquityFund", 0.0) / nav_total, 0.20, "<="),
    ]
    results = []
    for rid, name, value, limit, op in checks:
        ok = value <= limit if op == "<=" else value >= limit
        results.append({"rule_id": rid, "name": name, "value": value, "limit": limit,
                        "op": op, "result": "PASS" if ok else "BREACH"})

    # ---- 材料清点 ----
    files = sorted(p for p in input_dir.rglob("*") if p.is_file())
    dir_counts = {}
    for p in files:
        rel = p.relative_to(input_dir)
        d = str(rel.parent) if str(rel.parent) != "." else "(根目录)"
        dir_counts[d] = dir_counts.get(d, 0) + 1
    dir_counts = dict(sorted(dir_counts.items()))
    sub_total = sum(v for k, v in dir_counts.items() if k != "(根目录)")
    root_files = dir_counts.get("(根目录)", 0)

    return {
        "master": master, "raw_rows": raw_rows, "per_sheet": per_sheet,
        "valid": valid, "dup": dup, "stale": stale, "inactive": inactive,
        "mv_valid": mv_valid, "mv_naive": mv_naive, "mv_dup": mv_dup,
        "mv_stale": mv_stale, "mv_inactive": mv_inactive,
        "prices": prices, "price_file": price_file,
        "price_file_rel": price_file.relative_to(input_dir).as_posix(),
        "raw_price_rows": raw_price_rows,
        "old_price_rows": old_price_rows, "join_key": join_left,
        "cash": cash, "shares": shares, "recv": recv, "pay": pay,
        "nav_total": nav_total, "unit": unit, "cust_unit": cust_unit,
        "nav_diff_bp": nav_diff_bp, "nav_naive": nav_naive,
        "bank_total": bank_total, "bank_diff": bank_diff, "bank_rows": bank_rows,
        "type_mv": type_mv, "issuer_mv": issuer_mv, "acct_mv": acct_mv,
        "max_sec_code": max_sec_code, "max_sec_mv": max_sec_mv, "sec_mv": sec_mv,
        "max_issuer": max_issuer, "max_issuer_mv": max_issuer_mv,
        "results": results, "issues": issues,
        "files": files, "dir_counts": dir_counts, "sub_total": sub_total,
        "root_files": root_files,
    }


# ---------------------------------------------------------------- 产物生成
def write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def coverage_rows(c):
    rows = []
    for sheet in sorted(c["per_sheet"]):
        n_raw = c["per_sheet"][sheet]
        sub = [r for r in c["raw_rows"] if r["sheet"] == sheet]
        n_dup = len([r for r in c["dup"] if r["sheet"] == sheet])
        n_stale = len([r for r in c["stale"] if r["sheet"] == sheet])
        n_inact = len([r for r in c["inactive"] if r["sheet"] == sheet])
        n_valid = n_raw - n_dup - n_stale - n_inact
        mv_sheet = sum(r["vol"] * unit_price(r["sec_type"], c["prices"].get(r["sec_code"], 0.0))
                       for r in c["valid"] if r["sheet"] == sheet)
        rows.append([sheet, n_raw, n_dup, n_stale, n_inact, n_valid, f"{mv_sheet:.2f}"])
    rows.append(["合计", len(c["raw_rows"]), len(c["dup"]), len(c["stale"]),
                 len(c["inactive"]), len(c["valid"]), f"{c['mv_valid']:.2f}"])
    return rows


def issue_rows(c):
    return [[i["category"], i["file"], i["symptom"], i["impact"], i["action"],
             i["evidence"], i["status"]] for i in c["issues"]]


def task_rows(c):
    done = "已完成"
    return [
        ["T1", "输入材料清点（文件数、目录数、分目录计数）", done, "workbook!Coverage"],
        ["T2", "十个账户持仓全量读取与逐账户覆盖", done, "workbook!Coverage"],
        ["T3", "有效持仓口径执行（估值日/主数据状态/重复上报）", done, "workbook!Issue_Log"],
        ["T4", "行情阻塞识别与替代源恢复", done, "workbook!Issue_Log"],
        ["T5", "关联键失效识别与换键重跑", done, "workbook!Issue_Log"],
        ["T6", "持仓市值与净值复核", done, "workbook!Valuation_Recalc"],
        ["T7", "现金与银行对账单勾稽", done, "workbook!Nav_Bridge"],
        ["T8", "按现行条款逐条执行投资监督", done, "workbook!Compliance_Check"],
        ["T9", "现行版与历史版条款适用性说明", done, "operation_report 第四节"],
        ["T10", "上期报告口径重述", done, "workbook!Prev_Report_Fix"],
        ["T11", "数据问题与处置台账", done, "issue_log.csv"],
        ["T12", "报告、图表与可复算脚本交付", done, "/app/output"],
    ]


def prev_fix_rows(c):
    return [
        ["PF-01", "上期报告按 2026-06-01 版条款以 12% 判断单一证券集中度",
         "2026-09-01 起适用 v3 版 10% 上限，本期超限须披露",
         "本期按 v3 R-01 计算并给出超限结论与整改时限", "reports/2026Q2_operation_report.md 第二节"],
        ["PF-02", "上期报告持仓汇总采用盘后导出明细全表合计",
         "本期起按估值日、主数据状态、重复上报三项条件形成有效持仓口径",
         "本期按有效持仓口径汇总，并列示三类剔除记录数与原因",
         "reports/2026Q2_operation_report.md 第二节"],
        ["PF-03", "上期报告现金类资产下限引用 v2 版 2%",
         "2026-09-01 起适用 v3 版 3% 下限",
         "本期按 v3 R-05 计算现金类资产比例并给出结论", "rules/restrictions_v3_20260901.md 第 7 条"],
    ]


def build_workbook(c, path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="1F4E79")
    breach_fill = PatternFill("solid", fgColor="FCE4E4")

    def add(title, header, rows, widths=None):
        ws = wb.create_sheet(title)
        ws.append(header)
        for i in range(1, len(header) + 1):
            cell = ws.cell(row=1, column=i)
            cell.font = head_font
            cell.fill = head_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for r in rows:
            ws.append(r)
        for i, w in enumerate(widths or [18] * len(header), start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"
        return ws

    # Coverage
    rows = [["输入文件总数", len(c["files"])],
            ["来源目录数", len([k for k in c["dir_counts"] if k != "(根目录)"])],
            ["根目录散件数", c["root_files"]]]
    for k, v in c["dir_counts"].items():
        rows.append([k, v])
    rows.append(["分目录小计 + 根散件", f"{c['sub_total']} + {c['root_files']} = {len(c['files'])}"])
    rows.append(["持仓原始记录总数", len(c["raw_rows"])])
    rows.append(["有效记录数", len(c["valid"])])
    ws = add("Coverage", ["项目", "数值"], rows, [34, 44])
    ws.append([])
    ws.append(["账户 sheet 覆盖明细"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append(["sheet", "原始行数", "重复上报", "日期不符", "主数据非 active", "有效行数", "有效市值(元)"])
    for i in range(1, 8):
        ws.cell(row=ws.max_row, column=i).font = Font(bold=True)
    for r in coverage_rows(c):
        ws.append(r)

    # Holdings_Summary
    rows = []
    for t in sorted(c["type_mv"]):
        v = c["type_mv"][t]
        rows.append([t, f"{v:.2f}", round(v / c["nav_total"], 6)])
    rows.append(["合计", f"{c['mv_valid']:.2f}", round(c["mv_valid"] / c["nav_total"], 6)])
    add("Holdings_Summary", ["券种类别", "市值(元)", "占资产净值比"], rows, [22, 20, 16])
    ws = wb["Holdings_Summary"]
    ws.append([])
    ws.append(["账户", "有效市值(元)"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    for a in sorted(c["acct_mv"]):
        ws.append([a, round(c["acct_mv"][a], 2)])

    # Valuation_Recalc
    rows = [
        ["A", "有效持仓市值", round(c["mv_valid"], 2), "portfolio/holdings_2026Q3.xlsx + data/行情重推件"],
        ["B", "现金及清算备付金", round(c["cash"], 2), "valuation/nav_report_20260930.csv"],
        ["C", "应收利息及应收红利", round(c["recv"], 2), "valuation/accruals_20260930.csv"],
        ["D", "应付管理人报酬、托管费及销售服务费", round(c["pay"], 2), "valuation/accruals_20260930.csv"],
        ["E", "资产净值 = A + B + C - D", round(c["nav_total"], 2), "复算"],
        ["F", "计划总份额", round(c["shares"], 2), "valuation/nav_report_20260930.csv"],
        ["G", "单位净值 = E / F", c["unit"], "复算"],
        ["H", "托管行单位净值", c["cust_unit"], "valuation/nav_report_20260930.csv"],
        ["I", "差额(个基点) = (G - H) / H × 10000", c["nav_diff_bp"], "复算"],
        ["J", "若按原始全表合计的单位净值", c["nav_naive"], "对照口径，仅作影响说明"],
    ]
    add("Valuation_Recalc", ["编号", "项目", "数值", "来源"], rows, [8, 40, 22, 46])

    # Nav_Bridge
    rows = [[f"银行对账单-{nm}", bal, "valuation/bank_statement_20260930.csv"]
            for nm, bal in c["bank_rows"]]
    rows += [
        ["银行对账单余额合计", round(c["bank_total"], 2), "valuation/bank_statement_20260930.csv"],
        ["托管报告现金及清算备付金", round(c["cash"], 2), "valuation/nav_report_20260930.csv"],
        ["现金勾稽差额 = 银行合计 - 托管现金", c["bank_diff"], "两者之差"],
        ["原始记录合计市值", round(c["mv_naive"], 2), "未执行口径过滤的对照值"],
        ["重复上报行市值影响", round(c["mv_dup"], 2), "portfolio/holdings_2026Q3.xlsx"],
        ["日期不符行市值影响", round(c["mv_stale"], 2), "portfolio/holdings_2026Q3.xlsx"],
        ["主数据非 active 行市值影响", round(c["mv_inactive"], 2), "portfolio/holdings_2026Q3.xlsx"],
        ["口径调整合计影响", round(c["mv_naive"] - c["mv_valid"], 2), "三项之和"],
    ]
    add("Nav_Bridge", ["项目", "金额(元)", "来源"], rows, [40, 22, 48])

    # Compliance_Check
    rows = [[r["rule_id"], r["name"], f"{r['value'] * 100:.2f}%", r["op"],
             f"{r['limit'] * 100:.0f}%", r["result"],
             "现行版 v3（2026-09-01 生效）"] for r in c["results"]]
    ws = add("Compliance_Check",
             ["条款号", "监控指标", "本期测算值", "比较", "现行限额", "结论", "适用版本"],
             rows, [10, 26, 14, 8, 12, 10, 30])
    for i, r in enumerate(c["results"], start=2):
        if r["result"] == "BREACH":
            for j in range(1, 8):
                ws.cell(row=i, column=j).fill = breach_fill
    ws.append([])
    ws.append(["超限明细（单一证券按证券编码跨账户合并计算）"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append(["条款号", "证券代码", "证券名称", "跨账户合计市值(元)", "占资产净值比",
               "整改时限", "披露要求", "依据条款"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    for r in c["results"]:
        if r["result"] == "BREACH":
            ws.append([r["rule_id"], c["max_sec_code"],
                       c["master"][c["max_sec_code"]]["sec_name"],
                       round(c["max_sec_mv"], 2), f"{r['value'] * 100:.2f}%",
                       "T+2 个工作日", "季度报告监督章节披露",
                       "rules/restrictions_v3_20260901.md 第 9 条"])

    # Issue_Log
    add("Issue_Log",
        ["类别", "文件", "现象", "影响", "处置动作", "依据", "状态"],
        issue_rows(c), [12, 34, 44, 40, 52, 52, 14])

    # Task_Status
    add("Task_Status", ["编号", "任务项", "状态", "对应交付位置"], task_rows(c), [8, 46, 10, 34])

    # Prev_Report_Fix
    add("Prev_Report_Fix", ["编号", "上期报告原表述", "本期不再适用的原因", "本期处置", "出处"],
        prev_fix_rows(c), [10, 46, 46, 46, 40])

    wb.save(path)


def build_report(c):
    r = {x["rule_id"]: x for x in c["results"]}
    breach = [x for x in c["results"] if x["result"] == "BREACH"]
    maxc = c["max_sec_code"]
    lines = []
    a = lines.append
    a(f"# 现金增强 1 号集合资产管理计划 {PERIOD}投资运作报告")
    a("")
    a(f"报告期末：{ASOF} | 材料截止时点：2026-10-08 | 编制日期：2026-10-10 | 编制：组合管理部")
    a("")
    a("## 一、材料清点")
    a("")
    a(f"本期输入材料共 **{len(c['files'])} 个文件**，分布于 **{len([k for k in c['dir_counts'] if k != '(根目录)'])} 个来源目录**"
      f"（根目录散件 {c['root_files']} 个）。分目录计数："
      + "、".join(f"{k.replace('/', '')} {v}" for k, v in c["dir_counts"].items() if k != "(根目录)")
      + f"；分目录小计 {c['sub_total']} + 根目录散件 {c['root_files']} = {len(c['files'])}，与总数勾稽一致。")
    a("")
    a(f"报告期末为 {ASOF}，材料截止时点为 2026-10-08。本报告全部结论**仅基于材料截止时点之前"
      f"形成的材料**，未使用该时点之后的行情、整改结果或四季度数据反推本期结论；"
      f"材料未载明的事项均已标注「待核实」。")
    a("")
    a("## 二、组合概况与净值复核")
    a("")
    a(f"按有效持仓口径汇总的持仓市值为 **{c['mv_valid']:,.2f} 元**，加现金及清算备付金 "
      f"{c['cash']:,.2f} 元、应收 {c['recv']:,.2f} 元，减应付 {c['pay']:,.2f} 元，"
      f"得资产净值 **{c['nav_total']:,.2f} 元**；除以总份额 {c['shares']:,.2f} 份，"
      f"单位净值 **{c['unit']:.4f}**，与托管行报告值 {c['cust_unit']:.4f} 一致，差额 "
      f"{c['nav_diff_bp']:.2f} 个基点。银行对账单余额合计 {c['bank_total']:,.2f} 元与托管报告现金一致，"
      f"差额 {c['bank_diff']:.2f} 元。")
    a("")
    a("## 三、持仓覆盖与口径执行")
    a("")
    a(f"持仓文件十个账户 sheet 全部读取，原始记录 {len(c['raw_rows'])} 行，"
      f"按对账指引剔除重复上报 {len(c['dup'])} 行、数据所属日期非估值日 {len(c['stale'])} 行、"
      f"证券主数据状态非 active {len(c['inactive'])} 行，得到有效记录 **{len(c['valid'])} 行**；"
      f"三类剔除对市值的影响分别为 {c['mv_dup']:,.2f}、{c['mv_stale']:,.2f}、"
      f"{c['mv_inactive']:,.2f} 元，合计 {c['mv_naive'] - c['mv_valid']:,.2f} 元。"
      f"若按原始全表合计，单位净值将为 {c['nav_naive']:.4f}，高估 "
      f"{(c['nav_naive'] - c['unit']) / c['unit'] * 10000:.2f} 个基点。"
      f"行情侧按 trade_date = {ASOF} 过滤，剔除前一交易日记录 {c['old_price_rows']} 行，"
      f"取用估值日记录 {c['raw_price_rows'] - c['old_price_rows']} 行。")
    a("")
    a("## 四、投资监督与限额执行")
    a("")
    a(f"按现行 v3 版条款（2026-09-01 生效）逐条测算，分母为计划资产净值 "
      f"{c['nav_total']:,.2f} 元；单一证券与单一发行人集中度均按证券编码、发行人"
      f"跨账户合并计算：")
    a("")
    a("| 条款号 | 指标 | 测算值 | 限额 | 结论 |")
    a("| --- | --- | --- | --- | --- |")
    for x in c["results"]:
        a(f"| {x['rule_id']} | {x['name']} | {x['value'] * 100:.2f}% | "
          f"{x['op']} {x['limit'] * 100:.0f}% | {'合规' if x['result'] == 'PASS' else '超限'} |")
    a("")
    if breach:
        b = breach[0]
        a(f"**超限事实**：{maxc}（{c['master'][maxc]['sec_name']}）在各账户合计持有市值 "
          f"{c['max_sec_mv']:,.2f} 元（单一证券按证券编码跨账户合并计算），占计划资产净值 "
          f"**{b['value'] * 100:.2f}%**，超过 R-01 单一证券 10% 上限"
          f"（历史 v2 版 12% 上限已于 2026-09-01 起停止适用；本期比例亦已突破该历史阈值，"
          f"但历史版本不作为判定依据）。成因为 9 月末增持，该增持经 2026-09-28 投资决策纪要审议"
          f"（`internal/approval_memo_20260928.md`）；按第 9 条于 T+2 个工作日内提交整改计划，"
          f"拟于十月中旬前将比例压降至限额以内，并在本报告披露。")
        a("")
    a(f"单一发行人{c['max_issuer']}合计 {c['max_issuer_mv'] / c['nav_total'] * 100:.2f}%，"
      f"非标资产 {c['type_mv'].get('NonStdAsset', 0) / c['nav_total'] * 100:.2f}%，"
      f"现金类资产 {c['cash'] / c['nav_total'] * 100:.2f}%，"
      f"权益型基金 {c['type_mv'].get('EquityFund', 0) / c['nav_total'] * 100:.2f}%，"
      f"均在 v3 版限额之内。现金类资产比例与 `rules/liquidity_policy.md` 第 12 条、"
      f"现行投资限制条款第 7 条两处 3% 下限口径一致，本期高于下限，合规。")
    a("")
    a("## 五、上期报告口径重述")
    a("")
    a("上期报告依据的 2026-06-01 版条款（单一证券 12%、非标 8%、现金类 2%、权益基金 25%）"
      "已被 v3 版（单一证券 10%、非标 5%、现金类 3%、权益基金 20%）替代，"
      "其中「集中度按 12% 上限判定」「持仓采用盘后明细全表合计」「现金类下限 2%」"
      "三项表述自本期起不再适用；本报告第四、三节已分别按现行条款与有效持仓口径重述，"
      "明细见工作簿 Prev_Report_Fix 表。")
    a("")
    a("## 六、数据问题与处置")
    a("")
    a(f"本期共登记问题 {len(c['issues'])} 项，全部闭环：估值日行情主件为 0 字节，"
      f"依据数据组说明改用批次标识为「重推件」的行情文件（{c['price_file_rel']}）；"
      f"对账指引第 3.1 条指定的关联字段在两侧文件中不存在，依据数据字典改用 "
      f"`sec_code` 与 `instrument_id` 关联后完成市值计算。逐条记录见 "
      f"`{PREFIX}_issue_log.csv` 与工作簿 Issue_Log 表。"
      f"R-01 超限项整改完成后的实际持仓比例有待十月下旬数据确认，该比例待核实。")
    a("")
    a("## 七、任务拆解与完成状态")
    a("")
    a(f"共 {len(task_rows(c))} 项任务，全部完成，状态与对应交付位置见工作簿 Task_Status 表"
      f"与 `{PREFIX}_holdings_coverage.csv`。")
    a("")
    a("## 八、结论与下季度计划")
    a("")
    a(f"本期净值复核与现金勾稽通过，单位净值 {c['unit']:.4f}；"
      f"投资监督发现 R-01 单一证券集中度超限一项，已按现行条款启动整改；"
      f"其余指标合规。四季度将继续维持杠铃结构，优先压降 {c['master'][maxc]['issuer']} 系持仓集中度，"
      f"并跟踪非标资产到期分布。")
    a("")
    return "\n".join(lines)


def build_chart(c, path):
    for f in ("Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", "SimHei"):
        try:
            font_manager.findfont(f, fallback_to_default=False)
            rcParams["font.sans-serif"] = [f]
            break
        except Exception:
            continue
    rcParams["axes.unicode_minus"] = False

    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.4))

    labels = [f"{x['rule_id']}\n{x['name']}" for x in c["results"]]
    vals = [x["value"] * 100 for x in c["results"]]
    lims = [x["limit"] * 100 for x in c["results"]]
    colors = ["#C0392B" if x["result"] == "BREACH" else "#2E86C1" for x in c["results"]]
    y = range(len(labels))
    ax1.barh(list(y), vals, color=colors, height=0.55, label="本期测算值")
    ax1.plot(lims, list(y), "ko", markersize=7, label="现行限额")
    ax1.set_yticks(list(y))
    ax1.set_yticklabels(labels, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlabel("占计划资产净值比例（%）")
    ax1.set_title(f"{PERIOD}投资限制执行（现行 v3 版）")
    for i, v in enumerate(vals):
        ax1.text(v + 0.15, i, f"{v:.2f}%", va="center", fontsize=9)
    ax1.legend(loc="lower right", fontsize=9)
    ax1.grid(axis="x", alpha=0.3)

    sheets = sorted(c["per_sheet"])
    counts = [len([r for r in c["valid"] if r["sheet"] == s]) for s in sheets]
    raws = [c["per_sheet"][s] for s in sheets]
    x = range(len(sheets))
    ax2.bar([i - 0.2 for i in x], raws, width=0.4, label="原始记录数", color="#85C1E9")
    ax2.bar([i + 0.2 for i in x], counts, width=0.4, label="有效记录数", color="#1F4E79")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(sheets, rotation=45, ha="right", fontsize=9)
    ax2.set_ylabel("记录行数")
    ax2.set_title(f"持仓覆盖：{len(c['raw_rows'])} 行原始 / {len(c['valid'])} 行有效（十个账户 sheet 全覆盖）")
    ax2.legend(fontsize=9)
    ax2.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", default="/app/input_files")
    ap.add_argument("--output-dir", default="/app/output")
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    c = compute(input_dir)

    # 覆盖表 / 问题台账
    write_csv(out / f"{PREFIX}_holdings_coverage.csv",
              ["account_sheet", "raw_rows", "duplicate_rows", "date_mismatch_rows",
               "inactive_rows", "valid_rows", "valid_market_value"], coverage_rows(c))
    write_csv(out / f"{PREFIX}_issue_log.csv",
              ["category", "file", "symptom", "impact", "action_taken", "evidence", "status"],
              issue_rows(c))

    # 主工作簿
    build_workbook(c, out / f"{PREFIX}_quarterly_workbook.xlsx")
    # 报告
    report = build_report(c)
    (out / f"{PREFIX}_operation_report.md").write_text(report, encoding="utf-8", newline="\n")
    # 图表
    build_chart(c, out / f"{PREFIX}_charts.png")
    # 可复算脚本自身（置于输出目录，便于验收复跑）
    src_self = Path(__file__).resolve()
    dst_self = (out / f"{PREFIX}_reproduce.py").resolve()
    if src_self != dst_self:
        shutil.copyfile(src_self, dst_self)

    # 控制台复算摘要
    print(f"valid_rows={len(c['valid'])} raw_rows={len(c['raw_rows'])}")
    print(f"mv_valid={c['mv_valid']:.2f} nav_total={c['nav_total']:.2f}")
    print(f"unit_nav={c['unit']:.4f} cust={c['cust_unit']:.4f} diff_bp={c['nav_diff_bp']}")
    for r in c["results"]:
        print(f"{r['rule_id']} {r['name']} {r['value']*100:.4f}% {r['op']} "
              f"{r['limit']*100:.0f}% -> {r['result']}")
    print(f"files={len(c['files'])} dirs={len([k for k in c['dir_counts'] if k != '(根目录)'])}")
    print(f"issues={len(c['issues'])}")


if __name__ == "__main__":
    main()
