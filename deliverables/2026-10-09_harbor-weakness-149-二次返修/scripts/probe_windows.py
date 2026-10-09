# -*- coding: utf-8 -*-
"""FIN3-WKN-149 窗口口径探针：实测「逐日全负」vs「累计负」两种口径下各情景的合格窗口。"""
import pathlib, sys, re
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

IN = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                  r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-149\environment\input_files')

rd = lambda n, **kw: pd.read_csv(IN / n, parse_dates=['date'], **kw)
eq = {}
for sym, stem in [('000300', 'snapshot_000300SH'), ('000905', 'snapshot_000905SH'), ('399006', 'snapshot_399006SZ')]:
    d = pd.concat([rd(f'{stem}_seg1.csv'), rd(f'{stem}_seg2.csv')]).sort_values('date').reset_index(drop=True)
    eq[sym] = d
cal = rd('snapshot_trade_calendar.csv')
cgb = {t: rd(f'snapshot_cgb_yield_{t}.csv').set_index('date')['yield_pct'] for t in ['1y','2y','5y','10y','30y']}
fx = pd.concat([rd('snapshot_usdcnh_seg1.csv'), rd('snapshot_usdcnh_seg2.csv')]).sort_values('date').reset_index(drop=True)
spx = rd('snapshot_spx.csv').set_index('date')['close']
dr007 = rd('snapshot_dr007.csv').set_index('date')['dr007']
lpr1 = rd('snapshot_lpr_1y.csv'); lpr5 = rd('snapshot_lpr_5y.csv')
pmi = rd('snapshot_pmi_manufacturing.csv'); afre = rd('snapshot_afre_stock.csv')
ppi = rd('snapshot_ppi_yoy.csv')
hold = pd.read_csv(IN / 'params_holdings.csv'); dur = pd.read_csv(IN / 'params_duration.csv')
rules = pd.read_csv(IN / 'rules_scenarios.csv'); reb = pd.read_csv(IN / 'rules_rebalance.csv')

cgb_end = cgb['10y'].dropna().index.max()
sample = cal[(cal.date >= pd.Timestamp('2018-01-02')) & (cal.date <= cgb_end)]['date']
idx = pd.DatetimeIndex(sample)
px = pd.DataFrame({s: eq[s].set_index('date')['close'] for s in eq})
fx_a = fx.drop_duplicates('date').set_index('date')['usdcnh'].reindex(idx).ffill()
spx_a = spx.reindex(idx).ffill()
y = pd.DataFrame({t: cgb[t].reindex(idx).ffill() for t in cgb})[['1y','2y','5y','10y','30y']]
ret = pd.DataFrame(index=idx)
ret['EQ_000300'] = px['000300'].reindex(idx).ffill().pct_change()
ret['EQ_000905'] = px['000905'].reindex(idx).ffill().pct_change()
ret['EQ_399006'] = px['399006'].reindex(idx).ffill().pct_change()
w_dur = dict(zip(['1y','2y','5y','10y','30y'], dur.duration_contribution))
ret['CGB'] = -sum(y[t].diff() * w_dur[t] for t in w_dur) / 100.0
ret['SPX'] = (1 + spx_a.pct_change()) * (1 + fx_a.pct_change()) - 1
ret['USD_CASH'] = fx_a.pct_change()
ret['CNY_CASH'] = 0.0
ret = ret.dropna(how='all')
W = dict(zip(hold.asset_class, hold.weight_current))

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
mm['spx_r'] = mm.spx.pct_change(); mm['cnh_r'] = mm.cnh.pct_change()
mm['eq_r'] = mm['eq'].pct_change(); mm['afre_yoy'] = mm['afre'].pct_change(12)
mm['pmi_d'] = mm['pmi'].diff(); mm['ppi_d'] = mm['ppi'].diff()
mm['lpr_dn'] = (mm['lpr1'].diff() < 0) | (mm['lpr5'].diff() < 0)
ok = mm.dropna(subset=['spx_r', 'cnh_r']); okp = ok.dropna(subset=['pmi'])
_S1a = (okp['pmi'] < 50) & okp['lpr_dn']
_S1b = (okp['pmi_d'] <= -0.5) & (okp['cgb10'] < okp['cgb10'].shift())
S1 = okp[_S1a | _S1b]
S2 = okp[(okp['ppi'] > okp['ppi'].shift()) & (okp['cgb10'] > okp['cgb10'].shift()) & (okp['eq_r'] < 0)]
S3 = ok[(ok['spx_r'] <= -0.03) | (ok['cnh_r'] >= 0.015)]
S4 = okp[(okp['afre_yoy'] < okp['afre_yoy'].shift()) & (okp['dr007'] > okp['dr007'].shift()) & (okp['eq_r'] < 0)]
scen = {'S1': S1.index, 'S2': S2.index, 'S3': S3.index, 'S4': S4.index}

F = ['EQ_000300','EQ_000905','EQ_399006','CGB','SPX','USD_CASH']
wcur = np.array([W.get(c, 0.0) for c in F])

def build(months, k=10):
    """返回每个候选窗口的明细"""
    out = []
    for mo in months:
        nmo = pd.Period(str(mo)[:7], 'M') + 1
        cand = idx[idx >= nmo.to_timestamp()]
        if not len(cand): continue
        st = cand[0]; pos = idx.get_loc(st); w = idx[pos:pos + k]
        if len(w) < k: continue
        sub = ret.loc[w, F]
        pr = sub.values @ wcur
        cum = float((1 + pd.Series(pr, index=w)).prod() - 1)
        ndown = int((pd.Series(pr, index=w) < 0).sum())
        out.append(dict(month=str(mo)[:7], start=str(w[0].date()), end=str(w[-1].date()),
                        cum=cum, ndown=ndown, allneg=(ndown == k)))
    return out

print(f'样本区间 {idx[0].date()} ~ {idx[-1].date()}  共 {len(idx)} 个交易日')
tot = {}
for s, months in scen.items():
    rows = build(months)
    neg = [r for r in rows if r['cum'] < 0]
    alln = [r for r in rows if r['allneg']]
    tot[s] = dict(cand=len(rows), cumneg=len(neg), allneg=len(alln))
    print(f'\n===== {s}：合格月份 {len(months)} 个；候选窗口 {len(rows)}；累计负 {len(neg)}；逐日全负 {len(alln)} =====')
    if alln:
        print('  [逐日全负窗口]')
        for r in alln:
            print(f"    {r['month']} {r['start']}~{r['end']} cum={r['cum']*100:.4f}% ndown={r['ndown']}/10")
    print('  [累计负前 10]')
    for r in sorted(neg, key=lambda x: x['cum'])[:10]:
        print(f"    {r['month']} {r['start']}~{r['end']} cum={r['cum']*100:.4f}% ndown={r['ndown']}/10")
print('\n=== 汇总 ===')
for s, v in tot.items():
    print(f"{s}: 候选={v['cand']} 累计负={v['cumneg']} 逐日全负={v['allneg']}")
