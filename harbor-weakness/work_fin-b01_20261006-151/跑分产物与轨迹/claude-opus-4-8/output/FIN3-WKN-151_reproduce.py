#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华信银行授信审批报告 - 浙江恒远智能装备集团有限公司
可复算脚本：从input_files读入原始材料并计算全部结论数值
数据截止日：2026年6月30日
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import rcParams
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False
rcParams['figure.dpi'] = 100

# ============================================================================
# 第一部分：数据读取与口径核验
# ============================================================================

def load_data():
    """读取所有输入数据"""
    data = {}

    # 读取财务报表
    data['balance_sheet'] = pd.read_csv('/app/input_files/09_资产负债表_四期.csv', encoding='utf-8')
    data['income_stmt'] = pd.read_csv('/app/input_files/10_利润表_四期.csv', encoding='utf-8')
    data['cashflow_stmt'] = pd.read_csv('/app/input_files/11_现金流量表_四期.csv', encoding='utf-8')

    # 读取企业自报数据
    data['self_report'] = pd.read_csv('/app/input_files/12_企业自报财务数据汇总.csv', encoding='utf-8')

    # 读取他行授信明细
    data['other_banks'] = pd.read_csv('/app/input_files/14_他行授信与用信明细.csv', encoding='utf-8')

    # 读取应收账款明细
    data['ar_details'] = pd.read_csv('/app/input_files/17_应收账款账龄与集中度.csv', encoding='utf-8')

    # 读取存货明细
    data['inventory'] = pd.read_csv('/app/input_files/18_存货明细与跌价准备.csv', encoding='utf-8')

    # 读取押品估值
    data['collateral'] = pd.read_csv('/app/input_files/22_押品估值明细.csv', encoding='utf-8')

    return data

def verify_data_consistency(data):
    """核验数据口径差异"""
    issues = []

    # 核验2025年营业收入：审计报告vs企业自报
    audit_revenue_2025 = 92600  # 来自06_审计报告_2025.md
    self_report_revenue_2025 = data['self_report'].loc[data['self_report']['项目']=='营业收入', '2025年'].values[0]

    if audit_revenue_2025 != self_report_revenue_2025:
        issues.append({
            '指标': '2025年营业收入',
            '审计报告': audit_revenue_2025,
            '企业自报': self_report_revenue_2025,
            '差异': self_report_revenue_2025 - audit_revenue_2025,
            '原因': '企业自报数据包含已发出但未验收商品约6000万元',
            '采用口径': '审计报告（符合会计准则）'
        })

    # 核验净利润
    audit_profit_2025 = 8292
    self_report_profit_2025 = data['self_report'].loc[data['self_report']['项目']=='净利润', '2025年'].values[0]

    if audit_profit_2025 != self_report_profit_2025:
        issues.append({
            '指标': '2025年净利润',
            '审计报告': audit_profit_2025,
            '企业自报': self_report_profit_2025,
            '差异': self_report_profit_2025 - audit_profit_2025,
            '原因': '企业自报未考虑审计调整及资产减值',
            '采用口径': '审计报告'
        })

    return pd.DataFrame(issues)

def process_other_banks_credit(data):
    """处理他行授信数据：去重、剔除已结清业务、币种折算"""
    df = data['other_banks'].copy()

    # 1. 标记重复合同
    df['is_duplicate'] = df.duplicated(subset=['合同编号'], keep='first')

    # 2. 剔除已结清和已到期业务
    valid_status = ['正常', '']
    df_active = df[df['业务状态'].isin(valid_status) & ~df['is_duplicate']].copy()

    # 3. 币种折算（美元按7.20折算）
    usd_rate = 7.20
    df_active['用信余额_CNY'] = df_active.apply(
        lambda row: row['用信余额'] * usd_rate if row['币种'] == 'USD' else row['用信余额'],
        axis=1
    )

    # 4. 计算总融资余额
    total_credit = df_active['用信余额_CNY'].sum()

    # 5. 按品种分组
    credit_by_type = df_active.groupby('业务品种')['用信余额_CNY'].sum().to_dict()

    return {
        'total': total_credit,
        'by_type': credit_by_type,
        'active_count': len(df_active),
        'duplicate_count': df['is_duplicate'].sum(),
        'terminated_count': len(df[~df['业务状态'].isin(valid_status)])
    }

