#!/usr/bin/env python
"""按题汇总 Qwen/Opus 的 model_score_sum 与 testcase_pass_sum，并标注无效运行。"""
import json
import os
import glob

ROOT = r"C:/Users/Administrator/Desktop/wff-task/harbor-windows"
PRIMARY = {"qwen3.8-max-0902": "Qwen", "opus-5": "Opus"}


def load(rp):
    try:
        return json.load(open(rp, encoding="utf-8"))
    except Exception:
        return None


def pass_count(rd):
    p = os.path.join(rd, "per_testcase.json")
    if not os.path.exists(p):
        return None, None
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None, None
    res = d.get("results")
    if isinstance(res, dict):
        vals = list(res.values())
    elif isinstance(res, list):
        vals = res
    else:
        return None, None
    n = len(vals)
    ok = 0
    for v in vals:
        st = v.get("status") if isinstance(v, dict) else v
        if st == "PASS":
            ok += 1
    return ok, n


print("%-22s %-6s %-6s %-6s %s" % ("task", "model", "scores", "sum", "notes"))
for taskdir in sorted(glob.glob(os.path.join(ROOT, "wfflab__*"))):
    tid = os.path.basename(taskdir)
    mr = os.path.join(taskdir, "extras", "model_runs")
    if not os.path.isdir(mr):
        print("%-22s %s" % (tid, "NO_RUNS"))
        continue
    summary = {}
    for model in sorted(os.listdir(mr)):
        if model.startswith("_"):
            continue
        md = os.path.join(mr, model)
        if not os.path.isdir(md):
            continue
        scores = []
        notes = []
        pcsum = 0
        pcn = 0
        for run in sorted(os.listdir(md)):
            rd = os.path.join(md, run)
            rp = os.path.join(rd, "report.json")
            if not os.path.exists(rp):
                scores.append("NO_REPORT")
                continue
            d = load(rp) or {}
            st = d.get("status")
            sc = d.get("score")
            if st == "INVALID":
                scores.append("INV")
                j = d.get("judge") or {}
                notes.append("%s:INVALID(%s)" % (run, str(j.get("invalid_reason") or d.get("invalid_reason"))[:60]))
            else:
                scores.append(sc)
                if sc is None:
                    notes.append("%s:score=None" % run)
            ok, n = pass_count(rd)
            if ok is not None:
                pcsum += ok
                pcn = n
        vals = [s for s in scores if isinstance(s, (int, float))]
        s = sum(vals)
        if tid:
            pass
        summary[model] = (scores, s, pcsum, pcn, notes)

    for model, (scores, s, pcsum, pcn, notes) in summary.items():
        tag = PRIMARY.get(model, model)
        nt = "; ".join(notes)
        print("%-22s %-6s %-22s %-6s pass=%s/%s %s" % (tid, tag, scores, s, pcsum, pcn, nt))
    # 判定
    q = summary.get("qwen3.8-max-0902")
    o = summary.get("opus-5")
    if q and o:
        qs, os_ = q[1], o[1]
        if os_ > qs:
            verdict = "PASS 条件1 (Opus>Qwen)"
        elif os_ == 0 and qs == 0 and o[2] > q[2]:
            verdict = "PASS 条件2 (pass_sum)"
        elif os_ == qs and qs != 0:
            verdict = "FAIL 同分且非0"
        else:
            verdict = "FAIL"
        print("    -> 区分度: %s   (Opus=%s  Qwen=%s)" % (verdict, os_, qs))
    print()
