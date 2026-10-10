# -*- coding: utf-8 -*-
"""修复甲方生产侧门禁 6 项 FAIL：
A) rubrics.json 设计态负分 N01–N04 的 weight 由正数改为负数（设计态规范：负分写负权，
   落到 tests/rubrics.toml 才改写为 negate=true + 正 weight）；
B) 新增 R34/R35/R36 的 criterion_type/criterion_necessity 改为规范枚举值；
C) R18 描述去掉表格类定位语「单元格」，并把 criterion_type 由 Subjective 改 Objective（可核验锚点）。
"""
import json
import pathlib
import re
import sys

import tomllib

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = W / "FIN3-WKN-152"
JSONF = TASK / "rubrics.json"
TOML = TASK / "tests" / "rubrics.toml"

NEG = ["N01", "N02", "N03", "N04"]

j = json.loads(JSONF.read_text(encoding="utf-8"))
by = {i["id"]: i for i in j["items"]}

print("=" * 92)
print("A) 负分条目 weight -> 负数（设计态规范）")
print("=" * 92)
for nid in NEG:
    it = by[nid]
    old = it["weight"]
    if old > 0:
        it["weight"] = -old
        print(f"  [OK] {nid}: {old} -> {it['weight']}")
    else:
        print(f"  [--] {nid}: 已是 {old}")

print()
print("=" * 92)
print("B) 新增判据枚举值规范")
print("=" * 92)
for nid in ("R34", "R35", "R36"):
    it = by.get(nid)
    if not it:
        print(f"  [!!] 缺 {nid}")
        continue
    o1, o2 = it.get("criterion_type"), it.get("criterion_necessity")
    it["criterion_type"] = "Objective"
    it["criterion_necessity"] = "Explicit"
    print(f"  [OK] {nid}: criterion_type {o1!r} -> 'Objective', necessity {o2!r} -> 'Explicit'")

print()
print("=" * 92)
print("C) R18：去『单元格』定位语 + 改 Objective")
print("=" * 92)
r18 = by.get("R18")
if r18:
    old = r18["description"]
    new = old
    new = new.replace("**25 个单元格须全部有值，不得留空或以区间代替单点值**",
                      "**25 个格位须全部给出单点数值，不得留空或以区间代替**")
    new = new.replace("有空格", "存在空缺格位")
    if new != old:
        r18["description"] = new
        print("  [OK] R18 描述已去『单元格』")
    else:
        # 兜底：任何出现"单元格"的地方
        if "单元格" in new:
            new2 = new.replace("单元格", "格位")
            r18["description"] = new2
            print("  [OK] R18 兜底替换『单元格』->『格位』")
        else:
            print("  [--] R18 无『单元格』")
    if r18.get("criterion_type") != "Objective":
        print(f"  [OK] R18 criterion_type {r18.get('criterion_type')!r} -> 'Objective'")
        r18["criterion_type"] = "Objective"
    else:
        print("  [--] R18 criterion_type 已是 Objective")
    print(f"      R18 描述尾: …{r18['description'][-90:]}")

# 同步 toml 的 R18 描述
raw = TOML.read_text(encoding="utf-8")
t = tomllib.loads(raw)
t18 = next((c for c in t["criterion"] if c["id"] == "R18"), None)
if t18 and t18["description"] != by["R18"]["description"]:
    if t18["description"] in raw:
        raw = raw.replace(t18["description"], by["R18"]["description"], 1)
        TOML.write_text(raw, encoding="utf-8", newline="\n")
        print("  [OK] toml R18 描述已同步")
    else:
        print("  [!!] toml R18 原文未定位，需人工")

# s_max 与正分池复核
pos_w = sum(i["weight"] for i in j["items"] if i["weight"] > 0)
neg_w = [i["weight"] for i in j["items"] if i["weight"] < 0]
j["metadata"]["scoring"]["s_max"] = pos_w
j["metadata"]["criteria_count"] = len(j["items"])
# 负分清单（供 distribution check 留痕）
j["_distribution_check"]["no_negative_weight_in_tests_rubrics_toml"] = (
    "N01–N04 设计态为负权，落到 tests/rubrics.toml 时改写为 negate = true + 正 weight"
)

JSONF.write_text(json.dumps(j, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

print()
print("=" * 92)
print("结果复核")
print("=" * 92)
print(f"  items={len(j['items'])}  正分池(Σw>0)={pos_w}  s_max={j['metadata']['scoring']['s_max']}")
print(f"  负分条目: {[(i['id'], i['weight']) for i in j['items'] if i['weight'] < 0]}")
print(f"  负分档位: {sorted(set(neg_w))}")
print(f"  R34/R35/R36 枚举: {[(n, by[n]['criterion_type'], by[n]['criterion_necessity']) for n in ('R34','R35','R36')]}")

# toml 侧
t2 = tomllib.loads(TOML.read_text(encoding="utf-8"))
tpos = sum(float(c["weight"]) for c in t2["criterion"] if not c.get("negate"))
tneg = [c["id"] for c in t2["criterion"] if c.get("negate")]
jneg = [i["id"] for i in j["items"] if i["weight"] < 0]
print(f"  toml 正分池={tpos} negate={tneg}")
print(f"  json 负分集合={jneg}  一致={sorted(tneg) == sorted(jneg)}")
print(f"  toml 正分池 == json s_max: {tpos == j['metadata']['scoring']['s_max']}")
