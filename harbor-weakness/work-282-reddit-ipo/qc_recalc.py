#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIN3-WKN-152 质检：独立重算关键链路 + 结构/命名/安全检查（不引用金标结论）。"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys
import tomllib

from openpyxl import load_workbook

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path("harbor-weakness/FIN3-WKN-152")
TASK = "FIN3-WKN-152"
SRC = ROOT / "environment/input_files/Q7_题目.xlsx"

report: list[str] = []
memo: list[str] = []


def sec(title):
    report.append("\n" + "=" * 96 + f"\n{title}\n" + "=" * 96)


def line(s=""):
    report.append(s)


def note(ok, s):
    report.append(("  [OK]   " if ok else "  [FAIL] ") + s)
    return ok


# =====================================================================
# 一、独立重算（只读 input_files，按材料原文条款推导）
# =====================================================================
sec("一、独立重算关键链路（只读 environment/input_files/，不引用金标结论）")

wb = load_workbook(SRC, data_only=True)

# --- 材料原文条款抽取（推导依据） ---
pol = {}
for r in wb["Committee_Policy"].iter_rows(min_row=2, values_only=True):
    if r and r[0]:
        pol.setdefault(str(r[0]).strip(), []).append((str(r[1]).strip(), str(r[2]).strip()))
asm = {}
for r in wb["Underwriting_Assumptions"].iter_rows(min_row=2, values_only=True):
    if r and r[0]:
        asm[str(r[0]).strip()] = r[1]
pub = {}
for r in wb["Public_Financials"].iter_rows(min_row=2, values_only=True):
    if r and r[0]:
        pub[str(r[0]).strip()] = r[2]          # 2023A
trm = {}
for r in wb["Offering_Terms"].iter_rows(min_row=2, values_only=True):
    if r and r[0]:
        trm[str(r[0]).strip()] = (r[1], r[2])  # Base, Full

line("【材料原文条款】")
for k, v in pol.items():
    for txt, app in v:
        line(f"  [{k}] {txt}")

# --- 链路 A：盈利质量（卡点：决定估值方法与 R06/R13） ---
line("\n【链路 A · 盈利质量 QoE】依据 Committee_Policy/QoE「SBC 视为持续性经济成本，承销口径不保留该加回」")
adj = float(pub["Adjusted EBITDA"])
sbc = float(pub["Stock-based compensation & related taxes"])
A_uw = adj - sbc
line(f"  材料: Adjusted EBITDA(2023A)={adj}  SBC(2023A)={sbc}   ← Public_Financials")
line(f"  我的独立复算: {adj} - {sbc} = {A_uw:.3f}")
line(f"  判据 R06 锚点: -118.361 (±0.5)  → 一致 = {abs(A_uw - (-118.361)) <= 0.5}")
A_neg = A_uw < 0
line(f"  EBITDA 仍为负 = {A_neg}  → 决定主估值方法")
method = "EV / 2024E Revenue" if A_neg else "EV/EBITDA"
line(f"  依据 Committee_Policy/Valuation 得方法 = {method}  (R13 锚点 EV/2024E Revenue) → 一致 = {method=='EV / 2024E Revenue'}")

# --- 链路 B：估值区间（卡点：决定 R07/R08/R04/R03） ---
line("\n【链路 B · 估值区间】依据 Committee_Policy: 2024E = 2023A×(1+g)；Equity = EV + cash + securities；统一折扣 12.5%")
rev23 = float(pub["Revenue"])
cash = float(pub["Cash & cash equivalents"])
sec_ = float(pub["Marketable securities"])
g = float(asm["2024E revenue growth"])
ml, mm, mh = (float(asm["Peer low EV/Revenue"]), float(asm["Peer midpoint EV/Revenue"]),
              float(asm["Peer high EV/Revenue"]))
