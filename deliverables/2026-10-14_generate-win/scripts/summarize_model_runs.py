#!/usr/bin/env python3
"""Summarize and qualify Windows Harbor runner result.json files."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_MODELS = {"QWEN": 3, "OPUS": 3, "GLM": 1, "KIMI": 1}


def parse_after(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.datetime.now().astimezone().tzinfo)
    return parsed.astimezone(dt.timezone.utc)


def load_result(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    data["result_path"] = str(path.resolve())
    data["run_id"] = path.parent.parent.name
    data["run_label"] = path.parent.name
    data["mtime_utc"] = dt.datetime.fromtimestamp(
        path.stat().st_mtime, tz=dt.timezone.utc
    ).isoformat()
    test_log = path.parent / "test.log"
    if test_log.exists():
        data["test_log_sha256"] = hashlib.sha256(test_log.read_bytes()).hexdigest()
    return data


def compact(item: dict[str, Any]) -> dict[str, Any]:
    agent = item.get("agent") or {}
    report = ((item.get("test") or {}).get("report") or {})
    return {
        "run_id": item.get("run_id"),
        "run_label": item.get("run_label"),
        "result_path": item.get("result_path"),
        "model": item.get("model_alias"),
        "mode": item.get("mode"),
        "verdict": item.get("verdict"),
        "report_status": report.get("status"),
        "reason": item.get("reason"),
        "duration_seconds": item.get("duration_seconds"),
        "agent_status": agent.get("status"),
        "turns": agent.get("turns"),
        "test_log_sha256": item.get("test_log_sha256"),
        "mtime_utc": item.get("mtime_utc"),
    }


def valid_scored_result(item: dict[str, Any]) -> bool:
    """Accept only a completed verifier report whose score is self-consistent."""
    report = ((item.get("test") or {}).get("report") or {})
    verdict = item.get("verdict")
    return (
        str(report.get("status", "")).upper() == "VALID"
        and verdict in (0, 1)
        and report.get("score") == verdict
        and report.get("task_id") == item.get("task_id")
        and report.get("task_version") == item.get("task_version")
        and bool(item.get("test_log_sha256"))
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--after", help="Qualification epoch as ISO-8601 timestamp")
    parser.add_argument("--control-runs", type=int, default=3)
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.workspace_root).resolve()
    run_root = root / "runs" / args.task_id
    after = parse_after(args.after)
    loaded: list[dict[str, Any]] = []
    if run_root.exists():
        for path in run_root.glob("*/*/result.json"):
            if after:
                mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)
                if mtime < after:
                    continue
            item = load_result(path)
            if item and item.get("task_id") == args.task_id:
                loaded.append(item)
    loaded.sort(key=lambda item: item.get("mtime_utc", ""))

    no_change = [item for item in loaded if item.get("mode") == "no-change"]
    golden = [item for item in loaded if item.get("mode") == "golden"]
    candidates = [item for item in loaded if item.get("mode") == "candidate"]

    selected_no_change = [item for item in no_change if valid_scored_result(item)][-args.control_runs :]
    selected_golden = [item for item in golden if valid_scored_result(item)][-args.control_runs :]
    controls_ok = (
        len(selected_no_change) == args.control_runs
        and all(item.get("verdict") == 0 for item in selected_no_change)
        and len(selected_golden) == args.control_runs
        and all(item.get("verdict") == 1 for item in selected_golden)
    )

    model_summary: dict[str, Any] = {}
    models_ok = True
    for model, required in REQUIRED_MODELS.items():
        attempts = [item for item in candidates if str(item.get("model_alias", "")).upper() == model]
        valid = [item for item in attempts if valid_scored_result(item)]
        selected = valid[-required:]
        enough = len(selected) == required
        models_ok = models_ok and enough
        model_summary[model] = {
            "required": required,
            "valid_count": len(valid),
            "attempt_count": len(attempts),
            "selected": [compact(item) for item in selected],
            "scores": [item.get("verdict") for item in selected],
            "score_sum": sum(int(item.get("verdict")) for item in selected),
            "invalid_attempts": [compact(item) for item in attempts if item.get("verdict") == "INVALID"],
            "complete": enough,
        }

    differentiation_ok = (
        model_summary["OPUS"]["complete"]
        and model_summary["QWEN"]["complete"]
        and model_summary["OPUS"]["score_sum"] > model_summary["QWEN"]["score_sum"]
    )
    task_versions = sorted({str(item.get("task_version")) for item in loaded if item.get("task_version")})
    version_consistent = len(task_versions) <= 1
    qualified = controls_ok and models_ok and differentiation_ok and version_consistent

    result = {
        "generated_at": dt.datetime.now().astimezone().isoformat(),
        "workspace_root": str(root),
        "task_id": args.task_id,
        "task_versions": task_versions,
        "qualification_epoch": args.after,
        "controls": {
            "required_each": args.control_runs,
            "no_change": [compact(item) for item in selected_no_change],
            "golden": [compact(item) for item in selected_golden],
            "passed": controls_ok,
        },
        "models": model_summary,
        "gates": {
            "controls_passed": controls_ok,
            "model_counts_complete": models_ok,
            "opus_sum_greater_than_qwen": differentiation_ok,
            "task_version_consistent": version_consistent,
            "qualified": qualified,
        },
    }
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0 if qualified else 2


if __name__ == "__main__":
    raise SystemExit(main())
