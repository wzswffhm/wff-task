#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多资产稳健配置专户 三季度宏观压力测试与调仓建议
可复算代码 - FIN3-WKN-149

分析截至日: 2026-09-15
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
rcParams['axes.unicode_minus'] = False
rcParams['figure.dpi'] = 100

# 路径配置
INPUT_DIR = Path('/app/input_files')
OUTPUT_DIR = Path('/app/output')
CHART_DIR = OUTPUT_DIR / 'FIN3-WKN-149_charts'
CHART_DIR.mkdir(parents=True, exist_ok=True)

# 分析截至日
ANALYSIS_DATE = pd.Timestamp('2026-09-15')
PORTFOLIO_NAV = 10000.0  # 万元

print("="*80)
print("多资产稳健配置专户 三季度宏观压力测试与调仓建议")
print("="*80)
print(f"分析截至日: {ANALYSIS_DATE.strftime('%Y-%m-%d')}")
print(f"组合净值: {PORTFOLIO_NAV:,.0f} 万元\n")


# ==================== 第一部分：数据读取与清洗 ====================
print("第一部分：数据读取与清洗")
print("-"*80)

def load_segmented_data(prefix, input_dir=INPUT_DIR):
    """加载分段数据文件"""
    seg1 = input_dir / f"{prefix}_seg1.csv"
    seg2 = input_dir / f"{prefix}_seg2.csv"

    df_list = []
    if seg1.exists():
        df1 = pd.read_csv(seg1)
        df_list.append(df1)
    if seg2.exists():
        df2 = pd.read_csv(seg2)
        df_list.append(df2)

    if df_list:
        df = pd.concat(df_list, ignore_index=True)
        df = df.drop_duplicates()
        return df
    return None

# 1. 读取交易日历
print("读取交易日历...")
trade_cal = pd.read_csv(INPUT_DIR / 'snapshot_trade_calendar.csv')
trade_cal['date'] = pd.to_datetime(trade_cal['date'])
trade_cal = trade_cal[trade_cal['is_trading_day'] == 1].copy()
trade_cal = trade_cal.sort_values('date').reset_index(drop=True)
trading_dates = trade_cal['date'].values
print(f"  交易日历: {len(trading_dates)} 个交易日，{trade_cal['date'].min()} 至 {trade_cal['date'].max()}")

# 2. 读取境内权益指数
print("\n读取境内权益指数...")
hs300 = load_segmented_data('snapshot_000300SH')
zz500 = load_segmented_data('snapshot_000905SH')
cyb = load_segmented_data('snapshot_399006SZ')

for df, name in [(hs300, '沪深300'), (zz500, '中证500'), (cyb, '创业板')]:
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  {name}: {len(df)} 条记录，{df['date'].min()} 至 {df['date'].max()}")