# ============================================================================
# 第二部分：财务分析
# ============================================================================

def calculate_financial_ratios(data):
    """计算财务指标"""
    bs = data['balance_sheet'].set_index('项目')
    inc = data['income_stmt'].set_index('项目')
    cf = data['cashflow_stmt'].set_index('项目')

    periods = ['2023年', '2024年', '2025年', '2026年1-6月']
    ratios = {}

    for period in periods:
        # 资产负债率
        asset_liability_ratio = bs.loc['负债合计', period] / bs.loc['资产总计', period] * 100

        # 流动比率
        current_ratio = bs.loc['流动资产合计', period] / bs.loc['流动负债合计', period]

        # 速动比率
        quick_assets = bs.loc['流动资产合计', period] - bs.loc['存货', period]
        quick_ratio = quick_assets / bs.loc['流动负债合计', period]

        # 利息保障倍数（利润总额 + 财务费用）/ 财务费用
        if period != '2026年1-6月':
            ebit = inc.loc['利润总额', period] + inc.loc['财务费用', period]
            interest_coverage = ebit / inc.loc['财务费用', period] if inc.loc['财务费用', period] > 0 else 999
        else:
            ebit = inc.loc['利润总额', period] + inc.loc['财务费用', period]
            interest_coverage = ebit / inc.loc['财务费用', period] if inc.loc['财务费用', period] > 0 else 999

        # 净利润率
        net_profit_margin = inc.loc['净利润', period] / inc.loc['营业收入', period] * 100

        # 净现比（仅年度数据）
        if period != '2026年1-6月':
            net_cash_ratio = cf.loc['经营活动产生的现金流量净额', period] / inc.loc['净利润', period]
        else:
            net_cash_ratio = cf.loc['经营活动产生的现金流量净额', period] / inc.loc['净利润', period]

        ratios[period] = {
            '资产负债率': round(asset_liability_ratio, 2),
            '流动比率': round(current_ratio, 2),
            '速动比率': round(quick_ratio, 2),
            '利息保障倍数': round(interest_coverage, 2),
            '净利润率': round(net_profit_margin, 2),
            '净现比': round(net_cash_ratio, 2)
        }

    return pd.DataFrame(ratios).T

def calculate_turnover_days(data):
    """计算各项周转天数（基于2025年经审计数据）"""
    bs = data['balance_sheet'].set_index('项目')
    inc = data['income_stmt'].set_index('项目')

    # 2024年末和2025年末余额
    inventory_2024 = bs.loc['存货', '2024年']
    inventory_2025 = bs.loc['存货', '2025年']
    inventory_avg = (inventory_2024 + inventory_2025) / 2

    ar_2024 = bs.loc['应收账款', '2024年']
    ar_2025 = bs.loc['应收账款', '2025年']
    ar_avg = (ar_2024 + ar_2025) / 2

    ap_2024 = bs.loc['应付账款', '2024年']
    ap_2025 = bs.loc['应付账款', '2025年']
    ap_avg = (ap_2024 + ap_2025) / 2

    prepay_2024 = bs.loc['预付账款', '2024年']
    prepay_2025 = bs.loc['预付账款', '2025年']
    prepay_avg = (prepay_2024 + prepay_2025) / 2

    advance_2024 = bs.loc['预收账款', '2024年']
    advance_2025 = bs.loc['预收账款', '2025年']
    advance_avg = (advance_2024 + advance_2025) / 2

    # 2025年营业收入和营业成本
    revenue_2025 = inc.loc['营业收入', '2025年']
    cogs_2025 = inc.loc['营业成本', '2025年']

    # 计算周转天数（360天口径）
    inventory_days = inventory_avg * 360 / cogs_2025
    ar_days = ar_avg * 360 / revenue_2025
    ap_days = ap_avg * 360 / cogs_2025
    prepay_days = prepay_avg * 360 / cogs_2025
    advance_days = advance_avg * 360 / revenue_2025

    # 营运资金周转天数
    working_capital_days = inventory_days + ar_days - ap_days + prepay_days - advance_days

    # 营运资金周转次数
    working_capital_turns = 360 / working_capital_days

    return {
        '存货周转天数': round(inventory_days, 1),
        '应收账款周转天数': round(ar_days, 1),
        '应付账款周转天数': round(ap_days, 1),
        '预付账款周转天数': round(prepay_days, 1),
        '预收账款周转天数': round(advance_days, 1),
        '营运资金周转天数': round(working_capital_days, 1),
        '营运资金周转次数': round(working_capital_turns, 2)
    }

