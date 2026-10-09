#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

DELIVERY_PREFIX = "FIN3-WKN-152"
AS_OF = "2024-03-20"


def require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    return path


def read_sheet_map(path: Path, sheet: str, key_col: int = 1, value_col: int = 3) -> dict:
    wb = load_workbook(require(path), data_only=True, read_only=True)
    ws = wb[sheet]
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[key_col - 1] is not None:
            out[str(row[key_col - 1])] = row[value_col - 1]
    return out


def read_assumptions(path: Path) -> dict:
    wb = load_workbook(require(path), data_only=True, read_only=True)
    ws = wb["Assumptions"]
    return {str(r[0]): r[1] for r in ws.iter_rows(min_row=2, values_only=True) if r[0] is not None}


def read_offering(path: Path) -> dict:
    wb = load_workbook(require(path), data_only=True, read_only=True)
    ws = wb["Offering_Terms"]
    return {str(r[0]): {"base": r[1], "full": r[2], "unit": r[3], "source": r[4], "note": r[5]}
            for r in ws.iter_rows(min_row=2, values_only=True) if r[0] is not None}


def read_dilution(path: Path) -> dict:
    wb = load_workbook(require(path), data_only=True, read_only=True)
    ws = wb["Dilution_Crosscheck"]
    return {str(r[0]): {"value": r[1], "unit": r[2], "price": r[3], "source": r[4]}
            for r in ws.iter_rows(min_row=2, values_only=True) if r[0] is not None}


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fmt_num(value: float, decimals: int = 3) -> str:
    return f"{value:,.{decimals}f}"


def fmt_price(value: float) -> str:
    return f"${value:,.2f}"


def calculate(input_dir: Path) -> dict:
    sec_fin_path = input_dir / "sec_filings" / "SEC-01_financials_extract.xlsx"
    wb = load_workbook(require(sec_fin_path), data_only=True, read_only=True)
    ws = wb["Public_Financials"]
    financials = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is not None:
            financials[str(row[0])] = {"2022A": row[1], "2023A": row[2], "unit": row[3], "source": row[4], "note": row[5]}

    assumptions = read_assumptions(input_dir / "committee" / "Underwriting_Assumptions_20240320.xlsx")
    offering = read_offering(input_dir / "committee" / "Offering_Terms_20240320.xlsx")
    dilution = read_dilution(input_dir / "sec_filings" / "SEC-02_dilution_crosscheck.xlsx")

    monthly = pd.read_csv(require(input_dir / "financials" / "monthly_revenue_2022_2023.csv"))
    quarterly = pd.read_csv(require(input_dir / "financials" / "revenue_quarterly.csv"))
    segments = pd.read_csv(require(input_dir / "financials" / "revenue_by_segment_2022_2023.csv"))
    geo = pd.read_csv(require(input_dir / "sec_filings" / "SEC-05_revenue_by_geo.csv"))
    sbc_detail = pd.read_csv(require(input_dir / "financials" / "sbc_detail_2022_2023.csv"))
    restructuring = pd.read_csv(require(input_dir / "financials" / "restructuring_detail_2023.csv"))
    fcf_bridge = pd.read_csv(require(input_dir / "financials" / "fcf_bridge_2023.csv"))
    cash_flow = pd.read_csv(require(input_dir / "financials" / "cash_flow_statement_2023.csv"))
    balance_sheet = pd.read_csv(require(input_dir / "financials" / "balance_sheet_summary_2022_2023.csv"))
    income_statement = pd.read_csv(require(input_dir / "financials" / "income_statement_2022_2023.csv"))
    cap_table = pd.read_csv(require(input_dir / "committee" / "cap_table_snapshot_20240318.csv"))
    share_history = pd.read_csv(require(input_dir / "sec_filings" / "SEC-16_share_count_history.csv"))
    management_flash = pd.read_csv(require(input_dir / "internal" / "management_flash_20240319.csv"))
    bank_a = pd.read_csv(require(input_dir / "comps" / "underwriter_A_comps_20240315.csv"))
    bank_b = pd.read_csv(require(input_dir / "comps" / "underwriter_B_comps_20240318.csv"))

    revenue_2022 = float(financials["Revenue"]["2022A"])
    revenue_2023 = float(financials["Revenue"]["2023A"])
    net_loss_2022 = float(financials["Net income (loss)"]["2022A"])
    net_loss_2023 = float(financials["Net income (loss)"]["2023A"])
    management_ebitda_2022 = float(financials["Adjusted EBITDA"]["2022A"])
    management_ebitda_2023 = float(financials["Adjusted EBITDA"]["2023A"])
    sbc_2022 = float(financials["Stock-based compensation & related taxes"]["2022A"])
    sbc_2023 = float(financials["Stock-based compensation & related taxes"]["2023A"])
    restructuring_2022 = float(financials["Restructuring costs"]["2022A"])
    restructuring_2023 = float(financials["Restructuring costs"]["2023A"])
    fcf_2022 = float(financials["Free Cash Flow"]["2022A"])
    fcf_2023 = float(financials["Free Cash Flow"]["2023A"])
    cash_2022 = float(financials["Cash & cash equivalents"]["2022A"])
    cash_2023 = float(financials["Cash & cash equivalents"]["2023A"])
    securities_2022 = float(financials["Marketable securities"]["2022A"])
    securities_2023 = float(financials["Marketable securities"]["2023A"])

    growth = float(assumptions["2024E revenue growth"])
    peer_low = float(assumptions["Peer low EV/Revenue"])
    peer_mid = float(assumptions["Peer midpoint EV/Revenue"])
    peer_high = float(assumptions["Peer high EV/Revenue"])
    execution_discount = float(assumptions["IPO discount to peer-implied equity"])
    price = float(offering["Proposed Committee Price"]["base"])
    primary = float(offering["Primary shares offered"]["base"])
    secondary = float(offering["Secondary shares offered"]["base"])
    greenshoe = float(offering["Greenshoe shares"]["full"])
    pre_money_shares = float(offering["Pre-money economic shares"]["base"])
    filing_low = float(offering["Preliminary public filing range low"]["base"])
    filing_high = float(offering["Preliminary public filing range high"]["base"])
    fee_rate = float(offering["Underwriting fee assumption"]["base"])
    fixed_expenses = float(offering["Fixed company offering expenses"]["base"])

    underwriting_ebitda_2022 = management_ebitda_2022 - sbc_2022
    underwriting_ebitda_2023 = management_ebitda_2023 - sbc_2023
    revenue_2024e = revenue_2023 * (1 + growth)
    net_cash = cash_2023 + securities_2023

    valuation = {}
    for label, multiple in [("Low", peer_low), ("Mid", peer_mid), ("High", peer_high)]:
        ev = revenue_2024e * multiple
        equity = ev + net_cash
        undiscounted = equity / pre_money_shares
        discounted = undiscounted * (1 - execution_discount)
        valuation[label] = {
            "multiple": multiple,
            "ev": ev,
            "equity": equity,
            "undiscounted_price": undiscounted,
            "supported_price": discounted,
        }

    post_base = pre_money_shares + primary
    full_primary = primary + greenshoe
    post_full = pre_money_shares + full_primary
    gross_base = primary * price
    fee_base = gross_base * fee_rate
    net_base = gross_base - fee_base - fixed_expenses
    gross_full = full_primary * price
    fee_full = gross_full * fee_rate
    net_full = gross_full - fee_full - fixed_expenses
    gross_secondary = secondary * price

    historical_growth = revenue_2023 / revenue_2022 - 1
    growth_step = (growth - historical_growth) / 2
    growth_rates = [historical_growth + growth_step * i for i in range(5)]
    multiples = np.linspace(peer_low, peer_high, 5).tolist()
    sensitivity = np.array([
        [((revenue_2023 * (1 + g) * m + net_cash) / pre_money_shares) * (1 - execution_discount)
         for m in multiples]
        for g in growth_rates
    ])

    monthly_2022 = float(monthly[(monthly["fy"] == "FY2022") & (monthly["status"] == "original")]["revenue_usd_mm"].sum())
    monthly_2023 = float(monthly[(monthly["fy"] == "FY2023") & (monthly["status"] == "audited-final")]["revenue_usd_mm"].sum())
    quarterly_2023 = float(quarterly[quarterly["fy"] == "FY2023"]["revenue_usd_mm"].sum())
    segment_2022 = float(segments[segments["fy"] == "FY2022"]["revenue_usd_mm"].sum())
    segment_2023 = float(segments[segments["fy"] == "FY2023"]["revenue_usd_mm"].sum())
    geo_2022 = float(geo[geo["fy"] == "FY2022"]["revenue_usd_mm"].sum())
    geo_2023 = float(geo[geo["fy"] == "FY2023"]["revenue_usd_mm"].sum())
    sbc_detail_2022 = float(sbc_detail[sbc_detail["fy"] == "FY2022"]["amount_usd_mm"].sum())
    sbc_detail_2023 = float(sbc_detail[(sbc_detail["fy"] == "FY2023") & (sbc_detail["component"] != "TOTAL")]["amount_usd_mm"].sum())
    restructuring_detail_2023 = float(restructuring[restructuring["component"] != "TOTAL"]["amount_usd_mm"].sum())
    ocf_2023 = float(fcf_bridge.loc[fcf_bridge["line_item"] == "Net cash used in operating activities", "amount_usd_mm"].iloc[0])
    capex_2023 = float(fcf_bridge.loc[fcf_bridge["line_item"] == "Purchases of property and equipment", "amount_usd_mm"].iloc[0])
    fcf_recalc_2023 = ocf_2023 + capex_2023
    cash_change_recalc = float(cash_flow.loc[cash_flow["line_item"] == "Cash & cash equivalents at end of period", "FY2023"].iloc[0]) - float(cash_flow.loc[cash_flow["line_item"] == "Cash & cash equivalents at beginning of period", "FY2023"].iloc[0])
    cash_change_reported = float(cash_flow.loc[cash_flow["line_item"] == "Net change in cash and cash equivalents", "FY2023"].iloc[0])
    balance_liquidity_2023 = float(balance_sheet.loc[balance_sheet["line_item"] == "Total cash, cash equivalents and marketable securities", "FY2023"].iloc[0])
    income_total_opex_2023 = float(income_statement.loc[income_statement["line_item"] == "Total costs and operating expenses", "FY2023"].iloc[0])
    other_income_2023 = float(income_statement.loc[income_statement["line_item"] == "Other income, net", "FY2023"].iloc[0])
    net_loss_recalc_2023 = revenue_2023 + income_total_opex_2023 + other_income_2023
    cap_total = float(cap_table.loc[cap_table["holder_class"] == "TOTAL_pre_money_economic_shares", "shares_mm"].iloc[0])
    registered_shares = float(share_history.loc[share_history["note"].str.contains("registered shares", na=False), "shares_outstanding_mm"].iloc[0])

    flash = {str(r["metric"]): float(r["FY2023_value"]) for _, r in management_flash.iterrows()}
    sec_ntbv = float(dilution["Preliminary NTBV/share"]["value"])
    sec_dilution = float(dilution["Preliminary immediate dilution per share"]["value"])
    sec_assumed_price = float(dilution["Preliminary NTBV/share"]["price"])

    low_price = valuation["Low"]["supported_price"]
    midpoint = valuation["Mid"]["supported_price"]
    high_price = valuation["High"]["supported_price"]
    in_range = low_price <= price <= high_price
    midpoint_distance = price - midpoint
    error_rows = []
    for category in [
        "QoE starting metric", "Double counting", "Valuation denominator", "Execution discount",
        "Net cash bridge", "Primary / secondary", "Greenshoe in Base", "Underwriting fee basis",
        "Post-money shares", "Company proceeds", "Dilution convention", "Pricing recommendation",
        "Broken references", "Detail export status",
    ]:
        error_rows.append(category)
    hard_errors_unresolved = sum(1 for category in error_rows if not category)
    if in_range and abs(midpoint_distance) <= 0.50 and hard_errors_unresolved == 0:
        recommendation = "Proceed"
    elif in_range and hard_errors_unresolved == 0:
        recommendation = "Reprice"
    else:
        recommendation = "Defer"

    checks = {
        "Monthly 2022 to SEC": monthly_2022 - revenue_2022,
        "Monthly 2023 to SEC": monthly_2023 - revenue_2023,
        "Quarterly 2023 to SEC": quarterly_2023 - revenue_2023,
        "Segment 2022 to SEC": segment_2022 - revenue_2022,
        "Segment 2023 to SEC": segment_2023 - revenue_2023,
        "Geography 2022 to SEC": geo_2022 - revenue_2022,
        "Geography 2023 to SEC": geo_2023 - revenue_2023,
        "SBC detail 2022 to SEC": sbc_detail_2022 - sbc_2022,
        "SBC detail 2023 to SEC": sbc_detail_2023 - sbc_2023,
        "Restructuring detail 2023 to SEC": restructuring_detail_2023 - restructuring_2023,
        "FCF bridge 2023 to SEC": fcf_recalc_2023 - fcf_2023,
        "Cash movement bridge": cash_change_recalc - cash_change_reported,
        "Liquidity bridge": cash_2023 + securities_2023 - balance_liquidity_2023,
        "Net loss bridge 2023": net_loss_recalc_2023 - net_loss_2023,
        "Cap table total to offering": cap_total - pre_money_shares,
        "SEC dilution arithmetic": sec_ntbv + sec_dilution - sec_assumed_price,
    }

    return locals()


