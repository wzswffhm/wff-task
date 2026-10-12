# -*- coding: utf-8 -*-
"""归档第五轮判分并重建 summary.json。"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = "FIN3-WKN-150"
BATCH = "work_fin-b01_20261006_fix7-150"
TD = REPO / "harbor-weakness" / BATCH / TASK
REJUDGE = REPO / "harbor-weakness" / TASK / "_rejudge"
ARC = TD / "跑分产物与轨迹"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
G5 = EXECUTORS[1:]
PREV = {
    "oracle": 1.0,
    "qwen3.8-max-0902": 0.765909,
    "claude-opus-4-8": 0.573864,
    "gpt-5.6-sol": 0.654545,
}
PREV_ROUND = "fix6(qc3-remediation)+rejudged(2026-10-10 archived)"
NEW_ROUND = "fix7(exit-assumption-remediation)+rejudge"


def write_lf(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def read_reward(executor: str) -> tuple[dict | None, str]:
    path = REJUDGE / executor / "verifier" / "reward.json"
    if not path.is_file():
        return None, f"missing {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    error = path.parent / "reward_exit_message.json"
    if error.is_file():
        return None, f"{executor} incomplete: {error.read_text(encoding='utf-8')[:90]}"
    if float(data.get("criteria_counted") or 0) < 1:
        return None, f"{executor} criteria_counted=0"
    return data, ""


def find_details(executor: str) -> pathlib.Path | None:
    base = REJUDGE / executor / "verifier"
    for candidate in (base / "graded" / "reward.json", base / "reward-details.json",
                      base / "graded" / "reward-details.json"):
        if candidate.is_file() and candidate.stat().st_size > 1000:
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    results: dict[str, dict] = {}
    errors: list[str] = []
    for executor in EXECUTORS:
        data, error = read_reward(executor)
        if data:
            results[executor] = data
        else:
            errors.append(error)
    print("=== current results ===")
    for executor in EXECUTORS:
        data = results.get(executor)
        print(f"  {executor:20} "
              f"reward={data.get('reward') if data else None} "
              f"counted={data.get('criteria_counted') if data else None} "
              f"err={data.get('verifier_error') if data else None}")
    if errors:
        print("incomplete:")
        for error in errors:
            print(" ", error)
        return 1

    g5 = [float(results[executor]["reward"]) for executor in G5]
    mean = round(sum(g5) / len(g5), 6)
    print(f"mean={mean} oracle={results['oracle']['reward']}")
    print(f"gates: oracle>0.85={float(results['oracle']['reward']) > 0.85} "
          f"mean<0.70={mean < 0.70} non-zero={all(value > 0 for value in g5)}")

    summary = json.loads((ARC / "summary.json").read_text(encoding="utf-8"))
    for run in summary["runs"]:
        data = results[run["model"]]
        run["reward"] = float(data["reward"])
        run["verifier_error"] = float(data.get("verifier_error") or 0)
        run["criteria_counted"] = float(data.get("criteria_counted") or 36)
        run["scored"] = True
    summary["task_version"] = "1.0.7"
    summary["round"] = NEW_ROUND
    summary["mean"] = mean
    summary["mean_gate"] = "<0.70"
    summary["any_model_scored"] = all(float(results[executor]["reward"]) > 0 for executor in G5)
    summary["declared_difficulty"] = "A1"
    summary["gate_pass"] = bool(float(results["oracle"]["reward"]) > 0.85 and mean < 0.70
                                and summary["any_model_scored"])

    previous = [{
        "round": PREV_ROUND,
        "executor": executor,
        "reward": PREV[executor],
        "criteria_counted": 36.0,
        "verifier_error": 0.0,
        "reason": "R27 退出回报口径改为信息不足结论/条件分析、金标退出段修订后作废；"
                  "按复检报告（2026-10-10，序号 239）第 2/3 条重跑四执行体",
    } for executor in EXECUTORS]
    summary["invalid_runs"] = previous + summary.get("invalid_runs", [])

    print(f"summary: version={summary['task_version']} round={summary['round']} "
          f"mean={summary['mean']} gate={summary['gate_pass']} "
          f"invalid_runs={len(summary['invalid_runs'])}")
    if args.check and not args.apply:
        print("CHECK only")
        return 0
    if not args.apply:
        print("add --apply to write")
        return 0

    for executor in EXECUTORS:
        data = results[executor]
        output = {
            "reward": float(data["reward"]),
            "graded_score": float(data.get("graded_score") or data["reward"]),
            "criteria_counted": float(data.get("criteria_counted") or 36),
            "verifier_error": float(data.get("verifier_error") or 0),
        }
        details = find_details(executor)
        if details:
            shutil.copy2(details, ARC / executor / "reward-details.json")
        write_lf(ARC / executor / "reward.json",
                 json.dumps(output, ensure_ascii=False, indent=2) + "\n")
        print(f"archived {executor}: reward-details={'yes' if details else 'no'}")
    write_lf(ARC / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print("summary.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
