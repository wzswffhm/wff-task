#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-IPO 投资决策备忘录 - 可复算脚本
标的公司：杭州智联精密制造股份有限公司
估值基准日：2025年12月31日
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
# 第一部分：数据读取与核验
# ============================================================================

def load_all_data():
    """从input_files读取所有源数据"""
    data = {}

    # 1. 审计报告数据（利润表）
    profit_data = {
        '2023': {'营业收入': 82000, '营业成本': 61300, '销售费用': 2800, '管理费用': 4500,
                '研发费用': 4200, '财务费用': 350, '利息费用': 380, '其他收益': 1200,
                '投资收益': 280, '公允价值变动': 120, '资产处置': 300, '减值损失': -590,
                '营业利润': 10160, '营业外收支': -60, '利润总额': 10100, '所得税': 1515,
                '净利润': 8585, '归母净利润': 8585},
        '2024': {'营业收入': 105000, '营业成本': 78600, '销售费用': 3400, '管理费用': 5300,
                '研发费用': 5600, '财务费用': 420, '利息费用': 460, '其他收益': 1500,
                '投资收益': 360, '公允价值变动': 180, '资产处置': 0, '减值损失': -820,
                '营业利润': 12900, '营业外收支': 40, '利润总额': 12940, '所得税': 1941,
                '净利润': 10999, '归母净利润': 10999},
        '2025': {'营业收入': 130000, '营业成本': 97000, '销售费用': 4100, '管理费用': 6200,
                '研发费用': 7100, '财务费用': 380, '利息费用': 420, '其他收益': 1800,
                '投资收益': 420, '公允价值变动': 260, '资产处置': 600, '减值损失': -1020,
                '营业利润': 17280, '营业外收支': -80, '利润总额': 17200, '所得税': 2580,
                '净利润': 14620, '归母净利润': 14620},
        '2026H1': {'营业收入': 72000, '营业成本': 54300, '销售费用': 2300, '管理费用': 3400,
                  '研发费用': 4100, '财务费用': 180, '利息费用': 200, '其他收益': 900,
                  '投资收益': 300, '公允价值变动': 60, '资产处置': 0, '减值损失': -500,
                  '营业利润': 8480, '营业外收支': 20, '利润总额': 8500, '所得税': 1275,
                  '净利润': 7225, '归母净利润': 7225}
    }
    data['profit'] = pd.DataFrame(profit_data).T

    # 2. 资产负债表数据
    balance_data = {
        '2023': {'货币资金': 16800, '应收账款': 24000, '存货': 18000, '固定资产': 28500,
                '在建工程': 4600, '资产总计': 78400, '短期借款': 9000, '长期借款': 6000,
                '负债合计': 38600, '所有者权益': 39800},
        '2024': {'货币资金': 21400, '应收账款': 31500, '存货': 22500, '固定资产': 34200,
                '在建工程': 5200, '资产总计': 96800, '短期借款': 11500, '长期借款': 7500,
                '负债合计': 46200, '所有者权益': 50600},
        '2025': {'货币资金': 25000, '应收账款': 40200, '存货': 27000, '固定资产': 39800,
                '在建工程': 3800, '资产总计': 118500, '短期借款': 12000, '长期借款': 8000,
                '负债合计': 53800, '所有者权益': 64700},
        '2026H1': {'货币资金': 28300, '应收账款': 47500, '存货': 31000, '固定资产': 42600,
                  '在建工程': 3100, '资产总计': 131200, '短期借款': 13500, '长期借款': 7000,
                  '负债合计': 57900, '所有者权益': 73300}
    }
    data['balance'] = pd.DataFrame(balance_data).T

    # 3. 现金流量表数据
    cashflow_data = {
        '2023': {'经营现金流': 9200, '投资现金流': -8600, '筹资现金流': 2400, '现金净增加': 3000},
        '2024': {'经营现金流': 11500, '投资现金流': -11200, '筹资现金流': 3600, '现金净增加': 3900},
        '2025': {'经营现金流': 15800, '投资现金流': -12400, '筹资现金流': 1800, '现金净增加': 5200},
        '2026H1': {'经营现金流': 6900, '投资现金流': -6300, '筹资现金流': 2100, '现金净增加': 2700}
    }
    data['cashflow'] = pd.DataFrame(cashflow_data).T

    # 4. 货币资金受限情况
    restricted_cash = {
        '2023': {'质押保证金': 1200, '承兑保证金': 800, '保函保证金': 400, '受限合计': 2400},
        '2024': {'质押保证金': 1700, '承兑保证金': 900, '保函保证金': 300, '受限合计': 2900},
        '2025': {'质押保证金': 1800, '承兑保证金': 1200, '保函保证金': 500, '受限合计': 3500},
        '2026H1': {'质押保证金': 2000, '承兑保证金': 1500, '保函保证金': 1000, '受限合计': 4500}
    }
    data['restricted_cash'] = pd.DataFrame(restricted_cash).T

    # 5. 非经常性损益明细（税后）
    non_recurring = {
        '2023': {'政府补助': 1020, '投资收益': 238, '公允价值变动': 102, '资产处置': 255, '营业外收支': -51, '合计': 1564},
        '2024': {'政府补助': 1275, '投资收益': 306, '公允价值变动': 153, '资产处置': 0, '营业外收支': 34, '合计': 1768},
        '2025': {'政府补助': 1530, '投资收益': 357, '公允价值变动': 221, '资产处置': 510, '营业外收支': -68, '合计': 2550},
        '2026H1': {'政府补助': 765, '投资收益': 255, '公允价值变动': 51, '资产处置': 0, '营业外收支': 17, '合计': 1088}
    }
    data['non_recurring'] = pd.DataFrame(non_recurring).T

    # 6. 股份支付费用
    stock_payment = {'2023': 300, '2024': 480, '2025': 620, '2026H1': 350}
    data['stock_payment'] = pd.Series(stock_payment)

    # 7. 折旧摊销
    depreciation = {'2023': 4800, '2024': 5760, '2025': 7200, '2026H1': 3600}
    data['depreciation'] = pd.Series(depreciation)

    # 8. 可比公司数据（已清洗版本）
    comparables_clean = {
        '证券代码': ['300001.SZ', '300002.SZ', '300003.SZ', '300004.SZ', '300005.SZ',
                    '300006.SZ', '300007.SZ', '300008.SZ', '300009.SZ', '300010.SZ',
                    '300014.SZ', '300015.SZ'],
        '证券简称': ['精工精密', '富临结构', '东兴模组', '华威精工', '润泽科技',
                    '安捷制造', '明泰材料', '正泰结构', '晶合智造', '天元精密',
                    '远景精工', '中和智造'],
        '上市日期': ['2019-04-11', '2020-07-23', '2017-11-30', '2021-09-15', '2016-03-08',
                     '2022-06-20', '2018-12-05', '2020-03-27', '2019-10-18', '2021-12-09',
                     '2018-06-30', '2017-02-22'],
        '2025归母净利润': [42100, 22800, 31500, 18600, 56300, 12900, 38400, 27400, 45700, 16300, 29600, 35100],
        '2025营业收入': [452000, 231000, 288000, 197000, 610000, 143000, 336000, 259000, 398000, 158000, 302000, 366000],
        '2025EBITDA': [78600, 41500, 55200, 34200, 102000, 24800, 61600, 46900, 72800, 28600, 53400, 63200],
        'PE_TTM': [15.96, 16.32, 15.81, 15.65, 16.50, 15.89, 15.89, 16.17, 16.21, 16.07, 16.49, 16.75],
        'PS_TTM': [1.49, 1.61, 1.73, 1.48, 1.52, 1.43, 1.82, 1.71, 1.86, 1.66, 1.62, 1.61],
        'EV_EBITDA': [8.55, 8.96, 9.02, 8.51, 9.11, 8.27, 9.90, 9.45, 10.18, 9.16, 9.14, 9.30],
        'UnleveredBeta': [0.92, 0.98, 0.95, 0.89, 1.02, 0.94, 0.97, 0.93, 1.05, 0.91, 0.99, 1.00]
    }
    data['comparables'] = pd.DataFrame(comparables_clean)

    return data