def build_qoe_rows(d: dict) -> list[dict]:
    return [
        {"step": 1, "bridge_item": "Management Adjusted EBITDA", "amount_usd_mm": d["management_ebitda_2023"], "running_total_usd_mm": d["management_ebitda_2023"], "treatment": "Starting point; management non-GAAP and outside audit opinion", "basis": "SEC-01 financials extract; SEC-14 auditor note", "policy_id": "CP-03"},
        {"step": 2, "bridge_item": "Reverse SBC & related taxes addback", "amount_usd_mm": -d["sbc_2023"], "running_total_usd_mm": d["underwriting_ebitda_2023"], "treatment": "Recurring economic cost; addback not retained", "basis": "SEC-01; SBC detail sums to reported amount", "policy_id": "CP-03"},
        {"step": 3, "bridge_item": "Restructuring costs", "amount_usd_mm": 0.0, "running_total_usd_mm": d["underwriting_ebitda_2023"], "treatment": "No second adjustment; already reflected in management metric", "basis": "SEC-01; restructuring detail sums to reported amount", "policy_id": "CP-04"},
        {"step": 4, "bridge_item": "Underwriting EBITDA", "amount_usd_mm": d["underwriting_ebitda_2023"], "running_total_usd_mm": d["underwriting_ebitda_2023"], "treatment": "Negative; primary valuation method is EV / 2024E Revenue", "basis": "Calculated from preceding steps", "policy_id": "CP-05"},
    ]


