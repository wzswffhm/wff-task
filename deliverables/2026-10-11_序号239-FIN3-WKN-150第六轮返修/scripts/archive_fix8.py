# -*- coding: utf-8 -*-
"""归档第六轮 Oracle 重判结果并重建 summary.json。

本轮只重判 Oracle（判据语义未变，三模型按质检报告第 4 项沿用 fix7 归档值）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = "FIN3-WKN-150"
BATCH = "work_fin-b01_20261006_fix8-150"
TD = REPO / "harbor-weakness" / BATCH / TASK
REJUDGE = REPO / "harbor-weakness" / TASK / "_rejudge_fix8"
ARC = TD / "跑分产物与轨迹"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
G5 = EXECUTORS[1:]
NEW_ROUND = "fix8(reference-generation-closure)+rejudge"
PREV_ROUND = "fix7(exit-assumption-remediation)+rejudged(2026-10-11 archived)"
PREV = {
    "oracle": 1.0,
    "qwen3.8-max-0902": 0.731818,
    "claude-opus-4-8": 0.534091,
    "gpt-5.6-sol": 0.686364,
}


def write_lf(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def read_oracle() -> tuple[dict | None, str]:
    path = REJUDGE / "oracle" / "verifier" / "reward.json"
    if not path.is_file():
        return None, f"missing {path}"
    if (path.parent / "reward_exit_message.json").is_file():
        return None, "oracle incomplete: " + (path.parent / "reward_exit_message.json").read_text(
            encoding="utf-8")[:120]
    data = json.loads(path.read_text(encoding="utf-8"))
    if float(data.get("criteria_counted") or 0) < 1:
        return None, "oracle criteria_counted=0"
    return data, ""


def find_details() -> pathlib.Path | None:
    base = REJUDGE / "oracle" / "verifier"
    for candidate in (base / "reward-details.json", base / "graded" / "reward-details.json",
                      base / "graded" / "reward.json"):
        if candidate.is_file() and candidate.stat().st_size > 1000:
            return candidate
    return None


def read_archived(executor: str) -> dict:
    return json.loads((ARC / executor / "reward.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    oracle, error = read_oracle()
    if oracle is None:
        print("oracle 判分未就绪:", error)
        return 1

    results: dict[str, dict] = {"oracle": oracle}
    for executor in G5:
        results[executor] = read_archived(executor)
    print("=== current results ===")
    for executor in EXECUTORS:
        data = results[executor]
        print(f"  {executor:20} reward={data.get('reward')} "
              f"counted={data.get('criteria_counted')} err={data.get('verifier_error')}")

    g5 = [float(results[executor]["reward"]) for executor in G5]
    mean = round(sum(g5) / len(g5), 6)
    oracle_reward = float(oracle["reward"])
    print(f"mean={mean} oracle={oracle_reward}")
    print(f"gates: oracle>0.85={oracle_reward > 0.85} mean<0.70={mean < 0.70} "
          f"non-zero={all(value > 0 for value in g5)}")

    summary = json.loads((ARC / "summary.json").read_text(encoding="utf-8"))
    for run in summary["runs"]:
        data = results[run["model"]]
        run["reward"] = float(data["reward"])
        run["verifier_error"] = float(data.get("verifier_error") or 0)
        run["criteria_counted"] = float(data.get("criteria_counted") or 36)
        run["scored"] = True
    summary["task_version"] = "1.0.8"
    summary["round"] = NEW_ROUND
    summary["mean"] = mean
    summary["mean_gate"] = "<0.70"
    summary["any_model_scored"] = all(float(results[e]["reward"]) > 0 for e in G5)
    summary["declared_difficulty"] = "A1"
    summary["gate_pass"] = bool(oracle_reward > 0.85 and mean < 0.70 and summary["any_model_scored"])

    previous = [{
        "round": PREV_ROUND,
        "executor": executor,
        "reward": PREV[executor],
        "criteria_counted": 36.0,
        "verifier_error": 0.0,
        "reason": "参考实现（reproduce.py 字符串插值）与两份 golden 备忘录修订、"
                  "tests/rubrics.toml 补 [scoring] 等价配置后作废；按质检报告"
                  "（序号 239，快照 20261011_112005）第 5/6 项重新生成 Oracle 产物并重判",
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

    details = find_details()
    if details:
        shutil.copy2(details, ARC / "oracle" / "reward-details.json")
    write_lf(ARC / "oracle" / "reward.json", json.dumps({
        "reward": oracle_reward,
        "graded_score": float(oracle.get("graded_score") or oracle_reward),
        "criteria_counted": float(oracle.get("criteria_counted") or 36),
        "verifier_error": float(oracle.get("verifier_error") or 0),
    }, ensure_ascii=False, indent=2) + "\n")
    write_lf(ARC / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(f"archived oracle: reward-details={'yes' if details else 'no'}")
    print("summary.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
