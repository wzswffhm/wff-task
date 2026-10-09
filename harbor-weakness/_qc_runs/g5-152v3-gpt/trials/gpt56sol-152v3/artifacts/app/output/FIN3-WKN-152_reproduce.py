#!/usr/bin/env python3
"""Reproduce the Reddit IPO pre-pricing review from the supplied materials pack."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUTPUT_DIR = Path(__file__).resolve().parent
INPUT_DIR = OUTPUT_DIR.parent / "input_files"
PREFIX = "FIN3-WKN-152"


def read_csv(relative_path: str) -> list[dict[str, str]]:
    with (INPUT_DIR / relative_path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sheet_rows(relative_path: str, sheet_name: str) -> list[dict]:
    workbook = load_workbook(INPUT_DIR / relative_path, data_only=True, read_only=True)
    worksheet = workbook[sheet_name]
    rows = list(worksheet.iter_rows(values_only=True))
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:] if any(value is not None for value in row)]


def find_row(rows: list[dict], field: str, value) -> dict:
    return next(row for row in rows if row[field] == value)


def amount(rows: list[dict], field: str, value, amount_field: str) -> float:
    return float(find_row(rows, field, value)[amount_field])


def money(value: float) -> str:
    return f"{value:,.3f}"


def price(value: float) -> str:
    return f"${value:,.2f}"


def load_inputs() -> dict:
    public = sheet_rows("sec_filings/SEC-01_financials_extract.xlsx", "Public_Financials")
    assumptions = sheet_rows("committee/Underwriting_Assumptions_20240320.xlsx", "Assumptions")
    committee_terms = sheet_rows("committee/Offering_Terms_20240320.xlsx", "Offering_Terms")
    sec_terms = sheet_rows("sec_filings/SEC-03_offering_terms.xlsx", "Offering_Terms")
    dilution = sheet_rows("sec_filings/SEC-02_dilution_crosscheck.xlsx", "Dilution_Crosscheck")
    cap_table = read_csv("sec_filings/SEC-09_capitalization.csv")

    def public_value(metric: str, year: str = "2023A") -> float:
        return float(find_row(public, "Metric", metric)[year])

    def assumption_value(name: str) -> float:
        return float(find_row(assumptions, "Assumption", name)["Value"])

    def committee_term(item: str, scenario: str = "Base Offering"):
        return find_row(committee_terms, "Item", item)[scenario]

    def sec_term(item: str) -> float:
        return float(find_row(sec_terms, "Item", item)["Value"])

    return {
        "revenue_2022": public_value("Revenue", "2022A"),
        "revenue_2023": public_value("Revenue"),
        "net_loss_2023": public_value("Net income (loss)"),
        "management_ebitda_2023": public_value("Adjusted EBITDA"),
        "sbc_2023": public_value("Stock-based compensation & related taxes"),
        "restructuring_2023": public_value("Restructuring costs"),
        "fcf_2023": public_value("Free Cash Flow"),
        "cash_2023": public_value("Cash & cash equivalents"),
        "securities_2023": public_value("Marketable securities"),
        "growth": assumption_value("2024E revenue growth"),
        "multiple_low": assumption_value("Peer low EV/Revenue"),
        "multiple_mid": assumption_value("Peer midpoint EV/Revenue"),
        "multiple_high": assumption_value("Peer high EV/Revenue"),
        "discount": assumption_value("IPO discount to peer-implied equity"),
        "proposed_price": float(committee_term("Proposed Committee Price")),
        "primary_base": sec_term("Primary shares offered (base)"),
        "secondary_base": sec_term("Secondary shares offered (base)"),
        "greenshoe": sec_term("Over-allotment option"),
        "filing_low": sec_term("Preliminary public filing range low"),
        "filing_high": sec_term("Preliminary public filing range high"),
        "fee_rate": float(committee_term("Underwriting fee assumption")),
        "fixed_expenses": float(committee_term("Fixed company offering expenses")),
        "pre_money_shares": sum(float(row["shares_mm"]) for row in cap_table),
        "ntbv_assumed_price": float(find_row(dilution, "Item", "Preliminary NTBV/share")["Assumed price"]),
        "ntbv_per_share": float(find_row(dilution, "Item", "Preliminary NTBV/share")["Value"]),
        "sec_dilution": float(find_row(dilution, "Item", "Preliminary immediate dilution per share")["Value"]),
    }


def calculate(values: dict) -> dict:
    result = dict(values)
    result["underwriting_ebitda"] = values["management_ebitda_2023"] - values["sbc_2023"]
    result["net_cash"] = values["cash_2023"] + values["securities_2023"]
    result["revenue_2024"] = values["revenue_2023"] * (1 + values["growth"])
    result["management_margin"] = values["management_ebitda_2023"] / values["revenue_2023"]
    result["underwriting_margin"] = result["underwriting_ebitda"] / values["revenue_2023"]
    result["fcf_margin"] = values["fcf_2023"] / values["revenue_2023"]
    valuations = []
    for label, multiple in (("Low", values["multiple_low"]), ("Mid", values["multiple_mid"]), ("High", values["multiple_high"])):
        enterprise_value = result["revenue_2024"] * multiple
        equity_value = enterprise_value + result["net_cash"]
        undiscounted = equity_value / values["pre_money_shares"]
        valuations.append({
            "case": label,
            "multiple": multiple,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "undiscounted_per_share": undiscounted,
            "supported_per_share": undiscounted * (1 - values["discount"]),
        })
    result["valuations"] = valuations
    result["supported_low"] = valuations[0]["supported_per_share"]
    result["supported_mid"] = valuations[1]["supported_per_share"]
    result["supported_high"] = valuations[2]["supported_per_share"]
    result["distance_to_mid"] = abs(values["proposed_price"] - result["supported_mid"])
    result["primary_full"] = values["primary_base"] + values["greenshoe"]
    result["offered_base"] = values["primary_base"] + values["secondary_base"]
    result["offered_full"] = result["primary_full"] + values["secondary_base"]
    result["base_gross"] = values["primary_base"] * values["proposed_price"]
    result["base_fee"] = result["base_gross"] * values["fee_rate"]
    result["base_net"] = result["base_gross"] - result["base_fee"] - values["fixed_expenses"]
    result["secondary_gross"] = values["secondary_base"] * values["proposed_price"]
    result["full_gross"] = result["primary_full"] * values["proposed_price"]
    result["full_fee"] = result["full_gross"] * values["fee_rate"]
    result["full_net"] = result["full_gross"] - result["full_fee"] - values["fixed_expenses"]
    result["post_shares_base"] = values["pre_money_shares"] + values["primary_base"]
    result["post_shares_full"] = values["pre_money_shares"] + result["primary_full"]
    result["new_share_pct_base"] = values["primary_base"] / result["post_shares_base"]
    result["new_share_pct_full"] = result["primary_full"] / result["post_shares_full"]
    result["ntbv_check"] = values["ntbv_assumed_price"] - values["ntbv_per_share"]
    in_range = result["supported_low"] <= values["proposed_price"] <= result["supported_high"]
    result["recommendation"] = "Proceed" if in_range and result["distance_to_mid"] <= 0.50 else ("Reprice" if in_range else "Defer")
    return result


def audit_financial_details(values: dict) -> list[dict[str, str]]:
    anomalies = []
    priorities = {row["Source_ID"]: int(row["Priority"]) for row in read_csv("sec_filings/Source_Index.csv")}
    monthly = read_csv("financials/monthly_revenue_2022_2023.csv")
    seen = {}
    for line_no, row in enumerate(monthly, start=2):
        key = (row["fy"], row["month"], row["revenue_usd_mm"], row["Source_ID"])
        if key in seen:
            anomalies.append({"category": "明细异常-重复记录", "file_location": f"financials/monthly_revenue_2022_2023.csv:{line_no}", "issue": f"{row['month']} 与第 {seen[key]} 行同月、同源、同值重复；原始 FY2022 合计超过 SEC 年度数。", "basis": "完全重复记录去重；SEC-01 年度收入为控制数。", "resolution": f"排除第 {line_no} 行 {row['revenue_usd_mm']}；去重后 FY2022={money(values['revenue_2022'])}。", "impact": f"避免收入高估 {row['revenue_usd_mm']}。", "status": "已修正"})
        else:
            seen[key] = line_no
    month_groups = {}
    for line_no, row in enumerate(monthly, start=2):
        month_groups.setdefault((row["fy"], row["month"]), []).append((line_no, row))
    for (_, month), records in month_groups.items():
        if len({record[1]["revenue_usd_mm"] for record in records}) > 1:
            selected = min(records, key=lambda record: priorities.get(record[1]["Source_ID"], 999))
            rejected = [record for record in records if record != selected]
            anomalies.append({"category": "明细异常-同月多值", "file_location": ", ".join(f"financials/monthly_revenue_2022_2023.csv:{r[0]}" for r in records), "issue": f"{month} 同月存在 " + " / ".join(f"{r[1]['revenue_usd_mm']}({r[1]['Source_ID']})" for r in records) + "。", "basis": "CP-02 按 Source_Index Priority 升序取值；委员会邮件明确排除 IR preliminary 残留。", "resolution": f"采用 {selected[1]['revenue_usd_mm']}({selected[1]['Source_ID']})；排除 " + ", ".join(f"{r[1]['revenue_usd_mm']}({r[1]['Source_ID']})" for r in rejected) + f"；FY2023={money(values['revenue_2023'])}。", "impact": "避免低优先级草稿污染审计年度收入。", "status": "已修正"})
    segments = read_csv("financials/revenue_by_segment_2022_2023.csv")
    advertising = next(float(row["revenue_usd_mm"]) for row in segments if row["fy"] == "FY2023" and row["segment"] == "Advertising")
    other_line, other_row = next((line, row) for line, row in enumerate(segments, start=2) if row["fy"] == "FY2023" and row["segment"] == "Other")
    expected_other = values["revenue_2023"] - advertising
    if not math.isclose(float(other_row["revenue_usd_mm"]), expected_other, abs_tol=1e-9):
        anomalies.append({"category": "明细异常-量级错位", "file_location": f"financials/revenue_by_segment_2022_2023.csv:{other_line}", "issue": f"FY2023 Other={other_row['revenue_usd_mm']}，与 SEC-01 的 {expected_other:.3f} 不符；分部合计不等于年度收入。", "basis": "SEC-01 审计年度数及分部披露优先于待复核明细。", "resolution": f"采用 SEC-01 Other={expected_other:.3f}；分部合计={money(values['revenue_2023'])}。", "impact": f"纠正 Other 收入高估 {float(other_row['revenue_usd_mm']) - expected_other:.3f}。", "status": "已修正"})
    sbc = read_csv("financials/sbc_detail_2022_2023.csv")
    sbc_2023 = [(line, row) for line, row in enumerate(sbc, start=2) if row["fy"] == "FY2023"]
    detail_sum = sum(float(row["amount_usd_mm"]) for _, row in sbc_2023 if row["component"] != "TOTAL")
    total_line, total_row = next((line, row) for line, row in sbc_2023 if row["component"] == "TOTAL")
    if not math.isclose(float(total_row["amount_usd_mm"]), detail_sum, abs_tol=1e-9):
        anomalies.append({"category": "明细异常-错误总计", "file_location": f"financials/sbc_detail_2022_2023.csv:{total_line}", "issue": f"TOTAL={total_row['amount_usd_mm']}，四项组成合计及 SEC-01 均为 {detail_sum:.3f}。", "basis": "组成项交叉加总并与 SEC-01 年度数勾稽。", "resolution": f"TOTAL 改按 {detail_sum:.3f} 使用，且总计行不与组成项再次相加。", "impact": f"纠正总计高估 {float(total_row['amount_usd_mm']) - detail_sum:.3f}。", "status": "已修正"})
    restructuring = read_csv("financials/restructuring_detail_2023.csv")
    restructuring_details = sum(float(row["amount_usd_mm"]) for row in restructuring if row["component"] != "TOTAL")
    restructuring_total = amount(restructuring, "component", "TOTAL", "amount_usd_mm")
    anomalies.append({"category": "明细异常-小计重复风险", "file_location": "financials/restructuring_detail_2023.csv:5", "issue": f"TOTAL={restructuring_total:.3f} 与组成项并列；全行求和会错误得到 {(restructuring_details + restructuring_total):.3f}。", "basis": "TOTAL 为小计；组成项合计与 SEC-01 年度数一致。", "resolution": f"采用 TOTAL={restructuring_total:.3f}，不重复汇总；CP-04 下不二次调整 EBITDA。", "impact": "避免费用和 QoE 调整重复计算。", "status": "已修正"})
    fcf = read_csv("financials/fcf_bridge_2023.csv")
    operating_cash = amount(fcf, "line_item", "Net cash used in operating activities", "amount_usd_mm")
    capex = amount(fcf, "line_item", "Purchases of property and equipment", "amount_usd_mm")
    fcf_value = amount(fcf, "line_item", "Free cash flow", "amount_usd_mm")
    anomalies.append({"category": "明细异常-结果行重复风险", "file_location": "financials/fcf_bridge_2023.csv:4", "issue": f"FCF={fcf_value:.3f} 是前两行计算结果；全行求和会错误得到 {(operating_cash + capex + fcf_value):.3f}。", "basis": "SEC-01 定义 FCF=经营现金流-资本开支；资本开支在底表以负数列示。", "resolution": f"按 {operating_cash:.3f}+({capex:.3f})={fcf_value:.3f}，结果行不再加总。", "impact": "避免 FCF 重复计算。", "status": "已修正"})
    return anomalies


def legacy_errors(values: dict) -> list[dict[str, str]]:
    candidate = sheet_rows("legacy/Candidate_Model_v0.xlsx", "Candidate_Model")
    corrected = {
        "Profitability": f"撤回 SBC 加回；Underwriting EBITDA={money(values['underwriting_ebitda'])}。",
        "Valuation": f"使用 2024E Revenue={money(values['revenue_2024'])}，并应用 {values['discount']:.1%} 折扣。",
        "Cash": f"计入现金与有价证券；净现金={money(values['net_cash'])}。",
        "Primary/Secondary": f"Base primary={values['primary_base']:.6f}；secondary={values['secondary_base']:.6f}。",
        "Greenshoe": f"Base 排除 {values['greenshoe']:.6f}；另列 full exercise。",
        "Underwriting fee": f"仅对公司 primary gross 按 {values['fee_rate']:.1%} 计提。",
        "Post-money shares": f"仅新增 primary；Base post-money={values['post_shares_base']:.6f}。",
        "Proceeds": "Secondary 所得归出售股东，公司募集资金为零。",
        "Dilution": "发行前股数加 primary 构成发行后股数；SEC-02 仅作 $32.50 独立交叉验算。",
        "Recommendation": f"按 CP-14/15；$34 对比支持区间与 midpoint，结论={values['recommendation']}。",
    }
    policies = {"Profitability": "CP-03/CP-04", "Valuation": "CP-05/CP-06/CP-09", "Cash": "CP-08", "Primary/Secondary": "CP-10", "Greenshoe": "CP-11", "Underwriting fee": "CP-12", "Post-money shares": "CP-10", "Proceeds": "CP-10", "Dilution": "CP-10；SEC-02", "Recommendation": "CP-14/CP-15"}
    errors = [{"category": f"Legacy-{row['Workstream']}", "file_location": "legacy/Candidate_Model_v0.xlsx:Candidate_Model", "issue": str(row["Legacy treatment"]), "basis": policies[row["Workstream"]], "resolution": corrected[row["Workstream"]], "impact": str(row["Review point"]), "status": "已修正"} for row in candidate]
    for row in sheet_rows("legacy/Candidate_Model_v0.xlsx", "Broken_Links"):
        errors.append({"category": "Legacy-失效引用", "file_location": f"legacy/Candidate_Model_v0.xlsx:{row['Cell']}", "issue": f"公式 {row['Formula']} 返回 {row['Value']}。", "basis": "Candidate_Model_readme 禁止沿用未解析引用；本模型从原始输入重建。", "resolution": "不沿用该单元格，改由本复算脚本和模型公式重建。", "impact": "恢复模块联动和可复算性。", "status": "已修正"})
    errors.append({"category": "来源治理-索引缺口", "file_location": "sec_filings/Source_Index.csv", "issue": "委员会文件使用的 UW-01 未列入主 Source_Index.csv。", "basis": "不得虚构 Source_ID；委员会文件本身为控制口径。", "resolution": "关键内部假设直接追溯至委员会文件，并将 Source_ID 链接标注为待核实；未改动输入索引。", "impact": "不影响数值计算，但正式归档前应补齐索引治理。", "status": "待核实（非数值差异）"})
    return errors


def build_source_trace(values: dict) -> list[dict[str, str]]:
    note = "内部委员会假设；委员会文件中的 UW-01 未列入主 Source_Index.csv，索引链接待核实"
    return [
        {"metric": "2023A Revenue", "classification": "SEC 公开事实", "selected_value": money(values["revenue_2023"]), "unit": "USD mm", "selected_source": "SEC-01_financials_extract.xlsx/Public_Financials; SEC-01", "competing_value_source": "806.200 / management_flash_20240319.csv; INT-01", "disposition": "Priority 1 SEC-01；排除 Priority 9 未审核 flash"},
        {"metric": "2023 Net loss", "classification": "SEC 公开事实", "selected_value": money(values["net_loss_2023"]), "unit": "USD mm", "selected_source": "SEC-01; Public_Financials", "competing_value_source": "无", "disposition": "采用 SEC-01"},
        {"metric": "Management Adjusted EBITDA", "classification": "SEC 披露非GAAP事实", "selected_value": money(values["management_ebitda_2023"]), "unit": "USD mm", "selected_source": "SEC-01; Public_Financials", "competing_value_source": "-66.100 / INT-01", "disposition": "采用 SEC-01；非审计指标仅作桥起点"},
        {"metric": "SBC and related taxes", "classification": "SEC 公开事实", "selected_value": money(values["sbc_2023"]), "unit": "USD mm", "selected_source": "SEC-01; Public_Financials", "competing_value_source": "49.680 / sbc_detail TOTAL；47.300 / INT-01", "disposition": "组成项与 SEC-01 均为 49.086；排除错误总计及 flash"},
        {"metric": "Underwriting EBITDA", "classification": "内部承销口径计算", "selected_value": money(values["underwriting_ebitda"]), "unit": "USD mm", "selected_source": "SEC-01 + Committee Policy v3 CP-03", "competing_value_source": f"{money(values['management_ebitda_2023'])} / legacy", "disposition": "撤回持续性 SBC 加回；restructuring 不重复处理"},
        {"metric": "Free Cash Flow", "classification": "SEC 公开事实", "selected_value": money(values["fcf_2023"]), "unit": "USD mm", "selected_source": "SEC-01", "competing_value_source": "-82.400 / INT-01", "disposition": "采用 SEC-01；结果行不重复汇总"},
        {"metric": "Year-end cash", "classification": "SEC 公开事实", "selected_value": money(values["cash_2023"]), "unit": "USD mm", "selected_source": "SEC-01", "competing_value_source": "无", "disposition": "采用 SEC-01"},
        {"metric": "Marketable securities", "classification": "SEC 公开事实", "selected_value": money(values["securities_2023"]), "unit": "USD mm", "selected_source": "SEC-01", "competing_value_source": "legacy 漏计", "disposition": "CP-08 要求完整计入"},
        {"metric": "2024E Revenue growth", "classification": "内部委员会假设", "selected_value": f"{values['growth']:.1%}", "unit": "%", "selected_source": "Committee Policy v3 CP-06", "competing_value_source": "18% / sector_benchmark.md（背景）", "disposition": f"采用委员会控制假设；{note}"},
        {"metric": "2024E Revenue", "classification": "内部假设推导", "selected_value": money(values["revenue_2024"]), "unit": "USD mm", "selected_source": "SEC-01 2023A × CP-06", "competing_value_source": "legacy 使用 2023A", "disposition": "按 804.029×(1+22%) 计算"},
        {"metric": "Peer multiple range", "classification": "内部委员会假设", "selected_value": f"{values['multiple_low']:.1f}x-{values['multiple_high']:.1f}x; mid {values['multiple_mid']:.1f}x", "unit": "x", "selected_source": "Committee Policy v3 CP-07", "competing_value_source": "v2 3.5x-5.5x；BANK-B 4.2x-5.1x", "disposition": f"v3 取代 v2；bank comps 仅交叉验证；{note}"},
        {"metric": "Execution discount", "classification": "内部委员会假设", "selected_value": f"{values['discount']:.1%}", "unit": "%", "selected_source": "Committee Policy v3 CP-09", "competing_value_source": "v2 10%；legacy 0%", "disposition": f"按 v3 应用于 peer-implied equity/share；{note}"},
        {"metric": "Pre-money economic shares", "classification": "SEC 事实推导/委员会快照", "selected_value": f"{values['pre_money_shares']:.6f}", "unit": "mm shares", "selected_source": "SEC-09_capitalization.csv 各类别合计; SEC-09", "competing_value_source": "141.200 / SEC-16 registered shares", "disposition": "采用 economic fully diluted；registered shares 口径不同"},
        {"metric": "Proposed price", "classification": "内部委员会假设", "selected_value": price(values["proposed_price"]), "unit": "USD/share", "selected_source": "Offering_Terms_20240320.xlsx", "competing_value_source": f"公开申报区间 {price(values['filing_low'])}-{price(values['filing_high'])}; SEC-03", "disposition": f"决策输入，非最终定价；{note}"},
        {"metric": "Primary / Secondary / Greenshoe", "classification": "SEC 公开事实", "selected_value": f"{values['primary_base']:.6f} / {values['secondary_base']:.6f} / {values['greenshoe']:.6f}", "unit": "mm shares", "selected_source": "SEC-03_offering_terms.xlsx; SEC-03", "competing_value_source": "legacy 将 22.0 全部视为 primary 且并入 greenshoe", "disposition": "按 CP-10/11 重建；Base 排除 greenshoe"},
        {"metric": "Underwriting fee / fixed expenses", "classification": "内部委员会假设", "selected_value": f"{values['fee_rate']:.1%} / {money(values['fixed_expenses'])}", "unit": "% / USD mm", "selected_source": "Committee Policy v3 CP-12", "competing_value_source": "v2 按全部股份收费", "disposition": f"仅对 primary gross；固定费用仅一次；{note}"},
        {"metric": "SEC dilution cross-check", "classification": "SEC 公开事实", "selected_value": f"NTBV {price(values['ntbv_per_share'])}; dilution {price(values['sec_dilution'])}", "unit": "USD/share", "selected_source": "SEC-02_dilution_crosscheck.xlsx; SEC-02", "competing_value_source": "无", "disposition": f"仅适用于假定价格 {price(values['ntbv_assumed_price'])}，不外推至 $34"},
    ]


def sensitivity(values: dict):
    growths = [values["growth"] + offset * 0.02 for offset in (-2, -1, 0, 1, 2)]
    step = (values["multiple_high"] - values["multiple_low"]) / 4
    multiples = [values["multiple_low"] + index * step for index in range(5)]
    matrix = [[((values["revenue_2023"] * (1 + growth) * multiple + values["net_cash"]) / values["pre_money_shares"]) * (1 - values["discount"]) for multiple in multiples] for growth in growths]
    return growths, multiples, matrix


def write_csv_file(path: Path, headers: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def write_qoe_bridge(values: dict) -> None:
    rows = [
        {"step": 1, "item": "Management Adjusted EBITDA", "amount_usd_mm": f"{values['management_ebitda_2023']:.3f}", "treatment": "起点；管理层非 GAAP", "basis": "SEC-01/Public_Financials", "policy_id": "CP-03"},
        {"step": 2, "item": "Reverse SBC and related taxes addback", "amount_usd_mm": f"{-values['sbc_2023']:.3f}", "treatment": "SBC 为持续性经济成本，不保留加回", "basis": "SEC-01; sbc_detail 组成项", "policy_id": "CP-03"},
        {"step": 3, "item": "Restructuring costs", "amount_usd_mm": "0.000", "treatment": f"{values['restructuring_2023']:.3f} 已在管理层指标中调整，不二次加回", "basis": "SEC-01; restructuring_detail", "policy_id": "CP-04"},
        {"step": 4, "item": "Underwriting EBITDA", "amount_usd_mm": f"{values['underwriting_ebitda']:.3f}", "treatment": "承销口径结果；仍为负，采用 EV/2024E Revenue", "basis": "桥接计算", "policy_id": "CP-05"},
    ]
    write_csv_file(OUTPUT_DIR / f"{PREFIX}_qoe_bridge.csv", ["step", "item", "amount_usd_mm", "treatment", "basis", "policy_id"], rows)


def write_valuation_matrix(values: dict, growths, multiples, matrix) -> None:
    with (OUTPUT_DIR / f"{PREFIX}_valuation_matrix.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["2024E growth / EV-Revenue"] + [f"{m:.2f}x" for m in multiples] + ["row_note"])
        for growth, row in zip(growths, matrix):
            writer.writerow([f"{growth:.1%}"] + [f"{value:.4f}" for value in row] + ["BASE GROWTH" if math.isclose(growth, values["growth"]) else ""])
        writer.writerow([])
        writer.writerow(["Scenario", "Growth", "Multiple", "Supported price/share"])
        for row in values["valuations"]:
            writer.writerow([row["case"], f"{values['growth']:.1%}", f"{row['multiple']:.2f}x", f"{row['supported_per_share']:.4f}"])


def write_memo(values: dict, anomalies: list[dict]) -> None:
    anomaly_lines = "\n".join(f"- `{r['file_location']}`：{r['issue']} 依据：{r['basis']} 处置：{r['resolution']}" for r in anomalies)
    memo = f"""# Reddit, Inc. IPO Pricing Committee 备忘录

