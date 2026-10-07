#!/usr/bin/env python
"""扫描所有题目的模型运行状态，找出 INVALID / NOT_RUN / 缺失的 run。"""
import json
import os
import glob

ROOT = r"C:/Users/Administrator/Desktop/wff-task/harbor-windows"

rows = []
for taskdir in sorted(glob.glob(os.path.join(ROOT, "wfflab__*"))):
    tid = os.path.basename(taskdir)
    mr = os.path.join(taskdir, "extras", "model_runs")
    if not os.path.isdir(mr):
        rows.append((tid, "NO_RUNS", "", "", ""))
        continue
    for model in sorted(os.listdir(mr)):
        md = os.path.join(mr, model)
        if not os.path.isdir(md):
            continue
        for run in sorted(os.listdir(md)):
            rd = os.path.join(md, run)
            if not os.path.isdir(rd):
                continue
            rp = os.path.join(rd, "report.json")
            if not os.path.exists(rp):
                rows.append((tid, model, run, "NO_REPORT", ""))
                continue
            try:
                d = json.load(open(rp, encoding="utf-8"))
            except Exception as e:
                rows.append((tid, model, run, "BAD_JSON", str(e)[:60]))
                continue
            st = d.get("status")
            sc = d.get("score")
            ir = ""
            j = d.get("judge") or {}
            if isinstance(j, dict):
                ir = (j.get("invalid_reason") or "")[:150]
            if ir == "" and d.get("invalid_reason"):
                ir = str(d.get("invalid_reason"))[:150]
            rows.append((tid, model, run, "%s score=%s" % (st, sc), ir.replace("\n", " ")))

w = max(len(r[0]) for r in rows)
for r in rows:
    print("%-24s %-20s %-6s %-26s %s" % r)
