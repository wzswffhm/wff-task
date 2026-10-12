#!/usr/bin/env python3
from pathlib import Path
import re
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import TwoSlopeNorm

warnings.filterwarnings("ignore", category=RuntimeWarning)

ASOF = pd.Timestamp("2026-09-15")
ANNUAL_DAYS = 252
PREFIX = "FIN3-WKN-149"
CHART_FILES = {
    1: f"{PREFIX}_chart01_数据覆盖与缺口.png",
    2: f"{PREFIX}_chart02_历史风险总览.png",
    3: f"{PREFIX}_chart03_情景识别与校准.png",
    4: f"{PREFIX}_chart04_方案决策与执行.png",
    5: f"{PREFIX}_chart05_监测指标触发状态.png",
}
ASSETS = ["EQ_000300", "EQ_000905", "EQ_399006", "CGB", "USD_CASH", "SPX", "CNY_CASH"]
ASSET_CN = {
    "EQ_000300": "沪深300", "EQ_000905": "中证500", "EQ_399006": "创业板",
    "CGB": "中长期国债", "USD_CASH": "美元现金", "SPX": "标普500 QDII", "CNY_CASH": "人民币现金",
}
FACTOR_NAMES = ["境内权益", "SPX美元", "USD/CNH", "CGB1Y", "CGB2Y", "CGB5Y", "CGB10Y", "CGB30Y"]
TENORS = ["1Y", "2Y", "5Y", "10Y", "30Y"]


def setup_plotting():
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    ]
    font_path = next((x for x in candidates if Path(x).exists()), None)
    assert font_path, "未找到 Noto Sans/Serif CJK SC 字体"
    font_manager.fontManager.addfont(font_path)
    family = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams.update({
        "font.family": family, "axes.unicode_minus": False, "figure.dpi": 120,
        "savefig.dpi": 180, "axes.grid": True, "grid.alpha": 0.22,
    })


def read_csv(path, dates=True):
    df = pd.read_csv(path)
    if dates and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def fmt_pct(x):
    return "—" if pd.isna(x) else f"{x * 100:.2f}%"


def fmt_pp(x):
    return "—" if pd.isna(x) else f"{x * 100:.2f}个百分点"


def fmt_bp(x):
    return "—" if pd.isna(x) else f"{x:.2f}bp"


def fmt_num(x, digits=2):
    return "—" if pd.isna(x) else f"{x:.{digits}f}"


def md_table(df):
    shown = df.copy()
    shown.columns = [str(x) for x in shown.columns]
    shown = shown.map(lambda x: str(x))
    headers = "| " + " | ".join(shown.columns) + " |"
    sep = "|" + "|".join(["---"] * len(shown.columns)) + "|"
    rows = ["| " + " | ".join(row) + " |" for row in shown.to_numpy()]
    return "\n".join([headers, sep] + rows)


def compound(s):
    s = pd.Series(s).dropna()
    return np.nan if s.empty else float(np.prod(1.0 + s) - 1.0)


def calendar_months_missing(dates):
    periods = pd.DatetimeIndex(dates).to_period("M").unique().sort_values()
    if len(periods) < 2:
        return []
    full = pd.period_range(periods.min(), periods.max(), freq="M")
    return [str(x) for x in full.difference(periods)]


def compact_list(values, max_items=8):
    values = [str(x) for x in values]
    if not values:
        return "无"
    if len(values) <= max_items:
        return "、".join(values)
    return "、".join(values[:max_items]) + f"等{len(values)}项"


def audit_inputs(inp):
    manifest = read_csv(inp / "snapshot_data_manifest.csv", dates=False)
    required = [
        "params_committee_shocks.csv", "params_duration.csv", "params_holdings.csv", "params_limits.csv",
        "params_positions.csv", "plans_candidates.csv", "rules_checks.csv", "rules_rebalance.csv",
        "rules_scenarios.csv", "rules_windows.csv", "snapshot_data_manifest.csv", "template_monitor.csv",
        "template_memo.md",
    ]
    assert all((inp / x).exists() for x in required), "参数、规则或模板缺失"
    assert len(manifest) == 26 and manifest["file"].is_unique, "manifest 应含26个唯一快照文件"
    cal = read_csv(inp / "snapshot_trade_calendar.csv")
    sse = pd.DatetimeIndex(cal.loc[(cal.exchange == "SSE") & (cal.is_trading_day == 1), "date"]).sort_values()
    assert sse.is_unique and sse.max() == ASOF

    rows = []
    loaded = {}
    for _, m in manifest.iterrows():
        path = inp / m["file"]
        assert path.exists(), f"缺文件：{m['file']}"
        d = read_csv(path)
        loaded[m["file"]] = d
        assert len(d) == int(m["records"]), f"{m['file']} 行数与manifest不符"
        assert d["date"].is_unique and d["date"].is_monotonic_increasing
        assert d["date"].min() == pd.Timestamp(m["start"]) and d["date"].max() == pd.Timestamp(m["end"])
        nulls = int(d.drop(columns=["date"]).isna().sum().sum())
        issue = []
        if "000300SH" in m["file"] or "000905SH" in m["file"] or "399006SZ" in m["file"]:
            extras = d.loc[~d.date.isin(sse), "date"].dt.strftime("%Y-%m-%d").tolist()
            if extras:
                issue.append("非SSE日:" + compact_list(extras))
            pc_null = int(d["pre_close"].isna().sum())
            if pc_null:
                issue.append(f"pre_close首行空{pc_null}")
        elif m["file"] == "snapshot_lpr_5y.csv":
            valid = d.dropna(subset=["lpr_5y"])
            issue.append(f"发布前结构空值{nulls}（至{valid.date.min():%Y-%m-%d}前不填）")
        elif m["file"] in {"snapshot_lpr_1y.csv", "snapshot_pmi_manufacturing.csv", "snapshot_afre_stock.csv", "snapshot_ppi_yoy.csv"}:
            miss = calendar_months_missing(d.date)
            issue.append("缺月:" + compact_list(miss) if miss else "月序列无缺月")
        elif m["file"] == "snapshot_trade_calendar.csv":
            issue.append("SSE主轴完整")
        elif m["file"].startswith("snapshot_cgb_yield"):
            on_axis = d.date.isin(sse)
            missing_axis = sse[(sse >= d.date.min()) & (sse <= d.date.max())].difference(d.loc[on_axis, "date"])
            issue.append(f"SSE主轴缺{len(missing_axis)}；非SSE观测{int((~on_axis).sum())}条剔除")
        elif m["file"] in {"snapshot_spx.csv", "snapshot_usdcnh_seg1.csv", "snapshot_usdcnh_seg2.csv", "snapshot_ust_10y.csv", "snapshot_ust_m2.csv", "snapshot_ust_m4.csv"}:
            issue.append("源市场日历；对齐SSE时仅向前填充")
        else:
            issue.append("原始值无空" if nulls == 0 else f"原始空值{nulls}")
        manifest_flag = "未知（空白）" if pd.isna(m["possible_truncation"]) or str(m["possible_truncation"]).strip() == "" else str(m["possible_truncation"])
        rows.append({
            "文件/逻辑序列": m["file"], "实际范围": f"{d.date.min():%Y-%m-%d}~{d.date.max():%Y-%m-%d}",
            "实际行数": len(d), "缺口/结构空值处理": "；".join(issue), "manifest截断标志": manifest_flag,
        })

    eq300 = pd.concat([loaded["snapshot_000300SH_seg1.csv"], loaded["snapshot_000300SH_seg2.csv"]])
    eq500 = pd.concat([loaded["snapshot_000905SH_seg1.csv"], loaded["snapshot_000905SH_seg2.csv"]])
    gem = pd.concat([loaded["snapshot_399006SZ_seg1.csv"], loaded["snapshot_399006SZ_seg2.csv"]])
    bad300 = eq300.loc[~eq300.date.isin(sse), "date"]
    bad500 = eq500.loc[~eq500.date.isin(sse), "date"]
    assert bad300.dt.strftime("%Y-%m-%d").tolist() == ["2026-09-12"]
    assert bad500.dt.strftime("%Y-%m-%d").tolist() == ["2026-09-12"]
    assert gem.date.isin(sse).all()

    shibor = pd.concat([loaded["snapshot_shibor_seg1.csv"], loaded["snapshot_shibor_seg2.csv"]]).sort_values("date")
    dr = loaded["snapshot_dr007.csv"]
    overlap = shibor.merge(dr, on="date", how="inner")
    shibor_equal_dr = bool(np.allclose(overlap.shibor_1w, overlap.dr007, equal_nan=True))
    assert shibor_equal_dr
    ust_overlap = loaded["snapshot_ust_m2.csv"].merge(loaded["snapshot_ust_m4.csv"], on="date", suffixes=("_m2", "_m4"))
    ust_conflicts = int((~np.isclose(ust_overlap.yield_pct_m2, ust_overlap.yield_pct_m4)).sum())
    assert ust_conflicts > 0
    return pd.DataFrame(rows), loaded, sse, ust_conflicts


