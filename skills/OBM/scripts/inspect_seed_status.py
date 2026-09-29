#!/usr/bin/env python3
"""Print a compact Seed background status for low-token scheduled checks."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


TERMINAL_EXPERIMENT_STATES = {
    "needs_task_hardening",
    "needs_skill_revision",
    "infrastructure_error",
}
TERMINAL_FINALIZATION_STATES = {
    "passed",
    "final_check_failed",
    "package_failed",
}


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def process_alive(pid: Any) -> bool:
    try:
        numeric = int(pid)
        if numeric <= 0:
            return False
        os.kill(numeric, 0)
    except PermissionError:
        return True
    except (TypeError, ValueError, ProcessLookupError, OSError):
        return False
    return True


def mode_turns(run_root: Path, mode: str) -> int:
    output = run_root / mode / "seed-output"
    api_run = read_json(output / "API_RUN.json") or {}
    progress = read_json(output / "PROGRESS.json") or {}
    return int(api_run.get("turns", progress.get("turns", 0)) or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    run_root = args.run_root.expanduser().resolve()

    background = read_json(run_root / "BACKGROUND_RUN.json") or {}
    progress = read_json(run_root / "EXPERIMENT_PROGRESS.json") or {}
    experiment = read_json(run_root / "EXPERIMENT_RESULT.json") or {}
    monitor = read_json(run_root / "MONITOR_RESULT.json") or {}
    finalization = read_json(run_root / "FINALIZATION_RESULT.json") or {}
    alive = process_alive(background.get("pid"))

    monitor_status = monitor.get("status")
    experiment_status = experiment.get("status")
    finalization_status = finalization.get("status")
    terminal = False
    status = "running"
    if monitor_status in {"passed", "infrastructure_error"}:
        terminal = True
        status = str(monitor_status)
    elif finalization_status in TERMINAL_FINALIZATION_STATES:
        terminal = True
        status = str(finalization_status)
    elif experiment_status in TERMINAL_EXPERIMENT_STATES:
        terminal = True
        status = str(experiment_status)
    elif experiment_status == "passed":
        status = "finalizing" if alive else "passed_without_monitor_result"
        terminal = not alive
    elif not alive and background:
        terminal = True
        status = "background_process_exited"
    elif not background:
        terminal = True
        status = "background_run_missing"

    no_skill = experiment.get("no_skill", {})
    with_skill = experiment.get("with_skill", {})
    payload = {
        "terminal": terminal,
        "status": status,
        "stage": progress.get("stage", "starting"),
        "process_alive": alive,
        "pid": background.get("pid"),
        "experiment_status": experiment_status,
        "monitor_status": monitor_status,
        "finalization_status": finalization_status,
        "rewards": {
            "no_skill": no_skill.get("reward") if isinstance(no_skill, dict) else None,
            "with_skill": with_skill.get("reward") if isinstance(with_skill, dict) else None,
        },
        "turns": {
            "no_skill": mode_turns(run_root, "no-skill"),
            "with_skill": mode_turns(run_root, "with-skill"),
        },
        "result_paths": {
            "experiment": str(run_root / "EXPERIMENT_RESULT.json"),
            "turn_stats": str(run_root / "TURN_STATS.json"),
            "monitor": str(run_root / "MONITOR_RESULT.json"),
            "finalization": str(run_root / "FINALIZATION_RESULT.json"),
            "background_log": str(run_root / "BACKGROUND_MONITOR.log"),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
