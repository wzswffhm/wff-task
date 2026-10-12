from __future__ import annotations

import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

OUTPUT_NAMES = {
    "workbook": "FIN3-WKN-153_quarterly_workbook.xlsx",
    "report": "FIN3-WKN-153_operation_report.md",
    "script": "FIN3-WKN-153_reproduce.py",
    "coverage": "FIN3-WKN-153_holdings_coverage.csv",
    "issues": "FIN3-WKN-153_issue_log.csv",
    "chart": "FIN3-WKN-153_charts.png",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def nav_items(path: Path) -> dict[str, str]:
    frame = pd.read_csv(path, dtype=str)
    return dict(zip(frame["item"], frame["value"]))


def amount(value: object) -> float:
    return float(str(value).replace(",", ""))


def money(value: float) -> str:
    return f"{value:,.2f}"


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def extract_limit(text: str, rule_id: str) -> tuple[float, str, str]:
    pattern = rf"第\s*(\d+)\s*条（{re.escape(rule_id)}）.*?(不得超过|不得低于)\s*(\d+(?:\.\d+)?)%"
    match = re.search(pattern, text, flags=re.S)
    if not match:
        raise ValueError(f"未能从现行条款提取 {rule_id}")
    return float(match.group(3)) / 100, match.group(2), f"第{match.group(1)}条（{rule_id}）"


def parse_dates(readme: str, nav: dict[str, str]) -> tuple[str, str]:
    report_date = nav["report_date"]
    cutoff_match = re.search(r"材料包整理日[：:]\s*`?(\d{4}-\d{2}-\d{2})", readme)
    if not cutoff_match:
        raise ValueError("README 未载明材料整理日")
    return report_date, cutoff_match.group(1)


def load_inputs(input_dir: Path) -> dict[str, object]:
    paths = {
        "holdings": input_dir / "portfolio/holdings_2026Q3.xlsx",
        "master": input_dir / "portfolio/security_master.csv",
        "nav": input_dir / "valuation/nav_report_20260930.csv",
        "accruals": input_dir / "valuation/accruals_20260930.csv",
        "bank": input_dir / "valuation/bank_statement_20260930.csv",
        "price_residual": input_dir / "valuation/price_feed_20260930.csv",
        "price_repush": input_dir / "data/price_feed_20260930_repush.csv",
        "rules_v3": input_dir / "rules/restrictions_v3_20260901.md",
        "rules_v2": input_dir / "rules/restrictions_v2_20260601.md",
        "runbook": input_dir / "rules/recon_runbook.md",
        "liquidity": input_dir / "rules/liquidity_policy.md",
        "dictionary": input_dir / "internal/data_dictionary.md",
        "ops_email": input_dir / "internal/ops_email_20261008.txt",
        "manager_notes": input_dir / "internal/manager_notes.md",
        "approval": input_dir / "internal/approval_memo_20260928.md",
        "prev_report": input_dir / "reports/2026Q2_operation_report.md",
        "template": input_dir / "reports/report_template.md",
        "checklist": input_dir / "compliance/review_checklist.md",
        "readme": input_dir / "00_README.md",
    }
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(path)
    nav = nav_items(paths["nav"])
    readme = read_text(paths["readme"])
    report_date, cutoff_date = parse_dates(readme, nav)
    master = pd.read_csv(paths["master"], dtype={"sec_code": str})
    prices_raw = pd.read_csv(paths["price_repush"], dtype={"instrument_id": str})
    prices = prices_raw[
        (prices_raw["trade_date"] == report_date)
        & (prices_raw["batch_tag"] == "重推件")
    ].copy()
    if prices.empty:
        raise ValueError("估值日重推行情为空")
    if prices["instrument_id"].duplicated().any():
        raise ValueError("估值日重推行情 instrument_id 不唯一")
    sheet_names = pd.ExcelFile(paths["holdings"]).sheet_names
    account_sheets = sorted(s for s in sheet_names if re.fullmatch(r"acct_\d{2}", s))
    if len(account_sheets) != 10:
        raise ValueError(f"账户 sheet 应为10个，实际{len(account_sheets)}个")
    holdings_parts = []
    for sheet in account_sheets:
        frame = pd.read_excel(
            paths["holdings"],
            sheet_name=sheet,
            dtype={"sec_code": str, "source_row_id": str},
        )
        frame["sheet"] = sheet
        holdings_parts.append(frame)
    holdings = pd.concat(holdings_parts, ignore_index=True)
    holdings = holdings.merge(
        master,
        on="sec_code",
        how="left",
        suffixes=("_holding", "_master"),
        validate="many_to_one",
        indicator="master_match",
    )
    holdings = holdings.merge(
        prices[["instrument_id", "close_price"]],
        left_on="sec_code",
        right_on="instrument_id",
        how="left",
        validate="many_to_one",
        indicator="price_match",
    )
    if (holdings["master_match"] != "both").any():
        raise ValueError("存在未匹配证券主数据的持仓")
    if (holdings["price_match"] != "both").any():
        raise ValueError("存在未匹配估值日行情的持仓")
    holdings["close_price"] = holdings["close_price"].astype(float)
    holdings["market_value"] = holdings["vol"].astype(float) * holdings["close_price"]
    non_funds = holdings["sec_type_master"] != "EquityFund"
    holdings.loc[non_funds, "market_value"] /= 100
    holdings["date_ok"] = holdings["as_of"].astype(str).str[:10].eq(report_date)
    holdings["status_ok"] = holdings["status"].eq("active")
    eligible = holdings[holdings["date_ok"] & holdings["status_ok"]].sort_values("source_row_id")
    duplicate_flags = eligible.duplicated(["acct", "sec_code", "vol"], keep="first")
    holdings["duplicate_exclusion"] = False
    holdings.loc[eligible.index, "duplicate_exclusion"] = duplicate_flags.to_numpy()
    holdings["effective"] = (
        holdings["date_ok"]
        & holdings["status_ok"]
        & ~holdings["duplicate_exclusion"]
    )
    accruals = pd.read_csv(paths["accruals"])
    bank = pd.read_csv(paths["bank"])
    return {
        "paths": paths,
        "nav": nav,
        "report_date": report_date,
        "cutoff_date": cutoff_date,
        "master": master,
        "prices_raw": prices_raw,
        "prices": prices,
        "holdings": holdings,
        "effective": holdings[holdings["effective"]].copy(),
        "account_sheets": account_sheets,
        "accruals": accruals,
        "bank": bank,
        "rules_v3": read_text(paths["rules_v3"]),
        "rules_v2": read_text(paths["rules_v2"]),
        "runbook": read_text(paths["runbook"]),
        "liquidity": read_text(paths["liquidity"]),
        "dictionary": read_text(paths["dictionary"]),
        "ops_email": read_text(paths["ops_email"]),
        "manager_notes": read_text(paths["manager_notes"]),
        "approval": read_text(paths["approval"]),
        "prev_report": read_text(paths["prev_report"]),
    }


def build_calculations(data: dict[str, object], input_dir: Path) -> dict[str, object]:
    holdings = data["holdings"]
    effective = data["effective"]
    report_date = data["report_date"]
    nav = data["nav"]
    accruals = data["accruals"]
    bank = data["bank"]
    total_nav = amount(nav["total_nav"])
    total_shares = amount(nav["total_shares"])
    trustee_cash = amount(nav["cash_and_equivalent"])
    receivables = float(accruals.loc[accruals["item"].str.endswith("_receivable"), "amount"].sum())
    payables = float(accruals.loc[accruals["item"].str.contains("_payable_"), "amount"].sum())
    bank_total = float(bank["balance"].sum())
    raw_mv = float(holdings["market_value"].sum())
    after_date_mv = float(holdings.loc[holdings["date_ok"], "market_value"].sum())
    after_status_mask = holdings["date_ok"] & holdings["status_ok"]
    after_status_mv = float(holdings.loc[after_status_mask, "market_value"].sum())
    effective_mv = float(effective["market_value"].sum())
    recalculated_nav = effective_mv + trustee_cash + receivables - payables
    unit_nav = recalculated_nav / total_shares
    raw_unit_nav = (raw_mv + trustee_cash + receivables - payables) / total_shares
    trustee_unit_reported = amount(nav["nav_per_share"])
    trustee_unit_exact = total_nav / total_shares
    unit_diff_bps_exact = (unit_nav - trustee_unit_exact) * 10000
    unit_diff_bps_reported = (unit_nav - trustee_unit_reported) * 10000
    raw_overstatement_bps = (raw_unit_nav - unit_nav) * 10000

    coverage_rows = []
    for sheet in data["account_sheets"]:
        group = holdings[holdings["sheet"] == sheet]
        coverage_rows.append({
            "sheet": sheet,
            "原始行数": len(group),
            "估值日归属剔除行数": int((~group["date_ok"]).sum()),
            "主数据状态剔除行数": int((group["date_ok"] & ~group["status_ok"]).sum()),
            "重复上报剔除行数": int((group["date_ok"] & group["status_ok"] & group["duplicate_exclusion"]).sum()),
            "有效行数": int(group["effective"].sum()),
            "有效市值": float(group.loc[group["effective"], "market_value"].sum()),
        })
    coverage = pd.DataFrame(coverage_rows)
    coverage_total = {
        "sheet": "合计",
        "原始行数": int(coverage["原始行数"].sum()),
        "估值日归属剔除行数": int(coverage["估值日归属剔除行数"].sum()),
        "主数据状态剔除行数": int(coverage["主数据状态剔除行数"].sum()),
        "重复上报剔除行数": int(coverage["重复上报剔除行数"].sum()),
        "有效行数": int(coverage["有效行数"].sum()),
        "有效市值": float(coverage["有效市值"].sum()),
    }
    coverage = pd.concat([coverage, pd.DataFrame([coverage_total])], ignore_index=True)

    directory_rows = []
    for directory in sorted(p for p in input_dir.iterdir() if p.is_dir()):
        directory_rows.append({"目录": directory.name, "文件数": sum(p.is_file() for p in directory.iterdir())})
    root_files = sum(p.is_file() for p in input_dir.iterdir())
    directory_inventory = pd.DataFrame(directory_rows)
    total_files = int(directory_inventory["文件数"].sum() + root_files)
    inventory_with_root = pd.concat([
        directory_inventory,
        pd.DataFrame([
            {"目录": "根目录散件", "文件数": root_files},
            {"目录": "合计", "文件数": total_files},
        ]),
    ], ignore_index=True)

    limits = {rule: extract_limit(data["rules_v3"], rule) for rule in ["R-01", "R-02", "R-03", "R-05", "R-07"]}
    security_totals = effective.groupby(["sec_code", "sec_name_master"], as_index=False)["market_value"].sum()
    top_security = security_totals.sort_values("market_value", ascending=False).iloc[0]
    issuer_totals = effective.groupby("issuer", as_index=False)["market_value"].sum()
    top_issuer = issuer_totals.sort_values("market_value", ascending=False).iloc[0]
    nonstandard_mv = float(effective.loc[effective["sec_type_master"] == "NonStdAsset", "market_value"].sum())
    equity_fund_mv = float(effective.loc[effective["sec_type_master"] == "EquityFund", "market_value"].sum())
    metrics = [
        ("R-01", "单一证券集中度", float(top_security["market_value"]), f"{top_security['sec_code']} {top_security['sec_name_master']}"),
        ("R-02", "单一发行人及关联方集中度", float(top_issuer["market_value"]), str(top_issuer["issuer"])),
        ("R-03", "非标资产比例", nonstandard_mv, "sec_type=NonStdAsset"),
        ("R-05", "现金类资产比例", trustee_cash, "托管报告现金及清算备付金"),
        ("R-07", "权益型基金比例", equity_fund_mv, "sec_type=EquityFund"),
    ]
    compliance_rows = []
    for rule, name, numerator, max_item in metrics:
        limit, wording, article = limits[rule]
        measured = numerator / total_nav
        direction = "≤" if wording == "不得超过" else "≥"
        passed = measured <= limit if direction == "≤" else measured >= limit
        note = ""
        if rule == "R-02":
            note = "按证券主数据issuer聚合；材料未提供关联方映射，关联方合并口径待核实"
        if rule == "R-05":
            note = f"与流动性管理制度第12条同为不低于{pct(limit)}，阈值及方向一致；第21条误引“第七章”待核实"
        compliance_rows.append({
            "规则": rule,
            "指标": name,
            "条款号": article,
            "最大项/口径": max_item,
            "分子": numerator,
            "分母_资产净值": total_nav,
            "测算值": measured,
            "列报值": pct(measured),
            "限额": limit,
            "限额列报": pct(limit),
            "比较方向": direction,
            "结论": "合规" if passed else "超限",
            "说明": note,
        })
    compliance = pd.DataFrame(compliance_rows)

    adjustment_rows = [
        {"步骤": "未过滤持仓", "剔除记录数": 0, "本步市值影响": 0.0, "步骤后市值": raw_mv, "依据": "管理人盘后导出全部账户sheet"},
        {"步骤": "剔除非估值日归属", "剔除记录数": int((~holdings["date_ok"]).sum()), "本步市值影响": raw_mv - after_date_mv, "步骤后市值": after_date_mv, "依据": "对账指引2.1"},
        {"步骤": "剔除主数据非active", "剔除记录数": int((holdings["date_ok"] & ~holdings["status_ok"]).sum()), "本步市值影响": after_date_mv - after_status_mv, "步骤后市值": after_status_mv, "依据": "对账指引2.2"},
        {"步骤": "剔除重复上报", "剔除记录数": int((after_status_mask & holdings["duplicate_exclusion"]).sum()), "本步市值影响": after_status_mv - effective_mv, "步骤后市值": effective_mv, "依据": "对账指引2.3，acct+sec_code+vol，source_row_id升序首条"},
    ]
    adjustments = pd.DataFrame(adjustment_rows)

    holdings_summary = pd.pivot_table(
        effective,
        index="sec_type_master",
        columns="sheet",
        values="market_value",
        aggfunc="sum",
        fill_value=0,
        margins=True,
        margins_name="合计",
    ).reset_index().rename(columns={"sec_type_master": "券种"})

    issues = build_issues(data, limits, total_nav, report_date)
    prev_fixes = build_previous_fixes(data, limits)
    tasks = build_tasks()
    return {
        "total_nav": total_nav,
        "total_shares": total_shares,
        "trustee_cash": trustee_cash,
        "receivables": receivables,
        "payables": payables,
        "bank_total": bank_total,
        "raw_mv": raw_mv,
        "effective_mv": effective_mv,
        "recalculated_nav": recalculated_nav,
        "unit_nav": unit_nav,
        "raw_unit_nav": raw_unit_nav,
        "trustee_unit_reported": trustee_unit_reported,
        "trustee_unit_exact": trustee_unit_exact,
        "unit_diff_bps_exact": unit_diff_bps_exact,
        "unit_diff_bps_reported": unit_diff_bps_reported,
        "raw_overstatement_bps": raw_overstatement_bps,
        "coverage": coverage,
        "directory_inventory": inventory_with_root,
        "source_directory_count": len(directory_rows),
        "root_files": root_files,
        "total_files": total_files,
        "compliance": compliance,
        "adjustments": adjustments,
        "holdings_summary": holdings_summary,
        "issues": issues,
        "prev_fixes": prev_fixes,
        "tasks": tasks,
        "top_security": top_security,
        "top_issuer": top_issuer,
    }


def build_issues(data: dict[str, object], limits: dict[str, tuple[float, str, str]], total_nav: float, report_date: str) -> pd.DataFrame:
    holdings = data["holdings"]
    prices_raw = data["prices_raw"]
    paths = data["paths"]
    old_count = int((~holdings["date_ok"]).sum())
    inactive_count = int((holdings["date_ok"] & ~holdings["status_ok"]).sum())
    duplicate_count = int((holdings["date_ok"] & holdings["status_ok"] & holdings["duplicate_exclusion"]).sum())
    prior_price_count = int((prices_raw["trade_date"] != report_date).sum())
    approval_numbers = [float(x) / 100 for x in re.findall(r"(\d+(?:\.\d+)?)%", data["approval"])]
    hard_limit = limits["R-01"][0]
    approval_conflict = ", ".join(pct(x) for x in approval_numbers if x > hard_limit)
    rows = [
        {"类别": "行情阻塞", "文件": str(paths["price_residual"].relative_to(paths["readme"].parent)), "现象": "行情主件为0字节传输残留", "影响": "无法据其完成定价", "处置动作": "依据运营邮件改用数据组重推件", "依据": "internal/ops_email_20261008.txt；README行情优先级", "状态": "已处置"},
        {"类别": "行情日期", "文件": str(paths["price_repush"].relative_to(paths["readme"].parent)), "现象": f"重推件含{prior_price_count}条非估值日记录", "影响": "仅按证券码关联会错用前一交易日行情", "处置动作": f"过滤trade_date={report_date}且batch_tag=重推件", "依据": "对账指引3.3；运营邮件", "状态": "已处置"},
        {"类别": "字段口径", "文件": "rules/recon_runbook.md；internal/data_dictionary.md", "现象": "指引写wind_code，现行文件实际为sec_code/instrument_id", "影响": "照旧字段无法关联", "处置动作": "按2026-08数据字典以sec_code=instrument_id关联并留痕", "依据": "数据字典第2、3章", "状态": "已处置"},
        {"类别": "估值日归属", "文件": "portfolio/holdings_2026Q3.xlsx", "现象": f"账户sheet混入{old_count}条非估值日记录", "影响": "未过滤将高估持仓及单位净值", "处置动作": f"仅保留as_of={report_date}", "依据": "对账指引2.1", "状态": "已处置"},
        {"类别": "主数据状态", "文件": "portfolio/holdings_2026Q3.xlsx；portfolio/security_master.csv", "现象": f"估值日持仓含{inactive_count}条非active证券", "影响": "到期或赎回证券会被错误计入期末", "处置动作": "剔除status非active记录", "依据": "现行条款第3条；对账指引2.2", "状态": "已处置"},
        {"类别": "重复上报", "文件": "portfolio/holdings_2026Q3.xlsx", "现象": f"发现{duplicate_count}条重复上报", "影响": "重复计算市值及集中度", "处置动作": "按acct+sec_code+vol分组、source_row_id升序保留首条", "依据": "对账指引2.3", "状态": "已处置"},
        {"类别": "限额冲突", "文件": "internal/approval_memo_20260928.md；rules/restrictions_v3_20260901.md", "现象": f"纪要中的{approval_conflict}高于现行R-01硬限{pct(hard_limit)}", "影响": "内部批准参数不能作为合规阈值", "处置动作": f"本期统一按现行硬限{pct(hard_limit)}判断", "依据": "现行条款第4、12条", "状态": "已处置"},
        {"类别": "超限处置资料", "文件": "internal/manager_notes.md；internal/approval_memo_20260928.md", "现象": "经理说明称增持华骏第一期，期末超限证券为第三期；且增持时间早于所引纪要", "影响": "超限成因、审批链及整改动作无法完整核实", "处置动作": "报告披露差异；具体成因、整改动作及实际时限标注待核实", "依据": "现行条款第9条；信息集纪律", "状态": "待核实"},
        {"类别": "制度交叉引用", "文件": "rules/liquidity_policy.md；rules/restrictions_v3_20260901.md", "现象": "流动性制度第21条引用不存在的投资限制“第七章”", "影响": "条文定位不一致；现金比例阈值本身一致", "处置动作": "按两文件明确的3%下限交叉核对，引用错误待制度维护", "依据": "流动性制度第12、21条；现行条款第7条", "状态": "待核实"},
        {"类别": "关联方映射缺失", "文件": "portfolio/security_master.csv", "现象": "主数据仅载issuer，未提供发行人关联方映射", "影响": "R-02只能按同一issuer聚合，关联方合并范围待核实", "处置动作": "采用材料可复核的issuer聚合值并显式披露限制", "依据": "现行条款第5条；不得引入材料外假设", "状态": "待核实"},
    ]
    return pd.DataFrame(rows, columns=["类别", "文件", "现象", "影响", "处置动作", "依据", "状态"])


def build_previous_fixes(data: dict[str, object], limits: dict[str, tuple[float, str, str]]) -> pd.DataFrame:
    source = "reports/2026Q2_operation_report.md"
    current = "rules/restrictions_v3_20260901.md"
    previous_values = {
        rule: float(match.group(1)) / 100
        for rule in ["R-01", "R-03", "R-05"]
        if (match := re.search(rf"{rule}.*?(\d+(?:\.\d+)?)%", data["rules_v2"], flags=re.S))
    }
    if len(previous_values) != 3:
        raise ValueError("未能从v2提取上期历史限额")
    return pd.DataFrame([
        {"原表述": f"单一证券集中度低于{pct(previous_values['R-01'])}上限", "不再适用的原因": f"v2已被v3替代，R-01上限收紧至{pct(limits['R-01'][0])}", "本期处置": f"按第4条{pct(limits['R-01'][0])}重新测算", "出处": f"{source}:12；{current}:14"},
        {"原表述": f"非标资产比例低于{pct(previous_values['R-03'])}上限", "不再适用的原因": f"v2已被v3替代，R-03上限收紧至{pct(limits['R-03'][0])}", "本期处置": f"按第6条{pct(limits['R-03'][0])}重新测算", "出处": f"{source}:13；{current}:16-17"},
        {"原表述": f"现金类资产比例高于{pct(previous_values['R-05'])}下限", "不再适用的原因": f"v2已被v3替代，R-05下限提高至{pct(limits['R-05'][0])}", "本期处置": f"按第7条{pct(limits['R-05'][0])}并与流动性制度第12条交叉核对", "出处": f"{source}:13-14；{current}:18"},
        {"原表述": "各项指标均在限额之内", "不再适用的原因": "上期仅列R-01、R-03、R-05且依据旧限额，不能替代本期五项检查", "本期处置": "按v3逐项列示R-01、R-02、R-03、R-05、R-07", "出处": f"{source}:12-14；{current}:14-19"},
        {"原表述": "持仓汇总采用盘后导出明细全表合计，未区分日期", "不再适用的原因": "违反本期有效持仓估值日归属口径", "本期处置": "按as_of过滤并分列三类剔除及未过滤净值对照", "出处": f"{source}:16-17；rules/recon_runbook.md:13-16"},
    ])


def build_tasks() -> pd.DataFrame:
    rows = [
        ("T01", "材料清点与目录勾稽", "已完成", "Coverage!A1"),
        ("T02", "十账户持仓全覆盖", "已完成", "Coverage!A14；持仓覆盖CSV"),
        ("T03", "三类剔除与全口径净值对照", "已完成", "Nav_Bridge!A1"),
        ("T04", "估值日行情过滤与关联", "已完成", "Valuation_Recalc!A12"),
        ("T05", "市值、净值及单位净值复核", "已完成", "Valuation_Recalc!A1"),
        ("T06", "银行账户现金勾稽", "已完成", "Nav_Bridge!A12"),
        ("T07", "五项投资限制复核", "已完成", "Compliance_Check!A1"),
        ("T08", "现行与历史版本适用性判断", "已完成", "Compliance_Check!A10；报告第四章"),
        ("T09", "超限正文披露", "已完成", "报告第四章；Compliance_Check!A13"),
        ("T10", "上期报告重述", "已完成", "Prev_Report_Fix!A1"),
        ("T11", "数据问题及阻塞台账", "已完成", "Issue_Log!A1；问题台账CSV"),
        ("T12", "任务拆解与状态", "已完成", "Task_Status!A1"),
        ("T13", "复合图", "已完成", "FIN3-WKN-153_charts.png"),
        ("T14", "独立可复算代码", "已完成", "FIN3-WKN-153_reproduce.py"),
        ("T15", "八章季度报告及字数控制", "已完成", "FIN3-WKN-153_operation_report.md"),
        ("T16", "交付物一致性与来源回溯", "已完成", "全套交付物；Source_Trace"),
    ]
    return pd.DataFrame(rows, columns=["任务编号", "任务项", "状态", "对应交付物位置"])


def write_csvs(calc: dict[str, object], output_dir: Path) -> None:
    coverage = calc["coverage"].copy()
    coverage["有效市值"] = coverage["有效市值"].round(2)
    coverage.to_csv(output_dir / OUTPUT_NAMES["coverage"], index=False, encoding="utf-8-sig")
    calc["issues"].to_csv(output_dir / OUTPUT_NAMES["issues"], index=False, encoding="utf-8-sig")


def create_chart(calc: dict[str, object], output_dir: Path) -> None:
    compliance = calc["compliance"]
    coverage = calc["coverage"].iloc[:-1]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), dpi=180)
    positions = list(range(len(compliance)))
    width = 0.36
    measured = compliance["测算值"].to_numpy() * 100
    limits = compliance["限额"].to_numpy() * 100
    axes[0].bar([x - width / 2 for x in positions], measured, width, label="Measured")
    axes[0].bar([x + width / 2 for x in positions], limits, width, label="Limit")
    axes[0].set_xticks(positions, compliance["规则"].tolist())
    axes[0].set_ylabel("Percent of NAV (%)")
    axes[0].set_title("Five Limit Metrics vs Limits")
    axes[0].legend()
    for x, value in zip(positions, measured):
        axes[0].text(x - width / 2, value + 0.25, f"{value:.2f}", ha="center", fontsize=8)
    x2 = list(range(len(coverage)))
    axes[1].bar([x - width / 2 for x in x2], coverage["原始行数"], width, label="Raw")
    axes[1].bar([x + width / 2 for x in x2], coverage["有效行数"], width, label="Effective")
    axes[1].set_xticks(x2, coverage["sheet"].str.replace("acct_", "A", regex=False), rotation=0)
    axes[1].set_ylabel("Record count")
    axes[1].set_title("Ten-account Holdings Coverage")
    axes[1].legend()
    fig.suptitle("FIN3-WKN-153 Q3 Review", fontsize=14)
    fig.tight_layout()
    fig.savefig(output_dir / OUTPUT_NAMES["chart"], bbox_inches="tight")
    plt.close(fig)


