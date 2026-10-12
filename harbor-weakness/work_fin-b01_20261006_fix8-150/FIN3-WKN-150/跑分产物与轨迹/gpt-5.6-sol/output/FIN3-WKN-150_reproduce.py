#!/usr/bin/env python3
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
INPUT = BASE.parent / "input_files"
OUT = BASE
CHART_DIR = OUT / "FIN3-WKN-150_charts"
MEMO_PATH = OUT / "FIN3-WKN-150_PreIPO投资决策备忘录.md"

PERIOD_FILES = {
    "2023": "03_审计报告_2023.md",
    "2024": "04_审计报告_2024.md",
    "2025": "05_审计报告_2025.md",
    "2026H1": "06_审计报告_2026H1.md",
}
NOTE_FILES = {
    "2023": "07_财务报表附注_2023.md",
    "2024": "08_财务报表附注_2024.md",
    "2025": "09_财务报表附注_2025.md",
    "2026H1": "10_财务报表附注_2026H1.md",
}
PRODUCT_FILES = {
    "2023": "19_收入明细_分产品_2023.csv",
    "2024": "20_收入明细_分产品_2024.csv",
    "2025": "21_收入明细_分产品_2025.csv",
    "2026H1": "22_收入明细_分产品_2026H1.csv",
}
COST_FILES = {
    "2023": "24_成本费用明细_2023.csv",
    "2024": "25_成本费用明细_2024.csv",
    "2025": "26_成本费用明细_2025.csv",
    "2026H1": "27_成本费用明细_2026H1.csv",
}
PERIODS = list(PERIOD_FILES)


def read_text(name: str) -> str:
    return (INPUT / name).read_text(encoding="utf-8")


def clean_cell(value: str) -> str:
    return re.sub(r"[*`_]", "", value).strip()


def as_number(value: str) -> float:
    value = clean_cell(str(value)).replace(",", "").replace("—", "")
    value = value.replace("%", "").replace("+", "")
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        return float("nan")
    return float(match.group())


def markdown_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if cells and not all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            rows.append(cells)
    return rows


def row_cells(text: str, label: str) -> list[str]:
    for row in markdown_rows(text):
        if row and row[0] == label:
            return row[1:]
    raise KeyError(f"未在材料中找到表格行：{label}")


def row_number(text: str, label: str, position: int = 0) -> float:
    return as_number(row_cells(text, label)[position])


def regex_number(text: str, pattern: str, flags: int = 0) -> float:
    match = re.search(pattern, text, flags)
    if not match:
        raise ValueError(f"未匹配到输入参数：{pattern}")
    return as_number(match.group(1))


def regex_percent(text: str, pattern: str, flags: int = 0) -> float:
    return regex_number(text, pattern, flags) / 100.0


def fmt(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}"


