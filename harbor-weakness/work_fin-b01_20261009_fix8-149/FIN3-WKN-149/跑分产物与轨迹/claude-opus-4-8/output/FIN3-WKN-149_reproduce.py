# -*- coding: utf-8 -*-
"""
FIN3-WKN-149 多资产稳健配置专户 三季度宏观压力测试与调仓建议 可复算脚本
从 /app/input_files/ 原始快照读入，不硬编码任何结论数值。
运行: python3 FIN3-WKN-149_reproduce.py
产出: /app/output/ 下 7 项交付物中的代码/图表, 以及 _results.json 供备忘录追溯。
"""
import os, json, warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

warnings.filterwarnings("ignore")

IN = "/app/input_files"
OUT = "/app/output"
CH = os.path.join(OUT, "FIN3-WKN-149_charts")
os.makedirs(CH, exist_ok=True)

# ---- 中文字体 ----
_FP = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
if os.path.exists(_FP):
    fm.fontManager.addfont(_FP)
    _name = fm.FontProperties(fname=_FP).get_name()
    plt.rcParams["font.family"] = _name
plt.rcParams["axes.unicode_minus"] = False

ASOF = pd.Timestamp("2026-09-15")
NAV = 10000.0  # 万元

R = {}  # 结果汇总

def rd(f):
    return pd.read_csv(os.path.join(IN, f))

# ============ 第二章 数据核验 ============
cal = rd("snapshot_trade_calendar.csv")
cal["date"] = pd.to_datetime(cal["date"])
TDAYS = cal.loc[cal.is_trading_day == 1, "date"].sort_values().reset_index(drop=True)
TSET = set(TDAYS)
verify = []  # 逐序列核验记录

def load_eq(code):
    a = rd(f"snapshot_{code}_seg1.csv"); b = rd(f"snapshot_{code}_seg2.csv")
    d = pd.concat([a, b], ignore_index=True)
    d["date"] = pd.to_datetime(d["date"])
    n0 = len(d)
    # 剔除非交易日异常记录 (OHLC 全相等的休市日残留)
    notcal = d[~d["date"].isin(TSET)]
    d = d[d["date"].isin(TSET)].copy()
    d = d.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    verify.append(dict(series=code, rows_raw=n0, rows_clean=len(d),
                       start=str(d.date.min().date()), end=str(d.date.max().date()),
                       dropped_noncal=list(notcal.date.dt.strftime("%Y-%m-%d")),
                       nulls=int(d["close"].isna().sum())))
    return d.set_index("date")["close"]

eq = {c: load_eq(c) for c in ["000300SH", "000905SH", "399006SZ"]}

# CGB 五期限
CGB_T = ["1y", "2y", "5y", "10y", "30y"]
cgb = {}
for t in CGB_T:
    d = rd(f"snapshot_cgb_yield_{t}.csv"); d["date"] = pd.to_datetime(d["date"])
    d = d.drop_duplicates("date").sort_values("date")
    cgb[t] = d.set_index("date")["yield_pct"]
    verify.append(dict(series=f"cgb_{t}", rows_raw=len(d), rows_clean=len(d),
                       start=str(d.date.min().date()), end=str(d.date.max().date()),
                       dropped_noncal=[], nulls=int(d["yield_pct"].isna().sum())))
CGB_END = min(s.index.max() for s in cgb.values())  # 结构性缺口终点

# USD/CNH 两段
ua = rd("snapshot_usdcnh_seg1.csv"); ub = rd("snapshot_usdcnh_seg2.csv")
u = pd.concat([ua, ub], ignore_index=True); u["date"] = pd.to_datetime(u["date"])
u_noncal = u[~u["date"].isin(TSET)]
u = u.drop_duplicates("date").sort_values("date").set_index("date")["usdcnh"]
# 对齐到上交所交易日: 前向填充 (离岸在境内休市日的报价不参与, 仅在SSE交易日取值)
usdcnh = u.reindex(TDAYS).ffill()
verify.append(dict(series="usdcnh", rows_raw=len(ua)+len(ub), rows_clean=int(usdcnh.notna().sum()),
                   start=str(usdcnh.dropna().index.min().date()), end=str(usdcnh.dropna().index.max().date()),
                   dropped_noncal=f"{len(u_noncal)}条非交易日记录(离岸假期报价),对齐SSE后前向填充", nulls=0))

# SPX 对齐到 SSE
sp = rd("snapshot_spx.csv"); sp["date"] = pd.to_datetime(sp["date"])
sp = sp.drop_duplicates("date").sort_values("date").set_index("date")["close"]
spx = sp.reindex(TDAYS).ffill()
verify.append(dict(series="spx", rows_raw=len(sp), rows_clean=int(spx.notna().sum()),
                   start="2018-01-02", end="2026-09-15",
                   dropped_noncal="美股交易日与SSE不一致,对齐SSE后前向填充", nulls=0))

print("[OK] 数据加载与核验完成; CGB_END =", CGB_END.date())
R["asof"] = str(ASOF.date())
R["cgb_end"] = str(CGB_END.date())
R["verify"] = verify
R["n_tdays_full"] = int(len(TDAYS))

# ---- 宏观序列 (用于情景识别与监测) ----
def rd_idx(f, col, parse=True):
    d = rd(f); d["date"] = pd.to_datetime(d["date"])
    d = d.drop_duplicates("date").sort_values("date")
    return d.set_index("date")[col]

dr007 = rd_idx("snapshot_dr007.csv", "dr007")
shib = rd("snapshot_shibor_seg1.csv"); shib2 = rd("snapshot_shibor_seg2.csv")
lpr1 = rd_idx("snapshot_lpr_1y.csv", "lpr_1y")
lpr5_raw = rd("snapshot_lpr_5y.csv"); lpr5_raw["date"] = pd.to_datetime(lpr5_raw["date"])
lpr5 = lpr5_raw.dropna().set_index("date")["lpr_5y"]  # 结构性空值(2019-08前无5Y LPR)不填充
pmi = rd_idx("snapshot_pmi_manufacturing.csv", "pmi_mfg")
afre = rd_idx("snapshot_afre_stock.csv", "afre_stock")
ppi = rd_idx("snapshot_ppi_yoy.csv", "ppi_yoy")
ust10 = rd_idx("snapshot_ust_10y.csv", "yield_pct")

# ============ 第三/四章: 日收益因子面板 ============
# 分析窗口: 所有组合资产日收益均可得的交集 -> 受CGB终点约束
WIN = TDAYS[(TDAYS >= pd.Timestamp("2018-01-02")) & (TDAYS <= CGB_END)].reset_index(drop=True)
R["win_start"] = str(WIN.min().date()); R["win_end"] = str(WIN.max().date())
R["n_win"] = int(len(WIN))

# 久期贡献
dur = rd("params_duration.csv")
DUR = {r.tenor.replace("年","")+"y": r.duration_contribution for r in dur.itertuples()}
# tenor key 对齐: '1y'...'30y'
DURMAP = {"1y":DUR["1y"],"2y":DUR["2y"],"5y":DUR["5y"],"10y":DUR["10y"],"30y":DUR["30y"]}
R["dur_total"] = float(sum(DURMAP.values()))

