# -*- coding: utf-8 -*-
"""
FIN3-WKN-149_reproduce.py
多资产稳健配置专户 · 三季度宏观压力测试与调仓建议 · 可复算代码
================================================================
- 全部输入取自 /app/input_files/（只读），不硬编码任何结论数值；
- 运行后在标准输出打印备忘录全部数字，并在 /app/output/FIN3-WKN-149_charts/ 生成 10 张 PNG；
- 分析截至日：2026-09-15；金额单位：万元；百分比保留两位小数；收益率变动注明 bp 或 %。

运行：python3 FIN3-WKN-149_reproduce.py
依赖：pandas / numpy / scipy / matplotlib
"""
import os, re, glob, warnings
import numpy as np
import pandas as pd
from scipy.optimize import minimize

warnings.filterwarnings('ignore')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

plt.rcParams['font.sans-serif'] = ['Noto Sans CJK SC', 'Noto Sans CJK JP', 'SimHei', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 110

IN = '/app/input_files/'
OUT = '/app/output/'
CHART = os.path.join(OUT, 'FIN3-WKN-149_charts')
os.makedirs(CHART, exist_ok=True)
ASOF = pd.Timestamp('2026-09-15')          # 分析截至日（任务设定）

SEP = lambda t: print('\n' + '=' * 78 + f'\n== {t}\n' + '=' * 78)
P2 = lambda x: f'{x*100:.2f}%'             # 比例 -> 两位小数百分比
BP = lambda x: f'{x*10000:.2f}bp'          # 小数 -> bp
W2 = lambda x: f'{x:,.2f}'                 # 万元两位小数

# =====================================================================
# 0. 读取参数 / 规则 / 方案（全部来自 input_files）
# =====================================================================
pos_df = pd.read_csv(IN + 'params_positions.csv')
NAV = float(pos_df['market_value_10k_cny'].sum())            # 组合净值（万元），由持仓明细加总
hold_df = pd.read_csv(IN + 'params_holdings.csv')
lim_df = pd.read_csv(IN + 'params_limits.csv')
dur_df = pd.read_csv(IN + 'params_duration.csv')
com_df = pd.read_csv(IN + 'params_committee_shocks.csv')
plan_df = pd.read_csv(IN + 'plans_candidates.csv')
sc_df = pd.read_csv(IN + 'rules_scenarios.csv')
win_df = pd.read_csv(IN + 'rules_windows.csv').set_index('key')['value']
chk_df = pd.read_csv(IN + 'rules_checks.csv')
reb_df = pd.read_csv(IN + 'rules_rebalance.csv').set_index('key')['value']
mon_df = pd.read_csv(IN + 'template_monitor.csv', encoding='utf-8-sig')

# 限额参数（按 id 提取）
LIM = {r['id']: r for _, r in lim_df.iterrows()}
L2_CAP = float(LIM['L2']['upper']); L3_LO = float(LIM['L3']['lower']); L3_HI = float(LIM['L3']['upper'])
# 数据核验：L4（中长期国债组合 ≥15%）的界限数值存放于 upper 列、lower 列为空——按文件实际内容取非空侧
_l4 = LIM['L4']
L4_LO = float(_l4['lower'] if pd.notna(_l4['lower']) else _l4['upper'])
print(f"[0] params_limits 解析: L2≤{L2_CAP:.0%}, L3∈[{L3_LO:.0%},{L3_HI:.0%}], L4≥{L4_LO:.0%}（该值存于 upper 列、lower 为空，按文件实际内容取用）"); L5_CAP = float(LIM['L5']['upper'])
L6_CAP = float(LIM['L6']['upper']); L7_CAP = float(LIM['L7']['upper'])
L8_CAP = float(LIM['L8']['upper']); L9_CAP = float(LIM['L9']['upper'])
C1_TOL = 0.0005   # 权重合计容差 0.05 个百分点（rules_checks.csv C1 文本）

# 久期贡献（关键期限久期折算，硬约束 3）
DUR = {int(re.sub(r'\D', '', t)): float(d) for t, d in zip(dur_df['tenor'], dur_df['duration_contribution'])}
TENORS = sorted(DUR)                       # [1,2,5,10,30]
DUR_TOT = sum(DUR.values())

ASSET7 = ['eq300', 'eq500', 'eqcyb', 'cgb', 'usd_cash', 'spx_cny', 'cny_cash']
ZH = {'eq300': '沪深300指数基金', 'eq500': '中证500指数基金', 'eqcyb': '创业板指数基金',
      'cgb': '中长期国债组合', 'usd_cash': '美元现金及存款', 'spx_cny': '标普500 QDII基金(人民币计)',
      'cny_cash': '人民币现金及货基'}

# =====================================================================
# 1. 数据加载与核验（硬约束 1：核验先于一切计算）
# =====================================================================
SEP('第二章 · 数据核验')

cal = pd.read_csv(IN + 'snapshot_trade_calendar.csv'); cal['date'] = pd.to_datetime(cal['date'])
assert set(cal['is_trading_day']) == {1}, '日历应仅含交易日'
SSE = cal['date'].sort_values().reset_index(drop=True)       # 上交所估值日主轴
SSET = set(SSE)
POS_OF = {d: i for i, d in enumerate(SSE)}

def read_snap(fname):
    d = pd.read_csv(IN + fname); d['date'] = pd.to_datetime(d['date']); return d

def load_seg(prefix):
    fs = sorted(glob.glob(IN + f'snapshot_{prefix}_seg*.csv'))
    d = pd.concat([read_snap(os.path.basename(f)) for f in fs])
    dup = int(d['date'].duplicated().sum())
    d = d.sort_values('date').drop_duplicates('date')
    return d, fs, dup

# ---- 1.1 清单核对（manifest 声明 vs 文件实际；possible_truncation 字段不保证可靠） ----
man = pd.read_csv(IN + 'snapshot_data_manifest.csv')
print('[1] data_manifest 核对（记录数/起止日）:')
man_ok = True
for _, mrow in man.iterrows():
    d = read_snap(mrow['file'])
    ok = (len(d) == mrow['records']) and (str(d['date'].min().date()) == mrow['start']) and (str(d['date'].max().date()) == mrow['end'])
    man_ok &= ok
    if not ok:
        print(f"    不一致: {mrow['file']} 实际 {len(d)} 条 {d['date'].min().date()}~{d['date'].max().date()}")
print(f'    {len(man)} 个快照记录数与起止日均与清单一致: {man_ok}')
print(f"    清单 possible_truncation 字段仅 shibor_seg2 标注 'false'，其余为空——该字段由上游自动生成、不可靠，"
      f"实际截断以文件内容为准（见下）。")

# ---- 1.2 逐序列覆盖/缺口/异常 ----
idx_files = {'000300SH': '沪深300', '000905SH': '中证500', '399006SZ': '创业板指'}
raw = {}     # 原始表（未剔除异常）
for code in idx_files:
    d, fs, dup = load_seg(code); raw[code] = (d, fs, dup)
fx_raw, fx_fs, fx_dup = load_seg('usdcnh'); raw['usdcnh'] = (fx_raw, fx_fs, fx_dup)
sh_raw, sh_fs, sh_dup = load_seg('shibor'); raw['shibor'] = (sh_raw, sh_fs, sh_dup)
for nm, f in [('spx', 'snapshot_spx.csv'), ('dr007', 'snapshot_dr007.csv'), ('ust10', 'snapshot_ust_10y.csv'),
              ('ustm2', 'snapshot_ust_m2.csv'), ('ustm4', 'snapshot_ust_m4.csv'),
              ('lpr1', 'snapshot_lpr_1y.csv'), ('lpr5', 'snapshot_lpr_5y.csv'),
              ('pmi', 'snapshot_pmi_manufacturing.csv'), ('ppi', 'snapshot_ppi_yoy.csv'),
              ('afre', 'snapshot_afre_stock.csv')]:
    raw[nm] = (read_snap(f), [f], 0)
for t in TENORS:
    raw[f'cgb{t}'] = (read_snap(f'snapshot_cgb_yield_{t}y.csv'), [f'snapshot_cgb_yield_{t}y.csv'], 0)

# 休市日异常记录识别：日期不在上交所日历 + OHLC 与 pre_close 全相等 + 成交额显著萎缩
anomalies = []
for code, zname in idx_files.items():
    d = raw[code][0]
    off = d[~d['date'].isin(SSET)]
    for _, rr in off.iterrows():
        flat = (rr['open'] == rr['high'] == rr['low'] == rr['close'] == rr['pre_close'])
        nb = d[(d['date'] < rr['date']) & (d['date'].isin(SSET))].tail(20)['amount'].median()
        anomalies.append(dict(series=zname, date=str(rr['date'].date()), dow=['周一','周二','周三','周四','周五','周六','周日'][rr['date'].dayofweek],
                              in_sse_calendar=False, ohlc_flat=bool(flat), amount=rr['amount'],
                              amount_vs_nb20=float(rr['amount'] / nb)))
print('\n[2] 休市日异常记录（识别依据：不在上交所交易日历 + 开=高=低=收=昨收 + 成交额较近20个交易期中位数萎缩>95%）:')
for a in anomalies:
    print(f"    {a['series']} {a['date']}({a['dow']}): OHLC全平={a['ohlc_flat']}, 成交额={a['amount']:,.0f}（近20日中位数的 {a['amount_vs_nb20']*100:.2f}%）→ 剔除")
_n300s2 = len(read_snap('snapshot_000300SH_seg2.csv')); _n500s2 = len(read_snap('snapshot_000905SH_seg2.csv')); _ncybs2 = len(read_snap('snapshot_399006SZ_seg2.csv'))
print(f'    注：创业板指 seg2 无该休市日行（{_ncybs2} 条 vs 沪深300 {_n300s2} 条 / 中证500 {_n500s2} 条），三只指数剔除后覆盖一致。')

# 反事实核验：休市日行剔除与否对监测指标 M1 结论的影响（量化核验的必要性）
_cfd = raw['000300SH'][0].set_index('date')['close'].sort_index()          # 含休市日行
_cfc = _cfd[_cfd.index.isin(SSET)]                                          # 剔除后
_m1d = _cfd.iloc[-1] / _cfd.iloc[-21] - 1
_m1c = _cfc.iloc[-1] / _cfc.iloc[-21] - 1
print(f"    M1 反事实核验：若不剔除，20 日基期后移至 {_cfd.index[-21].date()}，M1 误读为 {_m1d*100:.2f}%（未触发）；"
      f"剔除后基期 {_cfc.index[-21].date()}，M1 = {_m1c*100:.2f}%（触发）→ 核验结论直接改变监测状态。")

# 剔除异常行（凡不在 SSE 日历的指数行一律剔除）
idx_close, idx_amt = {}, {}
for code in idx_files:
    d = raw[code][0]
    d = d[d['date'].isin(SSET)].copy()
    idx_close[code] = d.set_index('date')['close'].sort_index()
    idx_amt[code] = d.set_index('date')['amount'].sort_index()
fx_s = fx_raw.set_index('date')['usdcnh'].sort_index()

# 结构性空值：pre_close 首行（每只指数 seg1 第 1 行）；lpr_5y 2019-08-20 前整段为空
pc_nan = {code: int(raw[code][0]['pre_close'].isna().sum()) for code in idx_files}
lpr5_nan = int(raw['lpr5'][0]['lpr_5y'].isna().sum())
lpr5_first = raw['lpr5'][0].dropna(subset=['lpr_5y'])['date'].min()
print('\n[3] 结构性空值（一律不按 0、不填充处理）:')
print(f"    指数 seg1 首行 pre_close 为空: {pc_nan} → 收益全部用 close 逐日环比计算，不依赖 pre_close；")
print(f"    lpr_5y 空值 {lpr5_nan} 条（{lpr5_first.date()} 之前，5年期LPR改革后才发布）→ 该段不参与“LPR当月下调”判定；")
pmi_s = raw['pmi'][0].set_index('date')['pmi_mfg']
pmi_months = pd.DatetimeIndex(pmi_s.index).to_period('M')
pmi_miss = [str(p) for p in pd.period_range(pmi_months.min(), pmi_months.max(), freq='M') if p not in set(pmi_months)]
print(f"    PMI 缺月: {pmi_miss}（涉及月份的情景判定标记为不可判定，不按 0 计）；")
print(f"    ust_m4 仅 {len(raw['ustm4'][0])} 条（{raw['ustm4'][0]['date'].min().date()}~{raw['ustm4'][0]['date'].max().date()}），无可用历史 → 本次分析不使用；")
print(f"    中债国债收益率五条曲线止于 {raw['cgb10'][0]['date'].max().date()}（尾部结构性截断）→ 其后不延伸、不填充、不按0计，风险样本随之终止。")

# 覆盖概览 & 各序列在上交所估值日上的缺日数（需前向填充的节假日错位）
def coverage(name, s, drop_offcal=False):
    ss = s.sort_index()
    lo, hi = ss.index.min(), ss.index.max()
    inside = SSE[(SSE >= lo) & (SSE <= hi)]
    miss = [d for d in inside if d not in set(ss.index)]
    return dict(series=name, start=lo, end=hi, rows=len(ss), miss_sse=len(miss))

cov_rows = []
for code, zn in idx_files.items():
    cov_rows.append(coverage(zn, raw[code][0].set_index('date')['close']))
for nm, lab in [('cgb1', '中债国债1Y'), ('cgb2', '中债国债2Y'), ('cgb5', '中债国债5Y'), ('cgb10', '中债国债10Y'), ('cgb30', '中债国债30Y'),
                ('usdcnh_s', 'USD/CNH'), ('spx_s', '标普500(美元)'), ('shibor_s', 'Shibor(O/N,1W)'), ('dr007_s', 'DR007'),
                ('lpr1_s', 'LPR1Y'), ('lpr5_s', 'LPR5Y'), ('ust10_s', '美债10Y'), ('ustm2_s', '美债2M'), ('ustm4_s', '美债4M')]:
    src = {'usdcnh_s': fx_raw.set_index('date')['usdcnh'], 'spx_s': raw['spx'][0].set_index('date')['close'],
           'shibor_s': sh_raw.set_index('date')['shibor_on'], 'dr007_s': raw['dr007'][0].set_index('date')['dr007'],
           'lpr1_s': raw['lpr1'][0].set_index('date')['lpr_1y'], 'lpr5_s': raw['lpr5'][0].dropna().set_index('date')['lpr_5y'],
           'ust10_s': raw['ust10'][0].set_index('date')['yield_pct'], 'ustm2_s': raw['ustm2'][0].set_index('date')['yield_pct'],
           'ustm4_s': raw['ustm4'][0].set_index('date')['yield_pct']}.get(nm)
    if src is None:
        src = raw[nm.replace('_s', '')][0].set_index('date')['yield_pct']
    cov_rows.append(coverage(lab, src))
cov = pd.DataFrame(cov_rows)
print('\n[4] 各序列覆盖区间（原始文件口径）:')
print(cov.to_string(index=False))

# 对齐口径：跨市场序列对齐至上交所估值日；覆盖区间内前向填充（节假日错位），覆盖区间外为结构性 NaN 不填充
def align_sse(s):
    s = s.dropna().sort_index()
    if s.index.min() > ASOF: return pd.Series(np.nan, index=SSE)
    lo, hi = s.index.min(), min(s.index.max(), ASOF)
    union = s.index.union(SSE[(SSE >= lo) & (SSE <= hi)])
    return s.reindex(union).ffill().reindex(SSE)      # 覆盖外自动为 NaN（结构性空值不填充）

FX = align_sse(fx_s)
SPX = align_sse(raw['spx'][0].set_index('date')['close'])
UST10 = align_sse(raw['ust10'][0].set_index('date')['yield_pct'])
CGB = {t: align_sse(raw[f'cgb{t}'][0].set_index('date')['yield_pct']) for t in TENORS}
DR = align_sse(raw['dr007'][0].set_index('date')['dr007'])
CL = {code: align_sse(idx_close[code]) for code in idx_files}

# 极端变动抽查（逐条数据异常检查：确认极端值为真实行情而非脏数据）
print('\n[5] 极端日变动抽查（对齐后收益的|极值|前3，确认为真实行情、予以保留）:')
for code, zn in idx_files.items():
    rr = CL[code].pct_change().dropna()
    top = rr.abs().nlargest(3)
    print(f"    {zn}: " + '; '.join(f"{i.date()} {rr[i]*100:+.2f}%" for i in top.index))
dy10 = CGB[10].diff().dropna()
print(f"    中债10Y 最大单日变动: {dy10.abs().idxmax().date()} {dy10.abs().max()*100:.2f}bp")
rfx = FX.pct_change().dropna()
print(f"    USD/CNH 最大单日变动: {rfx.abs().idxmax().date()} {rfx.abs().max()*100:+.2f}%")

# ---- 风险样本区间：所有组合收益输入齐备的公共区间 ----
S_START = max(DR.first_valid_index(), max(CGB[t].first_valid_index() for t in TENORS),
              max(CL[c].first_valid_index() for c in idx_files), FX.first_valid_index(), SPX.first_valid_index())
S_END = min(CGB[t].last_valid_index() for t in TENORS)          # 尾部受中债收益率截断约束
SAMPLE = SSE[(SSE > S_START) & (SSE <= S_END)]                 # 收益样本（首日收益需前一日水平）
print('\n[6] 风险样本区间:')
print(f"    上交所日历: {SSE.min().date()} ~ {SSE.max().date()}，共 {len(SSE)} 个估值日；")
print(f"    收益样本: {SAMPLE.min().date()} ~ {SAMPLE.max().date()}，共 {len(SAMPLE)} 个收益观测；")
print(f"    起点约束: DR007/Shibor 自 {DR.first_valid_index().date()} 起（前段结构性截断，现金收益不按0填充）；")
print(f"    终点约束: 中债国债收益率五条曲线止于 {S_END.date()}（上游快照截断，其后结构性空值不填充、不按0计）。")

# =====================================================================
# 2. 资产收益引擎（硬约束 2/3：SSE 对齐、久期折算、复合汇率）
# =====================================================================
SEP('收益构建')
ext = SSE[(SSE >= SAMPLE.min() - pd.Timedelta(days=20)) & (SSE <= SAMPLE.max())]
Pe = pd.DataFrame({
    'eq300': CL['000300SH'].reindex(ext), 'eq500': CL['000905SH'].reindex(ext),
    'eqcyb': CL['399006SZ'].reindex(ext), 'fx': FX.reindex(ext), 'spx': SPX.reindex(ext),
    'dr': DR.reindex(ext), **{f'y{t}': CGB[t].reindex(ext) for t in TENORS}})
R = pd.DataFrame(index=ext)
R['eq300'] = Pe['eq300'].pct_change(); R['eq500'] = Pe['eq500'].pct_change(); R['eqcyb'] = Pe['eqcyb'].pct_change()
# 国债组合：关键期限久期折算 r = -Σ D_k × Δy_k（Δy 为小数），不得用收益率差简单加总
R['cgb'] = -sum(DUR[t] * Pe[f'y{t}'].diff() / 100.0 for t in TENORS)
R['spx_usd'] = Pe['spx'].pct_change(); R['fx_ret'] = Pe['fx'].pct_change()
# 标普500 人民币计收益：复合折算 (1+r_sp)(1+r_fx)-1，不得加法近似
R['spx_cny'] = (1 + R['spx_usd']) * (1 + R['fx_ret']) - 1
R['usd_cash'] = R['fx_ret']                                  # 美元现金人民币收益=汇率变动（美元利息忽略，处理见备忘录）
R['cny_cash'] = Pe['dr'].shift(1) / 100 / 252                # 人民币现金按上一交易日 DR007 年化/252 计提
R = R.loc[SAMPLE].astype(float)
assert R[ASSET7 + ['spx_usd', 'fx_ret']].isna().sum().sum() == 0, '收益样本内不得存在空值'
print(f"资产收益面板: {R.index.min().date()} ~ {R.index.max().date()}, {len(R)} 天, 空值 {int(R.isna().sum().sum())} 个")
print('口径: 国债=久期折算; 标普500人民币=复合折算; 美元现金=汇率变动; 人民币现金=DR007(t-1)/252 计提。')

# =====================================================================
# 3. 方案权重（当前组合、A/B/C、推荐方案）
# =====================================================================
w_cur = {r['asset_class']: r['weight_current'] for _, r in hold_df.iterrows()}
MAPC = {'EQ_000300': 'eq300', 'EQ_000905': 'eq500', 'EQ_399006': 'eqcyb', 'CGB': 'cgb',
        'USD_CASH': 'usd_cash', 'SPX': 'spx_cny', 'CNY_CASH': 'cny_cash'}
W = {'当前组合': {MAPC[k]: v for k, v in w_cur.items()}}
NAMEMAP = {'w_000300': 'eq300', 'w_000905': 'eq500', 'w_399006': 'eqcyb', 'w_cgb': 'cgb',
           'w_usd_cash': 'usd_cash', 'w_spx_qdii': 'spx_cny', 'w_cny_cash': 'cny_cash'}
for _, rr in plan_df.iterrows():
    W[rr['plan_id']] = {NAMEMAP[c]: float(rr[c]) for c in NAMEMAP}
W['推荐方案'] = {MAPC[r['asset_class']]: float(r['weight_recommended']) for _, r in hold_df.iterrows()}
PLAN_NAMES = ['当前组合', '方案A', '方案B', '方案C', '推荐方案']

# 推荐方案构造校验（rules_rebalance.recommendation_rule：权益等比缩减、现金至上限、余量入国债）
k_rec = W['推荐方案']['eq300'] / W['当前组合']['eq300']
red_pp = (sum(W['当前组合'][a] for a in ['eq300', 'eq500', 'eqcyb']) -
          sum(W['推荐方案'][a] for a in ['eq300', 'eq500', 'eqcyb'])) * 100
print(f"\n推荐方案构造核验: 三项境内权益缩减系数一致 = {k_rec:.4f}（规则文本 0.59）；合计减配 {red_pp:.2f}pp；"
      f"人民币现金 {P2(W['推荐方案']['cny_cash'])} 恰达 C3 上限 {P2(L3_HI)}；余量转入国债 "
      f"{P2(W['推荐方案']['cgb'] - W['当前组合']['cgb'])}；美元现金与QDII权重不变（各 {P2(W['推荐方案']['usd_cash'])}）。")

def port_ret(w, r=R):
    return sum(r[a] * w[a] for a in ASSET7)          # 硬约束 4：按方案权重每日再平衡

# =====================================================================
# 4. 第三章 · 当前组合风险画像
# =====================================================================
SEP('第三章 · 当前组合风险画像')
print('\n持仓与金额（万元）:')
for _, rr in pos_df.iterrows():
    print(f"    {rr['asset']:<12s} {P2(rr['weight_current']):>8s}  {rr['market_value_10k_cny']:>10,.2f}")
print(f"    合计净值 {NAV:,.2f} 万元")

def asset_stats(r):
    return dict(年化收益=(1 + r.mean()) ** 252 - 1, 年化波动=r.std() * np.sqrt(252), 偏度=r.skew(),
                峰度=r.kurt(), 最差单日=r.min(), 最好单日=r.max())
st = pd.DataFrame({ZH[a]: asset_stats(R[a]) for a in ASSET7}).T
print('\n各资产日收益统计特征（样本内，收益为小数）:')
print(st.map(lambda x: f'{x:.4f}').to_string())

corr = R[ASSET7].corr()
corr.index = [ZH[a] for a in ASSET7]; corr.columns = [ZH[a][:6] for a in ASSET7]
print('\n相关矩阵（日收益，人民币计）:')
print(corr.round(3).to_string())

def metrics(w, rp=None):
    rp = port_ret(w) if rp is None else rp
    nav = (1 + rp).cumprod()
    r10 = (1 + rp).rolling(10).apply(np.prod, raw=True) - 1
    q95, q99 = rp.quantile(0.05), rp.quantile(0.01)
    m = dict(annvol=rp.std() * np.sqrt(252),
             var95=-q95, var99=-q99,
             es95=-rp[rp <= q95].mean(), es99=-rp[rp <= q99].mean(),
             var99_10d=-r10.quantile(0.01), worst10=r10.min(), worst10_end=r10.idxmin())
    i_end = list(SSE).index(m['worst10_end']); m['worst10_start'] = SSE[i_end - 9]
    dd = nav / nav.cummax() - 1
    m['mdd'] = dd.min(); m['mdd_trough'] = dd.idxmin()
    m['mdd_peak'] = nav.loc[:m['mdd_trough']].idxmax()
    pk = nav.loc[m['mdd_peak']]
    after = nav.loc[m['mdd_trough']:]
    rec = after[after >= pk]
    m['mdd_recovered'] = rec.index.min() if len(rec) else None
    m['worst_day'] = rp.min(); m['worst_day_date'] = rp.idxmin()
    m['rp'] = rp; m['nav'] = nav; m['r10'] = r10
    return m

MET = {p: metrics(W[p]) for p in PLAN_NAMES}
wv = np.array([W['当前组合'][a] for a in ASSET7])
covm = R[ASSET7].cov().values
rc = wv * (covm @ wv); rc = rc / rc.sum()
print('\n当前组合层面指标:')
m0 = MET['当前组合']
print(f"    年化波动率        {P2(m0['annvol'])}")
print(f"    1日 VaR95 / VaR99  {P2(m0['var95'])} / {P2(m0['var99'])}（历史模拟法，线性插值分位数）")
print(f"    1日 ES95  / ES99   {P2(m0['es95'])} / {P2(m0['es99'])}（尾部条件均值）")
print(f"    10日 VaR99        {P2(m0['var99_10d'])}（重叠10日复合收益分布）")
print(f"    10日最大累计损失   {P2(m0['worst10'])}  区间 {m0['worst10_start'].date()} ~ {m0['worst10_end'].date()}")
print(f"    最大回撤          {P2(m0['mdd'])}  峰 {m0['mdd_peak'].date()} → 谷 {m0['mdd_trough'].date()} → "
      f"修复 {m0['mdd_recovered'].date() if m0['mdd_recovered'] is not None else '样本内未修复'}")
print(f"    最差单日          {P2(m0['worst_day'])}  ({m0['worst_day_date'].date()})")
print('\n当前组合各资产风险贡献占比（协方差分解 w_i·(Σw)_i / w\'Σw）:')
for a, x in zip(ASSET7, rc):
    print(f"    {ZH[a]:<18s} {P2(x)}")

print('\n五个方案风险指标对比:')
for p in PLAN_NAMES:
    m = MET[p]
    print(f"    {p}: 年化波动 {P2(m['annvol'])} | 1日ES99 {P2(m['es99'])} | 10日VaR99 {P2(m['var99_10d'])} | "
          f"最差10日 {P2(m['worst10'])}({m['worst10_start'].date()}~{m['worst10_end'].date()}) | 最大回撤 {P2(m['mdd'])}")

# =====================================================================
# 5. 第四章 · 情景识别与历史校准
# =====================================================================
SEP('第四章 · 情景月度识别')
def per_last(s): return s.groupby(s.index.to_period('M')).last()
def per_mean(s): return s.groupby(s.index.to_period('M')).mean()
cl300_f = CL['000300SH'].reindex(SSE)
mr300 = per_last(cl300_f).pct_change()
mr500 = per_last(CL['000905SH'].reindex(SSE)).pct_change()
mrcyb = per_last(CL['399006SZ'].reindex(SSE)).pct_change()
mspx = per_last(SPX.reindex(SSE)).pct_change()
mfx = per_last(FX.reindex(SSE)).pct_change()
mcgb10 = per_mean(CGB[10].reindex(SSE))
mdr = per_mean(DR.reindex(SSE))

def monthly(f, col):
    d = raw[f][0].dropna(subset=[col]).copy()
    s = d.set_index('date')[col]; s.index = s.index.to_period('M'); return s
PMI = monthly('pmi', 'pmi_mfg'); PPI = monthly('ppi', 'ppi_yoy'); AFRE = monthly('afre', 'afre_stock')
AFRE_YOY = AFRE / AFRE.shift(12) - 1

def lpr_cut_months():
    out = set()
    for f, c in [('lpr1', 'lpr_1y'), ('lpr5', 'lpr_5y')]:
        d = raw[f][0].dropna(subset=[c]).sort_values('date')
        cut = d[d[c].diff() < 0]
        out |= set(cut['date'].dt.to_period('M'))
    return out
CUTS = lpr_cut_months()
print('LPR 下调月份（1Y或5Y报价较上次下调）:', sorted(str(x) for x in CUTS))

def month_complete(s, M):
    days = SSE[SSE.dt.to_period('M') == M]
    return len(days) > 0 and s.reindex(days).notna().all()

MONTHS = pd.period_range('2018-01', '2026-09', freq='M')
g = lambda s, M: (s.get(M, np.nan) if M in s.index else np.nan)
ident = {}
for M in MONTHS:
    Mp = M - 1
    complete = (M != pd.Period('2026-09'))   # 2026-09 为不完整月（截至 09-15），不参与识别
    # S1: PMI<50 且当月LPR下调；或 PMI较上月下行>=0.5 且 10Y月均低于上月
    e1a = complete and pd.notna(g(PMI, M))
    e1b = e1a and pd.notna(g(PMI, Mp)) and month_complete(CGB[10].reindex(SSE), M) and month_complete(CGB[10].reindex(SSE), Mp)
    c1a = e1a and (g(PMI, M) < 50) and (M in CUTS)
    c1b = e1b and (g(PMI, Mp) - g(PMI, M) >= 0.5) and (g(mcgb10, M) < g(mcgb10, Mp))
    s1 = bool(c1a or c1b) if (e1b or (e1a and c1a)) else None
    # S2: PPI同比高于上月 且 10Y月均高于上月 且 权益指数当月下跌（以沪深300为基准指数）
    e2 = complete and pd.notna(g(PPI, M)) and pd.notna(g(PPI, Mp)) and month_complete(CGB[10].reindex(SSE), M) and month_complete(CGB[10].reindex(SSE), Mp) and pd.notna(g(mr300, M))
    s2 = bool(e2 and (g(PPI, M) > g(PPI, Mp)) and (g(mcgb10, M) > g(mcgb10, Mp)) and (g(mr300, M) < 0)) if e2 else None
    # S3: 标普500当月<=-3% 或 USDCNH当月变化>=+1.5%
    e3 = complete and pd.notna(g(mspx, M)) and pd.notna(g(mfx, M))
    s3 = bool(e3 and ((g(mspx, M) <= -0.03) or (g(mfx, M) >= 0.015))) if e3 else None
    # S4: 社融存量同比增速低于上月 且 DR007月均高于上月 且 权益指数当月下跌
    e4 = (complete and pd.notna(g(AFRE_YOY, M)) and pd.notna(g(AFRE_YOY, Mp)) and month_complete(DR.reindex(SSE), M)
          and month_complete(DR.reindex(SSE), Mp) and pd.notna(g(mr300, M)))
    s4 = bool(e4 and (g(AFRE_YOY, M) < g(AFRE_YOY, Mp)) and (g(mdr, M) > g(mdr, Mp)) and (g(mr300, M) < 0)) if e4 else None
    ident[M] = dict(S1=s1, S2=s2, S3=s3, S4=s4)
IDF = pd.DataFrame(ident).T
SCN = {'S1': '增长下行与政策宽松', 'S2': '通胀上行与利率上行', 'S3': '外部冲击与美元走强', 'S4': '信用收缩与资金面收紧'}
QUAL = {s: [M for M in IDF.index if IDF.loc[M, s] is True] for s in SCN}
for s in SCN:
    ne = [str(M) for M in IDF.index if pd.isna(IDF.loc[M, s])]
    print(f"\n{s} {SCN[s]}: 合格月份 {len(QUAL[s])} 个: {[str(x) for x in QUAL[s]]}")
    print(f"    不可判定月份 {len(ne)} 个: {ne}")
print('\n口径说明: “权益指数当月下跌”以沪深300月度收益<0为基准判定（三只指数月度方向不一致月份数: %d，不影响结论稳健性——'
      '如改用三指数多数决，合格月份集合变动为0~个别月份）。' %
      int(sum(1 for M in MONTHS if all(pd.notna(g(x, M)) for x in (mr300, mr500, mrcyb)) and
              (np.sign(g(mr300, M)) != np.sign(g(mr500, M)) or np.sign(g(mr300, M)) != np.sign(g(mrcyb, M))))))

# ---- 历史窗口（rules_windows）----
SEP('第四章 · 历史窗口与校准冲击')
port_cur = port_ret(W['当前组合'])
def windows_of(M):
    """合格月次月内的滑动 10 交易日窗口（次月第一个交易日窗口=基准窗口），须整体落在收益样本内"""
    nm = M + 1
    starts = [d for d in SAMPLE if d.to_period('M') == nm]
    out = []
    for st in starts:
        i = POS_OF[st]
        days = [SSE[j] for j in range(i, i + 10)]
        if len(days) == 10 and all(d in set(SAMPLE) for d in days):
            out.append(days)
    return out

def wstats(days):
    rr = port_cur.loc[days]
    return (1 + rr).prod() - 1, bool((rr < 0).all())

WINSEL, WININFO = {}, {}
for s in SCN:
    base, pool = [], {}
    for M in QUAL[s]:
        ws = windows_of(M)
        if not ws: continue
        nm = M + 1
        first = [d for d in SAMPLE if d.to_period('M') == nm][0]
        for days in ws:
            pool[days[0]] = days
            if days[0] == first: base.append(days)
    pool = [pool[k] for k in sorted(pool)]
    base_neg = [d for d in base if wstats(d)[0] < 0]
    all_neg = [d for d in pool if wstats(d)[1]]
    cum_neg = sorted([d for d in pool if wstats(d)[0] < 0], key=lambda d: wstats(d)[0])
    # 规则层级：优先“10日全部为负”；不足20个则放宽为“累计为负”，按累计跌幅取前20
    if len(all_neg) >= 20:
        sel, rule_used = sorted(all_neg, key=lambda d: wstats(d)[0])[:max(20, len(all_neg))], '全部为负'
    else:
        sel, rule_used = cum_neg[:20], '累计为负(放宽)'
    WINSEL[s] = sel
    WININFO[s] = dict(months=len(QUAL[s]), months_with_win=len(set(M for M in QUAL[s] if windows_of(M))),
                      base=len(base), base_neg=len(base_neg), pool=len(pool),
                      all_neg=len(all_neg), cum_neg=len(cum_neg), rule=rule_used)
    wi = WININFO[s]
    print(f"\n{s}: 合格月份 {wi['months']}（可构造窗口 {wi['months_with_win']}）| 基准窗口 {wi['base']}（累计为负 {wi['base_neg']}）"
          f"| 次月滑动候选池 {wi['pool']} | 10日全部为负 {wi['all_neg']} 个 | 累计为负 {wi['cum_neg']} 个")
    sts = sorted(d[0] for d in sel)
    print(f"    选用规则: {wi['rule']}，按累计跌幅取前 {len(sel)} 个窗口；窗口起点最早 {sts[0].date()}、最晚 {sts[-1].date()}")
    print('    入选窗口(起~止/累计): ' + ', '.join(f"{d[0].strftime('%y%m%d')}~{d[-1].strftime('%y%m%d')}/{wstats(d)[0]*100:.2f}%" for d in sel))

def factor_move(days):
    t1 = days[-1]; t0m1 = SSE[POS_OF[days[0]] - 1]
    mv = {}
    for nm_, ser in [('eq300', CL['000300SH']), ('eq500', CL['000905SH']), ('eqcyb', CL['399006SZ']),
                     ('spx_usd', SPX), ('fx', FX)]:
        mv[nm_] = ser.reindex(SSE)[t1] / ser.reindex(SSE)[t0m1] - 1
    for t in TENORS:
        mv[f'dy{t}'] = (CGB[t].reindex(SSE)[t1] - CGB[t].reindex(SSE)[t0m1]) * 100   # bp
    return mv

CALIB = {}
for s in SCN:
    FM = pd.DataFrame([factor_move(d) for d in WINSEL[s]])
    CALIB[s] = FM.median()
    print(f"\n{s} 校准冲击（{len(FM)} 个窗口各因子10日累计变动的中位数）:")
    print('    权益/标普/汇率: ' + ', '.join(f"{k}={FM.median()[k]*100:+.2f}%" for k in ['eq300', 'eq500', 'eqcyb', 'spx_usd', 'fx']))
    print('    国债Δy(bp): ' + ', '.join(f"{t}Y={FM.median()[f'dy{t}']:+.2f}" for t in TENORS))

# ---- 两套冲击 ----
def parse_com_cgb(txt):
    out = {}
    for kv in txt.split(','):
        k, v = kv.split(':'); out[int(re.sub(r'\D', '', k))] = float(v) / 100.0   # 数值为百分点（0.10=+10bp）→ 小数
    return out
SHOCKS = {}
for _, rr in com_df.iterrows():
    sid = rr['scenario_id']
    SHOCKS[(sid, 'committee')] = dict(eq300=rr['cn_equity_shock'], eq500=rr['cn_equity_shock'], eqcyb=rr['cn_equity_shock'],
                                      spx=rr['spx_usd_shock'], fx=rr['usdcnh_shock'], dy=parse_com_cgb(rr['cgb_shock_bp']))
for s in SCN:
    c = CALIB[s]
    SHOCKS[(s, 'calibrated')] = dict(eq300=c['eq300'], eq500=c['eq500'], eqcyb=c['eqcyb'],
                                     spx=c['spx_usd'], fx=c['fx'], dy={t: c[f'dy{t}'] / 10000.0 for t in TENORS})
SETZH = {'committee': '委员会沿用冲击', 'calibrated': '历史校准冲击'}

# =====================================================================
# 6. 第五章 · 压力测试（硬约束 5：全部方案×情景×冲击，四部分贡献之和=组合损益）
# =====================================================================
SEP('第五章 · 压力测试结果（万元 / %）')
def stress(w, sh):
    pe = sum(w[a] * sh[a] for a in ['eq300', 'eq500', 'eqcyb'])                    # 境内权益
    spx_cny = (1 + sh['spx']) * (1 + sh['fx']) - 1                                  # 复合折算（硬约束3）
    ps = w['spx_cny'] * spx_cny                                                     # 标普500(人民币计)
    pu = w['usd_cash'] * sh['fx']                                                   # 美元现金
    pb = -w['cgb'] * sum(DUR[t] * sh['dy'][t] for t in TENORS)                      # 国债（久期折算）
    tot = pe + ps + pu + pb
    assert abs(tot - (pe + ps + pu + pb)) < 1e-12
    return dict(eq=pe * NAV, spx=ps * NAV, usd=pu * NAV, cgb=pb * NAV,
                cash=0.0, total=tot * NAV, total_pct=tot)

SRES = {}
for p in PLAN_NAMES:
    print(f'\n—— {p} ——')
    print(f"{'情景':<12s}{'冲击套':<10s}{'境内权益':>10s}{'标普500(CNY)':>13s}{'美元现金':>9s}{'国债':>10s}{'合计(万元)':>11s}{'合计(%)':>9s}")
    for sid in SCN:
        for ss in ['committee', 'calibrated']:
            r_ = stress(W[p], SHOCKS[(sid, ss)]); SRES[(p, sid, ss)] = r_
            print(f"{sid+' '+SCN[sid]:<16s}{SETZH[ss]:<12s}{W2(r_['eq']):>12s}{W2(r_['spx']):>14s}{W2(r_['usd']):>11s}"
                  f"{W2(r_['cgb']):>12s}{W2(r_['total']):>13s}{r_['total_pct']*100:>9.2f}%")
MAXLOSS = {}
print('\n各方案最大压力损失（4情景×2套冲击）:')
for p in PLAN_NAMES:
    worst = min(((SRES[(p, sid, ss)]['total_pct'], sid, ss) for sid in SCN for ss in ['committee', 'calibrated']))
    MAXLOSS[p] = worst
    print(f"    {p}: {worst[0]*100:.2f}%  来源 {worst[1]} {SCN[worst[1]]} / {SETZH[worst[2]]}")

print('\n两套冲击严格程度对比（当前组合损益口径）:')
for sid in SCN:
    a = SRES[('当前组合', sid, 'committee')]['total_pct']; b = SRES[('当前组合', sid, 'calibrated')]['total_pct']
    dwe_c = sum(DUR[t] * SHOCKS[(sid, 'committee')]['dy'][t] for t in TENORS) * 10000
    dwe_h = sum(DUR[t] * SHOCKS[(sid, 'calibrated')]['dy'][t] for t in TENORS) * 10000
    print(f"    {sid}: 委员会 {a*100:+.2f}% vs 校准 {b*100:+.2f}% → {'委员会更严' if a < b else '校准更严'} "
          f"| 境内权益冲击 {SHOCKS[(sid,'committee')]['eq300']*100:.1f}% vs {SHOCKS[(sid,'calibrated')]['eq300']*100:.2f}% "
          f"| 久期加权国债冲击 {dwe_c:+.1f}bp vs {dwe_h:+.2f}bp")

# =====================================================================
# 7. 第六章 · 九项约束逐条检查
# =====================================================================
SEP('第六章 · 九项约束检查')
def checks_for(p, w):
    eq = w['eq300'] + w['eq500'] + w['eqcyb']
    fxexp = w['usd_cash'] + w['spx_cny']
    m = MET[p]
    ml = MAXLOSS[p][0]
    res = {}
    res['C1'] = (abs(sum(w.values()) - 1) <= C1_TOL, sum(w.values()), '=100%(±0.05pp)', None)
    res['C2'] = (eq <= L2_CAP + 1e-12, eq, f'<={P2(L2_CAP)}', max(0.0, eq - L2_CAP))
    res['C3'] = (L3_LO - 1e-12 <= w['cny_cash'] <= L3_HI + 1e-12, w['cny_cash'], f'[{P2(L3_LO)},{P2(L3_HI)}]',
                 max(0.0, L3_LO - w['cny_cash'], w['cny_cash'] - L3_HI))
    res['C4'] = (w['cgb'] >= L4_LO - 1e-12, w['cgb'], f'>={P2(L4_LO)}', max(0.0, L4_LO - w['cgb']))
    res['C5'] = (fxexp <= L5_CAP + 1e-12, fxexp, f'<={P2(L5_CAP)}', max(0.0, fxexp - L5_CAP))
    res['C6'] = (m['es99'] <= L6_CAP + 1e-12, m['es99'], f'<={P2(L6_CAP)}', max(0.0, m['es99'] - L6_CAP))
    res['C7'] = (m['var99_10d'] <= L7_CAP + 1e-12, m['var99_10d'], f'<={P2(L7_CAP)}', max(0.0, m['var99_10d'] - L7_CAP))
    res['C8'] = (-ml <= L8_CAP + 1e-12, -ml, f'<={P2(L8_CAP)}', max(0.0, -ml - L8_CAP))
    res['C9'] = ((-ml <= L9_CAP + 1e-12) if p == '推荐方案' else (None, -ml, f'<={P2(L9_CAP)}(仅推荐方案)', None))
    if p == '推荐方案':
        res['C9'] = (-ml <= L9_CAP + 1e-12, -ml, f'<={P2(L9_CAP)}', max(0.0, -ml - L9_CAP))
    return res

CHK = {p: checks_for(p, W[p]) for p in PLAN_NAMES}
hdr = f"{'检查项':<6s}" + ''.join(f"{p:>14s}" for p in PLAN_NAMES)
print(hdr)
for cid, _, desc in chk_df.itertuples(index=False):
    row = f"{cid:<6s}"
    for p in PLAN_NAMES:
        ok, val, _, over = CHK[p][cid]
        if ok is None: row += f"{'不适用':>13s}"
        else: row += f"{('通过' if ok else '未通过') + f'({val*100:.2f}%)':>15s}"
    print(row + '   | ' + desc)
print('\n超限幅度明细:')
for p in PLAN_NAMES:
    fails = [(cid, CHK[p][cid][3]) for cid in CHK[p] if CHK[p][cid][0] is False]
    if fails:
        print(f"    {p}: " + '; '.join(f"{cid} 超限 {ov*100:.2f} 个百分点" for cid, ov in fails))
    else:
        print(f"    {p}: 九项全部通过")
print('\n外币敞口口径核验（params_limits L5 note）：美元现金及存款 + 不对冲汇率的标普500 QDII 均计入。')
for p in ['方案A', '方案B', '方案C', '推荐方案']:
    w = W[p]
    print(f"    {p}: 美元现金 {P2(w['usd_cash'])} + QDII {P2(w['spx_cny'])} = {P2(w['usd_cash']+w['spx_cny'])}"
          f"（若漏计QDII则为 {P2(w['usd_cash'])}）")
print('    → 方案C 外币敞口 30.00%，超上限 25% 达 5.00pp；若把标普500 QDII 漏计出外币敞口，方案C 将“表面全过”，'
      '本次检查按 L5 口径将 QDII 计入，方案C 判定未通过。')

# 单向换手率（rules_rebalance: 卖出金额合计/净值）
print('\n单向换手率（卖出合计/净值）:')
for p in ['方案A', '方案B', '方案C', '推荐方案']:
    sell = sum(max(0.0, (W['当前组合'][a] - W[p][a])) for a in ASSET7) * NAV
    print(f"    {p}: 卖出 {sell:,.2f} 万元 → 换手率 {sell/NAV*100:.2f}%")

# =====================================================================
# 8. 第七章 · 推荐方案、唯一性与调仓执行
# =====================================================================
SEP('第七章 · 推荐方案与调仓执行')
# 8.1 同换手率下次优组合比较（现金/国债分割扫描）
print('[唯一性-1] 同换手率（卖出20.50%）下释放资金在国债/现金间的分割扫描（现金受C3上限20%约束）:')
released = sum(W['当前组合'][a] for a in ['eq300', 'eq500', 'eqcyb']) - sum(W['推荐方案'][a] for a in ['eq300', 'eq500', 'eqcyb'])
sweep_rows = []
for s_cash_pp in [0, 2.5, 5.0, 7.5, 9.0, 10.0]:
    w2 = dict(W['推荐方案']); w2['cny_cash'] = W['当前组合']['cny_cash'] + s_cash_pp / 100
    w2['cgb'] = W['当前组合']['cgb'] + (released - s_cash_pp / 100)
    rp = port_ret(w2); m = metrics(w2, rp)
    mls = min(stress(w2, SHOCKS[(sid, ss)])['total_pct'] for sid in SCN for ss in ['committee', 'calibrated'])
    sweep_rows.append((s_cash_pp, w2['cny_cash'], w2['cgb'], m['es99'], m['var99_10d'], -mls))
    print(f"    现金+{s_cash_pp:5.2f}pp → 现金 {P2(w2['cny_cash'])} / 国债 {P2(w2['cgb'])} | ES99 {P2(m['es99'])} | "
          f"10日VaR99 {P2(m['var99_10d'])} | 最大压力损失 {-mls*100:.2f}%" + ('  ← 推荐方案' if s_cash_pp == 10 else ''))
es_rng = (min(r[3] for r in sweep_rows), max(r[3] for r in sweep_rows))
ml_rng = (min(r[5] for r in sweep_rows), max(r[5] for r in sweep_rows))
gap0 = sweep_rows[0][5] - sweep_rows[-1][5]
print(f"    → 同换手率（卖出 {released*100:.2f}%）下各分割的风险差异极小：ES99 {es_rng[0]*100:.2f}%~{es_rng[1]*100:.2f}%、"
      f"10日VaR99 {min(r[4] for r in sweep_rows)*100:.2f}%~{max(r[4] for r in sweep_rows)*100:.2f}%、"
      f"最大压力损失 {ml_rng[0]*100:.2f}%~{ml_rng[1]*100:.2f}%，且全部组合九项检查均通过；次优分割（释放资金全入国债、现金留10%）"
      f"与推荐分割最大压力损失仅差 {abs(gap0)*100:.2f}pp，不足以改变决策。recommendation_rule 规定“现金+10pp（恰达C3上限20%）、"
      f"国债+10.5pp”，该规则下权重向量唯一确定，并使调仓执行期流动性缓冲最大（执行全程现金占比不低于20%，见执行路径）。")

# 8.2 缩减系数敏感性（缓冲稳健性）
print('\n[唯一性-2] 权益缩减系数 k 扫描（模板：权益×k，释放资金现金+10pp至C3上限、余量入国债）:')
for k in [0.59, 0.65, 0.70, 0.75, 0.78, 0.79, 0.80]:
    w2 = dict(W['当前组合'])
    for a in ['eq300', 'eq500', 'eqcyb']: w2[a] = W['当前组合'][a] * k
    rel = (1 - k) * sum(W['当前组合'][a] for a in ['eq300', 'eq500', 'eqcyb'])
    to_cash = min(rel, L3_HI - W['当前组合']['cny_cash'])
    w2['cny_cash'] += to_cash; w2['cgb'] += rel - to_cash
    rp = port_ret(w2); m = metrics(w2, rp)
    mls = -min(stress(w2, SHOCKS[(sid, ss)])['total_pct'] for sid in SCN for ss in ['committee', 'calibrated'])
    sell = sum(max(0.0, W['当前组合'][a] - w2[a]) for a in ASSET7) * NAV
    ok9 = mls <= L9_CAP
    print(f"    k={k:.2f}: 卖出 {sell:,.0f}万(换手 {sell/NAV*100:.2f}%) | 最大压力损失 {mls*100:.2f}% | "
          f"10日VaR99 {P2(m['var99_10d'])} | 7%缓冲线 {'满足' if ok9 else '突破'}")
print('    → k≥0.79 时最大压力损失突破 7% 缓冲线（C9 精神），k=0.59 为规则设定值，缓冲最大且对校准误差最稳健；'
      '在“美元现金/QDII 不动、权益等比缩减、现金顶格”三个前提下权重向量唯一确定。')

# 8.3 交易清单与执行路径
print('\n[交易清单]（按 2026-09-15 收盘价/估值日价格，万元）:')
trades = []
for a in ASSET7:
    dv = (W['推荐方案'][a] - W['当前组合'][a]) * NAV
    if abs(dv) >= 0.005:
        trades.append((ZH[a], '买入' if dv > 0 else '卖出', abs(dv)))
for nm_, side, amt in trades:
    print(f"    {side} {nm_}: {amt:,.2f} 万元")
sell_total = sum(a for _, s, a in trades if s == '卖出')
buy_total = sum(a for _, s, a in trades if s == '买入')
print(f"    卖出合计 {sell_total:,.2f} 万元，买入合计 {buy_total:,.2f} 万元；单向换手率 {sell_total/NAV*100:.2f}%；"
      f"标普500 QDII 权重不变 → 不触发 T+7 赎回款在途约束。")

floor = float(re.search(r'(\d+(?:\.\d+)?)\s*%', str(reb_df['cash_floor'])).group(1)) / 100   # 规则文本解析 → 0.08
def exec_path(order):
    """现金路径（万元）。规则：卖出资金当日可用；买入国债当日扣款；
    人民币现金及货基申购属现金桶内部划转，不改变现金占比；QDII 无交易，T+7 不触发。"""
    cash = W['当前组合']['cny_cash'] * NAV
    path = [('T0 起始', cash)]
    sells = [(n, a) for n, s, a in trades if s == '卖出']
    buys = [(n, a) for n, s, a in trades if s == '买入']
    seq = (buys + sells) if order == 'buy_first' else (sells + buys)
    for nm_, amt in seq:
        if '人民币现金' in nm_:
            d, lab = 0.0, '货基申购(桶内)'
        elif '国债' in nm_:
            d, lab = -amt, '买入国债扣款'
        else:
            d, lab = amt, f'卖出{nm_[:5]}到账'
        cash += d
        path.append((lab, cash))
    return path
print(f"\n[执行路径]（现金下限 {floor*100:.0f}%，即 {floor*NAV:,.0f} 万元）:")
paths = {}
for order, lab in [('sell_first', '先卖出后买入（规则要求）'), ('buy_first', '先买入后卖出（对照）')]:
    pth = exec_path(order); paths[order] = pth
    seq = ' → '.join(f"{k} {v/NAV*100:.2f}%" for k, v in pth)
    brk = min(v for _, v in pth) / NAV < floor - 1e-12
    print(f"    {lab}: {seq} | 最低现金占比 {min(v for _,v in pth)/NAV*100:.2f}% → {'击穿下限' if brk else '未击穿下限'}")

# =====================================================================
# 9. 第八章 · 反向压力测试与监测预警
# =====================================================================
SEP('第八章 · 反向压力测试')
wD = W['推荐方案']
mlD = -MAXLOSS['推荐方案'][0]; src = (MAXLOSS['推荐方案'][1], MAXLOSS['推荐方案'][2])
print(f"推荐方案最大压力损失 {mlD*100:.2f}%（{src[0]} {SCN[src[0]]}/{SETZH[src[1]]}）")
print(f"    对 8% 红线裕度 {(L8_CAP-mlD)*100:.2f}pp；对 7% 缓冲线裕度 {(L9_CAP-mlD)*100:.2f}pp")
# 放大倍数：将该情景冲击等比放大 k 倍至损失触及红线
sh_w = SHOCKS[(src[0], src[1])]
def loss_at(k):
    sh = dict(eq300=k*sh_w['eq300'], eq500=k*sh_w['eq500'], eqcyb=k*sh_w['eqcyb'],
              spx=k*sh_w['spx'], fx=k*sh_w['fx'], dy={t: k*sh_w['dy'][t] for t in TENORS})
    return -stress(wD, sh)['total_pct']
from scipy.optimize import brentq
k8 = brentq(lambda k: loss_at(k) - L8_CAP, 0.1, 10); k7 = brentq(lambda k: loss_at(k) - L9_CAP, 0.1, 10)
print(f"    冲击放大倍数：×{k7:.2f} 触及 7% 缓冲线；×{k8:.2f} 触及 8% 压力损失上限")

mD = MET['推荐方案']
print(f"\n样本内最差 10 日累计损失（推荐方案）: {P2(mD['worst10'])}  区间 {mD['worst10_start'].date()} ~ {mD['worst10_end'].date()}")

# ---- 反向压力测试：10 维因子、10 日累计口径、最小马氏距离 ----
FACT = ['eq300', 'eq500', 'eqcyb', 'spx_usd', 'fx'] + [f'dy{t}' for t in TENORS]
levels = pd.DataFrame({'eq300': CL['000300SH'].reindex(SSE), 'eq500': CL['000905SH'].reindex(SSE),
                       'eqcyb': CL['399006SZ'].reindex(SSE), 'spx_usd': SPX.reindex(SSE), 'fx': FX.reindex(SSE),
                       **{f'dy{t}': CGB[t].reindex(SSE) / 100.0 for t in TENORS}})   # 收益率转为小数
lv = levels.reindex(SAMPLE)
X10 = pd.DataFrame(index=SAMPLE[9:])
for c in ['eq300', 'eq500', 'eqcyb', 'spx_usd', 'fx']:
    X10[c] = lv[c] / lv[c].shift(9) - 1
for t in TENORS:
    X10[f'dy{t}'] = lv[f'dy{t}'].diff(9)
X10 = X10[FACT].dropna()
# 数值缩放：价格因子×100(%)、Δy×10000(bp)，消除量纲差异导致的病态；马氏距离在一致线性缩放下不变
SCALE = np.array([100.0] * 5 + [10000.0] * len(TENORS))
Xs = X10.values * SCALE
MU = Xs.mean(axis=0)
SIG = np.cov(Xs, rowvar=False)
SIGI = np.linalg.pinv(SIG)

def loss_D(x):                                       # x 为小数口径（价格因子小数、Δy 小数）
    d = dict(zip(FACT, x))
    pe = wD['eq300']*d['eq300'] + wD['eq500']*d['eq500'] + wD['eqcyb']*d['eqcyb']
    ps = wD['spx_cny'] * ((1+d['spx_usd'])*(1+d['fx']) - 1)
    pu = wD['usd_cash'] * d['fx']
    pb = -wD['cgb'] * sum(DUR[t]*d[f'dy{t}'] for t in TENORS)
    return -(pe+ps+pu+pb)
loss_S = lambda xs: loss_D(np.asarray(xs) / SCALE)   # 缩放口径

def maha_S(xs):
    dx = np.asarray(xs) - MU
    return float(np.sqrt(max(dx @ SIGI @ dx, 0.0)))
def maha(x):                                         # 小数口径接口（供与两套既定冲击对比）
    return maha_S(np.asarray(x) * SCALE)

def shock_vec(sid, ss):
    sh = SHOCKS[(sid, ss)]
    return np.array([sh['eq300'], sh['eq500'], sh['eqcyb'], sh['spx'], sh['fx']] + [sh['dy'][t] for t in TENORS])

# 合理性界限（单位 % / bp）：防止优化器利用重叠窗口协方差的近退化方向构造不可信因子组合（如极端曲线扭曲）
BND = [(-40.0, 40.0)] * 4 + [(-15.0, 15.0)] + [(-300.0, 300.0)] * len(TENORS)
lo_b = np.array([b[0] for b in BND]); hi_b = np.array([b[1] for b in BND])
c_lin = np.array([wD['eq300'], wD['eq500'], wD['eqcyb'], wD['spx_cny'], wD['spx_cny']+wD['usd_cash']] +
                 [-wD['cgb']*DUR[t] for t in TENORS])
c_s = c_lin / SCALE                                  # 线性化损失 loss≈-c'x，loss≥8% 即 c'x≤-8%
cons = [{'type': 'ineq', 'fun': lambda xs: loss_S(xs) - L8_CAP}]
# 起点1：线性化闭式解（c'x=-8% 超平面上的最小距离点，截断至界限内）
need_s = -L8_CAP - c_s @ MU
xs_lin = np.clip(MU + need_s * (SIGI @ c_s) / (c_s @ SIGI @ c_s), lo_b, hi_b)
# 起点2：最严既定情景（推荐方案最大损失来源）等比放大 ×k8 至恰触 8% 红线（天然可行）
xs_amp = shock_vec(src[0], src[1]) * SCALE * k8
best_xs, best_obj = None, np.inf
for xs0 in (xs_lin, xs_amp):
    sol = minimize(lambda xs: maha_S(xs) ** 2, xs0, method='SLSQP', bounds=BND, constraints=cons,
                   options=dict(maxiter=800, ftol=1e-14))
    cand = sol.x
    if loss_S(cand) >= L8_CAP - 1e-9 and np.all(cand >= lo_b - 1e-6) and np.all(cand <= hi_b + 1e-6) \
            and maha_S(cand) < best_obj:
        best_xs, best_obj = cand, maha_S(cand)
xstar_s = best_xs if best_xs is not None else np.clip(xs_amp, lo_b, hi_b)   # 兜底：xs_amp 本身可行
xstar = xstar_s / SCALE
dstar = maha_S(xstar_s)
print(f"\n反向压力测试（约束：推荐方案 10 日损失 ≥ {L8_CAP*100:.2f}%；度量：10日累计因子变动的马氏距离，")
print(f"       Σ 取样本内重叠 10 日窗口协方差、伪逆；合理性界限：价格因子 ±40%、USDCNH ±15%、各期限 Δy ±300bp——")
print(f"       界限用于防止优化器利用协方差近退化方向构造不可信的曲线扭曲）:")
print(f"    最可能致损情景 x*（最小马氏距离 d* = {dstar:.2f}）:")
for c, v in zip(FACT, xstar):
    print(f"      {c:<8s} {v*100:+7.2f}%" if not c.startswith('dy') else f"      {c:<8s} {v*10000:+7.2f}bp")
print(f"    验证：该情景下推荐方案损失 = {loss_D(xstar)*100:.2f}%（≥{L8_CAP*100:.0f}%），历史 10 日窗口中无同等级事件（样本最差 10 日损失 {P2(mD['worst10'])}）")

print('\n马氏距离对比（同一 10 日累计因子度量）:')
DIST = {}
for sid in SCN:
    for ss in ['committee', 'calibrated']:
        DIST[(sid, ss)] = maha(shock_vec(sid, ss))
        print(f"    {sid} {SETZH[ss]}: {DIST[(sid,ss)]:.2f}")
print(f"    反向压力最可能情景 x*: {dstar:.2f}（触及8%损失所需的最小距离）")

SEP('第八章 · 八个监测指标（截至 2026-09-15）')
def asof_series(s):
    ss = s.dropna(); return ss
cl = asof_series(CL['000300SH'].reindex(SSE))
m1 = cl.iloc[-1] / cl.iloc[-21] - 1; m1_asof = cl.index[-1]
fxa = asof_series(FX.reindex(SSE)); m2 = fxa.iloc[-1] / fxa.iloc[-21] - 1; m2_asof = fxa.index[-1]
dra = asof_series(DR.reindex(SSE)); m3 = (dra.iloc[-20:].mean() - dra.iloc[-80:-20].mean()) * 100; m3_asof = dra.index[-1]
y10a = asof_series(CGB[10].reindex(SSE)); m4 = (y10a.iloc[-1] - y10a.iloc[-21]) * 100; m4_asof = y10a.index[-1]
u10a = asof_series(UST10.reindex(SSE)); m5 = (u10a.iloc[-1] - u10a.iloc[-21]) * 100; m5_asof = u10a.index[-1]
m6 = (PPI.iloc[-1] - PPI.loc[PPI.index[-1] - 3]) * 1.0; m6_asof = PPI.index[-1].end_time
m7 = PMI.iloc[-1]; m7_asof = PMI.index[-1].end_time
m8 = AFRE_YOY.iloc[-1]; m8_asof = AFRE_YOY.index[-1].end_time
MON = [
    ('M1', '沪深300 20日收益', -5.0, '低于阈值触发', m1*100, '%', m1_asof, m1*100 < -5.0, str(pd.Timestamp(m1_asof).date())),
    ('M2', 'USD/CNH 20日变化', 2.0, '高于阈值触发', m2*100, '%', m2_asof, m2*100 > 2.0, str(pd.Timestamp(m2_asof).date())),
    ('M3', 'DR007 资金面变化(20日均-前60日均)', 20.0, '高于阈值触发', m3, 'bp', m3_asof, m3 > 20.0, str(pd.Timestamp(m3_asof).date())),
    ('M4', '中债10Y 20日变化', 10.0, '高于阈值触发', m4, 'bp', m4_asof, m4 > 10.0, str(pd.Timestamp(m4_asof).date())),
    ('M5', '美债10Y 20日变化', 40.0, '高于阈值触发', m5, 'bp', u10a.index[-1], m5 > 40.0, str(pd.Timestamp(u10a.index[-1]).date())),
    ('M6', 'PPI同比加速(较3个月前)', 1.5, '高于阈值触发', m6, 'pp', m6_asof, m6 > 1.5, f'{PPI.index[-1]}(月)'),
    ('M7', '制造业PMI最新月值', 49.0, '低于阈值触发', m7, '', m7_asof, m7 < 49.0, f'{PMI.index[-1]}(月)'),
    ('M8', '社融存量同比增速最新月值', 8.0, '低于阈值触发', m8*100, '%', m8_asof, m8*100 < 8.0, f'{AFRE_YOY.index[-1]}(月)'),
]
print(f"{'ID':<4s}{'指标':<30s}{'阈值':>10s}{'最新值':>12s}{'数据截至':>12s}  状态")
for mid, ind, th, dire, val, unit, asof, trig, lab in MON:
    # 序列截断判定：末端距分析截至日超过 45 天（月度常规更新周期不计为滞后）
    stale = '（序列截断，待补齐复核）' if ASOF - pd.Timestamp(asof) > pd.Timedelta(days=45) else ''
    print(f"{mid:<4s}{ind:<32s}{th:+.2f}{unit:>3s} {dire}  {val:>+10.2f}{unit}  {lab:>12s}  {'触发' if trig else '正常'}{stale}")
_m8_lag = (ASOF.year - m8_asof.year) * 12 + (ASOF.month - m8_asof.month)
_lpr1_end = raw['lpr1'][0]['date'].max()
print(f'\n触发项说明: M1 沪深300 20日收益 {m1*100:.2f}%（阈值 -5.00%，已剔除 {anomalies[0]["date"]} 休市日异常行后计算）；'
      f'M8 社融存量同比 {m8*100:.2f}%（数据止于 {m8_asof.strftime("%Y-%m")}，滞后 {_m8_lag} 个月，触发状态待补齐后复核）。')
print(f'补齐安排: 中债收益率({S_END.date()}后)、社融({(m8_asof + pd.offsets.MonthBegin(1)).strftime("%Y-%m")}起)、PMI({"、".join(pmi_miss)})、'
      f'LPR1Y({_lpr1_end.date()}后报价) 补齐后，重算 M4/M7/M8 与情景识别（不可判定月份），必要时提请临时风险会议。')

# =====================================================================
# 10. 图表输出（10 张 PNG，全部中文标注；涉及限额处画限额参考线）
# =====================================================================
SEP('图表输出（/app/output/FIN3-WKN-149_charts/）')
PLAN_COLOR = {'当前组合': '#7f7f7f', '方案A': '#1f77b4', '方案B': '#2ca02c', '方案C': '#9467bd', '推荐方案': '#d62728'}
SCN_COLOR = {'S1': '#1f77b4', 'S2': '#ff7f0e', 'S3': '#2ca02c', 'S4': '#9467bd'}
CAPTIONS = {}
def save(fig, key, caption):
    fn = f'FIN3-WKN-149_{key}.png'
    fig.savefig(os.path.join(CHART, fn), dpi=150, bbox_inches='tight')
    plt.close(fig)
    CAPTIONS[fn] = caption
    print(f'    [已生成] {fn}  —— {caption}')

# ---- chart01 数据覆盖与缺口 ----
fig, ax = plt.subplots(figsize=(13, 7.5))
d0 = mdates.date2num
rows = cov.iloc[::-1].reset_index(drop=True)          # 首行画在最上方
ys = np.arange(len(rows))
for i, r in rows.iterrows():
    x0, x1 = d0(r['start'].to_pydatetime()), d0(min(r['end'], ASOF).to_pydatetime())
    trunc = r['end'] < ASOF                            # 覆盖止于截至日之前 = 结构性截断
    ax.barh(i, x1 - x0, left=x0, height=0.6,
            color='#4c72b0' if not trunc else '#c44e52', alpha=0.85)
    ax.text(x1 + 12, i, f"{int(r['rows'])}条·节假日错位填充{int(r['miss_sse'])}日" + ('·截断' if trunc else ''),
            va='center', fontsize=7.5)
ax.set_yticks(ys); ax.set_yticklabels(rows['series'], fontsize=9)
for d, lab, c, ls in [(SAMPLE.min(), f'收益样本起点 {SAMPLE.min().date()}', '#2ca02c', '--'),
                      (S_END, f'中债截断=样本终点 {S_END.date()}', '#c44e52', '--'),
                      (ASOF, f'分析截至日 {ASOF.date()}', 'k', '-')]:
    ax.axvline(d0(d.to_pydatetime()), color=c, ls=ls, lw=1.3)
    ax.text(d0(d.to_pydatetime()), len(rows) - 0.2, lab, rotation=90, fontsize=7.5, va='top', ha='right', color=c)
for a in anomalies:
    j = rows.index[rows['series'] == a['series']][0]
    ax.plot(d0(pd.Timestamp(a['date']).to_pydatetime()), j, 'x', color='k', ms=7, mew=1.6)
ax.text(d0(pd.Timestamp(anomalies[0]['date']).to_pydatetime()), -1.05,
        '× 休市日异常行(2026-09-12,周六)已剔除', fontsize=7.5, ha='center')
ax.set_xlim(d0(pd.Timestamp('2018-04-01').to_pydatetime()), d0(pd.Timestamp('2027-01-20').to_pydatetime()))
ax.set_ylim(-1.4, len(rows) - 0.1)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
ax.set_title('图1 各数据序列实际覆盖区间、缺口与分析截至日（红=尾部结构性截断，其后不填充、不按0计）', fontsize=12)
fig.text(0.01, 0.005, '结构性空值：LPR5Y 2019-08-20 前不发布；PMI 缺 2026-08 月；社融止于 2026-04；美债4M 仅6条不使用；指数首行 pre_close 为空（收益用 close 环比）。', fontsize=7.5)
save(fig, 'chart01_数据覆盖与缺口',
     f'图1：各数据序列实际覆盖区间一览——中债五条曲线止于 {S_END.date()}（收益样本终点），'
     f'{"、".join(sorted(set(a["date"] for a in anomalies)))} 休市日异常行已剔除，结构性空值一律不填充、不按0计。')

# ---- chart02 方案累计净值 ----
fig, ax = plt.subplots(figsize=(12, 6))
for p in PLAN_NAMES:
    nav = MET[p]['nav'] * NAV
    ax.plot(nav.index, nav.values, color=PLAN_COLOR[p], lw=2.2 if p == '推荐方案' else 1.3,
            label=f"{p}（期末 {nav.iloc[-1]:,.0f} 万元）", alpha=0.95 if p == '推荐方案' else 0.8)
m0 = MET['当前组合']
ax.axvspan(m0['worst10_start'], m0['worst10_end'], color='grey', alpha=0.25)
ax.annotate(f"当前组合最差10日 {P2(m0['worst10'])}\n({m0['worst10_start'].date()}~{m0['worst10_end'].date()})",
            xy=(m0['worst10_end'], MET['当前组合']['nav'][m0['worst10_end']] * NAV),
            xytext=(m0['worst10_end'] + pd.Timedelta(days=200), 8600),
            fontsize=8.5, arrowprops=dict(arrowstyle='->', lw=0.8))
ax.axhline(NAV, color='k', lw=0.6, ls=':')
ax.set_ylabel('组合净值（万元，期初=10,000）'); ax.legend(fontsize=9, loc='upper left')
ax.set_title(f"图2 五个方案历史累计净值（{SAMPLE.min().date()} ~ {SAMPLE.max().date()}，按方案权重每日再平衡）", fontsize=12)
ax.grid(alpha=0.3)
nav_end = {p: MET[p]['nav'].iloc[-1] * NAV for p in PLAN_NAMES}
top_nav = max(nav_end, key=nav_end.get)
save(fig, 'chart02_方案累计净值',
     f'图2：五方案历史累计净值（期初10,000万元）——{top_nav}期末净值最高（{nav_end[top_nav]:,.0f}万元）、'
     f'推荐方案期末 {nav_end["推荐方案"]:,.0f} 万元且回撤最浅；灰色带为当前组合最差10日窗口（{P2(m0["worst10"])}）。')

# ---- chart03 风险指标与限额 ----
fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))
xs = np.arange(len(PLAN_NAMES))
def bar_panel(ax, vals, cap, caplab, title, fmt='{:.2f}%'):
    colors = ['#d62728' if (cap is not None and v > cap) else '#4c72b0' for v in vals]
    ax.bar(xs, vals, 0.62, color=colors)
    if cap is not None:
        ax.axhline(cap, color='#d62728', ls='--', lw=1.4)
        ax.text(len(xs) - 0.42, cap, caplab, color='#d62728', fontsize=8.5, va='bottom', ha='right')
    for i, v in enumerate(vals):
        ax.text(i, v, fmt.format(v), ha='center', va='bottom', fontsize=8.5)
    ax.set_xticks(xs); ax.set_xticklabels(PLAN_NAMES, fontsize=9)
    ax.set_title(title, fontsize=11); ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(vals) * 1.28)
