# -*- coding: utf-8 -*-
"""去掉 toml 中三引号 description 的首尾换行，使 toml/json 完全一致。"""
import json
import pathlib
import re
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
TOML = TASK / "tests" / "rubrics.toml"

raw = TOML.read_text(encoding="utf-8")

def repl(m):
    inner = m.group(1)
    inner = inner.strip("\n")
    return f'description = """{inner}"""'

new, n = re.subn(r'description = """\n(.*?)\n"""', repl, raw, flags=re.S)
print(f"  修复三引号 description {n} 处")
if n:
    TOML.write_text(new, encoding="utf-8", newline="\n")

t = tomllib.loads(TOML.read_text(encoding="utf-8"))
j = json.loads((TASK / "rubrics.json").read_text(encoding="utf-8"))
jt = {c["id"]: c for c in t["criterion"]}
jj = {i["id"]: i for i in j["items"]}

print()
print("=" * 90)
print("校验")
print("=" * 90)
print(f"  判据数 toml={len(jt)} json={len(jj)}  ID一致={set(jt) == set(jj)}")
bad = [k for k in jt if jt[k]["description"] != jj[k]["description"]]
print(f"  description 一致: {not bad}  {bad if bad else ''}")
badw = [k for k in jt if float(jt[k]["weight"]) != float(jj[k]["weight"])]
print(f"  weight 一致: {not badw}  {badw if badw else ''}")
badt = [k for k in jt if jt[k].get("type") != jj[k].get("type")]
print(f"  type 一致: {not badt}  {badt if badt else ''}")

# toml 结构与分数复核
pos = [c for c in t["criterion"] if not c.get("negate")]
neg = [c["id"] for c in t["criterion"] if c.get("negate")]
s = sum(float(c["weight"]) for c in pos)
print(f"  {len(t['criterion'])} 条（正 {len(pos)} / 负 {len(neg)}）S_max={s}")
print(f"  scoring.s_max(json metadata) = {j['metadata']['scoring']['s_max']}")
print(f"  criteria_count = {j['metadata']['criteria_count']}")
for cid in ("R34", "R35", "R36"):
    d = jt[cid]["description"]
    print(f"  {cid} len={len(d)} 尾={d[-30:]!r}")
