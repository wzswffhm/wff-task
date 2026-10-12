# -*- coding: utf-8 -*-
"""FIN3-WKN-153 输入材料生成器（出题工具，不进题包）。

场景：券商资管「现金增强 1 号集合资产管理计划」2026Q3 季度投资运作复核。
埋点：
  W03 阻塞 —— valuation/price_feed_20260930.csv 为 0 字节，恢复件在 data/ 下；
  W13 死路 —— rules/recon_runbook.md 指定关联键 wind_code，两个数据文件均无该列；
  W07 长表 —— holdings_2026Q3.xlsx 十个账户 sheet 共 295 行，含重复上报行 /
               期末后失效的上期行 / 主数据已非 active 的证券行。
输出：environment/input_files/ 全部材料 + anchors.json（金标锚点，留工具目录）。
"""
import csv
import json
import random
import shutil
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

SEED = 20261013
PKG = Path(__file__).resolve().parents[2] / "work_fin-b01_20261012-153" / "FIN3-WKN-153"
ROOT = PKG / "environment" / "input_files"
ANCHORS = Path(__file__).resolve().parent / "anchors_153.json"

ASOF = "2026-09-30"
PREV_ASOF = "2026-06-30"
PRICE_DATE = "2026-09-30"
OLD_PRICE_DATE = "2026-09-29"
SHARES = 1_250_000_000.0
CASH_RATIO = 0.034
MAX_RATIO_TARGET = 0.1042
NONSTD_RATIO_TARGET = 0.045

RECEIVABLES = [("interest_receivable", 3_412_800.00), ("dividend_receivable", 865_400.00)]
PAYABLES = [("fee_payable_admin", 1_842_300.00),
            ("fee_payable_custodian", 614_100.00),
            ("fee_payable_sales", 307_050.00)]


def unit_price(sec, prices) -> float:
    """每单位 vol（面值/份额/本金）对应的市值：权益基金 = 份额 × 净值；
    债券与非标按每百元报价折算 = 报价 / 100（非标报价恒为 100）。"""
    p = prices[sec["sec_code"]]
    return p if sec["sec_type"] == "EquityFund" else p / 100.0


# 账户 -> (名称, 券种池, 目标规模占总资产比例)
ACCOUNTS = [
    ("acct_01", "利率债账户", ["GovtBond", "PolicyBankBond"], 0.155),
    ("acct_02", "政策性金融债与存单账户", ["PolicyBankBond", "InterbankCD"], 0.115),
    ("acct_03", "信用债账户一", ["CreditBond"], 0.135),
    ("acct_04", "信用债账户二", ["CreditBond"], 0.125),
    ("acct_05", "同业存单账户", ["InterbankCD"], 0.085),
    ("acct_06", "权益基金账户", ["EquityFund"], 0.075),
    ("acct_07", "可转债账户", ["ConvertBond"], 0.050),
    ("acct_08", "非标专户", ["NonStdAsset"], 0.045),
    ("acct_09", "混合策略账户", ["CreditBond", "ConvertBond", "EquityFund"], 0.100),
    ("acct_10", "现金增强账户", ["PolicyBankBond", "InterbankCD", "CreditBond"], 0.081),
]
ACCOUNT_ROWS = {"acct_01": 40, "acct_02": 34, "acct_03": 36, "acct_04": 32,
                "acct_05": 26, "acct_06": 22, "acct_07": 24, "acct_08": 4,
                "acct_09": 30, "acct_10": 32}

TYPE_NAMES = {
    "GovtBond": "国债", "PolicyBankBond": "政策性金融债", "CreditBond": "中期票据",
    "InterbankCD": "同业存单", "EquityFund": "权益型指数基金", "ConvertBond": "可转换债",
    "NonStdAsset": "资产支持专项计划",
}
ISSUERS = {
    "GovtBond": ["中华人民共和国财政部"],
    "PolicyBankBond": ["国家开发银行", "中国农业发展银行", "中国进出口银行"],
    "CreditBond": ["华骏集团", "瑞泽控股", "中盛建设", "金岭能源", "南方水务",
                   "鸿基材料", "永泰化工", "临港物流", "云港科技", "宏图置业"],
    "InterbankCD": ["兴业银行", "招商银行", "浦发银行", "中信银行", "民生银行"],
    "EquityFund": ["华泰柏瑞基金", "易方达基金", "南方基金", "天弘基金"],
    "ConvertBond": ["旭光电子", "恒通装备", "新材科技", "联创医疗"],
    "NonStdAsset": ["汇远保理", "鼎信供应链", "中泉物业", "越秀租赁"],
}


def code_for(sec_type: str, seq: int) -> str:
    return {
        "GovtBond": f"25{seq:04d}.IB",
        "PolicyBankBond": f"26{seq:04d}.IB",
        "CreditBond": f"1026{seq:05d}.IB",
        "InterbankCD": f"1126{seq:04d}.SH",
        "EquityFund": f"51{seq:04d}.SH",
        "ConvertBond": f"113{seq:04d}.SH",
        "NonStdAsset": f"ZQ26{seq:04d}",
    }[sec_type]


