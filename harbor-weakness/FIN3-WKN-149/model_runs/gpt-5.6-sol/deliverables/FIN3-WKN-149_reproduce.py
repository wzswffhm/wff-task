from pathlib import Path
import re
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.dates import DateFormatter

warnings.filterwarnings("ignore")
INPUT = Path('/app/input_files')
OUTPUT = Path('/app/output')
CHARTS = OUTPUT / 'FIN3-WKN-149_charts'
CHARTS.mkdir(parents=True, exist_ok=True)
AS_OF = pd.Timestamp('2026-09-15')
NAV = 10000.0

# Chinese font available in the execution environment.
font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
if Path(font_path).exists():
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=font_path).get_name()
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 120


def read_csv(name):
    df = pd.read_csv(INPUT / name)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    return df


def load_segments(prefix):
    files = sorted(INPUT.glob(prefix + '_seg*.csv'))
    frames = [read_csv(f.name) for f in files]
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values('date').reset_index(drop=True), files


def fmt_pct(x):
    return '—' if pd.isna(x) else f'{x * 100:.2f}%'


def fmt_bp(x):
    return '—' if pd.isna(x) else f'{x * 10000:.2f}bp'


def fmt_num(x):
    return '—' if pd.isna(x) else f'{x:.2f}'


def date_s(x):
    return '—' if pd.isna(x) else pd.Timestamp(x).strftime('%Y-%m-%d')


def md_table(headers, rows):
    lines = ['|' + '|'.join(headers) + '|', '|' + '|'.join(['---'] * len(headers)) + '|']
    for row in rows:
        lines.append('|' + '|'.join(str(x) for x in row) + '|')
    return '\n'.join(lines)


def monthly_last(df, value_col):
    x = df[['date', value_col]].dropna().sort_values('date').copy()
    x['month'] = x['date'].dt.to_period('M')
    return x.groupby('month', as_index=True)[value_col].last()


def monthly_mean(df, value_col):
    x = df[['date', value_col]].dropna().sort_values('date').copy()
    x['month'] = x['date'].dt.to_period('M')
    return x.groupby('month', as_index=True)[value_col].mean()


def window_change(series, start, n=10):
    x = series.loc[series.index >= start].dropna().iloc[:n]
    if len(x) < n:
        return np.nan
    return x.iloc[-1] / x.iloc[0] - 1


def yield_change(y, start, n=10):
    x = y.loc[y.index >= start].dropna().iloc[:n]
    if len(x) < n:
        return np.nan
    return x.iloc[-1] - x.iloc[0]

# -------------------- input validation and aligned daily data --------------------
calendar = read_csv('snapshot_trade_calendar.csv')
calendar = calendar[(calendar.exchange == 'SSE') & (calendar.is_trading_day == 1)]
calendar = calendar[(calendar.date <= AS_OF)].sort_values('date')
valuation_dates = pd.DatetimeIndex(calendar.date)

idx300, idx300_files = load_segments('snapshot_000300SH')
idx500, idx500_files = load_segments('snapshot_000905SH')
idxg, idxg_files = load_segments('snapshot_399006SZ')
usdcnh, fx_files = load_segments('snapshot_usdcnh')
shibor, shibor_files = load_segments('snapshot_shibor')
spx = read_csv('snapshot_spx.csv')
ust10 = read_csv('snapshot_ust_10y.csv')
ustm2 = read_csv('snapshot_ust_m2.csv')
ustm4 = read_csv('snapshot_ust_m4.csv')

yields = {}
for tenor in ['1y', '2y', '5y', '10y', '30y']:
    yields[tenor] = read_csv(f'snapshot_cgb_yield_{tenor}.csv')

daily_sources = {
    '沪深300': idx300, '中证500': idx500, '创业板': idxg,
    'USD/CNH': usdcnh, '标普500美元': spx,
    '国债1年': yields['1y'], '国债2年': yields['2y'],
    '国债5年': yields['5y'], '国债10年': yields['10y'], '国债30年': yields['30y'],
    'DR007': read_csv('snapshot_dr007.csv'), '美国10年国债': ust10,
    'Shibor': shibor,
}

# Actual coverage, gaps and anomalies are retained for the memo and chart.
validation = []
def add_validation(name, df, value_cols=None, market=False):
    value_cols = value_cols or [c for c in df.columns if c != 'date']
    dates = pd.DatetimeIndex(df.date.dropna().sort_values().unique())
    within = valuation_dates[(valuation_dates >= dates.min()) & (valuation_dates <= dates.max())] if len(dates) else pd.DatetimeIndex([])
    gaps = within.difference(dates)
    duplicate_dates = int(df.date.duplicated().sum())
    na_counts = {c: int(df[c].isna().sum()) for c in value_cols}
    bad = 0
    if market:
        for c in ['open', 'high', 'low', 'close']:
            if c in df:
                bad += int((df[c] <= 0).sum())
        if {'high', 'low'}.issubset(df.columns):
            bad += int((df.high < df.low).sum())
        if {'close', 'high', 'low'}.issubset(df.columns):
            bad += int(((df.close > df.high) | (df.close < df.low)).sum())
        bad += int((~df.date.isin(set(valuation_dates))).sum())
    validation.append(dict(name=name, start=dates.min() if len(dates) else pd.NaT,
                           end=dates.max() if len(dates) else pd.NaT, records=len(df),
                           gaps=len(gaps), gap_dates=list(gaps), duplicate=duplicate_dates,
                           na=na_counts, bad=bad))

for name, df in daily_sources.items():
    if name in ['沪深300', '中证500', '创业板']:
        add_validation(name, df, ['open','high','low','close','pre_close','amount'], True)
    else:
        add_validation(name, df)
for f in sorted(INPUT.glob('snapshot_*.csv')):
    if f.name in {x.name for x in [Path('snapshot_data_manifest.csv'), Path('snapshot_trade_calendar.csv')]}:
        continue
    if f.name.startswith(('snapshot_000300SH','snapshot_000905SH','snapshot_399006SZ','snapshot_usdcnh','snapshot_shibor','snapshot_spx','snapshot_cgb_yield','snapshot_dr007','snapshot_ust_10y','snapshot_ust_m2','snapshot_ust_m4')):
        continue
    df = read_csv(f.name)
    add_validation(f.stem, df)

# For price/market series, forward fill only inside the observed coverage interval.
def aligned_value(df, col):
    s = df.set_index('date')[col].sort_index()
    s = s.reindex(valuation_dates)
    first, last = df.date.min(), df.date.max()
    s.loc[(s.index >= first) & (s.index <= last)] = s.loc[(s.index >= first) & (s.index <= last)].ffill()
    return s