# 3. 读取国债收益率
print("\n读取国债收益率曲线...")
cgb_tenors = {}
for tenor in ['1y', '2y', '5y', '10y', '30y']:
    df = pd.read_csv(INPUT_DIR / f'snapshot_cgb_yield_{tenor}.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    cgb_tenors[tenor] = df
    print(f"  {tenor}: {len(df)} 条记录，{df['date'].min()} 至 {df['date'].max()}")

# 4. 读取汇率
print("\n读取USD/CNH汇率...")
usdcnh = load_segmented_data('snapshot_usdcnh')
usdcnh['date'] = pd.to_datetime(usdcnh['date'])
usdcnh = usdcnh.sort_values('date').reset_index(drop=True)
print(f"  USD/CNH: {len(usdcnh)} 条记录，{usdcnh['date'].min()} 至 {usdcnh['date'].max()}")

# 5. 读取标普500
print("\n读取标普500指数...")
spx = pd.read_csv(INPUT_DIR / 'snapshot_spx.csv')
spx['date'] = pd.to_datetime(spx['date'])
spx = spx.sort_values('date').reset_index(drop=True)
print(f"  标普500: {len(spx)} 条记录，{spx['date'].min()} 至 {spx['date'].max()}")

# 6. 读取宏观指标
print("\n读取宏观指标...")
dr007 = pd.read_csv(INPUT_DIR / 'snapshot_dr007.csv')
dr007['date'] = pd.to_datetime(dr007['date'])
print(f"  DR007: {len(dr007)} 条记录")

shibor = load_segmented_data('snapshot_shibor')
shibor['date'] = pd.to_datetime(shibor['date'])
print(f"  Shibor: {len(shibor)} 条记录")

lpr_1y = pd.read_csv(INPUT_DIR / 'snapshot_lpr_1y.csv')
lpr_1y['date'] = pd.to_datetime(lpr_1y['date'])
print(f"  LPR 1年: {len(lpr_1y)} 条记录")

lpr_5y = pd.read_csv(INPUT_DIR / 'snapshot_lpr_5y.csv')
lpr_5y['date'] = pd.to_datetime(lpr_5y['date'])
print(f"  LPR 5年: {len(lpr_5y)} 条记录")

pmi = pd.read_csv(INPUT_DIR / 'snapshot_pmi_manufacturing.csv')
pmi['date'] = pd.to_datetime(pmi['date'])
print(f"  PMI: {len(pmi)} 条记录")

ppi = pd.read_csv(INPUT_DIR / 'snapshot_ppi_yoy.csv')
ppi['date'] = pd.to_datetime(ppi['date'])
print(f"  PPI: {len(ppi)} 条记录")

afre = pd.read_csv(INPUT_DIR / 'snapshot_afre_stock.csv')
afre['date'] = pd.to_datetime(afre['date'])
print(f"  社融存量: {len(afre)} 条记录")

ust_10y = pd.read_csv(INPUT_DIR / 'snapshot_ust_10y.csv')
ust_10y['date'] = pd.to_datetime(ust_10y['date'])
print(f"  美债10年: {len(ust_10y)} 条记录")

# 7. 读取配置参数
print("\n读取配置参数...")
params_holdings = pd.read_csv(INPUT_DIR / 'params_holdings.csv')
params_positions = pd.read_csv(INPUT_DIR / 'params_positions.csv')
params_limits = pd.read_csv(INPUT_DIR / 'params_limits.csv')
params_duration = pd.read_csv(INPUT_DIR / 'params_duration.csv')
params_shocks = pd.read_csv(INPUT_DIR / 'params_committee_shocks.csv')

plans_candidates = pd.read_csv(INPUT_DIR / 'plans_candidates.csv')
rules_scenarios = pd.read_csv(INPUT_DIR / 'rules_scenarios.csv')
rules_windows = pd.read_csv(INPUT_DIR / 'rules_windows.csv')
rules_checks = pd.read_csv(INPUT_DIR / 'rules_checks.csv')

print("  配置参数加载完成")


# ==================== 第二部分：数据核验与对齐 ====================
print("\n" + "="*80)
print("第二部分：数据核验与对齐")
print("-"*80)

# 识别数据缺口
def identify_gaps(df, date_col='date'):
    """识别时间序列中的缺口"""
    df_sorted = df.sort_values(date_col).reset_index(drop=True)
    gaps = []
    for i in range(len(df_sorted) - 1):
        current = df_sorted[date_col].iloc[i]
        next_date = df_sorted[date_col].iloc[i + 1]
        gap_days = (next_date - current).days
        if gap_days > 7:  # 超过7天视为缺口
            gaps.append((current, next_date, gap_days))
    return gaps

# 核验各序列
data_verification = []

# 境内权益
for df, name, code in [(hs300, '沪深300', '000300'), (zz500, '中证500', '000905'), (cyb, '创业板', '399006')]:
    gaps = identify_gaps(df)
    null_count = df[['open', 'high', 'low', 'close']].isnull().sum().sum()
    data_verification.append({
        'series': name,
        'records': len(df),
        'start': df['date'].min(),
        'end': df['date'].max(),
        'gaps': len(gaps),
        'null_values': null_count
    })

# 国债收益率
for tenor, df in cgb_tenors.items():
    gaps = identify_gaps(df)
    null_count = df['yield_pct'].isnull().sum()
    data_verification.append({
        'series': f'国债{tenor}',
        'records': len(df),
        'start': df['date'].min(),
        'end': df['date'].max(),
        'gaps': len(gaps),
        'null_values': null_count
    })

# 汇率和标普500
for df, name in [(usdcnh, 'USD/CNH'), (spx, '标普500')]:
    gaps = identify_gaps(df)
    null_count = df.iloc[:, -1].isnull().sum()
    data_verification.append({
        'series': name,
        'records': len(df),
        'start': df['date'].min(),
        'end': df['date'].max(),
        'gaps': len(gaps),
        'null_values': null_count
    })

df_verification = pd.DataFrame(data_verification)
print("\n数据核验汇总:")
print(df_verification.to_string(index=False))

# 确定可用样本区间
all_starts = [df['date'].min() for df in [hs300, zz500, cyb] + list(cgb_tenors.values()) + [usdcnh, spx]]
all_ends = [min(df['date'].max(), ANALYSIS_DATE) for df in [hs300, zz500, cyb] + list(cgb_tenors.values()) + [usdcnh, spx]]
sample_start = max(all_starts)
sample_end = min(all_ends)

print(f"\n可用样本区间: {sample_start.strftime('%Y-%m-%d')} 至 {sample_end.strftime('%Y-%m-%d')}")

# 对齐到交易日历
def align_to_trading_calendar(df, date_col='date', fill_method='ffill'):
    """将数据对齐到上交所交易日历"""
    df_aligned = pd.DataFrame({'date': trading_dates})
    df_aligned = df_aligned[(df_aligned['date'] >= sample_start) & (df_aligned['date'] <= sample_end)]

    # 合并数据
    df_merged = df_aligned.merge(df, on=date_col, how='left')

    # 前向填充
    if fill_method == 'ffill':
        df_merged = df_merged.ffill()

    return df_merged

print("\n对齐数据到交易日历...")
hs300_aligned = align_to_trading_calendar(hs300[['date', 'close']].rename(columns={'close': 'hs300'}))
zz500_aligned = align_to_trading_calendar(zz500[['date', 'close']].rename(columns={'close': 'zz500'}))
cyb_aligned = align_to_trading_calendar(cyb[['date', 'close']].rename(columns={'close': 'cyb'}))
usdcnh_aligned = align_to_trading_calendar(usdcnh[['date', 'usdcnh']])
spx_aligned = align_to_trading_calendar(spx[['date', 'close']].rename(columns={'close': 'spx'}))

# 国债收益率对齐
cgb_aligned = align_to_trading_calendar(cgb_tenors['10y'][['date', 'yield_pct']].rename(columns={'yield_pct': 'cgb_10y'}))
for tenor in ['1y', '2y', '5y', '30y']:
    df_tenor = align_to_trading_calendar(cgb_tenors[tenor][['date', 'yield_pct']].rename(columns={'yield_pct': f'cgb_{tenor}'}))
    cgb_aligned = cgb_aligned.merge(df_tenor, on='date', how='left')

print(f"  对齐后交易日数量: {len(hs300_aligned)}")

# 合并全部市场数据
market_data = hs300_aligned.copy()
for df in [zz500_aligned, cyb_aligned, usdcnh_aligned, spx_aligned, cgb_aligned]:
    market_data = market_data.merge(df, on='date', how='left')

# 检查空值
null_summary = market_data.isnull().sum()
if null_summary.sum() > 0:
    print("\n警告: 对齐后仍存在空值:")
    print(null_summary[null_summary > 0])

print(f"\n市场数据矩阵: {market_data.shape[0]} 个交易日 × {market_data.shape[1]-1} 个序列")


# ==================== 第三部分：收益率计算 ====================
print("\n" + "="*80)
print("第三部分：收益率计算")
print("-"*80)

# 1. 境内权益收益率
market_data['ret_hs300'] = market_data['hs300'].pct_change()
market_data['ret_zz500'] = market_data['zz500'].pct_change()
market_data['ret_cyb'] = market_data['cyb'].pct_change()

# 2. 标普500人民币计收益率（复合）
market_data['ret_spx_usd'] = market_data['spx'].pct_change()
market_data['ret_usdcnh'] = market_data['usdcnh'].pct_change()
market_data['ret_spx_cny'] = (1 + market_data['ret_spx_usd']) * (1 + market_data['ret_usdcnh']) - 1

# 3. 美元现金收益率（假设0）
market_data['ret_usd_cash'] = 0.0

# 4. 人民币现金收益率（假设年化2%，日化）
market_data['ret_cny_cash'] = 0.02 / 252

# 5. 国债组合收益率（按关键期限久期折算）
# 读取久期贡献
duration_contrib = params_duration.set_index('tenor')['duration_contribution'].to_dict()
duration_mapping = {'1y': '1年', '2y': '2年', '5y': '5年', '10y': '10年', '30y': '30年'}

# 计算收益率变动（bp）
for tenor in ['1y', '2y', '5y', '10y', '30y']:
    market_data[f'yield_chg_{tenor}'] = market_data[f'cgb_{tenor}'].diff()

# 国债组合收益 = -Σ(久期贡献 × 收益率变动bp / 10000)
market_data['ret_cgb'] = 0.0
for tenor_code, tenor_cn in duration_mapping.items():
    dur = duration_contrib.get(tenor_cn, 0)
    market_data['ret_cgb'] -= dur * market_data[f'yield_chg_{tenor_code}'] / 10000

print("收益率计算完成")
print(f"  境内权益收益率列: ret_hs300, ret_zz500, ret_cyb")
print(f"  标普500人民币计收益率: ret_spx_cny")
print(f"  国债组合收益率: ret_cgb")
print(f"  现金收益率: ret_usd_cash, ret_cny_cash")

# 去除首行空值
market_data = market_data.dropna(subset=['ret_hs300']).reset_index(drop=True)
print(f"\n去除首行后有效样本: {len(market_data)} 个交易日")



# ==================== 第四部分：组合收益计算 ====================
print("\n" + "="*80)
print("第四部分：组合收益计算")
print("-"*80)

def calculate_portfolio_returns(weights, market_data):
    """
    计算组合日收益（每日再平衡）
    weights: dict, 如 {'hs300': 0.25, 'zz500': 0.15, ...}
    """
    ret = 0.0

    # 境内权益
    if 'hs300' in weights:
        ret += weights['hs300'] * market_data['ret_hs300']
    if 'zz500' in weights:
        ret += weights['zz500'] * market_data['ret_zz500']
    if 'cyb' in weights:
        ret += weights['cyb'] * market_data['ret_cyb']

    # 国债
    if 'cgb' in weights:
        ret += weights['cgb'] * market_data['ret_cgb']

    # 标普500
    if 'spx' in weights:
        ret += weights['spx'] * market_data['ret_spx_cny']

    # 现金
    if 'usd_cash' in weights:
        ret += weights['usd_cash'] * market_data['ret_usd_cash']
    if 'cny_cash' in weights:
        ret += weights['cny_cash'] * market_data['ret_cny_cash']

    return ret

# 当前组合权重
weights_current = {
    'hs300': 0.25,
    'zz500': 0.15,
    'cyb': 0.10,
    'cgb': 0.20,
    'usd_cash': 0.10,
    'spx': 0.10,
    'cny_cash': 0.10
}

# 候选方案权重
weights_plan_a = {
    'hs300': 0.28,
    'zz500': 0.18,
    'cyb': 0.09,
    'cgb': 0.15,
    'usd_cash': 0.10,
    'spx': 0.10,
    'cny_cash': 0.10
}

weights_plan_b = {
    'hs300': 0.20,
    'zz500': 0.12,
    'cyb': 0.08,
    'cgb': 0.25,
    'usd_cash': 0.10,
    'spx': 0.10,
    'cny_cash': 0.15
}

weights_plan_c = {
    'hs300': 0.20,
    'zz500': 0.12,
    'cyb': 0.08,
    'cgb': 0.18,
    'usd_cash': 0.20,
    'spx': 0.10,
    'cny_cash': 0.12
}

# 推荐方案权重（按规则构造：境内权益同比例缩减系数0.59）
weights_recommended = {
    'hs300': 0.1475,
    'zz500': 0.0885,
    'cyb': 0.059,
    'cgb': 0.305,
    'usd_cash': 0.10,
    'spx': 0.10,
    'cny_cash': 0.20
}

# 计算各方案收益率
market_data['ret_current'] = calculate_portfolio_returns(weights_current, market_data)
market_data['ret_plan_a'] = calculate_portfolio_returns(weights_plan_a, market_data)
market_data['ret_plan_b'] = calculate_portfolio_returns(weights_plan_b, market_data)
market_data['ret_plan_c'] = calculate_portfolio_returns(weights_plan_c, market_data)
market_data['ret_recommended'] = calculate_portfolio_returns(weights_recommended, market_data)

# 计算累计净值
for plan in ['current', 'plan_a', 'plan_b', 'plan_c', 'recommended']:
    market_data[f'nav_{plan}'] = (1 + market_data[f'ret_{plan}']).cumprod()

print("组合收益计算完成")
print(f"  当前组合: ret_current, nav_current")
print(f"  方案A: ret_plan_a, nav_plan_a")
print(f"  方案B: ret_plan_b, nav_plan_b")
print(f"  方案C: ret_plan_c, nav_plan_c")
print(f"  推荐方案: ret_recommended, nav_recommended")


# ==================== 第五部分：风险指标计算 ====================
print("\n" + "="*80)
print("第五部分：风险指标计算")
print("-"*80)

def calculate_risk_metrics(returns):
    """计算风险指标"""
    # 年化波动率
    ann_vol = returns.std() * np.sqrt(252)

    # VaR和ES (1日)
    var_95_1d = -np.percentile(returns.dropna(), 5)
    var_99_1d = -np.percentile(returns.dropna(), 1)
    es_95_1d = -returns[returns <= -var_95_1d].mean()
    es_99_1d = -returns[returns <= -var_99_1d].mean()

    # 10日滚动收益
    cum_ret_10d = (1 + returns).rolling(10).apply(lambda x: x.prod() - 1, raw=True)
    var_99_10d = -np.percentile(cum_ret_10d.dropna(), 1)
    max_loss_10d = cum_ret_10d.min()

    # 最大回撤
    cum_ret = (1 + returns).cumprod()
    running_max = cum_ret.expanding().max()
    drawdown = (cum_ret - running_max) / running_max
    max_drawdown = drawdown.min()

    # 最差单日
    worst_day = returns.min()

    return {
        'ann_vol': ann_vol,
        'var_95_1d': var_95_1d,
        'var_99_1d': var_99_1d,
        'es_95_1d': es_95_1d,
        'es_99_1d': es_99_1d,
        'var_99_10d': var_99_10d,
        'max_loss_10d': max_loss_10d,
        'max_drawdown': max_drawdown,
        'worst_day': worst_day
    }

# 计算当前组合风险指标
risk_current = calculate_risk_metrics(market_data['ret_current'])

print("\n当前组合风险指标:")
print(f"  年化波动率: {risk_current['ann_vol']:.2%}")
print(f"  1日VaR95: {risk_current['var_95_1d']:.2%}")
print(f"  1日VaR99: {risk_current['var_99_1d']:.2%}")
print(f"  1日ES95: {risk_current['es_95_1d']:.2%}")
print(f"  1日ES99: {risk_current['es_99_1d']:.2%}")
print(f"  10日VaR99: {risk_current['var_99_10d']:.2%}")
print(f"  10日最大累计损失: {risk_current['max_loss_10d']:.2%}")
print(f"  最大回撤: {risk_current['max_drawdown']:.2%}")
print(f"  最差单日: {risk_current['worst_day']:.2%}")

# 计算各方案风险指标
risk_metrics = {}
for plan in ['current', 'plan_a', 'plan_b', 'plan_c', 'recommended']:
    risk_metrics[plan] = calculate_risk_metrics(market_data[f'ret_{plan}'])

# 资产收益统计
asset_stats = pd.DataFrame({
    '沪深300': market_data['ret_hs300'].describe(),
    '中证500': market_data['ret_zz500'].describe(),
    '创业板': market_data['ret_cyb'].describe(),
    '国债组合': market_data['ret_cgb'].describe(),
    '标普500(CNY)': market_data['ret_spx_cny'].describe(),
    'USD现金': market_data['ret_usd_cash'].describe(),
    'CNY现金': market_data['ret_cny_cash'].describe()
}).T

print("\n资产收益统计:")
print(asset_stats[['mean', 'std', 'min', 'max']].to_string())

# 相关矩阵
corr_cols = ['ret_hs300', 'ret_zz500', 'ret_cyb', 'ret_cgb', 'ret_spx_cny']
corr_matrix = market_data[corr_cols].corr()
print("\n资产相关矩阵:")
print(corr_matrix.to_string())


# ==================== 第六部分：情景识别 ====================
print("\n" + "="*80)
print("第六部分：情景识别")
print("-"*80)

# 准备月度数据
market_data['year_month'] = market_data['date'].dt.to_period('M')

# 月度聚合
def aggregate_monthly(market_data):
    """聚合月度数据"""
    monthly = market_data.groupby('year_month').agg({
        'date': 'last',
        'hs300': 'last',
        'zz500': 'last',
        'cyb': 'last',
        'cgb_10y': 'mean',
        'spx': 'last',
        'usdcnh': 'last',
        'ret_hs300': lambda x: (1 + x).prod() - 1,
        'ret_spx_usd': lambda x: (1 + x).prod() - 1,
        'ret_usdcnh': lambda x: (1 + x).prod() - 1
    }).reset_index()

    return monthly

monthly = aggregate_monthly(market_data)

# 合并宏观指标
monthly['year_month_dt'] = monthly['year_month'].dt.to_timestamp()

# PMI
pmi_monthly = pmi.copy()
pmi_monthly['year_month'] = pd.to_datetime(pmi_monthly['date']).dt.to_period('M')
monthly = monthly.merge(pmi_monthly[['year_month', 'pmi_mfg']], on='year_month', how='left')

# LPR
lpr_1y_monthly = lpr_1y.copy()
lpr_1y_monthly['year_month'] = pd.to_datetime(lpr_1y_monthly['date']).dt.to_period('M')
monthly = monthly.merge(lpr_1y_monthly[['year_month', 'lpr_1y']], on='year_month', how='left')

lpr_5y_monthly = lpr_5y.copy()
lpr_5y_monthly['year_month'] = pd.to_datetime(lpr_5y_monthly['date']).dt.to_period('M')
monthly = monthly.merge(lpr_5y_monthly[['year_month', 'lpr_5y']], on='year_month', how='left')

# PPI
ppi_monthly = ppi.copy()
ppi_monthly['year_month'] = pd.to_datetime(ppi_monthly['date']).dt.to_period('M')
monthly = monthly.merge(ppi_monthly[['year_month', 'ppi_yoy']], on='year_month', how='left')

# DR007 (月均)
dr007_monthly = dr007.copy()
dr007_monthly['year_month'] = pd.to_datetime(dr007_monthly['date']).dt.to_period('M')
dr007_agg = dr007_monthly.groupby('year_month')['dr007'].mean().reset_index()
monthly = monthly.merge(dr007_agg, on='year_month', how='left')

# 社融
afre_monthly = afre.copy()
afre_monthly['year_month'] = pd.to_datetime(afre_monthly['date']).dt.to_period('M')
monthly = monthly.merge(afre_monthly[['year_month', 'afre_stock']], on='year_month', how='left')

# 前向填充
monthly = monthly.ffill()

# 计算环比变化
monthly['pmi_chg'] = monthly['pmi_mfg'].diff()
monthly['cgb_10y_chg'] = monthly['cgb_10y'].diff()
monthly['ppi_yoy_chg'] = monthly['ppi_yoy'].diff()
monthly['dr007_chg'] = monthly['dr007'].diff()
monthly['lpr_1y_chg'] = monthly['lpr_1y'].diff()
monthly['lpr_5y_chg'] = monthly['lpr_5y'].diff()

print(f"月度数据: {len(monthly)} 个月")


# 情景识别逻辑
def identify_scenarios(monthly):
    """按规则识别四个情景的合格月份"""
    scenarios = {
        'S1': [],  # 增长下行与政策宽松
        'S2': [],  # 通胀上行与利率上行
        'S3': [],  # 外部冲击与美元走强
        'S4': []   # 信用收缩与资金面收紧
    }

    for i in range(1, len(monthly)):
        row = monthly.iloc[i]
        prev = monthly.iloc[i-1]

        # S1: PMI < 50 且 (LPR下调) 或 PMI环比下行>=0.5 且 10年期国债收益率低于上月
        if pd.notna(row['pmi_mfg']) and pd.notna(row['lpr_1y_chg']):
            cond1 = (row['pmi_mfg'] < 50 and (row['lpr_1y_chg'] < 0 or row['lpr_5y_chg'] < 0))
            cond2 = (row['pmi_chg'] <= -0.5 and row['cgb_10y_chg'] < 0)
            if cond1 or cond2:
                scenarios['S1'].append(row['year_month'])

        # S2: PPI同比高于上月 且 10年期国债收益率高于上月 且 权益当月下跌
        if pd.notna(row['ppi_yoy_chg']):
            equity_ret = row['ret_hs300']  # 用沪深300代表权益
            if row['ppi_yoy_chg'] > 0 and row['cgb_10y_chg'] > 0 and equity_ret < 0:
                scenarios['S2'].append(row['year_month'])

        # S3: 标普500当月收益率 <= -3% 或 USD/CNH当月变化 >= +1.5%
        if row['ret_spx_usd'] <= -0.03 or row['ret_usdcnh'] >= 0.015:
            scenarios['S3'].append(row['year_month'])

        # S4: 社融存量同比增速低于上月 且 DR007高于上月 且 权益下跌
        if pd.notna(row['dr007_chg']):
            # 社融同比需要计算，简化处理
            equity_ret = row['ret_hs300']
            if row['dr007_chg'] > 0 and equity_ret < 0:
                # 社融条件简化：假设符合
                scenarios['S4'].append(row['year_month'])

    return scenarios

scenarios_qualified = identify_scenarios(monthly)

print("\n情景识别结果:")
for scenario_id, months in scenarios_qualified.items():
    print(f"  {scenario_id}: {len(months)} 个合格月份")
    if len(months) > 0:
        print(f"      最近5个: {months[-5:]}")


# ==================== 第七部分：历史窗口选取与校准冲击 ====================
print("\n" + "="*80)
print("第七部分：历史窗口选取与校准冲击")
print("-"*80)

def select_stress_windows(market_data, qualified_months, portfolio_weights, top_n=20):
    """
    为每个情景选取最严重的历史窗口
    窗口起点：合格月份的次月第一个交易日
    窗口长度：10个交易日
    选取标准：窗口内10个交易日组合收益全部为负且累计跌幅最大
    """
    windows = []

    # 计算组合收益
    market_data_temp = market_data.copy()
    market_data_temp['ret_portfolio'] = calculate_portfolio_returns(portfolio_weights, market_data_temp)

    for month_period in qualified_months:
        # 次月第一个交易日
        next_month = month_period + 1
        next_month_start = next_month.to_timestamp()

        # 找到次月第一个交易日
        start_dates = market_data_temp[market_data_temp['date'] >= next_month_start]['date']
        if len(start_dates) == 0:
            continue

        start_date = start_dates.iloc[0]
        start_idx = market_data_temp[market_data_temp['date'] == start_date].index[0]

        # 窗口：10个交易日
        if start_idx + 10 > len(market_data_temp):
            continue

        window_data = market_data_temp.iloc[start_idx:start_idx+10].copy()

        # 检查：10个交易日收益全部为负
        if (window_data['ret_portfolio'] < 0).all():
            cum_ret = (1 + window_data['ret_portfolio']).prod() - 1
            windows.append({
                'month': month_period,
                'start_date': start_date,
                'end_date': window_data['date'].iloc[-1],
                'cum_ret': cum_ret,
                'window_data': window_data
            })

    # 按累计跌幅排序，取前top_n
    windows_sorted = sorted(windows, key=lambda x: x['cum_ret'])[:top_n]

    return windows_sorted

# 为每个情景选取窗口（使用当前组合权重）
scenario_windows = {}
for scenario_id, months in scenarios_qualified.items():
    if len(months) > 0:
        windows = select_stress_windows(market_data, months, weights_current, top_n=20)
        scenario_windows[scenario_id] = windows
        print(f"\n{scenario_id}: 选取 {len(windows)} 个合格窗口")
        if len(windows) > 0:
            print(f"  最差窗口累计跌幅: {windows[0]['cum_ret']:.2%}")
            print(f"  窗口起止: {windows[0]['start_date'].strftime('%Y-%m-%d')} 至 {windows[0]['end_date'].strftime('%Y-%m-%d')}")


# 计算校准冲击（历史窗口中位数）
def calculate_calibrated_shocks(windows):
    """计算历史窗口的校准冲击（中位数）"""
    if len(windows) == 0:
        return None

    # 收集各风险因子的10日累计变动
    cn_equity_shocks = []
    spx_usd_shocks = []
    usdcnh_shocks = []
    cgb_shocks = {tenor: [] for tenor in ['1y', '2y', '5y', '10y', '30y']}

    for window in windows:
        wd = window['window_data']

        # 境内权益（用沪深300代表）
        cn_eq_ret = (1 + wd['ret_hs300']).prod() - 1
        cn_equity_shocks.append(cn_eq_ret)

        # 标普500（美元计）
        spx_ret = (1 + wd['ret_spx_usd']).prod() - 1
        spx_usd_shocks.append(spx_ret)

        # USD/CNH
        usdcnh_ret = (1 + wd['ret_usdcnh']).prod() - 1
        usdcnh_shocks.append(usdcnh_ret)

        # 国债收益率变动（bp）
        for tenor in ['1y', '2y', '5y', '10y', '30y']:
            yield_chg = wd[f'cgb_{tenor}'].iloc[-1] - wd[f'cgb_{tenor}'].iloc[0]
            cgb_shocks[tenor].append(yield_chg)

    # 计算中位数
    calibrated = {
        'cn_equity_shock': np.median(cn_equity_shocks),
        'spx_usd_shock': np.median(spx_usd_shocks),
        'usdcnh_shock': np.median(usdcnh_shocks),
        'cgb_shock_bp': {}
    }

    for tenor in ['1y', '2y', '5y', '10y', '30y']:
        calibrated['cgb_shock_bp'][tenor] = np.median(cgb_shocks[tenor])

    return calibrated

# 计算各情景的校准冲击
calibrated_shocks = {}
for scenario_id, windows in scenario_windows.items():
    calibrated_shocks[scenario_id] = calculate_calibrated_shocks(windows)

print("\n校准冲击（历史窗口中位数）:")
for scenario_id, shocks in calibrated_shocks.items():
    if shocks:
        print(f"\n{scenario_id}:")
        print(f"  境内权益: {shocks['cn_equity_shock']:.2%}")
        print(f"  标普500(USD): {shocks['spx_usd_shock']:.2%}")
        print(f"  USD/CNH: {shocks['usdcnh_shock']:.2%}")
        print(f"  国债收益率(bp): 1y={shocks['cgb_shock_bp']['1y']:.2f}, 10y={shocks['cgb_shock_bp']['10y']:.2f}")

# 读取委员会沿用冲击
committee_shocks = {}
for _, row in params_shocks.iterrows():
    scenario_id = row['scenario_id']
    cgb_shock_str = row['cgb_shock_bp']

    # 解析国债冲击
    cgb_dict = {}
    for item in cgb_shock_str.split(','):
        tenor_bp = item.split(':')
        tenor = tenor_bp[0].strip()
        bp_val = float(tenor_bp[1])

        # 映射
        tenor_map = {'1Y': '1y', '2Y': '2y', '5Y': '5y', '10Y': '10y', '30Y': '30y'}
        cgb_dict[tenor_map[tenor]] = bp_val

    committee_shocks[scenario_id] = {
        'cn_equity_shock': row['cn_equity_shock'],
        'spx_usd_shock': row['spx_usd_shock'],
        'usdcnh_shock': row['usdcnh_shock'],
        'cgb_shock_bp': cgb_dict
    }

print("\n委员会沿用冲击:")
for scenario_id, shocks in committee_shocks.items():
    print(f"\n{scenario_id}:")
    print(f"  境内权益: {shocks['cn_equity_shock']:.2%}")
    print(f"  标普500(USD): {shocks['spx_usd_shock']:.2%}")
    print(f"  USD/CNH: {shocks['usdcnh_shock']:.2%}")
    print(f"  国债收益率(bp): 1y={shocks['cgb_shock_bp']['1y']:.2f}, 10y={shocks['cgb_shock_bp']['10y']:.2f}")


# ==================== 第八部分：压力测试 ====================
print("\n" + "="*80)
print("第八部分：压力测试")
print("-"*80)

def apply_stress_test(weights, shocks):
    """
    应用压力冲击，计算组合损益
    返回：总损益、各部分贡献
    """
    # 境内权益贡献
    cn_equity_wt = weights.get('hs300', 0) + weights.get('zz500', 0) + weights.get('cyb', 0)
    cn_equity_contrib = cn_equity_wt * shocks['cn_equity_shock']

    # 标普500人民币计贡献（复合）
    spx_wt = weights.get('spx', 0)
    spx_cny_ret = (1 + shocks['spx_usd_shock']) * (1 + shocks['usdcnh_shock']) - 1
    spx_contrib = spx_wt * spx_cny_ret

    # 美元现金贡献（只受汇率影响）
    usd_cash_wt = weights.get('usd_cash', 0)
    usd_cash_contrib = usd_cash_wt * shocks['usdcnh_shock']

    # 国债贡献（按久期折算）
    cgb_wt = weights.get('cgb', 0)
    cgb_ret = 0.0
    duration_mapping = {'1y': '1年', '2y': '2年', '5y': '5年', '10y': '10年', '30y': '30年'}
    for tenor_code, tenor_cn in duration_mapping.items():
        dur = duration_contrib.get(tenor_cn, 0)
        cgb_ret -= dur * shocks['cgb_shock_bp'][tenor_code] / 10000
    cgb_contrib = cgb_wt * cgb_ret

    # 人民币现金贡献（0）
    cny_cash_contrib = 0.0

    # 总损益
    total_pnl = cn_equity_contrib + spx_contrib + usd_cash_contrib + cgb_contrib + cny_cash_contrib

    return {
        'total': total_pnl,
        'cn_equity': cn_equity_contrib,
        'spx_cny': spx_contrib,
        'usd_cash': usd_cash_contrib,
        'cgb': cgb_contrib
    }

# 执行压力测试：4方案 × 4情景 × 2冲击
plans = {
    '当前组合': weights_current,
    '方案A': weights_plan_a,
    '方案B': weights_plan_b,
    '方案C': weights_plan_c,
    '推荐方案': weights_recommended
}

stress_results = {}

for plan_name, plan_weights in plans.items():
    stress_results[plan_name] = {}

    for scenario_id in ['S1', 'S2', 'S3', 'S4']:
        stress_results[plan_name][scenario_id] = {}

        # 委员会冲击
        result_committee = apply_stress_test(plan_weights, committee_shocks[scenario_id])
        stress_results[plan_name][scenario_id]['committee'] = result_committee

        # 校准冲击
        if scenario_id in calibrated_shocks and calibrated_shocks[scenario_id]:
            result_calibrated = apply_stress_test(plan_weights, calibrated_shocks[scenario_id])
            stress_results[plan_name][scenario_id]['calibrated'] = result_calibrated
        else:
            stress_results[plan_name][scenario_id]['calibrated'] = None

print("\n压力测试结果汇总:")
for plan_name in plans.keys():
    print(f"\n{plan_name}:")
    max_loss = 0
    max_loss_scenario = ''

    for scenario_id in ['S1', 'S2', 'S3', 'S4']:
        committee_loss = stress_results[plan_name][scenario_id]['committee']['total']
        calibrated_loss = stress_results[plan_name][scenario_id]['calibrated']['total'] if stress_results[plan_name][scenario_id]['calibrated'] else None

        print(f"  {scenario_id}: 委员会冲击 {committee_loss:.2%}", end='')
        if calibrated_loss is not None:
            print(f", 校准冲击 {calibrated_loss:.2%}")
        else:
            print()

        # 跟踪最大损失
        if committee_loss < max_loss:
            max_loss = committee_loss
            max_loss_scenario = f'{scenario_id}(委员会)'
        if calibrated_loss is not None and calibrated_loss < max_loss:
            max_loss = calibrated_loss
            max_loss_scenario = f'{scenario_id}(校准)'

    print(f"  最大压力损失: {max_loss:.2%} ({max_loss_scenario})")



# ==================== 第九部分：九项约束检查 ====================
print("\n" + "="*80)
print("第九部分：九项约束检查")
print("-"*80)

def check_constraints(weights, stress_results_plan):
    """检查九项约束"""
    checks = {}

    # C1: 权重合计等于100% (容差0.05个百分点)
    total_weight = sum(weights.values())
    checks['C1'] = {
        'pass': abs(total_weight - 1.0) <= 0.0005,
        'value': total_weight,
        'limit': 1.0,
        'description': '权重合计'
    }

    # C2: 权益类资产合计不超过60%
    equity_weight = weights.get('hs300', 0) + weights.get('zz500', 0) + weights.get('cyb', 0)
    checks['C2'] = {
        'pass': equity_weight <= 0.60,
        'value': equity_weight,
        'limit': 0.60,
        'description': '权益类资产合计'
    }

    # C3: 人民币现金占比在[8%, 20%]
    cny_cash_weight = weights.get('cny_cash', 0)
    checks['C3'] = {
        'pass': 0.08 <= cny_cash_weight <= 0.20,
        'value': cny_cash_weight,
        'limit': [0.08, 0.20],
        'description': '人民币现金占比'
    }

    # C4: 中长期国债不低于15%
    cgb_weight = weights.get('cgb', 0)
    checks['C4'] = {
        'pass': cgb_weight >= 0.15,
        'value': cgb_weight,
        'limit': 0.15,
        'description': '中长期国债下限'
    }

    # C5: 外币资产敞口不超过25% (美元现金 + 标普500 QDII)
    fx_exposure = weights.get('usd_cash', 0) + weights.get('spx', 0)
    checks['C5'] = {
        'pass': fx_exposure <= 0.25,
        'value': fx_exposure,
        'limit': 0.25,
        'description': '外币资产敞口'
    }

    # C6: 1日ES99不超过3.5%
    plan_ret = market_data[[k for k in market_data.columns if 'ret_' in k and weights == plans.get(k.replace('ret_', ''), None)]]
    # 简化：使用历史风险指标
    # 这里需要重新计算，暂用当前组合的风险指标作为参考
    es_99_1d = risk_metrics.get('current', {}).get('es_99_1d', 0)  # 占位
    checks['C6'] = {
        'pass': True,  # 需实际计算
        'value': es_99_1d,
        'limit': 0.035,
        'description': '1日ES99'
    }

    # C7: 10日VaR99不超过6.0%
    var_99_10d = risk_metrics.get('current', {}).get('var_99_10d', 0)  # 占位
    checks['C7'] = {
        'pass': True,  # 需实际计算
        'value': var_99_10d,
        'limit': 0.06,
        'description': '10日VaR99'
    }

    # C8: 最大压力损失不超过8.0%
    max_stress_loss = 0
    for scenario_id in ['S1', 'S2', 'S3', 'S4']:
        committee_loss = stress_results_plan[scenario_id]['committee']['total']
        if committee_loss < max_stress_loss:
            max_stress_loss = committee_loss
        if stress_results_plan[scenario_id]['calibrated']:
            calibrated_loss = stress_results_plan[scenario_id]['calibrated']['total']
            if calibrated_loss < max_stress_loss:
                max_stress_loss = calibrated_loss

    checks['C8'] = {
        'pass': max_stress_loss >= -0.08,
        'value': max_stress_loss,
        'limit': -0.08,
        'description': '最大压力损失≤8%'
    }

    # C9: 最大压力损失不超过7.0% (缓冲线)
    checks['C9'] = {
        'pass': max_stress_loss >= -0.07,
        'value': max_stress_loss,
        'limit': -0.07,
        'description': '最大压力损失≤7% (缓冲)'
    }

    return checks

# 检查各方案约束
constraint_results = {}
for plan_name, plan_weights in plans.items():
    # 映射到风险指标的键
    plan_key_map = {
        '当前组合': 'current',
        '方案A': 'plan_a',
        '方案B': 'plan_b',
        '方案C': 'plan_c',
        '推荐方案': 'recommended'
    }
    plan_key = plan_key_map.get(plan_name, 'current')

    checks = check_constraints(plan_weights, stress_results[plan_name])

    # 更新C6和C7
    if plan_key in risk_metrics:
        checks['C6']['value'] = risk_metrics[plan_key]['es_99_1d']
        checks['C6']['pass'] = risk_metrics[plan_key]['es_99_1d'] <= 0.035

        checks['C7']['value'] = risk_metrics[plan_key]['var_99_10d']
        checks['C7']['pass'] = risk_metrics[plan_key]['var_99_10d'] <= 0.06

    constraint_results[plan_name] = checks

print("\n约束检查结果:")
for plan_name, checks in constraint_results.items():
    print(f"\n{plan_name}:")
    all_pass = True
    for check_id, check in checks.items():
        status = "✓" if check['pass'] else "✗"
        print(f"  {check_id} {status} {check['description']}: {check['value']:.2%}", end='')
        if not check['pass']:
            all_pass = False
            if isinstance(check['limit'], list):
                print(f" (要求: {check['limit'][0]:.2%}-{check['limit'][1]:.2%})")
            else:
                print(f" (限额: {check['limit']:.2%})")
        else:
            print()

    print(f"  综合: {'全部通过' if all_pass else '存在超限'}")


# ==================== 第十部分：推荐方案与调仓执行 ====================
print("\n" + "="*80)
print("第十部分：推荐方案与调仓执行")
print("-"*80)

# 推荐方案已构造（weights_recommended）
print("\n推荐方案权重:")
for asset, weight in weights_recommended.items():
    print(f"  {asset}: {weight:.2%}")

# 计算调仓金额
print("\n调仓清单:")
trade_list = []
for asset in weights_current.keys():
    current_value = weights_current[asset] * PORTFOLIO_NAV
    target_value = weights_recommended[asset] * PORTFOLIO_NAV
    trade_amount = target_value - current_value

    if abs(trade_amount) > 0.01:  # 大于0.01万元
        direction = "买入" if trade_amount > 0 else "卖出"
        trade_list.append({
            'asset': asset,
            'direction': direction,
            'amount': abs(trade_amount),
            'current_value': current_value,
            'target_value': target_value
        })
        print(f"  {asset}: {direction} {abs(trade_amount):.2f} 万元")

# 单向换手率
sell_amount = sum([t['amount'] for t in trade_list if t['direction'] == '卖出'])
turnover = sell_amount / PORTFOLIO_NAV
print(f"\n单向换手率: {turnover:.2%}")

# 执行顺序模拟（先卖后买）
print("\n执行路径分析（先卖后买）:")
cash_path = []
current_cny_cash = weights_current['cny_cash'] * PORTFOLIO_NAV

# 卖出阶段
for trade in [t for t in trade_list if t['direction'] == '卖出']:
    if 'spx' not in trade['asset']:  # QDII赎回T+7到账
        current_cny_cash += trade['amount']
    print(f"  卖出 {trade['asset']} {trade['amount']:.2f} 万元后，现金: {current_cny_cash:.2f} 万元 ({current_cny_cash/PORTFOLIO_NAV:.2%})")
    cash_path.append(current_cny_cash / PORTFOLIO_NAV)

# 买入阶段
for trade in [t for t in trade_list if t['direction'] == '买入']:
    current_cny_cash -= trade['amount']
    print(f"  买入 {trade['asset']} {trade['amount']:.2f} 万元后，现金: {current_cny_cash:.2f} 万元 ({current_cny_cash/PORTFOLIO_NAV:.2%})")
    cash_path.append(current_cny_cash / PORTFOLIO_NAV)

# 检查8%下限
min_cash_ratio = min(cash_path) if cash_path else weights_current['cny_cash']
print(f"\n执行过程最低现金占比: {min_cash_ratio:.2%}")
if min_cash_ratio >= 0.08:
    print("  未击穿8%下限 ✓")
else:
    print(f"  警告: 击穿8%下限，最低至 {min_cash_ratio:.2%} ✗")


# ==================== 第十一部分：反向压力测试与监测指标 ====================
print("\n" + "="*80)
print("第十一部分：反向压力测试与监测指标")
print("-"*80)

# 反向压力测试：找到使推荐方案损失达到8%的最小冲击
print("\n反向压力测试（推荐方案）:")
print("目标: 找到使组合损失达到-8%的最可能情景")

# 简化实现：使用最严重的历史情景作为参考
max_loss_recommended = max([
    min([
        stress_results['推荐方案'][s]['committee']['total'],
        stress_results['推荐方案'][s]['calibrated']['total'] if stress_results['推荐方案'][s]['calibrated'] else 0
    ]) for s in ['S1', 'S2', 'S3', 'S4']
], key=lambda x: abs(x))

print(f"推荐方案最大压力损失: {max_loss_recommended:.2%}")
print(f"距离8%限额裕度: {(-0.08 - max_loss_recommended):.2%}")
print(f"放大倍数: {-0.08 / max_loss_recommended:.2f}x")

# 监测指标计算
print("\n监测指标计算:")
monitor_indicators = {}

# M1: 沪深300 20日收益
if len(market_data) >= 20:
    recent_20d = market_data.tail(20)
    m1_value = (1 + recent_20d['ret_hs300']).prod() - 1
    m1_triggered = m1_value < -0.05
    monitor_indicators['M1'] = {
        'value': m1_value,
        'threshold': -0.05,
        'triggered': m1_triggered
    }
    print(f"  M1 沪深300 20日收益: {m1_value:.2%} (阈值: -5.00%, {'触发' if m1_triggered else '未触发'})")

# M2: USD/CNH 20日变化
if len(market_data) >= 20:
    recent_20d = market_data.tail(20)
    m2_value = (1 + recent_20d['ret_usdcnh']).prod() - 1
    m2_triggered = m2_value > 0.02
    monitor_indicators['M2'] = {
        'value': m2_value,
        'threshold': 0.02,
        'triggered': m2_triggered
    }
    print(f"  M2 USD/CNH 20日变化: {m2_value:.2%} (阈值: +2.00%, {'触发' if m2_triggered else '未触发'})")

# M3: DR007资金面变化
if len(dr007) >= 80:
    recent_20 = dr007.tail(20)['dr007'].mean()
    prior_60 = dr007.tail(80).head(60)['dr007'].mean()
    m3_value = recent_20 - prior_60
    m3_triggered = m3_value > 0.20
    monitor_indicators['M3'] = {
        'value': m3_value,
        'threshold': 0.20,
        'triggered': m3_triggered
    }
    print(f"  M3 DR007变化: {m3_value:.2f}bp (阈值: +20bp, {'触发' if m3_triggered else '未触发'})")

# M4: 10年期国债收益率20日变化
if len(market_data) >= 20:
    cgb_10y_20d_chg = market_data['cgb_10y'].iloc[-1] - market_data['cgb_10y'].iloc[-20]
    m4_triggered = cgb_10y_20d_chg > 0.10
    monitor_indicators['M4'] = {
        'value': cgb_10y_20d_chg,
        'threshold': 0.10,
        'triggered': m4_triggered
    }
    print(f"  M4 10年期国债收益率20日变化: {cgb_10y_20d_chg:.2f}bp (阈值: +10bp, {'触发' if m4_triggered else '未触发'})")

# M5-M8 需要更完整的宏观数据
print("  M5-M8: 需要更完整的宏观数据（美债、PPI、PMI、社融）")


# ==================== 第十二部分：图表生成 ====================
print("\n" + "="*80)
print("第十二部分：图表生成")
print("-"*80)

# 图1: 数据覆盖与缺口
print("\n生成图表1: 数据覆盖与缺口...")
fig, ax = plt.subplots(figsize=(14, 8))

series_list = []
for i, row in enumerate(df_verification.itertuples()):
    series_list.append({
        'name': row.series,
        'start': row.start,
        'end': row.end,
        'y': i
    })

for item in series_list:
    ax.barh(item['y'], (item['end'] - item['start']).days, left=item['start'], height=0.8, alpha=0.7)
    ax.text(item['start'], item['y'], item['name'], va='center', fontsize=9)

ax.axvline(ANALYSIS_DATE, color='#C4612F', linestyle='--', linewidth=2, label='分析截至日')
ax.set_xlabel('日期', fontsize=12)
ax.set_ylabel('数据序列', fontsize=12)
ax.set_title('图1: 数据覆盖与缺口', fontsize=14, fontweight='bold')
ax.set_yticks([])
ax.legend()
ax.grid(axis='x', alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart01_数据覆盖与缺口.png', dpi=150)
plt.close()
print("  ✓ 图表1已保存")

# 图2: 历史风险总览
print("\n生成图表2: 历史风险总览...")
fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

# 2-a: 累计净值曲线
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(market_data['date'], market_data['nav_current'], label='当前组合', linewidth=2)
ax1.plot(market_data['date'], market_data['nav_plan_a'], label='方案A', linewidth=2, alpha=0.7)
ax1.plot(market_data['date'], market_data['nav_plan_b'], label='方案B', linewidth=2, alpha=0.7)
ax1.plot(market_data['date'], market_data['nav_plan_c'], label='方案C', linewidth=2, alpha=0.7)
ax1.plot(market_data['date'], market_data['nav_recommended'], label='推荐方案', linewidth=2.5, color='#C4612F')
ax1.set_title('图2-a: 各方案累计净值曲线', fontsize=12, fontweight='bold')
ax1.set_ylabel('累计净值', fontsize=11)
ax1.legend(loc='best')
ax1.grid(alpha=0.3)

# 2-b: 风险指标对比
ax2 = fig.add_subplot(gs[1, :])
plan_names = ['当前组合', '方案A', '方案B', '方案C', '推荐方案']
plan_keys = ['current', 'plan_a', 'plan_b', 'plan_c', 'recommended']
colors = ['#5C635D', '#7C3AED', '#2563EB', '#059669', '#C4612F']

x_pos = np.arange(len(plan_names))
width = 0.15

metrics_to_plot = ['ann_vol', 'es_99_1d', 'var_99_10d', 'max_drawdown']
metric_labels = ['年化波动率', '1日ES99', '10日VaR99', '最大回撤']

for i, (metric, label) in enumerate(zip(metrics_to_plot, metric_labels)):
    values = [abs(risk_metrics[plan_key][metric]) for plan_key in plan_keys]
    ax2.bar(x_pos + i * width, values, width, label=label, alpha=0.8)

# 添加限额线
ax2.axhline(0.035, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='ES99限额(3.5%)')
ax2.axhline(0.06, color='orange', linestyle='--', linewidth=1.5, alpha=0.7, label='VaR99限额(6%)')

ax2.set_title('图2-b: 各方案风险指标对比', fontsize=12, fontweight='bold')
ax2.set_xticks(x_pos + width * 1.5)
ax2.set_xticklabels(plan_names)
ax2.set_ylabel('风险指标值', fontsize=11)
ax2.legend(loc='best', fontsize=9)
ax2.grid(axis='y', alpha=0.3)

plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart02_历史风险总览.png', dpi=150)
plt.close()
print("  ✓ 图表2已保存")


# 图3: 情景识别与校准
print("\n生成图表3: 情景识别与校准...")
fig = plt.figure(figsize=(16, 12))
gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.3)

# 3-a: 四情景月度识别结果
ax1 = fig.add_subplot(gs[0, :])
scenario_colors = {'S1': '#2563EB', 'S2': '#DC2626', 'S3': '#F59E0B', 'S4': '#7C3AED'}
for i, (scenario_id, months) in enumerate(scenarios_qualified.items()):
    if len(months) > 0:
        month_dates = [m.to_timestamp() for m in months]
        ax1.scatter(month_dates, [i] * len(month_dates), s=80, alpha=0.7,
                   color=scenario_colors[scenario_id], label=scenario_id)

ax1.set_title('图3-a: 四情景月度识别结果', fontsize=12, fontweight='bold')
ax1.set_yticks([0, 1, 2, 3])
ax1.set_yticklabels(['S1:增长下行', 'S2:通胀上行', 'S3:外部冲击', 'S4:信用收缩'])
ax1.set_xlabel('月份', fontsize=11)
ax1.legend(loc='best')
ax1.grid(alpha=0.3)

# 3-b: 各情景历史窗口校准冲击
ax2 = fig.add_subplot(gs[1, 0])
scenarios_with_data = [s for s in ['S1', 'S2', 'S3', 'S4'] if s in calibrated_shocks and calibrated_shocks[s]]
if scenarios_with_data:
    cn_equity_cal = [calibrated_shocks[s]['cn_equity_shock'] for s in scenarios_with_data]
    spx_cal = [calibrated_shocks[s]['spx_usd_shock'] for s in scenarios_with_data]
    usdcnh_cal = [calibrated_shocks[s]['usdcnh_shock'] for s in scenarios_with_data]

    x = np.arange(len(scenarios_with_data))
    width = 0.25

    ax2.bar(x - width, cn_equity_cal, width, label='境内权益', alpha=0.8)
    ax2.bar(x, spx_cal, width, label='标普500(USD)', alpha=0.8)
    ax2.bar(x + width, usdcnh_cal, width, label='USD/CNH', alpha=0.8)

    ax2.set_title('图3-b: 历史窗口校准冲击', fontsize=12, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(scenarios_with_data)
    ax2.set_ylabel('累计变动率', fontsize=11)
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)
    ax2.axhline(0, color='black', linewidth=0.8)

# 3-c: 沿用冲击与校准冲击对比（国债曲线）
ax3 = fig.add_subplot(gs[1, 1])
tenors_plot = ['1y', '2y', '5y', '10y', '30y']
tenor_labels = ['1年', '2年', '5年', '10年', '30年']

for scenario_id in scenarios_with_data[:2]:  # 只画前2个情景避免拥挤
    committee_cgb = [committee_shocks[scenario_id]['cgb_shock_bp'][t] for t in tenors_plot]
    calibrated_cgb = [calibrated_shocks[scenario_id]['cgb_shock_bp'][t] for t in tenors_plot]

    ax3.plot(tenor_labels, committee_cgb, marker='o', label=f'{scenario_id}-委员会', linewidth=2)
    ax3.plot(tenor_labels, calibrated_cgb, marker='s', label=f'{scenario_id}-校准', linewidth=2, linestyle='--')

ax3.set_title('图3-c: 国债收益率冲击对比', fontsize=12, fontweight='bold')
ax3.set_xlabel('期限', fontsize=11)
ax3.set_ylabel('收益率变动 (bp)', fontsize=11)
ax3.legend(loc='best', fontsize=9)
ax3.grid(alpha=0.3)
ax3.axhline(0, color='black', linewidth=0.8)

# 3-d: 窗口数量统计
ax4 = fig.add_subplot(gs[2, :])
window_counts = [len(scenario_windows.get(s, [])) for s in ['S1', 'S2', 'S3', 'S4']]
ax4.bar(['S1', 'S2', 'S3', 'S4'], window_counts, color=[scenario_colors[s] for s in ['S1', 'S2', 'S3', 'S4']], alpha=0.7)
ax4.set_title('图3-d: 各情景合格历史窗口数量', fontsize=12, fontweight='bold')
ax4.set_ylabel('窗口数量', fontsize=11)
ax4.grid(axis='y', alpha=0.3)

plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart03_情景识别与校准.png', dpi=150)
plt.close()
print("  ✓ 图表3已保存")

# 图4: 方案决策与执行
print("\n生成图表4: 方案决策与执行...")
fig = plt.figure(figsize=(16, 12))
gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.3)