def build_master(rng: random.Random):
    """生成证券主数据，返回 list[dict]。"""
    plan = [("GovtBond", 16), ("PolicyBankBond", 24), ("CreditBond", 44),
            ("InterbankCD", 14), ("EquityFund", 12), ("ConvertBond", 12),
            ("NonStdAsset", 4)]
    secs, seq = [], {k: 1 for k, _ in plan}
    for sec_type, n in plan:
        issuers = [i for i in ISSUERS[sec_type] if i != "Volt_placeholder"]
        for k in range(n):
            code = code_for(sec_type, seq[sec_type])
            seq[sec_type] += 1
            if sec_type == "CreditBond":
                issuer = issuers[0] if k < 3 else issuers[(k - 3) % (len(issuers) - 1) + 1]
            else:
                issuer = issuers[k % len(issuers)]
            secs.append({
                "sec_code": code,
                "sec_name": f"{issuer}{2026 if sec_type != 'GovtBond' else 25}年第{k + 1}期{TYPE_NAMES[sec_type]}",
                "sec_type": sec_type,
                "issuer": issuer,
                "status": "active",
                "listed_date": "2026-03-16" if k % 2 == 0 else "2026-05-20",
                "maturity_date": "2029-09-15" if sec_type in ("CreditBond", "PolicyBankBond")
                                 else ("2027-03-18" if sec_type == "InterbankCD" else "2036-03-18"),
            })
    # 6 只非 active（已到期/已赎回），各类型分布
    inactive_targets = [("CreditBond", 2), ("InterbankCD", 2), ("PolicyBankBond", 1), ("ConvertBond", 1)]
    used = set()
    for sec_type, n in inactive_targets:
        cands = [s for s in secs if s["sec_type"] == sec_type and s["sec_code"] not in used][:n]
        for s in cands:
            s["status"] = "matured" if sec_type in ("CreditBond", "InterbankCD") else "called"
            s["maturity_date"] = "2026-09-12" if s["status"] == "matured" else "2026-09-18"
            used.add(s["sec_code"])
    return secs


def build_prices(rng: random.Random, secs):
    prices, old_rows = {}, []
    for s in secs:
        t = s["sec_type"]
        if t in ("GovtBond", "PolicyBankBond"):
            p = round(rng.uniform(96.80, 104.60), 3)
        elif t == "CreditBond":
            p = round(rng.uniform(97.50, 103.80), 3)
        elif t == "InterbankCD":
            p = round(rng.uniform(99.30, 100.20), 4)
        elif t == "EquityFund":
            p = round(rng.uniform(1.0500, 3.8500), 4)
        elif t == "ConvertBond":
            p = round(rng.uniform(104.00, 138.00), 3)
        else:  # 非标按摊余成本计价
            p = 100.0000
        prices[s["sec_code"]] = p
    return prices


