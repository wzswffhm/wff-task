"""Run the real Windows Harbor Oracle/NOP gate over adapted staged task copies.

Judging logic is imported verbatim from the client QC package (run_qc.classify_job
/ formal_result / dynamic_gate). Two QC-side deviations, both recorded in the
final report:

1. harbor receives ``--path <staged parent> --include-task-name <dir>`` because a
   bare single-task directory resolves to a dataset with zero tasks.
2. the staged copies carry the compatibility adaptations produced by
   stage_tasks.py / adapt_for_harbor.py / adapt_entrypoints.py; the delivered
   packages are never modified.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

QC_SCRIPTS = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_ref\windows-harbor-qc\scripts")
sys.path.insert(0, str(QC_SCRIPTS))
import run_qc  # noqa: E402

AGENTS = ("oracle", "nop")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_one(task_id: str, staged_root: Path, agent: str, attempt: int,
            jobs_root: Path, out: Path) -> dict:
    job_name = f"{task_id}-{agent}-{attempt}"
    log = out / f"{job_name}.cli.log"
    harbor = shutil.which("harbor") or shutil.which("harbor.exe") or "harbor"
    command = [harbor, "run", "--path", str(staged_root),
               "--include-task-name", task_id, "--agent", agent,
               "--n-attempts", "1", "--n-concurrent", "1", "--max-retries", "0",
               "--jobs-dir", str(jobs_root), "--job-name", job_name,
               "--env", "windows_qc_env:WindowsQCEnvironment", "--yes"]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(QC_SCRIPTS) + os.pathsep + os.environ.get("PYTHONPATH", ""),
           "DOCKER_CONTEXT": "desktop-windows"}
    started = utc_now()
    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace", env=env)
        code, output = proc.returncode, proc.stdout
    except OSError as exc:
        code, output = 127, str(exc)
    log.write_text(output, encoding="utf-8")

    trials = run_qc.classify_job(jobs_root / job_name) or run_qc.classify_job(jobs_root)
    task = {"task_id": task_id, "root": str(staged_root / task_id)}
    row = {"task_id": task_id, "agent": agent, "attempt": attempt, "command": command,
           "started": started, "ended": utc_now(), "exit_code": code,
           "cli_log": str(log), "trials": trials}
    row["formal_results"] = [run_qc.formal_result(t, task) for t in trials]
    if code != 0 or not trials or any(t.get("exception") or t.get("rewards") is None
                                      for t in trials):
        row["status"] = "BLOCKED"
    elif any(r.get("validity") != "VALID" for r in row["formal_results"]):
        row["status"] = "INVALID"
    else:
        row["status"] = "VALID"
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--only", action="append", default=None)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    jobs_root = args.out / "jobs"
    jobs_root.mkdir(exist_ok=True)

    task_ids = [p.name for p in sorted(args.staged.iterdir()) if (p / "task.toml").is_file()]
    if args.only:
        task_ids = [t for t in task_ids if t in set(args.only)]

    report = {"generated_at": utc_now(), "staged_root": str(args.staged),
              "attempts": args.attempts, "tasks": {}}
    for task_id in task_ids:
        runs: list[dict] = []
        for agent in AGENTS:
            for attempt in range(1, args.attempts + 1):
                row = run_one(task_id, args.staged, agent, attempt, jobs_root, args.out)
                runs.append(row)
                scores = [x.get("score") for x in row["formal_results"]]
                print(f"{task_id} {agent} {attempt}/{args.attempts} {row['status']} {scores}",
                      flush=True)
                report["tasks"][task_id] = {
                    "runs": runs,
                    "gate": run_qc.dynamic_gate(runs, args.attempts) if len(runs) >= 2 else None,
                }
                (args.out / "runs.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                if row["status"] in ("BLOCKED", "INVALID"):
                    print(f"  -> stopping {task_id}/{agent} after {row['status']}", flush=True)
                    break
        print(f"GATE {task_id}: {json.dumps(report['tasks'][task_id]['gate'], ensure_ascii=False)}",
              flush=True)

    (args.out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