**日期：** 2024-03-20　**建议：{values['recommendation']} at {price(values['proposed_price'])}**

## 结论

现行控制口径为 `Committee_Policy_v3_20240320.xlsx`。v2 关于保留 SBC 加回、3.5x–5.5x peer 区间、10% 折扣及按全部发行股份计费的条款均已失效。按 v3，支持价格为 **{price(values['supported_low'])}–{price(values['supported_high'])}**，midpoint **{price(values['supported_mid'])}**；拟议价 {price(values['proposed_price'])} 位于区间内，较 midpoint 低 **{price(values['distance_to_mid'])}/share**，不超过 CP-14 的 $0.50 门槛。结构性错误已在本模型修复，建议 Proceed。该价格、22% 增长、倍数、折扣及 cap-table snapshot 均为内部假设，不是 SEC 已实现结果。

## 盈利质量与估值

SEC-01 的 2023A Revenue 为 **${money(values['revenue_2023'])}mm**、净亏损 **${money(values['net_loss_2023'])}mm**、管理层 Adjusted EBITDA **${money(values['management_ebitda_2023'])}mm**。按 CP-03 撤回持续性 SBC **${money(values['sbc_2023'])}mm** 后，承销口径 EBITDA 为 **${money(values['underwriting_ebitda'])}mm**；重组费 **${money(values['restructuring_2023'])}mm** 已在管理层口径调整，不重复加回。FCF **${money(values['fcf_2023'])}mm**，两项均为负，是主要 QoE 风险。故采用 EV/2024E Revenue：${money(values['revenue_2023'])}×(1+{values['growth']:.0%})=**${money(values['revenue_2024'])}mm**。净现金桥计入现金 ${money(values['cash_2023'])} 与有价证券 ${money(values['securities_2023'])}，合计 **${money(values['net_cash'])}mm**；4.0x/4.5x/5.0x 后统一折价 {values['discount']:.1%}。