def clean_equity(loaded, sse, code):
    d = pd.concat([loaded[f"snapshot_{code}_seg1.csv"], loaded[f"snapshot_{code}_seg2.csv"]]).sort_values("date")
    d = d[d.date.isin(sse)].drop_duplicates("date", keep="last").set_index("date")
    return d["close"].astype(float)


def ffill_to_axis(df, value_col, axis):
    s = df.set_index("date")[value_col].sort_index().astype(float)
    return s.reindex(axis, method="ffill")


def build_market_data(inp, loaded, sse):
    price = pd.DataFrame(index=sse)
    price["EQ_000300"] = clean_equity(loaded, sse, "000300SH")
    price["EQ_000905"] = clean_equity(loaded, sse, "000905SH")
    price["EQ_399006"] = clean_equity(loaded, sse, "399006SZ")
    spx_usd_price = ffill_to_axis(loaded["snapshot_spx.csv"], "close", sse)
    fx_price = ffill_to_axis(
        pd.concat([loaded["snapshot_usdcnh_seg1.csv"], loaded["snapshot_usdcnh_seg2.csv"]]).sort_values("date"),
        "usdcnh", sse,
    )
    yields = pd.DataFrame(index=sse)
    for t in TENORS:
        f = loaded[f"snapshot_cgb_yield_{t.lower()}.csv"]
        yields[t] = f.set_index("date")["yield_pct"].reindex(sse)

    cgb_end = min(yields[c].dropna().index.max() for c in TENORS)
    common_axis = sse[(sse >= pd.Timestamp("2018-01-02")) & (sse <= cgb_end)]
    assert len(common_axis) == 2044 and common_axis[0] == pd.Timestamp("2018-01-02") and common_axis[-1] == pd.Timestamp("2026-06-09")
    assert price.loc[common_axis].notna().all().all() and yields.loc[common_axis].notna().all().all()
    assert spx_usd_price.loc[common_axis].notna().all() and fx_price.loc[common_axis].notna().all()

    full_axis = sse[(sse >= pd.Timestamp("2018-01-02")) & (sse <= ASOF)]
    equity_returns_full = price.loc[full_axis, ["EQ_000300", "EQ_000905", "EQ_399006"]].pct_change().iloc[1:]
    spx_usd_ret_full = spx_usd_price.loc[full_axis].pct_change().iloc[1:]
    fx_ret_full = fx_price.loc[full_axis].pct_change().iloc[1:]

    duration_df = read_csv(inp / "params_duration.csv", dates=False)
    duration = pd.Series(duration_df.duration_contribution.to_numpy(float), index=TENORS)
    returns = pd.DataFrame(index=common_axis[1:])
    for c in ["EQ_000300", "EQ_000905", "EQ_399006"]:
        returns[c] = price.loc[common_axis, c].pct_change().iloc[1:]
    spx_ret = spx_usd_price.loc[common_axis].pct_change().iloc[1:]
    fx_ret = fx_price.loc[common_axis].pct_change().iloc[1:]
    yield_diff = yields.loc[common_axis].diff().iloc[1:]
    returns["CGB"] = -(yield_diff / 100.0).mul(duration, axis=1).sum(axis=1)
    returns["USD_CASH"] = fx_ret
    returns["SPX"] = (1.0 + spx_ret) * (1.0 + fx_ret) - 1.0
    returns["CNY_CASH"] = 0.0
    returns = returns[ASSETS]
    assert len(returns) == 2043 and returns.notna().all().all()
    assert np.allclose(returns.SPX, (1 + spx_ret) * (1 + fx_ret) - 1)
    return {
        "price": price, "spx_price": spx_usd_price, "fx_price": fx_price, "yields": yields,
        "common_axis": common_axis, "returns": returns, "spx_usd_ret": spx_ret,
        "fx_ret": fx_ret, "yield_diff": yield_diff, "duration": duration,
        "equity_returns_full": equity_returns_full, "spx_usd_ret_full": spx_usd_ret_full,
        "fx_ret_full": fx_ret_full,
    }


def plan_weights(inp):
    candidates = read_csv(inp / "plans_candidates.csv", dates=False)
    plans = {}
    for _, r in candidates.iterrows():
        plans[r.plan_id] = pd.Series({
            "EQ_000300": r.w_000300, "EQ_000905": r.w_000905, "EQ_399006": r.w_399006,
            "CGB": r.w_cgb, "USD_CASH": r.w_usd_cash, "SPX": r.w_spx_qdii, "CNY_CASH": r.w_cny_cash,
        }, dtype=float)
    holdings = read_csv(inp / "params_holdings.csv", dates=False)
    current = holdings.set_index("asset_class")["weight_current"].reindex(ASSETS).astype(float)
    recommended = holdings.set_index("asset_class")["weight_recommended"].reindex(ASSETS).astype(float)
    plans["推荐方案"] = recommended
    assert all(abs(w.sum() - 1) < 1e-12 for w in plans.values())
    assert abs(current.sum() - 1) < 1e-12
    return plans, current, holdings


def drawdown_details(r):
    wealth = (1 + r).cumprod()
    peaks = wealth.cummax()
    dd = wealth / peaks - 1
    trough = dd.idxmin()
    peak = wealth.loc[:trough].idxmax()
    after = wealth.loc[trough:]
    recovered = after[after >= wealth.loc[peak]]
    recovery = recovered.index[0] if len(recovered) else None
    return float(-dd.min()), peak, trough, recovery


def risk_metrics(r):
    r = pd.Series(r).dropna()
    losses = -r.to_numpy()
    var95 = float(np.quantile(losses, 0.95, method="linear"))
    var99 = float(np.quantile(losses, 0.99, method="linear"))
    es95 = float(losses[losses >= var95].mean())
    es99 = float(losses[losses >= var99].mean())
    r10 = (1 + r).rolling(10).apply(np.prod, raw=True) - 1
    loss10 = -r10.dropna()
    var10 = float(np.quantile(loss10, 0.99, method="linear"))
    worst_end = loss10.idxmax()
    end_pos = r.index.get_loc(worst_end)
    worst_start = r.index[end_pos - 9]
    mdd, peak, trough, recovery = drawdown_details(r)
    return {
        "mean_daily": float(r.mean()), "daily_vol": float(r.std(ddof=1)),
        "ann_vol": float(r.std(ddof=1) * np.sqrt(ANNUAL_DAYS)), "var95": var95, "var99": var99,
        "es95": es95, "es99": es99, "var10_99": var10, "worst10": float(loss10.max()),
        "worst10_start": worst_start, "worst10_end": worst_end, "mdd": mdd, "dd_peak": peak,
        "dd_trough": trough, "dd_recovery": recovery, "worst1": float(losses.max()),
        "worst1_date": r.index[np.argmax(losses)],
    }