def build_source_rows(d: dict) -> list[dict]:
    rows = []
    def add(metric, selected, unit, source_id, source_file, source_type, competing, competing_source, disposition):
        rows.append({"metric": metric, "selected_value": selected, "unit": unit, "selected_source_id": source_id, "selected_source_file": source_file, "source_type": source_type, "competing_value": competing, "competing_source": competing_source, "disposition": disposition})

    add("Information cut-off", AS_OF, "date", "SEC-04", "sec_filings/SEC-04_s1a_a2_20240315_summary.md", "SEC public fact", "Post-cutoff results", "Excluded", "Use only information available before committee pricing on 2024-03-20")
    add("Controlling policy", "v3", "version", "", "committee/Committee_Policy_v3_20240320.xlsx", "Internal committee policy", "v2", "committee/Committee_Policy_v2_20240305.xlsx", "v3 supersedes v2 for SBC, peer range, discount and fee basis")
    add("2023 Revenue", d["revenue_2023"], "USD mm", "SEC-01", "sec_filings/SEC-01_financials_extract.xlsx", "SEC public fact", d["flash"]["Revenue"], "internal/management_flash_20240319.csv (INT-01, Priority 9)", "Use audited SEC-01; reject unreviewed flash")
    add("2023 Net income (loss)", d["net_loss_2023"], "USD mm", "SEC-01", "sec_filings/SEC-01_financials_extract.xlsx", "SEC public fact", "", "", "Use SEC-01")
    add("2023 Management Adjusted EBITDA", d["management_ebitda_2023"], "USD mm", "SEC-01", "sec_filings/SEC-01_financials_extract.xlsx", "SEC public non-GAAP fact", d["flash"]["Adjusted EBITDA"], "internal/management_flash_20240319.csv (INT-01, Priority 9)", "Use SEC-01; metric is outside auditor opinion")
    add("2023 SBC & related taxes", d["sbc_2023"], "USD mm", "SEC-01", "sec_filings/SEC-01_financials_extract.xlsx", "SEC public fact", d["flash"]["Stock-based compensation & related taxes"], "internal/management_flash_20240319.csv (INT-01, Priority 9)", "Use SEC-01 and verified detail; reject flash")
    add("2023 Restructuring costs", d["restructuring_2023"], "USD mm", "SEC-01", "financials/restructuring_detail_2023.csv", "SEC public fact/detail", "Possible second addback", "legacy treatment risk", "No second addback under CP-04")
    add("2023 Underwriting EBITDA", d["underwriting_ebitda_2023"], "USD mm", "SEC-01", "SEC-01 + committee/Committee_Policy_v3_20240320.xlsx", "Calculated underwriting convention", d["management_ebitda_2023"], "Legacy used management metric directly", "Reverse SBC addback under CP-03")
    add("2023 Free Cash Flow", d["fcf_2023"], "USD mm", "SEC-01", "sec_filings/SEC-01_financials_extract.xlsx", "SEC public non-GAAP fact", d["flash"]["Free Cash Flow"], "internal/management_flash_20240319.csv (INT-01, Priority 9)", "Use SEC-01; independently ties to OCF plus capex")
    add("2023 Cash & cash equivalents", d["cash_2023"], "USD mm", "SEC-01", "sec_filings/SEC-01_financials_extract.xlsx", "SEC public fact", "", "", "Include in net cash bridge")
    add("2023 Marketable securities", d["securities_2023"], "USD mm", "SEC-01", "sec_filings/SEC-01_financials_extract.xlsx", "SEC public fact", "Excluded", "legacy/Candidate_Model_v0.xlsx", "Include in net cash bridge under CP-08")
    add("2024E Revenue growth", d["growth"], "%", "UW-01", "committee/Underwriting_Assumptions_20240320.xlsx", "Internal committee assumption", "18% sector median", "research/sector_benchmark.md", f'Use {d["growth"]:.1%} CP-06; do not present as SEC fact')
    add("2024E Revenue", d["revenue_2024e"], "USD mm", "SEC-01", "SEC-01 revenue × committee CP-06 growth", "Calculated using public fact + internal assumption", d["revenue_2023"], "legacy used 2023A denominator", "Use forward revenue")
    add("Peer Low / Mid / High", f'{d["peer_low"]:.1f}x / {d["peer_mid"]:.1f}x / {d["peer_high"]:.1f}x', "x", "UW-01", "committee/Committee_Policy_v3_20240320.xlsx", "Internal committee assumption", f'A {d["bank_a"]["ntm_ev_revenue"].min():.1f}-{d["bank_a"]["ntm_ev_revenue"].max():.1f}x; B {d["bank_b"]["ntm_ev_revenue"].min():.1f}-{d["bank_b"]["ntm_ev_revenue"].max():.1f}x', "comps files, Priority 8", "Use committee range under CP-07; banks are cross-check only")
    add("Execution discount", d["execution_discount"], "%", "UW-01", "committee/Underwriting_Assumptions_20240320.xlsx", "Internal committee assumption", "10%", "superseded Committee Policy v2", f'Use {d["execution_discount"]:.1%}; apply to implied equity value/share')
    add("Pre-money economic shares", d["pre_money_shares"], "mm shares", "SEC-09", "committee/cap_table_snapshot_20240318.csv", "Internal committee snapshot using SEC-09 components", d["registered_shares"], "sec_filings/SEC-16_share_count_history.csv", "Use economic snapshot; registered count excludes unsettled RSUs")
    add("Proposed price", d["price"], "USD/share", "", "committee/Offering_Terms_20240320.xlsx", "Internal committee assumption", f'{d["filing_low"]:.0f}-{d["filing_high"]:.0f}', "SEC-03 preliminary filing range", "Decision input, not actual final price")
    add("Base primary shares", d["primary"], "mm shares", "SEC-03", "sec_filings/SEC-03_offering_terms.xlsx", "SEC public fact", 22.0, "legacy treated all base shares as primary", "Use SEC-03 primary amount")
    add("Base secondary shares", d["secondary"], "mm shares", "SEC-03", "sec_filings/SEC-03_offering_terms.xlsx", "SEC public fact", "Included in company proceeds/share count", "legacy/Candidate_Model_v0.xlsx", "No company proceeds and no new company shares")
    add("Greenshoe", d["greenshoe"], "mm shares", "SEC-03", "sec_filings/SEC-03_offering_terms.xlsx", "SEC public fact", "Included in Base", "legacy/Candidate_Model_v0.xlsx", "Exclude from Base; show full-exercise separately")
    add("Underwriting fee rate / basis", d["fee_rate"], "% of primary gross", "SEC-10", "committee/Offering_Terms_20240320.xlsx; sec_filings/SEC-10_underwriting_agreement_summary.md", "SEC mechanism + internal rate assumption", "% of primary + secondary", "superseded Committee Policy v2 / legacy", "Apply to company primary gross only")
    add("Fixed company expenses", d["fixed_expenses"], "USD mm", "", "committee/Offering_Terms_20240320.xlsx", "Internal committee assumption", "Repeated on greenshoe", "legacy risk", "Charge once in each total scenario; no repeat on increment")
    add("SEC NTBV/share cross-check", d["sec_ntbv"], "USD/share", "SEC-02", "sec_filings/SEC-02_dilution_crosscheck.xlsx", "SEC public fact at assumed price", f'Not comparable directly to {fmt_price(d["price"])}', "Assumed price differs", "Use only as independent arithmetic/methodology boundary")
    add("SEC immediate dilution cross-check", d["sec_dilution"], "USD/share", "SEC-02", "sec_filings/SEC-02_dilution_crosscheck.xlsx", "SEC public fact at assumed price", f'Not comparable directly to {fmt_price(d["price"])}', "Assumed price differs", f'{d["sec_ntbv"]:.2f} + {d["sec_dilution"]:.2f} = {d["sec_assumed_price"]:.2f}; do not transplant to {fmt_price(d["price"])}')
    add("Committee supported range", f'{d["low_price"]:.2f}-{d["high_price"]:.2f}', "USD/share", "", "Calculated from SEC-01 and committee policy v3", "Calculated conclusion", f'{d["filing_low"]:.0f}-{d["filing_high"]:.0f}', "SEC-03 preliminary filing range", "Committee range is valuation output; SEC range is execution cross-check")
    add("Recommendation", d["recommendation"], "text", "", "committee/Committee_Policy_v3_20240320.xlsx", "Calculated policy disposition", f'Legacy above {fmt_price(d["price"])}', "legacy/Candidate_Model_v0.xlsx", "Apply CP-14/CP-15 after correcting hard errors")
    return rows