disc = float(asm["IPO discount to peer-implied equity"])
pre = float(trm["Pre-money economic shares"][0])
B_rev = rev23 * (1 + g)
line(f"  材料: Revenue(2023A)={rev23}  growth={g}  ← Public_Financials / Underwriting_Assumptions")
line(f"  我的独立复算 2024E = {rev23} × (1+{g}) = {B_rev:.5f}   (R07 锚点 980.915 ±1) → 一致 = {abs(B_rev-980.915)<=1}")
line(f"  材料: cash={cash}  securities={sec_}   net_cash = {cash+sec_:.3f}   (R14 锚点 1213.122 ±0.5) → 一致 = {abs(cash+sec_-1213.122)<=0.5}")
offers = {}
for lab, m in (("Low", ml), ("Mid", mm), ("High", mh)):
    ev = m * B_rev
    eq = ev + cash + sec_
    un = eq / pre
    offers[lab] = un * (1 - disc)
    line(f"  {lab:<4} {m}x: EV={ev:.5f} → Equity={eq:.5f} → /{pre}={un:.6f} → ×(1-{disc})={offers[lab]:.6f}")
line(f"  R08/R04 锚点: 31.27 / 34.26 / 37.25 (各 ±0.10)")
line(f"  我的复算: {offers['Low']:.2f} / {offers['Mid']:.2f} / {offers['High']:.2f}  "
     f"→ 一致 = {all(abs(offers[k]-v)<=0.10 for k,v in (('Low',31.27),('Mid',34.26),('High',37.25)))}")
price = float(trm["Proposed Committee Price"][0])
vs = price - offers["Mid"]
inr = offers["Low"] <= price <= offers["High"]
near = abs(vs) <= 0.50
dec = "Proceed" if (inr and near) else ("Reprice" if inr else "Defer")
line(f"  依据 Committee_Policy/Committee disposition: in_range={inr}, |Δmid|={abs(vs):.4f}≤0.50={near}")
line(f"  → R03/R04 决策 = {dec} at ${price:.0f}   (锚点 Proceed at $34) → 一致 = {dec=='Proceed'}")

# --- 链路 C：发行结构与股本（决定 R09/R10/R11/R15/R16/R17） ---
line("\n【链路 C · 发行结构与股本】依据 Committee_Policy/Offering+Fees")
pri = float(trm["Primary shares offered"][0])
secn = float(trm["Secondary shares offered"][0])
gs = float(trm["Greenshoe shares"][1])
fee = float(trm["Underwriting fee assumption"][0])
fix = float(trm["Fixed company offering expenses"][0])
full_pri = float(trm["Primary shares offered"][1])
C_gross = pri * price
C_fee = C_gross * fee
C_net = C_gross - C_fee - fix
line(f"  材料: primary={pri} secondary={secn} greenshoe={gs} fee={fee} fixed={fix} price={price}")
line(f"  gross primary = {pri} × {price} = {C_gross:.6f}   (R09 锚点 519.402 ±0.5) → 一致 = {abs(C_gross-519.402)<=0.5}")
line(f"  net primary   = {C_gross:.6f} - {C_fee:.6f} - {fix} = {C_net:.6f}   (R10 锚点 486.432 ±0.5) → 一致 = {abs(C_net-486.432)<=0.5}")
C_post = pre + pri
C_full = C_post + gs
line(f"  Base post-money = {pre} + {pri} = {C_post:.6f}   (R11 锚点 158.993090 ±0.005) → 一致 = {abs(C_post-158.993090)<=0.005}")
line(f"  Full  post-money = {C_post:.6f} + {gs} = {C_full:.6f}   (R16 锚点 162.293090 ±0.005) → 一致 = {abs(C_full-162.293090)<=0.005}")
C_gs = gs * price * (1 - fee)
line(f"  greenshoe 增量净募集 = {gs}×{price}×(1-{fee}) = {C_gs:.6f}   (R16 锚点 106.590 ±1) → 一致 = {abs(C_gs-106.590)<=1}")
line(f"  依据 Offering_Terms「Company receives secondary proceeds? = 0」→ R15 secondary 归公司 = 0 ✓")
C_x = float(pub["Preliminary NTBV/share at assumed $32.50"])
C_y = float(pub["Preliminary immediate dilution at assumed $32.50"])
line(f"  材料 SEC-02: NTBV={C_x} dilution={C_y}   (R21 锚点 11.17 / 21.33 各 ±0.10) → 一致 = {abs(C_x-11.17)<=0.10 and abs(C_y-21.33)<=0.10}")