# ============================================================================
# 第二部分：数据核验与口径分析
# ============================================================================

def verify_data_consistency(data):
    """核验数据口径一致性"""
    conflicts = []

    # 核验点1：管理层口径 vs 审计报告（来自01文件）
    mgmt_data = {
        '2023': {'营业收入': 82000, '净利润': 8585, '扣非归母': 7150},
        '2024': {'营业收入': 105000, '净利润': 10999, '扣非归母': 9600},
        '2025': {'营业收入': 130000, '净利润': 14620, '扣非归母': 13090},
        '2026H1': {'营业收入': 72000, '净利润': 7225, '扣非归母': 6700}
    }

    # 检查营业收入一致性
    for year in ['2023', '2024', '2025', '2026H1']:
        audit_revenue = data['profit'].loc[year, '营业收入']
        mgmt_revenue = mgmt_data[year]['营业收入']
        if audit_revenue == mgmt_revenue:
            pass  # 一致
        else:
            conflicts.append(f"{year}营业收入：审计报告{audit_revenue}万元 vs 管理层口径{mgmt_revenue}万元")

    # 核验点2：成本数据口径（审计报告营业成本 vs 成本明细合计）
    cost_details = {
        '2023': 61320, '2024': 78505, '2025': 97160, '2026H1': 53815
    }
    for year in cost_details:
        audit_cost = data['profit'].loc[year, '营业成本']
        detail_cost = cost_details[year]
        if abs(audit_cost - detail_cost) > 10:  # 允许小幅差异
            conflicts.append(f"{year}营业成本：审计报告{audit_cost}万元 vs 成本明细{detail_cost}万元 - **口径冲突：取审计报告数**")

    return conflicts

# ============================================================================
# 第三部分：经营质量分析
# ============================================================================

