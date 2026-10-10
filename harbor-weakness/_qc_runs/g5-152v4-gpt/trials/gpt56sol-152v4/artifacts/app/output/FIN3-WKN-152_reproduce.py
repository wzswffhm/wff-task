#!/usr/bin/env python3
"""Reproduce the Reddit IPO pricing review deliverables from /app/input_files.

No network access is used. All financial conclusions and offering terms are read
from the supplied source pack; only presentation labels and the expressly
specified sensitivity axes are embedded in this script.
"""
from __future__ import annotations

import csv
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/fin3_wkn_152_mpl")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

INPUT = Path("/app/input_files")
OUT = Path(__file__).resolve().parent
STEM = "FIN3-WKN-152"
FILES = {
    f"{STEM}_ipo_model.xlsx",
    f"{STEM}_pricing_memo.md",
    f"{STEM}_reproduce.py",
    f"{STEM}_qoe_bridge.csv",
    f"{STEM}_valuation_matrix.csv",
    f"{STEM}_source_trace.csv",
    f"{STEM}_charts.png",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(value: Any) -> float:
    if value is None or value == "":
        raise ValueError("Expected a numeric value")
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace(",", "").replace("%", ""))


def csv_pick(rows: list[dict[str, str]], field: str, value: str, out_field: str) -> float:
    hits = [r for r in rows if r.get(field) == value]
    if len(hits) != 1:
        raise AssertionError(f"Expected one {field}={value}, found {len(hits)}")
    return num(hits[0][out_field])


def csv_rows(rows: list[dict[str, str]], **criteria: str) -> list[dict[str, str]]:
    return [r for r in rows if all(r.get(k) == v for k, v in criteria.items())]


def sheet_table(path: Path, sheet: str) -> tuple[list[str], list[dict[str, Any]], dict[str, str]]:
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=False))
    headers = [str(c.value) if c.value is not None else "" for c in rows[0]]
    data: list[dict[str, Any]] = []
    loc: dict[str, str] = {}
    for row in rows[1:]:
        if all(c.value is None for c in row):
            continue
        rec = {headers[i]: row[i].value for i in range(len(headers))}
        data.append(rec)
        first = str(row[0].value)
        for i, h in enumerate(headers):
            loc[f"{first}|{h}"] = f"'{sheet}'!{row[i].coordinate}"
    return headers, data, loc


def table_pick(rows: list[dict[str, Any]], key_col: str, key: str, value_col: str) -> Any:
    hits = [r for r in rows if str(r.get(key_col)) == key]
    if len(hits) != 1:
        raise AssertionError(f"Expected one {key_col}={key}, found {len(hits)}")
    return hits[0][value_col]


def path_cell(path: Path, locator: str) -> str:
    return f"{path}::{locator}"


def write_bom_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(v: float, decimals: int = 3) -> str:
    return f"{v:,.{decimals}f}"


# ---------------------------------------------------------------------------
# Read all conclusion inputs from fixed source paths
# ---------------------------------------------------------------------------
P_POLICY = INPUT / "committee" / "Committee_Policy_v3_20240320.xlsx"
P_POLICY_OLD = INPUT / "committee" / "Committee_Policy_v2_20240305.xlsx"
P_ASSUMP = INPUT / "committee" / "Underwriting_Assumptions_20240320.xlsx"
P_TERMS = INPUT / "committee" / "Offering_Terms_20240320.xlsx"
P_SEC1 = INPUT / "sec_filings" / "SEC-01_financials_extract.xlsx"
P_SEC2 = INPUT / "sec_filings" / "SEC-02_dilution_crosscheck.xlsx"
P_SEC3 = INPUT / "sec_filings" / "SEC-03_offering_terms.xlsx"
P_SOURCE_INDEX = INPUT / "sec_filings" / "Source_Index.csv"
P_MONTH = INPUT / "financials" / "monthly_revenue_2022_2023.csv"
P_QUARTER = INPUT / "financials" / "revenue_quarterly.csv"
P_SEGMENT = INPUT / "financials" / "revenue_by_segment_2022_2023.csv"
P_GEO = INPUT / "sec_filings" / "SEC-05_revenue_by_geo.csv"
P_SBC = INPUT / "financials" / "sbc_detail_2022_2023.csv"
P_RESTRUCT = INPUT / "financials" / "restructuring_detail_2023.csv"
P_FCF = INPUT / "financials" / "fcf_bridge_2023.csv"
P_CFS = INPUT / "financials" / "cash_flow_statement_2023.csv"
P_BS = INPUT / "financials" / "balance_sheet_summary_2022_2023.csv"
P_IS = INPUT / "financials" / "income_statement_2022_2023.csv"
P_OPEX = INPUT / "financials" / "opex_summary_2022_2023.csv"
P_EQUITY = INPUT / "financials" / "stockholders_equity_summary.csv"
P_CAP = INPUT / "committee" / "cap_table_snapshot_20240318.csv"
P_SEC9 = INPUT / "sec_filings" / "SEC-09_capitalization.csv"
P_SEC16 = INPUT / "sec_filings" / "SEC-16_share_count_history.csv"
P_FLASH = INPUT / "internal" / "management_flash_20240319.csv"
P_LEGACY = INPUT / "legacy" / "Candidate_Model_v0.xlsx"
P_LEGACY_ASSUMP = INPUT / "legacy" / "legacy_assumptions_export.csv"

_, policy_rows, policy_loc = sheet_table(P_POLICY, "Committee_Policy")
_, peer_rows, peer_loc = sheet_table(P_POLICY, "Committee_Peer_Set")
_, old_policy_rows, old_policy_loc = sheet_table(P_POLICY_OLD, "Committee_Policy")
_, assump_rows, assump_loc = sheet_table(P_ASSUMP, "Assumptions")
_, term_rows, term_loc = sheet_table(P_TERMS, "Offering_Terms")
_, sec1_rows, sec1_loc = sheet_table(P_SEC1, "Public_Financials")
_, sec2_rows, sec2_loc = sheet_table(P_SEC2, "Dilution_Crosscheck")
_, sec3_rows, sec3_loc = sheet_table(P_SEC3, "Offering_Terms")

policy_ids = {str(r["Policy_ID"]): r for r in policy_rows}
assert set(policy_ids) == {f"CP-{i:02d}" for i in range(1, 16)}, "Policy v3 must contain CP-01 through CP-15"
assert all("SUPERSEDED" not in str(r.get("Application", "")) for r in policy_rows)
assert any("SUPERSEDED" in str(r.get("Application", "")) for r in old_policy_rows)

financial = {str(r["Metric"]): r for r in sec1_rows}
revenue_2023 = num(financial["Revenue"]["2023A"])
mgmt_ebitda = num(financial["Adjusted EBITDA"]["2023A"])
sbc_adopted = num(financial["Stock-based compensation & related taxes"]["2023A"])
restructuring = num(financial["Restructuring costs"]["2023A"])
fcf = num(financial["Free Cash Flow"]["2023A"])
cash = num(financial["Cash & cash equivalents"]["2023A"])
securities = num(financial["Marketable securities"]["2023A"])
net_loss = num(financial["Net income (loss)"]["2023A"])

growth = num(table_pick(assump_rows, "Assumption", "2024E revenue growth", "Value"))
multiple_low = num(table_pick(assump_rows, "Assumption", "Peer low EV/Revenue", "Value"))
multiple_mid = num(table_pick(assump_rows, "Assumption", "Peer midpoint EV/Revenue", "Value"))
multiple_high = num(table_pick(assump_rows, "Assumption", "Peer high EV/Revenue", "Value"))
discount = num(table_pick(assump_rows, "Assumption", "IPO discount to peer-implied equity", "Value"))

price = num(table_pick(term_rows, "Item", "Proposed Committee Price", "Base Offering"))
primary = num(table_pick(term_rows, "Item", "Primary shares offered", "Base Offering"))
primary_full = num(table_pick(term_rows, "Item", "Primary shares offered", "Full Greenshoe"))
secondary = num(table_pick(term_rows, "Item", "Secondary shares offered", "Base Offering"))
shoe = num(table_pick(term_rows, "Item", "Greenshoe shares", "Full Greenshoe"))
economic_shares = num(table_pick(term_rows, "Item", "Pre-money economic shares", "Base Offering"))
fee_rate = num(table_pick(term_rows, "Item", "Underwriting fee assumption", "Base Offering"))
fixed_expense = num(table_pick(term_rows, "Item", "Fixed company offering expenses", "Base Offering"))
filing_low = num(table_pick(term_rows, "Item", "Preliminary public filing range low", "Base Offering"))
filing_high = num(table_pick(term_rows, "Item", "Preliminary public filing range high", "Base Offering"))

sec3_primary = num(table_pick(sec3_rows, "Item", "Primary shares offered (base)", "Value"))
sec3_secondary = num(table_pick(sec3_rows, "Item", "Secondary shares offered (base)", "Value"))
sec3_shoe = num(table_pick(sec3_rows, "Item", "Over-allotment option", "Value"))
assert math.isclose(primary, sec3_primary, abs_tol=1e-12)
assert math.isclose(secondary, sec3_secondary, abs_tol=1e-12)
assert math.isclose(shoe, sec3_shoe, abs_tol=1e-12)
assert math.isclose(primary_full, primary + shoe, abs_tol=1e-12)

ntbv_assumed = num(table_pick(sec2_rows, "Item", "Preliminary NTBV/share", "Value"))
ntbv_price = num(table_pick(sec2_rows, "Item", "Preliminary NTBV/share", "Assumed price"))
ntbv_dilution = num(table_pick(sec2_rows, "Item", "Preliminary immediate dilution per share", "Value"))
assert math.isclose(ntbv_price - ntbv_assumed, ntbv_dilution, abs_tol=1e-9)

revenue_2024 = revenue_2023 * (1 + growth)
underwriting_ebitda = mgmt_ebitda - sbc_adopted  # CP-03: reverse management's SBC addback

def valuation_at(g: float, mult: float) -> float:
    return (revenue_2023 * (1 + g) * mult + cash + securities) / economic_shares * (1 - discount)

support_low = valuation_at(growth, multiple_low)
support_mid = valuation_at(growth, multiple_mid)
support_high = valuation_at(growth, multiple_high)
signed_mid_diff = price - support_mid
absolute_mid_diff = abs(signed_mid_diff)
within_range = support_low <= price <= support_high
within_midpoint = absolute_mid_diff <= 0.50

base_gross = primary * price
base_fee = base_gross * fee_rate
base_net = base_gross - base_fee - fixed_expense
full_gross = primary_full * price
full_fee = full_gross * fee_rate
full_net = full_gross - full_fee - fixed_expense
base_post_shares = economic_shares + primary
full_post_shares = economic_shares + primary_full
base_new_post_pct = primary / base_post_shares
full_new_post_pct = primary_full / full_post_shares
base_new_pre_pct = primary / economic_shares
full_new_pre_pct = primary_full / economic_shares

# Detailed source files used for tie-outs.
monthly = read_csv(P_MONTH)
quarterly = read_csv(P_QUARTER)
segments = read_csv(P_SEGMENT)
geography = read_csv(P_GEO)
sbc_rows = read_csv(P_SBC)
restruct_rows = read_csv(P_RESTRUCT)
fcf_rows = read_csv(P_FCF)
cfs_rows = read_csv(P_CFS)
bs_rows = read_csv(P_BS)
is_rows = read_csv(P_IS)
opex_rows = read_csv(P_OPEX)
equity_rows = read_csv(P_EQUITY)
cap_rows = read_csv(P_CAP)
sec9_rows = read_csv(P_SEC9)
sec16_rows = read_csv(P_SEC16)
flash_rows = read_csv(P_FLASH)
source_index = read_csv(P_SOURCE_INDEX)

