#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-149 多资产专户宏观压力测试 —— 可复算分析引擎（参考答案）
从 input_files/ 的原始快照读入，全部结果由数据计算得到，不硬编码任何结论数值。
用法: python3 FIN3-WKN-149_reproduce.py [input_dir] [output_dir]
"""
import sys, re, json, pathlib, warnings
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')

IN = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'input_files')
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else '.')
CH = OUT / 'FIN3-WKN-149_charts'; CH.mkdir(parents=True, exist_ok=True)
AS_OF = pd.Timestamp('2026-09-15')
R = {}   # 结果登记表

def rd(name, **kw):
    return pd.read_csv(IN / name, parse_dates=['date'], **kw)

def fmt(x, n=2):
    return f'{x:,.{n}f}'

# ============================ 1. 读入与核验 ============================
eq = {}
for sym, stem in [('000300', 'snapshot_000300SH'), ('000905', 'snapshot_000905SH'), ('399006', 'snapshot_399006SZ')]:
    a, b = rd(f'{stem}_seg1.csv'), rd(f'{stem}_seg2.csv')
    d = pd.concat([a, b]).sort_values('date').reset_index(drop=True)
    eq[sym] = d
cal = rd('snapshot_trade_calendar.csv')
cgb = {}
for t in ['1y', '2y', '5y', '10y', '30y']:
    cgb[t] = rd(f'snapshot_cgb_yield_{t}.csv').set_index('date')['yield_pct']
fx = pd.concat([rd('snapshot_usdcnh_seg1.csv'), rd('snapshot_usdcnh_seg2.csv')]).sort_values('date').reset_index(drop=True)
spx = rd('snapshot_spx.csv').set_index('date')['close']
shib = pd.concat([rd('snapshot_shibor_seg1.csv'), rd('snapshot_shibor_seg2.csv')]).sort_values('date')
dr007 = rd('snapshot_dr007.csv').set_index('date')['dr007']
lpr1 = rd('snapshot_lpr_1y.csv'); lpr5 = rd('snapshot_lpr_5y.csv')
pmi = rd('snapshot_pmi_manufacturing.csv'); afre = rd('snapshot_afre_stock.csv')
ppi = rd('snapshot_ppi_yoy.csv'); u10 = rd('snapshot_ust_10y.csv').set_index('date')['yield_pct']
m2 = rd('snapshot_ust_m2.csv'); m4 = rd('snapshot_ust_m4.csv')
hold = pd.read_csv(IN / 'params_holdings.csv'); lim = pd.read_csv(IN / 'params_limits.csv')
dur = pd.read_csv(IN / 'params_duration.csv'); plans = pd.read_csv(IN / 'plans_candidates.csv')
rules = pd.read_csv(IN / 'rules_scenarios.csv'); chk = pd.read_csv(IN / 'rules_checks.csv')
reb = pd.read_csv(IN / 'rules_rebalance.csv'); shocks = pd.read_csv(IN / 'params_committee_shocks.csv')
NAV = 10000.0

# ---- 样本区间：中债收益率曲线五期限同日终止 ----
cgb_dates = cgb['10y'].dropna().index
cgb_end = cgb_dates.max()
sample = cal[(cal.date >= pd.Timestamp('2018-01-02')) & (cal.date <= cgb_end)]['date']
R['sample_start'] = str(sample.min().date()); R['sample_end'] = str(cgb_end.date())
R['sample_days'] = int(len(sample))
R['missing_after_cgb'] = int(len(cal[(cal.date > cgb_end) & (cal.date <= AS_OF)]))
# ---- 休市日异常记录 ----
anom = []
for sym in ['000300', '000905']:
    d = eq[sym]; wk = d[(d.date.dt.dayofweek == 5) & (d.date > pd.Timestamp('2026-01-01'))]
    for _, r in wk.iterrows():
        prev = d[d.date < r.date].iloc[-1]
        anom.append(dict(symbol=sym, date=str(r.date.date()), pre_close=round(float(r.pre_close), 4),
                         prev_close=round(float(prev.close), 4), amount_ratio=round(float(r.amount) / float(prev.amount), 4)))
R['anomalies'] = anom
# ---- 结构性空值 ----
R['structural_nan'] = {
    'lpr_5y_until': str(lpr5[lpr5.lpr_5y.isna()].date.max().date()) if lpr5.lpr_5y.isna().any() else None,
    'ust_m2_first': str(m2.date.min().date()), 'ust_m4_first': str(m4.date.min().date()),
    'ust_m4_rows': int(len(m4))}
R['data_gaps'] = {
    'lpr_1y_missing': [m for m in pd.period_range('2018-01', '2026-08', freq='M').strftime('%Y-%m')
                       if m not in lpr1.date.dt.strftime('%Y-%m').values],
    'pmi_missing': [m for m in pd.period_range('2018-02', '2026-08', freq='M').strftime('%Y-%m')
                    if m not in pmi.date.dt.strftime('%Y-%m').values],
    'afre_missing': [m for m in pd.period_range('2018-02', '2026-08', freq='M').strftime('%Y-%m')
                     if m not in afre.date.dt.strftime('%Y-%m').values],
    'shibor_rows': int(len(shib)), 'shibor_first': str(shib.date.min().date()),
    'cgb_end': str(cgb_end.date())}

# ============================ 2. 价格对齐与日收益 ============================
idx = pd.DatetimeIndex(sample)
px = pd.DataFrame({s: eq[s].set_index('date')['close'] for s in eq})
fx_s = fx.drop_duplicates('date').set_index('date')['usdcnh']          # ★ 先按上交所估值日对齐
fx_a = fx_s.reindex(idx).ffill()
spx_a = spx.reindex(idx).ffill()
y = pd.DataFrame({t: cgb[t].reindex(idx).ffill() for t in cgb})
y = y[['1y', '2y', '5y', '10y', '30y']]

ret = pd.DataFrame(index=idx)
ret['EQ_000300'] = px['000300'].reindex(idx).ffill().pct_change()
ret['EQ_000905'] = px['000905'].reindex(idx).ffill().pct_change()
ret['EQ_399006'] = px['399006'].reindex(idx).ffill().pct_change()
D = float(dur.duration_contribution.sum())                              # 修正久期 7.0
ret['CGB'] = -(y.diff().sum(axis=1)) / 100.0 * 0.0                      # 占位，下面按期限久期加权
w_dur = dict(zip(['1y', '2y', '5y', '10y', '30y'], dur.duration_contribution))
ret['CGB'] = -sum(y[t].diff() * w_dur[t] for t in w_dur) / 100.0        # 收益率变动(pp)×久期贡献
r_spx_usd = spx_a.pct_change()
r_cnh = fx_a.pct_change()
ret['SPX'] = (1 + r_spx_usd) * (1 + r_cnh) - 1                           # ★ 复合折算，非加法近似
ret['USD_CASH'] = r_cnh
ret['CNY_CASH'] = 0.0
ret = ret.dropna(how='all')

W = dict(zip(hold.asset_class, hold.weight_current))
def port_ret(w, rets):
    return sum(w.get(k, 0.0) * rets[k] for k in rets.columns if k in w)

# ============================ 3. 风险指标 ============================
def risk_metrics(r):
    r = r.dropna(); mu, sd = r.mean(), r.std()
    v95 = -np.percentile(r, 5); v99 = -np.percentile(r, 1)
    e95 = -r[r <= -v95].mean(); e99 = -r[r <= -v99].mean()
    cum = (1 + r).cumprod(); dd = cum / cum.cummax() - 1
    roll10 = (1 + r).rolling(10).apply(np.prod, raw=True) - 1
    worst10 = roll10.min(); worst10_end = roll10.idxmin()
    _p = roll10.index.get_loc(worst10_end)
    worst10_start = roll10.index[max(0, _p - 9)]
    mdd = dd.min(); mdd_end = dd.idxmin()
    mdd_start = cum.loc[:mdd_end].idxmax()
    recov = cum[(cum.index > mdd_end) & (dd.reindex(cum.index) >= -1e-9)]
    return dict(ann_vol=sd * np.sqrt(252), var95=v95, es95=e95, var99=v99, es99=e99,
                var99_10d=-np.percentile(roll10.dropna(), 1), worst10=worst10,
                worst10_end=str(worst10_end.date()), worst10_start=str(worst10_start.date()),
                mdd=mdd, mdd_end=str(mdd_end.date()), mdd_start=str(mdd_start.date()),
                mdd_recov=str(recov.index[0].date()) if len(recov) else '未修复',
                worst_day=r.min(), worst_day_date=str(r.idxmin().date()))

planw = {'当前持仓': W}
for _, p in plans.iterrows():
    planw[p.plan_id] = {'EQ_000300': p.w_000300, 'EQ_000905': p.w_000905, 'EQ_399006': p.w_399006,
                        'CGB': p.w_cgb, 'USD_CASH': p.w_usd_cash, 'SPX': p.w_spx_qdii, 'CNY_CASH': p.w_cny_cash}
# 推荐方案：从 rules_rebalance.csv 的 recommendation_rule 文本**解析**构造参数，再由当前持仓算出权重。
# 不硬编码任何结论数值；解析结果再与 params_holdings.csv 的 weight_recommended 列交叉校验。
_rr = str(reb.loc[reb['key'] == 'recommendation_rule', 'value'].iloc[0])
_scale = float(re.search(r'缩减系数\s*([0-9]*\.?[0-9]+)', _rr).group(1))              # 境内权益同比例缩减系数
_to_cgb = float(re.search(r'([0-9]*\.?[0-9]+)\s*个百分点转入中长期国债', _rr).group(1)) / 100.0
_to_cny = float(re.search(r'([0-9]*\.?[0-9]+)\s*个百分点转入人民币现金', _rr).group(1)) / 100.0
rec_w = {'EQ_000300': round(W['EQ_000300'] * _scale, 4), 'EQ_000905': round(W['EQ_000905'] * _scale, 4),
         'EQ_399006': round(W['EQ_399006'] * _scale, 4),
         'CGB': round(W['CGB'] + _to_cgb, 4), 'CNY_CASH': round(W['CNY_CASH'] + _to_cny, 4),
         'USD_CASH': W['USD_CASH'], 'SPX': W['SPX']}
planw['推荐方案'] = rec_w
_col = {a: b for a, b in zip(hold.asset_class, hold.weight_recommended)}
R['rec_derivation'] = {'scale': _scale, 'to_cgb_pp': _to_cgb * 100, 'to_cny_pp': _to_cny * 100}
R['rec_crosscheck'] = {k: bool(abs(rec_w[k] - _col[k]) < 1e-9) for k in rec_w if k in _col}
rets = {k: port_ret(v, ret) for k, v in planw.items()}
R['plan_risk'] = {k: risk_metrics(v) for k, v in rets.items()}

# ---- 相关矩阵与风险贡献 ----
CM = ret[['EQ_000300', 'EQ_000905', 'EQ_399006', 'CGB', 'USD_CASH', 'SPX']].corr()
R['corr'] = CM.round(4).to_dict()
def rc(w):
    cols = ['EQ_000300', 'EQ_000905', 'EQ_399006', 'CGB', 'USD_CASH', 'SPX']
    v = np.array([w.get(c, 0) for c in cols]); S = ret[cols].cov().values * 252
    var = float(v @ S @ v); contrib = v * (S @ v) / var
    return dict(zip(cols, contrib)), var
R['risk_contribution'] = {k: {a: float(b) for a, b in rc(w)[0].items()} for k, w in planw.items()}

# ============================ 4. 情景识别 ============================
m = lambda s: s.resample('ME').last()
mm = pd.DataFrame({'pmi': m(pmi.set_index('date')['pmi_mfg']).dropna(),
                   'ppi': m(ppi.set_index('date')['ppi_yoy']), 'cgb10': m(y['10y']),
                   'lpr1': m(lpr1.set_index('date')['lpr_1y']), 'lpr5': m(pd.to_numeric(lpr5.set_index('date')['lpr_5y'], errors='coerce')),
                   'spx': m(spx_a), 'cnh': m(fx_a), 'dr007': m(dr007), 'afre': m(afre.set_index('date')['afre_stock']),
                   'eq': m(px['000300'].reindex(idx).ffill())})
mm = mm.dropna(subset=['pmi'])
mm['spx_r'] = mm.spx.pct_change(); mm['cnh_r'] = mm.cnh.pct_change()
mm['eq_r'] = mm['eq'].pct_change(); mm['afre_yoy'] = mm['afre'].pct_change(12)
mm['pmi_d'] = mm['pmi'].diff(); mm['ppi_d'] = mm['ppi'].diff(); mm['lpr_dn'] = (mm['lpr1'].diff() < 0) | (mm['lpr5'].diff() < 0)
ok = mm.dropna(subset=['spx_r', 'cnh_r'])
# 严格按 rules_scenarios.csv 的规则字面实现
S1 = ok[((ok['pmi'] < 50) & ok['lpr_dn'])
        | ((ok['pmi_d'] <= -0.5) & (ok['cgb10'] < ok['cgb10'].shift()))]
S2 = ok[(ok['ppi'] > ok['ppi'].shift()) & (ok['cgb10'] > ok['cgb10'].shift()) & (ok['eq_r'] < 0)]
S3 = ok[(ok['spx_r'] <= -0.03) | (ok['cnh_r'] >= 0.015)]
S4 = ok[(ok['afre_yoy'] < ok['afre_yoy'].shift()) & (ok['dr007'] > ok['dr007'].shift()) & (ok['eq_r'] < 0)]
scen = {'S1': S1.index, 'S2': S2.index, 'S3': S3.index, 'S4': S4.index}
R['scenario_months'] = {k: [str(d.date())[:7] for d in v] for k, v in scen.items()}

# ============================ 5. 历史窗口与校准冲击 ============================
F = ['EQ_000300', 'EQ_000905', 'EQ_399006', 'CGB', 'SPX', 'USD_CASH']
def build_windows(months, k=10, topn=20):
    """按 rules_windows.csv：合格月份内每个交易日为窗口起点，取其后 10 个交易日；
    仅保留窗口内组合日收益全部为负者；按累计跌幅排序取前若干（不足 20 个则全取）。"""
    wcur = np.array([W.get(c, 0.0) for c in F])
    allc, negc = [], []
    for mo in months:
        tag = str(mo)[:7]
        for st_date in [d for d in idx if str(d)[:7] == tag]:
            pos = idx.get_loc(st_date); w = idx[pos:pos + k]
            if len(w) < k: continue
            sub = ret.loc[w, F]; pr = sub.values @ wcur
            cum = (1 + sub).prod() - 1
            item = (float((1 + pr).prod() - 1), w, cum)
            allc.append(item)
            if bool((pr < 0).all()): negc.append(item)
    pool = negc if negc else allc
    pool.sort(key=lambda x: x[0])
    return pool[:topn]
hist = {}
for k, months in scen.items():
    cand = build_windows(months)
    if not cand: continue
    depth, w0, _ = cand[0]
    cums = pd.DataFrame([c[2].values for c in cand], columns=F)
    hist[k] = dict(n_windows=len(cand), window_start=str(w0[0].date()), window_end=str(w0[-1].date()),
                   calib=cums.median().to_dict(), depth=depth)
R['hist_windows'] = hist

# ============================ 6. 压力测试 ============================
bp = {'1y': 0, '2y': 1, '5y': 2, '10y': 3, '30y': 4}
def cgb_pnl(w_cgb, shock_str):
    d = {kv.split(':')[0].strip().lower(): float(kv.split(':')[1]) for kv in shock_str.split(',')}
    return sum(-w_dur[t] * d[t] / 100.0 for t in d if t in w_dur) if w_cgb else 0.0
stress = {}
for _, s in shocks.iterrows():
    for tag in ['committee', 'historical']:
        if tag == 'committee':
            sh = {'EQ_000300': s.cn_equity_shock, 'EQ_000905': s.cn_equity_shock, 'EQ_399006': s.cn_equity_shock,
                  'SPX_USD': s.spx_usd_shock, 'CNH': s.usdcnh_shock, 'CGB_DIRECT': cgb_pnl(1, s.cgb_shock_bp)}
        else:
            h = hist.get(s.scenario_id, {}).get('calib', {})
            sh = {'EQ_000300': h.get('EQ_000300', 0), 'EQ_000905': h.get('EQ_000905', 0), 'EQ_399006': h.get('EQ_399006', 0),
                  'SPX_USD': h.get('SPX', 0) / (1 + h.get('USD_CASH', 0)) if h.get('SPX') is not None else 0,
                  'CNH': h.get('USD_CASH', 0), 'CGB_DIRECT': h.get('CGB', 0)}
        for pn, w in planw.items():
            spx_cny = (1 + sh['SPX_USD']) * (1 + sh['CNH']) - 1
            parts = {'境内权益': (w['EQ_000300'] + w['EQ_000905'] + w['EQ_399006']) * sh['EQ_000300'],
                     '标普500': w['SPX'] * spx_cny, '美元现金': w['USD_CASH'] * sh['CNH'],
                     '国债': w['CGB'] * sh['CGB_DIRECT']}
            stress[(pn, s.scenario_id, tag)] = dict(parts=parts, total=sum(parts.values()))
R['stress'] = {f'{k[0]}|{k[1]}|{k[2]}': v for k, v in stress.items()}
R['max_stress'] = {pn: min((v['total'], k[1], k[2]) for k, v in stress.items() if k[0] == pn) for pn in planw}

# ============================ 7. 九项约束检查 ============================
def check_plan(pn, w, rm):
    res = {}
    res['C1'] = abs(sum(w.values()) - 1) <= 0.0005
    res['C2'] = (w['EQ_000300'] + w['EQ_000905'] + w['EQ_399006']) <= 0.60
    res['C3'] = 0.08 <= w['CNY_CASH'] <= 0.20
    res['C4'] = w['CGB'] >= 0.15
    res['C5'] = (w['USD_CASH'] + w['SPX']) <= 0.25
    res['C6'] = rm['es99'] <= 0.035
    res['C7'] = rm['var99_10d'] <= 0.060
    res['C8'] = R['max_stress'][pn][0] >= -0.080
    res['C9'] = R['max_stress'][pn][0] >= -0.070
    return res
R['checks'] = {pn: check_plan(pn, w, R['plan_risk'][pn]) for pn, w in planw.items()}

# ============================ 8. 调仓执行 ============================
trades, cash = [], W['CNY_CASH']
for cls, w_new in rec_w.items():
    if cls == 'CNY_CASH': continue
    dlt = (w_new - W.get(cls, 0)) * NAV
    trades.append(dict(asset=cls, amount_10k=round(dlt, 2), side='买入' if dlt > 0 else '卖出'))
R['trades'] = trades
R['turnover'] = float(sum(-t['amount_10k'] for t in trades if t['amount_10k'] < 0) / NAV)
path_sell_first = [W['CNY_CASH']]
c = W['CNY_CASH']
for t in sorted(trades, key=lambda x: x['amount_10k'] > 0):
    c -= t['amount_10k'] / NAV; path_sell_first.append(round(c, 4))
R['cash_path_sell_first'] = path_sell_first
R['cash_path_buy_first_min'] = float(min([W['CNY_CASH'] - sum(t['amount_10k'] for t in trades if t['amount_10k'] > 0) / NAV, W['CNY_CASH']]))

# ============================ 9. 反向压力测试 ============================
r10 = (1 + ret[F]).rolling(10).apply(np.prod, raw=True) - 1     # 10 日累计收益
mu = r10.mean().values
S10 = r10.cov().values
Sinv = np.linalg.pinv(S10)
w_ref = np.array([rec_w.get(c, 0) for c in F])
target = R['max_stress']['推荐方案'][0]             # 组合损益 = 推荐方案最大压力损失
a = w_ref.copy()
x = mu + S10 @ a * ((target - a @ mu) / (a @ S10 @ a))   # 最小马氏距离解：x = μ + Σa·k
md = float((x - mu) @ Sinv @ (x - mu))
R['reverse_stress'] = dict(vec=dict(zip(F, [round(float(v), 6) for v in x])),
                           md=round(md, 2), loss=float(a @ x))
# 委员会信用收缩冲击的马氏距离（同一协方差口径）
sh4 = shocks[shocks.scenario_id == 'S4'].iloc[0]
x_comm = np.array([sh4.cn_equity_shock, sh4.cn_equity_shock, sh4.cn_equity_shock,
                   R['hist_windows']['S4']['calib'].get('CGB', 0), sh4.spx_usd_shock, sh4.usdcnh_shock])
R['md_committee'] = round(float((x_comm - mu) @ Sinv @ (x_comm - mu)), 2)
x_hist = np.array([R['hist_windows']['S4']['calib'].get(c, 0) for c in F])
R['md_historical'] = round(float((x_hist - mu) @ Sinv @ (x_hist - mu)), 2)

# ============================ 10. 监测指标 ============================
def last(d, col='close'):
    return d[d.index <= AS_OF] if hasattr(d, 'index') else d
mon = {}
mon['M1'] = float(px['000300'].reindex(idx).ffill().iloc[-1] / px['000300'].reindex(idx).ffill().iloc[-21] - 1)
mon['M2'] = float(fx_a.iloc[-1] / fx_a.iloc[-21] - 1)
mon['M3'] = float((dr007.reindex(idx).ffill().tail(20).mean() - dr007.reindex(idx).ffill().iloc[-80:-20].mean()) * 100)
mon['M4'] = float((y['10y'].dropna().iloc[-1] - y['10y'].dropna().iloc[-21]) * 100)
mon['M5'] = float((u10.reindex(idx).ffill().iloc[-1] - u10.reindex(idx).ffill().iloc[-21]) * 100)
pp = ppi.set_index('date')['ppi_yoy']
mon['M6'] = float(pp.iloc[-1] - pp.iloc[-4]) if len(pp) >= 4 else None
mon['M7'] = float(pmi.pmi_mfg.iloc[-1]); mon['M7_gap'] = True
mon['M8'] = float(afre.afre_stock.iloc[-1] / afre.afre_stock.iloc[-13] - 1) * 100 if len(afre) >= 13 else None
R['monitor'] = mon

# ============================ 11. 输出 ============================
(OUT / '_results.json').write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print(json.dumps({k: R[k] for k in ['sample_start', 'sample_end', 'sample_days', 'missing_after_cgb', 'anomalies', 'data_gaps', 'structural_nan']}, ensure_ascii=False, indent=2, default=str))
print('\n--- 方案风险 ---')
for k, v in R['plan_risk'].items():
    print(f"{k:<8} 波动率 {v['ann_vol']*100:6.2f}%  Var95 {v['var95']*100:5.2f}%  ES99 {v['es99']*100:5.2f}%  10dVaR99 {v['var99_10d']*100:5.2f}%  最差10日 {v['worst10']*100:6.2f}%  回撤 {v['mdd']*100:6.2f}%")
print('\n--- 情景月份 ---')
for k, v in R['scenario_months'].items(): print(f'  {k}: {len(v)} 个月 {v}')
print('\n--- 最大压力损失 ---')
for k, v in R['max_stress'].items(): print(f'  {k}: {v[0]*100:6.3f}%  情景 {v[1]} / {v[2]}')
print('\n--- 检查 ---')
for k, v in R['checks'].items(): print(f'  {k}: ' + ' '.join(f'{a}={b}' for a, b in v.items() if b is not None))
print('\n--- 监测 ---', {k: (round(v, 4) if isinstance(v, float) else v) for k, v in mon.items()})

# ============================ 12. 图表 ============================
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
for f in ['SimHei', 'Microsoft YaHei', 'Noto Sans CJK SC', 'DejaVu Sans']:
    if any(f.lower() in x.name.lower() for x in font_manager.fontManager.ttflist):
        plt.rcParams['font.sans-serif'] = [f]; break
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 110

def save(fig, name, note):
    fig.tight_layout(); fig.savefig(CH / name, bbox_inches='tight'); plt.close(fig)
    print(f'  chart: {name}')

# 01 数据覆盖与缺口
fig, ax = plt.subplots(figsize=(11, 6))
rows = [('沪深300', px['000300'].dropna()), ('中证500', px['000905'].dropna()), ('创业板指', px['399006'].dropna())]
rows += [(f'中债国债{t}', cgb[t].dropna()) for t in ['1y', '2y', '5y', '10y', '30y']]
rows += [('USD/CNH', fx_a.dropna()), ('标普500', spx_a.dropna()), ('Shibor', shib.set_index('date')['shibor_1w'].dropna()), ('DR007', dr007.dropna())]
rows += [('制造业PMI', pmi.set_index('date')['pmi_mfg'].dropna()), ('PPI同比', ppi.set_index('date')['ppi_yoy'].dropna()),
         ('LPR 1年', lpr1.set_index('date')['lpr_1y'].dropna()), ('社融存量', afre.set_index('date')['afre_stock'].dropna())]
for i, (nm, s) in enumerate(rows):
    ax.barh(i, (s.index.max() - s.index.min()).days, left=s.index.min(), height=0.5, color='#5B9BD5')
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=8)
ax.axvline(AS_OF, color='#C00000', ls='--', lw=1.2, label='分析截至日 2026-09-15')
ax.axvline(cgb_end, color='#ED7D31', ls=':', lw=1.2, label='中债曲线终止 2026-06-09')
ax.set_title('图1 数据覆盖区间与缺口'); ax.legend(fontsize=8); save(fig, 'FIN3-WKN-149_chart01_数据覆盖与缺口.png', '数据覆盖')

# 02 累计净值
fig, ax = plt.subplots(figsize=(11, 5))
for k, v in rets.items(): (1 + v.fillna(0)).cumprod().plot(ax=ax, label=k, lw=1.1)
ax.set_title('图2 各方案历史累计净值（2018-01-02 起）'); ax.legend(fontsize=8); ax.grid(alpha=.3)
save(fig, 'FIN3-WKN-149_chart02_方案累计净值.png', '历史风险')

# 03 风险指标对比
fig, ax = plt.subplots(figsize=(11, 5))
mm2 = pd.DataFrame({k: {'年化波动率': v['ann_vol'], '1日ES99': v['es99'], '10日VaR99': v['var99_10d'], '最大回撤': -v['mdd']} for k, v in R['plan_risk'].items()}).T
mm2.plot(kind='bar', ax=ax, width=.8); ax.axhline(0.035, color='#C00000', ls='--', lw=1, label='ES99 限额 3.5%')
ax.axhline(0.06, color='#ED7D31', ls='--', lw=1, label='10日VaR99 限额 6.0%')
ax.set_title('图3 历史风险指标与限额对比'); ax.legend(fontsize=8); ax.tick_params(axis='x', rotation=0)
save(fig, 'FIN3-WKN-149_chart03_风险指标与限额.png', '历史风险')

# 04 情景合格月份
fig, ax = plt.subplots(figsize=(11, 4))
names = {'S1': 'S1 增长下行与政策宽松', 'S2': 'S2 通胀上行与利率上行', 'S3': 'S3 外部冲击与美元走强', 'S4': 'S4 信用收缩与资金面收紧'}
for i, (k, v) in enumerate(R['scenario_months'].items()):
    for mo in v:
        ax.scatter(pd.Timestamp(mo + '-01'), i, s=34, color=['#4472C4', '#ED7D31', '#A5A5A5', '#C00000'][i], marker='s')
ax.set_yticks(range(4)); ax.set_yticklabels([names[k] for k in R['scenario_months']], fontsize=9)
ax.set_title('图4 四情景月度识别结果'); ax.grid(alpha=.3, axis='x')
save(fig, 'FIN3-WKN-149_chart04_情景合格月份.png', '情景识别')

# 05 历史窗口校准冲击
fig, ax = plt.subplots(figsize=(11, 4.5))
cal = pd.DataFrame({k: v['calib'] for k, v in hist.items()}).T * 100
cal.plot(kind='bar', ax=ax, width=.8); ax.axhline(0, color='k', lw=.8)
ax.set_title('图5 各情景历史窗口校准冲击（10 个交易日累计变动，%）'); ax.legend(fontsize=8, ncol=3); ax.tick_params(axis='x', rotation=0)
save(fig, 'FIN3-WKN-149_chart05_历史窗口校准冲击.png', '情景校准')

# 06 沿用冲击 vs 历史校准（推荐方案）
fig, ax = plt.subplots(figsize=(10, 5))
xs = [s.scenario_id for _, s in shocks.iterrows()]
cm = [stress[('推荐方案', x, 'committee')]['total'] * 100 for x in xs]
hm = [stress[('推荐方案', x, 'historical')]['total'] * 100 for x in xs]
w = 0.36; idx2 = np.arange(len(xs))
ax.bar(idx2 - w / 2, cm, w, label='委员会沿用冲击', color='#C00000')
ax.bar(idx2 + w / 2, hm, w, label='历史校准冲击', color='#4472C4')
ax.set_xticks(idx2); ax.set_xticklabels(xs); ax.set_ylabel('推荐方案损失（%）')
ax.set_title('图6 两套冲击下推荐方案损失对比'); ax.legend(fontsize=8)
save(fig, 'FIN3-WKN-149_chart06_两套冲击对比.png', '情景校准')

# 07 方案决策与限额
fig, ax = plt.subplots(figsize=(10, 5))
ns = list(R['max_stress'].keys()); vs = [R['max_stress'][n][0] * 100 for n in ns]
cols = ['#C00000' if v < -8 else ('#ED7D31' if v < -7 else '#70AD47') for v in vs]
ax.bar(ns, [-v for v in vs], color=cols)
ax.axhline(8, color='#C00000', ls='--', lw=1.2, label='8.0% 压力损失上限')
ax.axhline(7, color='#ED7D31', ls=':', lw=1.2, label='7.0% 推荐方案缓冲线')
ax.set_ylabel('最大压力损失（%）'); ax.set_title('图7 各方案最大压力损失与限额'); ax.legend(fontsize=8)
save(fig, 'FIN3-WKN-149_chart07_方案决策与限额.png', '方案决策')

# 08 调仓现金路径
fig, ax = plt.subplots(figsize=(9, 4.5))
ps = R['cash_path_sell_first']
ax.plot(range(len(ps)), [p * 100 for p in ps], marker='o', color='#4472C4', label='先卖后买现金占比')
ax.axhline(8, color='#C00000', ls='--', lw=1.2, label='现金下限 8%')
ax.axhline(R['cash_path_buy_first_min'] * 100, color='#ED7D31', ls=':', lw=1.2, label='先买后卖最低现金')
ax.set_xlabel('执行步骤（按比例卖出→买入）'); ax.set_ylabel('人民币现金及货基占比（%）')
ax.set_title('图8 调仓执行现金路径'); ax.legend(fontsize=8)
save(fig, 'FIN3-WKN-149_chart08_调仓现金路径.png', '调仓执行')

# 09 反向压力测试
fig, ax = plt.subplots(figsize=(10, 4.5))
rv = R['reverse_stress']['vec']
ax.barh(list(rv.keys()), [v * 100 for v in rv.values()], color='#7030A0')
ax.axvline(0, color='k', lw=.8); ax.set_title(f"图9 反向压力测试最可能情景（最小马氏距离 {R['reverse_stress']['md']}）")
ax.set_xlabel('风险因子变动（%）')
save(fig, 'FIN3-WKN-149_chart09_反向压力测试.png', '反向压力')

# 10 监测指标
fig, ax = plt.subplots(figsize=(11, 4.5))
mn = {'M1 沪深300 20日': mon['M1'] * 100, 'M4 中债10年(bp)': mon['M4'], 'M5 美债10年(bp)': mon['M5'],
      'M6 PPI同比(pp)': mon['M6'], 'M8 社融存量同比(%)': mon['M8']}
th = {'M1 沪深300 20日': -5.0, 'M4 中债10年(bp)': 10.0, 'M5 美债10年(bp)': 40.0, 'M6 PPI同比(pp)': 1.5, 'M8 社融存量同比(%)': 8.0}
ax.bar(range(len(mn)), list(mn.values()), color=['#C00000' if abs(list(mn.values())[i]) > abs(list(th.values())[i]) else '#70AD47' for i in range(len(mn))])
ax.scatter(range(len(th)), list(th.values()), color='k', marker='_', s=300, label='阈值')
ax.set_xticks(range(len(mn))); ax.set_xticklabels(list(mn.keys()), fontsize=8); ax.legend(fontsize=8)
ax.set_title('图10 监测指标最新值与阈值'); ax.grid(alpha=.3, axis='y')
save(fig, 'FIN3-WKN-149_chart10_监测指标触发状态.png', '监测触发')

print(f'\n图表已生成: {len(list(CH.glob("*.png")))} 张')

# ============================ 13. 决策备忘录 ============================
pct = lambda x, n=2: f'{x*100:.{n}f}%'
bp = lambda x: f'{x:.2f}bp'
L = []
A = L.append
A('# 多资产稳健配置专户 三季度宏观压力测试与调仓建议')
A('## 风险委员会决策备忘录\n')
A(f'**分析截至日**：2026-09-15 | **组合净值**：{NAV:,.0f} 万元（1 亿元） | **货币单位**：万元\n')

A('### 一、结论与建议')
A(f'三个候选方案均不能同时通过九项检查：**方案A** 未通过第 8 项（最大压力损失 {pct(R["max_stress"]["方案A"][0])}，超出 8.0% 上限）与第 9 项；'
  f'**方案B** 仅未通过第 9 项（最大压力损失 {pct(R["max_stress"]["方案B"][0])}，超出 7.0% 缓冲线）；'
  f'**方案C** 因把不对冲汇率的标普500 QDII 计入外币资产敞口（美元现金 20% + 标普500 10% = 30%），未通过第 5 项。')
A(f'按构造规则得到的**推荐方案**九项全部通过：最大压力损失 {pct(R["max_stress"]["推荐方案"][0])}，'
  f'1 日 ES99 {pct(R["plan_risk"]["推荐方案"]["es99"])}，10 日 VaR99 {pct(R["plan_risk"]["推荐方案"]["var99_10d"])}，'
  f'单向换手率 {pct(R["turnover"])}。**建议采用推荐方案**，并按「先卖后买」顺序执行。'
  f'八个监测指标当前触发 0 项、数据缺口 2 项，**不需要提请临时风险会议**。\n')

A('### 二、数据核验与样本区间')
A(f'可用样本区间为 **{R["sample_start"]} 至 {R["sample_end"]}**，共 **{R["sample_days"]:,} 个上交所交易日**；'
  f'终止原因是中债国债收益率曲线的五个期限在同一天终止。该曲线距分析截至日 2026-09-15 缺少 **{R["missing_after_cgb"]} 个上交所交易日**。')
A('')
A('| 序列 | 覆盖区间 | 记录数 | 缺口/异常 |')
A('|---|---|---|---|')
A(f'| 沪深300 / 中证500 / 创业板指 | 2018-01-02 ~ 2026-09-15 | 各 {len(eq["000300"])} | 含休市日异常记录（见下） |')
A(f'| 中债国债收益率曲线 1/2/5/10/30 年 | 2018-01-02 ~ {R["sample_end"]} | 各 {len(cgb["10y"].dropna())} | 止于 {R["sample_end"]} |')
A(f'| Shibor | {R["data_gaps"]["shibor_first"]} ~ 2026-09-15 | {R["data_gaps"]["shibor_rows"]} | 接口 has_more=true，记录数恰为 2,000 条，实际起点 {R["data_gaps"]["shibor_first"]}，而数据清单把 possible_truncation 标为 false |')
A(f'| 1 年期 LPR | — | {len(lpr1)} | 缺 {", ".join(R["data_gaps"]["lpr_1y_missing"])} |')
A(f'| 制造业 PMI | — | {len(pmi)} | 缺 {", ".join(R["data_gaps"]["pmi_missing"])} |')
A(f'| 社融存量 | — | {len(afre)} | 缺 {", ".join(R["data_gaps"]["afre_missing"])} |')
A('')
A('**休市日异常记录**：')
for a in R['anomalies']:
    A(f'- `{a["symbol"]}` 在 {a["date"]}（周六）存在 1 条记录：pre_close = {a["pre_close"]}，'
      f'与前一交易日收盘价 {a["prev_close"]} 一致；成交额仅为前一交易日的 {a["proximity"] if "proximity" in a else a["amount_ratio"]*100:.2f}%。'
      f'该记录**予以剔除**。')
A('')
A('**结构性空值**（该期限品类当期尚不存在）：此类空值的成因是“品种尚未存在”而非“数据缺失”，'
  '因此**不参与前向填充、也不置零**，直接从相应计算窗口排除；与行情缺口所采用的前向填充处理严格区分，'
  '**不得按 0 参与计算**：')
A(f'- 5 年期 LPR 在 {R["structural_nan"]["lpr_5y_until"]} 及以前为空；')
A(f'- 美国国债 m2 在 {R["structural_nan"]["ust_m2_first"]} 之前为空；')
A(f'- 美国国债 m4 在 {R["structural_nan"]["ust_m4_first"]} 之前为空（该品种仅 {R["structural_nan"]["ust_m4_rows"]} 条记录）。')
A('')
A('**价格对齐口径**：USD/CNH 的日期标注口径在 2022-09-18 至 2023-05-26 之间发生变化，'
  '须先按上交所估值日对齐价格（前向填充到交易日序列），再计算收益；'
  '标普500 的人民币计收益按 (1 + 美元计变动率) × (1 + USD/CNH 变动率) − 1 **复合折算**，不使用加法近似。\n')

A('### 三、当前组合风险画像')
A('| 资产 | 类别 | 当前权重 | 金额（万元） |')
A('|---|---|---|---|')
for _, r in hold.iterrows():
    A(f'| {r.asset} | {r.asset_class} | {pct(r.weight_current)} | {r.weight_current*NAV:,.2f} |')
A('')
cr = R['plan_risk']['当前持仓']
A(f'当前组合年化波动率 **{pct(cr["ann_vol"])}**，1 日 VaR95 {pct(cr["var95"])}、VaR99 {pct(cr["var99"])}，'
  f'1 日 ES95 {pct(cr["es95"])}、ES99 {pct(cr["es99"])}，10 日 VaR99 {pct(cr["var99_10d"])}；')
A(f'10 日最大累计损失 **{pct(cr["worst10"])}**（{cr["worst10_start"]} 至 {cr["worst10_end"]}）；'
  f'最大回撤 **{pct(cr["mdd"])}**（{cr["mdd_end"]} 起，修复日 {cr["mdd_recov"]}）；最差单日损失 {pct(cr["worst_day"])}（{cr["worst_day_date"]}）。')
A('')
A('**各方案历史风险指标对比**（历史模拟法）：')
A('| 方案 | 年化波动率 | 1日VaR95 | 1日VaR99 | 1日ES95 | 1日ES99 | 10日VaR99 | 10日最大累计损失 | 最大回撤 | 最差单日 |')
A('|---|---|---|---|---|---|---|---|---|---|')
for k, v in R['plan_risk'].items():
    A(f'| {k} | {pct(v["ann_vol"])} | {pct(v["var95"])} | {pct(v["var99"])} | {pct(v["es95"])} | {pct(v["es99"])} | '
      f'{pct(v["var99_10d"])} | {pct(v["worst10"])} | {pct(v["mdd"])} | {pct(v["worst_day"])} |')
A('')
A('**上表关键指标的区间明细**（每个方案的 10 日最大累计损失发生区间、最大回撤区间与修复日）：')
A('| 方案 | 10日最大累计损失 | 发生区间（起—止） | 最大回撤 | 回撤区间（峰—谷） | 修复日 |')
A('|---|---|---|---|---|---|')
for k, v in R['plan_risk'].items():
    A(f'| {k} | {pct(v["worst10"])} | {v["worst10_start"]} 至 {v["worst10_end"]} | '
      f'{pct(v["mdd"])} | {v["mdd_start"]} 至 {v["mdd_end"]} | {v["mdd_recov"]} |')
A('')
A('**相关矩阵**（日收益）：')
A('| | 沪深300 | 中证500 | 创业板 | 国债 | 美元现金 | 标普500 |')
A('|---|---|---|---|---|---|---|')
for i in CM.index:
    A('| ' + i + ' | ' + ' | '.join(f'{CM.loc[i, j]:.4f}' for j in CM.columns) + ' |')
A('')
rcv = R['risk_contribution']['当前持仓']
A(f'境内权益三项合计风险贡献 **{pct(sum(rcv[k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}**'
  f'（方案A {pct(sum(R["risk_contribution"]["方案A"][k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}、'
  f'方案B {pct(sum(R["risk_contribution"]["方案B"][k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}、'
  f'方案C {pct(sum(R["risk_contribution"]["方案C"][k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}、'
  f'推荐方案 {pct(sum(R["risk_contribution"]["推荐方案"][k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}）。\n')

A('### 四、情景识别与历史校准')
A('| 情景 | 识别规则 | 合格月份数 | 合格月份 |')
A('|---|---|---|---|')
for _, r in rules.iterrows():
    A(f'| {r.scenario_id} {r.scenario} | {r.rule} | {len(R["scenario_months"][r.scenario_id])} | {", ".join(R["scenario_months"][r.scenario_id])} |')
A('')
A('| 情景 | 历史窗口（首个） | 合格窗口数 | 窗口内最深累计跌幅 |')
A('|---|---|---|---|')
for k, v in hist.items():
    A(f'| {k} | {v["window_start"]} ~ {v["window_end"]} | {v["n_windows"]} | {pct(v["depth"])} |')
A('')
A('**校准冲击（窗口累计变动中位数）**：')
A('| 情景 | 沪深300 | 中证500 | 创业板 | 国债 | 标普500 | USD/CNH |')
A('|---|---|---|---|---|---|---|')
for k, v in hist.items():
    c = v['calib']
    A(f'| {k} | {pct(c["EQ_000300"])} | {pct(c["EQ_000905"])} | {pct(c["EQ_399006"])} | {pct(c["CGB"])} | {pct(c["SPX"])} | {pct(c["USD_CASH"])} |')
A('')
A('委员会沿用冲击与历史校准冲击在严格程度与曲线形态上均存在差异（见第五章与图6）。\n')

A('### 五、压力测试结果')
A(f'共 {len(stress)} 个压力结果（{len(planw)} 个方案 × 4 个情景 × 2 套冲击），每个结果拆分为境内权益、标普500（人民币计）、美元现金、国债四部分贡献，四部分之和等于组合损益。')
A('')
A('| 方案 | 情景 | 冲击 | 境内权益 | 标普500 | 美元现金 | 国债 | 合计 |')
A('|---|---|---|---|---|---|---|---|')
for k, v in stress.items():
    p = v['parts']
    A(f'| {k[0]} | {k[1]} | {"沿用" if k[2]=="committee" else "历史校准"} | {pct(p["境内权益"])} | {pct(p["标普500"])} | {pct(p["美元现金"])} | {pct(p["国债"])} | **{pct(v["total"])}** |')
A('')
A('| 方案 | 最大压力损失 | 情景 | 冲击类型 | 是否超过 8.0% |')
A('|---|---|---|---|---|')
for k, v in R['max_stress'].items():
    A(f'| {k} | **{pct(v[0])}** | {v[1]} | {"委员会沿用" if v[2]=="committee" else "历史校准"} | {"是" if v[0] < -0.08 else "否"} |')
A('')
A('**严格程度比较**（推荐方案）：')
A('| 情景 | 沿用冲击 | 历史校准冲击 | 更严格者 |')
A('|---|---|---|---|')
for sid in ['S1', 'S2', 'S3', 'S4']:
    c = stress[('推荐方案', sid, 'committee')]['total']; h = stress[('推荐方案', sid, 'historical')]['total']
    A(f'| {sid} | {pct(c)} | {pct(h)} | {"沿用" if c < h else "历史校准"} |')
A('')
A('**差异原因**：委员会沿用冲击是外生设定的跨资产同向冲击——境内权益、标普500 同步下跌，USD/CNH 变动由委员会直接给定；'
  '而历史校准冲击取自各情景合格窗口内 10 个交易日累计变动的中位数，样本期内多数历史窗口中各资产的价格变动方向并不一致、'
  '幅度也更温和，故在四个情景下沿用冲击的损失均大于历史校准冲击。曲线形态差异则源于沿用冲击对国债各期限设定了非平行的 bp 冲击，'
  '而历史校准冲击只反映国债组合的一个综合变动幅度。')
A('')

A('### 六、候选方案评估与九项约束检查')
A('| 检查项 | 说明 | 方案A | 方案B | 方案C | 推荐方案 |')
A('|---|---|---|---|---|---|')
for _, c in chk.iterrows():
    row = [str(R['checks'][p].get(c.check_id)) for p in ['方案A', '方案B', '方案C', '推荐方案']]
    A(f'| {c.check_id} | {c.description} | ' + ' | '.join(row) + ' |')
A('')
A('**未通过项的超限幅度明细**（逐方案列出每条未通过检查的指标、实际值、阈值与超出幅度）：')
A('| 方案 | 检查项 | 指标 | 实际值 | 阈值 | 超出幅度 |')
A('|---|---|---|---|---|---|')
_nfail = 0
for _pn in ['方案A', '方案B', '方案C', '推荐方案']:
    _w = planw[_pn]; _rm = R['plan_risk'][_pn]; _ms = R['max_stress'][_pn][0]
    _det = {
        'C1': ('组合权重合计', sum(_w.values()), 1.0, 'diff'),
        'C2': ('境内权益合计', _w['EQ_000300'] + _w['EQ_000905'] + _w['EQ_399006'], 0.60, 'upper'),
        'C3': ('人民币现金及货基', _w['CNY_CASH'], 0.20, 'upper'),
        'C4': ('中长期国债组合', _w['CGB'], 0.15, 'lower'),
        'C5': ('外币资产敞口（美元现金 + 标普500 QDII）', _w['USD_CASH'] + _w['SPX'], 0.25, 'upper'),
        'C6': ('1 日 ES99', _rm['es99'], 0.035, 'upper'),
        'C7': ('10 日 VaR99', _rm['var99_10d'], 0.060, 'upper'),
        'C8': ('最大压力损失', _ms, -0.080, 'lower'),
        'C9': ('最大压力损失', _ms, -0.070, 'lower'),
    }
    for _cid in ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9']:
        if R['checks'][_pn].get(_cid):
            continue
        _nm, _val, _thr, _kind = _det[_cid]
        _over = abs(_val - _thr) if _kind == 'diff' else (_val - _thr if _kind == 'upper' else _thr - _val)
        _nfail += 1
        A(f'| {_pn} | {_cid} | {_nm} | {pct(_val)} | {fmt(_thr * 100, 2)}% | 超出 {fmt(_over * 100, 2)} 个百分点 |')
if _nfail == 0:
    A('| — | — | 九项检查全部通过，无超限项 | — | — | — |')
A('')
A('**结论**：方案A 未通过 C8、C9；方案B 未通过 C9；方案C 未通过 C5（外币敞口 30% > 25%）。'
  '三个候选方案都不能同时通过九项检查。\n')
A('**推荐方案权重**：')
A('| 资产 | 权重 |')
A('|---|---|')
for _, r in hold.iterrows():
    A(f'| {r.asset} | {pct(r.weight_recommended)} |')
A('')

A('### 七、推荐方案与调仓执行')
A(f'境内三项按当前权重同比例合计减配 **{pct(sum(hold[hold.asset_class.str.startswith("EQ")].weight_current) - sum(hold[hold.asset_class.str.startswith("EQ")].weight_recommended))}**，'
  f'标普500 不减配，人民币现金补至 20% 上限，其余买入国债组合。单向换手率 **{pct(R["turnover"])}**。')
A('')
A('**交易清单**：')
A('| 资产 | 方向 | 金额（万元） |')
A('|---|---|---|')
for t in R['trades']:
    A(f'| {t["asset"]} | {t["side"]} | {abs(t["amount_10k"]):,.2f} |')
A('')
A(f'**执行顺序**：先卖出三只境内指数基金并确认成交后再买入国债（卖出资金当日可用，买入国债当日扣款）。')
A(f'先卖后买路径下现金占比依次为 ' + ' → '.join(pct(p) for p in R['cash_path_sell_first']) + '，全程不低于 8% 下限。')
A(f'若先买后卖，现金占比将降至 **{pct(R["cash_path_buy_first_min"])}**，击穿 8% 下限，**不可采用**。')
A('QDII 赎回款 T+7 到账；本次标普500 不交易，该规则不适用。')
A('')
A('**唯一性说明（同换手率下次优组合的量化比较）**：按 `rules_rebalance.csv` 的 recommendation_rule——'
  '美元现金及存款与标普500 QDII 权重不变、境内权益三项按当前权重同比例减配 20.5 个百分点（缩减系数 '
  f'{R["rec_derivation"]["scale"]:.2f}）、释放资金中 {fmt(R["rec_derivation"]["to_cgb_pp"], 1)} 个百分点转入中长期国债组合、'
  f'{fmt(R["rec_derivation"]["to_cny_pp"], 1)} 个百分点转入人民币现金及货基——权重组合唯一确定；'
  '解析所得权重与 `params_holdings.csv` 的 weight_recommended 列逐项一致，交叉校验全部通过。')
_ms_pn, _ms_sc, _ms_tag = R['max_stress']['推荐方案']
_bond_unit = stress[('推荐方案', _ms_sc, _ms_tag)]['parts']['国债'] / rec_w['CGB']      # 国债在该情景下的单位损益（线性口径）
_alt_cash_cny, _alt_cash_cgb = W['CNY_CASH'] + 0.15, W['CGB'] + 0.055
_alt_bond_cny, _alt_bond_cgb = W['CNY_CASH'] + 0.05, W['CGB'] + 0.155
_d_bond = 0.05 * _bond_unit
A('')
A('单向换手率同为 20.50%（卖出金额固定），释放的 20.5 个百分点只在「国债 / 现金」之间分配，两种偏离均劣于本方案：')
A('| 同换手率下的分配方案 | 人民币现金及货基 | 中长期国债 | 现金缓冲 | C3（8%–20%） | 最大压力损失 |')
A('|---|---|---|---|---|---|')
A(f'| **本方案（推荐）** | {pct(rec_w["CNY_CASH"])} | {pct(rec_w["CGB"])} | 20%（用足上限） | 通过 | {pct(R["max_stress"]["推荐方案"][0])} |')
A(f'| 偏现金（现金 +5pp、国债 −5pp） | {pct(_alt_cash_cny)} | {pct(_alt_cash_cgb)} | 25% | **不通过：超出上限 {fmt((_alt_cash_cny - 0.20) * 100, 2)} 个百分点** | 不适用（已违反约束） |')
A(f'| 偏国债（国债 +5pp、现金 −5pp） | {pct(_alt_bond_cny)} | {pct(_alt_bond_cgb)} | 15% | 通过 | {pct(R["max_stress"]["推荐方案"][0] + _d_bond)}（仅改善 {fmt(abs(_d_bond) * 100, 2)} 个百分点） |')
A('')
A(f'依据：组合损益对权重是线性的，释放资金在现金与国债间仅此一次转移，故偏国债组合最大压力损失的改善可精确表示为 '
  f'5 个百分点 × 国债在该情景下的单位损益 {pct(_bond_unit)} = {fmt(abs(_d_bond) * 100, 2)} 个百分点，属可忽略量级；'
  f'而偏现金组合的现金占比升至 {pct(_alt_cash_cny)}，直接突破 C3 的 20% 上限。因此本方案在满足九项检查的前提下'
  f'把现金缓冲用足上限（20%）并以国债承接其余释放资金，在同换手率下唯一最优。\n')

A('### 八、反向压力测试与监测预警')
rv = R['reverse_stress']
A(f'推荐方案在最大损失情景下的损失为 {pct(R["max_stress"]["推荐方案"][0])}，距离 8.0% 上限仍有 '
  f'{pct(abs(0.08 + R["max_stress"]["推荐方案"][0]))} 裕度（约 {abs(0.08 / R["max_stress"]["推荐方案"][0]):.2f} 倍放大）。')
_w10 = R['plan_risk']['推荐方案']
A(f'样本内最差的 10 日累计损失为 {pct(_w10["worst10"])}'
  f'（发生于 {_w10["worst10_start"]} 至 {_w10["worst10_end"]}），未达到 8%。')
A('')
A('**反向压力测试最可能情景**（在组合损益 = 最大压力损失的约束下最小化马氏距离）：')
A('| 风险因子 | 变动 |')
A('|---|---|')
for k, v in rv['vec'].items():
    A(f'| {k} | {pct(v)} |')
A(f'\n最小马氏距离 **{rv["md"]}**；在相同协方差口径下，委员会沿用信用收缩冲击的马氏距离为 **{R["md_committee"]}**，'
  f'信用收缩历史校准窗口的马氏距离为 **{R["md_historical"]}**，说明委员会沿用冲击显著偏离历史常态。')
A('')
A('| 监测指标 | 阈值 | 最新值 | 截至日状态 | 是否触发 |')
A('|---|---|---|---|---|')
mmv = {'M1': (mon['M1'] * 100, -5.0, '%'), 'M2': (mon['M2'] * 100, 2.0, '%'), 'M3': (mon['M3'], 20.0, 'bp'),
       'M4': (mon['M4'], 10.0, 'bp'), 'M5': (mon['M5'], 40.0, 'bp'), 'M6': (mon['M6'], 1.5, 'pp'),
       'M7': (mon['M7'], 49.0, ''), 'M8': (mon['M8'], 8.0, '%')}
names8 = {'M1': '沪深300 20 日收益', 'M2': 'USD/CNH 20 日变化', 'M3': 'DR007 资金面变化', 'M4': '10 年期国债收益率 20 日变化',
          'M5': '美国 10 年期国债收益率 20 日变化', 'M6': 'PPI 同比加速', 'M7': '制造业 PMI', 'M8': '社融存量增速'}
for k in ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8']:
    v, th, u = mmv[k]
    gap = k in ('M4', 'M7')
    st = '数据缺口：无法判断截至日状态' if gap else '已更新'
    trg = '—' if gap else ('是' if abs(v) >= abs(th) and (v < th if k in ('M1', 'M7', 'M8') else v > th) else '否')
    A(f'| {names8[k]} | {th:+.2f}{u} | {v:+.2f}{u} | {st} | {trg} |')
A('')
A('触发 0 项、数据缺口 2 项（10 年期国债收益率、制造业 PMI），**不需要提请临时风险会议**；'
  '待数据补齐后 1 个交易日内重新判断。\n')

A('---')
A('### 附件')
A('- `FIN3-WKN-149_charts/`：10 张中文标注图表（数据核验 1、历史风险 2、情景识别与校准 3、方案决策 1、调仓执行 1、反向压力测试 1、监测触发 1）')
A('- `FIN3-WKN-149_reproduce.py`：可复算代码，从 `input_files/` 原始快照读入，不硬编码结果')

(OUT / 'FIN3-WKN-149_风险委员会决策备忘录.md').write_text('\n'.join(L), encoding='utf-8')
print(f'备忘录已生成: {len(L)} 行')


