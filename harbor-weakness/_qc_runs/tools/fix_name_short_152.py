# -*- coding: utf-8 -*-
"""修复 v4 判据的两处规范问题：
1) 新增判据 name 必须 == id（check_rubrics 硬检查）；
2) 判据描述中的交付物须写全名（含 task 前缀与扩展名），check_package #3 提示项。
"""
import json
import pathlib
import re
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness\FIN3-WKN-152")
TOML = TASK / "tests" / "rubrics.toml"
JSONF = TASK / "rubrics.json"

PREFIX = "FIN3-WKN-152"
NEW_IDS = ("R34", "R35", "R36")

# 简称 -> 全名（负向后顾：前面不是下划线才是简称）
SUBS = [
    (r"(?<!_)ipo_model\.xlsx", f"{PREFIX}_ipo_model.xlsx"),
    (r"(?<!_)ipo_model(?![\w.])", f"{PREFIX}_ipo_model"),
    (r"(?<!_)source_trace\.csv", f"{PREFIX}_source_trace.csv"),
    (r"(?<!_)source_trace(?![\w.])", f"{PREFIX}_source_trace"),
    (r"(?<!_)pricing_memo\.md", f"{PREFIX}_pricing_memo.md"),
    (r"(?<!_)valuation_matrix\.csv", f"{PREFIX}_valuation_matrix.csv"),
    (r"(?<!_)qoe_bridge\.csv", f"{PREFIX}_qoe_bridge.csv"),
    (r"(?<!_)reproduce\.py", f"{PREFIX}_reproduce.py"),
    (r"(?<!_)charts\.png", f"{PREFIX}_charts.png"),
]


def fix_desc(s: str) -> str:
    for pat, rep in SUBS:
        s = re.sub(pat, rep, s)
    return s


# ── toml ──
raw = TOML.read_text(encoding="utf-8")

# 1) name 改为 id（仅新增三条）
for cid in NEW_IDS:
    # name = "中文名"  ->  name = "R34"
    m = re.search(rf'(id = "{cid}"\n)name = "[^"]*"', raw)
    if m:
        raw = raw[:m.start(0)] + f'{m.group(1)}name = "{cid}"' + raw[m.end(0):]
        print(f"  [OK] name -> id: {cid}")
    else:
        # name 在 id 之前的情况
        m2 = re.search(rf'name = "([^"]*)"(\n)id = "{cid}"', raw)
        if m2:
            raw = raw[:m2.start(0)] + f'name = "{cid}"{m2.group(2)}id = "{cid}"' + raw[m2.end(0):]
            print(f"  [OK] name -> id(前置): {cid}")
        else:
            print(f"  [!!] 未定位 {cid} 的 name")

# 2) 交付物简称 -> 全名（只处理 description 行，避免误伤结构）
lines = raw.split("\n")
changed = 0
for i, ln in enumerate(lines):
    if ln.lstrip().startswith("description ="):
        nl = fix_desc(ln)
        if nl != ln:
            lines[i] = nl
            changed += 1
raw = "\n".join(lines)
print(f"  [OK] description 简称替换 {changed} 行")
TOML.write_text(raw, encoding="utf-8", newline="\n")

# ── json ──
j = json.loads(JSONF.read_text(encoding="utf-8"))
jd = 0
for it in j["items"]:
    nd = fix_desc(it["description"])
    if nd != it["description"]:
        it["description"] = nd
        jd += 1
JSONF.write_text(json.dumps(j, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"  [OK] json description 替换 {jd} 条")

# ── 校验 ──
print()
print("=" * 90)
print("校验")
print("=" * 90)
t = tomllib.loads(TOML.read_text(encoding="utf-8"))
j2 = json.loads(JSONF.read_text(encoding="utf-8"))
jt = {c["id"]: c for c in t["criterion"]}
jj = {i["id"]: i for i in j2["items"]}

name_bad = [k for k, v in jt.items() if v.get("name") != k]
print(f"  name == id: {not name_bad}  {name_bad if name_bad else ''}")

bad = [k for k in jt if jt[k]["description"] != jj[k]["description"]]
print(f"  description 双文件一致: {not bad}  {bad if bad else ''}")

# 简称残留（排除 Deliverables 行里的全名）
short = set()
for k, v in jt.items():
    d = v["description"]
    for s in ("ipo_model.xlsx", "source_trace.csv", "pricing_memo.md",
              "valuation_matrix.csv", "qoe_bridge.csv", "reproduce.py", "charts.png"):
        # 找不带前缀的
        for mm in re.finditer(re.escape(s), d):
            st = mm.start()
            if st == 0 or d[st - 1] != "_" or not d[max(0, st - 15):st].endswith(PREFIX):
                if st >= 14 and d[st - 14:st] != PREFIX + "_":
                    short.add((k, s))
print(f"  简称残留: {sorted(short) if short else '无'}")

pos = [c for c in t["criterion"] if not c.get("negate")]
print(f"  {len(t['criterion'])} 条（正 {len(pos)} / 负 {len(t)-len(pos)}）S_max={sum(float(c['weight']) for c in pos)}")
print(f"  json s_max={j2['metadata']['scoring']['s_max']} count={j2['metadata']['criteria_count']}")
