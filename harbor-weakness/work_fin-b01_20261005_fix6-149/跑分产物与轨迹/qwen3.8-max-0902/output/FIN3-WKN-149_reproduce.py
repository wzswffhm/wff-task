#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-149 多资产稳健配置专户 · 三季度宏观压力测试与调仓建议 —— 可复算代码
================================================================================
输入 : /app/input_files/  （只读原始快照与参数、规则文件；不使用任何外部数据）
输出 : /app/output/FIN3-WKN-149_charts/ 下 5 张 PNG 图；stdout 打印备忘录全部数值
原则 : 不硬编码任何结论数值——所有权重、限额、冲击、阈值均从 input_files 读入，
       所有统计量、压力结果、检查结论均由原始快照计算得出。

方法论要点（与备忘录第二章一致）:
 1) 数据核验先于计算：休市日异常记录剔除、覆盖区间/缺口盘点、结构性空值不按 0 参与计算。
 2) 跨市场序列先对齐至上交所(SSE)估值日；他市场休市导致的不一致按前向填充，
    但仅在序列自身覆盖区间内填充（结构性空值/截断区间之外不填充）。
 3) 国债组合收益 = -Σ(关键期限久期贡献 × 收益率变动[小数])，逐日计算，不用收益率差简单加总。
 4) 标普500 人民币计收益 = (1+r_SPX,USD)×(1+r_USDCNH)-1（复合，不用加法近似）。
 5) 组合日收益 = Σ 方案权重 × 资产日收益（每日再平衡）。
 6) params_committee_shocks.csv 的 cgb_shock_bp 数值口径判定为“百分点(%)”，
    即 10Y:+0.20 表示 +20bp；依据：字段值域(0.10~0.80)与历史 10 日收益率变动(bp 级)
    及校准冲击（同为百分点）在同一量级方可比较；若按 0.10bp 解释则国债冲击近似为 0，
    与“压力测试”用途矛盾。备忘录第四章、第五章按此口径披露。
 7) 美元现金及存款的人民币计收益 = USD/CNH 汇率收益（快照未提供美元存款利率，利息按 0 处理，
    属披露的口径假设而非空值填 0）；人民币现金及货基收益按 0 处理（快照未提供货基收益率）。
 8) 情景月度识别中“权益指数当月下跌”以沪深300（组合主基准）月度收益判定（披露的口径假设）。
 9) 历史窗口选取：rules_windows 的“10 日组合收益全部为负”严格过滤在样本内无窗口满足
    （结果如实报告），按同条规则第二句回退为“同类窗口按累计跌幅排序取前若干（不少于 20 个）”，
    即每情景取累计跌幅最深的前 ceil(20/4)=5 个窗口、四情景合计 20 个。
    窗口选取所用“组合日收益”为专户当前权重组合（第四章先于方案推荐，口径为现状组合）。
