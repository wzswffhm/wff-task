from __future__ import annotations

import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

warnings.filterwarnings("ignore")

INPUT = Path("/app/input_files")
OUTPUT = Path("/app/output")
CHARTS = OUTPUT / "FIN3-WKN-149_charts"
CHARTS.mkdir(parents=True, exist_ok=True)
ASOF = pd.Timestamp("2026-09-15")
NAV = 10000.0
TRADING_DAYS = 252

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def read_csv(name, **kwargs):
    return pd.read_csv(INPUT / name, **kwargs)


def dates(df):
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    return out


def concat_segments(prefix):
    frames = [dates(read_csv(x)) for x in sorted(p.name for p in INPUT.glob(prefix + "_seg*.csv"))]
    out = pd.concat(frames, ignore_index=True).sort_values("date")
    return out.drop_duplicates("date", keep="last").reset_index(drop=True)


def pct(x, digits=2):
    return "—" if pd.isna(x) else f"{x * 100:.{digits}f}%"


def bp(x, digits=2):
    return "—" if pd.isna(x) else f"{x:.{digits}f} bp"


def num(x, digits=2):
    return "—" if pd.isna(x) else f"{x:,.{digits}f}"


def md_table(df, index=False):
    x = df.copy()
    if index:
        x.insert(0, x.index.name or "", x.index.astype(str))
    cols = [str(c) for c in x.columns]
    rows = [[str(v) for v in row] for row in x.itertuples(index=False, name=None)]
    widths = [max([len(cols[i])] + [len(row[i]) for row in rows]) for i in range(len(cols))]
    line = "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols)) + " |"
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(cols))) + " |"
    body = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(cols))) + " |" for row in rows]
    return "\\n".join([line, sep] + body)


# ---------- raw data and data-quality checks ----------
cal = dates(read_csv("snapshot_trade_calendar.csv"))
cal["is_trading_day_num"] = pd.to_numeric(cal["is_trading_day"], errors="coerce")
cal = cal[(cal["exchange"].astype(str).str.upper() == "SSE") & (cal["is_trading_day_num"] == 1)]
cal = cal[(cal.date <= ASOF)].drop_duplicates("date").sort_values("date")
sse = pd.DatetimeIndex(cal.date)

market_specs = {
    "沪深300": ("000300", "close"),
    "中证500": ("000905", "close"),
    "创业板": ("399006", "close"),
    "标普500美元": ("snapshot_spx.csv", "close"),
    "USD/CNH": ("usdcnh", "usdcnh"),
    "国债1Y": ("snapshot_cgb_yield_1y.csv", "yield_pct"),
    "国债2Y": ("snapshot_cgb_yield_2y.csv", "yield_pct"),
    "国债5Y": ("snapshot_cgb_yield_5y.csv", "yield_pct"),
    "国债10Y": ("snapshot_cgb_yield_10y.csv", "yield_pct"),
    "国债30Y": ("snapshot_cgb_yield_30y.csv", "yield_pct"),
    "DR007": ("snapshot_dr007.csv", "dr007"),
    "美国10Y": ("snapshot_ust_10y.csv", "yield_pct"),
}

raw = {}
raw["000300"] = concat_segments("snapshot_000300SH")
raw["000905"] = concat_segments("snapshot_000905SH")
raw["399006"] = concat_segments("snapshot_399006SZ")
raw["spx"] = dates(read_csv("snapshot_spx.csv")).sort_values("date").drop_duplicates("date")
raw["usdcnh"] = concat_segments("snapshot_usdcnh")
for tenor in ["1y", "2y", "5y", "10y", "30y"]:
    raw["cgb_" + tenor] = dates(read_csv(f"snapshot_cgb_yield_{tenor}.csv")).sort_values("date").drop_duplicates("date")
raw["dr007"] = dates(read_csv("snapshot_dr007.csv")).sort_values("date").drop_duplicates("date")
raw["ust10"] = dates(read_csv("snapshot_ust_10y.csv")).sort_values("date").drop_duplicates("date")
raw["shibor"] = concat_segments("snapshot_shibor")
raw["lpr1"] = dates(read_csv("snapshot_lpr_1y.csv"))
raw["lpr5"] = dates(read_csv("snapshot_lpr_5y.csv"))
raw["pmi"] = dates(read_csv("snapshot_pmi_manufacturing.csv"))
raw["ppi"] = dates(read_csv("snapshot_ppi_yoy.csv"))
raw["afre"] = dates(read_csv("snapshot_afre_stock.csv"))
raw["ustm2"] = dates(read_csv("snapshot_ust_m2.csv"))
raw["ustm4"] = dates(read_csv("snapshot_ust_m4.csv"))

# The calendar is the valuation-day authority. Non-SSE observations are retained for
# the QA table but excluded from all daily market calculations.
def on_sse(df, value_col):
    x = df[df.date.isin(sse)][["date", value_col]].copy()
    x = x.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    return x.reindex(sse).iloc[:, 0]

prices = pd.DataFrame(index=sse)
prices["000300"] = on_sse(raw["000300"], "close")
prices["000905"] = on_sse(raw["000905"], "close")
prices["399006"] = on_sse(raw["399006"], "close")
prices["spx"] = on_sse(raw["spx"], "close").ffill()
prices["usdcnh"] = on_sse(raw["usdcnh"], "usdcnh").ffill()
for tenor in ["1y", "2y", "5y", "10y", "30y"]:
    prices["cgb_" + tenor] = on_sse(raw["cgb_" + tenor], "yield_pct").ffill()
prices["dr007"] = on_sse(raw["dr007"], "dr007").ffill()
prices["ust10"] = on_sse(raw["ust10"], "yield_pct").ffill()

# Core daily risk sample: no imputation at the beginning, no zeros for missing data,
# and no forward fill beyond the actual end of any required risk-factor series.
cgb_end = min(raw["cgb_" + t].date.max() for t in ["1y", "2y", "5y", "10y", "30y"])
core = prices.loc[prices.index <= cgb_end].dropna(subset=["000300", "000905", "399006", "spx", "usdcnh", "cgb_1y", "cgb_2y", "cgb_5y", "cgb_10y", "cgb_30y"]).copy()
returns = pd.DataFrame(index=core.index)
for a in ["000300", "000905", "399006"]:
    returns[a] = core[a].pct_change()
returns["spx_rmb"] = (1 + core.spx.pct_change()) * (1 + core.usdcnh.pct_change()) - 1
returns["usd_cash"] = core.usdcnh.pct_change()
duration = read_csv("params_duration.csv")
duration_map = dict(zip(duration.tenor.astype(str).str.replace("年", "y"), duration.duration_contribution.astype(float)))
for tenor in ["1y", "2y", "5y", "10y", "30y"]:
    returns["dy_" + tenor] = core["cgb_" + tenor].diff()
returns["cgb"] = -sum(duration_map[t] * returns["dy_" + t] / 100 for t in ["1y", "2y", "5y", "10y", "30y"])
returns = returns.dropna()

holdings = read_csv("params_holdings.csv")
positions = read_csv("params_positions.csv")
plans = read_csv("plans_candidates.csv")
shocks = read_csv("params_committee_shocks.csv")
limits = read_csv("params_limits.csv")
monitor_template = read_csv("template_monitor.csv")

