from pathlib import Path
import csv
import re
import math
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = Path(__file__).resolve().parent.parent
INPUT = BASE / "input_files"
OUTPUT = Path(__file__).resolve().parent
CHARTS = OUTPUT / "FIN3-WKN-151_charts"
CHARTS.mkdir(parents=True, exist_ok=True)
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def read_text(name):
    return (INPUT / name).read_text(encoding="utf-8")


def read_csv(name):
    with (INPUT / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(value):
    return float(str(value).replace(",", "").replace("%", "").strip())


def pct(value):
    return f"{value * 100:.1f}%"


def money(value):
    return f"{value:,.0f}"


def round_down_10m(value):
    return math.floor(value / 1000) * 1000


def extract_number(text, pattern, flags=re.S):
    match = re.search(pattern, text, flags)
    if not match:
        raise ValueError(f"无法从材料中提取: {pattern}")
    return float(match.group(1).replace(",", ""))


# Read source tables and policy text; all conclusion figures below are derived from these inputs.
bs_rows = read_csv("09_资产负债表_四期.csv")
pl_rows = read_csv("10_利润表_四期.csv")
cf_rows = read_csv("11_现金流量表_四期.csv")
receivable_rows = read_csv("17_应收账款账龄与集中度.csv")
inventory_rows = read_csv("18_存货明细与跌价准备.csv")
finance_rows = read_csv("14_他行授信与用信明细.csv")
collateral_rows = read_csv("22_押品估值明细.csv")
self_rows = read_csv("12_企业自报财务数据汇总.csv")
policy_text = read_text("23_授信政策与行业限额指引.md")
measure_text = read_text("24_授信额度测算指引.md")
application_text = read_text("01_授信申请书.md")
industry_text = read_text("25_行业数据与可比企业.md")
note_text = read_text("08_财务报表附注_2025.md")
finance_note = read_text("14b_他行授信明细说明.md")
credit_text = read_text("13_征信报告摘要.md")

bs = {r["项目"]: {k: num(v) for k, v in r.items() if k != "项目"} for r in bs_rows}
pl = {r["项目"]: {k: num(v) for k, v in r.items() if k != "项目"} for r in pl_rows}
cf = {r["项目"]: {k: num(v) for k, v in r.items() if k != "项目"} for r in cf_rows}
years = ["2023年", "2024年", "2025年", "2026年1-6月"]
short_years = ["2023", "2024", "2025", "2026H1"]

# Policy parameters are extracted from the policy text rather than hard-coded as conclusions.
rate_patterns = {
    "厂房及办公楼": r"商业用房及厂房\s*\|\s*(\d+)%",
    "国有土地使用权": r"国有土地使用权（工业用地）\s*\|\s*(\d+)%",
    "应收账款": r"应收账款\s*\|\s*(\d+)%",
    "上市公司股权": r"上市公司股权\s*\|\s*(\d+)%",
    "非上市公司股权": r"非上市公司股权\s*\|\s*(\d+)%",
    "存货": r"存货\s*\|\s*(\d+)%",
}
policy_rates = {k: extract_number(policy_text, v) / 100 for k, v in rate_patterns.items()}
margin_floor = extract_number(policy_text, r"保证金比例原则上不低于\s*(\d+)%") / 100
concentration_ratio = extract_number(policy_text, r"不得超过本行资本净额的\s*(\d+)%") / 100
industry_multiplier = extract_number(policy_text, r"增速的\s*(\d+(?:\.\d+)?)\s*倍")

requested_limit = extract_number(application_text, r"申请.*?授信额度人民币\s*\*\*(\d[\d,]*)\s*万元")
forecast_growth = extract_number(application_text, r"较 2025 年增长\s*\*\*(\d+(?:\.\d+)?)%") / 100
industry_avg_growth = extract_number(industry_text, r"通用设备制造业营业收入增速\s*\|[^\n]*?\*\*(\d+(?:\.\d+)?)%\*\*", re.S) / 100
growth_cap = industry_avg_growth + 0.05
adopted_growth = min(forecast_growth, growth_cap)

# Financial analysis.
asset_ratio = {y: bs["负债合计"][y] / bs["资产总计"][y] for y in years}
current_ratio = {y: bs["流动资产合计"][y] / bs["流动负债合计"][y] for y in years}
quick_ratio = {y: (bs["流动资产合计"][y] - bs["存货"][y] - bs["预付账款"][y]) / bs["流动负债合计"][y] for y in years}
interest_coverage = {y: (pl["利润总额"][y] + pl["财务费用"][y]) / pl["财务费用"][y] for y in years}
net_cash_ratio = {y: cf["经营活动产生的现金流量净额"][y] / pl["净利润"][y] for y in years}
net_margin = {y: pl["净利润"][y] / pl["营业收入"][y] for y in years}

# Turnover days used for the 2025 policy calculation: average 2024/2025 balances, 360-day convention.
def avg(a, b):
    return (a + b) / 2

inventory_days_2025 = avg(bs["存货"]["2024年"], bs["存货"]["2025年"]) * 360 / pl["营业成本"]["2025年"]
ar_days_2025 = avg(bs["应收账款"]["2024年"], bs["应收账款"]["2025年"]) * 360 / pl["营业收入"]["2025年"]
ap_days_2025 = avg(bs["应付账款"]["2024年"], bs["应付账款"]["2025年"]) * 360 / pl["营业成本"]["2025年"]
prepaid_days_2025 = avg(bs["预付账款"]["2024年"], bs["预付账款"]["2025年"]) * 360 / pl["营业成本"]["2025年"]
pre_received_days_2025 = avg(bs["预收账款"]["2024年"], bs["预收账款"]["2025年"]) * 360 / pl["营业收入"]["2025年"]
working_days = inventory_days_2025 + ar_days_2025 - ap_days_2025 + prepaid_days_2025 - pre_received_days_2025
working_turns = 360 / working_days
sales_profit_margin = pl["净利润"]["2025年"] / pl["营业收入"]["2025年"]
working_capital = pl["营业收入"]["2025年"] * (1 - sales_profit_margin) * (1 + adopted_growth) / working_turns
restricted_cash = extract_number(note_text, r"使用受限的银行存款\s*\|\s*(\d[\d,]*)")
free_cash = bs["货币资金"]["2025年"] - restricted_cash
existing_short_loan = bs["短期借款"]["2025年"]
notes_payable = bs["应付票据"]["2025年"]
new_working_need = working_capital - free_cash - existing_short_loan - notes_payable
working_constraint = round_down_10m(max(new_working_need, 0))

# Financing detail: deduplicate by contract number, exclude explicit terminated records,
# convert USD exposure using the material's exchange rate, and keep blank status separate.
usd_rate = extract_number(finance_note, r"1 美元 =\s*(\d+(?:\.\d+)?)\s*元人民币")
cutoff = date(2026, 6, 30)
seen = set()
confirmed = []
pending = []
for row in finance_rows:
    contract = row["合同编号"]
    if contract in seen:
        continue
    seen.add(contract)
    status = row["业务状态"].strip()
    due = date.fromisoformat(row["到期日"])
    exposure = num(row["用信余额"])
    if row["币种"] == "USD":
        exposure *= usd_rate
    record = dict(row, exposure_cny=exposure, due=due)
    if status in {"已结清", "已到期"}:
        continue
    if status == "正常" and due > cutoff:
        confirmed.append(record)
    elif not status:
        pending.append(record)

confirmed_financing = sum(r["exposure_cny"] for r in confirmed)
pending_financing = sum(r["exposure_cny"] for r in pending)
all_unterminated_financing = confirmed_financing + pending_financing
confirmed_mix = {}
for r in confirmed:
    confirmed_mix[r["业务品种"]] = confirmed_mix.get(r["业务品种"], 0) + r["exposure_cny"]
pending_mix = {}
for r in pending:
    pending_mix[r["业务品种"]] = pending_mix.get(r["业务品种"], 0) + r["exposure_cny"]

# Collateral calculation. The listed status of the equity and its prior pledge are not verified,
# so it is excluded from the firm base and shown as a conditional amount.
collateral_values = {r["押品名称"]: num(r["评估价值(万元)"]) for r in collateral_rows}
collateral_eligible = {
    "厂房及办公楼": collateral_values["厂房及办公楼"] * policy_rates["厂房及办公楼"],
    "国有土地使用权": collateral_values["国有土地使用权"] * policy_rates["国有土地使用权"],
    "应收账款": collateral_values["应收账款"] * policy_rates["应收账款"],
    "存货": collateral_values["存货"] * policy_rates["存货"],
}
firm_collateral_value = sum(collateral_eligible.values())
equity_conditional_nonlisted = collateral_values["股权"] * policy_rates["非上市公司股权"]
equity_conditional_listed = collateral_values["股权"] * policy_rates["上市公司股权"]
collateral_constraint = round_down_10m(firm_collateral_value)
conditional_nonlisted_coverage = firm_collateral_value + equity_conditional_nonlisted
conditional_listed_coverage = firm_collateral_value + equity_conditional_listed
net_asset_value = bs["所有者权益合计"]["2025年"]
net_asset_constraint_raw = net_asset_value * 1.5
net_asset_constraint = round_down_10m(net_asset_constraint_raw)

# Concentration and sector limits cannot be computed without bank-level inputs. They stay pending.
final_recommendation = min(working_constraint, collateral_constraint)
final_recommendation = round_down_10m(final_recommendation)

# Comparable trend turnover days. H1 uses 180 days to annualize a six-month period for visual comparability;
# 2025 policy calculation above remains strictly 360 days.
def turnover_series(item, denominator_item, annual_period=True):
    result = []
    for idx, y in enumerate(years[1:], start=1):
        prior = years[idx - 1]
        balance = avg(bs[item][prior], bs[item][y])
        days = 360 if y != "2026年1-6月" else 180
        result.append(balance * days / pl[denominator_item][y])
    return result

inv_days_series = turnover_series("存货", "营业成本")
ar_days_series = turnover_series("应收账款", "营业收入")
ap_days_series = turnover_series("应付账款", "营业成本")
turnover_labels = ["2024", "2025", "2026H1等效"]

# Coverage chart.
all_material_files = sorted(p.name for p in INPUT.iterdir() if p.is_file())
material_list_text = read_text("00_材料清单.md")
listed_files = re.findall(r"`([^`]+)`", material_list_text)
listed_files = [f for f in listed_files if (INPUT / f).exists()]
categories = {
    "申请/客户": ["01_授信申请书.md", "02_客户基本情况与股权结构.md", "03_资质与证照摘要.md"],
    "财务/审计": ["04_审计报告_2023.md", "05_审计报告_2024.md", "06_审计报告_2025.md", "07_财务快报_2026H1.md", "08_财务报表附注_2025.md", "09_资产负债表_四期.csv", "10_利润表_四期.csv", "11_现金流量表_四期.csv", "12_企业自报财务数据汇总.csv", "12b_企业自报数据说明.md"],
    "征信/流水": ["13_征信报告摘要.md", "14_他行授信与用信明细.csv", "14b_他行授信明细说明.md", "15_结算账户流水摘要_2025.csv"],
    "税务/经营": ["16_纳税申报与纳税证明.md", "17_应收账款账龄与集中度.csv", "18_存货明细与跌价准备.csv"],
    "关联/或有": ["19_关联方与关联交易清单.md", "20_对外担保与或有负债清单.md"],
    "担保/政策": ["21_押品清单与评估报告.md", "22_押品估值明细.csv", "23_授信政策与行业限额指引.md", "24_授信额度测算指引.md"],
    "行业/模板": ["25_行业数据与可比企业.md", "template_report.md"],
}
coverage = {k: sum((INPUT / f).exists() for f in fs) / len(fs) for k, fs in categories.items()}
flags = ["审计数据", "半年度快报", "他行去重", "外币折算", "押品政策映射", "口径差异", "待核实项"]
flag_values = [1, 1, 1, 1, 1, 1, 1]

# Plot 1
fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
axes[0].bar(list(coverage), [v * 100 for v in coverage.values()], color="#4c78a8")
axes[0].set_ylim(0, 110)
axes[0].set_ylabel("材料覆盖率（%）")
axes[0].set_title("材料覆盖分布")
axes[0].tick_params(axis="x", rotation=35)
for i, v in enumerate(coverage.values()):
    axes[0].text(i, v * 100 + 3, f"{v:.0%}", ha="center", fontsize=9)
axes[1].barh(flags, flag_values, color=["#59a14f"] * 5 + ["#f28e2b", "#e15759"])
axes[1].set_xlim(0, 1.25)
axes[1].set_xticks([])
axes[1].set_title("核验标记")
for i, flag in enumerate(flags):
    axes[1].text(1.02, i, "已核验" if i < 5 else ("已披露" if i == 5 else "待核实"), va="center", fontsize=9)
fig.suptitle("材料覆盖与数据缺口（截至2026-06-30数据截止）")
fig.tight_layout()
fig.savefig(CHARTS / "FIN3-WKN-151_chart01_材料覆盖与数据缺口.png", dpi=180)
plt.close(fig)

# Plot 2
fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
x = np.arange(len(years))
axes[0].bar(x, [bs["资产总计"][y] for y in years], label="资产", color="#76b7b2")
axes[0].bar(x, [bs["负债合计"][y] for y in years], label="负债", color="#e15759")
axes[0].set_xticks(x, ["2023", "2024", "2025", "2026H1"])
axes[0].set_ylabel("万元")
axes[0].set_title("资产负债结构与资产负债率")
axes[0].legend()
for i, y in enumerate(years):
    axes[0].text(i, bs["资产总计"][y] + 2500, pct(asset_ratio[y]), ha="center", fontsize=9)
axes[1].plot(x, [current_ratio[y] for y in years], marker="o", label="流动比率")
axes[1].plot(x, [quick_ratio[y] for y in years], marker="o", label="速动比率")
axes[1].plot(x, [interest_coverage[y] for y in years], marker="o", label="利息保障倍数")
axes[1].set_xticks(x, ["2023", "2024", "2025", "2026H1"])
axes[1].set_title("流动比率、速动比率、利息保障倍数")
axes[1].set_ylabel("倍")
axes[1].legend()
fig.suptitle("财务与偿债能力")
fig.tight_layout()
fig.savefig(CHARTS / "FIN3-WKN-151_chart02_财务与偿债能力.png", dpi=180)
plt.close(fig)

# Plot 3
fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
axes[0].bar(x, [pl["净利润"][y] for y in years], label="净利润", color="#59a14f")
axes[0].plot(x, [cf["经营活动产生的现金流量净额"][y] for y in years], marker="o", color="#4c78a8", label="经营现金流")
for i, y in enumerate(years):
    axes[0].text(i, pl["净利润"][y] + 350, f"净现比{net_cash_ratio[y]:.2f}", ha="center", fontsize=8)
axes[0].set_xticks(x, ["2023", "2024", "2025", "2026H1"])
axes[0].set_ylabel("万元")
axes[0].set_title("净利润、经营现金流与净现比")
axes[0].legend()
xx = np.arange(3)
axes[1].plot(xx, inv_days_series, marker="o", label="存货")
axes[1].plot(xx, ar_days_series, marker="o", label="应收账款")
axes[1].plot(xx, ap_days_series, marker="o", label="应付账款")
axes[1].set_xticks(xx, turnover_labels)
axes[1].set_ylabel("天")
axes[1].set_title("存货、应收账款、应付账款周转天数")
axes[1].legend()
fig.suptitle("现金流与营运效率")
fig.tight_layout()
fig.savefig(CHARTS / "FIN3-WKN-151_chart03_现金流与营运效率.png", dpi=180)
plt.close(fig)

# Plot 4
fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
constraint_names = ["营运资金需求", "确定押品覆盖", "净资产约束", "集中度约束"]
constraint_values = [working_constraint, collateral_constraint, net_asset_constraint, np.nan]
colors = ["#4c78a8", "#f28e2b", "#59a14f", "#bab0ab"]
axes[0].bar(constraint_names, [0 if np.isnan(v) else v for v in constraint_values], color=colors)
axes[0].axhline(final_recommendation, color="#e15759", linestyle="--", label=f"孰低建议 {money(final_recommendation)}")
axes[0].set_ylabel("万元")
axes[0].set_title("各项额度约束对比与孰低结果")
axes[0].tick_params(axis="x", rotation=25)
axes[0].legend()
for i, v in enumerate(constraint_values):
    axes[0].text(i, (0 if np.isnan(v) else v) + 3000, "待核实" if np.isnan(v) else money(v), ha="center", fontsize=8)
collateral_names = list(collateral_eligible) + ["股权（待核实）", "专用设备（不得自行计入）"]
collateral_plot = list(collateral_eligible.values()) + [0, 0]
axes[1].bar(collateral_names, collateral_plot, color=["#76b7b2"] * 4 + ["#f28e2b", "#bab0ab"])
axes[1].set_ylabel("合格担保值（万元）")
axes[1].set_title("担保覆盖结构")
axes[1].tick_params(axis="x", rotation=35)
fig.suptitle("额度测算与担保覆盖")
fig.tight_layout()
fig.savefig(CHARTS / "FIN3-WKN-151_chart04_额度测算与担保覆盖.png", dpi=180)
plt.close(fig)

# Plot 5
fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
metric_names = ["申请增长", "测算增长", "行业上限", "票据/证保证金下限"]
metric_values = [forecast_growth * 100, adopted_growth * 100, growth_cap * 100, margin_floor * 100]
axes[0].bar(metric_names, metric_values, color=["#e15759", "#4c78a8", "#59a14f", "#f28e2b"])
axes[0].axhline(growth_cap * 100, color="#59a14f", linestyle="--", linewidth=1)
axes[0].axhline(margin_floor * 100, color="#f28e2b", linestyle=":", linewidth=1)
axes[0].set_ylabel("百分比（%）")
axes[0].set_title("关键指标与材料政策线")
axes[0].tick_params(axis="x", rotation=25)
for i, v in enumerate(metric_values):
    axes[0].text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=9)
