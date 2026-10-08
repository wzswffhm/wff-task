"""Check whether the package jobs/ records are backed by the original runner runs
in wff-task1, by matching the recorded test_log_sha256 against runs/**/test.log.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PKG = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
RUNS = Path(r"C:\Users\Administrator\Desktop\wff-task1\deliverables\2026-10-04_outside-harbor-win\runner\runs")

for task_id in ("wfflab__wfmt-215", "wfflab__wreparse-217"):
    jobs_dir = PKG / task_id / "jobs"
    runs_dir = RUNS / task_id
    print("=" * 78)
    print(task_id)
    print("  package jobs entries :", sum(1 for p in jobs_dir.iterdir() if p.is_dir()) if jobs_dir.exists() else 0)
    print("  runner runs entries  :", sum(1 for p in runs_dir.iterdir() if p.is_dir()) if runs_dir.exists() else 0)
    matched = unmatched = no_hash = no_run = 0
    missing_evidence: list[str] = []
    for job in sorted(p for p in jobs_dir.iterdir() if p.is_dir()):
        job_json = job / "job.json"
        if not job_json.is_file():
            continue
        doc = json.loads(job_json.read_text(encoding="utf-8-sig"))
        recorded = doc.get("test_log_sha256")
        run = runs_dir / job.name
        if not run.is_dir():
            no_run += 1
            continue
        logs = sorted(run.rglob("test.log"))
        if not logs:
            no_hash += 1
            continue
        digests = {hashlib.sha256(p.read_bytes()).hexdigest() for p in logs}
        if recorded and recorded in digests:
            matched += 1
        elif recorded is None:
            no_hash += 1
        else:
            unmatched += 1
        for name in ("agent.log", "checks.json", "result.json", "stderr.log"):
            if not any(run.rglob(name)):
                missing_evidence.append(f"{job.name}:{name}")
    print(f"  sha256 matched       : {matched}")
    print(f"  sha256 mismatched    : {unmatched}")
    print(f"  no recorded hash     : {no_hash}")
    print(f"  run dir missing      : {no_run}")
    if missing_evidence:
        print("  evidence absent in run dir:", ", ".join(missing_evidence[:8]))