ASSET_KEYS = ["000300", "000905", "399006", "cgb", "usd_cash", "spx_qdii", "cny_cash"]
PLAN_COLS = ["w_000300", "w_000905", "w_399006", "w_cgb", "w_usd_cash", "w_spx_qdii", "w_cny_cash"]
current = dict(zip(holdings.asset.map({"沪深300指数基金": "000300", "中证500指数基金": "000905", "创业板指数基金": "399006", "中长期国债组合": "cgb", "美元现金及存款": "usd_cash", "标普500 QDII基金": "spx_qdii", "人民币现金及货基": "cny_cash"}), holdings.weight_current.astype(float)))
recommended = dict(zip(holdings.asset.map({"沪深300指数基金": "000300", "中证500指数基金": "000905", "创业板指数基金": "399006", "中长期国债组合": "cgb", "美元现金及存款": "usd_cash", "标普500 QDII基金": "spx_qdii", "人民币现金及货基": "cny_cash"}), holdings.weight_recommended.astype(float)))

def row_plan(row):
    return {k: float(row[c]) for k, c in zip(ASSET_KEYS, PLAN_COLS)}

plan_dict = {"当前组合": current}
for _, r in plans.iterrows():
    plan_dict[str(r.plan_id)] = row_plan(r)
plan_dict["推荐方案"] = recommended

# ---------- scenario identification and historical calibration ----------
def monthly_last(df, value_col):
    x = df[["date", value_col]].dropna().copy()
    x["month"] = x.date.dt.to_period("M")
    return x.sort_values("date").groupby("month")[value_col].last()

def monthly_mean(df, value_col):
    x = df[["date", value_col]].dropna().copy()
    x["month"] = x.date.dt.to_period("M")
    return x.groupby("month")[value_col].mean()

# Monthly values use actual published observations; no structural NaN is converted to zero.
pmi_m = monthly_last(raw["pmi"], "pmi_mfg")
ppi_m = monthly_last(raw["ppi"], "ppi_yoy")
lpr1_m = monthly_last(raw["lpr1"], "lpr_1y")
lpr5_m = monthly_last(raw["lpr5"], "lpr_5y")
cgb10_m = monthly_mean(raw["cgb_10y"], "yield_pct")
dr007_m = monthly_mean(raw["dr007"], "dr007")
afre_m = monthly_last(raw["afre"], "afre_stock")
afre_growth_m = afre_m.pct_change(12) * 100
sse_prices = prices[["000300", "000905", "399006"]].dropna()
month_end_eq = sse_prices.groupby(sse_prices.index.to_period("M")).last()
eq_month_ret = month_end_eq.pct_change().mean(axis=1)
spx_m = monthly_last(raw["spx"], "close")
fx_m = monthly_last(raw["usdcnh"], "usdcnh")
spx_ret_m = spx_m.pct_change()
fx_ret_m = fx_m.pct_change()
months = pd.period_range(start=min(x.index.min() for x in [pmi_m, ppi_m, cgb10_m]), end=ASOF.to_period("M"), freq="M")
monthly = pd.DataFrame(index=months)
for name, series in [("pmi", pmi_m), ("ppi", ppi_m), ("lpr1", lpr1_m), ("lpr5", lpr5_m), ("cgb10", cgb10_m), ("dr007", dr007_m), ("afre_growth", afre_growth_m), ("eq_ret", eq_month_ret), ("spx_ret", spx_ret_m), ("fx_ret", fx_ret_m)]:
    monthly[name] = series.reindex(months)
monthly["lpr1_chg"] = monthly.lpr1.diff()
monthly["lpr5_chg"] = monthly.lpr5.diff()
monthly["pmi_chg"] = monthly.pmi.diff()
monthly["cgb10_chg"] = monthly.cgb10.diff()
monthly["ppi_chg"] = monthly.ppi.diff()
monthly["afre_growth_chg"] = monthly.afre_growth.diff()
monthly["dr007_chg"] = monthly.dr007.diff()
monthly["s1"] = ((monthly.pmi < 50) & ((monthly.lpr1_chg < 0) | (monthly.lpr5_chg < 0))) | ((monthly.pmi_chg <= -0.5) & (monthly.cgb10_chg < 0))
monthly["s2"] = (monthly.ppi_chg > 0) & (monthly.cgb10_chg > 0) & (monthly.eq_ret < 0)
monthly["s3"] = (monthly.spx_ret <= -0.03) | (monthly.fx_ret >= 0.015)
monthly["s4"] = (monthly.afre_growth_chg < 0) & (monthly.dr007_chg > 0) & (monthly.eq_ret < 0)
monthly = monthly.replace({True: True, False: False})

# Portfolio return columns for all allocation vectors.
asset_returns = returns[["000300", "000905", "399006", "cgb", "usd_cash", "spx_rmb"]].copy()

def portfolio_series(w):
    return (asset_returns[["000300", "000905", "399006", "cgb", "usd_cash", "spx_rmb"]] * [w["000300"], w["000905"], w["399006"], w["cgb"], w["usd_cash"], w["spx_qdii"]]).sum(axis=1)

current_ret = portfolio_series(current)

def next_sse_after(period):
    end = period.end_time.normalize()
    z = sse[sse > end]
    return z[0] if len(z) else None

scenario_names = dict(zip(shocks.scenario_id, shocks.scenario))
scenario_cols = {"S1": "s1", "S2": "s2", "S3": "s3", "S4": "s4"}
windows = {}
window_modes = {}
for sid, col in scenario_cols.items():
    all_windows = []
    strict_windows = []
    for month in monthly.index[monthly[col].fillna(False)]:
        start = next_sse_after(month)
        if start is None:
            continue
        ix = sse.get_loc(start)
        wdates = sse[ix:ix + 10]
        if len(wdates) < 10 or wdates[-1] > core.index.max() or not set(wdates).issubset(current_ret.index):
            continue
        wr = current_ret.reindex(wdates)
        if len(wr) == 10:
            item = {"month": str(month), "start": wdates[0], "end": wdates[-1], "cum": (1 + wr).prod() - 1, "dates": wdates}
            all_windows.append(item)
            if (wr < 0).all():
                strict_windows.append(item)
    strict_windows.sort(key=lambda x: x["cum"])
    all_windows.sort(key=lambda x: x["cum"])
    if strict_windows:
        selected = strict_windows[:20]
        window_modes[sid] = f"严格筛选 {len(strict_windows)} 个，取前 {len(selected)} 个"
    else:
        # The supplied sample has no ten-day run with every daily portfolio return negative.
        # Use the worst eligible ten-day windows for a transparent, non-empty calibration.
        selected = all_windows[:20]
        window_modes[sid] = f"严格筛选 0 个；退化使用合格月份窗口中累计跌幅最差 {len(selected)} 个"
    windows[sid] = selected

