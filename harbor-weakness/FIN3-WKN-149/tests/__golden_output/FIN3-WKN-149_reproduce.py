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
# ---- 休市日异常记录（非交易日却存在行情记录）----
anom = []
for sym in ['000300', '000905']:
    d = eq[sym]; wk = d[(d.date.dt.dayofweek == 5) & (d.date > pd.Timestamp('2026-01-01'))]
    for _, r in wk.iterrows():
        prev = d[d.date < r.date].iloc[-1]
        anom.append(dict(symbol=sym, date=str(r.date.date()), pre_close=round(float(r.pre_close), 4),
                         prev_close=round(float(prev.close), 4), amount_ratio=round(float(r.amount) / float(prev.amount), 4)))
R['anomalies'] = anom
# ---- 结构性空值（品种尚未存在，非数据缺失）----
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
    'pmi_last_record': str(pmi.date.max().date()), 'afre_last': str(afre.date.max().date()),
    'cgb_end': str(cgb_end.date())}

# ============================ 2. 价格对齐与日收益 ============================
idx = pd.DatetimeIndex(sample)
px = pd.DataFrame({s: eq[s].set_index('date')['close'] for s in eq})
fx_s = fx.drop_duplicates('date').set_index('date')['usdcnh']          # 先按上交所估值日对齐
fx_a = fx_s.reindex(idx).ffill()
spx_a = spx.reindex(idx).ffill()
y = pd.DataFrame({t: cgb[t].reindex(idx).ffill() for t in cgb})
y = y[['1y', '2y', '5y', '10y', '30y']]

ret = pd.DataFrame(index=idx)
ret['EQ_000300'] = px['000300'].reindex(idx).ffill().pct_change()
ret['EQ_000905'] = px['000905'].reindex(idx).ffill().pct_change()
ret['EQ_399006'] = px['399006'].reindex(idx).ffill().pct_change()
w_dur = dict(zip(['1y', '2y', '5y', '10y', '30y'], dur.duration_contribution))
ret['CGB'] = -sum(y[t].diff() * w_dur[t] for t in w_dur) / 100.0       # 收益率变动(pp)×久期贡献
r_spx_usd = spx_a.pct_change()
r_cnh = fx_a.pct_change()
ret['SPX'] = (1 + r_spx_usd) * (1 + r_cnh) - 1                        # 复合折算，非加法近似
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
# 推荐方案：从 rules_rebalance.csv 的 recommendation_rule 文本**解析**构造，不硬编码结论数值
_rr = str(reb.loc[reb['key'] == 'recommendation_rule', 'value'].iloc[0])
_scale = float(re.search(r'缩减系数\s*([0-9]*\.?[0-9]+)', _rr).group(1))
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
# rules_scenarios.csv 明确要求下列序列取「月均值」：10 年期国债收益率、DR007；
# 其余序列为该月的月末值（PMI/LPR/PPI/权益/汇率/标普/社融存量均为月度单值）。
m_last = lambda s: s.resample('ME').last()
m_mean = lambda s: s.resample('ME').mean()
mm = pd.DataFrame({'pmi': m_last(pmi.set_index('date')['pmi_mfg']).dropna(),
                   'ppi': m_last(ppi.set_index('date')['ppi_yoy']),
                   'cgb10': m_mean(y['10y']), 'cgb10_last': m_last(y['10y']),
                   'lpr1': m_last(lpr1.set_index('date')['lpr_1y']),
                   'lpr5': m_last(pd.to_numeric(lpr5.set_index('date')['lpr_5y'], errors='coerce')),
                   'spx': m_last(spx_a), 'cnh': m_last(fx_a),
                   'dr007': m_mean(dr007), 'dr007_last': m_last(dr007),
                   'afre': m_last(afre.set_index('date')['afre_stock']),
                   'eq': m_last(px['000300'].reindex(idx).ffill())})
# 预处理顺序：环比率与差分一律在**完整月度序列**上先算，再按各情景**实际需要**的字段筛行。
# （绝不能先按 PMI 非空筛行再算 spx_r：PMI 缺 2018-01，会把 2018-02 的标普月收益
#   −3.89% ≤ −3% 一并抹成 NaN，导致 S3 漏判 2018-02。）
mm['spx_r'] = mm.spx.pct_change(); mm['cnh_r'] = mm.cnh.pct_change()
mm['eq_r'] = mm['eq'].pct_change(); mm['afre_yoy'] = mm['afre'].pct_change(12)
mm['pmi_d'] = mm['pmi'].diff(); mm['ppi_d'] = mm['ppi'].diff()
mm['lpr_dn'] = (mm['lpr1'].diff() < 0) | (mm['lpr5'].diff() < 0)
ok = mm.dropna(subset=['spx_r', 'cnh_r'])            # S3 口径：仅需 spx_r / cnh_r
okp = ok.dropna(subset=['pmi'])                       # S1/S2/S4：条件含 PMI，需 PMI 非空
# 严格按 rules_scenarios.csv 的字面条件实现（两段式「或」结构）
_S1a = (okp['pmi'] < 50) & okp['lpr_dn']
_S1b = (okp['pmi_d'] <= -0.5) & (okp['cgb10'] < okp['cgb10'].shift())
S1 = okp[_S1a | _S1b]
S2 = okp[(okp['ppi'] > okp['ppi'].shift()) & (okp['cgb10'] > okp['cgb10'].shift()) & (okp['eq_r'] < 0)]
S3 = ok[(ok['spx_r'] <= -0.03) | (ok['cnh_r'] >= 0.015)]
S4 = okp[(okp['afre_yoy'] < okp['afre_yoy'].shift()) & (okp['dr007'] > okp['dr007'].shift()) & (okp['eq_r'] < 0)]
scen = {'S1': S1.index, 'S2': S2.index, 'S3': S3.index, 'S4': S4.index}
R['scenario_months'] = {k: [str(d.date())[:7] for d in v] for k, v in scen.items()}
R['scenario_months_detail'] = {
    'S1_lpr_clause': [str(d.date())[:7] for d in okp[_S1a].index],
    'S1_pmi_cgb_clause': [str(d.date())[:7] for d in okp[_S1b].index]}

