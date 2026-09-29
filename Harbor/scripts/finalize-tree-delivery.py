#!/usr/bin/env python3
"""Re-sync selected trials' job files to terminal state (batch2 done) and rebuild zip."""
import json, shutil
from pathlib import Path

TASK = Path("/home/wff/harbor/block-storage-c-feature-20260813-1515")
JOBS = TASK / "jobs"
SEL = JOBS / "selected-trials"
B1 = JOBS / "tree-difficulty-16c16" / "tree-difficulty-16c16"
B2 = JOBS / "tree-difficulty-16c16-b2" / "tree-difficulty-16c16-b2"
JOBFILES = ("config.json", "job.log", "lock.json", "result.json")

man = json.loads((JOBS / "difficulty-manifest.json").read_text())
src_map = {s["trial"].split("__")[-1]: s["source_job"] for s in man["selected_trials"]}

# top-level: batch1 files (complete batch, primary source)
for f in JOBFILES:
    shutil.copy(B1 / f, SEL / f)

# per-trial: source job terminal files
n = 0
for t in sorted(SEL.iterdir()):
    if not t.is_dir() or not t.name.startswith("trial-"):
        continue
    src = src_map.get(t.name.split("__")[-1])
    src_job = B1 if src == "tree-difficulty-16c16" else B2
    for f in JOBFILES:
        shutil.copy(src_job / f, t / f)
    n += 1
print(f"synced {n} trials' job files to terminal state")

# rebuild zip + check
import subprocess
subprocess.run(["python3", str(TASK / "build-zip.py")], check=True)
print("zip rebuilt")