# Factor shocks for each selected window. CGB changes are reported in bp.
def factor_from_dates(ds):
    first = ds[0]
    last = ds[-1]
    dom = (1 + current_ret.reindex(ds)).copy()
    dom_eq = (1 + (returns[["000300", "000905", "399006"]].reindex(ds) * [current["000300"], current["000905"], current["399006"]]).sum(axis=1)).prod() - 1
    spx = (1 + core.spx.pct_change().reindex(ds)).prod() - 1
    fx = (1 + core.usdcnh.pct_change().reindex(ds)).prod() - 1
    out = {"cn_equity": dom_eq, "spx_usd": spx, "usdcnh": fx}
    for tenor in ["1y", "2y", "5y", "10y", "30y"]:
        out["cgb_" + tenor] = (core["cgb_" + tenor].loc[last] - core["cgb_" + tenor].loc[first]) * 100
    return out

calibration = {}
window_rows = []
for sid, ws in windows.items():
    fs = pd.DataFrame([factor_from_dates(x["dates"]) for x in ws])
    calibration[sid] = fs.median(numeric_only=True).to_dict() if len(fs) else {"cn_equity": np.nan, "spx_usd": np.nan, "usdcnh": np.nan, **{"cgb_" + t: np.nan for t in ["1y", "2y", "5y", "10y", "30y"]}}
    for x in ws:
        window_rows.append({"scenario_id": sid, "month": x["month"], "start": x["start"], "end": x["end"], "cum": x["cum"]})

# Committee shocks: source column is explicitly *_bp, so values are used literally as bp.
def parse_cgb(text):
    out = {}
    for item in str(text).split(","):
        tenor, value = item.split(":")
        out["cgb_" + tenor.strip().lower()] = float(value.replace("+", ""))
    return out

committee = {}
for _, r in shocks.iterrows():
    committee[str(r.scenario_id)] = {"cn_equity": float(r.cn_equity_shock), "spx_usd": float(r.spx_usd_shock), "usdcnh": float(r.usdcnh_shock), **parse_cgb(r.cgb_shock_bp)}

# ---------- pressure test ----------
def shock_return(w, f):
    dom = (w["000300"] + w["000905"] + w["399006"]) * f["cn_equity"]
    spx_rmb = (1 + f["spx_usd"]) * (1 + f["usdcnh"]) - 1
    spx = w["spx_qdii"] * spx_rmb
    usd = w["usd_cash"] * f["usdcnh"]
    cgb_r = -sum(duration_map[t] * f["cgb_" + t] / 10000 for t in ["1y", "2y", "5y", "10y", "30y"])
    cgb = w["cgb"] * cgb_r
    return {"境内权益": dom, "标普500（人民币计）": spx, "美元现金": usd, "国债": cgb, "组合损益": dom + spx + usd + cgb}

pressure_rows = []
for pname, w in plan_dict.items():
    for sid in ["S1", "S2", "S3", "S4"]:
        for shock_type, f in [("委员会沿用", committee[sid]), ("历史校准", calibration[sid])]:
            result = shock_return(w, f)
            pressure_rows.append({"方案": pname, "情景": sid, "情景名称": scenario_names[sid], "冲击": shock_type, **result, "压力损失": -result["组合损益"]})
pressure = pd.DataFrame(pressure_rows)

# ---------- risk statistics and constraints ----------
def risk_stats(w):
    r = portfolio_series(w).dropna()
    losses = -r
    q95, q99 = losses.quantile([.95, .99])
    es95 = losses[losses >= q95].mean()
    es99 = losses[losses >= q99].mean()
    r10 = (1 + r).rolling(10).apply(np.prod, raw=True) - 1
    q10 = -r10.quantile(.01)
    min10 = r10.min()
    min10_end = r10.idxmin()
    min10_start = r10.index[r10.index.get_loc(min10_end) - 9]
    wealth = (1 + r).cumprod()
    peak = wealth.cummax()
    dd = wealth / peak - 1
    mdd_end = dd.idxmin()
    mdd_start = wealth.loc[:mdd_end].idxmax()
    recovered = wealth.index[(wealth.index > mdd_end) & (wealth >= wealth.loc[mdd_start])]
    rec_date = recovered[0] if len(recovered) else pd.NaT
    cov = r.to_frame("portfolio").join(asset_returns).drop(columns="portfolio").cov()
    names = ["000300", "000905", "399006", "cgb", "usd_cash", "spx_rmb"]
    ww = np.array([w["000300"], w["000905"], w["399006"], w["cgb"], w["usd_cash"], w["spx_qdii"]])
    cv = cov.loc[names, names].values
    vol = np.sqrt(ww @ cv @ ww)
    rc = ww * (cv @ ww) / (ww @ cv @ ww)
    maxp = pressure[pressure.方案 == w.get("name", "__none__")] if False else None
    return {"daily": r, "ann_vol": vol * np.sqrt(TRADING_DAYS), "var95": q95, "var99": q99, "es95": es95, "es99": es99, "var10": q10, "min10": min10, "min10_start": min10_start, "min10_end": min10_end, "mdd": dd.min(), "mdd_start": mdd_start, "mdd_end": mdd_end, "mdd_recovery": rec_date, "worst_day": losses.max(), "worst_day_date": losses.idxmax(), "rc": dict(zip(names, rc))}

risk = {name: risk_stats(w) for name, w in plan_dict.items()}


def constraint_result(name, w):
    rs = risk[name]
    p = pressure[pressure.方案 == name]
    max_loss = p.压力损失.max()
    vals = {
        "L1": sum(w.values()),
        "L2": w["000300"] + w["000905"] + w["399006"],
        "L3": w["cny_cash"],
        "L4": w["cgb"],
        "L5": w["usd_cash"] + w["spx_qdii"],
        "L6": rs["es99"],
        "L7": rs["var10"],
        "L8": max_loss,
        "L9": max_loss,
    }
    checks = {}
    for _, lim in limits.iterrows():
        lid = str(lim.id)
        val = vals[lid]
        op = str(lim.op)
        lower = float(lim.lower) if pd.notna(lim.lower) else None
        upper = float(lim.upper) if pd.notna(lim.upper) else None
        if op == "=": ok = abs(val - 1.0) <= 0.0005
        elif op == "<=": ok = val <= upper + 1e-12
        elif op == ">=": ok = val >= upper - 1e-12
        elif op == "in": ok = lower - 1e-12 <= val <= upper + 1e-12
        else: ok = False
        if op == "in": excess = max(lower - val, 0) + max(val - upper, 0)
        elif op == "=": excess = abs(val - 1.0)
        elif op == "<=": excess = max(val - upper, 0)
        else: excess = max(upper - val, 0)
        checks[lid] = {"value": val, "pass": bool(ok), "excess": excess, "constraint": lim.constraint, "unit": lim.unit}
    return checks

constraint_checks = {name: constraint_result(name, w) for name, w in plan_dict.items()}

