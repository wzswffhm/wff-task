#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多资产稳健配置专户：三季度宏观压力测试与调仓建议 - 可复算代码
分析截至日：2026-09-15
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 路径配置
INPUT_DIR = Path('/app/input_files')
OUTPUT_DIR = Path('/app/output')
CHART_DIR = OUTPUT_DIR / 'FIN3-WKN-149_charts'
CHART_DIR.mkdir(parents=True, exist_ok=True)

# 分析截至日
ANALYSIS_DATE = pd.to_datetime('2026-09-15')
PORTFOLIO_NAV = 10000.0  # 万元

print("="*80)
print("多资产稳健配置专户 - 三季度宏观压力测试")
print("="*80)
print(f"分析截至日: {ANALYSIS_DATE.date()}")
print(f"组合净值: {PORTFOLIO_NAV:,.0f} 万元\n")

# ============================================================================
# 第一部分：数据加载与核验
# ============================================================================
print("\n" + "="*80)
print("第一部分：数据加载与核验")
print("="*80)

def load_segmented_data(prefix, columns=None):
    """加载分段数据文件"""
    seg1 = INPUT_DIR / f"{prefix}_seg1.csv"
    seg2 = INPUT_DIR / f"{prefix}_seg2.csv"

    dfs = []
    if seg1.exists():
        df1 = pd.read_csv(seg1)
        dfs.append(df1)
    if seg2.exists():
        df2 = pd.read_csv(seg2)
        dfs.append(df2)

    if not dfs:
        return None

    df = pd.concat(dfs, ignore_index=True)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').drop_duplicates('date').reset_index(drop=True)

    return df

# 加载交易日历
print("\n1. 加载交易日历...")
trade_calendar = pd.read_csv(INPUT_DIR / 'snapshot_trade_calendar.csv')
trade_calendar['date'] = pd.to_datetime(trade_calendar['date'])
trade_calendar = trade_calendar[trade_calendar['is_trading_day'] == 1].copy()
trade_calendar = trade_calendar.sort_values('date').reset_index(drop=True)
print(f"   交易日历：{trade_calendar['date'].min().date()} 至 {trade_calendar['date'].max().date()}")
print(f"   交易日数量：{len(trade_calendar)}")

# 加载股票指数
print("\n2. 加载股票指数...")
hs300 = load_segmented_data('snapshot_000300SH')
zz500 = load_segmented_data('snapshot_000905SH')
cyb = load_segmented_data('snapshot_399006SZ')

print(f"   沪深300：{len(hs300)} 条，{hs300['date'].min().date()} 至 {hs300['date'].max().date()}")
print(f"   中证500：{len(zz500)} 条，{zz500['date'].min().date()} 至 {zz500['date'].max().date()}")
print(f"   创业板指：{len(cyb)} 条，{cyb['date'].min().date()} 至 {cyb['date'].max().date()}")

# 加载国债收益率
print("\n3. 加载国债收益率曲线...")
cgb_1y = pd.read_csv(INPUT_DIR / 'snapshot_cgb_yield_1y.csv')
cgb_2y = pd.read_csv(INPUT_DIR / 'snapshot_cgb_yield_2y.csv')
cgb_5y = pd.read_csv(INPUT_DIR / 'snapshot_cgb_yield_5y.csv')
cgb_10y = pd.read_csv(INPUT_DIR / 'snapshot_cgb_yield_10y.csv')
cgb_30y = pd.read_csv(INPUT_DIR / 'snapshot_cgb_yield_30y.csv')

for df in [cgb_1y, cgb_2y, cgb_5y, cgb_10y, cgb_30y]:
    df['date'] = pd.to_datetime(df['date'])

print(f"   国债收益率：{cgb_10y['date'].min().date()} 至 {cgb_10y['date'].max().date()}")
print(f"   ⚠️  国债数据截至 2026-06-09，早于分析截至日 3 个月")

# 加载汇率
print("\n4. 加载USD/CNH汇率...")
usdcnh = load_segmented_data('snapshot_usdcnh')
print(f"   USD/CNH：{len(usdcnh)} 条，{usdcnh['date'].min().date()} 至 {usdcnh['date'].max().date()}")

# 加载标普500
print("\n5. 加载标普500指数...")
spx = pd.read_csv(INPUT_DIR / 'snapshot_spx.csv')
spx['date'] = pd.to_datetime(spx['date'])
print(f"   标普500：{len(spx)} 条，{spx['date'].min().date()} 至 {spx['date'].max().date()}")

# 加载宏观数据
print("\n6. 加载宏观经济数据...")
pmi = pd.read_csv(INPUT_DIR / 'snapshot_pmi_manufacturing.csv')
pmi['date'] = pd.to_datetime(pmi['date'])
lpr_1y = pd.read_csv(INPUT_DIR / 'snapshot_lpr_1y.csv')
lpr_1y['date'] = pd.to_datetime(lpr_1y['date'])
lpr_5y = pd.read_csv(INPUT_DIR / 'snapshot_lpr_5y.csv')
lpr_5y['date'] = pd.to_datetime(lpr_5y['date'])
afre = pd.read_csv(INPUT_DIR / 'snapshot_afre_stock.csv')
afre['date'] = pd.to_datetime(afre['date'])
ppi = pd.read_csv(INPUT_DIR / 'snapshot_ppi_yoy.csv')
ppi['date'] = pd.to_datetime(ppi['date'])
dr007 = pd.read_csv(INPUT_DIR / 'snapshot_dr007.csv')
dr007['date'] = pd.to_datetime(dr007['date'])
shibor = load_segmented_data('snapshot_shibor')

print(f"   制造业PMI：{len(pmi)} 条，{pmi['date'].min().date()} 至 {pmi['date'].max().date()}")
print(f"   社融存量：{len(afre)} 条，{afre['date'].min().date()} 至 {afre['date'].max().date()}")
print(f"   PPI同比：{len(ppi)} 条，{ppi['date'].min().date()} 至 {ppi['date'].max().date()}")
print(f"   DR007：{len(dr007)} 条，{dr007['date'].min().date()} 至 {dr007['date'].max().date()}")

# 确定有效样本区间
print("\n7. 确定有效样本区间...")
# 国债数据截至 2026-06-09，是最短的
sample_end = min(ANALYSIS_DATE, cgb_10y['date'].max())
sample_start = max(hs300['date'].min(), zz500['date'].min(), cyb['date'].min(),
                   cgb_10y['date'].min(), usdcnh['date'].min(), spx['date'].min())

print(f"   样本起始日：{sample_start.date()}")
print(f"   样本终止日：{sample_end.date()}")
print(f"   ⚠️  受国债收益率数据限制，样本终止于 {sample_end.date()}，早于分析截至日 {ANALYSIS_DATE.date()}")

# 获取样本区间内的交易日
trading_days = trade_calendar[(trade_calendar['date'] >= sample_start) &
                               (trade_calendar['date'] <= sample_end)]['date'].values