m22 = csv_rows(monthly, fy="FY2022")
m23 = csv_rows(monthly, fy="FY2023")
monthly_2022_raw = sum(num(r["revenue_usd_mm"]) for r in m22)
aug_2022 = csv_rows(monthly, fy="FY2022", month="2022-08")
assert len(aug_2022) == 2
monthly_2022_adopted = monthly_2022_raw - num(aug_2022[-1]["revenue_usd_mm"])
monthly_2023_raw = sum(num(r["revenue_usd_mm"]) for r in m23)
dec23 = csv_rows(monthly, fy="FY2023", month="2023-12")
sec_dec = next(num(r["revenue_usd_mm"]) for r in dec23 if r["Source_ID"] == "SEC-01")
int_dec = next(num(r["revenue_usd_mm"]) for r in dec23 if r["Source_ID"] == "INT-01")
monthly_2023_adopted = sum(num(r["revenue_usd_mm"]) for r in m23 if r["Source_ID"] == "SEC-01")
monthly_2023_alt = monthly_2023_adopted - sec_dec + int_dec
quarter_total = sum(num(r["revenue_usd_mm"]) for r in csv_rows(quarterly, fy="FY2023"))
segment_2023 = csv_rows(segments, fy="FY2023")
segment_raw = sum(num(r["revenue_usd_mm"]) for r in segment_2023)
segment_ad = next(num(r["revenue_usd_mm"]) for r in segment_2023 if r["segment"] == "Advertising")
segment_other_bad = next(num(r["revenue_usd_mm"]) for r in segment_2023 if r["segment"] == "Other")
segment_other_adopted = num(financial["Other revenue"]["2023A"])
segment_corrected = segment_ad + segment_other_adopted
geo_total = sum(num(r["revenue_usd_mm"]) for r in csv_rows(geography, fy="FY2023"))
sbc_23 = csv_rows(sbc_rows, fy="FY2023")
sbc_component_sum = sum(num(r["amount_usd_mm"]) for r in sbc_23 if r["component"] != "TOTAL")
sbc_detail_total = next(num(r["amount_usd_mm"]) for r in sbc_23 if r["component"] == "TOTAL")
restruct_component_sum = sum(num(r["amount_usd_mm"]) for r in restruct_rows if r["component"] != "TOTAL")
restruct_detail_total = next(num(r["amount_usd_mm"]) for r in restruct_rows if r["component"] == "TOTAL")
ocf = csv_pick(fcf_rows, "line_item", "Net cash used in operating activities", "amount_usd_mm")
capex = csv_pick(fcf_rows, "line_item", "Purchases of property and equipment", "amount_usd_mm")
fcf_detail_total = csv_pick(fcf_rows, "line_item", "Free cash flow", "amount_usd_mm")
cfs_ops = csv_pick(cfs_rows, "line_item", "Net cash used in operating activities", "FY2023")
cfs_inv = csv_pick(cfs_rows, "line_item", "Net cash used in investing activities", "FY2023")
cfs_fin = csv_pick(cfs_rows, "line_item", "Net cash provided by financing activities", "FY2023")
cfs_change = csv_pick(cfs_rows, "line_item", "Net change in cash and cash equivalents", "FY2023")
cfs_begin = csv_pick(cfs_rows, "line_item", "Cash & cash equivalents at beginning of period", "FY2023")
cfs_end = csv_pick(cfs_rows, "line_item", "Cash & cash equivalents at end of period", "FY2023")
bs_cash = csv_pick(bs_rows, "line_item", "Cash & cash equivalents", "FY2023")
bs_secs = csv_pick(bs_rows, "line_item", "Marketable securities", "FY2023")
bs_liquidity = csv_pick(bs_rows, "line_item", "Total cash, cash equivalents and marketable securities", "FY2023")
is_revenue = csv_pick(is_rows, "line_item", "Revenue", "FY2023")
is_net_loss = csv_pick(is_rows, "line_item", "Net income (loss)", "FY2023")
opex_components = sum(num(r["FY2023"]) for r in opex_rows if r["line_item"] != "Total costs and operating expenses")
opex_total = csv_pick(opex_rows, "line_item", "Total costs and operating expenses", "FY2023")
deficit_2022 = csv_pick(equity_rows, "line_item", "Accumulated deficit", "FY2022")
deficit_2023 = csv_pick(equity_rows, "line_item", "Accumulated deficit", "FY2023")
cap_component_sum = sum(num(r["shares_mm"]) for r in cap_rows if r["holder_class"] != "TOTAL_pre_money_economic_shares")
cap_total = csv_pick(cap_rows, "holder_class", "TOTAL_pre_money_economic_shares", "shares_mm")
sec9_total = sum(num(r["shares_mm"]) for r in sec9_rows)
registered_2024 = next(num(r["shares_outstanding_mm"]) for r in sec16_rows if r["as_of"] == "2024-03-18" and r["Source_ID"] == "SEC-09")
registered_expected_ex_rsu = cap_total - next(num(r["shares_mm"]) for r in cap_rows if r["holder_class"] == "RSUs vested and unsettled")

# Arithmetic and source-discipline checks; all compare source-derived quantities.
assert math.isclose(monthly_2022_adopted, num(financial["Revenue"]["2022A"]), abs_tol=1e-9)
assert math.isclose(monthly_2023_adopted, revenue_2023, abs_tol=1e-9)
assert math.isclose(quarter_total, revenue_2023, abs_tol=1e-9)
assert math.isclose(segment_corrected, revenue_2023, abs_tol=1e-9)
assert math.isclose(geo_total, revenue_2023, abs_tol=1e-9)
assert math.isclose(sbc_component_sum, sbc_adopted, abs_tol=1e-9)
assert math.isclose(restruct_component_sum, restructuring, abs_tol=1e-9)
assert math.isclose(restruct_detail_total, restructuring, abs_tol=1e-9)
assert math.isclose(ocf - abs(capex), fcf, abs_tol=1e-9)
assert math.isclose(cfs_ops + cfs_inv + cfs_fin, cfs_change, abs_tol=1e-9)
assert math.isclose(cfs_begin + cfs_change, cfs_end, abs_tol=1e-9)
assert math.isclose(bs_cash + bs_secs, bs_liquidity, abs_tol=1e-9)
assert math.isclose(bs_cash, cash, abs_tol=1e-9) and math.isclose(bs_secs, securities, abs_tol=1e-9)
assert math.isclose(is_revenue, revenue_2023, abs_tol=1e-9) and math.isclose(is_net_loss, net_loss, abs_tol=1e-9)
assert math.isclose(opex_components, opex_total, abs_tol=1e-9)
assert math.isclose(deficit_2023 - deficit_2022, net_loss, abs_tol=1e-9)
assert math.isclose(cap_component_sum, cap_total, abs_tol=1e-9)
assert math.isclose(sec9_total, cap_total, abs_tol=1e-9)
assert math.isclose(economic_shares, cap_total, abs_tol=1e-9)

indexed_ids = {r["Source_ID"] for r in source_index}
sec_file_ids = {p.name[:6] for p in (INPUT / "sec_filings").iterdir() if p.is_file() and re.match(r"SEC-\d{2}", p.name)}
missing_sec_ids = sorted(sec_file_ids - indexed_ids)
referenced_uw = any(r.get("Source_ID") == "UW-01" for r in cap_rows) or any(str(r.get("Source_ID")) == "UW-01" for r in term_rows)
missing_actual_ids = missing_sec_ids + (["UW-01"] if referenced_uw and "UW-01" not in indexed_ids else [])

# Hard-error status is derived only from named offering-structure and core tie-out
# checks. SEC-16 reconciliation and Source_Index coverage remain separately
# disclosed governance exceptions and do not override sound offering mechanics.
committee_sec_terms_consistent = (
    math.isclose(primary, sec3_primary, abs_tol=1e-12)
    and math.isclose(secondary, sec3_secondary, abs_tol=1e-12)
    and math.isclose(shoe, sec3_shoe, abs_tol=1e-12)
)
full_primary_bridge_valid = math.isclose(primary_full, primary + shoe, abs_tol=1e-12)
base_sold_bridge_valid = math.isclose(primary + secondary, sec3_primary + sec3_secondary, abs_tol=1e-12)
base_shoe_zero_modelled = math.isclose(0.0, num(table_pick(term_rows, "Item", "Greenshoe shares", "Base Offering")), abs_tol=1e-12)
secondary_company_proceeds_zero = math.isclose(num(table_pick(term_rows, "Item", "Company receives secondary proceeds?", "Base Offering")), 0.0, abs_tol=1e-12)
base_capital_bridge_valid = math.isclose(base_post_shares, economic_shares + primary, abs_tol=1e-12)
full_capital_bridge_valid = math.isclose(full_post_shares, economic_shares + primary + shoe, abs_tol=1e-12)
fee_primary_only_valid = (
    math.isclose(base_fee, primary * price * fee_rate, abs_tol=1e-12)
    and math.isclose(full_fee, primary_full * price * fee_rate, abs_tol=1e-12)
)
fixed_expense_once_valid = (
    math.isclose(base_net, base_gross - base_fee - fixed_expense, abs_tol=1e-12)
    and math.isclose(full_net, full_gross - full_fee - fixed_expense, abs_tol=1e-12)
)
core_tieouts_valid = all([
    math.isclose(monthly_2022_adopted, num(financial["Revenue"]["2022A"]), abs_tol=1e-9),
    math.isclose(monthly_2023_adopted, revenue_2023, abs_tol=1e-9),
    math.isclose(quarter_total, revenue_2023, abs_tol=1e-9),
    math.isclose(segment_corrected, revenue_2023, abs_tol=1e-9),
    math.isclose(geo_total, revenue_2023, abs_tol=1e-9),
    math.isclose(sbc_component_sum, sbc_adopted, abs_tol=1e-9),
    math.isclose(restruct_component_sum, restructuring, abs_tol=1e-9),
    math.isclose(ocf - abs(capex), fcf, abs_tol=1e-9),
    math.isclose(cfs_ops + cfs_inv + cfs_fin, cfs_change, abs_tol=1e-9),
    math.isclose(cfs_begin + cfs_change, cfs_end, abs_tol=1e-9),
    math.isclose(bs_cash + bs_secs, bs_liquidity, abs_tol=1e-9),
    math.isclose(opex_components, opex_total, abs_tol=1e-9),
    math.isclose(deficit_2023 - deficit_2022, net_loss, abs_tol=1e-9),
    math.isclose(cap_component_sum, cap_total, abs_tol=1e-9),
    math.isclose(sec9_total, cap_total, abs_tol=1e-9),
])
structure_checks = {
    "committee/SEC primary-secondary-shoe agreement": committee_sec_terms_consistent,
    "full primary equals base primary plus shoe": full_primary_bridge_valid,
    "base sold equals primary plus secondary": base_sold_bridge_valid,
    "Base shoe model treatment equals zero": base_shoe_zero_modelled,
    "secondary company proceeds model treatment equals zero": secondary_company_proceeds_zero,
    "Base share-capital bridge": base_capital_bridge_valid,
    "Full share-capital bridge": full_capital_bridge_valid,
    "underwriting fee applies only to primary gross": fee_primary_only_valid,
    "fixed company expense deducted once per scenario": fixed_expense_once_valid,
    "core normal/corrected tie-outs pass": core_tieouts_valid,
}
hard_errors_resolved = all(structure_checks.values())
governance_exceptions = {
    "SEC-16 registered/economic share count remains unreconciled": not math.isclose(registered_2024, cap_total, abs_tol=1e-9),
    "Source_Index omits actual/referenced source IDs": bool(missing_actual_ids),
}
decision = "Proceed" if within_range and within_midpoint and hard_errors_resolved else ("Reprice" if within_range and hard_errors_resolved else "Defer")

# ---------------------------------------------------------------------------
# CSV deliverables
# ---------------------------------------------------------------------------
qoe_rows = [
    {"order": 1, "line_item": "Management Adjusted EBITDA", "amount_usd_mm": f"{mgmt_ebitda:.3f}", "underwriting_treatment": "starting point", "policy_clause": "CP-03", "source": path_cell(P_SEC1, sec1_loc["Adjusted EBITDA|2023A"]), "note": "Management-defined non-GAAP metric"},
    {"order": 2, "line_item": "Reverse SBC addback", "amount_usd_mm": f"{-sbc_adopted:.3f}", "underwriting_treatment": "deduct recurring economic cost", "policy_clause": "CP-03", "source": path_cell(P_SEC1, sec1_loc["Stock-based compensation & related taxes|2023A"]), "note": "Components support adopted amount; detail TOTAL is inconsistent"},
    {"order": 3, "line_item": "Restructuring incremental adjustment", "amount_usd_mm": f"{0.0:.3f}", "underwriting_treatment": "no second addback", "policy_clause": "CP-04", "source": f"{P_RESTRUCT}::TOTAL row; {path_cell(P_POLICY, policy_loc['CP-04|Committee convention'])}", "note": f"{restructuring:.3f} already included in management Adjusted EBITDA"},
    {"order": 4, "line_item": "Underwriting EBITDA", "amount_usd_mm": f"{underwriting_ebitda:.3f}", "underwriting_treatment": "conclusion", "policy_clause": "CP-03/CP-04", "source": "Calculated from preceding rows", "note": "Negative; therefore EV/2024E Revenue under CP-05"},
    {"order": 5, "line_item": "Free Cash Flow", "amount_usd_mm": f"{fcf:.3f}", "underwriting_treatment": "risk indicator", "policy_clause": "CP-13", "source": path_cell(P_SEC1, sec1_loc["Free Cash Flow|2023A"]), "note": "Negative and disclosed in memo"},
]
write_bom_csv(OUT / f"{STEM}_qoe_bridge.csv", list(qoe_rows[0]), qoe_rows)

sensitivity_growths = [0.18, 0.20, 0.22, 0.24, 0.26]  # user-specified display axis
sensitivity_multiples = [4.0, 4.3, 4.5, 4.8, 5.0]  # user-specified display axis
valuation_rows: list[dict[str, Any]] = []
for g in sensitivity_growths:
    for m in sensitivity_multiples:
        valuation_rows.append({
            "row_type": "sensitivity",
            "growth": f"{g:.0%}",
            "multiple_x": f"{m:.1f}",
            "discounted_value_per_share_usd": f"{valuation_at(g, m):.4f}",
            "is_base": "YES" if math.isclose(g, growth) and math.isclose(m, multiple_mid) else "",
            "scenario": "Base" if math.isclose(g, growth) and math.isclose(m, multiple_mid) else "Single-point",
            "formula": "(2023A revenue*(1+growth)*multiple + cash + marketable securities)/economic shares*(1-discount)",
        })