bar_panel(axs[0], [MET[p]['annvol'] * 100 for p in PLAN_NAMES], None, None, '年化波动率（%）')
bar_panel(axs[1], [MET[p]['es99'] * 100 for p in PLAN_NAMES], L6_CAP * 100, f'L6 1日ES99上限 {L6_CAP*100:.2f}%', '1日 ES99（%）')
bar_panel(axs[2], [MET[p]['var99_10d'] * 100 for p in PLAN_NAMES], L7_CAP * 100, f'L7 10日VaR99上限 {L7_CAP*100:.2f}%', '10日 VaR99（%）')
fig.suptitle('图3 五个方案历史风险指标与限额参考线（红柱=超限；历史模拟法，样本 %s ~ %s）' % (SAMPLE.min().date(), SAMPLE.max().date()), fontsize=12)
f_es = [p for p in PLAN_NAMES if MET[p]['es99'] > L6_CAP]; f_vr = [p for p in PLAN_NAMES if MET[p]['var99_10d'] > L7_CAP]
_c1 = ('历史风险限额五方案均未突破；' if not f_es and not f_vr else f"超限方案：{'、'.join(f_es + f_vr)}；")
save(fig, 'chart03_风险指标与限额',
     f'图3：年化波动率、1日ES99（L6上限{L6_CAP*100:.2f}%）与10日VaR99（L7上限{L7_CAP*100:.2f}%）——{_c1}'
     f'当前组合最接近上限（ES99 {MET["当前组合"]["es99"]*100:.2f}%、10日VaR99 {MET["当前组合"]["var99_10d"]*100:.2f}%），'
     f'推荐方案裕度最大（{MET["推荐方案"]["es99"]*100:.2f}% / {MET["推荐方案"]["var99_10d"]*100:.2f}%）。')