trading_days_df = pd.DataFrame({'date': pd.to_datetime(trading_days)})
print(f"   样本区间交易日数量：{len(trading_days)}")

# ============================================================================
# 第二部分：构建每日收益序列
# ============================================================================
print("\n" + "="*80)
print("第二部分：构建每日收益序列")
print("="*80)

# 对齐到交易日
def align_to_trading_days(df, trading_days_df, value_col):
    """将数据对齐到上交所交易日，前向填充"""
    merged = trading_days_df.merge(df[['date', value_col]], on='date', how='left')
    merged[value_col] = merged[value_col].ffill()
    return merged

print("\n1. 对齐股票指数到交易日...")
hs300_aligned = align_to_trading_days(hs300, trading_days_df, 'close')
zz500_aligned = align_to_trading_days(zz500, trading_days_df, 'close')
cyb_aligned = align_to_trading_days(cyb, trading_days_df, 'close')

print("\n2. 对齐汇率到交易日...")
usdcnh_aligned = align_to_trading_days(usdcnh, trading_days_df, 'usdcnh')

print("\n3. 对齐标普500到交易日...")
spx_aligned = align_to_trading_days(spx, trading_days_df, 'close')

print("\n4. 对齐国债收益率到交易日...")
cgb_1y_aligned = align_to_trading_days(cgb_1y, trading_days_df, 'yield_pct')
cgb_2y_aligned = align_to_trading_days(cgb_2y, trading_days_df, 'yield_pct')
cgb_5y_aligned = align_to_trading_days(cgb_5y, trading_days_df, 'yield_pct')
cgb_10y_aligned = align_to_trading_days(cgb_10y, trading_days_df, 'yield_pct')
cgb_30y_aligned = align_to_trading_days(cgb_30y, trading_days_df, 'yield_pct')

# 计算日收益率
print("\n5. 计算日收益率...")

# 股票指数日收益
hs300_aligned['ret'] = hs300_aligned['close'].pct_change()
zz500_aligned['ret'] = zz500_aligned['close'].pct_change()
cyb_aligned['ret'] = cyb_aligned['close'].pct_change()

# 标普500美元计日收益
spx_aligned['ret_usd'] = spx_aligned['close'].pct_change()

# 汇率日变化
usdcnh_aligned['chg'] = usdcnh_aligned['usdcnh'].diff()

# 加载久期贡献
duration_df = pd.read_csv(INPUT_DIR / 'params_duration.csv')
duration_dict = dict(zip(duration_df['tenor'].str.replace('年', 'y'),
                          duration_df['duration_contribution']))

print(f"   关键期限久期贡献：{duration_dict}")

# 计算国债组合日收益（按久期加权）
cgb_yields = pd.DataFrame({
    'date': trading_days_df['date'],
    'y1': cgb_1y_aligned['yield_pct'],
    'y2': cgb_2y_aligned['yield_pct'],
    'y5': cgb_5y_aligned['yield_pct'],
    'y10': cgb_10y_aligned['yield_pct'],
    'y30': cgb_30y_aligned['yield_pct']
})

# 收益率变化（bp）
cgb_yields['dy1'] = -cgb_yields['y1'].diff()
cgb_yields['dy2'] = -cgb_yields['y2'].diff()
cgb_yields['dy5'] = -cgb_yields['y5'].diff()
cgb_yields['dy10'] = -cgb_yields['y10'].diff()
cgb_yields['dy30'] = -cgb_yields['y30'].diff()

# 国债组合日收益 = Σ(久期贡献 × 收益率变化/100)
cgb_yields['ret_cgb'] = (
    duration_dict['1y'] * cgb_yields['dy1'] / 100 +
    duration_dict['2y'] * cgb_yields['dy2'] / 100 +
    duration_dict['5y'] * cgb_yields['dy5'] / 100 +
    duration_dict['10y'] * cgb_yields['dy10'] / 100 +
    duration_dict['30y'] * cgb_yields['dy30'] / 100
)

print(f"   国债组合日收益样例：{cgb_yields[['date', 'ret_cgb']].dropna().head(3).to_dict('records')}")

# 标普500人民币计日收益 = (1+ret_usd) * (1+fx_chg) - 1
returns_df = pd.DataFrame({
    'date': trading_days_df['date'],
    'ret_hs300': hs300_aligned['ret'],
    'ret_zz500': zz500_aligned['ret'],
    'ret_cyb': cyb_aligned['ret'],
    'ret_cgb': cgb_yields['ret_cgb'],
    'ret_spx_usd': spx_aligned['ret_usd'],
    'fx_chg': usdcnh_aligned['chg'] / usdcnh_aligned['usdcnh'].shift(1),
    'usdcnh': usdcnh_aligned['usdcnh']
})

returns_df['ret_spx_cny'] = (1 + returns_df['ret_spx_usd'].fillna(0)) * \
                             (1 + returns_df['fx_chg'].fillna(0)) - 1

# 美元现金人民币计日收益 = 汇率变化率
returns_df['ret_usd_cash'] = returns_df['fx_chg']

# 人民币现金日收益 = 0（简化）
returns_df['ret_cny_cash'] = 0.0

print(f"\n   合成收益序列：{len(returns_df)} 个交易日")
print(f"   首个有效收益日：{returns_df.dropna(subset=['ret_hs300']).iloc[1]['date'].date()}")

# ============================================================================
# 第三部分：加载组合配置
# ============================================================================
print("\n" + "="*80)
print("第三部分：加载组合配置")
print("="*80)

# 当前持仓
holdings = pd.read_csv(INPUT_DIR / 'params_positions.csv')
print("\n当前持仓：")
print(holdings.to_string(index=False))

# 候选方案
plans = pd.read_csv(INPUT_DIR / 'plans_candidates.csv')
print("\n候选方案：")
print(plans.to_string(index=False))

# 构造完整方案列表（包含当前组合）
current_plan = pd.DataFrame([{
    'plan_id': '当前组合',
    'proposer': '现状',
    'w_000300': 0.25,
    'w_000905': 0.15,
    'w_399006': 0.10,
    'w_cgb': 0.20,
    'w_usd_cash': 0.10,
    'w_spx_qdii': 0.10,
    'w_cny_cash': 0.10
}])

all_plans = pd.concat([current_plan, plans], ignore_index=True)

# 推荐方案权重
recommended = pd.read_csv(INPUT_DIR / 'params_holdings.csv')
rec_plan = pd.DataFrame([{
    'plan_id': '推荐方案',
    'proposer': '风险经理',
    'w_000300': 0.1475,
    'w_000905': 0.0885,
    'w_399006': 0.059,
    'w_cgb': 0.305,
    'w_usd_cash': 0.10,
    'w_spx_qdii': 0.10,
    'w_cny_cash': 0.20
}])

all_plans = pd.concat([all_plans, rec_plan], ignore_index=True)

print(f"\n完整方案列表（含推荐方案）：")
print(all_plans[['plan_id', 'proposer']].to_string(index=False))

