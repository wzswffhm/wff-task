# -*- coding: utf-8 -*-
"""读出 R16 与 R34 的完整 description（双文件），并复核 R16 算式真值。"""
import json
import pathlib
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
t = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
j = json.loads((TASK / "rubrics.json").read_text(encoding="utf-8"))
jt = {c["id"]: c for c in t["criterion"]}
jj = {i["id"]: i for i in j["items"]}

for cid in ("R16", "R34"):
    print("=" * 96)
    print(f"{cid}  weight={jt[cid]['weight']}")
    print("=" * 96)
    print("--- toml ---")
    print(jt[cid]["description"])
    print("--- json 一致?", jt[cid]["description"] == jj[cid]["description"])
    print()

print("=" * 96)
print("算式真值复核")
print("=" * 96)
a = 15.276527 + 3.3
print(f"  (15.276527 + 3.3) = {a}")
print(f"  × 34 = {a * 34:.6f}")
print(f"  判据 R16 写的 632.456518 差 {abs(632.456518 - a * 34):.6f}")
print(f"  公司 gross primary 15.276527 × 34 = {15.276527 * 34:.6f}")
print(f"  加 greenshoe 增量 3.3 × 34 = {3.3 * 34:.6f}")
print(f"  两者之和 = {15.276527 * 34 + 3.3 * 34:.6f}")

# input_files 顶层散件确认
INF = TASK / "environment" / "input_files"
top_files = sorted(p.name for p in INF.iterdir() if p.is_file())
dirs = sorted(p.name for p in INF.iterdir() if p.is_dir())
print()
print("=" * 96)
print("input_files 实际结构")
print("=" * 96)
print(f"  顶层散件 {len(top_files)}: {top_files}")
print(f"  目录 {len(dirs)}: {dirs}")
tot = len(top_files)
for d in dirs:
    n = sum(1 for p in (INF / d).rglob("*") if p.is_file())
    print(f"    {d}/ {n}")
    tot += n
print(f"  总计 = {tot}")