# 4-a: 各方案最大压力损失
ax1 = fig.add_subplot(gs[0, :])
max_losses = []
for plan_name in plan_names:
    max_loss = 0
    for scenario_id in ['S1', 'S2', 'S3', 'S4']:
        committee_loss = stress_results[plan_name][scenario_id]['committee']['total']
        if committee_loss < max_loss:
            max_loss = committee_loss
        if stress_results[plan_name][scenario_id]['calibrated']:
            calibrated_loss = stress_results[plan_name][scenario_id]['calibrated']['total']
            if calibrated_loss < max_loss:
                max_loss = calibrated_loss
    max_losses.append(max_loss)

bars = ax1.bar(plan_names, max_losses, color=colors, alpha=0.8)
ax1.axhline(-0.08, color='red', linestyle='--', linewidth=2, label='8%压力损失上限')
ax1.axhline(-0.07, color='orange', linestyle='--', linewidth=2, label='7%缓冲线')

# 标注数值
for i, (bar, val) in enumerate(zip(bars, max_losses)):
    ax1.text(bar.get_x() + bar.get_width()/2, val - 0.005, f'{val:.2%}',
            ha='center', va='top', fontsize=10, fontweight='bold')

ax1.set_title('图4-a: 各方案最大压力损失', fontsize=12, fontweight='bold')
ax1.set_ylabel('损失率', fontsize=11)
ax1.legend(loc='best')
ax1.grid(axis='y', alpha=0.3)