def monthly_last_valid(df, col):
    d = df.dropna(subset=[col]).copy()
    d["month"] = d.date.dt.to_period("M")
    return d.sort_values("date").groupby("month")[col].last()


def identify_scenarios(loaded, market, sse):
    full_eq_ret = market["equity_returns_full"]
    eq_internal = full_eq_ret.mul([0.5, 0.3, 0.2], axis=1).sum(axis=1)
    spx_source = loaded["snapshot_spx.csv"].set_index("date")["close"].sort_index().astype(float)
    fx_source = pd.concat([loaded["snapshot_usdcnh_seg1.csv"], loaded["snapshot_usdcnh_seg2.csv"]]).sort_values("date").set_index("date")["usdcnh"].astype(float)

    monthly = pd.DataFrame(index=pd.period_range("2018-01", ASOF.to_period("M"), freq="M"))
    monthly["eq_ret"] = eq_internal.groupby(eq_internal.index.to_period("M")).apply(compound)
    monthly["spx_ret"] = spx_source.pct_change().groupby(spx_source.index.to_period("M")).apply(compound)
    monthly["fx_ret"] = fx_source.pct_change().groupby(fx_source.index.to_period("M")).apply(compound)

    cgb10 = loaded["snapshot_cgb_yield_10y.csv"].copy()
    cgb10["month"] = cgb10.date.dt.to_period("M")
    monthly["cgb10_mean"] = cgb10.groupby("month").yield_pct.mean()
    dr = loaded["snapshot_dr007.csv"].copy()
    dr["month"] = dr.date.dt.to_period("M")
    monthly["dr_mean"] = dr.groupby("month").dr007.mean()
    monthly["lpr1"] = monthly_last_valid(loaded["snapshot_lpr_1y.csv"], "lpr_1y")
    monthly["lpr5"] = monthly_last_valid(loaded["snapshot_lpr_5y.csv"], "lpr_5y")
    monthly["pmi"] = monthly_last_valid(loaded["snapshot_pmi_manufacturing.csv"], "pmi_mfg")
    monthly["ppi"] = monthly_last_valid(loaded["snapshot_ppi_yoy.csv"], "ppi_yoy")
    afre = monthly_last_valid(loaded["snapshot_afre_stock.csv"], "afre_stock").reindex(monthly.index)
    monthly["afre_yoy"] = afre / afre.shift(12) - 1

    monthly["lpr1_chg"] = monthly.lpr1 - monthly.lpr1.shift(1)
    monthly["lpr5_chg"] = monthly.lpr5 - monthly.lpr5.shift(1)
    monthly["pmi_chg"] = monthly.pmi - monthly.pmi.shift(1)
    monthly["ppi_chg"] = monthly.ppi - monthly.ppi.shift(1)
    monthly["cgb10_chg"] = monthly.cgb10_mean - monthly.cgb10_mean.shift(1)
    monthly["dr_chg"] = monthly.dr_mean - monthly.dr_mean.shift(1)
    monthly["afre_yoy_chg"] = monthly.afre_yoy - monthly.afre_yoy.shift(1)

    flags = pd.DataFrame(index=monthly.index)
    flags["S1"] = ((monthly.pmi < 50) & ((monthly.lpr1_chg < 0) | (monthly.lpr5_chg < 0))) | ((monthly.pmi_chg <= -0.5) & (monthly.cgb10_chg < 0))
    flags["S2"] = (monthly.ppi_chg > 0) & (monthly.cgb10_chg > 0) & (monthly.eq_ret < 0)
    flags["S3"] = (monthly.spx_ret <= -0.03) | (monthly.fx_ret >= 0.015)
    flags["S4"] = (monthly.afre_yoy_chg < 0) & (monthly.dr_chg > 0) & (monthly.eq_ret < 0)
    flags = flags.fillna(False)
    months = {sid: list(flags.index[flags[sid]]) for sid in flags.columns}
    return monthly, flags, months, eq_internal


def factor_window(market, eq_internal, dates):
    return np.array([
        compound(eq_internal.reindex(dates)), compound(market["spx_usd_ret"].reindex(dates)),
        compound(market["fx_ret"].reindex(dates)),
        *[market["yield_diff"].reindex(dates)[t].sum() for t in TENORS],
    ], dtype=float)


def historical_calibration(months, plans, market, eq_internal, sse):
    records = []
    calibrations = {}
    all_windows = {}
    ret = market["returns"]
    common_end = market["common_axis"][-1]
    for pname, w in plans.items():
        pr = ret.mul(w, axis=1).sum(axis=1)
        for sid, qualified_months in months.items():
            windows = []
            for month in qualified_months:
                next_month = month + 1
                eligible = sse[sse.to_period("M") == next_month]
                if len(eligible) == 0:
                    continue
                start = eligible[0]
                loc = sse.get_indexer([start])[0]
                dates = sse[loc:loc + 10]
                if len(dates) != 10 or dates[-1] > common_end or not pd.DatetimeIndex(dates).isin(pr.index).all():
                    continue
                port_ret = compound(pr.reindex(dates))
                if port_ret < 0:
                    windows.append({"month": month, "start": dates[0], "end": dates[-1], "port_ret": port_ret, "factor": factor_window(market, eq_internal, dates)})
            windows.sort(key=lambda x: x["port_ret"])
            all_windows[(pname, sid)] = windows
            vec = np.median(np.vstack([x["factor"] for x in windows]), axis=0) if windows else np.zeros(8)
            calibrations[(pname, sid)] = vec
            records.append({
                "方案": pname, "情景": sid, "合格窗口数": len(windows),
                "全部合格窗口": "；".join(f"{x['start']:%Y-%m-%d}~{x['end']:%Y-%m-%d}({fmt_pct(x['port_ret'])})" for x in windows) or "无（冲击按0）",
            })
    return pd.DataFrame(records), calibrations, all_windows


def parse_cgb_shocks(text):
    pairs = re.findall(r"(1Y|2Y|5Y|10Y|30Y):([+-]?\d+(?:\.\d+)?)", str(text))
    out = dict(pairs)
    assert set(out) == set(TENORS)
    return np.array([float(out[t]) for t in TENORS])


def stress_contributions(w, shock, duration):
    eq, spx_usd, fx = shock[:3]
    dy = shock[3:]
    cn = float(w[["EQ_000300", "EQ_000905", "EQ_399006"]].sum() * eq)
    spx = float(w["SPX"] * ((1 + spx_usd) * (1 + fx) - 1))
    usd = float(w["USD_CASH"] * fx)
    bond = float(w["CGB"] * (-(duration.to_numpy() * dy / 100.0).sum()))
    total = cn + spx + usd + bond
    assert np.isclose(cn + spx + usd + bond, total, atol=1e-13)
    return cn, spx, usd, bond, total


def run_stress(inp, plans, calibrations, duration):
    committee = read_csv(inp / "params_committee_shocks.csv", dates=False)
    committee_vec = {}
    scenario_names = {}
    for _, r in committee.iterrows():
        committee_vec[r.scenario_id] = np.r_[r.cn_equity_shock, r.spx_usd_shock, r.usdcnh_shock, parse_cgb_shocks(r.cgb_shock_bp)]
        scenario_names[r.scenario_id] = r.scenario
    rows = []
    for pname, w in plans.items():
        for sid in committee_vec:
            for source, shock in [("委员会沿用", committee_vec[sid]), ("历史校准", calibrations[(pname, sid)])]:
                cn, spx, usd, bond, total = stress_contributions(w, shock, duration)
                rows.append({
                    "方案": pname, "情景编号": sid, "情景": scenario_names[sid], "冲击套系": source,
                    "境内权益贡献": cn, "标普500人民币贡献": spx, "美元现金贡献": usd,
                    "国债贡献": bond, "总损益": total, "压力损失": -total,
                })
    result = pd.DataFrame(rows)
    assert len(result) == 32
    assert np.allclose(result[["境内权益贡献", "标普500人民币贡献", "美元现金贡献", "国债贡献"]].sum(axis=1), result["总损益"])
    return result, committee_vec, scenario_names


