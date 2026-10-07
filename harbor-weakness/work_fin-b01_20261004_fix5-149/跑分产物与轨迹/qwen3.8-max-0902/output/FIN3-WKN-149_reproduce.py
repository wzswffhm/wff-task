#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-149 多资产稳健配置专户 三季度宏观压力测试与调仓建议 —— 可复算代码
=============================================================================
- 仅读取 /app/input_files/ 下的原始快照与参数、规则、模板文件（只读，不修改）。
- 不硬编码任何结论数值：所有指标、表格、图形均由原始数据计算得出。
- 运行后将 10 张 PNG 图表写入 /app/output/FIN3-WKN-149_charts/，
  并把备忘录中引用的全部数字打印到标准输出（建议重定向保存）。

运行方式：
    python3 FIN3-WKN-149_reproduce.py > results.txt

主要口径（与备忘录第二章一致）：
- 分析截至日 ASOF = 上交所交易日历中最大日期（数据推导，非硬编码）。
- 组合收益样本区间 = 七个资产袖（sleeve）收益全部可用的区间；
  终止日由中债国债收益率序列的实际截止日决定（数据推导）。
- 所有跨市场序列先对齐到上交所估值日（交易日）：以“并集索引 + 前向填充 +
  截取上交所日历”方式对齐；前向填充不超过各序列自身最后观测日（不外推）；
  结构性空值（如 5 年期 LPR 在 2019-08-20 之前）保持 NaN，不按 0 参与计算。
- 国债组合收益 = -Σ(关键期限久期贡献 × 该期限收益率日变动)，久期取自
  params_duration.csv；标普500 QDII 人民币收益 = (1+r_SPX,USD)×(1+r_FX)-1 复合折算。
- 组合日收益 = Σ(方案权重 × 资产日收益)，权重每日再平衡。
- 年化因子 = 244（上交所年均交易日）。
- 月度宏观数据（PMI/PPI/社融）按“发布月-1=数据所属月”映射（文件日期为发布标记日）。
- 委员会情景 cgb_shock_bp 字段数值口径判定为“百分点”（+0.10 = +10bp），
  依据：字段量级 0.10~0.80 与历史 10 日窗口国债收益率变动（校准冲击）同量级，
  若按 0.10bp 解释则冲击无经济意义（备忘录第二、五章说明）。