def factor_returns(window):
    """各资产日收益因子 (window: DatetimeIndex)"""
    idx = window
    out = pd.DataFrame(index=idx)
    # 境内权益: 三指数等按各自收益; 组合内权益按方案权重合成
    for c in eq:
        out["r_"+c] = eq[c].reindex(idx).pct_change()
    # 国债: 关键期限久期折算 r = -sum(Dur_i * dy_i) ; dy 为收益率变动(小数, pct->小数需/100)
    rcgb = pd.Series(0.0, index=idx)
    for t in CGB_T:
        dy = cgb[t].reindex(idx).diff() / 100.0  # pct点->小数
        rcgb = rcgb - DURMAP[t] * dy
    out["r_cgb"] = rcgb
    # 美元现金: USDCNH 升值即美元资产人民币计升值
    out["r_usd"] = usdcnh.reindex(idx).pct_change()
    # 标普500 人民币计: 复合 (1+r_spx_usd)*(1+r_usdcnh)-1
    r_spx_usd = spx.reindex(idx).pct_change()
    r_fx = usdcnh.reindex(idx).pct_change()
    out["r_spx_cny"] = (1+r_spx_usd)*(1+r_fx) - 1
    return out

FR = factor_returns(WIN)

# 方案权重
plans = rd("plans_candidates.csv")
PLAN_COLS = ["w_000300","w_000905","w_399006","w_cgb","w_usd_cash","w_spx_qdii","w_cny_cash"]
def plan_weights(row):
    return dict(EQ300=row.w_000300, EQ500=row.w_000905, EQ399=row.w_399006,
                CGB=row.w_cgb, USD=row.w_usd_cash, SPX=row.w_spx_qdii, CNY=row.w_cny_cash)

# 当前持仓作为"方案0"
cur = rd("params_holdings.csv")
curw = dict(EQ300=0.25,EQ500=0.15,EQ399=0.10,CGB=0.20,USD=0.10,SPX=0.10,CNY=0.10)

def port_daily(w):
    """按方案权重每日再平衡的组合日收益 (现金类日收益=0: CNY货基按0, USD现金收益已含汇率)"""
    r = (w["EQ300"]*FR["r_000300SH"] + w["EQ500"]*FR["r_000905SH"] + w["EQ399"]*FR["r_399006SZ"]
         + w["CGB"]*FR["r_cgb"] + w["USD"]*FR["r_usd"] + w["SPX"]*FR["r_spx_cny"]
         + w["CNY"]*0.0)
    return r.dropna()

PLANW = {"当前": curw}
for row in plans.itertuples():
    PLANW[row.plan_id] = plan_weights(row)

print("[OK] 因子面板构建完成; 分析窗口", R["win_start"], "->", R["win_end"], "共", R["n_win"], "交易日")

# ---- 风险度量 ----
def risk_metrics(r):
    r = r.dropna()
    ann_vol = r.std(ddof=1) * np.sqrt(252)
    var95 = -np.percentile(r, 5); var99 = -np.percentile(r, 1)
    es95 = -r[r <= -var95].mean(); es99 = -r[r <= -var99].mean()
    # 10日: 重叠累计
    cum10 = (1+r).rolling(10).apply(np.prod, raw=True) - 1
    cum10 = cum10.dropna()
    var99_10 = -np.percentile(cum10, 1)
    worst10 = cum10.min()
    worst10_end = cum10.idxmin()
    worst10_start_idx = r.index.get_loc(worst10_end) - 9
    worst10_start = r.index[max(0, worst10_start_idx)]
    # 最大回撤
    nav = (1+r).cumprod()
    peak = nav.cummax(); dd = nav/peak - 1
    mdd = dd.min(); mdd_end = dd.idxmin()
    mdd_start = nav[:mdd_end].idxmax()
    rec = nav[mdd_end:][nav[mdd_end:] >= peak[mdd_end]]
    mdd_rec = rec.index[0] if len(rec) else None
    worst_day = r.min(); worst_day_dt = r.idxmin()
    return dict(ann_vol=float(ann_vol), var95=float(var95), var99=float(var99),
                es95=float(es95), es99=float(es99), var99_10=float(var99_10),
                worst10=float(worst10), worst10_start=str(worst10_start.date()),
                worst10_end=str(worst10_end.date()),
                mdd=float(mdd), mdd_start=str(mdd_start.date()), mdd_end=str(mdd_end.date()),
                mdd_rec=(str(mdd_rec.date()) if mdd_rec is not None else "未修复"),
                worst_day=float(worst_day), worst_day_dt=str(worst_day_dt.date()))

PORTR = {k: port_daily(w) for k, w in PLANW.items()}
RISK = {k: risk_metrics(r) for k, r in PORTR.items()}
R["risk"] = RISK

# 当前组合: 资产统计特征 & 相关矩阵 & 风险贡献
assets_r = pd.DataFrame({
    "沪深300": FR["r_000300SH"], "中证500": FR["r_000905SH"], "创业板": FR["r_399006SZ"],
    "国债": FR["r_cgb"], "美元现金": FR["r_usd"], "标普500(CNY)": FR["r_spx_cny"]
}).dropna()
R["asset_stats"] = {c: dict(mean=float(assets_r[c].mean()), std=float(assets_r[c].std(ddof=1)),
                            ann_vol=float(assets_r[c].std(ddof=1)*np.sqrt(252)),
                            min=float(assets_r[c].min()), max=float(assets_r[c].max()))
                    for c in assets_r.columns}
R["corr"] = assets_r.corr().round(3).to_dict()
# 风险贡献 (当前组合)
wvec = np.array([curw["EQ300"],curw["EQ500"],curw["EQ399"],curw["CGB"],curw["USD"],curw["SPX"]])
cov = assets_r.cov().values
pvar = wvec @ cov @ wvec
mctr = (cov @ wvec)
ctr = wvec * mctr
R["risk_contrib"] = {c: float(ctr[i]/ctr.sum()) for i, c in enumerate(assets_r.columns)}

print("[OK] 风险度量完成; 当前组合年化波动=%.4f ES99=%.4f 10日VaR99=%.4f MDD=%.4f" %
      (RISK["当前"]["ann_vol"], RISK["当前"]["es99"], RISK["当前"]["var99_10"], RISK["当前"]["mdd"]))

# ============ 第四章: 情景识别 ============
def to_month(s): return s.index.to_period("M")
# 月度聚合
def monthly_last(s): return s.groupby(to_month(s)).last()
def monthly_mean(s): return s.groupby(to_month(s)).mean()
def monthly_first(s): return s.groupby(to_month(s)).first()