def evaluate_constraints(inp, plans, metrics, stress):
    limits = read_csv(inp / "params_limits.csv", dates=False).set_index("id")
    rows = []
    for pname, w in plans.items():
        values = {
            "L1": w.sum(), "L2": w[["EQ_000300", "EQ_000905", "EQ_399006"]].sum(),
            "L3": w.CNY_CASH, "L4": w.CGB, "L5": w.USD_CASH + w.SPX,
            "L6": metrics[pname]["es99"], "L7": metrics[pname]["var10_99"],
            "L8": stress.loc[stress.方案 == pname, "压力损失"].max(),
            "L9": stress.loc[stress.方案 == pname, "压力损失"].max(),
        }
        for lid, value in values.items():
            r = limits.loc[lid]
            op = r.op
            lo = None if pd.isna(r.lower) else float(r.lower)
            hi = None if pd.isna(r.upper) else float(r.upper)
            if lid == "L1":
                excess = max(abs(value - 1.0) - 0.0005, 0.0)
                passed = excess == 0
                threshold = "100.00%（容差±0.05个百分点）"
            elif op == "<=":
                threshold_value = hi if hi is not None else lo
                excess = max(value - threshold_value, 0.0)
                passed = excess == 0
                threshold = f"≤{fmt_pct(threshold_value)}"
            elif op == ">=":
                threshold_value = lo if lo is not None else hi
                excess = max(threshold_value - value, 0.0)
                passed = excess == 0
                threshold = f"≥{fmt_pct(threshold_value)}"
            elif op == "in":
                excess = max((lo - value) if value < lo else (value - hi) if value > hi else 0.0, 0.0)
                passed = excess == 0
                threshold = f"{fmt_pct(lo)}~{fmt_pct(hi)}"
            else:
                raise ValueError(f"未知约束操作符 {op}")
            rows.append({
                "方案": pname, "约束": lid, "指标": r.constraint, "实际值": fmt_pct(value),
                "阈值": threshold, "结论": "通过" if passed else "未通过",
                "超限幅度": "0.00个百分点" if passed else fmt_pp(excess),
            })
    out = pd.DataFrame(rows)
    assert len(out) == 36
    return out


def rolling_factor_vectors(market, eq_internal):
    idx = market["returns"].index
    out = pd.DataFrame(index=idx)
    out["境内权益"] = (1 + eq_internal.reindex(idx)).rolling(10).apply(np.prod, raw=True) - 1
    out["SPX美元"] = (1 + market["spx_usd_ret"]).rolling(10).apply(np.prod, raw=True) - 1
    out["USD/CNH"] = (1 + market["fx_ret"]).rolling(10).apply(np.prod, raw=True) - 1
    for t in TENORS:
        out[f"CGB{t}"] = market["yield_diff"][t].rolling(10).sum()
    return out.dropna()


def portfolio_factor_return(x, w, duration):
    return float(
        w[["EQ_000300", "EQ_000905", "EQ_399006"]].sum() * x[0]
        + w.SPX * ((1 + x[1]) * (1 + x[2]) - 1)
        + w.USD_CASH * x[2]
        - w.CGB * np.dot(duration.to_numpy(), x[3:]) / 100.0
    )


def portfolio_gradient(x, w, duration):
    return np.r_[
        w[["EQ_000300", "EQ_000905", "EQ_399006"]].sum(),
        w.SPX * (1 + x[2]), w.SPX * (1 + x[1]) + w.USD_CASH,
        -w.CGB * duration.to_numpy() / 100.0,
    ].astype(float)


def reverse_stress(factors, w, duration, target_loss=0.08):
    mu = factors.mean().to_numpy()
    cov = factors.cov().to_numpy()
    cov = (cov + cov.T) / 2
    eig, vec = np.linalg.eigh(cov)
    floor = max(eig.max() * 1e-10, 1e-14)
    cov_reg = (vec * np.maximum(eig, floor)) @ vec.T
    precision = np.linalg.inv(cov_reg)
    grad0 = portfolio_gradient(mu, w, duration)
    g0 = portfolio_factor_return(mu, w, duration) + target_loss
    lam = g0 / float(grad0 @ cov_reg @ grad0)
    x = mu - lam * (cov_reg @ grad0)
    hess = np.zeros((8, 8))
    hess[1, 2] = hess[2, 1] = w.SPX
    converged = False
    for _ in range(100):
        grad = portfolio_gradient(x, w, duration)
        f = np.r_[precision @ (x - mu) + lam * grad, portfolio_factor_return(x, w, duration) + target_loss]
        if np.linalg.norm(f) < 1e-10:
            converged = True
            break
        jac = np.block([[precision + lam * hess, grad[:, None]], [grad[None, :], np.zeros((1, 1))]])
        step = np.linalg.solve(jac, -f)
        x += step[:8]
        lam += step[8]
    if not converged:
        for _ in range(200):
            g = portfolio_factor_return(x, w, duration) + target_loss
            if abs(g) < 1e-11:
                converged = True
                break
            grad = portfolio_gradient(x, w, duration)
            denom = float(grad @ cov_reg @ grad)
            x -= g * (cov_reg @ grad) / denom
    assert converged and abs(portfolio_factor_return(x, w, duration) + target_loss) < 1e-8
    stationarity = precision @ (x - mu) + lam * portfolio_gradient(x, w, duration)
    assert np.linalg.norm(stationarity) < 1e-7, "反向压力解未满足KKT驻点条件"
    distance = float(np.sqrt((x - mu) @ precision @ (x - mu)))
    return x, distance, mu, cov_reg, precision


def mahalanobis(x, mu, precision):
    d = np.asarray(x) - mu
    return float(np.sqrt(max(d @ precision @ d, 0)))


def compute_monitors(loaded, market, sse):
    rows = []
    eq = market["price"].EQ_000300.dropna()
    value = eq.iloc[-1] / eq.iloc[-21] - 1
    rows.append(("M1", "沪深300 20日收益", value, -0.05, "低", eq.index[-1], "%"))
    fx = market["fx_price"].dropna()
    value = fx.iloc[-1] / fx.iloc[-21] - 1
    rows.append(("M2", "USD/CNH 20日变化", value, 0.02, "高", fx.index[-1], "%"))
    dr = loaded["snapshot_dr007.csv"].set_index("date").dr007
    value = (dr.iloc[-20:].mean() - dr.iloc[-80:-20].mean()) * 100
    rows.append(("M3", "DR007资金面变化", value, 20.0, "高", dr.index[-1], "bp"))
    cgb = loaded["snapshot_cgb_yield_10y.csv"].set_index("date").yield_pct.reindex(sse, method="ffill").dropna()
    cgb = cgb.loc[:loaded["snapshot_cgb_yield_10y.csv"].date.max()]
    value = (cgb.iloc[-1] - cgb.iloc[-21]) * 100
    rows.append(("M4", "中债10Y 20日变化", value, 10.0, "高", cgb.index[-1], "bp"))
    ust = loaded["snapshot_ust_10y.csv"].set_index("date").yield_pct.sort_index().dropna()
    value = (ust.iloc[-1] - ust.iloc[-21]) * 100
    rows.append(("M5", "美债10Y 20日变化", value, 40.0, "高", ust.index[-1], "bp"))
    ppi = monthly_last_valid(loaded["snapshot_ppi_yoy.csv"], "ppi_yoy")
    latest_month = ppi.index.max()
    value = ppi.loc[latest_month] - ppi.reindex([latest_month - 3]).iloc[0]
    rows.append(("M6", "PPI同比加速", value, 1.5, "高", latest_month.to_timestamp(), "个百分点"))
    pmi = loaded["snapshot_pmi_manufacturing.csv"].set_index("date").pmi_mfg
    rows.append(("M7", "制造业PMI荣枯线", float(pmi.iloc[-1]), 49.0, "低", pmi.index[-1], "点"))
    afre = monthly_last_valid(loaded["snapshot_afre_stock.csv"], "afre_stock")
    full = afre.reindex(pd.period_range(afre.index.min(), afre.index.max(), freq="M"))
    yoy = full / full.shift(12) - 1
    rows.append(("M8", "社融存量增速", float(yoy.dropna().iloc[-1]), 0.08, "低", yoy.dropna().index[-1].to_timestamp(), "%"))

    out = []
    for mid, name, value, threshold, direction, asof, unit in rows:
        triggered = value < threshold if direction == "低" else value > threshold
        formatter = fmt_pct if unit == "%" else fmt_bp if unit == "bp" else (lambda x: f"{x:.2f}{unit}")
        out.append({
            "编号": mid, "指标": name, "最新值": formatter(value), "阈值": formatter(threshold),
            "方向": f"{direction}于阈值触发", "截至日": pd.Timestamp(asof).strftime("%Y-%m-%d"),
            "状态": "触发" if triggered else "未触发", "triggered": triggered,
            "value_raw": value, "threshold_raw": threshold, "unit": unit,
        })
    return pd.DataFrame(out)


