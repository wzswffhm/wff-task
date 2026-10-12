"""Validate the Windows bench model-discrimination gate from local evidence.

Input is JSON with qwen/opus/glm/kimi arrays. Each run must contain
validity, binary score, and testcase cases with PASS/FAIL status. No model API
is called here and no credentials are accepted.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ALIASES = {"qwen": "qwen", "qwen3.8-max-0902": "qwen", "opus": "opus", "opus-5": "opus",
           "glm": "glm", "glm-5.3": "glm", "kimi": "kimi", "kimi-k3": "kimi"}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("model evidence root must be an object")
    normalized: dict[str, Any] = {}
    for key, runs in value.items():
        canonical = ALIASES.get(str(key).casefold())
        if canonical:
            if canonical in normalized:
                raise ValueError(f"duplicate model evidence for {canonical}")
            normalized[canonical] = runs
    return normalized


def inspect_runs(name: str, runs: Any, required_count: int | None) -> tuple[list[int], int, list[str]]:
    errors: list[str] = []
    if not isinstance(runs, list):
        return [], 0, [f"{name} evidence must be a list"]
    if required_count is not None and len(runs) != required_count:
        errors.append(f"{name} requires exactly {required_count} runs, got {len(runs)}")
    scores: list[int] = []
    testcase_pass_sum = 0
    for index, run in enumerate(runs, 1):
        if not isinstance(run, dict) or run.get("validity") != "VALID":
            errors.append(f"{name} run {index} is not VALID; rerun infrastructure failures")
            continue
        score = run.get("score")
        if type(score) is not int or score not in (0, 1):
            errors.append(f"{name} run {index} does not have binary score 0/1")
        else:
            scores.append(score)
        cases = run.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append(f"{name} run {index} has no testcase evidence")
            continue
        ids: list[str] = []
        for case in cases:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                errors.append(f"{name} run {index} has malformed testcase")
                continue
            if case["id"] in ids:
                errors.append(f"{name} run {index} has duplicate testcase {case['id']}")
            ids.append(case["id"])
            if case.get("status") not in ("PASS", "FAIL"):
                errors.append(f"{name} run {index} has non-terminal testcase status")
            elif case["status"] == "PASS":
                testcase_pass_sum += 1
    return scores, testcase_pass_sum, errors


def evaluate(value: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    stats: dict[str, Any] = {}
    qwen_scores, qwen_pass, qwen_errors = inspect_runs("qwen", value.get("qwen"), 3)
    opus_scores, opus_pass, opus_errors = inspect_runs("opus", value.get("opus"), 3)
    errors.extend(qwen_errors + opus_errors)
    for name in ("glm", "kimi"):
        scores, passes, model_errors = inspect_runs(name, value.get(name), None)
        if not scores:
            model_errors.append(f"{name} requires at least one VALID run")
        errors.extend(model_errors)
        stats[name] = {"valid_runs": len(scores), "model_score_sum": sum(scores),
                       "testcase_pass_sum": passes}
    stats["qwen"] = {"valid_runs": len(qwen_scores), "model_score_sum": sum(qwen_scores),
                      "testcase_pass_sum": qwen_pass}
    stats["opus"] = {"valid_runs": len(opus_scores), "model_score_sum": sum(opus_scores),
                     "testcase_pass_sum": opus_pass}
    if not errors:
        qwen_sum, opus_sum = sum(qwen_scores), sum(opus_scores)
        if not (opus_sum > qwen_sum or
                (qwen_sum == 0 and opus_sum == 0 and opus_pass > qwen_pass)):
            errors.append("model distinction gate failed: Opus must beat Qwen, or both sums 0 with Opus testcase_pass_sum greater")
    return {"pass": not errors, "errors": errors, "stats": stats}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="local model evidence JSON")
    parser.add_argument("--output", type=Path, help="optional JSON result path")
    args = parser.parse_args()
    try:
        result = evaluate(load(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"pass": False, "errors": [f"invalid model evidence: {exc}"], "stats": {}}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