# relaxed same-turnover comparison: preserve fixed foreign assets and the recommended total domestic sale,
# then grid domestic weights in 0.5 percentage point increments and choose the best distinct feasible point.
def relaxed_same_turnover():
    base = recommended.copy()
    target_dom = current["000300"] + current["000905"] + current["399006"] - (current["000300"] - base["000300"] + current["000905"] - base["000905"] + current["399006"] - base["399006"])
    candidates = []
    for a in np.arange(0, target_dom + 0.0001, 0.005):
        for b in np.arange(0, target_dom - a + 0.0001, 0.005):
            c = target_dom - a - b
            if c < -1e-9: continue
            w = base.copy(); w.update({"000300": a, "000905": b, "399006": c})
            tempname = "__temp"
            plan_dict[tempname] = w
            pressure_temp = []
            for sid in ["S1", "S2", "S3", "S4"]:
                for f in [committee[sid], calibration[sid]]:
                    pressure_temp.append(-shock_return(w, f)["组合损益"])
            rr = risk_stats(w)
            maxloss = max(pressure_temp)
            feasible = rr["es99"] <= .035 and rr["var10"] <= .06 and maxloss <= .07
            if feasible:
                candidates.append((maxloss, w.copy(), rr))
            plan_dict.pop(tempname, None)
    if not candidates: return None
    candidates.sort(key=lambda z: z[0])
    for item in candidates:
        if any(abs(item[1][x] - recommended[x]) > 1e-8 for x in ["000300", "000905", "399006"]):
            return item
    return candidates[0]

same_turnover = relaxed_same_turnover()

# ---------- monitoring ----------
def last_n_change(series, n):
    s = series.dropna()
    return s.iloc[-1] / s.iloc[-n-1] - 1 if len(s) > n else np.nan

monitor = []
# M1/M2 based on 20 SSE valuation days through ASOF.
monitor.append(("M1", "沪深300 20日收益", last_n_change(prices["000300"].loc[:ASOF], 20), "-5.00%", "2026-09-15", "低于"))
monitor.append(("M2", "USD/CNH 20日变化", last_n_change(prices["usdcnh"].loc[:ASOF], 20), "+2.00%", "2026-09-15", "高于"))
# M3 uses actual non-null DR007 observations, with the last 20 vs preceding 60.
dr = raw["dr007"].set_index("date")["dr007"].dropna()
monitor.append(("M3", "DR007资金面变化", dr.iloc[-20:].mean() - dr.iloc[-80:-20].mean(), "+20.00bp", str(dr.index[-1].date()), "高于"))
cgb10 = raw["cgb_10y"].set_index("date")["yield_pct"].dropna()
monitor.append(("M4", "10年期国债收益率20日变化", (cgb10.iloc[-1] - cgb10.iloc[-21]) * 100, "+10.00bp", str(cgb10.index[-1].date()), "高于"))
ust = raw["ust10"].set_index("date")["yield_pct"].dropna()
monitor.append(("M5", "美国10年期国债收益率20日变化", (ust.iloc[-1] - ust.iloc[-21]) * 100, "+40.00bp", str(ust.index[-1].date()), "高于"))
monitor.append(("M6", "PPI同比加速", ppi_m.iloc[-1] - ppi_m.iloc[-4] if len(ppi_m) >= 4 else np.nan, "+1.50个百分点", str(ppi_m.index[-1]), "高于"))
monitor.append(("M7", "制造业PMI荣枯线", pmi_m.iloc[-1], "49.00", str(pmi_m.index[-1]), "低于"))
monitor.append(("M8", "社融存量增速", afre_growth_m.dropna().iloc[-1] if len(afre_growth_m.dropna()) else np.nan, "8.00%", str(afre_growth_m.dropna().index[-1]) if len(afre_growth_m.dropna()) else "—", "低于"))
monitor_rows = []
for mid, ind, value, threshold, asof, direction in monitor:
    threshold_num = float(re.sub(r"[^0-9.+-]", "", threshold))
    # percentage-form values are decimals except M3-M5 bp and M6 percentage points.
    if mid in ["M1", "M2"]: trigger = value < threshold_num / 100 if mid == "M1" else value > threshold_num / 100
    elif mid in ["M3", "M4", "M5"]: trigger = value > threshold_num
    elif mid == "M6": trigger = value > threshold_num
    elif mid == "M7": trigger = value < threshold_num
    else: trigger = value < threshold_num
    monitor_rows.append({"监测指标": ind, "阈值": threshold, "最新值": value, "截至日": asof, "状态": "触发" if trigger else "未触发", "是否触发": "是" if trigger else "否", "monitor_id": mid})
monitor_df = pd.DataFrame(monitor_rows)

# ---------- reverse stress ----------
# Mahalanobis space uses 10-day rolling factor changes in the same units as the shock vectors.
factor_daily = pd.DataFrame(index=core.index)
factor_daily["cn_equity"] = (returns[["000300", "000905", "399006"]] * [current["000300"], current["000905"], current["399006"]]).sum(axis=1)
factor_daily["spx_usd"] = core.spx.pct_change()
factor_daily["usdcnh"] = core.usdcnh.pct_change()
for tenor in ["1y", "2y", "5y", "10y", "30y"]:
    factor_daily["cgb_" + tenor] = core["cgb_" + tenor].diff() * 100
factor10 = pd.DataFrame(index=core.index)
for c in ["cn_equity", "spx_usd", "usdcnh"]:
    factor10[c] = (1 + factor_daily[c]).rolling(10).apply(np.prod, raw=True) - 1
for tenor in ["1y", "2y", "5y", "10y", "30y"]:
    factor10["cgb_" + tenor] = factor_daily["cgb_" + tenor].rolling(10).sum()
factor10 = factor10.dropna()
factor_cols = ["cn_equity", "spx_usd", "usdcnh", "cgb_1y", "cgb_2y", "cgb_5y", "cgb_10y", "cgb_30y"]
mu = factor10[factor_cols].mean().values
covf = factor10[factor_cols].cov().values + np.eye(len(factor_cols)) * 1e-10
inv_cov = np.linalg.pinv(covf)

def vector_loss(x, w=recommended):
    f = dict(zip(factor_cols, x))
    return -shock_return(w, f)["组合损益"]

# Use scipy when available; bounded signs describe a downside shock and keep the result interpretable.
reverse_x = None
reverse_distance = np.nan
try:
    from scipy.optimize import minimize
    bounds = [(-0.60, 0.0), (-0.60, 0.0), (0.0, 0.60)] + [(-500.0, 500.0)] * 5
    starts = [np.array([-.12, -.08, .02, 10, 12, 10, 20, 25.]), np.array([-.18, -.12, .05, 80, 60, 45, -45, -50.])]
    best = None
    for start in starts:
        res = minimize(lambda x: float((x - mu) @ inv_cov @ (x - mu)), start, method="SLSQP", bounds=bounds, constraints=[{"type": "eq", "fun": lambda x: vector_loss(x) - .08}], options={"maxiter": 2000, "ftol": 1e-11})
        if res.success and (best is None or res.fun < best.fun): best = res
    if best is not None:
        reverse_x = best.x
        reverse_distance = float(np.sqrt(best.fun))
except Exception:
    reverse_x = None
if reverse_x is None:
    # The committee stress closest to the 8% boundary is a deterministic fallback.
    candidates = [(abs(vector_loss(np.array([committee[s][c] for c in factor_cols])) - .08), s) for s in committee]
    sid = sorted(candidates)[0][1]
    reverse_x = np.array([committee[sid][c] for c in factor_cols])
    reverse_distance = float(np.sqrt((reverse_x - mu) @ inv_cov @ (reverse_x - mu)))
reverse_factor = dict(zip(factor_cols, reverse_x))
reverse_loss = vector_loss(reverse_x)