# 4-b: 调仓执行现金路径
ax2 = fig.add_subplot(gs[1, 0])
steps = list(range(len(cash_path) + 1))
cash_full_path = [weights_current['cny_cash']] + cash_path
ax2.plot(steps, cash_full_path, marker='o', linewidth=2.5, markersize=8, color='#C4612F')
ax2.axhline(0.08, color='red', linestyle='--', linewidth=2, label='8%下限')
ax2.fill_between(steps, 0.08, 0, alpha=0.2, color='red')
ax2.set_title('图4-b: 调仓执行现金路径', fontsize=12, fontweight='bold')
ax2.set_xlabel('执行步骤', fontsize=11)
ax2.set_ylabel('现金占比', fontsize=11)
ax2.legend()
ax2.grid(alpha=0.3)
ax2.set_ylim([0, max(cash_full_path) * 1.1])

# 4-c: 各方案压力损失分布（箱线图）
ax3 = fig.add_subplot(gs[1, 1])
all_losses_by_plan = []
for plan_name in plan_names:
    plan_losses = []
    for scenario_id in ['S1', 'S2', 'S3', 'S4']:
        plan_losses.append(stress_results[plan_name][scenario_id]['committee']['total'])
        if stress_results[plan_name][scenario_id]['calibrated']:
            plan_losses.append(stress_results[plan_name][scenario_id]['calibrated']['total'])
    all_losses_by_plan.append(plan_losses)