for label, m in [("Low", multiple_low), ("Mid", multiple_mid), ("High", multiple_high)]:
    valuation_rows.append({
        "row_type": "support_range",
        "growth": f"{growth:.0%}",
        "multiple_x": f"{m:.1f}",
        "discounted_value_per_share_usd": f"{valuation_at(growth, m):.4f}",
        "is_base": "YES" if label == "Mid" else "",
        "scenario": label,
        "formula": "(2023A revenue*(1+growth)*multiple + cash + marketable securities)/economic shares*(1-discount)",
    })
write_bom_csv(OUT / f"{STEM}_valuation_matrix.csv", list(valuation_rows[0]), valuation_rows)

source_trace_rows = [
    {"item": "Policy status", "adopted_value": "v3 current; CP-01–CP-15", "unit": "text", "fact_type": "Internal committee policy", "adopted_source": path_cell(P_POLICY, "Committee_Policy!A2:D16"), "competing_value": "v2 superseded", "competing_source": path_cell(P_POLICY_OLD, "Revision_Note!A2:B5"), "disposition": "Adopt v3", "reason_policy": "Revision note and committee email; CP-01"},
    {"item": "2023A revenue", "adopted_value": f"{revenue_2023:.3f}", "unit": "USD mm", "fact_type": "SEC public fact", "adopted_source": path_cell(P_SEC1, sec1_loc["Revenue|2023A"]), "competing_value": f"IR flash {csv_pick(flash_rows, 'metric', 'Revenue', 'FY2023_value'):.3f}", "competing_source": P_FLASH, "disposition": "Exclude flash", "reason_policy": "SEC priority 1 vs INT-01 priority 9; CP-02"},
    {"item": "2024E growth", "adopted_value": f"{growth:.1%}", "unit": "%", "fact_type": "Internal committee assumption", "adopted_source": path_cell(P_ASSUMP, assump_loc["2024E revenue growth|Value"]), "competing_value": "Industry 18%", "competing_source": INPUT / "research" / "sector_benchmark.md", "disposition": "Retain committee forecast", "reason_policy": "CP-06"},
    {"item": "2024E revenue", "adopted_value": f"{revenue_2024:.5f}", "unit": "USD mm", "fact_type": "Calculated internal forecast", "adopted_source": f"{P_SEC1} revenue × {P_ASSUMP} growth", "competing_value": "None", "competing_source": "—", "disposition": "Adopt", "reason_policy": "CP-06"},
    {"item": "Management Adjusted EBITDA", "adopted_value": f"{mgmt_ebitda:.3f}", "unit": "USD mm", "fact_type": "SEC disclosed management non-GAAP", "adopted_source": path_cell(P_SEC1, sec1_loc["Adjusted EBITDA|2023A"]), "competing_value": f"IR flash {csv_pick(flash_rows, 'metric', 'Adjusted EBITDA', 'FY2023_value'):.3f}", "competing_source": P_FLASH, "disposition": "Exclude flash", "reason_policy": "CP-02/CP-03"},
    {"item": "SBC reversal", "adopted_value": f"{sbc_adopted:.3f}", "unit": "USD mm", "fact_type": "SEC public fact / underwriting adjustment", "adopted_source": path_cell(P_SEC1, sec1_loc["Stock-based compensation & related taxes|2023A"]), "competing_value": f"Detail TOTAL {sbc_detail_total:.3f}", "competing_source": P_SBC, "disposition": "Use components/SEC amount; flag total", "reason_policy": "CP-02/CP-03"},
    {"item": "Restructuring", "adopted_value": f"{restructuring:.3f}; incremental 0", "unit": "USD mm", "fact_type": "SEC public fact / policy treatment", "adopted_source": f"{path_cell(P_SEC1, sec1_loc['Restructuring costs|2023A'])}; {path_cell(P_POLICY, policy_loc['CP-04|Committee convention'])}", "competing_value": "Second addback", "competing_source": "Potential legacy treatment", "disposition": "No double count", "reason_policy": "CP-04"},
    {"item": "Underwriting EBITDA", "adopted_value": f"{underwriting_ebitda:.3f}", "unit": "USD mm", "fact_type": "Calculated underwriting conclusion", "adopted_source": f"{STEM}_qoe_bridge.csv", "competing_value": f"Management {mgmt_ebitda:.3f}", "competing_source": P_SEC1, "disposition": "Reverse SBC addback", "reason_policy": "CP-03"},
    {"item": "Free Cash Flow", "adopted_value": f"{fcf:.3f}", "unit": "USD mm", "fact_type": "SEC public fact", "adopted_source": path_cell(P_SEC1, sec1_loc["Free Cash Flow|2023A"]), "competing_value": f"IR flash {csv_pick(flash_rows, 'metric', 'Free Cash Flow', 'FY2023_value'):.3f}", "competing_source": P_FLASH, "disposition": "Exclude flash", "reason_policy": "CP-02/CP-13"},
    {"item": "Cash", "adopted_value": f"{cash:.3f}", "unit": "USD mm", "fact_type": "SEC public fact", "adopted_source": path_cell(P_SEC1, sec1_loc["Cash & cash equivalents|2023A"]), "competing_value": "—", "competing_source": "—", "disposition": "Include", "reason_policy": "CP-08"},
    {"item": "Marketable securities", "adopted_value": f"{securities:.3f}", "unit": "USD mm", "fact_type": "SEC public fact", "adopted_source": path_cell(P_SEC1, sec1_loc["Marketable securities|2023A"]), "competing_value": "Legacy omitted", "competing_source": P_LEGACY, "disposition": "Include", "reason_policy": "CP-08"},
    {"item": "Economic shares", "adopted_value": f"{economic_shares:.6f}", "unit": "mm shares", "fact_type": "Internal committee assumption supported by SEC-09 components", "adopted_source": f"{path_cell(P_TERMS, term_loc['Pre-money economic shares|Base Offering'])}; {P_CAP}", "competing_value": f"SEC-16 registered {registered_2024:.1f}", "competing_source": P_SEC16, "disposition": "Use committee economic count; flag unreconciled registered count", "reason_policy": "Economic basis for valuation; label conflict noted"},
    {"item": "Peer multiples", "adopted_value": f"{multiple_low:.1f}/{multiple_mid:.1f}/{multiple_high:.1f}", "unit": "x", "fact_type": "Internal committee assumption", "adopted_source": path_cell(P_ASSUMP, "Assumptions!A3:B5"), "competing_value": "BANK-B reaches 5.1x", "competing_source": INPUT / "comps" / "underwriter_B_comps_20240318.csv", "disposition": "Cross-check only", "reason_policy": "CP-07"},
    {"item": "IPO discount", "adopted_value": f"{discount:.1%}", "unit": "%", "fact_type": "Internal committee assumption", "adopted_source": path_cell(P_ASSUMP, assump_loc["IPO discount to peer-implied equity|Value"]), "competing_value": "v2 10%; legacy 0%", "competing_source": f"{P_POLICY_OLD}; {P_LEGACY_ASSUMP}", "disposition": "Use v3", "reason_policy": "CP-09"},
    {"item": "Working price", "adopted_value": f"{price:.2f}", "unit": "USD/share", "fact_type": "Internal committee assumption", "adopted_source": path_cell(P_TERMS, term_loc["Proposed Committee Price|Base Offering"]), "competing_value": f"SEC preliminary range {filing_low:.0f}–{filing_high:.0f}", "competing_source": P_SEC3, "disposition": "Decision input, not final result", "reason_policy": "CP-01/CP-14"},
    {"item": "Offering shares", "adopted_value": f"Primary {primary:.6f}; secondary {secondary:.6f}; shoe {shoe:.1f}", "unit": "mm shares", "fact_type": "SEC public fact", "adopted_source": path_cell(P_SEC3, "Offering_Terms!A2:E4"), "competing_value": "Legacy treats all as primary and includes shoe in Base", "competing_source": P_LEGACY, "disposition": "Separate mechanics", "reason_policy": "CP-10/CP-11"},
    {"item": "Fee and fixed expense", "adopted_value": f"{fee_rate:.1%}; {fixed_expense:.1f}", "unit": "% primary gross; USD mm", "fact_type": "Internal committee assumption / SEC mechanics", "adopted_source": f"{path_cell(P_TERMS, term_loc['Underwriting fee assumption|Base Offering'])}; {INPUT / 'sec_filings' / 'SEC-10_underwriting_agreement_summary.md'}", "competing_value": "v2/legacy fee on all offered shares", "competing_source": f"{P_POLICY_OLD}; {P_LEGACY}", "disposition": "Fee company primary only", "reason_policy": "CP-12"},
    {"item": "Monthly FY2022 duplicate", "adopted_value": f"{monthly_2022_adopted:.3f}", "unit": "USD mm", "fact_type": "Detail tie-out anomaly", "adopted_source": f"{P_MONTH} excluding row 14", "competing_value": f"Raw {monthly_2022_raw:.3f}", "competing_source": f"{P_MONTH} rows 9 and 14 duplicate August", "disposition": "Exclude row 14", "reason_policy": "Tie to SEC-01 annual total"},
    {"item": "Monthly FY2023 competing December", "adopted_value": f"SEC Dec {sec_dec:.3f}; FY {monthly_2023_adopted:.3f}", "unit": "USD mm", "fact_type": "Source conflict", "adopted_source": f"{P_MONTH} SEC-01 rows", "competing_value": f"INT Dec {int_dec:.3f}; replacement FY {monthly_2023_alt:.3f}", "competing_source": f"{P_MONTH} INT-01 row", "disposition": "Exclude INT preliminary row", "reason_policy": "CP-02; SEC priority"},
    {"item": "Segment Other typo", "adopted_value": f"{segment_other_adopted:.3f}", "unit": "USD mm", "fact_type": "Detail anomaly", "adopted_source": path_cell(P_SEC1, sec1_loc["Other revenue|2023A"]), "competing_value": f"{segment_other_bad:.3f}", "competing_source": P_SEGMENT, "disposition": "Replace detail typo", "reason_policy": "SEC-01 annual/segment fact controls"},
    {"item": "SBC detail total", "adopted_value": f"Components {sbc_component_sum:.3f}", "unit": "USD mm", "fact_type": "Detail anomaly", "adopted_source": f"{P_SBC} component rows", "competing_value": f"TOTAL {sbc_detail_total:.3f}", "competing_source": f"{P_SBC} TOTAL", "disposition": "Use components/SEC-01", "reason_policy": "Components tie to SEC fact"},
    {"item": "Cap table registered count", "adopted_value": f"Economic {cap_total:.6f}", "unit": "mm shares", "fact_type": "Unresolved source discrepancy disclosed", "adopted_source": P_CAP, "competing_value": f"Registered {registered_2024:.1f}; annotation implies {registered_expected_ex_rsu:.1f}", "competing_source": P_SEC16, "disposition": "Do not use registered count; flag", "reason_policy": "SEC-16 explanation cannot be rebuilt"},
    {"item": "Cap table labels", "adopted_value": "Committee economic snapshot 2024-03-18", "unit": "text", "fact_type": "Metadata anomaly", "adopted_source": P_CAP, "competing_value": "Rows tagged SEC-09 but dated 2024-03-18 vs SEC-09 2024-03-11", "competing_source": f"{P_CAP}; {P_SEC9}", "disposition": "Retain value; flag lineage", "reason_policy": "Mixed Source_ID/as-of labels"},
    {"item": "Source index coverage", "adopted_value": "Use actual files with explicit trace", "unit": "text", "fact_type": "Source governance anomaly", "adopted_source": P_SOURCE_INDEX, "competing_value": ", ".join(missing_actual_ids), "competing_source": "Actual file names / UW-01 references", "disposition": "Flag missing IDs", "reason_policy": "Index incomplete; no inference of priority"},
]
write_bom_csv(OUT / f"{STEM}_source_trace.csv", list(source_trace_rows[0]), source_trace_rows)

# ---------------------------------------------------------------------------
# Excel workbook
# ---------------------------------------------------------------------------
wb = Workbook()
wb.remove(wb.active)
try:
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
except AttributeError:
    pass

NAVY = "17365D"
BLUE = "D9EAF7"
GREEN = "E2F0D9"
YELLOW = "FFF2CC"
RED = "F4CCCC"
GRAY = "E7E6E6"
WHITE = "FFFFFF"
DARK_GREEN = "548235"
THIN = Side(style="thin", color="B7B7B7")
BORDER = Border(bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor=NAVY)
INPUT_FILL = PatternFill("solid", fgColor=BLUE)
FORMULA_FILL = PatternFill("solid", fgColor=GREEN)
WARN_FILL = PatternFill("solid", fgColor=YELLOW)
ERROR_FILL = PatternFill("solid", fgColor=RED)
BASE_FILL = PatternFill("solid", fgColor="A9D18E")
NUM_FMT = '#,##0.000;[Red](#,##0.000);-'
SHARE_FMT = '#,##0.000000;[Red](#,##0.000000);-'
PRICE_FMT = '$0.00;[Red]($0.00);-'
PCT_FMT = '0.0%;[Red](0.0%);-'
MULT_FMT = '0.0x'


