# -*- coding: utf-8 -*-
"""status.py -- 一览 218/219 的跑分进度与产物状态。

用法：python status.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"
STAGED = REL / "staged"
TASKS = {
    "218": "wfflab__wlogseg-218-v1.1.0-delivery",
    "219": "wfflab__wpeimg-219-v1.1.0-delivery",
}
PLAN = [("qwen", 3), ("opus", 3), ("glm", 1), ("kimi", 1)]


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return default


def main() -> int:
    out = sys.stdout
    for task, pkg in TASKS.items():
        out.write("=" * 72 + "\n")
        out.write("%s  %s\n" % (task, pkg))
        out.write("-" * 72 + "\n")
        ctl = REL / task / "controls" / "summary.json"
        if ctl.is_file():
            rows = read_json(ctl, []) or []
            out.write("controls (%d): " % len(rows))
            out.write("  ".join("%s=%s" % (r["job"], r["reward"]) for r in rows) + "\n")
        else:
            out.write("controls: (not finished)\n")
        summ = REL / task / "model-rounds" / "rounds_summary.json"
        done = read_json(summ, []) or []
        planned = sum(n for _, n in PLAN)
        out.write("models: %d/%d done -> %s\n" % (
            len(done), planned,
            "  ".join("%s#%d=%s" % (r["alias"], r["index"], r["reward"]) for r in done)))
        jobs = STAGED / pkg / "jobs"
        out.write("package jobs/: %s\n" % (
            ("%d dirs" % sum(1 for d in jobs.iterdir() if d.is_dir())) if jobs.is_dir() else "absent"))
        probes = REL / "evidence"
        if probes.is_dir():
            out.write("evidence: %s\n" % ", ".join(sorted(p.name for p in probes.iterdir())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