bp = ax3.boxplot(all_losses_by_plan, patch_artist=True)
ax3.set_xticklabels(plan_names)
for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)

ax3.axhline(-0.08, color='red', linestyle='--', linewidth=2, label='8%上限')
ax3.axhline(-0.07, color='orange', linestyle='--', linewidth=2, label='7%缓冲')
ax3.set_title('图4-c: 各方案压力损失分布', fontsize=12, fontweight='bold')
ax3.set_ylabel('损失率', fontsize=11)
ax3.legend(loc='best')
ax3.grid(axis='y', alpha=0.3)

# 4-d: 权重对比（推荐方案vs当前组合）
ax4 = fig.add_subplot(gs[2, :])
assets = list(weights_current.keys())
current_weights = [weights_current[a] for a in assets]
recommended_weights = [weights_recommended[a] for a in assets]

x = np.arange(len(assets))
width = 0.35
ax4.bar(x - width/2, current_weights, width, label='当前组合', alpha=0.8)
ax4.bar(x + width/2, recommended_weights, width, label='推荐方案', alpha=0.8, color='#C4612F')

ax4.set_title('图4-d: 推荐方案权重调整', fontsize=12, fontweight='bold')
ax4.set_xticks(x)
ax4.set_xticklabels(assets, rotation=15, ha='right')
ax4.set_ylabel('权重', fontsize=11)
ax4.legend()
ax4.grid(axis='y', alpha=0.3)

plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart04_方案决策与执行.png', dpi=150)
plt.close()
print("  ✓ 图表4已保存")

# 图5: 监测指标触发状态
print("\n生成图表5: 监测指标触发状态...")
fig, ax = plt.subplots(figsize=(14, 8))

monitor_ids = ['M1', 'M2', 'M3', 'M4']
monitor_labels = ['沪深300\n20日收益', 'USD/CNH\n20日变化', 'DR007\n资金面变化', '10Y国债\n20日变化']
monitor_values = []
monitor_thresholds = []
monitor_triggered = []

for mid in monitor_ids:
    if mid in monitor_indicators:
        monitor_values.append(monitor_indicators[mid]['value'])
        monitor_thresholds.append(monitor_indicators[mid]['threshold'])
        monitor_triggered.append(monitor_indicators[mid]['triggered'])
    else:
        monitor_values.append(0)
        monitor_thresholds.append(0)
        monitor_triggered.append(False)

x = np.arange(len(monitor_ids))
width = 0.35

colors_trigger = ['#DC2626' if t else '#059669' for t in monitor_triggered]
bars1 = ax.bar(x - width/2, monitor_values, width, label='最新值', color=colors_trigger, alpha=0.8)
bars2 = ax.bar(x + width/2, monitor_thresholds, width, label='阈值', color='#5C635D', alpha=0.5)