def pct(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


def multiple(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}x"


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out.extend("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join(out)


def parse_report_date(text: str) -> date:
    match = re.search(r"报告日期：(\d{4}) 年 (\d{1,2}) 月 (\d{1,2}) 日", text)
    if not match:
        raise ValueError("报告日期缺失")
    return date(*(int(x) for x in match.groups()))


def collect_inputs() -> dict:
    audit = {}
    for period, filename in PERIOD_FILES.items():
        text = read_text(filename)
        audit[period] = {
            "revenue": row_number(text, "营业收入"),
            "cost": row_number(text, "营业成本（含税金及附加）"),
            "selling": row_number(text, "销售费用"),
            "admin": row_number(text, "管理费用"),
            "rd": row_number(text, "研发费用"),
            "finance": row_number(text, "财务费用"),
            "interest": row_number(text, "其中：利息费用"),
            "pbt": row_number(text, "利润总额"),
            "tax": row_number(text, "所得税费用"),
            "net_profit": row_number(text, "净利润"),
            "cash": row_number(text, "货币资金"),
            "ar": row_number(text, "应收账款（净额）"),
            "inventory": row_number(text, "存货（净额）"),
            "fixed_assets": row_number(text, "固定资产"),
            "short_debt": row_number(text, "短期借款"),
            "long_debt": row_number(text, "长期借款"),
            "equity": row_number(text, "所有者权益合计"),
            "ocf": row_number(text, "经营活动产生的现金流量净额"),
            "report_date": parse_report_date(text),
        }
        audit[period]["gross_margin"] = (audit[period]["revenue"] - audit[period]["cost"]) / audit[period]["revenue"]
        audit[period]["expense_rate"] = (audit[period]["selling"] + audit[period]["admin"] + audit[period]["rd"]) / audit[period]["revenue"]
        audit[period]["cash_conversion"] = audit[period]["ocf"] / audit[period]["net_profit"]

    notes = {}
    for period, filename in NOTE_FILES.items():
        text = read_text(filename)
        notes[period] = {
            "debt": row_number(text, "有息负债合计"),
            "depreciation": row_number(text, "固定资产折旧"),
            "amortization": row_number(text, "无形资产与长期待摊费用摊销"),
        }
        notes[period]["da"] = notes[period]["depreciation"] + notes[period]["amortization"]

    nonrec = pd.read_csv(INPUT / "11_非经常性损益明细.csv")
    nonrec = nonrec[nonrec["项目"].notna()].copy()
    nonrec["报告期"] = nonrec["报告期"].astype(str)
    shares = pd.read_csv(INPUT / "12_股份支付明细.csv")
    shares["报告期"] = shares["报告期"].astype(str)
    share_pay = shares.groupby("报告期")["本期确认费用_万元"].sum().reindex(PERIODS)

    products = pd.concat([pd.read_csv(INPUT / name) for name in PRODUCT_FILES.values()], ignore_index=True)
    products["报告期"] = products["报告期"].astype(str)
    costs = pd.concat([pd.read_csv(INPUT / name) for name in COST_FILES.values()], ignore_index=True)
    costs["报告期"] = costs["报告期"].astype(str)

    cash_text = read_text("16_货币资金与银行流水摘要.md")
    restricted_rows = ["银行存款—质押/保证金", "其他货币资金—承兑汇票保证金", "其他货币资金—保函保证金"]
    restricted = np.sum([[as_number(x) for x in row_cells(cash_text, label)] for label in restricted_rows], axis=0)
    restricted_cash = dict(zip(PERIODS, restricted))

    dcf_text = read_text("32_DCF参数与折现率指引.md")
    start_year, end_year = (int(x) for x in re.search(r"明确预测期：\*\*(\d{4}) 年至 (\d{4}) 年", dcf_text).groups())
    dcf_params = {
        "start_year": start_year,
        "end_year": end_year,
        "revenue_growth": regex_percent(dcf_text, r"2026 年营业收入增速\s*\|\s*\+?([\d.]+)%"),
        "later_revenue_growth": regex_percent(dcf_text, r"2027—2030 年营业收入增速\s*\|\s*每年 \+?([\d.]+)%"),
        "gross_margin": regex_percent(dcf_text, r"预测期毛利率\s*\|\s*([\d.]+)%"),
        "expense_rate": regex_percent(dcf_text, r"研发费用率合计\s*\|\s*([\d.]+)%"),
        "da_rate": regex_percent(dcf_text, r"折旧与摊销占营业收入比例\s*\|\s*([\d.]+)%"),
        "capex_rate": regex_percent(dcf_text, r"资本性支出占营业收入比例\s*\|\s*([\d.]+)%"),
        "nwc_rate": regex_percent(dcf_text, r"营运资本追加\s*\|\s*按当年营业收入增量×([\d.]+)%"),
        "tax_rate": regex_percent(dcf_text, r"所得税税率\s*\|\s*([\d.]+)%"),
        "rf": regex_percent(dcf_text, r"无风险利率 Rf\s*\|\s*([\d.]+)%"),
        "erp": regex_percent(dcf_text, r"市场风险溢价 ERP\s*\|\s*([\d.]+)%"),
        "beta_u": regex_number(dcf_text, r"Unlevered Beta 中位数 βu\s*\|\s*([\d.]+)"),
        "debt_weight": regex_percent(dcf_text, r"D/\(D\+E\)\s*\|\s*([\d.]+)%"),
        "kd": regex_percent(dcf_text, r"债务成本 Kd（税前）\s*\|\s*([\d.]+)%"),
        "g": regex_percent(dcf_text, r"永续增长率 g = \*\*([\d.]+)%"),
        "wacc_step": regex_percent(dcf_text, r"WACC（±([\d.]+) 个百分点"),
        "g_step": regex_percent(dcf_text, r"永续增长率（±([\d.]+) 个百分点"),
    }

    transaction_text = read_text("01_交易概况与投资方案.md")
    company_text = read_text("02_标的公司概况与业务模式.md")
    transaction = {
        "investment": regex_number(transaction_text, r"拟投资金额\s*\|[^\n]*?([\d,]+) 万元"),
        "max_holding": regex_percent(transaction_text, r"拟取得股权\s*\|[^\n]*?不高于 ([\d.]+)%"),
        "shares": regex_number(company_text, r"总股本 ([\d,]+) 万股"),
    }

    market_text = read_text("31_行业数据与可比公司选取说明.md")
    cutoff_match = re.search(r"(2026 年 6 月 30 日)", market_text)
    cutoff = datetime.strptime(cutoff_match.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace(" ", ""), "%Y-%m-%d").date()
    rd_range = re.search(r"行业平均研发费用率\s*\|\s*约 ([\d.]+)%—([\d.]+)%", market_text)
    market_params = {
        "cutoff": cutoff,
        "min_revenue": regex_number(market_text, r"营业收入不低于 ([\d.]+) 亿元") * 10000,
        "dlom": regex_percent(market_text, r"\*\*([\d.]+)% 流动性折价"),
        "industry_cagr": regex_percent(market_text, r"行业 2023—2025 年复合增速\s*\|\s*约 ([\d.]+)%"),
        "industry_rd_low": as_number(rd_range.group(1)) / 100,
        "industry_rd_high": as_number(rd_range.group(2)) / 100,
    }

    promise_text = read_text("33_业绩承诺函与对赌条款.md")
    promise_rows = markdown_rows(promise_text)
    promise_values = {}
    for row in promise_rows:
        if row and re.fullmatch(r"202\d 年", row[0]):
            promise_values[row[0][:4]] = as_number(row[1])
    commitment = {
        "profits": promise_values,
        "annual_trigger": regex_percent(promise_text, r"承诺数的 \*\*([\d.]+)%\*\*"),
        "cumulative_trigger": regex_percent(promise_text, r"累计承诺数的 \*\*([\d.]+)%\*\*"),
        "repurchase_rate": regex_percent(promise_text, r"年化 \*\*([\d.]+)%\*\* 单利"),
    }

    return {
        "audit": audit,
        "notes": notes,
        "nonrec": nonrec,
        "share_pay": share_pay,
        "products": products,
        "costs": costs,
        "restricted_cash": restricted_cash,
        "dcf_params": dcf_params,
        "transaction": transaction,
        "market_params": market_params,
        "commitment": commitment,
    }


def calculate(data: dict) -> dict:
    audit = data["audit"]
    notes = data["notes"]
    nonrec = data["nonrec"]
    share_pay = data["share_pay"]

    bridge = {}
    for period in PERIODS:
        items = nonrec[nonrec["报告期"] == period].copy()
        pretax_nonrec = items["税前金额_万元"].sum()
        tax_effect = items["所得税影响_万元"].sum()
        aftertax_nonrec = items["税后金额_万元"].sum()
        adjusted_net = audit[period]["net_profit"] - aftertax_nonrec
        standard_ebitda = audit[period]["net_profit"] + audit[period]["tax"] + audit[period]["interest"] + notes[period]["da"]
        adjusted_tax = audit[period]["tax"] - tax_effect
        adjusted_ebitda = adjusted_net + adjusted_tax + audit[period]["interest"] + notes[period]["da"] + share_pay.loc[period]
        bridge[period] = {
            "items": items,
            "pretax_nonrec": pretax_nonrec,
            "tax_effect": tax_effect,
            "aftertax_nonrec": aftertax_nonrec,
            "adjusted_net": adjusted_net,
            "standard_ebitda": standard_ebitda,
            "adjusted_tax": adjusted_tax,
            "adjusted_ebitda": adjusted_ebitda,
            "share_pay": share_pay.loc[period],
        }

    days_in_period = {
        "2023": (date(2024, 1, 1) - date(2023, 1, 1)).days,
        "2024": (date(2025, 1, 1) - date(2024, 1, 1)).days,
        "2025": (date(2026, 1, 1) - date(2025, 1, 1)).days,
        "2026H1": (date(2026, 7, 1) - date(2026, 1, 1)).days,
    }
    turnover = {}
    for i, period in enumerate(PERIODS):
        if i == 0:
            avg_ar = audit[period]["ar"]
            avg_inventory = audit[period]["inventory"]
            basis = "期末余额替代平均余额"
        else:
            prev = PERIODS[i - 1]
            avg_ar = (audit[prev]["ar"] + audit[period]["ar"]) / 2
            avg_inventory = (audit[prev]["inventory"] + audit[period]["inventory"]) / 2
            basis = "期初期末平均余额"
        turnover[period] = {
            "ar_days": avg_ar / audit[period]["revenue"] * days_in_period[period],
            "inventory_days": avg_inventory / audit[period]["cost"] * days_in_period[period],
            "basis": basis,
        }

    p = data["dcf_params"]
    debt_weight = p["debt_weight"]
    equity_weight = 1 - debt_weight
    debt_to_equity = debt_weight / equity_weight
    beta_l = p["beta_u"] * (1 + (1 - p["tax_rate"]) * debt_to_equity)
    ke = p["rf"] + beta_l * p["erp"]
    wacc = ke * equity_weight + p["kd"] * (1 - p["tax_rate"]) * debt_weight

    forecasts = []
    prior_revenue = audit["2025"]["revenue"]
    for year in range(p["start_year"], p["end_year"] + 1):
        growth_rate = p["revenue_growth"] if year == p["start_year"] else p["later_revenue_growth"]
        revenue = prior_revenue * (1 + growth_rate)
        ebit = revenue * (p["gross_margin"] - p["expense_rate"])
        da = revenue * p["da_rate"]
        capex = revenue * p["capex_rate"]
        nwc = (revenue - prior_revenue) * p["nwc_rate"]
        fcff = ebit * (1 - p["tax_rate"]) + da - capex - nwc
        t = year - p["start_year"] + 1
        pv = fcff / ((1 + wacc) ** t)
        forecasts.append({"year": year, "revenue": revenue, "ebit": ebit, "da": da, "capex": capex, "nwc": nwc, "fcff": fcff, "pv": pv})
        prior_revenue = revenue

    terminal_value = forecasts[-1]["fcff"] * (1 + p["g"]) / (wacc - p["g"])
    terminal_pv = terminal_value / ((1 + wacc) ** len(forecasts))
    enterprise_value = sum(x["pv"] for x in forecasts) + terminal_pv
    free_cash = audit["2025"]["cash"] - data["restricted_cash"]["2025"]
    net_debt = notes["2025"]["debt"] - free_cash
    equity_value = enterprise_value - net_debt
    per_share = equity_value / data["transaction"]["shares"]

    waccs = [wacc - p["wacc_step"], wacc, wacc + p["wacc_step"]]
    growths = [p["g"] - p["g_step"], p["g"], p["g"] + p["g_step"]]
    sensitivity = np.zeros((len(waccs), len(growths)))
    explicit_pv_by_wacc = []
    for i, test_wacc in enumerate(waccs):
        explicit_pv = sum(x["fcff"] / ((1 + test_wacc) ** (j + 1)) for j, x in enumerate(forecasts))
        explicit_pv_by_wacc.append(explicit_pv)
        for j, test_g in enumerate(growths):
            tv = forecasts[-1]["fcff"] * (1 + test_g) / (test_wacc - test_g)
            sensitivity[i, j] = explicit_pv + tv / ((1 + test_wacc) ** len(forecasts)) - net_debt

    raw = pd.read_csv(INPUT / "29_可比公司数据_原始导出.csv")
    raw["上市日期"] = pd.to_datetime(raw["上市日期"])
    duplicate_mask = raw.duplicated(subset=["证券代码"], keep="first")
    deduped = raw.loc[~duplicate_mask].copy()
    one_year_cutoff = pd.Timestamp(data["market_params"]["cutoff"]) - pd.DateOffset(years=1)
    reason_map = {}
    for _, row in deduped.iterrows():
        reasons = []
        if not str(row["证券代码"]).endswith((".SZ", ".SH", ".BJ")):
            reasons.append("非A股")
        if "ST" in str(row["证券简称"]).upper():
            reasons.append("风险警示")
        if row["上市日期"] > one_year_cutoff:
            reasons.append("上市不足一年")
        if row["净利润_万元"] <= 0:
            reasons.append("2025年亏损")
        if row["营业收入_万元"] < data["market_params"]["min_revenue"]:
            reasons.append("收入低于10亿元门槛")
        if reasons:
            reason_map[row["证券简称"]] = "、".join(reasons)
    valid_mask = (
        deduped["证券代码"].str.endswith((".SZ", ".SH", ".BJ"))
        & ~deduped["证券简称"].str.upper().str.contains("ST")
        & (deduped["上市日期"] <= one_year_cutoff)
        & (deduped["净利润_万元"] > 0)
        & (deduped["营业收入_万元"] >= data["market_params"]["min_revenue"])
    )
    mechanically_cleaned = deduped.loc[valid_mask].copy()
    checked = pd.read_csv(INPUT / "28_可比上市公司财务与估值数据.csv")
    valid_codes = set(mechanically_cleaned["证券代码"])
    industry_mask = checked["所属行业"].str.contains("精密制造|消费电子零部件", regex=True, na=False)
    comps = checked[checked["证券代码"].isin(valid_codes) & industry_mask].copy().rename(columns={
        "2025归母净利润_万元": "净利润_万元",
        "2025营业收入_万元": "营业收入_万元",
        "2025EBITDA_万元": "EBITDA_万元",
        "20260630总市值_万元": "市值_万元",
        "PE_TTM": "PE",
        "PS_TTM": "PS",
        "EV_EBITDA": "EVEBITDA",
        "UnleveredBeta": "Beta",
    })
    medians = {
        "PE": comps["PE"].median(),
        "PS": comps["PS"].median(),
        "EVEBITDA": comps["EVEBITDA"].median(),
        "Beta": comps["Beta"].median(),
    }
    dlom = data["market_params"]["dlom"]
    pe_value = audit["2025"]["net_profit"] * medians["PE"] * (1 - dlom)
    ps_value = audit["2025"]["revenue"] * medians["PS"] * (1 - dlom)
    ev_ebitda_pre_discount_equity = bridge["2025"]["standard_ebitda"] * medians["EVEBITDA"] - net_debt
    ev_ebitda_value = ev_ebitda_pre_discount_equity * (1 - dlom)
    market_values = {"PE": pe_value, "PS": ps_value, "EV/EBITDA": ev_ebitda_value}
    market_median = float(np.median(list(market_values.values())))
    market_low = min(market_values.values())
    market_high = max(market_values.values())
    dcf_low, dcf_high = float(sensitivity.min()), float(sensitivity.max())
    valuation_low, valuation_high = max(market_low, dcf_low), min(market_high, dcf_high)
    if valuation_low > valuation_high:
        valuation_low, valuation_high = market_low, market_high
    pricing_cap = market_median

    investment = data["transaction"]["investment"]
    holding_low = investment / (valuation_high + investment)
    holding_high = investment / (valuation_low + investment)
    holding_at_cap = investment / (pricing_cap + investment)
    min_pre_money_for_cap = investment / data["transaction"]["max_holding"] - investment
    issue_price = pricing_cap / data["transaction"]["shares"]
    new_shares = investment / issue_price

    promises = data["commitment"]["profits"]
    promise_years = sorted(promises)
    cumulative_promise = sum(promises.values())
    commitment_metrics = {
        "multiples_low": {year: valuation_low / amount for year, amount in promises.items()},
        "multiples_high": {year: valuation_high / amount for year, amount in promises.items()},
        "multiples_cap": {year: pricing_cap / amount for year, amount in promises.items()},
        "cumulative": cumulative_promise,
        "cumulative_trigger_profit": cumulative_promise * data["commitment"]["cumulative_trigger"],
        "coverage_low": cumulative_promise * holding_low / investment,
        "coverage_high": cumulative_promise * holding_high / investment,
        "annual_trigger_profit": {year: amount * data["commitment"]["annual_trigger"] for year, amount in promises.items()},
        "promise_years": promise_years,
    }

    return {
        "bridge": bridge,
        "turnover": turnover,
        "beta_l": beta_l,
        "ke": ke,
        "wacc": wacc,
        "forecasts": forecasts,
        "terminal_value": terminal_value,
        "terminal_pv": terminal_pv,
        "enterprise_value": enterprise_value,
        "free_cash": free_cash,
        "net_debt": net_debt,
        "equity_value": equity_value,
        "per_share": per_share,
        "waccs": waccs,
        "growths": growths,
        "sensitivity": sensitivity,
        "raw_comps": raw,
        "duplicate_count": int(duplicate_mask.sum()),
        "reason_map": reason_map,
        "comps": comps,
        "medians": medians,
        "market_values": market_values,
        "market_median": market_median,
        "market_low": market_low,
        "market_high": market_high,
        "dcf_low": dcf_low,
        "dcf_high": dcf_high,
        "valuation_low": valuation_low,
        "valuation_high": valuation_high,
        "pricing_cap": pricing_cap,
        "holding_low": holding_low,
        "holding_high": holding_high,
        "holding_at_cap": holding_at_cap,
        "min_pre_money_for_cap": min_pre_money_for_cap,
        "issue_price": issue_price,
        "new_shares": new_shares,
        "commitment_metrics": commitment_metrics,
    }


def conflict_checks(data: dict, calc: dict) -> dict:
    audit = data["audit"]
    products = data["products"]
    costs = data["costs"]
    management_text = read_text("01_交易概况与投资方案.md")
    management_row = next(row for row in markdown_rows(management_text) if row and row[0] == "扣非归母净利润（万元）")
    management_adjusted = dict(zip(PERIODS, [as_number(x) for x in management_row[1:]]))
    product_costs = products[products["产品线"] == "合计"].set_index("报告期")["营业成本_万元"].to_dict()
    manufacturing_da = costs[costs["项目"] == "制造费用—折旧"].set_index("报告期")["金额_万元"].to_dict()

    ar_text = read_text("14_应收账款账龄与坏账政策.md")
    rates = {
        "1 年以内": row_number(ar_text, "1 年以内") / 100,
        "1–2 年": row_number(ar_text, "1–2 年") / 100,
        "2–3 年": row_number(ar_text, "2–3 年") / 100,
        "3 年以上": row_number(ar_text, "3 年以上") / 100,
    }
    expected_provision = dict.fromkeys(PERIODS, 0.0)
    ar_rows = markdown_rows(ar_text)
    for age, rate in rates.items():
        balance_cells = max((row[1:] for row in ar_rows if row and row[0] == age), key=len)
        values = [as_number(x) for x in balance_cells]
        if len(values) != len(PERIODS):
            raise AssertionError(f"应收账龄列数异常：{age}")
        for period, value in zip(PERIODS, values):
            expected_provision[period] += value * rate
    actual_provision = dict(zip(PERIODS, [as_number(x) for x in row_cells(ar_text, "减：坏账准备")]))

    customer = pd.read_csv(INPUT / "23_收入明细_分客户_2025.csv")
    customer["收入占比数"] = customer["收入占比"].str.rstrip("%").astype(float)
    customer_top5 = customer[~customer["客户"].str.contains("其他")]["收入占比数"].sum()
    customer_summary = row_number(read_text("35_主要客户与供应商.md"), "2025")

    return {
        "management_adjusted": management_adjusted,
        "product_costs": product_costs,
        "manufacturing_da": manufacturing_da,
        "expected_provision": expected_provision,
        "actual_provision": actual_provision,
        "customer_top5": customer_top5,
        "customer_summary": customer_summary,
    }


def setup_plotting() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
        "axes.facecolor": "#FAFAFA",
        "axes.edgecolor": "#666666",
        "grid.color": "#D9D9D9",
        "grid.alpha": 0.55,
        "axes.titleweight": "bold",
    })


