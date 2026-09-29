#!/usr/bin/env python3
"""Final delivery gate check (terminal state after batch2)."""
import json, hashlib, zipfile
from pathlib import Path

TASK = Path("/home/wff/harbor/block-storage-c-feature-20260813-1515")
JOBS = TASK / "jobs"
SEL = JOBS / "selected-trials"
ZIP = Path("/home/wff/harbor/block-storage-c-feature-20260813-1515-block-storage-c-feature.zip")
oks, fails = [], []

def ck(name, ok, detail=""):
    (oks if ok else fails).append(f"{name} {'PASS' if ok else 'FAIL'} {detail}")

def md5(p): return hashlib.md5(p.read_bytes()).hexdigest()[:12]

# manifest
man = json.loads((JOBS/"difficulty-manifest.json").read_text())
batches = man.get("batches", [])
total_trials = sum(len(b.get("trials",[])) for b in batches)
ck("manifest 2 complete batches", len(batches)==2 and all(len(b["trials"])==16 for b in batches),
   f"{[(b['batch'],b['reward1'],b['reward0']) for b in batches]}")
sel = man.get("selected_trials", [])
ck("selected==16", len(sel)==16, str(len(sel)))
ck("selected <1>=13 & =1>=1",
   sum(1 for s in sel if s["reward"]<1)>=13 and sum(1 for s in sel if s["reward"]==1.0)>=1,
   f"r0={sum(1 for s in sel if s['reward']==0.0)} r1={sum(1 for s in sel if s['reward']==1.0)}")
ck("selected has source/trial/reward/terminal/reason",
   all(all(k in s for k in ("source_job","trial_id","reward","terminal","selected_reason")) for s in sel))

# result.json ids == dir names
result = json.loads((SEL/"result.json").read_text())
rs = result["stats"]["evals"]["qwen-coder__qwen3.8-max__adhoc"]["reward_stats"]["reward"]
ids = set(rs["1.0"])|set(rs["0.0"])
dirs = {p.name for p in SEL.iterdir() if p.is_dir() and p.name.startswith("trial-")}
ck("result.json ids == selected dirs", ids==dirs, f"{len(ids)} vs {len(dirs)}")

# per-trial job files match source
src_map = {s["trial"].split("__")[-1]: s["source_job"] for s in sel}
mism = 0
for t in SEL.iterdir():
    if not t.is_dir() or not t.name.startswith("trial-"): continue
    src = JOBS/"tree-difficulty-16c16"/"tree-difficulty-16c16" if src_map.get(t.name.split("__")[-1])=="tree-difficulty-16c16" else JOBS/"tree-difficulty-16c16-b2"/"tree-difficulty-16c16-b2"
    for f in ("config.json","job.log","lock.json","result.json"):
        if not (t/f).exists() or md5(t/f)!=md5(src/f): mism += 1
ck("per-trial job files match source 64/64", mism==0, f"{64-mism}/64")

# baseline/oracle
b_rw = list((JOBS/"baseline").rglob("verifier/reward.txt"))
o_rw = list((JOBS/"oracle").rglob("verifier/reward.txt"))
ck("baseline reward=0", bool(b_rw) and b_rw[0].read_text().strip()=="0.0")
ck("oracle reward=1", bool(o_rw) and o_rw[0].read_text().strip()=="1.0")

# zip
ck("zip exists", ZIP.exists())
if ZIP.exists():
    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        ck("zip 16 selected", len({n.split("/")[2] for n in names if "jobs/selected-trials/trial-" in n})==16)
        ck("zip baseline+oracle", any("jobs/baseline/" in n for n in names) and any("jobs/oracle/" in n for n in names))
        ck("zip manifest", any("difficulty-manifest" in n for n in names))
        ck("zip 4 jobfiles", all(f"jobs/{f}" in names for f in ("config.json","job.log","lock.json","result.json")))

print("="*60)
print(f"PASS {len(oks)} / FAIL {len(fails)}")
for f in fails: print("[FAIL]", f)
for o in oks: print("[PASS]", o)