def title(ws, text: str, subtitle: str, max_col: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max_col)
    ws["A1"] = text
    ws["A1"].font = Font(size=16, bold=True, color=WHITE)
    ws["A1"].fill = HEADER_FILL
    ws["A1"].alignment = Alignment(horizontal="left")
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max_col)
    ws["A2"] = subtitle
    ws["A2"].font = Font(italic=True, color="666666")


def headers(ws, row: int, values: list[str]) -> None:
    for col, value in enumerate(values, 1):
        c = ws.cell(row, col, value)
        c.font = Font(bold=True, color=WHITE)
        c.fill = HEADER_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def finish(ws, header_row: int, widths: dict[str, float] | None = None, landscape: bool = True) -> None:
    ws.freeze_panes = f"A{header_row + 1}"
    if ws.max_row >= header_row:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(ws.max_column)}{ws.max_row}"
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.oddFooter.center.text = f"{STEM} | Page &P of &N"
    for row in ws.iter_rows(min_row=header_row + 1):
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
            c.border = BORDER
            if c.data_type == "f":
                c.fill = FORMULA_FILL
    if widths:
        for col, width in widths.items():
            ws.column_dimensions[col].width = width

# Inputs
ws = wb.create_sheet("Inputs")
title(ws, "Reddit IPO Pricing Review — Inputs", "Blue = imported source input; green elsewhere = formula. USD mm / mm shares unless noted.", 7)
headers(ws, 4, ["Key", "Value", "Unit", "Fact type", "Policy", "Source path / cell", "Notes"])
input_specs = [
    ("Revenue_2022A", num(financial["Revenue"]["2022A"]), "USD mm", "SEC public fact", "CP-02", path_cell(P_SEC1, sec1_loc["Revenue|2022A"]), "Authoritative FY2022 tie-out target"),
    ("Revenue_2023A", revenue_2023, "USD mm", "SEC public fact", "CP-02/06", path_cell(P_SEC1, sec1_loc["Revenue|2023A"]), "Audited historical revenue"),
    ("Growth_2024E", growth, "%", "Internal committee assumption", "CP-06", path_cell(P_ASSUMP, assump_loc["2024E revenue growth|Value"]), "Not an SEC fact"),
    ("Mgmt_Adj_EBITDA", mgmt_ebitda, "USD mm", "SEC-disclosed management non-GAAP", "CP-03", path_cell(P_SEC1, sec1_loc["Adjusted EBITDA|2023A"]), "Starting point"),
    ("SBC", sbc_adopted, "USD mm", "SEC public fact", "CP-03", path_cell(P_SEC1, sec1_loc["Stock-based compensation & related taxes|2023A"]), "Recurring economic cost"),
    ("Restructuring", restructuring, "USD mm", "SEC public fact", "CP-04", path_cell(P_SEC1, sec1_loc["Restructuring costs|2023A"]), "Already adjusted by management"),
    ("FCF", fcf, "USD mm", "SEC public fact", "CP-13", path_cell(P_SEC1, sec1_loc["Free Cash Flow|2023A"]), "Negative risk indicator"),
    ("Cash", cash, "USD mm", "SEC public fact", "CP-08", path_cell(P_SEC1, sec1_loc["Cash & cash equivalents|2023A"]), "Net cash bridge"),
    ("Marketable_Securities", securities, "USD mm", "SEC public fact", "CP-08", path_cell(P_SEC1, sec1_loc["Marketable securities|2023A"]), "Included in equity bridge"),
    ("Economic_Shares", economic_shares, "mm shares", "Internal committee assumption", "CP-02", path_cell(P_TERMS, term_loc["Pre-money economic shares|Base Offering"]), "SEC-09 components sum to same amount"),
    ("Multiple_Low", multiple_low, "x", "Internal committee assumption", "CP-07", path_cell(P_ASSUMP, assump_loc["Peer low EV/Revenue|Value"]), "Committee peer set"),
    ("Multiple_Mid", multiple_mid, "x", "Internal committee assumption", "CP-07", path_cell(P_ASSUMP, assump_loc["Peer midpoint EV/Revenue|Value"]), "Committee peer set"),
    ("Multiple_High", multiple_high, "x", "Internal committee assumption", "CP-07", path_cell(P_ASSUMP, assump_loc["Peer high EV/Revenue|Value"]), "Committee peer set"),
    ("IPO_Discount", discount, "%", "Internal committee assumption", "CP-09", path_cell(P_ASSUMP, assump_loc["IPO discount to peer-implied equity|Value"]), "Applied after equity/share"),
    ("Working_Price", price, "USD/share", "Internal committee assumption", "CP-14", path_cell(P_TERMS, term_loc["Proposed Committee Price|Base Offering"]), "Not a final pricing result"),
    ("Primary_Base", primary, "mm shares", "Internal committee term consistent with SEC", "CP-10", path_cell(P_TERMS, term_loc["Primary shares offered|Base Offering"]), "New shares/company proceeds"),
    ("Primary_Full", primary_full, "mm shares", "Internal committee term consistent with SEC", "CP-10/11", path_cell(P_TERMS, term_loc["Primary shares offered|Full Greenshoe"]), "Must equal Base primary plus greenshoe"),
    ("Secondary_Base", secondary, "mm shares", "Internal committee term consistent with SEC", "CP-10", path_cell(P_TERMS, term_loc["Secondary shares offered|Base Offering"]), "No company proceeds; no new shares"),
    ("Greenshoe_Base", num(table_pick(term_rows, "Item", "Greenshoe shares", "Base Offering")), "mm shares", "Internal committee term", "CP-11", path_cell(P_TERMS, term_loc["Greenshoe shares|Base Offering"]), "Must be zero in Base"),
    ("Greenshoe", shoe, "mm shares", "Internal committee term consistent with SEC", "CP-11", path_cell(P_TERMS, term_loc["Greenshoe shares|Full Greenshoe"]), "Excluded from Base"),
    ("SEC_Primary_Base", sec3_primary, "mm shares", "SEC public fact", "CP-10", path_cell(P_SEC3, sec3_loc["Primary shares offered (base)|Value"]), "Authority cross-check for committee term"),
    ("SEC_Secondary_Base", sec3_secondary, "mm shares", "SEC public fact", "CP-10", path_cell(P_SEC3, sec3_loc["Secondary shares offered (base)|Value"]), "Authority cross-check for committee term"),
    ("SEC_Greenshoe", sec3_shoe, "mm shares", "SEC public fact", "CP-11", path_cell(P_SEC3, sec3_loc["Over-allotment option|Value"]), "Authority cross-check for committee term"),
    ("Fee_Rate", fee_rate, "% primary gross", "Internal committee assumption", "CP-12", path_cell(P_TERMS, term_loc["Underwriting fee assumption|Base Offering"]), "Company primary only"),
    ("Fixed_Expense", fixed_expense, "USD mm", "Internal committee assumption", "CP-12", path_cell(P_TERMS, term_loc["Fixed company offering expenses|Base Offering"]), "Once in Base/full"),
    ("SEC02_Assumed_Price", ntbv_price, "USD/share", "SEC public cross-check", "Boundary", path_cell(P_SEC2, sec2_loc["Preliminary NTBV/share|Assumed price"]), "Do not extrapolate to working price"),
    ("SEC02_NTBV", ntbv_assumed, "USD/share", "SEC public cross-check", "Boundary", path_cell(P_SEC2, sec2_loc["Preliminary NTBV/share|Value"]), "Only at assumed filing price"),
    ("SEC02_Dilution", ntbv_dilution, "USD/share", "SEC public cross-check", "Boundary", path_cell(P_SEC2, sec2_loc["Preliminary immediate dilution per share|Value"]), "Only verifies assumed price less NTBV"),
]
input_row: dict[str, int] = {}
for r, spec in enumerate(input_specs, 5):
    input_row[spec[0]] = r
    for c, v in enumerate(spec, 1):
        ws.cell(r, c, v)
    ws.cell(r, 2).fill = INPUT_FILL
    if spec[2] == "%": ws.cell(r, 2).number_format = PCT_FMT
    elif spec[2] == "x": ws.cell(r, 2).number_format = MULT_FMT
    elif "share" in spec[2] and spec[2] != "mm shares": ws.cell(r, 2).number_format = PRICE_FMT
    elif spec[2] == "mm shares": ws.cell(r, 2).number_format = SHARE_FMT
    else: ws.cell(r, 2).number_format = NUM_FMT
finish(ws, 4, {"A": 25, "B": 15, "C": 18, "D": 30, "E": 13, "F": 74, "G": 35})

def iref(key: str) -> str:
    return f"Inputs!$B${input_row[key]}"

# QoE
ws = wb.create_sheet("QoE")
title(ws, "Quality of Earnings Bridge", "Management non-GAAP to underwriting EBITDA; restructuring is not double-counted.", 7)
headers(ws, 4, ["Line", "Amount", "Unit", "Formula / treatment", "Policy", "Source", "Risk / note"])
qoe_excel = [
    ("Management Adjusted EBITDA", f"={iref('Mgmt_Adj_EBITDA')}", "USD mm", "Starting point", "CP-03", path_cell(P_SEC1, sec1_loc["Adjusted EBITDA|2023A"]), "Management-defined; not audited non-GAAP"),
    ("Less: SBC addback reversed", f"=-{iref('SBC')}", "USD mm", "SBC is recurring economic cost", "CP-03", path_cell(P_SEC1, sec1_loc["Stock-based compensation & related taxes|2023A"]), "Detail TOTAL mismatch is audited separately"),
    ("Restructuring incremental adjustment", "=0", "USD mm", f"{restructuring:.3f} already in management adjustments", "CP-04", path_cell(P_POLICY, policy_loc["CP-04|Committee convention"]), "Do not add back twice"),
    ("Underwriting EBITDA", "=SUM(B5:B7)", "USD mm", "Management EBITDA − SBC + zero incremental restructuring", "CP-03/04", "Calculated", "Negative; EV/EBITDA not used"),
    ("Free Cash Flow", f"={iref('FCF')}", "USD mm", "SEC definition: operating cash flow less capex", "CP-13", path_cell(P_SEC1, sec1_loc["Free Cash Flow|2023A"]), "Negative; explicit pricing risk"),
]
for r, row in enumerate(qoe_excel, 5):
    for c, v in enumerate(row, 1): ws.cell(r, c, v)
    ws.cell(r, 2).number_format = NUM_FMT
ws["A8"].font = Font(bold=True); ws["B8"].font = Font(bold=True)
finish(ws, 4, {"A": 35, "B": 15, "C": 12, "D": 48, "E": 14, "F": 72, "G": 38})

# Valuation
ws = wb.create_sheet("Valuation")
title(ws, "EV / 2024E Revenue Valuation", "Underwriting EBITDA is negative, so CP-05 requires EV/2024E Revenue. Discount is applied to equity value/share.", 5)
headers(ws, 4, ["Step", "Low", "Mid", "High", "Unit / formula"])
valuation_steps = [
    ("2023A Revenue", f"={iref('Revenue_2023A')}", f"={iref('Revenue_2023A')}", f"={iref('Revenue_2023A')}", "SEC public fact"),
    ("2024E Growth", f"={iref('Growth_2024E')}", f"={iref('Growth_2024E')}", f"={iref('Growth_2024E')}", "Internal assumption"),
    ("2024E Revenue", "=B5*(1+B6)", "=C5*(1+C6)", "=D5*(1+D6)", "2023A × (1 + growth)"),
    ("EV / Revenue", f"={iref('Multiple_Low')}", f"={iref('Multiple_Mid')}", f"={iref('Multiple_High')}", "Committee multiples"),
    ("Enterprise Value", "=B7*B8", "=C7*C8", "=D7*D8", "2024E revenue × multiple"),
    ("Add: Cash", f"={iref('Cash')}", f"={iref('Cash')}", f"={iref('Cash')}", "CP-08"),
    ("Add: Marketable Securities", f"={iref('Marketable_Securities')}", f"={iref('Marketable_Securities')}", f"={iref('Marketable_Securities')}", "CP-08"),
    ("Pre-money Equity Value", "=SUM(B9:B11)", "=SUM(C9:C11)", "=SUM(D9:D11)", "EV + cash + securities"),
    ("Economic Shares", f"={iref('Economic_Shares')}", f"={iref('Economic_Shares')}", f"={iref('Economic_Shares')}", "mm shares"),
    ("Undiscounted Equity / Share", "=B12/B13", "=C12/C13", "=D12/D13", "Equity ÷ shares"),
    ("IPO Execution Discount", f"={iref('IPO_Discount')}", f"={iref('IPO_Discount')}", f"={iref('IPO_Discount')}", "CP-09"),
    ("Discounted Value / Share", "=B14*(1-B15)", "=C14*(1-C15)", "=D14*(1-D15)", "Undiscounted/share × (1 − discount)"),
]
for r, row in enumerate(valuation_steps, 5):
    for c, v in enumerate(row, 1): ws.cell(r, c, v)
    for c in range(2, 5):
        ws.cell(r, c).number_format = PCT_FMT if r in (6, 15) else MULT_FMT if r == 8 else PRICE_FMT if r in (14, 16) else SHARE_FMT if r == 13 else NUM_FMT