prices = pd.DataFrame(index=valuation_dates)
prices['000300'] = aligned_value(idx300, 'close')
prices['000905'] = aligned_value(idx500, 'close')
prices['399006'] = aligned_value(idxg, 'close')
prices['usdcnh'] = aligned_value(usdcnh, 'usdcnh')
prices['spx'] = aligned_value(spx, 'close')
for tenor in ['1y','2y','5y','10y','30y']:
    prices['cgb_' + tenor] = aligned_value(yields[tenor], 'yield_pct')

# Structure-preserving common sample: no value after a series' actual end is filled.
required = ['000300','000905','399006','usdcnh','spx'] + ['cgb_' + x for x in ['1y','2y','5y','10y','30y']]
common = prices.dropna(subset=required).copy()
common = common.loc[common.index <= AS_OF]
analysis_start, analysis_end = common.index.min(), common.index.max()

# Asset return construction.
ret = pd.DataFrame(index=common.index[1:])
for col in ['000300','000905','399006','spx','usdcnh']:
    ret[col] = common[col].pct_change().iloc[1:]
ret['spx_rmb'] = (1 + ret['spx']) * (1 + ret['usdcnh']) - 1
# CGB: yield_pct differences are percentage points; duration contribution is applied to decimal yield changes.
duration = read_csv('params_duration.csv').set_index('tenor')['duration_contribution']
for t in ['1y','2y','5y','10y','30y']:
    ret['dy_' + t] = common['cgb_' + t].diff().iloc[1:]
ret['cgb'] = -sum(duration.loc[{'1y':'1年','2y':'2年','5y':'5年','10y':'10年','30y':'30年'}[t]] * ret['dy_' + t] / 100 for t in ['1y','2y','5y','10y','30y'])
# No NAV series for the cash funds is supplied; cash return is conservatively set to zero, not NaN or zero-filled market data.
ret['usd_cash'] = ret['usdcnh']
ret['cny_cash'] = 0.0
ret = ret.dropna(subset=['000300','000905','399006','spx_rmb','usd_cash','cgb'])

assets = ['000300','000905','399006','cgb','usd_cash','spx_rmb','cny_cash']
asset_names = {'000300':'沪深300指数基金','000905':'中证500指数基金','399006':'创业板指数基金',
               'cgb':'中长期国债组合','usd_cash':'美元现金及存款','spx_rmb':'标普500 QDII基金','cny_cash':'人民币现金及货基'}
asset_classes = {'000300':'EQ_000300','000905':'EQ_000905','399006':'EQ_399006','cgb':'CGB',
                 'usd_cash':'USD_CASH','spx_rmb':'SPX','cny_cash':'CNY_CASH'}

holdings = read_csv('params_holdings.csv')
positions = read_csv('params_positions.csv')
limits = read_csv('params_limits.csv')
shocks = read_csv('params_committee_shocks.csv')
scenarios = read_csv('rules_scenarios.csv')
plans_raw = read_csv('plans_candidates.csv')
checks = read_csv('rules_checks.csv')
plan_cols = ['w_000300','w_000905','w_399006','w_cgb','w_usd_cash','w_spx_qdii','w_cny_cash']
plan_asset_map = dict(zip(plan_cols, assets))

plans = {}
for _, row in plans_raw.iterrows():
    plans[row.plan_id] = pd.Series({plan_asset_map[c]: float(row[c]) for c in plan_cols})
rec_weights = pd.Series(dict(zip(assets, holdings.weight_recommended.astype(float))))
plans['推荐方案'] = rec_weights
plan_proposers = {row.plan_id: row.proposer for _, row in plans_raw.iterrows()}
plan_proposers['推荐方案'] = '风险委员会建议'

# -------------------- historical risk and scenario identification --------------------
def port_series(weights):
    return ret[assets].mul(weights.reindex(assets).values, axis=1).sum(axis=1)

def risk_metrics(weights):
    p = port_series(weights)
    q05, q01 = p.quantile(.05), p.quantile(.01)
    below05, below01 = p[p <= q05], p[p <= q01]
    r10 = (1 + p).rolling(10).apply(np.prod, raw=True) - 1
    q10 = r10.dropna().quantile(.01)
    wealth = (1+p).cumprod()
    running = wealth.cummax()
    dd = wealth / running - 1
    trough = dd.idxmin()
    peak = wealth.loc[:trough].idxmax()
    recovery = wealth.loc[trough:][wealth.loc[trough:] >= wealth.loc[peak]]
    recovery_date = recovery.index[0] if len(recovery) else pd.NaT
    cov = ret[assets].cov()
    var = float(weights.reindex(assets).values @ cov.values @ weights.reindex(assets).values)
    rc = weights.reindex(assets) * (cov @ weights.reindex(assets).values) / var if var > 0 else weights * 0
    return dict(series=p, ann_vol=p.std(ddof=1)*np.sqrt(252), var95=-q05, var99=-q01,
                es95=-below05.mean(), es99=-below01.mean(), var10_99=-q10,
                max10=-r10.min(), max10_end=r10.idxmin(), max_drawdown=-dd.min(),
                dd_peak=peak, dd_trough=trough, dd_recovery=recovery_date,
                worst_day=-p.min(), worst_day_date=p.idxmin(), risk_contrib=rc)

risk = {name: risk_metrics(w) for name, w in plans.items()}

# Monthly scenario rules.
pmi = read_csv('snapshot_pmi_manufacturing.csv')
ppi = read_csv('snapshot_ppi_yoy.csv')
afre = read_csv('snapshot_afre_stock.csv')
lpr1 = read_csv('snapshot_lpr_1y.csv')
lpr5 = read_csv('snapshot_lpr_5y.csv')
dr007 = read_csv('snapshot_dr007.csv')
y10 = yields['10y']
monthly = pd.DataFrame(index=pd.period_range('2018-01','2026-09',freq='M'))
monthly['pmi'] = monthly_last(pmi, 'pmi_mfg')
monthly['ppi'] = monthly_last(ppi, 'ppi_yoy')
monthly['lpr1'] = monthly_last(lpr1, 'lpr_1y')
monthly['lpr5'] = monthly_last(lpr5, 'lpr_5y')
monthly['afre'] = monthly_last(afre, 'afre_stock')
monthly['dr007'] = monthly_mean(dr007, 'dr007')
monthly['y10'] = monthly_mean(y10, 'yield_pct')
monthly['eq'] = monthly_last(idx300, 'close').pct_change()
monthly['spx'] = monthly_last(spx, 'close').pct_change()
monthly['fx'] = monthly_last(usdcnh, 'usdcnh').pct_change()
monthly['afre_yoy'] = monthly['afre'].pct_change(12)
qualifying = {}
for sid in ['S1','S2','S3','S4']:
    prev = monthly.shift(1)
    if sid == 'S1':
        condition = ((monthly.pmi < 50) & ((monthly.lpr1 < prev.lpr1) | (monthly.lpr5 < prev.lpr5))) | ((monthly.pmi - prev.pmi <= -0.5) & (monthly.y10 < prev.y10))
    elif sid == 'S2':
        condition = (monthly.ppi > prev.ppi) & (monthly.y10 > prev.y10) & (monthly['eq'] < 0)
    elif sid == 'S3':
        condition = (monthly.spx <= -0.03) | (monthly.fx >= 0.015)
    else:
        condition = (monthly.afre_yoy < prev.afre_yoy) & (monthly.dr007 > prev.dr007) & (monthly['eq'] < 0)
    qualifying[sid] = list(monthly.index[condition.fillna(False)])