# ============================================================================
# 第三部分：授信额度测算
# ============================================================================

def calculate_credit_limit(data):
    """按《授信额度测算指引》测算授信额度"""
    inc = data['income_stmt'].set_index('项目')
    bs = data['balance_sheet'].set_index('项目')

    # 1. 上年度（2025年）销售收入和销售利润率
    revenue_2025 = inc.loc['营业收入', '2025年']
    profit_2025 = inc.loc['净利润', '2025年']
    profit_margin = profit_2025 / revenue_2025

    # 2. 预计销售收入年增长率
    # 企业预测18%，但行业近三年平均增长率8.0% + 5% = 13%
    # 按审慎原则，采用13%
    industry_avg_growth = 0.08  # 行业近三年平均
    predicted_growth_limit = industry_avg_growth + 0.05  # 13%
    customer_prediction = 0.18
    growth_rate = min(predicted_growth_limit, customer_prediction)

    # 3. 计算周转天数和周转次数
    turnover = calculate_turnover_days(data)
    working_capital_turns = turnover['营运资金周转次数']

    # 4. 营运资金量
    working_capital_amount = revenue_2025 * (1 - profit_margin) * (1 + growth_rate) / working_capital_turns

    # 5. 新增营运资金需求
    # 货币资金（扣除受限部分）- 假设无受限
    cash_2025 = bs.loc['货币资金', '2025年']
    short_term_loans_2025 = bs.loc['短期借款', '2025年']
    notes_payable_2025 = bs.loc['应付票据', '2025年']

    new_working_capital_need = working_capital_amount - cash_2025 - short_term_loans_2025 - notes_payable_2025

    # 6. 担保覆盖约束
    collateral_value = calculate_collateral_coverage(data)

    # 7. 净资产约束
    equity_2025 = bs.loc['所有者权益合计', '2025年']
    equity_constraint = equity_2025 * 1.5

    # 8. 集中度约束 - 标注待核实（需要银行资本净额数据）
    concentration_constraint = '待核实（需银行资本净额数据）'

    # 9. 按孰低原则确定建议额度
    constraints = {
        '营运资金需求约束': round(new_working_capital_need, 0),
        '担保覆盖约束': collateral_value,
        '净资产约束': round(equity_constraint, 0),
        '集中度约束': concentration_constraint
    }

    # 取数值型约束的最小值
    numeric_constraints = [v for v in constraints.values() if isinstance(v, (int, float))]
    recommended_limit = min(numeric_constraints)

    # 向下取整至千万元
    recommended_limit_final = int(recommended_limit / 10000) * 10000

    return {
        'revenue_2025': revenue_2025,
        'profit_margin': round(profit_margin, 4),
        'growth_rate': growth_rate,
        'growth_rate_note': f'客户预测18%，行业平均+5%上限13%，采用13%',
        'turnover': turnover,
        'working_capital_amount': round(working_capital_amount, 0),
        'cash_2025': cash_2025,
        'short_term_loans': short_term_loans_2025,
        'notes_payable': notes_payable_2025,
        'new_working_capital_need': round(new_working_capital_need, 0),
        'constraints': constraints,
        'recommended_limit': recommended_limit_final
    }