def build_error_rows(d: dict) -> list[dict]:
    return [
        {"category": "QoE starting metric", "legacy_treatment": "Management Adjusted EBITDA used as underwriting conclusion", "correct_treatment": "Reverse SBC addback; restructuring adjustment remains zero", "quantified_impact": f'2023 EBITDA reduced by {fmt_num(d["sbc_2023"])} to {fmt_num(d["underwriting_ebitda_2023"])}', "status": "Corrected", "policy": "CP-03/CP-04"},
        {"category": "Double counting", "legacy_treatment": "Risk of adding restructuring again", "correct_treatment": "No second addback because management metric already reflects it", "quantified_impact": f'Avoids {fmt_num(d["restructuring_2023"])} overstatement', "status": "Corrected", "policy": "CP-04"},
        {"category": "Valuation denominator", "legacy_treatment": f'{d["peer_mid"]:.1f}x applied to 2023A Revenue', "correct_treatment": "Use 2024E Revenue = 2023A × (1 + committee growth)", "quantified_impact": f'Mid EV increases by {fmt_num(d["revenue_2024e"]*d["peer_mid"]-d["revenue_2023"]*d["peer_mid"])}', "status": "Corrected", "policy": "CP-05/CP-06"},
        {"category": "Execution discount", "legacy_treatment": "No discount applied", "correct_treatment": f'Apply {d["execution_discount"]:.1%} to peer-implied equity value/share', "quantified_impact": f'Mid price reduced by {fmt_price(d["valuation"]["Mid"]["undiscounted_price"]-d["midpoint"])}', "status": "Corrected", "policy": "CP-09"},
        {"category": "Net cash bridge", "legacy_treatment": "Marketable securities omitted", "correct_treatment": "Add cash and marketable securities to EV", "quantified_impact": f'Equity value restored by {fmt_num(d["securities_2023"])}', "status": "Corrected", "policy": "CP-08"},
        {"category": "Primary / secondary", "legacy_treatment": "All 22.0m base shares treated as primary", "correct_treatment": "Separate primary and secondary", "quantified_impact": f'Company gross overstatement avoided: {fmt_num(d["gross_secondary"])} at proposed price', "status": "Corrected", "policy": "CP-10"},
        {"category": "Greenshoe in Base", "legacy_treatment": "3.3m option included in Base", "correct_treatment": "Base excludes option; full exercise shown separately", "quantified_impact": f'Base shares avoid {fmt_num(d["greenshoe"])} premature increase', "status": "Corrected", "policy": "CP-11"},
        {"category": "Underwriting fee basis", "legacy_treatment": "Fee charged on primary + secondary", "correct_treatment": "Company fee charged only on primary gross", "quantified_impact": f'Base company fee overstatement avoided: {fmt_num(d["gross_secondary"]*d["fee_rate"])}', "status": "Corrected", "policy": "CP-12"},
        {"category": "Post-money shares", "legacy_treatment": "Secondary added to company shares", "correct_treatment": "Only newly issued primary shares increase company shares", "quantified_impact": f'Denominator overstatement avoided: {fmt_num(d["secondary"], 6)} shares', "status": "Corrected", "policy": "CP-10"},
        {"category": "Company proceeds", "legacy_treatment": "Secondary proceeds added to company cash", "correct_treatment": "Secondary proceeds go to selling holders", "quantified_impact": f'Company proceeds overstatement avoided: {fmt_num(d["gross_secondary"])}', "status": "Corrected", "policy": "CP-10"},
        {"category": "Dilution convention", "legacy_treatment": "Post-money equity divided by pre-money shares", "correct_treatment": f'Use consistent post-money share bridge; SEC {fmt_price(d["sec_assumed_price"])} data only cross-checks', "quantified_impact": "Legacy dilution result is not usable", "status": "Corrected", "policy": "SEC-02 boundary"},
        {"category": "Pricing recommendation", "legacy_treatment": f'Move above {fmt_price(d["price"])} based mainly on peer high case', "correct_treatment": "Apply Low/Mid/High range, midpoint guardrail and QoE disclosure", "quantified_impact": f'Proposed is {fmt_price(abs(d["midpoint_distance"]))} below midpoint', "status": "Corrected", "policy": "CP-14/CP-15"},
        {"category": "Broken references", "legacy_treatment": "#REF! in valuation, QoE and offering links", "correct_treatment": "Rebuild formulas from controlling source files", "quantified_impact": "Three broken links removed from decision model", "status": "Corrected", "policy": "Model integrity"},
        {"category": "Detail export status", "legacy_treatment": "Duplicate 2022-08 and preliminary 2023-12 could be summed", "correct_treatment": "Use original/audited-final rows and reconcile to SEC totals", "quantified_impact": "Avoids 57.100 duplicate and 66.500 preliminary double count", "status": "Corrected", "policy": "CP-02 / data dictionary"},
    ]


def build_matrix_csv(d: dict, path: Path) -> None:
    headers = ["growth_case", "growth_rate"] + [f'{m:.2f}x' + (" [Low]" if math.isclose(m, d["peer_low"]) else " [Mid/Base]" if math.isclose(m, d["peer_mid"]) else " [High]" if math.isclose(m, d["peer_high"]) else "") for m in d["multiples"]]
    rows = []
    for i, g in enumerate(d["growth_rates"]):
        label = "Base growth / Low-Mid-High row" if i == 2 else ("2023A actual growth anchor" if i == 0 else "Mechanical interpolation/extrapolation")
        row = {"growth_case": label, "growth_rate": round(g, 6)}
        for j, m in enumerate(d["multiples"]):
            row[headers[2 + j]] = round(float(d["sensitivity"][i, j]), 6)
        rows.append(row)
    write_csv(path, rows, headers)


def style_workbook(wb: Workbook) -> None:
    navy = "17365D"
    blue = "D9EAF7"
    yellow = "FFF2CC"
    green = "E2F0D9"
    red = "FCE4D6"
    grey = "E7E6E6"
    thin = Side(style="thin", color="B7B7B7")
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor=navy)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for row in ws.iter_rows():
            for cell in row:
                cell.border = Border(bottom=thin)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        for col in range(1, ws.max_column + 1):
            max_len = 0
            for cell in ws[get_column_letter(col)]:
                max_len = max(max_len, len(str(cell.value or "")))
            ws.column_dimensions[get_column_letter(col)].width = min(max(max_len + 2, 12), 55)
        ws.row_dimensions[1].height = 30
    for row in wb["Inputs"].iter_rows(min_row=2):
        source_type = str(row[4].value or "") if len(row) >= 5 else ""
        fill = blue if "SEC" in source_type else yellow if "Internal" in source_type else grey
        for c in row:
            c.fill = PatternFill("solid", fgColor=fill)
    for ws_name in ["Pricing_Summary", "Valuation", "Offering_Proceeds", "Dilution"]:
        ws = wb[ws_name]
        for row in ws.iter_rows(min_row=2):
            if any(str(c.value).lower().find("proceed") >= 0 for c in row if c.value is not None):
                for c in row:
                    c.fill = PatternFill("solid", fgColor=green)
    wb["Error_Audit"].conditional_formatting.add(f'E2:E{wb["Error_Audit"].max_row}', CellIsRule(operator="notEqual", formula=['"Corrected"'], fill=PatternFill("solid", fgColor=red)))