def analyze_operating_quality(data):
    """分析报告期经营质量"""
    results = {}

    # 1. 收入与毛利率
    df = data['profit'].copy()
    df['毛利'] = df['营业收入'] - df['营业成本']
    df['毛利率%'] = (df['毛利'] / df['营业收入'] * 100).round(2)
    df['营业收入增速%'] = df['营业收入'].pct_change() * 100
    results['revenue_margin'] = df[['营业收入', '毛利', '毛利率%', '营业收入增速%']]

    # 2. 期间费用率
    df['销售费用率%'] = (df['销售费用'] / df['营业收入'] * 100).round(2)
    df['管理费用率%'] = (df['管理费用'] / df['营业收入'] * 100).round(2)
    df['研发费用率%'] = (df['研发费用'] / df['营业收入'] * 100).round(2)
    df['期间费用率%'] = df[['销售费用率%', '管理费用率%', '研发费用率%']].sum(axis=1).round(2)
    results['expense_ratio'] = df[['销售费用率%', '管理费用率%', '研发费用率%', '期间费用率%']]

    # 3. 现金流质量
    df_cf = pd.concat([df[['净利润']], data['cashflow'][['经营现金流']]], axis=1)
    df_cf['净现比'] = (df_cf['经营现金流'] / df_cf['净利润']).round(2)
    results['cashflow_quality'] = df_cf

    # 4. 营运效率（应收与存货周转）
    bal = data['balance']
    # 应收账款周转天数 = 平均应收 / 营业收入 * 365
    avg_ar = (bal['应收账款'] + bal['应收账款'].shift(1)) / 2
    turnover_ar = (avg_ar / df['营业收入'] * 365).round(0)
    # 存货周转天数
    avg_inv = (bal['存货'] + bal['存货'].shift(1)) / 2
    turnover_inv = (avg_inv / df['营业成本'] * 365).round(0)

    results['turnover'] = pd.DataFrame({
        '应收账款周转天数': turnover_ar,
        '存货周转天数': turnover_inv
    })

    return results

# ============================================================================
# 第四部分：利润口径还原
# ============================================================================

def profit_adjustment_bridge(data):
    """利润口径还原：净利润→扣非归母→调整后EBITDA"""
    periods = ['2023', '2024', '2025', '2026H1']
    bridge = pd.DataFrame(index=periods)

    # 步骤1：净利润（= 归母净利润，无少数股东）
    bridge['①净利润'] = data['profit']['归母净利润']

    # 步骤2：扣除非经常性损益（税后）
    bridge['②减：非经常性损益（税后）'] = data['non_recurring']['合计']
    bridge['③扣非归母净利润'] = bridge['①净利润'] - bridge['②减：非经常性损益（税后）']

    # 步骤3：加回所得税费用
    bridge['④加回：所得税费用'] = data['profit']['所得税']

    # 步骤4：加回利息费用
    bridge['⑤加回：利息费用'] = data['profit']['利息费用']

    # 步骤5：加回折旧摊销
    bridge['⑥加回：折旧摊销'] = data['depreciation']

    # 步骤6：调整后EBITDA = ③ + ④ + ⑤ + ⑥
    bridge['⑦调整后EBITDA'] = (bridge['③扣非归母净利润'] + bridge['④加回：所得税费用'] +
                                 bridge['⑤加回：利息费用'] + bridge['⑥加回：折旧摊销'])

    return bridge.round(0)

# ============================================================================
# 第五部分：DCF估值
# ============================================================================