pmi_m = pmi.copy(); pmi_m.index = pmi.index.to_period("M")
ppi_m = ppi.copy(); ppi_m.index = ppi.index.to_period("M")
afre_m = afre.copy(); afre_m.index = afre.index.to_period("M")
cgb10_mean = monthly_mean(cgb["10y"])
dr007_mean = monthly_mean(dr007)
# 权益指数月收益 (以沪深300为境内权益代表)
hs300_m = monthly_last(eq["000300SH"]); hs300_ret_m = hs300_m.pct_change()
spx_m = monthly_last(spx); spx_ret_m = spx_m.pct_change()
usdcnh_m = monthly_last(usdcnh); usdcnh_chg_m = usdcnh_m.pct_change()
# LPR 当月下调: 当月末值 < 上月末值
lpr1_m = monthly_last(lpr1); lpr1_cut = lpr1_m.diff() < 0
lpr5_m = monthly_last(lpr5); lpr5_cut = lpr5_m.reindex(lpr1_m.index).diff() < 0
# AFRE 同比增速
afre_yoy = afre_m.pct_change(12) * 100

allM = pd.period_range("2018-02", "2026-09", freq="M")
scen_months = {s: [] for s in ["S1","S2","S3","S4"]}
for m in allM:
    pm = pmi_m.get(m, np.nan)
    pm_prev = pmi_m.get(m-1, np.nan)
    c10 = cgb10_mean.get(m, np.nan); c10p = cgb10_mean.get(m-1, np.nan)
    # S1
    cond_s1a = (pm < 50) and (bool(lpr1_cut.get(m, False)) or bool(lpr5_cut.get(m, False)))
    cond_s1b = (not np.isnan(pm) and not np.isnan(pm_prev) and (pm_prev - pm) >= 0.5) and \
               (not np.isnan(c10) and not np.isnan(c10p) and c10 < c10p)
    if cond_s1a or cond_s1b: scen_months["S1"].append(str(m))
    # S2
    ppi_v = ppi_m.get(m, np.nan); ppi_p = ppi_m.get(m-1, np.nan)
    eqret = hs300_ret_m.get(m, np.nan)
    if (not np.isnan(ppi_v) and not np.isnan(ppi_p) and ppi_v > ppi_p) and \
       (not np.isnan(c10) and not np.isnan(c10p) and c10 > c10p) and \
       (not np.isnan(eqret) and eqret < 0):
        scen_months["S2"].append(str(m))
    # S3
    spxr = spx_ret_m.get(m, np.nan); fxr = usdcnh_chg_m.get(m, np.nan)
    if (not np.isnan(spxr) and spxr <= -0.03) or (not np.isnan(fxr) and fxr >= 0.015):
        scen_months["S3"].append(str(m))
    # S4
    af = afre_yoy.get(m, np.nan); afp = afre_yoy.get(m-1, np.nan)
    dr = dr007_mean.get(m, np.nan); drp = dr007_mean.get(m-1, np.nan)
    if (not np.isnan(af) and not np.isnan(afp) and af < afp) and \
       (not np.isnan(dr) and not np.isnan(drp) and dr > drp) and \
       (not np.isnan(eqret) and eqret < 0):
        scen_months["S4"].append(str(m))
R["scen_months"] = scen_months
R["scen_month_counts"] = {k: len(v) for k, v in scen_months.items()}
print("[OK] 情景识别:", R["scen_month_counts"])

# ============ 第四章: 历史窗口校准 ============
# 窗口起点 = 合格月份次月第一个SSE交易日; 长度10个SSE交易日
# 合格判定: 窗口内按(当前组合)权重每日再平衡的累计收益<0; 校准=全部合格窗口因子累计变动中位数
WIN_LEN = 10
cur_r_full = port_daily(curw)  # 用于窗口合格判定(与方案无关的参考组合)

def window_days(month_str):
    m = pd.Period(month_str, "M"); nxt = m + 1
    cand = TDAYS[(TDAYS.dt.to_period("M") == nxt)]
    if len(cand) == 0: return None
    start = cand.min()
    pos = TDAYS[TDAYS >= start].index
    if len(pos) < WIN_LEN: return None
    widx = TDAYS.iloc[pos[0]: pos[0]+WIN_LEN]
    if len(widx) < WIN_LEN: return None
    return widx.reset_index(drop=True)

def factor_cum_changes(widx):
    """窗口10日各因子累计变动: 权益/spx(USD)/usdcnh 用累计收益; cgb各期限用bp变动"""
    d0, d1 = widx.iloc[0], widx.iloc[-1]
    # 需要前一交易日作基点
    prev_pos = TDAYS[TDAYS < d0]
    if len(prev_pos) == 0: return None
    p = prev_pos.iloc[-1]
    def cum_ret(s):
        a = s.reindex([p]).iloc[0]; b = s.reindex([d1]).iloc[0]
        if pd.isna(a) or pd.isna(b): return np.nan
        return b/a - 1
    res = {}
    res["cn_equity"] = cum_ret(eq["000300SH"])
    res["spx_usd"] = cum_ret(spx)
    res["usdcnh"] = cum_ret(usdcnh)
    for t in CGB_T:
        a = cgb[t].reindex([p]).iloc[0]; b = cgb[t].reindex([d1]).iloc[0]
        res["cgb_"+t] = (b - a)  # pct点, =*100 bp? pct点即百分点; bp=pct点*100
    return res

def window_cum_port(widx):
    sub = cur_r_full.reindex(widx)
    if sub.isna().any(): return np.nan
    return (1+sub).prod() - 1

calib = {}
scen_windows = {}
for s, months in scen_months.items():
    qual = []  # 合格窗口因子变动
    wlist = []
    for mo in months:
        widx = window_days(mo)
        if widx is None: continue
        # 窗口须完整落在CGB可得区间 (因子含cgb)
        if widx.max() > CGB_END: continue
        cp = window_cum_port(widx)
        if np.isnan(cp): continue
        if cp < 0:  # 合格
            fc = factor_cum_changes(widx)
            if fc is None or any(pd.isna(list(fc.values()))): continue
            fc["_cum_port"] = cp
            fc["_start"] = str(widx.iloc[0].date()); fc["_end"] = str(widx.iloc[-1].date())
            fc["_month"] = mo
            qual.append(fc); wlist.append(fc)
    # 按跌幅排序
    qual.sort(key=lambda x: x["_cum_port"])
    scen_windows[s] = qual
    if len(qual) == 0:
        calib[s] = {k: 0.0 for k in ["cn_equity","spx_usd","usdcnh"]+["cgb_"+t for t in CGB_T]}
        calib[s]["_n"] = 0
    else:
        keys = ["cn_equity","spx_usd","usdcnh"]+["cgb_"+t for t in CGB_T]
        calib[s] = {k: float(np.median([w[k] for w in qual])) for k in keys}
        calib[s]["_n"] = len(qual)
R["calib"] = calib
R["scen_windows"] = {s: [{k:(round(v,6) if isinstance(v,float) else v) for k,v in w.items()}
                         for w in ws] for s, ws in scen_windows.items()}
print("[OK] 历史窗口校准完成; 合格窗口数:", {s: calib[s]["_n"] for s in calib})

