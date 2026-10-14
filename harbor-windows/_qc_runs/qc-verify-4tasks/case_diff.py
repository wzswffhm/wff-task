# -*- coding: utf-8 -*-
"""对比 218 / 219 各模型轮次的逐 testcase 结果，判断主模型（Opus vs Qwen）是否真的平手。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")

TASKS = {
    "218": ROOT / "harbor-windows" / "wfflab__wlogseg-218-v1.1.0-delivery",
    "219": ROOT / "harbor-windows" / "wfflab__wpeimg-219-v1.4.0-delivery",
}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))


for tid, pkg in TASKS.items():
    print("=" * 92)
    print("题包 %s" % tid)
    print("=" * 92)
    jobs = pkg / "jobs"
    groups: dict[str, list[dict]] = {}
    for jd in sorted(d for d in jobs.iterdir() if d.is_dir()):
        rp = jd / "verifier" / "report.json"
        if not rp.is_file():
            continue
        doc = load(rp)
        key = jd.name.rsplit("-", 1)[0]          # model-opus / model-qwen
        groups.setdefault(key, []).append(
            {"job": jd.name, "passed": doc.get("passed"), "total": doc.get("total"),
             "cases": {c["test_id"]: bool(c.get("passed")) for c in doc.get("cases", [])}}
        )

    for key in sorted(groups):
        rounds = groups[key]
        print("\n[%s]" % key)
        for r in rounds:
            print("  %-16s passed %s/%s" % (r["job"], r["passed"], r["total"]))
        if len(rounds) >= 2:
            allids = sorted(set().union(*[set(r["cases"]) for r in rounds]))
            union_pass = [i for i in allids if any(r["cases"].get(i) for r in rounds)]
            strict = [i for i in allids if all(r["cases"].get(i) for r in rounds)]
            print("  case 集合大小  : %d" % len(allids))
            print("  至少一轮通过   : %d" % len(union_pass))
            print("  三轮全通过     : %d" % len(strict))

    # 主模型对比：逐 case 汇总（任一模型任一轮通过即算“模型可解该 case”）
    if "model-opus" in groups and "model-qwen" in groups:
        def agg(key):
            rounds = groups[key]
            allids = sorted(set().union(*[set(r["cases"]) for r in rounds]))
            return {i: sum(1 for r in rounds if r["cases"].get(i)) for i in allids}
        o, q = agg("model-opus"), agg("model-qwen")
        ids = sorted(set(o) | set(q))
        only_o = [i for i in ids if o.get(i, 0) > 0 and q.get(i, 0) == 0]
        only_q = [i for i in ids if q.get(i, 0) > 0 and o.get(i, 0) == 0]
        print("\n>>> 主模型逐 case 对比（计三轮中通过轮数）")
        print("  Opus 通过 / Qwen 未通过 : %d 条 %s" % (len(only_o), only_o[:8]))
        print("  Qwen 通过 / Opus 未通过 : %d 条 %s" % (len(only_q), only_q[:8]))
        print("  两者都能通过            : %d 条"
              % len([i for i in ids if o.get(i, 0) > 0 and q.get(i, 0) > 0]))
        print("  两者都未通过            : %d 条"
              % len([i for i in ids if o.get(i, 0) == 0 and q.get(i, 0) == 0]))
        print("  Opus 逐 case 通过轮数合计: %d" % sum(o.values()))
        print("  Qwen 逐 case 通过轮数合计: %d" % sum(q.values()))
    print()