## 发行结构与稀释

Base 为 primary **{values['primary_base']:.6f}mm**、secondary **{values['secondary_base']:.6f}mm**；secondary 不形成公司募集资金或新增股数。{price(values['proposed_price'])} 下公司 gross/net primary proceeds 为 **${money(values['base_gross'])}mm / ${money(values['base_net'])}mm**；承销费仅按 primary gross 的 {values['fee_rate']:.1%} 计提，固定费用 ${money(values['fixed_expenses'])}mm 仅一次。Base post-money 股数 **{values['post_shares_base']:.6f}mm**，新增占比 **{values['new_share_pct_base']:.2%}**。3.300000mm greenshoe 单列 full-exercise：net proceeds **${money(values['full_net'])}mm**，post-money **{values['post_shares_full']:.6f}mm**，新增占比 **{values['new_share_pct_full']:.2%}**。SEC-02 在假定 {price(values['ntbv_assumed_price'])} 下的 NTBV/share {price(values['ntbv_per_share'])}、即时稀释 {price(values['sec_dilution'])} 可交叉验算，但不得外推为 $34 口径。

## 数据核验

{anomaly_lines}

## 处置与边界

SEC 历史数优先于 INT-01 flash；bank comps 与研究资料仅作交叉验证。主 `Source_Index.csv` 未登记委员会文件使用的 `UW-01`，未虚构来源编号，已在追溯表标注“待核实”；不影响数值，但正式归档前应补齐索引治理。未使用 2024-03-20 后信息、最终发行结果或上市后表现。
"""
    (OUTPUT_DIR / f"{PREFIX}_pricing_memo.md").write_text(memo, encoding="utf-8")


def append_table(worksheet, headers, rows) -> None:
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)


def style_workbook(workbook: Workbook) -> None:
    navy, pale, amber = "17324D", "E8F1F2", "F4B942"
    thin = Side(style="thin", color="D1D9E0")
    for worksheet in workbook.worksheets:
        worksheet.freeze_panes = "A2"
        worksheet.sheet_view.showGridLines = False
        for cell in worksheet[1]:
            cell.fill = PatternFill("solid", fgColor=navy)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        worksheet.row_dimensions[1].height = 28
        for row in worksheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                cell.border = Border(bottom=thin)
            status = " ".join(str(cell.value or "") for cell in row)
            if "Proceed" in status or "已修正" in status:
                row[0].fill = PatternFill("solid", fgColor=pale)
            if "待核实" in status:
                row[0].fill = PatternFill("solid", fgColor=amber)
        for cells in worksheet.columns:
            worksheet.column_dimensions[get_column_letter(cells[0].column)].width = max(12, min(max(len(str(cell.value or "")) for cell in cells) + 2, 48))
        worksheet.auto_filter.ref = worksheet.dimensions
    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    workbook.calculation.calcMode = "auto"


def write_workbook(values: dict, growths, multiples, matrix, anomalies, legacy, source_trace) -> None:
    workbook = Workbook()
    workbook.remove(workbook.active)
    inputs = workbook.create_sheet("Inputs")
    append_table(inputs, ["Input", "Value", "Unit", "Classification", "Source", "Notes"], [
        ["2023A Revenue", values["revenue_2023"], "USD mm", "SEC 公开事实", "SEC-01", "历史审计数"], ["2023 Net loss", values["net_loss_2023"], "USD mm", "SEC 公开事实", "SEC-01", ""], ["Management Adjusted EBITDA", values["management_ebitda_2023"], "USD mm", "SEC 披露非GAAP", "SEC-01", "非审计意见覆盖"], ["SBC and related taxes", values["sbc_2023"], "USD mm", "SEC 公开事实", "SEC-01", ""], ["Restructuring", values["restructuring_2023"], "USD mm", "SEC 公开事实", "SEC-01", "已在管理层 EBITDA 调整"], ["Free Cash Flow", values["fcf_2023"], "USD mm", "SEC 公开事实", "SEC-01", ""], ["Cash", values["cash_2023"], "USD mm", "SEC 公开事实", "SEC-01", ""], ["Marketable securities", values["securities_2023"], "USD mm", "SEC 公开事实", "SEC-01", ""], ["2024E growth", values["growth"], "%", "内部委员会假设", "CP-06", "非公开预测"], ["Peer low", values["multiple_low"], "x", "内部委员会假设", "CP-07", ""], ["Peer midpoint", values["multiple_mid"], "x", "内部委员会假设", "CP-07", ""], ["Peer high", values["multiple_high"], "x", "内部委员会假设", "CP-07", ""], ["Execution discount", values["discount"], "%", "内部委员会假设", "CP-09", ""], ["Pre-money economic shares", values["pre_money_shares"], "mm shares", "SEC 事实推导/委员会快照", "SEC-09 类别合计", ""], ["Proposed price", values["proposed_price"], "USD/share", "内部委员会假设", "Offering_Terms_20240320.xlsx", "决策输入，非已实现结果"], ["Primary base", values["primary_base"], "mm shares", "SEC 公开事实", "SEC-03", ""], ["Secondary base", values["secondary_base"], "mm shares", "SEC 公开事实", "SEC-03", "公司募集资金和新增股数均为零"], ["Greenshoe", values["greenshoe"], "mm shares", "SEC 公开事实", "SEC-03", "Base 排除"], ["Underwriting fee rate", values["fee_rate"], "% primary gross", "内部委员会假设", "CP-12", ""], ["Fixed company expenses", values["fixed_expenses"], "USD mm", "内部委员会假设", "CP-12", "仅一次"]])
    qoe = workbook.create_sheet("QoE")
    append_table(qoe, ["Item", "2022A", "2023A / Result", "Formula / Treatment", "Source / Policy"], [["Revenue", values["revenue_2022"], values["revenue_2023"], "SEC annual amounts", "SEC-01"], ["Net income (loss)", None, values["net_loss_2023"], "SEC annual amount", "SEC-01"], ["Management Adjusted EBITDA", None, values["management_ebitda_2023"], "Management non-GAAP starting point", "SEC-01 / CP-03"], ["Reverse SBC addback", None, -values["sbc_2023"], "=-SBC; recurring economic cost", "CP-03"], ["Restructuring incremental adjustment", None, 0.0, f"{values['restructuring_2023']:.3f} already adjusted", "CP-04"], ["Underwriting EBITDA", None, values["underwriting_ebitda"], "=Management Adj EBITDA - SBC", "CP-03"], ["Underwriting EBITDA margin", None, values["underwriting_margin"], "=Underwriting EBITDA / Revenue", "Calculated"], ["Free Cash Flow", None, values["fcf_2023"], "OCF less capex", "SEC-01"], ["FCF margin", None, values["fcf_margin"], "=FCF / Revenue", "Calculated"], ["Method conclusion", None, "EV / 2024E Revenue", "Underwriting EBITDA remains negative", "CP-05"]])
    valuation = workbook.create_sheet("Valuation")
    append_table(valuation, ["Case", "2024E Revenue", "EV/Revenue", "Enterprise Value", "Cash + Securities", "Pre-money Equity", "Economic Shares", "Undiscounted / Share", "Discount", "Supported / Share", "Formula"], [[r["case"], values["revenue_2024"], r["multiple"], r["enterprise_value"], values["net_cash"], r["equity_value"], values["pre_money_shares"], r["undiscounted_per_share"], values["discount"], r["supported_per_share"], "((2023A Revenue×(1+growth))×multiple+cash+securities)/shares×(1-discount)"] for r in values["valuations"]])
    sens = workbook.create_sheet("Sensitivity")
    sens.append(["2024E growth / EV-Revenue"] + [f"{m:.2f}x" for m in multiples] + ["Note"])
    for growth, row in zip(growths, matrix): sens.append([growth] + row + ["BASE GROWTH" if math.isclose(growth, values["growth"]) else ""])
    offering = workbook.create_sheet("Offering_Proceeds")
    append_table(offering, ["Item", "Base", "Full Exercise", "Unit", "Formula / Policy"], [["Primary shares", values["primary_base"], values["primary_full"], "mm shares", "SEC-03; full adds greenshoe"], ["Secondary shares", values["secondary_base"], values["secondary_base"], "mm shares", "No company proceeds"], ["Greenshoe in scenario", 0.0, values["greenshoe"], "mm shares", "CP-11"], ["Total offered shares", values["offered_base"], values["offered_full"], "mm shares", "Primary + secondary"], ["Company primary gross", values["base_gross"], values["full_gross"], "USD mm", "Primary shares × proposed price"], ["Secondary gross", values["secondary_gross"], values["secondary_gross"], "USD mm", "Selling stockholders"], ["Underwriting fee", values["base_fee"], values["full_fee"], "USD mm", "5% × company primary gross"], ["Fixed company expenses", values["fixed_expenses"], values["fixed_expenses"], "USD mm", "Once only"], ["Company net primary proceeds", values["base_net"], values["full_net"], "USD mm", "Gross - fee - fixed expenses"]])
    dilution = workbook.create_sheet("Dilution")
    append_table(dilution, ["Item", "Base", "Full Exercise", "Unit", "Formula / Use Boundary"], [["Pre-money economic shares", values["pre_money_shares"], values["pre_money_shares"], "mm shares", "SEC-09 category sum"], ["New primary shares", values["primary_base"], values["primary_full"], "mm shares", "Secondary excluded"], ["Post-money shares", values["post_shares_base"], values["post_shares_full"], "mm shares", "Pre-money + primary"], ["New shares / post-money", values["new_share_pct_base"], values["new_share_pct_full"], "%", "Primary / post-money"], ["SEC assumed price", values["ntbv_assumed_price"], values["ntbv_assumed_price"], "USD/share", "SEC-02 cross-check only"], ["SEC preliminary NTBV/share", values["ntbv_per_share"], values["ntbv_per_share"], "USD/share", "Only at assumed $32.50"], ["SEC immediate dilution", values["sec_dilution"], values["sec_dilution"], "USD/share", "Assumed price - NTBV/share"], ["Arithmetic cross-check", values["ntbv_check"], values["ntbv_check"], "USD/share", "Must equal SEC immediate dilution"], ["Boundary", "Do not extrapolate", "Do not extrapolate", "Text", "$34 formal NTBV bridge unavailable"]])
    pricing = workbook.create_sheet("Pricing_Summary")
    append_table(pricing, ["Metric", "Value", "Unit", "Test / Conclusion"], [["Supported low", values["supported_low"], "USD/share", "4.0x after discount"], ["Supported midpoint", values["supported_mid"], "USD/share", "4.5x after discount"], ["Supported high", values["supported_high"], "USD/share", "5.0x after discount"], ["Proposed price", values["proposed_price"], "USD/share", "Internal decision input"], ["Distance to midpoint", values["distance_to_mid"], "USD/share", "≤ $0.50"], ["Within supported range", values["supported_low"] <= values["proposed_price"] <= values["supported_high"], "Boolean", "CP-14"], ["Underwriting EBITDA", values["underwriting_ebitda"], "USD mm", "Negative QoE risk"], ["Free Cash Flow", values["fcf_2023"], "USD mm", "Negative QoE risk"], ["Recommendation", values["recommendation"], "Decision", "CP-14 / CP-15"]])
    audit = workbook.create_sheet("Error_Audit")
    append_table(audit, ["Category", "File / Location", "Original Issue", "Decision Basis", "Correct Treatment", "Impact", "Status"], [[r["category"], r["file_location"], r["issue"], r["basis"], r["resolution"], r["impact"], r["status"]] for r in anomalies + legacy])
    trace = workbook.create_sheet("Source_Trace")
    append_table(trace, ["Metric", "Classification", "Selected Value", "Unit", "Selected Source", "Competing Value / Source", "Disposition"], [[r["metric"], r["classification"], r["selected_value"], r["unit"], r["selected_source"], r["competing_value_source"], r["disposition"]] for r in source_trace])
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, float): cell.number_format = "0.000"
    for row in sens.iter_rows(min_row=2, min_col=2, max_col=6):
        for cell in row: cell.number_format = '$0.00'
    style_workbook(workbook)
    workbook.save(OUTPUT_DIR / f"{PREFIX}_ipo_model.xlsx")


def write_chart(values: dict, growths, multiples, matrix) -> None:
    plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans"})
    fig, (ax_price, ax_heat) = plt.subplots(1, 2, figsize=(13.5, 5.4), gridspec_kw={"width_ratios": [0.9, 1.35]})
    fig.patch.set_facecolor("#F7F8FA")
    ax_price.set_facecolor("#F7F8FA")
    ax_price.hlines(0, values["supported_low"], values["supported_high"], color="#127C7E", linewidth=16)
    ax_price.scatter(values["supported_mid"], 0, color="#17324D", s=95, zorder=3)
    ax_price.scatter(values["proposed_price"], 0, color="#D14B3F", marker="D", s=90, zorder=4)
    ax_price.text(values["supported_low"], 0.12, f"Low\n{price(values['supported_low'])}", ha="center")
    ax_price.text(values["supported_high"], 0.12, f"High\n{price(values['supported_high'])}", ha="center")
    ax_price.text(values["supported_mid"], -0.18, f"Mid {price(values['supported_mid'])}", ha="center")
    ax_price.text(values["proposed_price"], 0.31, f"Proposed {price(values['proposed_price'])}", ha="center", color="#D14B3F", fontweight="bold")
    padding = max(1.5, (values["supported_high"] - values["supported_low"]) * 0.22)
    ax_price.set_xlim(values["supported_low"] - padding, values["supported_high"] + padding)
    ax_price.set_ylim(-0.45, 0.55); ax_price.set_yticks([]); ax_price.set_xlabel("USD per share")
    ax_price.set_title("Committee-Supported Price Range", loc="left", fontweight="bold", color="#17324D")
    for spine in ("left", "right", "top"): ax_price.spines[spine].set_visible(False)
    cmap = LinearSegmentedColormap.from_list("committee", ["#E8F1F2", "#86C5B5", "#F4D06F", "#D96C55"])
    data = np.array(matrix); image = ax_heat.imshow(data, cmap=cmap, aspect="auto")
    for i in range(data.shape[0]):
        for j in range(data.shape[1]): ax_heat.text(j, i, f"${data[i, j]:.2f}", ha="center", va="center", color="#152536", fontweight="bold" if (i == 2 and j == 2) else "normal")
    ax_heat.add_patch(plt.Rectangle((1.52, 1.52), 0.96, 0.96, fill=False, edgecolor="#17324D", linewidth=2.6))
    ax_heat.set_xticks(range(len(multiples)), [f"{m:.2f}x" for m in multiples]); ax_heat.set_yticks(range(len(growths)), [f"{g:.0%}" for g in growths])
    ax_heat.set_xlabel("EV / 2024E Revenue"); ax_heat.set_ylabel("2024E Revenue growth"); ax_heat.set_title("Supported Price Sensitivity", loc="left", fontweight="bold", color="#17324D")
    for spine in ax_heat.spines.values(): spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=ax_heat, fraction=0.035, pad=0.03); colorbar.set_label("USD/share")
    fig.suptitle("Reddit IPO Pre-Pricing Review | As of 20 Mar 2024", x=0.06, ha="left", fontsize=14, fontweight="bold", color="#17324D")
    fig.text(0.06, 0.92, "Internal committee assumptions are distinct from SEC public facts.", color="#5E6B75")
    plt.tight_layout(rect=[0, 0, 1, 0.89]); fig.savefig(OUTPUT_DIR / f"{PREFIX}_charts.png", dpi=220, bbox_inches="tight", facecolor=fig.get_facecolor()); plt.close(fig)


def validate_outputs(values: dict, anomalies: list[dict]) -> None:
    required = [f"{PREFIX}_ipo_model.xlsx", f"{PREFIX}_pricing_memo.md", f"{PREFIX}_reproduce.py", f"{PREFIX}_qoe_bridge.csv", f"{PREFIX}_valuation_matrix.csv", f"{PREFIX}_source_trace.csv", f"{PREFIX}_charts.png"]
    missing = [name for name in required if not (OUTPUT_DIR / name).is_file()]
    if missing: raise RuntimeError(f"Missing outputs: {missing}")
    workbook = load_workbook(OUTPUT_DIR / f"{PREFIX}_ipo_model.xlsx", data_only=False, read_only=True)
    expected = {"Inputs", "QoE", "Valuation", "Sensitivity", "Offering_Proceeds", "Dilution", "Pricing_Summary", "Error_Audit", "Source_Trace"}
    if not expected.issubset(workbook.sheetnames): raise RuntimeError("Workbook is missing required worksheets")
    if not math.isclose(values["ntbv_check"], values["sec_dilution"], abs_tol=1e-9): raise RuntimeError("SEC dilution arithmetic does not tie")
    if len(anomalies) < 1: raise RuntimeError("No detail anomalies were recorded")
    with (OUTPUT_DIR / f"{PREFIX}_charts.png").open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n": raise RuntimeError("Chart output is not a valid PNG")


def main() -> None:
    values = calculate(load_inputs())
    anomalies = audit_financial_details(values)
    legacy = legacy_errors(values)
    source_trace = build_source_trace(values)
    growths, multiples, matrix = sensitivity(values)
    write_qoe_bridge(values)
    write_valuation_matrix(values, growths, multiples, matrix)
    write_csv_file(OUTPUT_DIR / f"{PREFIX}_source_trace.csv", ["metric", "classification", "selected_value", "unit", "selected_source", "competing_value_source", "disposition"], source_trace)
    write_memo(values, anomalies)
    write_workbook(values, growths, multiples, matrix, anomalies, legacy, source_trace)
    write_chart(values, growths, multiples, matrix)
    validate_outputs(values, anomalies)
    print("Reddit IPO pre-pricing review (information cut-off: 2024-03-20)")
    print(f"2023A Revenue: ${money(values['revenue_2023'])}mm")
    print(f"2024E Revenue: ${money(values['revenue_2024'])}mm ({values['growth']:.1%} internal growth assumption)")
    print(f"Underwriting EBITDA: ${money(values['underwriting_ebitda'])}mm")
    print(f"Free Cash Flow: ${money(values['fcf_2023'])}mm")
    print(f"Supported price range: {price(values['supported_low'])} - {price(values['supported_high'])}")
    print(f"Supported midpoint: {price(values['supported_mid'])}")
    print(f"Proposed price: {price(values['proposed_price'])}; distance to midpoint: {price(values['distance_to_mid'])}")
    print(f"Base company gross / net proceeds: ${money(values['base_gross'])}mm / ${money(values['base_net'])}mm")
    print(f"Full-exercise company net proceeds: ${money(values['full_net'])}mm")
    print(f"Base / full post-money shares: {values['post_shares_base']:.6f}mm / {values['post_shares_full']:.6f}mm")
    print(f"Financial detail anomalies documented: {len(anomalies)}")
    print(f"Legacy/source-governance issues documented: {len(legacy)}")
    print(f"Recommendation: {values['recommendation']}")
    print("Generated and validated all 7 required deliverables.")


if __name__ == "__main__":
    main()