def save_fig(fig: plt.Figure, filename: str) -> None:
    fig.savefig(CHART_DIR / filename, dpi=190, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def create_charts(data: dict, calc: dict, checks: dict) -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    setup_plotting()
    audit = data["audit"]
    periods = PERIODS
    x = np.arange(len(periods))
    money_fmt = FuncFormatter(lambda value, _: f"{value / 10000:.1f}")

    files = list(INPUT.glob("*"))
    coverage = Counter()
    for path in files:
        if path.name == "template_memo.md" or path.name[:2] in {"00", "01", "02"}:
            coverage["总览/交易/模板"] += 1
        elif path.name[:2] in {"03", "04", "05", "06"}:
            coverage["审计/审阅"] += 1
        elif path.name[:2].isdigit() and 7 <= int(path.name[:2]) <= 18:
            coverage["附注/专项财务"] += 1
        elif path.name[:2].isdigit() and 19 <= int(path.name[:2]) <= 27:
            coverage["收入/成本"] += 1
        elif path.name[:2].isdigit() and 28 <= int(path.name[:2]) <= 32:
            coverage["行业/估值"] += 1
        else:
            coverage["条款/其他尽调"] += 1
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5), gridspec_kw={"width_ratios": [1, 1.35]})
    axes[0].bar(coverage.keys(), coverage.values(), color="#2F6690")
    axes[0].set_title("(a) 40份材料覆盖分布")
    axes[0].set_ylabel("文件数")
    axes[0].tick_params(axis="x", rotation=32)
    for i, value in enumerate(coverage.values()):
        axes[0].text(i, value + 0.15, str(value), ha="center")
    status_labels = ["金额主表", "报告日期", "扣非口径", "产品成本", "折旧口径", "坏账计提", "客户集中度", "Beta", "净负债", "退出参数"]
    status = [2, 0, 0, 0, 0, 0, 1, 0, 2, 1]
    matrix = np.array(status).reshape(-1, 1)
    axes[1].imshow(matrix, cmap=ListedColormap(["#C94745", "#E9B949", "#3B8C6E"]), vmin=0, vmax=2, aspect="auto")
    axes[1].set_yticks(np.arange(len(status_labels)), status_labels)
    axes[1].set_xticks([0], ["核验状态"])
    label_map = {0: "冲突", 1: "待核实/缺口", 2: "已勾稽"}
    for i, value in enumerate(status):
        axes[1].text(0, i, label_map[value], ha="center", va="center", color="white" if value != 1 else "black", fontweight="bold")
    axes[1].set_title("(b) 关键数据核验标记")
    fig.suptitle("材料覆盖与数据缺口", fontsize=16, fontweight="bold")
    fig.tight_layout()
    save_fig(fig, "FIN3-WKN-150_chart01_材料覆盖与数据缺口.png")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.4))
    revenues = [audit[p]["revenue"] for p in periods]
    gm = [audit[p]["gross_margin"] for p in periods]
    axes[0].bar(x, revenues, color="#2F6690", label="营业收入")
    axes[0].set_xticks(x, periods)
    axes[0].set_ylabel("营业收入（亿元）")
    axes[0].yaxis.set_major_formatter(money_fmt)
    ax2 = axes[0].twinx()
    ax2.plot(x, np.array(gm) * 100, color="#C94745", marker="o", linewidth=2, label="毛利率")
    ax2.set_ylabel("毛利率")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}%"))
    axes[0].set_title("(a) 收入与审计摘要口径毛利率")
    axes[0].grid(axis="y")
    bridge_series = {
        "净利润": [audit[p]["net_profit"] for p in periods],
        "扣非归母": [calc["bridge"][p]["adjusted_net"] for p in periods],
        "调整后EBITDA": [calc["bridge"][p]["adjusted_ebitda"] for p in periods],
    }
    width = 0.24
    colors = ["#7EA8BE", "#E9B949", "#3B8C6E"]
    for idx, (label, values) in enumerate(bridge_series.items()):
        axes[1].bar(x + (idx - 1) * width, values, width=width, label=label, color=colors[idx])
    axes[1].set_xticks(x, periods)
    axes[1].set_ylabel("万元")
    axes[1].set_title("(b) 利润口径还原桥")
    axes[1].legend(frameon=False)
    axes[1].grid(axis="y")
    fig.suptitle("收入与利润口径还原", fontsize=16, fontweight="bold")
    fig.tight_layout()
    save_fig(fig, "FIN3-WKN-150_chart02_收入与利润口径还原.png")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.4))
    net = [audit[p]["net_profit"] for p in periods]
    ocf = [audit[p]["ocf"] for p in periods]
    width = 0.34
    axes[0].bar(x - width / 2, net, width=width, label="净利润", color="#7EA8BE")
    axes[0].bar(x + width / 2, ocf, width=width, label="经营现金流", color="#3B8C6E")
    axes[0].set_xticks(x, periods)
    axes[0].set_ylabel("万元")
    axes[0].legend(frameon=False)
    ax2 = axes[0].twinx()
    ax2.plot(x, [audit[p]["cash_conversion"] * 100 for p in periods], color="#C94745", marker="o", label="净现比")
    ax2.set_ylabel("净现比")
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    axes[0].set_title("(a) 利润、经营现金流与净现比")
    axes[0].grid(axis="y")
    axes[1].plot(x, [calc["turnover"][p]["ar_days"] for p in periods], marker="o", linewidth=2, label="应收周转天数")
    axes[1].plot(x, [calc["turnover"][p]["inventory_days"] for p in periods], marker="s", linewidth=2, label="存货周转天数")
    axes[1].set_xticks(x, periods)
    axes[1].set_ylabel("天")
    axes[1].set_title("(b) 应收与存货周转天数")
    axes[1].legend(frameon=False)
    axes[1].grid(axis="y")
    fig.suptitle("现金流与营运效率", fontsize=16, fontweight="bold")
    fig.tight_layout()
    save_fig(fig, "FIN3-WKN-150_chart03_现金流与营运效率.png")

    comps = calc["comps"]
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    metrics = [("PE", "PE", "(a) PE"), ("PS", "PS", "(b) PS"), ("EVEBITDA", "EVEBITDA", "(c) EV/EBITDA")]
    for ax, (column, key, title) in zip(axes.flat[:3], metrics):
        values = comps[column].to_numpy()
        names = comps["证券简称"].to_list()
        ax.bar(np.arange(len(names)), values, color="#7EA8BE")
        ax.axhline(calc["medians"][key], color="#C94745", linestyle="--", linewidth=2, label=f"中位数 {calc['medians'][key]:.2f}x")
        ax.set_xticks(np.arange(len(names)), names, rotation=55, ha="right", fontsize=8)
        ax.set_ylabel("倍数（x）")
        ax.set_title(title)
        ax.legend(frameon=False)
        ax.grid(axis="y")
    years = [str(x["year"]) for x in calc["forecasts"]]
    axes[1, 1].bar(np.arange(len(years)) - 0.18, [x["fcff"] for x in calc["forecasts"]], width=0.36, label="FCFF", color="#3B8C6E")
    axes[1, 1].bar(np.arange(len(years)) + 0.18, [x["pv"] for x in calc["forecasts"]], width=0.36, label="现值", color="#E9B949")
    axes[1, 1].set_xticks(np.arange(len(years)), years)
    axes[1, 1].set_ylabel("万元")
    axes[1, 1].set_title("(d) DCF预测期自由现金流与现值")
    axes[1, 1].legend(frameon=False)
    axes[1, 1].grid(axis="y")
    fig.suptitle("可比公司倍数与DCF估值", fontsize=17, fontweight="bold")
    fig.tight_layout()
    save_fig(fig, "FIN3-WKN-150_chart04_可比与DCF估值.png")

    risks = [("财务报告及底稿真实性", "高"), ("客户集中与议价", "高"), ("应收及坏账准备", "高"), ("IPO退出与回购履约", "高"), ("存货零跌价", "中"), ("专利诉讼", "中"), ("税惠续期", "中"), ("资本开支及补助退回", "中"), ("期权池稀释", "中"), ("社保公积金", "低")]
    gaps = [("签章审计/审阅底稿", "高"), ("扣非专项鉴证", "高"), ("成本折旧勾稽", "高"), ("坏账及回款核验", "高"), ("完全摊薄股本", "高"), ("退出参数", "高"), ("诉讼法律意见", "中"), ("库存库龄盘点", "中"), ("回购义务人偿付能力", "中")]
    fig, axes = plt.subplots(1, 3, figsize=(17, 6.4), gridspec_kw={"width_ratios": [1.15, 1.25, 1]})
    image = axes[0].imshow(calc["sensitivity"] / 10000, cmap="YlGnBu", aspect="auto")
    axes[0].set_xticks(range(len(calc["growths"])), [pct(g, 1) for g in calc["growths"]])
    axes[0].set_yticks(range(len(calc["waccs"])), [pct(w, 3) for w in calc["waccs"]])
    axes[0].set_xlabel("永续增长率")
    axes[0].set_ylabel("WACC")
    axes[0].set_title("(a) DCF股权价值（亿元）")
    for i in range(calc["sensitivity"].shape[0]):
        for j in range(calc["sensitivity"].shape[1]):
            axes[0].text(j, i, f"{calc['sensitivity'][i, j] / 10000:.2f}", ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=axes[0], fraction=0.046)

    valuation_labels = ["PE", "PS", "EV/EBITDA", "DCF"]
    valuation_values = [calc["market_values"]["PE"], calc["market_values"]["PS"], calc["market_values"]["EV/EBITDA"], calc["equity_value"]]
    y = np.arange(len(valuation_labels))
    axes[1].barh(y, np.array(valuation_values) / 10000, color=["#7EA8BE", "#7EA8BE", "#7EA8BE", "#3B8C6E"])
    axes[1].axvspan(calc["valuation_low"] / 10000, calc["valuation_high"] / 10000, color="#E9B949", alpha=0.3, label="建议区间")
    axes[1].axvline(calc["pricing_cap"] / 10000, color="#C94745", linestyle="--", label="建议上限")
    axes[1].set_yticks(y, valuation_labels)
    axes[1].set_xlabel("投前股权价值（亿元）")
    axes[1].set_title("(b) 估值结果与建议区间")
    axes[1].legend(frameon=False, fontsize=8)
    axes[1].grid(axis="x")

    levels = ["高", "中", "低"]
    risk_counts = Counter(level for _, level in risks)
    gap_counts = Counter(level for _, level in gaps)
    xx = np.arange(len(levels))
    axes[2].bar(xx - 0.18, [risk_counts[x] for x in levels], 0.36, label="风险", color="#C94745")
    axes[2].bar(xx + 0.18, [gap_counts[x] for x in levels], 0.36, label="尽调缺口", color="#E9B949")
    axes[2].set_xticks(xx, levels)
    axes[2].set_ylabel("事项数")
    axes[2].set_title("(c) 风险与尽调缺口评级")
    axes[2].legend(frameon=False)
    axes[2].grid(axis="y")
    fig.suptitle("估值区间与风险缺口", fontsize=17, fontweight="bold")
    fig.tight_layout()
    save_fig(fig, "FIN3-WKN-150_chart05_估值区间与风险缺口.png")