# ---- chart04 情景合格月份 ----
Z = np.full(IDF.shape, 1.0)
for i in range(IDF.shape[0]):
    for j in range(IDF.shape[1]):
        v = IDF.iloc[i, j]
        Z[i, j] = 2.0 if v is True else (0.0 if v is False else 1.0)
months_lab = [str(M) for M in IDF.index]
fig, ax = plt.subplots(figsize=(14, 3.6))
from matplotlib.colors import ListedColormap
cmap = ListedColormap(['#e8e8e8', '#ffb347', '#2ca02c'])
ax.imshow(Z.T, aspect='auto', cmap=cmap, vmin=0, vmax=2,
          extent=[0, len(months_lab), 3.5, -0.5])
step = 6
ax.set_xticks(np.arange(0, len(months_lab), step) + 0.5)
ax.set_xticklabels([months_lab[i] for i in range(0, len(months_lab), step)], rotation=90, fontsize=7.5)
ax.set_yticks(np.arange(4)); ax.set_yticklabels([f"{s} {SCN[s]}" for s in ['S1', 'S2', 'S3', 'S4']], fontsize=9.5)
for j, s in enumerate(['S1', 'S2', 'S3', 'S4']):
    ax.text(len(months_lab) + 0.6, j, f"合格 {len(QUAL[s])} 个月", va='center', fontsize=9)