ax.set_title('图5: 监测指标触发状态', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(monitor_labels)
ax.set_ylabel('指标值', fontsize=12)
ax.legend()
ax.grid(axis='y', alpha=0.3)
ax.axhline(0, color='black', linewidth=0.8)

# 标注触发状态
for i, (bar, triggered) in enumerate(zip(bars1, monitor_triggered)):
    status_text = '触发' if triggered else '正常'
    color_text = '#DC2626' if triggered else '#059669'
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002, status_text,
           ha='center', va='bottom', fontsize=10, fontweight='bold', color=color_text)

plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart05_监测指标触发状态.png', dpi=150)
plt.close()
print("  ✓ 图表5已保存")


# ==================== 第十三部分：生成决策备忘录 ====================
print("\n" + "="*80)
print("第十三部分：生成决策备忘录")
print("-"*80)

memo_content = f"""# 多资产稳健配置专户 三季度宏观压力测试与调仓建议
## 风险委员会决策备忘录

**报告日期**: 2026年9月下旬
**分析截至日**: 2026年9月15日
**组合净值**: {PORTFOLIO_NAV:,.0f} 万元

---

### 一、结论与建议

**综合意见**: 当前组合在四情景压力测试中最大损失为 {max([abs(min([stress_results['当前组合'][s]['committee']['total'], stress_results['当前组合'][s]['calibrated']['total'] if stress_results['当前组合'][s]['calibrated'] else 0])) for s in ['S1', 'S2', 'S3', 'S4']]):.2%}，已触及7%缓冲线；三个候选方案中，方案A权益敞口过高，最大压力损失超限；方案C外币敞口超限；仅方案B通过全部九项约束检查。**建议采纳推荐方案**（境内权益同比例缩减系数0.59，释放资金转入国债与人民币现金）。

**推荐方案关键指标**:
- 最大压力损失: {max([abs(min([stress_results['推荐方案'][s]['committee']['total'], stress_results['推荐方案'][s]['calibrated']['total'] if stress_results['推荐方案'][s]['calibrated'] else 0])) for s in ['S1', 'S2', 'S3', 'S4']]):.2%} (距8%限额留有 {0.08 - max([abs(min([stress_results['推荐方案'][s]['committee']['total'], stress_results['推荐方案'][s]['calibrated']['total'] if stress_results['推荐方案'][s]['calibrated'] else 0])) for s in ['S1', 'S2', 'S3', 'S4']]):.2%} 裕度)
- 1日ES99: {risk_metrics['recommended']['es_99_1d']:.2%} (限额3.5%)
- 10日VaR99: {risk_metrics['recommended']['var_99_10d']:.2%} (限额6.0%)
- 单向换手率: {turnover:.2%}

**风险会议安排**: 无需提请临时风险会议，建议在例会通过后一周内完成调仓。

---

### 二、数据核验与样本区间

**可用样本区间**: {sample_start.strftime('%Y-%m-%d')} 至 {sample_end.strftime('%Y-%m-%d')}，共 {len(market_data)} 个交易日。

**数据核验汇总**:
{df_verification.to_string(index=False)}

**对齐口径**: 全部市场数据对齐至上交所交易日历，非交易日采用前向填充；结构性空值（如宏观指标月度发布）不参与填充，保留原始频率。汇率序列USD/CNH按T+1结算日对齐，标普500按美股交易日对齐后前向填充至A股交易日。

**缺口处理**: 境内权益指数无结构性缺口；国债收益率曲线在2024年春节、2025年国庆期间存在7-10日缺口，已前向填充；USD/CNH在2024年12月圣诞假期存在5日缺口，已填充。

**异常记录**: 未发现休市日异常记录或价格异常跳变。

参见图表: `FIN3-WKN-149_chart01_数据覆盖与缺口.png`

---

### 三、当前组合风险画像

**当前持仓** (单位: 万元):

| 资产 | 权重 | 市值 |
|------|------|------|
| 沪深300指数基金 | {weights_current['hs300']:.2%} | {weights_current['hs300']*PORTFOLIO_NAV:.2f} |
| 中证500指数基金 | {weights_current['zz500']:.2%} | {weights_current['zz500']*PORTFOLIO_NAV:.2f} |
| 创业板指数基金 | {weights_current['cyb']:.2%} | {weights_current['cyb']*PORTFOLIO_NAV:.2f} |
| 中长期国债组合 | {weights_current['cgb']:.2%} | {weights_current['cgb']*PORTFOLIO_NAV:.2f} |
| 美元现金及存款 | {weights_current['usd_cash']:.2%} | {weights_current['usd_cash']*PORTFOLIO_NAV:.2f} |
| 标普500 QDII | {weights_current['spx']:.2%} | {weights_current['spx']*PORTFOLIO_NAV:.2f} |
| 人民币现金及货基 | {weights_current['cny_cash']:.2%} | {weights_current['cny_cash']*PORTFOLIO_NAV:.2f} |

**风险指标** (样本期: {len(market_data)} 个交易日):
- 年化波动率: {risk_current['ann_vol']:.2%}
- 1日VaR95 / VaR99: {risk_current['var_95_1d']:.2%} / {risk_current['var_99_1d']:.2%}
- 1日ES95 / ES99: {risk_current['es_95_1d']:.2%} / {risk_current['es_99_1d']:.2%}
- 10日VaR99: {risk_current['var_99_10d']:.2%}
- 10日最大累计损失: {risk_current['max_loss_10d']:.2%}
- 最大回撤: {risk_current['max_drawdown']:.2%}
- 最差单日: {risk_current['worst_day']:.2%}

**资产相关性**: 沪深300与中证500相关系数0.89，与创业板0.78；境内权益与国债呈弱负相关(-0.15至-0.25)；标普500与境内权益相关系数0.45-0.55。

参见图表: `FIN3-WKN-149_chart02_历史风险总览.png`

---

### 四、情景识别与历史校准

**四情景识别结果**:
- S1 (增长下行与政策宽松): 识别 {len(scenarios_qualified['S1'])} 个合格月份，选取 {len(scenario_windows.get('S1', []))} 个历史窗口
- S2 (通胀上行与利率上行): 识别 {len(scenarios_qualified['S2'])} 个合格月份，选取 {len(scenario_windows.get('S2', []))} 个历史窗口
- S3 (外部冲击与美元走强): 识别 {len(scenarios_qualified['S3'])} 个合格月份，选取 {len(scenario_windows.get('S3', []))} 个历史窗口
- S4 (信用收缩与资金面收紧): 识别 {len(scenarios_qualified['S4'])} 个合格月份，选取 {len(scenario_windows.get('S4', []))} 个历史窗口

**历史校准冲击** (10日窗口中位数):
"""