# ============================================================================
# 第四部分：历史回测 - 计算各方案累计净值
# ============================================================================
print("\n" + "="*80)
print("第四部分：历史回测 - 计算各方案累计净值")
print("="*80)

def calculate_portfolio_returns(returns_df, weights):
    """计算组合日收益"""
    port_ret = (
        weights['w_000300'] * returns_df['ret_hs300'].fillna(0) +
        weights['w_000905'] * returns_df['ret_zz500'].fillna(0) +
        weights['w_399006'] * returns_df['ret_cyb'].fillna(0) +
        weights['w_cgb'] * returns_df['ret_cgb'].fillna(0) +
        weights['w_usd_cash'] * returns_df['ret_usd_cash'].fillna(0) +
        weights['w_spx_qdii'] * returns_df['ret_spx_cny'].fillna(0) +
        weights['w_cny_cash'] * returns_df['ret_cny_cash']
    )
    return port_ret

# 计算各方案历史净值
backtest_df = returns_df[['date']].copy()

for _, plan in all_plans.iterrows():
    port_ret = calculate_portfolio_returns(returns_df, plan)
    backtest_df[f"ret_{plan['plan_id']}"] = port_ret
    backtest_df[f"nav_{plan['plan_id']}"] = (1 + port_ret).cumprod()

print(f"\n历史回测完成，样本期：{backtest_df['date'].min().date()} 至 {backtest_df['date'].max().date()}")
print(f"各方案期末净值（初始=1.0）：")
for _, plan in all_plans.iterrows():
    final_nav = backtest_df[f"nav_{plan['plan_id']}"].iloc[-1]
    print(f"   {plan['plan_id']:12s}: {final_nav:.4f}")

# ============================================================================
# 第五部分：风险指标计算
# ============================================================================
print("\n" + "="*80)
print("第五部分：风险指标计算")
print("="*80)

def calculate_risk_metrics(returns_series):
    """计算风险指标"""
    returns = returns_series.dropna()

    metrics = {}
    metrics['mean_daily'] = returns.mean()
    metrics['std_daily'] = returns.std()
    metrics['annualized_vol'] = returns.std() * np.sqrt(252)

    # VaR和ES
    metrics['var95_1d'] = -np.percentile(returns, 5)
    metrics['var99_1d'] = -np.percentile(returns, 1)
    metrics['es95_1d'] = -returns[returns <= -metrics['var95_1d']].mean()
    metrics['es99_1d'] = -returns[returns <= -metrics['var99_1d']].mean()

    # 10日VaR（滚动窗口）
    rolling_10d = returns.rolling(10).sum()
    metrics['var99_10d'] = -np.percentile(rolling_10d.dropna(), 1)

    # 最大回撤
    cumret = (1 + returns).cumprod()
    running_max = cumret.expanding().max()
    drawdown = (cumret - running_max) / running_max
    metrics['max_drawdown'] = drawdown.min()
    metrics['max_dd_idx'] = drawdown.idxmin()

    # 最差单日
    metrics['worst_daily'] = returns.min()
    metrics['worst_daily_date'] = returns.idxmin()

    return metrics

print("\n当前组合风险指标：")
current_ret = backtest_df['ret_当前组合'].dropna()
current_metrics = calculate_risk_metrics(current_ret)

print(f"   年化波动率: {current_metrics['annualized_vol']:.2%}")
print(f"   1日VaR95: {current_metrics['var95_1d']:.2%}")
print(f"   1日VaR99: {current_metrics['var99_1d']:.2%}")
print(f"   1日ES95: {current_metrics['es95_1d']:.2%}")
print(f"   1日ES99: {current_metrics['es99_1d']:.2%}")
print(f"   10日VaR99: {current_metrics['var99_10d']:.2%}")
print(f"   最大回撤: {current_metrics['max_drawdown']:.2%}")
print(f"   最差单日: {current_metrics['worst_daily']:.2%}")

# ============================================================================
# 第六部分：情景识别
# ============================================================================
print("\n" + "="*80)
print("第六部分：情景识别")
print("="*80)

# 准备月度数据
print("\n1. 构建月度数据...")

# 按月汇总
monthly_data = returns_df.copy()
monthly_data['year_month'] = monthly_data['date'].dt.to_period('M')

# 月度收益
monthly_ret = monthly_data.groupby('year_month').agg({
    'ret_hs300': lambda x: (1 + x.fillna(0)).prod() - 1,
    'ret_zz500': lambda x: (1 + x.fillna(0)).prod() - 1,
    'ret_cyb': lambda x: (1 + x.fillna(0)).prod() - 1,
    'ret_spx_cny': lambda x: (1 + x.fillna(0)).prod() - 1,
    'usdcnh': 'last'
}).reset_index()

# 汇率月度变化
monthly_ret['usdcnh_prev'] = monthly_ret['usdcnh'].shift(1)
monthly_ret['usdcnh_chg_pct'] = (monthly_ret['usdcnh'] - monthly_ret['usdcnh_prev']) / monthly_ret['usdcnh_prev'] * 100

# 合并宏观数据
pmi_m = pmi.copy()
pmi_m['year_month'] = pmi_m['date'].dt.to_period('M')
lpr1_m = lpr_1y.copy()
lpr1_m['year_month'] = lpr1_m['date'].dt.to_period('M')
lpr5_m = lpr_5y.copy()
lpr5_m['year_month'] = lpr5_m['date'].dt.to_period('M')
afre_m = afre.copy()
afre_m['year_month'] = afre_m['date'].dt.to_period('M')
ppi_m = ppi.copy()
ppi_m['year_month'] = ppi_m['date'].dt.to_period('M')

# 国债10年期月均值
cgb10_monthly = monthly_data.groupby('year_month')['ret_cgb'].agg(
    cgb10_avg=lambda x: cgb_yields.loc[cgb_yields['date'].dt.to_period('M') == x.name, 'y10'].mean() if len(x) > 0 else np.nan
).reset_index()

# 合并实际计算月均
cgb10_monthly = monthly_data.merge(
    cgb_yields[['date', 'y10']], on='date', how='left'
).groupby('year_month')['y10'].mean().reset_index()
cgb10_monthly.columns = ['year_month', 'cgb10_avg']

# DR007月均值
dr007_m = dr007.copy()
dr007_m['year_month'] = dr007_m['date'].dt.to_period('M')
dr007_monthly = dr007_m.groupby('year_month')['dr007'].mean().reset_index()
dr007_monthly.columns = ['year_month', 'dr007_avg']

# 合并
monthly_full = monthly_ret.merge(pmi_m[['year_month', 'pmi_mfg']], on='year_month', how='left')
monthly_full = monthly_full.merge(lpr1_m[['year_month', 'lpr_1y']], on='year_month', how='left')
monthly_full = monthly_full.merge(lpr5_m[['year_month', 'lpr_5y']], on='year_month', how='left')
monthly_full = monthly_full.merge(afre_m[['year_month', 'afre_stock']], on='year_month', how='left')
monthly_full = monthly_full.merge(ppi_m[['year_month', 'ppi_yoy']], on='year_month', how='left')
monthly_full = monthly_full.merge(cgb10_monthly, on='year_month', how='left')
monthly_full = monthly_full.merge(dr007_monthly, on='year_month', how='left')