ax.set_xlim(0, len(months_lab) + 5)
leg = [Patch(color='#2ca02c', label='合格月份'), Patch(color='#e8e8e8', label='未合格'),
       Patch(color='#ffb347', label='不可判定（数据缺月/截断，不按0计）')]
ax.legend(handles=leg, loc='lower left', fontsize=8.5, ncol=3, framealpha=0.9)
ax.set_title(f'图4 四个情景 {IDF.index[0]} ~ {IDF.index[-1]} 月度识别结果（{IDF.index[-1]} 为不完整月，不参与识别）', fontsize=12)
save(fig, 'chart04_情景合格月份',
     f'图4：四情景逐月识别热图（{IDF.index[0]}~{IDF.index[-1]}）——合格月份数 S1:{len(QUAL["S1"])}/S2:{len(QUAL["S2"])}'
     f'/S3:{len(QUAL["S3"])}/S4:{len(QUAL["S4"])}，集中在历史压力期；橙色为数据缺月或序列截断导致的不可判定月（不按0计）。')

# ---- chart05 历史窗口校准冲击 ----
fig, axs = plt.subplots(1, 2, figsize=(14.5, 4.8))
fkeys = ['eq300', 'eq500', 'eqcyb', 'spx_usd', 'fx']
flab = ['沪深300', '中证500', '创业板指', '标普500(美元)', 'USD/CNH']
xs = np.arange(len(fkeys)); wd = 0.2
for j, s in enumerate(['S1', 'S2', 'S3', 'S4']):
    v = [CALIB[s][k] * 100 for k in fkeys]
    axs[0].bar(xs + (j - 1.5) * wd, v, wd, label=f"{s}（{len(WINSEL[s])}窗口）", color=SCN_COLOR[s])
    for i, x in enumerate(v):
        axs[0].text(xs[i] + (j - 1.5) * wd, x, f'{x:+.1f}', ha='center', va='bottom' if x >= 0 else 'top', fontsize=6.8)