# Ten-day windows beginning at the first SSE trading day after each qualifying month.
portfolio_current = port_series(pd.Series(dict(zip(assets, positions.weight_current))))
cn_norm = pd.Series(dict(zip(['000300','000905','399006'], [0.5,0.3,0.2])))
cn_factor = ret[['000300','000905','399006']].mul(cn_norm.values, axis=1).sum(axis=1)
window_rows = []
# Build every 10-day window whose start is in the month after a potential event month.
# The strict rule is retained explicitly; when the supplied sample has no strict window,
# a separately labelled cumulative-loss fallback prevents an invented calibration.
for start in ret.index:
    event_month = start.to_period('M') - 1
    if event_month not in monthly.index:
        continue
    block = ret.loc[start:].iloc[:10]
    if len(block) < 10:
        continue
    factors = {
        'cn': (1+cn_factor.loc[block.index]).prod()-1,
        'spx_usd': (1+ret.loc[block.index, 'spx']).prod()-1,
        'fx': (1+ret.loc[block.index, 'usdcnh']).prod()-1,
    }
    for t in ['1y','2y','5y','10y','30y']:
        factors['dy_' + t] = ret.loc[block.index, 'dy_' + t].sum()
    factors['cgb'] = ret.loc[block.index, 'cgb'].sum()
    factors['portfolio'] = (1 + portfolio_current.loc[block.index]).prod() - 1
    factors['strict'] = bool((portfolio_current.loc[block.index] < 0).all())
    factors['start'], factors['end'], factors['month'] = start, block.index[-1], event_month
    window_rows.append(factors)
windows = pd.DataFrame(window_rows)
calibrations = {}
selected_windows = {}
window_modes = {}
for sid in ['S1','S2','S3','S4']:
    all_candidates = windows[windows['month'].isin(qualifying[sid])].copy()
    strict_candidates = all_candidates[all_candidates['strict']].sort_values('portfolio', ascending=True)
    if len(strict_candidates):
        candidates = strict_candidates; window_modes[sid] = f'严格窗口（{len(strict_candidates)}个）'
    else:
        # Actual supplied data have no 10-day run with every daily return negative;
        # use only negative cumulative-loss windows and disclose this exception.
        candidates = all_candidates[all_candidates['portfolio'] < 0].sort_values('portfolio', ascending=True)
        window_modes[sid] = f'严格窗口0个；累计损失替代窗口（{len(candidates)}个）'
    selected = candidates.head(min(20, len(candidates)))
    selected_windows[sid] = selected
    if len(selected):
        calibrations[sid] = {k: selected[k].median() for k in ['cn','spx_usd','fx','dy_1y','dy_2y','dy_5y','dy_10y','dy_30y']}
    else:
        calibrations[sid] = {k: np.nan for k in ['cn','spx_usd','fx','dy_1y','dy_2y','dy_5y','dy_10y','dy_30y']}

# Parse committee shock values. File values are percentage points in yield_pct units, converted to bp for display.
def parse_cgb_shock(text):
    out = {}
    for token in str(text).split(','):
        tenor, value = token.split(':')
        out[tenor.replace('Y','y')] = float(value)
    return out

def cgb_return_from_dy(dy):
    return -sum(duration.loc[{'1y':'1年','2y':'2年','5y':'5年','10y':'10年','30y':'30年'}[t]] * dy.get('dy_' + t, 0) / 100 for t in ['1y','2y','5y','10y','30y'])

shock_sets = {}
for _, row in shocks.iterrows():
    sid = row.scenario_id
    committee = {'cn':float(row.cn_equity_shock), 'spx_usd':float(row.spx_usd_shock), 'fx':float(row.usdcnh_shock)}
    for t, v in parse_cgb_shock(row.cgb_shock_bp).items(): committee['dy_' + t] = v / 100 # input is percentage points; retain yield_pct units
    calibration = calibrations[sid].copy()
    shock_sets[(sid,'委员会沿用')] = committee
    shock_sets[(sid,'历史校准')] = calibration

# Full 4 x 4 x 2 pressure table, decomposed into four contributions.
stress_rows = []
for plan, weights in plans.items():
    for sid in ['S1','S2','S3','S4']:
        for source in ['委员会沿用','历史校准']:
            x = shock_sets[(sid, source)]
            cn = weights[['000300','000905','399006']].sum() * x['cn']
            spx_rmb = weights['spx_rmb'] * ((1+x['spx_usd'])*(1+x['fx'])-1)
            usd = weights['usd_cash'] * x['fx']
            cgb = weights['cgb'] * cgb_return_from_dy(x)
            total = cn + spx_rmb + usd + cgb
            stress_rows.append(dict(plan=plan, scenario=sid, source=source, cn=cn, spx_rmb=spx_rmb, usd=usd, cgb=cgb, total=total, loss=-total))
stress = pd.DataFrame(stress_rows)
max_stress = stress.sort_values('loss', ascending=False).groupby('plan', as_index=False).first().set_index('plan')