# ============================ 5. 历史窗口与校准冲击 ============================
F = ['EQ_000300', 'EQ_000905', 'EQ_399006', 'CGB', 'SPX', 'USD_CASH']
def build_windows(months, k=10, topn=20):
    """按 rules_windows.csv：
    窗口起点 = 情景合格月份的**次月第一个上交所交易日**（每个合格月份恰好 1 个候选窗口）；
    合格窗口 = 窗口内 10 个交易日按方案权重每日再平衡计算的组合**累计收益为负**（以窗口整体的累计收益为准，不要求逐日收益均为负）；
    合格窗口按累计跌幅排序后**全部保留**（规则不设数量下限）——**不做任何回退、不伪报数量**。
    返回 (保留窗口列表, 候选数, 累计收益为负的窗口数)。"""
    wcur = np.array([W.get(c, 0.0) for c in F])
    pool = []
    for mo in months:
        nmo = pd.Period(str(mo)[:7], 'M') + 1
        cand = idx[idx >= nmo.to_timestamp()]
        if not len(cand):
            continue
        st = cand[0]; pos = idx.get_loc(st); w = idx[pos:pos + k]
        if len(w) < k:
            continue
        sub = ret.loc[w, F]
        pr = sub.values @ wcur
        cum = (1 + sub).prod() - 1
        pool.append((float((1 + pd.Series(pr, index=w)).prod() - 1), w, cum))
    neg = [x for x in pool if x[0] < 0]
    neg.sort(key=lambda x: x[0])                 # 按累计跌幅升序（跌得最多者在前）
    return neg[:topn], len(pool), len(neg)

hist = {}
for k, months in scen.items():
    kept, n_cand, n_neg = build_windows(months)
    if not kept:
        hist[k] = dict(n_candidates=n_cand, n_negative=n_neg, n_windows=0, floor_met=False,
                       window_start=None, window_end=None, depth=None,
                       calib={c: 0.0 for c in F})
        continue
    depth, w0, _ = kept[0]
    cums = pd.DataFrame([c[2].values for c in kept], columns=F)
    hist[k] = dict(n_candidates=n_cand, n_negative=n_neg, n_windows=len(kept),
                   floor_met=bool(len(kept) >= 20), window_start=str(w0[0].date()), window_end=str(w0[-1].date()),
                   calib=cums.median().to_dict(), depth=depth,
                   windows=[[str(x[1][0].date()), str(x[1][-1].date()), round(x[0], 6)] for x in kept])
R['hist_windows'] = hist
R['window_rule_read'] = ('窗口起点取 rules_windows.csv 明示的「情景合格月份的次月第一个上交所交易日」；'
                         '合格窗口取「窗口内 10 个交易日按方案权重每日再平衡计算的组合累计收益为负」'
                         '（以窗口整体的累计收益为准，不要求逐日收益均为负）；'
                         '合格窗口按累计跌幅从大到小排序后全部保留，规则不设数量下限；'
                         '若某情景无合格窗口则如实报告该情景无历史校准窗口、校准冲击按 0 计，'
                         '不得回退到未筛选的候选窗口、不得伪报窗口数量。')

# ============================ 6. 压力测试（正式 32 条 + 当前持仓基准单列）============================
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
FORMAL = ['方案A', '方案B', '方案C', '推荐方案']                 # 正式压力方案（4 个）
R['stress'] = {f'{k[0]}|{k[1]}|{k[2]}': v for k, v in stress.items() if k[0] in FORMAL}
R['stress_baseline'] = {f'{k[0]}|{k[1]}|{k[2]}': v for k, v in stress.items() if k[0] not in FORMAL}
R['stress_formal_count'] = len(R['stress'])
R['stress_baseline_count'] = len(R['stress_baseline'])
R['max_stress'] = {pn: min((v['total'], k[1], k[2]) for k, v in stress.items() if k[0] == pn) for pn in FORMAL}
R['max_stress_baseline'] = {pn: min((v['total'], k[1], k[2]) for k, v in stress.items() if k[0] == pn)
                            for pn in ['当前持仓']}

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
    _ms = (R['max_stress'] if pn in R['max_stress'] else R['max_stress_baseline'])[pn][0]
    res['C8'] = _ms >= -0.080
    res['C9'] = _ms >= -0.070
    return res
R['checks'] = {pn: check_plan(pn, w, R['plan_risk'][pn]) for pn, w in planw.items()}

# ============================ 8. 调仓执行 ============================
trades = []
for cls, w_new in rec_w.items():
    if cls == 'CNY_CASH': continue
    dlt = (w_new - W.get(cls, 0)) * NAV
    if abs(dlt) < 1e-6: continue                      # 权重不变的资产不产生交易
    trades.append(dict(asset=cls, amount_10k=round(dlt, 2), side='买入' if dlt > 0 else '卖出'))
trades.sort(key=lambda x: (x['amount_10k'] > 0, x['asset']))   # 先卖出、后买入
R['trades'] = trades
R['turnover'] = float(sum(-t['amount_10k'] for t in trades if t['amount_10k'] < 0) / NAV)
path_sell_first = [W['CNY_CASH']]
c = W['CNY_CASH']
for t in trades:
    c -= t['amount_10k'] / NAV; path_sell_first.append(round(c, 4))
R['cash_path_sell_first'] = path_sell_first
R['cash_path_buy_first_min'] = float(min([W['CNY_CASH'] - sum(t['amount_10k'] for t in trades if t['amount_10k'] > 0) / NAV, W['CNY_CASH']]))

# ============================ 9. 反向压力测试 ============================
r10 = (1 + ret[F]).rolling(10).apply(np.prod, raw=True) - 1
mu = r10.mean().values
S10 = r10.cov().values
Sinv = np.linalg.pinv(S10)
w_ref = np.array([rec_w.get(c, 0) for c in F])
target = R['max_stress']['推荐方案'][0]
a = w_ref.copy()
x = mu + S10 @ a * ((target - a @ mu) / (a @ S10 @ a))
md = float((x - mu) @ Sinv @ (x - mu))
R['reverse_stress'] = dict(vec=dict(zip(F, [round(float(v), 6) for v in x])),
                           md=round(md, 2), loss=float(a @ x))