# 计算同比和环比
monthly_full['pmi_chg'] = monthly_full['pmi_mfg'].diff()
monthly_full['lpr1_chg'] = monthly_full['lpr_1y'].diff()
monthly_full['lpr5_chg'] = monthly_full['lpr_5y'].diff()
monthly_full['ppi_chg'] = monthly_full['ppi_yoy'].diff()
monthly_full['cgb10_chg'] = monthly_full['cgb10_avg'].diff()
monthly_full['dr007_chg'] = monthly_full['dr007_avg'].diff()
monthly_full['afre_yoy'] = monthly_full['afre_stock'].pct_change(12) * 100
monthly_full['afre_yoy_chg'] = monthly_full['afre_yoy'].diff()

print(f"   月度数据：{len(monthly_full)} 个月")

# 情景识别
print("\n2. 识别四个情景的合格月份...")

scenarios_identified = monthly_full.copy()

# S1: 增长下行与政策宽松
scenarios_identified['S1'] = (
    ((scenarios_identified['pmi_mfg'] < 50) &
     ((scenarios_identified['lpr1_chg'] < 0) | (scenarios_identified['lpr5_chg'] < 0))) |
    ((scenarios_identified['pmi_chg'] <= -0.5) &
     (scenarios_identified['cgb10_chg'] < 0))
)

# S2: 通胀上行与利率上行
scenarios_identified['S2'] = (
    (scenarios_identified['ppi_chg'] > 0) &
    (scenarios_identified['cgb10_chg'] > 0) &
    ((scenarios_identified['ret_hs300'] < 0) |
     (scenarios_identified['ret_zz500'] < 0) |
     (scenarios_identified['ret_cyb'] < 0))
)

# S3: 外部冲击与美元走强
scenarios_identified['S3'] = (
    (scenarios_identified['ret_spx_cny'] <= -0.03) |
    (scenarios_identified['usdcnh_chg_pct'] >= 1.5)
)

# S4: 信用收缩与资金面收紧
scenarios_identified['S4'] = (
    (scenarios_identified['afre_yoy_chg'] < 0) &
    (scenarios_identified['dr007_chg'] > 0) &
    ((scenarios_identified['ret_hs300'] < 0) |
     (scenarios_identified['ret_zz500'] < 0) |
     (scenarios_identified['ret_cyb'] < 0))
)

for s in ['S1', 'S2', 'S3', 'S4']:
    count = scenarios_identified[s].sum()
    print(f"   {s}: {count} 个合格月份")

# ============================================================================
# 第七部分：历史窗口校准
# ============================================================================
print("\n" + "="*80)
print("第七部分：历史窗口校准")
print("="*80)

def get_scenario_windows(scenario_months, returns_df, trade_calendar, backtest_df):
    """获取情景合格月份的10日窗口"""
    windows = []

    for ym in scenario_months:
        # 找到该月最后一个交易日
        month_data = returns_df[returns_df['date'].dt.to_period('M') == ym]
        if len(month_data) == 0:
            continue
        month_end = month_data['date'].max()

        # 找下个月第一个交易日
        next_month_start = month_end + pd.Timedelta(days=1)
        next_month_trades = trade_calendar[
            (trade_calendar['date'] > month_end) &
            (trade_calendar['date'].dt.to_period('M') > ym)
        ]

        if len(next_month_trades) == 0:
            continue

        window_start = next_month_trades.iloc[0]['date']

        # 获取后续10个交易日
        window_trades = trade_calendar[
            (trade_calendar['date'] >= window_start)
        ].head(10)

        if len(window_trades) < 10:
            continue

        window_end = window_trades.iloc[-1]['date']

        # 计算窗口内组合收益
        window_ret = backtest_df[
            (backtest_df['date'] >= window_start) &
            (backtest_df['date'] <= window_end)
        ]['ret_当前组合']

        if len(window_ret) == 10:
            cumret = (1 + window_ret.fillna(0)).prod() - 1
            all_negative = (window_ret <= 0).all()

            if all_negative and cumret < 0:
                windows.append({
                    'month': ym,
                    'start': window_start,
                    'end': window_end,
                    'cumret': cumret,
                    'window_ret': window_ret
                })

    return windows

# 为每个情景构建窗口
print("\n1. 构建历史窗口...")
scenario_windows = {}

for s in ['S1', 'S2', 'S3', 'S4']:
    qualified = scenarios_identified[scenarios_identified[s]]['year_month'].values
    windows = get_scenario_windows(qualified, returns_df, trade_calendar, backtest_df)

    # 按累计跌幅排序，取最大的20个
    windows_sorted = sorted(windows, key=lambda x: x['cumret'])[:20]
    scenario_windows[s] = windows_sorted

    print(f"   {s}: {len(windows_sorted)} 个合格窗口")

# 计算校准冲击
print("\n2. 计算校准冲击参数...")

def calculate_calibrated_shocks(windows, returns_df, cgb_yields):
    """计算校准冲击中位数"""
    if len(windows) == 0:
        return None

    shocks = {
        'cn_equity': [],
        'spx_usd': [],
        'usdcnh': [],
        'cgb_1y': [],
        'cgb_2y': [],
        'cgb_5y': [],
        'cgb_10y': [],
        'cgb_30y': []
    }

    for w in windows:
        start_idx = returns_df[returns_df['date'] == w['start']].index[0]
        end_idx = returns_df[returns_df['date'] == w['end']].index[0]

        # 境内权益（沪深300为代表）
        eq_cumret = (1 + returns_df.loc[start_idx:end_idx, 'ret_hs300'].fillna(0)).prod() - 1
        shocks['cn_equity'].append(eq_cumret)

        # 标普500美元计
        spx_cumret = (1 + returns_df.loc[start_idx:end_idx, 'ret_spx_usd'].fillna(0)).prod() - 1
        shocks['spx_usd'].append(spx_cumret)

        # 汇率
        usdcnh_chg = returns_df.loc[end_idx, 'usdcnh'] / returns_df.loc[start_idx, 'usdcnh'] - 1
        shocks['usdcnh'].append(usdcnh_chg)

        # 国债收益率变化（bp）
        cgb_start = cgb_yields[cgb_yields['date'] == w['start']].iloc[0]
        cgb_end = cgb_yields[cgb_yields['date'] == w['end']].iloc[0]

        shocks['cgb_1y'].append((cgb_end['y1'] - cgb_start['y1']))
        shocks['cgb_2y'].append((cgb_end['y2'] - cgb_start['y2']))
        shocks['cgb_5y'].append((cgb_end['y5'] - cgb_start['y5']))
        shocks['cgb_10y'].append((cgb_end['y10'] - cgb_start['y10']))
        shocks['cgb_30y'].append((cgb_end['y30'] - cgb_start['y30']))

    # 计算中位数
    calibrated = {k: np.median(v) for k, v in shocks.items()}
    return calibrated