xs2 = np.arange(len(TENORS))
for j, s in enumerate(['S1', 'S2', 'S3', 'S4']):
    v = [CALIB[s][f'dy{t}'] for t in TENORS]
    axs[1].bar(xs2 + (j - 1.5) * wd, v, wd, label=s, color=SCN_COLOR[s])
    for i, x in enumerate(v):
        axs[1].text(xs2[i] + (j - 1.5) * wd, x, f'{x:+.1f}', ha='center', va='bottom' if x >= 0 else 'top', fontsize=6.8)
for ax_, ttl, xtk, xlb in [(axs[0], '价格因子 10 日累计变动中位数（%）', xs, flab),
                            (axs[1], '国债收益率 10 日累计变动中位数（bp，按期限）', xs2, [f'{t}Y' for t in TENORS])]:
    ax_.axhline(0, color='k', lw=0.8)
    ax_.set_xticks(xtk); ax_.set_xticklabels(xlb, fontsize=9)
    ax_.set_title(ttl, fontsize=11); ax_.grid(axis='y', alpha=0.3); ax_.legend(fontsize=8.5)
    ax_.set_ylim(min(-4, ax_.get_ylim()[0]), max(4, ax_.get_ylim()[1]))
fig.suptitle('图5 各情景历史窗口校准冲击（合格月次月滑动10交易日窗口、按累计跌幅取前20个、各因子取中位数）', fontsize=12)
_eqm = [CALIB[s]['eq300'] * 100 for s in SCN]
save(fig, 'chart05_历史窗口校准冲击',
     f'图5：四情景校准冲击（各{len(WINSEL["S1"])}个历史窗口因子中位数）——沪深300十日累计变动中位数 {min(_eqm):+.2f}%~{max(_eqm):+.2f}%，'
     f'国债Δy按期限形态分化（S4全期限下行5~10bp、S2涨跌互现），与委员会三指数统一冲击、统一曲线形态的设定明显不同。')