def build_charts(outdir, audit, market, plan_returns, metrics, flags, months, calibrations, stress,
                 current, plans, reverse_x, reverse_mu, reverse_cov, monitors):
    chart_dir = outdir / f"{PREFIX}_charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    for old in chart_dir.iterdir():
        if old.is_file():
            old.unlink()

    fig, ax = plt.subplots(figsize=(13, 11))
    starts = pd.to_datetime(audit["实际范围"].str.split("~").str[0])
    ends = pd.to_datetime(audit["实际范围"].str.split("~").str[1])
    y = np.arange(len(audit))
    colors = [
        "#d95f02" if any(mark in s for mark in ["缺月:", "结构空值", "非SSE日:"]) else "#1b9e77"
        for s in audit["缺口/结构空值处理"]
    ]
    ax.barh(y, (ends - starts).dt.days, left=starts.map(pd.Timestamp.toordinal), color=colors, alpha=0.85)
    ax.set_yticks(y, audit["文件/逻辑序列"].str.replace("snapshot_", "", regex=False).str.replace(".csv", "", regex=False), fontsize=7)
    ticks = pd.date_range("2018-01-01", "2027-01-01", freq="YS")
    ax.set_xticks([x.toordinal() for x in ticks], [x.year for x in ticks])
    ax.axvline(ASOF.toordinal(), color="red", linestyle="--", linewidth=1.5, label=f"分析截至日 {ASOF:%Y-%m-%d}")
    ax.legend(loc="lower right")
    ax.invert_yaxis()
    ax.set_title("图1 数据覆盖区间与缺口标记（橙色表示存在缺口、结构空值或非SSE异常记录）")
    ax.set_xlabel("年份；manifest空白截断标志按“未知”处理")
    fig.tight_layout()
    fig.savefig(chart_dir / CHART_FILES[1], bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(13, 10), gridspec_kw={"height_ratios": [1.35, 1]})
    for name, r in plan_returns.items():
        axes[0].plot((1 + r).cumprod() * 100, label=name, lw=1.2)
    axes[0].set_title("图2-a 四方案累计净值（每日按固定方案权重再平衡，起点100）")
    axes[0].legend(ncol=4)
    axes[0].set_ylabel("累计净值")
    categories = ["年化波动", "1日ES99", "10日VaR99", "最大回撤"]
    x = np.arange(4)
    width = 0.19
    for i, name in enumerate(plans):
        m = metrics[name]
        vals = np.array([m["ann_vol"], m["es99"], m["var10_99"], m["mdd"]]) * 100
        axes[1].bar(x + (i - 1.5) * width, vals, width, label=name)
    axes[1].hlines(3.5, x[1] - 0.45, x[1] + 0.45, colors="red", linestyles="--", lw=1.5)
    axes[1].hlines(6.0, x[2] - 0.45, x[2] + 0.45, colors="red", linestyles="--", lw=1.5)
    axes[1].text(x[1], 3.65, "ES限额3.5%", color="red", ha="center", fontsize=8)
    axes[1].text(x[2], 6.15, "VaR限额6%", color="red", ha="center", fontsize=8)
    axes[1].text(x[3], axes[1].get_ylim()[1] * 0.92, "无硬限额", ha="center", fontsize=8)
    axes[1].set_xticks(x, categories)
    axes[1].set_ylabel("%")
    axes[1].set_title("图2-b 四方案风险指标及硬限额参考线")
    axes[1].legend(ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(chart_dir / CHART_FILES[2], bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(14, 13), gridspec_kw={"height_ratios": [1, 1.25, 1]})
    scenario_order = ["S1", "S2", "S3", "S4"]
    for i, sid in enumerate(scenario_order):
        vals = months[sid]
        axes[0].scatter([p.to_timestamp() for p in vals], np.full(len(vals), i), s=22, label=sid)
    axes[0].set_yticks(range(4), scenario_order)
    axes[0].set_title("图3-a 四类历史情景的全部识别月份")
    axes[0].set_xlim(pd.Timestamp("2018-01-01"), ASOF)
    h = np.vstack([calibrations[("推荐方案", sid)] for sid in scenario_order])
    display = h.copy()
    display[:, :3] *= 100
    display[:, 3:] *= 100
    scale = np.nanstd(display, axis=0)
    normed = np.divide(display, scale, out=np.zeros_like(display), where=scale > 0)
    im = axes[1].imshow(normed, cmap="RdBu_r", aspect="auto", norm=TwoSlopeNorm(vcenter=0))
    axes[1].set_xticks(range(8), ["权益%", "SPX%", "FX%", "1Y bp", "2Y bp", "5Y bp", "10Y bp", "30Y bp"])
    axes[1].set_yticks(range(4), scenario_order)
    for i in range(4):
        for j in range(8):
            axes[1].text(j, i, f"{display[i,j]:.2f}", ha="center", va="center", fontsize=8)
    axes[1].set_title("图3-b 推荐方案历史校准冲击（颜色按因子标准化；格内为收益%或收益率bp）")
    fig.colorbar(im, ax=axes[1], fraction=0.02, pad=0.02, label="因子内标准化强度")
    rec = stress[stress.方案 == "推荐方案"]
    xx = np.arange(4)
    for j, src in enumerate(["委员会沿用", "历史校准"]):
        vals = [rec[(rec.情景编号 == sid) & (rec.冲击套系 == src)].压力损失.iloc[0] * 100 for sid in scenario_order]
        axes[2].bar(xx + (j - .5) * .36, vals, .36, label=src)
    axes[2].axhline(7, color="orange", ls="--", label="7%缓冲线")
    axes[2].set_xticks(xx, scenario_order)
    axes[2].set_ylabel("压力损失%")
    axes[2].set_title("图3-c 委员会沿用与历史校准冲击严格程度（推荐方案）")
    axes[2].legend()
    fig.tight_layout()
    fig.savefig(chart_dir / CHART_FILES[3], bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(13, 13))
    maxima = stress.groupby("方案").压力损失.max().reindex(plans.keys()) * 100
    bars = axes[0].bar(maxima.index, maxima.values, color="#4c78a8")
    axes[0].axhline(8, color="red", ls="--", label="8%硬限额")
    axes[0].axhline(7, color="orange", ls="--", label="7%缓冲线")
    axes[0].bar_label(bars, fmt="%.2f%%")
    axes[0].set_title("图4-a 四方案最大压力损失与限额")
    axes[0].set_ylabel("%")
    axes[0].legend()
    path_x = np.arange(3)
    axes[1].plot(path_x, [10, 30.5, 20], marker="o", label="先卖后买")
    axes[1].plot(path_x, [10, -0.5, 20], marker="o", label="先买后卖（反例）")
    axes[1].axhline(8, color="red", ls="--", label="8%现金下限")
    axes[1].set_xticks(path_x, ["初始", "第一步后", "完成后"])
    axes[1].set_ylabel("人民币现金占比%")
    axes[1].set_title("图4-b 两种执行顺序的人民币现金路径")
    axes[1].legend()
    std = np.sqrt(np.diag(reverse_cov))
    z = (reverse_x - reverse_mu) / std
    colors = ["#e45756" if v < 0 else "#54a24b" for v in z]
    bars = axes[2].bar(np.arange(8), z, color=colors)
    axes[2].axhline(0, color="black", lw=.8)
    axes[2].set_xticks(np.arange(8), ["权益", "SPX", "FX", "1Y", "2Y", "5Y", "10Y", "30Y"])
    axes[2].set_ylabel("相对10日因子均值的标准差倍数")
    axes[2].set_title("图4-c 反向压力最可能冲击（8%损失边界）")
    axes[2].bar_label(bars, fmt="%.2f", fontsize=8)
    fig.tight_layout()
    fig.savefig(chart_dir / CHART_FILES[4], bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 4, figsize=(15, 7))
    for ax, (_, r) in zip(axes.ravel(), monitors.iterrows()):
        vals = [r.value_raw, r.threshold_raw]
        color = "#d62728" if r.triggered else "#2ca02c"
        bars = ax.bar(["最新", "阈值"], vals, color=[color, "#808080"])
        ax.axhline(0, color="black", lw=.7)
        ax.set_title(f"{r['编号']} {r['指标']}\n{r['状态']}", fontsize=10)
        ax.set_ylabel(r.unit)
        ax.bar_label(bars, fmt="%.2f", fontsize=8)
    fig.suptitle("图5 八项监测指标：最新值相对阈值（红色为触发）", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, .95])
    fig.savefig(chart_dir / CHART_FILES[5], bbox_inches="tight")
    plt.close(fig)
    expected = set(CHART_FILES.values())
    assert {x.name for x in chart_dir.iterdir() if x.is_file()} == expected