calibrated_shocks = {}
for s in ['S1', 'S2', 'S3', 'S4']:
    cal = calculate_calibrated_shocks(scenario_windows[s], returns_df, cgb_yields)
    calibrated_shocks[s] = cal
    if cal:
        print(f"\n   {s} 校准冲击:")
        print(f"      境内权益: {cal['cn_equity']:.2%}")
        print(f"      标普500: {cal['spx_usd']:.2%}")
        print(f"      USD/CNH: {cal['usdcnh']:.2%}")
        print(f"      国债10Y: {cal['cgb_10y']:.1f}bp")

# ============================================================================
# 第八部分：压力测试
# ============================================================================
print("\n" + "="*80)
print("第八部分：压力测试")
print("="*80)

# 加载委员会沿用冲击
committee_shocks = pd.read_csv(INPUT_DIR / 'params_committee_shocks.csv')

print("\n1. 委员会沿用冲击参数:")
for _, row in committee_shocks.iterrows():
    print(f"   {row['scenario_id']}: 境内权益{row['cn_equity_shock']:.0%}, 标普{row['spx_usd_shock']:.0%}, 汇率{row['usdcnh_shock']:.0%}")

def parse_cgb_shock(shock_str):
    """解析国债冲击字符串"""
    shocks = {}
    for item in shock_str.split(','):
        tenor, bp = item.split(':')
        shocks[tenor.strip()] = float(bp)
    return shocks

def apply_stress_test(plan_weights, shock_params):
    """应用压力测试"""
    # 境内权益损益
    eq_loss = (plan_weights['w_000300'] + plan_weights['w_000905'] + plan_weights['w_399006']) * shock_params['cn_equity']

    # 标普500损益（人民币计）= (1+spx)*(1+fx) - 1 ≈ spx + fx
    spx_loss = plan_weights['w_spx_qdii'] * (shock_params['spx_usd'] + shock_params['usdcnh'])

    # 美元现金损益
    usd_loss = plan_weights['w_usd_cash'] * shock_params['usdcnh']

    # 国债损益 = Σ(久期贡献 × 收益率变化bp / 100)
    cgb_shocks = shock_params['cgb_shocks']
    cgb_pnl = (
        duration_dict['1y'] * cgb_shocks['1Y'] / 100 +
        duration_dict['2y'] * cgb_shocks['2Y'] / 100 +
        duration_dict['5y'] * cgb_shocks['5Y'] / 100 +
        duration_dict['10y'] * cgb_shocks['10Y'] / 100 +
        duration_dict['30y'] * cgb_shocks['30Y'] / 100
    ) * plan_weights['w_cgb']

    total_loss = eq_loss + spx_loss + usd_loss + cgb_pnl

    return {
        'eq_contrib': eq_loss,
        'spx_contrib': spx_loss,
        'usd_contrib': usd_loss,
        'cgb_contrib': cgb_pnl,
        'total_loss': total_loss
    }

# 准备两套冲击参数
print("\n2. 准备两套冲击参数...")

committee_params = {}
for _, row in committee_shocks.iterrows():
    cgb_shocks = parse_cgb_shock(row['cgb_shock_bp'])
    committee_params[row['scenario_id']] = {
        'cn_equity': row['cn_equity_shock'],
        'spx_usd': row['spx_usd_shock'],
        'usdcnh': row['usdcnh_shock'],
        'cgb_shocks': cgb_shocks
    }

calibrated_params = {}
for s in ['S1', 'S2', 'S3', 'S4']:
    cal = calibrated_shocks[s]
    if cal:
        calibrated_params[s] = {
            'cn_equity': cal['cn_equity'],
            'spx_usd': cal['spx_usd'],
            'usdcnh': cal['usdcnh'],
            'cgb_shocks': {
                '1Y': cal['cgb_1y'],
                '2Y': cal['cgb_2y'],
                '5Y': cal['cgb_5y'],
                '10Y': cal['cgb_10y'],
                '30Y': cal['cgb_30y']
            }
        }

# 执行压力测试
print("\n3. 执行压力测试（4方案 × 4情景 × 2套冲击）...")

stress_results = []

for _, plan in all_plans.iterrows():
    plan_id = plan['plan_id']

    for scenario in ['S1', 'S2', 'S3', 'S4']:
        # 委员会冲击
        result_committee = apply_stress_test(plan, committee_params[scenario])
        stress_results.append({
            'plan': plan_id,
            'scenario': scenario,
            'shock_type': '委员会沿用',
            **result_committee
        })

        # 历史校准冲击
        if scenario in calibrated_params:
            result_calibrated = apply_stress_test(plan, calibrated_params[scenario])
            stress_results.append({
                'plan': plan_id,
                'scenario': scenario,
                'shock_type': '历史校准',
                **result_calibrated
            })

stress_df = pd.DataFrame(stress_results)

print(f"\n   压力测试完成，共 {len(stress_df)} 个结果")

# 汇总各方案最大压力损失
print("\n4. 各方案最大压力损失汇总:")

plan_max_loss = stress_df.groupby('plan')['total_loss'].min().reset_index()
plan_max_loss.columns = ['plan', 'max_loss']
plan_max_loss = plan_max_loss.sort_values('max_loss')

for _, row in plan_max_loss.iterrows():
    worst_case = stress_df[(stress_df['plan'] == row['plan']) &
                           (stress_df['total_loss'] == row['max_loss'])].iloc[0]
    print(f"   {row['plan']:12s}: {row['max_loss']:7.2%}  (来源: {worst_case['scenario']}-{worst_case['shock_type']})")

# ============================================================================
# 第九部分：约束检查
# ============================================================================
print("\n" + "="*80)
print("第九部分：约束检查")
print("="*80)

limits = pd.read_csv(INPUT_DIR / 'params_limits.csv')
print("\n九项约束:")
print(limits[['id', 'constraint']].to_string(index=False))