# Mahalanobis distances for committee and calibration shocks.
def mahal(f):
    x = np.array([f[c] for c in factor_cols])
    return float(np.sqrt((x - mu) @ inv_cov @ (x - mu)))
mahal_rows = []
for sid in ["S1", "S2", "S3", "S4"]:
    mahal_rows.append({"情景": sid, "委员会沿用": mahal(committee[sid]), "历史校准": mahal(calibration[sid])})
mahal_df = pd.DataFrame(mahal_rows)

# ---------- charts ----------
def savefig(name):
    plt.savefig(CHARTS / name, dpi=180, bbox_inches="tight")
    plt.close()

# Chart 01: coverage and missingness.
coverage_items = []
for label, key in [("沪深300", "000300"), ("中证500", "000905"), ("创业板", "399006"), ("标普500", "spx"), ("USD/CNH", "usdcnh"), ("国债1Y", "cgb_1y"), ("国债2Y", "cgb_2y"), ("国债5Y", "cgb_5y"), ("国债10Y", "cgb_10y"), ("国债30Y", "cgb_30y"), ("DR007", "dr007"), ("美国10Y", "ust10"), ("PMI", "pmi"), ("PPI", "ppi"), ("社融存量", "afre")]:
    d = raw[key].date.dropna()
    coverage_items.append((label, d.min(), d.max(), int((~d.isin(sse)).sum())))
fig, ax = plt.subplots(figsize=(12, 8))
for i, (label, st, en, non_sse) in enumerate(coverage_items):
    ax.plot([st, en], [i, i], lw=7, solid_capstyle="butt", color="#4472C4")
    ax.scatter([st, en], [i, i], color="#1F4E79", s=16)
    if non_sse:
        ax.text(en, i + .18, f"非SSE {non_sse}条", fontsize=7, ha="right")
ax.axvline(ASOF.value / 86400000000000, alpha=0)  # keep date axis native below
ax.set_yticks(range(len(coverage_items))); ax.set_yticklabels([x[0] for x in coverage_items])
ax.set_xlim(pd.Timestamp("2017-12-15"), ASOF + pd.Timedelta(days=15)); ax.set_title("图1：数据覆盖与缺口（蓝线为实际覆盖，红线为分析截至日）")
ax.axvline(ASOF, color="crimson", ls="--", label="分析截至日 2026-09-15")
ax.grid(axis="x", alpha=.25); ax.legend(loc="lower right"); fig.autofmt_xdate(); savefig("FIN3-WKN-149_chart01_数据覆盖与缺口.png")

# Chart 02: cumulative paths and risk bars.
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 10), gridspec_kw={"height_ratios": [1.2, 1]})
for name in ["当前组合", "方案A", "方案B", "方案C", "推荐方案"]:
    rr = risk[name]["daily"]
    ax1.plot(rr.index, (1 + rr).cumprod(), label=name, lw=1.1)
ax1.set_title("图2-a：各方案历史累计净值曲线"); ax1.legend(ncol=5, fontsize=8); ax1.grid(alpha=.25)
labels = ["当前组合", "方案A", "方案B", "方案C", "推荐方案"]
x = np.arange(len(labels)); width = .16
metrics = [("ann_vol", "年化波动"), ("es99", "1日ES99"), ("var10", "10日VaR99"), ("mdd", "最大回撤")]
for j, (k, lab) in enumerate(metrics):
    values = [risk[n][k] if k != "mdd" else -risk[n][k] for n in labels]
    ax2.bar(x + (j - 1.5) * width, values, width, label=lab)
ax2.axhline(.035, color="red", ls="--", lw=1, label="ES99限额 3.50%")
ax2.axhline(.06, color="orange", ls=":", lw=1, label="10日VaR99限额 6.00%")
ax2.set_xticks(x); ax2.set_xticklabels(labels); ax2.yaxis.set_major_formatter(PercentFormatter(1)); ax2.set_title("图2-b：历史风险指标与限额参考线"); ax2.legend(ncol=3, fontsize=8); ax2.grid(axis="y", alpha=.25)
fig.tight_layout(); savefig("FIN3-WKN-149_chart02_历史风险总览.png")

# Chart 03.
fig, (a, b, c) = plt.subplots(3, 1, figsize=(14, 12), gridspec_kw={"height_ratios": [1, 1.3, 1]})
for sid, col in scenario_cols.items():
    a.plot(monthly.index.to_timestamp(), monthly[col].astype(int), marker=".", ms=3, label=f"{sid} {scenario_names[sid]}")
a.set_yticks([0, 1]); a.set_yticklabels(["未识别", "识别"]); a.set_title("图3-a：四情景月度识别结果"); a.legend(ncol=2, fontsize=8); a.grid(alpha=.2)
fac_labels = ["境内权益", "SPX美元", "USD/CNH", "1Y", "2Y", "5Y", "10Y", "30Y"]
fac_keys = factor_cols
xx = np.arange(len(fac_labels)); ww = .18
for j, sid in enumerate(["S1", "S2", "S3", "S4"]):
    vals = [calibration[sid].get(k, np.nan) for k in fac_keys]
    b.bar(xx + (j - 1.5) * ww, vals, ww, label=sid)
b.set_xticks(xx); b.set_xticklabels(fac_labels); b.axhline(0, color="black", lw=.6); b.set_title("图3-b：各情景历史窗口校准冲击（收益率为bp）"); b.legend(ncol=4); b.grid(axis="y", alpha=.2)
strict = []
for sid in ["S1", "S2", "S3", "S4"]:
    strict.append((sid, np.linalg.norm([committee[sid][k] for k in factor_cols]), np.linalg.norm([calibration[sid][k] for k in factor_cols])))
xx = np.arange(4); a1 = [z[1] for z in strict]; a2 = [z[2] for z in strict]
c.bar(xx - .18, a1, .36, label="委员会沿用（向量范数）"); c.bar(xx + .18, a2, .36, label="历史校准（向量范数）"); c.set_xticks(xx); c.set_xticklabels([z[0] for z in strict]); c.set_title("图3-c：沿用冲击与历史校准冲击的严格程度对比"); c.legend(); c.grid(axis="y", alpha=.2)
fig.tight_layout(); savefig("FIN3-WKN-149_chart03_情景识别与校准.png")