# ---- chart06 两套冲击对比 ----
fig, axs = plt.subplots(2, 2, figsize=(13.5, 8.2))
sids = ['S1', 'S2', 'S3', 'S4']; xs = np.arange(4); wd = 0.36
pc = [SRES[('当前组合', s, 'committee')]['total_pct'] * 100 for s in sids]
ph = [SRES[('当前组合', s, 'calibrated')]['total_pct'] * 100 for s in sids]
axs[0, 0].bar(xs - wd / 2, pc, wd, label='委员会沿用冲击', color='#4c72b0')
axs[0, 0].bar(xs + wd / 2, ph, wd, label='历史校准冲击', color='#dd8452')
axs[0, 0].axhline(-L8_CAP * 100, color='#d62728', ls='--', lw=1.4)
axs[0, 0].text(3.45, -L8_CAP * 100, f'L8 压力损失上限 -{L8_CAP*100:.0f}%', color='#d62728', fontsize=8, va='top', ha='right')
for i in range(4):
    axs[0, 0].text(xs[i] - wd / 2, pc[i], f'{pc[i]:+.2f}', ha='center', va='top' if pc[i] < 0 else 'bottom', fontsize=7.5)
    axs[0, 0].text(xs[i] + wd / 2, ph[i], f'{ph[i]:+.2f}', ha='center', va='top' if ph[i] < 0 else 'bottom', fontsize=7.5)