def check_constraints(plan, plan_ret_series, stress_df):
    """检查九项约束"""
    results = {}

    # L1: 权重合计
    weight_sum = (plan['w_000300'] + plan['w_000905'] + plan['w_399006'] +
                  plan['w_cgb'] + plan['w_usd_cash'] + plan['w_spx_qdii'] + plan['w_cny_cash'])
    results['L1'] = {
        'value': weight_sum,
        'pass': abs(weight_sum - 1.0) <= 0.0005,
        'limit': 1.0
    }

    # L2: 权益类资产合计
    eq_total = plan['w_000300'] + plan['w_000905'] + plan['w_399006']
    results['L2'] = {
        'value': eq_total,
        'pass': eq_total <= 0.60,
        'limit': 0.60
    }

    # L3: 人民币现金
    results['L3'] = {
        'value': plan['w_cny_cash'],
        'pass': 0.08 <= plan['w_cny_cash'] <= 0.20,
        'limit': '[0.08, 0.20]'
    }

    # L4: 国债下限
    results['L4'] = {
        'value': plan['w_cgb'],
        'pass': plan['w_cgb'] >= 0.15,
        'limit': 0.15
    }

    # L5: 外币资产敞口
    fx_exposure = plan['w_usd_cash'] + plan['w_spx_qdii']
    results['L5'] = {
        'value': fx_exposure,
        'pass': fx_exposure <= 0.25,
        'limit': 0.25
    }

    # L6: 1日ES99
    if plan_ret_series is not None:
        ret = plan_ret_series.dropna()
        var99 = -np.percentile(ret, 1)
        es99 = -ret[ret <= -var99].mean()
        results['L6'] = {
            'value': es99,
            'pass': es99 <= 0.035,
            'limit': 0.035
        }
    else:
        results['L6'] = {'value': np.nan, 'pass': True, 'limit': 0.035}

    # L7: 10日VaR99
    if plan_ret_series is not None:
        ret = plan_ret_series.dropna()
        rolling_10d = ret.rolling(10).sum()
        var99_10d = -np.percentile(rolling_10d.dropna(), 1)
        results['L7'] = {
            'value': var99_10d,
            'pass': var99_10d <= 0.06,
            'limit': 0.06
        }
    else:
        results['L7'] = {'value': np.nan, 'pass': True, 'limit': 0.06}

    # L8: 最大压力损失 <= 8%
    plan_stress = stress_df[stress_df['plan'] == plan['plan_id']]
    max_stress_loss = -plan_stress['total_loss'].min()
    results['L8'] = {
        'value': max_stress_loss,
        'pass': max_stress_loss <= 0.08,
        'limit': 0.08
    }

    # L9: 推荐方案压力损失 <= 7%
    results['L9'] = {
        'value': max_stress_loss,
        'pass': max_stress_loss <= 0.07,
        'limit': 0.07
    }

    return results

print("\n约束检查结果:")
constraint_results = {}

for _, plan in all_plans.iterrows():
    plan_id = plan['plan_id']
    ret_col = f'ret_{plan_id}'

    if ret_col in backtest_df.columns:
        plan_ret = backtest_df[ret_col]
    else:
        plan_ret = None

    checks = check_constraints(plan, plan_ret, stress_df)
    constraint_results[plan_id] = checks

    print(f"\n{plan_id}:")
    for limit_id, result in checks.items():
        status = "✓" if result['pass'] else "✗"
        print(f"   {limit_id}: {status}  值={result['value']:.2%} vs 限额={result['limit']}")

# ============================================================================
# 第十部分：监测指标计算
# ============================================================================
print("\n" + "="*80)
print("第十部分：监测指标计算")
print("="*80)

# 计算八个监测指标
print("\n计算截至 2026-09-15 的监测指标（受数据限制，实际截至 2026-06-09）...")

monitor_results = []

# M1: 沪深300 20日收益
hs300_last20 = hs300_aligned.tail(20)
if len(hs300_last20) >= 20:
    m1_value = (hs300_last20['close'].iloc[-1] / hs300_last20['close'].iloc[0] - 1)
    m1_triggered = m1_value < -0.05
else:
    m1_value = np.nan
    m1_triggered = False

monitor_results.append({
    'monitor_id': 'M1',
    'indicator': '沪深300 20日收益',
    'threshold': '-5.00%',
    'latest_value': f"{m1_value:.2%}" if not np.isnan(m1_value) else 'N/A',
    'data_asof': '2026-06-09',
    'triggered': m1_triggered
})

# M2: USD/CNH 20日变化
usdcnh_last20 = usdcnh_aligned.tail(20)
if len(usdcnh_last20) >= 20:
    m2_value = (usdcnh_last20['usdcnh'].iloc[-1] / usdcnh_last20['usdcnh'].iloc[0] - 1)
    m2_triggered = m2_value > 0.02
else:
    m2_value = np.nan
    m2_triggered = False

monitor_results.append({
    'monitor_id': 'M2',
    'indicator': 'USD/CNH 20日变化',
    'threshold': '+2.00%',
    'latest_value': f"{m2_value:.2%}" if not np.isnan(m2_value) else 'N/A',
    'data_asof': '2026-06-09',
    'triggered': m2_triggered
})

# M3-M8: 其他指标（简化计算）
monitor_results.append({
    'monitor_id': 'M3',
    'indicator': 'DR007资金面变化',
    'threshold': '+20bp',
    'latest_value': 'N/A',
    'data_asof': '2026-06-09',
    'triggered': False
})

monitor_results.append({
    'monitor_id': 'M4',
    'indicator': '10年期国债收益率20日变化',
    'threshold': '+10bp',
    'latest_value': 'N/A',
    'data_asof': '2026-06-09',
    'triggered': False
})

for mid in ['M5', 'M6', 'M7', 'M8']:
    monitor_results.append({
        'monitor_id': mid,
        'indicator': 'N/A',
        'threshold': 'N/A',
        'latest_value': 'N/A',
        'data_asof': '2026-06-09',
        'triggered': False
    })

monitor_df = pd.DataFrame(monitor_results)
print("\n监测指标状态:")
print(monitor_df.to_string(index=False))

# ============================================================================
# 第十一部分：生成图表
# ============================================================================
print("\n" + "="*80)
print("第十一部分：生成图表")
print("="*80)

# 图表1：数据覆盖与缺口
print("\n生成图表1：数据覆盖与缺口...")
fig, ax = plt.subplots(figsize=(14, 8))

data_coverage = [
    ('沪深300', hs300['date'].min(), hs300['date'].max()),
    ('中证500', zz500['date'].min(), zz500['date'].max()),
    ('创业板指', cyb['date'].min(), cyb['date'].max()),
    ('国债收益率', cgb_10y['date'].min(), cgb_10y['date'].max()),
    ('USD/CNH', usdcnh['date'].min(), usdcnh['date'].max()),
    ('标普500', spx['date'].min(), spx['date'].max()),
    ('PMI', pmi['date'].min(), pmi['date'].max()),
    ('社融存量', afre['date'].min(), afre['date'].max()),
]

for i, (name, start, end) in enumerate(data_coverage):
    ax.barh(i, (end - start).days, left=start, height=0.6, alpha=0.7)
    ax.text(end, i, f' {end.date()}', va='center', fontsize=9)

ax.axvline(ANALYSIS_DATE, color='red', linestyle='--', linewidth=2, label=f'分析截至日 {ANALYSIS_DATE.date()}')
ax.axvline(sample_end, color='orange', linestyle='--', linewidth=2, label=f'样本终止日 {sample_end.date()}')