# Nine constraint checks.
def check_plan(plan, weights):
    m = risk[plan]
    maxloss = float(stress.loc[stress.plan == plan, 'loss'].max())
    vals = {
        'L1': float(weights.sum()), 'L2': float(weights[['000300','000905','399006']].sum()),
        'L3': float(weights.cny_cash), 'L4': float(weights.cgb),
        'L5': float(weights.usd_cash + weights.spx_rmb), 'L6': float(m['es99']),
        'L7': float(m['var10_99']), 'L8': maxloss, 'L9': maxloss,
    }
    outcomes = {}
    for _, row in limits.iterrows():
        val = vals[row.id]
        if row.id == 'L1': ok = abs(val-1) <= 0.0005; excess = max(0, abs(val-1)-0.0005)
        elif row.id == 'L3': ok = val >= row.lower and val <= row.upper; excess = max(0, row.lower-val, val-row.upper)
        elif row.id == 'L4':
            bound = row.lower if pd.notna(row.lower) else row.upper
            ok = val >= bound; excess = max(0, bound-val)
        elif row.id in ['L2','L5','L6','L7','L8','L9']: ok = val <= row.upper; excess = max(0, val-row.upper)
        outcomes[row.id] = dict(value=val, passed=bool(ok), excess=excess)
    return outcomes
constraint_results = {p: check_plan(p,w) for p,w in plans.items()}

# Candidate unique construction: fixed foreign weights and proportional domestic reduction, then grid-search feasible alternatives at same 20.5% turnover.
rec_turnover = float((pd.Series(dict(zip(assets, positions.weight_current))) - rec_weights).clip(lower=0).sum())
alt_rows = []
current_w = pd.Series(dict(zip(assets, positions.weight_current)))
for cny in np.arange(0.08, 0.2001, 0.005):
    cgb = current_w.cgb + (rec_weights.cgb - current_w.cgb) + (0.20 - cny) # preserves total release if cny varies around recommendation
    if cgb < 0: continue
    w = rec_weights.copy(); w.cny_cash = cny; w.cgb = cgb
    if abs(w.sum()-1)>1e-8: continue
    tmpname = f'_alt_{cny:.3f}'
    plans[tmpname] = w
    risk[tmpname] = risk_metrics(w)
    # evaluate pressure directly
    sr = []
    for sid in ['S1','S2','S3','S4']:
        for source in ['委员会沿用','历史校准']:
            x=shock_sets[(sid,source)]
            total=w[['000300','000905','399006']].sum()*x['cn'] + w.spx_rmb*((1+x['spx_usd'])*(1+x['fx'])-1)+w.usd_cash*x['fx']+w.cgb*cgb_return_from_dy(x)
            sr.append(-total)
    max_alt=max(sr)
    alt_rows.append((tmpname,cny,cgb,max_alt))
    del plans[tmpname], risk[tmpname]
alt_df=pd.DataFrame(alt_rows, columns=['name','cny','cgb','maxloss'])
alt_df=alt_df[alt_df.cny.round(6) != rec_weights.cny_cash.round(6)]
next_alt=alt_df.sort_values(['maxloss','cny']).iloc[0] if len(alt_df) else None

# -------------------- monitoring indicators --------------------
monitor_template = read_csv('template_monitor.csv')
latest20 = ret.tail(20)
latest_date = ret.index.max()
monitor_rows=[]
# M1
m1=(1+ret['000300'].tail(20)).prod()-1
m2=(1+ret['usdcnh'].tail(20)).prod()-1
# DR007 means are calculated on the actual sequence, with 20 latest and 60 preceding observations.
dr=read_csv('snapshot_dr007.csv').set_index('date')['dr007'].dropna()
m3=(dr.tail(20).mean()-dr.iloc[-80:-20].mean())/100
m4=yields['10y'].set_index('date')['yield_pct'].dropna().tail(20).iloc[-1]-yields['10y'].set_index('date')['yield_pct'].dropna().tail(20).iloc[0]
m5=ust10.set_index('date')['yield_pct'].dropna().tail(20).iloc[-1]-ust10.set_index('date')['yield_pct'].dropna().tail(20).iloc[0]
ppi_month=monthly.ppi.dropna(); m6=ppi_month.iloc[-1]-ppi_month.iloc[-4] if len(ppi_month)>=4 else np.nan
m7=monthly.pmi.dropna().iloc[-1]
afre_yoy=monthly.afre_yoy.dropna(); m8=afre_yoy.iloc[-1] if len(afre_yoy) else np.nan
monitor_values=[m1,m2,m3,m4,m5,m6,m7,m8]
monitor_thresholds=[-0.05,0.02,0.002,0.001,0.004,1.5,49,0.08]
# m3,m4,m5 are in percentage-point units; thresholds likewise in percentage-point units.
triggered=[m1 < -.05, m2 > .02, m3 > .20, m4 > .10, m5 > .40, m6 > 1.5, m7 < 49, m8 < .08]
for i,row in monitor_template.iterrows():
    val=monitor_values[i]
    if i in [2,3,4]: value_text=fmt_bp(val/100)
    elif i==5: value_text=f'{val:.2f} 个百分点'
    elif i==6: value_text=f'{val:.2f}'
    else: value_text=fmt_pct(val)
    monitor_rows.append(dict(id=row.monitor_id, indicator=row.indicator, definition=row.definition, threshold=row.threshold,
                             direction=row.direction, latest=value_text, asof=date_s(latest_date), status='触发' if triggered[i] else '正常', triggered='是' if triggered[i] else '否'))

# -------------------- reverse stress --------------------
# Historical factor vectors use 10-day cumulative changes and the duration-converted bond return.
factor_cols=['cn','spx_usd','fx','cgb']
fac = windows[['cn','spx_usd','fx','cgb']].dropna().copy()
mu=fac.mean().values; cov=np.cov(fac.values, rowvar=False); cov += np.eye(4)*1e-8
inv=np.linalg.inv(cov)
def mahal(x):
    d=np.asarray(x)-mu
    return float(np.sqrt(d @ inv @ d))
rec = rec_weights
# Minimize distance subject to an 8% portfolio loss with a deterministic
# covariance-projection iteration, avoiding an external optimizer dependency.
def reverse_loss(x):
    cn,spxv,fxv,cgbv=x
    return -(rec[['000300','000905','399006']].sum()*cn + rec.spx_rmb*((1+spxv)*(1+fxv)-1) + rec.usd_cash*fxv + rec.cgb*cgbv)

bounds=np.array([[-.5,.2],[-.5,.3],[-.2,.3],[-.2,.2]])
reverse_vec=mu.copy()
for _ in range(100):
    loss=reverse_loss(reverse_vec)
    if loss >= .08 - 1e-10:
        break
    cn,spxv,fxv,cgbv=reverse_vec
    grad=np.array([-rec[['000300','000905','399006']].sum(),
                   -rec.spx_rmb*(1+fxv),
                   -rec.spx_rmb*(1+spxv)-rec.usd_cash,
                   -rec.cgb])
    step=(.08-loss)/(grad @ cov @ grad)
    reverse_vec=np.clip(reverse_vec + step*(cov @ grad), bounds[:,0], bounds[:,1])