def gen_holdings(rng: random.Random, secs, prices):
    """生成十个账户 sheet 的持仓行（含 4 重复 / 6 上期 / 5 非 active 干扰）。"""
    by_type = {}
    for s in secs:
        by_type.setdefault(s["sec_type"], []).append(s)

    active = [s for s in secs if s["status"] == "active"]
    inactive = [s for s in secs if s["status"] != "active"]
    max_sec = next(s for s in active if s["sec_type"] == "CreditBond" and s["issuer"] == "华骏集团")
    huajun_two = [s for s in active if s["issuer"] == "华骏集团" and s["sec_code"] != max_sec["sec_code"]][:2]

    # 各账户行的券（保证账户内不重复）
    picked = {}
    for acct, _name, pool, _target in ACCOUNTS:
        n = ACCOUNT_ROWS[acct]
        cands = []
        for t in pool:
            cands.extend([s for s in by_type[t] if s["status"] == "active"])
        seen, rows = set(), []
        # 强制持仓
        if acct == "acct_03":
            rows.append(max_sec)
            seen.add(max_sec["sec_code"])
        if acct == "acct_04":
            for s in huajun_two:
                rows.append(s)
                seen.add(s["sec_code"])
        rng.shuffle(cands)
        for s in cands:
            if len(rows) >= n:
                break
            if s["sec_code"] in seen:
                continue
            rows.append(s)
            seen.add(s["sec_code"])
        # 池不足时允许跨账户复用（同一券可在多账户持有）：从 active 全集补齐
        if len(rows) < n:
            pool_all = list(active)
            rng.shuffle(pool_all)
            for s in pool_all:
                if len(rows) >= n:
                    break
                if s["sec_code"] not in seen:
                    rows.append(s)
                    seen.add(s["sec_code"])
        picked[acct] = rows

    # --- 第一步：按账户目标规模随机分配权重 ---
    T_guess = 1.35e9
    holdings = []  # [acct, sec, vol]
    for acct, _name, _pool, target in ACCOUNTS:
        rows = picked[acct]
        n = len(rows)
        if acct == "acct_03":
            rest_target = target - MAX_RATIO_TARGET
            w = [rng.random() for _ in range(n - 1)]
            tot = sum(w)
            vols = [MAX_RATIO_TARGET * T_guess / unit_price(max_sec, prices)]
            vols += [rest_target * T_guess * x / tot / unit_price(s, prices)
                     for s, x in zip(rows[1:], w)]
        elif acct == "acct_04":
            # 两只华骏债合计 2.4%，其余 10.1%
            fixed = 0.024 * T_guess
            rest_target = target - 0.024
            w = [rng.random() for _ in range(n - 2)]
            tot = sum(w)
            vols = [fixed / 2 / unit_price(rows[0], prices),
                    fixed / 2 / unit_price(rows[1], prices)]
            vols += [rest_target * T_guess * x / tot / unit_price(s, prices)
                     for s, x in zip(rows[2:], w)]
        else:
            w = [rng.random() for _ in range(n)]
            tot = sum(w)
            vols = [target * T_guess * x / tot / unit_price(s, prices) for s, x in zip(rows, w)]
        for s, v in zip(rows, vols):
            holdings.append([acct, s, v])

    # --- 第二步：迭代解出与总资产自洽的规模、现金、集中度、非标占比 ---
    A = sum(v for _, v in RECEIVABLES)
    P = sum(v for _, v in PAYABLES)
    S = sum(v * unit_price(s, prices) for _a, s, v in holdings)
    for _ in range(12):
        T = (S + A - P) / (1 - CASH_RATIO)
        ns_mv = sum(v * unit_price(s, prices) for _a, s, v in holdings
                    if s["sec_type"] == "NonStdAsset")
        scale_ns = (NONSTD_RATIO_TARGET * T) / ns_mv if ns_mv else 1.0
        holdings = [[a, s, v * (scale_ns if s["sec_type"] == "NonStdAsset" else 1.0)]
                    for a, s, v in holdings]
        cur_max_mv = next(v * unit_price(s, prices) for _a, s, v in holdings
                          if s["sec_code"] == max_sec["sec_code"])
        scale_max = (MAX_RATIO_TARGET * T) / cur_max_mv
        holdings = [[a, s, v * (scale_max if s["sec_code"] == max_sec["sec_code"] else 1.0)]
                    for a, s, v in holdings]
        S = sum(v * unit_price(s, prices) for _a, s, v in holdings)

    # --- 第三步：vol 取整（面值/份额按 10000 取整）后微调主力券 ---
    holdings = [[a, s, max(10000.0, round(v / 10000.0) * 10000.0)] for a, s, v in holdings]
    S = sum(v * unit_price(s, prices) for _a, s, v in holdings)

    # --- 第四步：构造三类干扰行 ---
    lines = []  # dict(acct, sec, vol, as_of, updated_at, src)
    seq_by_acct = {a: 1 for a, *_ in ACCOUNTS}
    for acct, sec, vol in holdings:
        seq = seq_by_acct[acct]
        seq_by_acct[acct] += 1
        lines.append({"acct": acct, "sec": sec, "vol": vol, "as_of": ASOF,
                      "updated": "2026-10-03 18:20", "src": f"SRC-{acct}-{seq:04d}"})

    # 4 行重复上报（除 source_row_id 外完全相同）
    dup_idx = []
    for target_acct in ("acct_01", "acct_03", "acct_06", "acct_10"):
        cands = [i for i, l in enumerate(lines) if l["acct"] == target_acct]
        dup_idx.append(cands[len(cands) // 3])
    for i in dup_idx:
        src = lines[i]
        dup = dict(src)
        seq_by_acct[src["acct"]] += 1
        dup["src"] = f"SRC-{src['acct']}-{seq_by_acct[src['acct']]:04d}"
        lines.append(dup)

    # 6 行上期残留（同券同账户、as_of=2026-06-30、vol 为上期值）
    stale_idx = []
    for target_acct in ("acct_02", "acct_04", "acct_05", "acct_07", "acct_09", "acct_10"):
        cands = [i for i, l in enumerate(lines)
                 if l["acct"] == target_acct and l["as_of"] == ASOF]
        stale_idx.append(cands[len(cands) // 2])
    for k, i in enumerate(stale_idx):
        src = lines[i]
        st = dict(src)
        seq_by_acct[src["acct"]] += 1
        st["as_of"] = PREV_ASOF
        st["updated"] = "2026-07-03 09:45"
        st["src"] = f"SRC-{src['acct']}-{seq_by_acct[src['acct']]:04d}"
        st["vol"] = round(src["vol"] * (0.96 + 0.01 * k) / 10000.0) * 10000.0
        lines.append(st)

    # 5 行主数据已非 active 的证券
    inactive_picked = inactive[:5]
    for k, sec in enumerate(inactive_picked):
        acct = ACCOUNTS[k % len(ACCOUNTS)][0]
        seq_by_acct[acct] += 1
        lines.append({"acct": acct, "sec": sec, "vol": float((3 + k) * 1_000_000),
                      "as_of": ASOF, "updated": "2026-10-03 18:20",
                      "src": f"SRC-{acct}-{seq_by_acct[acct]:04d}"})

    # 打乱 sheet 内顺序
    by_acct = {a: [] for a, *_ in ACCOUNTS}
    for l in lines:
        by_acct[l["acct"]].append(l)
    for a in by_acct:
        rng.shuffle(by_acct[a])
    return by_acct, max_sec


def write_holdings(by_acct, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)
    bold = Font(bold=True)
    # 说明页
    ws = wb.create_sheet("readme")
    for r in [["计划全称", "现金增强 1 号集合资产管理计划"],
              ["报告期末", ASOF],
              ["数据来源", "托管行 TA 与管理人交易系统盘后导出"],
              ["字段说明", "acct=资金账户; sec_code=证券编码; vol=期末持仓数量(面值/份额); "
                           "as_of=数据所属日期; updated_at=导出时间; source_row_id=导出行编号"],
              ["注意事项", "同一账户同一证券可能因多次盘后导出形成多行，以 source_row_id 为准"]]:
        ws.append(r)
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 96
    ws["A1"].font = bold
    for i in range(1, 6):
        ws.cell(row=i, column=1).font = bold

    for acct, rows in by_acct.items():
        ws = wb.create_sheet(acct)
        head = ["acct", "sec_code", "sec_name", "sec_type", "vol", "as_of", "updated_at", "source_row_id"]
        ws.append(head)
        for c in range(1, len(head) + 1):
            cell = ws.cell(row=1, column=c)
            cell.font = bold
            cell.alignment = Alignment(horizontal="center")
        for l in rows:
            s = l["sec"]
            ws.append([l["acct"], s["sec_code"], s["sec_name"], s["sec_type"],
                       l["vol"], l["as_of"], l["updated"], l["src"]])
        widths = [10, 16, 42, 16, 16, 12, 20, 18]
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w
        ws.freeze_panes = "A2"
    # 干扰页（无持仓数据）
    ws = wb.create_sheet("q2_roll")
    ws.append(["上季度滚动表已于 2026-07-10 归档，本表仅保留历史链接，不作为期末持仓依据"])
    ws = wb.create_sheet("contact")
    ws.append(["对接人", "岗位", "邮箱（内网）"])
    ws.append(["运营支持组", "估值核算岗", "ops-valuation@internal"])
    ws.append(["组合管理部", "投资经理", "pm-cashplus@internal"])
    wb.save(path)


def write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def main():
    rng = random.Random(SEED)
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True, exist_ok=True)

    secs = build_master(rng)
    prices = build_prices(rng, secs)
    by_acct, max_sec = gen_holdings(rng, secs, prices)

    A = sum(v for _, v in RECEIVABLES)
    P = sum(v for _, v in PAYABLES)

    status = {s["sec_code"]: s for s in secs}

    # ---------- 口径重算（与金标一致的定义） ----------
    all_rows, dup_rows, stale_rows, inactive_rows, valid_rows = [], [], [], [], []
    seen_keys = set()
    for acct, rows in by_acct.items():
        for l in rows:
            all_rows.append(l)
            key = (l["acct"], l["sec"]["sec_code"], l["vol"], l["as_of"], l["src"][:0] or "")
            if l["as_of"] != ASOF:
                stale_rows.append(l)
            elif status[l["sec"]["sec_code"]]["status"] != "active":
                inactive_rows.append(l)
            else:
                dedup_key = (l["acct"], l["sec"]["sec_code"], l["vol"], l["as_of"])
                if dedup_key in seen_keys:
                    dup_rows.append(l)
                else:
                    seen_keys.add(dedup_key)
                    valid_rows.append(l)

    def mv(rows):
        return sum(l["vol"] * unit_price(l["sec"], prices) for l in rows)

    S = mv(valid_rows)
    S_naive = mv(all_rows)
    dup_mv, stale_mv, inactive_mv = mv(dup_rows), mv(stale_rows), mv(inactive_rows)

    T = (S + A - P) / (1 - CASH_RATIO)
    cash = round(T * CASH_RATIO, 2)
    T = S + cash + A - P
    unit = round(T / SHARES, 4)
    naive_T = S_naive + cash + A - P
    naive_unit = round(naive_T / SHARES, 4)

    max_row = next(l for l in valid_rows if l["sec"]["sec_code"] == max_sec["sec_code"])
    max_mv = max_row["vol"] * unit_price(max_sec, prices)
    max_ratio = max_mv / T

    huajun_mv = sum(l["vol"] * unit_price(l["sec"], prices) for l in valid_rows
                    if status[l["sec"]["sec_code"]]["issuer"] == "华骏集团")
    nonstd_mv = sum(l["vol"] * unit_price(l["sec"], prices) for l in valid_rows
                    if l["sec"]["sec_type"] == "NonStdAsset")
    equity_mv = sum(l["vol"] * unit_price(l["sec"], prices) for l in valid_rows
                    if l["sec"]["sec_type"] == "EquityFund")
    type_mv = {}
    for l in valid_rows:
        t = l["sec"]["sec_type"]
        type_mv[t] = type_mv.get(t, 0.0) + l["vol"] * unit_price(l["sec"], prices)

    # 0929 旧价行涉及的证券（在有效持仓中挑 5 只不同证券）
    old_price_secs = []
    for l in valid_rows:
        s = l["sec"]
        if s["sec_code"] not in {x["sec_code"] for x in old_price_secs}:
            old_price_secs.append(s)
        if len(old_price_secs) >= 5:
            break

    anchors = {
        "files_total": None,  # 下面统计
        "rows": {"total": len(all_rows), "dup": len(dup_rows), "stale": len(stale_rows),
                 "inactive": len(inactive_rows), "valid": len(valid_rows)},
        "per_sheet": {a: len(v) for a, v in by_acct.items()},
        "mv": {"valid": round(S, 2), "naive": round(S_naive, 2), "dup": round(dup_mv, 2),
               "stale": round(stale_mv, 2), "inactive": round(inactive_mv, 2),
               "diff": round(S_naive - S, 2)},
        "T": round(T, 2), "cash": cash, "unit_nav": unit, "naive_unit_nav": naive_unit,
        "nav_diff_bp": round((naive_unit - unit) / unit * 10000, 2),
        "shares": SHARES,
        "max_sec": {"code": max_sec["sec_code"], "name": max_sec["sec_name"],
                    "issuer": max_sec["issuer"], "mv": round(max_mv, 2),
                    "ratio_pct": round(max_ratio * 100, 4)},
        "huajun_ratio_pct": round(huajun_mv / T * 100, 4),
        "nonstd_ratio_pct": round(nonstd_mv / T * 100, 4),
        "equity_ratio_pct": round(equity_mv / T * 100, 4),
        "cash_ratio_pct": round(cash / T * 100, 4),
        "type_mv": {k: round(v, 2) for k, v in sorted(type_mv.items())},
        "prices": {s["sec_code"]: prices.get(s["sec_code"]) for s in secs},
        "old_price_codes": [s["sec_code"] for s in old_price_secs],
        "max_price_date": PRICE_DATE,
    }

    # ---------------- 写材料 ----------------
    # 持仓
    write_holdings(by_acct, ROOT / "portfolio" / "holdings_2026Q3.xlsx")
    write_csv(ROOT / "portfolio" / "security_master.csv",
              ["sec_code", "sec_name", "sec_type", "issuer", "status", "listed_date", "maturity_date"],
              [[s["sec_code"], s["sec_name"], s["sec_type"], s["issuer"], s["status"],
                s["listed_date"], s["maturity_date"]] for s in secs])

    # 价格：正常件 0 字节；重推件含 0930 全量 + 5 行 0929 旧行
    (ROOT / "valuation" / "price_feed_20260930.csv").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "valuation" / "price_feed_20260930.csv").write_bytes(b"")
    price_rows = []
    for s in secs:
        price_rows.append([s["sec_code"], PRICE_DATE, f"{prices[s['sec_code']]:.4f}", "收盘价", "重推件"])
    for s in old_price_secs:
        price_rows.append([s["sec_code"], OLD_PRICE_DATE,
                           f"{prices[s['sec_code']] * 0.9973:.4f}", "收盘价", "原始推送"])
    write_csv(ROOT / "data" / "price_feed_20260930_repush.csv",
              ["instrument_id", "trade_date", "close_price", "price_type", "batch_tag"], price_rows)

    # 净值报告 / 计提 / 银行对账
    write_csv(ROOT / "valuation" / "nav_report_20260930.csv",
              ["item", "item_name", "value", "source"],
              [["report_date", "报告期末", ASOF, "托管行"],
               ["fund_name", "计划名称", "现金增强 1 号集合资产管理计划", "托管行"],
               ["total_shares", "计划总份额", f"{SHARES:.2f}", "托管行"],
               ["total_nav", "计划资产净值", f"{T:.2f}", "托管行"],
               ["nav_per_share", "单位净值", f"{unit:.4f}", "托管行"],
               ["cash_and_equivalent", "现金及清算备付金", f"{cash:.2f}", "托管行"]])
    accr_names = {"interest_receivable": "应收利息", "dividend_receivable": "应收红利",
                  "fee_payable_admin": "应付管理人报酬", "fee_payable_custodian": "应付托管费",
                  "fee_payable_sales": "应付销售服务费"}
    write_csv(ROOT / "valuation" / "accruals_20260930.csv",
              ["item", "item_name", "amount", "accrual_period"],
              [[k, accr_names[k], f"{v:.2f}", "2026-07-01~2026-09-30"]
               for k, v in RECEIVABLES + PAYABLES])
    bank_cash = round(cash * 0.72, 2)
    write_csv(ROOT / "valuation" / "bank_statement_20260930.csv",
              ["account", "account_name", "balance", "as_of"],
              [["6220****1188", "托管存款专户", f"{bank_cash:.2f}", ASOF],
               ["6220****2299", "清算备付金账户", f"{cash - bank_cash:.2f}", ASOF]])

    # 基准
    bench = {"GovtBond": 0.18, "PolicyBankBond": 0.22, "CreditBond": 0.30,
             "InterbankCD": 0.12, "EquityFund": 0.10, "ConvertBond": 0.05, "NonStdAsset": 0.03}
    write_csv(ROOT / "data" / "benchmark_weights_2026Q3.csv",
              ["sec_type", "sec_type_name", "benchmark_weight"],
              [[k, TYPE_NAMES[k], f"{v:.4f}"] for k, v in bench.items()])
    write_csv(ROOT / "data" / "benchmark_returns_2026Q3.csv",
              ["benchmark", "period", "return"],
              [["中债-综合财富指数", "2026Q3", "0.0087"],
               ["沪深 300 全收益", "2026Q3", "0.0231"],
               ["计划业绩比较基准", "2026Q3", "0.0116"]])

    # 规则
    write_text(ROOT / "rules" / "restrictions_v3_20260901.md", RULES_V3)
    write_text(ROOT / "rules" / "restrictions_v2_20260601.md", RULES_V2)
    write_text(ROOT / "rules" / "recon_runbook.md", RUNBOOK)
    write_text(ROOT / "rules" / "liquidity_policy.md", LIQ_POLICY)
    # 报告
    write_text(ROOT / "reports" / "2026Q2_operation_report.md", Q2_REPORT)
    write_text(ROOT / "reports" / "2026Q1_operation_report.md", Q1_REPORT)
    write_text(ROOT / "reports" / "report_template.md", TEMPLATE)
    # 合规
    write_csv(ROOT / "compliance" / "limit_monitor_2026Q2.csv",
              ["check_date", "rule_id", "rule_name", "measured_value", "limit_value", "result"],
              [["2026-06-30", "R-01", "单一证券集中度上限", "0.0987", "0.1200", "PASS"],
               ["2026-06-30", "R-03", "非标资产比例上限", "0.0412", "0.0800", "PASS"],
               ["2026-06-30", "R-05", "现金类资产比例下限", "0.0286", "0.0200", "PASS"]])
    write_csv(ROOT / "compliance" / "breach_log_2026.csv",
              ["breach_id", "breach_date", "rule_id", "description", "status", "cure_deadline"],
              [["BR-2026-004", "2026-06-17", "R-02", "单一发行人集中度盘中触及 15% 预警线", "已解除", "2026-06-24"],
               ["BR-2026-005", "2026-08-11", "R-06", "逆回购剩余期限超过内部限额 1 天", "已解除", "2026-08-14"]])
    write_text(ROOT / "compliance" / "review_checklist.md", CHECKLIST)
    # internal
    write_text(ROOT / "internal" / "data_dictionary.md", DICT)
    write_text(ROOT / "internal" / "ops_email_20261008.txt", OPS_MAIL)
    write_text(ROOT / "internal" / "manager_notes.md", MGR_NOTES)
    write_text(ROOT / "internal" / "approval_memo_20260928.md", APPROVAL)
    # 根
    write_text(ROOT / "00_README.md", README)
    write_csv(ROOT / "manifest.csv", ["path", "category", "purpose"],
              [["portfolio/", "持仓", "期末持仓明细与证券主数据"],
               ["valuation/", "估值", "净值报告、计提明细、银行对账单"],
               ["data/", "行情", "行情与基准数据"],
               ["rules/", "制度", "投资限制、对账流程与流动性制度（以现行版本为准）"],
               ["reports/", "报告", "历史期间投资运作报告与模板"],
               ["compliance/", "合规", "限额监测与违约记录"],
               ["internal/", "内部", "数据字典、运营邮件、投资经理说明与决策纪要"]])

    files = [p for p in ROOT.rglob("*") if p.is_file()]
    anchors["files_total"] = len(files)
    anchors["dirs"] = sorted({str(p.parent.relative_to(ROOT)) for p in files})
    ANCHORS.write_text(json.dumps(anchors, ensure_ascii=False, indent=2), encoding="utf-8")
    print("files:", len(files))
    print(json.dumps({k: anchors[k] for k in
                      ("rows", "mv", "T", "unit_nav", "naive_unit_nav", "nav_diff_bp",
                       "max_sec", "huajun_ratio_pct", "nonstd_ratio_pct",
                       "equity_ratio_pct", "cash_ratio_pct", "files_total")},
                     ensure_ascii=False, indent=2))


README = """# 现金增强 1 号集合资产管理计划 — 2026 年三季度投资运作复核材料

- 计划全称：现金增强 1 号集合资产管理计划（券商资管集合类，母牌照编号见合同附件，本材料包不复制）。
- 报告期末：**2026-09-30**；材料包整理日：2026-10-08。
- 使用范围：季度投资运作报告编制、季度投资监督复核与合规留痕。

## 目录用途

| 目录 | 用途 |
| --- | --- |
| `portfolio/` | 期末持仓明细（十个资金账户）与证券主数据 |
| `valuation/` | 托管行净值报告、应收应付计提明细、银行对账单 |
| `data/` | 收盘行情、业绩比较基准权重与基准收益率 |
| `rules/` | 投资限制条款、对账操作指引、流动性管理制度 |
| `reports/` | 历史期间投资运作报告与本期报告模板 |
| `compliance/` | 限额监测记录、触发记录与复核清单 |
| `internal/` | 数据字典、运营邮件、投资经理说明、投资决策纪要 |

`manifest.csv` 给出各目录的用途；`rules/recon_runbook.md` 为运营侧期末对账与口径流程。

## 口径与优先级

1. 投资限制条款以 `rules/` 下**现行有效版本**为准，历史版本仅用于回溯说明。
2. 净值、份额、现金类资产以托管行报告为准；持仓明细以管理人交易系统盘后导出为准，
   两者不一致时须查明并留痕。
3. 行情以数据组当日收盘后推送的文件为准。
4. 全部材料为只读输入，不得修改、删除或在本目录内新增文件。

## 交付要求

交付要求、篇幅与文件命名见 `reports/report_template.md` 与 `compliance/review_checklist.md`。
"""

RULES_V3 = """# 集合资产管理计划投资限制条款（现行版）

版本：v3；生效日：2026-09-01；替代 v2（2026-06-01 版）。本版本为**现行有效**条款。

## 第一章 适用范围

- 第 1 条 本条款适用于现金增强 1 号集合资产管理计划全部投资账户。
- 第 2 条 监控口径为**报告期末**（估值日）时点数，分母为**计划资产净值总额**。
- 第 3 条 分子按报告期末**有效持仓**计算，即估值日当日归属、且证券主数据状态为
  `active` 的持仓；同一账户同一证券的重复上报行仅计一次。

## 第二章 限额条款

- 第 4 条（R-01）单一证券市值占计划资产净值总额的比例 **不得超过 10%**。
- 第 5 条（R-02）单一发行人及其关联方合计比例 **不得超过 15%**。
- 第 6 条（R-03）非标资产（证券主数据 `sec_type = NonStdAsset`）合计比例
  **不得超过 5%**。
- 第 7 条（R-05）现金类资产（含清算备付金）比例 **不得低于 3%**。
- 第 8 条（R-07）权益型基金合计比例 **不得超过 20%**。

## 第三章 超限处置

- 第 9 条 估值日日终仍超限的，投资经理须在 **T+2** 个工作日内提交整改计划，
  并在季度报告「投资监督」章节披露超限事实、成因、整改措施与时限。
- 第 10 条 盘中瞬时超限且在当日收盘前恢复的，记入限额监测台账，无需披露。
- 第 11 条 因证券到期、赎回等被动因素形成的偏离，按被动超限处理，
  但仍须在报告中说明。

## 第四章 附则

- 第 12 条 本条款由风险管理部负责解释；与 v2 版本不一致的，以本版本为准。
"""

RULES_V2 = """# 集合资产管理计划投资限制条款（历史版）

版本：v2；生效日：2026-06-01；已被 v3（2026-09-01 版）替代，**仅作历史回溯使用**。

- 第 4 条（R-01）单一证券市值占计划资产净值总额的比例不得超过 12%。
- 第 6 条（R-03）非标资产合计比例不得超过 8%。
- 第 7 条（R-05）现金类资产比例不得低于 2%。
- 第 8 条（R-07）权益型基金合计比例不得超过 25%。

> 归档说明：2026 年三季度及以后的期末监测一律执行 v3 版本。
"""

RUNBOOK = """# 期末持仓对账操作指引（运营支持组）

版本：2026-07-15；适用范围：季度 / 月度期末持仓对账。

## 1. 输入

1.1 持仓明细：`portfolio/` 下当期持仓导出文件，字段含义见 `internal/data_dictionary.md`。
1.2 行情：估值日收盘行情文件，由数据组于估值日日终推送。
1.3 主数据：`portfolio/security_master.csv`，提供证券状态与券种类别。

## 2. 有效持仓口径

2.1 取 `as_of` 等于**估值日**（本期为 2026-09-30）的记录；
2.2 剔除证券主数据 `status` 非 `active` 的记录；
2.3 同一 `acct + sec_code + vol` 的重复上报行，按 `source_row_id` 升序保留第一条；
2.4 其余记录一律不进入期末口径。

## 3. 关联与计算

3.1 持仓明细与行情文件以 **`wind_code`** 字段关联（两侧文件均提供该字段）；
3.2 持仓市值口径：债券与非标资产 `市值 = vol × close_price / 100`（报价为每百元面值价格，
    非标按摊余成本、报价恒为 100）；权益型基金 `市值 = vol × close_price`（份额 × 净值）；
3.3 行情文件如存在多个交易日，取**估值日当日**记录；
3.4 持仓侧无行情、或行情侧无持仓的记录，列入对账差异表并说明原因。

## 4. 复核与留痕

4.1 汇总市值与托管行净值报告的资产分类核对；
4.2 计算各项限额比例，与 `rules/` 现行条款比对；
4.3 全部阻塞、差异与处置动作记入对账台账，随季度报告归档。
"""

LIQ_POLICY = """# 流动性管理制度（摘要）

- 第 12 条 开放式集合计划应当保持不低于计划资产净值 3% 的现金类资产以应对日常赎回。
- 第 15 条 单一投资者持有比例超过 50% 的，应当在 T+1 内向托管人报告。
- 第 18 条 发生巨额赎回（单个开放日净赎回超过计划总份额 10%）时，
  管理人可按合同约定比例延期办理，并于次一开放日前披露。
- 第 21 条 现金类资产的界定与投资限制条款第七章保持一致。
"""

Q2_REPORT = """# 现金增强 1 号集合资产管理计划 2026 年二季度投资运作报告

编制日期：2026-07-08 | 报告期末：2026-06-30

## 一、组合概况

截至 2026-06-30，计划资产净值 12.86 亿元，份额 12.50 亿份，单位净值 1.0288。
组合以利率债、信用债与同业存单为主，权益基金与可转债为卫星配置。

## 二、投资监督与限额执行

本季度按 2026-06-01 版投资限制条款执行期末监测：单一证券集中度最高 9.87%，
低于 12% 上限；非标资产比例 4.12%，低于 8% 上限；现金类资产比例 2.86%，
高于 2% 下限。各项指标均在限额之内，未发生超限事项。

持仓汇总口径采用盘后导出明细**全表合计**，未区分数据所属日期，
主要原因是为了与上季度报表保持一致。

## 三、投资分析

二季度债券收益率震荡下行，组合久期保持在 1.8 年附近；信用债方面，
华骏集团两只中期票据于 6 月中旬完成付息，未发生信用事件。

## 四、下季度计划

三季度将维持杠铃结构，跟踪华骏集团及其关联方的授信变化，
并按计划完成两只到期存单的续作。

## 五、重要提示

本报告数据来源于管理人交易系统与托管行报告，未经审计。
"""

Q1_REPORT = """# 现金增强 1 号集合资产管理计划 2026 年一季度投资运作报告

编制日期：2026-04-10 | 报告期末：2026-03-31

## 一、组合概况

截至 2026-03-31，计划资产净值 12.31 亿元，单位净值 0.9852。
组合以利率债与同业存单为底仓。

## 二、投资监督

一季度按 2026-06-01 版条款（当时为草案）执行内部监测，各项指标均满足要求。

## 三、投资分析

一季度资金面整体均衡，组合维持较低杠杆。
"""

TEMPLATE = """# 季度投资运作报告模板（报告期末：____）

## 一、材料清点
- 输入文件总数、来源目录数、按目录分列的文件数（分项合计须与总数勾稽）。

## 二、组合概况与净值复核
- 持仓市值、现金、应收应付到资产净值的推导；单位净值与托管报告的核对结论；
  银行对账单余额与托管报告现金的勾稽差额。

## 三、持仓覆盖与口径执行
- 十个账户 sheet 的覆盖情况与逐账户行数；
- 有效持仓口径执行结果：原始记录数、三类剔除记录数与原因、有效记录数与市值；
- 全口径对照下单位净值的偏离说明；行情估值日过滤结果。

## 四、投资监督与限额执行
- 按现行有效条款逐条计算限额比例（条款号、测算值、限额、结论）；
  存在超限的，说明成因、整改措施与时限，并注明历史版本条款的适用性。

## 五、上期报告口径重述
- 上期报告中依据已被替代条款或旧口径形成的表述及其不再适用的原因与本期处置。

## 六、数据问题与处置
- 本期发现的数据问题、阻塞情形、处置动作与依据（逐条）。

## 七、任务拆解与完成状态
- 任务项、状态、对应交付物位置。

## 八、结论与下季度计划
"""

CHECKLIST = """# 季度复核清单（review_checklist）

- [ ] C1 输入材料清点：文件总数、目录数、分目录计数与总数勾稽。
- [ ] C2 持仓覆盖：十个账户 sheet 全部读取并汇总，逐账户行数留痕。
- [ ] C3 有效持仓口径：估值日、主数据状态、重复上报三项处理均有记录。
- [ ] C4 行情使用：估值日当日行情、关联字段与关联结果留痕。
- [ ] C5 净值勾稽：持仓市值 + 现金 + 应收 − 应付与托管报告单位净值的差额。
- [ ] C6 现金勾稽：银行对账单余额合计与托管报告现金一致。
- [ ] C7 限额执行：按现行有效条款逐条计算并给出条款号。
- [ ] C8 旧版本处置：历史条款的适用性说明。
- [ ] C9 上期报告修正：按现行口径重述上期报告中不再适用的表述。
- [ ] C10 数据问题台账：阻塞、差异、处置动作与依据逐条登记。
- [ ] C11 任务拆解与完成状态表。
- [ ] C12 交付物文件名与模板一致，篇幅符合要求。
"""

DICT = """# 数据字典（2026-08 版）

## 1. 持仓明细 `portfolio/holdings_2026Q3.xlsx`

| 字段 | 含义 |
| --- | --- |
| `acct` | 资金账户代码 |
| `sec_code` | 证券编码（交易所 / 银行间统一编码） |
| `sec_name` | 证券名称 |
| `sec_type` | 券种类别，取值见 `security_master.csv` |
| `vol` | 期末持仓数量：债券为面值（元），基金份额为份额（份），非标为本金（元） |
| `as_of` | 数据所属日期 |
| `updated_at` | 导出时间 |
| `source_row_id` | 导出行编号，重复上报时该编号不同 |

## 2. 行情文件 `data/`（估值日行情）

| 字段 | 含义 |
| --- | --- |
| `instrument_id` | 证券编码，与持仓明细的 `sec_code` 为**同一编码体系** |
| `trade_date` | 交易日 |
| `close_price` | 收盘价 / 估值价：债券与非标为每百元面值价格，权益型基金为每份额净值 |
| `price_type` | 价格类型 |
| `batch_tag` | 推送批次标识 |

市值折算：债券与非标 `市值 = vol × close_price / 100`；
权益型基金 `市值 = vol × close_price`。

## 3. 命名沿革

历史文件曾以 `wind_code` 标识证券编码；2026-08 数据字典改版后，
持仓侧统一为 `sec_code`、行情侧统一为 `instrument_id`，两者一一对应，
不再存在 `wind_code` 列。旧版字段名仅在历史归档文件中保留。
"""

OPS_MAIL = """发件人：数据组（data-support）
收件人：运营支持组；组合管理部
时间：2026-10-08 16:42
主题：关于 9 月 30 日收盘行情推送的情况说明

各位：

9 月 30 日估值日收盘后推送的行情主件在传输环节未落盘成功，
我组已于当日 17:30 完成重推，重推件批次标识为「重推件」，
请以重推件为准；主件目录下的同名文件为传输残留，不承载数据。

另：本次重推件同时包含 9 月 29 日的前一交易日记录，用于比对，
取数时请以估值日当日记录为准。

数据组
"""

MGR_NOTES = """# 投资经理说明（2026Q3）

1. 9 月中旬完成华骏集团 2026 年第一期中期票据的增持，单券规模接近内部预警线，
   主要因二级流动性充裕且发行人基本面未发生负面变化；相关审批见
   `internal/approval_memo_20260928.md`。
2. 两只同业存单于 9 月 12 日到期兑付，一只可转债于 9 月 18 日触发赎回条款，
   主数据状态已由数据组更新，期末不应再计入持仓。
3. 非标专户四笔资产均按摊余成本计价，无活跃报价。
4. 上季度报告中「持仓汇总采用全表合计」的表述在本期不再适用，
   本季度起按现行对账口径执行，请在本期报告中作出说明。
"""

APPROVAL = """# 投资决策纪要

会议时间：2026-09-28 15:00
召集人：组合管理部
议题：三季度末信用债持仓结构调整

决议：
1. 同意增持华骏集团 2026 年第一期中期票据，增持后单券规模占计划资产净值
   不超过 11%（内部预警线 10.5%，硬限按现行投资限制条款执行）；
2. 同意维持非标专户规模不变，四笔资产到期分布为 2027-03 至 2028-06；
3. 三季度末持仓结构由投资经理于 T+3 日内完成复核并留痕。
"""

if __name__ == "__main__":
    main()