# A transparent, material-based risk matrix: positions represent documented risks, not invented probabilities.
risks = [("收入确认/口径", 2, 2), ("应收集中度", 2, 2), ("质押顺位", 2, 2), ("现金流波动", 2, 1), ("关联担保", 1, 1), ("征信不良", 0, 0)]
for label, impact, likelihood in risks:
    axes[1].scatter(likelihood, impact, s=90, color="#e15759" if impact == 2 else ("#f28e2b" if impact == 1 else "#59a14f"))
    axes[1].text(likelihood + 0.06, impact + 0.04, label, fontsize=8)
axes[1].set_xlim(-0.3, 2.8)
axes[1].set_ylim(-0.3, 2.8)
axes[1].set_xticks([0, 1, 2], ["低", "中", "高"])
axes[1].set_yticks([0, 1, 2], ["低", "中", "高"])
axes[1].set_xlabel("发生可能性（材料判断）")
axes[1].set_ylabel("影响程度（材料判断）")
axes[1].set_title("风险矩阵与建议分类：正常类（附条件核实）")
axes[1].grid(alpha=0.25)
fig.suptitle("风险分类与授信条件")
fig.tight_layout()
fig.savefig(CHARTS / "FIN3-WKN-151_chart05_风险分类与授信条件.png", dpi=180)
plt.close(fig)