def build_memo(data: dict, calc: dict, checks: dict) -> str:
    audit = data["audit"]
    bridge = calc["bridge"]
    p = data["dcf_params"]
    t = data["transaction"]
    cm = calc["commitment_metrics"]
    customer_text = read_text("35_主要客户与供应商.md")
    customer_first = row_number(customer_text, "2025", 1)
    supplier_share_match = re.search(r"供应份额\s*约为[^\d]*([\d.]+)%—([\d.]+)%", customer_text)
    supplier_share_low, supplier_share_high = (as_number(x) for x in supplier_share_match.groups())
    restricted_text = read_text("17_受限资产与对外担保清单.md")
    planned_capex = regex_number(restricted_text, r"预计设备采购及厂房改造投入约\s*\n?\s*([\d,]+) 万元")
    investment_required = regex_number(restricted_text, r"累计固定资产投资\s*\n?\s*不低于 ([\d.]+) 亿元") * 10000
    investment_completed = regex_number(restricted_text, r"累计已完成\s*\n?\s*投资 ([\d.]+) 亿元") * 10000
    investment_gap = investment_required - investment_completed
    event_text = read_text("18_期后事项与未决诉讼.md")
    subsidy_review = regex_number(event_text, r"政府补助 ([\d,]+) 万元")
    option_text = read_text("34_股权结构、期权池与历史融资.md")
    option_reserved = regex_number(option_text, r"尚未授予的股份为 \*\*([\d,]+) 万股")
    option_unexercised = regex_number(option_text, r"已授予未行权股份 ([\d,]+) 万股")
    employee_platform = row_number(option_text, "杭州智联企业管理合伙企业（员工持股平台）")
    tax_text = read_text("38_税务情况说明.md")
    fallback_tax = regex_percent(tax_text, r"企业所得税税率将恢复至 ([\d.]+)%")
    staff_text = read_text("37_员工与社保缴纳明细.md")
    staff_h1 = row_cells(staff_text, "2026H1")
    social_uncovered = as_number(staff_h1[0]) - as_number(staff_h1[1])

    coverage_rows = [
        ["交易、公司与模板", "00—02、template", "4/4", "交易额、股本、业务及八章模板齐备；最终增资协议待核实"],
        ["审计/审阅", "03—06", "4/4", "金额摘要齐备；报告日期存在时序异常"],
        ["附注及专项财务", "07—18", "12/12", "债务、非经常、现金、应收、存货等齐备；缺完整报表及底稿"],
        ["收入与成本", "19—27", "9/9", "分产品四期、客户仅2025；成本与主表不完全勾稽"],
        ["行业与估值", "28—32", "5/5", "可比原始/核对版及两份强制口径齐备"],
        ["条款及其他尽调", "33—38", "6/6", "承诺、股权、客户、研发、员工、税务齐备；退出参数不足"],
    ]

    conflict_rows = []
    for period in PERIODS:
        conflict_rows.append([
            period,
            "扣非归母",
            fmt(checks["management_adjusted"][period], 0),
            fmt(bridge[period]["adjusted_net"], 0),
            "01 vs 03—06、11；采用全量非经常损益复算",
        ])
    conflict_rows.extend([
        ["2025", "营业成本", fmt(audit["2025"]["cost"], 0), fmt(checks["product_costs"]["2025"], 0), "05/26 vs 21；估值采用审计摘要，产品表仅作结构分析"],
        ["2025", "固定资产折旧", fmt(data["notes"]["2025"]["depreciation"], 0), fmt(checks["manufacturing_da"]["2025"], 0), "09 vs 26；采用附注，成本分摊待核"],
        ["2025", "坏账准备", fmt(checks["actual_provision"]["2025"], 0), fmt(checks["expected_provision"]["2025"], 0), "14同文件实际数 vs 政策机械计算；主表采用实际，充分性待核"],
        ["2025", "前五客户占比", f"{checks['customer_top5']:.1f}%", f"{checks['customer_summary']:.1f}%", f"23 vs 35；采用客户明细{checks['customer_top5']:.1f}%，差{abs(checks['customer_summary']-checks['customer_top5']):.1f}pct待核"],
        ["样本", "Unlevered Beta中位数", f"{p['beta_u']:.2f}", f"{calc['medians']['Beta']:.2f}", "32 vs 28实算；DCF强制采用指引值"],
    ])

    operating_rows = []
    for i, period in enumerate(PERIODS):
        growth = "—" if i == 0 or period == "2026H1" else pct(audit[period]["revenue"] / audit[PERIODS[i - 1]]["revenue"] - 1)
        operating_rows.append([
            period, fmt(audit[period]["revenue"], 0), growth, pct(audit[period]["gross_margin"]), pct(audit[period]["expense_rate"]),
            fmt(audit[period]["net_profit"], 0), fmt(audit[period]["ocf"], 0), pct(audit[period]["cash_conversion"]),
            fmt(calc["turnover"][period]["ar_days"], 1), fmt(calc["turnover"][period]["inventory_days"], 1),
        ])

    product_2025 = data["products"][(data["products"]["报告期"] == "2025") & (data["products"]["产品线"] != "合计")]
    product_rows = [[r["产品线"], fmt(r["营业收入_万元"], 0), f"{r['收入占比']:.1f}%", r["毛利率"]] for _, r in product_2025.iterrows()]

    bridge_rows = []
    item_names = data["nonrec"]["项目"].drop_duplicates().to_list()
    bridge_rows.append(["归母净利润"] + [fmt(audit[x]["net_profit"], 0) for x in PERIODS])
    for item in item_names:
        values = []
        for period in PERIODS:
            subset = data["nonrec"][(data["nonrec"]["报告期"] == period) & (data["nonrec"]["项目"] == item)]
            values.append(fmt(-subset["税后金额_万元"].sum(), 0))
        bridge_rows.append([f"{item}税后调整（负数扣减、正数加回）"] + values)
    bridge_rows.append(["=扣非归母净利润"] + [fmt(bridge[x]["adjusted_net"], 0) for x in PERIODS])
    bridge_rows.append(["加：扣非后所得税费用"] + [fmt(bridge[x]["adjusted_tax"], 0) for x in PERIODS])
    bridge_rows.append(["加：利息费用"] + [fmt(audit[x]["interest"], 0) for x in PERIODS])
    bridge_rows.append(["加：折旧与摊销"] + [fmt(data["notes"][x]["da"], 0) for x in PERIODS])
    bridge_rows.append(["加：股份支付"] + [fmt(bridge[x]["share_pay"], 0) for x in PERIODS])
    bridge_rows.append(["=调整后EBITDA"] + [fmt(bridge[x]["adjusted_ebitda"], 0) for x in PERIODS])

    forecast_rows = [[x["year"], fmt(x["revenue"]), fmt(x["ebit"]), fmt(x["da"]), fmt(x["capex"]), fmt(x["nwc"]), fmt(x["fcff"]), fmt(x["pv"])] for x in calc["forecasts"]]
    sensitivity_rows = []
    for i, wacc in enumerate(calc["waccs"]):
        sensitivity_rows.append([pct(wacc, 3)] + [fmt(v, 0) for v in calc["sensitivity"][i]])

    comp_rows = [[r["证券简称"], f"{r['PE']:.2f}", f"{r['PS']:.2f}", f"{r['EVEBITDA']:.2f}"] for _, r in calc["comps"].iterrows()]
    comp_rows.append(["中位数", f"{calc['medians']['PE']:.2f}", f"{calc['medians']['PS']:.3f}", f"{calc['medians']['EVEBITDA']:.3f}"])
    excluded = "；".join(f"{name}（{reason}）" for name, reason in calc["reason_map"].items())

    market_rows = [
        ["PE", fmt(audit["2025"]["net_profit"], 0), multiple(calc["medians"]["PE"]), fmt(calc["market_values"]["PE"] / (1 - data["market_params"]["dlom"]), 0), fmt(calc["market_values"]["PE"], 0)],
        ["PS", fmt(audit["2025"]["revenue"], 0), multiple(calc["medians"]["PS"], 3), fmt(calc["market_values"]["PS"] / (1 - data["market_params"]["dlom"]), 0), fmt(calc["market_values"]["PS"], 0)],
        ["EV/EBITDA", fmt(bridge["2025"]["standard_ebitda"], 0), multiple(calc["medians"]["EVEBITDA"], 3), fmt(calc["market_values"]["EV/EBITDA"] / (1 - data["market_params"]["dlom"]), 0), fmt(calc["market_values"]["EV/EBITDA"], 0)],
    ]

    risk_rows = [
        ["高", "财务资料可靠性", "2023—2025报告日期早于年末；2026H1审阅日又晚于检索截止日", "取得签章版报告、完整报表及审计底稿"],
        ["高", "客户集中与议价", f"2025前五客户{checks['customer_top5']:.1f}%，第一大{customer_first:.1f}%；年度议价且非独供", "核验合同、订单、降价和供应份额"],
        ["高", "应收及坏账", "应收净额持续上升；2025政策机械计提高于实际", "函证、期后回款、单项评估及迁徙率复核"],
        ["高", "IPO退出/回购", "上市仅为计划，且回购义务人偿付能力材料缺失", "补充资产证明、担保及可执行安排"],
        ["中", "存货", f"存货升至2026H1的{fmt(audit['2026H1']['inventory'],0)}万元，四期跌价均为零", "库龄、盘点、订单及期后售价测试"],
        ["中", "专利诉讼", "境外同业律师函，金额无法估计", "取得律师法律意见及产品规避方案"],
        ["中", "税惠与DCF偏差", f"高新证书2026到期，失败后税率{pct(fallback_tax,0)}；主模型仍按指引{pct(p['tax_rate'],0)}", "确认复审准备；另行报批补充情景"],
        ["中", "资本开支/补助", f"固定资产投资尚差{fmt(investment_gap,0)}万元，{fmt(subsidy_review,0)}万元补助年度亦冲突", "核验协议、付款计划及退回责任"],
        ["中", "稀释", f"{fmt(option_reserved,0)}万股预留与{fmt(option_unexercised,0)}万股未行权无法同平台{fmt(employee_platform,0)}万股勾稽", "确定完全摊薄股本及交割后持股"],
        ["低", "社保公积金", f"2026H1尚有{fmt(social_uncovered,0)}人未覆盖", "取得补缴凭证及兜底承诺效力意见"],
    ]

    gap_rows = [
        ["1", "签章审计/审阅报告、完整三表附注及底稿", "高", "会计师书面澄清日期；重做关键科目勾稽", "签约前"],
        ["2", "非经常损益专项鉴证", "高", "统一业绩承诺、估值和补偿口径", "签约前"],
        ["3", "成本分摊、固定资产卡片及折旧总账", "高", "解释产品成本和折旧冲突", "签约前"],
        ["4", "应收函证、期后回款和ECL模型", "高", "评估坏账准备充分性", "签约前"],
        ["5", "期权池台账与完全摊薄股本表", "高", "锁定增资价格、股份数及反稀释", "签约前"],
        ["6", "上市后退出估值、锁定/减持期与交割日", "高", "补齐MOIC、IRR必需输入", "投决前"],
        ["7", "库存库龄、盘点及可变现净值测试", "中", "验证零跌价准备", "交割前"],
        ["8", "诉讼法律意见与专利FTO报告", "中", "量化损失及销售限制", "交割前"],
        ["9", "回购义务人资产及担保材料", "中", f"验证{pct(data['commitment']['repurchase_rate'],0)}单利回购可执行性", "交割前"],
    ]

    first_promise, second_promise = cm["promise_years"]
    memo = f"""# FIN3-WKN-150 Pre-IPO投资决策备忘录

**标的：**杭州智联精密制造股份有限公司　**估值基准日：**2025年12月31日　**数据与检索截止日：**2026年6月30日　**金额单位：**万元（另注除外）

## 一、结论与建议

建议**有条件立项、审慎定价**，在高优先级尽调缺口关闭前不签署不可撤销投资文件。DCF中央投前股权价值为**{fmt(calc['equity_value'], 0)}万元（{fmt(calc['per_share'], 2)}元/股）**；其3×3敏感性范围为{fmt(calc['dcf_low'], 0)}—{fmt(calc['dcf_high'], 0)}万元。三种市场法经{pct(data['market_params']['dlom'], 0)}流动性折价后为{fmt(calc['market_low'], 0)}—{fmt(calc['market_high'], 0)}万元，中位数{fmt(calc['market_median'], 0)}万元。按31号文件“取交集”规则，建议投前估值区间为**{fmt(calc['valuation_low'], 0)}—{fmt(calc['valuation_high'], 0)}万元**；鉴于财务底稿、扣非、坏账和稀释口径未闭环，建议成交估值**不高于{fmt(calc['pricing_cap'], 0)}万元**。

{fmt(t['investment'],0)}万元增资在建议区间对应投后持股**{pct(calc['holding_low'], 2)}—{pct(calc['holding_high'], 2)}**，均低于{pct(t['max_holding'],2)}；建议上限估值下约{pct(calc['holding_at_cap'], 2)}，发行价约{fmt(calc['issue_price'], 2)}元/股、新增约{fmt(calc['new_shares'], 1)}万股。持股上限倒算最低投前估值为{fmt(calc['min_pre_money_for_cap'], 0)}万元。关键前置条件为：签章财务材料有效性、扣非专项鉴证、成本折旧与坏账勾稽、完全摊薄股本、退出参数及回购偿付保障。

## 二、材料核验与数据口径

截至截止日目录实际40份，编号00—38共39份加无编号模板1份，覆盖与清单一致。

{md_table(['类别','文件','覆盖','核验结论'], coverage_rows)}

采用口径：2023—2025损益、资产负债和现金流取03—05审计摘要；2026H1取06审阅摘要且不简单年化；债务、折旧摊销取07—10；受限现金取16/17；扣非逐项取11。周转天数2023因缺2022期初数以期末净额替代平均数，之后用期初期末平均净额；2026H1按实际181天。DCF与可比法只采用32、31规定参数。

材料数量完整不等于证据充分：现有审计文件仅为摘要，未包含会计师签章、意见原页、三张完整报表、合并范围及主要科目明细；银行流水仅有2025摘要，客户收入明细仅有2025，无法独立完成跨期截止性、函证替代程序和月度季节性检验。因此本备忘录可支持立项和定价边界判断，但不能替代交割审计或IPO申报财务核查。由于03—06仅提供“营业成本（含税金及附加）”，存货周转天数以该项目作分母，属于受材料限制的近似口径，待取得不含税金及附加的销售成本后更新。

主要冲突如下，未静默择一：

{md_table(['期间','指标','来源A','来源B/复算','取舍'], conflict_rows)}

此外，四期分产品成本与主表差额分别为{fmt(checks['product_costs']['2023']-audit['2023']['cost'],0)}、{fmt(checks['product_costs']['2024']-audit['2024']['cost'],0)}、{fmt(checks['product_costs']['2025']-audit['2025']['cost'],0)}、{fmt(checks['product_costs']['2026H1']-audit['2026H1']['cost'],0)}万元；2024/2025政府补助{fmt(subsidy_review,0)}万元所属年度在18与38冲突。2023—2025审计报告日均早于相应年末；06审阅日{audit['2026H1']['report_date']}晚于2026-06-30截止日，故虽按任务要求纳入，真实性与决策时可得性均待核实。期权池{fmt(option_reserved,0)}万股、未行权{fmt(option_unexercised,0)}万股与平台现持{fmt(employee_platform,0)}万股亦无法勾稽。

取舍原则依次为：投委会核准指引优先于一般材料；经审计/审阅主表优先于管理层与分部明细；可逐项复算的全量明细优先于未说明构成的汇总数。该顺序仅解决当前模型输入，并不消除冲突本身。所有差异均列为交割前核验事项；若签章原件或底稿推翻当前摘要，应整体重跑脚本，而非手工覆盖输出。

## 三、报告期经营质量分析

{md_table(['期间','收入','同比','毛利率','销管研率','净利润','经营现金流','净现比','应收天数','存货天数'], operating_rows)}

2024、2025收入分别增长{pct(audit['2024']['revenue']/audit['2023']['revenue']-1)}、{pct(audit['2025']['revenue']/audit['2024']['revenue']-1)}，增速高于31号文件所列行业2023—2025复合增速约{pct(data['market_params']['industry_cagr'])}；2026H1收入{fmt(audit['2026H1']['revenue'],0)}万元，但无同期数，不作同比判断。2025产品结构为：

{md_table(['产品','收入','占比','分产品毛利率'], product_rows)}

结构件占比最高且毛利率{product_2025.iloc[0]['毛利率']}，功能模组及模具毛利率较高；四期各产品毛利率完全不变，结合成本无法勾稽，需核查分摊是否模板化。主表毛利率稳定在{pct(min(audit[x]['gross_margin'] for x in PERIODS))}—{pct(max(audit[x]['gross_margin'] for x in PERIODS))}，销管研率由2023年{pct(audit['2023']['expense_rate'])}降至2025年{pct(audit['2025']['expense_rate'])}，2026H1回升至{pct(audit['2026H1']['expense_rate'])}。

净现比2023—2025均高于100%，但2026H1降至{pct(audit['2026H1']['cash_conversion'])}。应收周转天数在2024改善后升至2026H1的{fmt(calc['turnover']['2026H1']['ar_days'])}天，与90—120天账期及客户集中相符；存货天数约{fmt(min(calc['turnover'][x]['inventory_days'] for x in PERIODS))}—{fmt(max(calc['turnover'][x]['inventory_days'] for x in PERIODS))}天，而四期跌价准备均为零，盈利质量仍需期后回款、库龄和可变现净值验证。

增长质量存在三项约束。第一，2025前五大客户按23号明细合计{checks['customer_top5']:.1f}%，A客户占{customer_first:.1f}%，公司仅取得该客户同类采购约{supplier_share_low:.0f}%—{supplier_share_high:.0f}%，订单下降或年度降价会同时冲击收入和毛利。第二，应收净额由2023年{fmt(audit['2023']['ar'],0)}万元升至2026H1的{fmt(audit['2026H1']['ar'],0)}万元，增幅快于同口径可比期间的现金转化改善，且2025、2026H1实际坏账准备低于按14号列示政策机械计算额。第三，存货由{fmt(audit['2023']['inventory'],0)}万元升至{fmt(audit['2026H1']['inventory'],0)}万元，定制料和专用模具能否转售尚无库龄证据。

积极因素是研发费用率由2023年{pct(audit['2023']['rd']/audit['2023']['revenue'])}提高至2026H1的{pct(audit['2026H1']['rd']/audit['2026H1']['revenue'])}，处于31号文件行业{pct(data['market_params']['industry_rd_low'])}—{pct(data['market_params']['industry_rd_high'])}区间；2025销售收现{fmt(row_number(read_text('16_货币资金与银行流水摘要.md'),'销售商品、提供劳务收到的现金'),0)}万元，高于当年收入。但固定资产持续增长、2026计划投入{fmt(planned_capex,0)}万元及政府投资协议尚差{fmt(investment_gap,0)}万元，意味着现金流仍受资本开支约束，不能仅凭净现比判断可分配现金能力。

## 四、利润口径还原

公司无少数股东权益。01管理层仅称扣政府补助，且除2025外亦无法按该说明复算；本备忘录按11号文件全量逐项扣除。股份支付为非现金项目，在调整后EBITDA中加回，但33号业绩承诺明确**不得剔除股份支付**。桥接如下：

{md_table(['项目']+PERIODS, bridge_rows)}

市场法采用可比表同口径的**标准EBITDA**，2025年为净利润{fmt(audit['2025']['net_profit'],0)}+所得税{fmt(audit['2025']['tax'],0)}+利息{fmt(audit['2025']['interest'],0)}+折旧摊销{fmt(data['notes']['2025']['da'],0)}={fmt(bridge['2025']['standard_ebitda'],0)}万元；调整后EBITDA {fmt(bridge['2025']['adjusted_ebitda'],0)}万元仅用于经营质量分析。折旧冲突未解决前，两者均须底稿复核。

## 五、收益法估值（DCF）

严格采用32号文件：2026收入增长{pct(p['revenue_growth'])}、2027—2030每年增长{pct(p['later_revenue_growth'])}、毛利率{pct(p['gross_margin'])}、销管研率{pct(p['expense_rate'])}、折旧摊销/收入{pct(p['da_rate'])}、资本开支/收入{pct(p['capex_rate'])}、营运资本追加/收入增量{pct(p['nwc_rate'])}、税率{pct(p['tax_rate'])}、永续增长{pct(p['g'])}。

折现率：βL={p['beta_u']:.2f}×[1+(1−{pct(p['tax_rate'])})×{p['debt_weight']/(1-p['debt_weight']):.2f}]={calc['beta_l']:.6f}；Ke={pct(p['rf'],2)}+βL×{pct(p['erp'])}={pct(calc['ke'],3)}；WACC=Ke×{pct(1-p['debt_weight'])}+{pct(p['kd'])}×(1−{pct(p['tax_rate'])})×{pct(p['debt_weight'])}=**{pct(calc['wacc'],3)}**，未加规模溢价。

{md_table(['年度','收入','EBIT','折旧摊销','资本开支','营运资本追加','FCFF','现值'], forecast_rows)}

预测期FCFF现值合计{fmt(sum(x['pv'] for x in calc['forecasts']))}；终值{fmt(calc['terminal_value'])}、终值现值{fmt(calc['terminal_pv'])}；企业价值{fmt(calc['enterprise_value'])}。2025有息负债{fmt(data['notes']['2025']['debt'],0)}，货币资金{fmt(audit['2025']['cash'],0)}扣受限{fmt(data['restricted_cash']['2025'],0)}后可自由支配{fmt(calc['free_cash'],0)}，净负债为{fmt(calc['net_debt'],0)}（即净现金{fmt(-calc['net_debt'],0)}）。故股权价值{fmt(calc['equity_value'])}、每股{fmt(calc['per_share'],2)}元。终值现值占EV {pct(calc['terminal_pv']/calc['enterprise_value'])}，敏感性较高。

{md_table(['WACC\\g']+[pct(x,1) for x in calc['growths']], sensitivity_rows)}

## 六、市场法估值（可比公司）

29号原始导出共{len(calc['raw_comps'])}条：先按证券代码去重{calc['duplicate_count']}条；再按31号规则剔除{excluded}。保留证券代码均为A股后缀，且28号行业字段属于精密制造/消费电子零部件。29号仅用于识别清洗后的证券代码；最终公司名称、行业、财务指标及全部倍数均按31号要求从28号经核对版读取，保留{len(calc['comps'])}家。风险警示、亏损、上市不足一年和收入不足可能重叠，未重复计为独立样本。

{md_table(['公司','PE','PS','EV/EBITDA'], comp_rows)}

标的指标取2025审计口径；不加控制权溢价，股权价值统一扣{pct(data['market_params']['dlom'],0)}流动性折价。EV/EBITDA先以标准EBITDA乘倍数、减净负债得到股权价值，再整体折价，口径一致且未把受限现金当自由现金。

{md_table(['方法','标的指标','中位倍数','折价前股权价值','折价后股权价值'], market_rows)}

三种结果中位数为{fmt(calc['market_median'],0)}万元。DCF中央值高于市场法上限，主要因DCF终值占比较高，而市场法另含流动性折价；因此不直接采用DCF中央值定价。30号可比交易仅作合理性旁证：其中控制权案例含溢价，少数股权案例数量有限且缺少完整财务口径，按31号规则不并入上市公司倍数样本，也不据此新增折价或溢价。该处理避免把交易性质差异混入本轮少数股权增资定价。

## 七、估值结论与交易方案

收益法敏感性区间与市场法区间的交集为{fmt(calc['valuation_low'],0)}—{fmt(calc['valuation_high'],0)}万元，作为投前价值区间；本备忘录基于财务冲突尚未关闭的审慎判断，建议成交上限取三种市场法结果中位数{fmt(calc['pricing_cap'],0)}万元，该上限是投决建议而非31号文件新增参数。对应持股及发行数据见第一章；在未明确完全摊薄股本前，上述均按现有{fmt(t['shares'],0)}万股基本股本计算。

业绩承诺{first_promise}年{fmt(data['commitment']['profits'][first_promise],0)}万元、{second_promise}年{fmt(data['commitment']['profits'][second_promise],0)}万元，对建议估值区间隐含PE分别为{multiple(cm['multiples_low'][first_promise])}—{multiple(cm['multiples_high'][first_promise])}、{multiple(cm['multiples_low'][second_promise])}—{multiple(cm['multiples_high'][second_promise])}；建议上限对应{multiple(cm['multiples_cap'][first_promise])}、{multiple(cm['multiples_cap'][second_promise])}。单年{pct(data['commitment']['annual_trigger'],0)}补偿触发线分别为{fmt(cm['annual_trigger_profit'][first_promise],0)}、{fmt(cm['annual_trigger_profit'][second_promise],0)}万元；两年累计承诺{fmt(cm['cumulative'],0)}万元，{pct(data['commitment']['cumulative_trigger'],0)}回购触发线{fmt(cm['cumulative_trigger_profit'],0)}万元。按建议持股区间，“两年承诺利润×持股比例÷投资本金”的名义利润覆盖率为{pct(cm['coverage_low'])}—{pct(cm['coverage_high'])}；这既不是回购本金保障率，也不代表触发时实际赔偿比例，现金补偿不能视为本金全额保障。

**上市后退出回报：待核实，不能在现有材料下给出数值。**材料仅称预计2028年上市，未给交割日、上市估值/退出倍数、锁定与减持期、退出日及折价；自行填入将违反“不得引入文件外参数”。可复算式为：MOIC=退出时股权价值×退出持股比例÷{fmt(t['investment'],0)}；IRR=MOIC^(1/持有年数)−1。该式仅适用于无中间分红、追加投资、税费及后续稀释的简化单笔现金流。回购情景同样因起算日缺失，只能列示MOIC=1+{pct(data['commitment']['repurchase_rate'],0)}×T，IRR=(1+{pct(data['commitment']['repurchase_rate'],0)}×T)^(1/T)−1；须在投决前补齐T及退出价值后由本脚本扩展复算。

## 八、风险提示与尽调缺口

{md_table(['等级','风险','依据','缓释/核验'], risk_rows)}

尽调缺口与下一步动作如下：

{md_table(['序号','缺口','优先级','下一步动作','时点'], gap_rows)}

最终投资条件建议包括：成交投前估值不高于上述上限；交割后持股按完全摊薄口径复核且不高于8%；扣非定义与11号全量口径一致且不剔除股份支付；完善回购担保与IPO未完成触发条件；高优先级缺口未关闭时保留退出本项目的权利。

---

**图表索引：**[材料覆盖与数据缺口](FIN3-WKN-150_charts/FIN3-WKN-150_chart01_材料覆盖与数据缺口.png)；[收入与利润口径还原](FIN3-WKN-150_charts/FIN3-WKN-150_chart02_收入与利润口径还原.png)；[现金流与营运效率](FIN3-WKN-150_charts/FIN3-WKN-150_chart03_现金流与营运效率.png)；[可比与DCF估值](FIN3-WKN-150_charts/FIN3-WKN-150_chart04_可比与DCF估值.png)；[估值区间与风险缺口](FIN3-WKN-150_charts/FIN3-WKN-150_chart05_估值区间与风险缺口.png)。
"""
    return memo