# ============ 第五章: 压力测试 ============
# 委员会沿用冲击
cs = rd("params_committee_shocks.csv")
def parse_cgb(sstr):
    d = {}
    for part in sstr.split(","):
        k, v = part.split(":"); d[k.strip().lower()] = float(v)
    return d  # {'1y':+0.10,...} 单位: 百分点
COMM = {}
for row in cs.itertuples():
    COMM[row.scenario_id] = dict(cn_equity=row.cn_equity_shock, spx_usd=row.spx_usd_shock,
                                 usdcnh=row.usdcnh_shock, cgb=parse_cgb(row.cgb_shock_bp))

def stress_pnl(w, shock):
    """shock: dict(cn_equity, spx_usd, usdcnh, cgb={tenor:pct_point})
       返回4部分贡献(占净值比例) + 合计"""
    eq_w = w["EQ300"] + w["EQ500"] + w["EQ399"]
    c_eq = eq_w * shock["cn_equity"]
    c_spx = w["SPX"] * ((1+shock["spx_usd"])*(1+shock["usdcnh"]) - 1)  # 复合
    c_usd = w["USD"] * shock["usdcnh"]
    c_cgb = 0.0
    for t in CGB_T:
        dy = shock["cgb"].get(t, 0.0) / 100.0  # 百分点->小数
        c_cgb += w["CGB"] * (-DURMAP[t] * dy)
    tot = c_eq + c_spx + c_usd + c_cgb
    return dict(eq=c_eq, spx=c_spx, usd=c_usd, cgb=c_cgb, total=tot)

def calib_shock(s):
    c = calib[s]
    return dict(cn_equity=c["cn_equity"], spx_usd=c["spx_usd"], usdcnh=c["usdcnh"],
                cgb={t: c["cgb_"+t] for t in CGB_T})

STRESS = {}  # STRESS[plan][scenario][shockset] = pnl dict
for pid, w in PLANW.items():
    STRESS[pid] = {}
    for s in ["S1","S2","S3","S4"]:
        STRESS[pid][s] = {"committee": stress_pnl(w, COMM[s]),
                          "historical": stress_pnl(w, calib_shock(s))}
R["stress"] = STRESS

# 每方案最大压力损失 (最负 total)
maxloss = {}
for pid in PLANW:
    worst = None
    for s in ["S1","S2","S3","S4"]:
        for ss in ["committee","historical"]:
            t = STRESS[pid][s][ss]["total"]
            if worst is None or t < worst[0]:
                worst = (t, s, ss)
    maxloss[pid] = dict(loss=float(worst[0]), scenario=worst[1], shockset=worst[2])
R["maxloss"] = maxloss
print("[OK] 压力测试完成; 各方案最大压力损失:",
      {k: f"{v['loss']*100:.2f}%@{v['scenario']}/{v['shockset']}" for k,v in maxloss.items()})

# ============ 第六章: 九项约束检查 ============
def check_plan(pid, w):
    eqsum = w["EQ300"]+w["EQ500"]+w["EQ399"]
    wsum = sum(w.values())
    fx = w["USD"] + w["SPX"]  # 外币敞口: 美元现金 + 标普500 QDII(不对冲)
    if pid in RISK:
        rk = RISK[pid]
    else:
        rk = risk_metrics(port_daily(w))
    if pid in maxloss:
        ml = maxloss[pid]["loss"]
    else:
        _w=None
        for s in ["S1","S2","S3","S4"]:
            for sh in [COMM[s], calib_shock(s)]:
                t=stress_pnl(w,sh)["total"]
                if _w is None or t<_w: _w=t
        ml=_w
    checks = []
    checks.append(("C1","权重合计=100%", abs(wsum-1.0) <= 0.0005, f"{wsum*100:.2f}%", "=100%"))
    checks.append(("C2","权益类<=60%", eqsum <= 0.60+1e-9, f"{eqsum*100:.2f}%", "<=60%"))
    checks.append(("C3","人民币现金[8%,20%]", 0.08-1e-9 <= w["CNY"] <= 0.20+1e-9, f"{w['CNY']*100:.2f}%", "[8%,20%]"))
    checks.append(("C4","国债>=15%", w["CGB"] >= 0.15-1e-9, f"{w['CGB']*100:.2f}%", ">=15%"))
    checks.append(("C5","外币敞口<=25%", fx <= 0.25+1e-9, f"{fx*100:.2f}%", "<=25%"))
    checks.append(("C6","1日ES99<=3.5%", rk["es99"] <= 0.035, f"{rk['es99']*100:.2f}%", "<=3.50%"))
    checks.append(("C7","10日VaR99<=6%", rk["var99_10"] <= 0.06, f"{rk['var99_10']*100:.2f}%", "<=6.00%"))
    checks.append(("C8","最大压力损失<=8%", -ml <= 0.08+1e-9, f"{-ml*100:.2f}%", "<=8.00%"))
    checks.append(("C9","最大压力损失<=7%(缓冲)", -ml <= 0.07+1e-9, f"{-ml*100:.2f}%", "<=7.00%"))
    out = []
    for cid, desc, ok, val, lim in checks:
        # 超限幅度
        exc = ""
        if not ok:
            if cid=="C2": exc=f"+{(eqsum-0.60)*100:.2f}pp"
            elif cid=="C3": exc=f"{(w['CNY']-0.20)*100:+.2f}pp" if w['CNY']>0.20 else f"{(w['CNY']-0.08)*100:+.2f}pp"
            elif cid=="C4": exc=f"{(w['CGB']-0.15)*100:+.2f}pp"
            elif cid=="C5": exc=f"+{(fx-0.25)*100:.2f}pp"
            elif cid=="C6": exc=f"+{(rk['es99']-0.035)*100:.2f}pp"
            elif cid=="C7": exc=f"+{(rk['var99_10']-0.06)*100:.2f}pp"
            elif cid=="C8": exc=f"+{(-ml-0.08)*100:.2f}pp"
            elif cid=="C9": exc=f"+{(-ml-0.07)*100:.2f}pp"
        out.append(dict(check=cid, desc=desc, passed=bool(ok), value=val, limit=lim, exceed=exc))
    allpass = all(c["passed"] for c in out)
    allpass8 = all(c["passed"] for c in out if c["check"]!="C9")
    return dict(items=out, all_pass=allpass, pass_except_buffer=allpass8,
                eqsum=eqsum, fx=fx, wsum=wsum)
CHECKS = {pid: check_plan(pid, w) for pid, w in PLANW.items()}
R["checks"] = CHECKS
print("[OK] 九项约束检查完成; 各方案全通过:",
      {k: CHECKS[k]["all_pass"] for k in CHECKS})

# ============ 第七章: 推荐方案构造 ============
# 规则: USD/SPX 权重不变(各10%); 境内权益按当前权重同比例缩减,合计减配20.5pp(缩减系数0.59);
# 释放资金 10.5pp->国债, 10pp->人民币现金
k_eq = 0.59
rec = dict(EQ300=0.25*k_eq, EQ500=0.15*k_eq, EQ399=0.10*k_eq,
           CGB=0.20+0.105, USD=0.10, SPX=0.10, CNY=0.10+0.10)
