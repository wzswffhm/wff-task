#!/usr/bin/env python3
"""Launch the Seed monitor in a detached background process and return immediately."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=Path("model.env"))
    parser.add_argument("--model", default="doubao-seed-evolving")
    parser.add_argument("--reasoning-effort", default="minimal")
    parser.add_argument("--max-turns", type=int, default=120)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    parser.add_argument("--target-no-skill-min-turns", type=int, default=101)
    parser.add_argument("--target-with-skill-turns", type=int, default=70)
    parser.add_argument("--target-with-skill-tolerance", type=int, default=10)
    parser.add_argument("--accepted-no-skill-result", type=Path)
    parser.add_argument("--benchmark", default="deepSWE")
    parser.add_argument(
        "--finalize-on-pass",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--final-output-dir", type=Path)
    parser.add_argument("--delivery-zip", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def monitor_command(args: argparse.Namespace) -> List[str]:
    monitor = Path(__file__).with_name("monitor_seed_experiment.py")
    command = [
        sys.executable,
        str(monitor),
        "--task-dir",
        str(args.task_dir),
        "--run-root",
        str(args.run_root),
        "--env-file",
        str(args.env_file),
        "--model",
        args.model,
        "--reasoning-effort",
        args.reasoning_effort,
        "--max-turns",
        str(args.max_turns),
        "--max-tokens",
        str(args.max_tokens),
        "--docker",
        args.docker,
        "--poll-seconds",
        str(args.poll_seconds),
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--target-no-skill-min-turns",
        str(args.target_no_skill_min_turns),
        "--target-with-skill-turns",
        str(args.target_with_skill_turns),
        "--target-with-skill-tolerance",
        str(args.target_with_skill_tolerance),
        "--benchmark",
        args.benchmark,
        "--finalize-on-pass" if args.finalize_on_pass else "--no-finalize-on-pass",
    ]
    if args.accepted_no_skill_result:
        command.extend(
            ["--accepted-no-skill-result", str(args.accepted_no_skill_result)]
        )
    if args.final_output_dir:
        command.extend(["--final-output-dir", str(args.final_output_dir)])
    if args.delivery_zip:
        command.extend(["--delivery-zip", str(args.delivery_zip)])
    return command


def main() -> int:
    args = build_parser().parse_args()
    args.task_dir = args.task_dir.expanduser().resolve()
    args.run_root = args.run_root.expanduser().resolve()
    args.env_file = args.env_file.expanduser().resolve()
    if args.accepted_no_skill_result:
        args.accepted_no_skill_result = args.accepted_no_skill_result.expanduser().resolve()
    if args.final_output_dir:
        args.final_output_dir = args.final_output_dir.expanduser().resolve()
    if args.delivery_zip:
        args.delivery_zip = args.delivery_zip.expanduser().resolve()

    background_state = args.run_root / "BACKGROUND_RUN.json"
    log_path = args.run_root / "BACKGROUND_MONITOR.log"
    if not (args.run_root / "BASELINE.json").is_file():
        raise SystemExit(f"缺少 BASELINE.json：{args.run_root / 'BASELINE.json'}")
    if not args.task_dir.is_dir():
        raise SystemExit(f"题包目录不存在：{args.task_dir}")
    if not args.env_file.is_file():
        raise SystemExit(f"模型配置不存在：{args.env_file}")
    if not args.dry_run and (background_state.exists() or log_path.exists()):
        raise SystemExit("该实验目录已有后台启动记录或日志，拒绝重复启动")
    if not args.dry_run and (args.run_root / "EXPERIMENT_RESULT.json").exists():
        raise SystemExit("该实验目录已有结果，拒绝重复启动")

    command = monitor_command(args)
    status_command = [
        sys.executable,
        str(Path(__file__).with_name("inspect_seed_status.py")),
        "--run-root",
        str(args.run_root),
    ]
    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "command": command,
                    "monitor_log": str(log_path),
                    "background_state": str(background_state),
                    "status_command": status_command,
                    "codex_heartbeat_recommended_minutes": 5,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    with log_path.open("x", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    payload = {
        "status": "running",
        "started_at": utc_now(),
        "pid": process.pid,
        "task_dir": str(args.task_dir),
        "run_root": str(args.run_root),
        "monitor_log": str(log_path),
        "command": command,
        "status_command": status_command,
        "codex_heartbeat_recommended_minutes": 5,
    }
    try:
        write_json_atomic(background_state, payload)
    except OSError:
        try:
            os.killpg(process.pid, 15)
        except OSError:
            process.terminate()
        raise
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
