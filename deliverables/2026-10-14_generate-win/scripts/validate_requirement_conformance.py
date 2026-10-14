#!/usr/bin/env python3
"""Validate a complete local Windows task against the Feishu requirements."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


REQUIRED_PATHS = (
    "task.toml",
    "source.json",
    "instruction.md",
    "environment/adapter.toml",
    "environment/Dockerfile",
    "environment/prepare.ps1",
    "environment/validate_environment.ps1",
    "environment/run.ps1",
    "environment/restore.ps1",
    "environment/cleanup.ps1",
    "environment/workspace",
    "tests/test.ps1",
    "tests/run_tests.ps1",
    "tests/aggregate_results.ps1",
    "tests/judge.toml",
    "tests/rubric.json",
    "solution/README.md",
    "solution/solve.ps1",
)


def get_nested(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def load_utf8(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        errors.append(f"File is not valid UTF-8: {path}")
        return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-path", required=True)
    args = parser.parse_args()

    task = Path(args.task_path).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not task.is_dir():
        print(json.dumps({"valid": False, "errors": [f"Task directory not found: {task}"]}, indent=2))
        return 2

    for relative in REQUIRED_PATHS:
        if not (task / relative).exists():
            errors.append(f"Missing required path: {relative}")

    if errors:
        print(json.dumps({"task_path": str(task), "valid": False, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
        return 2

    text_files = [
        path
        for path in task.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".toml", ".ps1", ".bat", ".yaml", ".yml"}
    ]
    text_by_path = {path: load_utf8(path, errors) for path in text_files}

    try:
        with (task / "task.toml").open("rb") as handle:
            task_toml = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"Invalid task.toml: {exc}")
        task_toml = {}
    try:
        source = json.loads(text_by_path.get(task / "source.json", "{}"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid source.json: {exc}")
        source = {}
    try:
        rubric = json.loads(text_by_path.get(task / "tests/rubric.json", "{}"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid tests/rubric.json: {exc}")
        rubric = {}
    try:
        with (task / "tests/judge.toml").open("rb") as handle:
            judge = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"Invalid tests/judge.toml: {exc}")
        judge = {}

    required_toml = (
        "version",
        "docker_image",
        "metadata.quality_restoration_version",
        "metadata.author_name",
        "metadata.task_id",
        "metadata.tags",
        "metadata.difficulty",
        "agent.timeout_sec",
        "verifier.timeout_sec",
        "environment.build_timeout_sec",
        "environment.cpus",
        "environment.memory",
        "task.id",
        "task.version",
        "task.instruction",
        "task.workspace",
        "task.test",
        "task.setup",
        "task.golden",
    )
    for key in required_toml:
        value = get_nested(task_toml, key)
        if value is None or value == "" or value == []:
            errors.append(f"task.toml missing required value: {key}")

    image = str(task_toml.get("docker_image") or "")
    if image.endswith(":latest") or (":" not in image.rsplit("/", 1)[-1] and "@sha256:" not in image):
        errors.append("task.toml docker_image must use an immutable non-latest tag or digest")

    required_source = (
        "task_id",
        "task_version",
        "source_type",
        "source_document",
        "license",
        "source_time",
        "lineage",
        "pollution_risk",
        "authorization",
    )
    for key in required_source:
        if source.get(key) in (None, "", []):
            errors.append(f"source.json missing required value: {key}")
    if source.get("source_type") == "vendor_delivery":
        for key in ("repo", "commit"):
            if source.get(key) in (None, "", []):
                errors.append(f"vendor_delivery source.json missing required value: {key}")

    local_paths = {
        "task.instruction": get_nested(task_toml, "task.instruction"),
        "task.workspace": get_nested(task_toml, "task.workspace"),
        "task.test": get_nested(task_toml, "task.test"),
        "task.setup": get_nested(task_toml, "task.setup"),
        "task.golden": get_nested(task_toml, "task.golden"),
    }
    for label, relative in local_paths.items():
        if not relative:
            continue
        candidate = (task / str(relative)).resolve()
        try:
            candidate.relative_to(task)
        except ValueError:
            errors.append(f"{label} escapes the task root: {relative}")
            continue
        if not candidate.exists():
            errors.append(f"{label} does not exist: {relative}")

    task_ids = {
        "directory": task.name,
        "task.toml metadata.task_id": get_nested(task_toml, "metadata.task_id"),
        "task.toml task.id": get_nested(task_toml, "task.id"),
        "source.json": source.get("task_id"),
        "rubric.json": rubric.get("task_id"),
    }
    nonempty_ids = {str(value) for value in task_ids.values() if value not in (None, "")}
    if len(nonempty_ids) != 1:
        errors.append("Task IDs are inconsistent: " + json.dumps(task_ids, ensure_ascii=False))

    task_versions = {
        "task.toml task.version": get_nested(task_toml, "task.version"),
        "source.json": source.get("task_version"),
        "rubric.json": rubric.get("task_version"),
    }
    nonempty_versions = {str(value) for value in task_versions.values() if value not in (None, "")}
    if len(nonempty_versions) != 1:
        errors.append("Task versions are inconsistent: " + json.dumps(task_versions, ensure_ascii=False))

    items = rubric.get("items")
    if rubric.get("schema_version") in (None, ""):
        errors.append("rubric.json missing schema_version")
    if not isinstance(items, list) or not items:
        errors.append("rubric.json must contain at least one item")
        items = []
    weights = 0.0
    rubric_ids: set[str] = set()
    for index, item in enumerate(items):
        for key in ("rubric_id", "description", "type", "weight", "test_ids", "evidence_source", "pass_condition", "failure_reason"):
            if item.get(key) in (None, "", []):
                errors.append(f"rubric.json item {index} missing {key}")
        rubric_id = str(item.get("rubric_id") or "")
        if rubric_id in rubric_ids:
            errors.append(f"Duplicate rubric_id: {rubric_id}")
        rubric_ids.add(rubric_id)
        try:
            weights += float(item.get("weight", 0))
        except (TypeError, ValueError):
            errors.append(f"Invalid rubric weight for {rubric_id or index}")
    declared_total = rubric.get("total_weight")
    try:
        declared_total_value = float(declared_total)
    except (TypeError, ValueError):
        declared_total_value = -1.0
    if abs(declared_total_value - 1.0) > 1e-9 or abs(weights - 1.0) > 1e-9:
        errors.append(f"Rubric weights must total 1.0 (items={weights}, declared={declared_total})")

    rubric_hash = hashlib.sha256((task / "tests/rubric.json").read_bytes()).hexdigest()
    if judge.get("authoritative_source") != "rubric.json":
        errors.append("judge.toml authoritative_source must be rubric.json")
    if str(judge.get("source_sha256") or "").lower() != rubric_hash:
        errors.append("judge.toml source_sha256 does not match tests/rubric.json")
    try:
        programmatic_weight = float(judge.get("programmatic_weight", -1))
        llm_weight = float(judge.get("llm_judge_weight", -1))
    except (TypeError, ValueError):
        programmatic_weight, llm_weight = -1.0, -1.0
    if programmatic_weight != 1.0 or llm_weight != 0.0:
        errors.append("judge.toml must use programmatic_weight=1.0 and llm_judge_weight=0.0")

    instruction = text_by_path.get(task / "instruction.md", "")
    section_groups = {
        "background": ("背景", "background"),
        "goal": ("目标", "goal"),
        "behavior": ("必须满足的行为", "required behavior", "required behaviour"),
        "constraints": ("边界和约束", "boundaries and constraints", "constraints"),
        "run entry": ("运行入口", "run entry"),
        "acceptance": ("用户可见验收", "user-visible acceptance", "acceptance"),
    }
    lower_instruction = instruction.lower()
    for label, alternatives in section_groups.items():
        if not any(re.search(rf"(?m)^#+\s+.*{re.escape(value.lower())}", lower_instruction) for value in alternatives):
            warnings.append(f"instruction.md does not contain an explicit {label} section")

    run_script = text_by_path.get(task / "environment/run.ps1", "")
    prepare_calls = len(re.findall(r"(?i)prepare\.ps1", run_script))
    if prepare_calls != 1:
        errors.append(f"environment/run.ps1 must call prepare.ps1 exactly once (found {prepare_calls})")
    if "$LASTEXITCODE" not in run_script:
        errors.append("environment/run.ps1 must propagate child exit codes through $LASTEXITCODE")
    if "Join-Path" not in run_script:
        warnings.append("environment/run.ps1 should use Join-Path for Windows paths")

    test_entry = text_by_path.get(task / "tests/test.ps1", "")
    if "generated" not in test_entry.lower() or "do not edit" not in test_entry.lower():
        errors.append("tests/test.ps1 must be visibly marked as generated and Do not edit")

    private_path = re.compile(r"(?i)[a-z]:\\users\\|/users/[^/]+/|/home/[^/]+/")
    secret_assignment = re.compile(r"(?i)(api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"][^<][^'\"]+")
    for path, text in text_by_path.items():
        relative = path.relative_to(task).as_posix()
        # The frozen participant workspace may contain public upstream docs and
        # vendored examples with placeholder credentials or platform-specific
        # absolute paths. Scan task-authored files for leaked values, while the
        # dedicated filename check below still rejects real local env files
        # anywhere in the package.
        if relative.startswith("environment/workspace/"):
            continue
        if private_path.search(text):
            errors.append(f"Private absolute path found in {relative}")
        if secret_assignment.search(text):
            errors.append(f"Possible secret value found in {relative}")

    for path in task.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(task).as_posix()
        name = path.name.lower()
        if name == ".env.local" or (
            not relative.startswith("environment/workspace/")
            and name in {".env", "credentials.json", "oauth.json"}
        ):
            errors.append(f"Forbidden secret-bearing filename found: {relative}")

    result = {
        "task_path": str(task),
        "task_id": next(iter(nonempty_ids)) if len(nonempty_ids) == 1 else None,
        "task_version": next(iter(nonempty_versions)) if len(nonempty_versions) == 1 else None,
        "rubric_sha256": rubric_hash,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    sys.exit(main())