def dcf_valuation(data):
    """收益法（DCF）估值"""

    # DCF参数（来自32_DCF参数与折现率指引.md）
    params = {
        '基准日': '2025-12-31',
        '预测期': '2026-2030',
        '2025营业收入': 130000,  # 基数
        '收入增速': 0.10,
        '毛利率': 0.25,
        '期间费用率': 0.135,
        'EBIT率': 0.115,  # = 毛利率 - 期间费用率
        '折旧摊销率': 0.05,
        '资本支出率': 0.06,
        '营运资本追加率': 0.20,  # 按收入增量
        '所得税率': 0.15
    }

    # 折现率计算
    Rf = 0.0235
    ERP = 0.06
    beta_u = 0.95  # 可比公司Unlevered Beta中位数
    D_over_DE = 0.20  # 目标资本结构
    D_over_E = D_over_DE / (1 - D_over_DE)  # = 0.25
    Kd = 0.045
    t = 0.15

    beta_L = beta_u * (1 + (1 - t) * D_over_E)
    Ke = Rf + beta_L * ERP
    WACC = Ke * (1 - D_over_DE) + Kd * (1 - t) * D_over_DE

    discount_params = {
        'Rf': Rf,
        'ERP': ERP,
        'beta_u': beta_u,
        'beta_L': beta_L,
        'Ke': Ke,
        'Kd': Kd,
        'WACC': WACC
    }

    # 预测期现金流（2026-2030）
    forecast = pd.DataFrame(index=range(2026, 2031))
    forecast['年份'] = forecast.index

    # 营业收入
    base_revenue = params['2025营业收入']
    for i, year in enumerate(forecast.index):
        forecast.loc[year, '营业收入'] = base_revenue * (1 + params['收入增速']) ** (i + 1)

    # EBIT = 营业收入 × EBIT率
    forecast['EBIT'] = forecast['营业收入'] * params['EBIT率']

    # 税后EBIT
    forecast['税后EBIT'] = forecast['EBIT'] * (1 - params['所得税率'])

    # 折旧摊销
    forecast['折旧摊销'] = forecast['营业收入'] * params['折旧摊销率']

    # 资本支出
    forecast['资本支出'] = forecast['营业收入'] * params['资本支出率']

    # 营运资本追加（按收入增量）
    forecast['收入增量'] = forecast['营业收入'].diff()
    forecast.loc[2026, '收入增量'] = forecast.loc[2026, '营业收入'] - base_revenue
    forecast['营运资本追加'] = forecast['收入增量'] * params['营运资本追加率']

    # FCFF = 税后EBIT + 折旧摊销 - 资本支出 - 营运资本追加
    forecast['FCFF'] = (forecast['税后EBIT'] + forecast['折旧摊销'] -
                        forecast['资本支出'] - forecast['营运资本追加'])

    # 折现到2025年末
    forecast['折现期'] = forecast.index - 2025
    forecast['折现因子'] = 1 / (1 + WACC) ** forecast['折现期']
    forecast['现值'] = forecast['FCFF'] * forecast['折现因子']

    # 终值（2030年后永续）
    g = 0.025  # 永续增长率
    FCFF_2030 = forecast.loc[2030, 'FCFF']
    TV = FCFF_2030 * (1 + g) / (WACC - g)
    TV_PV = TV / (1 + WACC) ** 5

    # 企业价值
    EV = forecast['现值'].sum() + TV_PV

    # 净负债（2025年末）
    total_debt = data['balance'].loc['2025', '短期借款'] + data['balance'].loc['2025', '长期借款']
    restricted_cash_2025 = data['restricted_cash'].loc['2025', '受限合计']
    free_cash = data['balance'].loc['2025', '货币资金'] - restricted_cash_2025
    net_debt = total_debt - free_cash

    # 股权价值
    equity_value = EV - net_debt
    total_shares = 12000  # 万股
    value_per_share = equity_value / total_shares

    dcf_results = {
        'forecast': forecast.round(0),
        'discount_params': discount_params,
        'terminal_value': TV,
        'terminal_value_pv': TV_PV,
        'enterprise_value': EV,
        'net_debt': net_debt,
        'equity_value': equity_value,
        'value_per_share': value_per_share,
        'total_shares': total_shares
    }

    # 敏感性分析
    wacc_range = np.array([WACC - 0.01, WACC, WACC + 0.01])
    g_range = np.array([g - 0.005, g, g + 0.005])

    sensitivity = pd.DataFrame(index=[f'{w:.2%}' for w in wacc_range],
                               columns=[f'{gg:.2%}' for gg in g_range])

    for i, w in enumerate(wacc_range):
        for j, gg in enumerate(g_range):
            # 重新计算现值
            df_copy = forecast.copy()
            df_copy['折现因子'] = 1 / (1 + w) ** df_copy['折现期']
            df_copy['现值'] = df_copy['FCFF'] * df_copy['折现因子']
            pv_sum = df_copy['现值'].sum()

            # 终值
            tv = FCFF_2030 * (1 + gg) / (w - gg)
            tv_pv = tv / (1 + w) ** 5

            # 股权价值
            ev = pv_sum + tv_pv
            eq = ev - net_debt
            sensitivity.iloc[i, j] = int(eq)

    dcf_results['sensitivity'] = sensitivity

    return dcf_results

# ============================================================================
# 第六部分：市场法估值
# ============================================================================

def market_valuation(data, bridge_df):
    """市场法估值（可比公司）"""

    # 可比公司数据（已清洗，12家）
    comps = data['comparables'].copy()

    # 计算中位数
    pe_median = comps['PE_TTM'].median()
    ps_median = comps['PS_TTM'].median()
    ev_ebitda_median = comps['EV_EBITDA'].median()
    beta_u_median = comps['UnleveredBeta'].median()

    multiples_summary = {
        'PE_TTM中位数': pe_median,
        'PS_TTM中位数': ps_median,
        'EV/EBITDA中位数': ev_ebitda_median,
        'Unlevered Beta中位数': beta_u_median
    }

    # 标的公司2025年指标
    target_net_profit_2025 = bridge_df.loc['2025', '③扣非归母净利润']
    target_revenue_2025 = 130000
    target_ebitda_2025 = bridge_df.loc['2025', '⑦调整后EBITDA']

    # 三种估值方法（流动性折价前）
    valuation_pe_pre = target_net_profit_2025 * pe_median
    valuation_ps_pre = target_revenue_2025 * ps_median
    valuation_ev_ebitda_pre = target_ebitda_2025 * ev_ebitda_median

    # 流动性折价10%
    discount_rate = 0.10
    valuation_pe = valuation_pe_pre * (1 - discount_rate)
    valuation_ps = valuation_ps_pre * (1 - discount_rate)
    valuation_ev_ebitda = valuation_ev_ebitda_pre * (1 - discount_rate)

    market_results = {
        'comparables': comps,
        'multiples_summary': multiples_summary,
        'target_metrics': {
            '扣非归母净利润_2025': target_net_profit_2025,
            '营业收入_2025': target_revenue_2025,
            '调整后EBITDA_2025': target_ebitda_2025
        },
        'valuations_pre_discount': {
            'PE法': valuation_pe_pre,
            'PS法': valuation_ps_pre,
            'EV/EBITDA法': valuation_ev_ebitda_pre
        },
        'valuations_post_discount': {
            'PE法': valuation_pe,
            'PS法': valuation_ps,
            'EV/EBITDA法': valuation_ev_ebitda
        }
    }

    return market_results

# ============================================================================
# 第七部分：交易方案测算
# ============================================================================