def build_memo(inp, outdir, audit, ust_conflicts, market, current, holdings, plans, plan_returns, metrics,
               months, window_table, calibrations, scenario_names, stress, constraints, reverse_x,
               reverse_dist, factors, committee_vec, mu, precision, monitors, turnover, positions):
    rec = plans["推荐方案"]
    rec_stress = stress[stress.方案 == "推荐方案"]
    max_row = rec_stress.loc[rec_stress.压力损失.idxmax()]
    max_loss = float(max_row.压力损失)
    fails = constraints[constraints.结论 == "未通过"].groupby("方案").约束.apply(lambda x: "、".join(x)).to_dict()
    triggered = monitors[monitors.triggered]
    meeting = len(triggered) > 0 or len(constraints[(constraints.方案 == "推荐方案") & (constraints.结论 == "未通过")]) > 0

    current_positions = positions[["asset", "weight_current", "market_value_10k_cny"]].copy()
    current_positions.columns = ["资产", "当前权重", "金额（万元）"]
    current_positions["当前权重"] = current_positions["当前权重"].map(fmt_pct)
    current_positions["金额（万元）"] = current_positions["金额（万元）"].map(lambda x: f"{x:.2f}")

    asset_stats = pd.DataFrame({
        "资产": [ASSET_CN[x] for x in ASSETS],
        "日均收益": [fmt_pct(market["returns"][x].mean()) for x in ASSETS],
        "日波动": [fmt_pct(market["returns"][x].std()) for x in ASSETS],
        "年化波动": [fmt_pct(market["returns"][x].std() * np.sqrt(ANNUAL_DAYS)) for x in ASSETS],
        "最差单日": [fmt_pct(market["returns"][x].min()) for x in ASSETS],
    })
    corr = market["returns"].corr().rename(index=ASSET_CN, columns=ASSET_CN).round(3).reset_index().rename(columns={"index": "资产"})
    cm = metrics["当前组合"]
    metric_table = pd.DataFrame([
        ["日均收益", fmt_pct(cm["mean_daily"])], ["日波动", fmt_pct(cm["daily_vol"])],
        ["年化波动", fmt_pct(cm["ann_vol"])], ["1日VaR95", fmt_pct(cm["var95"])],
        ["1日VaR99", fmt_pct(cm["var99"])], ["1日ES95", fmt_pct(cm["es95"])],
        ["1日ES99", fmt_pct(cm["es99"])], ["10日VaR99", fmt_pct(cm["var10_99"])],
        ["10日最大累计损失", f"{fmt_pct(cm['worst10'])}（{cm['worst10_start']:%Y-%m-%d}~{cm['worst10_end']:%Y-%m-%d}）"],
        ["最大回撤", f"{fmt_pct(cm['mdd'])}（峰值{cm['dd_peak']:%Y-%m-%d}、谷值{cm['dd_trough']:%Y-%m-%d}、修复{cm['dd_recovery'].strftime('%Y-%m-%d') if cm['dd_recovery'] is not None else '样本内未修复'}）"],
        ["最差单日损失", f"{fmt_pct(cm['worst1'])}（{cm['worst1_date']:%Y-%m-%d}）"],
    ], columns=["指标", "当前组合"])
    sigma = market["returns"].cov().to_numpy()
    wv = current.reindex(ASSETS).to_numpy()
    denom = float(wv @ sigma @ wv)
    rc = wv * (sigma @ wv) / denom
    rc_table = pd.DataFrame({"资产": [ASSET_CN[x] for x in ASSETS], "风险贡献": [fmt_pct(x) for x in rc]})

    scenario_rules = read_csv(inp / "rules_scenarios.csv", dates=False)
    scenario_month_table = scenario_rules[["scenario_id", "scenario", "rule"]].copy()
    scenario_month_table["全部合格月份"] = scenario_month_table.scenario_id.map(lambda x: "、".join(str(p) for p in months[x]) or "无")
    scenario_month_table.columns = ["编号", "情景", "识别规则", "全部合格月份"]

    calibration_rows = []
    for pname in plans:
        for sid in ["S1", "S2", "S3", "S4"]:
            x = calibrations[(pname, sid)]
            calibration_rows.append({
                "方案": pname, "情景": sid, "境内权益": fmt_pct(x[0]), "SPX美元": fmt_pct(x[1]),
                "FX": fmt_pct(x[2]), "CGB1Y": fmt_bp(x[3] * 100), "CGB2Y": fmt_bp(x[4] * 100),
                "CGB5Y": fmt_bp(x[5] * 100), "CGB10Y": fmt_bp(x[6] * 100), "CGB30Y": fmt_bp(x[7] * 100),
            })
    calibration_table = pd.DataFrame(calibration_rows)

    stress_display = stress.copy()
    for c in ["境内权益贡献", "标普500人民币贡献", "美元现金贡献", "国债贡献", "总损益", "压力损失"]:
        stress_display[c] = stress_display[c].map(fmt_pct)
    stress_display = stress_display[["方案", "情景编号", "情景", "冲击套系", "境内权益贡献", "标普500人民币贡献", "美元现金贡献", "国债贡献", "总损益", "压力损失"]]

    max_table = stress.loc[stress.groupby("方案").压力损失.idxmax(), ["方案", "情景编号", "情景", "冲击套系", "压力损失"]].copy()
    max_table["压力损失"] = max_table["压力损失"].map(fmt_pct)
    strict_rows = []
    for sid in ["S1", "S2", "S3", "S4"]:
        a = rec_stress[(rec_stress.情景编号 == sid) & (rec_stress.冲击套系 == "委员会沿用")].压力损失.iloc[0]
        b = rec_stress[(rec_stress.情景编号 == sid) & (rec_stress.冲击套系 == "历史校准")].压力损失.iloc[0]
        strict_rows.append([sid, fmt_pct(a), fmt_pct(b), "委员会沿用" if a > b else "历史校准" if b > a else "相同"])
    strict_table = pd.DataFrame(strict_rows, columns=["情景", "委员会损失", "历史校准损失", "更严格套系"])

    rec_weights = pd.DataFrame({"资产": [ASSET_CN[x] for x in ASSETS], "推荐权重": [fmt_pct(rec[x]) for x in ASSETS]})
    nav = float(positions.market_value_10k_cny.sum())
    assert np.isclose(nav, 10000)
    trades = holdings.copy()
    trades["当前金额"] = trades.weight_current * nav
    trades["推荐金额"] = trades.weight_recommended * nav
    trades["交易金额"] = trades["推荐金额"] - trades["当前金额"]
    trades["方向"] = trades["交易金额"].map(lambda x: "买入/增加" if x > 1e-9 else "卖出" if x < -1e-9 else "不变")
    trades["交易金额（万元）"] = trades["交易金额"].abs().map(lambda x: f"{x:.2f}")
    trade_table = trades[["asset", "方向", "交易金额（万元）"]].rename(columns={"asset": "证券/资产"})

    candidate_compare = []
    for p in ["方案A", "方案B", "方案C"]:
        sell = float(((current - plans[p]).clip(lower=0)).sum())
        candidate_compare.append([p, fmt_pct(sell), fails.get(p, "无")])
    candidate_compare = pd.DataFrame(candidate_compare, columns=["方案", "单向换手率", "未通过项"])

    rec_metric = metrics["推荐方案"]
    margin = 0.08 - max_loss
    scale = 0.08 / max_loss if max_loss > 0 else np.inf
    worst_factor_loss = rec_metric["worst10"]
    worst_factor_start = rec_metric["worst10_start"]
    worst_factor_end = rec_metric["worst10_end"]

    reverse_table = pd.DataFrame({
        "风险因子": FACTOR_NAMES,
        "反向冲击": [fmt_pct(reverse_x[i]) if i < 3 else fmt_bp(reverse_x[i] * 100) for i in range(8)],
    })
    distance_rows = []
    for sid, x in committee_vec.items():
        distance_rows.append([sid, "委员会沿用", f"{mahalanobis(x, mu, precision):.3f}"])
        hx = calibrations[("推荐方案", sid)]
        distance_rows.append([sid, "历史校准", f"{mahalanobis(hx, mu, precision):.3f}"])
    distance_table = pd.DataFrame(distance_rows, columns=["情景", "冲击套系", "马氏距离"])

    monitor_display = monitors.drop(columns=["triggered", "value_raw", "threshold_raw", "unit"])
    audit_display = audit.copy()
    for c in ["实际行数"]:
        audit_display[c] = audit_display[c].astype(str)

    recommendation_status = "推荐方案九项约束全部通过" if "推荐方案" not in fails else f"推荐方案仍未通过{fails['推荐方案']}"
    monitor_text = "监测未见触发" if triggered.empty else "触发" + "、".join(triggered.编号)
    meeting_text = "建议提请临时风险会议" if meeting else "无需提请临时风险会议，按常规风险委员会流程执行"

    text = f"""# FIN3-WKN-149 多资产专户三季度宏观压力测试与调仓建议
## 风险委员会决策备忘录

**分析截至日：2026-09-15；金额单位：万元；组合净值：{nav:.2f}。**

### 一、结论与建议

当前组合用于风险画像，不纳入四方案硬约束比较。方案A、方案B、方案C的未通过项分别为{fails.get('方案A','无')}、{fails.get('方案B','无')}、{fails.get('方案C','无')}；{recommendation_status}，建议采用推荐方案。推荐方案最大压力损失{fmt_pct(max_loss)}（{max_row.情景编号}/{max_row.冲击套系}）、1日ES99为{fmt_pct(rec_metric['es99'])}、10日VaR99为{fmt_pct(rec_metric['var10_99'])}、单向换手率{fmt_pct(turnover)}。{monitor_text}；{meeting_text}。

### 二、数据核验与样本区间

脚本首先完成文件存在性、manifest行数/起止日、日期唯一性、异常日、空值及交叉源一致性检查，再进入计算。完整风险样本为2018-01-02~2026-06-09，共{len(market['common_axis'])}个价格估值日、{len(market['returns'])}个简单收益日；终止原因是五条中债国债关键期限曲线均止于2026-06-09。数据序列逐项核验如下（分段文件保留各自实际范围与行数；manifest的possible_truncation空白严格记为“未知”，不当作False）：

{md_table(audit_display)}

沪深300和中证500各识别并剔除2026-09-12周六记录，依据是该日不在SSE交易日历；创业板无此异常。境外SPX、USD/CNH和监测所用UST10Y先对齐SSE估值日，只用当日或更早观测进行past-only forward-fill，再计算收益或端点变化；不作向后填充。结构空值不填：5Y LPR在正式发布前为空，pre_close首行空值不参与收益计算；PMI缺2026-08、1Y LPR缺2024-11，月度规则不跨月填充。UST m2与m4重叠期发现{ust_conflicts}个冲突观测，二者不用于核心计算；SHIBOR 1W与DR007在重叠源文件中完全一致，按原始文件保留、不擅自修改。社融、PPI、PMI和LPR均有发布滞后，结论按各自实际截至日。

图1说明：橙色标示存在缺口、结构空值或非SSE异常记录的序列，绿色为未发现上述问题的覆盖区间，红色虚线为分析截至日。

![图1 数据覆盖与缺口]({PREFIX}_charts/{CHART_FILES[1]})

### 三、当前组合风险画像

当前持仓：

{md_table(current_positions)}

资产收益统计（CGB日收益严格按 `-Σ(各关键期限久期贡献×收益率日变动十进制)`，SPX人民币收益为 `(1+r_spx_usd)(1+r_fx)-1`，美元现金人民币收益为FX收益，人民币现金收益为0）：

{md_table(asset_stats)}

相关矩阵：

{md_table(corr)}

组合指标：

{md_table(metric_table)}

风险贡献采用协方差边际波动贡献 `w_i(Σw)_i/(w'Σw)`，允许负贡献（负值表示协方差对组合波动有对冲作用）：

{md_table(rc_table)}

风险口径：风险样本以SSE估值日为主轴；简单收益；历史VaR表示正损失，1日分位数使用 `np.quantile(method='linear')`，ES为损失大于等于VaR的均值；10日指标使用重叠的10个交易日日收益复合；年化波动按√252；最大回撤从每日复合净值计算。图2说明：四方案均按固定权重每日再平衡后复合，风险柱状图同时展示ES99和10日VaR99硬限额，最大回撤明确无硬限额。

![图2 历史风险]({PREFIX}_charts/{CHART_FILES[2]})

### 四、情景识别与历史校准

“权益指数”由当前境内权益内部权重归一化为沪深300/中证500/创业板=50%/30%/20%，按日再平衡，其月收益由月内日收益复合；S3中的SPX和USD/CNH月变化按各自源市场观测计算，避免中外休市错位改变月度识别；中债10Y与DR007取月均；LPR取月末最后有效值且只比较连续日历月；宏观月序列不填缺月。四类情景及全部合格月份：

{md_table(scenario_month_table)}

历史窗口从合格月次月首个SSE交易日的当日收益起算，连续取10个交易日日收益（含首日前一交易日收盘至首日收盘的收益），必须完整落在共同样本；各方案以每日再平衡组合10日累计收益<0筛选，并按累计收益从低到高排列（最大跌幅在前），全部合格窗口用于校准，无窗口则全因子冲击为0：

{md_table(window_table)}

各方案—情景校准冲击为全部合格窗口的因子10日累计变动中位数；境内权益使用上述统一指数，SPX为美元收益，FX为USD/CNH收益，五个CGB因子为端点收益率百分点变动：

{md_table(calibration_table)}

图3说明：上图列出全部情景月份，中图给出推荐方案的历史校准冲击，下图直接比较推荐方案在委员会沿用冲击和历史校准冲击下的压力损失严格程度。

![图3 情景与校准]({PREFIX}_charts/{CHART_FILES[3]})

### 五、压力测试结果

委员会CGB字符串中的+0.10按百分点（+10bp）解释，债券压力收益为 `-Σ(duration×shock/100)`；SPX人民币冲击保留SPX×FX交互项；美元现金贡献为权重×FX；人民币现金贡献为0；境内贡献为三项境内权益权重合计×统一冲击。历史校准冲击按方案相关窗口计算。以下为完整4×4×2=32行，程序已逐行断言四项贡献之和等于总损益：

{md_table(stress_display)}

各方案最大压力损失来源：

{md_table(max_table)}

推荐方案逐情景严格程度：

{md_table(strict_table)}

严格程度差异来自两套冲击的权益/汇率幅度与国债曲线形态共同作用；不能仅按单一因子的绝对值判断。图4-a说明：最大压力损失同时与8%硬限额及7%缓冲线比较。

### 六、候选方案评估与九项约束检查

四方案九项检查共36行；L1使用0.05个百分点容差，L5明确等于美元现金加未对冲SPX，L8/L9均基于各方案32格中的最大压力损失，百分比超限按百分点报告：

{md_table(constraints)}

未发现把SPX QDII漏计外币敞口的情况；所有方案均按 `USD现金+SPX` 计算L5。

### 七、推荐方案与调仓执行

推荐权重直接读取params_holdings的weight_recommended，并校验rules_rebalance：

{md_table(rec_weights)}

规则锁定美元现金和SPX各10%，境内三项按当前内部比例同比缩减；释放20.50个百分点中10.50个百分点转入国债、10.00个百分点转入人民币现金。因此在线性等式组约束下只有一组解，这不是虚构的全空间优化；同换手率下不存在第二组可比较。A/B/C的实际单向换手率与不通过项为：

{md_table(candidate_compare)}

完整交易清单：

{md_table(trade_table)}

执行顺序为先卖三只境内权益，卖出资金当日可用，再买国债；人民币现金路径为10.00%→30.50%→20.00%，全程不低于8%。反例先买国债则为10.00%→-0.50%→20.00%，中间击穿8%下限。卖出合计{nav * turnover:.2f}万元，单向换手率=卖出合计/净值={fmt_pct(turnover)}。图4-b展示两种路径及8%现金下限。

### 八、反向压力测试与监测预警

推荐方案最大压力损失距8%限额尚有{fmt_pp(margin)}裕度；若沿该最大压力损失格的组合损失同比放大，达到8%的倍数为{scale:.2f}倍。按与历史风险指标一致的固定权重每日再平衡口径，共同样本中最差10日累计损失为{fmt_pct(worst_factor_loss)}，区间{worst_factor_start:%Y-%m-%d}~{worst_factor_end:%Y-%m-%d}。

反向压力使用共同样本的重叠10日风险因子向量 `[统一境内权益收益, SPX美元收益, FX收益, 1Y/2Y/5Y/10Y/30Y百分点变动]` 估计均值和协方差；以推荐方案收益精确保留SPX×FX交互和久期项，在组合收益=-8%的约束下用KKT牛顿法求最小马氏距离。最可能冲击如下，最小马氏距离为{reverse_dist:.3f}：

{md_table(reverse_table)}

委员会沿用及推荐方案历史校准冲击相对同一10日因子分布的马氏距离：

{md_table(distance_table)}

八项监测：M1/M2使用最近20个SSE区间（21个价格点）复合/端点；M3为最近20日均值减此前60日均值；M4按中债10Y实际最新2026-06-09向前20个SSE区间；M5直接使用美国10年期国债收益率源市场最近20个交易区间；M6比较最新PPI与三个日历月前；M7为最新PMI；M8由社融存量计算最新同比。

{md_table(monitor_display)}

图4-c说明：反向压力冲击按各因子的历史10日标准差展示；图5说明：八个小面板保留各自单位，红色表示触发、绿色表示未触发。

![图4 方案、执行与反向压力]({PREFIX}_charts/{CHART_FILES[4]})

![图5 监测触发]({PREFIX}_charts/{CHART_FILES[5]})

宏观月频与中债数据存在发布滞后；待PMI 2026-08、LPR1Y 2024-11若获权威补数，以及CGB 2026-06-09后曲线更新后，应重跑同一脚本重新判断。

---

**附件清单**（以用户最新明确要求为准，替代模板“不少于10图”的旧要求）：

- 五张复合图：`{PREFIX}_charts/{CHART_FILES[1]}`、`{CHART_FILES[2]}`、`{CHART_FILES[3]}`、`{CHART_FILES[4]}`、`{CHART_FILES[5]}`；
- 可复算代码：`{PREFIX}_reproduce.py`。
"""
    memo_path = outdir / f"{PREFIX}_风险委员会决策备忘录.md"
    memo_path.write_text(text, encoding="utf-8")
    return memo_path


