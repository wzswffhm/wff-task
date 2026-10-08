"""Summarize the original-QC run for both delivery zips."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs")
for tag in ("215", "217"):
    rp = BASE / f"qcorig-{tag}" / "report.json"
    print("=" * 78)
    if not rp.is_file():
        print(f"{tag}: report.json 不存在（{rp}）")
        lg = BASE / f"qcorig-{tag}.log"
        if lg.is_file():
            print("   log tail:", lg.read_text(encoding="utf-8", errors="ignore")[-500:])
        continue
    d = json.loads(rp.read_text(encoding="utf-8-sig"))
    print(f"{tag}: conclusion={d.get('conclusion')}  runs={len(d.get('runs') or [])}")
    for t in d.get("tasks", []):
        print(f"  task={t['task_id']}  static_pass={t['static_pass']}")
        for e in t.get("errors") or []:
            print(f"    ERROR: {e}")
        for w in t.get("warnings") or []:
            print(f"    WARN : {w}")
        gate = t.get("dynamic_gate")
        if gate:
            print(f"    gate pass={gate['pass']} oracle={gate['oracle_scores']} nop={gate['nop_scores']}")
            for r in gate.get("reasons") or []:
                print(f"      reason: {r}")
    print(f"  preflight={d.get('preflight')}")