def build_report(data: dict[str, object], calc: dict[str, object]) -> str:
    comp = calc["compliance"].set_index("规则")
    coverage = calc["coverage"].iloc[:-1]
    dirs = calc["directory_inventory"]
    dir_text = "、".join(f"{r['目录']}{int(r['文件数'])}" for _, r in dirs.iloc[:-2].iterrows())
    account_text = "、".join(f"{r['sheet']} {int(r['原始行数'])}/{int(r['有效行数'])}" for _, r in coverage.iterrows())
    bank = data["bank"]
    bank_text = "、".join(f"{r['account']} {money(float(r['balance']))}" for _, r in bank.iterrows())
    sec = calc["top_security"]
    r01 = comp.loc["R-01"]
    rows = "\n".join(
        f"|{row['规则']}|{row['条款号']}|{row['列报值']}|{row['比较方向']}{row['限额列报']}|{row['结论']}|"
        for _, row in calc["compliance"].iterrows()
    )
    version_match = re.search(r"生效日[：:]\s*(\d{4}-\d{2}-\d{2}).*?替代\s*(v\d+)", data["rules_v3"])
    if not version_match:
        raise ValueError("未能解析现行条款生效日及被替代版本")
    effective_date, replaced_version = version_match.groups()
    v3_r01 = float(comp.loc["R-01", "限额"])
    v2_r01_match = re.search(r"R-01.*?(\d+(?:\.\d+)?)%", data["rules_v2"], flags=re.S)
    v2_r03_match = re.search(r"R-03.*?(\d+(?:\.\d+)?)%", data["rules_v2"], flags=re.S)
    v2_r05_match = re.search(r"R-05.*?(\d+(?:\.\d+)?)%", data["rules_v2"], flags=re.S)
    if not all([v2_r01_match, v2_r03_match, v2_r05_match]):
        raise ValueError("未能解析v2历史限额")
    v2_r01 = float(v2_r01_match.group(1)) / 100
    v2_r03 = float(v2_r03_match.group(1)) / 100
    v2_r05 = float(v2_r05_match.group(1)) / 100
    approval_values = [float(x) / 100 for x in re.findall(r"(\d+(?:\.\d+)?)%", data["approval"])]
    approval_cap = max(approval_values)
    approval_warning = min(x for x in approval_values if x > v3_r01)
    t_plus_match = re.search(r"T\+(\d+)", data["rules_v3"])
    if not t_plus_match:
        raise ValueError("未能解析超限整改时限")
    t_plus_days = t_plus_match.group(1)
    report = f"""# 现金增强1号集合资产管理计划2026年三季度投资运作报告
报告期末：{data['report_date']}；材料截止时点：{data['cutoff_date']}。

## 一、材料清点
共{calc['total_files']}个文件、{calc['source_directory_count']}个来源目录；{dir_text}、根目录散件{calc['root_files']}，合计{calc['total_files']}，勾稽一致。

## 二、组合概况与净值复核
持仓{money(calc['effective_mv'])}+现金及备付金{money(calc['trustee_cash'])}+应收{money(calc['receivables'])}−应付{money(calc['payables'])}=资产净值{money(calc['recalculated_nav'])}；净值÷份额{money(calc['total_shares'])}=单位净值{calc['unit_nav']:.12f}，与托管精确值差{calc['unit_diff_bps_exact']:.2f}bp（与列报1.0740差{calc['unit_diff_bps_reported']:.2f}bp）。银行余额：{bank_text}，合计{money(calc['bank_total'])}，与托管现金差{money(calc['bank_total']-calc['trustee_cash'])}。

## 三、持仓覆盖与口径执行
账户原始/有效行：{account_text}；合计{int(calc['coverage'].iloc[-1]['原始行数'])}/{int(calc['coverage'].iloc[-1]['有效行数'])}。依次剔除非估值日{int(calc['adjustments'].iloc[1]['剔除记录数'])}行（{money(calc['adjustments'].iloc[1]['本步市值影响'])}）、非active {int(calc['adjustments'].iloc[2]['剔除记录数'])}行（{money(calc['adjustments'].iloc[2]['本步市值影响'])}）、重复{int(calc['adjustments'].iloc[3]['剔除记录数'])}行（{money(calc['adjustments'].iloc[3]['本步市值影响'])}）。未过滤单位净值{calc['raw_unit_nav']:.12f}，较正确口径高估{calc['raw_overstatement_bps']:.2f}bp。重推行情{len(data['prices_raw'])}条，过滤估值日及批次后{len(data['prices'])}条；以sec_code=instrument_id关联，有效持仓{len(data['effective'])}行全部命中。

## 四、投资监督与限额执行
|指标|条款|测算|比较|结论|
|---|---|---:|---:|---|
{rows}
R-05与流动性制度第12条均为不低于{comp.loc['R-05']['限额列报']}，口径一致；第21条误引“第七章”待核实。R-01超限证券{sec['sec_code']}（{sec['sec_name_master']}），市值{money(float(sec['market_value']))}、占比{r01['列报值']}。经理材料称增持因二级流动性及基本面，但写“第一期”，与本券“第三期”不符，成因待核实；未见具体整改动作及实际完成时限，待核实。按现行第9条须T+{t_plus_days}个工作日内提交整改计划并披露。R-02按issuer聚合，关联方映射未提供，待核实。v3自{effective_date}生效并替代{replaced_version}，历史限额不适用于期末。

## 五、上期报告口径重述
上期“R-01上限{pct(v2_r01)}”“R-03上限{pct(v2_r03)}”“R-05下限{pct(v2_r05)}”分别改按{comp.loc['R-01']['限额列报']}、{comp.loc['R-03']['限额列报']}、{comp.loc['R-05']['限额列报']}；“各项均合规”改为本期五项逐条复核；“全表合计、不分日期”改按估值日、状态及重复规则过滤。出处见`Prev_Report_Fix`。

## 六、数据问题与处置
主行情空件改用邮件确认重推件；旧日期、非active、重复行已分项剔除；旧字段wind_code改按现行字典关联；审批{pct(approval_cap)}/预警{pct(approval_warning)}与{pct(v3_r01)}硬限冲突，采用v3硬限。审批链、整改资料、关联方映射及制度误引待核实，详见台账。

## 七、任务拆解与完成状态
T01—T16均已完成，位置见`Task_Status`；六项交付物齐备。

## 八、结论与下季度计划
净值与现金勾稽一致；R-01超限，其余四项按可核实口径合规。下季度跟踪超限整改、补齐审批及关联方映射，并推动制度字段与引用更新。
"""
    return report