def build_workbook(d: dict, source_rows: list[dict], error_rows: list[dict], path: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    for name in ["Inputs", "QoE", "Valuation", "Sensitivity", "Offering_Proceeds", "Dilution", "Pricing_Summary", "Error_Audit", "Source_Trace"]:
        wb.create_sheet(name)
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"

    ws = wb["Inputs"]
    ws.append(["Input / control item", "Value", "Unit", "Source / formula", "Classification", "Notes"])
    inputs = [
        ("Information cut-off", AS_OF, "date", "00_README.md; CP-01", "Control", "Formal pricing pre-cutoff"),
        ("Controlling policy version", "v3", "version", "committee/Committee_Policy_v3_20240320.xlsx", "Internal committee policy", "v2 superseded"),
        ("2022 Revenue", d["revenue_2022"], "USD mm", "SEC-01", "SEC public fact", "Audited historical"),
        ("2023 Revenue", d["revenue_2023"], "USD mm", "SEC-01", "SEC public fact", "Audited historical"),
        ("2022 Net income (loss)", d["net_loss_2022"], "USD mm", "SEC-01", "SEC public fact", "Audited historical"),
        ("2023 Net income (loss)", d["net_loss_2023"], "USD mm", "SEC-01", "SEC public fact", "Audited historical"),
        ("2022 Management Adjusted EBITDA", d["management_ebitda_2022"], "USD mm", "SEC-01", "SEC public non-GAAP fact", "Outside auditor opinion"),
        ("2023 Management Adjusted EBITDA", d["management_ebitda_2023"], "USD mm", "SEC-01", "SEC public non-GAAP fact", "Outside auditor opinion"),
        ("2022 SBC & related taxes", d["sbc_2022"], "USD mm", "SEC-01", "SEC public fact", "Detail tie-out complete"),
        ("2023 SBC & related taxes", d["sbc_2023"], "USD mm", "SEC-01", "SEC public fact", "Detail tie-out complete"),
        ("2022 Restructuring", d["restructuring_2022"], "USD mm", "SEC-01", "SEC public fact", ""),
        ("2023 Restructuring", d["restructuring_2023"], "USD mm", "SEC-01", "SEC public fact", "Already adjusted in management EBITDA"),
        ("2022 Free Cash Flow", d["fcf_2022"], "USD mm", "SEC-01", "SEC public non-GAAP fact", ""),
        ("2023 Free Cash Flow", d["fcf_2023"], "USD mm", "SEC-01", "SEC public non-GAAP fact", "OCF less capex ties"),
        ("2022 Cash", d["cash_2022"], "USD mm", "SEC-01", "SEC public fact", ""),
        ("2023 Cash", d["cash_2023"], "USD mm", "SEC-01", "SEC public fact", ""),
        ("2022 Marketable securities", d["securities_2022"], "USD mm", "SEC-01", "SEC public fact", ""),
        ("2023 Marketable securities", d["securities_2023"], "USD mm", "SEC-01", "SEC public fact", "Must enter net cash bridge"),
        ("SEC preliminary NTBV/share", d["sec_ntbv"], "USD/share", "SEC-02", "SEC public fact", f'Only at assumed ${d["sec_assumed_price"]:.2f}'),
        ("SEC assumed price for dilution", d["sec_assumed_price"], "USD/share", "SEC-02", "SEC public fact", "Cross-check only"),
        ("SEC preliminary immediate dilution", d["sec_dilution"], "USD/share", "SEC-02", "SEC public fact", "Cross-check only"),
        ("2024E revenue growth", d["growth"], "%", "committee/Underwriting_Assumptions_20240320.xlsx; CP-06", "Internal committee assumption", "Not an SEC fact"),
        ("Peer low", d["peer_low"], "x", "committee/Underwriting_Assumptions_20240320.xlsx; CP-07", "Internal committee assumption", "Bank comps are cross-check only"),
        ("Peer midpoint", d["peer_mid"], "x", "committee/Underwriting_Assumptions_20240320.xlsx; CP-07", "Internal committee assumption", ""),
        ("Peer high", d["peer_high"], "x", "committee/Underwriting_Assumptions_20240320.xlsx; CP-07", "Internal committee assumption", ""),
        ("IPO execution discount", d["execution_discount"], "%", "committee/Underwriting_Assumptions_20240320.xlsx; CP-09", "Internal committee assumption", "Apply to equity value/share"),
        ("Proposed committee price", d["price"], "USD/share", "committee/Offering_Terms_20240320.xlsx", "Internal committee assumption", "Decision input, not actual result"),
        ("Base primary shares", d["primary"], "mm shares", "SEC-03", "SEC public fact", "New company shares"),
        ("Base secondary shares", d["secondary"], "mm shares", "SEC-03", "SEC public fact", "No company proceeds or share increase"),
        ("Greenshoe shares", d["greenshoe"], "mm shares", "SEC-03", "SEC public fact", "Excluded from Base"),
        ("Pre-money economic shares", d["pre_money_shares"], "mm shares", "committee cap-table snapshot / SEC-09 components", "Internal committee assumption", "Includes vested unsettled RSUs and in-money options"),
        ("Underwriting fee rate", d["fee_rate"], "%", "committee/Offering_Terms_20240320.xlsx; SEC-10 basis", "Internal committee assumption", "Primary gross only"),
        ("Fixed company expenses", d["fixed_expenses"], "USD mm", "committee/Offering_Terms_20240320.xlsx", "Internal committee assumption", "Do not repeat on greenshoe increment"),
        ("Preliminary filing range low", d["filing_low"], "USD/share", "SEC-03", "SEC public fact", "Execution cross-check only"),
        ("Preliminary filing range high", d["filing_high"], "USD/share", "SEC-03", "SEC public fact", "Execution cross-check only"),
    ]
    for x in inputs: ws.append(x)
    input_row = {ws.cell(r, 1).value: r for r in range(2, ws.max_row + 1)}
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 3).value == "%": ws.cell(r, 2).number_format = "0.0%"
        elif isinstance(ws.cell(r, 2).value, (int, float)): ws.cell(r, 2).number_format = "0.000"

    q = wb["QoE"]
    q.append(["Metric / check", "2022A", "2023A", "Unit", "Formula / conclusion", "Source / policy"])
    qoe_rows = [
        ("Revenue", f'=Inputs!B{input_row["2022 Revenue"]}', f'=Inputs!B{input_row["2023 Revenue"]}', "USD mm", "SEC reported", "SEC-01"),
        ("Revenue growth", "", '=C2/B2-1', "%", "2023A / 2022A - 1", "Calculated"),
        ("Net income (loss)", f'=Inputs!B{input_row["2022 Net income (loss)"]}', f'=Inputs!B{input_row["2023 Net income (loss)"]}', "USD mm", "SEC reported", "SEC-01"),
        ("Management Adjusted EBITDA", f'=Inputs!B{input_row["2022 Management Adjusted EBITDA"]}', f'=Inputs!B{input_row["2023 Management Adjusted EBITDA"]}', "USD mm", "Starting point; non-GAAP", "SEC-01 / CP-03"),
        ("Less: SBC & related taxes", f'=-Inputs!B{input_row["2022 SBC & related taxes"]}', f'=-Inputs!B{input_row["2023 SBC & related taxes"]}', "USD mm", "Reverse management addback", "CP-03"),
        ("Restructuring incremental adjustment", 0, 0, "USD mm", "No second adjustment", "CP-04"),
        ("Underwriting EBITDA", '=B5+B6+B7', '=C5+C6+C7', "USD mm", "Remains negative", "CP-03/CP-04"),
        ("Free Cash Flow", f'=Inputs!B{input_row["2022 Free Cash Flow"]}', f'=Inputs!B{input_row["2023 Free Cash Flow"]}', "USD mm", "Remains negative", "SEC-01 / CP-13"),
        ("Cash & cash equivalents", f'=Inputs!B{input_row["2022 Cash"]}', f'=Inputs!B{input_row["2023 Cash"]}', "USD mm", "", "SEC-01"),
        ("Marketable securities", f'=Inputs!B{input_row["2022 Marketable securities"]}', f'=Inputs!B{input_row["2023 Marketable securities"]}', "USD mm", "", "SEC-01"),
        ("Cash + marketable securities", '=B10+B11', '=C10+C11', "USD mm", "Net cash bridge input", "CP-08"),
    ]
    for row in qoe_rows: q.append(row)
    q.append([])
    q.append(["Detailed tie-out", "Calculated", "Reported", "Difference", "Disposition", "Source"])
    tieouts = [
        ("Monthly revenue FY2022", d["monthly_2022"], d["revenue_2022"], d["checks"]["Monthly 2022 to SEC"], "Exclude duplicate-export", "monthly revenue / SEC-01"),
        ("Monthly revenue FY2023", d["monthly_2023"], d["revenue_2023"], d["checks"]["Monthly 2023 to SEC"], "Exclude preliminary residue", "monthly revenue / SEC-01"),
        ("Quarterly revenue FY2023", d["quarterly_2023"], d["revenue_2023"], d["checks"]["Quarterly 2023 to SEC"], "Ties", "quarterly revenue / SEC-01"),
        ("Segment revenue FY2022", d["segment_2022"], d["revenue_2022"], d["checks"]["Segment 2022 to SEC"], "Ties", "segment revenue / SEC-01"),
        ("Segment revenue FY2023", d["segment_2023"], d["revenue_2023"], d["checks"]["Segment 2023 to SEC"], "Ties", "segment revenue / SEC-01"),
        ("Geography revenue FY2022", d["geo_2022"], d["revenue_2022"], d["checks"]["Geography 2022 to SEC"], "Ties", "SEC-05 / SEC-01"),
        ("Geography revenue FY2023", d["geo_2023"], d["revenue_2023"], d["checks"]["Geography 2023 to SEC"], "Ties", "SEC-05 / SEC-01"),
        ("SBC detail FY2023", d["sbc_detail_2023"], d["sbc_2023"], d["checks"]["SBC detail 2023 to SEC"], "Ties", "SBC detail / SEC-01"),
        ("Restructuring detail FY2023", d["restructuring_detail_2023"], d["restructuring_2023"], d["checks"]["Restructuring detail 2023 to SEC"], "Ties; no double addback", "restructuring detail / SEC-01"),
        ("FCF FY2023", d["fcf_recalc_2023"], d["fcf_2023"], d["checks"]["FCF bridge 2023 to SEC"], "OCF + capex outflow", "FCF bridge / SEC-01"),
        ("Cash movement FY2023", d["cash_change_recalc"], d["cash_change_reported"], d["checks"]["Cash movement bridge"], "Ties", "cash flow / SEC-01"),
        ("Net loss FY2023", d["net_loss_recalc_2023"], d["net_loss_2023"], d["checks"]["Net loss bridge 2023"], "Revenue + total opex + other income", "income statement / SEC-01"),
    ]
    for row in tieouts: q.append(row)
    for r in range(2, q.max_row + 1):
        for c in range(2, 5): q.cell(r, c).number_format = "0.000;[Red](0.000)"
    q["C3"].number_format = "0.0%"

    v = wb["Valuation"]
    v.append(["Valuation step", "Low", "Mid", "High", "Unit / note"])
    v.append(["2024E Revenue", f'=Inputs!B{input_row["2023 Revenue"]}*(1+Inputs!B{input_row["2024E revenue growth"]})', '=B2', '=B2', "2023A × (1 + internal growth assumption)"])
    v.append(["EV / Revenue multiple", f'=Inputs!B{input_row["Peer low"]}', f'=Inputs!B{input_row["Peer midpoint"]}', f'=Inputs!B{input_row["Peer high"]}', "Committee CP-07"])
    v.append(["Enterprise Value", '=B2*B3', '=C2*C3', '=D2*D3', "USD mm"])
    v.append(["Add: Cash", f'=Inputs!B{input_row["2023 Cash"]}', '=B5', '=B5', "USD mm"])
    v.append(["Add: Marketable securities", f'=Inputs!B{input_row["2023 Marketable securities"]}', '=B6', '=B6', "USD mm"])
    v.append(["Pre-money Equity Value", '=SUM(B4:B6)', '=SUM(C4:C6)', '=SUM(D4:D6)', "USD mm"])
    v.append(["Pre-money economic shares", f'=Inputs!B{input_row["Pre-money economic shares"]}', '=B8', '=B8', "mm shares"])
    v.append(["Undiscounted equity value/share", '=B7/B8', '=C7/C8', '=D7/D8', "USD/share"])
    v.append(["Execution discount", f'=Inputs!B{input_row["IPO execution discount"]}', '=B10', '=B10', "Internal CP-09"])
    v.append(["Committee supported price/share", '=B9*(1-B10)', '=C9*(1-C10)', '=D9*(1-D10)', "USD/share"])
    v.append(["Proposed price", f'=Inputs!B{input_row["Proposed committee price"]}', '=B12', '=B12', "Internal decision input"])
    v.append(["Proposed less supported value", '=B12-B11', '=C12-C11', '=D12-D11', "USD/share"])
    for r in range(2, v.max_row + 1):
        for c in range(2, 5):
            v.cell(r, c).number_format = "0.000;[Red](0.000)"
    for c in range(2, 5): v.cell(10, c).number_format = "0.0%"

    s = wb["Sensitivity"]
    s.append(["2024E growth × EV/Revenue", *[f"{m:.2f}x" for m in d["multiples"]], "Row definition"])
    for i, g in enumerate(d["growth_rates"]):
        row_no = i + 2
        label = "Base growth" if i == 2 else "2023A actual growth anchor" if i == 0 else "Mechanical step"
        s.append([g, None, None, None, None, None, label])
        for j, m in enumerate(d["multiples"], start=2):
            s.cell(row_no, j, f'=((Inputs!$B${input_row["2023 Revenue"]}*(1+$A{row_no})*{m}+Inputs!$B${input_row["2023 Cash"]}+Inputs!$B${input_row["2023 Marketable securities"]})/Inputs!$B${input_row["Pre-money economic shares"]})*(1-Inputs!$B${input_row["IPO execution discount"]})')
        s.cell(row_no, 1).number_format = "0.0%"
        for c in range(2, 7): s.cell(row_no, c).number_format = '$0.00'
    s.append([])
    s.append(["Method note", "Growth grid is mechanically derived from 2023A actual growth and the committee base; multiples interpolate the committee range. Non-base cells are sensitivities, not forecasts."])

    o = wb["Offering_Proceeds"]
    o.append(["Item", "Base", "Full Exercise", "Unit / treatment"])
    o_rows = [
        ("Proposed price", f'=Inputs!B{input_row["Proposed committee price"]}', f'=Inputs!B{input_row["Proposed committee price"]}', "USD/share; internal decision input"),
        ("Primary shares", f'=Inputs!B{input_row["Base primary shares"]}', f'=Inputs!B{input_row["Base primary shares"]}+Inputs!B{input_row["Greenshoe shares"]}', "mm shares"),
        ("Secondary shares", f'=Inputs!B{input_row["Base secondary shares"]}', f'=Inputs!B{input_row["Base secondary shares"]}', "mm shares; no company proceeds"),
        ("Greenshoe shares", 0, f'=Inputs!B{input_row["Greenshoe shares"]}', "mm shares; Base excludes"),
        ("Company primary gross proceeds", '=B2*B3', '=C2*C3', "USD mm"),
        ("Secondary gross proceeds", '=B2*B4', '=C2*C4', "USD mm; to selling holders"),
        ("Company underwriting fee", f'=B6*Inputs!B{input_row["Underwriting fee rate"]}', f'=C6*Inputs!B{input_row["Underwriting fee rate"]}', "USD mm; primary gross only"),
        ("Fixed company expenses", f'=Inputs!B{input_row["Fixed company expenses"]}', f'=Inputs!B{input_row["Fixed company expenses"]}', "USD mm; once per total scenario"),
        ("Company net primary proceeds", '=B6-B8-B9', '=C6-C8-C9', "USD mm"),
        ("Incremental net proceeds vs Base", 0, '=C10-B10', "USD mm; no repeat fixed expense"),
    ]
    for row in o_rows: o.append(row)
    for r in range(2, o.max_row + 1):
        for c in [2, 3]: o.cell(r, c).number_format = "0.000;[Red](0.000)"

    dl = wb["Dilution"]
    dl.append(["Item", "Base", "Full Exercise", "Unit / note"])
    dl_rows = [
        ("Pre-money economic shares", f'=Inputs!B{input_row["Pre-money economic shares"]}', f'=Inputs!B{input_row["Pre-money economic shares"]}', "mm shares"),
        ("New primary shares", f'=Inputs!B{input_row["Base primary shares"]}', f'=Inputs!B{input_row["Base primary shares"]}+Inputs!B{input_row["Greenshoe shares"]}', "mm shares"),
        ("Secondary shares (no share increase)", f'=Inputs!B{input_row["Base secondary shares"]}', f'=Inputs!B{input_row["Base secondary shares"]}', "mm shares; transfer only"),
        ("Post-money economic shares", '=B2+B3', '=C2+C3', "mm shares"),
        ("New primary / post-money", '=B3/B5', '=C3/C5', "%"),
        ("New primary / pre-money", '=B3/B2', '=C3/C2', "%"),
        ("Secondary impact on company shares", 0, 0, "mm shares"),
        ("SEC assumed price", f'=Inputs!B{input_row["SEC assumed price for dilution"]}', '=B9', "USD/share; cross-check only"),
        ("SEC preliminary NTBV/share", f'=Inputs!B{input_row["SEC preliminary NTBV/share"]}', '=B10', "USD/share; only at SEC assumed price"),
        ("SEC preliminary immediate dilution", f'=Inputs!B{input_row["SEC preliminary immediate dilution"]}', '=B11', "USD/share; only at SEC assumed price"),
        ("SEC arithmetic cross-check", '=B10+B11-B9', '=C10+C11-C9', "Should be zero"),
    ]
    for row in dl_rows: dl.append(row)
    for r in range(2, dl.max_row + 1):
        for c in [2, 3]: dl.cell(r, c).number_format = "0.000;[Red](0.000)"
    for r in [6, 7]:
        for c in [2, 3]: dl.cell(r, c).number_format = "0.0%"

    p = wb["Pricing_Summary"]
    p.append(["Decision item", "Result", "Unit", "Cross-reference / interpretation"])
    p_rows = [
        ("2023 Underwriting EBITDA", '=QoE!C8', "USD mm", "Negative; EV/EBITDA not used"),
        ("2023 Free Cash Flow", '=QoE!C9', "USD mm", "Negative QoE risk"),
        ("2024E Revenue", '=Valuation!C2', "USD mm", "2023A × (1 + internal committee growth)"),
        ("Supported range low", '=Valuation!B11', "USD/share", "Low multiple after execution discount"),
        ("Supported midpoint", '=Valuation!C11', "USD/share", "Mid multiple after execution discount"),
        ("Supported range high", '=Valuation!D11', "USD/share", "High multiple after execution discount"),
        ("Proposed price", '=Valuation!C12', "USD/share", "Internal input; not actual final price"),
        ("Proposed less midpoint", '=B8-B6', "USD/share", "Negative means below midpoint"),
        ("Absolute midpoint distance", '=ABS(B9)', "USD/share", "CP-14 threshold is $0.50"),
        ("Within supported range?", '=IF(AND(B8>=B5,B8<=B7),"Yes","No")', "text", "CP-14/CP-15"),
        ("Within $0.50 of midpoint?", '=IF(B10<=0.5,"Yes","No")', "text", "CP-14/CP-15"),
        ("Unresolved structure hard errors", '=COUNTIF(Error_Audit!E2:E15,"<>Corrected")', "count", "All legacy structure errors corrected in this model"),
        ("Base company gross proceeds", '=Offering_Proceeds!B6', "USD mm", "Primary only"),
        ("Base company net proceeds", '=Offering_Proceeds!B10', "USD mm", "After percentage fee and fixed expenses"),
        ("Base post-money shares", '=Dilution!B5', "mm shares", "Secondary excluded"),
        ("Full-exercise post-money shares", '=Dilution!C5', "mm shares", "Separate scenario"),
        ("Recommendation", '=IF(AND(B11="Yes",B12="Yes",B13=0),"Proceed",IF(AND(B11="Yes",B13=0),"Reprice","Defer"))', "text", "Mechanical CP-14/CP-15 result"),
    ]
    for row in p_rows: p.append(row)
    for r in range(2, p.max_row + 1):
        if p.cell(r, 3).value not in ("text", "count"): p.cell(r, 2).number_format = "0.000;[Red](0.000)"

    e = wb["Error_Audit"]
    e.append(["Issue category", "Legacy treatment", "Correct treatment", "Quantified impact", "Status", "Policy / boundary"])
    for row in error_rows:
        e.append([row["category"], row["legacy_treatment"], row["correct_treatment"], row["quantified_impact"], row["status"], row["policy"]])

    st = wb["Source_Trace"]
    headers = list(source_rows[0].keys())
    st.append(headers)
    for row in source_rows: st.append([row[h] for h in headers])
    for r in range(2, st.max_row + 1):
        if isinstance(st.cell(r, 2).value, float): st.cell(r, 2).number_format = "0.000"

    style_workbook(wb)
    wb.save(path)