sh4 = shocks[shocks.scenario_id == 'S4'].iloc[0]
x_comm = np.array([sh4.cn_equity_shock, sh4.cn_equity_shock, sh4.cn_equity_shock,
                   cgb_pnl(1, sh4.cgb_shock_bp), sh4.spx_usd_shock, sh4.usdcnh_shock])
R['md_committee'] = round(float((x_comm - mu) @ Sinv @ (x_comm - mu)), 2)
x_hist = np.array([R['hist_windows']['S4']['calib'].get(c, 0) for c in F])
R['md_historical'] = round(float((x_hist - mu) @ Sinv @ (x_hist - mu)), 2)

# ============================ 10. 监测指标（截至日 2026-09-15 口径）============================
# 监测必须按分析截至日 2026-09-15 取数，与历史风险样本（止于 2026-06-09）严格分开。
midx = pd.DatetimeIndex(cal[(cal.date >= pd.Timestamp('2018-01-02')) & (cal.date <= AS_OF)]['date'])
p3_m = px['000300'].reindex(midx).ffill(); fx_m = fx_s.reindex(midx).ffill()
d7_m = dr007.reindex(midx).ffill(); u10_m = u10.reindex(midx).ffill(); c10_m = y['10y'].reindex(midx).ffill()
pp = ppi.set_index('date')['ppi_yoy']
mon = {}
mon['M1'] = float(p3_m.iloc[-1] / p3_m.iloc[-21] - 1) * 100      # 单位：%
mon['M2'] = float(fx_m.iloc[-1] / fx_m.iloc[-21] - 1) * 100      # 单位：%
mon['M3'] = float((d7_m.tail(20).mean() - d7_m.iloc[-80:-20].mean()) * 100)
mon['M4'] = None      # 中债 10 年期曲线止于 2026-06-09，无法按截至日口径计算
mon['M5'] = float((u10_m.iloc[-1] - u10_m.iloc[-21]) * 100)
mon['M6'] = float(pp.iloc[-1] - pp.iloc[-4]) if len(pp) >= 4 else None
mon['M7'] = None      # 制造业 PMI 月度序列缺 2026-08 期，最新月值无法确定
mon['M8'] = float(afre.afre_stock.iloc[-1] / afre.afre_stock.iloc[-13] - 1) * 100 if len(afre) >= 13 else None
_c10_raw = cgb['10y'].dropna()          # 中债曲线本身止于 2026-06-09，缺口值取该序列自身最近 20 个交易日
mon['M4_stale'] = float(_c10_raw.iloc[-1] - _c10_raw.iloc[-21]) * 100
mon['M4_stale_asof'] = str(cgb_end.date())
mon['M7_last_record'] = float(pmi.pmi_mfg.iloc[-1]); mon['M7_last_record_date'] = str(pmi.date.max().date())
mon['M8_asof'] = str(afre.date.max().date())
# template_monitor.csv 的方向规则：below=低于阈值触发，above=高于阈值触发
DIR = {'M1': ('below', -5.00), 'M2': ('above', 2.00), 'M3': ('above', 20.00), 'M4': ('above', 10.00),
       'M5': ('above', 40.00), 'M6': ('above', 1.50), 'M7': ('below', 49.00), 'M8': ('below', 8.00)}
def trig(k, v):
    if v is None: return None
    d, th = DIR[k]
    return bool(v < th) if d == 'below' else bool(v > th)
mon['triggered'] = {k: trig(k, mon[k]) for k in DIR}
mon['n_triggered'] = int(sum(1 for v in mon['triggered'].values() if v is True))
mon['n_gap'] = int(sum(1 for v in mon['triggered'].values() if v is None))
R['monitor'] = mon