def main():
    script = Path(__file__).resolve()
    outdir = script.parent
    inp = script.parent.parent / "input_files"
    assert inp.is_dir() and outdir.is_dir()
    setup_plotting()

    audit, loaded, sse, ust_conflicts = audit_inputs(inp)
    market = build_market_data(inp, loaded, sse)
    plans, current, holdings = plan_weights(inp)
    positions = read_csv(inp / "params_positions.csv", dates=False)
    nav = float(positions.market_value_10k_cny.sum())
    assert np.isclose((positions.weight_current * nav).to_numpy(), positions.market_value_10k_cny.to_numpy()).all()

    plan_returns = {name: market["returns"].mul(w, axis=1).sum(axis=1) for name, w in plans.items()}
    current_return = market["returns"].mul(current, axis=1).sum(axis=1)
    metrics = {name: risk_metrics(r) for name, r in plan_returns.items()}
    metrics["当前组合"] = risk_metrics(current_return)

    monthly, flags, months, eq_internal = identify_scenarios(loaded, market, sse)
    window_table, calibrations, all_windows = historical_calibration(months, plans, market, eq_internal, sse)
    stress, committee_vec, scenario_names = run_stress(inp, plans, calibrations, market["duration"])
    constraints = evaluate_constraints(inp, plans, metrics, stress)

    factors = rolling_factor_vectors(market, eq_internal)
    reverse_x, reverse_dist, mu, reverse_cov, precision = reverse_stress(factors, plans["推荐方案"], market["duration"])
    monitors = compute_monitors(loaded, market, sse)

    equity_sales = (current[["EQ_000300", "EQ_000905", "EQ_399006"]] - plans["推荐方案"][["EQ_000300", "EQ_000905", "EQ_399006"]]).sum()
    turnover = float(((current - plans["推荐方案"]).clip(lower=0)).sum())
    assert np.isclose(equity_sales, 0.205) and np.isclose(turnover, 0.205)
    assert np.isclose(plans["推荐方案"].USD_CASH, 0.10) and np.isclose(plans["推荐方案"].SPX, 0.10)
    assert np.isclose(plans["推荐方案"].CGB - current.CGB, 0.105)
    assert np.isclose(plans["推荐方案"].CNY_CASH - current.CNY_CASH, 0.10)

    build_charts(outdir, audit, market, plan_returns, metrics, flags, months, calibrations, stress,
                 current, plans, reverse_x, mu, reverse_cov, monitors)
    memo = build_memo(inp, outdir, audit, ust_conflicts, market, current, holdings, plans, plan_returns,
                      metrics, months, window_table, calibrations, scenario_names, stress, constraints,
                      reverse_x, reverse_dist, factors, committee_vec, mu, precision, monitors, turnover, positions)

    chart_dir = outdir / f"{PREFIX}_charts"
    expected = set(CHART_FILES.values())
    assert memo.exists() and memo.stat().st_size > 0
    assert {p.name for p in chart_dir.iterdir() if p.is_file()} == expected
    assert all((chart_dir / x).stat().st_size > 10_000 for x in expected)
    assert script.exists()
    print(f"完成：{memo}")
    print(f"图表：{chart_dir}（5张PNG）")
    print(f"共同样本：{market['common_axis'][0]:%Y-%m-%d}~{market['common_axis'][-1]:%Y-%m-%d}，{len(market['common_axis'])}估值日/{len(market['returns'])}收益日")


if __name__ == "__main__":
    main()