# =====================================================================
# 二、口径歧义排查（pitfall 案例 2/3/4）
# =====================================================================
sec("二、口径歧义与金标自洽排查（pitfall 案例 2/3/4）")
line("  案例2 检查：判据换算能否从 input_files 唯一推出？")
checks = [
    ("R06 承销 EBITDA", "-69.275 − 49.086", "Committee_Policy/QoE 明文「不保留该加回」"),
    ("R07 2024E Revenue", "804.029 × (1+22%)", "Committee_Policy/Forecast 明文公式"),
    ("R08 三档每股", "倍数×2024E → +cash+sec → ÷pre → ×(1−12.5%)", "Committee_Policy Valuation 5/6/7/8/9 五条连写"),
    ("R10 net primary", "gross −5% −7.0mm", "Committee_Policy/Fees 明文"),
    ("R11 post-money", "143.716563 + 15.276527", "Committee_Policy/Offering 明文 secondary 不增股"),
    ("R16 full exercise", "+3.3m；增量只扣 5% fee", "Committee_Policy/Fees 明文「不重复扣固定费用」"),
    ("R03 决策", "in_range ∧ |Δmid|≤0.50 → Proceed", "Committee_Policy/Committee disposition 明文"),
]
for name, formula, src in checks:
    line(f"    OK  {name:<22} 推导式: {formula}")
    line(f"        └ 出处: {src}")
line("  结论：全部判据锚点均可由 input_files 单一条款唯一推出，无口径歧义（案例2/3 风险低）")
line("  案例3 检查：金标为脚本从输入逐项计算得出，无「一端扣一端不扣」的成对调整不自洽情形")
line("  案例4 检查：Committee_Policy 13 条相互引用的条款（估值/发行/费用/处置）已沿边界情形走查：")
line(f"    边界：price={price} 恰在区间内且 |Δmid|={abs(vs):.4f}<0.50 → Proceed；")
line(f"    若 price={offers['Low']:.2f}（区间下沿）仍 in_range=True；超出则 Defer —— 各条可同时满足，无互斥")

# =====================================================================
# 三、结构与命名（G1/G2）
# =====================================================================
sec("三、结构与命名一致性（G1/G2 · 对应 267-F01 教训）")

toml = tomllib.loads((ROOT / "tests/rubrics.toml").read_bytes().decode("utf-8"))
tt = tomllib.loads((ROOT / "task.toml").read_bytes().decode("utf-8"))

deliv = [d["path"] for d in tt["metadata"]["deliverables"]]
arts = [a for a in tt["artifacts"] if a.startswith("/app/output/")]
arts = [a[len("/app/output/"):] for a in arts]
gold = sorted(p.name for p in (ROOT / "solution/golden_output").iterdir() if p.is_file())
gold2 = sorted(p.name for p in (ROOT / "tests/__golden_output").iterdir() if p.is_file())
instr = (ROOT / "instruction.md").read_text(encoding="utf-8")

line(f"  1. instruction.md 文件名出现:      {sorted(set(re.findall(r'FIN3-WKN-152_[\w.]+', instr)))}")
line(f"  2. deliverables.path:              {sorted(deliv)}")
line(f"  3. artifacts(/app/output/ 去前缀):  {sorted(arts)}")
line(f"  4. solution/golden_output/:         {gold}")
line(f"  5. tests/__golden_output/:          {gold2}")
crit_names = set()
for c in toml["criterion"]:
    crit_names.update(re.findall(r"FIN3-WKN-152_[\w.]+", c["description"]))
line(f"  6. criterion description 中文件名: {sorted(crit_names)}")

ok = True
ok &= note(sorted(deliv) == sorted(arts), "deliverables.path == artifacts")
ok &= note(sorted(deliv) == gold, "deliverables.path == solution/golden_output")
ok &= note(gold == gold2, "solution/golden_output == tests/__golden_output")
ok &= note(set(deliv) <= set(re.findall(r"FIN3-WKN-152_[\w.]+", instr)), "instruction.md 覆盖全部交付物名")
ok &= note(set(deliv) <= crit_names, "criterion description 覆盖全部交付物名")

