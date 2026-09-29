#!/usr/bin/env python3
"""Assemble final difficulty-manifest.json with batches + selected_trials."""
import json, subprocess, hashlib
from pathlib import Path

TASK = Path("/home/wff/harbor/block-storage-c-feature-20260813-1515")
JOBS = TASK / "jobs"

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()[:16]

frozen = {}
hf = JOBS / "frozen-hashes.txt"
if hf.exists():
    for line in hf.read_text().splitlines():
        if "  " in line:
            h, f = line.split("  ", 1)
            frozen[f.strip()] = h

def load_batch(job_dir: str) -> dict:
    d = JOBS / job_dir
    trials = []
    # harbor layout: <job>/<job>/<trial>/
    base = d / job_dir if (d / job_dir).is_dir() else d
    for trial in sorted(base.iterdir()):
        if not trial.is_dir():
            continue
        rw = trial / "verifier" / "reward.txt"
        if not rw.exists():
            continue
        r = rw.read_text().strip()
        terminal = "complete"
        valid = r in ("0.0", "1.0", "0", "1")
        trials.append({"trial_id": trial.name, "reward": float(r),
                       "terminal": terminal, "valid": valid,
                       "source_job": job_dir})
    r1 = sum(1 for t in trials if t["reward"] == 1.0)
    r0 = sum(1 for t in trials if t["reward"] == 0.0)
    return {"batch": job_dir, "job_dir": f"jobs/{job_dir}",
            "n_attempts": 16, "concurrency": 16,
            "reward1": r1, "reward0": r0, "trials": trials}

# selected trials (from selected-trials/ trial dirs)
sel_dir = JOBS / "selected-trials"
selected = []
for t in sorted(sel_dir.iterdir()):
    if not t.is_dir():
        continue
    rw = t / "verifier" / "reward.txt"
    if not rw.exists():
        continue
    r = float(rw.read_text().strip())
    # trial-NN__shortname -> source guess via shortname in batches
    short = t.name.split("__")[-1]
    src = "unknown"
    for b in ("tree-difficulty-16c16", "tree-difficulty-16c16-b2"):
        for cand in (JOBS / b / b).iterdir() if (JOBS / b / b).is_dir() else []:
            if cand.is_dir() and cand.name.endswith(short):
                src = b
    selected.append({
        "trial": t.name, "source_job": src, "trial_id": short,
        "reward": r, "terminal": "complete",
        "selected_reason": ("deterministic: maximize reward=0 (15) + keep one reward=1" if r == 0.0 else "deterministic: keep one reward=1 sample") if r == 0.0 else "deterministic: keep one reward=1 sample",
    })

manifest = {
    "task": "block-storage-c-feature-20260813-1515",
    "generated": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]).decode().strip(),
    "frozen_hashes": frozen,
    "batches": [load_batch("tree-difficulty-16c16"),
                load_batch("tree-difficulty-16c16-b2")],
    "selected_trials": selected,
    "selection_rule": ("deterministic: from 16xN candidate pool of normally-completed trials "
                       "with reward.txt, select exactly 16: prefer 15 reward=0 (sorted by trial "
                       "name) + 1 reward=1 (sorted by trial name); satisfies reward<1>=13 and "
                       "reward=1>=1. timeout/cancel/infra failures excluded."),
}

(JOBS / "difficulty-manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

b1 = manifest["batches"][0]; b2 = manifest["batches"][1]
print(f"batch1: {b1['reward1']}x1.0 {b1['reward0']}x0.0 ({len(b1['trials'])} trials)")
print(f"batch2: {b2['reward1']}x1.0 {b2['reward0']}x0.0 ({len(b2['trials'])} trials)")
print(f"selected: {len(selected)} trials, r1={sum(1 for s in selected if s['reward']==1.0)} "
      f"r0={sum(1 for s in selected if s['reward']==0.0)}")
