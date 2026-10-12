# -*- coding: utf-8 -*-
"""提取待改写判据全文（v3 现行）+ v2 的 R18 原版（曾压分 qwen/gpt 的严格网格判据）。"""
import json
import pathlib
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = W / "harbor-weakness" / "FIN3-WKN-152"
Q = W / "harbor-weakness" / "_qc_runs"

WANT = ["R03", "R04", "R05", "R06", "R07", "R08", "R09", "R11", "R13",
        "R14", "R17", "R18", "R27", "R30", "R31", "R32", "R33"]

print("=" * 104)
print("A) v3 现行判据全文（待改写）")
print("=" * 104)
crit = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))["criterion"]
for c in crit:
    if c["id"] in WANT:
        print(f"\n--- {c['id']}  weight={c.get('weight')}  negate={c.get('negate')} ---")
        print(c.get("description", ""))

print()
print("=" * 104)
print("B) v2 判据（从 g5-152v2-qwen2 reward-details 提取）")
print("=" * 104)
v2 = Q / "g5-152v2-qwen2" / "trials" / "qwen38max2-152v2" / "verifier" / "reward-details.json"
if v2.exists():
    j = json.loads(v2.read_text(encoding="utf-8"))
    for c in j["reward"]["criteria"]:
        cid = c["id"]
        if cid in WANT or cid == "R18":
            print(f"\n--- v2 {cid} w={c.get('weight')} value={c.get('value')} ---")
            print(str(c.get("description", ""))[:1400])
else:
    print(f"  缺 {v2}")

print()
print("=" * 104)
print("C) v2 中 qwen 失分判据（value<1）—— 现成的压分点")
print("=" * 104)
if v2.exists():
    j = json.loads(v2.read_text(encoding="utf-8"))
    for c in j["reward"]["criteria"]:
        if c.get("value", 1) < 1:
            print(f"\n  {c['id']} value={c['value']} w={c.get('weight')}")
            print(f"    desc: {str(c.get('description',''))[:700]}")
            print(f"    reason: {str(c.get('reasoning',''))[:600]}")