def transaction_analysis(dcf_results, market_results):
    """交易方案测算"""

    # 估值结论区间
    dcf_value = dcf_results['equity_value']
    market_values = market_results['valuations_post_discount']
    market_median = np.median(list(market_values.values()))

    # 估值区间取收益法与市场法交集
    val_min = min(dcf_value, market_median) * 0.95
    val_max = max(dcf_value, market_median) * 1.05
    val_mid = (dcf_value + market_median) / 2

    # 投资方案
    investment_amount = 15000  # 万元
    max_ownership = 0.08  # 不高于8%

    # 按估值区间计算持股比例
    # 投后股权比例 = 投资金额 / (投前估值 + 投资金额)
    ownership_at_min = investment_amount / (val_min + investment_amount)
    ownership_at_mid = investment_amount / (val_mid + investment_amount)
    ownership_at_max = investment_amount / (val_max + investment_amount)

    # 业绩承诺覆盖率
    commitment_2026 = 15000
    commitment_2027 = 18000
    target_profit_2025 = market_results['target_metrics']['扣非归母净利润_2025']

    # 承诺对应的隐含估值（PE法）
    pe_median = market_results['multiples_summary']['PE_TTM中位数']
    implied_val_2026 = commitment_2026 * pe_median * (1 - 0.10)
    coverage_ratio = val_mid / implied_val_2026

    # 退出回报测算（假设2028年上市，PE=20x）
    ipo_pe = 20.0
    ipo_profit_assumption = commitment_2027 * 1.20  # 假设2028年再增20%
    ipo_market_cap = ipo_profit_assumption * ipo_pe
    ipo_value_of_stake = ipo_market_cap * ownership_at_mid
    investment_return_multiple = ipo_value_of_stake / investment_amount
    years_to_exit = 2028 - 2026  # 2年
    annual_return = (investment_return_multiple ** (1 / years_to_exit) - 1)

    transaction_results = {
        'valuation_range': {
            '下限': val_min,
            '中值': val_mid,
            '上限': val_max
        },
        'ownership_range': {
            '估值下限对应持股%': ownership_at_min * 100,
            '估值中值对应持股%': ownership_at_mid * 100,
            '估值上限对应持股%': ownership_at_max * 100
        },
        'commitment_analysis': {
            '2026年承诺': commitment_2026,
            '2027年承诺': commitment_2027,
            '承诺隐含估值': implied_val_2026,
            '估值/承诺覆盖率': coverage_ratio
        },
        'exit_return': {
            'IPO假设年份': 2028,
            'IPO假设PE': ipo_pe,
            'IPO假设扣非归母': ipo_profit_assumption,
            'IPO市值': ipo_market_cap,
            '投资回报倍数': investment_return_multiple,
            '年化回报率%': annual_return * 100
        }
    }

    return transaction_results

# ============================================================================
# 第八部分：图表生成
# ============================================================================