rec_eq_cut = (0.25+0.15+0.10) - (rec["EQ300"]+rec["EQ500"]+rec["EQ399"])
R["rec_weights"] = rec
R["rec_eq_cut"] = float(rec_eq_cut)
R["rec_wsum"] = float(sum(rec.values()))
# 校验与 params_holdings 推荐权重一致
hold_rec = {r.asset_class: r.weight_recommended for r in cur.itertuples()}
R["rec_match"] = {
    "EQ300": (round(rec["EQ300"],4), hold_rec["EQ_000300"]),
    "EQ500": (round(rec["EQ500"],4), hold_rec["EQ_000905"]),
    "EQ399": (round(rec["EQ399"],4), hold_rec["EQ_399006"]),
    "CGB": (round(rec["CGB"],4), hold_rec["CGB"]),
    "CNY": (round(rec["CNY"],4), hold_rec["CNY_CASH"])}
PLANW["推荐"] = rec
PORTR["推荐"] = port_daily(rec)
RISK["推荐"] = risk_metrics(PORTR["推荐"])
STRESS["推荐"] = {s: {"committee": stress_pnl(rec, COMM[s]),
                     "historical": stress_pnl(rec, calib_shock(s))} for s in ["S1","S2","S3","S4"]}
_worst=None
for s in ["S1","S2","S3","S4"]:
    for ss in ["committee","historical"]:
        t=STRESS["推荐"][s][ss]["total"]
        if _worst is None or t<_worst[0]: _worst=(t,s,ss)
maxloss["推荐"]=dict(loss=float(_worst[0]),scenario=_worst[1],shockset=_worst[2])
CHECKS["推荐"]=check_plan("推荐",rec)
print("[OK] 推荐方案: 权重合计=%.4f 权益减配=%.1fpp 全通过=%s 最大压力损失=%.2f%%" %
      (R["rec_wsum"], rec_eq_cut*100, CHECKS["推荐"]["all_pass"], -maxloss["推荐"]["loss"]*100))

# ============ 第七章: 唯一性 & 交易清单 & 执行现金路径 ============
# 唯一性: 在相同换手率下, 枚举"权益减配/国债/现金"再分配比例, 找满足九检查且换手最小的组合
# 换手率(单向)=卖出合计/净值. 推荐仅卖出境内权益(减配20.5pp), 买入国债+现金 => 单向换手=20.50%
turnover = rec_eq_cut  # 仅境内权益净卖出
R["turnover"] = float(turnover)
# 唯一性论证: 固定 USD/SPX=10%, 权益按比例缩减系数 k, 释放资金在 CGB/CNY 间分配
# 需同时满足 C4(CGB>=15%,已满足), C3(CNY in[8,20]), C8/C9(压力), C2/C5. 搜索最小减配(最大k)
# (a) 全局最小换手 (仅卖权益、USD/SPX不动): 搜索满足九检查的最小权益减配
glob_best = None
for k in np.arange(0.0, 1.0001, 0.005):
    e3=0.25*k; e5=0.15*k; e9=0.10*k; released=0.50-(e3+e5+e9)
    if released < -1e-9: continue
    for cny_add in np.arange(0.0, min(released,0.10)+1e-9, 0.005):
        cgb_add = released - cny_add
        if cgb_add < -1e-9: continue
        w = dict(EQ300=e3,EQ500=e5,EQ399=e9,CGB=0.20+cgb_add,USD=0.10,SPX=0.10,CNY=0.10+cny_add)
        if not (0.08-1e-9 <= w["CNY"] <= 0.20+1e-9): continue
        if w["CGB"] < 0.15-1e-9: continue
        ml2=min(stress_pnl(w,sh)["total"] for s in ["S1","S2","S3","S4"] for sh in [COMM[s],calib_shock(s)])
        if -ml2 > 0.07+1e-9: continue
        if not check_plan("_t",w)["all_pass"]: continue
        if glob_best is None or released < glob_best["tov"]-1e-9:
            glob_best = dict(tov=float(released), cny_add=float(cny_add), cgb_add=float(cgb_add),
                             maxloss=float(-ml2))
# (b) 同换手率(20.5pp)下的次优: 固定 k=0.59, 变动 CGB/CNY 分配, 比较最大压力损失与缓冲
k_fix = 0.59
frontier = []
for cny_add in np.arange(0.0, rec_eq_cut+1e-9, 0.005):
    cgb_add = rec_eq_cut - cny_add
    if cgb_add < -1e-9: continue
    w = dict(EQ300=0.25*k_fix,EQ500=0.15*k_fix,EQ399=0.10*k_fix,
             CGB=0.20+cgb_add,USD=0.10,SPX=0.10,CNY=0.10+cny_add)
    chk = check_plan("_t", w)
    ml2=min(stress_pnl(w,sh)["total"] for s in ["S1","S2","S3","S4"] for sh in [COMM[s],calib_shock(s)])
    frontier.append(dict(cny_add=round(cny_add*100,2), cgb_add=round(cgb_add*100,2),
                         cny_w=round(w["CNY"]*100,2), cgb_w=round(w["CGB"]*100,2),
                         maxloss=round(-ml2*100,2), all_pass=chk["all_pass"]))
feas = [f for f in frontier if f["all_pass"]]
R["unique"] = dict(
    global_min_turnover=(glob_best["tov"] if glob_best else None),
    global_min_detail=glob_best,
    rec_turnover=float(turnover),
    frontier_same_turnover=frontier,
    n_feasible_same_turnover=len(feas))
print("[OK] 唯一性: 全局最小换手=%.2f%%; 20.5pp档可行分配数=%d" %
      ((glob_best["tov"]*100 if glob_best else -1), len(feas)))

# 交易清单 (万元)
trades = []
for cls, w0, w1, name in [("EQ300",0.25,rec["EQ300"],"沪深300指数基金"),
                           ("EQ500",0.15,rec["EQ500"],"中证500指数基金"),
                           ("EQ399",0.10,rec["EQ399"],"创业板指数基金"),
                           ("CGB",0.20,rec["CGB"],"中长期国债组合"),
                           ("CNY",0.10,rec["CNY"],"人民币现金及货基"),
                           ("USD",0.10,0.10,"美元现金及存款"),
                           ("SPX",0.10,0.10,"标普500 QDII基金")]:
    amt = (w1-w0)*NAV
    if abs(amt) < 1e-6: continue
    trades.append(dict(asset=name, direction=("买入" if amt>0 else "卖出"),
                       amount_10k=round(abs(amt),2), dw_pp=round((w1-w0)*100,2)))
R["trades"] = trades

