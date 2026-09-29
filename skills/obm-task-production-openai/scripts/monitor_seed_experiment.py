#!/usr/bin/env python3
"""Launch a Seed experiment and poll artifacts until the strict result is known."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


INFRASTRUCTURE_ERROR = 22


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def transcript_turns(path: Path) -> int:
    maximum = 0
    if not path.is_file():
        return maximum
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event.get("event") == "assistant":
                    maximum = max(maximum, int(event.get("turn", 0)))
    except OSError:
        return maximum
    return maximum


def mode_snapshot(run_root: Path, mode: str) -> Dict[str, Any]:
    output = run_root / mode / "seed-output"
    progress = read_json(output / "PROGRESS.json") or {}
    api_run = read_json(output / "API_RUN.json") or {}
    verification = read_json(run_root / mode / "verification/VERIFICATION.json") or {}
    turns = int(api_run.get("turns", progress.get("turns", 0)) or 0)
    if turns == 0:
        turns = transcript_turns(output / "TRANSCRIPT.jsonl")
    return {
        "status": api_run.get("status") or progress.get("status") or "pending",
        "turns": turns,
        "tool_calls": int(api_run.get("tool_calls", progress.get("tool_calls", 0)) or 0),
        "last_event": progress.get("last_event"),
        "last_tool": progress.get("last_tool"),
        "duration_seconds": api_run.get("duration_seconds", progress.get("duration_seconds")),
        "reward": verification.get("reward"),
        "verification_status": verification.get("status"),
    }


def docker_available(docker: str) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            [docker, "info", "--format", "{{json .ServerVersion}}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": "{}: {}".format(type(exc).__name__, exc)}
    version = result.stdout.strip() if result.returncode == 0 else None
    if version:
        try:
            version = json.loads(version)
        except json.JSONDecodeError:
            pass
    return {
        "ok": result.returncode == 0,
        "server_version": version,
        "error": result.stderr.strip()[-1000:] if result.returncode != 0 else None,
    }


def experiment_command(args: argparse.Namespace) -> List[str]:
    runner = Path(__file__).with_name("run_seed_experiment.py")
    command = [
        sys.executable,
        str(runner),
        "--task-dir", str(args.task_dir),
        "--run-root", str(args.run_root),
        "--env-file", str(args.env_file),
        "--model", args.model,
        "--reasoning-effort", args.reasoning_effort,
        "--max-turns", str(args.max_turns),
        "--max-tokens", str(args.max_tokens),
        "--docker", args.docker,
        "--target-no-skill-min-turns", str(args.target_no_skill_min_turns),
        "--target-with-skill-turns", str(args.target_with_skill_turns),
        "--target-with-skill-tolerance", str(args.target_with_skill_tolerance),
    ]
    if args.accepted_no_skill_result:
        command.extend(["--accepted-no-skill-result", str(args.accepted_no_skill_result)])
    return command


def finalization_command(args: argparse.Namespace) -> List[str]:
    finalizer = Path(__file__).with_name("finalize_seed_delivery.py")
    command = [
        sys.executable,
        str(finalizer),
        "--task-dir", str(args.task_dir),
        "--run-root", str(args.run_root),
        "--benchmark", args.benchmark,
    ]
    if args.final_output_dir:
        command.extend(["--output-dir", str(args.final_output_dir)])
    if args.delivery_zip:
        command.extend(["--delivery-zip", str(args.delivery_zip)])
    return command


def build_snapshot(run_root: Path, started: float, child_status: str) -> Dict[str, Any]:
    progress = read_json(run_root / "EXPERIMENT_PROGRESS.json") or {}
    result = read_json(run_root / "EXPERIMENT_RESULT.json")
    return {
        "observed_at": utc_now(),
        "elapsed_seconds": round(time.time() - started, 3),
        "child_status": child_status,
        "stage": progress.get("stage", "starting"),
        "experiment_status": (result or {}).get("status") or progress.get("status") or "running",
        "no_skill": mode_snapshot(run_root, "no-skill"),
        "with_skill": mode_snapshot(run_root, "with-skill"),
    }


def turn_stats(
    result: Optional[Dict[str, Any]],
    final_snapshot: Dict[str, Any],
    args: argparse.Namespace,
    child_returncode: int,
    timed_out: bool,
) -> Dict[str, Any]:
    no_result = (result or {}).get("no_skill") or {}
    with_result = (result or {}).get("with_skill") or {}
    no_agent = no_result.get("agent") or {}
    with_agent = with_result.get("agent") or {}
    no_turns = int(no_agent.get("turns", final_snapshot["no_skill"].get("turns", 0)) or 0)
    with_turns = int(with_agent.get("turns", final_snapshot["with_skill"].get("turns", 0)) or 0)
    no_reward = normalized_reward(no_result.get("reward"))
    with_reward = normalized_reward(with_result.get("reward"))
    lower = max(1, args.target_with_skill_turns - args.target_with_skill_tolerance)
    upper = args.target_with_skill_turns + args.target_with_skill_tolerance
    no_preference = no_turns >= args.target_no_skill_min_turns
    with_preference = lower <= with_turns <= upper
    strict_pair = no_reward == 0 and with_reward == 1
    warnings: List[str] = []
    if no_reward is not None and not no_preference:
        warnings.append(
            "no-skill 轮次低于偏好目标 {}，应检查题目是否过快暴露关键路径".format(
                args.target_no_skill_min_turns
            )
        )
    if with_reward is not None and not with_preference:
        warnings.append(
            "with-skill 轮次不在偏好区间 {}-{}，仅作为调优信号".format(lower, upper)
        )
    if not strict_pair:
        warnings.append("硬验收未满足：必须是 no-skill reward=0 且 with-skill reward=1")
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "experiment_status": (result or {}).get("status"),
        "child_returncode": child_returncode,
        "timed_out": timed_out,
        "strict_acceptance": {
            "required": True,
            "no_skill_reward": no_reward,
            "with_skill_reward": with_reward,
            "passed": strict_pair and (result or {}).get("status") == "passed" and child_returncode == 0,
        },
        "turns": {
            "no_skill": no_turns,
            "with_skill": with_turns,
        },
        "turn_preferences": {
            "required": False,
            "no_skill": {
                "preferred_minimum": args.target_no_skill_min_turns,
                "met": no_preference,
            },
            "with_skill": {
                "preferred": args.target_with_skill_turns,
                "tolerance": args.target_with_skill_tolerance,
                "range": [lower, upper],
                "met": with_preference,
            },
        },
        "warnings": warnings,
        "final_snapshot": final_snapshot,
    }


def normalized_reward(value: Any) -> Optional[int]:
    try:
        reward = int(value)
    except (TypeError, ValueError):
        return None
    return reward if reward in (0, 1) else None


def terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        process.terminate()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            process.kill()
        process.wait(timeout=10)


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
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=0,
        help="0 means wait without a monitor-imposed deadline",
    )
    parser.add_argument("--target-no-skill-min-turns", type=int, default=101)
    parser.add_argument("--target-with-skill-turns", type=int, default=70)
    parser.add_argument("--target-with-skill-tolerance", type=int, default=10)
    parser.add_argument("--accepted-no-skill-result", type=Path)
    parser.add_argument("--benchmark", default="deepSWE")
    parser.add_argument(
        "--finalize-on-pass",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="after strict Seed pass, run final QC, render PNG, and build the ZIP",
    )
    parser.add_argument("--final-output-dir", type=Path)
    parser.add_argument("--delivery-zip", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser


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
    if not (args.run_root / "BASELINE.json").is_file():
        raise SystemExit("缺少 BASELINE.json：{}".format(args.run_root / "BASELINE.json"))
    if not args.task_dir.is_dir():
        raise SystemExit("题包目录不存在：{}".format(args.task_dir))
    if not args.env_file.is_file():
        raise SystemExit("模型配置不存在：{}".format(args.env_file))
    if args.poll_seconds < 1 or args.timeout_seconds < 0:
        raise SystemExit("poll-seconds 必须大于 0，timeout-seconds 不能为负数")
    if args.max_turns < args.target_no_skill_min_turns:
        raise SystemExit("max-turns 必须不小于 no-skill 偏好最小轮次")

    docker = docker_available(args.docker)
    if not docker["ok"]:
        write_json_atomic(
            args.run_root / "MONITOR_RESULT.json",
            {
                "status": "infrastructure_error",
                "reason": "docker_unavailable",
                "docker": docker,
                "generated_at": utc_now(),
            },
        )
        print("Docker 不可用：{}".format(docker.get("error")), file=sys.stderr)
        return INFRASTRUCTURE_ERROR
    command = experiment_command(args)
    if args.dry_run:
        print(json.dumps({
            "dry_run": True,
            "docker": docker,
            "command": command,
            "turn_preferences": {
                "no_skill_minimum": args.target_no_skill_min_turns,
                "with_skill_preferred": args.target_with_skill_turns,
                "with_skill_tolerance": args.target_with_skill_tolerance,
            },
            "finalize_on_pass": args.finalize_on_pass,
            "finalization_command": finalization_command(args),
        }, ensure_ascii=False, indent=2))
        return 0
    if (args.run_root / "EXPERIMENT_RESULT.json").exists():
        raise SystemExit("该实验目录已有结果，拒绝覆盖；请创建新的版本化尝试目录")

    monitor_log = args.run_root / "MONITOR_STATUS.jsonl"
    experiment_log = args.run_root / "SEED_EXPERIMENT.log"
    started = time.time()
    timed_out = False
    with experiment_log.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            text=True,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            while process.poll() is None:
                snapshot = build_snapshot(args.run_root, started, "running")
                append_jsonl(monitor_log, snapshot)
                print(
                    "[{observed_at}] stage={stage} elapsed={elapsed_seconds}s "
                    "no-skill={no_turns}轮 with-skill={with_turns}轮".format(
                        observed_at=snapshot["observed_at"],
                        stage=snapshot["stage"],
                        elapsed_seconds=snapshot["elapsed_seconds"],
                        no_turns=snapshot["no_skill"]["turns"],
                        with_turns=snapshot["with_skill"]["turns"],
                    ),
                    flush=True,
                )
                if args.timeout_seconds and time.time() - started >= args.timeout_seconds:
                    timed_out = True
                    terminate_process(process)
                    break
                try:
                    process.wait(timeout=args.poll_seconds)
                except subprocess.TimeoutExpired:
                    pass
        except KeyboardInterrupt:
            terminate_process(process)
            raise
    child_returncode = process.returncode if process.returncode is not None else INFRASTRUCTURE_ERROR
    final_snapshot = build_snapshot(args.run_root, started, "finished")
    append_jsonl(monitor_log, final_snapshot)
    result = read_json(args.run_root / "EXPERIMENT_RESULT.json")
    stats = turn_stats(result, final_snapshot, args, child_returncode, timed_out)
    write_json_atomic(args.run_root / "TURN_STATS.json", stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if timed_out or result is None:
        write_json_atomic(
            args.run_root / "MONITOR_RESULT.json",
            {
                "status": "infrastructure_error",
                "reason": "monitor_timeout" if timed_out else "experiment_result_missing",
                "child_returncode": child_returncode,
                "generated_at": utc_now(),
            },
        )
        return INFRASTRUCTURE_ERROR
    if result.get("status") == "passed" and not stats["strict_acceptance"]["passed"]:
        return INFRASTRUCTURE_ERROR
    if child_returncode == 0 and stats["strict_acceptance"]["passed"] and args.finalize_on_pass:
        command = finalization_command(args)
        finalized = subprocess.run(command, text=True, capture_output=True)
        if finalized.stdout:
            print(finalized.stdout, end="" if finalized.stdout.endswith("\n") else "\n")
        if finalized.stderr:
            print(finalized.stderr, file=sys.stderr, end="" if finalized.stderr.endswith("\n") else "\n")
        if finalized.returncode != 0:
            write_json_atomic(
                args.run_root / "MONITOR_RESULT.json",
                {
                    "status": "infrastructure_error",
                    "reason": "finalization_failed",
                    "child_returncode": child_returncode,
                    "finalization_returncode": finalized.returncode,
                    "finalization_command": command,
                    "generated_at": utc_now(),
                },
            )
            return INFRASTRUCTURE_ERROR
        write_json_atomic(
            args.run_root / "MONITOR_RESULT.json",
            {
                "status": "passed",
                "child_returncode": child_returncode,
                "finalization_returncode": finalized.returncode,
                "finalization_result": str(args.run_root / "FINALIZATION_RESULT.json"),
                "generated_at": utc_now(),
            },
        )
    return child_returncode


if __name__ == "__main__":
    raise SystemExit(main())