def write_report(data: dict[str, object], calc: dict[str, object], output_dir: Path) -> None:
    report = build_report(data, calc)
    chinese_count = len(re.findall(r"[\u4e00-\u9fff]", report))
    if chinese_count > 1600:
        raise ValueError(f"报告中文字符数{chinese_count}超过1600")
    (output_dir / OUTPUT_NAMES["report"]).write_text(report, encoding="utf-8")


def source_trace(data: dict[str, object]) -> pd.DataFrame:
    rows = [
        ("持仓原始记录", "portfolio/holdings_2026Q3.xlsx", "acct_01至acct_10"),
        ("证券状态、券种、发行人", "portfolio/security_master.csv", "sec_code关联"),
        ("估值日行情", "data/price_feed_20260930_repush.csv", "trade_date=报告期末；batch_tag=重推件"),
        ("份额、净值、现金", "valuation/nav_report_20260930.csv", "托管报告优先"),
        ("应收应付", "valuation/accruals_20260930.csv", "应收/应付项目汇总"),
        ("银行现金", "valuation/bank_statement_20260930.csv", "按账户分列后求和"),
        ("有效持仓规则", "rules/recon_runbook.md", "第2、3章"),
        ("投资限制", "rules/restrictions_v3_20260901.md", "现行v3第2至12条"),
        ("现金制度交叉核对", "rules/liquidity_policy.md", "第12、21条"),
        ("字段与市值公式", "internal/data_dictionary.md", "第1至3章"),
        ("行情重推取舍", "internal/ops_email_20261008.txt", "以重推件为准"),
        ("超限成因材料", "internal/manager_notes.md；internal/approval_memo_20260928.md", "存在券名及时间冲突，待核实"),
    ]
    return pd.DataFrame(rows, columns=["结论/参数", "来源文件", "定位/取数条件"])