# 执行现金路径 (规则: 先卖后买; 卖出资金当日可用; 买入国债当日扣款; QDII不动)
# 先卖后买: 卖权益+2050 -> 现金升; 买国债-1050; 现金净+1000 -> CNY 10%->20%
sell_eq = rec_eq_cut*NAV   # 2050
buy_cgb = (rec["CGB"]-0.20)*NAV  # 1050
cash0 = 0.10*NAV  # 1000
# 先卖后买路径
path_sellfirst = [("期初", cash0),
                  ("卖出境内权益", cash0+sell_eq),
                  ("买入国债", cash0+sell_eq-buy_cgb)]
# 先买后卖路径 (违规参考): 先买国债(扣款) 再卖权益
path_buyfirst = [("期初", cash0),
                 ("买入国债", cash0-buy_cgb),
                 ("卖出境内权益", cash0-buy_cgb+sell_eq)]
floor = 0.08*NAV
R["cash_path"] = dict(
    sell_first=[(n, round(c,2), round(c/NAV*100,2)) for n,c in path_sellfirst],
    buy_first=[(n, round(c,2), round(c/NAV*100,2)) for n,c in path_buyfirst],
    floor_10k=floor, floor_pp=8.0,
    sell_first_breaches=any(c<floor-1e-9 for _,c in path_sellfirst),
    buy_first_breaches=any(c<floor-1e-9 for _,c in path_buyfirst))
print("[OK] 执行现金路径; 先卖后买击穿=%s 先买后卖击穿=%s" %
      (R["cash_path"]["sell_first_breaches"], R["cash_path"]["buy_first_breaches"]))

# ============ 第八章: 反向压力测试 & 马氏距离 ============
# 风险因子(日): 境内权益(沪深300)、标普500(USD)、USDCNH、国债(久期加权收益)
# 国债收益因子 = -sum(Dur*dy)/dur_total 归一? 直接用组合国债收益 r_cgb (已久期折算)
f_eq = eq["000300SH"].reindex(WIN).pct_change()
f_spx = spx.reindex(WIN).pct_change()
f_fx = usdcnh.reindex(WIN).pct_change()
f_cgb = FR["r_cgb"]  # 久期折算的国债日收益
F = pd.DataFrame({"eq":f_eq,"spx":f_spx,"fx":f_fx,"cgb":f_cgb}).dropna()
mu = F.mean().values
Sig = F.cov().values
Sinv = np.linalg.inv(Sig)
# 推荐方案对各因子的损益敏感度 a (使得 loss = a·x), x=因子收益向量
w = rec
# eq: 三境内权益合计权重 (都随沪深300因子) ; spx: QDII USD收益 + 汇率复合近似线性: w_SPX*(spx+fx)
# 但复合=加法一阶近似; fx 还含美元现金. 线性化:
a = np.array([
    (w["EQ300"]+w["EQ500"]+w["EQ399"]),  # eq
    w["SPX"],                             # spx(USD)
    w["SPX"]+w["USD"],                    # fx (QDII + 美元现金)
    w["CGB"]                              # cgb 收益因子
])
# 反向压力: min (x-mu)' Sinv (x-mu) s.t. a·x = -L (目标损失)
# 闭式: x* = mu + (c - a·mu) * Sig a / (a'Sig a), c=-L
def reverse_stress(L):
    c = -L
    denom = a @ Sig @ a
    lam = (c - a @ mu) / denom
    xstar = mu + lam * (Sig @ a)
    dm = np.sqrt((xstar-mu) @ Sinv @ (xstar-mu))
    return xstar, dm
L_target = 0.08  # 以8%压力上限为反向目标
xstar, d_min = reverse_stress(L_target)
R["reverse"] = dict(target_loss=L_target,
                    factors=dict(eq=float(xstar[0]), spx=float(xstar[1]),
                                 fx=float(xstar[2]), cgb=float(xstar[3])),
                    maha_dist=float(d_min),
                    daily_sigma=dict(zip(F.columns, F.std(ddof=1).round(5).tolist())))

# 委员会沿用冲击 & 历史校准窗口 的马氏距离 (投影到4因子, cgb折算为收益)
def shock_to_factors(cn_eq, spx_usd, usdcnh_s, cgb_dict):
    cgb_ret = 0.0
    for t in CGB_T:
        cgb_ret += -DURMAP[t]*(cgb_dict.get(t,0.0)/100.0)
    return np.array([cn_eq, spx_usd, usdcnh_s, cgb_ret])
def maha(x): return float(np.sqrt((x-mu)@Sinv@(x-mu)))
# S4 committee (最严情景)
s4c = COMM["S4"]
x_comm = shock_to_factors(s4c["cn_equity"], s4c["spx_usd"], s4c["usdcnh"], s4c["cgb"])
cS4 = calib["S4"]
x_hist = shock_to_factors(cS4["cn_equity"], cS4["spx_usd"], cS4["usdcnh"],
                          {t:cS4["cgb_"+t] for t in CGB_T})
R["reverse"]["maha_committee_S4"] = maha(x_comm)
R["reverse"]["maha_hist_S4"] = maha(x_hist)
print("[OK] 反向压力: 最小马氏距离=%.3f (目标损失8%%); 委员会S4马氏=%.3f 历史S4马氏=%.3f" %
      (d_min, R["reverse"]["maha_committee_S4"], R["reverse"]["maha_hist_S4"]))

# 放大倍数 & 样本内最差10日
R["reverse"]["rec_maxloss"] = -maxloss["推荐"]["loss"]
R["reverse"]["margin_to_8pct"] = 0.08 - (-maxloss["推荐"]["loss"])
R["reverse"]["amplify_to_8pct"] = 0.08 / (-maxloss["推荐"]["loss"])
R["reverse"]["worst10_rec"] = RISK["推荐"]["worst10"]
R["reverse"]["worst10_rec_range"] = (RISK["推荐"]["worst10_start"], RISK["推荐"]["worst10_end"])

# ============ 第八章: 八个监测指标 ============
mon = []
def last_n_tdays(n, upto=ASOF):
    d = TDAYS[TDAYS <= upto]
    return d.iloc[-n:]
# M1 沪深300 20日累计收益
e3 = eq["000300SH"]
w20 = last_n_tdays(21)  # 需20个变动=21点
m1 = e3.reindex(w20).iloc[-1]/e3.reindex(w20).iloc[0]-1
mon.append(("M1","沪深300 20日收益", m1, -0.05, "低于", m1 < -0.05, f"{m1*100:.2f}%","-5.00%"))
# M2 USDCNH 20日变化
u20 = usdcnh.reindex(last_n_tdays(21))
m2 = u20.iloc[-1]/u20.iloc[0]-1
mon.append(("M2","USD/CNH 20日变化", m2, 0.02, "高于", m2 > 0.02, f"{m2*100:.2f}%","+2.00%"))
# M3 DR007: 最近20日均值 vs 此前60日均值
dser = dr007[dr007.index <= ASOF]
r20 = dser.iloc[-20:].mean(); r60 = dser.iloc[-80:-20].mean()
m3 = (r20 - r60)*100  # bp
mon.append(("M3","DR007 资金面变化", m3, 20.0, "高于", m3 > 20.0, f"{m3:+.2f}bp","+20.00bp"))
# M4 10Y CGB 20日变化 (bp) — 数据止于CGB_END
c10 = cgb["10y"]; c10w = c10.iloc[-21:]
m4 = (c10w.iloc[-1]-c10w.iloc[0])*100
mon.append(("M4","10年期国债收益率 20日变化", m4, 10.0, "高于", m4 > 10.0,
            f"{m4:+.2f}bp (截至{c10.index.max().date()})","+10.00bp"))
