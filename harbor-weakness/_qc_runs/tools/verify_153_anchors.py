# -*- coding: utf-8 -*-
"""FIN3-WKN-153 锚点核对（出题工具，不进题包）。

逐条把 tests/rubrics.toml 中声明的锚点与 solution/golden_output 的实际产物比对，
用于替代本地无法执行的 G4 判分预检：确认金标满足全部正分项、不命中任何负向项。
"""
import csv
import io
import re
import struct
import sys
from pathlib import Path

import openpyxl

PKG = Path(__file__).resolve().parents[2] / "work_fin-b01_20261012-153" / "FIN3-WKN-153"
GOLD = PKG / "solution" / "golden_output"


def gold_text():
    parts = []
    wb = openpyxl.load_workbook(GOLD / "FIN3-WKN-153_quarterly_workbook.xlsx", data_only=True)
    sheet_names = list(wb.sheetnames)
    for ws in wb.worksheets:
        parts.append(f"### sheet {ws.title}")
        for row in ws.iter_rows(values_only=True):
            parts.append(" | ".join("" if c is None else str(c) for c in row))
    wb.close()
    parts.append((GOLD / "FIN3-WKN-153_operation_report.md").read_text(encoding="utf-8"))
    for name in ("FIN3-WKN-153_holdings_coverage.csv", "FIN3-WKN-153_issue_log.csv"):
        parts.append((GOLD / name).read_text(encoding="utf-8"))
    py = (GOLD / "FIN3-WKN-153_reproduce.py").read_text(encoding="utf-8")
    return "\n".join(parts), py, sheet_names


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def main():
    text, py_text, sheets = gold_text()
    fails, notes = [], []

    def need(cid, *needles):
        for n in needles:
            if n not in text:
                fails.append(f"{cid}: 产物缺少锚点 {n!r}")

    # 结构化核对
    cov = read_csv(GOLD / "FIN3-WKN-153_holdings_coverage.csv")
    iss = read_csv(GOLD / "FIN3-WKN-153_issue_log.csv")
    if len(cov) != 12:
        fails.append(f"R17: 覆盖表行数 {len(cov)} != 12（含表头）")
    if len(cov[0]) != 7:
        fails.append(f"R17: 覆盖表列数 {len(cov[0])} != 7")
    for row in cov[1:]:
        raw, dup, stale, inact, valid = (int(row[1]), int(row[2]), int(row[3]),
                                         int(row[4]), int(row[5]))
        if raw - dup - stale - inact != valid:
            fails.append(f"R17: 覆盖表勾稽不成立 {row[0]} {raw}-{dup}-{stale}-{inact}!={valid}")
    if len(iss) != 7:
        fails.append(f"R15: 台账记录数 {len(iss) - 1} != 6")

    need("R01", "295", "280", "11,554,917.40", "25,774,234.50", "25,142,250.00")
    need("R02", "1,295,353,746.36", "45,645,475.03", "4,278,200.00", "2,763,450.00",
         "1,342,513,971.39", "1,250,000,000.00", "1.0740")
    need("R03", "R-01", "R-02", "R-03", "R-05", "R-07", "BREACH")
    need("R04", "valuation/price_feed_20260930.csv", "0 字节",
         "data/price_feed_20260930_repush.csv", "重推件", "ops_email_20261008.txt")
    need("R05", "25 个文件", "7 个来源目录", "compliance 3", "data 3", "internal 4",
         "portfolio 2", "reports 3", "rules 4", "valuation 4", "23 + 2 = 25")
    for s, n_raw, n_val in (("acct_01", 42, 40), ("acct_02", 36, 34), ("acct_03", 38, 36),
                            ("acct_04", 34, 32), ("acct_05", 28, 26), ("acct_06", 23, 22),
                            ("acct_07", 25, 24), ("acct_08", 4, 4), ("acct_09", 31, 30),
                            ("acct_10", 34, 32)):
        row = [r for r in cov[1:] if r[0] == s]
        if not row or int(row[0][1]) != n_raw or int(row[0][5]) != n_val:
            fails.append(f"R06: {s} 行数不符 期望 {n_raw}/{n_val}")
    need("R07", "1,295,353,746.36", "NonStdAsset", "EquityFund")
    need("R08", "12.01", "4.50", "3.40", "7.63")
    need("R09", "v3", "2026-09-01", "12%", "8%", "2%", "25%")
    need("R10", "102600003.IB", "161,214,619.60", "T+2", "approval_memo_20260928.md", "跨账户合并")
    need("R11", "32864742.02", "12780733.01", "45645475.03", "45,645,475.03", "0.00")
    need("R12", "wind_code", "sec_code", "instrument_id", "data_dictionary.md")
    need("R13", "126 行", "5 行", "2026-09-29")
    need("R14", "PF-01", "PF-02", "PF-03")
    need("R16", "T12", "已完成")
    need("R19", "295", "280", "1,295,353,746.36", "1,342,513,971.39", "1.0740", "12.01")
    need("R20", "1.1240", "465.55")
    need("R22", "一、材料清点", "二、组合概况与净值复核", "三、持仓覆盖与口径执行",
         "四、投资监督与限额执行", "五、上期报告口径重述", "六、数据问题与处置",
         "七、任务拆解与完成状态", "八、结论与下季度计划")
    need("R25", "待核实")
    need("R27", "nav_report_20260930.csv", "accruals_20260930.csv",
         "restrictions_v3_20260901.md", "holdings_2026Q3.xlsx")
    need("R28", "超限事实")
    need("R29", "liquidity_policy.md")
    need("R30", "2026-10-08")

    # 交付物齐全
    expect = ["FIN3-WKN-153_quarterly_workbook.xlsx", "FIN3-WKN-153_operation_report.md",
              "FIN3-WKN-153_reproduce.py", "FIN3-WKN-153_holdings_coverage.csv",
              "FIN3-WKN-153_issue_log.csv", "FIN3-WKN-153_charts.png"]
    for name in expect:
        p = GOLD / name
        if not p.is_file() or p.stat().st_size == 0:
            fails.append(f"R21: 交付物缺失或为空 {name}")

    # 工作簿八表
    for s in ("Coverage", "Holdings_Summary", "Valuation_Recalc", "Nav_Bridge",
              "Compliance_Check", "Issue_Log", "Task_Status", "Prev_Report_Fix"):
        if s not in sheets:
            fails.append(f"R26: 工作簿缺工作表 {s}")

    # 报告篇幅
    md = (GOLD / "FIN3-WKN-153_operation_report.md").read_text(encoding="utf-8")
    zh = len(re.findall(r"[\u4e00-\u9fff]", md))
    if zh > 1600:
        fails.append(f"R23: 报告中文字符 {zh} > 1600")

    # 图表有效性
    png = (GOLD / "FIN3-WKN-153_charts.png").read_bytes()
    if png[:8] != b"\x89PNG\r\n\x1a\n" or len(png) < 5000:
        fails.append("R24: charts.png 不是有效 PNG 或过小")

    # 负向项不应被金标命中（只看出现在交付物中的表述）
    if "阻塞未解除" in text or "无法完成复核" in text:
        fails.append("N01: 产物出现阻塞未恢复的表述")
    if re.search(r"(网络|联网|互联网).{0,6}(数据|行情)", text):
        fails.append("N03: 交付物出现网络数据表述")
    if "未找到" in text:
        fails.append("N01: 交付物出现「未找到」类未恢复表述")

    # 交付物命名与声明一致
    declared = re.findall(r'path = "(FIN3-WKN-153_[^"]+)"',
                          (PKG / "task.toml").read_text(encoding="utf-8"))
    if sorted(declared) != sorted(expect):
        fails.append(f"交付物声明与金标不一致: {sorted(declared)}")
    arts = re.findall(r'"(/app/output/FIN3-WKN-153_[^"]+)"',
                      (PKG / "task.toml").read_text(encoding="utf-8"))
    if sorted(a.split("/")[-1] for a in arts) != sorted(expect):
        fails.append(f"artifacts 与交付物不一致: {sorted(arts)}")
    inst = (PKG / "instruction.md").read_text(encoding="utf-8")
    for name in expect:
        if name not in inst:
            fails.append(f"instruction.md 未列出交付物 {name}")

    print(f"判据条数核对：34；锚点核对：{'PASS' if not fails else 'FAIL'}")
    print(f"报告中文字符={zh}；覆盖表行={len(cov)}；台账行={len(iss)}；工作表数={len(sheets)}")
    for n in notes:
        print("NOTE:", n)
    for f in fails:
        print("FAIL:", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
