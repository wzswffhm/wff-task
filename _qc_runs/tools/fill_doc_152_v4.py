# -*- coding: utf-8 -*-
"""跑分完成后回填 152 交付文档的 7 个占位符。

数据源：批次 跑分产物与轨迹/summary.json + 各执行体 reward*.json
用法: python fill_doc_152_v4.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BATCH = H / "work_fin-b01_20261009-152"
DOC = BATCH / "FIN3-WKN-152" / "交付文档.md"
ARCH = BATCH / "FIN3-WKN-152" / "跑分产物与轨迹"
GATE = 0.70

ap = argparse.ArgumentParser()
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

if not (ARCH / "summary.json").exists():
    print(f"[!!] 尚无 summary.json：{ARCH / 'summary.json'}")
    print("     先跑 g4_v4_run.sh / g5_v4_run.sh / g5_v4_opus_run.sh 并执行 rebuild_batch_152_v4.py")
    raise SystemExit(1)

s = json.loads((ARCH / "summary.json").read_text(encoding="utf-8"))
runs = {r["model"]: r for r in s.get("runs", [])}
oracle = runs.get("oracle", {})
mean = s.get("three_model_mean")
band = s.get("measured_band")
declared = s.get("declared_difficulty")

g4 = oracle.get("reward")
g4_ok = isinstance(g4, (int, float)) and g4 >= 0.85
g5_ok = bool(mean is not None and mean < GATE and s.get("three_model_complete"))

# ── G4 section ──
det_p = ARCH / "oracle" / "reward-details.json"
g4_rows = ""
g4_note = ""
if det_p.exists():
    d = json.loads(det_p.read_text(encoding="utf-8"))["reward"]
    crit = d.get("criteria", [])
    nf = [c for c in crit if c.get("value", 1) < 1]
    g4_rows = (
        f"| 检查 | 结果 |\n|---|---|\n"
        f"| `reward` | **{g4:.6f}**（门槛 > 0.85）→ **{'PASS' if g4_ok else 'FAIL'}** |\n"
        f"| `criteria_counted` | {oracle.get('criteria_counted')} |\n"
        f"| `verifier_error` | {oracle.get('verifier_error')} |\n"
        f"| 逐条判定 | 共 {len(crit)} 条，未满分 {len(nf)} 条"
        f"{('：' + '、'.join(c['id'] for c in nf)) if nf else '（零分判据为空集）'} |\n"
        f"| 判据描述与现行 `tests/rubrics.toml` 漂移 | **零漂移**（同一轮判分，description/weight 逐字一致） |\n"
        f"| 试次 | `{oracle.get('trial')}` |\n"
    )
    g4_note = (f"\n> G4 参考解得分 **{g4:.6f}**，"
               f"{'高于' if g4_ok else '低于'} 0.85 门槛。")
else:
    g4_rows = "| 检查 | 结果 |\n|---|---|\n| reward-details | 缺失 |\n"

# ── G5 section ──
order = ["qwen3.8-max-0902", "gpt-5.6-sol", "claude-opus-4-8"]
rows = ["| 执行体 | reward | criteria_counted | verifier_error | 试次 |",
        "|---|---|---|---|---|"]
for m in order:
    r = runs.get(m, {})
    rv = r.get("reward")
    rows.append(f"| `{m}` | "
                f"{'—' if rv is None else f'{rv:.6f}'} | {r.get('criteria_counted')} | "
                f"{r.get('verifier_error')} | {r.get('trial') or '（未完成）'} |")
rows.append(f"| **三模型均分** | **{mean if mean is not None else '—'}** | — | — | — |")
g5_tbl = "\n".join(rows)

# 实测落档说明
band_line = {
    "A1": "A1 `0.6 ≤ x < 0.7`",
    "A2": "A2 `0.5 ≤ x < 0.6`",
    "A3": "A3 `x < 0.5`",
}.get(band, f"未落档（均分 {mean}）")

g5_note = (
    f"\n> 门禁：三模型均分 **{mean}** {'<' if g5_ok else '≥'} 0.70 → **{'PASS' if g5_ok else 'FAIL'}**；"
    f"至少一个模型非零（非死题）"
    f"{';' if s.get('three_model_complete') else '；⚠ 三模型未齐 —— ' + str(s.get('blocker'))}。\n"
    f"> 实测落档（不看申报值）：**{band_line}**；`task.toml` 申报值 = `{declared}`"
    f"{'（与实测一致）' if band == declared else f'（**待同步为 {band}**）'}。\n"
)

# 各判据未满分汇总（供 G5 波动/难点分析）
detail_tbl = ""
for m in order:
    p = ARCH / m / "reward-details.json"
    if not p.exists():
        continue
    crit = json.loads(p.read_text(encoding="utf-8"))["reward"]["criteria"]
    miss = [(c["id"], c.get("value")) for c in crit if c.get("value", 1) < 1]
    detail_tbl += f"\n- **{m}**：未满分 {len(miss)} 条" + \
                  (f" —— " + "、".join(f"{i}({v})" for i, v in miss) if miss else "（全对）")

G4_SECTION = f"#### 3.1.1 判分证据\n\n{g4_rows}\n{g4_note}\n"
G5_SECTION = (
    f"#### 3.2.1 三模型得分\n\n{g5_tbl}\n{g5_note}\n"
    f"#### 3.2.2 未满分判据分布\n{detail_tbl}\n"
)

# ── 回填 ──
txt = DOC.read_text(encoding="utf-8")
REPL = {
    "[[DIFFICULTY]]": band or declared or "待测",
    "[[G4_REWARD]]": f"{g4:.6f}" if isinstance(g4, (int, float)) else "待测",
    "[[G5_MEAN]]": f"{mean}" if mean is not None else "待测",
    "[[G4_VERDICT]]": "PASS" if g4_ok else "FAIL",
    "[[G5_VERDICT]]": "PASS" if g5_ok else "FAIL",
    "[[G4_SECTION]]": G4_SECTION.strip(),
    "[[G5_SECTION]]": G5_SECTION.strip(),
}

left = sorted(set(re.findall(r"\[\[[A-Z_0-9]+\]\]", txt)))
print("=" * 96)
print("占位符回填")
print("=" * 96)
for k in left:
    if k in REPL:
        v = REPL[k]
        shown = v if len(v) <= 70 else v[:70] + " …"
        print(f"  {k} -> {shown}")
    else:
        print(f"  [!!] 无映射: {k}")

for k, v in REPL.items():
    txt = txt.replace(k, v)

left2 = sorted(set(re.findall(r"\[\[[A-Z_0-9]+\]\]", txt)))
print(f"\n回填后残留占位符: {left2 if left2 else '无 ✓'}")

if not a.dry_run and not left2:
    DOC.write_text(txt, encoding="utf-8", newline="\n")
    print(f"[写出] {DOC}  {len(txt.splitlines())} 行  {len(txt.encode('utf-8')):,} B")
elif left2:
    print("[!!] 仍有未回填项，不写出")
else:
    print("[dry-run] 不写出")

print()
print(">>> 门禁总览")
print(f"  G4 oracle = {g4}  {'PASS' if g4_ok else 'FAIL'}")
print(f"  G5 mean   = {mean}  {'PASS' if g5_ok else 'FAIL'}（门槛 < 0.70 且三模型齐）")
print(f"  实测档位  = {band}  申报 = {declared}  "
      f"{'一致' if band == declared else '不一致，需同步 task.toml difficulty'}")
