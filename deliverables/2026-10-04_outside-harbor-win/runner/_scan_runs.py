#!/usr/bin/env python3
"""Scan runner/runs and print every run: alias / mode / verdict / status / turns / dur.

Ground truth for the discrimination gate. Read-only.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs" / "wfflab__wreparse-217"


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


rows = []
for run_dir in sorted(RUNS.iterdir() if RUNS.exists() else []):
    if not run_dir.is_dir():
        continue
    for label_dir in sorted(run_dir.iterdir()):
        if not label_dir.is_dir():
            continue
        rj = label_dir / "results" / "result.json"
        if not rj.exists():
            rj = label_dir / "result.json"
        data = load(rj) if rj.exists() else None

        rep = ((data or {}).get("test") or {}).get("report") or {}
        agent = (data or {}).get("agent") or {}
        rows.append(
            dict(
                run=run_dir.name,
                label=label_dir.name,
                alias=(data or {}).get("model_alias"),
                mode=(data or {}).get("mode"),
                verdict=(data or {}).get("verdict"),
                status=rep.get("status"),
                score=rep.get("score"),
                ver=rep.get("task_version"),
                turns=agent.get("turns"),
                astatus=agent.get("status"),
                dur=(data or {}).get("duration_seconds"),
                has=1 if data else 0,
            )
        )

hdr = "{:<44} {:<18} {:<6} {:<8} {:<7} {:<7} {:<6} {:<6} {:<5} {:<11} {:<7} {}".format(
    "run", "label", "mode", "alias", "verdict", "status", "score", "ver", "turns", "agent_status", "dur", "rj"
)
print(hdr)
print("-" * len(hdr))
for r in rows:
    print(
        "{:<44} {:<18} {:<6} {:<8} {:<7} {:<7} {:<6} {:<6} {:<5} {:<11} {:<7} {}".format(
            r["run"][:44],
            r["label"][:18],
            str(r["mode"])[:6],
            str(r["alias"]),
            str(r["verdict"]),
            str(r["status"])[:7],
            str(r["score"]),
            str(r["ver"])[:6],
            str(r["turns"]),
            str(r["astatus"])[:11],
            str(round(r["dur"]) if isinstance(r["dur"], (int, float)) else r["dur"]),
            r["has"],
        )
    )

print()
print("total runs:", len(rows))