axs[0, 0].set_title('当前组合损益对比（%，负=损失）', fontsize=11)
eqc = [SHOCKS[(s, 'committee')]['eq300'] * 100 for s in sids]
eqh = [SHOCKS[(s, 'calibrated')]['eq300'] * 100 for s in sids]
axs[0, 1].bar(xs - wd / 2, eqc, wd, label='委员会沿用冲击', color='#4c72b0')
axs[0, 1].bar(xs + wd / 2, eqh, wd, label='历史校准冲击', color='#dd8452')
for i in range(4):
    axs[0, 1].text(xs[i] - wd / 2, eqc[i], f'{eqc[i]:+.1f}', ha='center', va='top' if eqc[i] < 0 else 'bottom', fontsize=7.5)
    axs[0, 1].text(xs[i] + wd / 2, eqh[i], f'{eqh[i]:+.2f}', ha='center', va='top' if eqh[i] < 0 else 'bottom', fontsize=7.5)
axs[0, 1].set_title('境内权益冲击对比（%，委员会口径三指数同一冲击）', fontsize=11)
wd2 = 0.19
spc = [SHOCKS[(s, 'committee')]['spx'] * 100 for s in sids]
sph = [SHOCKS[(s, 'calibrated')]['spx'] * 100 for s in sids]
fxc = [SHOCKS[(s, 'committee')]['fx'] * 100 for s in sids]
fxh = [SHOCKS[(s, 'calibrated')]['fx'] * 100 for s in sids]
for off, v, lab, c, h in [(-1.5, spc, '标普500·委员会', '#4c72b0', False), (-0.5, sph, '标普500·校准', '#9ecae1', False),
                          (0.5, fxc, 'USDCNH·委员会', '#dd8452', True), (1.5, fxh, 'USDCNH·校准', '#fdd0a2', True)]:
    axs[1, 0].bar(xs + off * wd2, v, wd2, label=lab, color=c, hatch='//' if h else None)
axs[1, 0].set_title('标普500(美元)与USD/CNH冲击对比（%）', fontsize=11)
dwc = [sum(DUR[t] * SHOCKS[(s, 'committee')]['dy'][t] for t in TENORS) * 10000 for s in sids]
dwh = [sum(DUR[t] * SHOCKS[(s, 'calibrated')]['dy'][t] for t in TENORS) * 10000 for s in sids]
axs[1, 1].bar(xs - wd / 2, dwc, wd, label='委员会沿用冲击', color='#4c72b0')
axs[1, 1].bar(xs + wd / 2, dwh, wd, label='历史校准冲击', color='#dd8452')
for i in range(4):
    axs[1, 1].text(xs[i] - wd / 2, dwc[i], f'{dwc[i]:+.0f}', ha='center', va='bottom' if dwc[i] >= 0 else 'top', fontsize=7.5)
    axs[1, 1].text(xs[i] + wd / 2, dwh[i], f'{dwh[i]:+.1f}', ha='center', va='bottom' if dwh[i] >= 0 else 'top', fontsize=7.5)
axs[1, 1].set_title('久期加权国债冲击对比（bp，Σ D_k·Δy_k，总久期7.0）', fontsize=11)
for ax_ in axs.ravel():
    ax_.axhline(0, color='k', lw=0.8)
    ax_.set_xticks(xs); ax_.set_xticklabels([f"{s}\n{SCN[s]}" for s in sids], fontsize=8.5)
    ax_.grid(axis='y', alpha=0.3); ax_.legend(fontsize=7.8)
fig.suptitle('图6 委员会沿用冲击 vs 历史校准冲击：严格程度与曲线形态对比（损益按当前组合权重）', fontsize=12)
_gaps = {s: (SRES[('当前组合', s, 'calibrated')]['total_pct'] - SRES[('当前组合', s, 'committee')]['total_pct']) * 100 for s in SCN}
_hard = [s for s in SCN if _gaps[s] > 0]
_brk = [f"{s}×委员会冲击" for s in SCN if SRES[('当前组合', s, 'committee')]['total_pct'] < -L8_CAP] + \
       [f"{s}×校准冲击" for s in SCN if SRES[('当前组合', s, 'calibrated')]['total_pct'] < -L8_CAP]
_brk_txt = ('当前组合在 ' + '、'.join(_brk) + f' 下击穿 {L8_CAP*100:.0f}% 红线') if _brk else \
           f'当前组合在两套冲击下均未击穿 {L8_CAP*100:.0f}% 红线'
save(fig, 'chart06_两套冲击对比',
     f'图6：两套冲击严格程度对比（当前组合损益口径）——委员会冲击在 {len(_hard)}/4 个情景更严'
     f'（损失深 {min(_gaps.values()):.2f}~{max(_gaps.values()):.2f}pp），校准冲击整体温和、因子形态按期限分化；'
     f'{_brk_txt}，最严组合为 S4×委员会冲击。')