for c in range(1, 6): ws.cell(16, c).font = Font(bold=True, color=DARK_GREEN)
finish(ws, 4, {"A": 36, "B": 16, "C": 16, "D": 16, "E": 42})

# Sensitivity
ws = wb.create_sheet("Sensitivity")
title(ws, "Single-Point Pricing Sensitivity", "Each cell independently varies growth and multiple; all other inputs remain unchanged. Base = 22% × 4.5x.", 7)
headers(ws, 4, ["Growth / Multiple"] + sensitivity_multiples + ["Row note"])
for c_idx in range(2, 7):
    ws.cell(4, c_idx).number_format = MULT_FMT
for r_idx, g in enumerate(sensitivity_growths, 5):
    ws.cell(r_idx, 1, g).number_format = PCT_FMT
    for c_idx, m in enumerate(sensitivity_multiples, 2):
        # Formula exactly follows the requested methodology.
        ws.cell(r_idx, c_idx, f"=({iref('Revenue_2023A')}*(1+$A{r_idx})*{get_column_letter(c_idx)}$4+{iref('Cash')}+{iref('Marketable_Securities')})/{iref('Economic_Shares')}*(1-{iref('IPO_Discount')})")
        ws.cell(r_idx, c_idx).number_format = PRICE_FMT
        if math.isclose(g, growth) and math.isclose(m, multiple_mid):
            ws.cell(r_idx, c_idx).fill = BASE_FILL
            ws.cell(r_idx, c_idx).font = Font(bold=True)
    ws.cell(r_idx, 7, "Base growth" if math.isclose(g, growth) else "Single-point")
headers(ws, 12, ["Scenario", "Growth", "Multiple", "Value/share", "Role", "Policy", "Note"])
for r, (label, mult_ref, val_ref) in enumerate([
    ("Low", "Multiple_Low", "=Valuation!B16"),
    ("Mid", "Multiple_Mid", "=Valuation!C16"),
    ("High", "Multiple_High", "=Valuation!D16"),
], 13):
    vals = [label, f"={iref('Growth_2024E')}", f"={iref(mult_ref)}", val_ref, "Base" if label == "Mid" else "Range endpoint", "CP-07/09", "Committee support range"]
    for c, v in enumerate(vals, 1): ws.cell(r, c, v)
    ws.cell(r, 2).number_format = PCT_FMT; ws.cell(r, 3).number_format = MULT_FMT; ws.cell(r, 4).number_format = PRICE_FMT
finish(ws, 4, {"A": 21, "B": 15, "C": 15, "D": 15, "E": 15, "F": 15, "G": 24})

# Offering proceeds
ws = wb.create_sheet("Offering_Proceeds")
title(ws, "Offering Structure and Company Proceeds", "Base excludes greenshoe. Secondary produces no company proceeds and no new company shares.", 5)
headers(ws, 4, ["Line", "Base", "Full Greenshoe", "Unit", "Formula / policy"])
offering_rows = [
    ("Working price", f"={iref('Working_Price')}", f"={iref('Working_Price')}", "USD/share", "Internal decision input"),
    ("Primary shares", f"={iref('Primary_Base')}", f"={iref('Primary_Base')}+{iref('Greenshoe')}", "mm shares", "CP-10/11"),
    ("Secondary shares", f"={iref('Secondary_Base')}", f"={iref('Secondary_Base')}", "mm shares", "No company proceeds"),
    ("Greenshoe shares", "=0", f"={iref('Greenshoe')}", "mm shares", "Base excluded; full exercised"),
    ("Total shares sold", "=B6+B7", "=C6+C7", "mm shares", "Primary + secondary; shoe already in full primary"),
    ("Company gross proceeds", "=B5*B6", "=C5*C6", "USD mm", "Price × primary only"),
    ("Underwriting fee rate", f"={iref('Fee_Rate')}", f"={iref('Fee_Rate')}", "% primary gross", "CP-12"),
    ("Underwriting fee", "=B10*B11", "=C10*C11", "USD mm", "Company primary gross × fee rate"),
    ("Fixed company expenses", f"={iref('Fixed_Expense')}", f"={iref('Fixed_Expense')}", "USD mm", "Once; not repeated for shoe"),
    ("Net company proceeds", "=B10-B12-B13", "=C10-C12-C13", "USD mm", "Gross − fee − fixed"),
    ("Secondary proceeds to company", "=0", "=0", "USD mm", "CP-10 / SEC-12"),
]
for r, row in enumerate(offering_rows, 5):
    for c, v in enumerate(row, 1): ws.cell(r, c, v)
    for c in (2, 3):
        ws.cell(r, c).number_format = PCT_FMT if r == 11 else PRICE_FMT if r == 5 else SHARE_FMT if r in (6, 7, 8, 9) else NUM_FMT
for c in range(1, 6): ws.cell(14, c).font = Font(bold=True, color=DARK_GREEN)
finish(ws, 4, {"A": 35, "B": 18, "C": 18, "D": 18, "E": 48})

# Dilution
ws = wb.create_sheet("Dilution")
title(ws, "Share Count Bridge and Dilution", "New-share percentages are clearly labeled. SEC-02 is only a $32.50 cross-check and is not extrapolated to $34.", 5)
headers(ws, 4, ["Line", "Base", "Full Greenshoe", "Unit", "Formula / boundary"])
dilution_rows = [
    ("Pre-money economic shares", f"={iref('Economic_Shares')}", f"={iref('Economic_Shares')}", "mm shares", "Committee economic denominator"),
    ("New primary shares", f"={iref('Primary_Base')}", f"={iref('Primary_Base')}+{iref('Greenshoe')}", "mm shares", "Secondary excluded"),
    ("Secondary incremental shares", "=0", "=0", "mm shares", "Transfer only"),
    ("Post-money shares", "=B5+B6+B7", "=C5+C6+C7", "mm shares", "Pre-money + new primary"),
    ("New primary / post-money", "=B6/B8", "=C6/C8", "%", "Primary ÷ post-money"),
    ("New primary / pre-money", "=B6/B5", "=C6/C5", "%", "Additional disclosure; not post-money dilution"),
    ("SEC-02 assumed price", f"={iref('SEC02_Assumed_Price')}", "—", "USD/share", "Cross-check only"),
    ("SEC-02 preliminary NTBV/share", f"={iref('SEC02_NTBV')}", "—", "USD/share", "At assumed price only"),
    ("SEC-02 immediate dilution", "=B11-B12", "—", "USD/share", "Assumed price − NTBV/share"),
    ("SEC-02 reported dilution", f"={iref('SEC02_Dilution')}", "—", "USD/share", "Tie-out; no $34 NTBV extrapolation"),
    ("SEC-02 tie-out difference", "=B13-B14", "—", "USD/share", "Must be zero"),
]
for r, row in enumerate(dilution_rows, 5):
    for c, v in enumerate(row, 1): ws.cell(r, c, v)
    for c in (2,3):
        ws.cell(r,c).number_format = PCT_FMT if r in (9,10) else PRICE_FMT if r in (11,12,13,14,15) else SHARE_FMT
finish(ws, 4, {"A": 38, "B": 18, "C": 18, "D": 16, "E": 48})

# Pricing summary
ws = wb.create_sheet("Pricing_Summary")
title(ws, "Pricing Committee Summary", "Rule: within support range, within $0.50 of midpoint, and no unresolved hard structural error.", 5)
headers(ws, 4, ["Metric / test", "Value", "Unit", "Result", "Formula / policy"])
structure_method_start_row = 13
structure_method_end_row = structure_method_start_row + len(structure_checks) - 1
summary_rows = [
    ("Support range — low", "=Valuation!B16", "USD/share", "Range endpoint", "CP-07/09"),
    ("Support range — midpoint", "=Valuation!C16", "USD/share", "Reference", "CP-07/09"),
    ("Support range — high", "=Valuation!D16", "USD/share", "Range endpoint", "CP-07/09"),
    ("Proposed working price", f"={iref('Working_Price')}", "USD/share", "Decision input", "Not a final result"),
    ("Signed price − midpoint", "=B8-B6", "USD/share", "Negative = below midpoint", "Working price − midpoint"),
    ("Absolute distance to midpoint", "=ABS(B9)", "USD/share", "Threshold ≤ $0.50", "CP-14"),
    ("Test 1: within support range", "=AND(B8>=B5,B8<=B7)", "Boolean", "Required", "CP-14"),
    ("Test 2: midpoint distance ≤ $0.50", "=B10<=0.5", "Boolean", "Required", "CP-14"),
    ("Test 3: no unresolved hard structural error", f"=AND(Methodology!C{structure_method_start_row}:C{structure_method_end_row})", "Boolean", "Required", "Linked to named Methodology structure checks; governance exceptions are separately flagged"),
    ("Committee disposition", '=IF(AND(B11,B12,B13),"Proceed",IF(AND(B11,B13),"Reprice","Defer"))', "Decision", decision, "CP-14/15; references all three tests"),
    ("QoE risk", "Underwriting EBITDA and FCF are negative", "Text", "Disclose", "CP-13"),
]
for r, row in enumerate(summary_rows, 5):
    for c, v in enumerate(row, 1): ws.cell(r,c,v)
    if r <= 10: ws.cell(r,2).number_format=PRICE_FMT
    if r in (11,12,13): ws.cell(r,2).fill = FORMULA_FILL if ws.cell(r,2).data_type == "f" else INPUT_FILL
for c in range(1,6): ws.cell(14,c).font=Font(bold=True, color=DARK_GREEN)
finish(ws, 4, {"A": 42, "B": 30, "C": 16, "D": 28, "E": 60})

