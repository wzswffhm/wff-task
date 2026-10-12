"""Run the standard Harbor CLI against ONE task package and write the run records
back into the package as jobs/<job-id>/{agent,verifier}.

Judging is imported verbatim from the client QC package (run_qc.classify_job /
formal_result); the on-disk record shape mirrors the task package's existing
jobs/ entries (job.json + agent/run.json + verifier/result.json).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

QC_SCRIPTS = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_ref\windows-harbor-qc\scripts")
sys.path.insert(0, str(QC_SCRIPTS))
import run_qc  # noqa: E402

# agent, mode, role, model_key, run_label
PLAN = [
    ("oracle", "golden", "golden", "ORACLE", "oracle"),
    ("nop", "no-change", "no-change", "NOP", "nop"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def harbor_version() -> str:
    harbor = shutil.which("harbor") or "harbor"
    try:
        out = subprocess.run([harbor, "--version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace")
        return out.stdout.strip()
    except OSError:
        return "unknown"


def run_trial(task_path: Path, agent: str, job_id: str, jobs_root: Path) -> dict:
    harbor = shutil.which("harbor") or "harbor"
    command = [harbor, "run", "--path", str(task_path), "--agent", agent,
               "--n-attempts", "1", "--n-concurrent", "1", "--max-retries", "0",
               "--jobs-dir", str(jobs_root), "--job-name", job_id,
               "--env", "windows_qc_env:WindowsQCEnvironment", "--yes"]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": str(QC_SCRIPTS) + os.pathsep + os.environ.get("PYTHONPATH", ""),
           "DOCKER_CONTEXT": "desktop-windows"}
    started = time.time()
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace", env=env)
    duration = round(time.time() - started, 1)
    log = jobs_root / f"{job_id}.cli.log"
    log.write_text(proc.stdout, encoding="utf-8")
    trials = run_qc.classify_job(jobs_root / job_id) or run_qc.classify_job(jobs_root)
    trial = trials[0] if trials else None
    return {"command": command, "exit_code": proc.returncode, "log": str(log),
            "duration_seconds": duration, "trial": trial}


def write_record(task_path: Path, task_id: str, task_version: str,
                 agent: str, mode: str, role: str, model_key: str, label: str,
                 attempt: int, job_id: str, run: dict, harness: str) -> dict:
    formal = None
    reason = "no trial produced"
    verdict = None
    report_status = "BLOCKED"
    cases: list[dict] = []
    trial_root = Path(run["trial"]["trial_root"]) if run["trial"] else None
    if run["trial"] is not None:
        formal = run_qc.formal_result(run["trial"], {"root": str(task_path)})
        report_status = formal.get("validity", "INVALID")
        verdict = formal.get("score")
        cases = formal.get("cases", [])
        if report_status == "VALID":
            verifier_report = (trial_root / "verifier" / "report.json")
            if verifier_report.is_file():
                try:
                    reason = json.loads(verifier_report.read_text(encoding="utf-8-sig")).get("reason") or "scored"
                except (ValueError, UnicodeError):
                    reason = "scored"
        else:
            reason = formal.get("reason") or "invalid testcase execution"

    record_dir = task_path / "jobs" / job_id
    (record_dir / "agent").mkdir(parents=True, exist_ok=True)
    (record_dir / "verifier").mkdir(parents=True, exist_ok=True)

    agent_status = "completed" if run["exit_code"] == 0 else f"exit_{run['exit_code']}"
    test_log = None
    if trial_root is not None:
        for name in ("test-stdout.txt", "reward.txt", "report.json"):
            src = trial_root / "verifier" / name
            if src.is_file():
                shutil.copy2(src, record_dir / "verifier" / name)
        for name in (f"{agent}.txt", "exit-code.txt"):
            src = trial_root / "agent" / name
            if src.is_file():
                shutil.copy2(src, record_dir / "agent" / name)
        test_log = sha256_file(trial_root / "verifier" / "test-stdout.txt")
        if (trial_root / "trial.log").is_file():
            shutil.copy2(trial_root / "trial.log", record_dir / "verifier" / "trial.log")

    stamp = utc_now()
    job = {
        "task_id": task_id,
        "task_version": task_version,
        "job_id": job_id,
        "run_id": job_id,
        "run_label": label,
        "mode": mode,
        "role": role,
        "model_key": model_key,
        "verdict": verdict,
        "report_status": report_status,
        "reason": reason,
        "duration_seconds": run["duration_seconds"],
        "agent_status": agent_status,
        "turns": None,
        "test_log_sha256": test_log,
        "mtime_utc": stamp,
        "excluded": False,
        "exclusion": None,
        "scoring_policy": "scored",
        "harness": harness,
        "source": {
            "runner": harness,
            "command": " ".join(run["command"]),
            "cli_log": run["log"],
            "trial": run["trial"]["trial_root"] if run["trial"] else None,
        },
    }
    (record_dir / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
    agent_doc = {
        "job_id": job_id,
        "task_id": task_id,
        "task_version": task_version,
        "role": role,
        "mode": mode,
        "model_key": model_key,
        "model_label": label,
        "agent_status": agent_status,
        "turns": None,
        "duration_seconds": run["duration_seconds"],
        "excluded": False,
        "exclusion": None,
        "artifacts_present": run["trial"] is not None,
        "artifacts_note": "agent stdout kept as agent/%s.txt; full job tree under the --jobs-dir of this run"
                          % agent,
    }
    (record_dir / "agent" / "run.json").write_text(
        json.dumps(agent_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result_doc = {
        "job_id": job_id,
        "task_id": task_id,
        "task_version": task_version,
        "mode": mode,
        "role": role,
        "model_key": model_key,
        "verdict": verdict,
        "report_status": report_status,
        "reason": reason,
        "test_log_sha256": test_log,
        "duration_seconds": run["duration_seconds"],
        "mtime_utc": stamp,
        "scored": report_status == "VALID",
        "scoring_policy": "scored",
        "raw_log_present": True,
        "raw_log_note": "verifier/report.json (aggregate-v1), reward.txt and test-stdout.txt are the container-produced originals.",
        "cases": cases,
    }
    (record_dir / "verifier" / "result.json").write_text(
        json.dumps(result_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return job


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-path", type=Path, required=True)
    ap.add_argument("--jobs-root", type=Path, required=True)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--only-agent", default=None)
    args = ap.parse_args()

    task_path = args.task_path.resolve()
    cfg = tomllib.loads((task_path / "task.toml").read_text(encoding="utf-8"))
    task_id = cfg["task"]["id"]
    task_version = cfg["task"]["version"]
    harness = harbor_version()
    args.jobs_root.mkdir(parents=True, exist_ok=True)

    summary = {"task_id": task_id, "task_version": task_version, "harness": harness,
               "task_path": str(task_path), "jobs": []}
    for agent, mode, role, model_key, label in PLAN:
        if args.only_agent and agent != args.only_agent:
            continue
        for attempt in range(1, args.attempts + 1):
            stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
            job_id = f"{stamp}-{mode}-{label}-{attempt:02d}"
            run = run_trial(task_path, agent, job_id, args.jobs_root)
            job = write_record(task_path, task_id, task_version, agent, mode, role,
                               model_key, label, attempt, job_id, run, harness)
            summary["jobs"].append(job)
            print(f"{job_id} status={job['report_status']} verdict={job['verdict']} "
                  f"exit={run['exit_code']} {job['duration_seconds']}s", flush=True)
            (args.jobs_root / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if job["report_status"] != "VALID":
                print(f"  -> stopping {agent} after {job['report_status']}", flush=True)
                break
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