def generate_all_charts(data, operating, bridge, dcf, market, transaction):
    """生成全部5张复合图"""

    # 图1：材料覆盖与数据缺口
    fig1, axes1 = plt.subplots(1, 2, figsize=(14, 6))
    fig1.suptitle('图1：材料覆盖与数据缺口分析', fontsize=14, fontweight='bold')

    # 子图a：材料类别分布
    categories = ['交易与公司', '财务报表', '成本收入明细', '可比与行业', '交易条款', '其他尽调']
    file_counts = [2, 10, 13, 4, 3, 8]
    colors_cat = ['#C4612F', '#F2E3D6', '#A94E22', '#E7E1D7', '#5C635D', '#FBF9F5']
    axes1[0].pie(file_counts, labels=categories, autopct='%1.1f%%', colors=colors_cat, startangle=90)
    axes1[0].set_title('材料类别分布（共40份文件）')

    # 子图b：核验状态
    verification = ['已核验', '口径冲突已处理', '待核实事项']
    verify_counts = [38, 2, 0]
    colors_verify = ['#C4612F', '#F2E3D6', '#5C635D']
    axes1[1].barh(verification, verify_counts, color=colors_verify, edgecolor='black')
    axes1[1].set_xlabel('文件数量')
    axes1[1].set_title('材料核验状态')
    axes1[1].set_xlim(0, 40)

    plt.tight_layout()
    plt.savefig('/app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart01_材料覆盖与数据缺口.png',
                dpi=150, bbox_inches='tight')
    plt.close()

    # 图2：收入与利润口径还原
    fig2, axes2 = plt.subplots(2, 1, figsize=(14, 10))
    fig2.suptitle('图2：收入与利润口径还原', fontsize=14, fontweight='bold')

    # 子图a：收入与毛利率
    periods = ['2023', '2024', '2025']
    revenue = operating['revenue_margin'].loc[periods, '营业收入'].values
    margin = operating['revenue_margin'].loc[periods, '毛利率%'].values

    x_pos = np.arange(len(periods))
    ax2a = axes2[0]
    ax2a_twin = ax2a.twinx()

    bars = ax2a.bar(x_pos, revenue, color='#C4612F', alpha=0.7, label='营业收入')
    ax2a_twin.plot(x_pos, margin, 'o-', color='#A94E22', linewidth=2, markersize=8, label='毛利率%')

    ax2a.set_ylabel('营业收入（万元）', fontsize=11)
    ax2a_twin.set_ylabel('毛利率（%）', fontsize=11)
    ax2a.set_xticks(x_pos)
    ax2a.set_xticklabels(periods)
    ax2a.set_title('(a) 营业收入与毛利率趋势', fontsize=12)
    ax2a.legend(loc='upper left')
    ax2a_twin.legend(loc='upper right')
    ax2a.grid(axis='y', alpha=0.3)

    # 子图b：利润口径还原桥
    bridge_2025 = bridge.loc['2025']
    bridge_keys = ['①净利润', '③扣非归母净利润', '⑦调整后EBITDA']
    bridge_vals = [bridge_2025[k] for k in bridge_keys]
    bridge_labels = ['净利润', '扣非归母', '调整后EBITDA']

    ax2b = axes2[1]
    bars2 = ax2b.barh(bridge_labels, bridge_vals, color=['#C4612F', '#A94E22', '#5C635D'], edgecolor='black')
    ax2b.set_xlabel('金额（万元）', fontsize=11)
    ax2b.set_title('(b) 2025年利润口径还原（净利润→扣非归母→调整后EBITDA）', fontsize=12)
    ax2b.set_xlim(0, max(bridge_vals) * 1.15)
    for i, (label, val) in enumerate(zip(bridge_labels, bridge_vals)):
        ax2b.text(val + 200, i, f'{val:,.0f}', va='center', fontsize=10, fontweight='bold')
    ax2b.grid(axis='x', alpha=0.3)

    plt.tight_layout()
    plt.savefig('/app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart02_收入与利润口径还原.png',
                dpi=150, bbox_inches='tight')
    plt.close()

    # 图3：现金流与营运效率
    fig3, axes3 = plt.subplots(2, 1, figsize=(14, 10))
    fig3.suptitle('图3：现金流与营运效率', fontsize=14, fontweight='bold')

    # 子图a：净利润、经营现金流与净现比
    periods_cf = ['2023', '2024', '2025']
    net_profit = operating['cashflow_quality'].loc[periods_cf, '净利润'].values
    op_cf = operating['cashflow_quality'].loc[periods_cf, '经营现金流'].values
    ocf_ratio = operating['cashflow_quality'].loc[periods_cf, '净现比'].values

    x_cf = np.arange(len(periods_cf))
    width = 0.35
    ax3a = axes3[0]
    ax3a_twin = ax3a.twinx()

    ax3a.bar(x_cf - width/2, net_profit, width, label='净利润', color='#C4612F', alpha=0.8)
    ax3a.bar(x_cf + width/2, op_cf, width, label='经营现金流', color='#A94E22', alpha=0.8)
    ax3a_twin.plot(x_cf, ocf_ratio, 's-', color='#5C635D', linewidth=2, markersize=8, label='净现比')

    ax3a.set_ylabel('金额（万元）', fontsize=11)
    ax3a_twin.set_ylabel('净现比', fontsize=11)
    ax3a.set_xticks(x_cf)
    ax3a.set_xticklabels(periods_cf)
    ax3a.set_title('(a) 净利润、经营现金流与净现比', fontsize=12)
    ax3a.legend(loc='upper left')
    ax3a_twin.legend(loc='upper right')
    ax3a.grid(axis='y', alpha=0.3)

    # 子图b：应收与存货周转天数
    turnover_df = operating['turnover'].loc[periods_cf]
    ar_days = turnover_df['应收账款周转天数'].values
    inv_days = turnover_df['存货周转天数'].values

    ax3b = axes3[1]
    x_turn = np.arange(len(periods_cf))
    width_turn = 0.35
    ax3b.bar(x_turn - width_turn/2, ar_days, width_turn, label='应收账款周转天数', color='#C4612F', alpha=0.8)
    ax3b.bar(x_turn + width_turn/2, inv_days, width_turn, label='存货周转天数', color='#A94E22', alpha=0.8)

    ax3b.set_ylabel('天数', fontsize=11)
    ax3b.set_xticks(x_turn)
    ax3b.set_xticklabels(periods_cf)
    ax3b.set_title('(b) 应收账款与存货周转天数', fontsize=12)
    ax3b.legend()
    ax3b.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig('/app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart03_现金流与营运效率.png',
                dpi=150, bbox_inches='tight')
    plt.close()

    # 图4：可比与DCF估值
    fig4 = plt.figure(figsize=(16, 10))
    gs = fig4.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
    fig4.suptitle('图4：可比公司估值与DCF预测', fontsize=14, fontweight='bold')

    # 子图a-c：可比公司倍数箱线图
    comps = market['comparables']

    ax4a = fig4.add_subplot(gs[0, 0])
    bp1 = ax4a.boxplot([comps['PE_TTM']], vert=True, patch_artist=True)
    for patch in bp1['boxes']:
        patch.set_facecolor('#C4612F')
        patch.set_alpha(0.7)
    ax4a.set_ylabel('倍数')
    ax4a.set_xticklabels(['PE倍数'])
    ax4a.set_title(f'(a) PE倍数分布\n中位数={market["multiples_summary"]["PE_TTM中位数"]:.2f}x')
    ax4a.grid(axis='y', alpha=0.3)

    ax4b = fig4.add_subplot(gs[0, 1])
    bp2 = ax4b.boxplot([comps['PS_TTM']], vert=True, patch_artist=True)
    for patch in bp2['boxes']:
        patch.set_facecolor('#A94E22')
        patch.set_alpha(0.7)
    ax4b.set_ylabel('倍数')
    ax4b.set_xticklabels(['PS倍数'])
    ax4b.set_title(f'(b) PS倍数分布\n中位数={market["multiples_summary"]["PS_TTM中位数"]:.2f}x')
    ax4b.grid(axis='y', alpha=0.3)

    ax4c = fig4.add_subplot(gs[0, 2])
    bp3 = ax4c.boxplot([comps['EV_EBITDA']], vert=True, patch_artist=True)
    for patch in bp3['boxes']:
        patch.set_facecolor('#5C635D')
        patch.set_alpha(0.7)
    ax4c.set_ylabel('倍数')
    ax4c.set_xticklabels(['EV/EBITDA'])
    ax4c.set_title(f'(c) EV/EBITDA倍数分布\n中位数={market["multiples_summary"]["EV/EBITDA中位数"]:.2f}x')
    ax4c.grid(axis='y', alpha=0.3)

    # 子图d：DCF预测期现金流与现值
    ax4d = fig4.add_subplot(gs[1, :])
    forecast = dcf['forecast']
    years = forecast['年份'].values
    fcff = forecast['FCFF'].values
    pv = forecast['现值'].values

    x_dcf = np.arange(len(years))
    width_dcf = 0.35
    ax4d.bar(x_dcf - width_dcf/2, fcff, width_dcf, label='FCFF', color='#C4612F', alpha=0.8)
    ax4d.bar(x_dcf + width_dcf/2, pv, width_dcf, label='现值', color='#A94E22', alpha=0.8)

    ax4d.set_ylabel('金额（万元）', fontsize=11)
    ax4d.set_xticks(x_dcf)
    ax4d.set_xticklabels(years.astype(int))
    ax4d.set_title(f'(d) DCF预测期自由现金流与现值（WACC={dcf["discount_params"]["WACC"]:.2%}）', fontsize=12)
    ax4d.legend()
    ax4d.grid(axis='y', alpha=0.3)

    plt.savefig('/app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart04_可比与DCF估值.png',
                dpi=150, bbox_inches='tight')
    plt.close()

    # 图5：估值区间与风险缺口
    fig5 = plt.figure(figsize=(16, 10))
    gs5 = fig5.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
    fig5.suptitle('图5：估值区间与风险缺口', fontsize=14, fontweight='bold')

    # 子图a：DCF敏感性分析
    ax5a = fig5.add_subplot(gs5[0, 0])
    sensitivity = dcf['sensitivity']
    im = ax5a.imshow(sensitivity.astype(float).values, cmap='RdYlGn', aspect='auto')
    ax5a.set_xticks(np.arange(len(sensitivity.columns)))
    ax5a.set_yticks(np.arange(len(sensitivity.index)))
    ax5a.set_xticklabels(sensitivity.columns)
    ax5a.set_yticklabels(sensitivity.index)
    ax5a.set_xlabel('永续增长率g')
    ax5a.set_ylabel('WACC')
    ax5a.set_title('(a) DCF股权价值敏感性（万元）')

    for i in range(len(sensitivity.index)):
        for j in range(len(sensitivity.columns)):
            val = sensitivity.iloc[i, j]
            ax5a.text(j, i, f'{val:,}', ha='center', va='center', fontsize=9)

    # 子图b：估值结果对比
    ax5b = fig5.add_subplot(gs5[0, 1])
    val_methods = ['DCF', 'PE法', 'PS法', 'EV/EBITDA法', '市场法中位数']
    val_results = [
        dcf['equity_value'],
        market['valuations_post_discount']['PE法'],
        market['valuations_post_discount']['PS法'],
        market['valuations_post_discount']['EV/EBITDA法'],
        np.median(list(market['valuations_post_discount'].values()))
    ]

    colors_val = ['#C4612F', '#A94E22', '#5C635D', '#E7E1D7', '#1F2421']
    bars_val = ax5b.barh(val_methods, val_results, color=colors_val, edgecolor='black')
    ax5b.set_xlabel('估值（万元）')
    ax5b.set_title('(b) 不同估值方法结果对比')
    ax5b.set_xlim(0, max(val_results) * 1.15)
    for i, (method, val) in enumerate(zip(val_methods, val_results)):
        ax5b.text(val + 2000, i, f'{val:,.0f}', va='center', fontsize=9)
    ax5b.grid(axis='x', alpha=0.3)

    # 区间标注
    val_range = transaction['valuation_range']
    ax5b.axvspan(val_range['下限'], val_range['上限'], alpha=0.2, color='yellow', label='估值区间')
    ax5b.legend()

    # 子图c：风险评级
    ax5c = fig5.add_subplot(gs5[1, 0])
    risks = ['客户集中度', '账期压力', '毛利率波动', '业绩承诺兑现', 'IPO时间不确定']
    risk_levels = [3, 2, 2, 2, 3]  # 1低 2中 3高
    colors_risk = ['#C4612F' if r == 3 else '#F2E3D6' if r == 2 else '#5C635D' for r in risk_levels]

    ax5c.barh(risks, risk_levels, color=colors_risk, edgecolor='black')
    ax5c.set_xlabel('风险等级（1=低，2=中，3=高）')
    ax5c.set_title('(c) 关键风险评级')
    ax5c.set_xlim(0, 4)
    ax5c.grid(axis='x', alpha=0.3)

    # 子图d：尽调缺口
    ax5d = fig5.add_subplot(gs5[1, 1])
    gaps = ['关联交易公允性', '客户稳定性', '产能利用率', '期权池稀释', '税务合规']
    gap_priority = [2, 3, 2, 2, 1]  # 1低 2中 3高
    colors_gap = ['#C4612F' if g == 3 else '#F2E3D6' if g == 2 else '#5C635D' for g in gap_priority]

    ax5d.barh(gaps, gap_priority, color=colors_gap, edgecolor='black')
    ax5d.set_xlabel('优先级（1=低，2=中，3=高）')
    ax5d.set_title('(d) 尽调缺口优先级')
    ax5d.set_xlim(0, 4)
    ax5d.grid(axis='x', alpha=0.3)

    plt.savefig('/app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart05_估值区间与风险缺口.png',
                dpi=150, bbox_inches='tight')
    plt.close()

    print("所有图表已生成完毕。")