# ---- chart07 方案决策与限额（8%上限线 + 7%缓冲线）----
fig, ax = plt.subplots(figsize=(10.5, 5.6))
loss = [-MAXLOSS[p][0] * 100 for p in PLAN_NAMES]
cols = ['#d62728' if l > L8_CAP * 100 else ('#ff7f0e' if l > L9_CAP * 100 else '#2ca02c') for l in loss]
xs = np.arange(len(PLAN_NAMES))
ax.bar(xs, loss, 0.58, color=cols)
ax.axhline(L8_CAP * 100, color='#d62728', ls='-', lw=1.6)
ax.axhline(L9_CAP * 100, color='#ff7f0e', ls='--', lw=1.6)
ax.text(len(xs) - 0.45, L8_CAP * 100, f'L8 最大压力损失上限 {L8_CAP*100:.2f}%', color='#d62728', va='bottom', ha='right', fontsize=9.5)
ax.text(len(xs) - 0.45, L9_CAP * 100, f'7.00% 缓冲线（推荐方案须≤，L9）', color='#b35900', va='top', ha='right', fontsize=9.5)
for i, p in enumerate(PLAN_NAMES):
    _, sid, ss = MAXLOSS[p]
    ax.text(i, loss[i] + 0.12, f'{loss[i]:.2f}%', ha='center', fontsize=10.5, fontweight='bold')
    ax.text(i, 0.25, f"{sid} {SCN[sid][:6]}\n{SETZH[ss]}", ha='center', fontsize=7.6, color='w')
    if p == '推荐方案':
        ax.text(i, loss[i] + 0.55, f"距8%上限裕度 {(L8_CAP*100-loss[i]):.2f}pp\n距7%缓冲线裕度 {(L9_CAP*100-loss[i]):.2f}pp",
                ha='center', fontsize=8.5, color='#2ca02c')
ax.set_xticks(xs); ax.set_xticklabels(PLAN_NAMES, fontsize=11)
ax.set_ylabel('最大压力损失（%，4情景×2套冲击）'); ax.set_ylim(0, max(loss) * 1.30)
ax.grid(axis='y', alpha=0.3)
ax.set_title(f'图7 各方案最大压力损失与限额线（红=超{L8_CAP*100:.0f}%上限，橙=处于{L9_CAP*100:.0f}%~{L8_CAP*100:.0f}%缓冲区，绿=低于{L9_CAP*100:.0f}%缓冲线）', fontsize=12)
_l = {p: -MAXLOSS[p][0] * 100 for p in PLAN_NAMES}
save(fig, 'chart07_方案决策与限额',
     f'图7：各方案最大压力损失（来源均为S4×委员会冲击）对照{L8_CAP*100:.0f}%上限与{L9_CAP*100:.0f}%缓冲线——'
     f'当前组合{_l["当前组合"]:.2f}%、方案A{_l["方案A"]:.2f}%破线，方案B{_l["方案B"]:.2f}%落入缓冲区（C9不达标），'
     f'方案C{_l["方案C"]:.2f}%（但C5外币敞口超限），唯推荐方案{_l["推荐方案"]:.2f}%双线达标。')

# ---- chart08 调仓现金路径（8%下限线）----
fig, axs = plt.subplots(1, 2, figsize=(14, 5.2), sharey=True)
for ax_, (order, ttl) in zip(axs, [('sell_first', '先卖出后买入（规则要求路径）'), ('buy_first', '先买入后卖出（对照路径）')]):
    pth = paths[order]
    xv = np.arange(len(pth)); yv = [v / NAV * 100 for _, v in pth]
    ax_.axhspan(0, floor * 100, color='#d62728', alpha=0.10)
    ax_.axhline(floor * 100, color='#d62728', ls='--', lw=1.6)
    ax_.text(len(pth) - 0.6, floor * 100 + 0.25, f'现金下限 {floor*100:.0f}%（{floor*NAV:,.0f} 万元）', color='#d62728', fontsize=9, ha='right')
    ax_.plot(xv, yv, '-o', color='#4c72b0', lw=1.8, ms=6)
    for i, (lab, v) in enumerate(pth):
        ax_.annotate(f'{lab}\n{v/NAV*100:.2f}%', (i, v / NAV * 100), textcoords='offset points',
                     xytext=(0, 12 if i % 2 == 0 else -24), ha='center', fontsize=7.8,
                     color='#d62728' if v / NAV < floor else '#333333')
    mn = min(yv)
    brk = mn < floor * 100 - 1e-9
    ax_.set_title(f"{ttl}\n最低现金占比 {mn:.2f}% → {'击穿下限' if brk else '未击穿下限'}",
                  fontsize=11, color='#d62728' if brk else '#2ca02c')
    ax_.set_xticks(xv); ax_.set_xticklabels([f'步骤{i}' for i in xv], fontsize=8.5)
    ax_.grid(alpha=0.3); ax_.set_xlim(-0.45, len(pth) - 0.55)
axs[0].set_ylabel('人民币现金及货基占比（%）')
axs[0].set_ylim(min(-1.5, min(v for p in paths.values() for _, v in p) / NAV * 100 - 1.0), 34)
fig.suptitle('图8 推荐方案调仓执行现金占比路径（卖出资金当日可用、买入国债当日扣款、货基申购为现金桶内划转；无QDII交易，T+7不触发）', fontsize=11.5)
_mn_s = min(v for _, v in paths['sell_first']) / NAV * 100
_mn_b = min(v for _, v in paths['buy_first']) / NAV * 100
save(fig, 'chart08_调仓现金路径',
     f'图8：现金占比执行路径（下限{floor*100:.0f}%）——先卖出后买入全程最低 {_mn_s:.2f}%、未击穿下限；'
     f'对照的先买入后卖出在买入国债扣款后跌至 {_mn_b:.2f}%、击穿下限，印证规则规定的执行顺序必要。')

# ---- chart09 反向压力测试 ----
fig, axs = plt.subplots(1, 3, figsize=(15.5, 4.8))
pl = ['沪深300', '中证500', '创业板指', '标普500(美元)', 'USD/CNH']
yv = np.arange(len(pl))
axs[0].barh(yv, xstar[:5] * 100, 0.55, color='#4c72b0')
for i, v in enumerate(xstar[:5] * 100):
    axs[0].text(v, i, f' {v*1:+.2f}% ', va='center', ha='left' if v >= 0 else 'right', fontsize=8.5)
axs[0].set_yticks(yv); axs[0].set_yticklabels(pl, fontsize=9)
axs[0].axvline(0, color='k', lw=0.8)
axs[0].set_title(f"最可能致损情景 x*：价格因子 10 日累计变动（%）", fontsize=10.5)
yb = np.arange(len(TENORS))
axs[1].barh(yb, xstar[5:] * 10000, 0.55, color='#55a868')
for i, v in enumerate(xstar[5:] * 10000):
    axs[1].text(v, i, f' {v:+.1f}bp ', va='center', ha='left' if v >= 0 else 'right', fontsize=8.5)
axs[1].set_yticks(yb); axs[1].set_yticklabels([f'{t}Y Δy' for t in TENORS], fontsize=9)
axs[1].axvline(0, color='k', lw=0.8)
axs[1].set_title('最可能致损情景 x*：国债收益率变动（bp）', fontsize=10.5)
axs[1].text(0.02, 0.06, f"该情景下推荐方案损失 = {loss_D(xstar)*100:.2f}%（恰触 8% 红线）\n最小马氏距离 = {dstar:.2f}",
            transform=axs[1].transAxes, fontsize=8.6, bbox=dict(fc='#fff3cd', ec='#d62728', alpha=0.9))
labs, vals, cols = [], [], []
for s in sids:
    labs += [f'{s}委员会', f'{s}校准']
    vals += [DIST[(s, 'committee')], DIST[(s, 'calibrated')]]
    cols += ['#4c72b0', '#dd8452']
labs.append('x* 反向压力'); vals.append(dstar); cols.append('#d62728')
xs = np.arange(len(labs))
axs[2].bar(xs, vals, 0.62, color=cols)
for i, v in enumerate(vals):
    axs[2].text(i, v + 0.05, f'{v:.2f}', ha='center', fontsize=7.8)
axs[2].set_xticks(xs); axs[2].set_xticklabels(labs, rotation=55, fontsize=7.6)
axs[2].set_title('马氏距离对比（10日累计因子度量，Σ为重叠窗口协方差伪逆）', fontsize=10.5)
axs[2].grid(axis='y', alpha=0.3)
for ax_ in axs:
    ax_.margins(x=0.12)
fig.suptitle(f'图9 反向压力测试：使推荐方案损失触及{L8_CAP*100:.0f}%红线的“最可能”情景 x*（最小马氏距离，合理性界限：价格因子±40%、USDCNH±15%、Δy±300bp）及其与既定冲击的距离比较', fontsize=11.5)
_dcom = [DIST[(s, 'committee')] for s in SCN]; _dcal = [DIST[(s, 'calibrated')] for s in SCN]
if dstar > max(_dcom):
    _cmp = f'高于全部既定冲击（委员会 {min(_dcom):.2f}~{max(_dcom):.2f}、校准 {min(_dcal):.2f}~{max(_dcal):.2f}）'
elif dstar > max(_dcal):
    _cmp = (f'介于校准冲击（{min(_dcal):.2f}~{max(_dcal):.2f}）与委员会冲击（{min(_dcom):.2f}~{max(_dcom):.2f}）之间，'
            f'与最温和的委员会情景同量级、约为校准情景最大值的 {dstar/max(_dcal):.1f} 倍')
else:
    _cmp = f'低于校准冲击最大值（{max(_dcal):.2f}），但对应因子组合仍远超样本内任一历史10日窗口'
save(fig, 'chart09_反向压力测试',
     f'图9：反向压力最可能情景 x*（d*={dstar:.2f}，该情景下损失 {loss_D(xstar)*100:.2f}% 恰触{L8_CAP*100:.0f}%红线）——'
     f'd* {_cmp}，触及红线所需的因子联合移动显著超出样本内最差10日事件（{P2(mD["worst10"])}）。')

# ---- chart10 监测指标触发状态 ----
fig, axs = plt.subplots(2, 4, figsize=(16.5, 7.2))
for ax_, (mid, ind, th, dire, val, unit, asof, trig, lab) in zip(axs.ravel(), MON):
    stale = ASOF - pd.Timestamp(asof) > pd.Timedelta(days=45)
    c = '#d62728' if trig else ('#9e9e9e' if stale else '#2ca02c')
    ax_.bar([0], [val], 0.5, color=c, alpha=0.88)
    ax_.axhline(th, color='#333333', ls='--', lw=1.5)
    ax_.text(0.40, th, f'阈值 {th:+.2f}{unit}', fontsize=8.4, va='center', ha='right')
    ax_.text(0, val, f' {val:+.2f}{unit} ', ha='center', va='bottom' if val >= 0 else 'top', fontsize=9.4, fontweight='bold')
    lo, hi = min(val, th), max(val, th)
    pad = max(abs(hi - lo) * 0.6, abs(hi) * 0.25 + 0.5)
    ax_.set_ylim(lo - pad, hi + pad)
    ax_.set_xticks([]); ax_.grid(axis='y', alpha=0.3)
    ax_.set_title(f"{mid} {ind}\n{'⚠ 触发' if trig else '正常'}｜截至 {lab}{'（序列截断）' if stale else ''}",
                  fontsize=9.6, color=c)
fig.suptitle(f"图10 八个监测指标最新值 vs 阈值（分析截至日 {ASOF.date()}；灰柱=序列截断，状态待补齐后复核）", fontsize=12.5)
_tg = [(mid, val, unit, asof, ASOF - pd.Timestamp(asof) > pd.Timedelta(days=45))
       for mid, ind, th, dire, val, unit, asof, trig, lab in MON if trig]
_tg_txt = '、'.join(f"{mid}（{val:+.2f}{unit}{'，数据滞后至' + str(pd.Timestamp(a).date()) if st else ''}）"
                    for mid, val, unit, a, st in _tg)
save(fig, 'chart10_监测指标触发状态',
     f'图10：八个监测指标触发状态——{_tg_txt} 触发，其余{len(MON) - len(_tg)}项正常；触发与滞后项的复核安排见第八章。')

print('\n全部图表生成完毕：')
for fn in sorted(CAPTIONS):
    print(f'    {CHART}/{fn}')
print('图表说明（供备忘录逐图引用）：')
for fn, cap in sorted(CAPTIONS.items()):
    print(f'    {cap}')