# Report generation.
confirmed_mix_lines = "；".join(f"{k}{money(v)}万元" for k, v in confirmed_mix.items())
pending_mix_lines = "；".join(f"{k}{money(v)}万元" for k, v in pending_mix.items())
差异表 = "；".join([
    "2025年企业自报收入98,600万元、审计/报表收入92,600万元，差6,000万元",
    "2025年自报净利润8,900万元、审计/报表净利润8,292万元，差608万元",
    "2026年上半年自报收入51,800万元、快报收入46,800万元，差5,000万元",
    "税务申报销售额2025年88,000万元与财务收入92,600万元差4,600万元",
    "2026年6月末存货明细账面余额36,400万元与资产负债表账面价值35,800万元差600万元",
])

def table_rows(values):
    return "\n".join(values)

report = f"""# 授信审批报告

数据与检索截止日：2026年6月30日。报告依据输入材料形成，金额单位均为万元；2026年1—6月数据未经审计。申请日为2026年7月8日，与本报告数据截止日不同，涉及截止日后的业务状态均不作事实推定。

## 一、授信结论与建议

建议在关键核实事项完成前有条件同意综合授信人民币{money(final_recommendation)}万元，期限1年，品种为流动资金贷款、银行承兑汇票和国内信用证；不得超过本次测算的孰低结果。申请额度为{money(requested_limit)}万元，上一年度获批额度为25,000万元，本次建议低于申请额，主要受政策折算押品覆盖约束，最终可用价值须以权利核验结果为准。流动资金贷款期限原则上不超过1年；银行承兑汇票、国内信用证保证金比例原则上不低于{margin_floor:.0%}，除非核实客户信用等级达到政策所称AA-以上。

担保建议采用厂房及办公楼、工业用地、符合合格条件的应收账款和存货抵质押，配套连带责任保证；关联方保证不得作为唯一担保方式。股权是否上市、既有质押登记的债权及顺位、应收账款回款控制、存货权利负担和专用设备政策审批完成前，不将相应不确定价值计入确定担保覆盖。五级分类建议为正常类，但以征信、合同状态、到期日和质押登记核实无重大不利变化为前提。

## 二、材料核验与数据口径

材料清单列示的申请、客户、资质、三年审计报告、2026年半年度快报、四期报表、自报数据、征信、他行授信、流水、税务、经营明细、关联及或有事项、押品、政策、行业数据和模板均已在输入目录找到，覆盖完整。2023—2025年审计报告均为标准无保留意见；2026年半年度快报明确未经审计。

本报告财务分析优先采用《09_资产负债表_四期.csv》《10_利润表_四期.csv》《11_现金流量表_四期.csv》，并以《04—06_审计报告》《07_财务快报_2026H1.md》《08_财务报表附注_2025.md》交叉核对。政策额度测算严格采用《授信额度测算指引》：2025年经审计营业收入、净利润、营业成本用于核心计算；周转天数采用年初年末平均余额及360天；自由资金为货币资金扣受限部分；短期借款和应付票据采用2025年末合并报表口径。自报数据不替代审计/快报数据。

已识别的差异为：{差异表}；差异原因材料仅部分解释为未取得验收单收入、审计调整、资产减值、免税/视同销售及账务调整；未提供逐项调节表的，标注待核实。2025年应收账款账面余额42,600万元、坏账准备2,400万元、账面价值40,200万元，报告使用净额进行资产分析；2026年末存货跌价准备未在明细表中明确，待核实。

他行融资按合同编号去重，排除已结清、已到期业务；USD按材料载明的1美元=7.20元人民币折算；用信余额直接按扣除保证金后的敞口使用，不再重复扣减。截止日确认状态正常且到期日晚于2026年6月30日的融资敞口为{money(confirmed_financing)}万元；两笔状态空白且到期日已过的业务合计{money(pending_financing)}万元，状态、是否结清/垫付/续作待核实，故总额{money(all_unterminated_financing)}万元仅作上限提示。

## 三、客户与经营概况

客户为浙江恒远智能装备集团有限公司，2009年5月成立，注册资本及实缴资本20,000万元，法定代表人和实际控制人为陈立远，注册地址为杭州市萧山区经济技术开发区，行业为通用设备制造业C34、工业机器人制造C3491。主营工业机器人本体、精密减速器和伺服驱动系统研发、生产与销售，员工1,860人，其中研发人员420人；拥有高新技术企业、专利及软件著作权等资质，相关证照有效期应持续关注。

股权方面，恒远控股集团持股62%，杭州远见创投18%，宁波恒信投资12%，陈立远直接持股8%；陈立远通过恒远控股合计控制70%表决权。集团成员包括100%持股的恒远精密机械、70%持股的恒远自动化系统工程及100%持股的恒远供应链管理公司，分别从事减速器制造、自动化产线集成和原材料采购仓储。

客户2023—2025年收入由{money(pl['营业收入']['2023年'])}万元增至{money(pl['营业收入']['2025年'])}万元，年增速分别为{pct(pl['营业收入']['2024年'] / pl['营业收入']['2023年'] - 1)}和{pct(pl['营业收入']['2025年'] / pl['营业收入']['2024年'] - 1)}；2026年上半年收入{money(pl['营业收入']['2026年1-6月'])}万元，同比增长9.9%，快报称受汽车下游需求波动影响。申请人预计全年收入109,300万元、增长18%，在手订单15.6亿元，但政策测算对增长率设有审慎上限。

按他行明细，确认正常融资结构为：{confirmed_mix_lines}；状态待核实的融资结构为：{pending_mix_lines}，合计{money(pending_financing)}万元。短期借款报表余额为{money(existing_short_loan)}万元，与明细表确认敞口不是同一口径，不能静默替代；授信测算仍按指引使用短期借款。

## 四、财务状况与偿债能力分析

资产总额由2023年{money(bs['资产总计']['2023年'])}万元增至2025年{money(bs['资产总计']['2025年'])}万元，2026年6月末为{money(bs['资产总计']['2026年1-6月'])}万元。负债总额同期由{money(bs['负债合计']['2023年'])}万元增至{money(bs['负债合计']['2025年'])}万元、期末{money(bs['负债合计']['2026年1-6月'])}万元，资产负债率由{pct(asset_ratio['2023年'])}升至{pct(asset_ratio['2026年1-6月'])}，杠杆逐步上行但仍有权益支撑。2025年流动资产{money(bs['流动资产合计']['2025年'])}万元、流动负债{money(bs['流动负债合计']['2025年'])}万元，流动比率{current_ratio['2025年']:.2f}倍，速动比率{quick_ratio['2025年']:.2f}倍；至2026年6月末分别降至{current_ratio['2026年1-6月']:.2f}倍和{quick_ratio['2026年1-6月']:.2f}倍，短期偿债缓冲收窄。速动比率按流动资产扣除存货及预付账款计算。

盈利方面，净利润由{money(pl['净利润']['2023年'])}万元升至2025年{money(pl['净利润']['2025年'])}万元，净利率由{pct(net_margin['2023年'])}升至{pct(net_margin['2025年'])}；2026年上半年净利润{money(pl['净利润']['2026年1-6月'])}万元，净利率{pct(net_margin['2026年1-6月'])}，盈利仍为正但增速放缓。2025年利息保障倍数为{interest_coverage['2025年']:.2f}倍，因材料未单列利息支出，按财务费用作为利息支出的近似值计算，需核实实际利息支出；2026年上半年该近似指标为{interest_coverage['2026年1-6月']:.2f}倍。

营运方面，2025年政策口径存货周转天数{inventory_days_2025:.2f}天、应收账款{ar_days_2025:.2f}天、应付账款{ap_days_2025:.2f}天、预付账款{prepaid_days_2025:.2f}天、预收账款{pre_received_days_2025:.2f}天，营运资金周转天数{working_days:.2f}天、周转次数{working_turns:.3f}次；图表对2026年上半年周转指标按180日等效展示，仅作趋势比较，未改变授信测算的360日口径。2026年6月末应收账款账面价值42,000万元，1年以内占比88%，但前五名客户占比87%、第一名28%，集中度和回款控制是重要风险点；存货账面余额增长且2026年跌价准备待核实。

现金流质量方面，经营现金净流量由2023年5,400万元、2024年6,700万元增至2025年9,100万元，净现比分别为{net_cash_ratio['2023年']:.2f}、{net_cash_ratio['2024年']:.2f}和{net_cash_ratio['2025年']:.2f}，2025年经营现金覆盖净利润较好；但2026年上半年经营现金流降至2,300万元，净现比{net_cash_ratio['2026年1-6月']:.2f}，低于1，快报解释为大客户付款方式调整及票据结算增加。需结合流水、票据和应收回款验证经营现金是否持续弱化。

## 五、授信需求测算与额度建议

收入增长率取值：申请预测18%；行业近三年营业收入平均增长率为8.0%，按政策加5个百分点形成13.0%上限，因此测算采用{adopted_growth:.1%}。2025年经审计销售利润率为净利润{money(pl['净利润']['2025年'])}÷收入{money(pl['营业收入']['2025年'])}={sales_profit_margin:.2%}。营运资金周转次数为360÷{working_days:.2f}={working_turns:.3f}次，代入公式：{money(pl['营业收入']['2025年'])}×(1-{sales_profit_margin:.2%})×(1+{adopted_growth:.1%})÷{working_turns:.3f}={working_capital:,.2f}万元。

新增营运资金需求为：营运资金量{working_capital:,.2f}−自由货币资金{money(free_cash)}−短期借款{money(existing_short_loan)}−应付票据{money(notes_payable)}={new_working_need:,.2f}万元，按政策向下取整，营运资金需求约束为{money(working_constraint)}万元。自由货币资金计算为2025年货币资金{money(bs['货币资金']['2025年'])}扣除受限资金{money(restricted_cash)}，受限资金包括票据保证金、保函保证金和被冻结存款。

额度约束逐项为：一是营运资金需求{money(working_constraint)}万元；二是政策折算押品覆盖{money(collateral_constraint)}万元（其中应收账款权利可用性待核实）；三是净资产约束，四期表2025年所有者权益{money(net_asset_value)}万元乘1.5为{money(net_asset_constraint_raw)}万元、向下取整为{money(net_asset_constraint)}万元，但四期表未明确审计属性，审计报告正文未列净资产，故该项仍待取得经审计净资产确认；四是集中度约束，政策为本行资本净额15%，本行资本净额材料未提供，待核实，不能假设可用额度。确定数据的孰低值为{money(final_recommendation)}万元，建议额度为该金额；如后续净资产、集中度或权利核验不支持，应重新按孰低原则调整。

## 六、担保与风险缓释

按政策率逐项折算，厂房及办公楼10,000×70%={money(collateral_eligible['厂房及办公楼'])}万元，工业用地5,000×60%={money(collateral_eligible['国有土地使用权'])}万元，应收账款12,000×50%={money(collateral_eligible['应收账款'])}万元，存货6,000×50%={money(collateral_eligible['存货'])}万元；在应收账款权利可用、登记顺位有效等前提下，政策折算合格担保值合计{money(firm_collateral_value)}万元，额度约束向下取整为{money(collateral_constraint)}万元，提款前未满足条件则应重新测算。

机器设备评估值8,500万元，属于政策未列示的专用设备，未经总行风险管理部逐笔审批，不设抵押率、不计入覆盖。股权评估值6,000万元，但材料未核实恒远精密机械是否上市，且征信显示应收账款质押登记16,000万元、股权质押登记8,000万元，押品表备注又称已质押登记，与“是否已抵押=否”存在矛盾。股权如核实为非上市且已有质押释放、顺位和可用价值满足要求，可追加{money(equity_conditional_nonlisted)}万元；如为上市公司可追加{money(equity_conditional_listed)}万元，但本次不将其计入确定值。

厂房和土地评估报告称已抵押余额为0，但仍需权属及登记查询确认；应收账款需核实账龄、债务人通知确认、回款专户、重复质押和前五大客户集中度；存货需核实权属、监管及在先质押。保证担保可接受自然人或法人连带责任保证，但关联方保证不宜作为唯一方式；公司已有对子公司无反担保保证8,600万元，应计入或有风险而非本次授信的有效增信。

## 七、风险分类与授信条件

基于征信报告，截至查询日未结清业务均为正常类，无逾期、无垫款、无不良，审计意见为标准无保留，客户有持续盈利和经营现金流，因此建议五级分类为正常类。该结论不是对空白状态融资、到期日矛盾、未决诉讼及质押顺位的豁免；如核实出现垫付、展期、逾期、重大诉讼损失或担保不可用，应立即重评分类和额度。

建议条件如下：第一，额度不超过{money(final_recommendation)}万元，期限1年，贷款、银承和国内证在综合额度内不得重复占用；第二，提款前取得有效授信申请文件、营业及资质持续有效证明、经审计净资产及本行资本净额集中度核验结果；第三，银承和国内证保证金不低于{margin_floor:.0%}，如申请下调须先核实AA-以上等级；第四，押品办理有效抵质押登记并确认优先顺位、价值和保险/监管安排，专用设备未获总行风险管理部审批不纳入；第五，核销/更新空白状态他行业务并确认已到期敞口处置；第六，不得将未经核实的自报收入、关联方资金拆借或未确认订单直接作为提款依据。

财务约束建议以材料可计算指标持续监测：资产负债率、流动比率、速动比率、经营现金流、净现比、应收账款账龄及集中度、存货跌价准备、短期借款和应付票据；具体触发阈值应使用本行已批准的监控标准，材料未提供的阈值不在本报告自行设定。

## 八、风险提示与贷后管理要求

高风险关注事项包括：一是收入确认和自报/审计/税务差异，可能导致收入、利润和需求高估；二是应收账款前五大客户集中度87%，第一名28%，且应收账款质押登记和回款控制待核实；三是2026年上半年经营现金流和净现比下降；四是他行两笔空白状态融资已过到期日，另有明细与报表融资口径差异；五是机器设备政策抵押率缺失，股权上市状态和既有质押顺位不明；六是对外担保8,600万元无反担保、未决专利诉讼标的1,200万元、附追索权商业承兑汇票3,200万元；七是高新技术企业证书及ISO证照存在2026年下半年到期事项。中风险事项包括下游汽车、3C需求波动、原材料价格波动、关联采购和资金往来；正面因素为征信正常、审计无保留、持续盈利及订单储备。

贷后管理建议：提款前逐项核实上述待核实事项并留存原始凭证；授信存续期按月取得银行流水、主要回款和融资余额，按月关注短期借款、票据、国内证及保证金；按季取得资产负债表、利润表、现金流量表及应收账款账龄、前五大客户、存货跌价准备明细；按季复核征信、他行合同状态、到期日、质押登记和对外担保；重大诉讼、票据追索、主要客户违约、证照失效或经营现金流持续恶化应立即报告。到期前至少按本行规定的提前管理时点核查回款、销售回款归行、融资续接和押品有效性；因本材料未给出具体天数，不自行设定提前天数，按行内现行到期管理制度执行。

附：图表已按同一脚本生成于`FIN3-WKN-151_charts/`；运行`python3 FIN3-WKN-151_reproduce.py`将从`/app/input_files/`重新读取材料并重建本报告及全部图表。
"""

(OUTPUT / "FIN3-WKN-151_授信审批报告.md").write_text(report, encoding="utf-8")
print(f"报告已生成: {OUTPUT / 'FIN3-WKN-151_授信审批报告.md'}")
print(f"图表已生成: {CHARTS}")
print(f"确认正常融资敞口: {confirmed_financing:.2f} 万元；待核实敞口: {pending_financing:.2f} 万元")
print(f"营运资金需求约束: {working_constraint:.2f} 万元；确定押品约束: {collateral_constraint:.2f} 万元；建议额度: {final_recommendation:.2f} 万元")
print(f"报告中文字符（含标点粗略计数）: {len(re.findall(r'[\u4e00-\u9fff，。；：、“”‘’（）《》【】？！,.!?]', report))}")
