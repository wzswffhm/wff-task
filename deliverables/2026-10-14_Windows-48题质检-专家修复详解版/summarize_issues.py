# -*- coding: utf-8 -*-
"""按题目汇总 48 题质检发现，并与 Windows 价值评估合表。"""
import json, os, csv, io, sys

SRC = r"C:\Users\Administrator\Desktop\Windows-48题质检-专家修复详解版-20261012\evidence"
OUT = os.path.dirname(os.path.abspath(__file__))

def load(name):
    with io.open(os.path.join(SRC, name), "r", encoding="utf-8") as f:
        return json.load(f)

issues = load("issues.json")
value = load("windows-value.json")
topics = load("topics.json")

val_by_key = {v["key"]: v for v in value}
top_by_key = {t["key"]: t for t in topics}

rows = []
for key, items in issues.items():
    counts = {"问题": 0, "风险": 0, "证据不足": 0}
    for it in items:
        lv = it.get("level")
        if lv in counts:
            counts[lv] += 1
    t = top_by_key.get(key, {})
    v = val_by_key.get(key, {})
    rows.append({
        "key": key,
        "task_id": t.get("task_id", ""),
        "zq_id": t.get("zq_id", v.get("zq_id", "")),
        "archive": t.get("original_archive", ""),
        "total": len(items),
        "issue": counts["问题"],
        "risk": counts["风险"],
        "insufficient": counts["证据不足"],
        "win_value": v.get("assessment", ""),
    })

# 排序：问题数升序 -> 风险数升序 -> key
rows.sort(key=lambda r: (r["issue"], r["risk"], r["insufficient"], r["key"]))

with io.open(os.path.join(OUT, "issues_by_task.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["key", "zq_id", "task_id", "issue", "risk", "insufficient", "total", "archive", "win_value"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

print("key  问题 风险 证据不足 合计  task_id")
for r in rows:
    print(f'{r["key"]:<7}{r["issue"]:>3}{r["risk"]:>5}{r["insufficient"]:>6}{r["total"]:>6}  {r["task_id"]}')

print()
print("总发现条数:", sum(r["total"] for r in rows))
print("问题:", sum(r["issue"] for r in rows), "风险:", sum(r["risk"] for r in rows), "证据不足:", sum(r["insufficient"] for r in rows))

# 提取"Windows 价值高/较高" 且 问题数 <= 1 的题
print()
print("=== Windows 价值高/较高 且 问题数<=1 ===")
for r in rows:
    if ("高" in r["win_value"]) and r["issue"] <= 1:
        print(f'{r["key"]:<7} issue={r["issue"]} risk={r["risk"]} insuf={r["insufficient"]}  {r["task_id"]}')
        print(f'        {r["win_value"]}')
