"""Validate the four-model admission gate from normalized local evidence.

The command never calls a model API. It accepts evidence already collected by
Harbor and rejects incomplete, invalid, duplicated, or cross-version runs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALIASES = {
    "qwen": "qwen", "qwen3.8-max-0902": "qwen", "qwen3.8": "qwen",
    "opus": "opus", "opus-5": "opus", "claude-opus-5": "opus",
    "glm": "glm", "glm-5.3": "glm",
    "kimi": "kimi", "kimi-k3": "kimi",
}

# Required rounds: the primary comparison pair. The discrimination rule is
# stated exclusively in terms of qwen vs opus.
REQUIRED_COUNTS = {"qwen": 3, "opus": 3}

# 2026-10-14 rule: GLM and Kimi are no longer run. If evidence for them is
# present it is ignored entirely -- it neither affects the gate nor counts as
# an error.
IGNORED_MODELS = ("glm", "kimi")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("model evidence root must be an object")
    return value


def normalize(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    task = value.get("task") if isinstance(value.get("task"), dict) else {}
    source = value.get("models") if isinstance(value.get("models"), dict) else value
    models: dict[str, Any] = {}
    for key, runs in source.items():
        canonical = ALIASES.get(str(key).casefold())
        if not canonical:
            continue
        if canonical in models:
            raise ValueError(f"duplicate model evidence for {canonical}")
        models[canonical] = runs
    return task, models


def inspect_runs(
    name: str,
    runs: Any,
    required_count: int,
    expected_identity: dict[str, Any],
    seen_run_ids: set[str],
    optional: bool = False,
) -> tuple[list[int], int, list[str]]:
    errors: list[str] = []
    if not isinstance(runs, list):
        return [], 0, [f"{name} evidence must be a list"]
    if len(runs) != required_count:
        # An optional model may be absent altogether under the latest scope;
        # supplying a partial set is still an error.
        if not (optional and len(runs) == 0):
            errors.append(f"{name} requires exactly {required_count} runs, got {len(runs)}")
    scores: list[int] = []
    testcase_pass_sum = 0
    for index, run in enumerate(runs, 1):
        label = f"{name} run {index}"
        if not isinstance(run, dict):
            errors.append(f"{label} is malformed")
            continue
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not run_id.strip():
            errors.append(f"{label} has no run_id")
        elif run_id in seen_run_ids:
            errors.append(f"duplicate run_id: {run_id}")
        else:
            seen_run_ids.add(run_id)
        is_valid = run.get("validity") == "VALID"
        if not is_valid:
            errors.append(f"{label} is not VALID; infrastructure failures cannot count as zero")
        score = run.get("score")
        if type(score) is not int or score not in (0, 1):
            errors.append(f"{label} does not have binary score 0/1")
        elif is_valid:
            scores.append(score)
        for field in ("task_id", "task_version", "task_hash"):
            expected = expected_identity.get(field)
            actual = run.get(field)
            if not isinstance(actual, str) or not actual:
                errors.append(f"{label} has no {field}")
            elif expected and actual != expected:
                errors.append(f"{label} {field} does not match the delivered Task")
        cases = run.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append(f"{label} has no testcase evidence")
            continue
        ids: set[str] = set()
        for case in cases:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                errors.append(f"{label} has malformed testcase")
                continue
            case_id = case["id"]
            if case_id in ids:
                errors.append(f"{label} has duplicate testcase {case_id}")
            ids.add(case_id)
            status = case.get("status")
            if status not in ("PASS", "FAIL"):
                errors.append(f"{label} testcase {case_id} has non-terminal status {status!r}")
            elif status == "PASS":
                testcase_pass_sum += 1
    return scores, testcase_pass_sum, errors


def evaluate(value: dict[str, Any], expected_identity: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[str] = []
    stats: dict[str, Any] = {}
    try:
        declared_task, models = normalize(value)
    except ValueError as exc:
        return {"pass": False, "errors": [str(exc)], "stats": {}}
    identity = dict(expected_identity or declared_task)
    for field in ("task_id", "task_version", "task_hash"):
        if not isinstance(identity.get(field), str) or not identity[field]:
            errors.append(f"model evidence has no bound {field}")
        declared = declared_task.get(field)
        if expected_identity and declared is not None and declared != identity.get(field):
            errors.append(f"declared {field} does not match the delivered Task")

    seen_run_ids: set[str] = set()
    scores_by_model: dict[str, list[int]] = {}
    for name, count in REQUIRED_COUNTS.items():
        scores, passes, model_errors = inspect_runs(
            name, models.get(name), count, identity, seen_run_ids, optional=False
        )
        errors.extend(model_errors)
        scores_by_model[name] = scores
        stats[name] = {
            "valid_runs": len(scores),
            "model_score_sum": sum(scores),
            "testcase_pass_sum": passes,
            "required": True,
        }

    qwen_scores = scores_by_model["qwen"]
    opus_scores = scores_by_model["opus"]
    qwen_score_sum = sum(qwen_scores)
    opus_score_sum = sum(opus_scores)
    qwen_testcase_pass_sum = stats["qwen"]["testcase_pass_sum"]
    opus_testcase_pass_sum = stats["opus"]["testcase_pass_sum"]
    all_scores = [score for scores in scores_by_model.values() for score in scores]
    # The "every run is VALID/0" and "every run is full score" exceptions cover
    # exactly the required primary-model rounds (Qwen 3 + Opus 3 = 6).
    expected_total = sum(REQUIRED_COUNTS.values())
    all_zero_exception = (
        not errors
        and len(all_scores) == expected_total
        and all(score == 0 for score in all_scores)
    )
    qwen_opus_full_score = (
        not errors
        and len(qwen_scores) == REQUIRED_COUNTS["qwen"]
        and len(opus_scores) == REQUIRED_COUNTS["opus"]
        and all(score == 1 for score in qwen_scores + opus_scores)
    )
    all_models_full_score = (
        not errors
        and len(all_scores) == expected_total
        and all(score == 1 for score in all_scores)
    )
    stats["distinction"] = {
        "all_models_zero_exception": all_zero_exception,
        "qwen_opus_full_score": qwen_opus_full_score,
        "all_models_full_score": all_models_full_score,
        "score_tie": opus_score_sum == qwen_score_sum,
        "testcase_tiebreak_pass": (
            opus_score_sum == qwen_score_sum
            and opus_testcase_pass_sum > qwen_testcase_pass_sum
        ),
        "full_score_tiebreak_pass": (
            qwen_opus_full_score
            and opus_testcase_pass_sum > qwen_testcase_pass_sum
        ),
        "rule": (
            "Opus score sum must exceed Qwen; when the score sums tie, Opus testcase pass sum "
            "must strictly exceed Qwen, unless every required model run is VALID/0. A Qwen/Opus "
            "full-score tie is decided by testcase_pass_sum: Qwen passing fewer testcases than "
            "Opus is sufficient distinction, so the required testcase set must still separate "
            "the two models. all_models_full_score is recorded for the report only."
        ),
    }
    if not errors and not all_zero_exception:
        if opus_score_sum < qwen_score_sum:
            errors.append(
                "model distinction gate failed: Opus model_score_sum is lower than "
                "Qwen model_score_sum"
            )
        elif (
            opus_score_sum == qwen_score_sum
            and opus_testcase_pass_sum <= qwen_testcase_pass_sum
        ):
            if qwen_opus_full_score:
                errors.append(
                    "model distinction gate failed: Qwen and Opus are both full-score across "
                    f"all required runs (model_score_sum tied at {opus_score_sum}), and Opus "
                    f"testcase_pass_sum ({opus_testcase_pass_sum}) is not strictly greater than "
                    f"Qwen ({qwen_testcase_pass_sum}); the required testcases do not separate "
                    "the two models"
                )
            else:
                errors.append(
                    "model distinction gate failed: Opus and Qwen model_score_sum are tied, "
                    "but Opus testcase_pass_sum is not strictly greater than Qwen"
                )
    return {"pass": not errors, "errors": errors, "stats": stats, "task": identity}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="normalized local model evidence JSON")
    parser.add_argument("--output", type=Path, help="optional JSON result path")
    args = parser.parse_args()
    try:
        result = evaluate(load(args.input))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"pass": False, "errors": [f"invalid model evidence: {exc}"], "stats": {}}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