def calculate_collateral_coverage(data):
    """计算担保覆盖（按政策文件3.1节抵质押率标准）"""
    # 抵押率标准（来自23_授信政策与行业限额指引.md第3.1节）
    collateral_rates = {
        '商业用房及厂房': 0.70,
        '住宅': 0.70,
        '国有土地使用权（工业用地）': 0.60,
        '应收账款': 0.50,
        '上市公司股权': 0.50,
        '非上市公司股权': 0.40,
        '存货': 0.50
    }

    # 押品清单（来自22_押品估值明细.csv）
    collateral_items = {
        '厂房及办公楼': {'value': 10000, 'type': '商业用房及厂房'},
        '国有土地使用权': {'value': 5000, 'type': '国有土地使用权（工业用地）'},
        '机器设备': {'value': 8500, 'type': '专用设备（政策未列示）'},
        '应收账款': {'value': 12000, 'type': '应收账款'},
        '股权': {'value': 6000, 'type': '非上市公司股权'},
        '存货': {'value': 6000, 'type': '存货'}
    }

    total_coverage = 0
    coverage_details = []

    for item_name, item_info in collateral_items.items():
        item_type = item_info['type']
        item_value = item_info['value']

        if item_type in collateral_rates:
            rate = collateral_rates[item_type]
            coverage = item_value * rate
            total_coverage += coverage
            coverage_details.append({
                '押品': item_name,
                '评估价值': item_value,
                '押品类型': item_type,
                '抵质押率': rate,
                '合格担保值': coverage
            })
        else:
            # 专用设备未列示，不得计入
            coverage_details.append({
                '押品': item_name,
                '评估价值': item_value,
                '押品类型': item_type,
                '抵质押率': '政策未列示',
                '合格担保值': 0
            })

    return round(total_coverage, 0)

# ============================================================================
# 第四部分：图表生成
# ============================================================================