def validate_outputs(memo: str) -> None:
    required_headings = ["一、结论与建议", "二、材料核验与数据口径", "三、报告期经营质量分析", "四、利润口径还原", "五、收益法估值（DCF）", "六、市场法估值（可比公司）", "七、估值结论与交易方案", "八、风险提示与尽调缺口"]
    for heading in required_headings:
        if memo.count(heading) != 1:
            raise AssertionError(f"章节校验失败：{heading}")
    expected = [
        MEMO_PATH,
        OUT / "FIN3-WKN-150_reproduce.py",
        CHART_DIR / "FIN3-WKN-150_chart01_材料覆盖与数据缺口.png",
        CHART_DIR / "FIN3-WKN-150_chart02_收入与利润口径还原.png",
        CHART_DIR / "FIN3-WKN-150_chart03_现金流与营运效率.png",
        CHART_DIR / "FIN3-WKN-150_chart04_可比与DCF估值.png",
        CHART_DIR / "FIN3-WKN-150_chart05_估值区间与风险缺口.png",
    ]
    missing = [str(path) for path in expected if not path.exists() or path.stat().st_size == 0]
    if missing:
        raise AssertionError("交付物缺失：" + ", ".join(missing))
    expected_pngs = {path.name for path in expected if path.suffix == ".png"}
    actual_pngs = {path.name for path in CHART_DIR.glob("*.png")}
    if actual_pngs != expected_pngs:
        raise AssertionError(f"图表文件集合不符：{sorted(actual_pngs)}")


def main() -> None:
    data = collect_inputs()
    calc = calculate(data)
    checks = conflict_checks(data, calc)
    create_charts(data, calc, checks)
    memo = build_memo(data, calc, checks)
    MEMO_PATH.write_text(memo, encoding="utf-8")
    validate_outputs(memo)
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", memo))
    print(f"已生成：{MEMO_PATH.name}，中文字符数约 {chinese_chars}")
    print(f"已生成图表：{len(list(CHART_DIR.glob('*.png')))} 张")
    print(f"DCF股权价值：{calc['equity_value']:.2f} 万元；市场法中位数：{calc['market_median']:.2f} 万元")


if __name__ == "__main__":
    main()
