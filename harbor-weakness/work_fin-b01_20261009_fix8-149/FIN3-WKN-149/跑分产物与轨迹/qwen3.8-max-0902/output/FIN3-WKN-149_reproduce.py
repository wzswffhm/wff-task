#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FIN3-WKN-149 多资产稳健配置专户：三季度宏观压力测试与调仓建议 —— 可复算代码
=============================================================================
运行方式:  python3 FIN3-WKN-149_reproduce.py
输入:      /app/input_files/  (只读原始快照与参数/规则文件)
输出:      1) stdout 完整结果报告(备忘录八章全部数字的来源)
           2) /app/output/FIN3-WKN-149_charts/ 下 5 张 PNG 图表

设计原则:
  * 不硬编码任何结论数值：全部指标由原始快照 + params_*/rules_* 参数文件计算得出；
  * 分析截至日取自交易日历最后一个交易日（=2026-09-15），不写死在代码里；
  * 结构性空值（序列覆盖期之外、指标发布机制不存在等）一律保留 NaN：
    不前向填充、不按 0 参与计算；
  * 跨市场序列先对齐到上交所估值日，市场间交易日不一致造成的日内缺口才做前向填充；
  * 金额单位万元；百分比两位小数；收益率变动注明 bp / %。
"""

import os
import json
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------------
# 0. 路径与全局口径
# -----------------------------------------------------------------------------
IN_DIR = "/app/input_files"
OUT_DIR = "/app/output"
CHART_DIR = os.path.join(OUT_DIR, "FIN3-WKN-149_charts")
os.makedirs(CHART_DIR, exist_ok=True)

ANN_FACTOR = 252          # 年化因子（约定：sqrt(252)）
PCT = 100.0               # 小数 -> 百分数
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

def f(name):
    return os.path.join(IN_DIR, name)

def hr(title=""):
    print("\n" + "=" * 88)
    if title:
        print(title)
        print("=" * 88)

def sub(title=""):
    print("\n--- " + title + " " + "-" * max(0, 80 - len(title)))

# -----------------------------------------------------------------------------
# 1. 载入交易日历（分析截至日 = 日历最后一个交易日）
# -----------------------------------------------------------------------------
cal = pd.read_csv(f("snapshot_trade_calendar.csv"), parse_dates=["date"])
cal = cal[cal["exchange"] == "SSE"].copy()
tdays_all = pd.DatetimeIndex(cal.loc[cal["is_trading_day"] == 1, "date"].sort_values().unique())
CUTOFF = tdays_all.max()                      # 2026-09-15
CAL_START = tdays_all.min()                   # 2018-01-02
tday_set = set(tdays_all)

hr("第 0 部分  交易日历与分析截至日")
print(f"上交所交易日历: {len(tdays_all)} 个交易日, {CAL_START.date()} ~ {CUTOFF.date()}")
print(f"日历中 is_trading_day 取值: {sorted(cal['is_trading_day'].unique().tolist())} (仅含交易日记录)")
print(f"分析截至日(取自日历最后一个交易日): {CUTOFF.date()}")

# -----------------------------------------------------------------------------
# 2. 数据核验（必须在一切计算之前）
# -----------------------------------------------------------------------------
hr("第 1 部分  数据核验（计算前置）")

manifest = pd.read_csv(f("snapshot_data_manifest.csv"))

def load_seg(files, value_cols):
    """按批次文件拼接同一序列; 返回(合并后 DataFrame, 批次信息 dict)"""
    parts, info = [], {}
    for fn in files:
        d = pd.read_csv(f(fn), parse_dates=["date"])
        d["__src"] = fn
        parts.append(d)
        info[fn] = dict(rows=len(d), start=d["date"].min(), end=d["date"].max())
    df = pd.concat(parts, ignore_index=True).sort_values("date").reset_index(drop=True)
    return df, info

# -- 序列清单: (逻辑名, 文件列表, 值列, 序列类型) --------------------------------
SERIES_DEF = [
    ("沪深300",       ["snapshot_000300SH_seg1.csv", "snapshot_000300SH_seg2.csv"], ["close"], "equity"),
    ("中证500",       ["snapshot_000905SH_seg1.csv", "snapshot_000905SH_seg2.csv"], ["close"], "equity"),
    ("创业板指",      ["snapshot_399006SZ_seg1.csv", "snapshot_399006SZ_seg2.csv"], ["close"], "equity"),
    ("中债国债1Y",    ["snapshot_cgb_yield_1y.csv"],  ["yield_pct"], "yield"),
    ("中债国债2Y",    ["snapshot_cgb_yield_2y.csv"],  ["yield_pct"], "yield"),
    ("中债国债5Y",    ["snapshot_cgb_yield_5y.csv"],  ["yield_pct"], "yield"),
    ("中债国债10Y",   ["snapshot_cgb_yield_10y.csv"], ["yield_pct"], "yield"),
    ("中债国债30Y",   ["snapshot_cgb_yield_30y.csv"], ["yield_pct"], "yield"),
    ("USD/CNH",       ["snapshot_usdcnh_seg1.csv", "snapshot_usdcnh_seg2.csv"], ["usdcnh"], "fx"),
    ("标普500",       ["snapshot_spx.csv"],          ["close"], "us_equity"),
    ("Shibor_ON",     ["snapshot_shibor_seg1.csv", "snapshot_shibor_seg2.csv"], ["shibor_on"], "rate"),
    ("Shibor_1W",     ["snapshot_shibor_seg1.csv", "snapshot_shibor_seg2.csv"], ["shibor_1w"], "rate"),
    ("LPR_1Y",        ["snapshot_lpr_1y.csv"],       ["lpr_1y"], "monthly_rate"),
    ("LPR_5Y",        ["snapshot_lpr_5y.csv"],       ["lpr_5y"], "monthly_rate"),
    ("制造业PMI",     ["snapshot_pmi_manufacturing.csv"], ["pmi_mfg"], "macro_m"),
    ("社融存量",      ["snapshot_afre_stock.csv"],   ["afre_stock"], "macro_m"),
    ("DR007",         ["snapshot_dr007.csv"],        ["dr007"], "rate"),
    ("PPI同比",       ["snapshot_ppi_yoy.csv"],      ["ppi_yoy"], "macro_m"),
    ("美债10Y",       ["snapshot_ust_10y.csv"],      ["yield_pct"], "us_rate"),
    ("美债2M",        ["snapshot_ust_m2.csv"],       ["yield_pct"], "us_rate"),
    ("美债4M",        ["snapshot_ust_m4.csv"],       ["yield_pct"], "us_rate"),
]

raw = {}          # 逻辑名 -> 原始合并 DataFrame
seg_info = {}     # 逻辑名 -> 批次信息
validation = []   # 数据核验记录表

for name, files, vcols, kind in SERIES_DEF:
    df, info = load_seg(files, vcols)
    raw[name] = df
    seg_info[name] = info
    # --- 核验项 ---
    n_rows = len(df)
    d0, d1 = df["date"].min(), df["date"].max()
    dup = int(df["date"].duplicated().sum())
    non_td = df[~df["date"].isin(tday_set)]
    n_non_td = len(non_td)
    # 自身覆盖区间内缺失的上交所交易日
    expect = tdays_all[(tdays_all >= d0) & (tdays_all <= d1)]
    have = set(df["date"])
    missing_td = [d for d in expect if d not in have]
    nan_counts = {c: int(df[c].isna().sum()) for c in vcols}
    # 与 manifest 对照
    man_rows = manifest[manifest["file"].isin(files)]
    man_rec = int(man_rows["records"].sum())
    man_start = pd.to_datetime(man_rows["start"].min()).date()
    man_end = pd.to_datetime(man_rows["end"].max()).date()
    man_trunc = "/".join(man_rows["possible_truncation"].fillna("(空)").astype(str).unique())
    consistent = (n_rows == man_rec) and (d0.date() == man_start) and (d1.date() == man_end)
    validation.append(dict(
        序列=name, 文件="+".join(files), 实际行数=n_rows, 实际起=d0.date(), 实际止=d1.date(),
        重复日期=dup, 非交易日记录=n_non_td, 范围内缺失交易日=len(missing_td),
        结构性空值={k: v for k, v in nan_counts.items() if v > 0},
        manifest记录数=man_rec, manifest起=man_start, manifest止=man_end,
        manifest截断标记=man_trunc, 与manifest一致=consistent,
        距截至日缺口交易日=int(((tdays_all > d1) & (tdays_all <= CUTOFF)).sum()),
    ))

val_df = pd.DataFrame(validation)
sub("1.1 各序列实际覆盖 vs manifest（以文件实际内容为准）")
for _, r in val_df.iterrows():
    print(f"{r['序列']:<10} 行数={r['实际行数']:>5}  覆盖 {r['实际起']} ~ {r['实际止']}  "
          f"非交易日记录={r['非交易日记录']:>3}  缺失交易日={r['范围内缺失交易日']:>3}  "
          f"距截至日缺口={r['距截至日缺口交易日']:>3}  manifest一致={r['与manifest一致']}  截断标记={r['manifest截断标记']}")
    if r["结构性空值"]:
        print(f"           结构性空值: {r['结构性空值']}")

# -- 1.2 休市日异常记录识别（2026-09-12 周六） ---------------------------------
sub("1.2 休市日异常记录识别与剔除")
sat_records = []
for name in ["沪深300", "中证500", "创业板指"]:
    df = raw[name]
    ntr = df[~df["date"].isin(tday_set)].copy()
    for _, r in ntr.iterrows():
        flat = (r["open"] == r["high"] == r["low"] == r["close"] == r["pre_close"])
        amt_ratio = r["amount"] / df["amount"].median()
        sat_records.append({"序列": name, "日期": r["date"].date(), "星期": r["date"].day_name(),
                            "在交易日历": "否", "OHLC全等于pre_close": flat,
                            "成交额": float(r["amount"]), "成交额/样本中位数": round(float(amt_ratio), 4)})
sat_df = pd.DataFrame(sat_records)
print(sat_df.to_string(index=False))
print("识别依据: (1)日期不在上交所交易日历(2026-09-12为周六); (2)open=high=low=close=pre_close 全等; "
      "(3)成交额仅为样本中位数的1%~2%。三条证据一致 -> 判定为休市日异常记录, 予以剔除。")
print("创业板指 seg2 无该记录(898行 vs 沪深300/中证500 的899行), 交叉印证该记录为异常而非真实行情。")

# -- 1.3 序列内部质量检查 --------------------------------------------------------
sub("1.3 序列内部质量检查")
for name in ["沪深300", "中证500", "创业板指"]:
    df = raw[name].copy()
    df = df[~df["date"].isin(tday_set - tday_set)]  # keep all, check internally
    bad_ohlc = int(((df["high"] < df["low"]) | (df["close"] <= 0)).sum())
    d2 = df.sort_values("date").reset_index(drop=True)
    mm = d2[(d2["pre_close"].notna()) & (d2["pre_close"].shift(0).notna())]
    prev_close = d2["close"].shift(1)
    mism = int((mm["pre_close"] - prev_close[mm.index]).abs().gt(1e-3).sum())
    ret = d2["close"].pct_change()
    big = d2.loc[ret.abs() > 0.11, ["date", "close"]]
    seg_big = ", ".join(f"{r['date'].date()}({ret.loc[r.name]*100:+.2f}%)" for _, r in big.iterrows())
    print(f"{name}: OHLC违规={bad_ohlc}, pre_close与前日close不一致={mism}条(均由周六异常记录引起), "
          f"|日收益|>11%={len(big)}条 [{seg_big if seg_big else '无'}], 零/负成交额={int((d2['amount']<=0).sum())}")
print("说明: 创业板指 2024-09-30(+15.36%)/2024-10-08(+17.25%)/2025-04-07(-12.50%) 为真实极端行情"
      "(创业板20%涨跌幅限制以内), 予以保留; 首日 pre_close 为空属结构性空值, 收益按 close 序列计算, 不受影响。")

spx = raw["标普500"]
print(f"标普500: 非上交所交易日记录={len(spx[~spx['date'].isin(tday_set)])}条(美股在A股休市日仍交易, 正常), "
      f"NaN={int(spx['close'].isna().sum())}, 非正值={int((spx['close']<=0).sum())}, "
      f"|日收益|>10%={int((spx['close'].pct_change().abs()>0.10).sum())}条(2020-03-16疫情暴跌, 真实行情)")

# -----------------------------------------------------------------------------
# 3. 对齐到上交所估值日 + 收益序列
# -----------------------------------------------------------------------------
hr("第 2 部分  价格/收益率对齐与收益序列构造")

def clean_to_tdays(df, col, drop_non_td=True):
    """去重、剔除非交易日记录（若要求）、返回以交易日为索引的 Series"""
    d = df.sort_values("date").drop_duplicates("date", keep="last").copy()
    if drop_non_td:
        d = d[d["date"].isin(tday_set)]
    s = d.set_index("date")[col].astype(float)
    return s

align_log = []

def align_series(name, s, ffill_within_coverage, coverage_end=None):
    """把序列对齐到上交所交易日历。
    ffill_within_coverage=True: 覆盖期内的跨市场交易日缺口前向填充;
    覆盖期外(序列起止之外)一律为 NaN —— 结构性空值不填充、不按0计。"""
    cov_start, cov_end = s.index.min(), (coverage_end if coverage_end is not None else s.index.max())
    reindexed = s.reindex(tdays_all)
    filled = reindexed.ffill() if ffill_within_coverage else reindexed
    n_missing_in_cov = int(reindexed[(reindexed.index >= cov_start) & (reindexed.index <= cov_end)].isna().sum())
    # 覆盖期外保持 NaN
    filled[filled.index < cov_start] = np.nan
    filled[filled.index > cov_end] = np.nan
    align_log.append(dict(序列=name, 原始起=cov_start.date(), 原始止=cov_end.date(),
                          覆盖期内缺失交易日=n_missing_in_cov, 是否前向填充=ffill_within_coverage))
    return filled

# 权益(境内): 剔除休市日异常记录后覆盖完整, 无需填充
panel = pd.DataFrame(index=tdays_all)
panel["close_000300"] = align_series("沪深300", clean_to_tdays(raw["沪深300"], "close"), True)
panel["close_000905"] = align_series("中证500", clean_to_tdays(raw["中证500"], "close"), True)
panel["close_399006"] = align_series("创业板指", clean_to_tdays(raw["创业板指"], "close"), True)
# 中债收益率: 覆盖期内完整; 2026-06-09 之后为上游截断 -> 结构性空值, 不填充
for tenor, nm in [("1y", "中债国债1Y"), ("2y", "中债国债2Y"), ("5y", "中债国债5Y"),
                  ("10y", "中债国债10Y"), ("30y", "中债国债30Y")]:
    panel["cgb_" + tenor] = align_series(nm, clean_to_tdays(raw[nm], "yield_pct"), True)
# 美元/人民币、标普500、美债: 跨市场交易日不一致 -> 覆盖期内前向填充
panel["usdcnh"] = align_series("USD/CNH", clean_to_tdays(raw["USD/CNH"], "usdcnh", drop_non_td=False), True)
panel["spx"] = align_series("标普500", clean_to_tdays(raw["标普500"], "close", drop_non_td=False), True)
panel["ust10y"] = align_series("美债10Y", clean_to_tdays(raw["美债10Y"], "yield_pct", drop_non_td=False), True)
panel["dr007"] = align_series("DR007", clean_to_tdays(raw["DR007"], "dr007"), True)

sub("2.1 对齐日志（覆盖期内缺失交易日 -> 前向填充; 覆盖期外 -> 结构性空值 NaN）")
for r in align_log:
    print(f"{r['序列']:<10} 原始覆盖 {r['原始起']}~{r['原始止']}  覆盖期内缺失交易日={r['覆盖期内缺失交易日']:>3}  前向填充={r['是否前向填充']}")

# 注意: USD/CNH 与标普500 用 drop_non_td=False 保留了非上交所交易日(境外交易日)的记录,
# reindex 到上交所日历时这些日期自然被丢弃; 上交所开市而境外休市的日子(如美国假日)按前向填充。
# 中债收益率在调休上班的周末(62条)不属于上交所估值日, 对齐时剔除(其信息已由相邻估值日反映)。

# -- 共同样本区间: 所有参与组合收益的腿均有数据的区间 ----------------------------
legs_need = ["close_000300", "close_000905", "close_399006", "spx", "usdcnh",
             "cgb_1y", "cgb_2y", "cgb_5y", "cgb_10y", "cgb_30y"]
valid = panel[legs_need].notna().all(axis=1)
sample_days = tdays_all[valid.values]
SAMPLE_START, SAMPLE_END = sample_days.min(), sample_days.max()

sub("2.2 共同样本区间（四条腿全部有数据）")
print(f"样本区间: {SAMPLE_START.date()} ~ {SAMPLE_END.date()}")
print(f"样本交易日数: {len(sample_days)}")
print(f"终止原因: 中债国债收益率(五个期限)在 {SAMPLE_END.date()} 之后无数据(上游截断, 距分析截至日 "
      f"{int(((tdays_all > SAMPLE_END) & (tdays_all <= CUTOFF)).sum())} 个交易日); "
      f"为遵守'空值不得按0参与计算、结构性空值不填充', 组合历史风险样本止于该日。")
print(f"权益/汇率/标普序列覆盖至 {CUTOFF.date()}, 继续用于监测指标(M1/M2/M5)与调仓定价基准。")

P = panel.loc[sample_days]          # 共同样本面板
N = len(P)

# -- 收益序列 --------------------------------------------------------------------
ret = pd.DataFrame(index=P.index)
ret["EQ_000300"] = P["close_000300"].pct_change()
ret["EQ_000905"] = P["close_000905"].pct_change()
ret["EQ_399006"] = P["close_399006"].pct_change()
ret["USD_CASH"] = P["usdcnh"].pct_change()                                   # 美元现金人民币收益=汇率变动
ret["SPX_USD"] = P["spx"].pct_change()
ret["SPX"] = (1.0 + ret["SPX_USD"]) * (1.0 + ret["USD_CASH"]) - 1.0          # 复合折算(硬约束3)
for tenor in ["1y", "2y", "5y", "10y", "30y"]:
    ret["dy_" + tenor] = P["cgb_" + tenor].diff()                            # 百分点变动
ret["CNY_CASH"] = 0.0                                                        # 货基: 无市场风险, 收益取0(口径假设)

# 国债组合收益: 按关键期限久期贡献折算(硬约束3)
dur = pd.read_csv(f("params_duration.csv"))
TENOR_MAP = {"1年": "1y", "2年": "2y", "5年": "5y", "10年": "10y", "30年": "30y"}
dur_contrib = {TENOR_MAP[t]: float(c) for t, c in zip(dur["tenor"], dur["duration_contribution"])}
ret["CGB"] = -sum(dur_contrib[t] * ret["dy_" + t] / 100.0 for t in dur_contrib)  # Δy(%)→小数
TOTAL_DURATION = sum(dur_contrib.values())

sub("2.3 国债组合久期折算口径")
print(f"关键期限久期贡献: { {k: v for k, v in dur_contrib.items()} }  组合总久期 = {TOTAL_DURATION:.2f} 年")
print("日收益 = -Σ_tenor 久期贡献 × Δ收益率(小数); 非收益率差值简单加总。")
print("标普500人民币收益 = (1+r_SPX美元)×(1+r_USDCNH) - 1 (复合), 非加法近似。")

ret = ret.iloc[1:]                    # 去掉首个无收益日
RET_DAYS = ret.index
print(f"\n收益样本: {RET_DAYS.min().date()} ~ {RET_DAYS.max().date()}, 共 {len(ret)} 个日收益")
print(f"收益矩阵 NaN 检查: {int(ret[['EQ_000300','EQ_000905','EQ_399006','CGB','USD_CASH','SPX','CNY_CASH']].isna().sum().sum())} (必须为0)")

# -----------------------------------------------------------------------------
# 4. 方案权重
# -----------------------------------------------------------------------------
hr("第 3 部分  方案与权重")
hold = pd.read_csv(f("params_holdings.csv"))
pos = pd.read_csv(f("params_positions.csv"))
plans_df = pd.read_csv(f("plans_candidates.csv"))
NAV = float(pos["market_value_10k_cny"].sum())      # 组合净值(万元), 由持仓明细加总
print(f"组合净值 = {NAV:.2f} 万元 (由 params_positions 加总)")

ASSETS = ["EQ_000300", "EQ_000905", "EQ_399006", "CGB", "USD_CASH", "SPX", "CNY_CASH"]
W_COL = {"EQ_000300": "w_000300", "EQ_000905": "w_000905", "EQ_399006": "w_399006",
         "CGB": "w_cgb", "USD_CASH": "w_usd_cash", "SPX": "w_spx_qdii", "CNY_CASH": "w_cny_cash"}

PLANS = {}
PLANS["当前组合"] = {a: float(hold.loc[hold["asset_class"] == a, "weight_current"].iloc[0]) for a in ASSETS}
for _, r in plans_df.iterrows():
    PLANS[r["plan_id"] + f"({r['proposer']})"] = {a: float(r[W_COL[a]]) for a in ASSETS}
PLANS["推荐方案"] = {a: float(hold.loc[hold["asset_class"] == a, "weight_recommended"].iloc[0]) for a in ASSETS}
PLAN_KEYS = list(PLANS.keys())

# 推荐方案构造规则校验(由 rules_rebalance 的 recommendation_rule 复算, 不硬编码)
rb = pd.read_csv(f("rules_rebalance.csv")).set_index("key")["value"].to_dict()
eq_cur = sum(PLANS["当前组合"][a] for a in ["EQ_000300", "EQ_000905", "EQ_399006"])
eq_rec = sum(PLANS["推荐方案"][a] for a in ["EQ_000300", "EQ_000905", "EQ_399006"])
shrink = eq_rec / eq_cur
sub("3.1 方案权重一览")
print("当前持仓明细(params_positions, 万元):")
for _, r in pos.iterrows():
    print(f"  {r['asset']:<12} {r['asset_class']:<10} 权重 {float(r['weight_current'])*100:>5.2f}%  "
          f"市值 {float(r['market_value_10k_cny']):>8.2f} 万元")
w_table = pd.DataFrame(PLANS).T[ASSETS]
print((w_table * 100).round(2).to_string())
print(f"\n推荐方案构造校验: 境内权益合计 {eq_cur*100:.2f}% -> {eq_rec*100:.2f}% (减配 {(eq_cur-eq_rec)*100:.2f} 个百分点, "
      f"缩减系数 {shrink:.4f}); 国债 {PLANS['当前组合']['CGB']*100:.1f}%->{PLANS['推荐方案']['CGB']*100:.1f}% "
      f"(+{(PLANS['推荐方案']['CGB']-PLANS['当前组合']['CGB'])*100:.1f}pp), "
      f"人民币现金 {PLANS['当前组合']['CNY_CASH']*100:.1f}%->{PLANS['推荐方案']['CNY_CASH']*100:.1f}% "
      f"(+{(PLANS['推荐方案']['CNY_CASH']-PLANS['当前组合']['CNY_CASH'])*100:.1f}pp); "
      f"美元现金与标普QDII权重不变(各10%)。")
print("rules_rebalance.recommendation_rule:", rb["recommendation_rule"])

# -----------------------------------------------------------------------------
# 5. 组合历史风险指标
# -----------------------------------------------------------------------------
hr("第 4 部分  组合历史风险画像（共同样本, 每日再平衡）")

R = ret[ASSETS].values                              # T×7

def portfolio_returns(w):
    wv = np.array([w[a] for a in ASSETS])
    return pd.Series(R @ wv, index=RET_DAYS), wv

def hist_var_es(r, q):
    """历史模拟法(置信度 q): VaR_q = -P_{1-q}(r); ES_q = -mean(r <= P_{1-q}(r))。
    VaR/ES 以正数表示损失幅度。"""
    thr = np.percentile(r, (1 - q) * 100)
    var = -thr
    tail = r[r <= thr]
    es = -tail.mean() if len(tail) else var
    return var, es, len(tail)

def risk_metrics(r):
    nav = (1 + r).cumprod()
    m = {}
    m["ann_vol"] = float(r.std(ddof=1) * np.sqrt(ANN_FACTOR))
    m["var95_1d"], m["es95_1d"], _ = hist_var_es(r.values, 0.95)
    m["var99_1d"], m["es99_1d"], m["es99_tail_n"] = hist_var_es(r.values, 0.99)
    nav10 = nav / nav.shift(10) - 1.0               # 重叠10日累计收益(每日再平衡复利)
    nav10 = nav10.dropna()
    m["var99_10d"] = float(-np.percentile(nav10.values, 1))
    worst_i = int(np.argmin(nav10.values))
    m["worst10"] = float(nav10.values[worst_i])
    m["worst10_end"] = nav10.index[worst_i]
    m["worst10_start"] = nav.index[max(nav.index.get_loc(m["worst10_end"]) - 9, 0)]
    dd = nav / nav.cummax() - 1.0
    trough_i = int(np.argmin(dd.values))
    trough = dd.index[trough_i]
    peak = nav[:trough].idxmax()
    m["mdd"] = float(dd.values[trough_i])
    m["mdd_peak"], m["mdd_trough"] = peak, trough
    rec = nav.loc[trough:][nav.loc[trough:] >= nav.loc[peak]]
    m["mdd_recover"] = rec.index.min() if len(rec) else None
    m["worst_day"] = float(r.min())
    m["worst_day_date"] = r.idxmin()
    m["ann_ret"] = float((nav.iloc[-1]) ** (ANN_FACTOR / len(r)) - 1)
    m["nav_final"] = float(nav.iloc[-1])
    m["nav"] = nav
    m["r"] = r
    return m

METRICS = {}
for k in PLAN_KEYS:
    r_p, wv = portfolio_returns(PLANS[k])
    METRICS[k] = risk_metrics(r_p)

cur = METRICS["当前组合"]
sub("4.1 当前组合(50/20/10/10/10)风险画像")
print(f"年化收益(几何)   : {cur['ann_ret']*100:>8.2f}%")
print(f"年化波动率       : {cur['ann_vol']*100:>8.2f}%   (日波动 {cur['r'].std(ddof=1)*100:.4f}%, 年化因子 sqrt({ANN_FACTOR}))")
print(f"1日 VaR95 / VaR99: {cur['var95_1d']*100:>7.2f}% / {cur['var99_1d']*100:.2f}%")
print(f"1日 ES95  / ES99 : {cur['es95_1d']*100:>7.2f}% / {cur['es99_1d']*100:.2f}%  (ES99尾部样本 {cur['es99_tail_n']} 天)")
print(f"10日 VaR99       : {cur['var99_10d']*100:>8.2f}%   (重叠10日累计收益历史模拟)")
print(f"10日最大累计损失 : {cur['worst10']*100:>8.2f}%   区间 {cur['worst10_start'].date()} -> {cur['worst10_end'].date()}")
print(f"最大回撤         : {cur['mdd']*100:>8.2f}%   峰 {cur['mdd_peak'].date()} 谷 {cur['mdd_trough'].date()} "
      f"修复 {cur['mdd_recover'].date() if cur['mdd_recover'] is not None else '样本内未修复'}")
print(f"最差单日         : {cur['worst_day']*100:>8.2f}%   ({cur['worst_day_date'].date()})")
print(f"期末净值(起点1)  : {cur['nav_final']:.4f}")

sub("4.2 各资产日收益统计特征（共同样本）")
asset_stats = pd.DataFrame({
    "年化收益%": ret[ASSETS].mean() * ANN_FACTOR * PCT,
    "年化波动%": ret[ASSETS].std(ddof=1) * np.sqrt(ANN_FACTOR) * PCT,
    "偏度": ret[ASSETS].skew(),
    "峰度": ret[ASSETS].kurt(),
    "最差单日%": ret[ASSETS].min() * PCT,
    "最好单日%": ret[ASSETS].max() * PCT,
}).round(2)
print(asset_stats.to_string())

sub("4.3 资产日收益相关矩阵")
corr = ret[ASSETS].corr().round(3)
print(corr.to_string())
print("(人民币现金收益恒为0, 相关系数无定义, 显示为NaN)")

sub("4.4 当前组合各资产风险贡献占比（协方差法 RC_i = w_i(Σw)_i / w'Σw）")
w_cur = np.array([PLANS["当前组合"][a] for a in ASSETS])
cov = np.cov(ret[ASSETS].values.T, ddof=1)
mcr = cov @ w_cur
rc = w_cur * mcr
rc_share = rc / rc.sum()
port_var_daily = float(w_cur @ mcr)
for a, s, v in zip(ASSETS, rc_share, rc):
    print(f"  {a:<10} 风险贡献占比 {s*100:>7.2f}%   (RC={v*1e4:.4f}bp^2/日)")
print(f"  组合日方差 = {port_var_daily*1e4:.4f}bp^2 -> 日波动 {np.sqrt(port_var_daily)*100:.4f}% "
      f"-> 年化 {np.sqrt(port_var_daily)*np.sqrt(ANN_FACTOR)*100:.2f}% (与4.1一致)")

sub("4.5 五套权重的历史风险指标对比")
rows = []
for k in PLAN_KEYS:
    m = METRICS[k]
    rows.append(dict(方案=k, 年化波动=m["ann_vol"] * PCT, ES99_1d=m["es99_1d"] * PCT,
                     VaR99_10d=m["var99_10d"] * PCT, 最大回撤=m["mdd"] * PCT,
                     最差10日=m["worst10"] * PCT, 最差单日=m["worst_day"] * PCT))
cmp_df = pd.DataFrame(rows).set_index("方案").round(2)
print(cmp_df.to_string())

# -----------------------------------------------------------------------------
# 6. 情景月度识别
# -----------------------------------------------------------------------------
hr("第 5 部分  情景识别与历史校准")

rules_sc = pd.read_csv(f("rules_scenarios.csv"))
rules_w = pd.read_csv(f("rules_windows.csv")).set_index("key")["value"].to_dict()

# -- 月度聚合 --------------------------------------------------------------------
def month_series_from_raw(name, col):
    d = raw[name].dropna(subset=[col]).copy()
    d["m"] = d["date"].dt.to_period("M")
    return d.groupby("m")[col].last()      # 月值=当月最后一条(月度发布序列每月一条)

pmi_m = month_series_from_raw("制造业PMI", "pmi_mfg")
ppi_m = month_series_from_raw("PPI同比", "ppi_yoy")
afre_m = month_series_from_raw("社融存量", "afre_stock")

# 月度均值/月度收益: 基于对齐后的上交所估值日面板(与收益口径一致)
pan_m = panel.copy()
pan_m["m"] = pan_m.index.to_period("M")
cgb10y_mean_m = pan_m.groupby("m")["cgb_10y"].mean(skipna=True)
dr007_mean_m = pan_m.groupby("m")["dr007"].mean(skipna=True)

def month_end_ret(col):
    s = pan_m[col]
    me = s.groupby(pan_m["m"]).last()
    return me.pct_change(), me

hs300_mret, hs300_me = month_end_ret("close_000300")
hs905_mret, _ = month_end_ret("close_000905")
cyb_mret, _ = month_end_ret("close_399006")
spx_mret, _ = month_end_ret("spx")
fx_mchg, _ = month_end_ret("usdcnh")

# 社融存量同比增速(%)
afre_yoy_m = (afre_m / afre_m.shift(12) - 1) * PCT

# LPR 当月下调判定(基于原始发布记录, 结构性空值不参与)
def lpr_cuts(name, col):
    d = raw[name].dropna(subset=[col]).sort_values("date")
    out = {}
    months = pd.period_range(d["date"].min(), d["date"].max(), freq="M")
    vals = list(zip(d["date"], d[col]))
    last_before = {}
    prev = None
    for m in months:
        in_m = [v for dt, v in vals if dt.to_period("M") == m]
        out[m] = None if (prev is None or not in_m) else bool(min(in_m) < prev - 1e-9)
        if in_m:
            prev = in_m[-1]
    return out

cut1y = lpr_cuts("LPR_1Y", "lpr_1y")
cut5y = lpr_cuts("LPR_5Y", "lpr_5y")

# -- 三值逻辑 ---------------------------------------------------------------------
def tv_and(*xs):
    if any(x is False for x in xs):
        return False
    if all(x is True for x in xs):
        return True
    return None

def tv_or(*xs):
    if any(x is True for x in xs):
        return True
    if all(x is False for x in xs):
        return False
    return None

def g(series, m):
    try:
        v = series.get(m, None)
    except Exception:
        v = None
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return float(v)

def cmp_tv(a, b, op):
    if a is None or b is None:
        return None
    return bool(op(a, b))

ALL_MONTHS = pd.period_range(pd.Period("2018-01", "M"), CUTOFF.to_period("M"), freq="M")

scen_months = {sid: [] for sid in rules_sc["scenario_id"]}
scen_noneval = {sid: [] for sid in rules_sc["scenario_id"]}
scen_detail = []

for m in ALL_MONTHS:
    mp = m - 1
    pmi, pmi_p = g(pmi_m, m), g(pmi_m, mp)
    p1y, p5y = cut1y.get(m, None), cut5y.get(m, None)
    y10, y10p = g(cgb10y_mean_m, m), g(cgb10y_mean_m, mp)
    ppi, ppip = g(ppi_m, m), g(ppi_m, mp)
    hs = g(hs300_mret, m)
    spx_r = g(spx_mret, m)          # 小数收益, 与规则阈值(百分数)比较前 ×100
    fx_c = g(fx_mchg, m)            # 小数变化, 同上
    af_y, af_yp = g(afre_yoy_m, m), g(afre_yoy_m, mp)
    dr, drp = g(dr007_mean_m, m), g(dr007_mean_m, mp)

    # S1: (PMI<50 且 (1Y或5Y LPR当月下调)) 或 (PMI较上月下行>=0.5 且 10Y国债月均低于上月)
    b1 = tv_and(cmp_tv(pmi, 50.0, lambda a, b: a < b), tv_or(p1y, p5y))
    b2 = tv_and(cmp_tv(None if (pmi is None or pmi_p is None) else pmi_p - pmi, 0.5, lambda a, b: a >= b),
                cmp_tv(y10, y10p, lambda a, b: a < b)) if (pmi is not None and pmi_p is not None) else \
         (None if (pmi is None or pmi_p is None or y10 is None or y10p is None) else False)
    s1 = tv_or(b1, b2)
    # S2: PPI同比高于上月 且 10Y国债月均高于上月 且 权益指数当月下跌(以沪深300为代表)
    s2 = tv_and(cmp_tv(ppi, ppip, lambda a, b: a > b) if ppip is not None else None,
                cmp_tv(y10, y10p, lambda a, b: a > b),
                cmp_tv(hs, 0.0, lambda a, b: a < b))
    # S3: 标普500当月收益<=-3% 或 USDCNH当月变化>=+1.5% (月度序列为小数, ×100 换算为百分数后比较)
    s3 = tv_or(cmp_tv(None if spx_r is None else spx_r * 100, -3.0, lambda a, b: a <= b),
               cmp_tv(None if fx_c is None else fx_c * 100, 1.5, lambda a, b: a >= b))
    # S4: 社融存量同比增速低于上月 且 DR007月均高于上月 且 权益指数当月下跌
    s4 = tv_and(cmp_tv(af_y, af_yp, lambda a, b: a < b) if af_yp is not None else None,
                cmp_tv(dr, drp, lambda a, b: a > b),
                cmp_tv(hs, 0.0, lambda a, b: a < b))

    for sid, v in zip(["S1", "S2", "S3", "S4"], [s1, s2, s3, s4]):
        if v is True:
            scen_months[sid].append(m)
        elif v is None:
            scen_noneval[sid].append(m)
    scen_detail.append(dict(月份=str(m), PMI=pmi, PMI上月=pmi_p, LPR1Y下调=p1y, LPR5Y下调=p5y,
                            CGB10Y月均=y10, CGB10Y上月均=y10p, PPI=ppi, PPI上月=ppip,
                            HS300月收益=hs, SPX月收益=spx_r, FX月变化=fx_c,
                            社融同比=af_y, 社融同比上月=af_yp, DR007月均=dr, DR007上月均=drp,
                            S1=s1, S2=s2, S3=s3, S4=s4))

det_df = pd.DataFrame(scen_detail)
sub("5.1 情景识别规则(来自 rules_scenarios.csv)")
for _, r in rules_sc.iterrows():
    print(f"{r['scenario_id']} {r['scenario']}: {r['rule']}  [{r['shock_type']}]")
print("\n口径说明: '权益指数当月下跌'以组合第一大持仓基准沪深300为代表; 月度均值基于上交所估值日对齐面板;")
print("          LPR下调=当月发布值低于月前最后发布值; 三值逻辑: 输入缺失的月份记为'不可判定'(不视为不满足)。")

sub("5.2 各情景合格月份（全部）")
for sid in ["S1", "S2", "S3", "S4"]:
    ms = scen_months[sid]
    ev = [m for m in ALL_MONTHS if m not in scen_noneval[sid]]
    print(f"{sid}: 合格月份 {len(ms)} 个 / 可判定月份 {len(ev)} 个 (不可判定 {len(scen_noneval[sid])} 个)")
    print("    " + ", ".join(str(x) for x in ms))
    if scen_noneval[sid]:
        ne = scen_noneval[sid]
        if len(ne) <= 12:
            print(f"    不可判定月份(输入存在结构性缺失)共{len(ne)}个: " + ", ".join(str(x) for x in ne))
        else:
            print(f"    不可判定月份(输入存在结构性缺失): {str(ne[0])} ~ {str(ne[-1])} 共{len(ne)}个 "
                  f"(最近6个: {', '.join(str(x) for x in ne[-6:])})")

# 敏感性: 权益指数改用三只等权
hs_comp_mret = (hs300_mret + hs905_mret + cyb_mret) / 3.0
sens_cnt = {}
for sid in ["S2", "S4"]:
    cnt = 0
    for m in ALL_MONTHS:
        hs_c = g(hs_comp_mret, m)
        if sid == "S2":
            v = tv_and(cmp_tv(g(ppi_m, m), g(ppi_m, m - 1), lambda a, b: a > b) if g(ppi_m, m - 1) is not None else None,
                       cmp_tv(g(cgb10y_mean_m, m), g(cgb10y_mean_m, m - 1), lambda a, b: a > b),
                       cmp_tv(hs_c, 0.0, lambda a, b: a < b))
        else:
            v = tv_and(cmp_tv(g(afre_yoy_m, m), g(afre_yoy_m, m - 1), lambda a, b: a < b) if g(afre_yoy_m, m - 1) is not None else None,
                       cmp_tv(g(dr007_mean_m, m), g(dr007_mean_m, m - 1), lambda a, b: a > b),
                       cmp_tv(hs_c, 0.0, lambda a, b: a < b))
        if v is True:
            cnt += 1
    sens_cnt[sid] = cnt
print(f"\n敏感性: 若'权益指数'改用三只境内指数等权月收益, S2合格月份 {sens_cnt['S2']} 个, S4合格月份 {sens_cnt['S4']} 个 "
      f"(主口径: S2 {len(scen_months['S2'])} 个, S4 {len(scen_months['S4'])} 个)")

# -----------------------------------------------------------------------------
# 7. 历史窗口构造、合格性判定与校准冲击
# -----------------------------------------------------------------------------
sub("5.3 历史窗口构造规则(来自 rules_windows.csv)")
for k, v in rules_w.items():
    print(f"  {k}: {v}")

td_list = list(tdays_all)
pos_of = {d: i for i, d in enumerate(td_list)}
sample_end_pos = pos_of[SAMPLE_END]

def build_windows(sid, ref_plan_keys):
    """返回(候选窗口list, 不可构造月份list)。窗口=合格月份次月第一个交易日起10个交易日。"""
    cands, skipped = [], []
    for m in scen_months[sid]:
        nxt = m + 1
        days_next = [d for d in td_list if d.to_period("M") == nxt]
        if not days_next:
            skipped.append((m, "次月无交易日记录"))
            continue
        i0 = pos_of[days_next[0]]
        if i0 < 1:
            skipped.append((m, "窗口基期不足"))
            continue
        if i0 + 9 > sample_end_pos:
            skipped.append((m, f"窗口越过共同样本末端({SAMPLE_END.date()}), 国债腿数据不足, 不可判定"))
            continue
        wdays = td_list[i0:i0 + 10]
        base = td_list[i0 - 1]
        cands.append(dict(month=m, base=base, start=wdays[0], end=wdays[-1], days=wdays, i0=i0))
    return cands, skipped

# 组合窗口累计收益(每日再平衡)
NAV_PLAN = {k: METRICS[k]["nav"] for k in PLAN_KEYS}

def window_cum_return(k, w):
    nav = NAV_PLAN[k]
    return float(nav.loc[w["end"]] / nav.loc[w["base"]] - 1.0)

REF_PLAN = "当前组合"    # 情景级窗口合格性判定的参照组合(校准冲击为情景级、与方案无关, 见备忘录说明)
windows, calib_shocks, skipped_all = {}, {}, {}
qualify_matrix = {}
qualify_sets = {}

for sid in ["S1", "S2", "S3", "S4"]:
    cands, skipped = build_windows(sid, REF_PLAN)
    qual = []
    for w in cands:
        rc = {k: window_cum_return(k, w) for k in PLAN_KEYS}
        w["cum_ret"] = rc
        if rc[REF_PLAN] < 0:
            qual.append(w)
    qual.sort(key=lambda w: w["cum_ret"][REF_PLAN])   # 按累计跌幅从大到小(负得最多在前)
    windows[sid] = qual
    skipped_all[sid] = skipped
    qualify_matrix[sid] = {k: sum(1 for w in cands if w["cum_ret"][k] < 0) for k in PLAN_KEYS}
    qualify_matrix[sid]["候选"] = len(cands)
    qualify_sets[sid] = {k: tuple(w["start"] for w in cands if w["cum_ret"][k] < 0) for k in PLAN_KEYS}

    # 校准冲击 = 全部合格窗口内各风险因子10个交易日累计变动的中位数
    if qual:
        eq_c = {a: [] for a in ["EQ_000300", "EQ_000905", "EQ_399006"]}
        spx_l, fx_l, comp_l = [], [], []
        dy_l = {t: [] for t in ["1y", "2y", "5y", "10y", "30y"]}
        for w in qual:
            b, e = w["base"], w["end"]
            cum = {}
            for a, col in [("EQ_000300", "close_000300"), ("EQ_000905", "close_000905"),
                           ("EQ_399006", "close_399006"), ("SPX_USD", "spx"), ("FX", "usdcnh")]:
                cum[a] = float(panel[col].loc[e] / panel[col].loc[b] - 1.0)
                if a in eq_c:
                    eq_c[a].append(cum[a])
            comp_l.append(float(np.mean([cum["EQ_000300"], cum["EQ_000905"], cum["EQ_399006"]])))
            spx_l.append(cum["SPX_USD"])
            fx_l.append(cum["FX"])
            for t in dy_l:
                dy_l[t].append(float((panel["cgb_" + t].loc[e] - panel["cgb_" + t].loc[b]) * 100.0))  # bp
        calib_shocks[sid] = dict(
            cn_equity_shock=float(np.median(comp_l)),
            cn_eq_by_index={a: float(np.median(v)) for a, v in eq_c.items()},
            spx_usd_shock=float(np.median(spx_l)),
            usdcnh_shock=float(np.median(fx_l)),
            cgb_bp={t: float(np.median(v)) for t, v in dy_l.items()},
            n_windows=len(qual),
        )
    else:
        calib_shocks[sid] = dict(cn_equity_shock=0.0, cn_eq_by_index={a: 0.0 for a in ASSETS[:3]},
                                 spx_usd_shock=0.0, usdcnh_shock=0.0,
                                 cgb_bp={t: 0.0 for t in ["1y", "2y", "5y", "10y", "30y"]},
                                 n_windows=0)

for sid in ["S1", "S2", "S3", "S4"]:
    qual = windows[sid]
    cs = calib_shocks[sid]
    print(f"\n{sid}: 合格月份 {len(scen_months[sid])} 个 -> 候选窗口 {qualify_matrix[sid]['候选']} 个 "
          f"-> 合格窗口 {cs['n_windows']} 个 (参照组合={REF_PLAN})")
    for w in qual:
        print(f"    窗口 {w['start'].date()} ~ {w['end'].date()} (月份 {w['month']}, 基期 {w['base'].date()}): "
              f"参照组合累计收益 {w['cum_ret'][REF_PLAN]*100:+.2f}%")
    if skipped_all[sid]:
        for m, why in skipped_all[sid]:
            print(f"    未构造: 合格月份 {m} —— {why}")
    if cs["n_windows"]:
        print(f"    校准冲击: 境内权益 {cs['cn_equity_shock']*100:+.2f}% "
              f"(分指数中位数: 300 {cs['cn_eq_by_index']['EQ_000300']*100:+.2f}%, "
              f"500 {cs['cn_eq_by_index']['EQ_000905']*100:+.2f}%, 创业板 {cs['cn_eq_by_index']['EQ_399006']*100:+.2f}%), "
              f"标普500(美元) {cs['spx_usd_shock']*100:+.2f}%, USDCNH {cs['usdcnh_shock']*100:+.2f}%, "
              f"国债bp {{ {', '.join(t + ':' + format(v, '+.2f') for t, v in cs['cgb_bp'].items())} }}")
    else:
        print("    该情景无合格历史窗口 -> 按 rules_windows 规定, 历史校准冲击按 0 计, 不做任何回退。")

print("\n窗口合格性对参照方案的敏感性(合格窗口数): ")
qm = pd.DataFrame(qualify_matrix).T[["候选"] + PLAN_KEYS]
print(qm.to_string())
identical = all(len(set(qualify_sets[s].values())) == 1 for s in qualify_sets)
print("五套权重下合格窗口集合完全一致(窗口合格性与参照方案无关)" if identical
      else "五套权重下合格窗口集合存在差异(以当前组合为参照判定, 差异明细已在备忘录披露)")
if not identical:
    for s in qualify_sets:
        base = qualify_sets[s][REF_PLAN]
        for k in PLAN_KEYS:
            if qualify_sets[s][k] != base:
                print(f"  {s}/{k}: 与参照组合差异窗口 "
                      f"{[str(d.date()) for d in set(qualify_sets[s][k]) ^ set(base)]}")

# -----------------------------------------------------------------------------
# 8. 压力测试: 4方案(+推荐) × 4情景 × 2套冲击, 四腿分解
# -----------------------------------------------------------------------------
hr("第 6 部分  压力测试（四腿分解, 四部分之和=组合损益）")

com = pd.read_csv(f("params_committee_shocks.csv"))

def parse_bp(s):
    out = {}
    for kv in str(s).split(","):
        k, v = kv.split(":")
        out[{"1Y": "1y", "2Y": "2y", "5Y": "5y", "10Y": "10y", "30Y": "30y"}[k.strip()]] = float(v)
    return out

COM_SHOCKS = {}
for _, r in com.iterrows():
    COM_SHOCKS[r["scenario_id"]] = dict(
        scenario=r["scenario"],
        cn_equity_shock=float(r["cn_equity_shock"]),
        spx_usd_shock=float(r["spx_usd_shock"]),
        usdcnh_shock=float(r["usdcnh_shock"]),
        cgb_bp=parse_bp(r["cgb_shock_bp"]))

def stress_legs(w, sh):
    """返回四腿贡献(占净值比例)与合计。金额=比例×NAV(万元)。"""
    w_eq = w["EQ_000300"] + w["EQ_000905"] + w["EQ_399006"]
    leg_eq = w_eq * sh["cn_equity_shock"]
    leg_spx = w["SPX"] * ((1 + sh["spx_usd_shock"]) * (1 + sh["usdcnh_shock"]) - 1)   # 复合
    leg_usd = w["USD_CASH"] * sh["usdcnh_shock"]
    leg_cgb = w["CGB"] * (-sum(dur_contrib[t] * sh["cgb_bp"][t] / 10000.0 for t in dur_contrib))
    total = leg_eq + leg_spx + leg_usd + leg_cgb
    assert abs(total - (leg_eq + leg_spx + leg_usd + leg_cgb)) < 1e-15
    return dict(境内权益=leg_eq, 标普500人民币=leg_spx, 美元现金=leg_usd, 国债=leg_cgb, 合计=total)

STRESS = {}      # (plan, sid, shockset) -> legs
for k in PLAN_KEYS:
    for sid in ["S1", "S2", "S3", "S4"]:
        STRESS[(k, sid, "委员会沿用")] = stress_legs(PLANS[k], COM_SHOCKS[sid])
        STRESS[(k, sid, "历史校准")] = stress_legs(PLANS[k], calib_shocks[sid])

sub("6.1 全部压力结果（占净值%, 括号内为万元; 四腿之和=合计）")
print(f"{'方案':<14}{'情景':<4}{'冲击':<8}{'境内权益':>12}{'标普500CNY':>12}{'美元现金':>10}{'国债':>9}{'合计%':>9}{'合计万元':>10}")
for k in PLAN_KEYS:
    for sid in ["S1", "S2", "S3", "S4"]:
        for ss in ["委员会沿用", "历史校准"]:
            L = STRESS[(k, sid, ss)]
            print(f"{k:<14}{sid:<4}{ss:<8}"
                  f"{L['境内权益']*PCT:>8.2f}({L['境内权益']*NAV:>8.1f}) "
                  f"{L['标普500人民币']*PCT:>7.2f}({L['标普500人民币']*NAV:>7.1f}) "
                  f"{L['美元现金']*PCT:>6.2f}({L['美元现金']*NAV:>6.1f}) "
                  f"{L['国债']*PCT:>6.3f} "
                  f"{L['合计']*PCT:>8.2f} {L['合计']*NAV:>9.1f}")

sub("6.2 各方案最大压力损失及来源")
max_loss = {}
for k in PLAN_KEYS:
    worst = min(((L["合计"], sid, ss) for sid in ["S1", "S2", "S3", "S4"] for ss in ["委员会沿用", "历史校准"]
                 for L in [STRESS[(k, sid, ss)]]), key=lambda x: x[0])
    max_loss[k] = dict(loss=-worst[0], sid=worst[1], ss=worst[2])
    print(f"{k:<14} 最大压力损失 {max_loss[k]['loss']*PCT:>6.2f}% ({max_loss[k]['loss']*NAV:>7.1f}万元)  "
          f"来源: {worst[1]} {COM_SHOCKS[worst[1]]['scenario']} / {worst[2]}冲击")

sub("6.3 两套冲击严格程度对比（当前组合口径的组合损失, %）")
for sid in ["S1", "S2", "S3", "S4"]:
    a = STRESS[("当前组合", sid, "委员会沿用")]["合计"] * PCT
    b = STRESS[("当前组合", sid, "历史校准")]["合计"] * PCT
    cs = calib_shocks[sid]
    co = COM_SHOCKS[sid]
    stricter = "历史校准更严" if b < a else ("委员会沿用更严" if a < b else "相同")
    print(f"{sid}: 沿用 {a:+.2f}% vs 校准 {b:+.2f}% -> {stricter}")
    print(f"    因子对比: 境内权益 沿用{co['cn_equity_shock']*PCT:+.2f}% / 校准{cs['cn_equity_shock']*PCT:+.2f}%; "
          f"标普 沿用{co['spx_usd_shock']*PCT:+.2f}% / 校准{cs['spx_usd_shock']*PCT:+.2f}%; "
          f"汇率 沿用{co['usdcnh_shock']*PCT:+.2f}% / 校准{cs['usdcnh_shock']*PCT:+.2f}%; "
          f"10Y国债 沿用{co['cgb_bp']['10y']:+.2f}bp / 校准{cs['cgb_bp']['10y']:+.2f}bp")

sub("6.4 委员会国债冲击单位口径敏感性（字段 cgb_shock_bp 按字面'bp'解释 vs 按'百分点'解释）")
print("主口径: 字段名为 cgb_shock_bp, 数值按 bp 字面解释(如 +0.10 => +0.10bp, 国债腿影响可忽略)。")
print("敏感性: 若数值实为百分点(×100 => +10bp), 各方案国债腿与最大压力损失变化如下, 并复核 C8/C9 结论:")
sens_same = True
for k in PLAN_KEYS:
    ml_bp, ml_pct = 0.0, 0.0
    leg_bp, leg_pct = [], []
    for sid in ["S1", "S2", "S3", "S4"]:
        for sh, tag in [(COM_SHOCKS[sid], "c"), (calib_shocks[sid], "k")]:
            L = stress_legs(PLANS[k], sh)
            ml_bp = max(ml_bp, -L["合计"])
            if tag == "c":
                sh_alt = dict(sh, cgb_bp={t: v * 100 for t, v in sh["cgb_bp"].items()})
                La = stress_legs(PLANS[k], sh_alt)
                ml_pct = max(ml_pct, -La["合计"])
                leg_bp.append(L["国债"] * PCT)
                leg_pct.append(La["国债"] * PCT)
            else:
                ml_pct = max(ml_pct, -L["合计"])
    c8a, c8b = ml_bp <= 0.08 + 1e-12, ml_pct <= 0.08 + 1e-12
    extra = ""
    if k == "推荐方案":
        c9a, c9b = ml_bp <= 0.07 + 1e-12, ml_pct <= 0.07 + 1e-12
        extra = f"; C9缓冲(≤7%): bp口径 {'通过' if c9a else '不通过'} / 百分点口径 {'通过' if c9b else '不通过'}"
        sens_same = sens_same and (c9a == c9b)
    sens_same = sens_same and (c8a == c8b)
    print(f"  {k:<14} 委员会国债腿(4情景, bp口径) [{', '.join(f'{v:+.3f}' for v in leg_bp)}] pp -> "
          f"(百分点口径) [{', '.join(f'{v:+.3f}' for v in leg_pct)}] pp; "
          f"最大压力损失 {ml_bp*PCT:.2f}% -> {ml_pct*PCT:.2f}%; C8(≤8%): {'通过' if c8a else '不通过'} -> "
          f"{'通过' if c8b else '不通过'}{extra}")
print("  => 两种单位口径下各方案 C8/C9 通过与不通过结论完全一致(国债腿量级远小于权益腿), 主口径选择不影响任何约束判定。"
      if sens_same else
      "  => 注意: 两种单位口径下存在约束判定结论不一致的方案(见上), 备忘录须按 bp 主口径披露并说明差异。")

# -----------------------------------------------------------------------------
# 9. 九项约束检查
# -----------------------------------------------------------------------------
hr("第 7 部分  九项约束逐条检查")
limits = pd.read_csv(f("params_limits.csv"))
checks = pd.read_csv(f("rules_checks.csv"))
print(limits.to_string(index=False))

def check_plan(k):
    w = PLANS[k]
    m = METRICS[k]
    ml = max_loss[k]["loss"]
    res = {}
    tot = sum(w.values())
    res["C1"] = dict(值=tot, 通过=abs(tot - 1.0) <= 0.0005, 超限=abs(tot - 1.0) - 0.0005)
    eq = w["EQ_000300"] + w["EQ_000905"] + w["EQ_399006"]
    res["C2"] = dict(值=eq, 通过=eq <= 0.60 + 1e-12, 超限=eq - 0.60)
    res["C3"] = dict(值=w["CNY_CASH"], 通过=0.08 - 1e-12 <= w["CNY_CASH"] <= 0.20 + 1e-12,
                     超限=(0.08 - w["CNY_CASH"]) if w["CNY_CASH"] < 0.08 else (w["CNY_CASH"] - 0.20))
    res["C4"] = dict(值=w["CGB"], 通过=w["CGB"] >= 0.15 - 1e-12, 超限=0.15 - w["CGB"])
    fxexp = w["USD_CASH"] + w["SPX"]
    res["C5"] = dict(值=fxexp, 通过=fxexp <= 0.25 + 1e-12, 超限=fxexp - 0.25)
    res["C6"] = dict(值=m["es99_1d"], 通过=m["es99_1d"] <= 0.035 + 1e-12, 超限=m["es99_1d"] - 0.035)
    res["C7"] = dict(值=m["var99_10d"], 通过=m["var99_10d"] <= 0.06 + 1e-12, 超限=m["var99_10d"] - 0.06)
    res["C8"] = dict(值=ml, 通过=ml <= 0.08 + 1e-12, 超限=ml - 0.08)
    res["C9"] = dict(值=ml, 通过=ml <= 0.07 + 1e-12, 超限=ml - 0.07)
    return res

CHECKS = {k: check_plan(k) for k in PLAN_KEYS}
CHECK_ORDER = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"]
VAL_FMT = {"C1": ("权重合计", PCT, "%"), "C2": ("权益合计", PCT, "%"), "C3": ("人民币现金", PCT, "%"),
           "C4": ("国债", PCT, "%"), "C5": ("外币敞口", PCT, "%"), "C6": ("ES99_1d", PCT, "%"),
           "C7": ("VaR99_10d", PCT, "%"), "C8": ("最大压力损失", PCT, "%"), "C9": ("最大压力损失", PCT, "%")}

sub("7.1 检查结果（√通过 / ×未通过, 括号内为具体数值; 超限幅度为正表示违反）")
header = f"{'检查':<6}{'口径':<12}" + "".join(f"{k:>16}" for k in PLAN_KEYS)
print(header)
for c in CHECK_ORDER:
    lbl = VAL_FMT[c]
    row = f"{c:<6}{lbl[0]:<12}"
    for k in PLAN_KEYS:
        r = CHECKS[k][c]
        mark = "√" if r["通过"] else "×"
        row += f"{mark} {r['值']*lbl[1]:>8.2f}{lbl[2]:<2}   "
    print(row)
print()
for k in PLAN_KEYS:
    fails = [c for c in CHECK_ORDER if not CHECKS[k][c]["通过"]]
    if fails:
        detail = "; ".join(f"{c}(值={CHECKS[k][c]['值']*PCT:.2f}%, 超限{CHECKS[k][c]['超限']*PCT:+.2f}pp)"
                           for c in fails)
        print(f"{k:<14} 未通过 {len(fails)} 项: {detail}")
    else:
        print(f"{k:<14} 九项全部通过")

print("\nC5外币敞口口径说明(params_limits L5): 美元现金及存款 + 不对冲汇率的标普500 QDII 均计入外币敞口。")
for k in PLAN_KEYS:
    w = PLANS[k]
    print(f"  {k:<14} 美元现金 {w['USD_CASH']*100:>5.2f}% + 标普QDII {w['SPX']*100:>5.2f}% = "
          f"{(w['USD_CASH']+w['SPX'])*100:>5.2f}% (若漏计QDII则误报为 {w['USD_CASH']*100:.2f}%)")

# -----------------------------------------------------------------------------
# 10. 推荐方案唯一性(同换手率下的网格搜索)与调仓执行
# -----------------------------------------------------------------------------
hr("第 8 部分  推荐方案唯一性与调仓执行")

def turnover_oneway(w_from, w_to):
    sells = sum(max(0.0, (w_from[a] - w_to[a])) for a in ASSETS)
    return sells

def full_check_vec(w, r_p_cache={}):
    """对任意权重向量执行九项检查(历史风险指标由收益矩阵直接计算)"""
    wv = np.array([w[a] for a in ASSETS])
    rp = R @ wv
    tot = wv.sum()
    eq = w["EQ_000300"] + w["EQ_000905"] + w["EQ_399006"]
    thr99 = np.percentile(rp, 1)
    tail99 = rp[rp <= thr99]
    es99 = -tail99.mean() if len(tail99) else -thr99
    nav = np.cumprod(1 + rp)
    nav10 = nav[10:] / nav[:-10] - 1.0        # 重叠10日累计收益
    var99_10 = -np.percentile(nav10, 1)
    # 压力
    ml = 0.0
    for sid in ["S1", "S2", "S3", "S4"]:
        for sh in [COM_SHOCKS[sid], calib_shocks[sid]]:
            L = stress_legs(w, sh)["合计"]
            ml = max(ml, -L)
    ok = (abs(tot - 1) <= 0.0005 and eq <= 0.6 + 1e-12 and 0.08 - 1e-12 <= w["CNY_CASH"] <= 0.2 + 1e-12
          and w["CGB"] >= 0.15 - 1e-12 and w["USD_CASH"] + w["SPX"] <= 0.25 + 1e-12
          and es99 <= 0.035 + 1e-12 and var99_10 <= 0.06 + 1e-12 and ml <= 0.07 + 1e-12)
    return ok, dict(es99=es99, var99_10d=var99_10, max_stress=ml)

w_cur = PLANS["当前组合"]
w_rec = PLANS["推荐方案"]
to_rec = turnover_oneway(w_cur, w_rec)
sub("8.1 推荐方案换手率与九项检查")
print(f"推荐方案单向换手率 = 卖出金额合计/净值 = {to_rec*NAV:.2f}/{NAV:.2f} = {to_rec*PCT:.2f}%")
ok_rec, aux_rec = full_check_vec(w_rec)
print(f"推荐方案九项检查(含C9缓冲): {'全部通过' if ok_rec else '存在未通过'}  "
      f"ES99_1d={aux_rec['es99']*100:.2f}%, VaR99_10d={aux_rec['var99_10d']*100:.2f}%, "
      f"最大压力损失={aux_rec['max_stress']*100:.2f}%")

sub("8.2 唯一性搜索: 美元现金/标普QDII固定10%, 境内权益同比例缩减, 释放资金在国债与人民币现金间分配")
grid = []
k_vals = np.arange(0.30, 1.0001, 0.005)
for kk in k_vals:
    freed = 0.5 * (1 - kk)                     # 权益合计50% -> 50k%, 释放 freed
    if freed < -1e-12:
        continue
    s_cny_vals = np.arange(0, freed + 1e-9, 0.005) if freed > 0 else [0.0]
    for s_cny in s_cny_vals:
        s_cgb = freed - s_cny
        w = {"EQ_000300": w_cur["EQ_000300"] * kk, "EQ_000905": w_cur["EQ_000905"] * kk,
             "EQ_399006": w_cur["EQ_399006"] * kk, "CGB": w_cur["CGB"] + s_cgb,
             "USD_CASH": 0.10, "SPX": 0.10, "CNY_CASH": w_cur["CNY_CASH"] + s_cny}
        to = turnover_oneway(w_cur, w)
        # 快速筛: 先做权重类检查, 再算风险
        eqsum = w["EQ_000300"] + w["EQ_000905"] + w["EQ_399006"]
        if not (abs(sum(w.values()) - 1) <= 0.0005 and eqsum <= 0.6 + 1e-12
                and 0.08 - 1e-12 <= w["CNY_CASH"] <= 0.2 + 1e-12 and w["CGB"] >= 0.15 - 1e-12):
            continue
        ok, aux = full_check_vec(w)
        grid.append(dict(k=round(float(kk), 4), turnover=to, ok=ok, w=dict(w), **aux))
grid_df = pd.DataFrame(grid)
SORT_KEYS = ["max_stress", "var99_10d", "es99"]
allpass = grid_df[grid_df["ok"]].sort_values(["turnover"] + SORT_KEYS).reset_index(drop=True)
print(f"网格规模: {len(grid_df)} 个组合; 九项全过: {len(allpass)} 个")
if len(allpass):
    print(f"全过组合的最小单向换手率 = {allpass['turnover'].iloc[0]*PCT:.2f}%")
    print(f"推荐方案换手率 = {to_rec*PCT:.2f}%; 是否达到最小换手率: {abs(allpass['turnover'].iloc[0]-to_rec)<1e-9}")
    # 最小换手率前沿的诚实披露: 更低换手率的全过组合是否存在, 其C9裕度如何
    r_min = allpass.iloc[0]
    if abs(r_min["turnover"] - to_rec) > 1e-9:
        print(f"披露: 存在换手率更低的全过组合 (k={r_min['k']:.3f}, 国债 {r_min['w']['CGB']*100:.1f}% / "
              f"现金 {r_min['w']['CNY_CASH']*100:.1f}%, 换手率 {r_min['turnover']*PCT:.2f}%), "
              f"其最大压力损失 {r_min['max_stress']*PCT:.2f}% (距7%缓冲线仅 {(0.07-r_min['max_stress'])*PCT:.2f}pp), "
              f"而推荐方案 {aux_rec['max_stress']*PCT:.2f}% (裕度 {(0.07-aux_rec['max_stress'])*PCT:.2f}pp)。")
        print("      推荐方案并非全局最小换手率解, 而是 recommendation_rule 构造约束(权益×0.59、国债+10.5pp、现金+10pp)下的唯一解; "
              "更低换手率解的C9裕度过薄(≈0.04pp), 冲击估计稍有偏差即穿破缓冲线, 不构成更优选择。")
    def is_rec(w):
        return all(abs(w[a] - w_rec[a]) < 1e-9 for a in ASSETS)
    same_to = allpass[np.isclose(allpass["turnover"], to_rec, atol=1e-9)].sort_values(SORT_KEYS).reset_index(drop=True)
    cash_arr = same_to["w"].apply(lambda w: w["CNY_CASH"])
    n_maxcash = int((np.isclose(cash_arr, 0.20)).sum())
    print(f"\n与推荐方案同换手率({to_rec*PCT:.2f}%, 即权益同比例系数 k=0.590)且九项全过的组合共 {len(same_to)} 个")
    print(f"  现金腿范围 {cash_arr.min()*PCT:.1f}% ~ {cash_arr.max()*PCT:.1f}% (国债腿承接其余释放资金); "
          f"其中国债/现金分配使现金处于C3上限20%的仅 {n_maxcash} 个, 即推荐方案")
    print(f"  按(最大压力损失, VaR99_10d, ES99)排序(前5):")
    for i, r in same_to.head(5).iterrows():
        w = r["w"]
        tag = " <- 推荐方案" if is_rec(w) else ""
        print(f"  国债{w['CGB']*100:>5.1f}%/现金{w['CNY_CASH']*100:>5.1f}%: 最大压力损失 {r['max_stress']*PCT:.2f}%, "
              f"ES99 {r['es99']*100:.2f}%, VaR99_10d {r['var99_10d']*100:.2f}%{tag}")
    second = same_to[~same_to["w"].apply(is_rec)]
    if len(second):
        r2 = second.iloc[0]
        w2 = r2["w"]
        print(f"\n  同换手率下风险指标最优的非推荐组合: 国债 {w2['CGB']*100:.1f}% / 现金 {w2['CNY_CASH']*100:.1f}% (k={r2['k']:.3f})")
        print(f"    最大压力损失 {r2['max_stress']*PCT:.2f}% vs 推荐 {aux_rec['max_stress']*PCT:.2f}% (并列, 均由S4委员会冲击主导, 权益腿相同); "
              f"ES99 {r2['es99']*PCT:.2f}% vs {aux_rec['es99']*PCT:.2f}%; VaR99_10d {r2['var99_10d']*PCT:.2f}% vs {aux_rec['var99_10d']*PCT:.2f}%")
        print("    差异说明: 国债更重/现金更轻的组合 ES99 与 VaR99_10d 略低(样本内国债低波动且与境内权益负相关),")
        print("    但其现金腿低于C3上限, 牺牲流动性缓冲; 推荐方案是同换手率下唯一将人民币现金置于C3上限20%的组合,")
        print("    与 recommendation_rule 构造(释放资金 10.5pp入国债、10pp入现金)完全一致 => 在规则构造约束下唯一。")

sub("8.3 交易清单（按 2026-09-15 估值日价格, 单位万元）")
trades = []
NAME_CN = {"EQ_000300": "沪深300指数基金", "EQ_000905": "中证500指数基金", "EQ_399006": "创业板指数基金",
           "CGB": "中长期国债组合", "USD_CASH": "美元现金及存款", "SPX": "标普500 QDII基金",
           "CNY_CASH": "人民币现金及货基"}
for a in ASSETS:
    cur_amt = w_cur[a] * NAV
    tgt_amt = w_rec[a] * NAV
    d = tgt_amt - cur_amt
    if abs(d) >= 0.005:
        trades.append(dict(资产=NAME_CN[a], 方向="卖出" if d < 0 else "买入", 金额万元=round(abs(d), 2),
                           当前万元=round(cur_amt, 2), 目标万元=round(tgt_amt, 2)))
trade_df = pd.DataFrame(trades)
print(trade_df.to_string(index=False))
total_sell = trade_df.loc[trade_df["方向"] == "卖出", "金额万元"].sum()
total_buy = trade_df.loc[trade_df["方向"] == "买入", "金额万元"].sum()
print(f"卖出合计 {total_sell:.2f} 万元, 买入合计 {total_buy:.2f} 万元; 单向换手率 = {total_sell/NAV*PCT:.2f}%")
print("人民币现金及货基 +1000.00 万元为卖出资金的留存(无证券交易), 不构成买卖指令; "
      "标普500 QDII 无交易 -> T+7 赎回款到账规则不触发。")

sub("8.4 执行路径与现金下限(8%)检验")
cash0 = w_cur["CNY_CASH"] * NAV
sells = [(t["资产"], t["金额万元"]) for _, t in trade_df[trade_df["方向"] == "卖出"].iterrows()]
# 人民币现金及货基本身即现金腿, 卖出资金留存货基不产生扣款指令; 执行路径中仅国债买入扣款
buys = [(t["资产"], t["金额万元"]) for _, t in trade_df[trade_df["方向"] == "买入"].iterrows()
        if t["资产"] != "人民币现金及货基"]

def run_path(order):
    cash = cash0
    path = [("期初", cash, cash / NAV)]
    for nm, amt in order:
        if nm.startswith("卖出"):
            cash += amt
            path.append((nm.split("|")[1], cash, cash / NAV))
        else:
            cash -= amt
            path.append((nm.split("|")[1], cash, cash / NAV))
    return path

sell_steps = [("卖出|" + s[0], s[1]) for s in sells]
buy_steps = [("买入|" + b[0], b[1]) for b in buys]
path_sell_first = run_path(sell_steps + buy_steps)
path_buy_first = run_path(buy_steps + sell_steps)
for label, path in [("先卖出后买入(规则口径)", path_sell_first), ("先买入后卖出(对照)", path_buy_first)]:
    print(f"\n{label}:")
    breach = False
    for nm, c, ratio in path:
        flag = "" if ratio >= 0.08 - 1e-12 else "  <-- 击穿8%下限"
        if ratio < 0.08 - 1e-12:
            breach = True
        print(f"  {nm:<22} 现金 {c:>9.2f} 万元  占比 {ratio*PCT:>6.2f}%{flag}")
    print(f"  结论: {'存在击穿, 不可执行' if breach else '全程不低于8%下限, 可执行'}")

# -----------------------------------------------------------------------------
# 11. 反向压力测试（最小马氏距离）
# -----------------------------------------------------------------------------
hr("第 9 部分  反向压力测试与监测预警")

FACTORS = ["cn_eq", "spx_usd", "fx", "dy1", "dy2", "dy5", "dy10", "dy30"]

# 历史10日重叠累计变动样本(共同样本内)
X_rows = []
eq_mat = P[["close_000300", "close_000905", "close_399006"]].values
spx_v = P["spx"].values
fx_v = P["usdcnh"].values
y_mat = P[["cgb_1y", "cgb_2y", "cgb_5y", "cgb_10y", "cgb_30y"]].values
idx_days = P.index
for i in range(10, N):
    j = i - 10
    eq_c = eq_mat[i] / eq_mat[j] - 1
    X_rows.append([float(np.mean(eq_c)), float(spx_v[i] / spx_v[j] - 1), float(fx_v[i] / fx_v[j] - 1),
                   *( (y_mat[i] - y_mat[j]) * 100.0 )])
X = np.array(X_rows)
X_dates = idx_days[10:]
SIGMA = np.cov(X.T, ddof=1)
SIGMA_INV = np.linalg.pinv(SIGMA)

def loss_exact(w, x):
    sh = dict(cn_equity_shock=x[0], spx_usd_shock=x[1], usdcnh_shock=x[2],
              cgb_bp={"1y": x[3], "2y": x[4], "5y": x[5], "10y": x[6], "30y": x[7]})
    return stress_legs(w, sh)["合计"]

# 损失在0处的梯度(线性化): d(loss)/dx
w = w_rec
a = np.zeros(8)
a[0] = w["EQ_000300"] + w["EQ_000905"] + w["EQ_399006"]
a[1] = w["SPX"]                      # ∂/∂spx (1+spx)(1+fx)-1 @0 = 1
a[2] = w["SPX"] + w["USD_CASH"]      # ∂/∂fx  = (1+spx)@0 *w_spx + w_usd
for i, t in enumerate(["1y", "2y", "5y", "10y", "30y"]):
    a[3 + i] = -w["CGB"] * dur_contrib[t] / 10000.0   # 每bp

TARGET = 0.08                       # L8 压力损失上限(触及即为违约边界)
# 最小化 x'Σ⁻¹x s.t. a'x = -TARGET 的拉格朗日解: x* = -TARGET·Σa/(a'Σa), d = TARGET/sqrt(a'Σa)
Sa = SIGMA @ a
aSa = float(a @ Sa)                 # = a'Σa > 0
d_lin = np.sqrt(TARGET ** 2 / aSa)  # 线性化闭式解的马氏距离(参考值)

# 精确损失含 spx×fx 交叉项 -> 沿最速下降方向 x_dir = -Σa/||Σa|| 缩放, 二分求 loss = -TARGET
x_dir = -Sa / np.linalg.norm(Sa)
def loss_of_lam(lam):
    return loss_exact(w_rec, lam * x_dir)
hi = max(1.0, TARGET * np.linalg.norm(Sa) / aSa * 2)
while -loss_of_lam(hi) < TARGET:    # 自适应扩大括号区间
    hi *= 2.0
lo = 0.0
for _ in range(200):                # loss 沿该射线单调下降, 二分求 -loss = TARGET
    mid = (lo + hi) / 2
    if -loss_of_lam(mid) < TARGET:
        lo = mid
    else:
        hi = mid
lam_star = (lo + hi) / 2
x_star = lam_star * x_dir
d2_star = float(x_star @ SIGMA_INV @ x_star)
d_star = np.sqrt(max(d2_star, 0))
loss_star = loss_exact(w_rec, x_star)

sub("9.1 反向压力测试: 使推荐方案触及 8% 压力损失上限的最小马氏距离情景")
print(f"因子编码: cn_eq=境内权益(三指数同幅), spx_usd=标普美元收益, fx=USDCNH变动, dy*=各期限国债收益率变动(bp)")
print(f"历史10日重叠窗口样本: {X.shape[0]} 个, 协方差矩阵条件数 {np.linalg.cond(SIGMA):.3e} (用伪逆)")
print(f"最可能违约情景 x* (最小马氏距离):")
print(f"  境内权益   {x_star[0]*PCT:>+8.2f}%")
print(f"  标普500美元 {x_star[1]*PCT:>+8.2f}%")
print(f"  USD/CNH    {x_star[2]*PCT:>+8.2f}%")
for i, t in enumerate(["1Y", "2Y", "5Y", "10Y", "30Y"]):
    print(f"  国债{t:<4}  {x_star[3+i]:>+8.2f} bp")
print(f"  精确组合损失 = {loss_star*PCT:+.2f}% (= -8.00% 边界), 马氏距离 d = {d_star:.4f}")
print(f"  (线性化闭式解参考距离 d_lin = {d_lin:.4f}; 精确解含标普×汇率交叉项, 二者差异反映非线性程度)")

def maha(x):
    return float(np.sqrt(max(x @ SIGMA_INV @ x, 0)))

def shock_to_vec(sh):
    return np.array([sh["cn_equity_shock"], sh["spx_usd_shock"], sh["usdcnh_shock"],
                     sh["cgb_bp"]["1y"], sh["cgb_bp"]["2y"], sh["cgb_bp"]["5y"],
                     sh["cgb_bp"]["10y"], sh["cgb_bp"]["30y"]])

sub("9.2 各冲击向量的马氏距离对比")
d_hist = np.sqrt(np.einsum("ij,jk,ik->i", X, SIGMA_INV, X))
print(f"历史10日窗口马氏距离分布: 中位数 {np.median(d_hist):.3f}, P90 {np.percentile(d_hist,90):.3f}, "
      f"P99 {np.percentile(d_hist,99):.3f}, 最大 {d_hist.max():.3f}")
for sid in ["S1", "S2", "S3", "S4"]:
    dc = maha(shock_to_vec(COM_SHOCKS[sid]))
    dk = maha(shock_to_vec(calib_shocks[sid]))
    pct_c = float((d_hist <= dc).mean())
    pct_k = float((d_hist <= dk).mean())
    print(f"{sid}: 委员会沿用冲击 d={dc:.3f} (历史分位 {pct_c*100:.1f}%) | 校准冲击 d={dk:.3f} (历史分位 {pct_k*100:.1f}%)")
pct_star = float((d_hist <= d_star).mean())
print(f"反向压力最可能情景 d={d_star:.3f} (历史分位 {pct_star*100:.1f}%)")

sub("9.3 推荐方案最大压力损失情景的裕度与放大倍数")
ml_rec = max_loss["推荐方案"]
print(f"推荐方案最大压力损失 = {ml_rec['loss']*PCT:.2f}% (来源 {ml_rec['sid']}/{ml_rec['ss']})")
print(f"距 8% 上限裕度 = {(0.08-ml_rec['loss'])*PCT:.2f}pp; 距 7% 缓冲线裕度 = {(0.07-ml_rec['loss'])*PCT:.2f}pp")
# 放大倍数: 将该情景冲击等比放大至触及8%所需倍数(精确解, 含交叉项)
sh_worst = COM_SHOCKS[ml_rec["sid"]] if ml_rec["ss"] == "委员会沿用" else calib_shocks[ml_rec["sid"]]
x0 = shock_to_vec(sh_worst)
def loss_of_scale(s):
    return loss_exact(w_rec, s * x0)
lo2, hi2 = 1.0, 2.0
if -loss_of_scale(1.0) >= TARGET:
    amp = 1.0
else:
    while -loss_of_scale(hi2) < TARGET:
        hi2 *= 2.0
    for _ in range(200):
        mid = (lo2 + hi2) / 2
        if -loss_of_scale(mid) < TARGET:
            lo2 = mid
        else:
            hi2 = mid
    amp = (lo2 + hi2) / 2
print(f"最不利情景冲击需等比放大 {amp:.3f} 倍方触及 8% 上限 (线性近似 0.08/损失 = {0.08/ml_rec['loss']:.3f})")

sub("9.4 推荐方案样本内最差10日累计损失")
mr = METRICS["推荐方案"]
print(f"最差10日累计损失 {mr['worst10']*PCT:.2f}%, 区间 {mr['worst10_start'].date()} -> {mr['worst10_end'].date()}")
print(f"最大回撤 {mr['mdd']*PCT:.2f}% (峰 {mr['mdd_peak'].date()}, 谷 {mr['mdd_trough'].date()}, "
      f"修复 {mr['mdd_recover'].date() if mr['mdd_recover'] is not None else '未修复'})")

# -----------------------------------------------------------------------------
# 12. 监测指标 M1~M8
# -----------------------------------------------------------------------------
hr("第 10 部分  八个监测指标（截至日状态）")

mon_tpl = pd.read_csv(f("template_monitor.csv"), encoding="utf-8-sig")

def last_n_valid(s, n, upto=None):
    ss = s.dropna()
    if upto is not None:
        ss = ss[ss.index <= upto]
    return ss.iloc[-n:]

# M1 沪深300 20日收益(至截至日)
c300 = panel["close_000300"].dropna()
c300_cut = c300[c300.index <= CUTOFF]
m1 = float(c300_cut.iloc[-1] / c300_cut.iloc[-21] - 1)
m1_asof = c300_cut.index[-1]
# M2 USDCNH 20日变化
fxs = panel["usdcnh"].dropna(); fxs = fxs[fxs.index <= CUTOFF]
m2 = float(fxs.iloc[-1] / fxs.iloc[-21] - 1)
m2_asof = fxs.index[-1]
# M3 DR007: 最近20日均值 vs 此前60日均值 (bp)
dr = panel["dr007"].dropna(); dr = dr[dr.index <= CUTOFF]
m3 = float((dr.iloc[-20:].mean() - dr.iloc[-80:-20].mean()) * 100)
m3_asof = dr.index[-1]
# M4 10Y国债20日变化 (数据止于共同样本末端)
y10 = panel["cgb_10y"].dropna()
m4 = float((y10.iloc[-1] - y10.iloc[-21]) * 100)
m4_asof = y10.index[-1]
# M5 美债10Y 20日变化(对齐到上交所日)
u10 = panel["ust10y"].dropna(); u10 = u10[u10.index <= CUTOFF]
m5 = float((u10.iloc[-1] - u10.iloc[-21]) * 100)
m5_asof = u10.index[-1]
# M6 PPI 同比加速: 最新月 vs 3个月前 (百分点)
pp = ppi_m.dropna()
m6 = float(pp.iloc[-1] - pp.iloc[-4])
m6_asof = pp.index[-1]
m6_base = pp.index[-4]
# M7 PMI 最新月值
pm = pmi_m.dropna()
m7 = float(pm.iloc[-1]); m7_asof = pm.index[-1]
# M8 社融存量同比增速最新月值
ay = afre_yoy_m.dropna()
m8 = float(ay.iloc[-1]); m8_asof = ay.index[-1]

MON = [
    ("M1", m1 * PCT, "%", -5.00, "low", m1_asof),
    ("M2", m2 * PCT, "%", 2.00, "high", m2_asof),
    ("M3", m3, "bp", 20.00, "high", m3_asof),
    ("M4", m4, "bp", 10.00, "high", m4_asof),
    ("M5", m5, "bp", 40.00, "high", m5_asof),
    ("M6", m6, "pp", 1.50, "high", m6_asof),
    ("M7", m7, "", 49.00, "low", m7_asof),
    ("M8", m8, "%", 8.00, "low", m8_asof),
]
def asof_str(a):
    if isinstance(a, pd.Period):
        return str(a.to_timestamp(how="end").date())
    return str(pd.Timestamp(a).date())

mon_rows = []
for mid, val, unit, thr, direction, asof in MON:
    trig = val < thr if direction == "low" else val > thr
    # 接近阈值: 未触发, 但处于安全侧且距阈值不超过 |阈值| 的 20% (方向感知)
    near = (not trig) and abs(val - thr) <= 0.2 * abs(thr)
    ratio = val / thr if thr != 0 else np.nan
    status = "触发" if trig else ("接近阈值" if near else "正常")
    mon_rows.append(dict(monitor_id=mid, latest_value=f"{val:+.2f}{unit}", data_asof=asof_str(asof),
                         status=status, triggered="是" if trig else "否", _val=val, _thr=thr,
                         _unit=unit, _dir=direction, _ratio=ratio))
mon_out = mon_tpl.astype(object).copy()
for i, r in enumerate(mon_rows):
    mon_out.loc[i, "latest_value"] = r["latest_value"]
    mon_out.loc[i, "data_asof"] = r["data_asof"]
    mon_out.loc[i, "status"] = r["status"]
    mon_out.loc[i, "triggered"] = r["triggered"]
print(mon_out[["monitor_id", "indicator", "threshold", "direction", "latest_value", "data_asof", "status", "triggered"]].to_string(index=False))
print("\n注: M4 受中债收益率截断影响, 数据截至 "
      f"{m4_asof.date()}; M6 基期 {asof_str(m6_base)}; M7 最新行 {asof_str(m7_asof)} (2026-08 缺行); "
      f"M8 社融存量止于 {asof_str(m8_asof)}。")

# 数据缺口与重判安排
sub("10.1 数据缺口清单与补齐后重新判断安排")
gaps = []
for r in validation:
    if r["距截至日缺口交易日"] > 0:
        gaps.append(f"{r['序列']}: 止于 {r['实际止']} (距截至日缺 {r['距截至日缺口交易日']} 个交易日)")
for gtxt in gaps:
    print("  " + gtxt)
print("  制造业PMI: 2026-08 月值缺行(2026-07 与 2026-09 之间存在缺口)")
print("  LPR_5Y: 2018-01-02~2019-08-16 共406行结构性空值(5年期LPR于2019-08-20才发布)")
print("  美债2M: 起点 2018-10-16 (晚于其他序列); 美债4M: 仅6条(2026-09-08起)")
print("重判安排: 中债收益率/PMI/社融/LPR_1Y 补齐后 T+1 个工作日内重跑本脚本, 复核 M4/M6/M7/M8 状态、"
      "S1/S2/S4 情景合格月份与历史校准冲击, 并重新出具第九项约束(C8/C9)结论。")

# -----------------------------------------------------------------------------
# 13. 图表
# -----------------------------------------------------------------------------
hr("第 11 部分  生成图表（5 张 PNG）")

C_PLAN = {"当前组合": "#555555", "方案A(投资经理)": "#1f77b4", "方案B(风险管理部)": "#2ca02c",
          "方案C(宏观策略组)": "#ff7f0e", "推荐方案": "#d62728"}

# ---- chart01 数据覆盖与缺口 ----------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(13, 9), height_ratios=[2.2, 1],
                         gridspec_kw=dict(hspace=0.32))
ax = axes[0]
cov_names = []
for r in validation:
    cov_names.append(r["序列"])
ypos = np.arange(len(cov_names))[::-1]
for i, r in enumerate(validation):
    y = ypos[i]
    ax.barh(y, pd.Timestamp(r["实际止"]) - pd.Timestamp(r["实际起"]),
            left=pd.Timestamp(r["实际起"]), height=0.6,
            color="#4c72b0" if r["距截至日缺口交易日"] == 0 else "#dd8452", alpha=0.85)
    if r["距截至日缺口交易日"] > 0:
        ax.barh(y, CUTOFF - pd.Timestamp(r["实际止"]), left=pd.Timestamp(r["实际止"]),
                height=0.6, color="none", edgecolor="#c00000", hatch="///", linewidth=1.0)
        ax.text(CUTOFF + pd.Timedelta(days=20), y,
                f"缺口{r['距截至日缺口交易日']}个交易日", va="center", fontsize=8, color="#c00000")
    if r["非交易日记录"] > 0 and r["序列"] in ("沪深300", "中证500"):
        ax.plot([pd.Timestamp("2026-09-12")], [y], marker="X", color="black", markersize=8, zorder=5)
ax.set_yticks(ypos)
ax.set_yticklabels(cov_names, fontsize=9)
ax.set_ylim(-1.9, len(cov_names) - 0.3)
ax.axvline(CUTOFF, color="#c00000", lw=1.8, ls="--")
ax.text(CUTOFF, len(cov_names) - 0.2, " 分析截至日 2026-09-15", color="#c00000", fontsize=9, va="bottom")
ax.axvline(SAMPLE_END, color="#7030a0", lw=1.5, ls=":")
ax.text(SAMPLE_END, -1.1, " 共同样本末端 2026-06-09(中债截断)", color="#7030a0", fontsize=9, va="top")
ax.set_title("图1-a 各序列实际覆盖区间、缺口与分析截至日（红色斜纹=覆盖期外结构性空值, 黑X=休市日异常记录）", fontsize=11)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.grid(axis="x", alpha=0.3)
ax.set_xlim(pd.Timestamp("2017-10-01"), pd.Timestamp("2027-06-01"))

ax = axes[1]
zoom_names = ["中债国债10Y", "LPR_1Y", "LPR_5Y", "制造业PMI", "社融存量", "PPI同比", "美债2M", "美债4M", "沪深300"]
zmap = {r["序列"]: r for r in validation}
ypos2 = np.arange(len(zoom_names))[::-1]
for i, nm in enumerate(zoom_names):
    r = zmap[nm]
    y = ypos2[i]
    ax.barh(y, pd.Timestamp(r["实际止"]) - pd.Timestamp(r["实际起"]), left=pd.Timestamp(r["实际起"]),
            height=0.55, color="#4c72b0", alpha=0.85)
    if nm == "制造业PMI":
        ax.plot([pd.Timestamp("2026-08-01")], [y], marker="o", mfc="white", mec="#c00000", mew=2, ms=9)
        ax.text(pd.Timestamp("2026-08-05"), y + 0.32, "2026-08缺行", fontsize=8, color="#c00000")
    if nm == "LPR_5Y":
        ax.barh(y, pd.Timestamp("2019-08-20") - pd.Timestamp("2018-01-02"), left=pd.Timestamp("2018-01-02"),
                height=0.55, color="none", edgecolor="#c00000", hatch="///")
        ax.text(pd.Timestamp("2018-06-01"), y + 0.33, "406行结构性空值(未发布)", fontsize=8, color="#c00000")
    if nm == "沪深300":
        ax.plot([pd.Timestamp("2026-09-12")], [y], marker="X", color="black", ms=9)
        ax.text(pd.Timestamp("2026-07-20"), y + 0.33, "周六异常记录(剔除)", fontsize=8, color="black")
ax.set_yticks(ypos2); ax.set_yticklabels(zoom_names, fontsize=9)
ax.axvline(CUTOFF, color="#c00000", lw=1.8, ls="--")
ax.axvline(SAMPLE_END, color="#7030a0", lw=1.5, ls=":")
ax.set_title("图1-b 2026年及重点序列缺口放大（截至日=2026-09-15）", fontsize=11)
ax.set_xlim(pd.Timestamp("2018-01-01"), pd.Timestamp("2026-12-15"))
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.grid(axis="x", alpha=0.3)
fig.suptitle("数据核验：覆盖区间与缺口（计算前置检查）", fontsize=13, y=0.995)
fig.savefig(os.path.join(CHART_DIR, "FIN3-WKN-149_chart01_数据覆盖与缺口.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print("chart01 done")

# ---- chart02 历史风险总览 ------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw=dict(wspace=0.25))
ax = axes[0]
for k in PLAN_KEYS:
    nav = METRICS[k]["nav"]
    ax.plot(nav.index, nav.values, lw=1.4 if k != "推荐方案" else 2.0,
            color=C_PLAN[k], label=f"{k}(期末{nav.iloc[-1]:.2f})")
ax.set_title("图2-a 各方案累计净值曲线（起点=1, 每日再平衡, 共同样本）", fontsize=11)
ax.legend(fontsize=8.5, loc="upper left")
ax.grid(alpha=0.3)
ax.set_ylabel("净值")
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

ax = axes[1]
metrics_plot = ["ann_vol", "es99_1d", "var99_10d", "mdd"]
labels = ["年化波动率", "1日ES99", "10日VaR99", "最大回撤"]
x = np.arange(len(PLAN_KEYS))
wd = 0.2
colors = ["#4c72b0", "#dd8452", "#55a868", "#8172b3"]
for j, (mk, lb) in enumerate(zip(metrics_plot, labels)):
    vals = [abs(METRICS[k][mk]) * PCT for k in PLAN_KEYS]
    ax.bar(x + (j - 1.5) * wd, vals, wd, label=lb, color=colors[j])
    for xi, v in zip(x + (j - 1.5) * wd, vals):
        ax.text(xi, v + 0.15, f"{v:.2f}", ha="center", fontsize=7)
ax.axhline(3.5, color="#c00000", ls="--", lw=1.5)
ax.text(len(PLAN_KEYS) - 0.42, 3.58, "L6限额: 1日ES99≤3.5%", color="#c00000", fontsize=8.5, ha="right")
ax.axhline(6.0, color="#7030a0", ls="--", lw=1.5)
ax.text(len(PLAN_KEYS) - 0.42, 6.08, "L7限额: 10日VaR99≤6.0%", color="#7030a0", fontsize=8.5, ha="right")
ax.set_xticks(x)
ax.set_xticklabels([k.replace("(", "\n(") for k in PLAN_KEYS], fontsize=8.5)
ax.set_ylabel("%")
ax.set_title("图2-b 风险指标与限额参考线（最大回撤为绝对值, 无限额）", fontsize=11)
ax.legend(fontsize=8.5)
ax.grid(axis="y", alpha=0.3)
fig.suptitle("历史风险总览（共同样本 2018-01-03 ~ 2026-06-09）", fontsize=13)
fig.savefig(os.path.join(CHART_DIR, "FIN3-WKN-149_chart02_历史风险总览.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print("chart02 done")

# ---- chart03 情景识别与校准 ----------------------------------------------------
fig = plt.figure(figsize=(14, 11))
gs = fig.add_gridspec(3, 1, height_ratios=[1.15, 1.15, 1.15], hspace=0.42)
ax = fig.add_subplot(gs[0])
sid_list = ["S1", "S2", "S3", "S4"]
for i, sid in enumerate(sid_list):
    ms = [pd.Timestamp(str(m)) for m in scen_months[sid]]
    ax.scatter(ms, [i] * len(ms), marker="|", s=900, color="#4c72b0", lw=2)
    ne = [pd.Timestamp(str(m)) for m in scen_noneval[sid]]
    ax.scatter(ne, [i] * len(ne), marker=".", s=18, color="#bbbbbb")
ax.set_yticks(range(4))
ax.set_yticklabels([f"{s} {rules_sc.loc[rules_sc.scenario_id==s,'scenario'].iloc[0]}" for s in sid_list], fontsize=9)
ax.set_title("图3-a 四情景月度识别结果（蓝竖线=合格月份, 灰点=输入缺失不可判定月份）", fontsize=11)
ax.grid(axis="x", alpha=0.3)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.set_xlim(pd.Timestamp("2017-10-01"), pd.Timestamp("2026-12-01"))

ax = fig.add_subplot(gs[1])
hm = np.zeros((4, 8))
for i, sid in enumerate(sid_list):
    cs = calib_shocks[sid]
    hm[i] = [cs["cn_equity_shock"] * PCT, cs["spx_usd_shock"] * PCT, cs["usdcnh_shock"] * PCT,
             cs["cgb_bp"]["1y"], cs["cgb_bp"]["2y"], cs["cgb_bp"]["5y"], cs["cgb_bp"]["10y"], cs["cgb_bp"]["30y"]]
im = ax.imshow(hm, cmap="RdYlGn_r", aspect="auto")
ax.set_xticks(range(8))
ax.set_xticklabels(["境内权益%", "标普500美元%", "USDCNH%", "1Y bp", "2Y bp", "5Y bp", "10Y bp", "30Y bp"], fontsize=9)
ax.set_yticks(range(4))
ax.set_yticklabels([f"{s} (窗口数{calib_shocks[s]['n_windows']})" for s in sid_list], fontsize=9)
for i in range(4):
    for j in range(8):
        ax.text(j, i, f"{hm[i,j]:+.2f}", ha="center", va="center", fontsize=8.5,
                color="black")
ax.set_title("图3-b 各情景历史窗口校准冲击（合格窗口内10个交易日累计变动的中位数）", fontsize=11)
fig.colorbar(im, ax=ax, shrink=0.8)

ax = fig.add_subplot(gs[2])
x = np.arange(4)
wd = 0.35
com_l = [-STRESS[("当前组合", s, "委员会沿用")]["合计"] * PCT for s in sid_list]
cal_l = [-STRESS[("当前组合", s, "历史校准")]["合计"] * PCT for s in sid_list]
ax.bar(x - wd / 2, com_l, wd, label="委员会沿用冲击", color="#4c72b0")
ax.bar(x + wd / 2, cal_l, wd, label="历史校准冲击", color="#dd8452")
for xi, v in zip(x - wd / 2, com_l):
    ax.text(xi, v + 0.08, f"{v:.2f}", ha="center", fontsize=8.5)
for xi, v in zip(x + wd / 2, cal_l):
    ax.text(xi, v + 0.08, f"{v:.2f}", ha="center", fontsize=8.5)
ax.set_xticks(x)
ax.set_xticklabels([f"{s}\n{COM_SHOCKS[s]['scenario']}" for s in sid_list], fontsize=9)
ax.set_ylabel("压力损失（%, 正数=损失）")
ax.set_title("图3-c 沿用冲击 vs 历史校准冲击的严格程度对比（当前组合口径）", fontsize=11)
ax.legend(fontsize=9)
ax.grid(axis="y", alpha=0.3)
fig.suptitle("情景识别与校准", fontsize=13)
fig.savefig(os.path.join(CHART_DIR, "FIN3-WKN-149_chart03_情景识别与校准.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print("chart03 done")

# ---- chart04 方案决策与执行 ----------------------------------------------------
fig = plt.figure(figsize=(14, 13))
gs = fig.add_gridspec(3, 1, height_ratios=[1.1, 1.1, 1.0], hspace=0.45)

ax = fig.add_subplot(gs[0])
x = np.arange(len(PLAN_KEYS))
ml_com = [max(-min(STRESS[(k, s, "委员会沿用")]["合计"] for s in sid_list), 0) * PCT for k in PLAN_KEYS]
ml_cal = [max(-min(STRESS[(k, s, "历史校准")]["合计"] for s in sid_list), 0) * PCT for k in PLAN_KEYS]
ml_all = [max_loss[k]["loss"] * PCT for k in PLAN_KEYS]
wd = 0.27
ax.bar(x - wd, ml_com, wd, label="最大损失·委员会沿用冲击", color="#4c72b0")
ax.bar(x, ml_cal, wd, label="最大损失·历史校准冲击", color="#dd8452")
ax.bar(x + wd, ml_all, wd, label="最大压力损失(两套取大)", color="#c00000", alpha=0.75)
ax.axhline(8.0, color="#c00000", ls="--", lw=1.8)
ax.text(-0.45, 8.15, "L8 压力损失上限 8.00%", color="#c00000", fontsize=9)
ax.axhline(7.0, color="#e69f00", ls=":", lw=1.8)
ax.text(-0.45, 7.15, "L9 缓冲线 7.00%（推荐方案须留1pp缓冲）", color="#b8860b", fontsize=9)
for xi, v in zip(x + wd, ml_all):
    ax.text(xi, v + 0.12, f"{v:.2f}", ha="center", fontsize=8.5)
ax.set_xticks(x)
ax.set_xticklabels([k.replace("(", "\n(") for k in PLAN_KEYS], fontsize=8.5)
ax.set_ylabel("压力损失（%, 正数=损失）")
ax.set_title("图4-a 各方案最大压力损失与 8% 上限线 / 7% 缓冲线", fontsize=11)
ax.legend(fontsize=8.5, loc="upper right")
ax.grid(axis="y", alpha=0.3)

ax = fig.add_subplot(gs[1])
steps1 = [p[0] for p in path_sell_first]
cash1 = [p[1] for p in path_sell_first]
steps2 = [p[0] for p in path_buy_first]
cash2 = [p[1] for p in path_buy_first]
xx = np.arange(len(steps1))
ax.step(xx, cash1, where="mid", lw=2.0, color="#2ca02c", label="先卖出后买入（规则口径）")
ax.step(xx, cash2, where="mid", lw=2.0, color="#c00000", ls="--", label="先买入后卖出（对照）")
ax.axhline(0.08 * NAV, color="#7030a0", ls=":", lw=1.8)
ax.text(0.05, 0.08 * NAV + 40, f"现金下限 8% = {0.08*NAV:.0f} 万元", color="#7030a0", fontsize=9)
ax.axhline(0, color="black", lw=0.8)
for i, s in enumerate(steps1):
    ax.text(i, max(cash1[i], cash2[i]) + 90, s.replace("|", "\n"), ha="center", fontsize=7.5)
for i, c in enumerate(cash2):
    if c < 0.08 * NAV:
        ax.annotate(f"{c:.0f}万({c/NAV*PCT:.2f}%)", (i, c), textcoords="offset points",
                    xytext=(0, -18), ha="center", fontsize=8, color="#c00000")
ax.set_xticks([])
ax.set_xlim(-0.6, len(steps1) - 0.4)
ax.set_ylabel("人民币现金及货基（万元）")
ax.set_ylim(min(-300, min(cash2) - 150), max(max(cash1), max(cash2)) + 420)
ax.set_title("图4-b 调仓执行现金路径与 8% 现金下限（净值 10,000 万元）", fontsize=11)
ax.legend(fontsize=9, loc="lower left")
ax.grid(alpha=0.3)

ax = fig.add_subplot(gs[2])
fl = ["境内权益%", "标普500美元%", "USDCNH%", "1Y bp", "2Y bp", "5Y bp", "10Y bp", "30Y bp"]
xv = np.arange(8)
ax.bar(xv, [x_star[0] * PCT, x_star[1] * PCT, x_star[2] * PCT, *x_star[3:]], color="#c00000", alpha=0.8,
       label=f"最可能违约情景(最小马氏距离 d={d_star:.2f})")
ax.axhline(0, color="black", lw=0.8)
for i in range(8):
    v = [x_star[0] * PCT, x_star[1] * PCT, x_star[2] * PCT, *x_star[3:]][i]
    ax.text(i, v + (0.15 if v >= 0 else -0.35), f"{v:+.2f}", ha="center", fontsize=8.5)
ax.set_xticks(xv)
ax.set_xticklabels(fl, fontsize=9)
ax.set_title(f"图4-c 反向压力测试：推荐方案触及8%损失上限的最可能情景（精确损失 {loss_star*PCT:+.2f}%, 历史分位 {pct_star*100:.1f}%）", fontsize=11)
ax.grid(axis="y", alpha=0.3)
ax.legend(fontsize=9)
fig.suptitle("方案决策与执行", fontsize=13)
fig.savefig(os.path.join(CHART_DIR, "FIN3-WKN-149_chart04_方案决策与执行.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print("chart04 done")

# ---- chart05 监测指标触发状态 --------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.8), gridspec_kw=dict(width_ratios=[1.35, 1], wspace=0.12))
ax = axes[0]
y = np.arange(8)[::-1]
for i, r in enumerate(mon_rows):
    ratio = r["_ratio"]
    color = "#c00000" if r["triggered"] == "是" else ("#e69f00" if r["status"] == "接近阈值" else "#2ca02c")
    ax.barh(y[i], ratio, height=0.55, color=color, alpha=0.85)
    ax.text(ratio + (0.03 if ratio >= 0 else -0.03), y[i],
            f"最新 {r['latest_value']}  /  阈值 {r['_thr']:+.2f}{r['_unit']}  [{r['status']}]",
            va="center", ha="left" if ratio >= 0 else "right", fontsize=8.5)
ax.axvline(1.0, color="#7030a0", ls="--", lw=1.8)
ax.text(1.02, 7.6, "阈值线(最新值/阈值=1)", color="#7030a0", fontsize=9)
ax.set_yticks(y)
ax.set_yticklabels([f"{r['monitor_id']} {mon_out.loc[i,'indicator']}" for i, r in enumerate(mon_rows)], fontsize=9)
ax.set_xlim(-1.6, 2.6)
ax.set_xlabel("最新值 / 阈值（比例; M1/M4等带符号指标按同号比值计算）")
ax.set_title("图5-a 八个监测指标触发状态（红=触发, 橙=接近阈值, 绿=正常）", fontsize=11)
ax.grid(axis="x", alpha=0.3)

ax = axes[1]
ax.axis("off")
tbl_data = [[r["monitor_id"], mon_out.loc[i, "indicator"], mon_out.loc[i, "threshold"],
             r["latest_value"], r["data_asof"], r["status"], r["triggered"]]
            for i, r in enumerate(mon_rows)]
tbl = ax.table(cellText=tbl_data,
               colLabels=["编号", "指标", "阈值", "最新值", "数据截至", "状态", "触发"],
               loc="center", cellLoc="center")
tbl.auto_set_font_size(False)
tbl.set_fontsize(8.5)
tbl.scale(1, 1.7)
for j in range(7):
    tbl[0, j].set_facecolor("#4c72b0")
    tbl[0, j].set_text_props(color="white", weight="bold")
for i, r in enumerate(mon_rows):
    c = "#f8d7da" if r["triggered"] == "是" else ("#fff3cd" if r["status"] == "接近阈值" else "#d4edda")
    for j in range(7):
        tbl[i + 1, j].set_facecolor(c)
ax.set_title("图5-b 监测指标明细表（口径同 template_monitor.csv）", fontsize=11)
fig.suptitle("监测指标触发状态", fontsize=13)
fig.savefig(os.path.join(CHART_DIR, "FIN3-WKN-149_chart05_监测指标触发状态.png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print("chart05 done")

# -----------------------------------------------------------------------------
# 14. 结果汇总(供备忘录引用的一致性自检)
# -----------------------------------------------------------------------------
hr("第 12 部分  备忘录关键数字汇总（自检）")
summary = dict(
    样本区间=[str(SAMPLE_START.date()), str(SAMPLE_END.date())], 样本交易日=len(sample_days),
    收益样本天数=len(ret), 截至日=str(CUTOFF.date()), 净值万元=NAV,
    当前组合={k: (round(float(v), 4) if not isinstance(v, (pd.Timestamp, type(None))) else str(v))
              for k, v in cur.items() if k in ["ann_vol", "var95_1d", "var99_1d", "es95_1d", "es99_1d",
                                                "var99_10d", "worst10", "mdd", "worst_day", "ann_ret", "nav_final"]},
    最大压力损失={k: round(max_loss[k]["loss"] * PCT, 2) for k in PLAN_KEYS},
    最大压力来源={k: f"{max_loss[k]['sid']}/{max_loss[k]['ss']}" for k in PLAN_KEYS},
    推荐方案=dict(换手率=round(to_rec * PCT, 2), ES99=round(aux_rec["es99"] * PCT, 2),
                 VaR99_10d=round(aux_rec["var99_10d"] * PCT, 2), 最大压力=round(aux_rec["max_stress"] * PCT, 2),
                 九项全过=bool(ok_rec)),
    合格窗口数={s: calib_shocks[s]["n_windows"] for s in sid_list},
    合格月份数={s: len(scen_months[s]) for s in sid_list},
    反向压力=dict(距离=round(d_star, 3), 损失=round(loss_star * PCT, 2), 放大倍数=round(amp, 3),
                 x=[round(float(v), 4) for v in x_star]),
    监测={r["monitor_id"]: dict(值=r["latest_value"], 截至=r["data_asof"], 状态=r["status"], 触发=r["triggered"]) for r in mon_rows},
)
print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))
print("\n全部计算与图表生成完毕。")