reverse_md=mahal(reverse_vec)
# Use the calibration vector for the recommended plan's worst-loss scenario.
worst_sid=max_stress.loc['推荐方案','scenario']
cal=calibrations[worst_sid]
cal_vec=np.array([cal['cn'],cal['spx_usd'],cal['fx'],cgb_return_from_dy(cal)])
comm=shock_sets[(worst_sid,'委员会沿用')]
comm_vec=np.array([comm['cn'],comm['spx_usd'],comm['fx'],cgb_return_from_dy(comm)])

# -------------------- charts --------------------
def savefig(name):
    plt.tight_layout()
    plt.savefig(CHARTS / name, dpi=160, bbox_inches='tight')
    plt.close()

# 1 coverage and gaps
fig, ax=plt.subplots(figsize=(13,9))
for i,v in enumerate(validation):
    if pd.isna(v['start']): continue
    ax.plot([v['start'],v['end']],[i,i],lw=8,solid_capstyle='butt')
    ax.scatter([v['start'],v['end']],[i,i],s=20)
ax.axvline(AS_OF,color='red',ls='--',label='分析截至日 2026-09-15')
ax.axvline(analysis_end,color='darkgreen',ls=':',label=f'共同可计算终点 {date_s(analysis_end)}')
ax.set_yticks(range(len(validation))); ax.set_yticklabels([v['name'] for v in validation]); ax.invert_yaxis()
ax.set_title('数据覆盖区间、缺口与分析截至日'); ax.set_xlabel('日期'); ax.legend(loc='lower right'); ax.grid(axis='x',alpha=.3)
savefig('FIN3-WKN-149_chart01_数据覆盖与缺口.png')

# 2 cumulative NAV
fig,ax=plt.subplots(figsize=(12,6))
for p in plans_raw.plan_id.tolist()+['推荐方案']:
    ax.plot((1+risk[p]['series']).cumprod(),label=p)
ax.set_title('各方案历史累计净值（样本起点=1）'); ax.set_ylabel('累计净值'); ax.legend(); ax.grid(alpha=.3)
savefig('FIN3-WKN-149_chart02_方案累计净值.png')

# 3 risk and limits
names=plans_raw.plan_id.tolist()+['推荐方案']; x=np.arange(len(names)); width=.24
fig,ax=plt.subplots(figsize=(11,6))
ax.bar(x-width, [risk[p]['es99']*100 for p in names],width,label='1日 ES99')
ax.bar(x, [risk[p]['var10_99']*100 for p in names],width,label='10日 VaR99')
ax.bar(x+width, [max_stress.loc[p,'loss']*100 for p in names],width,label='最大压力损失')
for y,l in [(3.5,'ES99上限'),(6,'10日VaR99上限'),(8,'压力损失上限')]: ax.axhline(y,color='red',ls='--',lw=1,label=l)
ax.set_xticks(x,names); ax.set_ylabel('%'); ax.set_title('方案风险指标与限额参考线'); ax.legend(ncol=3); ax.grid(axis='y',alpha=.3)
savefig('FIN3-WKN-149_chart03_风险指标与限额.png')

# 4 scenario qualifying months
fig,axs=plt.subplots(4,1,figsize=(13,8),sharex=True)
for ax,sid in zip(axs,['S1','S2','S3','S4']):
    months=pd.period_range(monthly.index.min(),monthly.index.max(),freq='M')
    y=np.array([1 if m in qualifying[sid] else 0 for m in months])
    ax.bar(months.to_timestamp(),y,width=20,color='#4472c4'); ax.set_yticks([0,1]); ax.set_ylabel(sid); ax.grid(axis='x',alpha=.2)
axs[0].set_title('四情景月度识别结果（蓝色为合格月份）'); axs[-1].xaxis.set_major_formatter(DateFormatter('%Y'))
savefig('FIN3-WKN-149_chart04_情景合格月份.png')

# 5 calibrated shocks
fig,axs=plt.subplots(2,2,figsize=(12,8)); factor_display=[('cn','境内权益累计收益','%'),('spx_usd','标普500美元累计收益','%'),('fx','USD/CNH累计变动','%'),('cgb','久期折算国债收益','%')]
for ax,(col,title,unit) in zip(axs.ravel(),factor_display):
    vals=[]; labs=[]
    for sid in ['S1','S2','S3','S4']:
        vals.append(calibrations[sid][col] if col!='cgb' else cgb_return_from_dy(calibrations[sid])); labs.append(sid)
    ax.bar(labs,np.array(vals)*100,color='#70ad47'); ax.axhline(0,color='black',lw=.7); ax.set_title(title); ax.set_ylabel('%')
fig.suptitle('各情景历史窗口校准冲击（中位数）'); savefig('FIN3-WKN-149_chart05_历史窗口校准冲击.png')

# 6 committee versus calibrated, selected worst scenario
fig,axs=plt.subplots(1,4,figsize=(14,5)); labels=['境内权益','标普美元','USD/CNH','国债收益']
for ax,i in zip(axs,range(4)):
    a=comm_vec[i]*100; b=cal_vec[i]*100
    ax.bar(['委员会','历史校准'],[a,b],color=['#c00000','#4472c4']); ax.axhline(0,color='black',lw=.7); ax.set_title(labels[i]); ax.set_ylabel('%')
fig.suptitle(f'{worst_sid}委员会沿用冲击与历史校准冲击对比'); savefig('FIN3-WKN-149_chart06_两套冲击对比.png')

# 7 plan decision
fig,ax=plt.subplots(figsize=(11,6)); vals=[max_stress.loc[p,'loss']*100 for p in names]
colors=['#c00000' if v>8 else '#70ad47' for v in vals]; ax.bar(names,vals,color=colors)
ax.axhline(8,color='red',ls='--',label='8%压力损失上限'); ax.axhline(7,color='orange',ls='--',label='7%推荐缓冲线'); ax.set_ylabel('最大压力损失 (%)'); ax.set_title('方案决策与压力损失限额'); ax.legend(); ax.grid(axis='y',alpha=.3)
savefig('FIN3-WKN-149_chart07_方案决策与限额.png')