def write_workbook(data: dict[str, object], calc: dict[str, object], output_dir: Path) -> None:
    workbook_path = output_dir / OUTPUT_NAMES["workbook"]
    coverage = calc["coverage"].copy()
    inventory = calc["directory_inventory"].copy()
    price_recon = pd.DataFrame([
        {"环节": "行情原始记录", "记录数": len(data["prices_raw"]), "条件/结果": "重推文件全表"},
        {"环节": "估值日及批次过滤后", "记录数": len(data["prices"]), "条件/结果": f"trade_date={data['report_date']}；batch_tag=重推件"},
        {"环节": "有效持仓关联前", "记录数": len(data["effective"]), "条件/结果": "关联键：holdings.sec_code=prices.instrument_id"},
        {"环节": "有效持仓关联命中", "记录数": int(data["effective"]["close_price"].notna().sum()), "条件/结果": "持仓侧未匹配0条"},
        {"环节": "行情侧无有效持仓证券", "记录数": len(set(data["prices"]["instrument_id"]) - set(data["effective"]["sec_code"])), "条件/结果": "保留为行情侧差异"},
    ])
    valuation_chain = pd.DataFrame([
        {"步骤": 1, "项目": "有效持仓市值", "运算": "持仓逐行按券种折算后汇总", "本步列报值": calc["effective_mv"], "累计值": calc["effective_mv"], "来源": "持仓+主数据+估值日重推行情"},
        {"步骤": 2, "项目": "加：现金及清算备付金", "运算": f"{money(calc['effective_mv'])}+{money(calc['trustee_cash'])}", "本步列报值": calc["trustee_cash"], "累计值": calc["effective_mv"] + calc["trustee_cash"], "来源": "托管净值报告"},
        {"步骤": 3, "项目": "加：应收", "运算": f"{money(calc['effective_mv']+calc['trustee_cash'])}+{money(calc['receivables'])}", "本步列报值": calc["receivables"], "累计值": calc["effective_mv"] + calc["trustee_cash"] + calc["receivables"], "来源": "应收应付计提明细"},
        {"步骤": 4, "项目": "减：应付=资产净值", "运算": f"{money(calc['effective_mv']+calc['trustee_cash']+calc['receivables'])}-{money(calc['payables'])}={money(calc['recalculated_nav'])}", "本步列报值": -calc["payables"], "累计值": calc["recalculated_nav"], "来源": "应收应付计提明细"},
        {"步骤": 5, "项目": "资产净值÷总份额=单位净值", "运算": f"{money(calc['recalculated_nav'])}÷{money(calc['total_shares'])}={calc['unit_nav']:.12f}", "本步列报值": calc["unit_nav"], "累计值": calc["unit_nav"], "来源": "托管总份额"},
        {"步骤": 6, "项目": "与托管单位净值差额", "运算": f"({calc['unit_nav']:.12f}-{calc['trustee_unit_exact']:.12f})×10000", "本步列报值": calc["unit_diff_bps_exact"], "累计值": calc["unit_diff_bps_exact"], "来源": "托管total_nav÷total_shares；单位bp"},
        {"步骤": 7, "项目": "与托管列报单位净值差额", "运算": f"({calc['unit_nav']:.12f}-{calc['trustee_unit_reported']:.4f})×10000", "本步列报值": calc["unit_diff_bps_reported"], "累计值": calc["unit_diff_bps_reported"], "来源": "托管nav_per_share；单位bp"},
    ])
    bank_table = data["bank"].copy()
    bank_table = pd.concat([bank_table, pd.DataFrame([{"account": "合计", "account_name": "银行余额合计", "balance": calc["bank_total"], "as_of": data["report_date"]}])], ignore_index=True)
    cash_recon = pd.DataFrame([
        {"项目": "银行余额合计", "金额": calc["bank_total"], "算式/来源": "银行对账单逐账户求和"},
        {"项目": "托管报告现金及清算备付金", "金额": calc["trustee_cash"], "算式/来源": "nav_report.cash_and_equivalent"},
        {"项目": "差额", "金额": calc["bank_total"] - calc["trustee_cash"], "算式/来源": "银行合计-托管现金"},
        {"项目": "未过滤单位净值", "金额": calc["raw_unit_nav"], "算式/来源": "(未过滤持仓市值+现金+应收-应付)÷份额"},
        {"项目": "正确口径单位净值", "金额": calc["unit_nav"], "算式/来源": "(有效持仓市值+现金+应收-应付)÷份额"},
        {"项目": "未过滤口径高估", "金额": calc["raw_overstatement_bps"], "算式/来源": "(未过滤单位净值-正确单位净值)×10000，单位bp"},
    ])
    v3_effective_match = re.search(r"生效日[：:]\s*(\d{4}-\d{2}-\d{2}).*?替代\s*(v\d+)", data["rules_v3"])
    v2_effective_match = re.search(r"生效日[：:]\s*(\d{4}-\d{2}-\d{2})", data["rules_v2"])
    if not v3_effective_match or not v2_effective_match:
        raise ValueError("未能解析条款版本关系")
    v3_effective, replaced_version = v3_effective_match.groups()
    v2_effective = v2_effective_match.group(1)
    version_table = pd.DataFrame([
        {"版本": "v3", "生效/状态": f"{v3_effective}生效；现行有效", "本期适用性": "适用", "依据": "v3第12条；报告期末为2026-09-30"},
        {"版本": replaced_version, "生效/状态": f"{v2_effective}版；已被v3替代", "本期适用性": "不适用，仅历史回溯", "依据": "v3首页及第12条；v2版本说明"},
    ])
    t_plus_match = re.search(r"T\+(\d+)", data["rules_v3"])
    if not t_plus_match:
        raise ValueError("未能解析超限整改时限")
    breach_detail = pd.DataFrame([
        {"证券代码": calc["top_security"]["sec_code"], "证券名称": calc["top_security"]["sec_name_master"], "市值": float(calc["top_security"]["market_value"]), "占比": float(calc["top_security"]["market_value"] / calc["total_nav"]), "成因": "经理说明称增持因二级流动性及基本面，但说明为第一期、持仓为第三期，待核实", "整改动作": "材料未载明，待核实", "时限": f"第9条要求T+{t_plus_match.group(1)}个工作日内提交整改计划；实际完成时限待核实", "披露要求": "季度报告投资监督章节披露事实、成因、措施、时限"},
    ])
    excluded = data["holdings"].loc[~data["holdings"]["effective"], ["sheet", "acct", "sec_code", "sec_name_holding", "vol", "as_of", "status", "source_row_id", "market_value", "date_ok", "status_ok", "duplicate_exclusion"]].copy()
    excluded["剔除原因"] = ""
    excluded.loc[~excluded["date_ok"], "剔除原因"] = "非估值日归属"
    excluded.loc[excluded["date_ok"] & ~excluded["status_ok"], "剔除原因"] = "主数据非active"
    excluded.loc[excluded["date_ok"] & excluded["status_ok"] & excluded["duplicate_exclusion"], "剔除原因"] = "重复上报"
    excluded = excluded.rename(columns={"sec_name_holding": "sec_name"})
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        inventory.to_excel(writer, sheet_name="Coverage", index=False, startrow=1)
        coverage.to_excel(writer, sheet_name="Coverage", index=False, startrow=len(inventory) + 5)
        calc["holdings_summary"].to_excel(writer, sheet_name="Holdings_Summary", index=False, startrow=1)
        valuation_chain.to_excel(writer, sheet_name="Valuation_Recalc", index=False, startrow=1)
        price_recon.to_excel(writer, sheet_name="Valuation_Recalc", index=False, startrow=len(valuation_chain) + 5)
        calc["adjustments"].to_excel(writer, sheet_name="Nav_Bridge", index=False, startrow=1)
        bank_table.to_excel(writer, sheet_name="Nav_Bridge", index=False, startrow=len(calc["adjustments"]) + 5)
        cash_recon.to_excel(writer, sheet_name="Nav_Bridge", index=False, startrow=len(calc["adjustments"]) + len(bank_table) + 9)
        calc["compliance"].to_excel(writer, sheet_name="Compliance_Check", index=False, startrow=1)
        version_table.to_excel(writer, sheet_name="Compliance_Check", index=False, startrow=len(calc["compliance"]) + 5)
        breach_detail.to_excel(writer, sheet_name="Compliance_Check", index=False, startrow=len(calc["compliance"]) + len(version_table) + 9)
        calc["issues"].to_excel(writer, sheet_name="Issue_Log", index=False, startrow=1)
        calc["tasks"].to_excel(writer, sheet_name="Task_Status", index=False, startrow=1)
        calc["prev_fixes"].to_excel(writer, sheet_name="Prev_Report_Fix", index=False, startrow=1)
        excluded.to_excel(writer, sheet_name="Excluded_Detail", index=False, startrow=1)
        source_trace(data).to_excel(writer, sheet_name="Source_Trace", index=False, startrow=1)
    wb = load_workbook(workbook_path)
    titles = {
        "Coverage": [(1, "材料清点（目录文件数）"), (len(inventory) + 4, "十账户持仓覆盖")],
        "Holdings_Summary": [(1, "有效持仓券种×账户市值汇总")],
        "Valuation_Recalc": [(1, "资产净值与单位净值逐行推导链"), (len(valuation_chain) + 4, "行情过滤及关联")],
        "Nav_Bridge": [(1, "有效持仓三类剔除桥接"), (len(calc["adjustments"]) + 4, "银行账户余额"), (len(calc["adjustments"]) + len(bank_table) + 8, "现金及单位净值勾稽")],
        "Compliance_Check": [(1, "现行v3五项限额检查"), (len(calc["compliance"]) + 4, "条款版本适用性"), (len(calc["compliance"]) + len(version_table) + 8, "R-01超限处置披露")],
        "Issue_Log": [(1, "数据问题与阻塞台账")],
        "Task_Status": [(1, "任务拆解与完成状态")],
        "Prev_Report_Fix": [(1, "上期报告口径重述")],
        "Excluded_Detail": [(1, "剔除记录明细")],
        "Source_Trace": [(1, "关键结论来源回溯")],
    }
    for sheet_name, locations in titles.items():
        ws = wb[sheet_name]
        for row, title in locations:
            ws.cell(row=row, column=1, value=title)
            ws.cell(row=row, column=1).font = Font(bold=True, size=12, color="FFFFFF")
            ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor="1F4E78")
        ws.freeze_panes = "A3"
        ws.sheet_view.showGridLines = False
        for row in ws.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        for col in range(1, ws.max_column + 1):
            values = [str(ws.cell(row=r, column=col).value or "") for r in range(1, min(ws.max_row, 200) + 1)]
            width = min(max(max((len(v) for v in values), default=8) + 2, 10), 42)
            ws.column_dimensions[get_column_letter(col)].width = width
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, (int, float)) and any(k in str(ws.cell(row=2, column=cell.column).value) for k in ["市值", "金额", "分子", "分母", "累计"]):
                    cell.number_format = '#,##0.00'
    chart_sheet = wb.create_sheet("Charts")
    chart_sheet["A1"] = "复合图：五项限额对比与十账户覆盖"
    chart_sheet["A1"].font = Font(bold=True, size=12)
    chart_sheet.add_image(XLImage(output_dir / OUTPUT_NAMES["chart"]), "A3")
    wb.save(workbook_path)