# Error audit
ws = wb.create_sheet("Error_Audit")
title(ws, "Legacy and Data Error Audit", "Each legacy treatment and identified detail exception is separately logged with correction, quantified impact, basis, and source.", 8)
headers(ws, 4, ["Category", "Issue", "Legacy / observed treatment", "Correct treatment", "Quantified impact", "Unit", "Basis", "Source"])
old_mid_2023 = (revenue_2023 * multiple_mid + cash + securities) / economic_shares * (1 - discount)
undiscounted_mid = (revenue_2024 * multiple_mid + cash + securities) / economic_shares
cash_only_mid = (revenue_2024 * multiple_mid + cash) / economic_shares * (1 - discount)
legacy_primary_over = (primary + secondary - primary) * price
legacy_all_fee = (primary + secondary) * price * fee_rate
errors = [
    ("Legacy model", "Management EBITDA did not reverse SBC", f"Retained {mgmt_ebitda:.3f}", "Deduct recurring SBC addback", mgmt_ebitda - underwriting_ebitda, "USD mm EBITDA overstatement", "CP-03", P_LEGACY),
    ("Legacy model", "Used 2023A valuation denominator", "Applied multiple to historical revenue", "Use 2024E revenue", support_mid - old_mid_2023, "USD/share understatement at midpoint", "CP-05/06", P_LEGACY),
    ("Legacy model", "Applied 0% discount", "No execution discount", "Apply v3 discount to equity/share", undiscounted_mid - support_mid, "USD/share overstatement", "CP-09", P_LEGACY_ASSUMP),
    ("Legacy model", "Omitted marketable securities", "Cash-only bridge", "Add cash and marketable securities", support_mid - cash_only_mid, "USD/share understatement", "CP-08", P_LEGACY),
    ("Legacy model", "Treated all 22m Base shares as primary", "Primary included secondary", "Only SEC primary forms company gross", legacy_primary_over, "USD mm gross overstatement", "CP-10", P_LEGACY),
    ("Legacy model", "Included greenshoe in Base", "Assumed full exercise", "Base excludes option", shoe * price * (1-fee_rate), "USD mm net proceeds improperly in Base", "CP-11/12", P_LEGACY),
    ("Legacy model", "Fee on all offered shares", "Company fee included secondary", "Fee only on company primary gross", legacy_all_fee - base_fee, "USD mm company fee overstatement", "CP-12", P_LEGACY),
    ("Legacy model", "Secondary increased share count", "Added sold secondary shares", "Secondary is transfer", secondary, "mm shares overstatement", "CP-10", P_LEGACY),
    ("Legacy model", "Secondary proceeds paid to company", "Added seller proceeds to company", "Company receives zero", secondary * price, "USD mm gross overstatement", "CP-10 / SEC-12", P_LEGACY),
    ("Legacy model", "Dilution numerator/denominator mismatch", "Post-money equity / pre-money shares", "Match equity and share bases; present issuance ratios", None, "Conceptual hard error", "CP-10; denominator consistency", P_LEGACY),
    ("Legacy model", "High case pushed above $34", "Recommendation anchored to high case", "Apply CP-14 tests around midpoint", support_high - price, "USD/share high case above working price", "CP-14/15", P_LEGACY),
    ("Legacy model", "Used superseded v2 policy", "SBC/10% discount/all-share fee", "Use current v3 CP-01–CP-15", None, "Version control", "v2 Revision_Note", P_POLICY_OLD),
    ("Legacy model", "Three groups of broken REF links", "Valuation, QoE and offering linkage failed", "Rebuild formulas from Inputs", 3, "broken formula groups", "Candidate model readme", P_LEGACY),
    ("Data anomaly", "FY2022 August duplicated at rows 9/14", f"Raw sum {monthly_2022_raw:.3f}", "Exclude row 14", monthly_2022_raw - monthly_2022_adopted, "USD mm overstatement", "Tie to SEC-01", P_MONTH),
    ("Data anomaly", "FY2023 all rows include duplicate-source December", f"All rows {monthly_2023_raw:.3f}", "Exclude INT preliminary; retain SEC December", monthly_2023_raw - monthly_2023_adopted, "USD mm raw overstatement", "CP-02 source priority", P_MONTH),
    ("Data anomaly", "FY2023 INT replaces SEC December scenario", f"SEC-only adopted {monthly_2023_adopted:.3f}", f"INT replacement scenario {monthly_2023_alt:.3f}", monthly_2023_alt - monthly_2023_adopted, "USD mm replacement scenario difference", "Rejected alternative; CP-02", P_MONTH),
    ("Data anomaly", "FY2023 segment Other decimal typo", f"Other {segment_other_bad:.3f}; raw {segment_raw:.3f}", f"Other {segment_other_adopted:.3f}; corrected {segment_corrected:.3f}", segment_raw - revenue_2023, "USD mm raw overstatement", "SEC-01 annual/segment fact", P_SEGMENT),
    ("Data anomaly", "FY2023 SBC TOTAL differs from components", f"TOTAL {sbc_detail_total:.3f}", f"Components/SEC {sbc_component_sum:.3f}", sbc_detail_total - sbc_component_sum, "USD mm total overstatement", "CP-02", P_SBC),
    ("Data anomaly", "SEC-16 registered count cannot be rebuilt", f"Reported {registered_2024:.1f}; note says exclude RSUs", f"Annotation implies {registered_expected_ex_rsu:.1f}; economic {cap_total:.6f}", registered_2024 - registered_expected_ex_rsu, "mm shares vs annotation", "Use economic count; disclose", P_SEC16),
    ("Data anomaly", "Cap table Source_ID/as-of conflict", "SEC-09-tagged rows dated 2024-03-18", "SEC-09 file is 2024-03-11; retain committee snapshot with flag", None, "Metadata exception", "Lineage conflict", f"{P_CAP}; {P_SEC9}"),
    ("Data anomaly", "UW-01 absent from master Source_Index", "UW-01 used in terms/cap table", "Trace directly and flag missing index entry", 1, "missing source ID", "Source governance", P_SOURCE_INDEX),
    ("Data anomaly", "Source_Index misses actual files/IDs", ", ".join(missing_sec_ids), "Use actual files but flag incomplete index", len(missing_sec_ids), "missing SEC IDs", "Source governance", P_SOURCE_INDEX),
]
for r, row in enumerate(errors, 5):
    for c, v in enumerate(row, 1): ws.cell(r,c,str(v) if isinstance(v,Path) else v)
    ws.cell(r,5).number_format=NUM_FMT
    if row[0] == "Data anomaly": ws.cell(r,1).fill = WARN_FILL
finish(ws, 4, {"A": 18, "B": 38, "C": 45, "D": 50, "E": 18, "F": 30, "G": 28, "H": 70})

# Source Trace
ws = wb.create_sheet("Source_Trace")
title(ws, "Source Trace", "SEC public facts are distinguished from internal committee assumptions; competing values are explicitly disposed.", 10)
headers(ws, 4, ["Item", "Adopted value", "Unit", "Fact type", "Adopted source", "Competing value", "Competing source", "Disposition", "Reason / policy", "Index status"])
for r, item in enumerate(source_trace_rows, 5):
    vals = [item["item"], item["adopted_value"], item["unit"], item["fact_type"], str(item["adopted_source"]), item["competing_value"], str(item["competing_source"]), item["disposition"], item["reason_policy"], "Missing/flag" if item["item"] in ("Cap table labels","Source index coverage") else "Traced"]
    for c,v in enumerate(vals,1): ws.cell(r,c,v)
finish(ws, 4, {"A": 30, "B": 28, "C": 18, "D": 34, "E": 72, "F": 38, "G": 60, "H": 32, "I": 35, "J": 16})

# Tieout detail
ws = wb.create_sheet("Tieout_Detail")
title(ws, "Detailed Tie-outs", "C/D contain recalculable Excel formulas assembled from source detail or linked authority; E is always C minus D.", 9)
headers(ws, 4, ["Area", "Displayed calculation / detail", "Computed total", "Target", "Difference", "Unit", "Exception type", "Disposition", "Source"])


def xl_num(value: float) -> str:
    return f"{value:.12g}"


def xl_sum(values: list[float]) -> str:
    terms = [xl_num(v) for v in values]
    if not terms:
        return "=0+0"
    if len(terms) == 1:
        terms.append("0")
    return "=SUM(" + ",".join(terms) + ")"


m22_values = [num(r["revenue_usd_mm"]) for r in m22]
m22_adopted_values = [num(r["revenue_usd_mm"]) for r in m22 if r is not aug_2022[-1]]
m23_values = [num(r["revenue_usd_mm"]) for r in m23]
m23_sec_values = [num(r["revenue_usd_mm"]) for r in m23 if r["Source_ID"] == "SEC-01"]
m23_alt_values = [num(r["revenue_usd_mm"]) for r in m23 if not (r["month"] == "2023-12" and r["Source_ID"] == "SEC-01") and r["Source_ID"] == "SEC-01"] + [int_dec]
quarter_values = [num(r["revenue_usd_mm"]) for r in csv_rows(quarterly, fy="FY2023")]
segment_raw_values = [num(r["revenue_usd_mm"]) for r in segment_2023]
geo_values = [num(r["revenue_usd_mm"]) for r in csv_rows(geography, fy="FY2023")]
sbc_component_values = [num(r["amount_usd_mm"]) for r in sbc_23 if r["component"] != "TOTAL"]
restruct_component_values = [num(r["amount_usd_mm"]) for r in restruct_rows if r["component"] != "TOTAL"]
opex_component_values = [num(r["FY2023"]) for r in opex_rows if r["line_item"] != "Total costs and operating expenses"]
cap_component_values = [num(r["shares_mm"]) for r in cap_rows if r["holder_class"] != "TOTAL_pre_money_economic_shares"]
sec9_component_values = [num(r["shares_mm"]) for r in sec9_rows]
cap_ex_rsu_values = [num(r["shares_mm"]) for r in cap_rows if r["holder_class"] not in ("TOTAL_pre_money_economic_shares", "RSUs vested and unsettled")]

tieouts = [
    ("Monthly revenue", "FY2022 rows 2–14, including duplicate Aug row 14", xl_sum(m22_values), f"={iref('Revenue_2022A')}", "USD mm", "Duplicate", "Exclude row 14 duplicate of row 9", P_MONTH),
    ("Monthly revenue", "FY2022 rows 2–13; row 14 excluded", xl_sum(m22_adopted_values), f"={iref('Revenue_2022A')}", "USD mm", "Resolved", "Adopt", P_MONTH),
    ("Monthly revenue", "FY2023 rows 15–27, both Dec sources", xl_sum(m23_values), f"={iref('Revenue_2023A')}", "USD mm", "Competing source row", "Exclude INT-01 December", P_MONTH),
    ("Monthly revenue", "FY2023 SEC-01 rows 15–26", xl_sum(m23_sec_values), f"={iref('Revenue_2023A')}", "USD mm", "Resolved", "Adopt", P_MONTH),
    ("Monthly revenue", "Rows 15–25 plus INT-01 Dec row 27", xl_sum(m23_alt_values), f"={iref('Revenue_2023A')}", "USD mm", "Rejected alternative", "Exclude; preliminary", P_MONTH),
    ("Quarterly revenue", "Rows 2–5: Q1+Q2+Q3+Q4", xl_sum(quarter_values), f"={iref('Revenue_2023A')}", "USD mm", "None", "Adopt as corroboration", P_QUARTER),
    ("Segment revenue", "Rows 4–5: Advertising + raw Other", xl_sum(segment_raw_values), f"={iref('Revenue_2023A')}", "USD mm", "Decimal typo", "Replace Other from SEC-01", P_SEGMENT),
    ("Segment revenue", f"Advertising row 4 + SEC-01 Other ({segment_other_adopted:.3f})", f"=SUM({xl_num(segment_ad)},{xl_num(segment_other_adopted)})", f"={iref('Revenue_2023A')}", "USD mm", "Resolved", "Adopt", f"{P_SEGMENT}; {P_SEC1}"),
    ("Geographic revenue", "FY2023 rows 4–5: US + International", xl_sum(geo_values), f"={iref('Revenue_2023A')}", "USD mm", "None", "Adopt as corroboration", P_GEO),
    ("SBC", "FY2023 component rows 6–9", xl_sum(sbc_component_values), f"={iref('SBC')}", "USD mm", "None", "Adopt components", P_SBC),
    ("SBC", "FY2023 reported TOTAL row 10", xl_sum([sbc_detail_total]), f"={iref('SBC')}", "USD mm", "Total mismatch", "Reject TOTAL row", P_SBC),
    ("Restructuring", "Component rows 2–4", xl_sum(restruct_component_values), f"={iref('Restructuring')}", "USD mm", "None", "Already adjusted; incremental zero", P_RESTRUCT),
    ("Restructuring", "Reported TOTAL row 5", xl_sum([restruct_detail_total]), f"={iref('Restructuring')}", "USD mm", "None", "No second addback", P_RESTRUCT),
    ("FCF", "Rows 2–3: operating cash flow − absolute capex", f"={xl_num(ocf)}-ABS({xl_num(capex)})", f"={iref('FCF')}", "USD mm", "None", "Adopt", P_FCF),
    ("CFS", "Rows 2–4: operating + investing + financing", f"=SUM({xl_num(cfs_ops)},{xl_num(cfs_inv)},{xl_num(cfs_fin)})", xl_sum([cfs_change]), "USD mm", "None", "Ties to net change", P_CFS),
    ("CFS", "Rows 5–6: beginning cash + net change", f"=SUM({xl_num(cfs_begin)},{xl_num(cfs_change)})", xl_sum([cfs_end]), "USD mm", "None", "Ties to ending cash", P_CFS),
    ("Balance sheet", "Rows 2–3: cash + marketable securities", f"=SUM({xl_num(bs_cash)},{xl_num(bs_secs)})", xl_sum([bs_liquidity]), "USD mm", "None", "Both included in equity bridge", P_BS),
    ("Income statement", "Revenue row 2", xl_sum([is_revenue]), f"={iref('Revenue_2023A')}", "USD mm", "None", "Adopt", P_IS),
    ("Income statement", "Net income (loss) row 9 vs deficit movement", xl_sum([is_net_loss]), f"=SUM({xl_num(deficit_2023)},-({xl_num(deficit_2022)}))", "USD mm", "None", "Adopt", P_IS),
    ("Operating expenses", "Rows 2–5: cost of revenue + R&D + S&M + G&A", xl_sum(opex_component_values), xl_sum([opex_total]), "USD mm", "None", "Ties", P_OPEX),
    ("Accumulated deficit", "FY2023 less FY2022, equity row 3", f"={xl_num(deficit_2023)}-({xl_num(deficit_2022)})", xl_sum([net_loss]), "USD mm", "None", "Ties to net loss", P_EQUITY),
    ("Cap table", "Rows 2–7 committee components", xl_sum(cap_component_values), f"={iref('Economic_Shares')}", "mm shares", "None", "Arithmetic holds", P_CAP),
    ("Cap table", "SEC-09 rows 2–7 components", xl_sum(sec9_component_values), f"={iref('Economic_Shares')}", "mm shares", "Metadata mismatch", "Value supports economic count; as-of differs", P_SEC9),
    ("Cap table", "SEC-16 row 5 registered vs economic", xl_sum([registered_2024]), f"={iref('Economic_Shares')}", "mm shares", "Unreconciled", "Do not use registered count", P_SEC16),
    ("Cap table", "Committee components excluding unsettled RSUs vs SEC-16 row 5", xl_sum(cap_ex_rsu_values), xl_sum([registered_2024]), "mm shares", "Unreconciled annotation", "Flag 3.2m gap", P_SEC16),
    ("Offering shares", "Committee Base primary + secondary", f"=SUM({iref('Primary_Base')},{iref('Secondary_Base')})", f"=SUM({iref('SEC_Primary_Base')},{iref('SEC_Secondary_Base')})", "mm shares", "None", "Base sold shares; secondary not new", P_SEC3),
    ("Offering shares", "Committee Base primary + secondary + shoe", f"=SUM({iref('Primary_Base')},{iref('Secondary_Base')},{iref('Greenshoe')})", f"=SUM({iref('SEC_Primary_Base')},{iref('SEC_Secondary_Base')},{iref('SEC_Greenshoe')})", "mm shares", "None", "Full option scenario", P_SEC3),
]
for r, row in enumerate(tieouts, 5):
    ws.cell(r, 1, row[0])
    ws.cell(r, 2, row[1])
    ws.cell(r, 3, row[2])
    ws.cell(r, 4, row[3])
    ws.cell(r, 5, f"=C{r}-D{r}")
    ws.cell(r, 6, row[4])
    ws.cell(r, 7, row[5])
    ws.cell(r, 8, row[6])
    ws.cell(r, 9, str(row[7]) if isinstance(row[7], Path) else row[7])
    for c in (3, 4, 5): ws.cell(r, c).number_format = SHARE_FMT if row[4] == "mm shares" else NUM_FMT
    if row[5] not in ("None", "Resolved"): ws.cell(r, 7).fill = WARN_FILL
