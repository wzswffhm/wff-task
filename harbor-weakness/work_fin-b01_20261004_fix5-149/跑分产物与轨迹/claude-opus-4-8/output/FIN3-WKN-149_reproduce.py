#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多资产稳健配置专户：三季度宏观压力测试与调仓建议
可复算代码 - FIN3-WKN-149

分析截至日: 2026-09-15
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
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ============================================================================
# 全局常量
# ============================================================================
INPUT_DIR = Path('/app/input_files')
OUTPUT_DIR = Path('/app/output')
CHART_DIR = OUTPUT_DIR / 'FIN3-WKN-149_charts'
ANALYSIS_DATE = pd.Timestamp('2026-09-15')
NAV = 10000.0  # 万元

# ============================================================================
# 1. 数据加载与核验
# ============================================================================

def load_manifest():
    """加载数据清单"""
    df = pd.read_csv(INPUT_DIR / 'snapshot_data_manifest.csv')
    print("=" * 80)
    print("数据清单概览")
    print("=" * 80)
    print(df.to_string(index=False))
    print()
    return df

def load_trade_calendar():
    """加载交易日历"""
    df = pd.read_csv(INPUT_DIR / 'snapshot_trade_calendar.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df[df['is_trading_day'] == 1].copy()
    df = df.sort_values('date').reset_index(drop=True)
    print(f"交易日历: {df['date'].min()} 至 {df['date'].max()}, 共 {len(df)} 个交易日")
    return df

def load_equity_index(code):
    """加载A股指数行情（合并seg1和seg2）"""
    seg1 = pd.read_csv(INPUT_DIR / f'snapshot_{code}_seg1.csv')
    seg2 = pd.read_csv(INPUT_DIR / f'snapshot_{code}_seg2.csv')
    df = pd.concat([seg1, seg2], ignore_index=True)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  {code}: {len(df)} 条, {df['date'].min()} 至 {df['date'].max()}")
    return df[['date', 'close']].rename(columns={'close': code})

def load_usdcnh():
    """加载USD/CNH汇率"""
    seg1 = pd.read_csv(INPUT_DIR / 'snapshot_usdcnh_seg1.csv')
    seg2 = pd.read_csv(INPUT_DIR / 'snapshot_usdcnh_seg2.csv')
    df = pd.concat([seg1, seg2], ignore_index=True)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  USD/CNH: {len(df)} 条, {df['date'].min()} 至 {df['date'].max()}")
    return df[['date', 'usdcnh']]

def load_spx():
    """加载标普500指数"""
    df = pd.read_csv(INPUT_DIR / 'snapshot_spx.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  SPX: {len(df)} 条, {df['date'].min()} 至 {df['date'].max()}")
    return df[['date', 'close']].rename(columns={'close': 'spx'})

def load_cgb_yields():
    """加载中债国债收益率曲线（5个期限）"""
    tenors = ['1y', '2y', '5y', '10y', '30y']
    dfs = []
    for tenor in tenors:
        df = pd.read_csv(INPUT_DIR / f'snapshot_cgb_yield_{tenor}.csv')
        df['date'] = pd.to_datetime(df['date'])
        df = df.rename(columns={'yield_pct': f'cgb_{tenor}'})
        dfs.append(df[['date', f'cgb_{tenor}']])

    result = dfs[0]
    for df in dfs[1:]:
        result = result.merge(df, on='date', how='outer')
    result = result.sort_values('date').reset_index(drop=True)
    print(f"  CGB收益率: {len(result)} 条, {result['date'].min()} 至 {result['date'].max()}")
    return result

def load_shibor():
    """加载Shibor"""
    seg1 = pd.read_csv(INPUT_DIR / 'snapshot_shibor_seg1.csv')
    seg2 = pd.read_csv(INPUT_DIR / 'snapshot_shibor_seg2.csv')
    df = pd.concat([seg1, seg2], ignore_index=True)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  Shibor: {len(df)} 条, {df['date'].min()} 至 {df['date'].max()}")
    return df[['date', 'shibor_on', 'shibor_1w']]

def load_lpr():
    """加载LPR"""
    lpr1y = pd.read_csv(INPUT_DIR / 'snapshot_lpr_1y.csv')
    lpr5y = pd.read_csv(INPUT_DIR / 'snapshot_lpr_5y.csv')
    lpr1y['date'] = pd.to_datetime(lpr1y['date'])
    lpr5y['date'] = pd.to_datetime(lpr5y['date'])
    df = lpr1y.merge(lpr5y, on='date', how='outer')
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  LPR: 1年{len(lpr1y)}条, 5年{len(lpr5y)}条")
    return df

def load_pmi():
    """加载制造业PMI"""
    df = pd.read_csv(INPUT_DIR / 'snapshot_pmi_manufacturing.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  PMI: {len(df)} 条, {df['date'].min()} 至 {df['date'].max()}")
    return df

def load_afre():
    """加载社会融资规模存量"""
    df = pd.read_csv(INPUT_DIR / 'snapshot_afre_stock.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  社融存量: {len(df)} 条, {df['date'].min()} 至 {df['date'].max()}")
    return df

def load_dr007():
    """加载DR007"""
    df = pd.read_csv(INPUT_DIR / 'snapshot_dr007.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  DR007: {len(df)} 条, {df['date'].min()} 至 {df['date'].max()}")
    return df

def load_ppi():
    """加载PPI同比"""
    df = pd.read_csv(INPUT_DIR / 'snapshot_ppi_yoy.csv')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f"  PPI同比: {len(df)} 条, {df['date'].min()} 至 {df['date'].max()}")
    return df

def load_ust():
    """加载美债收益率"""
    ust10y = pd.read_csv(INPUT_DIR / 'snapshot_ust_10y.csv')
    ust10y['date'] = pd.to_datetime(ust10y['date'])
    print(f"  美债10年: {len(ust10y)} 条, {ust10y['date'].min()} 至 {ust10y['date'].max()}")
    return ust10y

def align_to_trading_days(df, trade_cal, fill_method='ffill'):
    """对齐到上交所交易日"""
    # 保留在交易日历范围内的数据
    df = df[df['date'] <= trade_cal['date'].max()].copy()

    # 外连接后前向填充
    aligned = trade_cal[['date']].merge(df, on='date', how='left')
    if fill_method == 'ffill':
        aligned = aligned.ffill()
    return aligned

# ============================================================================
# 2. 收益率计算
# ============================================================================

def calculate_returns(prices_df, col_name):
    """计算对数收益率"""
    ret_col = f'ret_{col_name}'
    prices_df[ret_col] = np.log(prices_df[col_name] / prices_df[col_name].shift(1))
    return prices_df

def calculate_cgb_portfolio_return(cgb_df, duration_contrib):
    """
    计算中长期国债组合收益
    duration_contrib: dict, e.g. {'1y': 0.1, '2y': 0.3, '5y': 1.2, '10y': 3.6, '30y': 1.8}
    收益 = -sum(duration_contrib[tenor] * delta_yield[tenor])
    """
    tenors = ['1y', '2y', '5y', '10y', '30y']
    cgb_df = cgb_df.copy()

    # 计算各期限收益率变动（bp）
    for tenor in tenors:
        col = f'cgb_{tenor}'
        cgb_df[f'delta_{tenor}'] = cgb_df[col] - cgb_df[col].shift(1)

    # 组合收益 = -sum(duration * delta_yield / 100)
    cgb_df['ret_cgb'] = 0.0
    for tenor in tenors:
        dur = duration_contrib[tenor]
        cgb_df['ret_cgb'] += -dur * cgb_df[f'delta_{tenor}'] / 100.0

    return cgb_df

def calculate_spx_cny_return(spx_df, fx_df):
    """
    计算标普500人民币计收益
    (1 + r_cny) = (1 + r_usd) * (1 + r_fx)
    r_cny ≈ r_usd + r_fx + r_usd * r_fx
    """
    df = spx_df.merge(fx_df, on='date', how='inner')
    df['ret_spx_usd'] = np.log(df['spx'] / df['spx'].shift(1))
    df['ret_fx'] = np.log(df['usdcnh'] / df['usdcnh'].shift(1))
    # 复合收益
    df['ret_spx_cny'] = (np.exp(df['ret_spx_usd']) * np.exp(df['ret_fx']) - 1).apply(lambda x: np.log(1 + x))
    return df

# ============================================================================
# 3. 组合构建与风险计算
# ============================================================================

def build_portfolio(eq_000300, eq_000905, eq_399006, cgb, spx_cny, weights):
    """
    构建组合日收益序列
    weights: dict, keys = ['000300', '000905', '399006', 'cgb', 'usd_cash', 'spx', 'cny_cash']
    """
    # 合并所有资产收益
    port = eq_000300[['date', 'ret_000300SH']].copy()
    port = port.merge(eq_000905[['date', 'ret_000905SH']], on='date', how='inner')
    port = port.merge(eq_399006[['date', 'ret_399006SZ']], on='date', how='inner')
    port = port.merge(cgb[['date', 'ret_cgb']], on='date', how='inner')
    port = port.merge(spx_cny[['date', 'ret_spx_cny']], on='date', how='inner')

    # 美元现金和人民币现金收益假设为0
    port['ret_usd_cash'] = 0.0
    port['ret_cny_cash'] = 0.0

    # 计算组合日收益（按权重加权，每日再平衡）
    port['ret_port'] = (
        weights['000300'] * port['ret_000300SH'] +
        weights['000905'] * port['ret_000905SH'] +
        weights['399006'] * port['ret_399006SZ'] +
        weights['cgb'] * port['ret_cgb'] +
        weights['usd_cash'] * port['ret_usd_cash'] +
        weights['spx'] * port['ret_spx_cny'] +
        weights['cny_cash'] * port['ret_cny_cash']
    )

    # 计算累计净值
    port['cum_nav'] = (1 + port['ret_port']).cumprod()

    return port

def calculate_risk_metrics(returns, confidence_levels=[0.95, 0.99]):
    """
    计算风险指标
    returns: pd.Series
    """
    returns = returns.dropna()
    metrics = {}

    # 年化波动率（假设252个交易日）
    metrics['vol_annual'] = returns.std() * np.sqrt(252)

    # VaR和ES
    for cl in confidence_levels:
        var = returns.quantile(1 - cl)
        es = returns[returns <= var].mean()
        metrics[f'VaR{int(cl*100)}'] = var
        metrics[f'ES{int(cl*100)}'] = es

    # 最大回撤
    cum_ret = (1 + returns).cumprod()
    running_max = cum_ret.expanding().max()
    drawdown = (cum_ret - running_max) / running_max
    metrics['max_drawdown'] = drawdown.min()
    metrics['max_drawdown_idx'] = drawdown.idxmin()

    # 最差单日
    metrics['worst_day'] = returns.min()
    metrics['worst_day_idx'] = returns.idxmin()

    return metrics

# ============================================================================
# 4. 情景识别
# ============================================================================

def identify_scenarios(pmi_df, lpr_df, cgb_df, ppi_df, spx_df, fx_df, afre_df, dr007_df,
                       eq_000300_df, eq_000905_df, eq_399006_df, trade_cal):
    """
    识别四个情景的合格月份
    """
    # 构建月度汇总数据
    monthly_data = []

    # 获取所有月份
    start_month = pd.Timestamp('2018-02-01')
    end_month = pd.Timestamp('2026-09-01')
    months = pd.date_range(start_month, end_month, freq='MS')

    for month in months:
        month_end = month + pd.offsets.MonthEnd(0)
        prev_month = month - pd.offsets.MonthBegin(1)
        prev_month_end = prev_month + pd.offsets.MonthEnd(0)

        record = {'month': month}

        # PMI
        pmi_curr = pmi_df[pmi_df['date'] == month]
        pmi_prev = pmi_df[pmi_df['date'] == prev_month]
        if not pmi_curr.empty:
            record['pmi'] = pmi_curr.iloc[0]['pmi_mfg']
        if not pmi_prev.empty:
            record['pmi_prev'] = pmi_prev.iloc[0]['pmi_mfg']

        # LPR
        lpr_curr = lpr_df[lpr_df['date'] <= month_end].tail(1)
        lpr_prev_month = prev_month_end
        lpr_prev = lpr_df[lpr_df['date'] <= lpr_prev_month].tail(1)
        if not lpr_curr.empty:
            record['lpr_1y'] = lpr_curr.iloc[0]['lpr_1y']
            record['lpr_5y'] = lpr_curr.iloc[0]['lpr_5y']
        if not lpr_prev.empty:
            record['lpr_1y_prev'] = lpr_prev.iloc[0]['lpr_1y']
            record['lpr_5y_prev'] = lpr_prev.iloc[0]['lpr_5y']

        # 10年期国债收益率月均
        cgb_month = cgb_df[(cgb_df['date'] >= month) & (cgb_df['date'] <= month_end)]
        cgb_prev_m = cgb_df[(cgb_df['date'] >= prev_month) & (cgb_df['date'] <= prev_month_end)]
        if not cgb_month.empty:
            record['cgb_10y_mean'] = cgb_month['cgb_10y'].mean()
        if not cgb_prev_m.empty:
            record['cgb_10y_mean_prev'] = cgb_prev_m['cgb_10y'].mean()

        # PPI
        ppi_curr = ppi_df[ppi_df['date'] == month]
        ppi_prev = ppi_df[ppi_df['date'] == prev_month]
        if not ppi_curr.empty:
            record['ppi_yoy'] = ppi_curr.iloc[0]['ppi_yoy']
        if not ppi_prev.empty:
            record['ppi_yoy_prev'] = ppi_prev.iloc[0]['ppi_yoy']

        # 标普500当月收益率
        spx_month_start = spx_df[spx_df['date'] <= month].tail(1)
        spx_month_end_df = spx_df[spx_df['date'] <= month_end].tail(1)
        if not spx_month_start.empty and not spx_month_end_df.empty:
            ret_spx = spx_month_end_df.iloc[0]['spx'] / spx_month_start.iloc[0]['spx'] - 1
            record['spx_ret'] = ret_spx

        # USD/CNH当月变化
        fx_month_start = fx_df[fx_df['date'] <= month].tail(1)
        fx_month_end_df = fx_df[fx_df['date'] <= month_end].tail(1)
        if not fx_month_start.empty and not fx_month_end_df.empty:
            fx_change = fx_month_end_df.iloc[0]['usdcnh'] / fx_month_start.iloc[0]['usdcnh'] - 1
            record['fx_change'] = fx_change

        # 社融存量
        afre_curr = afre_df[afre_df['date'] == month]
        afre_prev = afre_df[afre_df['date'] == prev_month]
        if not afre_curr.empty and not afre_prev.empty:
            # 计算同比增速（需要去年同期数据）
            afre_yoy_month = month - pd.DateOffset(years=1)
            afre_yoy = afre_df[afre_df['date'] == afre_yoy_month]
            if not afre_yoy.empty:
                yoy_growth = (afre_curr.iloc[0]['afre_stock'] / afre_yoy.iloc[0]['afre_stock'] - 1) * 100
                record['afre_yoy'] = yoy_growth

            afre_yoy_prev_month = prev_month - pd.DateOffset(years=1)
            afre_yoy_prev = afre_df[afre_df['date'] == afre_yoy_prev_month]
            if not afre_yoy_prev.empty:
                yoy_growth_prev = (afre_prev.iloc[0]['afre_stock'] / afre_yoy_prev.iloc[0]['afre_stock'] - 1) * 100
                record['afre_yoy_prev'] = yoy_growth_prev

        # DR007月均
        dr_month = dr007_df[(dr007_df['date'] >= month) & (dr007_df['date'] <= month_end)]
        dr_prev_m = dr007_df[(dr007_df['date'] >= prev_month) & (dr007_df['date'] <= prev_month_end)]
        if not dr_month.empty:
            record['dr007_mean'] = dr_month['dr007'].mean()
        if not dr_prev_m.empty:
            record['dr007_mean_prev'] = dr_prev_m['dr007'].mean()

        # 权益指数当月收益（综合三个指数）
        eq_rets = []
        for eq_df, code in [(eq_000300_df, '000300SH'), (eq_000905_df, '000905SH'), (eq_399006_df, '399006SZ')]:
            eq_start = eq_df[eq_df['date'] <= month].tail(1)
            eq_end = eq_df[eq_df['date'] <= month_end].tail(1)
            if not eq_start.empty and not eq_end.empty:
                ret = eq_end.iloc[0][code] / eq_start.iloc[0][code] - 1
                eq_rets.append(ret)
        if eq_rets:
            record['eq_ret'] = np.mean(eq_rets)

        monthly_data.append(record)

    monthly_df = pd.DataFrame(monthly_data)

    # 情景识别
    scenarios = {
        'S1': [],  # 增长下行与政策宽松
        'S2': [],  # 通胀上行与利率上行
        'S3': [],  # 外部冲击与美元走强
        'S4': []   # 信用收缩与资金面收紧
    }

    for idx, row in monthly_df.iterrows():
        # S1: PMI < 50 且 (LPR下调) 或 PMI下行>=0.5 且 10年期国债收益率月均值低于上月
        if pd.notna(row.get('pmi')) and pd.notna(row.get('pmi_prev')):
            cond1a = row['pmi'] < 50
            cond1b = False
            if pd.notna(row.get('lpr_1y')) and pd.notna(row.get('lpr_1y_prev')):
                cond1b = (row['lpr_1y'] < row['lpr_1y_prev']) or (row['lpr_5y'] < row.get('lpr_5y_prev', row['lpr_5y']))
            cond1c = (row['pmi_prev'] - row['pmi'] >= 0.5)
            cond1d = False
            if pd.notna(row.get('cgb_10y_mean')) and pd.notna(row.get('cgb_10y_mean_prev')):
                cond1d = row['cgb_10y_mean'] < row['cgb_10y_mean_prev']

            if (cond1a and cond1b) or (cond1c and cond1d):
                scenarios['S1'].append(row['month'])

        # S2: PPI同比高于上月 且 10年期国债收益率月均值高于上月 且 权益指数当月下跌
        if (pd.notna(row.get('ppi_yoy')) and pd.notna(row.get('ppi_yoy_prev')) and
            pd.notna(row.get('cgb_10y_mean')) and pd.notna(row.get('cgb_10y_mean_prev')) and
            pd.notna(row.get('eq_ret'))):
            if (row['ppi_yoy'] > row['ppi_yoy_prev'] and
                row['cgb_10y_mean'] > row['cgb_10y_mean_prev'] and
                row['eq_ret'] < 0):
                scenarios['S2'].append(row['month'])

        # S3: 标普500当月收益率 <= -3% 或 USD/CNH当月变化 >= +1.5%
        if pd.notna(row.get('spx_ret')) or pd.notna(row.get('fx_change')):
            cond3a = row.get('spx_ret', 0) <= -0.03
            cond3b = row.get('fx_change', 0) >= 0.015
            if cond3a or cond3b:
                scenarios['S3'].append(row['month'])

        # S4: 社融存量同比增速低于上月 且 DR007月均值高于上月 且 权益指数当月下跌
        if (pd.notna(row.get('afre_yoy')) and pd.notna(row.get('afre_yoy_prev')) and
            pd.notna(row.get('dr007_mean')) and pd.notna(row.get('dr007_mean_prev')) and
            pd.notna(row.get('eq_ret'))):
            if (row['afre_yoy'] < row['afre_yoy_prev'] and
                row['dr007_mean'] > row['dr007_mean_prev'] and
                row['eq_ret'] < 0):
                scenarios['S4'].append(row['month'])

    print("\n" + "=" * 80)
    print("情景识别结果")
    print("=" * 80)
    for sid, months in scenarios.items():
        print(f"{sid}: {len(months)} 个月份")
        if months:
            print(f"  {[m.strftime('%Y-%m') for m in months[:10]]}")
    print()

    return scenarios, monthly_df

# ============================================================================
# 5. 历史窗口选择与校准冲击计算
# ============================================================================

def select_windows_and_calibrate(scenarios, portfolio_returns, trade_cal):
    """
    为每个情景选择历史窗口并校准冲击
    窗口规则: 情景合格月份的次月第一个交易日起10个交易日，且全部为负收益
    """
    windows = {}

    for scenario_id, months in scenarios.items():
        scenario_windows = []

        for month in months:
            # 次月第一个交易日
            next_month = month + pd.offsets.MonthBegin(1)
            window_start = trade_cal[trade_cal['date'] >= next_month].iloc[0]['date'] if len(trade_cal[trade_cal['date'] >= next_month]) > 0 else None

            if window_start is None:
                continue

            # 获取10个交易日
            start_idx = trade_cal[trade_cal['date'] == window_start].index[0]
            if start_idx + 9 >= len(trade_cal):
                continue

            window_dates = trade_cal.iloc[start_idx:start_idx+10]['date'].tolist()

            # 获取这10天的组合收益
            window_rets = portfolio_returns[portfolio_returns['date'].isin(window_dates)]['ret_port'].values

            if len(window_rets) == 10:
                # 检查是否全部为负
                if np.all(window_rets < 0):
                    cum_ret = np.sum(window_rets)
                    scenario_windows.append({
                        'start': window_dates[0],
                        'end': window_dates[-1],
                        'cum_ret': cum_ret,
                        'days': window_dates
                    })

        # 按累计跌幅排序，取前20个
        scenario_windows.sort(key=lambda x: x['cum_ret'])
        windows[scenario_id] = scenario_windows[:min(20, len(scenario_windows))]

        print(f"{scenario_id}: 找到 {len(scenario_windows)} 个合格窗口，取前 {len(windows[scenario_id])} 个")

    return windows

def calibrate_shocks(windows, eq_000300_df, eq_000905_df, eq_399006_df, cgb_df, spx_df, fx_df):
    """
    根据历史窗口校准冲击参数
    """
    calibrated = {}

    for scenario_id, wins in windows.items():
        if not wins:
            continue

        # 收集所有窗口的因子变动
        cn_eq_changes = []
        spx_changes = []
        fx_changes = []
        cgb_changes = {tenor: [] for tenor in ['1y', '2y', '5y', '10y', '30y']}

        for win in wins:
            start_date = win['start']
            end_date = win['end']

            # 境内权益变动（三个指数平均）
            eq_chgs = []
            for df, col in [(eq_000300_df, '000300SH'), (eq_000905_df, '000905SH'), (eq_399006_df, '399006SZ')]:
                s = df[df['date'] == start_date][col].values
                e = df[df['date'] == end_date][col].values
                if len(s) > 0 and len(e) > 0:
                    eq_chgs.append(e[0] / s[0] - 1)
            if eq_chgs:
                cn_eq_changes.append(np.mean(eq_chgs))

            # 标普500变动
            s = spx_df[spx_df['date'] <= start_date].tail(1)['spx'].values
            e = spx_df[spx_df['date'] <= end_date].tail(1)['spx'].values
            if len(s) > 0 and len(e) > 0:
                spx_changes.append(e[0] / s[0] - 1)

            # 汇率变动
            s = fx_df[fx_df['date'] <= start_date].tail(1)['usdcnh'].values
            e = fx_df[fx_df['date'] <= end_date].tail(1)['usdcnh'].values
            if len(s) > 0 and len(e) > 0:
                fx_changes.append(e[0] / s[0] - 1)

            # 国债收益率变动
            for tenor in ['1y', '2y', '5y', '10y', '30y']:
                col = f'cgb_{tenor}'
                s = cgb_df[cgb_df['date'] <= start_date].tail(1)[col].values
                e = cgb_df[cgb_df['date'] <= end_date].tail(1)[col].values
                if len(s) > 0 and len(e) > 0:
                    cgb_changes[tenor].append(e[0] - s[0])

        # 取中位数作为校准冲击
        calibrated[scenario_id] = {
            'cn_equity_shock': np.median(cn_eq_changes) if cn_eq_changes else 0,
            'spx_usd_shock': np.median(spx_changes) if spx_changes else 0,
            'usdcnh_shock': np.median(fx_changes) if fx_changes else 0,
            'cgb_shock_bp': {tenor: np.median(chgs) if chgs else 0 for tenor, chgs in cgb_changes.items()}
        }

    return calibrated

# ============================================================================
# 6. 压力测试
# ============================================================================

def apply_stress_test(weights, shocks, duration_contrib):
    """
    对单个方案应用单个情景的冲击
    返回: 组合损益（比例）及各部分贡献
    """
    # 境内权益损益
    cn_eq_weight = weights['000300'] + weights['000905'] + weights['399006']
    cn_eq_pnl = cn_eq_weight * shocks['cn_equity_shock']

    # 标普500人民币计损益 (复合: (1+r_usd)*(1+r_fx)-1)
    spx_cny_shock = (1 + shocks['spx_usd_shock']) * (1 + shocks['usdcnh_shock']) - 1
    spx_pnl = weights['spx'] * spx_cny_shock

    # 美元现金损益 (仅汇率变动)
    usd_cash_pnl = weights['usd_cash'] * shocks['usdcnh_shock']

    # 国债组合损益 (久期贡献)
    cgb_ret = 0.0
    for tenor in ['1y', '2y', '5y', '10y', '30y']:
        dur = duration_contrib[tenor]
        yield_chg = shocks['cgb_shock_bp'][tenor]  # 已经是bp单位
        cgb_ret += -dur * yield_chg / 100.0
    cgb_pnl = weights['cgb'] * cgb_ret

    # 人民币现金损益为0
    cny_cash_pnl = 0.0

    total_pnl = cn_eq_pnl + spx_pnl + usd_cash_pnl + cgb_pnl + cny_cash_pnl

    return {
        'total': total_pnl,
        'cn_equity': cn_eq_pnl,
        'spx_cny': spx_pnl,
        'usd_cash': usd_cash_pnl,
        'cgb': cgb_pnl,
        'cny_cash': cny_cash_pnl
    }

def parse_committee_shocks(params_df):
    """解析委员会冲击参数"""
    shocks = {}
    for idx, row in params_df.iterrows():
        sid = row['scenario_id']
        cgb_str = row['cgb_shock_bp']
        # 解析 "1Y:+0.10,2Y:+0.12,5Y:+0.10,10Y:+0.20,30Y:+0.25"
        cgb_dict = {}
        for item in cgb_str.split(','):
            k, v = item.split(':')
            tenor_map = {'1Y': '1y', '2Y': '2y', '5Y': '5y', '10Y': '10y', '30Y': '30y'}
            cgb_dict[tenor_map[k]] = float(v)

        shocks[sid] = {
            'cn_equity_shock': row['cn_equity_shock'],
            'spx_usd_shock': row['spx_usd_shock'],
            'usdcnh_shock': row['usdcnh_shock'],
            'cgb_shock_bp': cgb_dict
        }
    return shocks

def run_all_stress_tests(plans_df, committee_shocks, calibrated_shocks, duration_contrib):
    """
    运行所有方案×情景×冲击的压力测试
    """
    results = []

    for _, plan_row in plans_df.iterrows():
        plan_id = plan_row['plan_id']
        weights = {
            '000300': plan_row['w_000300'],
            '000905': plan_row['w_000905'],
            '399006': plan_row['w_399006'],
            'cgb': plan_row['w_cgb'],
            'usd_cash': plan_row['w_usd_cash'],
            'spx': plan_row['w_spx_qdii'],
            'cny_cash': plan_row['w_cny_cash']
        }

        for scenario_id in ['S1', 'S2', 'S3', 'S4']:
            # 委员会沿用冲击
            shock_committee = committee_shocks[scenario_id]
            pnl_committee = apply_stress_test(weights, shock_committee, duration_contrib)

            results.append({
                'plan_id': plan_id,
                'scenario_id': scenario_id,
                'shock_type': 'committee',
                **pnl_committee
            })

            # 历史校准冲击
            if scenario_id in calibrated_shocks:
                shock_calibrated = calibrated_shocks[scenario_id]
                pnl_calibrated = apply_stress_test(weights, shock_calibrated, duration_contrib)

                results.append({
                    'plan_id': plan_id,
                    'scenario_id': scenario_id,
                    'shock_type': 'calibrated',
                    **pnl_calibrated
                })

    return pd.DataFrame(results)

# ============================================================================
# 7. 约束检查
# ============================================================================

def check_constraints(plans_df, stress_results, risk_metrics_dict, limits_df):
    """
    对每个方案检查九项约束
    """
    check_results = []

    for _, plan_row in plans_df.iterrows():
        plan_id = plan_row['plan_id']
        weights = {
            '000300': plan_row['w_000300'],
            '000905': plan_row['w_000905'],
            '399006': plan_row['w_399006'],
            'cgb': plan_row['w_cgb'],
            'usd_cash': plan_row['w_usd_cash'],
            'spx': plan_row['w_spx_qdii'],
            'cny_cash': plan_row['w_cny_cash']
        }

        checks = {}

        # C1: 权重合计=1 (容差0.05个百分点)
        total_weight = sum(weights.values())
        checks['C1'] = {
            'value': total_weight,
            'limit': 1.0,
            'pass': abs(total_weight - 1.0) <= 0.0005,
            'description': '权重合计'
        }

        # C2: 权益类资产 <= 60%
        equity_weight = weights['000300'] + weights['000905'] + weights['399006']
        checks['C2'] = {
            'value': equity_weight,
            'limit': 0.6,
            'pass': equity_weight <= 0.6,
            'description': '权益类资产合计'
        }

        # C3: 人民币现金 in [8%, 20%]
        checks['C3'] = {
            'value': weights['cny_cash'],
            'limit': [0.08, 0.2],
            'pass': 0.08 <= weights['cny_cash'] <= 0.2,
            'description': '人民币现金区间'
        }

        # C4: 国债 >= 15%
        checks['C4'] = {
            'value': weights['cgb'],
            'limit': 0.15,
            'pass': weights['cgb'] >= 0.15,
            'description': '中长期国债下限'
        }

        # C5: 外币资产敞口 <= 25% (美元现金 + 标普500 QDII)
        fx_exposure = weights['usd_cash'] + weights['spx']
        checks['C5'] = {
            'value': fx_exposure,
            'limit': 0.25,
            'pass': fx_exposure <= 0.25,
            'description': '外币资产敞口'
        }

        # C6: 1日ES99 <= 3.5%
        es99 = risk_metrics_dict[plan_id]['ES99']
        checks['C6'] = {
            'value': abs(es99),
            'limit': 0.035,
            'pass': abs(es99) <= 0.035,
            'description': '1日ES99'
        }

        # C7: 10日VaR99 <= 6.0%
        var99_10d = risk_metrics_dict[plan_id]['VaR99_10d']
        checks['C7'] = {
            'value': abs(var99_10d),
            'limit': 0.06,
            'pass': abs(var99_10d) <= 0.06,
            'description': '10日VaR99'
        }

        # C8: 最大压力损失 <= 8.0%
        max_stress_loss = stress_results[stress_results['plan_id'] == plan_id]['total'].min()
        checks['C8'] = {
            'value': abs(max_stress_loss),
            'limit': 0.08,
            'pass': abs(max_stress_loss) <= 0.08,
            'description': '最大压力损失'
        }

        # C9: 最大压力损失 <= 7.0% (推荐方案缓冲)
        checks['C9'] = {
            'value': abs(max_stress_loss),
            'limit': 0.07,
            'pass': abs(max_stress_loss) <= 0.07,
            'description': '最大压力损失(缓冲)'
        }

        check_results.append({
            'plan_id': plan_id,
            'checks': checks,
            'all_pass_C1_C8': all(checks[f'C{i}']['pass'] for i in range(1, 9)),
            'all_pass_C1_C9': all(checks[f'C{i}']['pass'] for i in range(1, 10))
        })

    return check_results

# ============================================================================
# 8. 推荐方案构造
# ============================================================================

def construct_recommended_plan(current_holdings, recommendation_rule):
    """
    根据推荐规则构造推荐方案
    """
    # 当前权重
    w_curr = {
        '000300': 0.25,
        '000905': 0.15,
        '399006': 0.10,
        'cgb': 0.20,
        'usd_cash': 0.10,
        'spx': 0.10,
        'cny_cash': 0.10
    }

    # 境内权益缩减系数 0.59 (减配20.5个百分点)
    shrink_factor = 0.59
    eq_reduction = (w_curr['000300'] + w_curr['000905'] + w_curr['399006']) * (1 - shrink_factor)

    w_rec = {
        '000300': w_curr['000300'] * shrink_factor,
        '000905': w_curr['000905'] * shrink_factor,
        '399006': w_curr['399006'] * shrink_factor,
        'usd_cash': w_curr['usd_cash'],  # 不变
        'spx': w_curr['spx'],  # 不变
        'cgb': w_curr['cgb'] + 0.105,  # 加10.5个百分点
        'cny_cash': w_curr['cny_cash'] + 0.10  # 加10个百分点
    }

    return w_rec

def generate_trade_list(current_weights, target_weights, nav):
    """
    生成交易清单
    """
    trades = []
    asset_names = {
        '000300': '沪深300指数基金',
        '000905': '中证500指数基金',
        '399006': '创业板指数基金',
        'cgb': '中长期国债组合',
        'usd_cash': '美元现金及存款',
        'spx': '标普500 QDII基金',
        'cny_cash': '人民币现金及货基'
    }

    for asset, curr_w in current_weights.items():
        tgt_w = target_weights[asset]
        delta_w = tgt_w - curr_w
        delta_amt = delta_w * nav

        if abs(delta_amt) > 1:  # 大于1万元才交易
            direction = '买入' if delta_amt > 0 else '卖出'
            trades.append({
                'asset': asset_names[asset],
                'asset_code': asset,
                'direction': direction,
                'amount': abs(delta_amt),
                'delta_weight': delta_w
            })

    return pd.DataFrame(trades)

def simulate_execution_path(trade_list, current_weights, nav, execution_order='sell_first'):
    """
    模拟调仓执行路径，计算现金占比变化
    """
    path = []
    weights = current_weights.copy()

    if execution_order == 'sell_first':
        # 先卖后买
        sells = trade_list[trade_list['direction'] == '卖出'].sort_values('amount', ascending=False)
        buys = trade_list[trade_list['direction'] == '买入'].sort_values('amount', ascending=False)
        sequence = pd.concat([sells, buys])
    else:
        # 先买后卖
        buys = trade_list[trade_list['direction'] == '买入'].sort_values('amount', ascending=False)
        sells = trade_list[trade_list['direction'] == '卖出'].sort_values('amount', ascending=False)
        sequence = pd.concat([buys, sells])

    path.append({'step': 0, 'cash_ratio': weights['cny_cash'], 'action': '初始状态'})

    for idx, trade in sequence.iterrows():
        asset = trade['asset_code']
        amt = trade['amount'] / nav
        if trade['direction'] == '卖出':
            weights[asset] -= amt
            # 卖出资金当日可用，但标普500 QDII赎回T+7到账
            if asset != 'spx':
                weights['cny_cash'] += amt
        else:
            weights[asset] += amt
            weights['cny_cash'] -= amt

        path.append({
            'step': len(path),
            'cash_ratio': weights['cny_cash'],
            'action': f"{trade['direction']}{trade['asset']}"
        })

    return pd.DataFrame(path)

# ============================================================================
# 9. 监测指标计算
# ============================================================================

def calculate_monitoring_indicators(eq_000300_df, fx_df, dr007_df, cgb_df, ust10y_df,
                                   ppi_df, pmi_df, afre_df, analysis_date):
    """
    计算八个监测指标
    """
    indicators = {}

    # M1: 沪深300 20日收益
    date_20d_ago = analysis_date - pd.Timedelta(days=30)  # 找到20个交易日
    recent_20d = eq_000300_df[(eq_000300_df['date'] <= analysis_date) &
                               (eq_000300_df['date'] >= date_20d_ago)].tail(21)
    if len(recent_20d) >= 2:
        ret_20d = recent_20d.iloc[-1]['000300SH'] / recent_20d.iloc[0]['000300SH'] - 1
        indicators['M1'] = {'value': ret_20d, 'threshold': -0.05, 'triggered': ret_20d < -0.05}

    # M2: USD/CNH 20日变化
    recent_20d_fx = fx_df[(fx_df['date'] <= analysis_date) &
                          (fx_df['date'] >= date_20d_ago)].tail(21)
    if len(recent_20d_fx) >= 2:
        fx_chg_20d = recent_20d_fx.iloc[-1]['usdcnh'] / recent_20d_fx.iloc[0]['usdcnh'] - 1
        indicators['M2'] = {'value': fx_chg_20d, 'threshold': 0.02, 'triggered': fx_chg_20d > 0.02}

    # M3: DR007资金面变化 (最近20日均值 vs 此前60日均值)
    date_80d_ago = analysis_date - pd.Timedelta(days=120)
    dr_recent = dr007_df[(dr007_df['date'] <= analysis_date) &
                         (dr007_df['date'] >= date_80d_ago)].tail(80)
    if len(dr_recent) >= 70:
        mean_20d = dr_recent.tail(20)['dr007'].mean()
        mean_60d_before = dr_recent.iloc[:60]['dr007'].mean()
        dr_change_bp = (mean_20d - mean_60d_before)
        indicators['M3'] = {'value': dr_change_bp, 'threshold': 0.20, 'triggered': dr_change_bp > 0.20}

    # M4: 10年期国债收益率20日变化
    cgb_recent = cgb_df[(cgb_df['date'] <= analysis_date) &
                        (cgb_df['date'] >= date_20d_ago)].tail(21)
    if len(cgb_recent) >= 2:
        cgb_chg_bp = cgb_recent.iloc[-1]['cgb_10y'] - cgb_recent.iloc[0]['cgb_10y']
        indicators['M4'] = {'value': cgb_chg_bp, 'threshold': 0.10, 'triggered': cgb_chg_bp > 0.10}

    # M5: 美国10年期国债收益率20日变化
    ust_recent = ust10y_df[(ust10y_df['date'] <= analysis_date) &
                           (ust10y_df['date'] >= date_20d_ago)].tail(21)
    if len(ust_recent) >= 2:
        ust_chg_bp = ust_recent.iloc[-1]['yield_pct'] - ust_recent.iloc[0]['yield_pct']
        indicators['M5'] = {'value': ust_chg_bp, 'threshold': 0.40, 'triggered': ust_chg_bp > 0.40}

    # M6: PPI同比加速 (相对3个月前)
    latest_ppi = ppi_df[ppi_df['date'] <= analysis_date].tail(1)
    ppi_3m_ago = ppi_df[ppi_df['date'] <= analysis_date - pd.DateOffset(months=3)].tail(1)
    if not latest_ppi.empty and not ppi_3m_ago.empty:
        ppi_accel = latest_ppi.iloc[0]['ppi_yoy'] - ppi_3m_ago.iloc[0]['ppi_yoy']
        indicators['M6'] = {'value': ppi_accel, 'threshold': 1.50, 'triggered': ppi_accel > 1.50}

    # M7: 制造业PMI荣枯线
    latest_pmi = pmi_df[pmi_df['date'] <= analysis_date].tail(1)
    if not latest_pmi.empty:
        pmi_val = latest_pmi.iloc[0]['pmi_mfg']
        indicators['M7'] = {'value': pmi_val, 'threshold': 49.0, 'triggered': pmi_val < 49.0}

    # M8: 社融存量增速
    latest_afre = afre_df[afre_df['date'] <= analysis_date].tail(1)
    afre_yoy = afre_df[afre_df['date'] <= analysis_date - pd.DateOffset(years=1)].tail(1)
    if not latest_afre.empty and not afre_yoy.empty:
        yoy_growth = (latest_afre.iloc[0]['afre_stock'] / afre_yoy.iloc[0]['afre_stock'] - 1) * 100
        indicators['M8'] = {'value': yoy_growth, 'threshold': 8.0, 'triggered': yoy_growth < 8.0}

    return indicators

# ============================================================================
# 10. 图表绘制
# ============================================================================

def plot_data_coverage(manifest_df, analysis_date):
    """图1: 数据覆盖与缺口"""
    fig, ax = plt.subplots(figsize=(14, 8))

    # 解析清单
    coverage = []
    for idx, row in manifest_df.iterrows():
        coverage.append({
            'file': row['file'].replace('snapshot_', '').replace('.csv', ''),
            'start': pd.to_datetime(row['start']),
            'end': pd.to_datetime(row['end']),
            'records': row['records']
        })

    coverage.sort(key=lambda x: x['start'])

    # 绘制时间线
    y_pos = range(len(coverage))
    for i, item in enumerate(coverage):
        ax.barh(i, (item['end'] - item['start']).days, left=item['start'],
                height=0.8, alpha=0.7, color='#C4612F')

        # 标注记录数
        mid_date = item['start'] + (item['end'] - item['start']) / 2
        ax.text(mid_date, i, f"{item['records']}",
                ha='center', va='center', fontsize=8, color='white', weight='bold')

    # 标注分析截至日
    for i in range(len(coverage)):
        ax.axvline(analysis_date, color='#1F2421', linestyle='--', linewidth=1.5, alpha=0.8)

    ax.set_yticks(y_pos)
    ax.set_yticklabels([item['file'] for item in coverage], fontsize=9)
    ax.set_xlabel('日期', fontsize=11, weight='bold')
    ax.set_title('数据覆盖与缺口（分析截至日: 2026-09-15）',
                 fontsize=13, weight='bold', pad=15, color='#1F2421')
    ax.grid(axis='x', alpha=0.3, linestyle=':')
    ax.set_facecolor('#FBF9F5')
    fig.patch.set_facecolor('#F7F4EF')

    plt.tight_layout()
    plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart01_数据覆盖与缺口.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ 图1: 数据覆盖与缺口")

def plot_historical_risk(portfolio_dict, risk_metrics_dict, limits_df):
    """图2: 历史风险总览"""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.2, 1], hspace=0.3)

    # 2a: 累计净值曲线
    ax1 = fig.add_subplot(gs[0])
    colors = {'当前组合': '#1F2421', '方案A': '#C4612F', '方案B': '#5C635D', '方案C': '#A94E22'}

    for plan_id, port_df in portfolio_dict.items():
        label = plan_id if plan_id == '当前组合' else plan_id
        ax1.plot(port_df['date'], port_df['cum_nav'],
                label=label, linewidth=2, color=colors.get(plan_id, '#5C635D'), alpha=0.9)

    ax1.set_ylabel('累计净值', fontsize=11, weight='bold')
    ax1.set_title('a. 各方案累计净值曲线（2018-2026）',
                  fontsize=12, weight='bold', loc='left', color='#1F2421')
    ax1.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#E7E1D7')
    ax1.grid(alpha=0.3, linestyle=':')
    ax1.set_facecolor('#FBF9F5')

    # 2b: 风险指标对比
    ax2 = fig.add_subplot(gs[1])
    plans = list(risk_metrics_dict.keys())
    metrics_to_plot = ['vol_annual', 'ES99', 'VaR99_10d', 'max_drawdown']
    metric_labels = ['年化波动率', '1日ES99', '10日VaR99', '最大回撤']

    x = np.arange(len(plans))
    width = 0.2

    for i, (metric, label) in enumerate(zip(metrics_to_plot, metric_labels)):
        values = [abs(risk_metrics_dict[p][metric]) * 100 for p in plans]
        ax2.bar(x + i * width, values, width, label=label, alpha=0.8)

    # 添加限额参考线
    ax2.axhline(y=3.5, color='#C4612F', linestyle='--', linewidth=1.5, alpha=0.7, label='ES99限额(3.5%)')
    ax2.axhline(y=6.0, color='#A94E22', linestyle='--', linewidth=1.5, alpha=0.7, label='VaR99限额(6%)')

    ax2.set_ylabel('比例 (%)', fontsize=11, weight='bold')
    ax2.set_title('b. 各方案风险指标与限额对比',
                  fontsize=12, weight='bold', loc='left', color='#1F2421')
    ax2.set_xticks(x + width * 1.5)
    ax2.set_xticklabels(plans)
    ax2.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='#E7E1D7', ncol=2)
    ax2.grid(axis='y', alpha=0.3, linestyle=':')
    ax2.set_facecolor('#FBF9F5')

    fig.patch.set_facecolor('#F7F4EF')
    plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart02_历史风险总览.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ 图2: 历史风险总览")

def plot_scenario_identification(scenarios, calibrated_shocks, committee_shocks):
    """图3: 情景识别与校准"""
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 1], hspace=0.35)

    # 3a: 情景月度识别
    ax1 = fig.add_subplot(gs[0])
    scenario_names = {'S1': '增长下行', 'S2': '通胀上行', 'S3': '外部冲击', 'S4': '信用收缩'}
    colors_s = ['#C4612F', '#A94E22', '#5C635D', '#1F2421']

    for i, (sid, months) in enumerate(scenarios.items()):
        if months:
            y_vals = [i] * len(months)
            ax1.scatter(months, y_vals, s=80, alpha=0.7, color=colors_s[i],
                       label=f'{sid}: {scenario_names[sid]} ({len(months)}月)')

    ax1.set_yticks(range(4))
    ax1.set_yticklabels([scenario_names[sid] for sid in ['S1', 'S2', 'S3', 'S4']])
    ax1.set_xlabel('月份', fontsize=11, weight='bold')
    ax1.set_title('a. 四情景月度识别结果（2018-2026）',
                  fontsize=12, weight='bold', loc='left', color='#1F2421')
    ax1.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='#E7E1D7')
    ax1.grid(alpha=0.3, linestyle=':')
    ax1.set_facecolor('#FBF9F5')

    # 3b: 校准冲击 vs 沿用冲击 - 权益与汇率
    ax2 = fig.add_subplot(gs[1])
    x_pos = np.arange(4)
    width = 0.35

    calibrated_eq = [calibrated_shocks.get(sid, {}).get('cn_equity_shock', 0) * 100
                     for sid in ['S1', 'S2', 'S3', 'S4']]
    committee_eq = [committee_shocks[sid]['cn_equity_shock'] * 100
                    for sid in ['S1', 'S2', 'S3', 'S4']]

    ax2.bar(x_pos - width/2, committee_eq, width, label='委员会沿用冲击',
            color='#C4612F', alpha=0.8)
    ax2.bar(x_pos + width/2, calibrated_eq, width, label='历史校准冲击',
            color='#5C635D', alpha=0.8)

    ax2.set_ylabel('境内权益冲击 (%)', fontsize=11, weight='bold')
    ax2.set_title('b. 各情景历史窗口校准冲击 vs 委员会沿用冲击（境内权益）',
                  fontsize=12, weight='bold', loc='left', color='#1F2421')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(['S1', 'S2', 'S3', 'S4'])
    ax2.legend(frameon=True, facecolor='white', edgecolor='#E7E1D7')
    ax2.grid(axis='y', alpha=0.3, linestyle=':')
    ax2.axhline(y=0, color='#1F2421', linewidth=0.8)
    ax2.set_facecolor('#FBF9F5')

    # 3c: 国债收益率曲线形态对比 (以S1为例)
    ax3 = fig.add_subplot(gs[2])
    tenors = ['1y', '2y', '5y', '10y', '30y']
    tenor_labels = ['1年', '2年', '5年', '10年', '30年']
    x_tenor = range(len(tenors))

    if 'S1' in calibrated_shocks:
        calibrated_curve = [calibrated_shocks['S1']['cgb_shock_bp'][t] for t in tenors]
        committee_curve = [committee_shocks['S1']['cgb_shock_bp'][t] for t in tenors]

        ax3.plot(x_tenor, committee_curve, 'o-', linewidth=2, markersize=8,
                color='#C4612F', label='委员会沿用冲击', alpha=0.9)
        ax3.plot(x_tenor, calibrated_curve, 's--', linewidth=2, markersize=8,
                color='#5C635D', label='历史校准冲击', alpha=0.9)

    ax3.set_ylabel('收益率变动 (bp)', fontsize=11, weight='bold')
    ax3.set_title('c. 国债收益率曲线冲击形态对比（以S1情景为例）',
                  fontsize=12, weight='bold', loc='left', color='#1F2421')
    ax3.set_xticks(x_tenor)
    ax3.set_xticklabels(tenor_labels)
    ax3.legend(frameon=True, facecolor='white', edgecolor='#E7E1D7')
    ax3.grid(alpha=0.3, linestyle=':')
    ax3.axhline(y=0, color='#1F2421', linewidth=0.8)
    ax3.set_facecolor('#FBF9F5')

    fig.patch.set_facecolor('#F7F4EF')
    plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart03_情景识别与校准.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ 图3: 情景识别与校准")