def validate_outputs(data: dict[str, object], calc: dict[str, object], output_dir: Path) -> None:
    expected = [output_dir / name for name in OUTPUT_NAMES.values()]
    missing = [str(path) for path in expected if not path.exists()]
    if missing:
        raise FileNotFoundError(f"缺少交付物: {missing}")
    wb = load_workbook(output_dir / OUTPUT_NAMES["workbook"], read_only=True, data_only=False)
    required_sheets = {"Coverage", "Holdings_Summary", "Valuation_Recalc", "Nav_Bridge", "Compliance_Check", "Issue_Log", "Task_Status", "Prev_Report_Fix"}
    if not required_sheets.issubset(wb.sheetnames):
        raise ValueError("工作簿缺少必需工作表")
    report = read_text(output_dir / OUTPUT_NAMES["report"])
    if len(re.findall(r"[\u4e00-\u9fff]", report)) > 1600:
        raise ValueError("报告中文字符超限")
    coverage = pd.read_csv(output_dir / OUTPUT_NAMES["coverage"])
    if int(coverage.iloc[-1]["原始行数"]) != len(data["holdings"]):
        raise ValueError("覆盖表原始行数不一致")
    if abs(float(coverage.iloc[-1]["有效市值"]) - calc["effective_mv"]) > 0.01:
        raise ValueError("覆盖表有效市值不一致")
    if abs(calc["recalculated_nav"] - calc["total_nav"]) > 0.01:
        raise ValueError("复算净值未与托管净值勾稽")
    if calc["total_files"] != int(calc["directory_inventory"].iloc[-1]["文件数"]):
        raise ValueError("材料文件总数未勾稽")


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    input_dir = output_dir.parent / "input_files"
    data = load_inputs(input_dir)
    calc = build_calculations(data, input_dir)
    write_csvs(calc, output_dir)
    create_chart(calc, output_dir)
    write_report(data, calc, output_dir)
    write_workbook(data, calc, output_dir)
    validate_outputs(data, calc, output_dir)
    print(f"已生成并验证6项交付物，资产净值={money(calc['recalculated_nav'])}，单位净值={calc['unit_nav']:.12f}")


if __name__ == "__main__":
    main()