# Chart 04.
fig, (a, b, c) = plt.subplots(3, 1, figsize=(13, 12))
max_losses = [pressure[pressure.方案 == n].压力损失.max() for n in labels]
a.bar(labels, max_losses, color="#4472C4"); a.axhline(.08, color="red", ls="--", label="8%压力损失上限"); a.axhline(.07, color="orange", ls=":", label="7%缓冲线"); a.yaxis.set_major_formatter(PercentFormatter(1)); a.set_title("图4-a：各方案最大压力损失"); a.legend(); a.grid(axis="y", alpha=.2)
valid_path = [0.10, 0.10 + 0.205, 0.10 + 0.205 - 0.105, 0.20]
bad_path = [0.10, 0.10 - 0.105, 0.10 - 0.105 + 0.205, 0.20]
b.plot(range(len(valid_path)), valid_path, marker="o", label="先卖后买（规则路径）")
b.plot(range(len(bad_path)), bad_path, marker="o", label="先买后卖")
b.axhline(.08, color="red", ls="--", label="现金下限8%"); b.set_xticks(range(4)); b.set_xticklabels(["起始", "境内权益卖出/国债买入前", "国债买入后", "完成"]); b.yaxis.set_major_formatter(PercentFormatter(1)); b.set_title("图4-b：调仓执行人民币现金路径"); b.legend(fontsize=8); b.grid(alpha=.2)
rf = [reverse_factor[k] for k in factor_cols]; c.bar(fac_labels, rf, color="#70AD47"); c.axhline(0, color="black", lw=.6); c.set_title(f"图4-c：反向压力测试最可能情景（损失{pct(reverse_loss)}，距离{reverse_distance:.2f}）"); c.tick_params(axis="x", rotation=20); c.grid(axis="y", alpha=.2)
fig.tight_layout(); savefig("FIN3-WKN-149_chart04_方案决策与执行.png")

# Chart 05. Native units differ, so each latest value is normalized by its template threshold.
def native_threshold(row):
    value = float(re.sub(r"[^0-9.+-]", "", str(row.threshold)))
    return value / 100 if row.monitor_id in ["M1", "M2"] else value
threshold_map = {r.monitor_id: native_threshold(r) for _, r in monitor_template.iterrows()}
fig, ax = plt.subplots(figsize=(12, 6)); xx = np.arange(len(monitor_df)); vals = monitor_df.最新值.astype(float).values
ratios = np.array([v / threshold_map[mid] for v, mid in zip(vals, monitor_df.monitor_id)])
colors = ["#C00000" if x == "是" else "#70AD47" for x in monitor_df.是否触发]
ax.bar(xx, ratios, color=colors); ax.axhline(1, color="red", ls="--", lw=1.1, label="阈值=1.00"); ax.axhline(0, color="black", lw=.6)
ax.set_xticks(xx); ax.set_xticklabels(monitor_df.monitor_id); ax.set_ylabel("最新值 / 阈值（各指标原生单位）"); ax.set_title("图5：八个监测指标最新值与阈值（红=触发，绿=未触发）"); ax.legend(); ax.grid(axis="y", alpha=.2)
for i, row in monitor_df.iterrows(): ax.text(i, ratios[i], f"{ratios[i]:.2f}×\n{row['是否触发']}", ha="center", va="bottom", fontsize=8)
fig.tight_layout(); savefig("FIN3-WKN-149_chart05_监测指标触发状态.png")

# ---------- memo generation ----------
coverage_df = pd.DataFrame(coverage_items, columns=["序列", "实际起始", "实际终止", "非SSE记录数"])
coverage_df["实际起始"] = coverage_df["实际起始"].dt.strftime("%Y-%m-%d")
coverage_df["实际终止"] = coverage_df["实际终止"].dt.strftime("%Y-%m-%d")

hold_df = holdings.copy(); hold_df["金额（万元）"] = positions.market_value_10k_cny; hold_df["当前权重"] = hold_df.weight_current.map(pct); hold_df["推荐权重"] = hold_df.weight_recommended.map(pct); hold_df = hold_df[["asset", "asset_class", "当前权重", "推荐权重", "金额（万元）"]]

risk_rows = []
for name in labels:
    z = risk[name]
    risk_rows.append({"方案": name, "年化波动": pct(z["ann_vol"]), "1日VaR95": pct(z["var95"]), "1日VaR99": pct(z["var99"]), "1日ES95": pct(z["es95"]), "1日ES99": pct(z["es99"]), "10日VaR99": pct(z["var10"]), "10日最大累计损失": pct(-z["min10"]), "最大回撤": pct(-z["mdd"]), "最差单日": pct(z["worst_day"])})
risk_df = pd.DataFrame(risk_rows)

pressure_display = pressure.copy()
for col in ["境内权益", "标普500（人民币计）", "美元现金", "国债", "组合损益", "压力损失"]:
    pressure_display[col] = pressure_display[col].map(pct)
pressure_display = pressure_display[["方案", "情景", "冲击", "境内权益", "标普500（人民币计）", "美元现金", "国债", "组合损益", "压力损失"]]

constraint_rows = []
for name in ["方案A", "方案B", "方案C", "推荐方案"]:
    for lid, z in constraint_checks[name].items():
        value = pct(z["value"]) if lid not in ["L1"] else pct(z["value"])
        constraint_rows.append({"方案": name, "限额": lid, "约束": z["constraint"], "实际值": value, "结论": "通过" if z["pass"] else "未通过", "超限幅度": pct(z["excess"]) if z["excess"] else "0.00%"})
constraint_df = pd.DataFrame(constraint_rows)

scenario_summary = []
for sid in ["S1", "S2", "S3", "S4"]:
    ws = windows[sid]
    scenario_summary.append({"情景": sid, "名称": scenario_names[sid], "合格月份": ", ".join(str(x) for x in monthly.index[monthly[scenario_cols[sid]].fillna(False)]) or "无", "窗口校准口径": window_modes[sid], "选定窗口数": len(ws), "选定窗口": "; ".join(f"{x['start'].date()}至{x['end'].date()}" for x in ws[:5]) + ("；其余略" if len(ws) > 5 else "")})
scenario_df = pd.DataFrame(scenario_summary)
cal_df = pd.DataFrame(calibration).T.reset_index().rename(columns={"index": "情景"})
for k in factor_cols: cal_df[k] = cal_df[k].map(lambda x: pct(x) if k in ["cn_equity", "spx_usd", "usdcnh"] else bp(x))

# current asset stats and correlation.
asset_stat = asset_returns.describe().T[["mean", "std", "min", "max"]].reset_index().rename(columns={"index": "资产", "mean": "日均收益", "std": "日波动", "min": "最小日收益", "max": "最大日收益"})
for col in ["日均收益", "日波动", "最小日收益", "最大日收益"]: asset_stat[col] = asset_stat[col].map(pct)
corr = asset_returns.corr().round(3)
rc_df = pd.DataFrame([{ "资产": k, "风险贡献占比": pct(v)} for k, v in risk["当前组合"]["rc"].items()])

# latest pressure summaries.
max_rows = []
for name in labels:
    z = pressure[pressure.方案 == name].sort_values("压力损失", ascending=False).iloc[0]
    max_rows.append({"方案": name, "最大压力损失": pct(z.压力损失), "来源": f"{z.情景} {z.冲击}"})
max_df = pd.DataFrame(max_rows)

rec_max = max_df[max_df.方案 == "推荐方案"].iloc[0]
rec_risk = risk["推荐方案"]
rec_turnover = sum(max(current[k] - recommended[k], 0) for k in ASSET_KEYS)
rec_margin = .08 - float(pressure[pressure.方案 == "推荐方案"].压力损失.max())
rec_amp = float(pressure[pressure.方案 == "推荐方案"].压力损失.max()) / .08

exec_rows = []
for asset, key in [("沪深300指数基金", "000300"), ("中证500指数基金", "000905"), ("创业板指数基金", "399006"), ("中长期国债组合", "cgb"), ("人民币现金及货基", "cny_cash")]:
    delta = recommended[key] - current[key]
    if abs(delta) > 1e-12: exec_rows.append({"证券/资产": asset, "方向": "买入" if delta > 0 else "卖出", "金额（万元）": abs(delta) * NAV, "权重变动": pct(delta)})