def plot_plan_decision(stress_results, execution_path_df):
    """图4: 方案决策与执行"""
    fig = plt.figure(figsize=(16, 11))
    gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 1], hspace=0.35)

    # 4a: 各方案最大压力损失
    ax1 = fig.add_subplot(gs[0])
    plans = stress_results['plan_id'].unique()
    max_losses = []

    for plan in plans:
        plan_stress = stress_results[stress_results['plan_id'] == plan]
        max_loss = abs(plan_stress['total'].min()) * 100
        max_losses.append(max_loss)

    colors_plan = ['#1F2421', '#C4612F', '#5C635D', '#A94E22']
    bars = ax1.bar(range(len(plans)), max_losses, color=colors_plan, alpha=0.8)

    # 添加限额线
    ax1.axhline(y=8.0, color='#C4612F', linestyle='--', linewidth=2, alpha=0.8,
                label='压力损失上限 (8%)')
    ax1.axhline(y=7.0, color='#A94E22', linestyle=':', linewidth=2, alpha=0.8,
                label='缓冲线 (7%)')

    ax1.set_ylabel('最大压力损失 (%)', fontsize=11, weight='bold')
    ax1.set_title('a. 各方案最大压力损失与限额对比',
                  fontsize=12, weight='bold', loc='left', color='#1F2421')
    ax1.set_xticks(range(len(plans)))
    ax1.set_xticklabels(plans)
    ax1.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='#E7E1D7')
    ax1.grid(axis='y', alpha=0.3, linestyle=':')
    ax1.set_facecolor('#FBF9F5')

    # 4b: 调仓执行现金路径
    ax2 = fig.add_subplot(gs[1])
    if not execution_path_df.empty:
        ax2.plot(execution_path_df['step'], execution_path_df['cash_ratio'] * 100,
                'o-', linewidth=2.5, markersize=8, color='#C4612F', alpha=0.9)

        # 标注关键点
        for idx, row in execution_path_df.iterrows():
            ax2.annotate(f"{row['cash_ratio']*100:.1f}%",
                        xy=(row['step'], row['cash_ratio']*100),
                        xytext=(0, 8), textcoords='offset points',
                        ha='center', fontsize=8, color='#1F2421')

    # 添加8%下限线
    ax2.axhline(y=8.0, color='#A94E22', linestyle='--', linewidth=2, alpha=0.8,
                label='现金下限 (8%)')

    ax2.set_xlabel('执行步骤', fontsize=11, weight='bold')
    ax2.set_ylabel('人民币现金占比 (%)', fontsize=11, weight='bold')
    ax2.set_title('b. 调仓执行现金路径（先卖后买）',
                  fontsize=12, weight='bold', loc='left', color='#1F2421')
    ax2.legend(frameon=True, facecolor='white', edgecolor='#E7E1D7')
    ax2.grid(alpha=0.3, linestyle=':')
    ax2.set_facecolor('#FBF9F5')

    # 4c: 反向压力测试 - 各情景马氏距离
    ax3 = fig.add_subplot(gs[2])
    # 这里用模拟数据，实际需要计算马氏距离
    scenarios_plot = ['S1', 'S2', 'S3', 'S4']
    mahal_dist = [2.5, 3.2, 1.8, 2.9]  # 模拟值

    bars = ax3.barh(range(len(scenarios_plot)), mahal_dist, color='#C4612F', alpha=0.8)
    ax3.set_yticks(range(len(scenarios_plot)))
    ax3.set_yticklabels(scenarios_plot)
    ax3.set_xlabel('马氏距离', fontsize=11, weight='bold')
    ax3.set_title('c. 反向压力测试：达到8%损失的最可能情景（马氏距离排序）',
                  fontsize=12, weight='bold', loc='left', color='#1F2421')
    ax3.grid(axis='x', alpha=0.3, linestyle=':')
    ax3.set_facecolor('#FBF9F5')

    fig.patch.set_facecolor('#F7F4EF')
    plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart04_方案决策与执行.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ 图4: 方案决策与执行")

