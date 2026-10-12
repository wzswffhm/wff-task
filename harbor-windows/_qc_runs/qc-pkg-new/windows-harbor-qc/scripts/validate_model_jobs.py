"""Validate direct Harbor jobs: 8 model trajectories plus 3 Oracle and 3 NOP."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from validate_model_gate import ALIASES, REQUIRED_COUNTS


CJK = re.compile(r"[\u3400-\u9fff]")
BANNED_PROMPT_PREFIX = re.compile(r"中文口语化提示\s*[：:]", re.I)
SECRET_PATTERNS = (
    re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]{12,}"),
    re.compile(r"(?i)(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9._-]{12,}"),
    re.compile(r"\b(?:sk|ark)-[A-Za-z0-9._-]{16,}\b"),
)
COMMON_FILES = (
    "config.json", "lock.json", "result.json", "trial.log", "artifacts/manifest.json",
    "verifier/result.json", "verifier/reward.txt", "verifier/test-stdout.txt", "verifier/verifier.log",
)
MODEL_FILES = ("agent/model-result.json", "agent/trajectory.jsonl")
ORACLE_FILES = ("agent/oracle.txt", "agent/qc-oracle-application.json")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_model(value: Any) -> str | None:
    if value is None:
        return None
    folded = str(value).strip().casefold()
    direct = {"qwen": "qwen", "opus": "opus", "glm": "glm", "kimi": "kimi"}
    return direct.get(folded) or ALIASES.get(folded)


def required_cases(task_root: Path) -> tuple[set[str], dict[str, str]]:
    value = read_json(task_root / "tests" / "required_testcases.json")
    rows = value if isinstance(value, list) else []
    ids = {str(row["id"]) for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)}
    groups = {str(row["id"]): str(row.get("group")) for row in rows
              if isinstance(row, dict) and isinstance(row.get("id"), str)}
    return ids, groups


def report_cases(report: dict[str, Any]) -> dict[str, str]:
    rows = report.get("items") if isinstance(report.get("items"), list) else report.get("testcases")
    if isinstance(rows, dict):
        return {str(key): str(value).upper() for key, value in rows.items()}
    result: dict[str, str] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        case_id = row.get("test_id") or row.get("id")
        outcome = row.get("outcome") or row.get("status")
        if not isinstance(case_id, str):
            continue
        normalized = {"PASSED": "PASS", "PASS": "PASS", "FAILED": "FAIL", "FAIL": "FAIL"}.get(
            str(outcome).upper(), str(outcome).upper())
        result[case_id] = normalized
    return result


def parse_reward(path: Path) -> int | None:
    try:
        value = float(path.read_text(encoding="utf-8-sig").strip())
    except (OSError, ValueError):
        return None
    return int(value) if value in (0.0, 1.0) else None


def job_identity(result: dict[str, Any], config: dict[str, Any]) -> tuple[str, str | None, str | None]:
    agent = ((result.get("config") or {}).get("agent") or config.get("agent") or {})
    name = str(agent.get("name") or "").casefold()
    if name == "oracle":
        return "oracle", None, None
    if name == "nop":
        return "nop", None, None
    metadata = ((result.get("agent_result") or {}).get("metadata") or {})
    kwargs = agent.get("kwargs") if isinstance(agent.get("kwargs"), dict) else {}
    alias = metadata.get("alias") or kwargs.get("alias")
    model = canonical_model(alias) or canonical_model(metadata.get("model"))
    return "model", model, str(metadata.get("model")) if metadata.get("model") else None


def scan_secrets(job: Path) -> str | None:
    for path in job.rglob("*"):
        if (not path.is_file() or path.stat().st_size > 5 * 1024 * 1024 or
                path.suffix.casefold() not in {".json", ".jsonl", ".txt", ".log", ".md", ".toml"}):
            continue
        content = path.read_text(encoding="utf-8-sig", errors="ignore")
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            return path.relative_to(job).as_posix()
    return None


def validate_jobs(jobs_root: Path, task_root: Path, identity: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    details: list[dict[str, Any]] = []
    models: dict[str, list[dict[str, Any]]] = {name: [] for name in REQUIRED_COUNTS}
    agent_counts = {"oracle": 0, "nop": 0}
    checksums: set[str] = set()
    required_ids, groups = required_cases(task_root)
    expected_checksum = identity.get("harbor_task_checksum")
    for relative in ("config.json", "lock.json", "result.json", "job.log"):
        if not (jobs_root / relative).is_file():
            errors.append(f"jobs/ is missing Harbor parent job file: {relative}")
    job_dirs = sorted(path for path in jobs_root.iterdir() if path.is_dir() and (path / "result.json").is_file())

    if len(job_dirs) != 14:
        errors.append(f"jobs/ must contain exactly 14 Harbor job directories, got {len(job_dirs)}")
    for job in job_dirs:
        label = job.name
        for relative in COMMON_FILES:
            if not (job / relative).is_file():
                errors.append(f"{label} is missing {relative}")
        try:
            config = read_json(job / "config.json")
            result = read_json(job / "result.json")
            verifier = read_json(job / "verifier" / "result.json")
        except Exception as exc:
            errors.append(f"{label} contains unreadable core JSON: {exc}")
            continue
        kind, model, actual_model_name = job_identity(result, config)
        required_files = MODEL_FILES if kind == "model" else ORACLE_FILES if kind == "oracle" else ()
        for relative in required_files:
            if not (job / relative).is_file():
                errors.append(f"{label} is missing {relative}")
        if kind == "model" and model is None:
            errors.append(f"{label} has no recognized Qwen/Opus/GLM/Kimi alias")
        elif kind in agent_counts:
            agent_counts[kind] += 1

        if result.get("exception_info") is not None:
            errors.append(f"{label} has Harbor exception_info")
        checksum = result.get("task_checksum")
        if not isinstance(checksum, str) or not checksum:
            errors.append(f"{label} result.json has no task_checksum")
        else:
            checksums.add(checksum)
            if expected_checksum and checksum != expected_checksum:
                errors.append(f"{label} was run against a different Task checksum")

        status = verifier.get("status")
        score = verifier.get("score")
        if status != "VALID":
            errors.append(f"{label} verifier status is not VALID")
        if type(score) is not int or score not in (0, 1):
            errors.append(f"{label} verifier score is not binary 0/1")
        cases = report_cases(verifier)
        if set(cases) != required_ids:
            errors.append(f"{label} testcase set does not match tests/required_testcases.json")
        for case_id, outcome in cases.items():
            if outcome not in ("PASS", "FAIL"):
                errors.append(f"{label} testcase {case_id} has non-terminal status {outcome!r}")
        reward = parse_reward(job / "verifier" / "reward.txt")
        harbor_reward = (((result.get("verifier_result") or {}).get("rewards") or {}).get("reward"))
        if reward != score or harbor_reward != score:
            errors.append(f"{label} verifier/result/reward values are inconsistent")

        if kind == "oracle":
            if score != 1 or any(value != "PASS" for value in cases.values()):
                errors.append(f"{label} Oracle evidence is not VALID/1 with all required cases passing")
        elif kind == "nop":
            p2p = [cases.get(case_id) for case_id, group in groups.items() if group == "P2P"]
            f2p = [cases.get(case_id) for case_id, group in groups.items() if group == "F2P"]
            if score != 0 or not p2p or any(value != "PASS" for value in p2p) or "FAIL" not in f2p:
                errors.append(f"{label} NOP evidence must be VALID/0, P2P PASS, with at least one F2P FAIL")
        elif model:
            try:
                provenance = read_json(job / "agent" / "model-result.json")
                if canonical_model(provenance.get("alias")) != model or canonical_model(provenance.get("model")) != model:
                    errors.append(f"{label} model-result.json alias/model does not match {model}")
                if not provenance.get("protocol") or not provenance.get("runner_sha256"):
                    errors.append(f"{label} model-result.json provenance is incomplete")
            except Exception as exc:
                errors.append(f"{label} model provenance is unreadable: {exc}")
            trajectory = job / "agent" / "trajectory.jsonl"
            if trajectory.is_file():
                text = trajectory.read_text(encoding="utf-8-sig", errors="replace")
                if not text.strip():
                    errors.append(f"{label} trajectory.jsonl is empty")
                if BANNED_PROMPT_PREFIX.search(text):
                    errors.append(f"{label} contains the forbidden '中文口语化提示：' label")
                if len(CJK.findall(text)) < 8:
                    warnings.append(f"{label} trajectory does not expose a verifiable Chinese conversational prompt")
            run = {
                "run_id": str(result.get("id") or label), "job_dir": label,
                "task_id": identity.get("task_id"), "task_version": identity.get("task_version"),
                "task_hash": identity.get("task_hash"), "harbor_task_checksum": checksum,
                "validity": status, "score": score,
                "cases": [{"id": key, "status": value} for key, value in sorted(cases.items())],
            }
            models[model].append(run)
            details.append({"job_dir": label, "kind": "model", "model": model,
                            "actual_model": actual_model_name, "score": score})
        else:
            details.append({"job_dir": label, "kind": kind, "score": score})

        secret = scan_secrets(job)
        if secret:
            errors.append(f"{label} contains a possible credential in {secret}")

    for model, count in REQUIRED_COUNTS.items():
        if len(models[model]) != count:
            errors.append(f"jobs/ contains {len(models[model])} {model} model jobs; exactly {count} required")
    for agent in ("oracle", "nop"):
        if agent_counts[agent] != 3:
            errors.append(f"jobs/ contains {agent_counts[agent]} {agent} jobs; exactly 3 required")
    if len(checksums) > 1:
        errors.append("jobs were run against different Harbor Task checksums")

    evidence = {"task": identity, "models": models}
    return {
        "pass": not errors, "errors": errors, "warnings": warnings,
        "discovered_counts": {**{name: len(runs) for name, runs in models.items()}, **agent_counts},
        "harbor_task_checksums": sorted(checksums), "jobs": details, "evidence": evidence,
    }
