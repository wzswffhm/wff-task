# -*- coding: utf-8 -*-
"""按 Windows 价值等级给 48 题（43 条）分类，供选题参考。"""
import json, os, io

SRC = r"C:\Users\Administrator\Desktop\Windows-48题质检-专家修复详解版-20261012\evidence"
OUT = os.path.dirname(os.path.abspath(__file__))
with io.open(os.path.join(SRC, "windows-value.json"), "r", encoding="utf-8") as f:
    value = json.load(f)
with io.open(os.path.join(SRC, "topics.json"), "r", encoding="utf-8") as f:
    topics = {t["key"]: t for t in json.load(f)}

HIGH = ("价值高", "价值较高")
MID = ("平台语义价值", "价值中等", "有平台价值", "生态集成价值中等")
LOW = ("价值低", "偏低")

buckets = {"高": [], "中": [], "低": []}
for v in value:
    a = v["assessment"]
    k = v["key"]
    t = topics.get(k, {})
    row = (k, t.get("task_id", ""), a)
    if any(x in a for x in LOW):
        buckets["低"].append(row)
    elif any(x in a for x in HIGH):
        buckets["高"].append(row)
    else:
        buckets["中"].append(row)

lines = ["# 48 题 Windows 价值分级（甲方 windows-value.json 口径）", ""]
for name in ("高", "中", "低"):
    rows = buckets[name]
    lines.append(f"## {name}（{len(rows)} 题）")
    lines.append("")
    lines.append("| key | task_id | 甲方评价 |")
    lines.append("|---|---|---|")
    for k, tid, a in rows:
        lines.append(f"| {k} | `{tid}` | {a} |")
    lines.append("")

with io.open(os.path.join(OUT, "windows-value-tiers.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines))

print(f"高={len(buckets['高'])} 中={len(buckets['中'])} 低={len(buckets['低'])}")
for k, tid, a in buckets["低"]:
    print("低:", k, tid, "|", a)
print()
for k, tid, a in buckets["中"]:
    print("中:", k, tid, "|", a)
