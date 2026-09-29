#!/usr/bin/env python3
"""Run final QC, render the dashboard, and build the formal delivery ZIP."""

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


def run(command: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True)


def combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout + result.stderr).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--delivery-zip", type=Path)
    parser.add_argument("--benchmark", default="deepSWE")
    args = parser.parse_args()

    task = args.task_dir.expanduser().resolve()
    run_root = args.run_root.expanduser().resolve()
    experiment = run_root / "EXPERIMENT_RESULT.json"
    turn_stats = run_root / "TURN_STATS.json"
    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else run_root.parent / "final-check"
    )
    delivery_zip = (
        args.delivery_zip.expanduser().resolve()
        if args.delivery_zip
        else task.parent / f"{task.name}.zip"
    )
    result_path = run_root / "FINALIZATION_RESULT.json"

    if result_path.exists():
        raise SystemExit(f"最终收尾结果已存在，拒绝重复执行：{result_path}")
    if not task.is_dir():
        raise SystemExit(f"正式题包目录不存在：{task}")
    for required in (experiment, turn_stats):
        if not required.is_file():
            raise SystemExit(f"缺少最终收尾输入：{required}")
    expected_outputs = [
        output_dir / "FINAL_CHECK.txt",
        output_dir / "FINAL_CHECK.json",
        output_dir / "FINAL_CHECK.png",
        delivery_zip,
    ]
    existing = [str(path) for path in expected_outputs if path.exists()]
    if existing:
        raise SystemExit("最终收尾输出已存在，拒绝覆盖：\n" + "\n".join(existing))

    scripts = Path(__file__).resolve().parent
    capture_command = [
        sys.executable,
        str(scripts / "capture_final_check.py"),
        "--task-dir",
        str(task),
        "--experiment-result",
        str(experiment),
        "--output-dir",
        str(output_dir),
        "--benchmark",
        args.benchmark,
    ]
    capture = run(capture_command)
    payload: Dict[str, Any] = {
        "status": "running",
        "generated_at": utc_now(),
        "task_dir": str(task),
        "run_root": str(run_root),
        "experiment_result": str(experiment),
        "turn_stats": str(turn_stats),
        "final_check_dir": str(output_dir),
        "delivery_zip": str(delivery_zip),
        "capture": {
            "command": capture_command,
            "returncode": capture.returncode,
            "output": combined_output(capture),
        },
    }
    if capture.returncode != 0:
        payload["status"] = "final_check_failed"
        payload["completed_at"] = utc_now()
        write_json_atomic(result_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    final_check = output_dir / "FINAL_CHECK.json"
    package_command = [
        sys.executable,
        str(scripts / "build_delivery_zip.py"),
        "--task-dir",
        str(task),
        "--experiment-result",
        str(experiment),
        "--turn-stats",
        str(turn_stats),
        "--final-check",
        str(final_check),
        "--output",
        str(delivery_zip),
        "--benchmark",
        args.benchmark,
    ]
    package = run(package_command)
    payload["package"] = {
        "command": package_command,
        "returncode": package.returncode,
        "output": combined_output(package),
    }
    payload["status"] = "passed" if package.returncode == 0 else "package_failed"
    payload["completed_at"] = utc_now()
    write_json_atomic(result_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if package.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
