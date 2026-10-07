#!/usr/bin/env python3
"""Show failed checks + rubric items for the runs that scored 0."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs" / "wfflab__wreparse-217"

targets = [
    "20261005T132138-candidate-opus-5-01",
    "20261005T134359-candidate-opus-5-02",
    "20261005T132138-candidate-glm-5.3-01",
    "20261005T133112-candidate-kimi-k3-01",
    "20261005T132138-candidate-qwen3.8-max-0902-01",
    "20261005T110502-candidate-glm-5.3-01",
    "20261005T113954-candidate-opus-5-02",
]

for t in targets:
    d = RUNS / t
    if not d.is_dir():
        print(f"[missing] {t}")
        continue
    for label in sorted(p for p in d.iterdir() if p.is_dir()):
        rj = label / "result.json"
        if not rj.exists():
            print(f"{t}/{label.name}: no result.json")
            continue
        r = json.loads(rj.read_text(encoding="utf-8"))
        rep = r["test"]["report"]
        print("=" * 100)
        print(f"{t}  [{label.name}]  alias={r.get('model_alias')}  verdict={r.get('verdict')}"
              f"  status={rep.get('status')} score={rep.get('score')}")
        a = r.get("agent") or {}
        print(f"    agent: status={a.get('status')} turns={a.get('turns')} "
              f"tool_calls={a.get('tool_calls')} changed={a.get('changed_workspace')} "
              f"dur={r.get('duration_seconds')}")
        rb = r["test"].get("rubric_items") or []
        bad = [x for x in rb if not x.get("passed")]
        print(f"    rubric failed: {[x['rubric_id'] for x in bad]}")
        for x in bad:
            print(f"      - {x['rubric_id']}: failed={x.get('failed')} missing={x.get('missing')}")
        ch = r["test"].get("checks") or []
        badc = [x for x in ch if x.get("status") != "PASS"]
        print(f"    checks failed ({len(badc)}/{len(ch)}):")
        for x in badc:
            print(f"      * {x['test_id']}: {x.get('status')} :: {str(x.get('detail'))[:400]}")