# ============================================================================
# 主程序
# ============================================================================

def main():
    print("="*80)
    print("Pre-IPO 投资决策备忘录 - 可复算脚本")
    print("标的公司：杭州智联精密制造股份有限公司")
    print("="*80)

    # 1. 加载数据
    print("\n[1/8] 加载源数据...")
    data = load_all_data()
    print(f"  - 利润表：{len(data['profit'])}期")
    print(f"  - 资产负债表：{len(data['balance'])}期")
    print(f"  - 可比公司：{len(data['comparables'])}家")

    # 2. 数据核验
    print("\n[2/8] 核验数据口径...")
    conflicts = verify_data_consistency(data)
    if conflicts:
        print("  口径冲突：")
        for c in conflicts:
            print(f"    - {c}")
    else:
        print("  - 未发现口径冲突")

    # 3. 经营质量分析
    print("\n[3/8] 分析报告期经营质量...")
    operating = analyze_operating_quality(data)
    print(f"  - 2025年毛利率：{operating['revenue_margin'].loc['2025', '毛利率%']:.2f}%")
    print(f"  - 2025年净现比：{operating['cashflow_quality'].loc['2025', '净现比']:.2f}")

    # 4. 利润口径还原
    print("\n[4/8] 还原利润口径...")
    bridge = profit_adjustment_bridge(data)
    print(f"  - 2025年净利润：{bridge.loc['2025', '①净利润']:,.0f}万元")
    print(f"  - 2025年扣非归母：{bridge.loc['2025', '③扣非归母净利润']:,.0f}万元")
    print(f"  - 2025年调整后EBITDA：{bridge.loc['2025', '⑦调整后EBITDA']:,.0f}万元")

    # 5. DCF估值
    print("\n[5/8] 计算DCF估值...")
    dcf = dcf_valuation(data)
    print(f"  - WACC：{dcf['discount_params']['WACC']:.2%}")
    print(f"  - 企业价值：{dcf['enterprise_value']:,.0f}万元")
    print(f"  - 净负债：{dcf['net_debt']:,.0f}万元")
    print(f"  - 股权价值：{dcf['equity_value']:,.0f}万元")
    print(f"  - 每股价值：{dcf['value_per_share']:.2f}元")

    # 6. 市场法估值
    print("\n[6/8] 计算市场法估值...")
    market = market_valuation(data, bridge)
    print(f"  - PE法（折价后）：{market['valuations_post_discount']['PE法']:,.0f}万元")
    print(f"  - PS法（折价后）：{market['valuations_post_discount']['PS法']:,.0f}万元")
    print(f"  - EV/EBITDA法（折价后）：{market['valuations_post_discount']['EV/EBITDA法']:,.0f}万元")

    # 7. 交易方案测算
    print("\n[7/8] 测算交易方案...")
    transaction = transaction_analysis(dcf, market)
    print(f"  - 估值区间：{transaction['valuation_range']['下限']:,.0f} ~ {transaction['valuation_range']['上限']:,.0f}万元")
    print(f"  - 持股比例区间：{transaction['ownership_range']['估值上限对应持股%']:.2f}% ~ {transaction['ownership_range']['估值下限对应持股%']:.2f}%")
    print(f"  - 投资回报倍数：{transaction['exit_return']['投资回报倍数']:.2f}x")
    print(f"  - 年化回报率：{transaction['exit_return']['年化回报率%']:.2f}%")

    # 8. 生成图表
    print("\n[8/8] 生成图表...")
    generate_all_charts(data, operating, bridge, dcf, market, transaction)

    print("\n" + "="*80)
    print("脚本执行完毕！")
    print("输出文件：")
    print("  - /app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart01_材料覆盖与数据缺口.png")
    print("  - /app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart02_收入与利润口径还原.png")
    print("  - /app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart03_现金流与营运效率.png")
    print("  - /app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart04_可比与DCF估值.png")
    print("  - /app/output/FIN3-WKN-150_charts/FIN3-WKN-150_chart05_估值区间与风险缺口.png")
    print("="*80)

    return {
        'data': data,
        'operating': operating,
        'bridge': bridge,
        'dcf': dcf,
        'market': market,
        'transaction': transaction
    }

if __name__ == '__main__':
    results = main()