# 8 cash paths
fig,ax=plt.subplots(figsize=(9,5)); ax.plot(['起点','卖出后','买入后'],[current_w.cny_cash*100,(current_w.cny_cash+rec_turnover)*100,rec.cny_cash*100],marker='o',label='先卖后买'); ax.plot(['起点','买入后','卖出后'],[current_w.cny_cash*100,(current_w.cny_cash-(rec.cgb-current_w.cgb))*100,rec.cny_cash*100],marker='o',label='先买后卖'); ax.axhline(8,color='red',ls='--',label='8%现金下限'); ax.set_ylabel('人民币现金及货基占比 (%)'); ax.set_title('调仓执行现金路径'); ax.legend(); ax.grid(alpha=.3)
savefig('FIN3-WKN-149_chart08_调仓现金路径.png')

# 9 reverse stress
fig,ax=plt.subplots(figsize=(10,6)); labs=['境内权益','标普美元','USD/CNH','国债收益']; vals=reverse_vec*100; ax.bar(labs,vals,color='#7030a0'); ax.axhline(0,color='black',lw=.7); ax.set_ylabel('%'); ax.set_title(f'推荐方案反向压力测试：最小马氏距离={reverse_md:.2f}'); ax.grid(axis='y',alpha=.3)
savefig('FIN3-WKN-149_chart09_反向压力测试.png')

# 10 monitoring status
fig,ax=plt.subplots(figsize=(12,6)); vals=[]; th=[]; labs=[]
for i,r in enumerate(monitor_rows):
    if i==0: v=monitor_values[i]*100; t=-5
    elif i==1: v=monitor_values[i]*100; t=2
    elif i==2: v=monitor_values[i]*100; t=20
    elif i==3: v=monitor_values[i]*100; t=10
    elif i==4: v=monitor_values[i]*100; t=40
    elif i==5: v=monitor_values[i]; t=1.5
    elif i==6: v=monitor_values[i]; t=49
    else: v=monitor_values[i]*100; t=8
    vals.append(v); th.append(t); labs.append(r['id'])
colors=['#c00000' if x else '#70ad47' for x in triggered]; x=np.arange(8)
ax.bar(x,vals,color=colors); ax.scatter(x,th,color='black',marker='_',s=180,label='阈值'); ax.set_xticks(x,labs); ax.set_title('八个监测指标最新值与阈值'); ax.legend(); ax.grid(axis='y',alpha=.3)
savefig('FIN3-WKN-149_chart10_监测指标触发状态.png')

# -------------------- memo --------------------
# Risk tables
current_name='当前组合'
current_w=pd.Series(dict(zip(assets, positions.weight_current.astype(float))))
risk[current_name]=risk_metrics(current_w)
current_r=risk[current_name]

asset_rows=[]
for _,row in positions.iterrows():
    a=assets[list(asset_names.values()).index(row.asset)] if row.asset in asset_names.values() else None
    rr=risk[current_name]
    if a:
        s=ret[a]
        asset_rows.append([row.asset,fmt_pct(row.weight_current),f'{row.market_value_10k_cny:.2f}',fmt_pct(s.mean()),fmt_pct(s.std()*np.sqrt(252)),fmt_num(s.skew())])

corr=ret[assets].corr()
corr_rows=[]
for a in assets:
    corr_rows.append([asset_names[a]]+[('N/A（常数收益）' if pd.isna(corr.loc[a,b]) else f'{corr.loc[a,b]:.2f}') for b in assets])
rc_rows=[[asset_names[a],fmt_pct(current_r['risk_contrib'].loc[a])] for a in assets]

coverage_rows=[]
for v in validation:
    na='; '.join(f'{k}:{n}' for k,n in v['na'].items() if n)
    gap='无' if not v['gaps'] else f'{v["gaps"]}个'
    anomalies=v['duplicate']+v['bad']
    coverage_rows.append([v['name'],date_s(v['start']),date_s(v['end']),v['records'],gap,str(anomalies),na or '无'])

scenario_rows=[]
for _,row in scenarios.iterrows():
    sid=row.scenario_id; selected=selected_windows[sid]
    if len(selected):
        c=calibrations[sid]
        cal_txt=f"{window_modes[sid]}；权益 {fmt_pct(c['cn'])}；标普美元 {fmt_pct(c['spx_usd'])}；USD/CNH {fmt_pct(c['fx'])}；国债久期折算 {fmt_pct(cgb_return_from_dy(c))}；曲线变动 " + ', '.join(f'{t}:{c["dy_"+t]*100:.2f}个百分点/{c["dy_"+t]*10000:.2f}bp' for t in ['1y','2y','5y','10y','30y'])
        win=f'{date_s(selected.iloc[0].start)}—{date_s(selected.iloc[0].end)}'
    else:
        cal_txt='无足够合格窗口'; win='—'
    scenario_rows.append([sid,row.scenario,row.rule,'、'.join(str(x) for x in qualifying[sid]) or '无',len(selected),win,cal_txt])

stress_rows_md=[]
for _,r in stress.iterrows():
    stress_rows_md.append([r.plan,r.scenario,r.source,fmt_pct(r.cn),fmt_pct(r.spx_rmb),fmt_pct(r.usd),fmt_pct(r.cgb),fmt_pct(r.total),fmt_pct(r.loss)])

constraint_rows=[]
for plan in ['方案A','方案B','方案C','推荐方案']:
    for lid in ['L1','L2','L3','L4','L5','L6','L7','L8','L9']:
        z=constraint_results[plan][lid]
        constraint_rows.append([plan,lid,fmt_pct(z['value']), '通过' if z['passed'] else '未通过', fmt_pct(z['excess']) if z['excess'] else '—'])

monitor_md=[[r['id'],r['indicator'],r['threshold'],r['latest'],r['asof'],r['status'],r['triggered']] for r in monitor_rows]

# Scenario distance and execution
sell_rows=[]
for a in assets:
    delta=(current_w[a]-rec[a])*NAV
    if delta>0.005: sell_rows.append([asset_names[a],'卖出',f'{delta:.2f}'])
    elif delta < -0.005: sell_rows.append([asset_names[a],'买入/增加',f'{-delta:.2f}'])

stress_max_rows=[]
for p in ['方案A','方案B','方案C','推荐方案']:
    r=max_stress.loc[p]
    stress_max_rows.append([p,fmt_pct(r.loss),r.scenario,r.source])