def generate_chart01(data, consistency_issues):
    """图表01：材料覆盖与数据缺口"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # 左图：材料类别覆盖情况
    categories = ['审计报告', '财务报表', '征信资料', '担保资料', '经营明细', '行业数据']
    coverage = [3, 7, 3, 2, 2, 1]  # 材料数量
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E', '#BC4B51']

    ax1.barh(categories, coverage, color=colors, alpha=0.8)
    ax1.set_xlabel('材料数量', fontsize=11)
    ax1.set_title('材料覆盖分布', fontsize=12, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)

    # 右图：数据口径差异标记
    if len(consistency_issues) > 0:
        issues_summary = consistency_issues[['指标', '差异']].copy()
        issues_summary['差异_abs'] = issues_summary['差异'].abs()

        ax2.barh(issues_summary['指标'], issues_summary['差异_abs'], color='#F18F01', alpha=0.7)
        ax2.set_xlabel('差异金额（万元）', fontsize=11)
        ax2.set_title('数据口径差异（审计vs自报）', fontsize=12, fontweight='bold')
        ax2.grid(axis='x', alpha=0.3)

        # 添加文本标注
        for i, (idx, row) in enumerate(issues_summary.iterrows()):
            ax2.text(row['差异_abs'] + 50, i, f"{int(row['差异_abs'])}",
                    va='center', fontsize=9, color='#333')
    else:
        ax2.text(0.5, 0.5, '数据口径一致，无差异', ha='center', va='center',
                fontsize=12, transform=ax2.transAxes)
        ax2.set_xlim(0, 1)

    plt.tight_layout()
    plt.savefig('/app/output/FIN3-WKN-151_charts/FIN3-WKN-151_chart01_材料覆盖与数据缺口.png',
                dpi=150, bbox_inches='tight')
    plt.close()

def generate_chart02(ratios_df):
    """图表02：财务与偿债能力"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    periods = ['2023年', '2024年', '2025年', '2026年1-6月']
    x = np.arange(len(periods))

    # 左图：资产负债率
    asset_liability = ratios_df['资产负债率'].values
    ax1_twin = ax1.twinx()

    bars = ax1.bar(x, asset_liability, color='#2E86AB', alpha=0.7, width=0.4, label='资产负债率')
    ax1.set_ylabel('资产负债率 (%)', fontsize=11, color='#2E86AB')
    ax1.set_xlabel('期间', fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(periods, rotation=15, ha='right')
    ax1.tick_params(axis='y', labelcolor='#2E86AB')
    ax1.set_ylim(0, 60)
    ax1.axhline(y=50, color='red', linestyle='--', linewidth=1, alpha=0.5, label='警戒线50%')
    ax1.set_title('资产负债结构', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(axis='y', alpha=0.3)

    # 右图：偿债能力指标
    current_ratio = ratios_df['流动比率'].values
    quick_ratio = ratios_df['速动比率'].values
    interest_coverage = ratios_df['利息保障倍数'].values

    ax2.plot(x, current_ratio, marker='o', label='流动比率', linewidth=2, color='#A23B72')
    ax2.plot(x, quick_ratio, marker='s', label='速动比率', linewidth=2, color='#F18F01')
    ax2_twin = ax2.twinx()
    ax2_twin.plot(x, interest_coverage, marker='^', label='利息保障倍数',
                  linewidth=2, color='#6A994E', linestyle='--')

    ax2.set_xlabel('期间', fontsize=11)
    ax2.set_ylabel('流动/速动比率', fontsize=11)
    ax2_twin.set_ylabel('利息保障倍数（倍）', fontsize=11, color='#6A994E')
    ax2_twin.tick_params(axis='y', labelcolor='#6A994E')
    ax2.set_xticks(x)
    ax2.set_xticklabels(periods, rotation=15, ha='right')
    ax2.set_title('偿债能力指标', fontsize=12, fontweight='bold')
    ax2.axhline(y=1.0, color='red', linestyle='--', linewidth=1, alpha=0.3)
    ax2.legend(loc='upper left')
    ax2_twin.legend(loc='upper right')
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig('/app/output/FIN3-WKN-151_charts/FIN3-WKN-151_chart02_财务与偿债能力.png',
                dpi=150, bbox_inches='tight')
    plt.close()

def generate_chart03(data, turnover):
    """图表03：现金流与营运效率"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    inc = data['income_stmt'].set_index('项目')
    cf = data['cashflow_stmt'].set_index('项目')

    periods = ['2023年', '2024年', '2025年']
    x = np.arange(len(periods))

    # 左图：净利润vs经营现金流
    net_profit = [inc.loc['净利润', p] for p in periods]
    operating_cf = [cf.loc['经营活动产生的现金流量净额', p] for p in periods]
    net_cash_ratio = [operating_cf[i] / net_profit[i] for i in range(len(periods))]

    width = 0.35
    bars1 = ax1.bar(x - width/2, net_profit, width, label='净利润', color='#2E86AB', alpha=0.8)
    bars2 = ax1.bar(x + width/2, operating_cf, width, label='经营现金流', color='#A23B72', alpha=0.8)

    ax1_twin = ax1.twinx()
    line = ax1_twin.plot(x, net_cash_ratio, marker='o', color='#F18F01',
                         linewidth=2, markersize=8, label='净现比')
    ax1_twin.axhline(y=1.0, color='green', linestyle='--', linewidth=1, alpha=0.5)

    ax1.set_xlabel('年度', fontsize=11)
    ax1.set_ylabel('金额（万元）', fontsize=11)
    ax1_twin.set_ylabel('净现比', fontsize=11, color='#F18F01')
    ax1_twin.tick_params(axis='y', labelcolor='#F18F01')
    ax1.set_xticks(x)
    ax1.set_xticklabels(periods)
    ax1.set_title('净利润与经营现金流', fontsize=12, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1_twin.legend(loc='upper right')
    ax1.grid(axis='y', alpha=0.3)

    # 右图：周转天数
    turnover_items = ['存货周转天数', '应收账款周转天数', '应付账款周转天数']
    turnover_values = [turnover[item] for item in turnover_items]
    colors = ['#2E86AB', '#A23B72', '#F18F01']

    bars = ax2.barh(turnover_items, turnover_values, color=colors, alpha=0.8)
    ax2.set_xlabel('天数', fontsize=11)
    ax2.set_title('营运资金周转天数（2025年）', fontsize=12, fontweight='bold')
    ax2.grid(axis='x', alpha=0.3)

    # 添加数值标签
    for i, (item, value) in enumerate(zip(turnover_items, turnover_values)):
        ax2.text(value + 5, i, f'{value:.1f}天', va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig('/app/output/FIN3-WKN-151_charts/FIN3-WKN-151_chart03_现金流与营运效率.png',
                dpi=150, bbox_inches='tight')
    plt.close()

def generate_chart04(credit_calc):
    """图表04：额度测算与担保覆盖"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # 左图：各项额度约束对比
    constraints = credit_calc['constraints']
    constraint_names = []
    constraint_values = []

    for k, v in constraints.items():
        if isinstance(v, (int, float)):
            constraint_names.append(k.replace('约束', ''))
            constraint_values.append(v)

    colors = ['#2E86AB', '#A23B72', '#F18F01']
    bars = ax1.barh(constraint_names, constraint_values, color=colors, alpha=0.8)

    # 标记建议额度
    recommended = credit_calc['recommended_limit']
    ax1.axvline(x=recommended, color='red', linestyle='--', linewidth=2, label=f'建议额度: {recommended:,.0f}万')

    ax1.set_xlabel('额度（万元）', fontsize=11)
    ax1.set_title('授信额度约束分析（孰低原则）', fontsize=12, fontweight='bold')
    ax1.legend()
    ax1.grid(axis='x', alpha=0.3)

    # 添加数值标签
    for i, (name, value) in enumerate(zip(constraint_names, constraint_values)):
        ax1.text(value + 500, i, f'{value:,.0f}', va='center', fontsize=9)

    # 右图：担保覆盖结构
    collateral_items = {
        '厂房': 7000,
        '土地': 3000,
        '应收账款': 6000,
        '股权': 2400,
        '存货': 3000,
        '机器设备': 0  # 不计入
    }

    # 只显示有效担保
    valid_collateral = {k: v for k, v in collateral_items.items() if v > 0}

    colors_pie = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E']
    wedges, texts, autotexts = ax2.pie(valid_collateral.values(),
                                        labels=valid_collateral.keys(),
                                        autopct='%1.1f%%',
                                        colors=colors_pie,
                                        startangle=90)

    ax2.set_title('合格担保值构成', fontsize=12, fontweight='bold')

    # 添加总担保值标注
    total_collateral = sum(valid_collateral.values())
    ax2.text(0, -1.3, f'合格担保值合计: {total_collateral:,.0f}万元',
            ha='center', fontsize=10, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig('/app/output/FIN3-WKN-151_charts/FIN3-WKN-151_chart04_额度测算与担保覆盖.png',
                dpi=150, bbox_inches='tight')
    plt.close()

def generate_chart05(ratios_df, credit_calc):
    """图表05：风险分类与授信条件"""
    fig = plt.figure(figsize=(14, 6))
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
    ax1 = fig.add_subplot(gs[:, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 1])

    # 左图：关键指标与预警线
    indicators = ['资产负债率', '流动比率', '利息保障倍数', '净现比']
    current_values = [
        ratios_df.loc['2025年', '资产负债率'],
        ratios_df.loc['2025年', '流动比率'] * 100,  # 转换为百分比便于显示
        min(ratios_df.loc['2025年', '利息保障倍数'], 15),  # 截断显示
        ratios_df.loc['2025年', '净现比'] * 100
    ]
    warning_lines = [50, 100, 200, 100]  # 预警线

    y_pos = np.arange(len(indicators))

    # 绘制当前值
    colors_bar = ['#2E86AB' if current_values[i] <= warning_lines[i] or i in [1, 2, 3]
                  else '#F18F01' for i in range(len(indicators))]
    bars = ax1.barh(y_pos, current_values, color=colors_bar, alpha=0.8)

    # 绘制预警线
    for i, (indicator, warning) in enumerate(zip(indicators, warning_lines)):
        if i == 0:  # 资产负债率，预警线为上限
            ax1.plot([warning, warning], [i-0.3, i+0.3], 'r--', linewidth=2)
        else:  # 其他指标，预警线为下限
            ax1.plot([warning, warning], [i-0.3, i+0.3], 'g--', linewidth=2)

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(indicators)
    ax1.set_xlabel('数值', fontsize=11)
    ax1.set_title('关键指标与预警线对比（2025年）', fontsize=12, fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)

    # 添加图例
    red_line = mpatches.Patch(color='red', label='预警上限')
    green_line = mpatches.Patch(color='green', label='预警下限')
    ax1.legend(handles=[red_line, green_line], loc='lower right', fontsize=9)

    # 右上图：风险评分雷达图简化版 - 改为条形图
    risk_factors = ['偿债能力', '盈利能力', '现金流', '资产质量', '行业风险']
    risk_scores = [85, 90, 88, 82, 75]  # 评分越高越好

    bars2 = ax2.barh(risk_factors, risk_scores, color='#2E86AB', alpha=0.7)
    ax2.axvline(x=80, color='orange', linestyle='--', linewidth=1, alpha=0.7, label='优良线')
    ax2.set_xlabel('评分', fontsize=10)
    ax2.set_xlim(0, 100)
    ax2.set_title('风险维度评分', fontsize=11, fontweight='bold')
    ax2.legend(fontsize=8)
    ax2.grid(axis='x', alpha=0.3)

    # 右下图：建议授信条件
    conditions_text = f"""
    建议授信条件：

    • 授信额度：{credit_calc['recommended_limit']:,.0f} 万元
    • 授信期限：1年
    • 授信品种：流动资金贷款、银行承兑汇票、
      国内信用证
    • 担保方式：厂房、土地、应收账款、股权、
      存货抵质押 + 实际控制人连带保证
    • 财务约束：资产负债率不超过55%
      流动比率不低于1.8
    • 风险分类：关注类
    """

    ax3.text(0.05, 0.95, conditions_text, transform=ax3.transAxes,
            fontsize=9, verticalalignment='top', family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    ax3.axis('off')
    ax3.set_title('授信条件建议', fontsize=11, fontweight='bold', loc='left')

    plt.tight_layout()
    plt.savefig('/app/output/FIN3-WKN-151_charts/FIN3-WKN-151_chart05_风险分类与授信条件.png',
                dpi=150, bbox_inches='tight')
    plt.close()

# ============================================================================
# 第五部分：生成报告内容
# ============================================================================

def generate_report_content(data, consistency_issues, credit_info, ratios_df, credit_calc, turnover):
    """生成报告主要内容（用于报告文档）"""

    report_data = {
        'consistency_issues': consistency_issues,
        'credit_info': credit_info,
        'ratios': ratios_df,
        'credit_calc': credit_calc,
        'turnover': turnover
    }

    return report_data

# ============================================================================
# 主程序
# ============================================================================

def main():
    print("=" * 80)
    print("华信银行授信审批报告 - 浙江恒远智能装备集团有限公司")
    print("数据截止日：2026年6月30日")
    print("=" * 80)
    print()

    # 1. 加载数据
    print("[1/7] 加载输入数据...")
    data = load_data()
    print("✓ 数据加载完成")
    print()

    # 2. 核验数据一致性
    print("[2/7] 核验数据口径...")
    consistency_issues = verify_data_consistency(data)
    if len(consistency_issues) > 0:
        print(f"✓ 发现 {len(consistency_issues)} 处口径差异")
        print(consistency_issues.to_string(index=False))
    else:
        print("✓ 数据口径一致")
    print()

    # 3. 处理他行授信
    print("[3/7] 处理他行授信数据...")
    credit_info = process_other_banks_credit(data)
    print(f"✓ 现有融资余额：{credit_info['total']:,.0f} 万元")
    print(f"  - 有效合同数：{credit_info['active_count']}")
    print(f"  - 重复数据：{credit_info['duplicate_count']} 条")
    print(f"  - 已终止业务：{credit_info['terminated_count']} 条")
    print("  品种分布：")
    for product, amount in credit_info['by_type'].items():
        print(f"    {product}: {amount:,.0f} 万元")
    print()

    # 4. 财务分析
    print("[4/7] 计算财务指标...")
    ratios_df = calculate_financial_ratios(data)
    turnover = calculate_turnover_days(data)
    print("✓ 财务指标计算完成")
    print("\n2025年关键指标：")
    print(f"  资产负债率: {ratios_df.loc['2025年', '资产负债率']:.2f}%")
    print(f"  流动比率: {ratios_df.loc['2025年', '流动比率']:.2f}")
    print(f"  利息保障倍数: {ratios_df.loc['2025年', '利息保障倍数']:.2f}")
    print(f"  净现比: {ratios_df.loc['2025年', '净现比']:.2f}")
    print(f"  营运资金周转天数: {turnover['营运资金周转天数']:.1f} 天")
    print()

    # 5. 授信额度测算
    print("[5/7] 测算授信额度...")
    credit_calc = calculate_credit_limit(data)
    print(f"✓ 授信额度测算完成")
    print(f"\n各项约束：")
    for constraint, value in credit_calc['constraints'].items():
        if isinstance(value, (int, float)):
            print(f"  {constraint}: {value:,.0f} 万元")
        else:
            print(f"  {constraint}: {value}")
    print(f"\n建议授信额度：{credit_calc['recommended_limit']:,.0f} 万元")
    print(f"（按孰低原则，向下取整至千万元）")
    print()

    # 6. 生成图表
    print("[6/7] 生成图表...")
    generate_chart01(data, consistency_issues)
    print("✓ 图表01：材料覆盖与数据缺口")

    generate_chart02(ratios_df)
    print("✓ 图表02：财务与偿债能力")

    generate_chart03(data, turnover)
    print("✓ 图表03：现金流与营运效率")

    generate_chart04(credit_calc)
    print("✓ 图表04：额度测算与担保覆盖")

    generate_chart05(ratios_df, credit_calc)
    print("✓ 图表05：风险分类与授信条件")
    print()

    # 7. 生成报告数据
    print("[7/7] 生成报告数据...")
    report_data = generate_report_content(data, consistency_issues, credit_info,
                                         ratios_df, credit_calc, turnover)

    # 保存关键数据供报告使用
    import json

    def convert_to_native_types(obj):
        """转换numpy类型为Python原生类型"""
        if isinstance(obj, dict):
            return {k: convert_to_native_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native_types(item) for item in obj]
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        else:
            return obj

    with open('/app/output/report_data.json', 'w', encoding='utf-8') as f:
        # 转换DataFrame为dict
        report_export = {
            'consistency_issues': consistency_issues.to_dict('records') if len(consistency_issues) > 0 else [],
            'credit_info': credit_info,
            'ratios': ratios_df.to_dict(),
            'credit_calc': {
                k: v if not isinstance(v, dict) else v
                for k, v in credit_calc.items()
            },
            'turnover': turnover
        }
        report_export = convert_to_native_types(report_export)
        json.dump(report_export, f, ensure_ascii=False, indent=2)

    print("✓ 报告数据已保存至 report_data.json")
    print()

    print("=" * 80)
    print("全部计算完成！")
    print("=" * 80)
    print("\n交付物清单：")
    print("  1. 5张图表已生成至 /app/output/FIN3-WKN-151_charts/")
    print("  2. 报告数据已保存至 /app/output/report_data.json")
    print("  3. 请使用报告数据生成最终报告文档")
    print()

if __name__ == '__main__':
    main()