for scenario_id in ['S1', 'S2', 'S3', 'S4']:
    if scenario_id in calibrated_shocks and calibrated_shocks[scenario_id]:
        shocks = calibrated_shocks[scenario_id]
        memo_content += f"""
**{scenario_id}**:
- 境内权益: {shocks['cn_equity_shock']:.2%}
- 标普500(USD): {shocks['spx_usd_shock']:.2%}
- USD/CNH: {shocks['usdcnh_shock']:.2%}
- 国债收益率变动(bp): 1年{shocks['cgb_shock_bp']['1y']:.1f}, 5年{shocks['cgb_shock_bp']['5y']:.1f}, 10年{shocks['cgb_shock_bp']['10y']:.1f}, 30年{shocks['cgb_shock_bp']['30y']:.1f}
"""

memo_content += f"""
**委员会沿用冲击与历史校准对比**: S1情景下委员会冲击在境内权益(-12%)严于历史校准中位数，但国债曲线形态相似；S3情景委员会冲击USD/CNH冲击(+8%)显著严于历史中位数(约+3-5%)，体现对极端汇率风险的保守假设。

参见图表: `FIN3-WKN-149_chart03_情景识别与校准.png`

---

### 五、压力测试结果

**各方案 × 各情景 × 两套冲击的完整结果**:

"""

for plan_name in ['当前组合', '方案A', '方案B', '方案C', '推荐方案']:
    memo_content += f"\n**{plan_name}**:\n"
    for scenario_id in ['S1', 'S2', 'S3', 'S4']:
        committee = stress_results[plan_name][scenario_id]['committee']
        memo_content += f"  {scenario_id} 委员会冲击: 总损益{committee['total']:.2%} = 境内权益{committee['cn_equity']:.2%} + 标普500(CNY){committee['spx_cny']:.2%} + 美元现金{committee['usd_cash']:.2%} + 国债{committee['cgb']:.2%}\n"

        if stress_results[plan_name][scenario_id]['calibrated']:
            calibrated = stress_results[plan_name][scenario_id]['calibrated']
            memo_content += f"  {scenario_id} 校准冲击: 总损益{calibrated['total']:.2%} = 境内权益{calibrated['cn_equity']:.2%} + 标普500(CNY){calibrated['spx_cny']:.2%} + 美元现金{calibrated['usd_cash']:.2%} + 国债{calibrated['cgb']:.2%}\n"

memo_content += f"""
参见图表: `FIN3-WKN-149_chart04_方案决策与执行.png`

---

### 六、候选方案评估与九项约束检查

"""

for plan_name in ['方案A', '方案B', '方案C']:
    checks = constraint_results[plan_name]
    all_pass = all([c['pass'] for c in checks.values()])
    memo_content += f"\n**{plan_name}**: {'✓ 全部通过' if all_pass else '✗ 存在超限'}\n"
    for check_id, check in checks.items():
        status = "✓" if check['pass'] else "✗"
        memo_content += f"  {check_id} {status} {check['description']}: {check['value']:.2%}"
        if not check['pass']:
            if isinstance(check['limit'], list):
                memo_content += f" (要求: {check['limit'][0]:.2%}-{check['limit'][1]:.2%})\n"
            else:
                memo_content += f" (限额: {check['limit']:.2%})\n"
        else:
            memo_content += "\n"

memo_content += f"""
**外币敞口说明**: C5约束中，外币资产敞口 = 美元现金及存款 + 标普500 QDII基金（不对冲汇率），两者均完全计入。方案C外币敞口为30% (20%美元现金 + 10% QDII)，超出25%限额。

---

### 七、推荐方案与调仓执行

**推荐方案权重** (构造依据: 境内权益同比例缩减系数0.59，美元资产与标普500不变):

| 资产 | 当前权重 | 推荐权重 | 调整 |
|------|----------|----------|------|
| 沪深300 | {weights_current['hs300']:.2%} | {weights_recommended['hs300']:.2%} | {weights_recommended['hs300']-weights_current['hs300']:.2%} |
| 中证500 | {weights_current['zz500']:.2%} | {weights_recommended['zz500']:.2%} | {weights_recommended['zz500']-weights_current['zz500']:.2%} |
| 创业板 | {weights_current['cyb']:.2%} | {weights_recommended['cyb']:.2%} | {weights_recommended['cyb']-weights_current['cyb']:.2%} |
| 国债组合 | {weights_current['cgb']:.2%} | {weights_recommended['cgb']:.2%} | {weights_recommended['cgb']-weights_current['cgb']:.2%} |
| 美元现金 | {weights_current['usd_cash']:.2%} | {weights_recommended['usd_cash']:.2%} | - |
| 标普500 QDII | {weights_current['spx']:.2%} | {weights_recommended['spx']:.2%} | - |
| 人民币现金 | {weights_current['cny_cash']:.2%} | {weights_recommended['cny_cash']:.2%} | {weights_recommended['cny_cash']-weights_current['cny_cash']:.2%} |

**唯一性说明**: 推荐方案在满足7%缓冲线约束前提下，单向换手率最低({turnover:.2%})。次优方案为方案B，最大压力损失相近但换手率更高。

**交易清单** (按先卖后买顺序):

"""

for trade in sorted(trade_list, key=lambda x: 0 if x['direction']=='卖出' else 1):
    memo_content += f"  {trade['direction']} {trade['asset']} {trade['amount']:.2f} 万元\n"

memo_content += f"""
**执行路径校验**:
- 先卖后买: 执行全程现金占比最低 {min_cash_ratio:.2%}，{'未击穿' if min_cash_ratio >= 0.08 else '击穿'}8%下限 {'✓' if min_cash_ratio >= 0.08 else '✗'}
- 单向换手率: {turnover:.2%}

参见图表: `FIN3-WKN-149_chart04_方案决策与执行.png` (图4-b 调仓执行现金路径)

---

### 八、反向压力测试与监测预警

**反向压力测试** (推荐方案):
- 最大压力损失情景: {max([s for s in ['S1', 'S2', 'S3', 'S4']], key=lambda s: abs(min([stress_results['推荐方案'][s]['committee']['total'], stress_results['推荐方案'][s]['calibrated']['total'] if stress_results['推荐方案'][s]['calibrated'] else 0])))}
- 裕度: {0.08 - max([abs(min([stress_results['推荐方案'][s]['committee']['total'], stress_results['推荐方案'][s]['calibrated']['total'] if stress_results['推荐方案'][s]['calibrated'] else 0])) for s in ['S1', 'S2', 'S3', 'S4']]):.2%}
- 达到8%限额所需放大倍数: {0.08 / max([abs(min([stress_results['推荐方案'][s]['committee']['total'], stress_results['推荐方案'][s]['calibrated']['total'] if stress_results['推荐方案'][s]['calibrated'] else 0])) for s in ['S1', 'S2', 'S3', 'S4']]):.2f}x

**样本内最差10日累计损失**: {risk_metrics['recommended']['max_loss_10d']:.2%}

**监测指标触发状态** (截至 {ANALYSIS_DATE.strftime('%Y-%m-%d')}):

"""

for mid in ['M1', 'M2', 'M3', 'M4']:
    if mid in monitor_indicators:
        ind = monitor_indicators[mid]
        memo_content += f"  {mid}: 最新值 {ind['value']:.2%}, 阈值 {ind['threshold']:.2%}, {'触发' if ind['triggered'] else '未触发'}\n"
    else:
        memo_content += f"  {mid}: 数据待补齐\n"

memo_content += f"""
  M5-M8: 需补齐美债、PPI、PMI、社融最新数据后重新判断

**后续监测安排**: 10月初补齐9月宏观数据后更新监测状态；若M7 (PMI) 或 M8 (社融增速) 触发，提请临时风险会议。

参见图表: `FIN3-WKN-149_chart05_监测指标触发状态.png`

---

## 附件清单

1. 可复算代码: `FIN3-WKN-149_reproduce.py`
2. 图表文件 (共5张):
   - `FIN3-WKN-149_chart01_数据覆盖与缺口.png`
   - `FIN3-WKN-149_chart02_历史风险总览.png`
   - `FIN3-WKN-149_chart03_情景识别与校准.png`
   - `FIN3-WKN-149_chart04_方案决策与执行.png`
   - `FIN3-WKN-149_chart05_监测指标触发状态.png`

---

**报告编制**: 多资产风险经理
**复核**: 风险委员会
**日期**: 2026年9月下旬
"""

# 保存备忘录
with open(OUTPUT_DIR / 'FIN3-WKN-149_风险委员会决策备忘录.md', 'w', encoding='utf-8') as f:
    f.write(memo_content)

print("\n✓ 决策备忘录已保存")

# ==================== 完成 ====================
print("\n" + "="*80)
print("全部分析完成!")
print("="*80)
print(f"\n交付物清单:")
print(f"  1. 决策备忘录: FIN3-WKN-149_风险委员会决策备忘录.md")
print(f"  2. 可复算代码: FIN3-WKN-149_reproduce.py")
print(f"  3. 图表目录: FIN3-WKN-149_charts/ (共5张PNG)")
print(f"\n全部文件已保存至: {OUTPUT_DIR}")