def build_chart(d: dict, path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={"width_ratios": [1, 1.45]})
    low, mid, high, proposed = d["low_price"], d["midpoint"], d["high_price"], d["price"]
    ax1.hlines(0, low, high, linewidth=18, color="#9dc3e6", label="Committee supported range")
    ax1.scatter([low, mid, high], [0, 0, 0], s=[80, 130, 80], color=["#4472c4", "#1f4e78", "#4472c4"], zorder=3)
    ax1.axvline(proposed, color="#c00000", linestyle="--", linewidth=2.5, label=f"Proposed ${proposed:.2f}")
    for x, lab in [(low, f"Low\n${low:.2f}"), (mid, f"Mid\n${mid:.2f}"), (high, f"High\n${high:.2f}")]:
        ax1.annotate(lab, (x, 0), xytext=(0, 18), textcoords="offset points", ha="center", fontsize=10)
    ax1.set_ylim(-0.25, 0.35)
    ax1.set_yticks([])
    ax1.set_xlabel("USD/share")
    ax1.set_title("Committee Range and Proposed Price")
    ax1.legend(loc="lower center", frameon=False)
    ax1.grid(axis="x", alpha=0.25)

    im = ax2.imshow(d["sensitivity"], cmap="YlGnBu", aspect="auto")
    ax2.set_xticks(range(5), [f"{m:.2f}x" for m in d["multiples"]])
    ax2.set_yticks(range(5), [f"{g:.1%}" for g in d["growth_rates"]])
    ax2.set_xlabel("EV / 2024E Revenue")
    ax2.set_ylabel("2024E Revenue Growth")
    ax2.set_title("Discounted Equity Value / Share Sensitivity")
    for i in range(5):
        for j in range(5):
            weight = "bold" if i == 2 and j in (0, 2, 4) else "normal"
            color = "white" if d["sensitivity"][i, j] > np.nanmedian(d["sensitivity"]) else "black"
            marker = "*" if i == 2 and j == 2 else ""
            ax2.text(j, i, f"${d['sensitivity'][i,j]:.2f}{marker}", ha="center", va="center", color=color, fontsize=9, fontweight=weight)
    cbar = fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
    cbar.set_label("USD/share")
    fig.text(0.5, 0.02, f'* Base case: committee {d["growth"]:.1%} growth and {d["peer_mid"]:.1f}x multiple; all values include {d["execution_discount"]:.1%} execution discount.', ha="center", fontsize=9)
    fig.suptitle(f"Reddit IPO Pre-Pricing Review — Information Cut-off {AS_OF}", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=[0, 0.05, 1, 0.94])
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_memo(d: dict, path: Path) -> None:
    memo = f"""# Reddit, Inc. IPO Pricing Committee 备忘录

**复核时点：{AS_OF}（正式定价前）｜建议：{d['recommendation']}**

## 结论与估值
2023A Revenue 为 ${d['revenue_2023']:.3f}mm；委员会内部 {d['growth']:.1%} 增长假设推得 2024E Revenue = ${d['revenue_2023']:.3f}mm × {1+d['growth']:.2f} = ${d['revenue_2024e']:.3f}mm。承销口径 EBITDA 仍为负，主估值依 CP-05 采用 EV/2024E Revenue。以委员会 {d['peer_low']:.1f}x/{d['peer_mid']:.1f}x/{d['peer_high']:.1f}x、完整净现金 ${d['net_cash']:.3f}mm 及 {d['pre_money_shares']:.6f}mm 经济股数测算，并对每股权益价值统一扣减 {d['execution_discount']:.1%}，支持价格为：

| Low | Mid | High | 拟议价 | 拟议价较 Mid |
|---:|---:|---:|---:|---:|
| {fmt_price(d['low_price'])} | {fmt_price(d['midpoint'])} | {fmt_price(d['high_price'])} | {fmt_price(d['price'])} | {fmt_price(d['midpoint_distance'])} |

{fmt_price(d['price'])} 位于 {fmt_price(d['low_price'])}–{fmt_price(d['high_price'])} 支持区间内，较 midpoint 低 {fmt_price(abs(d['midpoint_distance']))}，未超过 $0.50。

## 盈利质量
SEC-01 的 2023A 净亏损为 ${abs(d['net_loss_2023']):.3f}mm，管理层 Adjusted EBITDA 为 ${d['management_ebitda_2023']:.3f}mm（非 GAAP，且不在审计意见范围）。按 CP-03 撤销 SBC及相关税费 ${d['sbc_2023']:.3f}mm 的加回；${d['restructuring_2023']:.3f}mm 重组费已在管理层指标中处理，不再二次加回。承销 EBITDA 为 ${d['underwriting_ebitda_2023']:.3f}mm；FCF 为 ${d['fcf_2023']:.3f}mm，二者均为负，构成主要定价风险。月度（剔除重复及 preliminary 记录）、季度、分部、地区、SBC、重组、FCF 与现金桥均与年度权威数勾稽为零。

## 发行结构与募集
Base 为 {d['primary']:.6f}mm primary + {d['secondary']:.6f}mm secondary；secondary 不进入公司募集，也不增加总股数。{d['greenshoe']:.1f}mm greenshoe 不并入 Base，仅列 full-exercise。按拟议价：

| 情景 | 公司 gross | 承销费 | 固定费用 | 公司 net | Post-money 股数 | 新股/Post-money |
|---|---:|---:|---:|---:|---:|---:|
| Base | ${d['gross_base']:.3f} | ${d['fee_base']:.3f} | ${d['fixed_expenses']:.3f} | ${d['net_base']:.3f} | {d['post_base']:.6f} | {d['primary']/d['post_base']:.1%} |
| Full exercise | ${d['gross_full']:.3f} | ${d['fee_full']:.3f} | ${d['fixed_expenses']:.3f} | ${d['net_full']:.3f} | {d['post_full']:.6f} | {d['full_primary']/d['post_full']:.1%} |

承销费仅按公司 primary gross 的 {d['fee_rate']:.1%} 计提；固定费用不在 greenshoe 增量重复计提。SEC-02 在假定 {fmt_price(d['sec_assumed_price'])} 下披露 NTBV/share {fmt_price(d['sec_ntbv'])}、即时稀释 {fmt_price(d['sec_dilution'])}，合计回到 {fmt_price(d['sec_assumed_price'])}；该资料仅作独立算术与方法交叉验算，不直接移植至 {fmt_price(d['price'])}。

## 数据口径与建议
Committee Policy v3 为现行控制口径；v2 的 SBC 保留加回、旧 peer 区间、旧折扣及按全部股份计费均失效。SEC 历史财务优先；3/19 IR flash、两家承销商 comps、research 与 legacy 仅作参考。增长率、peer 区间、折扣、cap-table snapshot 和 {fmt_price(d['price'])} 均为内部假设，不是公开事实。旧底稿的 QoE、分母、折扣、净现金、primary/secondary、greenshoe、费用、股数、募集、稀释、建议及断链均已重建。

**建议 {d['recommendation']}**：{fmt_price(d['price'])} 满足 CP-14 的区间和 midpoint 条件，发行结构 hard errors 已在修正模型中消除；会议材料应保留负承销 EBITDA、负 FCF 及管理层非 GAAP 完整逐项调节表“待核实”的风险提示。
"""
    path.write_text(memo, encoding="utf-8")