# M5 UST10Y 20日变化 bp
us = ust10[ust10.index <= ASOF]; usw = us.iloc[-21:]
m5 = (usw.iloc[-1]-usw.iloc[0])*100
mon.append(("M5","美国10年期国债收益率 20日变化", m5, 40.0, "高于", m5 > 40.0, f"{m5:+.2f}bp","+40.00bp"))
# M6 PPI 同比 vs 3个月前
ppi_s = ppi.sort_index()
m6 = ppi_s.iloc[-1] - ppi_s.iloc[-4]
mon.append(("M6","PPI 同比加速", m6, 1.5, "高于", m6 > 1.5, f"{m6:+.2f}pp","+1.50pp"))
# M7 PMI 最新月
m7 = pmi.sort_index().iloc[-1]
mon.append(("M7","制造业PMI 荣枯线", m7, 49.0, "低于", m7 < 49.0, f"{m7:.2f}","49.00"))
# M8 社融存量同比增速 最新 (数据止于2026-04)
afre_s = afre.sort_index(); afre_yoy_last = (afre_s.iloc[-1]/afre_s.iloc[-13]-1)*100
m8 = afre_yoy_last
mon.append(("M8","社融存量增速", m8, 8.0, "低于", m8 < 8.0,
            f"{m8:.2f}% (截至{afre_s.index.max().date()})","8.00%"))
R["monitors"] = [dict(id=m[0], indicator=m[1], value=float(m[2]), threshold=m[3],
                      direction=m[4], triggered=bool(m[5]), value_str=m[6], thr_str=m[7]) for m in mon]
print("[OK] 监测指标; 触发:", [m[0] for m in mon if m[5]])

# ============ 图表 ============
PLANS_ORD = ["当前","方案A","方案B","方案C","推荐"]
COLORS = {"当前":"#888888","方案A":"#1f77b4","方案B":"#2ca02c","方案C":"#ff7f0e","推荐":"#d62728"}

# ---- 图1: 数据覆盖与缺口 ----
cov = [
    ("沪深300/中证500/创业板","2018-01-02","2026-09-15",True),
    ("中债国债曲线(1-30Y)","2018-01-02",str(CGB_END.date()),False),
    ("USD/CNH","2018-01-02","2026-09-15",True),
    ("标普500","2018-01-02","2026-09-15",True),
    ("Shibor/DR007","2018-09-03","2026-09-15",True),
    ("1年期LPR","2018-01-02","2026-07-20",True),
    ("5年期LPR","2019-08-20","2026-08-20",True),
    ("制造业PMI(缺2026-08)","2018-02-01","2026-09-01",True),
    ("社融存量","2018-02-01","2026-04-01",False),
    ("PPI同比","2018-02-01","2026-08-01",True),
    ("美债10Y","2018-01-02","2026-09-15",True),
]
fig, ax = plt.subplots(figsize=(11,6))
for i,(name,s,e,full) in enumerate(cov):
    sd=pd.Timestamp(s); ed=pd.Timestamp(e)
    ax.barh(i, (ed-sd).days, left=sd, height=0.5,
            color=("#4c72b0" if full else "#c44e52"))
ax.axvline(ASOF, color="black", ls="--", lw=1.5, label="分析截至日 2026-09-15")
ax.axvline(CGB_END, color="#c44e52", ls=":", lw=1.3, label=f"国债数据终点 {CGB_END.date()}")
ax.set_yticks(range(len(cov))); ax.set_yticklabels([c[0] for c in cov], fontsize=9)
ax.set_xlabel("日期"); ax.set_title("图1 各数据序列实际覆盖区间与缺口（红=末端缺口/结构空值）")
ax.legend(loc="lower left", fontsize=9); ax.invert_yaxis()
plt.tight_layout(); plt.savefig(os.path.join(CH,"FIN3-WKN-149_chart01_数据覆盖与缺口.png"),dpi=120); plt.close()

# ---- 图2: 历史风险总览 (a 净值曲线; b 风险指标+限额线) ----
fig, (axa, axb) = plt.subplots(1,2,figsize=(14,6))
for pid in PLANS_ORD:
    nav = (1+PORTR[pid]).cumprod()
    axa.plot(nav.index, nav.values, label=pid, color=COLORS[pid], lw=1.2)
axa.set_title("图2-a 各方案累计净值曲线（2018-01→2026-06）")
axa.set_ylabel("累计净值(起点=1)"); axa.legend(fontsize=9); axa.grid(alpha=0.3)
mets = ["ann_vol","es99","var99_10","mdd"]
labels = ["年化波动率","1日ES99","10日VaR99","最大回撤(绝对值)"]
x = np.arange(len(labels)); bw=0.15
for j,pid in enumerate(PLANS_ORD):
    vals = [RISK[pid]["ann_vol"], RISK[pid]["es99"], RISK[pid]["var99_10"], abs(RISK[pid]["mdd"])]
    axb.bar(x+j*bw, [v*100 for v in vals], bw, label=pid, color=COLORS[pid])
axb.axhline(3.5, color="purple", ls="--", lw=1, label="ES99限额3.5%")
axb.axhline(6.0, color="brown", ls="--", lw=1, label="10日VaR99限额6%")
axb.set_xticks(x+2*bw); axb.set_xticklabels(labels, fontsize=9)
axb.set_ylabel("%"); axb.set_title("图2-b 各方案风险指标与限额参考线")
axb.legend(fontsize=8, ncol=2); axb.grid(alpha=0.3, axis="y")
plt.tight_layout(); plt.savefig(os.path.join(CH,"FIN3-WKN-149_chart02_历史风险总览.png"),dpi=120); plt.close()
print("[OK] 图1,图2 已生成")

# ---- 图3: 情景识别与校准 (a 月度识别; b 校准冲击; c 严格程度对比) ----
fig = plt.figure(figsize=(15,10))
axa = fig.add_subplot(2,2,1); axb = fig.add_subplot(2,2,2); axc = fig.add_subplot(2,1,2)
# a 月度识别散点
SC = ["S1","S2","S3","S4"]
for i,s in enumerate(SC):
    ms = [pd.Period(m,"M").to_timestamp() for m in scen_months[s]]
    axa.scatter(ms, [i]*len(ms), s=18, color=list(COLORS.values())[i+1], label=f"{s}({len(ms)})")