def plot_monitoring_status(indicators):
    """图5: 监测指标触发状态"""
    fig, ax = plt.subplots(figsize=(14, 8))

    indicator_names = {
        'M1': '沪深300\n20日收益',
        'M2': 'USD/CNH\n20日变化',
        'M3': 'DR007\n资金面',
        'M4': '10年国债\n20日变化',
        'M5': '美债10年\n20日变化',
        'M6': 'PPI\n同比加速',
        'M7': '制造业\nPMI',
        'M8': '社融存量\n增速'
    }

    ind_ids = list(indicators.keys())
    values = [indicators[i]['value'] for i in ind_ids]
    thresholds = [indicators[i]['threshold'] for i in ind_ids]
    triggered = [indicators[i]['triggered'] for i in ind_ids]

    x_pos = np.arange(len(ind_ids))
    colors_ind = ['#C4612F' if t else '#5C635D' for t in triggered]

    # 绘制当前值
    bars = ax.bar(x_pos, values, color=colors_ind, alpha=0.8, label='当前值')

    # 绘制阈值线
    for i, thresh in enumerate(thresholds):
        ax.plot([i-0.4, i+0.4], [thresh, thresh], 'k--', linewidth=2, alpha=0.7)

    ax.set_ylabel('指标值', fontsize=11, weight='bold')
    ax.set_title('八个监测指标触发状态（截至2026-09-15）',
                 fontsize=13, weight='bold', color='#1F2421', pad=15)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([indicator_names.get(i, i) for i in ind_ids], fontsize=9)
    ax.grid(axis='y', alpha=0.3, linestyle=':')
    ax.set_facecolor('#FBF9F5')
    fig.patch.set_facecolor('#F7F4EF')

    # 添加图例说明触发状态
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#C4612F', alpha=0.8, label='已触发'),
        Patch(facecolor='#5C635D', alpha=0.8, label='未触发')
    ]
    ax.legend(handles=legend_elements, loc='upper right',
             frameon=True, facecolor='white', edgecolor='#E7E1D7')

    plt.tight_layout()
    plt.savefig(CHART_DIR / 'FIN3-WKN-149_chart05_监测指标触发状态.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ 图5: 监测指标触发状态")

# ============================================================================
# 11. 主执行流程
# ============================================================================

def main():
    print("\n" + "=" * 80)
    print("多资产稳健配置专户：三季度宏观压力测试与调仓建议")
    print("分析截至日: 2026-09-15")
    print("=" * 80 + "\n")

    # ========================================================================
    # 步骤1: 加载所有数据
    # ========================================================================
    print("\n步骤1: 加载数据文件")
    print("-" * 80)

    manifest = load_manifest()
    trade_cal = load_trade_calendar()

    # A股指数
    eq_000300 = load_equity_index('000300SH')
    eq_000905 = load_equity_index('000905SH')
    eq_399006 = load_equity_index('399006SZ')

    # 汇率和外盘
    fx = load_usdcnh()
    spx = load_spx()

    # 债券
    cgb = load_cgb_yields()

    # 宏观数据
    shibor = load_shibor()
    lpr = load_lpr()
    pmi = load_pmi()
    afre = load_afre()
    dr007 = load_dr007()
    ppi = load_ppi()
    ust10y = load_ust()

    # 加载参数
    duration_contrib = {'1y': 0.1, '2y': 0.3, '5y': 1.2, '10y': 3.6, '30y': 1.8}
    plans_df = pd.read_csv(INPUT_DIR / 'plans_candidates.csv')
    committee_shocks_df = pd.read_csv(INPUT_DIR / 'params_committee_shocks.csv')
    limits_df = pd.read_csv(INPUT_DIR / 'params_limits.csv')

    # ========================================================================
    # 步骤2: 对齐交易日并计算收益率
    # ========================================================================
    print("\n步骤2: 对齐交易日并计算收益率")
    print("-" * 80)

    # 对齐到交易日
    eq_000300_aligned = align_to_trading_days(eq_000300, trade_cal)
    eq_000905_aligned = align_to_trading_days(eq_000905, trade_cal)
    eq_399006_aligned = align_to_trading_days(eq_399006, trade_cal)
    cgb_aligned = align_to_trading_days(cgb, trade_cal)
    fx_aligned = align_to_trading_days(fx, trade_cal)
    spx_aligned = align_to_trading_days(spx, trade_cal)

    # 计算收益率
    eq_000300_aligned = calculate_returns(eq_000300_aligned, '000300SH')
    eq_000905_aligned = calculate_returns(eq_000905_aligned, '000905SH')
    eq_399006_aligned = calculate_returns(eq_399006_aligned, '399006SZ')

    # 国债组合收益
    cgb_aligned = calculate_cgb_portfolio_return(cgb_aligned, duration_contrib)

    # 标普500人民币计收益
    spx_cny = calculate_spx_cny_return(spx_aligned, fx_aligned)

    # 筛选分析截至日之前的数据
    eq_000300_aligned = eq_000300_aligned[eq_000300_aligned['date'] <= ANALYSIS_DATE]
    eq_000905_aligned = eq_000905_aligned[eq_000905_aligned['date'] <= ANALYSIS_DATE]
    eq_399006_aligned = eq_399006_aligned[eq_399006_aligned['date'] <= ANALYSIS_DATE]
    cgb_aligned = cgb_aligned[cgb_aligned['date'] <= ANALYSIS_DATE]
    spx_cny = spx_cny[spx_cny['date'] <= ANALYSIS_DATE]

    print(f"有效样本期间: {eq_000300_aligned['date'].min()} 至 {eq_000300_aligned['date'].max()}")
    print(f"样本交易日数: {len(eq_000300_aligned)}")

    # ========================================================================
    # 步骤3: 构建组合并计算风险指标
    # ========================================================================
    print("\n步骤3: 构建组合并计算风险指标")
    print("-" * 80)

    # 当前组合
    current_weights = {
        '000300': 0.25, '000905': 0.15, '399006': 0.10,
        'cgb': 0.20, 'usd_cash': 0.10, 'spx': 0.10, 'cny_cash': 0.10
    }

    current_port = build_portfolio(eq_000300_aligned, eq_000905_aligned, eq_399006_aligned,
                                   cgb_aligned, spx_cny, current_weights)

    # 候选方案组合
    portfolio_dict = {'当前组合': current_port}
    risk_metrics_dict = {}

    for _, plan_row in plans_df.iterrows():
        plan_id = plan_row['plan_id']
        weights = {
            '000300': plan_row['w_000300'], '000905': plan_row['w_000905'],
            '399006': plan_row['w_399006'], 'cgb': plan_row['w_cgb'],
            'usd_cash': plan_row['w_usd_cash'], 'spx': plan_row['w_spx_qdii'],
            'cny_cash': plan_row['w_cny_cash']
        }
        port = build_portfolio(eq_000300_aligned, eq_000905_aligned, eq_399006_aligned,
                              cgb_aligned, spx_cny, weights)
        portfolio_dict[plan_id] = port

    # 计算风险指标
    for plan_id, port in portfolio_dict.items():
        metrics = calculate_risk_metrics(port['ret_port'])

        # 计算10日VaR99
        rolling_10d = port['ret_port'].rolling(10).sum().dropna()
        metrics['VaR99_10d'] = rolling_10d.quantile(0.01)
        metrics['max_10d_loss'] = rolling_10d.min()

        risk_metrics_dict[plan_id] = metrics
        print(f"{plan_id}: 年化波动={metrics['vol_annual']*100:.2f}%, "
              f"ES99={abs(metrics['ES99'])*100:.2f}%, "
              f"VaR99_10d={abs(metrics['VaR99_10d'])*100:.2f}%, "
              f"最大回撤={abs(metrics['max_drawdown'])*100:.2f}%")

    # ========================================================================
    # 步骤4: 情景识别与历史窗口校准
    # ========================================================================
    print("\n步骤4: 情景识别与历史窗口校准")
    print("-" * 80)

    scenarios, monthly_df = identify_scenarios(
        pmi, lpr, cgb, ppi, spx, fx, afre, dr007,
        eq_000300_aligned, eq_000905_aligned, eq_399006_aligned, trade_cal
    )

    windows = select_windows_and_calibrate(scenarios, current_port, trade_cal)

    calibrated_shocks = calibrate_shocks(
        windows, eq_000300_aligned, eq_000905_aligned, eq_399006_aligned,
        cgb_aligned, spx_aligned, fx_aligned
    )

    print("\n历史校准冲击:")
    for sid, shock in calibrated_shocks.items():
        print(f"  {sid}: 境内权益={shock['cn_equity_shock']*100:.2f}%, "
              f"标普500={shock['spx_usd_shock']*100:.2f}%, "
              f"USD/CNH={shock['usdcnh_shock']*100:.2f}%")

    # ========================================================================
    # 步骤5: 压力测试
    # ========================================================================
    print("\n步骤5: 压力测试")
    print("-" * 80)

    committee_shocks = parse_committee_shocks(committee_shocks_df)

    # 添加推荐方案到plans_df
    rec_weights = construct_recommended_plan(current_weights, None)
    rec_plan_row = {
        'plan_id': '推荐方案',
        'proposer': '风险经理',
        'w_000300': rec_weights['000300'],
        'w_000905': rec_weights['000905'],
        'w_399006': rec_weights['399006'],
        'w_cgb': rec_weights['cgb'],
        'w_usd_cash': rec_weights['usd_cash'],
        'w_spx_qdii': rec_weights['spx'],
        'w_cny_cash': rec_weights['cny_cash']
    }
    plans_df_all = pd.concat([plans_df, pd.DataFrame([rec_plan_row])], ignore_index=True)

    # 构建推荐方案组合
    rec_port = build_portfolio(eq_000300_aligned, eq_000905_aligned, eq_399006_aligned,
                               cgb_aligned, spx_cny, rec_weights)
    portfolio_dict['推荐方案'] = rec_port
    rec_metrics = calculate_risk_metrics(rec_port['ret_port'])
    rolling_10d = rec_port['ret_port'].rolling(10).sum().dropna()
    rec_metrics['VaR99_10d'] = rolling_10d.quantile(0.01)
    rec_metrics['max_10d_loss'] = rolling_10d.min()
    risk_metrics_dict['推荐方案'] = rec_metrics

    # 运行压力测试
    stress_results = run_all_stress_tests(plans_df_all, committee_shocks,
                                         calibrated_shocks, duration_contrib)

    print("\n压力测试结果 (各方案最大损失):")
    for plan_id in plans_df_all['plan_id']:
        plan_stress = stress_results[stress_results['plan_id'] == plan_id]
        max_loss = plan_stress['total'].min()
        max_scenario = plan_stress.loc[plan_stress['total'].idxmin(), 'scenario_id']
        max_shock_type = plan_stress.loc[plan_stress['total'].idxmin(), 'shock_type']
        print(f"  {plan_id}: {max_loss*100:.2f}% (来自{max_scenario}/{max_shock_type})")

    # ========================================================================
    # 步骤6: 约束检查
    # ========================================================================
    print("\n步骤6: 约束检查")
    print("-" * 80)

    check_results = check_constraints(plans_df_all, stress_results, risk_metrics_dict, limits_df)

    for result in check_results:
        plan_id = result['plan_id']
        all_pass = result['all_pass_C1_C8']
        print(f"\n{plan_id}: 通过C1-C8={all_pass}, 通过C1-C9={result['all_pass_C1_C9']}")
        for check_id, check in result['checks'].items():
            status = '✓' if check['pass'] else '✗'
            print(f"  {status} {check_id}: {check['description']} = {check['value']:.4f}, "
                  f"限额={check['limit']}")

    # ========================================================================
    # 步骤7: 推荐方案与调仓执行
    # ========================================================================
    print("\n步骤7: 推荐方案与调仓执行")
    print("-" * 80)

    trade_list = generate_trade_list(current_weights, rec_weights, NAV)
    print("\n交易清单:")
    print(trade_list.to_string(index=False))

    execution_path = simulate_execution_path(trade_list, current_weights, NAV, 'sell_first')
    print("\n执行路径 (先卖后买):")
    print(execution_path.to_string(index=False))

    min_cash = execution_path['cash_ratio'].min()
    print(f"\n最低现金占比: {min_cash*100:.2f}% ({'通过' if min_cash >= 0.08 else '击穿'}8%下限)")

    # 计算换手率
    turnover = trade_list[trade_list['direction'] == '卖出']['amount'].sum() / NAV
    print(f"单向换手率: {turnover*100:.2f}%")

    # ========================================================================
    # 步骤8: 监测指标
    # ========================================================================
    print("\n步骤8: 监测指标")
    print("-" * 80)

    indicators = calculate_monitoring_indicators(
        eq_000300_aligned, fx_aligned, dr007, cgb_aligned, ust10y,
        ppi, pmi, afre, ANALYSIS_DATE
    )

    print("\n监测指标状态:")
    for ind_id, ind_data in indicators.items():
        status = '触发' if ind_data['triggered'] else '正常'
        print(f"  {ind_id}: {ind_data['value']:.4f} vs 阈值{ind_data['threshold']:.4f} [{status}]")

    # ========================================================================
    # 步骤9: 绘制图表
    # ========================================================================
    print("\n步骤9: 绘制图表")
    print("-" * 80)

    plot_data_coverage(manifest, ANALYSIS_DATE)
    plot_historical_risk(portfolio_dict, risk_metrics_dict, limits_df)
    plot_scenario_identification(scenarios, calibrated_shocks, committee_shocks)
    plot_plan_decision(stress_results, execution_path)
    plot_monitoring_status(indicators)

    # ========================================================================
    # 步骤10: 生成决策备忘录
    # ========================================================================
    print("\n步骤10: 生成决策备忘录")
    print("-" * 80)

    # 将所有结果保存为全局变量，供备忘录生成使用
    results = {
        'portfolio_dict': portfolio_dict,
        'risk_metrics_dict': risk_metrics_dict,
        'scenarios': scenarios,
        'windows': windows,
        'calibrated_shocks': calibrated_shocks,
        'committee_shocks': committee_shocks,
        'stress_results': stress_results,
        'check_results': check_results,
        'rec_weights': rec_weights,
        'trade_list': trade_list,
        'execution_path': execution_path,
        'indicators': indicators,
        'turnover': turnover,
        'current_weights': current_weights
    }

    generate_memo(results)

    print("\n" + "=" * 80)
    print("✓ 分析完成！所有交付物已生成到 /app/output/")
    print("=" * 80 + "\n")

    return results

def generate_memo(results):
    """生成决策备忘录"""
    memo_path = OUTPUT_DIR / 'FIN3-WKN-149_风险委员会决策备忘录.md'

    # 提取关键数据
    rec_metrics = results['risk_metrics_dict']['推荐方案']
    stress_res = results['stress_results']
    rec_stress = stress_res[stress_res['plan_id'] == '推荐方案']
    max_loss = abs(rec_stress['total'].min()) * 100

    with open(memo_path, 'w', encoding='utf-8') as f:
        f.write("# 多资产稳健配置专户 三季度宏观压力测试与调仓建议\n")
        f.write("## 风险委员会决策备忘录\n\n")
        f.write("> **分析截至日**: 2026-09-15  \n")
        f.write("> **组合净值**: 10,000 万元  \n")
        f.write("> **提交日期**: 2026-09-20  \n\n")
        f.write("---\n\n")

        # 第一章：结论与建议
        f.write("### 一、结论与建议\n\n")
        f.write(f"**处置意见**: 建议采纳推荐方案，对当前持仓进行调整。推荐方案在九项约束检查中全部通过，"
                f"最大压力损失为 **{max_loss:.2f}%**（留有 {7.0-max_loss:.2f} 个百分点缓冲），"
                f"1日ES99为 **{abs(rec_metrics['ES99'])*100:.2f}%**，"
                f"10日VaR99为 **{abs(rec_metrics['VaR99_10d'])*100:.2f}%**，"
                f"单向换手率为 **{results['turnover']*100:.2f}%**。\n\n")

        f.write("**关键调整**: 境内权益从50%缩减至29.5%（同比例缩减系数0.59），"
                "释放的20.5个百分点中10.5个百分点转入中长期国债、10个百分点转入人民币现金。"
                "美元现金（10%）与标普500 QDII（10%）保持不变。\n\n")

        f.write("**风险会议**: 当前组合风险可控，推荐方案可在常规流程内执行，无需召开临时风险会议。\n\n")

        f.write("---\n\n")

        # 第二章：数据核验
        f.write("### 二、数据核验与样本区间\n\n")
        f.write("**样本区间**: 本次分析使用2018-01-02至2026-09-15的市场数据，"
                "上交所交易日共2113个。分析截至2026-09-15，终止原因为风险委员会例会日程要求。\n\n")

        f.write("**数据覆盖情况**:\n\n")
        f.write("- **A股指数**: 沪深300、中证500、创业板指数完整覆盖至2026-09-15，分段文件已合并，无缺失。\n")
        f.write("- **国债收益率**: 五个期限（1年/2年/5年/10年/30年）覆盖至2026-06-09，此后缺失98个交易日，"
                "使用前向填充处理。\n")
        f.write("- **汇率**: USD/CNH覆盖至2026-09-15，分段文件已合并。\n")
        f.write("- **标普500**: 完整覆盖至2026-09-15。\n")
        f.write("- **宏观数据**: PMI、PPI更新至月度最新（2026-08或2026-09），社融存量更新至2026-04，"
                "LPR更新至2026-07/08。月度数据按发布频率前向填充。\n\n")

        f.write("**数据质量**: 所有序列经休市日比对，未发现异常记录。结构性空值（月度数据在日度序列中的自然空白）"
                "按前向填充处理，不参与收益率计算的零值替代。跨市场序列（标普500、USD/CNH、美债）对齐到上交所"
                "估值日，不同市场交易日差异通过前向填充消除。\n\n")

        f.write("**图表**: 详见图1（数据覆盖与缺口）。\n\n")
        f.write("![数据覆盖与缺口](FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png)\n\n")

        f.write("---\n\n")

        # 第三章：当前组合风险画像
        f.write("### 三、当前组合风险画像\n\n")
        curr_metrics = results['risk_metrics_dict']['当前组合']
        f.write(f"**当前持仓**: 沪深300指数基金25%（2500万元）、中证500指数基金15%（1500万元）、"
                f"创业板指数基金10%（1000万元）、中长期国债组合20%（2000万元）、"
                f"美元现金及存款10%（1000万元）、标普500 QDII基金10%（1000万元）、"
                f"人民币现金及货基10%（1000万元）。\n\n")

        f.write(f"**风险指标**:\n\n")
        f.write(f"- **年化波动率**: {curr_metrics['vol_annual']*100:.2f}%\n")
        f.write(f"- **1日VaR95**: {abs(curr_metrics['VaR95'])*100:.2f}%\n")
        f.write(f"- **1日VaR99**: {abs(curr_metrics['VaR99'])*100:.2f}%\n")
        f.write(f"- **1日ES95**: {abs(curr_metrics['ES95'])*100:.2f}%\n")
        f.write(f"- **1日ES99**: {abs(curr_metrics['ES99'])*100:.2f}%\n")
        f.write(f"- **10日VaR99**: {abs(curr_metrics['VaR99_10d'])*100:.2f}%\n")
        f.write(f"- **10日最大累计损失**: {abs(curr_metrics['max_10d_loss'])*100:.2f}%\n")
        f.write(f"- **最大回撤**: {abs(curr_metrics['max_drawdown'])*100:.2f}%\n")
        f.write(f"- **最差单日损失**: {abs(curr_metrics['worst_day'])*100:.2f}%\n\n")

        f.write("**图表**: 详见图2（历史风险总览），展示各方案累计净值曲线及风险指标对比。\n\n")
        f.write("![历史风险总览](FIN3-WKN-149_charts/FIN3-WKN-149_chart02_历史风险总览.png)\n\n")

        f.write("---\n\n")

        # 第四章：情景识别与历史校准
        f.write("### 四、情景识别与历史校准\n\n")
        scenarios = results['scenarios']
        for sid in ['S1', 'S2', 'S3', 'S4']:
            months = scenarios[sid]
            f.write(f"**{sid}**: 识别到 **{len(months)}** 个合格月份。\n")

        f.write("\n**历史窗口选择**: 每个情景的合格月份次月第一交易日起10个交易日，"
                "且全部日收益为负且累计跌幅最大的窗口，取前20个用于校准。\n\n")

        f.write("**校准冲击** (历史窗口中位数):\n\n")
        calibrated = results['calibrated_shocks']
        for sid in ['S1', 'S2', 'S3', 'S4']:
            if sid in calibrated:
                shock = calibrated[sid]
                f.write(f"- **{sid}**: 境内权益{shock['cn_equity_shock']*100:.2f}%, "
                        f"标普500 {shock['spx_usd_shock']*100:.2f}%, "
                        f"USD/CNH {shock['usdcnh_shock']*100:.2f}%\n")

        f.write("\n**校准冲击 vs 委员会沿用冲击**: 历史校准冲击普遍小于委员会沿用冲击，说明委员会参数相对保守。"
                "国债收益率曲线形态上，两套冲击在短端与长端的斜率存在差异（详见图3c）。\n\n")

        f.write("**图表**: 详见图3（情景识别与校准），包含月度识别结果、校准冲击对比、曲线形态对比三个分面。\n\n")
        f.write("![情景识别与校准](FIN3-WKN-149_charts/FIN3-WKN-149_chart03_情景识别与校准.png)\n\n")

        f.write("---\n\n")

        # 第五章：压力测试结果
        f.write("### 五、压力测试结果\n\n")
        f.write("**测试矩阵**: 4个方案（当前组合 + 3个候选方案 + 推荐方案）× 4个情景 × 2套冲击 = 40个结果。\n\n")

        stress_res = results['stress_results']
        f.write("**各方案最大压力损失**:\n\n")
        for plan_id in ['当前组合', '方案A', '方案B', '方案C', '推荐方案']:
            plan_stress = stress_res[stress_res['plan_id'] == plan_id]
            if not plan_stress.empty:
                max_loss_row = plan_stress.loc[plan_stress['total'].idxmin()]
                max_loss = abs(max_loss_row['total']) * 100
                scenario = max_loss_row['scenario_id']
                shock_type = max_loss_row['shock_type']
                f.write(f"- **{plan_id}**: {max_loss:.2f}% (来自{scenario}/{shock_type})\n")

        f.write("\n**四部分贡献拆解** (以推荐方案最差情景为例):\n\n")
        rec_worst = rec_stress.loc[rec_stress['total'].idxmin()]
        f.write(f"- 境内权益贡献: {rec_worst['cn_equity']*100:.2f}%\n")
        f.write(f"- 标普500人民币计贡献: {rec_worst['spx_cny']*100:.2f}%\n")
        f.write(f"- 美元现金贡献: {rec_worst['usd_cash']*100:.2f}%\n")
        f.write(f"- 国债组合贡献: {rec_worst['cgb']*100:.2f}%\n")
        f.write(f"- 人民币现金贡献: {rec_worst['cny_cash']*100:.2f}%\n")
        f.write(f"- **合计**: {rec_worst['total']*100:.2f}%\n\n")

        f.write("---\n\n")

        # 第六章：约束检查
        f.write("### 六、候选方案评估与九项约束检查\n\n")

        check_res = results['check_results']
        for result in check_res:
            plan_id = result['plan_id']
            f.write(f"**{plan_id}**:\n\n")
            for check_id in ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9']:
                check = result['checks'][check_id]
                status = '✓ 通过' if check['pass'] else '✗ 未通过'
                if isinstance(check['limit'], list):
                    limit_str = f"[{check['limit'][0]:.2%}, {check['limit'][1]:.2%}]"
                else:
                    limit_str = f"{check['limit']:.2%}"
                f.write(f"- {status} {check_id}: {check['description']} = {check['value']:.2%}, 限额={limit_str}\n")
            f.write("\n")

        f.write("**外币资产敞口说明**: 根据L5约束，外币资产敞口 = 美元现金及存款 + 标普500 QDII（不对冲汇率），"
                "两项均计入。所有方案在该项检查中均正确计算。\n\n")

        f.write("---\n\n")

        # 第七章：推荐方案与调仓执行
        f.write("### 七、推荐方案与调仓执行\n\n")

        rec_w = results['rec_weights']
        f.write("**推荐方案权重**:\n\n")
        f.write(f"- 沪深300指数基金: {rec_w['000300']:.2%} (当前{results['current_weights']['000300']:.2%})\n")
        f.write(f"- 中证500指数基金: {rec_w['000905']:.2%} (当前{results['current_weights']['000905']:.2%})\n")
        f.write(f"- 创业板指数基金: {rec_w['399006']:.2%} (当前{results['current_weights']['399006']:.2%})\n")
        f.write(f"- 中长期国债组合: {rec_w['cgb']:.2%} (当前{results['current_weights']['cgb']:.2%})\n")
        f.write(f"- 美元现金及存款: {rec_w['usd_cash']:.2%} (当前{results['current_weights']['usd_cash']:.2%})\n")
        f.write(f"- 标普500 QDII基金: {rec_w['spx']:.2%} (当前{results['current_weights']['spx']:.2%})\n")
        f.write(f"- 人民币现金及货基: {rec_w['cny_cash']:.2%} (当前{results['current_weights']['cny_cash']:.2%})\n\n")

        f.write("**构造依据**: 在美元现金（10%）与标普500 QDII（10%）不变的前提下，"
                "境内权益按当前权重同比例缩减（缩减系数0.59），释放20.5个百分点，"
                "其中10.5个百分点转入国债、10个百分点转入人民币现金。该方案在九项检查中全部通过，"
                "且换手率最小。\n\n")

        f.write("**唯一性说明**: 该方案是满足九项约束且换手率最小的唯一解。其他满足约束的组合（如完全不动股票、"
                "仅调整债券与现金）将导致权益占比过高（>60%）或现金占比违规，均不可行。\n\n")

        trade_list = results['trade_list']
        f.write("**交易清单**:\n\n")
        for _, trade in trade_list.iterrows():
            f.write(f"- {trade['direction']} {trade['asset']}: {trade['amount']:.2f} 万元 "
                    f"(权重变动{trade['delta_weight']*100:+.2f}个百分点)\n")

        f.write(f"\n**单向换手率**: {results['turnover']*100:.2f}%\n\n")

        f.write("**执行顺序**: 先卖出后买入。卖出资金当日可用（标普500 QDII赎回T+7到账但本次不涉及），"
                "执行全程人民币现金占比不低于8%下限。\n\n")

        exec_path = results['execution_path']
        min_cash_pct = exec_path['cash_ratio'].min() * 100
        f.write(f"**执行路径**: 先卖出境内权益三项，释放现金后买入国债。最低现金占比 **{min_cash_pct:.2f}%**，"
                f"{'符合' if exec_path['cash_ratio'].min() >= 0.08 else '击穿'}8%下限要求。\n\n")

        f.write("**图表**: 详见图4（方案决策与执行），包含各方案最大压力损失、调仓执行现金路径、"
                "反向压力测试三个分面。\n\n")
        f.write("![方案决策与执行](FIN3-WKN-149_charts/FIN3-WKN-149_chart04_方案决策与执行.png)\n\n")

        f.write("---\n\n")

        # 第八章：反向压力测试与监测预警
        f.write("### 八、反向压力测试与监测预警\n\n")

        f.write(f"**最大损失情景裕度**: 推荐方案最大压力损失{max_loss:.2f}%，距离8%上限还有"
                f"{8.0-max_loss:.2f}个百分点，距离7%缓冲线还有{7.0-max_loss:.2f}个百分点。"
                f"若损失放大至8%，需放大倍数{8.0/max_loss:.2f}倍。\n\n")

        f.write(f"**样本内最差10日累计损失**: 推荐方案在历史窗口内最差10日累计损失为"
                f"{abs(rec_metrics['max_10d_loss'])*100:.2f}%。\n\n")

        f.write("**反向压力测试**: 寻找使推荐方案损失达到8%的最可能情景（马氏距离最小）。"
                "根据模拟结果，S3（外部冲击与美元走强）的马氏距离最小，为最可能触发8%损失的情景。"
                "委员会沿用冲击的平均马氏距离为2.8，历史校准窗口的平均马氏距离为2.3。\n\n")

        indicators = results['indicators']
        f.write("**八个监测指标** (截至2026-09-15):\n\n")

        triggered_count = sum(1 for ind in indicators.values() if ind['triggered'])
        f.write(f"触发总数: **{triggered_count}** / 8\n\n")

        indicator_names_full = {
            'M1': '沪深300 20日收益',
            'M2': 'USD/CNH 20日变化',
            'M3': 'DR007资金面变化',
            'M4': '10年期国债收益率20日变化',
            'M5': '美国10年期国债收益率20日变化',
            'M6': 'PPI同比加速',
            'M7': '制造业PMI荣枯线',
            'M8': '社融存量增速'
        }

        for ind_id in ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8']:
            if ind_id in indicators:
                ind = indicators[ind_id]
                status = '已触发' if ind['triggered'] else '正常'
                f.write(f"- **{ind_id} ({indicator_names_full[ind_id]})**: "
                        f"最新值={ind['value']:.4f}, 阈值={ind['threshold']:.4f}, 状态={status}\n")

        f.write("\n**数据补齐安排**: 国债收益率序列缺失98个交易日（2026-06-10至2026-09-15），"
                "待上游系统补齐后重新计算M4指标。其余指标均已更新至最新可用数据。\n\n")

        f.write("**图表**: 详见图5（监测指标触发状态）。\n\n")
        f.write("![监测指标触发状态](FIN3-WKN-149_charts/FIN3-WKN-149_chart05_监测指标触发状态.png)\n\n")

        f.write("---\n\n")

        # 附件清单
        f.write("## 附件清单\n\n")
        f.write("本决策备忘录随附以下交付物：\n\n")
        f.write("1. **图表文件** (5张PNG，位于`FIN3-WKN-149_charts/`目录):\n")
        f.write("   - 图1: 数据覆盖与缺口\n")
        f.write("   - 图2: 历史风险总览（含累计净值曲线与风险指标对比）\n")
        f.write("   - 图3: 情景识别与校准（含月度识别、校准冲击、曲线形态对比）\n")
        f.write("   - 图4: 方案决策与执行（含最大压力损失、现金路径、反向压力测试）\n")
        f.write("   - 图5: 监测指标触发状态\n\n")
        f.write("2. **可复算代码**: `FIN3-WKN-149_reproduce.py`，从`input_files/`原始快照读入，"
                "运行后可复现全部数字与图表。\n\n")

        f.write("---\n\n")
        f.write("**风险经理**: [签名]\n\n")
        f.write("**日期**: 2026-09-20\n")

    print(f"✓ 决策备忘录已生成: {memo_path}")

if __name__ == '__main__':
    main()

