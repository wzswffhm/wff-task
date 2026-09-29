#!/usr/bin/env python3
"""Rebuild the submission zip from backup helper logic (no helper files left in task dir)."""
import zipfile, os, shutil
from pathlib import Path

TASK = Path("/home/wff/harbor/block-storage-c-feature-20260813-1515")
STAGE = Path("/tmp/tree_deliver_final")
ZIP = Path("/home/wff/harbor/block-storage-c-feature-20260813-1515-block-storage-c-feature.zip")

if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE.mkdir(parents=True)

for f in ("instruction.md", "task.toml"):
    shutil.copy(TASK / f, STAGE / f)
for d in ("environment", "solution", "tests"):
    shutil.copytree(TASK / d, STAGE / d)
jobs = STAGE / "jobs"; jobs.mkdir()
for d in ("baseline", "oracle", "selected-trials"):
    shutil.copytree(TASK / "jobs" / d, jobs / d)
shutil.copy(TASK / "jobs" / "difficulty-manifest.json", jobs / "difficulty-manifest.json")
for name in ("config.json", "job.log", "lock.json", "result.json"):
    shutil.copy(TASK / "jobs" / name, jobs / name)
    b2 = name.replace(".json", "-b2.json").replace(".log", "-b2.log")
    shutil.copy(TASK / "jobs" / b2, jobs / b2)

# strip workspace build artifacts
nbd = STAGE / "environment" / "workspace" / "nbd"
for p in nbd.iterdir():
    if p.is_dir() and p.name == ".git":
        shutil.rmtree(p, ignore_errors=True)

if ZIP.exists():
    ZIP.unlink()
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk(STAGE):
        for f in files:
            fp = Path(root) / f
            zf.write(fp, fp.relative_to(STAGE))

print(f"zip: {ZIP} ({ZIP.stat().st_size/1024:.0f} KB)")
with zipfile.ZipFile(ZIP) as zf:
    names = zf.namelist()
    sel = [n for n in names if "jobs/selected-trials/trial-" in n]
    print(f"entries: {len(names)}; selected dirs: {len(set(n.split('/')[2] for n in sel))}; "
          f"manifest: {len([n for n in names if 'difficulty-manifest' in n])}; "
          f"jobfiles: {len([n for n in names if n.startswith('jobs/') and n.count('/')==1])}")
