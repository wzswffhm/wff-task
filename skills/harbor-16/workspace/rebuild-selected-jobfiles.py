#!/usr/bin/env python3
"""Rebuild selected-trials/ top-level job files: result.json stats over the 16
selected dir names, config job_name=tree-difficulty-selected-16, lock/job.log=b1."""
import json, datetime
from pathlib import Path

TASK = Path("/home/wff/harbor/block-storage-c-feature-20260813-1515")
SEL = TASK / "jobs" / "selected-trials"
B1 = TASK / "jobs" / "tree-difficulty-16c16" / "tree-difficulty-16c16"

trials = []
for t in sorted(SEL.iterdir()):
    if not t.is_dir() or not t.name.startswith("trial-"):
        continue
    rw = t / "verifier" / "reward.txt"
    if rw.exists():
        trials.append({"trial_id": t.name, "reward": float(rw.read_text().strip())})

r1 = [x["trial_id"] for x in trials if x["reward"] == 1.0]
r0 = [x["trial_id"] for x in trials if x["reward"] == 0.0]
n = len(trials)
mean = sum(x["reward"] for x in trials) / n if n else 0.0
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
b1r = json.loads((B1 / "result.json").read_text())

result = {
    "id": "selected-16-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
    "started_at": b1r.get("started_at", now),
    "updated_at": now,
    "finished_at": now,
    "n_total_trials": n,
    "stats": {
        "n_completed_trials": n, "n_errored_trials": 0, "n_running_trials": 0,
        "n_pending_trials": 0, "n_cancelled_trials": 0, "n_retries": 0,
        "evals": {"qwen-coder__qwen3.8-max__adhoc": {
            "n_trials": n, "n_errors": 0, "metrics": [{"mean": mean}],
            "reward_stats": {"reward": {"1.0": r1, "0.0": r0}}}}},
}
(SEL / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

cfg = json.loads((B1 / "config.json").read_text())
cfg["job_name"] = "tree-difficulty-selected-16"
cfg["jobs_dir"] = "block-storage-c-feature-20260813-1515/jobs/selected-trials"
(SEL / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

for f in ("lock.json", "job.log"):
    (SEL / f).write_bytes((B1 / f).read_bytes())

print(f"rebuilt: {n} trials, 1.0 x {len(r1)}, 0.0 x {len(r0)}, mean={mean:.4f}")
print("result.json ids:", sorted(r1 + r0)[:3], "...")