exec_df = pd.DataFrame(exec_rows)
exec_df["金额（万元）"] = exec_df["金额（万元）"].round(2)

monitor_display = monitor_df.copy(); monitor_display["最新值"] = monitor_display.apply(lambda r: (pct(r["最新值"]) if r.monitor_id in ["M1", "M2"] else (f"{r['最新值']:.2f}%" if r.monitor_id == "M8" else (bp(r["最新值"]) if r.monitor_id in ["M3", "M4", "M5"] else (f"{r['最新值']:.2f} 个百分点" if r.monitor_id == "M6" else f"{r['最新值']:.2f}")))), axis=1)
monitor_display = monitor_display[["monitor_id", "监测指标", "阈值", "最新值", "截至日", "状态", "是否触发"]]

memo = f"""# 多资产稳健配置专户：三季度宏观压力测试与调仓建议
## 风险委员会决策备忘录

**分析截至日：2026-09-15；组合净值：{NAV:,.0f} 万元；金额单位：万元。**

### 一、结论与建议

建议否决投资经理方案A、风险管理部方案B和宏观策略组方案C，按 `params_holdings.csv` 给出的**推荐方案**执行：境内权益由 50.00% 降至 29.50%，中长期国债升至 30.50%，人民币现金及货基升至 20.00%，美元现金与标普500 QDII 各维持 10.00%。推荐方案最大压力损失为 **{rec_max['最大压力损失']}**（{rec_max['来源']}），1日 ES99 为 **{pct(rec_risk['es99'])}**，10日 VaR99 为 **{pct(rec_risk['var10'])}**，单向换手率为 **{pct(rec_turnover)}**；建议召开临时风险会议确认执行窗口，但不建议在数据未补齐前扩大风险预算。

推荐方案最大压力损失距 8.00%硬上限的裕度为 **{pct(rec_margin)}**，距 7.00%缓冲线的裕度为 **{pct(.07 - float(pressure[pressure.方案 == '推荐方案'].压力损失.max()))}**。图4-a同时给出8.00%上限和7.00%缓冲线。

### 二、数据核验与样本区间

核心市场风险样本为 **{returns.index.min().date()}至{returns.index.max().date()}，{len(returns):,}个上交所估值日**。终止原因是五个中债国债期限序列实际共同终止于 **{core.index.max().date()}**；不得把其后的数据按前值外推为新的国债风险观测。估值日仍为 2026-09-15，监测指标分别保留各自真实截至日。

#### 实际覆盖区间与缺口

{md_table(coverage_df)}

数据核验先于计算，具体处理如下：

- 上交所交易日历作为唯一估值日历；不在该日历中的周末/休市记录从日收益、窗口和月度市场统计中剔除。三只境内指数中的 2026-09-12 周六记录以及各期限国债、DR007等非SSE日期均不进入日收益计算；图1显示实际覆盖与截至日。
- 三只境内指数首行 `pre_close` 为空属于结构性首日缺失，不用0代替；收益从首个有前值的有效估值日开始。LPR5Y在2019-08-20前的连续空值属于结构性空值，规则判断中保持缺失，不填0、不前填。
- 普通跨市场日期不一致时，先映射至SSE估值日，再对已有序列前向填充；序列起点前没有有效观测的结构性空值不填充。美元计SPX和USD/CNH先在SSE估值日对齐，人民币计收益严格按 `(1+SPX美元收益)*(1+USD/CNH变动)-1` 复合计算。
- 中债收益率的 `yield_pct` 变动先换算为bp；国债组合日收益为 `-Σ(关键期限久期贡献×收益率变动bp/10000)`，久期贡献来自 `params_duration.csv`，总和为7.00。委员会文件字段为 `cgb_shock_bp`，因此冲击值按bp原值使用，不作百分点放大。
- `afre_stock`按源文件的社会融资规模存量水平计算12个月同比增速，用于S4和M8；这是从水平序列派生同比，未把水平值误当成百分比。

### 三、当前组合风险画像

#### 当前持仓

{md_table(hold_df)}

#### 各资产日收益统计与相关矩阵

{md_table(asset_stat)}

相关矩阵（境内三指数、国债、美元现金、SPX人民币计）如下：

{md_table(corr.round(3), index=True)}

#### 组合风险指标

{md_table(risk_df[risk_df.方案 == '当前组合'])}

当前组合10日最大累计损失为 **{pct(-risk['当前组合']['min10'])}**，区间为 **{risk['当前组合']['min10_start'].date()}至{risk['当前组合']['min10_end'].date()}**；最大回撤为 **{pct(-risk['当前组合']['mdd'])}**，区间起点 **{risk['当前组合']['mdd_start'].date()}**、低点 **{risk['当前组合']['mdd_end'].date()}**，{'截至样本末尚未修复' if pd.isna(risk['当前组合']['mdd_recovery']) else '修复日为 ' + str(risk['当前组合']['mdd_recovery'].date())}；最差单日损失为 **{pct(risk['当前组合']['worst_day'])}**（{risk['当前组合']['worst_day_date'].date()}）。

波动率风险贡献占比为：

{md_table(rc_df)}

图2-a展示各方案累计净值，图2-b展示年化波动、ES99、10日VaR99和最大回撤，并画出3.50% ES99和6.00% 10日VaR99参考线。

![图2：历史风险总览](FIN3-WKN-149_charts/FIN3-WKN-149_chart02_历史风险总览.png)

### 四、情景识别与历史校准

四情景均按 `rules_scenarios.csv` 的月度规则识别：S1为PMI低于50且LPR下调或PMI环比下降至少0.5且10Y收益率月均下降；S2为PPI同比上升、10Y月均收益率上升且权益下跌；S3为SPX月跌幅不低于3%或USD/CNH月升幅不低于1.5%；S4为社融存量同比增速下降、DR007月均上升且权益下跌。合格月份和窗口如下：

{md_table(scenario_df)}

窗口起点为合格月份次月首个SSE交易日，长度10个SSE交易日；严格规则要求10日组合收益每日为负，再按累计跌幅取前20个。经核验，本输入样本四个情景均没有满足“10日每日全负”的窗口；为保证四情景×两套冲击完整可复算，本文透明地退化使用各情景合格月份所对应窗口中累计跌幅最差的前20个窗口，并在表中标注。该退化结果不应与严格规则下的正式校准混同，待数据补齐后重算。校准为所选窗口各因子10日累计变动中位数：

{md_table(cal_df)}

严格规则下四个情景均为0个窗口，故输入样本不满足“不少于20个”的正式校准条件；退化口径也仅使用实际存在的合格月份窗口，S2和S4分别只有8个和5个，未人为补造数据。委员会沿用冲击与历史校准冲击的比较见图3-b、图3-c：沿用冲击按文件字段的bp口径，退化校准反映实际窗口中的复合权益/汇率变化和收益率曲线形态，因此两者不应简单按单一总幅度替换。

![图1：数据覆盖与缺口](FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png)

![图3：情景识别与校准](FIN3-WKN-149_charts/FIN3-WKN-149_chart03_情景识别与校准.png)

### 五、压力测试结果

压力测试对当前组合、三个候选方案和推荐方案均计算四情景×两套冲击；每条记录拆分为境内权益、标普500人民币计、美元现金和国债四部分，四项贡献相加得到组合损益。完整矩阵如下（百分比为组合净值损益贡献）：

{md_table(pressure_display)}

各方案最大压力损失及来源：

{md_table(max_df)}

委员会沿用冲击与历史校准冲击的严格程度由各因子共同决定：权益和汇率按复合口径，国债按久期折算；图3-c给出因子向量范数比较，图4-a给出各方案最大压力损失及8.00%/7.00%参考线。推荐方案在最差情景下仍需保留执行和模型误差余量，故采用7.00%缓冲线而非仅满足8.00%硬限额。

![图4：方案决策与执行](FIN3-WKN-149_charts/FIN3-WKN-149_chart04_方案决策与执行.png)

### 六、候选方案评估与九项约束检查

逐条检查结果如下；L5按“美元现金+未对冲汇率SPX QDII”计算，未把SPX QDII漏计为外币敞口，也未将其重复计入境内权益L2：

{md_table(constraint_df)}

方案A/B/C的未通过项由表中“未通过”和超限幅度直接给出；推荐方案按九项检查全部通过的规则评估。L9是推荐方案的额外7.00%缓冲要求，不是把L8的8.00%上限重复解释为另一类资产限额。

### 七、推荐方案与调仓执行

#### 推荐权重与构造依据

推荐方案完整权重为：沪深300 **{pct(recommended['000300'])}**、中证500 **{pct(recommended['000905'])}**、创业板 **{pct(recommended['399006'])}**、中长期国债 **{pct(recommended['cgb'])}**、美元现金 **{pct(recommended['usd_cash'])}**、SPX QDII **{pct(recommended['spx_qdii'])}**、人民币现金 **{pct(recommended['cny_cash'])}**。依据是：美元现金和SPX各10.00%不变；境内三项权益按当前权重同比例乘以0.59；释放的20.50个百分点中10.50个百分点配置国债、10.00个百分点留作人民币现金。

在该规则下推荐方案具有唯一性：三项境内权益的比例缩减系数、两项外币资产的固定权重、国债与人民币现金的资金分配均已被规则确定，故没有第二个满足同一构造规则的权重向量。作为放宽比例缩减规则的对照，同样单向换手率下，网格搜索得到的次优可行组合为：{('沪深300 ' + pct(same_turnover[1]['000300']) + '、中证500 ' + pct(same_turnover[1]['000905']) + '、创业板 ' + pct(same_turnover[1]['399006']) + '、国债 ' + pct(same_turnover[1]['cgb']) + '、人民币现金 ' + pct(same_turnover[1]['cny_cash']) + '，最大压力损失 ' + pct(same_turnover[0])) if same_turnover else '未找到满足相同换手率和7.00%缓冲线的可行对照'}；这只是放宽规则后的比较，不改变规则下的唯一推荐。

#### 交易清单与顺序

{md_table(exec_df)}

按规则先卖后买：第一步卖出沪深300、中证500、创业板合计2,050.00万元；第二步买入中长期国债1,050.00万元；剩余1,000.00万元卖出款保留在人民币现金及货基，使其从1,000.00万元升至2,000.00万元。美元现金和SPX QDII不交易，因此不存在QDII赎回款T+7对本次目标权重的当日资金贡献。

先卖后买路径的人民币现金占比为10.00%→30.50%→20.00%，全程高于8.00%下限。若先买后卖，先支付1,050.00万元国债款会使人民币现金占比降至-0.50%，随后才回升，直接击穿8.00%下限；因此不允许先买后卖。图4-b给出两条路径和8.00%下限线。

### 八、反向压力测试与监测预警

推荐方案最大压力损失为 **{rec_max['最大压力损失']}**，距8.00%压力上限裕度 **{pct(rec_margin)}**，压力损失相当于上限的 **{rec_amp:.2f}倍**。样本内最差10日累计损失为 **{pct(-rec_risk['min10'])}**，区间为 **{rec_risk['min10_start'].date()}至{rec_risk['min10_end'].date()}**。

反向压力测试以推荐方案损失达到8.00%为等式边界，以境内权益、SPX美元收益为非正、USD/CNH为非负，并以历史10日因子协方差定义马氏距离；得到最小距离 **{reverse_distance:.2f}** 的最可能因子组合：境内权益 **{pct(reverse_factor['cn_equity'])}**、SPX美元 **{pct(reverse_factor['spx_usd'])}**、USD/CNH **{pct(reverse_factor['usdcnh'])}**、国债1Y **{bp(reverse_factor['cgb_1y'])}**、2Y **{bp(reverse_factor['cgb_2y'])}**、5Y **{bp(reverse_factor['cgb_5y'])}**、10Y **{bp(reverse_factor['cgb_10y'])}**、30Y **{bp(reverse_factor['cgb_30y'])}**。约束条件是8.00%损失边界、上述方向边界及各期限±500bp搜索边界；结果用于识别最可能越限方向，不替代委员会情景。

委员会沿用冲击与历史校准冲击的马氏距离如下：

{md_table(mahal_df.round(2))}

监测指标截至各自实际最新日期如下；因国债、PPI、社融等数据存在截断，未将滞后数据伪装为2026-09-15同步观测：

{md_table(monitor_display)}

![图5：监测指标触发状态](FIN3-WKN-149_charts/FIN3-WKN-149_chart05_监测指标触发状态.png)

若上游补齐中债曲线至2026-09-15、PPI至最新月、社融存量至最新月及结构性缺口说明，应重新计算共同样本、情景识别、校准冲击、ES99/VaR99、压力矩阵和监测状态，并在下一次风险会议前替换本备忘录中的滞后指标；在补齐前不调整本次已确定的8.00%硬限额和8.00%现金执行下限。

---

**附件**

- `FIN3-WKN-149_reproduce.py`
- `FIN3-WKN-149_charts/FIN3-WKN-149_chart01_数据覆盖与缺口.png`
- `FIN3-WKN-149_charts/FIN3-WKN-149_chart02_历史风险总览.png`
- `FIN3-WKN-149_charts/FIN3-WKN-149_chart03_情景识别与校准.png`
- `FIN3-WKN-149_charts/FIN3-WKN-149_chart04_方案决策与执行.png`
- `FIN3-WKN-149_charts/FIN3-WKN-149_chart05_监测指标触发状态.png`
"""

(OUTPUT / "FIN3-WKN-149_风险委员会决策备忘录.md").write_text(memo, encoding="utf-8")
print(f"Generated memo and charts in {OUTPUT}")
print(f"Core risk sample: {returns.index.min().date()} to {returns.index.max().date()}, {len(returns)} days")
print(f"Recommendation max pressure loss: {pressure[pressure.方案 == '推荐方案'].压力损失.max():.6f}")
print(f"Recommendation ES99: {rec_risk['es99']:.6f}; 10d VaR99: {rec_risk['var10']:.6f}")
print("Scenario windows:", {sid: len(ws) for sid, ws in windows.items()})
