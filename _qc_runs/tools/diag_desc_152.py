# -*- coding: utf-8 -*-
"""诊断 R34/R35/R36 在 toml 与 json 中 description 的实际差异。"""
import json
import pathlib
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
t = tomllib.loads((TASK / "tests" / "rubrics.toml").read_text(encoding="utf-8"))
j = json.loads((TASK / "rubrics.json").read_text(encoding="utf-8"))
jt = {c["id"]: c["description"] for c in t["criterion"]}
jj = {i["id"]: i["description"] for i in j["items"]}

for cid in ("R34", "R35", "R36"):
    a, b = jt[cid], jj[cid]
    print("=" * 90)
    print(f"{cid}: toml len={len(a)}  json len={len(b)}")
    if a == b:
        print("  完全一致")
        continue
    # 找第一处差异
    n = min(len(a), len(b))
    k = next((i for i in range(n) if a[i] != b[i]), n)
    print(f"  首个差异位置 {k}")
    print(f"  toml[{max(0,k-30)}:{k+40}] = {a[max(0,k-30):k+40]!r}")
    print(f"  json[{max(0,k-30)}:{k+40}] = {b[max(0,k-30):k+40]!r}")
    print(f"  toml 尾 60: {a[-60:]!r}")
    print(f"  json 尾 60: {b[-60:]!r}")