"""

import os
import re
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Noto Sans CJK JP', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

IN = '/app/input_files/'
OUT = '/app/output/'
CHART = os.path.join(OUT, 'FIN3-WKN-149_charts')
os.makedirs(CHART, exist_ok=True)

ANN = 244            # 年化因子（上交所年均交易日）
NAV = None           # 组合净值（万元），由 params_positions.csv 求和得到
pd.set_option('display.width', 200)

SEP = '=' * 100

def hdr(title):
    print('\n' + SEP)
    print('### ' + title)
    print(SEP)

def fmt_pct(x, nd=2):
    return f'{x * 100:.{nd}f}%'

def fmt_bp(x_pct_points, nd=2):
    """输入为百分点，输出 bp 字符串"""
    return f'{x_pct_points * 100:.{nd}f}bp'

# ============================================================================
# 第 1 部分：读取原始数据 + 数据核验（备忘录第二章）
# ============================================================================
hdr('1. 数据加载与核验（第二章素材）')

cal = pd.read_csv(IN + 'snapshot_trade_calendar.csv', parse_dates=['date'])
cal = cal[cal['exchange'] == 'SSE'].copy()
SSE = cal.loc[cal['is_trading_day'] == 1, 'date'].sort_values().reset_index(drop=True)
ASOF = SSE.max()
print(f'上交所交易日历: {len(SSE)} 个交易日, {SSE.min().date()} ~ {ASOF.date()} (ASOF 由日历最大日推导)')
print(f'日历中 is_trading_day 取值: {sorted(cal.is_trading_day.unique())}; 非交易日行数: {(cal.is_trading_day != 1).sum()}')

manifest = pd.read_csv(IN + 'snapshot_data_manifest.csv')

def load_seg(prefix, parse_cols=None):
    a = pd.read_csv(IN + f'snapshot_{prefix}_seg1.csv', parse_dates=['date'])
    b = pd.read_csv(IN + f'snapshot_{prefix}_seg2.csv', parse_dates=['date'])
    return a, b

audit_rows = []   # 数据核验汇总表

def audit_series(name, df, valcols, expect_sse_only=False):
    """通用核验：重复、空值、非上交所日记录、区间内缺失交易日、极值"""
    df = df.sort_values('date').reset_index(drop=True)
    rec = {'序列': name, '行数': len(df),
           '起始': str(df['date'].min().date()), '截止': str(df['date'].max().date()),
           '重复日期': int(df['date'].duplicated().sum())}
    for c in valcols:
        rec[f'空值_{c}'] = int(df[c].isna().sum())
    non_sse = df[~df['date'].isin(set(SSE))]
    rec['非上交所日记录'] = len(non_sse)
    rec['非上交所日样例'] = ','.join(str(d.date()) for d in non_sse['date'].head(3))
    span = SSE[(SSE >= df['date'].min()) & (SSE <= df['date'].max())]
    missing = sorted(set(span) - set(df['date']))
    rec['区间内缺失上交所交易日'] = len(missing)
    rec['缺失样例'] = ','.join(str(d.date()) for d in missing[:3])
    return rec, df, missing

# ---- A 股权益指数（seg1+seg2 拼接，剔除非上交所交易日的休市日异常记录） ----
EQ_CODE = {'EQ_000300': '000300SH', 'EQ_000905': '000905SH', 'EQ_399006': '399006SZ'}
EQ_NAME = {'EQ_000300': '沪深300', 'EQ_000905': '中证500', 'EQ_399006': '创业板指'}
eq_close = {}
anomaly_rows = []
for cls, code in EQ_CODE.items():
    a, b = load_seg(code)
    df = pd.concat([a, b], ignore_index=True)
    rec, df, missing = audit_series(code, df, ['open', 'high', 'low', 'close', 'pre_close', 'amount'])
    rec['seg重叠日期'] = len(set(a['date']) & set(b['date']))
    # 休市日异常记录识别：日期不在上交所交易日历内
    bad = df[~df['date'].isin(set(SSE))].copy()
    for _, r0 in bad.iterrows():
        anomaly_rows.append({'序列': code, '日期': str(r0['date'].date()),
                             '星期': r0['date'].day_name(),
                             'open': r0['open'], 'high': r0['high'], 'low': r0['low'],
                             'close': r0['close'], 'pre_close': r0['pre_close'],
                             'amount': r0['amount'],
                             'OHLC全同': bool(r0['open'] == r0['high'] == r0['low'] == r0['close']),
                             '量比(异常/前5日均量)': None})
    df_clean = df[df['date'].isin(set(SSE))].copy()
    # 前收一致性（剔除异常后 close.shift 与 pre_close 对照）
    mm = (df_clean['pre_close'] - df_clean['close'].shift(1)).abs()
    rec['pre_close不一致(>0.01)'] = int((mm > 0.01).sum())
    ret_chk = df_clean['close'].pct_change()
    rec['最大单日绝对涨幅'] = f'{ret_chk.abs().max() * 100:.2f}%@{df_clean["date"].iloc[np.nanargmax(ret_chk.abs().values)].date()}'
    rec['剔除休市日异常行数'] = len(bad)
    audit_rows.append(rec)
    s = df_clean.set_index('date')['close']
    # 异常行前后量比
    for ar in anomaly_rows:
        if ar['序列'] == code and ar['量比(异常/前5日均量)'] is None:
            d0 = pd.Timestamp(ar['日期'])
            prev5 = df_clean.loc[df_clean['date'] < d0, 'amount'].tail(5).mean()
            bad_amt = df.loc[df['date'] == d0, 'amount'].iloc[0]
            ar['量比(异常/前5日均量)'] = round(float(bad_amt / prev5), 4)
    eq_close[cls] = s

print('\n休市日异常记录（识别依据：日期不在上交所交易日历 + OHLC 全同 + 成交额异常）:')
print(pd.DataFrame(anomaly_rows).to_string(index=False))

# ---- 跨市场序列 ----
u1, u2 = load_seg('usdcnh')
usdcnh_raw = pd.concat([u1, u2], ignore_index=True)
rec, usdcnh_raw, miss_fx = audit_series('USDCNH', usdcnh_raw, ['usdcnh'])
rec['seg重叠日期'] = len(set(u1['date']) & set(u2['date']))
rec['最大单日变动'] = f'{usdcnh_raw["usdcnh"].pct_change().abs().max() * 100:.2f}%'
audit_rows.append(rec)
usdcnh = usdcnh_raw.set_index('date')['usdcnh'].sort_index()

spx_raw = pd.read_csv(IN + 'snapshot_spx.csv', parse_dates=['date'])
rec, spx_raw, miss_spx = audit_series('SPX', spx_raw, ['close'])
rec['最大单日绝对涨跌'] = f'{spx_raw["close"].pct_change().abs().max() * 100:.2f}%'
audit_rows.append(rec)
spx = spx_raw.set_index('date')['close'].sort_index()

s1, s2 = load_seg('shibor')
shibor_raw = pd.concat([s1, s2], ignore_index=True)
rec, shibor_raw, _ = audit_series('SHIBOR', shibor_raw, ['shibor_on', 'shibor_1w'])
rec['seg重叠日期'] = len(set(s1['date']) & set(s2['date']))
audit_rows.append(rec)

dr_raw = pd.read_csv(IN + 'snapshot_dr007.csv', parse_dates=['date'])
rec, dr_raw, _ = audit_series('DR007', dr_raw, ['dr007'])
audit_rows.append(rec)
dr007 = dr_raw.set_index('date')['dr007'].sort_index()

# DR007 与 Shibor 1W 的一致性检查（上游字段复制问题）
shibor = shibor_raw.set_index('date').sort_index()
common = dr007.index.intersection(shibor.index)
same = bool((dr007.loc[common] == shibor.loc[common, 'shibor_1w']).all())
print(f'\n[数据质量] DR007 与 Shibor1W 在全部 {len(common)} 个共同日期上取值完全相同: {same}'
      f'（相关系数={dr007.loc[common].corr(shibor.loc[common, "shibor_1w"]):.6f}）→ 疑似上游字段复制，按原样使用并在备忘录中披露')

cgb_raw = {}
for t in ['1y', '2y', '5y', '10y', '30y']:
    df = pd.read_csv(IN + f'snapshot_cgb_yield_{t}.csv', parse_dates=['date'])
    rec, df, _ = audit_series(f'中债国债{t.upper()}', df, ['yield_pct'])
    dy = df['yield_pct'].diff()
    imax = int(np.nanargmax(dy.abs().values))
    rec['最大单日变动'] = f'{dy.iloc[imax] * 100:+.1f}bp@{df["date"].iloc[imax].date()}'
    audit_rows.append(rec)
    cgb_raw[t] = df.set_index('date')['yield_pct'].sort_index()

ust = {}
for t in ['10y', 'm2', 'm4']:
    df = pd.read_csv(IN + f'snapshot_ust_{t}.csv', parse_dates=['date'])
    rec, df, _ = audit_series(f'美债UST_{t.upper()}', df, ['yield_pct'])
    audit_rows.append(rec)
    ust[t] = df.set_index('date')['yield_pct'].sort_index()

lpr_raw = {}
for t in ['1y', '5y']:
    df = pd.read_csv(IN + f'snapshot_lpr_{t}.csv', parse_dates=['date'])
    rec, df, _ = audit_series(f'LPR_{t.upper()}', df, [f'lpr_{t}'])
    first = df[f'lpr_{t}'].first_valid_index()
    rec['结构性空值(首值前)'] = int(first)
    rec['首值后空值'] = int(df.loc[first:, f'lpr_{t}'].isna().sum())
    rec['首个有效值'] = f'{df.loc[first, "lpr_5y" if t == "5y" else "lpr_1y"]}@{df.loc[first, "date"].date()}'
    audit_rows.append(rec)
    lpr_raw[t] = df.set_index('date')[f'lpr_{t}'].sort_index()

pmi_raw = pd.read_csv(IN + 'snapshot_pmi_manufacturing.csv', parse_dates=['date'])
ppi_raw = pd.read_csv(IN + 'snapshot_ppi_yoy.csv', parse_dates=['date'])
afre_raw = pd.read_csv(IN + 'snapshot_afre_stock.csv', parse_dates=['date'])
for nm, df, col in [('PMI制造业', pmi_raw, 'pmi_mfg'), ('PPI同比', ppi_raw, 'ppi_yoy'), ('社融存量', afre_raw, 'afre_stock')]:
    rec = {'序列': nm, '行数': len(df), '起始': str(df['date'].min().date()), '截止': str(df['date'].max().date()),
           '重复日期': int(df['date'].duplicated().sum()), f'空值_{col}': int(df[col].isna().sum())}
    months_have = set(df['date'].dt.to_period('M'))
    months_all = pd.period_range(df['date'].min(), df['date'].max(), freq='M')
    rec['缺失发布月'] = ','.join(str(p) for p in months_all if p not in months_have)
    audit_rows.append(rec)

audit_df = pd.DataFrame(audit_rows)
print('\n数据核验汇总表:')
print(audit_df.to_string(index=False))

# manifest 与实际文件的一致性
print('\nmanifest 与实际文件对照（records 一致性 / possible_truncation 标记可靠性）:')
for _, m in manifest.iterrows():
    f = m['file']
    if f in ('snapshot_data_manifest.csv',):
        continue
    actual = sum(1 for _ in open(IN + f)) - 1
    flag = '一致' if actual == m['records'] else f"不一致(实际{actual})"
    print(f"  {f:38s} manifest={m['records']:5d} 实际={actual:5d} {flag}  truncation标记={m['possible_truncation']!r}  区间={m['start']}~{m['end']}")

# ============================================================================
# 第 2 部分：对齐到上交所估值日 + 资产袖收益构建
# ============================================================================
hdr('2. 价格对齐与资产袖收益构建（第二、三章素材）')

def align_union(s: pd.Series) -> pd.Series:
    """并集索引 + 前向填充 + 截取上交所日历；不超过序列自身最后观测日（不外推）；
    结构性空值（序列首值之前）保持 NaN。"""
    s = s.sort_index()
    idx = s.index.union(SSE)
    idx = idx[idx <= s.index.max()]
    filled = s.reindex(idx).ffill()
    return filled.reindex(SSE)

aligned = {}
for cls, code in EQ_CODE.items():
    aligned[cls] = align_union(eq_close[cls])
aligned['USDCNH'] = align_union(usdcnh)
aligned['SPX'] = align_union(spx)
for t in ['1y', '2y', '5y', '10y', '30y']:
    aligned['CGB_' + t] = align_union(cgb_raw[t])
aligned['UST10Y'] = align_union(ust['10y'])
aligned['DR007'] = align_union(dr_raw.set_index('date')['dr007'].sort_index())
aligned['SHIBOR_ON'] = align_union(shibor['shibor_on'].sort_index())
aligned['SHIBOR_1W'] = align_union(shibor['shibor_1w'].sort_index())

# 对齐质量检查
print('对齐后各序列在上交所日历上的覆盖（非 NaN 数 / 首日 / 末日）:')
for k, v in aligned.items():
    vv = v.dropna()
    print(f'  {k:12s} 覆盖 {len(vv):5d}/{len(SSE)} 首日 {vv.index.min().date()} 末日 {vv.index.max().date()}'
          f'  区间内ffill补日数 {int(v.notna().sum() - len(vv.dropna())) if False else ""}', end='')
    # 原始序列缺失、靠 ffill 补的上交所日数量
    raw_idx = {'EQ_000300': eq_close['EQ_000300'], 'EQ_000905': eq_close['EQ_000905'],
               'EQ_399006': eq_close['EQ_399006'], 'USDCNH': usdcnh, 'SPX': spx}.get(k)
    if raw_idx is not None:
        span = SSE[(SSE >= raw_idx.index.min()) & (SSE <= raw_idx.index.max())]
        n_ffill = len(set(span) - set(raw_idx.index))
        print(f'  ffill补日 {n_ffill}')
    else:
        print()

# ---- 参数文件 ----
hold = pd.read_csv(IN + 'params_holdings.csv')
pos = pd.read_csv(IN + 'params_positions.csv')
NAV = float(pos['market_value_10k_cny'].sum())
print(f'\n组合净值 NAV = {NAV:.2f} 万元（由 params_positions.csv 求和）')
dur = pd.read_csv(IN + 'params_duration.csv')
TENOR_MAP = {'1年': '1y', '2年': '2y', '5年': '5y', '10年': '10y', '30年': '30y'}
DUR = {TENOR_MAP[r['tenor']]: float(r['duration_contribution']) for _, r in dur.iterrows()}
PORT_DUR = sum(DUR.values())
print(f'久期贡献: {DUR}  组合久期合计 = {PORT_DUR:.2f}')

limits = pd.read_csv(IN + 'params_limits.csv')
checks = pd.read_csv(IN + 'rules_checks.csv')
shocks_com = pd.read_csv(IN + 'params_committee_shocks.csv')
plans = pd.read_csv(IN + 'plans_candidates.csv')
rules_scen = pd.read_csv(IN + 'rules_scenarios.csv')
rules_win = pd.read_csv(IN + 'rules_windows.csv')
rules_reb = pd.read_csv(IN + 'rules_rebalance.csv')
monitor_tpl = pd.read_csv(IN + 'template_monitor.csv')

def parse_cgb_shock(s):
    """'1Y:+0.10,2Y:+0.12,...' -> {'1y':0.10,...}（百分点）"""
    out = {}
    for part in s.split(','):
        k, v = part.split(':')
        out[k.strip().lower()] = float(v)
    return out

COM_SHOCK = {}
for _, r in shocks_com.iterrows():
    COM_SHOCK[r['scenario_id']] = {
        'eq': float(r['cn_equity_shock']), 'spx': float(r['spx_usd_shock']),
        'fx': float(r['usdcnh_shock']), 'cgb': parse_cgb_shock(r['cgb_shock_bp'])}
print('\n委员会沿用冲击（cgb 字段按百分点口径，+0.10=+10bp）:')
for k, v in COM_SHOCK.items():
    print(f"  {k}: 境内权益 {v['eq']*100:+.2f}%  SPX(USD) {v['spx']*100:+.2f}%  USDCNH {v['fx']*100:+.2f}%  "
          f"国债bp {{{', '.join(f'{t}:{bp*100:+.0f}' for t, bp in v['cgb'].items())}}}")

# ---- 方案权重 ----
W = {}
W['当前组合'] = dict(zip(hold['asset_class'], hold['weight_current']))
W['推荐方案'] = dict(zip(hold['asset_class'], hold['weight_recommended']))
for _, r in plans.iterrows():
    W[r['plan_id']] = {'EQ_000300': r['w_000300'], 'EQ_000905': r['w_000905'], 'EQ_399006': r['w_399006'],
                       'CGB': r['w_cgb'], 'USD_CASH': r['w_usd_cash'], 'SPX': r['w_spx_qdii'],
                       'CNY_CASH': r['w_cny_cash']}
PLAN_ORDER = ['当前组合', '方案A', '方案B', '方案C', '推荐方案']
print('\n各方案权重:')
print(pd.DataFrame(W).T.to_string(float_format=lambda x: f'{x*100:.2f}%'))

# 推荐方案构造校验（依据 rules_rebalance.recommendation_rule，全部由文件数据推导）
rec_rule = rules_reb.set_index('key').loc['recommendation_rule', 'value']
cur_eq = sum(W['当前组合'][c] for c in EQ_CODE)
rec_eq = sum(W['推荐方案'][c] for c in EQ_CODE)
shrink = {c: W['推荐方案'][c] / W['当前组合'][c] for c in EQ_CODE}
print(f'\n推荐方案构造校验: 权益合计 {cur_eq*100:.2f}% -> {rec_eq*100:.2f}% (减配 {(cur_eq-rec_eq)*100:.2f}pp), '
      f'三项缩减系数 {[round(v,4) for v in shrink.values()]}, '
      f'美元现金变动 {(W["推荐方案"]["USD_CASH"]-W["当前组合"]["USD_CASH"])*100:+.2f}pp, '
      f'SPX变动 {(W["推荐方案"]["SPX"]-W["当前组合"]["SPX"])*100:+.2f}pp, '
      f'国债 {(W["推荐方案"]["CGB"]-W["当前组合"]["CGB"])*100:+.2f}pp, '
      f'人民币现金 {(W["推荐方案"]["CNY_CASH"]-W["当前组合"]["CNY_CASH"])*100:+.2f}pp')
print(f'规则原文: {rec_rule}')

# ---- 资产袖日收益 ----
ret_eq = {c: aligned[c].pct_change() for c in EQ_CODE}
dy = {t: aligned['CGB_' + t].diff() / 100.0 for t in DUR}          # 小数变动
ret_cgb = -sum(DUR[t] * dy[t] for t in DUR)                        # 久期折算
ret_fx = aligned['USDCNH'].pct_change()
ret_spx_usd = aligned['SPX'].pct_change()
ret_spx_cny = (1 + ret_spx_usd) * (1 + ret_fx) - 1                 # 复合折算
ret_usd_cash = ret_fx                                              # 美元现金人民币收益=汇率变动
ret_cny_cash = pd.Series(0.0, index=SSE)

SLEEVE = pd.DataFrame({
    'EQ_000300': ret_eq['EQ_000300'], 'EQ_000905': ret_eq['EQ_000905'], 'EQ_399006': ret_eq['EQ_399006'],
    'CGB': ret_cgb, 'USD_CASH': ret_usd_cash, 'SPX': ret_spx_cny, 'CNY_CASH': ret_cny_cash})

valid = SLEEVE.dropna()
SAMPLE_START, SAMPLE_END = valid.index.min(), valid.index.max()
N_DAYS = len(valid)
print(f'\n组合收益样本区间: {SAMPLE_START.date()} ~ {SAMPLE_END.date()}  交易日收益数 N = {N_DAYS}')
print(f'样本终止原因: 中债国债收益率各期限序列实际截止 {aligned["CGB_10y"].dropna().index.max().date()}'
      f'（其后为 NaN，结构性缺失不外推、不按0计），权益/汇率/标普序列覆盖至 {ASOF.date()}')
R = SLEEVE.loc[SAMPLE_START:SAMPLE_END].dropna()

def port_ret(w):
    wv = np.array([w[c] for c in R.columns])
    return R.values @ wv

port_rets = pd.DataFrame({p: pd.Series(port_ret(W[p]), index=R.index) for p in PLAN_ORDER})

# ---- 单资产统计与相关性（第三章） ----
hdr('3. 当前组合风险画像（第三章素材）')
stats = pd.DataFrame({
    '年化收益': R.mean() * ANN, '年化波动': R.std(ddof=1) * np.sqrt(ANN),
    '偏度': R.skew(), '峰度': R.kurt(),
    '最差单日': R.min(), '最好单日': R.max(),
    '1日VaR99': -R.quantile(0.01), '1日ES99': -R[R <= R.quantile(0.01)].mean(),
})
stats.index = [f'{EQ_NAME.get(c, c)}' for c in stats.index]
stats = stats.rename(index={'CGB': '国债组合(久期折算)', 'USD_CASH': '美元现金(汇率)', 'SPX': '标普500QDII(人民币复合)',
                            'CNY_CASH': '人民币现金'})
print('各资产袖日收益统计特征（样本 %s~%s, N=%d）:' % (SAMPLE_START.date(), SAMPLE_END.date(), N_DAYS))
stats_show = stats.copy()
for c0 in ['年化收益', '年化波动', '最差单日', '最好单日', '1日VaR99', '1日ES99']:
    stats_show[c0] = stats_show[c0] * 100
print(stats_show.round(3).to_string(), '\n(收益/波动/极值/VaR/ES 单位:%；偏度、峰度为无量纲)')

corr = R.corr()
corr_show = corr.copy()
corr_show.index = stats.index
corr_show.columns = stats.index
print('\n资产袖日收益相关矩阵:')
print(corr_show.round(4).to_string())

# 组合风险指标函数
def risk_metrics(r: pd.Series):
    r = r.dropna()
    nav = (1 + r).cumprod()
    peak = nav.cummax()
    dd = nav / peak - 1
    i_trough = dd.values.argmin()
    mdd = dd.iloc[i_trough]
    t_trough = dd.index[i_trough]
    peak_val = peak.iloc[i_trough]
    prior = nav.loc[:t_trough]
    i_peak = prior[prior >= peak_val - 1e-12].index[-1]
    after = nav.loc[t_trough:]
    rec_days = after[after >= peak_val - 1e-12]
    t_rec = rec_days.index[0] if len(rec_days) else None
    cum10 = (1 + r).rolling(10).apply(np.prod, raw=True) - 1
    cum10 = cum10.dropna()
    i_w10 = cum10.values.argmin()
    q01, q05 = r.quantile(0.01), r.quantile(0.05)
    return {
        '累计净值': nav.iloc[-1], '年化收益': r.mean() * ANN, '年化波动': r.std(ddof=1) * np.sqrt(ANN),
        '1日VaR95': -q05, '1日VaR99': -q01,
        '1日ES95': -r[r <= q05].mean(), '1日ES99': -r[r <= q01].mean(),
        '10日VaR99': -cum10.quantile(0.01),
        '最差10日累计': cum10.iloc[i_w10],
        '最差10日区间': f'{cum10.index[max(i_w10 - 9, 0)].date()}~{cum10.index[i_w10].date()}',
        '最大回撤': mdd, '回撤高点': i_peak, '回撤低点': t_trough,
        '修复日': t_rec if t_rec is None else t_rec,
        '最差单日': r.min(), '最差单日日期': r.index[r.values.argmin()],
        'cum10': cum10, 'nav': nav, 'dd': dd,
    }

METRICS = {}
for p in PLAN_ORDER:
    m = risk_metrics(port_rets[p])
    METRICS[p] = m

show_cols = ['累计净值', '年化收益', '年化波动', '1日VaR95', '1日VaR99', '1日ES95', '1日ES99',
             '10日VaR99', '最差10日累计', '最大回撤', '最差单日']
mt = pd.DataFrame({p: {k: METRICS[p][k] for k in show_cols} for p in PLAN_ORDER}).T
print('\n各方案组合层面风险指标（历史窗口 %s~%s）:' % (SAMPLE_START.date(), SAMPLE_END.date()))
print((mt[show_cols[:-1]] * 100).round(2).to_string(), '\n(单位:%)')
for p in PLAN_ORDER:
    m = METRICS[p]
    print(f'  {p}: 最差10日区间 {m["最差10日区间"]}; 回撤高点 {m["回撤高点"].date()} 低点 {m["回撤低点"].date()} '
          f'修复日 {m["修复日"].date() if m["修复日"] is not None else "尚未修复"}; '
          f'最差单日 {m["最差单日"]*100:.2f}% @{m["最差单日日期"].date()}')

# 风险贡献（Euler 方差分解，当前组合）
cov_ann = R.cov() * ANN
w_cur = np.array([W['当前组合'][c] for c in R.columns])
pv = w_cur @ cov_ann.values @ w_cur
rc = w_cur * (cov_ann.values @ w_cur) / pv
rc_s = pd.Series(rc, index=stats.index)
print('\n当前组合各资产风险贡献占比（Euler 方差分解，合计=100%）:')
print((rc_s * 100).round(2).to_string())
print(f'当前组合年化波动(校验) = {np.sqrt(pv)*100:.2f}%')

# ============================================================================
# 第 4 部分：情景月度识别（rules_scenarios.csv）与历史窗口校准（rules_windows.csv）
# ============================================================================
hdr('4. 情景月度识别与历史窗口冲击校准（第四章素材）')

# ---- 月度宏观表：文件日期为发布标记日，数据所属月 = 发布月 - 1 ----
def to_data_month(df, col):
    d = df.copy()
    d['dm'] = (pd.to_datetime(d['date']) - pd.Timedelta(days=1)).dt.to_period('M')
    return d.set_index('dm')[col].sort_index()

pmi_m = to_data_month(pmi_raw, 'pmi_mfg')
ppi_m = to_data_month(ppi_raw, 'ppi_yoy')
afre_m = to_data_month(afre_raw, 'afre_stock')
print(f'月度数据映射（数据月=发布月-1）: PMI {pmi_m.index.min()}~{pmi_m.index.max()} (缺 {sorted(set(pd.period_range(pmi_m.index.min(), pmi_m.index.max(), freq="M")) - set(pmi_m.index))}); '
      f'PPI {ppi_m.index.min()}~{ppi_m.index.max()}; 社融 {afre_m.index.min()}~{afre_m.index.max()}')

# LPR 月度值（每月最后一个公布值）与当月下调
def lpr_monthly(s):
    s = s.dropna()
    return s.groupby(s.index.to_period('M')).last()

lpr1_m, lpr5_m = lpr_monthly(lpr_raw['1y']), lpr_monthly(lpr_raw['5y'])
lpr1_cut = lpr1_m.diff() < -1e-9
lpr5_cut = lpr5_m.diff() < -1e-9
print(f'LPR1Y 月度覆盖 {lpr1_m.index.min()}~{lpr1_m.index.max()}, 下调月: {[str(p) for p in lpr1_cut[lpr1_cut].index]}')
print(f'LPR5Y 月度覆盖 {lpr5_m.index.min()}~{lpr5_m.index.max()} (2019-08 前为结构性空值), 下调月: {[str(p) for p in lpr5_cut[lpr5_cut].index]}')

# 月度市场变量（基于对齐序列；月末=当月最后一个上交所交易日的对齐值）
mkt_daily = pd.DataFrame({'eq300': aligned['EQ_000300'], 'spx': aligned['SPX'], 'fx': aligned['USDCNH'],
                          'cgb10y': aligned['CGB_10y'], 'dr007': aligned['DR007']}).loc[SSE.min():ASOF]
month_end = mkt_daily.groupby(mkt_daily.index.to_period('M')).last()
month_mean = mkt_daily.groupby(mkt_daily.index.to_period('M')).mean()
month_cnt = mkt_daily.groupby(mkt_daily.index.to_period('M')).count()
# 各月应有的上交所交易日数（判断部分月）
sse_cnt_m = pd.Series(1, index=pd.DatetimeIndex(SSE)).groupby(pd.DatetimeIndex(SSE).to_period('M')).sum()

mkt_m = pd.DataFrame({
    'eq300_ret': month_end['eq300'].pct_change(),
    'spx_ret': month_end['spx'].pct_change(),
    'fx_chg': month_end['fx'].pct_change(),
    'cgb10y_mean': month_mean['cgb10y'],
    'dr007_mean': month_mean['dr007'],
})
mkt_m['cgb10y_mean_prev'] = mkt_m['cgb10y_mean'].shift(1)
mkt_m['dr007_mean_prev'] = mkt_m['dr007_mean'].shift(1)
# 部分月标记：当月对齐覆盖天数 < 当月应有交易日数（如 2026-06 中债仅到 06-09；2026-09 截至 ASOF）
mkt_m['partial'] = [bool(month_cnt.loc[p].isna().any() or month_cnt.loc[p].min() < sse_cnt_m.get(p, 0))
                    for p in mkt_m.index]
afre_yoy = afre_m / afre_m.shift(12) - 1
pmi_d = pmi_m.diff()

print('\n月度表尾部:')
tail_m = mkt_m.tail(10).copy()
tail_m['afre_yoy'] = afre_yoy.reindex(tail_m.index)
tail_m['pmi'] = pmi_m.reindex(tail_m.index)
tail_m['ppi'] = ppi_m.reindex(tail_m.index)
print(tail_m.round(4).to_string())

# ---- 逐月识别四情景 ----
def identify():
    rows = []
    for M in mkt_m.index:
        if M < pd.Period('2018-01'):
            continue
        row = {'month': M}
        partial = mkt_m.loc[M, 'partial']
        # S1: (PMI<50 且 (LPR1Y或LPR5Y当月下调)) 或 (PMI较上月下行>=0.5 且 10Y国债月均低于上月)
        pmi_v = pmi_m.get(M, np.nan)
        c1a = (pd.notna(pmi_v) and pmi_v < 50) and (bool(lpr1_cut.get(M, False)) or bool(lpr5_cut.get(M, False)))
        dpmi = pmi_d.get(M, np.nan)
        cgb_low = (pd.notna(mkt_m.loc[M, 'cgb10y_mean']) and pd.notna(mkt_m.loc[M, 'cgb10y_mean_prev'])
                   and mkt_m.loc[M, 'cgb10y_mean'] < mkt_m.loc[M, 'cgb10y_mean_prev'])
        c1b = (pd.notna(dpmi) and dpmi <= -0.5) and cgb_low
        row['S1'] = bool(c1a or c1b)
        row['S1_条款'] = ('A:LPR下调' if c1a else '') + ('|B:PMI速降+利率回落' if c1b else '')
        # S2: PPI高于上月 且 10Y国债月均高于上月 且 权益指数当月下跌
        ppi_v, ppi_p = ppi_m.get(M, np.nan), ppi_m.get(M - 1, np.nan)
        c2 = (pd.notna(ppi_v) and pd.notna(ppi_p) and ppi_v > ppi_p
              and pd.notna(mkt_m.loc[M, 'cgb10y_mean']) and pd.notna(mkt_m.loc[M, 'cgb10y_mean_prev'])
              and mkt_m.loc[M, 'cgb10y_mean'] > mkt_m.loc[M, 'cgb10y_mean_prev']
              and pd.notna(mkt_m.loc[M, 'eq300_ret']) and mkt_m.loc[M, 'eq300_ret'] < 0
              and not partial)
        row['S2'] = bool(c2)
        # S3: SPX当月<=-3% 或 USDCNH当月变化>=+1.5%
        spx_r, fx_c = mkt_m.loc[M, 'spx_ret'], mkt_m.loc[M, 'fx_chg']
        c3 = (pd.notna(spx_r) and spx_r <= -0.03) or (pd.notna(fx_c) and fx_c >= 0.015)
        # 部分月（2026-09 截至 ASOF）不参与识别
        if partial and M == pd.Period('2026-09'):
            c3 = False
        row['S3'] = bool(c3)
        row['S3_条款'] = ('SPX<=-3%' if (pd.notna(spx_r) and spx_r <= -0.03) else '') + \
                        ('|FX>=+1.5%' if (pd.notna(fx_c) and fx_c >= 0.015) else '')
        # S4: 社融存量同比增速低于上月 且 DR007月均高于上月 且 权益当月下跌
        g, gp = afre_yoy.get(M, np.nan), afre_yoy.get(M - 1, np.nan)
        c4 = (pd.notna(g) and pd.notna(gp) and g < gp
              and pd.notna(mkt_m.loc[M, 'dr007_mean']) and pd.notna(mkt_m.loc[M, 'dr007_mean_prev'])
              and mkt_m.loc[M, 'dr007_mean'] > mkt_m.loc[M, 'dr007_mean_prev']
              and pd.notna(mkt_m.loc[M, 'eq300_ret']) and mkt_m.loc[M, 'eq300_ret'] < 0)
        row['S4'] = bool(c4)
        rows.append(row)
    return pd.DataFrame(rows).set_index('month')

ident = identify()
# 各情景可评估区间（规则输入齐备）
for sid in ['S1', 'S2', 'S3', 'S4']:
    months = ident.index[ident[sid]]
    print(f'\n{sid} {rules_scen.set_index("scenario_id").loc[sid, "scenario"]}: 合格月份共 {len(months)} 个')
    print('  ' + ', '.join(str(m) for m in months))

# ---- 窗口构造与校准 ----
WIN_LEN = int(rules_win.set_index('key').loc['window_length', 'value'].split()[0])
sse_pos = {d: i for i, d in enumerate(SSE)}

def window_for_month(M):
    """合格月份次月第一个上交所交易日起 10 个交易日；返回窗口日期列表或 None（不完整）"""
    M1 = M + 1
    days = [d for d in SSE if d.to_period('M') == M1]
    if len(days) == 0:
        return None
    start_i = sse_pos[days[0]]
    if start_i + WIN_LEN - 1 >= len(SSE):
        return None
    win = list(SSE[start_i:start_i + WIN_LEN])
    # 组合收益样本必须覆盖整个窗口（中债截止约束）
    if win[-1] > SAMPLE_END or win[0] < SAMPLE_START:
        return None
    return win

port_cur = port_rets['当前组合']
FACTOR_KEYS = ['EQ_000300', 'EQ_000905', 'EQ_399006', 'SPX_USD', 'USDCNH', 'CGB_1y', 'CGB_2y', 'CGB_5y', 'CGB_10y', 'CGB_30y']
fac_daily = pd.DataFrame({
    'EQ_000300': aligned['EQ_000300'], 'EQ_000905': aligned['EQ_000905'], 'EQ_399006': aligned['EQ_399006'],
    'SPX_USD': aligned['SPX'], 'USDCNH': aligned['USDCNH'],
    'CGB_1y': aligned['CGB_1y'], 'CGB_2y': aligned['CGB_2y'], 'CGB_5y': aligned['CGB_5y'],
    'CGB_10y': aligned['CGB_10y'], 'CGB_30y': aligned['CGB_30y']}).loc[SAMPLE_START:SAMPLE_END]

def window_factor_changes(win):
    """窗口因子累计变动：d0=窗口首日前一个交易日；收益类=P(d10)/P(d0)-1；收益率类=y(d10)-y(d0)（百分点）"""
    d10 = win[-1]
    d0 = SSE[sse_pos[win[0]] - 1]
    out = {}
    for k in ['EQ_000300', 'EQ_000905', 'EQ_399006', 'SPX_USD', 'USDCNH']:
        out[k] = fac_daily.loc[d10, k] / fac_daily.loc[d0, k] - 1
    for k in ['CGB_1y', 'CGB_2y', 'CGB_5y', 'CGB_10y', 'CGB_30y']:
        out[k] = (fac_daily.loc[d10, k] - fac_daily.loc[d0, k])
    return out

MIN_CALIB = 20   # rules_windows: 同类窗口按累计跌幅排序取前若干（不少于 20 个）
calib_windows = {}
for sid in ['S1', 'S2', 'S3', 'S4']:
    months = list(ident.index[ident[sid]])
    cands = []
    infeasible = []
    for M in months:
        win = window_for_month(M)
        if win is None:
            infeasible.append(M)
            continue
        r_w = port_cur.loc[win]
        cands.append({'month': M, 'start': win[0], 'end': win[-1],
                      'cum': (1 + r_w).prod() - 1, 'neg_days': int((r_w < 0).sum()),
                      'all_neg': bool((r_w < 0).all()), 'win': win})
    cands.sort(key=lambda x: x['cum'])
    e1 = [c for c in cands if c['all_neg']]
    if len(e1) >= MIN_CALIB:
        chosen = e1[:max(MIN_CALIB, len(e1))]  # 全部合格窗口（不少于20）
        relax = 0
    else:
        rest = [c for c in cands if not c['all_neg']]
        chosen = e1 + rest[:MIN_CALIB - len(e1)]
        relax = len(chosen) - len(e1)   # 实际放宽补足数（候选不足 20 时以全部候选为限）
    calib_windows[sid] = {'candidates': cands, 'chosen': chosen, 'infeasible': infeasible, 'relax': relax}
    print(f'\n{sid} 窗口: 合格月份 {len(months)}, 可构造窗口 {len(cands)}, 不可构造(样本截止/无次月) {len(infeasible)}'
          + (f' -> {[str(m) for m in infeasible]}' if infeasible else ''))
    print(f'   全部10日为负的窗口 {len(e1)} 个; 校准窗口取 {len(chosen)} 个' + (f'（其中 {relax} 个为放宽补足, 按累计跌幅次大排序）' if relax else '（全部为全负窗口）'))
    for c in chosen[:50]:
        print(f"   数据月{c['month']} 窗口 {c['start'].date()}~{c['end'].date()} 组合累计 {c['cum']*100:6.2f}% 负日数 {c['neg_days']}/10 {'√全负' if c['all_neg'] else '补足'}")

# ---- 校准冲击 = 合格窗口内各因子 10 个交易日累计变动的中位数 ----
CAL_SHOCK = {}
for sid, obj in calib_windows.items():
    chgs = [window_factor_changes(c['win']) for c in obj['chosen']]
    med = {k: float(np.median([c[k] for c in chgs])) for k in FACTOR_KEYS}
    CAL_SHOCK[sid] = med

cal_tab = pd.DataFrame(CAL_SHOCK).T[FACTOR_KEYS]
print('\n历史校准冲击（窗口因子累计变动中位数；权益/SPX/FX 为 %, 国债为 bp）:')
show = cal_tab.copy()
for c in ['EQ_000300', 'EQ_000905', 'EQ_399006', 'SPX_USD', 'USDCNH']:
    show[c] = show[c] * 100
for c in ['CGB_1y', 'CGB_2y', 'CGB_5y', 'CGB_10y', 'CGB_30y']:
    show[c] = show[c] * 100
print(show.round(2).to_string())

# 校准冲击折算为袖收益（国债按久期折算），便于与委员会冲击比较严格程度
def cgb_sleeve_from_pctpts(dy_pctpts):
    return -sum(DUR[t] * dy_pctpts[t] / 100.0 for t in DUR)

cal_sleeve = {}
for sid, med in CAL_SHOCK.items():
    dy_pct = {'1y': med['CGB_1y'], '2y': med['CGB_2y'], '5y': med['CGB_5y'], '10y': med['CGB_10y'], '30y': med['CGB_30y']}
    cal_sleeve[sid] = {'eq300': med['EQ_000300'], 'eq500': med['EQ_000905'], 'eqgem': med['EQ_399006'],
                       'spx_usd': med['SPX_USD'], 'fx': med['USDCNH'],
                       'cgb_sleeve': cgb_sleeve_from_pctpts(dy_pct)}
com_sleeve = {}
for sid, v in COM_SHOCK.items():
    com_sleeve[sid] = {'eq300': v['eq'], 'eq500': v['eq'], 'eqgem': v['eq'], 'spx_usd': v['spx'], 'fx': v['fx'],
                       'cgb_sleeve': cgb_sleeve_from_pctpts(v['cgb'])}
sleeve_tab = pd.DataFrame({('委员会', k): com_sleeve[k] for k in com_sleeve} |
                          {('校准', k): cal_sleeve[k] for k in cal_sleeve}).T
print('\n两套冲击折算为袖收益影响（%）:')
print((sleeve_tab * 100).round(2).to_string())

# ============================================================================
# 第 5 部分：压力测试（4 方案 × 4 情景 × 2 套冲击，四部分贡献拆分）
# ============================================================================
hdr('5. 压力测试结果（第五章素材）')

EQ_CLASSES = ['EQ_000300', 'EQ_000905', 'EQ_399006']

def stress_components(w, sid, shock_set):
    """返回四部分贡献（组合收益比例）：境内权益 / 标普500(人民币计) / 美元现金 / 国债"""
    if shock_set == '委员会':
        v = COM_SHOCK[sid]
        eq_shocks = {c: v['eq'] for c in EQ_CLASSES}
        s_spx, s_fx, dy_pct = v['spx'], v['fx'], v['cgb']
    else:
        med = CAL_SHOCK[sid]
        eq_shocks = {c: med[c] for c in EQ_CLASSES}
        s_spx, s_fx = med['SPX_USD'], med['USDCNH']
        dy_pct = {'1y': med['CGB_1y'], '2y': med['CGB_2y'], '5y': med['CGB_5y'],
                  '10y': med['CGB_10y'], '30y': med['CGB_30y']}
    eq_part = sum(w[c] * eq_shocks[c] for c in EQ_CLASSES)
    spx_part = w['SPX'] * ((1 + s_spx) * (1 + s_fx) - 1)   # 复合折算
    usd_part = w['USD_CASH'] * s_fx
    cgb_part = w['CGB'] * (-sum(DUR[t] * dy_pct[t] / 100.0 for t in DUR))
    total = eq_part + spx_part + usd_part + cgb_part
    return {'境内权益': eq_part, '标普500(人民币)': spx_part, '美元现金': usd_part, '国债': cgb_part,
            '合计': total}

STRESS = {}
rows = []
for p in ['方案A', '方案B', '方案C', '推荐方案', '当前组合']:
    for sid in ['S1', 'S2', 'S3', 'S4']:
        for ss in ['委员会', '校准']:
            comp = stress_components(W[p], sid, ss)
            STRESS[(p, sid, ss)] = comp
            rows.append({'方案': p, '情景': sid, '冲击': ss,
                         **{k: round(v * 100, 3) for k, v in comp.items()}})
stress_tab = pd.DataFrame(rows)
print('压力损失矩阵（组合损益 %，负=损失；四部分之和=合计，已校验）:')
print(stress_tab.to_string(index=False))
# 拆分加和校验
max_err = max(abs(sum(v for k, v in STRESS[k2].items() if k != '合计') - STRESS[k2]['合计']) for k2 in STRESS)
print(f'四部分贡献加和与合计最大偏差: {max_err:.2e}（浮点精度内）')
print('\n金额口径（万元, NAV=%.0f）:' % NAV)
rows_amt = []
for p in ['方案A', '方案B', '方案C', '推荐方案', '当前组合']:
    for sid in ['S1', 'S2', 'S3', 'S4']:
        for ss in ['委员会', '校准']:
            comp = STRESS[(p, sid, ss)]
            rows_amt.append({'方案': p, '情景': sid, '冲击': ss,
                             **{k: round(v * NAV, 2) for k, v in comp.items()}})
print(pd.DataFrame(rows_amt).to_string(index=False))

# 各方案最大压力损失（4情景×2冲击）
MAXLOSS = {}
for p in ['方案A', '方案B', '方案C', '推荐方案', '当前组合']:
    worst = min(((sid, ss, STRESS[(p, sid, ss)]['合计']) for sid in ['S1', 'S2', 'S3', 'S4'] for ss in ['委员会', '校准']),
                key=lambda x: x[2])
    MAXLOSS[p] = {'sid': worst[0], 'shock': worst[1], 'loss': worst[2]}
    rank = sorted(((sid, ss, STRESS[(p, sid, ss)]['合计']) for sid in ['S1', 'S2', 'S3', 'S4'] for ss in ['委员会', '校准']), key=lambda x: x[2])
    print(f'\n{p} 最大压力损失 = {worst[2]*100:.2f}%  来源: 情景{worst[0]}({rules_scen.set_index("scenario_id").loc[worst[0],"scenario"]}) × {worst[1]}冲击')
    print('   损失排序前4: ' + '; '.join(f'{s}/{k}:{v*100:.2f}%' for s, k, v in rank[:4]))

# ============================================================================
# 第 6 部分：九项约束逐条检查
# ============================================================================
hdr('6. 九项约束检查（第六章素材）')

LIM = limits.set_index('id')
def check_plan(p):
    w = W[p]
    if p in METRICS:
        m = METRICS[p]
    else:
        m = risk_metrics(pd.Series(port_ret(w), index=R.index))
    res = {}
    # C1 权重合计 = 100%（容差从 rules_checks 描述解析）
    tol = 0.05
    mtch = re.search(r'容差([\d.]+)', checks.set_index('check_id').loc['C1', 'description'])
    if mtch:
        tol = float(mtch.group(1)) / 100.0
    s = sum(w.values())
    res['C1'] = {'值': s, '通过': abs(s - 1.0) <= tol, '超限': abs(s - 1.0) - tol, '说明': f'权重合计 {s*100:.2f}% (容差±{tol*100:.2f}pp)'}
    # C2 权益合计 <= 60%
    eq = sum(w[c] for c in EQ_CLASSES)
    up = float(LIM.loc['L2', 'upper'])
    res['C2'] = {'值': eq, '通过': eq <= up + 1e-12, '超限': eq - up, '说明': f'境内权益合计 {eq*100:.2f}% vs ≤{up*100:.0f}%'}
    # C3 人民币现金 in [8%, 20%]
    c = w['CNY_CASH']
    lo, up = float(LIM.loc['L3', 'lower']), float(LIM.loc['L3', 'upper'])
    res['C3'] = {'值': c, '通过': lo - 1e-12 <= c <= up + 1e-12, '超限': (lo - c if c < lo else (c - up if c > up else 0.0)),
                 '说明': f'人民币现金 {c*100:.2f}% vs [{lo*100:.0f}%,{up*100:.0f}%]'}
    # C4 国债 >= 15%（注意：params_limits.csv 中 L4 的界限值存放于 upper 列，note 标明"下限 15%"，
    #     按 op='>=' 语义取有效界限值作为下限）
    g = w['CGB']
    l4 = LIM.loc['L4']
    lo = float(l4['lower']) if pd.notna(l4['lower']) else float(l4['upper'])
    res['C4'] = {'值': g, '通过': g >= lo - 1e-12, '超限': lo - g, '说明': f'国债 {g*100:.2f}% vs ≥{lo*100:.0f}%'}
    # C5 外币敞口 <= 25%（美元现金 + 不对冲 SPX QDII 均计入）
    fx_exp = w['USD_CASH'] + w['SPX']
    up = float(LIM.loc['L5', 'upper'])
    res['C5'] = {'值': fx_exp, '通过': fx_exp <= up + 1e-12, '超限': fx_exp - up,
                 '说明': f'外币敞口 {fx_exp*100:.2f}% (美元现金{w["USD_CASH"]*100:.2f}%+SPX QDII{w["SPX"]*100:.2f}%) vs ≤{up*100:.0f}%'}
    # C6 1日ES99 <= 3.5%
    up = float(LIM.loc['L6', 'upper'])
    res['C6'] = {'值': m['1日ES99'], '通过': m['1日ES99'] <= up + 1e-12, '超限': m['1日ES99'] - up,
                 '说明': f'1日ES99 {m["1日ES99"]*100:.2f}% vs ≤{up*100:.1f}%'}
    # C7 10日VaR99 <= 6%
    up = float(LIM.loc['L7', 'upper'])
    res['C7'] = {'值': m['10日VaR99'], '通过': m['10日VaR99'] <= up + 1e-12, '超限': m['10日VaR99'] - up,
                 '说明': f'10日VaR99 {m["10日VaR99"]*100:.2f}% vs ≤{up*100:.1f}%'}
    # C8 最大压力损失 <= 8%
    if p in MAXLOSS:
        ml, ml_sid, ml_ss = -MAXLOSS[p]['loss'], MAXLOSS[p]['sid'], MAXLOSS[p]['shock']
    else:
        worst = min(((sid, ss, stress_components(w, sid, ss)['合计'])
                     for sid in ['S1', 'S2', 'S3', 'S4'] for ss in ['委员会', '校准']), key=lambda x: x[2])
        ml, ml_sid, ml_ss = -worst[2], worst[0], worst[1]
    up = float(LIM.loc['L8', 'upper'])
    res['C8'] = {'值': ml, '通过': ml <= up + 1e-12, '超限': ml - up,
                 '说明': f'最大压力损失 {ml*100:.2f}% (情景{ml_sid}×{ml_ss}) vs ≤{up*100:.1f}%'}
    # C9 缓冲线 7%（拟推荐方案须留足 1pp）
    up = float(LIM.loc['L9', 'upper'])
    res['C9'] = {'值': ml, '通过': ml <= up + 1e-12, '超限': ml - up,
                 '说明': f'最大压力损失 {ml*100:.2f}% vs 缓冲线≤{up*100:.1f}%'}
    return res

CHECKS = {p: check_plan(p) for p in ['方案A', '方案B', '方案C', '推荐方案', '当前组合']}
for p in ['方案A', '方案B', '方案C', '推荐方案', '当前组合']:
    print(f'\n{p} 九项约束检查:')
    for cid in [f'C{i}' for i in range(1, 10)]:
        r = CHECKS[p][cid]
        status = '通过' if r['通过'] else f"未通过(超限 {r['超限']*100:+.2f}pp)"
        print(f"  {cid} [{limits.set_index('id').loc[r['说明'] and checks.set_index('check_id').loc[cid,'limit_id'],'constraint']}] {r['说明']} -> {status}")
npass = {p: sum(1 for c in CHECKS[p].values() if c['通过']) for p in CHECKS}
print('\n通过项数汇总:', {k: f'{v}/9' for k, v in npass.items()})
print('外币敞口口径核对（L5 note）:', limits.set_index('id').loc['L5', 'note'])

# ============================================================================
# 第 7 部分：调仓执行（当前组合 -> 推荐方案）
# ============================================================================
hdr('7. 调仓执行与现金路径（第七章素材）')

NAV_VAL = NAV
delta = {c: (W['推荐方案'][c] - W['当前组合'][c]) * NAV_VAL for c in W['推荐方案']}
print('调仓明细（万元, 正=买入 负=卖出, 价格基准 %s 收盘/估值日）:' % ASOF.date())
for c, v in delta.items():
    if abs(v) > 1e-9:
        print(f'  {c:12s} {v:+10.2f} 万元   权重 {W["当前组合"][c]*100:6.2f}% -> {W["推荐方案"][c]*100:6.2f}%')
sells = -sum(v for v in delta.values() if v < 0)
buys = sum(v for v in delta.values() if v > 0)
turnover = sells / NAV_VAL
print(f'卖出合计 {sells:.2f} 万元, 买入合计 {buys:.2f} 万元, 单向换手率 = {turnover*100:.2f}%')

# 价格基准表
px = {'沪深300': aligned['EQ_000300'].dropna().iloc[-1], '中证500': aligned['EQ_000905'].dropna().iloc[-1],
      '创业板指': aligned['EQ_399006'].dropna().iloc[-1], 'SPX': aligned['SPX'].dropna().iloc[-1],
      'USDCNH': aligned['USDCNH'].dropna().iloc[-1]}
px_dates = {'沪深300': aligned['EQ_000300'].dropna().index[-1], 'SPX': aligned['SPX'].dropna().index[-1]}
cgb_last = {t: (aligned['CGB_' + t].dropna().index[-1], aligned['CGB_' + t].dropna().iloc[-1]) for t in DUR}
print(f'价格基准: 权益/FX/SPX 截至 {ASOF.date()}: ' + ', '.join(f'{k}={v:.4f}' for k, v in px.items()))
print(f'中债收益率最后可用估值日: ' + ', '.join(f'{t}:{d.date()}={v:.4f}%' for t, (d, v) in cgb_last.items()))

FLOOR = 0.08
def cash_path(order):
    cash = W['当前组合']['CNY_CASH'] * NAV_VAL
    path = [{'步骤': 'T0 初始', '动作': '-', '现金流': 0.0, '现金余额': cash, '现金占比': cash / NAV_VAL}]
    sells_list = [(c, -delta[c]) for c in ['EQ_000300', 'EQ_000905', 'EQ_399006'] if delta[c] < -1e-9]
    buys_list = [(c, delta[c]) for c in ['CGB', 'CNY_CASH', 'USD_CASH', 'SPX'] if delta[c] > 1e-9]
    buys_list = [(c, v) for c, v in buys_list if c != 'CNY_CASH']  # 现金目标为余量
    steps = (sells_list + buys_list) if order == '先卖后买' else (buys_list + sells_list)
    breach = False
    for i, (c, v) in enumerate(steps, 1):
        if c in [x[0] for x in sells_list]:
            cash += v
            act = f'卖出 {c} {v:.2f} 万元（资金当日可用）'
        else:
            cash -= v
            act = f'买入 {c} {v:.2f} 万元（当日扣款）'
        ratio = cash / NAV_VAL
        if ratio < FLOOR - 1e-12:
            breach = True
        path.append({'步骤': f'{"S" if c in [x[0] for x in sells_list] else "B"}{i}', '动作': act,
                     '现金流': v if c in [x[0] for x in sells_list] else -v,
                     '现金余额': cash, '现金占比': ratio})
    return path, breach

for order in ['先卖后买', '先买后卖']:
    path, breach = cash_path(order)
    print(f'\n执行路径（{order}）— 现金下限 {FLOOR*100:.0f}%:')
    for s0 in path:
        flag = ' <== 击穿下限!' if s0['现金占比'] < FLOOR - 1e-12 else ''
        print(f"  {s0['步骤']:6s} {s0['动作']:44s} 现金余额 {s0['现金余额']:9.2f} 万元 ({s0['现金占比']*100:6.2f}%){flag}")
    print(f'  结论: {order} {"击穿" if breach else "未击穿"} 8% 现金下限')
    if order == '先卖后买':
        PATH_SELL_FIRST = path
    else:
        PATH_BUY_FIRST, BREACH_BUY_FIRST = path, breach

print('\nQDII 结算规则: 标普500 QDII 赎回款 T+7 到账；本次调仓不涉及 QDII 赎回（SPX 权重不变），该规则不适用。')

# ---- 推荐方案唯一性与次优比较（第七章） ----
hdr('7b. 推荐方案唯一性与次优组合比较（第七章素材）')

def make_alt(cgb_add, cash_add, shrink_k=None, eq_cut=None):
    """构造备选：权益按 shrink_k 同比例缩减（或按 eq_cut 绝对缩减），释放资金按 cgb_add/cash_add 分配"""
    w = dict(W['当前组合'])
    if shrink_k is not None:
        for c in EQ_CLASSES:
            w[c] = W['当前组合'][c] * shrink_k
        freed = cur_eq - sum(w[c] for c in EQ_CLASSES)
    else:
        freed = eq_cut
        # 同比例缩减 freed
        for c in EQ_CLASSES:
            w[c] = W['当前组合'][c] * (1 - freed / cur_eq)
    w['CGB'] = W['当前组合']['CGB'] + cgb_add
    w['CNY_CASH'] = W['当前组合']['CNY_CASH'] + cash_add
    return w

# 备选1: 同换手率(20.5pp 权益减配)，国债多配 0.5pp / 现金少配 0.5pp
alt1 = make_alt(cgb_add=0.11, cash_add=0.095, eq_cut=cur_eq - rec_eq)
# 备选2: 同换手率，非比例缩减（沪深300 多减、创业板少减）——总减配同为 20.5pp
alt2 = dict(W['当前组合'])
alt2['EQ_000300'] = 0.25 - 0.1225
alt2['EQ_000905'] = 0.15 - 0.0615
alt2['EQ_399006'] = 0.10 - 0.0210
alt2['CGB'] = 0.305
alt2['CNY_CASH'] = 0.20
# 备选3: 更小换手率（缩减系数 0.65，减配 17.5pp：国债+7.5pp、现金+10pp 至上限）
alt3 = make_alt(cgb_add=0.075, cash_add=0.10, shrink_k=0.65)
# 备选4: 更小换手率（缩减系数 0.70，减配 15pp：国债+5pp、现金+10pp 至上限）
alt4 = make_alt(cgb_add=0.05, cash_add=0.10, shrink_k=0.70)

ALT = {'备选1(国债31.0/现金19.5)': alt1, '备选2(非比例减配)': alt2,
       '备选3(系数0.65)': alt3, '备选4(系数0.70)': alt4}

def eval_alt(name, w):
    r = pd.Series(port_ret(w), index=R.index)
    m = risk_metrics(r)
    ml = min(stress_components(w, sid, ss)['合计']
             for sid in ['S1', 'S2', 'S3', 'S4'] for ss in ['委员会', '校准'])
    sells = sum(max(0.0, (W['当前组合'][c] - w[c])) for c in w) * NAV_VAL
    to = sells / NAV_VAL
    return {'名称': name, '换手率': to, 'ES99_1d': m['1日ES99'], 'VaR99_10d': m['10日VaR99'],
            '年化波动': m['年化波动'], '最大压力损失': -ml}

rows_alt = [eval_alt('推荐方案(系数0.59)', W['推荐方案'])]
for k, v in ALT.items():
    rows_alt.append(eval_alt(k, v))
alt_tab = pd.DataFrame(rows_alt).set_index('名称')
print('同构造族备选比较（现金上限20%约束下，现金增配最多+10pp，故国债增配≥10.5pp 才能吸收 20.5pp 减配）:')
print((alt_tab * 100).round(2).to_string())

# 备选方案九项约束快速检查
for k, v in ALT.items():
    W_tmp = dict(W)
    W['__alt__'] = v
    ck = check_plan('__alt__')
    fails = [cid for cid, r0 in ck.items() if not r0['通过']]
    print(f'  {k}: 未通过项 {fails if fails else "无"} ' + '; '.join(ck[c2]["说明"] for c2 in fails))
    del W['__alt__']

# 缩减系数网格：满足 C8(≤8%)与 C9(≤7%) 的最小权益减配
print('\n缩减系数网格（现金始终配至 20% 上限、余额入国债，检验 20.5pp 减配的必要性）:')
grid_rows = []
for k in [0.75, 0.72, 0.70, 0.68, 0.65, 0.62, 0.60, 0.59, 0.58, 0.55]:
    w = make_alt(cgb_add=(cur_eq * (1 - k) - 0.10), cash_add=0.10, shrink_k=k)
    r = pd.Series(port_ret(w), index=R.index)
    m = risk_metrics(r)
    ml = min(sum(stress_components(w, sid, ss)[x] for x in ['境内权益', '标普500(人民币)', '美元现金', '国债'])
             for sid in ['S1', 'S2', 'S3', 'S4'] for ss in ['委员会', '校准'])
    grid_rows.append({'缩减系数': k, '权益减配pp': cur_eq * (1 - k) * 100, '换手率%': cur_eq * (1 - k) * 100,
                      '最大压力损失%': -ml * 100, 'C8(≤8%)': '√' if -ml <= 0.08 + 1e-12 else '×',
                      'C9(≤7%)': '√' if -ml <= 0.07 + 1e-12 else '×',
                      'ES99_1d%': m['1日ES99'] * 100, 'C6(≤3.5%)': '√' if m['1日ES99'] <= 0.035 + 1e-12 else '×',
                      'VaR99_10d%': m['10日VaR99'] * 100, 'C7(≤6%)': '√' if m['10日VaR99'] <= 0.06 + 1e-12 else '×'})
print(pd.DataFrame(grid_rows).round(3).to_string(index=False))

# ============================================================================
# 第 8 部分：反向压力测试与马氏距离（第八章）
# ============================================================================
hdr('8. 反向压力测试与马氏距离（第八章素材）')

# 因子 10 日变动分布（全部重叠窗口，与校准窗口同口径：z[t] = 因子在 (t-10, t] 的累计变动）
Z = pd.DataFrame(index=R.index)
for k in ['EQ_000300', 'EQ_000905', 'EQ_399006', 'SPX_USD', 'USDCNH']:
    s = fac_daily[k]
    Z[k] = s / s.shift(10) - 1
for k in ['CGB_1y', 'CGB_2y', 'CGB_5y', 'CGB_10y', 'CGB_30y']:
    s = fac_daily[k]
    Z[k] = s - s.shift(10)          # 百分点
Z = Z.dropna()
mu = Z.mean().values
SIG = Z.cov().values
SIGINV = np.linalg.inv(SIG)
print(f'因子10日变动分布: 窗口数 {len(Z)}, 因子数 {Z.shape[1]}, 协方差条件数 {np.linalg.cond(SIG):.3e}')

def maha(x):
    d = np.asarray(x, dtype=float) - mu
    return float(np.sqrt(d @ SIGINV @ d))

def plan_loss_z(w, z):
    """z: 10 因子向量 [eq300,eq500,eqGEM,spx,fx,y1,y2,y5,y10,y30(百分点)] -> 组合压力收益（负=损失）"""
    eq = w['EQ_000300'] * z[0] + w['EQ_000905'] * z[1] + w['EQ_399006'] * z[2]
    spx = w['SPX'] * ((1 + z[3]) * (1 + z[4]) - 1)
    usd = w['USD_CASH'] * z[4]
    dy_pct = {'1y': z[5], '2y': z[6], '5y': z[7], '10y': z[8], '30y': z[9]}
    cgb = w['CGB'] * (-sum(DUR[t] * dy_pct[t] / 100.0 for t in DUR))
    return eq + spx + usd + cgb

def grad_loss_z(w, z):
    g = np.zeros(10)
    g[0], g[1], g[2] = w['EQ_000300'], w['EQ_000905'], w['EQ_399006']
    g[3] = w['SPX'] * (1 + z[4])
    g[4] = w['SPX'] * (1 + z[3]) + w['USD_CASH']
    for i, t in zip([5, 6, 7, 8, 9], ['1y', '2y', '5y', '10y', '30y']):
        g[i] = -w['CGB'] * DUR[t] / 100.0
    return g

def reverse_stress(w, target_loss):
    """min Mahalanobis s.t. plan_loss_z(z) = target_loss（负值）; 不动点迭代 + 二分"""
    z = mu.copy()
    for _ in range(200):
        a = grad_loss_z(w, z)
        Sa = SIG @ a
        def g(lam):
            return plan_loss_z(w, mu + lam * Sa) - target_loss
        lo, hi = 0.0, 1.0
        while g(hi) > 0 and hi < 1e6:
            hi *= 2
        for _ in range(200):
            mid = (lo + hi) / 2
            if g(mid) > 0:
                lo = mid
            else:
                hi = mid
        z_new = mu + (lo + hi) / 2 * Sa
        if np.max(np.abs(z_new - z)) < 1e-14:
            z = z_new
            break
        z = z_new
    return z, maha(z)

TARGET = -float(LIM.loc['L8', 'upper'])   # 触及 8% 压力损失上限
z_star, d_star = reverse_stress(W['推荐方案'], TARGET)
print(f'\n反向压力测试（约束: 推荐方案压力损失达到 {-TARGET*100:.1f}% = L8 上限）:')
print(f'最可能情景（最小马氏距离解）: 马氏距离 = {d_star:.3f}')
zn = ['沪深300累计', '中证500累计', '创业板累计', 'SPX(USD)累计', 'USDCNH累计', 'Δ1Y', 'Δ2Y', 'Δ5Y', 'Δ10Y', 'Δ30Y']
for i, nm in enumerate(zn):
    unit = '%' if i < 5 else 'bp'
    v = z_star[i] * 100
    hist_q = np.percentile(Z.iloc[:, i].values, [1, 50, 99])
    print(f'  {nm:12s} {v:+8.2f}{unit}   (历史10日分布 P1/中位/P99: {hist_q[0]*100:+.2f}/{hist_q[1]*100:+.2f}/{hist_q[2]*100:+.2f}{unit})')

# 委员会冲击与校准冲击的马氏距离
print('\n各情景两套冲击的马氏距离（同因子口径）:')
dist_rows = []
for sid in ['S1', 'S2', 'S3', 'S4']:
    v = COM_SHOCK[sid]
    z_com = [v['eq'], v['eq'], v['eq'], v['spx'], v['fx'],
             v['cgb']['1y'], v['cgb']['2y'], v['cgb']['5y'], v['cgb']['10y'], v['cgb']['30y']]
    med = CAL_SHOCK[sid]
    z_cal = [med['EQ_000300'], med['EQ_000905'], med['EQ_399006'], med['SPX_USD'], med['USDCNH'],
             med['CGB_1y'], med['CGB_2y'], med['CGB_5y'], med['CGB_10y'], med['CGB_30y']]
    d_com, d_cal = maha(z_com), maha(z_cal)
    # 校准窗口逐个距离
    win_dists = []
    for c in calib_windows[sid]['chosen']:
        fc = window_factor_changes(c['win'])
        z_w = [fc['EQ_000300'], fc['EQ_000905'], fc['EQ_399006'], fc['SPX_USD'], fc['USDCNH'],
               fc['CGB_1y'], fc['CGB_2y'], fc['CGB_5y'], fc['CGB_10y'], fc['CGB_30y']]
        win_dists.append(maha(z_w))
    dist_rows.append({'情景': sid, '委员会冲击距离': d_com, '校准冲击距离(中位数向量)': d_cal,
                      '校准窗口距离_中位': float(np.median(win_dists)), '校准窗口距离_最小': float(np.min(win_dists)),
                      '校准窗口距离_最大': float(np.max(win_dists))})
    calib_windows[sid]['win_dists'] = win_dists
dist_tab = pd.DataFrame(dist_rows).set_index('情景')
print(dist_tab.round(3).to_string())
print(f'反向压力最小马氏距离 = {d_star:.3f}（对比上表各情景冲击距离）')

# 推荐方案最大损失情景的裕度与放大倍数
rec_ml = MAXLOSS['推荐方案']
worst_loss = rec_ml['loss']
up8 = float(LIM.loc['L8', 'upper'])
up7 = float(LIM.loc['L9', 'upper'])
margin8 = up8 - (-worst_loss)
margin7 = up7 - (-worst_loss)
# 放大倍数 k: loss(k×冲击向量) = -8%
if rec_ml['shock'] == '委员会':
    v = COM_SHOCK[rec_ml['sid']]
    z_worst = np.array([v['eq'], v['eq'], v['eq'], v['spx'], v['fx'],
                        v['cgb']['1y'], v['cgb']['2y'], v['cgb']['5y'], v['cgb']['10y'], v['cgb']['30y']])
else:
    med = CAL_SHOCK[rec_ml['sid']]
    z_worst = np.array([med['EQ_000300'], med['EQ_000905'], med['EQ_399006'], med['SPX_USD'], med['USDCNH'],
                        med['CGB_1y'], med['CGB_2y'], med['CGB_5y'], med['CGB_10y'], med['CGB_30y']])
def loss_k(k):
    return plan_loss_z(W['推荐方案'], mu * 0 + k * z_worst) - TARGET
lo, hi = 0.5, 10.0
for _ in range(200):
    mid = (lo + hi) / 2
    if loss_k(mid) > 0:
        lo = mid
    else:
        hi = mid
k_star = (lo + hi) / 2
print(f'\n推荐方案最大损失情景 = {rec_ml["sid"]}×{rec_ml["shock"]}: 损失 {-worst_loss*100:.2f}%')
print(f'距 8% 上限裕度 = {margin8*100:.2f}pp; 距 7% 缓冲线裕度 = {margin7*100:.2f}pp')
print(f'冲击放大倍数 k* = {k_star:.3f}（将该情景冲击向量整体放大 k* 倍时损失恰好触及 8%）')
print(f'放大 k* 倍后马氏距离 = {maha(k_star * z_worst):.3f}（原冲击距离 = {maha(z_worst):.3f}）')
kgrid = np.linspace(0.5, k_star * 1.3, 60)
KCURVE = pd.Series([plan_loss_z(W['推荐方案'], k * z_worst) for k in kgrid], index=kgrid)

# 样本内最差 10 日累计损失（推荐方案与当前组合）
for p in ['推荐方案', '当前组合']:
    m = METRICS[p]
    print(f'{p} 样本内最差10日累计损失 {m["最差10日累计"]*100:.2f}%, 区间 {m["最差10日区间"]}')

# ============================================================================
# 第 9 部分：监测指标 M1~M8
# ============================================================================
hdr('9. 监测指标（第八章素材）')

def last_n_days(series, n, end=None):
    s = series.dropna()
    if end is not None:
        s = s.loc[:end]
    return s.iloc[-n:]

mon = monitor_tpl.copy()
res_mon = {}

# M1 沪深300 20日收益
s = aligned['EQ_000300'].dropna()
v = s.iloc[-1] / s.iloc[-21] - 1
res_mon['M1'] = (v, s.index[-1])
# M2 USDCNH 20日变化
s = aligned['USDCNH'].dropna()
v = s.iloc[-1] / s.iloc[-21] - 1
res_mon['M2'] = (v, s.index[-1])
# M3 DR007 最近20日均值 vs 此前60日均值 (bp)
s = aligned['DR007'].dropna()
v = (s.iloc[-20:].mean() - s.iloc[-80:-20].mean()) * 100
res_mon['M3'] = (v, s.index[-1])
# M4 中债10Y 20日变化 (bp)
s = aligned['CGB_10y'].dropna()
v = (s.iloc[-1] - s.iloc[-21]) * 100
res_mon['M4'] = (v, s.index[-1])
# M5 美债10Y 20日变化 (bp)
s = aligned['UST10Y'].dropna()
v = (s.iloc[-1] - s.iloc[-21]) * 100
res_mon['M5'] = (v, s.index[-1])
# M6 PPI 同比 vs 3个月前 (pp)
v = (ppi_m.iloc[-1] - ppi_m.iloc[-4])
res_mon['M6'] = (v, ppi_m.index[-1].end_time.replace(hour=0) if False else ppi_raw['date'].iloc[-1])
# M7 PMI 最新
v = pmi_m.iloc[-1]
res_mon['M7'] = (v, pmi_raw['date'].iloc[-1])
# M8 社融存量同比增速最新
v = afre_yoy.iloc[-1]
res_mon['M8'] = (v, afre_raw['date'].iloc[-1])

def parse_thr(s):
    s = str(s).strip()
    m = re.match(r'([+-]?[\d.]+)', s)
    val = float(m.group(1))
    if '%' in s and 'bp' not in s and '个百分点' not in s:
        val /= 100.0
    return val

mon_rows = []
for _, r0 in mon.iterrows():
    mid = r0['monitor_id']
    val, asof = res_mon[mid]
    thr = parse_thr(r0['threshold'])
    direction = r0['direction']
    if '低于' in direction:
        trig = val < thr
    else:
        trig = val > thr
    if mid in ('M3', 'M4', 'M5'):
        val_s = f'{val:+.2f}bp'
    elif mid in ('M1', 'M2', 'M6', 'M8'):
        val_s = f'{val*100:+.2f}%' if mid != 'M6' else f'{val:+.2f}个百分点'
    else:
        val_s = f'{val:.2f}'
    stale = ''
    if mid == 'M4':
        stale = '（数据截至2026-06-09，中债序列截断，待补数复核）'
    if mid == 'M8':
        stale = '（社融序列截至2026-03数据月，待补数复核）'
    if mid == 'M7':
        stale = '（PMI缺2026-07数据月，最新为2026-08）'
    mon_rows.append({'monitor_id': mid, 'indicator': r0['indicator'], 'threshold': r0['threshold'],
                     'direction': direction, 'latest_value': val_s, 'data_asof': str(pd.Timestamp(asof).date()),
                     'status': ('触发' if trig else '正常') + ('·待复核' if stale else ''),
                     'triggered': '是' if trig else '否', 'note': stale, '_val': val, '_thr': thr, '_trig': trig})
mon_out = pd.DataFrame(mon_rows)
print(mon_out[['monitor_id', 'indicator', 'threshold', 'direction', 'latest_value', 'data_asof', 'status', 'triggered']].to_string(index=False))
n_trig = int((mon_out['triggered'] == '是').sum())
print(f'\n触发指标数: {n_trig}/8; 触发项: {mon_out.loc[mon_out["triggered"]=="是", "monitor_id"].tolist()}')

# ============================================================================
# 第 10 部分：图表（10 张 PNG，中文标注）
# ============================================================================
hdr('10. 生成图表')

C_NAVY, C_RED, C_ORANGE, C_GREEN, C_BLUE, C_GRAY, C_PURPLE, C_BROWN = \
    '#1f4e79', '#c00000', '#ed7d31', '#548235', '#2e75b6', '#7f7f7f', '#7030a0', '#843c0c'
SCEN_COLORS = {'S1': C_BLUE, 'S2': C_ORANGE, 'S3': C_PURPLE, 'S4': C_RED}
PLAN_COLORS = {'当前组合': C_GRAY, '方案A': C_RED, '方案B': C_ORANGE, '方案C': C_BLUE, '推荐方案': C_GREEN}
SCEN_NAME = rules_scen.set_index('scenario_id')['scenario'].to_dict()

def savefig(fig, name):
    p = os.path.join(CHART, name)
    fig.savefig(p, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('已输出:', p)

# ---------------- 图1 数据覆盖与缺口 ----------------
cov_specs = []
def add_cov(label, start, end, note=''):
    cov_specs.append((label, pd.Timestamp(start), pd.Timestamp(end), note))
for cls, code in EQ_CODE.items():
    s = eq_close[cls]
    add_cov(f'{EQ_NAME[cls]}({code})', s.index.min(), s.index.max(), '剔除2026-09-12休市日异常' if code != '399006SZ' else '')
add_cov('USDCNH', usdcnh.index.min(), usdcnh.index.max(), '缺86个上交所日,ffill')
add_cov('SPX500', spx.index.min(), spx.index.max(), '缺73个上交所日,ffill')
for t in ['1y', '2y', '5y', '10y', '30y']:
    s = cgb_raw[t]
    add_cov(f'中债国债{t.upper()}', s.index.min(), s.index.max(), '2026-06-09截断')
add_cov('SHIBOR', shibor.index.min(), shibor.index.max(), '2018-09-03起')
add_cov('DR007', dr_raw['date'].min(), dr_raw['date'].max(), '与Shibor1W完全相同')
add_cov('LPR 1Y', lpr_raw['1y'].index.min(), lpr_raw['1y'].dropna().index.max(), '2026-07-20截断(缺8月)')
add_cov('LPR 5Y', lpr_raw['5y'].dropna().index.min(), lpr_raw['5y'].dropna().index.max(), '2019-08-20前结构性空值')
add_cov('PMI(数据月)', (pmi_m.index.min().start_time), (pmi_m.index.max().end_time), '缺2026-07数据月')
add_cov('PPI(数据月)', (ppi_m.index.min().start_time), (ppi_m.index.max().end_time), '至2026-07数据月')
add_cov('社融存量(数据月)', (afre_m.index.min().start_time), (afre_m.index.max().end_time), '2026-03截断')
add_cov('美债UST10Y', ust['10y'].index.min(), ust['10y'].index.max(), '')
add_cov('美债UST M2', ust['m2'].index.min(), ust['m2'].index.max(), '2018-10-16起')
add_cov('美债UST M4', ust['m4'].index.min(), ust['m4'].index.max(), '仅6条,严重截断')
add_cov('上交所日历', SSE.min(), SSE.max(), f'{len(SSE)}个交易日')

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 10), height_ratios=[2.1, 1])
labels = [c[0] for c in cov_specs][::-1]
for i, (lab, st, en, note) in enumerate(cov_specs[::-1]):
    ax1.barh(i, (en - st).days, left=st, height=0.55, color=C_NAVY, alpha=0.85)
    if note:
        ax1.text(en + pd.Timedelta(days=40), i, note, va='center', fontsize=7.5, color=C_RED)
ax1.axvline(ASOF, color=C_RED, ls='--', lw=1.4)
ax1.text(ASOF, len(labels) - 0.2, f' 分析截至日 {ASOF.date()}', color=C_RED, fontsize=9, va='bottom')
ax1.axvline(SAMPLE_END, color=C_ORANGE, ls=':', lw=1.6)
ax1.text(SAMPLE_END, -1.4, f'组合收益样本止 {SAMPLE_END.date()}（中债截断） ', color=C_ORANGE, fontsize=9, ha='right')
ax1.set_yticks(range(len(labels)))
ax1.set_yticklabels(labels, fontsize=8.5)
ax1.set_title('图1-a 各序列实际覆盖区间、缺口与分析截至日（2018-01-02 ~ 2026-09-15）', fontsize=11)
ax1.grid(axis='x', alpha=0.3)

# b: 2026 放大
zoom = [c for c in cov_specs]
z0, z1 = pd.Timestamp('2026-01-01'), pd.Timestamp('2026-10-05')
for i, (lab, st, en, note) in enumerate(zoom[::-1]):
    st2, en2 = max(st, z0), min(en, z1)
    if st2 <= en2:
        truncated = en < ASOF
        ax2.barh(i, (en2 - st2).days + 1, left=st2, height=0.55,
                 color=C_RED if truncated else C_NAVY, alpha=0.85)
        ax2.text(en2 + pd.Timedelta(days=3), i, f'止{en.date()}' + ('（截断）' if truncated else ''),
                 va='center', fontsize=7.5, color=C_RED if truncated else C_GRAY)
ax2.axvline(ASOF, color=C_RED, ls='--', lw=1.2)
ax2.axvline(pd.Timestamp('2026-09-12'), color='k', ls=':', lw=1.0)
ax2.text(pd.Timestamp('2026-09-12'), len(labels) * 0.62, '09-12(周六)\n休市日异常记录\n(000300/000905,已剔除)', fontsize=7.5, ha='right')
ax2.set_yticks(range(len(labels)))
ax2.set_yticklabels(labels, fontsize=8.5)
ax2.set_xlim(z0, z1 + pd.Timedelta(days=45))
ax2.set_title('图1-b 2026 年放大：各序列截止日与截断标记（红=早于分析截至日）', fontsize=11)
ax2.grid(axis='x', alpha=0.3)
fig.suptitle('数据核验：覆盖区间与缺口（红色标注=截断/异常，全部依据文件实际内容，manifest 截断标记不可靠）', fontsize=12, y=1.0)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart01_数据覆盖与缺口.png')

# ---------------- 图2 历史风险总览 ----------------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 10), height_ratios=[1.4, 1])
for p in PLAN_ORDER:
    nav = METRICS[p]['nav']
    ax1.plot(nav.index, nav.values, label=f'{p}（期末 {nav.iloc[-1]:.3f}）', color=PLAN_COLORS[p],
             lw=1.8 if p in ('当前组合', '推荐方案') else 1.1, alpha=0.95)
ax1.set_title(f'图2-a 各方案累计净值曲线（每日再平衡，{SAMPLE_START.date()}~{SAMPLE_END.date()}，N={N_DAYS}）', fontsize=11)
ax1.legend(fontsize=8.5)
ax1.grid(alpha=0.3)
ax1.set_ylabel('净值（期初=1）')

x = np.arange(len(PLAN_ORDER))
wd = 0.2
mets = [('年化波动', '年化波动', C_NAVY, None), ('1日ES99', '1日ES99', C_RED, float(LIM.loc['L6', 'upper'])),
        ('10日VaR99', '10日VaR99', C_ORANGE, float(LIM.loc['L7', 'upper'])), ('最大回撤', '最大回撤(绝对值)', C_PURPLE, None)]
for j, (key, lab, c, lim) in enumerate(mets):
    vals = [abs(METRICS[p][key]) * 100 for p in PLAN_ORDER]
    ax2.bar(x + (j - 1.5) * wd, vals, wd, label=lab, color=c, alpha=0.9)
    for xi, v in zip(x + (j - 1.5) * wd, vals):
        ax2.text(xi, v + 0.08, f'{v:.2f}', ha='center', fontsize=7)
ax2.axhline(float(LIM.loc['L6', 'upper']) * 100, color=C_RED, ls='--', lw=1.3)
ax2.text(len(PLAN_ORDER) - 0.4, float(LIM.loc['L6', 'upper']) * 100 + 0.12, f'L6 上限 {float(LIM.loc["L6","upper"])*100:.1f}%（ES99）', color=C_RED, fontsize=8.5, ha='right')
ax2.axhline(float(LIM.loc['L7', 'upper']) * 100, color=C_ORANGE, ls='--', lw=1.3)
ax2.text(len(PLAN_ORDER) - 0.4, float(LIM.loc['L7', 'upper']) * 100 + 0.12, f'L7 上限 {float(LIM.loc["L7","upper"])*100:.1f}%（10日VaR99）', color=C_ORANGE, fontsize=8.5, ha='right')
ax2.set_xticks(x)
ax2.set_xticklabels(PLAN_ORDER)
ax2.set_ylabel('%')
ax2.set_title('图2-b 各方案年化波动率、1日ES99、10日VaR99、最大回撤与限额参考线', fontsize=11)
ax2.legend(fontsize=8.5, ncol=4)
ax2.grid(axis='y', alpha=0.3)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart02_历史风险总览.png')

# ---------------- 图3 情景识别与校准 ----------------
months_all = pd.period_range('2018-01', mkt_m.index.max(), freq='M')
M = np.zeros((4, len(months_all)))
infeas_set = {}
for ri, sid in enumerate(['S1', 'S2', 'S3', 'S4']):
    hit = set(ident.index[ident[sid]])
    feas = set(c['month'] for c in calib_windows[sid]['candidates'])
    infeas_set[sid] = set(str(m0) for m0 in calib_windows[sid]['infeasible'])
    for ci, mth in enumerate(months_all):
        if mth in hit:
            M[ri, ci] = 2 if str(mth) in feas or mth in feas else 1   # 2=可校准 1=识别但窗口不可行
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), height_ratios=[0.9, 1.1, 1.1])
from matplotlib.colors import ListedColormap
cmap = ListedColormap(['#f2f2f2', '#ffd966', '#1f4e79'])
ax1.imshow(M, aspect='auto', cmap=cmap, vmin=0, vmax=2,
           extent=[months_all[0].ordinal, months_all[-1].ordinal + 1, 3.5, -0.5])
ax1.set_yticks(range(4))
ax1.set_yticklabels([f'{s} {SCEN_NAME[s]}' for s in ['S1', 'S2', 'S3', 'S4']], fontsize=9)
ticks = [p for p in months_all if p.month == 1 and p.year % 1 == 0]
ax1.set_xticks([p.ordinal + 0.5 for p in ticks])
ax1.set_xticklabels([str(p.year) for p in ticks], fontsize=8)
ax1.set_title('图3-a 四情景月度识别结果（深蓝=合格月且校准窗口可行；黄=合格月但窗口超出样本（中债截断，待补数复核）；灰=不合格）', fontsize=10.5)
handles = [Patch(color='#1f4e79', label='合格月（窗口可行，用于校准）'), Patch(color='#ffd966', label='合格月（窗口不可行）'),
           Patch(color='#f2f2f2', label='不合格月')]
ax1.legend(handles=handles, fontsize=8, loc='upper left', ncol=3)

# b: 校准冲击（折算为袖收益影响 %）
sids = ['S1', 'S2', 'S3', 'S4']
facs = [('eq300', '沪深300'), ('eq500', '中证500'), ('eqgem', '创业板指'), ('spx_usd', 'SPX(USD)'), ('fx', 'USDCNH'), ('cgb_sleeve', '国债(久期折算)')]
x = np.arange(len(sids))
wd = 0.13
for j, (k, lab) in enumerate(facs):
    vals = [cal_sleeve[s][k] * 100 for s in sids]
    ax2.bar(x + (j - 2.5) * wd, vals, wd, label=lab, alpha=0.9)
    for xi, v in zip(x + (j - 2.5) * wd, vals):
        ax2.text(xi, v + (0.25 if v >= 0 else -0.55), f'{v:.1f}', ha='center', fontsize=6.8)
ax2.axhline(0, color='k', lw=0.8)
ax2.set_xticks(x)
ax2.set_xticklabels([f'{s}\n{SCEN_NAME[s]}' for s in sids], fontsize=9)
ax2.set_ylabel('10日累计变动（%）')
n_chosen = {s: len(calib_windows[s]['chosen']) for s in sids}
ax2.set_title('图3-b 各情景历史窗口校准冲击（合格窗口因子累计变动中位数，窗口数 ' + ', '.join(f'{s}:{n_chosen[s]}' for s in sids) + '）', fontsize=10.5)
ax2.legend(fontsize=8, ncol=6)
ax2.grid(axis='y', alpha=0.3)

# c: 委员会 vs 校准 —— 当前组合总冲击影响
w0 = W['当前组合']
x = np.arange(len(sids))
tot_com = [sum(stress_components(w0, s, '委员会')[k] for k in ['境内权益', '标普500(人民币)', '美元现金', '国债']) * 100 for s in sids]
tot_cal = [sum(stress_components(w0, s, '校准')[k] for k in ['境内权益', '标普500(人民币)', '美元现金', '国债']) * 100 for s in sids]
ax3.bar(x - 0.18, tot_com, 0.36, label='委员会沿用冲击', color=C_NAVY, alpha=0.9)
ax3.bar(x + 0.18, tot_cal, 0.36, label='历史校准冲击', color=C_ORANGE, alpha=0.9)
for xi, v in zip(x - 0.18, tot_com):
    ax3.text(xi, v - 0.35, f'{v:.2f}%', ha='center', fontsize=8, color='white')
for xi, v in zip(x + 0.18, tot_cal):
    ax3.text(xi, v - 0.35, f'{v:.2f}%', ha='center', fontsize=8, color='white')
for xi, a, b in zip(x, tot_com, tot_cal):
    stricter = '校准更严' if b < a else ('委员会更严' if a < b else '相当')
    ax3.text(xi, max(a, b) + 0.35, stricter, ha='center', fontsize=8.5, color=C_RED)
ax3.axhline(0, color='k', lw=0.8)
ax3.set_xticks(x)
ax3.set_xticklabels([f'{s} {SCEN_NAME[s]}' for s in sids], fontsize=9)
ax3.set_ylabel('当前组合压力损益（%）')
ax3.set_title('图3-c 沿用冲击与历史校准冲击的严格程度对比（对当前组合的总冲击影响）', fontsize=10.5)
ax3.legend(fontsize=9)
ax3.grid(axis='y', alpha=0.3)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart03_情景识别与校准.png')

# ---------------- 图4 方案决策与执行 ----------------
fig = plt.figure(figsize=(14, 11))
gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.15], width_ratios=[1.15, 1])
ax1 = fig.add_subplot(gs[0, :])
ax2 = fig.add_subplot(gs[1, 0])
ax3 = fig.add_subplot(gs[1, 1])

plans4 = ['方案A', '方案B', '方案C', '推荐方案']
pl_show = plans4 + ['当前组合']
vals = [-MAXLOSS[p]['loss'] * 100 for p in pl_show]
cols = [C_RED if -MAXLOSS[p]['loss'] > float(LIM.loc['L8', 'upper']) else (C_ORANGE if -MAXLOSS[p]['loss'] > float(LIM.loc['L9', 'upper']) else C_GREEN) for p in pl_show]
bars = ax1.bar(range(len(pl_show)), vals, 0.55, color=cols, alpha=0.9)
for i, p in enumerate(pl_show):
    ml = MAXLOSS[p]
    ax1.text(i, vals[i] + 0.12, f'{vals[i]:.2f}%\n({ml["sid"]}×{ml["shock"]})', ha='center', fontsize=8.5)
ax1.axhline(float(LIM.loc['L8', 'upper']) * 100, color=C_RED, ls='--', lw=1.5)
ax1.text(len(pl_show) - 0.45, float(LIM.loc['L8', 'upper']) * 100 + 0.1, f'L8 压力损失上限 {float(LIM.loc["L8","upper"])*100:.0f}%', color=C_RED, ha='right', fontsize=9)
ax1.axhline(float(LIM.loc['L9', 'upper']) * 100, color=C_ORANGE, ls=':', lw=1.6)
ax1.text(len(pl_show) - 0.45, float(LIM.loc['L9', 'upper']) * 100 + 0.1, f'L9 缓冲线 {float(LIM.loc["L9","upper"])*100:.0f}%', color=C_ORANGE, ha='right', fontsize=9)
ax1.set_xticks(range(len(pl_show)))
ax1.set_xticklabels(pl_show)
ax1.set_ylabel('最大压力损失（%）')
ax1.set_ylim(0, max(vals) * 1.22)
ax1.set_title('图4-a 各方案最大压力损失（4情景×2套冲击中的最差值；红=超8%上限，橙=超7%缓冲线，绿=达标）', fontsize=10.5)
ax1.grid(axis='y', alpha=0.3)

# b: 现金路径
for path, lab, c, ls in [(PATH_SELL_FIRST, '先卖后买（规则顺序）', C_GREEN, '-'), (PATH_BUY_FIRST, '先买后卖（对照）', C_RED, '--')]:
    xs = np.arange(len(path))
    ys = [s0['现金占比'] * 100 for s0 in path]
    ax2.plot(xs, ys, marker='o', color=c, ls=ls, lw=1.8, label=lab)
    for xi, yi, s0 in zip(xs, ys, path):
        ax2.annotate(f'{yi:.1f}%', (xi, yi), textcoords='offset points', xytext=(0, 7), fontsize=7.5, color=c, ha='center')
ax2.axhline(FLOOR * 100, color=C_RED, ls=':', lw=1.5)
ax2.text(0.05, FLOOR * 100 + 0.6, f'现金下限 {FLOOR*100:.0f}%', color=C_RED, fontsize=9)
lbls = [s0['步骤'] for s0 in PATH_SELL_FIRST] + ['B1*']
xt = list(range(len(PATH_SELL_FIRST))) + [len(PATH_SELL_FIRST)]
ax2.set_xticks(range(max(len(PATH_SELL_FIRST), len(PATH_BUY_FIRST))))
ax2.set_xticklabels([s0['步骤'] for s0 in (PATH_SELL_FIRST if len(PATH_SELL_FIRST) >= len(PATH_BUY_FIRST) else PATH_BUY_FIRST)], fontsize=8)
ax2.set_ylabel('人民币现金占比（%）')
ax2.set_title('图4-b 调仓执行现金路径（T0→卖出300/500/创→买入国债；先买后卖在B1即击穿下限）', fontsize=10)
ax2.legend(fontsize=8.5)
ax2.grid(alpha=0.3)

# c: 反向压力测试最可能情景
names = ['沪深300\n(%)', '中证500\n(%)', '创业板\n(%)', 'SPX美元\n(%)', 'USDCNH\n(%)', 'Δ1Y\n(bp)', 'Δ2Y\n(bp)', 'Δ5Y\n(bp)', 'Δ10Y\n(bp)', 'Δ30Y\n(bp)']
vals = [z_star[i] * 100 for i in range(10)]
cols = [C_BLUE] * 5 + [C_BROWN] * 5
ax3.bar(range(10), vals, 0.6, color=cols, alpha=0.9)
for i, v in enumerate(vals):
    ax3.text(i, v + (0.4 if v >= 0 else -1.0), f'{v:+.1f}', ha='center', fontsize=7.5)
ax3.axhline(0, color='k', lw=0.8)
ax3.set_xticks(range(10))
ax3.set_xticklabels(names, fontsize=7.5)
ax3.set_title(f'图4-c 反向压力测试最可能情景（推荐方案损失达 {float(LIM.loc["L8","upper"])*100:.0f}% 的最小马氏距离解 d={d_star:.2f}）', fontsize=10)
txt = (f'马氏距离对比:\n反向压力最可能情景 d={d_star:.2f}\n'
       + '\n'.join(f'{s0} 委员会 d={r0["委员会冲击距离"]:.2f} / 校准 d={r0["校准冲击距离(中位数向量)"]:.2f}' for s0, r0 in dist_tab.iterrows()))
ax3.text(0.02, 0.03, txt, transform=ax3.transAxes, fontsize=7, va='bottom',
         bbox=dict(boxstyle='round', fc='#fff7e6', ec=C_ORANGE, alpha=0.9))
ax3.grid(axis='y', alpha=0.3)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart04_方案决策与执行.png')

# ---------------- 图5 监测指标触发状态 ----------------
fig, ax = plt.subplots(figsize=(12, 6.5))
mm = mon_out.iloc[::-1].reset_index(drop=True)
ys = np.arange(len(mm))
for i, r0 in mm.iterrows():
    val, thr = r0['_val'], r0['_thr']
    if '低于' in r0['direction']:
        margin = (val - thr) / abs(thr) * 100 if thr != 0 else np.nan
    else:
        margin = (thr - val) / abs(thr) * 100 if thr != 0 else np.nan
    c = C_RED if r0['_trig'] else C_GREEN
    ax.barh(i, margin, 0.55, color=c, alpha=0.85)
    ax.text(margin + (1.5 if margin >= 0 else -1.5), i, f"{r0['latest_value']}（阈值 {r0['threshold']}，{r0['data_asof']}）{'，触发' if r0['_trig'] else ''}",
            va='center', ha='left' if margin >= 0 else 'right', fontsize=8.5)
ax.axvline(0, color='k', lw=1.2)
ax.set_yticks(ys)
ax.set_yticklabels([f"{r0['monitor_id']} {r0['indicator']}" for _, r0 in mm.iterrows()], fontsize=9)
lim_txt = max(abs((r0['_val'] - r0['_thr']) / r0['_thr'] * 100) if r0['_thr'] else 0 for _, r0 in mm.iterrows())
ax.set_xlim(-lim_txt * 1.9 - 5, lim_txt * 1.9 + 5)
ax.set_xlabel('相对阈值的安全边际（%，正=安全，负=已触发）')
ax.set_title('图5 八个监测指标最新值与阈值（截至 2026-09-15；红=触发，绿=正常；M4/M8 因数据截断标注待复核）', fontsize=11)
ax.grid(axis='x', alpha=0.3)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart05_监测指标触发状态.png')

# ---------------- 图6 相关矩阵与风险贡献（补充） ----------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
corr_v = corr_show.values.copy()
mask = np.isnan(corr_v)
im = ax1.imshow(np.nan_to_num(corr_v), cmap='RdBu_r', vmin=-1, vmax=1)
ax1.set_xticks(range(len(corr_show.columns)))
ax1.set_xticklabels(corr_show.columns, rotation=35, ha='right', fontsize=8.5)
ax1.set_yticks(range(len(corr_show.index)))
ax1.set_yticklabels(corr_show.index, fontsize=8.5)
for i in range(corr_v.shape[0]):
    for j in range(corr_v.shape[1]):
        t = '—' if mask[i, j] else f'{corr_v[i, j]:.2f}'
        ax1.text(j, i, t, ha='center', va='center', fontsize=7.5,
                 color='k' if mask[i, j] or abs(np.nan_to_num(corr_v[i, j])) < 0.6 else 'w')
ax1.set_title('图6-a 资产袖日收益相关矩阵（人民币现金收益恒为0，相关系数无定义，以—表示）', fontsize=10)
fig.colorbar(im, ax=ax1, shrink=0.8)
rc_plot = rc_s * 100
ax2.bar(range(len(rc_plot)), rc_plot.values, 0.55, color=[C_BLUE, C_BLUE, C_BLUE, C_GREEN, C_ORANGE, C_PURPLE, C_GRAY], alpha=0.9)
for i, v in enumerate(rc_plot.values):
    ax2.text(i, v + (0.4 if v >= 0 else -1.2), f'{v:.1f}%', ha='center', fontsize=8.5)
ax2.set_xticks(range(len(rc_plot)))
ax2.set_xticklabels(rc_plot.index, rotation=30, ha='right', fontsize=8.5)
ax2.axhline(0, color='k', lw=0.8)
ax2.set_ylabel('风险贡献占比（%）')
ax2.set_title('图6-b 当前组合各资产风险贡献占比（Euler 方差分解）', fontsize=10)
ax2.grid(axis='y', alpha=0.3)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart06_相关矩阵与风险贡献.png')

# ---------------- 图7 情景合格月份与窗口分布（补充） ----------------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9))
years = sorted(set(m.year for m in months_all))
cnt = {sid: [int(((ident.index.year == y) & ident[sid]).sum()) for y in years] for sid in ['S1', 'S2', 'S3', 'S4']}
x = np.arange(len(years))
bottom = np.zeros(len(years))
for sid in ['S1', 'S2', 'S3', 'S4']:
    ax1.bar(x, cnt[sid], 0.6, bottom=bottom, label=f'{sid} {SCEN_NAME[sid]}', color=SCEN_COLORS[sid], alpha=0.85)
    bottom += np.array(cnt[sid])
ax1.set_xticks(x)
ax1.set_xticklabels(years, fontsize=8.5)
ax1.set_ylabel('合格月份数')
ax1.set_title('图7-a 各情景合格月份按年分布', fontsize=10.5)
ax1.legend(fontsize=8.5, ncol=2)
ax1.grid(axis='y', alpha=0.3)
for sid in ['S1', 'S2', 'S3', 'S4']:
    chosen_set = calib_windows[sid]['chosen']
    for c in calib_windows[sid]['candidates']:
        is_chosen = c in chosen_set
        if c['all_neg']:
            ax2.scatter(c['start'], c['cum'] * 100, s=30, color=SCEN_COLORS[sid],
                        marker='o', alpha=0.9,
                        edgecolors='k' if is_chosen else 'none', linewidths=1.0)
        else:
            ax2.scatter(c['start'], c['cum'] * 100, s=44 if is_chosen else 20,
                        color=SCEN_COLORS[sid], marker='x', alpha=0.9,
                        linewidths=1.7 if is_chosen else 0.8)
ax2.axhline(0, color='k', lw=0.8)
ax2.set_ylabel('窗口组合累计收益（%，当前组合）')
ax2.set_title('图7-b 候选校准窗口分布（圆=10日全负，×=含非负日；黑边/大号=入选校准集；颜色=情景）', fontsize=10.5)
handles = [Line2D([0], [0], marker='o', color='w', markerfacecolor=SCEN_COLORS[s], markersize=8, label=f'{s} {SCEN_NAME[s]}') for s in ['S1', 'S2', 'S3', 'S4']]
ax2.legend(handles=handles, fontsize=8.5, ncol=2)
ax2.grid(alpha=0.3)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart07_情景月份与窗口分布.png')

# ---------------- 图8 压力测试贡献分解（补充） ----------------
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 10))
cases = [(p, ss) for p in plans4 for ss in ['委员会', '校准']]
worst_sid = {p: MAXLOSS[p]['sid'] for p in plans4}
x = np.arange(len(cases))
comp_keys = ['境内权益', '标普500(人民币)', '美元现金', '国债']
comp_colors = {'境内权益': C_RED, '标普500(人民币)': C_PURPLE, '美元现金': C_ORANGE, '国债': C_GREEN}
bottom_pos = np.zeros(len(cases))
bottom_neg = np.zeros(len(cases))
for k in comp_keys:
    vals = np.array([STRESS[(p, worst_sid[p], ss)][k] * 100 for p, ss in cases])
    pos = np.where(vals >= 0, vals, 0)
    neg = np.where(vals < 0, vals, 0)
    ax1.bar(x, pos, 0.62, bottom=bottom_pos, color=comp_colors[k], alpha=0.9, label=k)
    ax1.bar(x, neg, 0.62, bottom=bottom_neg, color=comp_colors[k], alpha=0.9)
    bottom_pos += pos
    bottom_neg += neg
tot = bottom_pos + bottom_neg
for xi, tv in zip(x, tot):
    ax1.text(xi, tv - 0.32, f'{tv:.2f}%', ha='center', fontsize=7.5, color='white')
ax1.axhline(-float(LIM.loc['L8', 'upper']) * 100, color=C_RED, ls='--', lw=1.4)
ax1.text(0, -float(LIM.loc['L8', 'upper']) * 100 - 0.5, f'L8 上限 -{float(LIM.loc["L8","upper"])*100:.0f}%', color=C_RED, fontsize=8.5)
ax1.axhline(-float(LIM.loc['L9', 'upper']) * 100, color=C_ORANGE, ls=':', lw=1.4)
ax1.text(0, -float(LIM.loc['L9', 'upper']) * 100 + 0.18, f'L9 缓冲 -{float(LIM.loc["L9","upper"])*100:.0f}%', color=C_ORANGE, fontsize=8.5)
ax1.axhline(0, color='k', lw=0.8)
ax1.set_xticks(x)
ax1.set_xticklabels([f'{p}\n{worst_sid[p]}×{ss}' for p, ss in cases], fontsize=7.5)
ax1.set_ylabel('压力损益（%）')
ax1.set_title('图8-a 各方案最不利情景下四部分贡献分解（每方案两根柱=委员会/校准冲击；柱内标注合计损益）', fontsize=10.5)
ax1.legend(fontsize=8.5, ncol=4)
ax1.grid(axis='y', alpha=0.3)

hm = np.zeros((len(pl_show), 4))
ann = [['' for _ in range(4)] for _ in pl_show]
for i, p in enumerate(pl_show):
    for j, sid in enumerate(['S1', 'S2', 'S3', 'S4']):
        wc = STRESS[(p, sid, '委员会')]['合计']
        wk = STRESS[(p, sid, '校准')]['合计']
        worst = min(wc, wk)
        hm[i, j] = worst * 100
        ann[i][j] = f'{worst*100:.2f}\n({"委" if wc <= wk else "校"})'
im = ax2.imshow(hm, cmap='RdYlGn_r', vmin=min(0, hm.min()), vmax=max(8.0, hm.max()))
ax2.set_xticks(range(4))
ax2.set_xticklabels([f'{s}\n{SCEN_NAME[s]}' for s in ['S1', 'S2', 'S3', 'S4']], fontsize=8.5)
ax2.set_yticks(range(len(pl_show)))
ax2.set_yticklabels(pl_show, fontsize=9)
for i in range(len(pl_show)):
    for j in range(4):
        ax2.text(j, i, ann[i][j], ha='center', va='center', fontsize=8)
ax2.set_title('图8-b 压力损失热图（各方案×各情景，取两套冲击中更严者；数值=损失%，标注=来源冲击）', fontsize=10.5)
fig.colorbar(im, ax=ax2, shrink=0.8, label='损失（%）')
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart08_压力测试贡献分解.png')

# ---------------- 图9 收益率曲线冲击形态（补充） ----------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), width_ratios=[1.6, 1])
tenors = ['1y', '2y', '5y', '10y', '30y']
tlab = ['1Y', '2Y', '5Y', '10Y', '30Y']
xt = np.arange(5)
for sid in ['S1', 'S2', 'S3', 'S4']:
    com_bp = [COM_SHOCK[sid]['cgb'][t] * 100 for t in tenors]
    cal_bp = [CAL_SHOCK[sid]['CGB_' + t] * 100 for t in tenors]
    ax1.plot(xt, com_bp, marker='o', color=SCEN_COLORS[sid], lw=1.8, label=f'{sid} 委员会')
    ax1.plot(xt, cal_bp, marker='s', ls='--', color=SCEN_COLORS[sid], lw=1.4, alpha=0.8, label=f'{sid} 校准')
ax1.axhline(0, color='k', lw=0.8)
ax1.set_xticks(xt)
ax1.set_xticklabels(tlab)
ax1.set_ylabel('收益率冲击（bp）')
ax1.set_title('图9-a 各情景国债收益率冲击形态（实线圆点=委员会沿用；虚线方块=历史校准中位数）', fontsize=10)
ax1.legend(fontsize=7.5, ncol=2)
ax1.grid(alpha=0.3)
dv = [DUR[t] for t in tenors]
ax2.bar(xt, dv, 0.55, color=C_GREEN, alpha=0.85)
for xi, v in zip(xt, dv):
    ax2.text(xi, v + 0.05, f'{v:.1f}', ha='center', fontsize=9)
ax2.set_xticks(xt)
ax2.set_xticklabels(tlab)
ax2.set_ylabel('久期贡献（年）')
ax2.set_title(f'图9-b 国债组合关键期限久期贡献（合计 {PORT_DUR:.1f} 年，params_duration.csv）', fontsize=10)
ax2.grid(axis='y', alpha=0.3)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart09_收益率曲线冲击形态.png')

# ---------------- 图10 反向压力与裕度分析（补充） ----------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
ax1.plot(KCURVE.index, KCURVE.values * 100, color=C_NAVY, lw=2)
ax1.axhline(-8, color=C_RED, ls='--', lw=1.4)
ax1.axhline(-7, color=C_ORANGE, ls=':', lw=1.4)
ax1.plot([k_star], [TARGET * 100], marker='*', ms=15, color=C_RED)
ax1.annotate(f'k*={k_star:.2f}\n损失={-TARGET*100:.0f}%', (k_star, TARGET * 100), textcoords='offset points',
             xytext=(10, 14), fontsize=9, color=C_RED)
ax1.plot([1], [worst_loss * 100], marker='o', color=C_GREEN)
ax1.annotate(f'原冲击 k=1\n损失={-worst_loss*100:.2f}%', (1, worst_loss * 100), textcoords='offset points',
             xytext=(8, -16), fontsize=8.5, color=C_GREEN)
ax1.text(0.98, -7.6, 'L9 缓冲线 -7%', color=C_ORANGE, ha='right', fontsize=9)
ax1.text(0.98, -8.55, 'L8 上限 -8%', color=C_RED, ha='right', fontsize=9)
ax1.set_xlabel(f'冲击放大倍数 k（{rec_ml["sid"]}×{rec_ml["shock"]} 冲击向量）')
ax1.set_ylabel('推荐方案压力损益（%）')
ax1.set_title(f'图10-a 推荐方案裕度与放大倍数（最大损失情景 {rec_ml["sid"]}×{rec_ml["shock"]}）', fontsize=10.5)
ax1.grid(alpha=0.3)

names = [f'{s}\n委员会' for s in ['S1', 'S2', 'S3', 'S4']] + [f'{s}\n校准' for s in ['S1', 'S2', 'S3', 'S4']] + ['反向压力\n最可能情景']
dv = [dist_tab.loc[s, '委员会冲击距离'] for s in ['S1', 'S2', 'S3', 'S4']] + \
     [dist_tab.loc[s, '校准冲击距离(中位数向量)'] for s in ['S1', 'S2', 'S3', 'S4']] + [d_star]
cols = [C_NAVY] * 4 + [C_ORANGE] * 4 + [C_RED]
bars = ax2.bar(range(9), dv, 0.6, color=cols, alpha=0.9)
for i, v in enumerate(dv):
    ax2.text(i, v + 0.05, f'{v:.2f}', ha='center', fontsize=8)
ax2.set_xticks(range(9))
ax2.set_xticklabels(names, fontsize=7.5)
ax2.set_ylabel('马氏距离（因子10日变动分布）')
ax2.set_title('图10-b 委员会沿用冲击、历史校准冲击与反向压力情景的马氏距离', fontsize=10.5)
ax2.grid(axis='y', alpha=0.3)
fig.tight_layout()
savefig(fig, 'FIN3-WKN-149_chart10_反向压力与裕度分析.png')

# ============================================================================
# 第 11 部分：结论汇总（第一章素材）
# ============================================================================
hdr('11. 结论关键数字汇总（第一章素材）')
rec = W['推荐方案']
print(f'推荐方案权重: ' + ', '.join(f'{c}={rec[c]*100:.2f}%' for c in ['EQ_000300', 'EQ_000905', 'EQ_399006', 'CGB', 'USD_CASH', 'SPX', 'CNY_CASH']))
mR = METRICS['推荐方案']
print(f'推荐方案关键指标: 最大压力损失 {-MAXLOSS["推荐方案"]["loss"]*100:.2f}% (来源 {MAXLOSS["推荐方案"]["sid"]}×{MAXLOSS["推荐方案"]["shock"]}), '
      f'1日ES99 {mR["1日ES99"]*100:.2f}%, 10日VaR99 {mR["10日VaR99"]*100:.2f}%, 年化波动 {mR["年化波动"]*100:.2f}%, '
      f'最大回撤 {mR["最大回撤"]*100:.2f}%, 单向换手率 {turnover*100:.2f}%')
fails = {p: [cid for cid, r0 in CHECKS[p].items() if not r0['通过']] for p in ['方案A', '方案B', '方案C', '推荐方案', '当前组合']}
print('九项检查未通过项:', fails)
print(f'监测指标触发: {mon_out.loc[mon_out["triggered"]=="是", "monitor_id"].tolist()}')
print(f'反向压力: 最小马氏距离 {d_star:.3f}, 放大倍数 k* {k_star:.3f}, 距8%上限裕度 {margin8*100:.2f}pp, 距7%缓冲裕度 {margin7*100:.2f}pp')
print('\n全部计算完成。图表位于', CHART)