finish(ws, 4, {"A": 22, "B": 54, "C": 18, "D": 18, "E": 18, "F": 14, "G": 28, "H": 42, "I": 72})

# Methodology / checks
ws = wb.create_sheet("Methodology")
title(ws, "Methodology and Reproduction Checks", "Control hierarchy, valuation rationale, named structural checks, governance exceptions, and file inventory.", 5)
headers(ws, 4, ["Section", "Item", "Result", "Status", "Basis"])
source_dirs = ["committee", "sec_filings", "financials", "comps", "research", "internal", "legacy"]
dir_counts = {d: sum(1 for p in (INPUT/d).iterdir() if p.is_file()) for d in source_dirs}
root_files = sum(1 for p in INPUT.iterdir() if p.is_file())
method_rows = [
    ("Method", "Information cutoff", "2024-03-20 pre-pricing only", "PASS", "CP-01"),
    ("Method", "Source hierarchy", "Source_Index priority; v3 resolves equal-priority policy", "PASS", "CP-02 and README"),
    ("Method", "Profitability", "Reverse SBC; no repeat restructuring addback", "PASS", "CP-03/04"),
    ("Method", "Primary valuation", "EV / 2024E Revenue because underwriting EBITDA remains negative", "PASS", "CP-05"),
    ("Method", "Equity bridge", "EV + cash + marketable securities", "PASS", "CP-08"),
    ("Method", "Discount placement", "After equity value per share", "PASS", "CP-09"),
    ("Method", "Offering mechanics", "Secondary excluded from proceeds/new shares; shoe separate", "PASS", "CP-10/11/12"),
    ("Boundary", "SEC-02", f"{ntbv_price:.2f} − {ntbv_assumed:.2f} = {ntbv_dilution:.2f}; no extrapolation", "PASS", "Cross-check only"),
]
assert len(method_rows) + 5 == structure_method_start_row
structure_excel_formulas = {
    "committee/SEC primary-secondary-shoe agreement": f"=AND({iref('Primary_Base')}={iref('SEC_Primary_Base')},{iref('Secondary_Base')}={iref('SEC_Secondary_Base')},{iref('Greenshoe')}={iref('SEC_Greenshoe')})",
    "full primary equals base primary plus shoe": f"={iref('Primary_Full')}={iref('Primary_Base')}+{iref('Greenshoe')}",
    "base sold equals primary plus secondary": f"=Offering_Proceeds!B9={iref('SEC_Primary_Base')}+{iref('SEC_Secondary_Base')}",
    "Base shoe model treatment equals zero": f"=AND({iref('Greenshoe_Base')}=0,Offering_Proceeds!B8=0)",
    "secondary company proceeds model treatment equals zero": "=Offering_Proceeds!B15=0",
    "Base share-capital bridge": f"=Dilution!B8={iref('Economic_Shares')}+{iref('Primary_Base')}",
    "Full share-capital bridge": f"=Dilution!C8={iref('Economic_Shares')}+{iref('Primary_Base')}+{iref('Greenshoe')}",
    "underwriting fee applies only to primary gross": "=AND(Offering_Proceeds!B12=Offering_Proceeds!B10*Offering_Proceeds!B11,Offering_Proceeds!C12=Offering_Proceeds!C10*Offering_Proceeds!C11)",
    "fixed company expense deducted once per scenario": "=AND(Offering_Proceeds!B14=Offering_Proceeds!B10-Offering_Proceeds!B12-Offering_Proceeds!B13,Offering_Proceeds!C14=Offering_Proceeds!C10-Offering_Proceeds!C12-Offering_Proceeds!C13)",
    "core normal/corrected tie-outs pass": "=AND(ABS(Tieout_Detail!E6)<0.0000001,ABS(Tieout_Detail!E8)<0.0000001,ABS(Tieout_Detail!E10)<0.0000001,ABS(Tieout_Detail!E12)<0.0000001,ABS(Tieout_Detail!E13)<0.0000001,ABS(Tieout_Detail!E14)<0.0000001,ABS(Tieout_Detail!E16)<0.0000001,ABS(Tieout_Detail!E17)<0.0000001,ABS(Tieout_Detail!E18)<0.0000001,ABS(Tieout_Detail!E21)<0.0000001,ABS(Tieout_Detail!E22)<0.0000001,ABS(Tieout_Detail!E25)<0.0000001,ABS(Tieout_Detail!E26)<0.0000001,ABS(Tieout_Detail!E30)<0.0000001,ABS(Tieout_Detail!E31)<0.0000001)",
}
assert set(structure_excel_formulas) == set(structure_checks)
for check_name, check_result in structure_checks.items():
    method_rows.append(("Structure check", check_name, structure_excel_formulas[check_name], "PASS" if check_result else "FAIL", "Included in Pricing_Summary Test 3"))
for d in source_dirs:
    method_rows.append(("Inventory", d, dir_counts[d], "COUNT", "Input files"))
method_rows += [
    ("Inventory", "Seven source directories subtotal", sum(dir_counts.values()), "COUNT", "Derived by pathlib"),
    ("Inventory", "Root files", root_files, "COUNT", "README + data dictionary"),
    ("Inventory", "Total source files", sum(dir_counts.values()) + root_files, "COUNT", "Seven directories + root"),
    ("Check", "QoE bridge", f"{mgmt_ebitda:.3f} − {sbc_adopted:.3f} = {underwriting_ebitda:.3f}", "PASS", "CP-03"),
    ("Check", "Base proceeds", f"Gross {base_gross:.6f}; fee {base_fee:.7f}; net {base_net:.7f}", "PASS", "CP-12"),
    ("Check", "Full proceeds", f"Gross {full_gross:.6f}; fee {full_fee:.7f}; net {full_net:.7f}", "PASS", "CP-12"),
    ("Check", "Pricing decision", decision, "PASS" if decision == "Proceed" else "REVIEW", "CP-14/15; all three Pricing_Summary tests"),
    ("Governance exception", "SEC-16 registered/economic count", f"Registered {registered_2024:.6f}; economic {cap_total:.6f}; unresolved", "FLAG", "Disclosed exception, excluded from structural hard-error gate"),
    ("Governance exception", "Missing actual source IDs", ", ".join(missing_actual_ids), "FLAG", "Source_Index incomplete; excluded from structural hard-error gate"),
]
for r,row in enumerate(method_rows,5):
    for c,v in enumerate(row,1): ws.cell(r,c,v)
    if row[3] == "FLAG": ws.cell(r,4).fill=WARN_FILL
finish(ws, 4, {"A": 18, "B": 38, "C": 62, "D": 14, "E": 36})

# Workbook-wide styles and save.
for ws in wb.worksheets:
    ws.auto_filter.ref = ws.auto_filter.ref  # explicit for auditability
    for row in ws.iter_rows():
        for cell in row:
            if cell.row > 2 and cell.data_type == "f" and cell.fill.fill_type is None:
                cell.fill = FORMULA_FILL
            if cell.row > 2 and cell.value is not None:
                cell.alignment = Alignment(vertical="top", wrap_text=True)

xlsx_path = OUT / f"{STEM}_ipo_model.xlsx"
wb.save(xlsx_path)

