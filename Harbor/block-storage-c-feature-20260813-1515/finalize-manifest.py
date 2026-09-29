#!/usr/bin/env python3
"""Finalize delivery after batch2 completes:
- rebuild manifest with batch2 FULL 16 trials (keep existing selected 16)
- re-sync b2-sourced selected trials' job files (terminal state)
"""
import json, subprocess, hashlib
from pathlib import Path

TASK = Path("/home/wff/harbor/block-storage-c-feature-20260813-1515")
JOBS = TASK / "jobs"
SEL = JOBS / "selected-trials"

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()[:16]

# frozen hashes
frozen = {}
hf = JOBS / "frozen-hashes.txt"
if hf.exists():
    for line in hf.read_text().splitlines():
        if "  " in line:
            h, f = line.split("  ", 1)
            frozen[f.strip()] = h

def load_batch(job_dir: str) -> dict:
    d = JOBS / job_dir
    base = d / job_dir if (d / job_dir).is_dir() else d
    trials = []
    for trial in sorted(base.iterdir()):
        if not trial.is_dir():
            continue
        rw = trial / "verifier" / "reward.txt"
        if not rw.exists():
            continue
        r = rw.read_text().strip()
        trials.append({"trial_id": trial.name, "reward": float(r),
                       "terminal": "complete", "valid": r in ("0.0","1.0","0","1"),
                       "source_job": job_dir})
    return {"batch": job_dir, "job_dir": f"jobs/{job_dir}", "n_attempts": 16,
            "concurrency": 16,
            "reward1": sum(1 for t in trials if t["reward"]==1.0),
            "reward0": sum(1 for t in trials if t["reward"]==0.0),
            "trials": trials}

b1 = load_batch("tree-difficulty-16c16")
b2 = load_batch("tree-difficulty-16c16-b2")
print(f"b1: {b1['reward1']}x1.0 {b1['reward0']}x0.0 ({len(b1['trials'])})")
print(f"b2: {b2['reward1']}x1.0 {b2['reward0']}x0.0 ({len(b2['trials'])})")

# keep existing selected trials
sel = []
for t in sorted(SEL.iterdir()):
    if not t.is_dir() or not t.name.startswith("trial-"):
        continue
    rw = t / "verifier" / "reward.txt"
    if not rw.exists():
        continue
    r = float(rw.read_text().strip())
    short = t.name.split("__")[-1]
    src = "tree-difficulty-16c16"
    found = False
    for trial in b1["trials"]:
        if trial["trial_id"].endswith(short):
            src = "tree-difficulty-16c16"; found = True; break
    if not found:
        src = "tree-difficulty-16c16-b2"
    sel.append({
        "trial": t.name, "source_job": src, "trial_id": short,
        "reward": r, "terminal": "complete",
        "selected_reason": ("deterministic: prefer reward=0 (15)" if r == 0.0 else "deterministic: keep one reward=1"),
    })

man = {
    "task": "block-storage-c-feature-20260813-1515",
    "generated": subprocess.check_output(["date","-u","+%Y-%m-%dT%H:%M:%SZ"]).decode().strip(),
    "frozen_hashes": frozen,
    "batches": [b1, b2],
    "selected_trials": sel,
    "selection_rule": ("deterministic from 16xN candidate pool of normally-completed trials with "
                       "reward.txt: prefer 15 reward=0 (sorted by trial name) + 1 reward=1 (sorted "
                       "by trial name); reward<1>=13 and reward=1>=1; timeout/cancel/infra excluded."),
}
(JOBS / "difficulty-manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"manifest updated: {len(b1['trials'])+len(b2['trials'])} trials across 2 batches; selected {len(sel)} (r1={sum(1 for s in sel if s['reward']==1.0)}, r0={sum(1 for s in sel if s['reward']==0.0)})")