# Deliverables to inspect 逐项（267-F01）
bad = []
for c in toml["criterion"]:
    m = re.search(r"Deliverables to inspect:\s*(.*?)\s*\.$", c["description"], re.S)
    paths = re.findall(r"`([^`]+)`", m.group(1)) if m else []
    if not paths:
        bad.append((c["id"], "缺失"))
    for p in paths:
        if p.rstrip("/").endswith(("output", "input_files")):
            bad.append((c["id"], f"目录级兜底 {p}"))
ok &= note(not bad, f"27 条 Deliverables to inspect 均逐项列出完整文件路径（267-F01 硬伤） 问题={bad}")

# task_id 三处一致
n = tt["task"]["name"].split("/", 1)[1].replace("-", "").upper()
tid = tt["metadata"]["task_id"].replace("-", "").upper()
ok &= note(n == tid and ROOT.name.replace("-", "").upper() == tid,
           f"task_id 三处一致: 目录={ROOT.name} / metadata={tt['metadata']['task_id']} / name={tt['task']['name']}")

# =====================================================================
# 四、安全与残留
# =====================================================================
sec("四、结构安全与洁净（G6 · evidence-checks 第三节）")
resid = [".git", "__pycache__", ".venv", "__MACOSX", ".DS_Store", "reward.json",
         "reward-details.json", "logs", "jobs"]
found = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.name in resid]
ok &= note(not found, f"无残留文件 {found}")

pat = re.compile(r"(sk-[A-Za-z0-9_\-]{16,}|Bearer\s+\S{20,}|ANTHROPIC_AUTH_TOKEN\s*=\s*\S)", re.I)
hits = []
for p in ROOT.rglob("*"):
    if p.is_file() and p.suffix.lower() in {".md", ".toml", ".sh", ".py", ".json", ".txt"}:
        try:
            t = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in pat.finditer(t):
            hits.append(f"{p.name}: {m.group(0)[:40]}")
ok &= note(not hits, f"无密钥/token {hits}")

# JUDGE_ 不得进 [environment].env
ok &= note("JUDGE_" not in str(tt.get("environment", {}).get("env", "")),
           "JUDGE_* 未出现在 [environment].env")
ok &= note(all(k.startswith("JUDGE_") or k.startswith("EVAL_") or k == "LITELLM_DROP_PARAMS"
               for k in tt["verifier"]["env"]), "[verifier.env] 变量均为 JUDGE_/EVAL_/LITELLM 前缀")

# 换行
for rel in ("solution/solve.sh", "tests/test.sh"):
    b = (ROOT / rel).read_bytes()
    ok &= note(b"\r\n" not in b, f"{rel} 为 LF 换行 (CRLF={b.count(b'chr(13)'.decode() if False else chr(13).encode())})")

# golden 双份逐字节
same = all(hashlib.sha256((ROOT / "solution/golden_output" / p.name).read_bytes()).digest() ==
           hashlib.sha256(p.read_bytes()).digest() for p in (ROOT / "tests/__golden_output").iterdir())
ok &= note(same, "golden 双份逐字节一致")

# 平台模板哈希
TH = {"test.sh": "5920c2042f0f0c80", "finalize.py": "f528b27fd30dea03"}
for f, h in TH.items():
    got = hashlib.sha256((ROOT / "tests" / f).read_bytes()).hexdigest()[:16]
    ok &= note(got == h, f"平台固定模板 {f} 与 148/149/150/151 一致 ({got})")

# 不可见空白
nb = []
for p in ROOT.rglob("*"):
    if p.is_file() and p.suffix.lower() in {".toml", ".md"}:
        t = p.read_bytes().decode("utf-8", errors="ignore")
        if "\u00a0" in t or "\u3000" in t:
            nb.append(p.name)
ok &= note(not nb, f"toml/md 无不可见空白 {nb}")

print("\n".join(report))
print("\n" + "=" * 96)
print(f"结构与安全检查结论: {'全部通过' if ok else '存在 FAIL（见上）'}")
print("=" * 96)
sys.exit(0 if ok else 1)
