# -*- coding: utf-8 -*-
"""诊断：对比 v3 备份与当前 rubrics.json 的负分条目（N01-N04）字段差异，
定位 validate_rubrics 5 项 FAIL 的根因。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
CUR = W / "FIN3-WKN-152" / "rubrics.json"
BK = W / "_backup" / "FIN3-WKN-152-rubrics-v3-20261010" / "rubrics.json"

NEG = ["N01", "N02", "N03", "N04"]


def load(p):
    j = json.loads(p.read_text(encoding="utf-8"))
    return j, {i["id"]: i for i in j["items"]}


print("=" * 96)
print("字段对比：备份(v3) vs 当前")
print("=" * 96)
jb, ib = load(BK)
jc, ic = load(CUR)

for label, j, it in [("备份 v3", jb, ib), ("当前 v4", jc, ic)]:
    pos = [i for i in it.values() if i["weight"] > 0]
    negw = [i for i in it.values() if i["weight"] < 0]
    print(f"\n[{label}] items={len(it)}  weight>0: {len(pos)} 条(池 {sum(i['weight'] for i in pos)})  "
          f"weight<0: {len(negw)} 条")
    print(f"    s_max(metadata) = {j['metadata']['scoring'].get('s_max')}")
    print(f"    criteria_count = {j['metadata'].get('criteria_count')}")
    for nid in NEG:
        i = it.get(nid)
        if i:
            keys = {k: i[k] for k in ("weight", "type", "criterion_type", "criterion_necessity")
                    if k in i}
            print(f"    {nid}: {keys}")
        else:
            print(f"    {nid}: 缺失")

print()
print("=" * 96)
print("逐项差异（当前 vs 备份）—— 仅列变化的字段")
print("=" * 96)
for nid in list(ib.keys()):
    a, b = ib[nid], ic.get(nid)
    if b is None:
        print(f"  {nid}: 当前缺失")
        continue
    diffs = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
    if diffs:
        print(f"  {nid}: 变化字段 {diffs}")
        for k in diffs:
            if k == "description":
                print(f"      {k}: (改写，{len(str(a.get(k)))} -> {len(str(b.get(k)))} 字)")
            else:
                print(f"      {k}: {a.get(k)!r} -> {b.get(k)!r}")

print()
print("=" * 96)
print("判据验证脚本关注的『负分集合』判定模拟")
print("=" * 96)
for label, it in [("备份", ib), ("当前", ic)]:
    neg_by_weight = [k for k, v in it.items() if v["weight"] < 0]
    print(f"  {label}: weight<0 的条目 = {neg_by_weight}")