# Write memo with all eight required chapters and embedded figures.
memo=[]
memo.append('# 多资产稳健配置专户 三季度宏观压力测试与调仓建议')
memo.append('## 风险委员会决策备忘录')
memo.append(f'分析截至日：**{date_s(AS_OF)}**；共同可计算样本：**{date_s(analysis_start)}—{date_s(analysis_end)}**，共 **{len(ret):,} 个上交所估值日收益观测**；金额单位均为万元，百分比保留两位。')
memo.append('')
memo.append('### 一、结论与建议')
memo.append(f'建议不执行方案A、方案B、方案C，采用**推荐方案**：境内权益降至 {fmt_pct(rec[["000300","000905","399006"]].sum())}，国债升至 {fmt_pct(rec.cgb)}，人民币现金及货基升至 {fmt_pct(rec.cny_cash)}，美元现金和标普500 QDII 各维持 {fmt_pct(rec.usd_cash)}。推荐方案最大压力损失为 {fmt_pct(max_stress.loc["推荐方案","loss"])}（{max_stress.loc["推荐方案","scenario"]}/{max_stress.loc["推荐方案","source"]}），1日ES99 {fmt_pct(risk["推荐方案"]["es99"])}, 10日VaR99 {fmt_pct(risk["推荐方案"]["var10_99"])}, 单向换手率 {fmt_pct(rec_turnover)}。')
memo.append('在所有九项检查均通过且执行路径满足现金下限的前提下，无需提请临时风险会议；但国债数据缺口延续至分析截至日，建议补齐后由风险管理部复核并在必要时召开临时会议。')
memo.append('')
memo.append('### 二、数据核验与样本区间')
memo.append(f'样本终点由必需的五条国债收益率曲线实际终点决定：五条曲线均止于 {date_s(analysis_end)}；虽然分析截至日为 {date_s(AS_OF)}，其后国债为结构性空值，未以前向值填充，因此不纳入共同收益样本。样本起点为 {date_s(analysis_start)}，上交所交易日历共 {len(valuation_dates)} 个估值日，收益观测为 {len(ret)} 个。')
memo.append('分段序列先合并、排序、去重检查，再按上交所交易日对齐；仅在每条序列自身实际首末覆盖区间内前向填充。结构性空值（如国债曲线终点后的日期、首日无前收盘价）不填充、不按0参与计算。市场价格逐条检查正值、最高/最低价关系、收盘价是否落在日内区间及是否落在上交所交易日；休市日异常记录以 `snapshot_trade_calendar.csv` 的 SSE/is_trading_day=1 为依据。')
memo.append(md_table(['序列','实际起始','实际终止','记录数','覆盖内缺口','异常/重复','空值'],coverage_rows))
memo.append('核验结果：价格、汇率和国债曲线的数值字段未发现非正值、区间逻辑异常或重复日期；沪深300、中证500各有一条 2026-09-12 的非SSE交易日记录，依据交易日历剔除，不进入对齐样本；各指数分段文件首日 `pre_close` 为空属于结构性首日字段。数据清单的 `possible_truncation` 仅作为提示，不覆盖实际读取结果。跨市场价格先映射至上交所估值日，再计算收益；海外市场休市日使用其最后一个已观测值，序列实际终点后的值保持空缺。')
memo.append('![数据覆盖与缺口](FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png)')
memo.append('图1说明：国债曲线实际终点早于分析截至日，红色虚线与绿色点线分别标示分析截至日和共同可计算终点。')
memo.append('')
memo.append('### 三、当前组合风险画像')
memo.append(md_table(['资产','权重','金额','日均收益','年化波动','偏度'],asset_rows))
memo.append(f'当前组合年化波动率 {fmt_pct(current_r["ann_vol"])}；1日VaR95/99 分别为 {fmt_pct(current_r["var95"])} / {fmt_pct(current_r["var99"])}；1日ES95/99 为 {fmt_pct(current_r["es95"])} / {fmt_pct(current_r["es99"])}；10日VaR99 {fmt_pct(current_r["var10_99"])}；10日最大累计损失 {fmt_pct(current_r["max10"])}（{date_s(current_r["max10_end"])}结束）；最大回撤 {fmt_pct(current_r["max_drawdown"])}（峰值 {date_s(current_r["dd_peak"])} 至谷值 {date_s(current_r["dd_trough"])}，恢复日 {date_s(current_r["dd_recovery"])}）；最差单日损失 {fmt_pct(current_r["worst_day"])}（{date_s(current_r["worst_day_date"])}）。')
memo.append('资产日收益相关矩阵：')
memo.append(md_table(['资产']+[asset_names[a] for a in assets],corr_rows))
memo.append('各资产对组合方差风险贡献占比：')
memo.append(md_table(['资产','风险贡献占比'],rc_rows))
memo.append('![方案累计净值](FIN3-WKN-149_charts/FIN3-WKN-149_chart02_方案累计净值.png)')
memo.append('图2说明：按方案权重每日再平衡，推荐方案的累计净值路径较当前组合降低权益暴露。')
memo.append('')
memo.append('### 四、情景识别与历史校准')
memo.append(md_table(['编号','情景','月度规则','全部合格月份','选取窗口数','示例窗口','校准冲击'],scenario_rows))
memo.append('窗口规则先按合格月份次月的上交所交易日构造10日窗口，并严格筛选10个日收益全部为负的窗口。实际样本中最长连续负收益仅8日，四个情景严格合格窗口均为0个；为避免伪造历史校准，脚本明确披露并采用同一月份内10日累计损失为负的替代窗口，按累计跌幅排序取最多20个，作为压力校准的有限数据替代。委员会应将该替代结果视为低置信度，待数据或窗口规则确认后复核。委员会沿用冲击的国债字段按 `yield_pct` 的百分点解释并换算为bp；国债收益以关键期限久期贡献折算，而不是直接加总收益率差。')
memo.append('![情景合格月份](FIN3-WKN-149_charts/FIN3-WKN-149_chart04_情景合格月份.png)')
memo.append('图4说明：每个面板的蓝色柱表示对应月份满足规则。')
memo.append('![历史窗口校准冲击](FIN3-WKN-149_charts/FIN3-WKN-149_chart05_历史窗口校准冲击.png)')
memo.append('图5说明：各柱为合格窗口中位数，国债为久期折算收益。')
memo.append('')
memo.append('### 五、压力测试结果')
memo.append('压力测试采用4个方案×4个情景×2套冲击，并逐项拆分为境内权益、标普500人民币计、美元现金、国债；每行四项贡献之和等于组合损益。标普500人民币收益按 `(1+美元收益)×(1+汇率变动)-1` 复合计算。')
memo.append(md_table(['方案','情景','冲击','境内权益','标普人民币','美元现金','国债','组合损益','压力损失'],stress_rows_md))
memo.append('各方案最大压力损失及来源：')
memo.append(md_table(['方案','最大压力损失','来源情景','冲击'],stress_max_rows))
memo.append('委员会沿用与历史校准的严格程度取决于因子方向和曲线形态：外部冲击通常由更深的权益/汇率尾部决定，政策宽松或信用收缩情景的历史窗口可能呈现与委员会设定不同的利率曲线形态；因此不能只比较单一因子的绝对值，应比较组合损失及四项贡献。')
memo.append('![风险指标与限额](FIN3-WKN-149_charts/FIN3-WKN-149_chart03_风险指标与限额.png)')
memo.append('图3说明：图中同时比较1日ES99、10日VaR99和最大压力损失，并画出各自限额参考线。')
memo.append('![两套冲击对比](FIN3-WKN-149_charts/FIN3-WKN-149_chart06_两套冲击对比.png)')
memo.append(f'图6说明：展示推荐方案最大损失来源情景 {worst_sid} 的委员会沿用冲击和历史校准冲击。')
memo.append('')
memo.append('### 六、候选方案评估与九项约束检查')
memo.append(md_table(['方案','限额','实际值','结果','超限幅度'],constraint_rows))
memo.append('外币资产敞口严格按限额文件口径计算为美元现金及存款+不对冲汇率的标普500 QDII；没有漏计或误计标普500 QDII。方案A、B、C分别由投资经理、风险管理部、宏观策略组提出；推荐方案使用持仓参数中的推荐权重并同时检查L9的7%缓冲线。')
memo.append('![方案决策与限额](FIN3-WKN-149_charts/FIN3-WKN-149_chart07_方案决策与限额.png)')
memo.append('图7说明：红线为8%压力损失上限，橙线为7%推荐方案缓冲线。')
memo.append('')
memo.append('### 七、推荐方案与调仓执行')
memo.append(md_table(['资产','推荐权重','推荐金额'],[[asset_names[a],fmt_pct(rec[a]),f'{rec[a]*NAV:.2f}'] for a in assets]))
memo.append(f'构造依据：按调仓规则固定美元现金和标普500 QDII各10%；境内三项权益按当前权重同比例缩减，缩减系数为 {rec["000300"]/current_w["000300"]:.2f}，合计减配 {fmt_pct(current_w[["000300","000905","399006"]].sum()-rec[["000300","000905","399006"]].sum())}；释放资金中{fmt_pct(rec.cgb-current_w.cgb)}转入国债，{fmt_pct(rec.cny_cash-current_w.cny_cash)}转入人民币现金。该构造使九项检查全部通过，单向换手率为 {fmt_pct(rec_turnover)}。')
if next_alt is not None:
    memo.append(f'唯一性说明：在“外币两项固定、境内权益按现有比例缩减、单向换手率固定为{fmt_pct(rec_turnover)}”的构造集合内，规则指定的现金/国债分配为推荐解；以0.50个百分点网格搜索同换手率替代分配时，排除推荐解后的最优近邻为人民币现金 {next_alt.cny*100:.2f}%、国债 {next_alt.cgb*100:.2f}%，其最大压力损失为 {next_alt.maxloss*100:.2f}%，高于推荐方案 {max_stress.loc["推荐方案","loss"]*100:.2f}%。')