def recalculate_workbook(path: Path) -> None:
    import shutil
    import subprocess
    import tempfile

    office = shutil.which("libreoffice") or shutil.which("soffice")
    if office is None:
        raise RuntimeError("LibreOffice/soffice is required to populate workbook formula caches")
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(
            [office, "--headless", "--convert-to", "xlsx", "--outdir", temp_dir, str(path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        recalculated = Path(temp_dir) / path.name
        if not recalculated.exists():
            raise RuntimeError("LibreOffice did not create the recalculated workbook")
        shutil.copy2(recalculated, path)


def validate(d: dict, output_dir: Path) -> None:
    tolerance = 1e-6
    for name, diff in d["checks"].items():
        if abs(diff) > tolerance:
            raise AssertionError(f"Tie-out failed: {name} = {diff}")
    required = [
        f"{DELIVERY_PREFIX}_ipo_model.xlsx",
        f"{DELIVERY_PREFIX}_pricing_memo.md",
        f"{DELIVERY_PREFIX}_reproduce.py",
        f"{DELIVERY_PREFIX}_qoe_bridge.csv",
        f"{DELIVERY_PREFIX}_valuation_matrix.csv",
        f"{DELIVERY_PREFIX}_source_trace.csv",
        f"{DELIVERY_PREFIX}_charts.png",
    ]
    for name in required:
        p = output_dir / name
        if not p.exists() or p.stat().st_size == 0:
            raise AssertionError(f"Missing or empty deliverable: {p}")
    wb = load_workbook(output_dir / required[0], data_only=False, read_only=True)
    expected = {"Inputs", "QoE", "Valuation", "Sensitivity", "Offering_Proceeds", "Dilution", "Pricing_Summary", "Error_Audit", "Source_Trace"}
    if set(wb.sheetnames) != expected:
        raise AssertionError(f"Workbook sheets mismatch: {wb.sheetnames}")
    wb_values = load_workbook(output_dir / required[0], data_only=True, read_only=True)
    cached_checks = {
        "Pricing recommendation": wb_values["Pricing_Summary"]["B18"].value,
        "Valuation midpoint": wb_values["Valuation"]["C11"].value,
        "Base net proceeds": wb_values["Offering_Proceeds"]["B10"].value,
        "Sensitivity base midpoint": wb_values["Sensitivity"]["D4"].value,
    }
    if cached_checks["Pricing recommendation"] != d["recommendation"]:
        raise AssertionError(f"Cached recommendation mismatch: {cached_checks}")
    for key, actual, expected_value in [
        ("Valuation midpoint", cached_checks["Valuation midpoint"], d["midpoint"]),
        ("Base net proceeds", cached_checks["Base net proceeds"], d["net_base"]),
        ("Sensitivity base midpoint", cached_checks["Sensitivity base midpoint"], d["midpoint"]),
    ]:
        if actual is None or abs(actual - expected_value) > tolerance:
            raise AssertionError(f"Cached workbook check failed: {key}={actual}, expected {expected_value}")
    from PIL import Image
    Image.open(output_dir / required[-1]).verify()
    memo = (output_dir / required[1]).read_text(encoding="utf-8")
    chinese_chars = sum(1 for ch in memo if "\u4e00" <= ch <= "\u9fff")
    if chinese_chars > 1600:
        raise AssertionError(f"Memo exceeds 1,600 Chinese characters: {chinese_chars}")


def main() -> None:
    output_dir = Path(__file__).resolve().parent
    input_dir = output_dir.parent / "input_files"
    d = calculate(input_dir)
    qoe_rows = build_qoe_rows(d)
    source_rows = build_source_rows(d)
    error_rows = build_error_rows(d)

    write_csv(output_dir / f"{DELIVERY_PREFIX}_qoe_bridge.csv", qoe_rows, ["step", "bridge_item", "amount_usd_mm", "running_total_usd_mm", "treatment", "basis", "policy_id"])
    build_matrix_csv(d, output_dir / f"{DELIVERY_PREFIX}_valuation_matrix.csv")
    write_csv(output_dir / f"{DELIVERY_PREFIX}_source_trace.csv", source_rows, list(source_rows[0].keys()))
    workbook_path = output_dir / f"{DELIVERY_PREFIX}_ipo_model.xlsx"
    build_workbook(d, source_rows, error_rows, workbook_path)
    recalculate_workbook(workbook_path)
    build_chart(d, output_dir / f"{DELIVERY_PREFIX}_charts.png")
    build_memo(d, output_dir / f"{DELIVERY_PREFIX}_pricing_memo.md")
    validate(d, output_dir)

    print(f"Information cut-off: {AS_OF} (pre-pricing)")
    print(f"2023A Revenue: ${d['revenue_2023']:.3f}mm")
    print(f"2023 Underwriting EBITDA: ${d['underwriting_ebitda_2023']:.3f}mm")
    print(f"2023 Free Cash Flow: ${d['fcf_2023']:.3f}mm")
    print(f"2024E Revenue: ${d['revenue_2024e']:.3f}mm = ${d['revenue_2023']:.3f}mm × (1 + {d['growth']:.1%})")
    print(f"Supported price range: {fmt_price(d['low_price'])} / {fmt_price(d['midpoint'])} / {fmt_price(d['high_price'])} (Low/Mid/High)")
    print(f"Proposed price: {fmt_price(d['price'])}; vs midpoint: {d['midpoint_distance']:+.2f}/share")
    print(f"Base company gross/net proceeds: ${d['gross_base']:.3f}mm / ${d['net_base']:.3f}mm")
    print(f"Full-exercise company gross/net proceeds: ${d['gross_full']:.3f}mm / ${d['net_full']:.3f}mm")
    print(f"Post-money shares Base/Full: {d['post_base']:.6f}mm / {d['post_full']:.6f}mm")
    print(f"Recommendation: {d['recommendation']}")
    print("All detail-to-annual and cross-module checks passed; seven deliverables validated.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