axa.set_yticks(range(4)); axa.set_yticklabels(SC)
axa.set_title("图3-a 四情景月度识别结果"); axa.legend(fontsize=8, loc="upper left"); axa.grid(alpha=0.3)
# b 校准冲击 (权益/美股/汇率 + 10Y bp)
width=0.2
xx=np.arange(4)
eqv=[calib[s]["cn_equity"]*100 for s in SC]
spxv=[calib[s]["spx_usd"]*100 for s in SC]
fxv=[calib[s]["usdcnh"]*100 for s in SC]
c10v=[calib[s]["cgb_10y"]*100 for s in SC]  # bp
axb.bar(xx-1.5*width, eqv, width, label="境内权益%", color="#1f77b4")
axb.bar(xx-0.5*width, spxv, width, label="标普500(USD)%", color="#ff7f0e")
axb.bar(xx+0.5*width, fxv, width, label="USDCNH%", color="#2ca02c")
axb.bar(xx+1.5*width, c10v, width, label="10Y国债(bp)", color="#9467bd")
axb.set_xticks(xx); axb.set_xticklabels(SC); axb.axhline(0,color="k",lw=0.5)
axb.set_title("图3-b 各情景历史窗口校准冲击"); axb.legend(fontsize=8); axb.grid(alpha=0.3,axis="y")
# c 严格程度对比: 委员会 vs 历史 的组合压力损失(用当前组合)
commloss=[-stress_pnl(curw,COMM[s])["total"]*100 for s in SC]
histloss=[-stress_pnl(curw,calib_shock(s))["total"]*100 for s in SC]
axc.bar(xx-0.2, commloss, 0.4, label="委员会沿用冲击", color="#d62728")
axc.bar(xx+0.2, histloss, 0.4, label="历史校准冲击", color="#7f7f7f")
axc.set_xticks(xx); axc.set_xticklabels([f"{s}\n{dict(zip(SC,['增长下行','通胀上行','外部冲击','信用收缩']))[s]}" for s in SC])
axc.set_ylabel("当前组合压力损失%"); axc.set_title("图3-c 沿用冲击与历史校准冲击的严格程度对比（当前组合）")
axc.legend(fontsize=9); axc.grid(alpha=0.3,axis="y")
plt.tight_layout(); plt.savefig(os.path.join(CH,"FIN3-WKN-149_chart03_情景识别与校准.png"),dpi=120); plt.close()

# ---- 图4: 方案决策与执行 (a 最大压力损失+限额线; b 现金路径; c 反向压力情景) ----
fig = plt.figure(figsize=(15,10))
axa=fig.add_subplot(2,2,1); axb=fig.add_subplot(2,2,2); axc=fig.add_subplot(2,1,2)
mls=[-maxloss[p]["loss"]*100 for p in PLANS_ORD]
bars=axa.bar(PLANS_ORD, mls, color=[COLORS[p] for p in PLANS_ORD])
axa.axhline(8.0,color="red",ls="--",lw=1.5,label="8%压力损失上限(L8)")
axa.axhline(7.0,color="orange",ls="--",lw=1.5,label="7%缓冲线(L9)")
for b,v in zip(bars,mls): axa.text(b.get_x()+b.get_width()/2,v+0.1,f"{v:.2f}",ha="center",fontsize=8)
axa.set_ylabel("最大压力损失%"); axa.set_title("图4-a 各方案最大压力损失与限额线")
axa.legend(fontsize=8); axa.grid(alpha=0.3,axis="y")
# b 现金路径
sf=R["cash_path"]["sell_first"]; bf=R["cash_path"]["buy_first"]
axb.plot([p[2] for p in sf], "o-", label="先卖后买(合规)", color="#2ca02c", lw=1.8)
axb.plot([p[2] for p in bf], "s--", label="先买后卖(违规)", color="#d62728", lw=1.8)
axb.axhline(8.0,color="red",ls="--",lw=1.5,label="8%现金下限")
axb.set_xticks(range(3)); axb.set_xticklabels([p[0] for p in sf], fontsize=9)
axb.set_ylabel("人民币现金及货基占比%"); axb.set_title("图4-b 调仓执行现金路径与8%下限线")
axb.legend(fontsize=8); axb.grid(alpha=0.3)
# c 反向压力最可能情景
rf=R["reverse"]["factors"]
fnames=["境内权益%","标普500(USD)%","USDCNH%","国债收益%"]
fvals=[rf["eq"]*100, rf["spx"]*100, rf["fx"]*100, rf["cgb"]*100]
axc.barh(fnames, fvals, color=["#1f77b4","#ff7f0e","#2ca02c","#9467bd"])
axc.axvline(0,color="k",lw=0.5)
for i,v in enumerate(fvals): axc.text(v,i,f" {v:.2f}",va="center",fontsize=9)
axc.set_xlabel("因子变动"); axc.set_title("图4-c 反向压力测试最可能情景（推荐方案，目标损失8%，最小马氏距离"+f"{R['reverse']['maha_dist']:.2f}）")
axc.grid(alpha=0.3,axis="x")
plt.tight_layout(); plt.savefig(os.path.join(CH,"FIN3-WKN-149_chart04_方案决策与执行.png"),dpi=120); plt.close()

# ---- 图5: 监测指标触发状态 ----
fig, ax = plt.subplots(figsize=(13,6.5))
mids=[m["id"] for m in R["monitors"]]
# 归一化: 值/阈值方向. 用 文本显示
yy=np.arange(len(mids))
cols=["#d62728" if m["triggered"] else "#2ca02c" for m in R["monitors"]]
ax.barh(yy, [1]*len(mids), color=cols, alpha=0.25, height=0.6)
for i,m in enumerate(R["monitors"]):
    ax.text(0.02, i, f"{m['id']} {m['indicator']}", va="center", fontsize=9)
    ax.text(0.98, i, f"最新 {m['value_str']} | 阈值 {m['thr_str']} | {'触发' if m['triggered'] else '未触发'}",
            va="center", ha="right", fontsize=9, color=("#d62728" if m["triggered"] else "#2ca02c"))
ax.set_yticks([]); ax.set_xlim(0,1); ax.set_xticks([])
ax.set_title("图5 八个监测指标最新值与阈值（红=触发，绿=未触发）"); ax.invert_yaxis()
plt.tight_layout(); plt.savefig(os.path.join(CH,"FIN3-WKN-149_chart05_监测指标触发状态.png"),dpi=120); plt.close()
print("[OK] 图3,图4,图5 已生成")

# ---- 监测表 CSV (按模板字段) ----
mt = rd("template_monitor.csv")
rows = []
for i, m in enumerate(R["monitors"]):
    base = mt.iloc[i].to_dict()
    base["latest_value"] = m["value_str"]
    base["data_asof"] = R["asof"]
    base["status"] = "触发" if m["triggered"] else "未触发"
    base["triggered"] = "是" if m["triggered"] else "否"
    rows.append(base)
pd.DataFrame(rows).to_csv(os.path.join(OUT, "FIN3-WKN-149_monitor_filled.csv"), index=False)

# ---- 导出结果 JSON ----
with open(os.path.join(OUT, "FIN3-WKN-149_results.json"), "w") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=float)
print("[OK] 结果已导出 _results.json 与 monitor_filled.csv")