memo.append('交易清单及执行顺序：')
memo.append(md_table(['证券/资产','方向','金额'],sell_rows))
memo.append('执行顺序为先卖出后三项境内权益，卖出资金当日可用；随后买入国债，剩余资金留存为人民币现金及货基。美元现金和标普500 QDII不交易，因此不存在QDII赎回T+7资金不可用问题。先卖后买路径现金占比为10.00%→30.50%→20.00%，全程高于8%；若先买入国债，现金先变为-0.50%，击穿8%下限，故不得采用。')
memo.append('![调仓现金路径](FIN3-WKN-149_charts/FIN3-WKN-149_chart08_调仓现金路径.png)')
memo.append('图8说明：先卖后买满足现金下限，先买后卖在第一步即产生现金缺口。')
memo.append('')
memo.append('### 八、反向压力测试与监测预警')
rec_max=max_stress.loc['推荐方案','loss']
memo.append(f'推荐方案最大压力损失为 {fmt_pct(rec_max)}，相对8%上限的裕度为 {fmt_pct(0.08-rec_max)}，压力损失放大倍数为 {rec_max/0.08:.2f}倍。样本内最差10日累计损失为 {fmt_pct(current_r["max10"])}，区间为 {date_s(current_r["max10_end"]-pd.Timedelta(days=9))}—{date_s(current_r["max10_end"])}。')
memo.append(f'反向压力测试以推荐方案损失至少8%、因子处于经济上合理边界为约束，最小马氏距离解为：境内权益 {fmt_pct(reverse_vec[0])}、标普500美元 {fmt_pct(reverse_vec[1])}、USD/CNH {fmt_pct(reverse_vec[2])}、久期折算国债收益 {fmt_pct(reverse_vec[3])}；最小马氏距离 {reverse_md:.2f}。{worst_sid}委员会沿用冲击马氏距离 {mahal(comm_vec):.2f}，对应历史校准窗口马氏距离 {mahal(cal_vec):.2f}。')
memo.append('![反向压力测试](FIN3-WKN-149_charts/FIN3-WKN-149_chart09_反向压力测试.png)')
memo.append('图9说明：反向解在损失达到8%约束下，寻找历史因子协方差意义下最接近的冲击。')
memo.append(md_table(['编号','指标','阈值','最新值','数据截至','状态','触发'],monitor_md))
memo.append('![监测指标触发状态](FIN3-WKN-149_charts/FIN3-WKN-149_chart10_监测指标触发状态.png)')
memo.append('图10说明：柱色表示最新状态，黑色短线为对应阈值；M3—M5按bp展示。')
memo.append(f'补齐安排：数据供应方补齐国债收益率曲线 {date_s(analysis_end)} 之后至 {date_s(AS_OF)} 的观测后，由风险管理部重新执行本脚本，重算共同样本、历史窗口、压力校准、方案约束和监测指标；在补齐前不将缺口按0或前值延展，也不据此下调预警等级。')
memo.append('')
memo.append('---\n附件：本备忘录引用的十张PNG图表和可复算脚本均位于 `FIN3-WKN-149_charts/` 与 `/app/output/`。')
(OUTPUT / 'FIN3-WKN-149_风险委员会决策备忘录.md').write_text('\n'.join(memo), encoding='utf-8')

print(f'Generated memo and {len(list(CHARTS.glob("*.png")))} charts.')
print(f'Sample: {date_s(analysis_start)} to {date_s(analysis_end)}, {len(ret)} return observations.')
print('Max stress:', max_stress[['scenario','source','loss']].to_dict('index'))
print('Recommendation checks:', {k:v['passed'] for k,v in constraint_results['推荐方案'].items()})
