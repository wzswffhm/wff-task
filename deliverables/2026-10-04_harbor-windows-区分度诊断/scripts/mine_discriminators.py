#!/usr/bin/env python
"""跨全部题目：找出「Qwen 失败而 Opus 通过」的 testcase —— 即潜在的可区分语义点。

输出两张表：
  A. 每个 testcase 在 Qwen/Opus 各 run 的 PASS/FAIL 矩阵（仅列出至少一方出现过 FAIL 的）
  B. 候选区分点：Qwen 有 FAIL 且 Opus 全 PASS
"""
import json
import os
import glob
from collections import defaultdict

ROOT = r"C:/Users/Administrator/Desktop/wff-task/harbor-windows"
MODELS = {"qwen3.8-max-0902": "Q", "opus-5": "O"}


def per_testcase(rd):
    p = os.path.join(rd, "per_testcase.json")
    if not os.path.exists(p):
        return None
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        return None
    res = d.get("results")
    out = {}
    if isinstance(res, dict):
        for k, v in res.items():
            out[k] = v.get("status") if isinstance(v, dict) else v
    elif isinstance(res, list):
        for t in res:
            out[t.get("name")] = t.get("status")
    return out


def kind(name):
    """按测试名尾段归类语义主题。"""
    n = name.split("::")[-1]
    for kw in ("mtime", "case_only", "readonly", "locked", "truncat", "idempot",
               "crc", "checksum", "magic", "placeholder", "collision", "quote",
               "quote_char", "forward", "backward", "placeholder"):
        if kw in n:
            return kw
    return "other"


matrix = defaultdict(dict)   # (task,test) -> {"Q": [...], "O": [...]}
for taskdir in sorted(glob.glob(os.path.join(ROOT, "wfflab__*"))):
    tid = os.path.basename(taskdir)
    mr = os.path.join(taskdir, "extras", "model_runs")
    if not os.path.isdir(mr):
        continue
    for model, tag in MODELS.items():
        md = os.path.join(mr, model)
        if not os.path.isdir(md):
            continue
        for run in sorted(os.listdir(md)):
            rd = os.path.join(md, run)
            if not os.path.isdir(rd):
                continue
            rp = os.path.join(rd, "report.json")
            if os.path.exists(rp):
                try:
                    st = json.load(open(rp, encoding="utf-8")).get("status")
                except Exception:
                    st = None
                if st == "INVALID":
                    continue
            pt = per_testcase(rd)
            if not pt:
                continue
            for name, status in pt.items():
                matrix[(tid, name)].setdefault(tag, []).append(status)

print("=== A. 出现过 FAIL 的 testcase ===")
for (tid, name), d in sorted(matrix.items()):
    q = d.get("Q", [])
    o = d.get("O", [])
    if "FAIL" not in q and "FAIL" not in o:
        continue
    print("%-22s %-58s Q=%-18s O=%s" % (tid, name.split("::")[-1][:58], ",".join(q) or "-", ",".join(o) or "-"))

print()
print("=== B. 候选区分点：Qwen 有 FAIL 且 Opus 非空且全 PASS ===")
found = 0
for (tid, name), d in sorted(matrix.items()):
    q = d.get("Q", [])
    o = d.get("O", [])
    if not q or not o:
        continue
    if "FAIL" in q and all(x == "PASS" for x in o):
        print("  %-22s %-58s Q=%s O=%s" % (tid, name.split("::")[-1][:58], ",".join(q), ",".join(o)))
        found += 1
print("  (共 %d 个)" % found)