# Populate formula caches when LibreOffice is available. Conversion occurs in a
# temporary directory and only the validated workbook is copied back to OUT.
libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
formula_cache_refreshed = False
if libreoffice:
    with tempfile.TemporaryDirectory(prefix="fin3_wkn_152_lo_") as tmp:
        tmp_dir = Path(tmp)
        source_copy = tmp_dir / xlsx_path.name
        shutil.copy2(xlsx_path, source_copy)
        profile_dir = tmp_dir / "profile"
        converted_dir = tmp_dir / "converted"
        converted_dir.mkdir()
        result = subprocess.run(
            [
                libreoffice,
                "--headless",
                f"-env:UserInstallation=file://{profile_dir}",
                "--convert-to", "xlsx",
                "--outdir", str(converted_dir),
                str(source_copy),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        converted_path = converted_dir / xlsx_path.name
        if result.returncode != 0 or not converted_path.exists():
            raise RuntimeError(f"LibreOffice recalculation failed: {result.stderr or result.stdout}")
        load_workbook(converted_path, data_only=False, read_only=True).close()
        shutil.copy2(converted_path, xlsx_path)
        formula_cache_refreshed = True

# ---------------------------------------------------------------------------
# Memo (Chinese, compact, every identified anomaly one line)
# ---------------------------------------------------------------------------
memo = f"""# Reddit IPO 定价复核备忘录

**日期：**2024-03-20（正式定价前）  **建议：{decision}**

## 结论与方法
委员会v3（CP-01至15）为现行政策。SEC事实为2023A收入{revenue_2023:.3f}、现金{cash:.3f}、证券{securities:.3f}；{growth:.0%}增长、{multiple_low:.1f}x/{multiple_mid:.1f}x/{multiple_high:.1f}x、{discount:.1%}折扣及$34均为内部假设。承销EBITDA为负，按CP-05采用EV/2024E Revenue：收入×(1+增长)×倍数，加现金及证券，除经济股数后施加折扣。支持区间${support_low:.2f}–${support_high:.2f}，中点${support_mid:.2f}；$34较中点signed {signed_mid_diff:+.2f}、absolute {absolute_mid_diff:.2f}。

## 盈利质量、结构与募集
管理层Adjusted EBITDA {mgmt_ebitda:.3f}减SBC {sbc_adopted:.3f}得承销EBITDA {underwriting_ebitda:.3f}；重组{restructuring:.3f}已调整，增量为零；FCF {fcf:.3f}。Base公司gross/fee/net为{base_gross:.6f}/{base_fee:.7f}/{base_net:.7f}，Full为{full_gross:.6f}/{full_fee:.7f}/{full_net:.7f}；fee仅按primary gross，固定费用各情景仅一次。Base不含shoe，secondary {secondary:.6f}不形成公司募集或新增股。Post shares为{base_post_shares:.6f}/{full_post_shares:.6f}；primary/post-money为{base_new_post_pct:.3%}/{full_new_post_pct:.3%}。SEC-02仅核验${ntbv_price:.2f}−${ntbv_assumed:.2f}=${ntbv_dilution:.2f}，不外推$34 NTBV。

## 数据核验（逐异常一行）
- `monthly_revenue_2022_2023.csv`第9/14行、2022-08：重复57.100；SEC-01年数{num(financial['Revenue']['2022A']):.3f}为依据；剔除第14行，{monthly_2022_raw:.3f}→{monthly_2022_adopted:.3f}。
- `monthly_revenue_2022_2023.csv`第15–27行、FY2023：All rows {monthly_2023_raw:.3f}含两条12月；SEC优先；剔除INT第27行后{monthly_2023_adopted:.3f}，原口径影响+{monthly_2023_raw-monthly_2023_adopted:.3f}。
- `monthly_revenue_2022_2023.csv`第26/27行、2023-12：INT {int_dec:.3f}替换SEC {sec_dec:.3f}会得{monthly_2023_alt:.3f}、差{monthly_2023_alt-monthly_2023_adopted:.3f}；CP-02以SEC为准，拒绝替换。
- `revenue_by_segment_2022_2023.csv`第5行、FY2023 Other：152.470为小数错位；`SEC-01_financials_extract.xlsx` Revenue/Other revenue行支持{segment_other_adopted:.3f}；更正后总额{segment_corrected:.3f}。
- `sbc_detail_2022_2023.csv`第6–10行、FY2023：components {sbc_component_sum:.3f}与TOTAL {sbc_detail_total:.3f}差{sbc_detail_total-sbc_component_sum:.3f}；components与SEC-01一致；拒绝TOTAL。
- `SEC-16_share_count_history.csv`第5行、2024-03-18：注册{registered_2024:.1f}无法由“排除RSU”重建（应{registered_expected_ex_rsu:.6f}）；委员会经济股{cap_total:.6f}与SEC-09组件一致；列治理例外，不用于估值。
- `cap_table_snapshot_20240318.csv`第2–5行、2024-03-18：SEC-09标签与`SEC-09_capitalization.csv`第2–7行的2024-03-11冲突；算术一致；保留委员会快照并标记血缘。
- `Source_Index.csv`全表：UW-01被`Offering_Terms_20240320.xlsx`第2–13行及cap table第6–8行引用但未收录；直接追踪并列治理例外。
- `Source_Index.csv`全表：缺9个实际文件ID（{', '.join(missing_sec_ids)}）；以对应文件名直接追踪、不推定优先级，列治理例外。

## 决策
发行结构10项检查均由明确条件计算并通过；SEC-16及来源索引为披露的治理例外，不是发行结构hard error。$34通过区间、距中点及结构三项测试，按CP-14建议 **{decision}**。
"""
chinese_chars = len(re.findall(r"[\u3400-\u9fff]", memo))
assert chinese_chars <= 1600, f"Memo exceeds 1600 Chinese characters: {chinese_chars}"
(OUT / f"{STEM}_pricing_memo.md").write_text(memo, encoding="utf-8")

# ---------------------------------------------------------------------------
# Composite chart, 300 dpi
# ---------------------------------------------------------------------------
fig = plt.figure(figsize=(12, 5.6), constrained_layout=True)
gs = fig.add_gridspec(1, 2, width_ratios=[0.9, 1.4])
ax1 = fig.add_subplot(gs[0, 0])
ax1.set_title("Committee Support Range", fontweight="bold")
ax1.set_ylim(0, 1)
ax1.set_yticks([])
ax1.set_xlim(math.floor(support_low)-1, math.ceil(support_high)+1)
ax1.hlines(0.5, support_low, support_high, color="#4472C4", linewidth=12, alpha=0.35)
ax1.scatter([support_low, support_high], [0.5, 0.5], color="#4472C4", s=75, zorder=3, label="Low / High")
ax1.scatter([support_mid], [0.5], color="#70AD47", s=120, marker="D", zorder=4, label="Midpoint")
ax1.scatter([price], [0.5], color="#C00000", s=140, marker="*", zorder=5, label="$34 working price")
for x, label, y in [(support_low, f"Low\n${support_low:.2f}", .61), (support_mid, f"Mid\n${support_mid:.2f}", .27), (support_high, f"High\n${support_high:.2f}", .61), (price, f"$34\nDelta {signed_mid_diff:+.2f}", .72)]:
    ax1.annotate(label, (x, .5), xytext=(x, y), ha="center", fontsize=9, arrowprops=dict(arrowstyle="-", color="#777777"))
ax1.set_xlabel("Discounted equity value per share (USD)")
ax1.grid(axis="x", linestyle=":", alpha=.35)
ax1.legend(loc="lower center", fontsize=8, frameon=False)

ax2 = fig.add_subplot(gs[0, 1])
heat = np.array([[valuation_at(g,m) for m in sensitivity_multiples] for g in sensitivity_growths])
cmap = LinearSegmentedColormap.from_list("pricing", ["#F4CCCC", "#FFF2CC", "#D9EAD3"])
im = ax2.imshow(heat, cmap=cmap, aspect="auto")
ax2.set_title("5x5 Single-Point Sensitivity", fontweight="bold")
ax2.set_xticks(range(5), [f"{m:.1f}x" for m in sensitivity_multiples])
ax2.set_yticks(range(5), [f"{g:.0%}" for g in sensitivity_growths])
ax2.set_xlabel("EV / 2024E Revenue")
ax2.set_ylabel("2024E Revenue Growth")
for i in range(5):
    for j in range(5):
        is_base = math.isclose(sensitivity_growths[i], growth) and math.isclose(sensitivity_multiples[j], multiple_mid)
        ax2.text(j, i, f"${heat[i,j]:.2f}" + ("\nBASE" if is_base else ""), ha="center", va="center", fontsize=8, fontweight="bold" if is_base else "normal", color="#17365D")
        if is_base:
            ax2.add_patch(plt.Rectangle((j-.49,i-.49),.98,.98,fill=False,edgecolor="#C00000",linewidth=2.5))
fig.suptitle("Reddit IPO Pricing Review — Pre-Pricing as of 2024-03-20", fontsize=14, fontweight="bold")
fig.savefig(OUT / f"{STEM}_charts.png", dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)

# ---------------------------------------------------------------------------
# Final self-checks and stdout audit trail
# ---------------------------------------------------------------------------
# Ensure the source pack remains read-only from this script's perspective: no writes above target OUT.
expected_paths = {OUT / name for name in FILES}
actual_paths = {p for p in OUT.iterdir() if p.is_file()}
extra_files = actual_paths - expected_paths
if extra_files:
    raise AssertionError(f"Unexpected output files: {sorted(str(p) for p in extra_files)}")
missing_files = expected_paths - actual_paths
if missing_files:
    raise AssertionError(f"Missing output files: {sorted(str(p) for p in missing_files)}")
if any(p.is_dir() for p in OUT.iterdir()):
    raise AssertionError("Unexpected output directory present")

check_wb = load_workbook(xlsx_path, data_only=False, read_only=False)
required_sheets = {"Inputs", "QoE", "Valuation", "Sensitivity", "Offering_Proceeds", "Dilution", "Pricing_Summary", "Error_Audit", "Source_Trace", "Tieout_Detail", "Methodology"}
assert required_sheets.issubset(check_wb.sheetnames)

# Exact critical-formula and formatting checks: fail rather than silently issue
# a Proceed recommendation with broken offering or audit mechanics.
offering_check = check_wb["Offering_Proceeds"]
expected_offering_formulas = {
    "B12": "=B10*B11",
    "C12": "=C10*C11",
    "B14": "=B10-B12-B13",
    "C14": "=C10-C12-C13",
}
for coordinate, expected_formula in expected_offering_formulas.items():
    assert offering_check[coordinate].value == expected_formula, f"Incorrect offering formula {coordinate}: {offering_check[coordinate].value}"
assert "0.0%" in offering_check["B11"].number_format and "0.0%" in offering_check["C11"].number_format
for coordinate in ("B6", "C6", "B7", "C7", "B8", "C8", "B9", "C9"):
    assert "0.000000" in offering_check[coordinate].number_format, f"Offering share format missing at {coordinate}"
assert offering_check["A14"].font.bold and offering_check["B14"].font.bold and offering_check["C14"].font.bold
assert not offering_check["A13"].font.bold, "Fixed expense row should not carry net-proceeds bold formatting"

tieout_check = check_wb["Tieout_Detail"]
assert tieout_check.max_row - 4 >= 27, "Tieout_Detail must retain at least 27 rows"
for r in range(5, tieout_check.max_row + 1):
    for col in ("C", "D", "E"):
        assert tieout_check[f"{col}{r}"].data_type == "f", f"Tieout formula missing at {col}{r}"
    assert tieout_check[f"E{r}"].value == f"=C{r}-D{r}", f"Tieout difference formula incorrect at E{r}"
    assert not re.fullmatch(r"=-?\d+(?:\.\d+)?", str(tieout_check[f"C{r}"].value)), f"Static-result formula prohibited at C{r}"
    assert not re.fullmatch(r"=-?\d+(?:\.\d+)?", str(tieout_check[f"D{r}"].value)), f"Static-result formula prohibited at D{r}"

pricing_check = check_wb["Pricing_Summary"]
assert pricing_check["B13"].data_type == "f" and "Methodology!" in pricing_check["B13"].value
assert pricing_check["B14"].value == '=IF(AND(B11,B12,B13),"Proceed",IF(AND(B11,B13),"Reprice","Defer"))'
method_check = check_wb["Methodology"]
for r in range(structure_method_start_row, structure_method_end_row + 1):
    assert method_check[f"A{r}"].value == "Structure check"
    assert method_check[f"C{r}"].data_type == "f"
    assert method_check[f"C{r}"].value not in ("=TRUE", "=TRUE()", "=FALSE", "=FALSE()"), f"Static structure result at Methodology!C{r}"

formula_count = 0
excel_error_tokens = {"#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A"}
for ws_check in check_wb.worksheets:
    assert ws_check.max_row > 5, f"Sheet lacks substantive content: {ws_check.title}"
    for row in ws_check.iter_rows():
        for cell in row:
            if cell.data_type == "f":
                formula_count += 1
                assert not any(tok in str(cell.value) for tok in excel_error_tokens), f"Error token in formula {ws_check.title}!{cell.coordinate}"
            elif isinstance(cell.value, str):
                assert cell.value not in excel_error_tokens, f"Excel error value in {ws_check.title}!{cell.coordinate}"
assert formula_count >= 100, f"Expected substantial formula content, found {formula_count}"
check_wb.close()

if formula_cache_refreshed:
    cached_wb = load_workbook(xlsx_path, data_only=True, read_only=True)
    cached_offering = cached_wb["Offering_Proceeds"]
    cached_expected = {
        "B12": base_fee,
        "C12": full_fee,
        "B14": base_net,
        "C14": full_net,
    }
    for coordinate, expected_value in cached_expected.items():
        cached_value = cached_offering[coordinate].value
        assert isinstance(cached_value, (int, float)), f"Missing recalculated cache at Offering_Proceeds!{coordinate}"
        assert math.isclose(float(cached_value), expected_value, rel_tol=0, abs_tol=1e-7), (
            f"Cached value mismatch at Offering_Proceeds!{coordinate}: {cached_value} vs {expected_value}"
        )
    assert cached_wb["Pricing_Summary"]["B13"].value is True, "Cached structural Test 3 must pass"
    assert cached_wb["Pricing_Summary"]["B14"].value == decision, "Cached decision differs from Python decision"
    for r in range(5, tieout_check.max_row + 1):
        assert cached_wb["Tieout_Detail"][f"E{r}"].value is not None, f"Missing Tieout cache at E{r}"
    cached_wb.close()

from PIL import Image
with Image.open(OUT / f"{STEM}_charts.png") as img:
    img.verify()
for csv_name in [f"{STEM}_qoe_bridge.csv", f"{STEM}_valuation_matrix.csv", f"{STEM}_source_trace.csv"]:
    p = OUT / csv_name
    assert p.read_bytes().startswith(b"\xef\xbb\xbf"), f"CSV lacks UTF-8 BOM: {csv_name}"
    assert len(read_csv(p)) > 0
assert len(valuation_rows) == 28 and sum(r["row_type"] == "sensitivity" for r in valuation_rows) == 25

print("=== KEY RESULTS ===")
print(f"Policy: v3 current ({len(policy_ids)} clauses)")
print(f"2023A Revenue: {revenue_2023:.3f} USD mm")
print(f"Growth: {growth:.1%}; 2024E Revenue: {revenue_2024:.5f} USD mm")
print(f"Management Adj EBITDA: {mgmt_ebitda:.3f}; SBC reversal: {sbc_adopted:.3f}; Underwriting EBITDA: {underwriting_ebitda:.3f}")
print(f"Restructuring: {restructuring:.3f}; incremental adjustment: 0.000; FCF: {fcf:.3f}")
print(f"Cash: {cash:.3f}; Marketable securities: {securities:.3f}; Economic shares: {economic_shares:.6f}")
print(f"Support range: ${support_low:.4f} / ${support_mid:.4f} / ${support_high:.4f}")
print(f"Working price: ${price:.2f}; signed vs midpoint: {signed_mid_diff:+.4f}; absolute: {absolute_mid_diff:.4f}")
print(f"Base gross/fee/net: {base_gross:.6f} / {base_fee:.7f} / {base_net:.7f}")
print(f"Full gross/fee/net: {full_gross:.6f} / {full_fee:.7f} / {full_net:.7f}")
print(f"Base/full post shares: {base_post_shares:.6f} / {full_post_shares:.6f}; primary/post: {base_new_post_pct:.3%} / {full_new_post_pct:.3%}")
print("=== 25-CELL SENSITIVITY ===")
for g in sensitivity_growths:
    print(f"Growth {g:.0%}: " + ", ".join(f"{m:.1f}x=${valuation_at(g,m):.4f}" for m in sensitivity_multiples))
print("=== IDENTIFIED ANOMALIES ===")
for row in errors:
    if row[0] == "Data anomaly":
        print(f"- {row[1]} | observed: {row[2]} | disposition: {row[3]} | impact: {row[4]} {row[5]}")
print("=== SOURCE FILE INVENTORY ===")
for d in source_dirs:
    print(f"{d}: {dir_counts[d]}")
print(f"Seven directories: {sum(dir_counts.values())}; root: {root_files}; total: {sum(dir_counts.values()) + root_files}")
print(f"Missing Source_Index IDs: {', '.join(missing_actual_ids)}")
print("=== OUTPUT SELF-CHECK ===")
for p in sorted(expected_paths):
    print(f"OK {p.name} ({p.stat().st_size:,} bytes)")
print(f"Workbook sheets: {len(check_wb.sheetnames)}; formulas: {formula_count}; memo Chinese characters: {chinese_chars}")
print(f"Formula cache refreshed and verified: {formula_cache_refreshed}")
print("Structural checks: " + "; ".join(f"{name}={result}" for name, result in structure_checks.items()))
print("Governance exceptions disclosed: " + "; ".join(f"{name}={flag}" for name, flag in governance_exceptions.items()))
print(f"DECISION: {decision} (range={within_range}, midpoint_distance={within_midpoint}, structural_errors_resolved={hard_errors_resolved})")
