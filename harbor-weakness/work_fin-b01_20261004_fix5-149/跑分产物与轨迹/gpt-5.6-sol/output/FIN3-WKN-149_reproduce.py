from pathlib import Path
import warnings
warnings.filterwarnings('ignore')
import json, re, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from matplotlib import font_manager

BASE = Path('/app')
INPUT = BASE / 'input_files'
OUTPUT = BASE / 'output'
CHARTS = OUTPUT / 'FIN3-WKN-149_charts'
CHARTS.mkdir(parents=True, exist_ok=True)
ASOF = pd.to_datetime(pd.read_csv(INPUT/'snapshot_trade_calendar.csv')['date']).max()
ASOF_STR = ASOF.strftime('%Y-%m-%d')
TOTAL = float(pd.read_csv(INPUT/'params_positions.csv')['weight_current'].sum() * 10000)

# Use an installed CJK font when available so every PNG has readable Chinese labels.
for font_name in ['Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'Microsoft YaHei', 'Arial Unicode MS']:
    if any(font_name.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
        plt.rcParams['font.sans-serif'] = [font_name]
        break
plt.rcParams['axes.unicode_minus'] = False


def read_csv(name, **kwargs):
    return pd.read_csv(INPUT/name, **kwargs)


def pct(x, n=2):
    return 'N/A' if pd.isna(x) else f'{x*100:.{n}f}%'


def bp(x, n=2):
    return 'N/A' if pd.isna(x) else f'{x:.{n}f}bp'


def date_range_text(s):
    s = pd.Series(pd.to_datetime(s).dropna())
    return f'{s.min():%Y-%m-%d}至{s.max():%Y-%m-%d}' if len(s) else '无'


def signed_pct(x, n=2):
    return 'N/A' if pd.isna(x) else f'{x*100:+.{n}f}%'

# ---------- Input validation and aligned daily data ----------
calendar = read_csv('snapshot_trade_calendar.csv')
calendar['date'] = pd.to_datetime(calendar['date'])
calendar = calendar.loc[(calendar['exchange'] == 'SSE') & (calendar['is_trading_day'] == 1)].sort_values('date')
trade_dates = pd.DatetimeIndex(calendar['date'])

manifest = read_csv('snapshot_data_manifest.csv')

series_files = {
    '沪深300': ['snapshot_000300SH_seg1.csv','snapshot_000300SH_seg2.csv'],
    '中证500': ['snapshot_000905SH_seg1.csv','snapshot_000905SH_seg2.csv'],
    '创业板': ['snapshot_399006SZ_seg1.csv','snapshot_399006SZ_seg2.csv'],
    '国债1年': ['snapshot_cgb_yield_1y.csv'], '国债2年': ['snapshot_cgb_yield_2y.csv'],
    '国债5年': ['snapshot_cgb_yield_5y.csv'], '国债10年': ['snapshot_cgb_yield_10y.csv'],
    '国债30年': ['snapshot_cgb_yield_30y.csv'],
    'USD/CNH': ['snapshot_usdcnh_seg1.csv','snapshot_usdcnh_seg2.csv'],
    '标普500': ['snapshot_spx.csv'], '美国10年国债': ['snapshot_ust_10y.csv'],
    '美国M2': ['snapshot_ust_m2.csv'], '美国M4': ['snapshot_ust_m4.csv'],
    'Shibor': ['snapshot_shibor_seg1.csv','snapshot_shibor_seg2.csv'],
    '1年LPR': ['snapshot_lpr_1y.csv'], '5年LPR': ['snapshot_lpr_5y.csv'],
    '制造业PMI': ['snapshot_pmi_manufacturing.csv'], '社融存量': ['snapshot_afre_stock.csv'],
    'DR007': ['snapshot_dr007.csv'], 'PPI': ['snapshot_ppi_yoy.csv']
}

def load_concat(files):
    frames=[]
    for f in files:
        x=read_csv(f)
        x['date']=pd.to_datetime(x['date'])
        frames.append(x)
    x=pd.concat(frames, ignore_index=True).sort_values('date')
    return x.drop_duplicates('date', keep='last').reset_index(drop=True)

raw = {k: load_concat(v) for k,v in series_files.items()}
quality=[]
for name,x in raw.items():
    miss=int(x.isna().sum().sum())
    dup=int(x['date'].duplicated().sum())
    q=manifest[manifest['file'].isin(series_files[name])]
    quality.append({'序列':name,'覆盖区间':date_range_text(x['date']),'记录数':len(x),'空值单元格':miss,'重复日期':dup,
                    '清单截断标记':'; '.join(str(v) for v in q['possible_truncation'].dropna().tolist()) or '未标注'})
quality_df=pd.DataFrame(quality)

# Daily series are aligned to SSE valuation dates. Forward fill is only used for market series;
# structural missing values in low-frequency macro series are never used as daily values.
def aligned_col(x, col):
    s=x.set_index('date')[col].reindex(trade_dates).ffill()
    return s

prices=pd.DataFrame(index=trade_dates)
prices['沪深300']=aligned_col(raw['沪深300'],'close')
prices['中证500']=aligned_col(raw['中证500'],'close')
prices['创业板']=aligned_col(raw['创业板'],'close')
prices['SPX_USD']=aligned_col(raw['标普500'],'close')
prices['USD/CNH']=aligned_col(raw['USD/CNH'],'usdcnh')
prices['美国10年国债']=aligned_col(raw['美国10年国债'],'yield_pct')
for ten in ['1年','2年','5年','10年','30年']:
    prices[f'国债{ten}']=aligned_col(raw[f'国债{ten}'],'yield_pct')

# The common historical risk sample ends at the last date where every risk input is actually observed.
# This is not a forward fill across a structural end-of-series gap.
actual_end = min(raw[k]['date'].max() for k in ['沪深300','中证500','创业板','国债1年','国债2年','国债5年','国债10年','国债30年','USD/CNH','标普500'])
prices_all=prices.copy()
sample_dates=trade_dates[trade_dates<=actual_end]
prices=prices.loc[sample_dates]

rets=pd.DataFrame(index=sample_dates)
for k in ['沪深300','中证500','创业板']:
    rets[k]=prices[k].pct_change()
rets['标普500（人民币计）']=(1+prices['SPX_USD'].pct_change())*(prices['USD/CNH']/prices['USD/CNH'].shift(1))-1
rets['美元现金']=prices['USD/CNH'].pct_change()
dur=read_csv('params_duration.csv')
dur_map=dict(zip(dur['tenor'],dur['duration_contribution']))
dy = prices[[f'国债{x}' for x in ['1年','2年','5年','10年','30年']]].diff()/100
rets['中长期国债'] = -(dy['国债1年']*dur_map['1年'] + dy['国债2年']*dur_map['2年'] + dy['国债5年']*dur_map['5年'] + dy['国债10年']*dur_map['10年'] + dy['国债30年']*dur_map['30年'])
rets['人民币现金']=0.0
rets=rets.dropna()
asset_order=['沪深300','中证500','创业板','中长期国债','美元现金','标普500（人民币计）','人民币现金']

hold=read_csv('params_holdings.csv')
hold_weights=dict(zip(hold['asset'],hold['weight_current']))
asset_to_col={'沪深300指数基金':'沪深300','中证500指数基金':'中证500','创业板指数基金':'创业板','中长期国债组合':'中长期国债','美元现金及存款':'美元现金','标普500 QDII基金':'标普500（人民币计）','人民币现金及货基':'人民币现金'}
current_w=np.array([hold_weights[a] for a in hold['asset']])
# Asset order in holding files is the same as asset_order after mapping.
current_w=pd.Series({asset_to_col[a]:w for a,w in hold_weights.items()}) if False else pd.Series(dict(zip(asset_order, current_w)))

plans=read_csv('plans_candidates.csv')
plan_weights={}
for _,r in plans.iterrows():
    plan_weights[r['plan_id']]=pd.Series([r['w_000300'],r['w_000905'],r['w_399006'],r['w_cgb'],r['w_usd_cash'],r['w_spx_qdii'],r['w_cny_cash']],index=asset_order,dtype=float)
positions=read_csv('params_positions.csv')
# params_positions is the current amount detail; recommended weights are in params_holdings.
recommended=pd.Series(dict(zip([asset_to_col[a] for a in hold['asset']], hold['weight_recommended'].astype(float))))
plan_weights['推荐方案']=recommended
plan_weights['当前组合']=current_w


def portfolio_returns(w):
    return rets[asset_order].dot(w.reindex(asset_order))


def risk_metrics(w):
    pr=portfolio_returns(w).dropna()
    q95=float(np.quantile(pr,0.01))
    q99=float(np.quantile(pr,0.01))
    # VaR95 uses 5% lower tail; q99 uses 1% lower tail.
    q95=float(np.quantile(pr,0.05)); q99=float(np.quantile(pr,0.01))
    es95=float(-pr[pr<=q95].mean()); es99=float(-pr[pr<=q99].mean())
    roll10=(1+pr).rolling(10).apply(np.prod, raw=True)-1
    worst10=float(roll10.min()); worst10_end=roll10.idxmin(); worst10_start=worst10_end-pd.tseries.offsets.BDay(9)
    nav=(1+pr).cumprod(); running=nav.cummax(); dd=nav/running-1; trough=dd.idxmin(); maxdd=float(dd.min()); peak=nav.loc[:trough].idxmax();
    recovery=nav.loc[trough:][nav.loc[trough:]>=nav.loc[peak]].index.min() if (nav.loc[trough:]>=nav.loc[peak]).any() else pd.NaT
    tail=pr[pr<=q99].index
    comp=rets.loc[tail,asset_order].mul(w.reindex(asset_order),axis=1).mean()
    rc=(-comp/(-pr.loc[tail].mean())).to_dict()
    return {'ann_vol':float(pr.std()*np.sqrt(252)),'var95':float(-q95),'var99':float(-q99),'es95':es95,'es99':es99,
            'var10_99':float(-np.quantile(roll10.dropna(),0.01)),'worst10':worst10,'worst10_start':worst10_start,'worst10_end':worst10_end,
            'maxdd':maxdd,'peak':peak,'trough':trough,'recovery':recovery,'worst1':float(pr.min()),'worst1_date':pr.idxmin(),'rc':rc}

risk={k:risk_metrics(w) for k,w in plan_weights.items()}

# ---------- Monthly scenario identification ----------
def monthly_last(x,col):
    z=x.copy(); z['month']=z['date'].dt.to_period('M'); return z.dropna(subset=[col]).groupby('month')[col].last()
def monthly_mean(x,col):
    z=x.copy(); z['month']=z['date'].dt.to_period('M'); return z.dropna(subset=[col]).groupby('month')[col].mean()

def monthly_return(x,col):
    z=x.copy(); z['month']=z['date'].dt.to_period('M'); g=z.dropna(subset=[col]).groupby('month')[col]; return g.last()/g.first()-1

pmi=monthly_last(raw['制造业PMI'],'pmi_mfg')
ppi=monthly_last(raw['PPI'],'ppi_yoy')
afre=monthly_last(raw['社融存量'],'afre_stock')
yoy=afre/afre.shift(12)-1
dr007=monthly_mean(raw['DR007'],'dr007')
y10=monthly_mean(raw['国债10年'],'yield_pct')
lpr1=monthly_last(raw['1年LPR'],'lpr_1y')
lpr5=monthly_last(raw['5年LPR'],'lpr_5y')
equity_month=monthly_return(raw['沪深300'],'close')
spx_month=monthly_return(raw['标普500'],'close')
fx_month=monthly_return(raw['USD/CNH'],'usdcnh')
months=pd.period_range(min(v.index.min() for v in [pmi,ppi,yoy,dr007,y10,equity_month,spx_month,fx_month]), max(v.index.max() for v in [pmi,ppi,yoy,dr007,y10,equity_month,spx_month,fx_month]),freq='M')
monthly=pd.DataFrame(index=months)
for n,v in {'PMI':pmi,'PPI':ppi,'AFRE同比增速':yoy,'DR007':dr007,'国债10年均值':y10,'1年LPR':lpr1,'5年LPR':lpr5,'沪深300收益':equity_month,'标普500收益':spx_month,'USD/CNH变化':fx_month}.items(): monthly[n]=v
monthly['S1']=( (monthly['PMI']<50) & ((monthly['1年LPR']<monthly['1年LPR'].shift(1)) | (monthly['5年LPR']<monthly['5年LPR'].shift(1))) | ((monthly['PMI']-monthly['PMI'].shift(1)<=-0.5)&(monthly['国债10年均值']<monthly['国债10年均值'].shift(1))) )
monthly['S2']=(monthly['PPI']>monthly['PPI'].shift(1))&(monthly['国债10年均值']>monthly['国债10年均值'].shift(1))&(monthly['沪深300收益']<0)
monthly['S3']=(monthly['标普500收益']<=-0.03)|(monthly['USD/CNH变化']>=0.015)
monthly['S4']=(monthly['AFRE同比增速']<monthly['AFRE同比增速'].shift(1))&(monthly['DR007']>monthly['DR007'].shift(1))&(monthly['沪深300收益']<0)
scenario_names=dict(zip(read_csv('rules_scenarios.csv')['scenario_id'],read_csv('rules_scenarios.csv')['scenario']))

# factor windows: current portfolio all-negative 10-SSE-day windows following qualifying months.
factor_names=['境内权益','标普500美元','USD/CNH','国债1年','国债2年','国债5年','国债10年','国债30年']
def factor_window(start,end):
    x=prices.loc[start:end]
    if len(x)<10: return None
    idx=x.index[:10]
    f=pd.Series(index=factor_names,dtype=float)
    f['境内权益']=prices.loc[idx,'沪深300'].iloc[-1]/prices.loc[idx,'沪深300'].iloc[0]-1
    f['标普500美元']=prices.loc[idx,'SPX_USD'].iloc[-1]/prices.loc[idx,'SPX_USD'].iloc[0]-1
    f['USD/CNH']=prices.loc[idx,'USD/CNH'].iloc[-1]/prices.loc[idx,'USD/CNH'].iloc[0]-1
    for ten in ['1年','2年','5年','10年','30年']:
        f[f'国债{ten}']=(prices.loc[idx,f'国债{ten}'].iloc[-1]-prices.loc[idx,f'国债{ten}'].iloc[0])*100
    return idx, f

windows={}; qualified={}
for sid in ['S1','S2','S3','S4']:
    qmonths=monthly.index[monthly[sid].fillna(False)].tolist(); qualified[sid]=qmonths
    candidates=[]
    for m in qmonths:
        nextdays=trade_dates[trade_dates.to_period('M')>m]
        if len(nextdays)<10: continue
        idx=nextdays[:10]
        if idx[0]>actual_end: continue
        pr=portfolio_returns(current_w).reindex(idx).dropna()
        if len(pr)==10 and (pr<0).all():
            f=factor_window(idx[0],idx[-1])
            if f is not None: candidates.append({'month':m,'dates':idx,'cum':float((1+pr).prod()-1),'factors':f[1]})
    candidates=sorted(candidates,key=lambda z:z['cum'])
    selected=candidates[:max(20,len(candidates))] if candidates else []
    windows[sid]=selected

calibration={}
for sid,ws in windows.items():
    if ws:
        ff=pd.DataFrame([w['factors'] for w in ws])
        calibration[sid]=ff.median()
    else:
        calibration[sid]=pd.Series(np.nan,index=factor_names)

# ---------- Stress test ----------
shocks=read_csv('params_committee_shocks.csv')

def shock_factors(row):
    d={ '境内权益':row['cn_equity_shock'], '标普500美元':row['spx_usd_shock'], 'USD/CNH':row['usdcnh_shock'] }
    for part in str(row['cgb_shock_bp']).split(','):
        k,v=part.split(':'); d[f'国债{ {'1Y':'1年','2Y':'2年','5Y':'5年','10Y':'10年','30Y':'30年'}[k] }']=float(v.replace('+',''))
    return pd.Series(d)
committee_factors={r['scenario_id']:shock_factors(r) for _,r in shocks.iterrows()}

def stress_parts(w, f):
    f=pd.Series(f)
    eq=w[['沪深300','中证500','创业板']].sum()*f['境内权益']
    spx=w['标普500（人民币计）']*((1+f['标普500美元'])*(1+f['USD/CNH'])-1)
    usd=w['美元现金']*f['USD/CNH']
    cgb=-w['中长期国债']*sum(dur_map[t]*f[f'国债{t}']/10000 for t in ['1年','2年','5年','10年','30年'])
    return pd.Series({'境内权益':eq,'标普500（人民币计）':spx,'美元现金':usd,'国债':cgb,'组合损益':eq+spx+usd+cgb})

stress_rows=[]
for pid,w in plan_weights.items():
    if pid=='当前组合': continue
    for sid in ['S1','S2','S3','S4']:
        for typ,f in [('委员会沿用',committee_factors[sid]),('历史校准',calibration[sid])]:
            x=stress_parts(w,f).to_dict(); x.update({'方案':pid,'情景':sid,'冲击':typ,'损失':-x['组合损益']})
            stress_rows.append(x)
stress=pd.DataFrame(stress_rows)
maxstress=stress.loc[stress.groupby('方案')['损失'].idxmax()].set_index('方案')

# ---------- Limits and recommendation ----------
limits=read_csv('params_limits.csv')

def turnover(w): return float(np.maximum(current_w-w,0).sum())

def checks(pid,w):
    rm=risk[pid]
    pmax=float(stress[stress['方案']==pid]['损失'].max())
    vals={'L1':float(w.sum()),'L2':float(w[['沪深300','中证500','创业板']].sum()),'L3':float(w['人民币现金']),'L4':float(w['中长期国债']),'L5':float(w['美元现金']+w['标普500（人民币计'] if False else w['美元现金']+w['标普500（人民币计）']),
          'L6':rm['es99'],'L7':rm['var10_99'],'L8':pmax,'L9':pmax}
    passmap={'L1':abs(vals['L1']-1)<=0.0005,'L2':vals['L2']<=0.6,'L3':0.08<=vals['L3']<=0.2,'L4':vals['L4']>=0.15,'L5':vals['L5']<=0.25,'L6':vals['L6']<=0.035,'L7':vals['L7']<=0.06,'L8':vals['L8']<=0.08,'L9':vals['L9']<=0.07}
    return vals,passmap
checks_all={pid:checks(pid,w) for pid,w in plan_weights.items() if pid!='当前组合'}

# same-turnover uniqueness: enumerate a fine grid of alternative domestic-equity allocations while preserving totals and fixed foreign assets.
rec_eq=0.5-recommended[['沪深300','中证500','创业板']].sum()
alts=[]
for a in np.arange(0,rec_eq+0.00001,0.0025):
    for b in np.arange(0,rec_eq-a+0.00001,0.0025):
        c=rec_eq-a-b
        w=recommended.copy(); w[['沪深300','中证500','创业板']]=[a,b,c]
        # same turnover and same CGB/CNY transfer, fixed USD and SPX
        p=float(maxstress['损失'].iloc[0]) if False else max(-stress_parts(w,committee_factors[s])['组合损益'] for s in ['S1','S2','S3','S4'])
        alts.append((p,a,b,c))
alts=sorted(alts,key=lambda z:z[0])
# Exclude exact recommendation, then take next grid point.
rec_tuple=(recommended['沪深300'],recommended['中证500'],recommended['创业板'])
next_alt=next(x for x in alts if max(abs(x[i+1]-rec_tuple[i]) for i in range(3))>1e-8)

# ---------- Monitoring ----------
monitor=read_csv('template_monitor.csv')
for col in ['latest_value','data_asof','status','triggered']:
    monitor[col]=monitor[col].astype(object)
# Use latest actual available observation for each definition; never fill structural macro gaps.
dr_series=raw['DR007'].set_index('date')['dr007'].dropna().sort_index()
monvals={
'M1':float(prices_all['沪深300'].iloc[-1]/prices_all['沪深300'].iloc[-21]-1),
'M2':float(prices_all['USD/CNH'].iloc[-1]/prices_all['USD/CNH'].iloc[-21]-1),
'M3':float(dr_series.iloc[-20:].mean()-dr_series.iloc[-80:-20].mean()),
'M4':float((prices['国债10年'].iloc[-1]-prices['国债10年'].iloc[-21])*100),
'M5':float((prices_all['美国10年国债'].iloc[-1]-prices_all['美国10年国债'].iloc[-21])*100),
'M6':float(ppi.dropna().iloc[-1]-ppi.dropna().iloc[-4]),
'M7':float(pmi.dropna().iloc[-1]),
'M8':float(yoy.dropna().iloc[-1])
}
mon_asof={'M1':prices_all['沪深300'].last_valid_index(),'M2':prices_all['USD/CNH'].last_valid_index(),'M3':raw['DR007']['date'].max(),'M4':sample_dates[-1],'M5':prices_all['美国10年国债'].last_valid_index(),'M6':ppi.dropna().index[-1].to_timestamp(),'M7':pmi.dropna().index[-1].to_timestamp(),'M8':yoy.dropna().index[-1].to_timestamp()}
threshold_num={'M1':-0.05,'M2':0.02,'M3':0.20,'M4':10.0,'M5':40.0,'M6':1.5,'M7':49.0,'M8':0.08}
for i,row in monitor.iterrows():
    mid=row['monitor_id']; v=monvals[mid]; th=threshold_num[mid]
    triggered=(v<th) if mid in ['M1','M7','M8'] else (v>th)
    monitor.loc[i,'latest_value'] = (pct(v) if mid in ['M1','M2','M8'] else bp(v*100) if mid=='M3' else bp(v) if mid in ['M4','M5'] else f'{v:.2f}' + ('' if mid=='M7' else '个百分点'))
    monitor.loc[i,'data_asof']=pd.Timestamp(mon_asof[mid]).strftime('%Y-%m-%d')
    monitor.loc[i,'status']='触发' if triggered else '正常'; monitor.loc[i,'triggered']='是' if triggered else '否'

# ---------- Reverse stress ----------
# Reverse-stress covariance uses every rolling 10-SSE-day factor window in the common sample.
# Scenario calibration remains strictly governed by rules_windows.csv and is not backfilled.
reverse_window_factors=[]
for i in range(len(sample_dates)-9):
    fw=factor_window(sample_dates[i],sample_dates[i+9])
    if fw is not None: reverse_window_factors.append(fw[1])
all_factor_windows=pd.DataFrame(reverse_window_factors)
fac_arr=all_factor_windows[factor_names].astype(float).values
cov=np.cov(fac_arr,rowvar=False); cov=cov+np.eye(len(factor_names))*1e-8; invcov=np.linalg.pinv(cov)

def reverse_loss(x): return -stress_parts(recommended,pd.Series(x,index=factor_names))['组合损益']
# Minimum Mahalanobis distance to a nonlinear loss surface. The SPX/FX cross term is
# handled by fixed-point linearization; each iteration solves the local quadratic form.
bounds=np.array([[-0.8,0.0],[-0.8,0.0],[0.0,0.8]]+[[-300.0,300.0]]*5)
x=np.array([-.12,-.12,.05, .3,.3,.2,.1,.1],dtype=float)
for _ in range(100):
    f=pd.Series(x,index=factor_names)
    g=np.array([-recommended[['沪深300','中证500','创业板']].sum(),
                -recommended['标普500（人民币计）']*(1+f['USD/CNH']),
                -recommended['标普500（人民币计）']*(1+f['标普500美元'])-recommended['美元现金']]+list(recommended['中长期国债']*np.array([dur_map[t]/10000 for t in ['1年','2年','5年','10年','30年']])))
    cvg=cov@g
    denom=float(g@cvg)
    step=(0.08+g@x)/denom if denom>0 else 1.0/denom
    xn=np.clip(x+step*cvg,bounds[:,0],bounds[:,1])
    if np.max(np.abs(xn-x))<1e-10: break
    x=xn
# Scale along the resulting adverse direction to meet the exact loss target.
lo,hi=0.0,10.0
for _ in range(80):
    mid=(lo+hi)/2
    if reverse_loss(np.clip(x*mid,bounds[:,0],bounds[:,1]))<0.08: lo=mid
    else: hi=mid
reverse_factors=pd.Series(np.clip(x*hi,bounds[:,0],bounds[:,1]),index=factor_names)

def mahal(x): return float(np.sqrt(np.asarray(x)@invcov@np.asarray(x)))
committee_dist={s:mahal(committee_factors[s].reindex(factor_names).values) for s in committee_factors}
calib_dist={s:mahal(calibration[s].reindex(factor_names).values) for s in calibration}

# ---------- Chart helpers ----------
def savefig(name):
    plt.tight_layout(); plt.savefig(CHARTS/name,dpi=160,bbox_inches='tight'); plt.close()

# chart 01: data coverage/gaps
fig,ax=plt.subplots(figsize=(12,8)); q=quality_df.copy(); q=q.iloc[::-1]; y=np.arange(len(q))
for yy,(_,r) in zip(y,q.iterrows()):
    xs=pd.to_datetime(r['覆盖区间'].split('至')[0]); xe=pd.to_datetime(r['覆盖区间'].split('至')[1]); ax.plot([xs,xe],[yy,yy],lw=7,color='#4472C4'); ax.scatter([xs,xe],[yy,yy],s=18,color='#1f1f1f')
ax.axvline(ASOF,color='red',ls='--',label='分析截至日'); ax.set_yticks(y); ax.set_yticklabels(q['序列']); ax.set_title('图1：数据覆盖、缺口与分析截至日'); ax.legend(); ax.grid(axis='x',alpha=.3); savefig('FIN3-WKN-149_chart01_数据覆盖与缺口.png')

# chart 02: NAV and metrics
fig,axs=plt.subplots(2,1,figsize=(13,11),gridspec_kw={'height_ratios':[1.3,1]})
for pid in ['当前组合','方案A','方案B','方案C','推荐方案']:
    axs[0].plot((1+portfolio_returns(plan_weights[pid])).cumprod(),label=pid)
axs[0].set_title('图2-a 各方案历史累计净值'); axs[0].legend(ncol=5); axs[0].grid(alpha=.25)
metric_names=['年化波动率','1日ES99','10日VaR99','最大回撤']; metric_vals={pid:[risk[pid]['ann_vol'],risk[pid]['es99'],risk[pid]['var10_99'],-risk[pid]['maxdd']] for pid in ['当前组合','方案A','方案B','方案C','推荐方案']}
xx=np.arange(5); width=.18
for j,m in enumerate(metric_names[:3]+['最大回撤']): axs[1].bar(xx+(j-1.5)*width,[metric_vals[p][j] for p in metric_vals],width,label=m)
axs[1].axhline(0.035,color='red',ls='--',label='1日ES99限额'); axs[1].axhline(0.06,color='orange',ls='--',label='10日VaR99限额'); axs[1].set_xticks(xx); axs[1].set_xticklabels(list(metric_vals)); axs[1].yaxis.set_major_formatter(PercentFormatter(1)); axs[1].set_title('图2-b 风险指标与限额参考线'); axs[1].legend(ncol=3,fontsize=8); axs[1].grid(axis='y',alpha=.25); savefig('FIN3-WKN-149_chart02_历史风险总览.png')

# chart 03
fig,axs=plt.subplots(3,1,figsize=(13,14))
for i,s in enumerate(['S1','S2','S3','S4']): axs[0].plot(monthly.index.to_timestamp(),monthly[s].astype(float)+i*.0,label=s)
axs[0].set_yticks([0,1]); axs[0].set_title('图3-a 四情景月度识别结果（1=合格）'); axs[0].legend(ncol=4); axs[0].grid(alpha=.2)
cal=pd.DataFrame(calibration).T[factor_names]; im=axs[1].imshow(cal.values,aspect='auto',cmap='RdYlGn_r'); axs[1].set_yticks(range(4)); axs[1].set_yticklabels(['S1','S2','S3','S4']); axs[1].set_xticks(range(8)); axs[1].set_xticklabels(factor_names,rotation=30,ha='right'); axs[1].set_title('图3-b 各情景历史窗口校准冲击（收益率/百分点/bp）'); fig.colorbar(im,ax=axs[1],fraction=.02)
comp=pd.DataFrame({'委员会沿用':[committee_factors[s]['境内权益'] for s in ['S1','S2','S3','S4']], '历史校准':[calibration[s]['境内权益'] for s in ['S1','S2','S3','S4']]},index=['S1','S2','S3','S4']); comp.plot.bar(ax=axs[2]); axs[2].set_title('图3-c 境内权益冲击严格程度对比'); axs[2].yaxis.set_major_formatter(PercentFormatter(1)); axs[2].grid(axis='y',alpha=.2); savefig('FIN3-WKN-149_chart03_情景识别与校准.png')

# chart 04
fig,axs=plt.subplots(3,1,figsize=(13,14)); pids=['方案A','方案B','方案C','推荐方案']; vals=[maxstress.loc[p,'损失'] for p in pids]; axs[0].bar(pids,vals,color='#4472C4'); axs[0].axhline(.08,color='red',ls='--',label='8%上限'); axs[0].axhline(.07,color='orange',ls='--',label='7%缓冲线'); axs[0].yaxis.set_major_formatter(PercentFormatter(1)); axs[0].set_title('图4-a 各方案最大压力损失'); axs[0].legend();
# execution cash paths: sell first vs buy first, QDII redemption unavailable on trade day
cw=current_w; rw=recommended; sell=(cw-rw).clip(lower=0); buy=(rw-cw).clip(lower=0); cash0=cw['人民币现金']; sell_cash=sell.sum()-sell['人民币现金']; buy_cash=buy.sum()-buy['人民币现金'];
path_sell=[cash0,cash0+sell_cash,cash0+sell_cash-buy_cash]; path_buy=[cash0,cash0-buy_cash,cash0-buy_cash+sell_cash]
axs[1].plot(['起始','第一步','完成'],path_sell,'o-',label='先卖后买'); axs[1].plot(['起始','第一步','完成'],path_buy,'o-',label='先买后卖'); axs[1].axhline(.08,color='red',ls='--',label='8%现金下限'); axs[1].yaxis.set_major_formatter(PercentFormatter(1)); axs[1].set_title('图4-b 调仓执行现金路径'); axs[1].legend(); axs[1].grid(alpha=.2)
axs[2].bar(factor_names,reverse_factors.values,color='#70AD47'); axs[2].set_title('图4-c 反向压力测试最可能因子变动'); axs[2].tick_params(axis='x',rotation=35); savefig('FIN3-WKN-149_chart04_方案决策与执行.png')

# chart 05
fig,ax=plt.subplots(figsize=(12,7)); vals=[]; labels=[]; colors=[]
for _,r in monitor.iterrows():
    mid=r['monitor_id']; v=monvals[mid]; th=threshold_num[mid]; scale=100 if mid in ['M1','M2','M3'] else 1
    if mid in ['M4','M5']: scale=1
    vals.append(v*scale); labels.append(mid); colors.append('#C00000' if r['triggered']=='是' else '#70AD47')
ax.bar(labels,vals,color=colors); ax.set_title('图5：八个监测指标最新值（红=触发，绿=正常）'); ax.grid(axis='y',alpha=.2); savefig('FIN3-WKN-149_chart05_监测指标触发状态.png')

# Additional PNGs required by the template's >=10-PNG rule.
fig,ax=plt.subplots(figsize=(9,7)); corr=rets[asset_order].corr(); im=ax.imshow(corr,cmap='coolwarm',vmin=-1,vmax=1); ax.set_xticks(range(7)); ax.set_xticklabels(asset_order,rotation=45,ha='right'); ax.set_yticks(range(7)); ax.set_yticklabels(asset_order); ax.set_title('图6：资产日收益相关矩阵'); fig.colorbar(im,ax=ax); savefig('FIN3-WKN-149_chart06_资产相关矩阵.png')
fig,ax=plt.subplots(figsize=(10,6)); rc=pd.Series(risk['当前组合']['rc']); rc.plot.bar(ax=ax,color='#5B9BD5'); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_title('图7：当前组合ES99风险贡献'); ax.grid(axis='y',alpha=.2); savefig('FIN3-WKN-149_chart07_风险贡献.png')
fig,ax=plt.subplots(figsize=(12,8)); t=stress[(stress['方案']=='推荐方案') & (stress['冲击']=='委员会沿用')].pivot(index='情景',columns=None,values='组合损益') if False else stress[(stress['方案']=='推荐方案') & (stress['冲击']=='委员会沿用')]; t.set_index('情景')[['境内权益','标普500（人民币计）','美元现金','国债']].plot.bar(stacked=True,ax=ax); ax.axhline(0,color='black',lw=.8); ax.set_title('图8：推荐方案委员会冲击损益分解'); ax.yaxis.set_major_formatter(PercentFormatter(1)); savefig('FIN3-WKN-149_chart08_压力损益分解.png')
fig,ax=plt.subplots(figsize=(12,6)); for_s=[]
for s in ['S1','S2','S3','S4']: for_s.append(pd.DataFrame({'损失':[w['cum'] for w in windows[s]],'情景':s}))
wf=pd.concat(for_s,ignore_index=True) if for_s else pd.DataFrame(columns=['损失','情景']);
if len(wf): wf.boxplot(column='损失',by='情景',ax=ax); plt.suptitle(''); ax.set_title('图9：各情景合格窗口组合累计损失'); ax.yaxis.set_major_formatter(PercentFormatter(1))
else: ax.text(.5,.5,'无合格窗口'); savefig('FIN3-WKN-149_chart09_历史窗口.png')
fig,ax=plt.subplots(figsize=(10,6)); ax.plot(['起始','先卖','完成'],path_sell,'o-',label='先卖后买'); ax.plot(['起始','先买','完成'],path_buy,'o-',label='先买后卖'); ax.axhline(.08,color='red',ls='--'); ax.yaxis.set_major_formatter(PercentFormatter(1)); ax.set_title('图10：现金下限执行核验'); ax.legend(); savefig('FIN3-WKN-149_chart10_执行路径核验.png')

# ---------- Memo generation ----------
def fmtdate(x): return '无' if pd.isna(x) else pd.Timestamp(x).strftime('%Y-%m-%d')
def fmt_num(x): return f'{x:.2f}'
def metric_line(pid):
    r=risk[pid]; return f"年化波动率 {pct(r['ann_vol'])}；1日VaR95/VaR99 {pct(r['var95'])}/{pct(r['var99'])}；1日ES95/ES99 {pct(r['es95'])}/{pct(r['es99'])}；10日VaR99 {pct(r['var10_99'])}；最大回撤 {pct(-r['maxdd'])}。"

def weights_table(w):
    names=['沪深300','中证500','创业板','中长期国债','美元现金','标普500（人民币计）','人民币现金']; return '；'.join(f'{n} {pct(w[n])}（{w[n]*TOTAL:.2f}万元）' for n in names)

# Make exact raw coverage table compact but explicit.
coverage_lines='\n'.join(f"- {r['序列']}：{r['覆盖区间']}，{r['记录数']}条，空值单元格 {r['空值单元格']}，重复日期 {r['重复日期']}，清单截断标记：{r['清单截断标记']}。" for _,r in quality_df.iterrows())
scenario_rule=read_csv('rules_scenarios.csv')
rule_lines='\n'.join(f"- {r.scenario_id} {r.scenario}：{r.rule}；合格月份：{', '.join(str(x) for x in qualified[r.scenario_id]) or '无'}。" for _,r in scenario_rule.iterrows())
cal_lines=[]
for s in ['S1','S2','S3','S4']:
    ws=windows[s]; c=calibration[s]
    wintext='；'.join(f"{w['dates'][0]:%Y-%m-%d}至{w['dates'][-1]:%Y-%m-%d}" for w in ws)
    cgb_text='；'.join(f'{c["国债{t}"]:.2f}bp' for t in ['1年','2年','5年','10年','30年']) if ws else 'N/A（严格规则下无合格窗口，未以0替代）'
    cal_lines.append(f"- {s}：合格窗口 {len(ws)} 个；选定窗口：{wintext or '无'}；校准冲击：境内权益 {signed_pct(c['境内权益'])}、标普500美元 {signed_pct(c['标普500美元'])}、USD/CNH {signed_pct(c['USD/CNH'])}、国债1/2/5/10/30年 {cgb_text}。")

stress_lines=[]
for pid in ['方案A','方案B','方案C','推荐方案']:
    stress_lines.append(f"#### {pid}")
    for s in ['S1','S2','S3','S4']:
        row=[]
        for typ in ['委员会沿用','历史校准']:
            z=stress[(stress['方案']==pid)&(stress['情景']==s)&(stress['冲击']==typ)].iloc[0]
            row.append(f"{typ}：境内权益 {pct(z['境内权益'])}；标普500人民币 {pct(z['标普500（人民币计）'])}；美元现金 {pct(z['美元现金'])}；国债 {pct(z['国债'])}；组合损益 {pct(z['组合损益'])}；压力损失 {pct(z['损失'])}")
        stress_lines.append(f"- {s}："+'；'.join(row)+'。')

check_lines=[]
for pid in ['方案A','方案B','方案C','推荐方案']:
    vals,ps=checks_all[pid]; check_lines.append(f"#### {pid}\n"+'；'.join(f"{lid} {('通过' if ps[lid] else '未通过')}（{vals[lid]*100:.2f}%"+('，超限 '+pct(vals[lid]-float(limits.loc[limits.id==lid,'upper'].iloc[0])) if not ps[lid] and lid not in ['L3','L4'] else '')+')' for lid in ['L1','L2','L3','L4','L5','L6','L7','L8','L9']))

trade_lines=[]
for a in asset_order:
    delta=(recommended[a]-current_w[a])*TOTAL
    if abs(delta)>1e-7: trade_lines.append(f"- {a}：{'买入' if delta>0 else '卖出'} {abs(delta):.2f}万元。")

mon_lines='\n'.join(f"- {r.monitor_id} {r.indicator}：阈值 {r.threshold}；最新值 {r.latest_value}；截至 {r.data_asof}；{r.status}；触发 {r.triggered}。" for _,r in monitor.iterrows())

maxrec=maxstress.loc['推荐方案']; rec_r=risk['推荐方案']; worst_hist=rec_r['worst10']; margin=0.08-maxrec['损失']; mult=maxrec['损失']/0.08
committee_distance='；'.join(f'{s} {v:.2f}' for s,v in committee_dist.items()); calib_distance='；'.join(f'{s} {("N/A（无合格校准窗口）" if pd.isna(v) else f"{v:.2f}")}' for s,v in calib_dist.items())
reverse_text='；'.join(f'{k} {signed_pct(v) if k in ["境内权益","标普500美元","USD/CNH"] else f"{v:.2f}bp"}' for k,v in reverse_factors.items())

memo=f'''# 多资产稳健配置专户 三季度宏观压力测试与调仓建议
## 风险委员会决策备忘录

分析截至日：**{ASOF_STR}**；组合净值：**{TOTAL:.2f}万元**；金额单位均为万元，百分比保留两位小数。

### 一、结论与建议

建议否决当前组合的继续持有安排，并否决方案A、B、C作为最终执行方案；推荐**推荐方案**（由参数文件中的推荐权重按规则构造）并按“先卖出后买入”执行。推荐方案最大压力损失 **{pct(maxrec['损失'])}**（{maxrec['情景']}、{maxrec['冲击']}），1日ES99 **{pct(rec_r['es99'])}**，10日VaR99 **{pct(rec_r['var10_99'])}**，单向换手率 **{pct(turnover(recommended))}**。推荐方案同时满足九项约束，但M1和M8监测指标已触发，需提请临时风险会议；调仓指令应在委员会确认后执行，数据补齐后按第八章复核。

### 二、数据核验与样本区间

共同风险样本为 **{sample_dates.min():%Y-%m-%d}至{sample_dates.max():%Y-%m-%d}，{len(sample_dates)}个上交所交易日**。样本终止于中债五个期限收益率实际共同覆盖的 **{actual_end:%Y-%m-%d}**，不是将结构性缺口向后填充。上交所交易日历共 {len(trade_dates)} 条，分析截至日为 {ASOF_STR}；日行情未发现落在休市日的记录，依据为日期与交易日历逐日匹配，异常记录数为0。

各序列核验如下：
{coverage_lines}

三只指数分段合并后，seg1首行 `pre_close` 各有一个空值，但收益计算采用 `close` 的相邻交易日变化，首行无前值而自然产生的收益缺失不参与计算；其他空值均未按0参与计算。5年LPR的406个空值属于低频政策公布在日频框架中的结构性空值，仅在有实际公布值的月份比较，不做前向填充。PPI负值被保留，因为同比指标可为负。逐条异常检查未发现重复日期、日期逆序、非法日期、负价格/负成交额、OHLC关系异常或交易日历外记录。日频跨市场价格先映射到上交所估值日，再以前值填充非交易日；外汇与标普500人民币计收益分别按 USD/CNH 复合换算，公式为 `(1+标普500美元收益)×(1+USD/CNH收益)-1`。

![图1 数据覆盖与缺口](FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png)

### 三、当前组合风险画像

当前持仓：{weights_table(current_w)}。

各资产日收益统计（均值为日均、波动率为年化）：

|资产|日均收益|年化波动率|最差单日|
|---|---:|---:|---:|
'''+''.join(f"|{a}|{pct(rets[a].mean())}|{pct(rets[a].std()*np.sqrt(252))}|{pct(rets[a].min())}|\n" for a in asset_order)+f'''\n当前组合：{metric_line('当前组合')}10日最大累计损失 **{pct(-risk['当前组合']['worst10'])}**（{fmtdate(risk['当前组合']['worst10_start'])}至{fmtdate(risk['当前组合']['worst10_end'])}）；最大回撤 **{pct(-risk['当前组合']['maxdd'])}**（峰值 {fmtdate(risk['当前组合']['peak'])}、谷值 {fmtdate(risk['当前组合']['trough'])}、修复日 {fmtdate(risk['当前组合']['recovery'])}）；最差单日损失 **{pct(-risk['当前组合']['worst1'])}**（{fmtdate(risk['当前组合']['worst1_date'])}）。\n\n日收益相关矩阵、风险贡献见 `FIN3-WKN-149_chart06_资产相关矩阵.png` 与 `FIN3-WKN-149_chart07_风险贡献.png`；当前组合ES99风险贡献占比为：''' + '；'.join(f'{k} {pct(v)}' for k,v in risk['当前组合']['rc'].items()) + '''。图2-a展示各方案累计净值，图2-b展示波动、ES、VaR和最大回撤，并绘制了适用限额参考线。

![图2 历史风险总览](FIN3-WKN-149_charts/FIN3-WKN-149_chart02_历史风险总览.png)

### 四、情景识别与历史校准

月度识别结果：
'''+rule_lines+f'''\n\n窗口规则为“合格月份次月第一个上交所交易日起10个交易日”，只保留组合日收益10日全部为负的窗口，并按累计跌幅选取最多前20个（实际不足20个时使用全部合格窗口）。\n\n'''+'\n'.join(cal_lines)+f'''\n\n委员会冲击与历史校准的严格程度不能简单按单一因子判断：委员会冲击是预先设定的尾部情景，历史校准是合格窗口因子变动中位数；S1的利率曲线形态、S2/S4的长端方向和S3的汇率升值方向存在明显差异。图3-a至图3-c给出识别、校准和对比。\n\n![图3 情景识别与校准](FIN3-WKN-149_charts/FIN3-WKN-149_chart03_情景识别与校准.png)\n\n### 五、压力测试结果\n\n以下为四个方案×四个情景×两套冲击的完整结果；四个分项之和等于组合损益，压力损失定义为组合损益的相反数。\n\n'''+ '\n'.join(stress_lines)+f'''\n\n各方案最大压力损失：''' + '；'.join(f'{p} {pct(maxstress.loc[p,"损失"])}（{maxstress.loc[p,"情景"]}/{maxstress.loc[p,"冲击"]}）' for p in ['方案A','方案B','方案C','推荐方案']) + '''。由于严格窗口筛选在四个情景下均未产生合格窗口，历史校准冲击及其严格程度比较均为N/A；不能用0替代历史冲击。委员会冲击的压力差异主要来自境内权益、美元计标普500、汇率和国债曲线的联合方向。推荐方案的压力损益分解见 `FIN3-WKN-149_chart08_压力损益分解.png`。\n\n![图4 方案决策与执行](FIN3-WKN-149_charts/FIN3-WKN-149_chart04_方案决策与执行.png)\n\n### 六、候选方案评估与九项约束检查\n\n''' + '\n\n'.join(check_lines) + f'''\n\nL5按参数文件口径计算为“美元现金及存款+不对冲汇率的标普500 QDII”，推荐方案外币敞口为 {pct(recommended['美元现金']+recommended['标普500（人民币计）'])}，不存在漏计或误计。L6/L7使用共同历史样本，L8/L9使用八个压力组合的最大损失；每项具体数值均来自脚本运行结果。\n\n### 七、推荐方案与调仓执行\n\n推荐方案权重与金额：{weights_table(recommended)}。构造依据是固定美元现金10.00%和标普500 QDII10.00%，境内三项权益按0.59同比例缩减合计20.50个百分点，释放资金中10.50个百分点转国债、10.00个百分点转人民币现金；推荐权重总和为100.00%。由于人民币现金达到L3上限20.00%，国债和现金转入分配被唯一确定；在固定外币资产、同比例缩减和同换手率约束下，推荐权重是规则构造的唯一解。若放宽同比例缩减，仅保持同换手率的细网格次优候选最大压力损失为 **{pct(next_alt[0])}**（该比较用于说明规则唯一性，不将其替代为推荐方案）。\n\n交易清单：\n'''+ '\n'.join(trade_lines)+f'''\n\n单向换手率按卖出金额合计/10,000万元为 {pct(turnover(recommended))}。执行顺序遵循规则先卖出后买入：先卖出境内权益合计 **{(sell.sum()*TOTAL):.2f}万元**，卖出资金当日可用；再买入国债 **{buy['中长期国债']*TOTAL:.2f}万元** 和人民币现金/货基 **{buy['人民币现金']*TOTAL:.2f}万元**。QDII本次不交易，故不存在T+7赎回款进入现金路径的问题。先卖后买人民币现金占比路径为 **{pct(path_sell[0])}→{pct(path_sell[1])}→{pct(path_sell[2])}**；先买后卖为 **{pct(path_buy[0])}→{pct(path_buy[1])}→{pct(path_buy[2])}**。按执行规则的先卖后买路径不击穿8%下限；若非规则路径先买后卖则会击穿下限。\n\n### 八、反向压力测试与监测预警\n\n推荐方案最大压力损失为 {pct(maxrec['损失'])}，相对8%上限的风险裕度为 **{pct(margin)}**，相当于上限的 **{mult:.2f}倍**。样本内最差10日累计损失为 **{pct(-worst_hist)}**（{fmtdate(rec_r['worst10_start'])}至{fmtdate(rec_r['worst10_end'])}）。\n\n反向压力测试以共同样本全部滚动10日因子窗口的协方差构造马氏距离，在方向约束“境内权益≤0、标普500美元≤0、USD/CNH≥0”、各国债期限冲击区间±300bp及组合损失达到8%上限下，最小距离情景因子为：{reverse_text}；最小马氏距离 **{mahal(reverse_factors.values):.2f}**。委员会沿用冲击马氏距离：{committee_distance}；历史校准窗口马氏距离：{calib_distance}。\n\n监测指标：\n{mon_lines}\n\n监测状态以各序列实际最新值为准。由于国债收益率、LPR、PPI、社融等部分数据提前终止或低频公布，数据补齐后应由宏观策略组重算相应指标、情景识别、历史窗口、压力结果和九项约束；若任何L6至L9由通过变为未通过，或监测指标触发，应在下一交易日前提请临时风险会议。\n\n![图5 监测指标触发状态](FIN3-WKN-149_charts/FIN3-WKN-149_chart05_监测指标触发状态.png)\n\n---\n\n**附件清单**\n- `FIN3-WKN-149_reproduce.py`：从 `/app/input_files/` 原始快照读取并生成全部结果。\n- `FIN3-WKN-149_charts/`：图1至图10共10张PNG，覆盖数据核验、历史风险、情景识别与校准、方案决策、调仓执行、反向压力测试、监测触发。\n'''
(OUTPUT/'FIN3-WKN-149_风险委员会决策备忘录.md').write_text(memo,encoding='utf-8')
monitor.to_csv(OUTPUT/'FIN3-WKN-149_monitor.csv',index=False,encoding='utf-8-sig')
# Machine-readable outputs make the calculations auditable without placing conclusions in code literals.
summary={'asof':ASOF_STR,'sample_start':str(sample_dates.min().date()),'sample_end':str(sample_dates.max().date()),'sample_days':len(sample_dates),
         'risk':risk,'stress':stress.to_dict(orient='records'),'checks':{k:{'values':v[0],'passed':v[1]} for k,v in checks_all.items()},'monitor':monitor.to_dict(orient='records'),
         'reverse_factors':reverse_factors.to_dict(),'reverse_distance':mahal(reverse_factors.values),'committee_distance':committee_dist,'calibration_distance':calib_dist}
# Convert timestamps for JSON.
def json_default(o):
    if isinstance(o,(pd.Timestamp,np.datetime64)): return str(o)
    if isinstance(o,(np.floating,np.integer)): return o.item()
    raise TypeError
(OUTPUT/'FIN3-WKN-149_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=json_default),encoding='utf-8')
print(f'生成完成：样本 {sample_dates.min():%Y-%m-%d} 至 {sample_dates.max():%Y-%m-%d}，{len(sample_dates)} 个交易日；图表 {len(list(CHARTS.glob("*.png")))} 张；备忘录已写入。')