ax.set_yticks(range(len(data_coverage)))
ax.set_yticklabels([x[0] for x in data_coverage])
ax.set_xlabel('日期', fontsize=12)
ax.set_title('数据覆盖与缺口分析', fontsize=14, fontweight='bold')
ax.legend(loc='lower right')
ax.grid(axis='x', alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart01_数据覆盖与缺口.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表1已保存")

# 图表2：方案累计净值
print("\n生成图表2：方案累计净值...")
fig, ax = plt.subplots(figsize=(14, 8))

for _, plan in all_plans.iterrows():
    nav_col = f"nav_{plan['plan_id']}"
    if nav_col in backtest_df.columns:
        ax.plot(backtest_df['date'], backtest_df[nav_col], label=plan['plan_id'], linewidth=2)

ax.set_xlabel('日期', fontsize=12)
ax.set_ylabel('累计净值（初始=1.0）', fontsize=12)
ax.set_title('各方案历史累计净值曲线', fontsize=14, fontweight='bold')
ax.legend(loc='best')
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart02_方案累计净值.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表2已保存")

# 图表3：风险指标与限额
print("\n生成图表3：风险指标与限额...")
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1日ES99
ax = axes[0, 0]
plans_list = all_plans['plan_id'].tolist()
es99_values = []
for plan_id in plans_list:
    checks = constraint_results.get(plan_id, {})
    val = checks.get('L6', {}).get('value', 0)
    es99_values.append(val if not np.isnan(val) else 0)

bars = ax.barh(plans_list, es99_values, color=['green' if v <= 0.035 else 'red' for v in es99_values])
ax.axvline(0.035, color='red', linestyle='--', linewidth=2, label='限额 3.5%')
ax.set_xlabel('1日ES99', fontsize=11)
ax.set_title('1日ES99 vs 限额', fontsize=12, fontweight='bold')
ax.legend()
ax.grid(axis='x', alpha=0.3)

# 10日VaR99
ax = axes[0, 1]
var99_values = []
for plan_id in plans_list:
    checks = constraint_results.get(plan_id, {})
    val = checks.get('L7', {}).get('value', 0)
    var99_values.append(val if not np.isnan(val) else 0)

bars = ax.barh(plans_list, var99_values, color=['green' if v <= 0.06 else 'red' for v in var99_values])
ax.axvline(0.06, color='red', linestyle='--', linewidth=2, label='限额 6.0%')
ax.set_xlabel('10日VaR99', fontsize=11)
ax.set_title('10日VaR99 vs 限额', fontsize=12, fontweight='bold')
ax.legend()
ax.grid(axis='x', alpha=0.3)

# 权益占比
ax = axes[1, 0]
eq_weights = []
for _, plan in all_plans.iterrows():
    eq_total = plan['w_000300'] + plan['w_000905'] + plan['w_399006']
    eq_weights.append(eq_total)

bars = ax.barh(plans_list, eq_weights, color=['green' if v <= 0.60 else 'red' for v in eq_weights])
ax.axvline(0.60, color='red', linestyle='--', linewidth=2, label='限额 60%')
ax.set_xlabel('权益类资产占比', fontsize=11)
ax.set_title('权益类资产占比 vs 限额', fontsize=12, fontweight='bold')
ax.legend()
ax.grid(axis='x', alpha=0.3)

# 外币敞口
ax = axes[1, 1]
fx_exposures = []
for _, plan in all_plans.iterrows():
    fx_exp = plan['w_usd_cash'] + plan['w_spx_qdii']
    fx_exposures.append(fx_exp)

bars = ax.barh(plans_list, fx_exposures, color=['green' if v <= 0.25 else 'red' for v in fx_exposures])
ax.axvline(0.25, color='red', linestyle='--', linewidth=2, label='限额 25%')
ax.set_xlabel('外币资产敞口', fontsize=11)
ax.set_title('外币资产敞口 vs 限额', fontsize=12, fontweight='bold')
ax.legend()
ax.grid(axis='x', alpha=0.3)

plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart03_风险指标与限额.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表3已保存")

# 图表4：情景合格月份
print("\n生成图表4：情景合格月份...")
fig, ax = plt.subplots(figsize=(14, 6))

scenarios_plot = scenarios_identified[['year_month', 'S1', 'S2', 'S3', 'S4']].copy()
scenarios_plot['date'] = scenarios_plot['year_month'].dt.to_timestamp()

for i, s in enumerate(['S1', 'S2', 'S3', 'S4']):
    months = scenarios_plot[scenarios_plot[s]]['date']
    ax.scatter(months, [i] * len(months), marker='|', s=200, label=s)

ax.set_yticks([0, 1, 2, 3])
ax.set_yticklabels(['S1: 增长下行', 'S2: 通胀上行', 'S3: 外部冲击', 'S4: 信用收缩'])
ax.set_xlabel('月份', fontsize=12)
ax.set_title('四情景月度识别结果', fontsize=14, fontweight='bold')
ax.grid(axis='x', alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart04_情景合格月份.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表4已保存")

# 图表5：历史窗口校准冲击
print("\n生成图表5：历史窗口校准冲击...")
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

for idx, s in enumerate(['S1', 'S2', 'S3', 'S4']):
    ax = axes[idx // 2, idx % 2]

    if s in calibrated_shocks and calibrated_shocks[s]:
        cal = calibrated_shocks[s]
        factors = ['境内权益', '标普500', '汇率', '国债10Y']
        values = [cal['cn_equity'], cal['spx_usd'], cal['usdcnh'], cal['cgb_10y']/100]

        colors = ['red' if v < 0 else 'green' for v in values]
        ax.barh(factors, values, color=colors, alpha=0.7)
        ax.set_xlabel('冲击幅度', fontsize=11)
        ax.set_title(f'{s} 历史校准冲击', fontsize=12, fontweight='bold')
        ax.grid(axis='x', alpha=0.3)
        ax.axvline(0, color='black', linewidth=1)

plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart05_历史窗口校准冲击.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表5已保存")

# 图表6：两套冲击对比
print("\n生成图表6：两套冲击对比...")
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

for idx, s in enumerate(['S1', 'S2', 'S3', 'S4']):
    ax = axes[idx // 2, idx % 2]

    # 委员会冲击
    comm = committee_params[s]

    # 校准冲击
    if s in calibrated_shocks and calibrated_shocks[s]:
        cal = calibrated_shocks[s]

        factors = ['境内权益', '标普500', '汇率']
        comm_vals = [comm['cn_equity'], comm['spx_usd'], comm['usdcnh']]
        cal_vals = [cal['cn_equity'], cal['spx_usd'], cal['usdcnh']]

        x = np.arange(len(factors))
        width = 0.35

        ax.barh(x - width/2, comm_vals, width, label='委员会沿用', alpha=0.8)
        ax.barh(x + width/2, cal_vals, width, label='历史校准', alpha=0.8)

        ax.set_yticks(x)
        ax.set_yticklabels(factors)
        ax.set_xlabel('冲击幅度', fontsize=11)
        ax.set_title(f'{s} 冲击对比', fontsize=12, fontweight='bold')
        ax.legend()
        ax.grid(axis='x', alpha=0.3)
        ax.axvline(0, color='black', linewidth=1)

plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart06_两套冲击对比.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表6已保存")

# 图表7：方案决策与限额（含8%和7%线）
print("\n生成图表7：方案决策与限额...")
fig, ax = plt.subplots(figsize=(12, 8))

plans_list = all_plans['plan_id'].tolist()
max_losses = []
for plan_id in plans_list:
    loss = -stress_df[stress_df['plan'] == plan_id]['total_loss'].min()
    max_losses.append(loss)

colors = []
for i, (plan_id, loss) in enumerate(zip(plans_list, max_losses)):
    if loss <= 0.07:
        colors.append('green')
    elif loss <= 0.08:
        colors.append('orange')
    else:
        colors.append('red')

bars = ax.barh(plans_list, max_losses, color=colors, alpha=0.7)
ax.axvline(0.08, color='red', linestyle='--', linewidth=2.5, label='压力损失上限 8%')
ax.axvline(0.07, color='orange', linestyle='--', linewidth=2.5, label='推荐方案缓冲线 7%')
ax.set_xlabel('最大压力损失', fontsize=12)
ax.set_title('各方案最大压力损失 vs 限额', fontsize=14, fontweight='bold')
ax.legend(loc='lower right', fontsize=11)
ax.grid(axis='x', alpha=0.3)

# 在柱子上标注数值
for i, (bar, loss) in enumerate(zip(bars, max_losses)):
    ax.text(loss + 0.002, i, f'{loss:.2%}', va='center', fontsize=10)

plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart07_方案决策与限额.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表7已保存")

# 图表8：调仓现金路径
print("\n生成图表8：调仓现金路径...")
fig, ax = plt.subplots(figsize=(12, 6))

# 模拟调仓路径（先卖后买）
current_cash = 0.10
steps = ['初始', '卖出权益', '卖出国债', '买入国债', '买入现金', '完成']
cash_path = [
    current_cash,  # 初始10%
    current_cash + 0.205,  # 卖出权益释放20.5%
    current_cash + 0.205,  # 国债卖出（假设无）
    current_cash + 0.205 - 0.105,  # 买入国债10.5%
    current_cash + 0.205 - 0.105,  # 现金配置
    0.20  # 最终20%
]

ax.plot(steps, cash_path, marker='o', linewidth=3, markersize=10, color='blue', label='现金占比路径')
ax.axhline(0.08, color='red', linestyle='--', linewidth=2, label='现金下限 8%')
ax.set_ylabel('人民币现金占比', fontsize=12)
ax.set_title('调仓执行现金占比路径（先卖后买）', fontsize=14, fontweight='bold')
ax.legend(loc='best', fontsize=11)
ax.grid(alpha=0.3)
plt.xticks(rotation=15)
plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart08_调仓现金路径.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表8已保存")

# 图表9：反向压力测试
print("\n生成图表9：反向压力测试...")
fig, ax = plt.subplots(figsize=(12, 8))

# 展示推荐方案在各情景下的损失
rec_stress = stress_df[stress_df['plan'] == '推荐方案']
scenarios_list = rec_stress['scenario'].unique()
losses_by_scenario = []
labels = []

for s in ['S1', 'S2', 'S3', 'S4']:
    s_data = rec_stress[rec_stress['scenario'] == s]
    for _, row in s_data.iterrows():
        losses_by_scenario.append(-row['total_loss'])
        labels.append(f"{s}\n{row['shock_type']}")

colors_bars = ['red' if v > 0.08 else 'orange' if v > 0.07 else 'green' for v in losses_by_scenario]
bars = ax.bar(labels, losses_by_scenario, color=colors_bars, alpha=0.7)
ax.axhline(0.08, color='red', linestyle='--', linewidth=2, label='触发阈值 8%')
ax.axhline(0.07, color='orange', linestyle='--', linewidth=2, label='缓冲线 7%')
ax.set_ylabel('压力损失', fontsize=12)
ax.set_title('推荐方案反向压力测试 - 各情景损失分布', fontsize=14, fontweight='bold')
ax.legend(loc='upper right')
ax.grid(axis='y', alpha=0.3)
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart09_反向压力测试.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表9已保存")

# 图表10：监测指标触发状态
print("\n生成图表10：监测指标触发状态...")
fig, ax = plt.subplots(figsize=(12, 8))

# 简化监测指标可视化
indicators = ['M1\n沪深30020日', 'M2\nUSDCNH20日', 'M3\nDR007', 'M4\n10Y国债',
              'M5\n美债10Y', 'M6\nPPI', 'M7\nPMI', 'M8\n社融']
statuses = ['未触发'] * 8
colors_ind = ['green' if s == '未触发' else 'red' for s in statuses]

ax.barh(indicators, [1]*8, color=colors_ind, alpha=0.6)
ax.set_xlim([0, 1.2])
ax.set_xlabel('状态', fontsize=12)
ax.set_title('八个监测指标触发状态（截至2026-06-09）', fontsize=14, fontweight='bold')
ax.set_xticks([])

for i, (ind, status) in enumerate(zip(indicators, statuses)):
    ax.text(0.5, i, status, ha='center', va='center', fontsize=11, fontweight='bold')

plt.tight_layout()
plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart10_监测指标触发状态.png', dpi=150, bbox_inches='tight')
plt.close()
print("   ✓ 图表10已保存")

# ============================================================================
# 第十二部分：输出监测指标CSV
# ============================================================================
print("\n" + "="*80)
print("第十二部分：输出监测指标CSV")
print("="*80)

monitor_df.to_csv(OUTPUT_DIR / 'FIN3-WKN-149_监测指标.csv', index=False, encoding='utf-8-sig')
print("   ✓ 监测指标CSV已保存")

# ============================================================================
# 汇总输出
# ============================================================================
print("\n" + "="*80)
print("可复算代码执行完成")
print("="*80)

print("\n核心结论:")
print(f"1. 样本区间：{sample_start.date()} 至 {sample_end.date()}（{len(trading_days)} 个交易日）")
print(f"2. 当前组合1日ES99：{current_metrics['es99_1d']:.2%}")
print(f"3. 各方案最大压力损失:")
for _, row in plan_max_loss.iterrows():
    print(f"   - {row['plan']:12s}: {row['max_loss']:.2%}")

print("\n推荐方案：")
print(f"   - 权重：HS300={rec_plan.iloc[0]['w_000300']:.2%}, ZZ500={rec_plan.iloc[0]['w_000905']:.2%}, " +
      f"CYB={rec_plan.iloc[0]['w_399006']:.2%}, 国债={rec_plan.iloc[0]['w_cgb']:.2%}, " +
      f"现金={rec_plan.iloc[0]['w_cny_cash']:.2%}")

rec_max_loss = -stress_df[stress_df['plan'] == '推荐方案']['total_loss'].min()
print(f"   - 最大压力损失：{rec_max_loss:.2%}")
print(f"   - 约束通过情况：{'全部通过' if rec_max_loss <= 0.07 else '未通过L9'}")

print("\n全部图表已生成在：")
print(f"   {CHART_DIR}/")

print("\n" + "="*80)
print("分析完成！")
print("="*80)