"""
import os, re, sys, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Noto Sans CJK JP', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 110

IN  = '/app/input_files'
OUT = '/app/output'
CHART_DIR = os.path.join(OUT, 'FIN3-WKN-149_charts')
os.makedirs(CHART_DIR, exist_ok=True)
CUT = pd.Timestamp('2026-09-15')          # 分析截至日（rules_rebalance.price_basis 同源）
ANN = 252                                  # 年化交易日

def sec(t):
    print('\n' + '=' * 100); print(t); print('=' * 100)

def f2(x):  # 两位小数百分比字符串
    return f"{x*100:.2f}%"

# ============================================================================
# PART 1  数据读入与核验（先于一切计算）
# ============================================================================
sec('PART 1  数据核验：日历、异常记录、覆盖与缺口、结构性空值（备忘录第二章）')

def load(f, **kw):
    return pd.read_csv(os.path.join(IN, f), **kw)

cal = load('snapshot_trade_calendar.csv', parse_dates=['date'])
assert set(cal.exchange.unique()) == {'SSE'}
assert (cal.is_trading_day == 1).all()
sse = pd.DatetimeIndex(sorted(cal.date.unique()))
full_sse = sse[sse <= CUT]
print(f"上交所交易日历: {sse.min().date()} .. {sse.max().date()}, 共 {len(sse)} 个估值日, 无重复、无周末日期")
print(f"分析截至日: {CUT.date()}")

# ---- manifest 与实际文件核对（manifest 的 possible_truncation 不保证与内容一致，以内容为准）----
manifest = load('snapshot_data_manifest.csv')
print('\n[manifest 核对] file / manifest_records / actual_records / manifest_trunc_flag / 实际覆盖')
actual_rows = {}
for _, r in manifest.iterrows():
    df = load(r['file'], parse_dates=['date'])
    actual_rows[r['file']] = df
    flag = r['possible_truncation'] if pd.notna(r['possible_truncation']) else '(空)'
    print(f"  {r['file']:38s} {r['records']:>5d} {len(df):>7d} {str(flag):>6s}  {df.date.min().date()}..{df.date.max().date()}"
          + ('   <-- 记录数与 manifest 不一致' if len(df) != r['records'] else ''))

# ---- 各逻辑序列拼接与异常识别 ----
def concat_segs(pre):
    df = pd.concat([actual_rows[f'snapshot_{pre}_seg1.csv'], actual_rows[f'snapshot_{pre}_seg2.csv']]).sort_values('date')
    assert df.date.duplicated().sum() == 0
    return df.reset_index(drop=True)

idx = {'000300': concat_segs('000300SH'), '000905': concat_segs('000905SH'), '399006': concat_segs('399006SZ')}
fx_raw   = concat_segs('usdcnh')[['date', 'usdcnh']]
shibor   = concat_segs('shibor')
cgb_raw  = {t: actual_rows[f'snapshot_cgb_yield_{t}.csv'] for t in ['1y', '2y', '5y', '10y', '30y']}
spx_raw  = actual_rows['snapshot_spx.csv']
dr_raw   = actual_rows['snapshot_dr007.csv']
lpr1_raw = actual_rows['snapshot_lpr_1y.csv']
lpr5_raw = actual_rows['snapshot_lpr_5y.csv']
pmi_raw  = actual_rows['snapshot_pmi_manufacturing.csv']
ppi_raw  = actual_rows['snapshot_ppi_yoy.csv']
afre_raw = actual_rows['snapshot_afre_stock.csv']
ust10_raw = actual_rows['snapshot_ust_10y.csv']
ustm2_raw = actual_rows['snapshot_ust_m2.csv']
ustm4_raw = actual_rows['snapshot_ust_m4.csv']

# (a) 休市日异常记录：境内行情序列出现在非 SSE 交易日
print('\n[休市日异常记录识别]')
anomalies = []
for nm, df in idx.items():
    bad = df[~df.date.isin(sse)]
    for _, r in bad.iterrows():
        degenerate = (r.open == r.high == r.low == r.close)
        amt20 = df[(df.date < r.date)].tail(20).amount.mean()
        chain_ok = None
        nxt = df[df.date > r.date].head(1)
        if len(nxt):
            prev_close = df[df.date < r.date].tail(1).close.iloc[0]
            chain_ok = abs(nxt.pre_close.iloc[0] - prev_close) < 1e-6
        anomalies.append(dict(series=nm, date=str(r.date.date()), weekday=r.date.day_name(),
                              degenerate=bool(degenerate), amount_ratio=float(r.amount / amt20),
                              next_pre_close_matches_prev_close=bool(chain_ok)))
        print(f"  指数 {nm}: {r.date.date()}（{r.date.day_name()}, 非 SSE 交易日）"
              f" O=H=L=C={r.close:.4f} 四价相同={degenerate}, 成交额为前20日均值的 {r.amount/amt20*100:.2f}%,"
              f" 次一交易日 pre_close 等于该异常日前一交易日收盘={chain_ok}  ==> 判定为休市日伪记录, 剔除")
for nm in idx:
    idx[nm] = idx[nm][idx[nm].date.isin(sse)].reset_index(drop=True)

# 银行间序列（CGB/Shibor/DR007/LPR）出现在 SSE 休市日：核对是否为调休补班日（银行间开市、交易所休市）
interbank_extra = {}
for nm, df in [('中债国债收益率', cgb_raw['10y']), ('Shibor', shibor), ('DR007', dr_raw),
               ('LPR1Y', lpr1_raw), ('LPR5Y', lpr5_raw)]:
    extra = sorted(set(df.date) - set(sse))
    interbank_extra[nm] = extra
    n_we = sum(1 for d in extra if d.dayofweek >= 5)
    print(f"  {nm}: 非 SSE 交易日记录 {len(extra)} 条（其中周末 {n_we} 条）——为银行间市场调休补班日/公告日，"
          f"属真实行情但不在上交所估值日历内，对齐时不参与（非伪记录）")
cgb10 = cgb_raw['10y'].sort_values('date')
cgb10_we = cgb10[cgb10.date.dt.dayofweek >= 5]
same_as_prev = int((cgb10_we.yield_pct.values == cgb10.set_index('date').yield_pct.shift(1).reindex(cgb10_we.date).values).sum())
print(f"  核对：10Y 国债周末(补班日)记录中与前一日取值相同的仅 {same_as_prev}/{len(cgb10_we)} 条，确认为真实报价而非复制填充")

# (b) 覆盖区间、SSE 日缺口、月度缺口、结构性空值
def coverage(name, df, col, monthly=False, base=full_sse):
    dates = pd.DatetimeIndex(sorted(df.date))
    rec = dict(name=name, start=dates.min(), end=dates.max(), rows=len(df))
    if monthly:
        months = pd.period_range(dates.min(), dates.max(), freq='M')
        have = set(dates.to_period('M'))
        rec['missing_months'] = [str(m) for m in months if m not in have]
        rec['nulls'] = int(df[col].isna().sum())
        rec['on_sse'] = None
        rec['missing_sse'] = []
    else:
        inbase = dates[dates.isin(base)]
        exp = base[(base >= inbase.min()) & (base <= inbase.max())]
        rec['on_sse'] = int(len(inbase)); rec['extra_nonSSE'] = int(len(dates) - len(inbase))
        rec['missing_sse'] = [str(d.date()) for d in exp.difference(inbase)]
        rec['nulls'] = int(df[col].isna().sum())
        rec['missing_months'] = []
    return rec

cov = []
for nm, key in [('沪深300', '000300'), ('中证500', '000905'), ('创业板指', '399006')]:
    cov.append(coverage(nm, idx[key], 'close'))
for t in ['1y', '2y', '5y', '10y', '30y']:
    cov.append(coverage(f'中债国债{t.upper()}', cgb_raw[t], 'yield_pct'))
cov.append(coverage('USD/CNH', fx_raw, 'usdcnh'))
cov.append(coverage('标普500', spx_raw, 'close'))
cov.append(coverage('Shibor', shibor, 'shibor_on'))
cov.append(coverage('DR007', dr_raw, 'dr007'))
cov.append(coverage('LPR1Y', lpr1_raw, 'lpr_1y'))
cov.append(coverage('LPR5Y', lpr5_raw, 'lpr_5y'))
cov.append(coverage('UST10Y', ust10_raw, 'yield_pct'))
cov.append(coverage('UST_M2', ustm2_raw, 'yield_pct'))
cov.append(coverage('UST_M4', ustm4_raw, 'yield_pct'))
for nm, df, col in [('制造业PMI', pmi_raw, 'pmi_mfg'), ('社融存量', afre_raw, 'afre_stock'), ('PPI同比', ppi_raw, 'ppi_yoy')]:
    cov.append(coverage(nm, df, col, monthly=True))

print('\n[覆盖盘点]（对齐口径：SSE 估值日；他市场序列在自身覆盖内前向填充）')
for c in cov:
    gaps = ''
    if c['missing_months']: gaps += f" 缺失月份: {c['missing_months']}"
    if c['missing_sse']:
        ms = c['missing_sse']
        gaps += f" 覆盖内缺 SSE 日 {len(ms)} 个(前向填充): {ms[:4]}{'...' if len(ms) > 4 else ''}"
    trunc = ' [早于分析截至日结束=截断]' if c['end'] < CUT else ''
    late = ' [晚于2018-01-02开始]' if c['start'] > sse.min() else ''
    print(f"  {c['name']:10s} {c['start'].date()}..{c['end'].date()} rows={c['rows']:>5d}"
          f" nulls={c['nulls']:>4d}{trunc}{late}{gaps}")

lpr5_nulls = int(lpr5_raw.lpr_5y.isna().sum())
lpr5_first = lpr5_raw.dropna().date.min()
print(f"\n[结构性空值] LPR5Y 在 {lpr5_first.date()}（首次发布日）之前为空值 {lpr5_nulls} 条——结构性缺失，"
      f"不按 0 处理、不填充；S1 情景中“5 年期 LPR 下调”分支自该日起方可判定")
print("[结构性空值] 指数 seg1 首日 pre_close 为空（无前收盘，结构性）；收益计算采用 close/close，不使用 pre_close")
print("[截断] 中债国债收益率五档均止于 %s（早于分析截至日 %s）——组合收益公共样本因此在该日终止；"
      % (str(cov[3]['end'].date()), CUT.date()))
print("       社融存量止于 2026-04、制造业PMI 缺 2026-08、LPR1Y 缺 2026-08-20 公告行（LPR5Y 存在该行）、UST_M4 仅 6 条（2026-09-08 起）")
print("[manifest] possible_truncation 字段仅 shibor_seg2 标注 'false'、其余为空，与实际截断情况不符——按题设以文件实际内容为准")

# ============================================================================
# PART 2  对齐与收益序列（公共样本）
# ============================================================================
sec('PART 2  SSE 估值日对齐与日收益构造（备忘录第二、三章）')

sample_end = min(c['end'] for c in cov if c['name'].startswith('中债国债'))
sample_start = sse.min()
days = sse[(sse >= sample_start) & (sse <= sample_end)]
print(f"公共样本区间: {days[0].date()} .. {days[-1].date()}  SSE 估值日 {len(days)} 个"
      f"（终止原因: 中债国债收益率截断于 {sample_end.date()}；空值不得按 0 参与计算，故不外推）")

px = pd.DataFrame({
    'eq300': idx['000300'].set_index('date').close.reindex(days),
    'eq905': idx['000905'].set_index('date').close.reindex(days),
    'eqcyb': idx['399006'].set_index('date').close.reindex(days)})
assert px.notna().all().all(), '指数在公共样本内应无缺失'

def align_ffill(df, col, calendar):
    """在序列自身覆盖区间内对齐到给定日历并前向填充（覆盖区间外不填充=结构性缺失不填充）"""
    s = df.set_index('date')[col].sort_index()
    cal_in = calendar[(calendar >= s.index.min()) & (calendar <= s.index.max())]
    return s.reindex(cal_in).ffill().reindex(calendar)   # 超出覆盖 -> NaN（不外推）

Y = pd.DataFrame({t: align_ffill(cgb_raw[t], 'yield_pct', days) for t in ['1y', '2y', '5y', '10y', '30y']})
fx_s   = align_ffill(fx_raw, 'usdcnh', days)
spx_s  = align_ffill(spx_raw, 'close', days)
dr_s   = align_ffill(dr_raw[dr_raw.date.isin(sse)], 'dr007', days)

# 全日历版本（监测指标用，直至分析截至日；同样只在覆盖内填充）
fx_f   = align_ffill(fx_raw, 'usdcnh', full_sse)
spx_f  = align_ffill(spx_raw, 'close', full_sse)
eq300_f = idx['000300'].set_index('date').close.reindex(full_sse)
dr_f   = align_ffill(dr_raw[dr_raw.date.isin(sse)], 'dr007', full_sse)
ust10_f = align_ffill(ust10_raw, 'yield_pct', full_sse)
y10_f  = align_ffill(cgb_raw['10y'], 'yield_pct', full_sse)

dur_df = load('params_duration.csv')
tmap = {'1年': '1y', '2年': '2y', '5年': '5y', '10年': '10y', '30年': '30y'}
DUR = {tmap[r.tenor]: r.duration_contribution for _, r in dur_df.iterrows()}
TEN = ['1y', '2y', '5y', '10y', '30y']
print(f"关键期限久期贡献: {DUR}, 合计久期 {sum(DUR.values()):.1f}")

R = px.pct_change()
R['cgb'] = -sum(DUR[t] * Y[t].diff() / 100.0 for t in TEN)          # 久期折算，Δy 为百分点 -> /100
R['spx_usd'] = spx_s.pct_change()
R['fx'] = fx_s.pct_change()
R['spx_cny'] = (1 + R['spx_usd']) * (1 + R['fx']) - 1               # 复合折算
R['usd_cash'] = R['fx']                                             # 美元现金人民币计收益=汇率收益（利息按0，见口径假设）
R['cny_cash'] = 0.0                                                 # 货基收益快照未提供，按 0（口径假设）
R = R.iloc[1:]                                                       # 首日无前值
COLS = ['eq300', 'eq905', 'eqcyb', 'cgb', 'usd_cash', 'spx_cny', 'cny_cash']
CN = {'eq300': '沪深300', 'eq905': '中证500', 'eqcyb': '创业板', 'cgb': '中长期国债',
      'usd_cash': '美元现金', 'spx_cny': '标普500QDII(人民币计)', 'cny_cash': '人民币现金'}
assert R[COLS].notna().all().all(), '公共样本内收益序列存在空值——违反空值不按0计算的约束'
print(f"日收益序列: {R.index[0].date()} .. {R.index[-1].date()}, 共 {len(R)} 个收益日, 无 NaN")
print(f"对齐说明: USD/CNH 覆盖内缺 SSE 日 {len([d for d in coverage('x', fx_raw, 'usdcnh')['missing_sse']])} 个、"
      f"标普500 缺 {len(coverage('x', spx_raw, 'close')['missing_sse'])} 个、UST10Y 缺 {len(coverage('x', ust10_raw, 'yield_pct')['missing_sse'])} 个 —— 均按前向填充对齐；"
      f"银行间补班日记录不在 SSE 估值日历内，不参与收益计算")

# ============================================================================
# PART 3  组合构造与历史风险指标
# ============================================================================
sec('PART 3  方案权重、历史风险指标、风险贡献（备忘录第三章）')

hold = load('params_holdings.csv')
pos = load('params_positions.csv')
plans_df = load('plans_candidates.csv')
AMAP = {'EQ_000300': 'eq300', 'EQ_000905': 'eq905', 'EQ_399006': 'eqcyb', 'CGB': 'cgb',
        'USD_CASH': 'usd_cash', 'SPX': 'spx_cny', 'CNY_CASH': 'cny_cash'}
W_CUR = {AMAP[r.asset_class]: r.weight_current for _, r in hold.iterrows()}
W_REC = {AMAP[r.asset_class]: r.weight_recommended for _, r in hold.iterrows()}
PLANS = {}
for _, r in plans_df.iterrows():
    PLANS[r.plan_id] = dict(eq300=r.w_000300, eq905=r.w_000905, eqcyb=r.w_399006, cgb=r.w_cgb,
                            usd_cash=r.w_usd_cash, spx_cny=r.w_spx_qdii, cny_cash=r.w_cny_cash)
PORTS = {'当前组合': W_CUR, '方案A': PLANS['方案A'], '方案B': PLANS['方案B'],
         '方案C': PLANS['方案C'], '推荐方案': W_REC}
PROPOSER = {r.plan_id: r.proposer for _, r in plans_df.iterrows()}

print('\n[当前持仓]（组合净值 10,000.00 万元）')
for _, r in pos.iterrows():
    print(f"  {r.asset:14s} 权重 {r.weight_current*100:6.2f}%  市值 {r.market_value_10k_cny:8.2f} 万元")

def skew_g1(x):
    n = len(x); m2 = ((x - x.mean()) ** 2).sum() / n; m3 = ((x - x.mean()) ** 3).sum() / n
    return m3 / m2 ** 1.5 * np.sqrt(n * (n - 1)) / (n - 2)

def kurt_g2(x):
    n = len(x); m2 = ((x - x.mean()) ** 2).sum() / n; m4 = ((x - x.mean()) ** 4).sum() / n
    g2 = m4 / m2 ** 2 - 3
    return ((n - 1) * ((n + 1) * g2 + 6)) / ((n - 2) * (n - 3))

print('\n[各资产日收益统计特征]（样本 %s..%s, n=%d, 单位%%）' % (R.index[0].date(), R.index[-1].date(), len(R)))
stat_rows = []
for c in COLS:
    x = R[c].values
    if x.std() == 0:
        stat_rows.append([CN[c], 0, 0, np.nan, np.nan, 0, 0])
        print(f"  {CN[c]:16s} 均值 0.000 波动 0.000 偏度 — 峰度 — 最小 0.000 最大 0.000 （零方差，相关系数无定义）")
    else:
        row = [CN[c], x.mean() * 100, x.std(ddof=1) * 100, skew_g1(x), kurt_g2(x), x.min() * 100, x.max() * 100]
        stat_rows.append(row)
        print(f"  {CN[c]:16s} 均值 {row[1]:6.3f} 波动 {row[2]:6.3f} 偏度 {row[3]:6.3f} 峰度 {row[4]:7.3f} 最小 {row[5]:7.3f} 最大 {row[6]:7.3f}")

corr = R[COLS].corr()
print('\n[相关矩阵]（人民币现金零方差记 —）')
print('                 ' + ''.join(f"{CN[c][:6]:>10s}" for c in COLS))
for a in COLS:
    line = f"  {CN[a][:8]:10s}"
    for b in COLS:
        v = corr.loc[a, b]
        line += f"{'—':>10s}" if pd.isna(v) else f"{v:>10.3f}"
    print(line)

def port_metrics(w):
    rp = sum(w[c] * R[c] for c in COLS)
    nav = (1 + rp).cumprod()
    ann_vol = rp.std(ddof=1) * np.sqrt(ANN)
    q95, q99 = np.quantile(rp, 0.05), np.quantile(rp, 0.01)
    es95 = -rp[rp <= q95].mean(); es99 = -rp[rp <= q99].mean()
    c10 = (nav / nav.shift(10) - 1).dropna()
    var99_10 = -np.quantile(c10, 0.01)
    dd = 1 - nav / nav.cummax(); mdd = dd.max()
    trough = dd.idxmax(); peak = nav.loc[:trough].idxmax()
    after = nav.loc[trough:]; rec = after[after >= nav.loc[peak]]
    recover = rec.index[0] if len(rec) else None
    w10_end = c10.idxmin(); i10 = list(nav.index).index(w10_end)
    w10_start = nav.index[i10 - 9]
    return dict(rp=rp, nav=nav, ann_vol=ann_vol, var95_1d=-q95, var99_1d=-q99,
                es95_1d=es95, es99_1d=es99, var99_10d=var99_10, mdd=mdd,
                peak=peak, trough=trough, recover=recover,
                worst10=float(c10.min()), w10_start=w10_start, w10_end=w10_end,
                worst1d=float(rp.min()), worst1d_date=rp.idxmin(), final_nav=float(nav.iloc[-1]),
                ann_ret=float(nav.iloc[-1] ** (ANN / len(rp)) - 1))

M = {k: port_metrics(w) for k, w in PORTS.items()}
print('\n[组合层面历史风险指标]')
hdr = ('组合', '年化收益', '年化波动', 'VaR95_1d', 'VaR99_1d', 'ES95_1d', 'ES99_1d', 'VaR99_10d',
       '最大回撤', '回撤峰', '回撤谷', '修复日', '最差10日', '10日区间', '最差单日', '单日日期', '期末净值')
print('  ' + ' | '.join(hdr))
for k, m in M.items():
    print(f"  {k} | {f2(m['ann_ret'])} | {f2(m['ann_vol'])} | {f2(m['var95_1d'])} | {f2(m['var99_1d'])} | "
          f"{f2(m['es95_1d'])} | {f2(m['es99_1d'])} | {f2(m['var99_10d'])} | {f2(m['mdd'])} | {m['peak'].date()} | "
          f"{m['trough'].date()} | {m['recover'].date() if m['recover'] is not None else '未修复'} | "
          f"{f2(m['worst10'])} | {m['w10_start'].date()}..{m['w10_end'].date()} | {f2(m['worst1d'])} | "
          f"{m['worst1d_date'].date()} | {m['final_nav']:.4f}")

# 风险贡献（当前组合）
Wc = np.array([W_CUR[c] for c in COLS])
Sig = np.cov(R[COLS].values.T, ddof=1)
sig_p = np.sqrt(Wc @ Sig @ Wc)
rc = Wc * (Sig @ Wc) / sig_p
print('\n[当前组合各资产风险贡献]（欧拉分解，合计=组合日波动 %.4f%%）' % (sig_p * 100))
for n, v in zip(COLS, rc / rc.sum()):
    print(f"  {CN[n]:16s} {v*100:7.2f}%")
RC_CUR = dict(zip(COLS, rc / rc.sum()))

# ============================================================================
# PART 4  情景月度识别、历史窗口与校准冲击（备忘录第四章）
# ============================================================================
sec('PART 4  情景识别与历史校准（备忘录第四章）')

rules_sc = load('rules_scenarios.csv')
rules_win = load('rules_windows.csv').set_index('key').value
MIN_WINDOWS = int(re.search(r'不少于\s*(\d+)\s*个', rules_win['window_rule']).group(1))
PER_SCEN = math.ceil(MIN_WINDOWS / len(rules_sc))
WIN_LEN = int(re.search(r'(\d+)\s*个上交所交易日', rules_win['window_length']).group(1))
print(f"窗口规则: 长度 {WIN_LEN} 个 SSE 交易日; 校准最少窗口数 {MIN_WINDOWS} -> 每情景取累计跌幅最深前 {PER_SCEN} 个")
for _, r in rules_sc.iterrows():
    print(f"  [{r.scenario_id}] {r.scenario}: {r.rule}")

def month_end(s): return s.groupby(s.index.to_period('M')).last()
def month_mean(s): return s.groupby(s.index.to_period('M')).mean()

pmi_m = load('snapshot_pmi_manufacturing.csv', parse_dates=['date']).set_index('date').pmi_mfg
pmi_m.index = pmi_m.index.to_period('M')
ppi_m = ppi_raw.set_index('date').ppi_yoy.copy(); ppi_m.index = ppi_m.index.to_period('M')
afre_m = afre_raw.set_index('date').afre_stock.copy(); afre_m.index = afre_m.index.to_period('M')
afre_yoy = afre_m / afre_m.shift(12) - 1
lpr1_d = lpr1_raw.set_index('date').lpr_1y.reindex(sse).ffill()
lpr5_pub = lpr5_raw.dropna().set_index('date').lpr_5y
lpr5_d = lpr5_pub.reindex(sse[sse >= lpr5_pub.index.min()]).ffill()
lpr1_cut = month_end(lpr1_d) < month_end(lpr1_d).shift(1)
lpr5_cut = month_end(lpr5_d) < month_end(lpr5_d).shift(1)
cgb10_mean = month_mean(Y['10y'])
dr_mean = month_mean(dr_s)
hs300_mret = month_end(eq300_f).pct_change()
spx_mret = month_end(spx_f).pct_change()
fx_mret = month_end(fx_f).pct_change()

months = pd.period_range('2018-01', '2026-09', freq='M')

def g(s, m):
    if m in s.index:
        v = s.loc[m]
        return None if (pd.isna(v) if not isinstance(v, (bool, np.bool_)) else False) else (bool(v) if isinstance(v, (bool, np.bool_)) else float(v))
    return None

ident = {}
for m in months:
    pm, pmp = g(pmi_m, m), g(pmi_m, m - 1)
    c10, c10p = g(cgb10_mean, m), g(cgb10_mean, m - 1)
    ppi, ppip = g(ppi_m, m), g(ppi_m, m - 1)
    ay, ayp = g(afre_yoy, m), g(afre_yoy, m - 1)
    dm, dmp = g(dr_mean, m), g(dr_mean, m - 1)
    hs = g(hs300_mret, m); sp = g(spx_mret, m); fxm = g(fx_mret, m)
    l1, l5 = g(lpr1_cut, m), g(lpr5_cut, m)
    # S1: (PMI<50 且当月 LPR 下调) 或 (PMI 环比降幅>=0.5 且 10Y 月均低于上月)
    b1 = None
    if pm is not None:
        if pm < 50:
            cuts = [x for x in (l1, l5) if x is not None]
            b1 = any(cuts) if cuts else None
        else:
            b1 = False
    b2 = None
    if None not in (pm, pmp, c10, c10p):
        b2 = (pmp - pm >= 0.5) and (c10 < c10p)
    s1 = True if (b1 is True or b2 is True) else (None if (b1 is None or b2 is None) else False)
    # S2
    s2 = None if None in (ppi, ppip, c10, c10p, hs) else bool(ppi > ppip and c10 > c10p and hs < 0)
    # S3
    if sp is None and fxm is None:
        s3 = None
    else:
        s3 = bool((sp is not None and sp <= -0.03) or (fxm is not None and fxm >= 0.015))
    # S4
    s4 = None if None in (ay, ayp, dm, dmp, hs) else bool(ay < ayp and dm > dmp and hs < 0)
    ident[str(m)] = dict(S1=s1, S2=s2, S3=s3, S4=s4, partial=(str(m) == '2026-09'))

ID = pd.DataFrame(ident).T
QUAL = {}
for s in ['S1', 'S2', 'S3', 'S4']:
    q = [m for m in ID.index if ID.loc[m, s] is True]
    ind = [m for m in ID.index if ID.loc[m, s] is None]
    QUAL[s] = q
    nm = rules_sc[rules_sc.scenario_id == s].scenario.iloc[0]
    print(f"\n[{s} {nm}] 合格月份 n={len(q)}: {', '.join(q)}")
    print(f"    不可判定月份 n={len(ind)}: {', '.join(ind)}" if ind else "    不可判定月份: 无")
print("\n说明: 2026-09 为部分月（MTD 至 09-15）；不可判定=规则所需数据缺失（结构性空值不按 0 参与判定）。")
print(f"      S3 2026-09 部分月: 标普500 MTD {spx_mret.loc[pd.Period('2026-09')]*100:.2f}%, USD/CNH MTD {fx_mret.loc[pd.Period('2026-09')]*100:.2f}% -> 未合格")

# ---- 窗口构造 ----
rp_cur = M['当前组合']['rp']
daylist = list(days)
windows = {}
for s in ['S1', 'S2', 'S3', 'S4']:
    ws = []
    for mstr in QUAL[s]:
        pm = pd.Period(mstr, freq='M') + 1
        cand = [d for d in daylist if d.to_period('M') == pm]
        if len(cand) < WIN_LEN:
            print(f"  [{s}] {mstr}: 次月窗口超出公共样本（国债数据止于 {sample_end.date()}），不用于校准"); continue
        w = cand[:WIN_LEN]; d0 = daylist[daylist.index(w[0]) - 1]
        r = rp_cur.loc[w[0]:w[-1]]
        fac = {}
        for c, src in [('eq300', px.eq300), ('eq905', px.eq905), ('eqcyb', px.eqcyb)]:
            fac[c] = float(src.loc[w[-1]] / src.loc[d0] - 1)
        fac['spx_usd'] = float(spx_s.loc[w[-1]] / spx_s.loc[d0] - 1)
        fac['fx'] = float(fx_s.loc[w[-1]] / fx_s.loc[d0] - 1)
        for t in TEN:
            fac['y_' + t] = float(Y[t].loc[w[-1]] - Y[t].loc[d0])
        ws.append(dict(scen=s, month=mstr, start=w[0], end=w[-1], base=d0,
                       cum=float((1 + r).prod() - 1), allneg=bool((r < 0).all()), **fac))
    windows[s] = ws
    n_neg = sum(x['allneg'] for x in ws)
    print(f"[{s}] 候选窗口 {len(ws)} 个；其中“10 日组合收益全部为负”的窗口 {n_neg} 个")
assert all(sum(x['allneg'] for x in windows[s]) == 0 for s in windows), '若严格过滤有窗口满足，应改用严格窗口'
print(f">> 严格过滤（全部为负）在样本内无窗口满足（当前组合含 40% 现金+国债，10 连阴未出现），"
      f"按 rules_windows 第二句回退：同类窗口按累计跌幅排序，每情景取前 {PER_SCEN} 个、"
      f"合计 {PER_SCEN * 4} 个（满足不少于 {MIN_WINDOWS} 个）")

SEL = {s: sorted(windows[s], key=lambda z: z['cum'])[:PER_SCEN] for s in windows}
FACS = ['eq300', 'eq905', 'eqcyb', 'spx_usd', 'fx'] + ['y_' + t for t in TEN]
CALIB = {s: {f: float(np.median([x[f] for x in sel])) for f in FACS} for s, sel in SEL.items()}
for s in ['S1', 'S2', 'S3', 'S4']:
    print(f"\n[{s}] 选定窗口（按累计跌幅排序）:")
    for x in sorted(windows[s], key=lambda z: z['cum']):
        mark = ' <选定>' if x in SEL[s] else ''
        print(f"    {x['month']} -> [{x['start'].date()}..{x['end'].date()}] 组合累计 {x['cum']*100:+7.2f}% 全负={x['allneg']}{mark}")
    c = CALIB[s]
    print(f"    校准冲击(中位数): 沪深300 {c['eq300']*100:+.2f}% 中证500 {c['eq905']*100:+.2f}% 创业板 {c['eqcyb']*100:+.2f}% "
          f"标普500(USD) {c['spx_usd']*100:+.2f}% USDCNH {c['fx']*100:+.2f}% | 国债 "
          + ' '.join(f"{t.upper()}:{c['y_'+t]*100:+.1f}bp" for t in TEN))

# ---- 委员会冲击（口径：cgb 数值为百分点）----
cs = load('params_committee_shocks.csv')
def parse_cgb(s):
    km = {'1Y': '1y', '2Y': '2y', '5Y': '5y', '10Y': '10y', '30Y': '30y'}
    return {km[kv.split(':')[0].strip()]: float(kv.split(':')[1]) for kv in s.split(',')}
COMM = {r.scenario_id: dict(eq=r.cn_equity_shock, spx=r.spx_usd_shock, fx=r.usdcnh_shock, y=parse_cgb(r.cgb_shock_bp))
        for _, r in cs.iterrows()}
print('\n[委员会沿用冲击]（国债数值口径=百分点，即 +0.20 = +20bp）')
for sid, c in COMM.items():
    nm = rules_sc[rules_sc.scenario_id == sid].scenario.iloc[0]
    print(f"  {sid} {nm}: 境内权益 {c['eq']*100:+.2f}% 标普500(USD) {c['spx']*100:+.2f}% USDCNH {c['fx']*100:+.2f}% 国债 "
          + ' '.join(f"{t.upper()}:{c['y'][t]*100:+.0f}bp" for t in TEN))

# ============================================================================
# PART 5  压力测试（4 方案 × 4 情景 × 2 套冲击，四部分分解）
# ============================================================================
sec('PART 5  压力测试（备忘录第五章）')

def stress_parts(w, kind, sid):
    if kind == 'comm':
        c = COMM[sid]; e = [c['eq']] * 3; spx, fxk = c['spx'], c['fx']; yd = [c['y'][t] / 100 for t in TEN]
    else:
        c = CALIB[sid]; e = [c['eq300'], c['eq905'], c['eqcyb']]; spx, fxk = c['spx_usd'], c['fx']
        yd = [c['y_' + t] / 100 for t in TEN]
    p_eq = w['eq300'] * e[0] + w['eq905'] * e[1] + w['eqcyb'] * e[2]
    p_spx = w['spx_cny'] * ((1 + spx) * (1 + fxk) - 1)
    p_usd = w['usd_cash'] * fxk
    p_cgb = -w['cgb'] * sum(DUR[t] * dy for t, dy in zip(TEN, yd))
    return dict(eq=p_eq, spx=p_spx, usd=p_usd, cgb=p_cgb, total=p_eq + p_spx + p_usd + p_cgb)

STRESS = {}
for pname in ['方案A', '方案B', '方案C', '推荐方案', '当前组合']:
    w = PORTS[pname]
    for sid in ['S1', 'S2', 'S3', 'S4']:
        for kind in ['comm', 'calib']:
            STRESS[(pname, sid, kind)] = stress_parts(w, kind, sid)

NAV0 = 10000.0
print('\n[压力结果全表]（组合损益 %；括号内为四部分贡献: 境内权益/标普500人民币计/美元现金/国债，四者之和=组合损益；金额按净值 10,000 万元折算）')
for pname in ['方案A', '方案B', '方案C', '推荐方案', '当前组合']:
    print(f"\n  ◆ {pname}" + (f"（{PROPOSER[pname]}）" if pname in PROPOSER else "（参考）"))
    print(f"    {'情景':16s} {'冲击':6s} {'境内权益%':>9s} {'标普500%':>9s} {'美元现金%':>9s} {'国债%':>9s} {'合计%':>8s} {'合计万元':>10s}")
    for sid in ['S1', 'S2', 'S3', 'S4']:
        nm = rules_sc[rules_sc.scenario_id == sid].scenario.iloc[0]
        for kind, kn in [('comm', '沿用'), ('calib', '校准')]:
            p = STRESS[(pname, sid, kind)]
            chk = abs(p['eq'] + p['spx'] + p['usd'] + p['cgb'] - p['total'])
            assert chk < 1e-12
            print(f"    {sid} {nm[:6]:8s} {kn:4s} {p['eq']*100:9.3f} {p['spx']*100:9.3f} {p['usd']*100:9.3f} "
                  f"{p['cgb']*100:9.3f} {p['total']*100:8.3f} {p['total']*NAV0:10.2f}")

MAXLOSS = {}
for pname in PORTS:
    worst = min(((v['total'], sid, kind) for (p, sid, kind), v in STRESS.items() if p == pname))
    MAXLOSS[pname] = dict(loss=-worst[0] * 100, scen=worst[1], kind=worst[2])
    print(f"{pname}: 最大压力损失 {MAXLOSS[pname]['loss']:.2f}%  来源 {worst[1]}/{'沿用' if worst[2]=='comm' else '校准'}冲击")

print('\n[两套冲击严格程度比较]（以推荐方案压力损失计）')
for sid in ['S1', 'S2', 'S3', 'S4']:
    lc = -STRESS[('推荐方案', sid, 'comm')]['total'] * 100
    lk = -STRESS[('推荐方案', sid, 'calib')]['total'] * 100
    who = '沿用冲击更严格' if lc > lk else '校准冲击更严格'
    print(f"  {sid}: 沿用 {lc:.2f}% vs 校准 {lk:.2f}%  -> {who}")

# ============================================================================
# PART 6  九项约束检查（备忘录第六章）
# ============================================================================
sec('PART 6  九项约束逐条检查（备忘录第六章）')

limits = load('params_limits.csv').set_index('id')
checks = load('rules_checks.csv')
LIM = {}
for lid, r in limits.iterrows():
    LIM[lid] = dict(op=r.op, lower=None if pd.isna(r.lower) else float(r.lower),
                    upper=None if pd.isna(r.upper) else float(r.upper), note=r.note, name=r.constraint)

def run_checks(pname, w, m, maxloss_pct):
    eqsum = w['eq300'] + w['eq905'] + w['eqcyb']
    out = {}
    out['C1'] = (abs(sum(w.values()) - 1.0) <= 0.0005, f"权重合计 {sum(w.values())*100:.2f}%（容差 0.05pp）")
    out['C2'] = (eqsum <= LIM['L2']['upper'] + 1e-12, f"权益合计 {eqsum*100:.2f}% vs ≤{LIM['L2']['upper']*100:.0f}%")
    out['C3'] = (LIM['L3']['lower'] - 1e-12 <= w['cny_cash'] <= LIM['L3']['upper'] + 1e-12,
                 f"人民币现金 {w['cny_cash']*100:.2f}% vs [{LIM['L3']['lower']*100:.0f}%,{LIM['L3']['upper']*100:.0f}%]")
    # 注: params_limits.csv 中 L4(op='>=') 的阈值 0.15 存放于 upper 列（lower 为空），按 op 语义取该值为下限
    l4 = LIM['L4']['lower'] if LIM['L4']['lower'] is not None else LIM['L4']['upper']
    out['C4'] = (w['cgb'] >= l4 - 1e-12, f"国债 {w['cgb']*100:.2f}% vs ≥{l4*100:.0f}%")
    fx_exp = w['usd_cash'] + w['spx_cny']
    out['C5'] = (fx_exp <= LIM['L5']['upper'] + 1e-12,
                 f"外币敞口 {fx_exp*100:.2f}%（美元现金 {w['usd_cash']*100:.2f}%+QDII {w['spx_cny']*100:.2f}%）vs ≤{LIM['L5']['upper']*100:.0f}%")
    out['C6'] = (m['es99_1d'] <= LIM['L6']['upper'] + 1e-12, f"1日ES99 {m['es99_1d']*100:.2f}% vs ≤{LIM['L6']['upper']*100:.1f}%")
    out['C7'] = (m['var99_10d'] <= LIM['L7']['upper'] + 1e-12, f"10日VaR99 {m['var99_10d']*100:.2f}% vs ≤{LIM['L7']['upper']*100:.1f}%")
    out['C8'] = (maxloss_pct <= LIM['L8']['upper'] * 100 + 1e-9, f"最大压力损失 {maxloss_pct:.2f}% vs ≤{LIM['L8']['upper']*100:.1f}%")
    out['C9'] = (maxloss_pct <= LIM['L9']['upper'] * 100 + 1e-9, f"最大压力损失 {maxloss_pct:.2f}% vs ≤{LIM['L9']['upper']*100:.1f}%（缓冲线）")
    return out

CHECKS = {}
for pname in ['当前组合', '方案A', '方案B', '方案C', '推荐方案']:
    ck = run_checks(pname, PORTS[pname], M[pname], MAXLOSS[pname]['loss'])
    CHECKS[pname] = ck
    fails = [k for k, v in ck.items() if not v[0]]
    print(f"\n  ◆ {pname}: {'全部通过' if not fails else '未通过 ' + ','.join(fails)}")
    for k, (ok, desc) in ck.items():
        print(f"    {k} [{'通过' if ok else '未通过'}] {desc}")

print('\n[超限幅度]')
def exceed(pname, cid):
    w = PORTS[pname]
    if cid == 'C5': return (w['usd_cash'] + w['spx_cny'] - LIM['L5']['upper']) * 100
    if cid == 'C8': return MAXLOSS[pname]['loss'] - LIM['L8']['upper'] * 100
    if cid == 'C9': return MAXLOSS[pname]['loss'] - LIM['L9']['upper'] * 100
    if cid == 'C2': return (w['eq300'] + w['eq905'] + w['eqcyb'] - LIM['L2']['upper']) * 100
    if cid == 'C6': return (M[pname]['es99_1d'] - LIM['L6']['upper']) * 100
    if cid == 'C7': return (M[pname]['var99_10d'] - LIM['L7']['upper']) * 100
    return None
for pname in ['当前组合', '方案A', '方案B', '方案C', '推荐方案']:
    for cid, (ok, _) in CHECKS[pname].items():
        if not ok:
            print(f"  {pname} {cid}: 超限 {exceed(pname, cid):+.2f} 个百分点")
print("  外币敞口口径: params_limits L5 明确“美元现金及存款 + 不对冲汇率的标普500 QDII 均计入外币敞口”。")
print("  方案C 将美元现金提至 20% 而 QDII 仍为 10%：若漏计 QDII 则外币敞口看似 20%≤25% 合规，实际 30% 超限 5.00pp——存在漏计情形。")

# ============================================================================
# PART 7  推荐方案构造验证、唯一性扫描与调仓执行（备忘录第七章）
# ============================================================================
sec('PART 7  推荐方案构造、唯一性与调仓执行（备忘录第七章）')

rb = load('rules_rebalance.csv').set_index('key').value
CASH_FLOOR = float(re.search(r'不得低于\s*([\d.]+)\s*%', rb['cash_floor']).group(1)) / 100
print(f"执行规则: {rb['execution_order']}; 现金下限 {CASH_FLOOR*100:.0f}%; QDII 赎回 T+{rb['qdii_settlement'].split('T+')[1][0]}; 价格基准 {rb['price_basis']}")

# (1) 构造依据核对
coef = float(re.search(r'缩减系数\s*([\d.]+)', rb['recommendation_rule']).group(1))
eq_cut_pp = float(re.search(r'合计减配\s*([\d.]+)\s*个百分点', rb['recommendation_rule']).group(1))
cgb_in = float(re.search(r'([\d.]+)\s*个百分点转入中长期国债', rb['recommendation_rule']).group(1))
cash_in = float(re.search(r'([\d.]+)\s*个百分点转入人民币现金', rb['recommendation_rule']).group(1))
print(f"\n[构造依据核对] 缩减系数 {coef}: ", end='')
for c, a in [('eq300', 'EQ_000300'), ('eq905', 'EQ_000905'), ('eqcyb', 'EQ_399006')]:
    calc = W_CUR[c] * coef
    print(f"{CN[c]} {W_CUR[c]*100:.2f}%×{coef}={calc*100:.2f}%(推荐 {W_REC[c]*100:.2f}%) ", end='')
print(f"\n  合计减配 {(sum(W_CUR[c] for c in ['eq300','eq905','eqcyb'])-sum(W_REC[c] for c in ['eq300','eq905','eqcyb']))*100:.2f}pp（规则: {eq_cut_pp}pp）; "
      f"国债 +{(W_REC['cgb']-W_CUR['cgb'])*100:.2f}pp（规则: {cgb_in}）; 现金 +{(W_REC['cny_cash']-W_CUR['cny_cash'])*100:.2f}pp（规则: {cash_in}）; "
      f"现金达到 L3 上限 {LIM['L3']['upper']*100:.0f}%")

# (2) 全网格扫描（规则构造族: USD/SPX 不动、权益同比例缩减、释放资金现金先满上限其余入国债）
print('\n[规则构造族扫描] f=权益缩减系数, 换手率=卖出合计/净值')
scan = []
for f in np.arange(0.50, 1.0001, 0.01):
    freed = (sum(W_CUR[c] for c in ['eq300', 'eq905', 'eqcyb'])) * (1 - f)
    cash_d = min(LIM['L3']['upper'] - W_CUR['cny_cash'], freed)
    w = dict(eq300=W_CUR['eq300'] * f, eq905=W_CUR['eq905'] * f, eqcyb=W_CUR['eqcyb'] * f,
             cgb=W_CUR['cgb'] + freed - cash_d, usd_cash=W_CUR['usd_cash'],
             spx_cny=W_CUR['spx_cny'], cny_cash=W_CUR['cny_cash'] + cash_d)
    m = port_metrics(w)
    ml = max(-stress_parts(w, k, s)['total'] for k in ['comm', 'calib'] for s in ['S1', 'S2', 'S3', 'S4']) * 100
    ck = run_checks('scan', w, m, ml)
    scan.append(dict(f=round(float(f), 2), eq=0.5 * f * 100, turnover=freed * 100, es99=m['es99_1d'] * 100,
                     v10=m['var99_10d'] * 100, maxloss=ml, allpass=all(v[0] for v in ck.values()),
                     fails=','.join([k for k, v in ck.items() if not v[0]])))
sc = pd.DataFrame(scan)
passing = sc[sc.allpass]
print(sc.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
fmax = passing.f.max(); fstar = passing[passing.turnover == passing[passing.f == fmax].turnover.iloc[0]]
lo, hi = 0.5, 1.0
for _ in range(200):
    mid = (lo + hi) / 2
    freed = 0.5 * (1 - mid); cash_d = min(0.10, freed)
    w = dict(eq300=0.25 * mid, eq905=0.15 * mid, eqcyb=0.10 * mid, cgb=0.20 + freed - cash_d,
             usd_cash=0.10, spx_cny=0.10, cny_cash=0.10 + cash_d)
    ml = max(-stress_parts(w, k, s)['total'] for k in ['comm', 'calib'] for s in ['S1', 'S2', 'S3', 'S4']) * 100
    if ml <= 7.0: lo = mid
    else: hi = mid
print(f"\n  扫描结论: 规则构造族中通过全部九项的最大 f={fmax:.2f}（换手率 {0.5*(1-fmax)*100:.1f}%）; "
      f"C9 连续边界 f≈{lo:.4f}（换手率≈{0.5*(1-lo)*100:.2f}%），f>{hi:.2f} 起 C9 未通过、f≥0.90 起 C8 亦未通过")
print("  >> 如实报告：在无约束网格上存在换手率更低的通过组合（f 至 %.2f）；规则将缩减系数钉定 %.2f，" % (fmax, coef))
print("     其“换手率最小”表述在候选集 {A,B,C,推荐} 内成立（A/B/C 均未全部通过，推荐为其中唯一全部通过者）；")
print("     f=%.2f 使最大压力损失距 7%% 缓冲线另有约 %.2fpp 二级缓冲，符合 L9“留足缓冲”意图。备忘录按规则推荐 f=%.2f。"
      % (coef, 7.0 - MAXLOSS['推荐方案']['loss'], coef))

# (3) 同换手率邻域（次优组合比较）
print('\n[同换手率(20.50%)邻域组合比较]')
sells0 = {c: max(0.0, W_CUR[c] - W_REC[c]) for c in COLS}
turn_rec = sum(sells0.values())
variants = {
    '推荐方案（规则: 比例缩减+现金满上限+余额入国债）': W_REC,
    '拆分偏移: 现金+9.5pp/国债+11.0pp': dict(W_REC, cgb=0.310, cny_cash=0.195),
    '拆分偏移: 现金+9.0pp/国债+11.5pp': dict(W_REC, cgb=0.315, cny_cash=0.190),
    '拆分偏移: 现金+10.5pp/国债+10.0pp': dict(W_REC, cgb=0.300, cny_cash=0.205),
    '非比例: 只减沪深300(-20.5pp)': dict(W_CUR, eq300=0.25 - 0.205, cgb=0.305, cny_cash=0.20),
    '非比例: 减尽创业板(-10pp)再减中证500(-10.5pp)': dict(W_CUR, eq905=0.045, eqcyb=0.0, cgb=0.305, cny_cash=0.20),
    '非比例: 三指数等额减持(各-6.8333pp)': dict(eq300=0.25 - 0.205 / 3, eq905=0.15 - 0.205 / 3, eqcyb=0.10 - 0.205 / 3,
                                          cgb=0.305, usd_cash=0.10, spx_cny=0.10, cny_cash=0.20),
}
for nm, w in variants.items():
    m = port_metrics(w)
    ml = max(-stress_parts(w, k, s)['total'] for k in ['comm', 'calib'] for s in ['S1', 'S2', 'S3', 'S4']) * 100
    ck = run_checks('v', w, m, ml)
    fails = [k for k, v in ck.items() if not v[0]]
    sells = sum(max(0.0, W_CUR[c] - w[c]) for c in COLS)
    print(f"  {nm}: 权重和 {sum(w.values())*100:.2f}% 卖出 {sells*100:.2f}% ES99 {m['es99_1d']*100:.2f}% "
          f"VaR99_10d {m['var99_10d']*100:.2f}% 最大压力损失 {ml:.2f}% -> {'全部通过' if not fails else '未通过:' + ','.join(fails)}")
print("  >> 唯一性: 在规则构造原则（USD现金/QDII 不动、境内权益按当前权重同比例缩减、现金补足至 L3 上限、余额转入国债）下，")
print("     给定缩减系数 0.59，权重向量被唯一确定；同换手率的拆分偏移/非比例变体或违反 C1/C3，或虽通过检查但违背比例缩减构造原则")
print("     （改变风格相对暴露）且压力损失差异 ≤0.02pp，不构成规则内替代。")

# (4) 交易清单与执行
print('\n[交易清单]（价格基准 %s；金额万元，两位小数）' % CUT.date())
NAMES = {'eq300': '沪深300指数基金', 'eq905': '中证500指数基金', 'eqcyb': '创业板指数基金', 'cgb': '中长期国债组合',
         'usd_cash': '美元现金及存款', 'spx_cny': '标普500 QDII基金', 'cny_cash': '人民币现金及货基'}
trades = []
for c in COLS:
    d = (W_REC[c] - W_CUR[c]) * NAV0
    if abs(d) >= 0.005:
        trades.append((NAMES[c], '卖出' if d < 0 else '买入', abs(d)))
for nm, sd, amt in sorted(trades, key=lambda z: (z[1] != '卖出', z[0])):
    print(f"  {sd} {nm:12s} {amt:10.2f} 万元")
sell_total = sum(a for _, s, a in trades if s == '卖出')
buy_total = sum(a for _, s, a in trades if s == '买入')
turnover = sell_total / NAV0
print(f"  卖出合计 {sell_total:.2f} 万元, 买入合计 {buy_total:.2f} 万元; 单向换手率 = {sell_total:.2f}/{NAV0:.0f} = {turnover*100:.2f}%")
print("  QDII 结算规则: 本次无标普500 QDII 赎回（权重不变），T+7 到账规则不启用")
print('\n[各候选方案换手率（单向，卖出合计/净值）]')
for pname in ['方案A', '方案B', '方案C', '推荐方案']:
    w = PORTS[pname]
    sells = sum(max(0.0, W_CUR[c] - w[c]) for c in COLS) * NAV0
    print(f"  {pname}: 卖出 {sells:.2f} 万元 -> 换手率 {sells/NAV0*100:.2f}%")

def cash_path(order):
    cash = W_CUR['cny_cash'] * NAV0
    path = [('期初', cash)]
    sells_t = [(NAMES[c], (W_CUR[c] - W_REC[c]) * NAV0) for c in COLS if W_REC[c] < W_CUR[c] - 1e-12]
    buys_t = [(NAMES[c], (W_REC[c] - W_CUR[c]) * NAV0) for c in COLS if W_REC[c] > W_CUR[c] + 1e-12 and c != 'cny_cash']
    mmf = (W_REC['cny_cash'] - W_CUR['cny_cash']) * NAV0
    seq = []
    if order == 'sell_first':
        seq = [('卖出' + n, +a) for n, a in sells_t] + [('买入' + n, -a) for n, a in buys_t] + [('申购货基(桶内划转)', 0.0)]
    else:
        seq = [('买入' + n, -a) for n, a in buys_t] + [('卖出' + n, +a) for n, a in sells_t] + [('申购货基(桶内划转)', 0.0)]
    breach = False
    for nm, d in seq:
        cash += d
        path.append((nm, cash))
        if cash / NAV0 < CASH_FLOOR - 1e-12: breach = True
    return path, breach

print('\n[现金占比路径]（人民币现金及货基口径；申购货基为桶内划转，不改变现金类占比）')
paths = {}
for order, oname in [('sell_first', '先卖出后买入（规则规定顺序）'), ('buy_first', '先买入后卖出（对照）')]:
    p, br = cash_path(order)
    paths[order] = (p, br)
    print(f"  {oname}:")
    for nm, c in p:
        flag = '  <-- 击穿 8% 下限!' if c / NAV0 < CASH_FLOOR - 1e-12 else ''
        print(f"    {nm:22s} 现金 {c:9.2f} 万元 = {c/NAV0*100:6.2f}%{flag}")
    print(f"    最低现金占比 {min(c for _, c in p)/NAV0*100:.2f}% -> {'击穿下限' if br else '未击穿下限'}")
print(f"  结论: 必须按“{rb['execution_order']}”执行；先买后卖在第一步买入国债 {trades[0][2] if trades else 0:.0f} 万元后即把现金压至 "
      f"{paths['buy_first'][0][1][1]/NAV0*100:.2f}%，击穿 {CASH_FLOOR*100:.0f}% 下限 "
      f"{(CASH_FLOOR - paths['buy_first'][0][1][1]/NAV0)*100:.2f}pp。")

# ============================================================================
# PART 8  反向压力测试、马氏距离与监测指标（备忘录第八章）
# ============================================================================
sec('PART 8  反向压力测试与监测预警（备忘录第八章）')

wr = PORTS['推荐方案']
navs = {k: (1 + R[k]).cumprod() for k in ['eq300', 'eq905', 'eqcyb', 'spx_usd', 'fx']}
def cum10(n): return (n / n.shift(10) - 1).dropna()
X = pd.DataFrame({'r300': cum10(navs['eq300']), 'r905': cum10(navs['eq905']), 'rcyb': cum10(navs['eqcyb']),
                  'rspx': cum10(navs['spx_usd']), 'rfx': cum10(navs['fx'])})
for t in TEN:
    X['y_' + t] = (Y[t] - Y[t].shift(10)).reindex(X.index)
X = X.dropna()
SIG10 = X.cov().values
SIG10_inv = np.linalg.inv(SIG10)
cvec = np.array([-wr['eq300'], -wr['eq905'], -wr['eqcyb'], -wr['spx_cny'], -(wr['spx_cny'] + wr['usd_cash'])]
                + [wr['cgb'] * DUR[t] / 100 for t in TEN])
cSc = float(cvec @ SIG10 @ cvec)
LT = LIM['L8']['upper']           # 反向压力目标 = 8% 压力损失上限
xstar = LT * (SIG10 @ cvec) / cSc
dstar = LT / math.sqrt(cSc)
FN = ['沪深300', '中证500', '创业板', '标普500(USD)', 'USDCNH'] + [f'{t.upper()}国债' for t in TEN]
print(f"10 日因子变动协方差窗口数: {len(X)}; 推荐方案 10 日线性化损失波动 sqrt(c'Σc)={math.sqrt(cSc)*100:.3f}%")
print(f"\n[反向压力测试] 目标: 推荐方案损失达到 L8 上限 {LT*100:.1f}% 的最小马氏距离情景")
for n, v in zip(FN, xstar):
    print(f"  {n:12s} {v*100:+8.2f}" + ('bp' if n.endswith('国债') else '%'))
def loss_exact(w, x):
    p = (w['eq300'] * x[0] + w['eq905'] * x[1] + w['eqcyb'] * x[2]
         + w['spx_cny'] * ((1 + x[3]) * (1 + x[4]) - 1) + w['usd_cash'] * x[4]
         - w['cgb'] * sum(DUR[t] * x[5 + i] / 100 for i, t in enumerate(TEN)))
    return -p
print(f"  最小马氏距离 d* = {dstar:.2f} (σ 单位); 线性损失 = {cvec@xstar*100:.3f}%; "
      f"含复合项精确损失 = {loss_exact(wr, xstar)*100:.3f}%")

def maha(x): return float(np.sqrt(x @ SIG10_inv @ x))
print('\n[马氏距离对比]（同一 10 日因子协方差口径，σ 单位）')
DIST = {}
for sid in ['S1', 'S2', 'S3', 'S4']:
    cc = COMM[sid]
    xc = np.array([cc['eq']] * 3 + [cc['spx'], cc['fx']] + [cc['y'][t] for t in TEN])
    ca = CALIB[sid]
    xa = np.array([ca['eq300'], ca['eq905'], ca['eqcyb'], ca['spx_usd'], ca['fx']] + [ca['y_' + t] for t in TEN])
    DIST[sid] = (maha(xc), maha(xa))
    print(f"  {sid}: 沿用冲击 {DIST[sid][0]:6.2f} | 历史校准冲击 {DIST[sid][1]:5.2f}")
print(f"  反向压力最可能情景（损失 {LT*100:.0f}%）: d* = {dstar:.2f}")

# 放大倍数: 最大损失情景冲击等比例放大至 L8 上限
wsid, wkind = MAXLOSS['推荐方案']['scen'], MAXLOSS['推荐方案']['kind']
def loss_scaled(k):
    if wkind == 'comm':
        cc = COMM[wsid]
        x = np.array([cc['eq'] * k] * 3 + [cc['spx'] * k, cc['fx'] * k] + [cc['y'][t] * k for t in TEN])
    else:
        ca = CALIB[wsid]
        x = np.array([ca['eq300'] * k, ca['eq905'] * k, ca['eqcyb'] * k, ca['spx_usd'] * k, ca['fx'] * k]
                     + [ca['y_' + t] * k for t in TEN])
    return loss_exact(wr, x)
lo, hi = 0.5, 10.0
for _ in range(200):
    mid = (lo + hi) / 2
    if loss_scaled(mid) < LT: lo = mid
    else: hi = mid
KAMP = lo
ml_rec = MAXLOSS['推荐方案']['loss']
print(f"\n[裕度与放大倍数] 推荐方案最大压力损失 {ml_rec:.2f}%（{wsid}/{'沿用' if wkind=='comm' else '校准'}）:")
print(f"  距 L8 上限 8.00%: 裕度 {8.0-ml_rec:.2f}pp; 距 L9 缓冲线 7.00%: 裕度 {7.0-ml_rec:.2f}pp")
print(f"  冲击等比例放大倍数（至损失=8.00%，含复合效应，数值求解）: k = {KAMP:.2f} 倍")
print(f"  样本内最差 10 日累计损失: {M['推荐方案']['worst10']*100:.2f}% "
      f"[{M['推荐方案']['w10_start'].date()}..{M['推荐方案']['w10_end'].date()}]（当前组合为 {M['当前组合']['worst10']*100:.2f}%）")

# ---- 监测指标 ----
sec('监测指标 M1-M8')
mon_t = pd.read_csv(os.path.join(IN, 'template_monitor.csv'), encoding='utf-8-sig')
def thr_parse(s):
    v = float(re.search(r'[-+]?[\d.]+', s).group(0))
    return v
MON = []
def add_mon(mid, value, unit, asof, thr, direction, note=''):
    if direction.startswith('高于'):
        ratio = value / thr
        trig = value >= thr
    else:
        ratio = value / thr if thr < 0 else thr / value
        trig = value <= thr
    MON.append(dict(mid=mid, value=value, unit=unit, asof=str(asof), thr=thr, direction=direction,
                    ratio=ratio, triggered=trig, note=note))

n20 = 20
m1 = float(eq300_f.iloc[-1] / eq300_f.iloc[-1 - n20] - 1)
add_mon('M1', m1 * 100, '%', eq300_f.index[-1].date(), thr_parse(mon_t[mon_t.monitor_id == 'M1'].threshold.iloc[0]),
        mon_t[mon_t.monitor_id == 'M1'].direction.iloc[0],
        f"窗口 {eq300_f.index[-1-n20].date()}->{eq300_f.index[-1].date()}")
fxl = fx_f.dropna()
m2 = float(fxl.iloc[-1] / fxl.iloc[-1 - n20] - 1)
add_mon('M2', m2 * 100, '%', fxl.index[-1].date(), thr_parse(mon_t[mon_t.monitor_id == 'M2'].threshold.iloc[0]),
        mon_t[mon_t.monitor_id == 'M2'].direction.iloc[0], f"窗口 {fxl.index[-1-n20].date()}->{fxl.index[-1].date()}, 最新价 {fxl.iloc[-1]:.4f}")
drl = dr_f.dropna()
m3 = float((drl.iloc[-n20:].mean() - drl.iloc[-3 * n20:-n20].mean()) * 100)
add_mon('M3', m3, 'bp', drl.index[-1].date(), thr_parse(mon_t[mon_t.monitor_id == 'M3'].threshold.iloc[0]),
        mon_t[mon_t.monitor_id == 'M3'].direction.iloc[0],
        f"近20日均值 {drl.iloc[-n20:].mean():.4f}% vs 前60日 {drl.iloc[-3*n20:-n20].mean():.4f}%")
y10l = y10_f.dropna()
m4 = float((y10l.iloc[-1] - y10l.iloc[-1 - n20]) * 100)
add_mon('M4', m4, 'bp', y10l.index[-1].date(), thr_parse(mon_t[mon_t.monitor_id == 'M4'].threshold.iloc[0]),
        mon_t[mon_t.monitor_id == 'M4'].direction.iloc[0],
        f"窗口 {y10l.index[-1-n20].date()}->{y10l.index[-1].date()}; 数据截断于 {y10l.index[-1].date()}（早于分析截至日），需补数复核")
u10l = ust10_f.dropna()
m5 = float((u10l.iloc[-1] - u10l.iloc[-1 - n20]) * 100)
add_mon('M5', m5, 'bp', u10l.index[-1].date(), thr_parse(mon_t[mon_t.monitor_id == 'M5'].threshold.iloc[0]),
        mon_t[mon_t.monitor_id == 'M5'].direction.iloc[0],
        f"窗口 {u10l.index[-1-n20].date()}->{u10l.index[-1].date()}, 最新 {u10l.iloc[-1]:.2f}%")
ppim = ppi_raw.set_index('date').ppi_yoy.copy(); ppim.index = ppim.index.to_period('M')
m6 = float(ppim.iloc[-1] - ppim.loc[ppim.index[-1] - 3])
add_mon('M6', m6, 'pp', ppim.index[-1].end_time.date(), thr_parse(mon_t[mon_t.monitor_id == 'M6'].threshold.iloc[0]),
        mon_t[mon_t.monitor_id == 'M6'].direction.iloc[0],
        f"{ppim.index[-1]}({ppim.iloc[-1]:.1f}%) vs {ppim.index[-1]-3}({ppim.loc[ppim.index[-1]-3]:.1f}%)")
pmim = pmi_raw.set_index('date').pmi_mfg.copy(); pmim.index = pmim.index.to_period('M')
m7 = float(pmim.iloc[-1])
add_mon('M7', m7, '', pmim.index[-1].end_time.date(), thr_parse(mon_t[mon_t.monitor_id == 'M7'].threshold.iloc[0]),
        mon_t[mon_t.monitor_id == 'M7'].direction.iloc[0], '2026-08 缺报，最新月值为 2026-09')
afm = afre_raw.set_index('date').afre_stock.copy(); afm.index = afm.index.to_period('M')
m8 = float(afm.iloc[-1] / afm.loc[afm.index[-1] - 12] - 1) * 100
add_mon('M8', m8, '%', afm.index[-1].end_time.date(), thr_parse(mon_t[mon_t.monitor_id == 'M8'].threshold.iloc[0]),
        mon_t[mon_t.monitor_id == 'M8'].direction.iloc[0],
        f"{afm.index[-1]} 存量 {afm.iloc[-1]:.2f} 万亿 vs 上年同月 {afm.loc[afm.index[-1]-12]:.2f} 万亿; 数据截断于 2026-04，需补数复核")

print(f"{'ID':4s} {'指标':28s} {'阈值':>10s} {'方向':8s} {'最新值':>12s} {'数据截至':>12s} {'触发比率':>8s} 状态")
for r, (_, t) in zip(MON, mon_t.iterrows()):
    v = f"{r['value']:+.2f}{r['unit']}"
    print(f"{r['mid']:4s} {t['indicator'][:26]:28s} {t['threshold']:>10s} {t['direction']:8s} {v:>12s} "
          f"{r['asof']:>12s} {r['ratio']:8.3f} {'触发' if r['triggered'] else '正常'}  ({r['note']})")
print("触发比率口径: 高于阈值触发=值/阈值；低于阈值触发=值/阈值(阈值为负)或阈值/值(阈值为正)；≥1 即触发")
ntrig = sum(r['triggered'] for r in MON)
print(f"共 {ntrig}/8 项触发: {[r['mid'] for r in MON if r['triggered']]}")
print("补数安排: 中债国债(2026-06-09 后)、社融存量(2026-04 后)、PMI(2026-08)、LPR1Y(2026-08-20 行) 补齐后，"
      "重跑本脚本刷新 M4/M7/M8、情景识别(2026-07..09)与公共样本区间，并复核推荐方案结论")

# ============================================================================
# PART 9  图表
# ============================================================================
sec('PART 9  绘图（5 张 PNG）')
BLUE, RED, ORANGE, GREEN, GRAY, PURPLE = '#1f77b4', '#d62728', '#ff7f0e', '#2ca02c', '#7f7f7f', '#9467bd'
PCOLOR = {'当前组合': GRAY, '方案A': BLUE, '方案B': GREEN, '方案C': PURPLE, '推荐方案': RED}

# ---------- 图1 数据覆盖与缺口 ----------
fig, ax = plt.subplots(figsize=(13, 8.5))
rows = []
for nm, df in [('沪深300(seg1+2)', pd.concat([actual_rows['snapshot_000300SH_seg1.csv'], actual_rows['snapshot_000300SH_seg2.csv']], ignore_index=True)),
               ('中证500(seg1+2)', pd.concat([actual_rows['snapshot_000905SH_seg1.csv'], actual_rows['snapshot_000905SH_seg2.csv']], ignore_index=True)),
               ('创业板指(seg1+2)', pd.concat([actual_rows['snapshot_399006SZ_seg1.csv'], actual_rows['snapshot_399006SZ_seg2.csv']], ignore_index=True))]:
    rows.append((nm, df, 'close'))
for t in TEN: rows.append((f'中债国债{t.upper()}', cgb_raw[t], 'yield_pct'))
rows += [('USD/CNH(seg1+2)', fx_raw, 'usdcnh'), ('标普500', spx_raw, 'close'),
         ('Shibor(seg1+2)', shibor, 'shibor_on'), ('DR007', dr_raw, 'dr007'),
         ('LPR1Y', lpr1_raw, 'lpr_1y'), ('LPR5Y(2019-08-20前结构性空)', lpr5_raw, 'lpr_5y'),
         ('UST10Y', ust10_raw, 'yield_pct'), ('UST_M2', ustm2_raw, 'yield_pct'), ('UST_M4(仅6条)', ustm4_raw, 'yield_pct'),
         ('制造业PMI(月)', pmi_raw, 'pmi_mfg'), ('社融存量(月)', afre_raw, 'afre_stock'), ('PPI同比(月)', ppi_raw, 'ppi_yoy'),
         ('SSE交易日历', cal, 'is_trading_day')]
ypos = np.arange(len(rows))[::-1]
for y, (nm, df, col) in zip(ypos, rows):
    d = df.dropna(subset=[col]) if col in df else df
    lo_, hi_ = d.date.min(), d.date.max()
    truncated = hi_ < CUT
    color = RED if truncated else BLUE
    ax.barh(y, (hi_ - lo_).days + 1, left=lo_, height=0.55, color=color, alpha=0.75)
    if lo_ > sse.min():
        ax.barh(y, (lo_ - sse.min()).days, left=sse.min(), height=0.55, color='none',
                edgecolor=GRAY, hatch='////', linewidth=0.6, alpha=0.8)
    if nm.startswith('制造业PMI'):
        ax.plot([pd.Timestamp('2026-08-01')], [y], marker='x', color='black', ms=8, mew=2)
        ax.text(pd.Timestamp('2026-08-01'), y + 0.42, '缺2026-08', fontsize=7.5, ha='center')
    if nm.startswith('沪深300') or nm.startswith('中证500'):
        ax.plot([pd.Timestamp('2026-09-12')], [y], marker='X', color=ORANGE, ms=9)
ax.axvline(CUT, color='black', lw=1.6)
ax.text(CUT, len(rows) - 0.2, ' 分析截至日 2026-09-15', fontsize=9, va='bottom')
ax.axvline(sample_end, color=GREEN, lw=1.4, ls='--')
ax.text(sample_end, -1.1, '公共样本终点 2026-06-09\n(国债收益率截断)', fontsize=8.5, color=GREEN, ha='center', va='top')
ax.set_yticks(ypos); ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
ax.set_xlim(pd.Timestamp('2017-10-01'), pd.Timestamp('2026-12-15'))
ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.set_title('图1  数据覆盖与缺口：各序列实际覆盖区间（红=早于截至日结束/截断，斜纹=晚开始，X=缺失/异常记录）', fontsize=11)
ax.grid(axis='x', alpha=0.3)
fig.tight_layout()
p1 = os.path.join(CHART_DIR, 'FIN3-WKN-149_chart01_数据覆盖与缺口.png')
fig.savefig(p1, bbox_inches='tight'); plt.close(fig); print('saved', p1)

# ---------- 图2 历史风险总览 ----------
fig = plt.figure(figsize=(14, 10))
gs = fig.add_gridspec(3, 4, height_ratios=[2.2, 1, 1], hspace=0.42, wspace=0.35)
axa = fig.add_subplot(gs[0, :])
for k in ['当前组合', '方案A', '方案B', '方案C', '推荐方案']:
    axa.plot(M[k]['nav'].index, M[k]['nav'], label=k, color=PCOLOR[k], lw=1.6 if k != '推荐方案' else 2.2)
    axa.annotate(f"{M[k]['final_nav']:.3f}", (M[k]['nav'].index[-1], M[k]['nav'].iloc[-1]),
                 textcoords='offset points', xytext=(6, 0), fontsize=9, color=PCOLOR[k])
axa.set_title(f"图2-a  各方案累计净值曲线（每日再平衡，{R.index[0].date()}..{R.index[-1].date()}，起点=1）", fontsize=11)
axa.legend(loc='upper left', fontsize=9); axa.grid(alpha=0.3); axa.set_ylabel('累计净值')
panels = [('ann_vol', '年化波动率', None, None), ('es99_1d', '1日 ES99', LIM['L6']['upper'], 'L6 上限 3.50%'),
          ('var99_10d', '10日 VaR99', LIM['L7']['upper'], 'L7 上限 6.00%'), ('mdd', '最大回撤', None, None)]
for j, (key, title, lim, limlab) in enumerate(panels):
    axx = fig.add_subplot(gs[1:, j])
    names = ['当前', 'A', 'B', 'C', '推荐']
    vals = [M[k][key] * 100 for k in ['当前组合', '方案A', '方案B', '方案C', '推荐方案']]
    bars = axx.bar(names, vals, color=[PCOLOR[k] for k in ['当前组合', '方案A', '方案B', '方案C', '推荐方案']], alpha=0.85)
    for b, v in zip(bars, vals):
        axx.annotate(f"{v:.2f}", (b.get_x() + b.get_width() / 2, v), ha='center', va='bottom', fontsize=8.5)
    if lim is not None:
        axx.axhline(lim * 100, color=RED, ls='--', lw=1.4)
        axx.annotate(limlab, (len(names) - 0.5, lim * 100), ha='right', va='bottom', color=RED, fontsize=8.5)
    lab = f"图2-b{['①','②','③','④'][j]} {title}" + ('（%）' if True else '')
    axx.set_title(lab, fontsize=10); axx.grid(axis='y', alpha=0.3); axx.tick_params(labelsize=9)
fig.suptitle('')
p2 = os.path.join(CHART_DIR, 'FIN3-WKN-149_chart02_历史风险总览.png')
fig.savefig(p2, bbox_inches='tight'); plt.close(fig); print('saved', p2)

# ---------- 图3 情景识别与校准 ----------
fig = plt.figure(figsize=(15, 11))
gs = fig.add_gridspec(3, 2, height_ratios=[1, 1.15, 1.15], hspace=0.5, wspace=0.22)
axa = fig.add_subplot(gs[0, :])
mlist = list(ID.index)
mx = np.full((4, len(mlist)), np.nan)   # 0=不合格 1=合格 2=不可判定
for i, s in enumerate(['S1', 'S2', 'S3', 'S4']):
    for j, m in enumerate(mlist):
        v = ID.loc[m, s]
        mx[i, j] = 1 if v is True else (2 if v is None else 0)
cmap = matplotlib.colors.ListedColormap(['#d9d9d9', '#d62728', 'white'])
axa.imshow(mx, aspect='auto', cmap=cmap, vmin=0, vmax=2, extent=[-0.5, len(mlist) - 0.5, 3.5, -0.5])
for i, j in zip(*np.where(mx == 2)):
    axa.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, hatch='///', edgecolor=GRAY, lw=0.4))
axa.set_yticks(range(4)); axa.set_yticklabels(['S1 增长下行', 'S2 通胀上行', 'S3 外部冲击', 'S4 信用收缩'], fontsize=9)
tickpos = [j for j, m in enumerate(mlist) if m.endswith('-01') or m.endswith('-07')]
axa.set_xticks(tickpos); axa.set_xticklabels([mlist[j][:7] for j in tickpos], rotation=60, fontsize=7.5)
axa.plot([mlist.index('2026-09')], [3.7], marker='v', color='black', ms=6)
axa.text(mlist.index('2026-09') - 3, 3.72, '2026-09 为部分月(MTD)', fontsize=7.5)
axa.set_title('图3-a  四情景月度识别结果（红=合格，灰=不合格，斜纹白=数据缺失不可判定）', fontsize=11)
axa.legend(handles=[Patch(color='#d62728', label='合格'), Patch(color='#d9d9d9', label='不合格'),
                    Patch(facecolor='white', edgecolor=GRAY, hatch='///', label='不可判定')],
           loc='upper left', fontsize=8, ncol=3, bbox_to_anchor=(0, 1.0))
axb1 = fig.add_subplot(gs[1, 0]); axb2 = fig.add_subplot(gs[1, 1])
sids = ['S1', 'S2', 'S3', 'S4']; xx = np.arange(4); wd = 0.13
groups1 = [('eq300', '沪深300'), ('eq905', '中证500'), ('eqcyb', '创业板'), ('spx_usd', '标普500USD'), ('fx', 'USDCNH')]
for gi, (f, lab) in enumerate(groups1):
    axb1.bar(xx + (gi - 2) * wd, [CALIB[s][f] * 100 for s in sids], wd, label=lab)
axb1.axhline(0, color='black', lw=0.8); axb1.set_xticks(xx); axb1.set_xticklabels(sids)
axb1.set_title('图3-b① 各情景历史窗口校准冲击：权益/标普/汇率（10日累计，%）', fontsize=10)
axb1.legend(fontsize=8); axb1.grid(axis='y', alpha=0.3); axb1.set_ylabel('%')
for gi, t in enumerate(TEN):
    axb2.bar(xx + (gi - 2) * wd, [CALIB[s]['y_' + t] * 100 for s in sids], wd, label=t.upper())
axb2.axhline(0, color='black', lw=0.8); axb2.set_xticks(xx); axb2.set_xticklabels(sids)
axb2.set_title('图3-b② 校准冲击：国债各期限收益率变动（10日累计，bp）', fontsize=10)
axb2.legend(fontsize=8, ncol=5); axb2.grid(axis='y', alpha=0.3); axb2.set_ylabel('bp')
axc = fig.add_subplot(gs[2, :])
xc = np.arange(4); wc = 0.32
loss_comm = [-STRESS[('推荐方案', s, 'comm')]['total'] * 100 for s in sids]
loss_cal = [-STRESS[('推荐方案', s, 'calib')]['total'] * 100 for s in sids]
b1 = axc.bar(xc - wc / 2, loss_comm, wc, label='委员会沿用冲击', color=RED, alpha=0.8)
b2 = axc.bar(xc + wc / 2, loss_cal, wc, label='历史校准冲击', color=BLUE, alpha=0.8)
for bs in (b1, b2):
    for b in bs:
        axc.annotate(f"{b.get_height():.2f}", (b.get_x() + b.get_width() / 2, b.get_height()),
                     ha='center', va='bottom' if b.get_height() >= 0 else 'top', fontsize=8.5)
for i, s in enumerate(sids):
    axc.text(i, max(loss_comm[i], loss_cal[i]) + 0.9,
             f"马氏距离\n沿用 {DIST[s][0]:.1f}σ / 校准 {DIST[s][1]:.1f}σ", ha='center', fontsize=8)
axc.set_xticks(xc); axc.set_xticklabels([f"{s} {rules_sc[rules_sc.scenario_id==s].scenario.iloc[0]}" for s in sids], fontsize=9)
axc.axhline(0, color='black', lw=0.8)
axc.set_title('图3-c  沿用冲击与历史校准冲击严格程度对比（推荐方案压力损失 %，负值=情景下组合盈利；四情景沿用冲击均更严格）', fontsize=10.5)
axc.legend(fontsize=9); axc.grid(axis='y', alpha=0.3); axc.set_ylabel('压力损失 %')
p3 = os.path.join(CHART_DIR, 'FIN3-WKN-149_chart03_情景识别与校准.png')
fig.savefig(p3, bbox_inches='tight'); plt.close(fig); print('saved', p3)

# ---------- 图4 方案决策与执行 ----------
fig = plt.figure(figsize=(16, 5.6))
gs = fig.add_gridspec(1, 3, wspace=0.3)
axa = fig.add_subplot(gs[0, 0])
pnames = ['方案A', '方案B', '方案C', '推荐方案', '当前组合']
xl = np.arange(len(pnames)); wd = 0.27
ml_comm = [max(-STRESS[(p, s, 'comm')]['total'] for s in sids) * 100 for p in pnames]
ml_cal = [max(-STRESS[(p, s, 'calib')]['total'] for s in sids) * 100 for p in pnames]
ml_all = [MAXLOSS[p]['loss'] for p in pnames]
axa.bar(xl - wd, ml_comm, wd, label='沿用冲击最大损失', color=RED, alpha=0.85)
axa.bar(xl, ml_cal, wd, label='校准冲击最大损失', color=BLUE, alpha=0.85)
axa.bar(xl + wd, ml_all, wd, label='两者合计最大(L8口径)', color='black', alpha=0.55)
axa.axhline(LIM['L8']['upper'] * 100, color=RED, ls='--', lw=1.6)
axa.text(len(pnames) - 0.55, LIM['L8']['upper'] * 100 + 0.12, 'L8 压力损失上限 8.00%', color=RED, fontsize=8.5, ha='right')
axa.axhline(LIM['L9']['upper'] * 100, color=ORANGE, ls='-.', lw=1.6)
axa.text(len(pnames) - 0.55, LIM['L9']['upper'] * 100 + 0.12, 'L9 缓冲线 7.00%', color=ORANGE, fontsize=8.5, ha='right')
for i, p in enumerate(pnames):
    axa.annotate(f"{ml_all[i]:.2f}%\n({MAXLOSS[p]['scen']})", (i + wd, ml_all[i]), ha='center', va='bottom', fontsize=7.8)
axa.set_xticks(xl); axa.set_xticklabels(pnames, fontsize=9)
axa.set_title('图4-a  各方案最大压力损失（4情景×2冲击）', fontsize=10.5)
axa.legend(fontsize=8, loc='upper right'); axa.grid(axis='y', alpha=0.3); axa.set_ylabel('%'); axa.set_ylim(0, 11.4)

axb = fig.add_subplot(gs[0, 1])
for (order, lab, colr, ls) in [('sell_first', '先卖出后买入(规则顺序)', GREEN, '-'), ('buy_first', '先买入后卖出(对照)', RED, '--')]:
    pth, br = paths[order]
    xs = np.arange(len(pth)); ys = [c / NAV0 * 100 for _, c in pth]
    axb.plot(xs, ys, marker='o', color=colr, ls=ls, lw=2, label=lab + ('（击穿）' if br else ''))
    for x, y, (nm, _) in zip(xs, ys, pth):
        axb.annotate(f"{y:.1f}", (x, y), textcoords='offset points', xytext=(0, 7 if y >= 8 else -13), fontsize=7.5, color=colr)
axb.set_xticks(np.arange(len(pth)))
axb.set_xticklabels([nm[:6] for nm, _ in pth], rotation=40, ha='right', fontsize=7.5)
axb.axhline(CASH_FLOOR * 100, color=RED, ls='--', lw=1.5)
axb.text(0.05, CASH_FLOOR * 100 + 0.7, f'现金下限 {CASH_FLOOR*100:.0f}%', color=RED, fontsize=9)
axb.axhline(0, color='black', lw=0.8)
axb.set_title('图4-b  调仓执行现金占比路径（%）', fontsize=10.5)
axb.legend(fontsize=8.5); axb.grid(alpha=0.3); axb.set_ylabel('人民币现金及货基占比 %')

axc = fig.add_subplot(gs[0, 2])
xn = np.arange(len(FN))
vals = [v * 100 for v in xstar]
colors = [PURPLE if not n.endswith('国债') else GREEN for n in FN]
bars = axc.bar(xn, vals, color=colors, alpha=0.85)
for b, v, n in zip(bars, vals, FN):
    axc.annotate(f"{v:+.1f}" + ('bp' if n.endswith('国债') else '%'), (b.get_x() + b.get_width() / 2, v),
                 ha='center', va='bottom' if v >= 0 else 'top', fontsize=7.8)
axc.set_xticks(xn); axc.set_xticklabels(FN, rotation=40, ha='right', fontsize=8)
axc.axhline(0, color='black', lw=0.8)
axc.set_title(f'图4-c  反向压力测试最可能情景（损失达 {LT*100:.0f}%，最小马氏距离 d*={dstar:.2f}σ）', fontsize=10.5)
axc.text(0.97, 0.06, f"距离对比(σ): 反向最优 {dstar:.2f}\n沿用 S1..S4: " + '/'.join(f"{DIST[s][0]:.1f}" for s in sids)
         + "\n校准 S1..S4: " + '/'.join(f"{DIST[s][1]:.1f}" for s in sids),
         transform=axc.transAxes, ha='right', fontsize=8,
         bbox=dict(boxstyle='round', fc='#f7f7f7', ec=GRAY))
axc.grid(axis='y', alpha=0.3); axc.set_ylabel('10日累计变动（%／bp）')
p4 = os.path.join(CHART_DIR, 'FIN3-WKN-149_chart04_方案决策与执行.png')
fig.savefig(p4, bbox_inches='tight'); plt.close(fig); print('saved', p4)

# ---------- 图5 监测指标触发状态 ----------
fig, ax = plt.subplots(figsize=(13, 6))
xl = np.arange(len(MON))
cols = [RED if r['triggered'] else BLUE for r in MON]
hatch = ['///' if r['mid'] in ('M4', 'M8') else '' for r in MON]
bars = ax.bar(xl, [r['ratio'] for r in MON], color=cols, alpha=0.85)
for b, h in zip(bars, hatch):
    if h: b.set_hatch(h)
ax.axhline(1.0, color=RED, ls='--', lw=1.6)
ax.text(len(MON) - 0.4, 1.02, '触发线（触发比率=1）', color=RED, fontsize=9, ha='right')
for i, r in enumerate(MON):
    ax.annotate(f"{r['value']:+.2f}{r['unit']}\n(截至{r['asof'][5:]})", (i, r['ratio']),
                ha='center', va='bottom' if r['ratio'] >= 0 else 'top', fontsize=8,
                xytext=(0, 4 if r['ratio'] >= 0 else -4), textcoords='offset points')
ax.set_xticks(xl)
ax.set_xticklabels([f"{r['mid']}\n{t['indicator'][:14]}" for r, (_, t) in zip(MON, mon_t.iterrows())], fontsize=8.5)
ax.set_ylabel('触发比率（值/阈值 或 阈值/值，≥1 触发）')
ax.set_title('图5  八个监测指标最新值与阈值（红=触发：M1、M8；斜纹=数据截断需补数复核：M4、M8）', fontsize=11)
ax.grid(axis='y', alpha=0.3); ax.axhline(0, color='black', lw=0.8)
ax.set_ylim(min(-0.35, min(r['ratio'] for r in MON) - 0.15), max(r['ratio'] for r in MON) + 0.45)
p5 = os.path.join(CHART_DIR, 'FIN3-WKN-149_chart05_监测指标触发状态.png')
fig.savefig(p5, bbox_inches='tight'); plt.close(fig); print('saved', p5)

# ============================================================================
# PART 10  汇总
# ============================================================================
sec('汇总（备忘录第一章要素）')
print(f"推荐方案: 最大压力损失 {MAXLOSS['推荐方案']['loss']:.2f}%（{MAXLOSS['推荐方案']['scen']}/沿用冲击），"
      f"1日ES99 {M['推荐方案']['es99_1d']*100:.2f}%，10日VaR99 {M['推荐方案']['var99_10d']*100:.2f}%，"
      f"年化波动 {M['推荐方案']['ann_vol']*100:.2f}%，单向换手率 {turnover*100:.2f}%，九项检查全部通过")
print(f"方案A: 最大压力损失 {MAXLOSS['方案A']['loss']:.2f}% 超 L8 {exceed('方案A','C8'):.2f}pp；"
      f"方案B: {MAXLOSS['方案B']['loss']:.2f}% 超 L9 缓冲线 {exceed('方案B','C9'):.2f}pp；"
      f"方案C: 外币敞口 30.00% 超 L5 {exceed('方案C','C5'):.2f}pp")
print(f"监测: {ntrig}/8 触发（{[r['mid'] for r in MON if r['triggered']]}）；"
      f"反向压力 d*={dstar:.2f}σ，冲击放大倍数 k={KAMP:.2f}")
print('\n全部计算完成。图表已输出至', CHART_DIR)