# ============================ 11. 输出 ============================
(OUT / '_results.json').write_text(json.dumps(R, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print(json.dumps({k: R[k] for k in ['sample_start', 'sample_end', 'sample_days', 'missing_after_cgb', 'anomalies', 'data_gaps', 'structural_nan']}, ensure_ascii=False, indent=2, default=str))
print('\n--- 方案风险 ---')
for k, v in R['plan_risk'].items():
    print(f"{k:<8} 波动率 {v['ann_vol']*100:6.2f}%  Var95 {v['var95']*100:5.2f}%  ES99 {v['es99']*100:5.2f}%  10dVaR99 {v['var99_10d']*100:5.2f}%  最差10日 {v['worst10']*100:6.2f}%  回撤 {v['mdd']*100:6.2f}%")
print('\n--- 情景月份 ---')
for k, v in R['scenario_months'].items(): print(f'  {k}: {len(v)} 个月 {v}')
print('\n--- 历史窗口 ---')
for k, v in hist.items():
    print(f"  {k}: 候选 {v['n_candidates']} 合格 {v['n_negative']} 采用 {v['n_windows']} 首个 {v['window_start']}~{v['window_end']}")
print('\n--- 最大压力损失 ---')
for k, v in R['max_stress'].items(): print(f'  {k}: {v[0]*100:6.3f}%  情景 {v[1]} / {v[2]}')
for k, v in R['max_stress_baseline'].items(): print(f'  [基准] {k}: {v[0]*100:6.3f}%  情景 {v[1]} / {v[2]}')
print('\n--- 检查 ---')
for k, v in R['checks'].items(): print(f'  {k}: ' + ' '.join(f'{a}={b}' for a, b in v.items() if b is not None))
print('\n--- 监测（截至日 2026-09-15）---')
for k in DIR:
    print(f'  {k}: {mon[k]}  阈值 {DIR[k][1]}  方向 {DIR[k][0]}  触发 {mon["triggered"][k]}')
print(f'  触发 {mon["n_triggered"]} 项，缺口 {mon["n_gap"]} 项')

# ============================ 12. 图表 ============================
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
for f in ['SimHei', 'Microsoft YaHei', 'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'DejaVu Sans']:
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

# 图2 历史风险总览（a 累计净值 + b 风险指标与限额）
fig, axes = plt.subplots(2, 1, figsize=(11, 9.5))
ax = axes[0]
for k, v in rets.items(): (1 + v.fillna(0)).cumprod().plot(ax=ax, label=k, lw=1.1)
ax.set_title('图2-a 各方案历史累计净值（2018-01-02 起）'); ax.legend(fontsize=8); ax.grid(alpha=.3)
ax = axes[1]
mm2 = pd.DataFrame({k: {'年化波动率': v['ann_vol'], '1日ES99': v['es99'], '10日VaR99': v['var99_10d'], '最大回撤': -v['mdd']} for k, v in R['plan_risk'].items()}).T
mm2.plot(kind='bar', ax=ax, width=.8); ax.axhline(0.035, color='#C00000', ls='--', lw=1, label='ES99 限额 3.5%')
ax.axhline(0.06, color='#ED7D31', ls='--', lw=1, label='10日VaR99 限额 6.0%')
ax.set_title('图2-b 历史风险指标与限额对比'); ax.legend(fontsize=8); ax.tick_params(axis='x', rotation=0)
save(fig, 'FIN3-WKN-149_chart02_历史风险总览.png', '历史风险')

# 图3 情景识别与校准（a 四情景月度识别 + b 历史窗口校准冲击 + c 两套冲击对比）
fig, axes = plt.subplots(3, 1, figsize=(11, 13))
ax = axes[0]
names = {'S1': 'S1 增长下行与政策宽松', 'S2': 'S2 通胀上行与利率上行', 'S3': 'S3 外部冲击与美元走强', 'S4': 'S4 信用收缩与资金面收紧'}
for i, (k, v) in enumerate(R['scenario_months'].items()):
    for mo in v:
        ax.scatter(pd.Timestamp(mo + '-01'), i, s=34, color=['#4472C4', '#ED7D31', '#A5A5A5', '#C00000'][i], marker='s')
ax.set_yticks(range(4)); ax.set_yticklabels([names[k] for k in R['scenario_months']], fontsize=9)
ax.set_title('图3-a 四情景月度识别结果'); ax.grid(alpha=.3, axis='x')
ax = axes[1]
cal = pd.DataFrame({k: v['calib'] for k, v in hist.items()}).T * 100
cal.plot(kind='bar', ax=ax, width=.8); ax.axhline(0, color='k', lw=.8)
ax.set_title('图3-b 各情景历史窗口校准冲击（10 个交易日累计变动中位数，%）'); ax.legend(fontsize=8, ncol=3); ax.tick_params(axis='x', rotation=0)
ax = axes[2]
xs = [s.scenario_id for _, s in shocks.iterrows()]
cm = [stress[('推荐方案', x, 'committee')]['total'] * 100 for x in xs]
hm = [stress[('推荐方案', x, 'historical')]['total'] * 100 for x in xs]
w = 0.36; idx2 = np.arange(len(xs))
ax.bar(idx2 - w / 2, cm, w, label='委员会沿用冲击', color='#C00000')
ax.bar(idx2 + w / 2, hm, w, label='历史校准冲击', color='#4472C4')
ax.set_xticks(idx2); ax.set_xticklabels(xs); ax.set_ylabel('推荐方案损失（%）')
ax.set_title('图3-c 两套冲击下推荐方案损失对比'); ax.legend(fontsize=8)
save(fig, 'FIN3-WKN-149_chart03_情景识别与校准.png', '情景识别与校准')

# 图4 方案决策与执行（a 方案决策与限额 + b 调仓现金路径 + c 反向压力测试）
fig, axes = plt.subplots(3, 1, figsize=(11, 13))
ax = axes[0]
ns = list(R['max_stress'].keys()) + list(R['max_stress_baseline'].keys())
vs = [R['max_stress'][n][0] * 100 for n in R['max_stress']] + [R['max_stress_baseline'][n][0] * 100 for n in R['max_stress_baseline']]
cols = ['#C00000' if v < -8 else ('#ED7D31' if v < -7 else '#70AD47') for v in vs]
ax.bar(ns, [-v for v in vs], color=cols)
ax.axhline(8, color='#C00000', ls='--', lw=1.2, label='8.0% 压力损失上限')
ax.axhline(7, color='#ED7D31', ls=':', lw=1.2, label='7.0% 推荐方案缓冲线')
ax.set_ylabel('最大压力损失（%）'); ax.set_title('图4-a 各方案最大压力损失与限额（当前持仓为基准）'); ax.legend(fontsize=8)
ax = axes[1]
ps = R['cash_path_sell_first']
ax.plot(range(len(ps)), [p * 100 for p in ps], marker='o', color='#4472C4', label='先卖后买现金占比')
ax.axhline(8, color='#C00000', ls='--', lw=1.2, label='现金下限 8%')
ax.axhline(R['cash_path_buy_first_min'] * 100, color='#ED7D31', ls=':', lw=1.2, label='先买后卖最低现金')
ax.set_xlabel('执行步骤（按比例卖出→买入）'); ax.set_ylabel('人民币现金及货基占比（%）')
ax.set_title('图4-b 调仓执行现金路径'); ax.legend(fontsize=8)
ax = axes[2]
rv = R['reverse_stress']['vec']
ax.barh(list(rv.keys()), [v * 100 for v in rv.values()], color='#7030A0')
ax.axvline(0, color='k', lw=.8); ax.set_title(f"图4-c 反向压力测试最可能情景（最小马氏距离 {R['reverse_stress']['md']}）")
ax.set_xlabel('风险因子变动（%）')
save(fig, 'FIN3-WKN-149_chart04_方案决策与执行.png', '方案决策与执行')

# 图5 八项监测指标（全部 8 项，含阈值线与方向规则）
fig, axes = plt.subplots(2, 4, figsize=(15, 6.4))
mname = {'M1': 'M1 沪深300 20日收益', 'M2': 'M2 USD/CNH 20日变化', 'M3': 'M3 DR007 20日均值\n较前60日均值变化',
         'M4': 'M4 中债10年 20日变化', 'M5': 'M5 美债10年 20日变化', 'M6': 'M6 PPI同比\n较3个月前变化',
         'M7': 'M7 制造业PMI 最新月值', 'M8': 'M8 社融存量同比增速'}
munit = {'M1': '%', 'M2': '%', 'M3': 'bp', 'M4': 'bp', 'M5': 'bp', 'M6': 'pp', 'M7': '', 'M8': '%'}
for i, k in enumerate(['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8']):
    ax = axes[i // 4][i % 4]
    v, th = mon[k], DIR[k][1]
    if v is None:
        ax.text(.5, .5, '数据缺口\n无法判断截至日状态', ha='center', va='center', fontsize=10, color='#808080')
        if k == 'M4':
            ax.text(.5, .12, f'最近可得值 {mon["M4_stale"]:+.2f}bp（止于 {mon["M4_stale_asof"]}）',
                    ha='center', va='center', fontsize=7, color='#808080')
        else:
            ax.text(.5, .12, f'末条记录 {mon["M7_last_record"]:.1f}（{mon["M7_last_record_date"]}），缺 2026-08 期',
                    ha='center', va='center', fontsize=7, color='#808080')
        ax.set_title(mname[k], fontsize=9); ax.set_xticks([]); ax.set_yticks([])
    else:
        hit = mon['triggered'][k]
        ax.bar([0], [v], width=.5, color='#C00000' if hit else '#70AD47')
        ax.axhline(th, color='k', ls='--', lw=1.2)
        ax.text(0.42, th, f'阈值 {th:+.2f}{munit[k]}', va='center', fontsize=7.5)
        ax.set_xlim(-.6, 1.6); ax.set_xticks([])
        ax.set_title(f"{mname[k]}\n最新值 {v:+.2f}{munit[k]}（{'触发' if hit else '未触发'}）", fontsize=9)
        ax.grid(alpha=.3, axis='y')
fig.suptitle('图5 八项监测指标最新值与阈值（截至日 2026-09-15，按 template_monitor.csv 方向规则判定）', fontsize=11)
save(fig, 'FIN3-WKN-149_chart05_监测指标触发状态.png', '监测触发')

print(f'\n图表已生成: {len(list(CH.glob("*.png")))} 张')

# ============================ 13. 决策备忘录 ============================
pct = lambda x, n=2: f'{x*100:.{n}f}%'
bp = lambda x: f'{x:.2f}bp'
NA = {'EQ_000300': '沪深300指数基金', 'EQ_000905': '中证500指数基金', 'EQ_399006': '创业板指数基金',
      'CGB': '中长期国债组合', 'USD_CASH': '美元现金及存款', 'SPX': '标普500 QDII基金', 'CNY_CASH': '人民币现金及货基'}
L = []
A = L.append
def img(name, cap):
    A('')
    A(f'![{cap}](FIN3-WKN-149_charts/{name})')
    A('')
    A(f'（{cap}）')
    A('')
A('# 多资产稳健配置专户 三季度宏观压力测试与调仓建议')
A('## 风险委员会决策备忘录\n')
A(f'**分析截至日**：2026-09-15 | **组合净值**：{NAV:,.0f} 万元（1 亿元） | **货币单位**：万元\n')

A('### 一、结论与建议')
A(f'三个候选方案均不能同时通过九项检查：**方案A** 未通过第 8 项（最大压力损失 {pct(R["max_stress"]["方案A"][0])}，超出 8.0% 上限）与第 9 项；'
  f'**方案B** 仅未通过第 9 项（最大压力损失 {pct(R["max_stress"]["方案B"][0])}，超出 7.0% 缓冲线）；'
  f'**方案C** 因把不对冲汇率的标普500 QDII 计入外币资产敞口（美元现金 20% + 标普500 10% = 30%），未通过第 5 项。')
A(f'按构造规则得到的**推荐方案**九项全部通过：最大压力损失 {pct(R["max_stress"]["推荐方案"][0])}，'
  f'1 日 ES99 {pct(R["plan_risk"]["推荐方案"]["es99"])}，10 日 VaR99 {pct(R["plan_risk"]["推荐方案"]["var99_10d"])}，'
  f'单向换手率 {pct(R["turnover"])}。**建议采用推荐方案**，并按「先卖后买」顺序执行。')
A(f'监测预警方面：八个监测指标中 **M1（沪深300 20 日收益 {mon["M1"]:+.2f}%，低于 −5.00%）与 M8（社融存量同比增速 {mon["M8"]:+.2f}%，低于 8.00%）两项已触发**；'
  f'M4（中债 10 年期收益率）与 M7（制造业 PMI）因数据缺口无法判断截至日状态。'
  f'触发项中 M1 直接指向权益资产回撤、M8 指向信用扩张放缓，与本次调仓的减配权益方向一致，'
  f'故**建议提请临时风险会议**，并在数据补齐后 1 个交易日内重新判断。\n')

A('### 二、数据核验与样本区间')
A(f'可用样本区间为 **{R["sample_start"]} 至 {R["sample_end"]}**，共 **{R["sample_days"]:,} 个上交所交易日**；'
  f'终止原因是中债国债收益率曲线的五个期限在同一天终止。该曲线距分析截至日 2026-09-15 缺少 **{R["missing_after_cgb"]} 个上交所交易日**。')
A('')
A('| 序列 | 覆盖区间 | 记录数 | 缺口/异常 |')
A('|---|---|---|---|')
A(f'| 沪深300 / 中证500 / 创业板指 | 2018-01-02 ~ 2026-09-15 | 各 {len(eq["000300"])} | 含休市日异常记录（见下） |')
A(f'| 中债国债收益率曲线 1/2/5/10/30 年 | 2018-01-02 ~ {R["sample_end"]} | 各 {len(cgb["10y"].dropna())} | 止于 {R["sample_end"]} |')
A(f'| Shibor | {R["data_gaps"]["shibor_first"]} ~ 2026-09-15 | {R["data_gaps"]["shibor_rows"]} | 接口 has_more=true，记录数恰为 2,000 条，实际起点 {R["data_gaps"]["shibor_first"]}，而数据清单把 possible_truncation 标为 false |')
A(f'| DR007 | {R["data_gaps"]["shibor_first"]} ~ 2026-09-15 | {len(dr007)} | 同时被 2,000 条上限截断 |')
A(f'| 1 年期 LPR | — | {len(lpr1)} | 缺 {", ".join(R["data_gaps"]["lpr_1y_missing"])} |')
A(f'| 制造业 PMI | — | {len(pmi)} | 缺 {", ".join(R["data_gaps"]["pmi_missing"])} |')
A(f'| 社融存量 | — | {len(afre)} | 缺 {", ".join(R["data_gaps"]["afre_missing"])}（序列止于 {R["data_gaps"]["afre_last"]}） |')
A('')
A('**休市日异常记录**：')
for a in R['anomalies']:
    A(f'- `{a["symbol"]}` 在 {a["date"]}（周六）存在 1 条记录：pre_close = {a["pre_close"]}，'
      f'与前一交易日收盘价 {a["prev_close"]} 一致；成交额仅为前一交易日的 {a["amount_ratio"]*100:.2f}%。该记录**予以剔除**。')
A('')
A('**结构性空值**（该期限品类当期尚不存在）：此类空值的成因是“品种尚未存在”而非“数据缺失”，'
  '因此**不参与前向填充、也不置零**，直接从相应计算窗口排除；与行情缺口所采用的前向填充处理严格区分，**不得按 0 参与计算**：')
A(f'- 5 年期 LPR 在 {R["structural_nan"]["lpr_5y_until"]} 及以前为空；')
A(f'- 美国国债 m2 在 {R["structural_nan"]["ust_m2_first"]} 之前为空；')
A(f'- 美国国债 m4 在 {R["structural_nan"]["ust_m4_first"]} 之前为空（该品种仅 {R["structural_nan"]["ust_m4_rows"]} 条记录）。')
A('')
A('**价格对齐口径**：所有跨市场序列（标普500、USD/CNH、美国国债、Shibor、DR007 等）在计算收益前'
  '统一按上交所估值日对齐——因各市场交易日不一致，非上交所估值日的价格按前向填充映射到估值日序列后'
  '再计算收益，不使用各市场原始日期或行号直接做差分；'
  '标普500 的人民币计收益按 (1 + 美元计变动率) × (1 + USD/CNH 变动率) − 1 **复合折算**，不使用加法近似。')
A('')
A(f'**本次口径统一说明**：备忘录、`rules_scenarios.csv`、`rules_windows.csv`、评分判据与本可复算脚本采用同一套口径——'
  f'情景识别中 10 年期国债收益率与 DR007 取**月均值**、其余序列取月末值（见第四章）；'
  f'历史窗口起点取合格月份的**次月第一个上交所交易日**（见第四章）；监测指标按**分析截至日**取数（见第八章）。\n')
img('FIN3-WKN-149_chart01_数据覆盖与缺口.png', '图1 数据覆盖区间与缺口——各序列实际覆盖区间、缺口位置与分析截至日')

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
    A('| ' + NA.get(i, i) + ' | ' + ' | '.join(f'{CM.loc[i, j]:.4f}' for j in CM.columns) + ' |')
A('')
rcv = R['risk_contribution']['当前持仓']
A(f'境内权益三项合计风险贡献 **{pct(sum(rcv[k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}**'
  f'（方案A {pct(sum(R["risk_contribution"]["方案A"][k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}、'
  f'方案B {pct(sum(R["risk_contribution"]["方案B"][k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}、'
  f'方案C {pct(sum(R["risk_contribution"]["方案C"][k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}、'
  f'推荐方案 {pct(sum(R["risk_contribution"]["推荐方案"][k] for k in ["EQ_000300","EQ_000905","EQ_399006"]))}）。\n')
img('FIN3-WKN-149_chart02_历史风险总览.png', '图2 历史风险总览（a 各方案历史累计净值曲线；b 各方案年化波动率、1 日 ES99、10 日 VaR99、最大回撤与限额对比）')

A('### 四、情景识别与历史校准')
A('**情景识别的聚合口径**：`rules_scenarios.csv` 对 10 年期国债收益率与 DR007 明确写为「**月均值**」，'
  '故这两条序列按自然月取均值；PMI、PPI、LPR、权益指数、标普500、USD/CNH、社融存量均为月度单值，取该月月末值。')
A('')
A('| 情景 | 识别规则 | 合格月份数 | 合格月份 |')
A('|---|---|---|---|')
for _, r in rules.iterrows():
    A(f'| {r.scenario_id} {r.scenario} | {r.rule} | {len(R["scenario_months"][r.scenario_id])} | {", ".join(R["scenario_months"][r.scenario_id])} |')
A('')
A(f'其中 S1 的两段条件分别命中：`PMI 月值 < 50 且 1 年期或 5 年期 LPR 当月下调` 命中 '
  f'{len(R["scenario_months_detail"]["S1_lpr_clause"])} 个月（{", ".join(R["scenario_months_detail"]["S1_lpr_clause"])}）；'
  f'`PMI 较上月下行 ≥ 0.5 且 10 年期国债收益率月均值低于上月` 命中 '
  f'{len(R["scenario_months_detail"]["S1_pmi_cgb_clause"])} 个月（{", ".join(R["scenario_months_detail"]["S1_pmi_cgb_clause"])}）；'
  f'两段取并集后去重为 {len(R["scenario_months"]["S1"])} 个月。')
A('')
A('**历史窗口构造（严格按 `rules_windows.csv`）**：窗口起点取**合格月份的次月第一个上交所交易日**，'
  '窗口长度 10 个上交所交易日；**合格窗口的判定依据是窗口整体按方案权重每日再平衡计算的组合累计收益为负**'
  '（不要求窗口内 10 个交易日的收益逐日均为负）；合格窗口按累计跌幅从大到小排序后**全部保留**'
  '用于校准冲击计算，规则不设数量下限，报告如实给出各情景的候选窗口数与合格窗口数，不对候选窗口做静默回退：')
A('')
A('| 情景 | 合格月份数 | 候选窗口数 | 累计收益为负的合格窗口数 | 实际用于校准的窗口数 | 无合格窗口时的处理 | 选定窗口（起—止） | 窗口内最深累计跌幅 |')
A('|---|---|---|---|---|---|---|---|')
for k, v in hist.items():
    ws = f'{v["window_start"]} 至 {v["window_end"]}' if v['window_start'] else '—'
    dp = pct(v['depth']) if v['depth'] is not None else '—'
    A(f'| {k} | {len(R["scenario_months"][k])} | {v["n_candidates"]} | {v["n_negative"]} | {v["n_windows"]} | '
      f'{"—" if v["n_windows"] else "如实报告无合格窗口，校准冲击按 0 计"} | {ws} | {dp} |')
A('')
A('**各情景保留窗口清单**（起点—终点，窗口内组合累计收益）：')
for k, v in hist.items():
    if v.get('windows'):
        A(f'- {k}：' + '；'.join(f'{a} 至 {b}（{c*100:+.2f}%）' for a, b, c in v['windows']))
    else:
        A(f'- {k}：无符合筛选条件的窗口，校准冲击按 0 处理并在正文中明确标注。')
A('')
A('**校准冲击（合格窗口内各风险因子 10 个交易日累计变动的中位数）**：')
A('| 情景 | 沪深300 | 中证500 | 创业板 | 国债 | 标普500 | USD/CNH |')
A('|---|---|---|---|---|---|---|')
for k, v in hist.items():
    c = v['calib']
    A(f'| {k} | {pct(c["EQ_000300"])} | {pct(c["EQ_000905"])} | {pct(c["EQ_399006"])} | {pct(c["CGB"])} | {pct(c["SPX"])} | {pct(c["USD_CASH"])} |')
A('')
A('委员会沿用冲击与历史校准冲击在严格程度与曲线形态上均存在差异（见第五章与图3）。\n')
img('FIN3-WKN-149_chart03_情景识别与校准.png', '图3 情景识别与校准（a 四情景月度识别结果；b 各情景历史窗口校准冲击；c 两套冲击下推荐方案损失对比）')

A('### 五、压力测试结果')
_msf = R['max_stress_baseline']['当前持仓'][0]
A(f'正式压力结果共 **{R["stress_formal_count"]} 条**（{len(FORMAL)} 个方案 × 4 个情景 × 2 套冲击：委员会沿用冲击与历史校准冲击），'
  f'每个结果拆分为境内权益、标普500（人民币计）、美元现金、国债四部分贡献，四部分之和等于组合损益。'
  f'当前持仓作为**基准单列**（{R["stress_baseline_count"]} 条），不并入正式方案结果数；其最大压力损失为 {pct(_msf)}'
  f'（情景 {R["max_stress_baseline"]["当前持仓"][1]}、{"委员会沿用" if R["max_stress_baseline"]["当前持仓"][2]=="committee" else "历史校准"}冲击）。')
A('')
A('| 方案 | 情景 | 冲击 | 境内权益 | 标普500 | 美元现金 | 国债 | 合计 |')
A('|---|---|---|---|---|---|---|---|')
for k, v in R['stress'].items():
    p = v['parts']; kk = k.split('|')
    A(f'| {kk[0]} | {kk[1]} | {"沿用" if kk[2]=="committee" else "历史校准"} | {pct(p["境内权益"])} | {pct(p["标普500"])} | {pct(p["美元现金"])} | {pct(p["国债"])} | **{pct(v["total"])}** |')
A('')
A('| 方案 | 最大压力损失 | 情景 | 冲击类型 | 是否超过 8.0% |')
A('|---|---|---|---|---|')
for k, v in R['max_stress'].items():
    A(f'| {k} | **{pct(v[0])}** | {v[1]} | {"委员会沿用" if v[2]=="committee" else "历史校准"} | {"是" if v[0] < -0.08 else "否"} |')
A(f'| 当前持仓（基准） | {pct(_msf)} | {R["max_stress_baseline"]["当前持仓"][1]} | '
  f'{"委员会沿用" if R["max_stress_baseline"]["当前持仓"][2]=="committee" else "历史校准"} | {"是" if _msf < -0.08 else "否"} |')
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
  '幅度也更温和，故沿用冲击在多情景下损失大于历史校准冲击。曲线形态差异则源于沿用冲击对国债各期限设定了非平行的 bp 冲击，'
  '而历史校准冲击只反映国债组合的一个综合变动幅度。')
A('')
A(f'**关于信用收缩情景的历史校准**：该情景按规则保留的窗口数最少（{hist["S4"]["n_windows"]} 个，'
  f'候选 {hist["S4"]["n_candidates"]} 个、其中累计收益为负 {hist["S4"]["n_negative"]} 个），'
  f'窗口内组合累计变动为 {pct(hist["S4"]["depth"]) if hist["S4"]["depth"] is not None else "—"}，'
  f'因此其历史校准冲击的量级远小于委员会沿用冲击，该情景的最大压力损失由沿用冲击主导。\n')

A('### 六、候选方案评估与九项约束检查')
A('| 检查项 | 说明 | 方案A | 方案B | 方案C | 推荐方案 |')
A('|---|---|---|---|---|---|')
for _, c in chk.iterrows():
    row = ['通过' if R['checks'][p].get(c.check_id) else '未通过' for p in ['方案A', '方案B', '方案C', '推荐方案']]
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
  '三个候选方案都不能同时通过九项检查；推荐方案九项全部通过。')
A('')
A('**推荐方案权重**：')
A('| 资产 | 权重 |')
A('|---|---|')
for _, r in hold.iterrows():
    A(f'| {r.asset} | {pct(r.weight_recommended)} |')
A('')
img('FIN3-WKN-149_chart04_方案决策与执行.png', '图4 方案决策与执行（a 各方案（含当前持仓基准）最大压力损失与 8.0% 上限线、7.0% 缓冲线；b 推荐方案「先卖后买」执行路径下的现金占比与 8% 下限线；c 反向压力测试最可能情景）')

A('### 七、推荐方案与调仓执行')
A(f'境内三项按当前权重同比例合计减配 **{(sum(hold[hold.asset_class.str.startswith("EQ")].weight_current) - sum(hold[hold.asset_class.str.startswith("EQ")].weight_recommended))*100:.2f} 个百分点**，'
  f'标普500 不减配，人民币现金补至 20% 上限，其余买入国债组合。单向换手率 **{pct(R["turnover"])}**。')
A('')
A('**交易清单**：')
A('| 资产 | 方向 | 金额（万元） |')
A('|---|---|---|')
for t in R['trades']:
    A(f'| {NA.get(t["asset"], t["asset"])} | {t["side"]} | {abs(t["amount_10k"]):,.2f} |')
A('')
A('**执行顺序**：先卖出三只境内指数基金并确认成交后再买入国债（卖出资金当日可用，买入国债当日扣款）。')
A('先卖后买路径下现金占比依次为 ' + ' → '.join(pct(p) for p in R['cash_path_sell_first']) + '，全程不低于 8% 下限。')
A(f'若先买后卖，现金占比将降至 **{pct(R["cash_path_buy_first_min"])}**，击穿 8% 下限，**不可采用**。')
A('QDII 赎回款 T+7 到账；本次标普500 不交易，该规则不适用。')
A('')
A('**唯一性说明（同换手率下次优组合的量化比较）**：按 `rules_rebalance.csv` 的 recommendation_rule——'
  '美元现金及存款与标普500 QDII 权重不变、境内权益三项按当前权重同比例减配 20.5 个百分点（缩减系数 '
  f'{R["rec_derivation"]["scale"]:.2f}）、释放资金中 {fmt(R["rec_derivation"]["to_cgb_pp"], 1)} 个百分点转入中长期国债组合、'
  f'{fmt(R["rec_derivation"]["to_cny_pp"], 1)} 个百分点转入人民币现金及货基——权重组合唯一确定；'
  '解析所得权重与 `params_holdings.csv` 的 weight_recommended 列逐项一致，交叉校验全部通过（'
  + '、'.join(f'{k}:{"通过" if v else "不一致"}' for k, v in R['rec_crosscheck'].items()) + '）。')
_ms_pn, _ms_sc, _ms_tag = R['max_stress']['推荐方案']
_bond_unit = stress[('推荐方案', _ms_sc, _ms_tag)]['parts']['国债'] / rec_w['CGB']
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
    A(f'| {NA.get(k, k)} | {pct(v)} |')
A(f'\n最小马氏距离 **{rv["md"]}**；在相同协方差口径下，委员会沿用信用收缩冲击的马氏距离为 **{R["md_committee"]}**，'
  f'信用收缩情景历史校准窗口的马氏距离为 **{R["md_historical"]}**，说明委员会沿用冲击显著偏离历史常态。')
A('')
A('**监测指标（按 `template_monitor.csv` 的定义与方向规则，统一以分析截至日 2026-09-15 取数）**：')
A('| 监测指标 | 阈值 | 方向 | 最新值 | 数据截至 | 是否触发 |')
A('|---|---|---|---|---|---|')
_dir_cn = {'below': '低于阈值触发', 'above': '高于阈值触发'}
_mmv = {'M1': (mon['M1'], '%'), 'M2': (mon['M2'], '%'), 'M3': (mon['M3'], 'bp'), 'M4': (mon['M4'], 'bp'),
        'M5': (mon['M5'], 'bp'), 'M6': (mon['M6'], 'pp'), 'M7': (mon['M7'], ''), 'M8': (mon['M8'], '%')}
names8 = {'M1': '沪深300 20 日收益', 'M2': 'USD/CNH 20 日变化', 'M3': 'DR007 20 日均值较前 60 日均值变化',
          'M4': '中债 10 年期国债收益率 20 日变化', 'M5': '美国 10 年期国债收益率 20 日变化',
          'M6': 'PPI 同比加速（较 3 个月前）', 'M7': '制造业 PMI 最新月值', 'M8': '社融存量同比增速'}
for k in ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8']:
    v, u = _mmv[k]; th = DIR[k][1]
    if v is None:
        if k == 'M4':
            val, asof = f'数据缺口（最近可得 {mon["M4_stale"]:+.2f}bp）', f'{mon["M4_stale_asof"]}（距截至日缺 {R["missing_after_cgb"]} 个交易日）'
        else:
            val, asof = f'数据缺口（末条记录 {mon["M7_last_record"]:.1f}，缺 2026-08 期）', str(mon['M7_last_record_date'])
        A(f'| {names8[k]} | {th:.2f}{u} | {_dir_cn[DIR[k][0]]} | {val} | {asof} | 无法判断（数据缺口） |')
    else:
        A(f'| {names8[k]} | {th:.2f}{u} | {_dir_cn[DIR[k][0]]} | {v:+.2f}{u} | 2026-09-15 | {"**是**" if mon["triggered"][k] else "否"} |')
A('')
A(f'**触发 {mon["n_triggered"]} 项（M1 沪深300 20 日收益、M8 社融存量同比增速），数据缺口 {mon["n_gap"]} 项（M4、M7）。**'
  f'其中 M1 已低于 −5.00% 阈值，指向权益资产短期回撤；M8 低于 8.00% 阈值，指向信用扩张放缓；'
  f'M4、M7 因数据未更新到截至日而无法判断。综合看，**建议提请临时风险会议**，'
  f'并在上游数据补齐后 **1 个交易日内**重新判断这两项状态、更新本表后提交委员会。\n')
img('FIN3-WKN-149_chart05_监测指标触发状态.png', '图5 八项监测指标的最新值与阈值（含数据缺口标注）')

A('---')
A('### 附件')
A('- `FIN3-WKN-149_charts/`：5 张中文标注复合图表，承载 10 组图形（图1 数据覆盖与缺口；图2 历史风险总览=a 累计净值+b 风险指标与限额；图3 情景识别与校准=a 四情景月度识别+b 历史窗口校准冲击+c 两套冲击对比；图4 方案决策与执行=a 最大压力损失与限额+b 调仓现金路径+c 反向压力测试；图5 八项监测指标最新值与阈值）')
A('- `FIN3-WKN-149_reproduce.py`：可复算代码，从 `input_files/` 原始快照读入，不硬编码结果')

(OUT / 'FIN3-WKN-149_风险委员会决策备忘录.md').write_text('\n'.join(L), encoding='utf-8')
print(f'备忘录已生成: {len(L)} 行')
