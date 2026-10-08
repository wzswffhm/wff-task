"""Portable local QC entry point for Outside Harbor Windows task packages.

The command accepts one task directory or a ZIP containing one or more task
directories. It never edits the input. Static contract checks run before real
Harbor executions; every NOP and Oracle attempt gets its own job directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any


MAX_UNPACKED = 8 * 1024**3
MAX_MEMBERS = 200_000
MAX_FILE = 100 * 1024**2
DEFAULT_ATTEMPTS = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_zip_parts(name: str) -> list[str]:
    normalized = name.replace("\\", "/")
    if not normalized or normalized.startswith("/") or PureWindowsPath(normalized).drive:
        raise ValueError(f"archive absolute path: {name}")
    parts = normalized.rstrip("/").split("/")
    reserved = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", re.I)
    for part in parts:
        if (not part or part in (".", "..") or ":" in part or
                part.rstrip(" .") != part or reserved.match(part)):
            raise ValueError(f"unsafe Windows archive path: {name}")
    return parts


def safe_extract(archive: Path, destination: Path) -> list[dict[str, Any]]:
    destination = destination.resolve()
    seen: set[str] = set()
    total = 0
    members: list[tuple[zipfile.ZipInfo, Path]] = []
    with zipfile.ZipFile(archive) as source:
        for info in source.infolist():
            parts = safe_zip_parts(info.filename)
            key = "/".join(parts).casefold()
            if key in seen:
                raise ValueError(f"duplicate or case-conflicting archive path: {info.filename}")
            seen.add(key)
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError(f"symbolic link in archive: {info.filename}")
            total += info.file_size
            if total > MAX_UNPACKED or len(seen) > MAX_MEMBERS:
                raise ValueError("archive expansion exceeds safety limits")
            if (info.file_size > MAX_FILE and
                    info.file_size > max(info.compress_size, 1) * 1000):
                raise ValueError(f"suspicious compression ratio: {info.filename}")
            target = destination.joinpath(*parts)
            if not target.is_relative_to(destination):
                raise ValueError(f"archive path escapes destination: {info.filename}")
            members.append((info, target))
        if destination.exists():
            raise ValueError(f"refusing to overwrite evidence directory: {destination}")
        destination.mkdir(parents=True)
        for info, target in members:
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst)
    return [{"name": i.filename, "size": i.file_size} for i, _ in members]


def discover_tasks(root: Path) -> list[Path]:
    root = root.resolve()
    if (root / "task.toml").is_file():
        return [root]
    candidates = sorted({p.parent for p in root.rglob("task.toml")})
    return [p for p in candidates if not any(part.startswith(".") for part in p.relative_to(root).parts)]


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"TOML root is not an object: {path}")
    return value


def load_json(path: Path) -> Any:
    value = read_json(path)
    return value


def id_from_toml(config: dict[str, Any]) -> str | None:
    metadata = config.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("task_id"), str):
        return metadata["task_id"]
    for key in ("task_id", "id"):
        if isinstance(config.get(key), str):
            return config[key]
    return None


def collect_referenced_paths(task: Path) -> list[str]:
    references: list[str] = []
    path_pattern = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.${}\\/-]+)+|[A-Za-z0-9_.-]+\.(?:go|ps1|psm1|json|toml|dll|exe|bat|cmd))")
    for file in task.rglob("*"):
        if not file.is_file() or ".git" in file.parts:
            continue
        if file.suffix.lower() not in {".ps1", ".psm1", ".bat", ".cmd"}:
            continue
        try:
            text = file.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            continue
        references.extend(path_pattern.findall(text))
    return references


def static_check(task: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required_top = ["task.toml", "source.json", "instruction.md", "environment", "tests", "solution"]
    for name in required_top:
        if not (task / name).exists():
            errors.append(f"missing top-level {name}")
    env_required = ["adapter.toml", "Dockerfile", "prepare.ps1", "validate_environment.ps1",
                    "run.ps1", "restore.ps1", "cleanup.ps1"]
    tests_required = ["test.ps1", "run_tests.ps1", "aggregate_results.ps1", "judge.toml",
                      "rubric.json", "required_testcases.json"]
    solution_required = ["README.md"]
    for name in env_required:
        if not (task / "environment" / name).is_file():
            errors.append(f"missing environment/{name}")
    for name in tests_required:
        if not (task / "tests" / name).is_file():
            errors.append(f"missing tests/{name}")
    for name in solution_required:
        if not (task / "solution" / name).is_file():
            errors.append(f"missing solution/{name}")
    if (task / "solution").is_dir() and not any((task / "solution" / n).is_file() for n in ("solve.ps1", "solve.bat")):
        errors.append("solution must provide solve.ps1 or solve.bat")

    config: dict[str, Any] = {}
    source: dict[str, Any] = {}
    rubric: dict[str, Any] = {}
    manifest: list[Any] = []
    if (task / "task.toml").is_file():
        try:
            config = load_toml(task / "task.toml")
        except Exception as exc:
            errors.append(f"task.toml parse error: {type(exc).__name__}: {exc}")
    if (task / "source.json").is_file():
        try:
            source = load_json(task / "source.json")
            if not isinstance(source, dict):
                errors.append("source.json root must be an object")
        except Exception as exc:
            errors.append(f"source.json parse error: {type(exc).__name__}: {exc}")
    if (task / "tests" / "rubric.json").is_file():
        try:
            rubric = load_json(task / "tests" / "rubric.json")
            if not isinstance(rubric, dict):
                errors.append("tests/rubric.json root must be an object")
        except Exception as exc:
            errors.append(f"rubric.json parse error: {type(exc).__name__}: {exc}")
    if (task / "tests" / "required_testcases.json").is_file():
        try:
            manifest = load_json(task / "tests" / "required_testcases.json")
            if not isinstance(manifest, list):
                errors.append("required_testcases.json must be a list")
                manifest = []
        except Exception as exc:
            errors.append(f"required_testcases.json parse error: {type(exc).__name__}: {exc}")

    task_id = id_from_toml(config)
    source_id = source.get("task_id") if isinstance(source, dict) else None
    ids = [x for x in (task.name, task_id, source_id, rubric.get("task_id")) if x]
    if task_id is None:
        errors.append("task.toml has no task_id (metadata.task_id or task_id)")
    if len(set(ids)) > 1:
        errors.append(f"task identity mismatch: {ids}")
    version = config.get("version")
    if not version:
        errors.append("task.toml has no version")
    docker_image = config.get("docker_image")
    if not docker_image and isinstance(config.get("environment"), dict):
        docker_image = config["environment"].get("docker_image")
    if not isinstance(docker_image, str) or not docker_image.strip():
        errors.append("task.toml has no docker_image")
    elif docker_image.strip().endswith(":latest") or docker_image.strip() == "latest":
        errors.append("docker_image must not use floating latest tag")
    if isinstance(source, dict):
        if not source.get("task_id"):
            errors.append("source.json has no task_id")
        for key in ("source_type", "license", "lineage", "authorization"):
            if not source.get(key):
                warnings.append(f"source.json missing traceability field: {key}")
    if isinstance(rubric, dict) and not rubric.get("task_id"):
        errors.append("rubric.json has no task_id")
    if not manifest:
        errors.append("required testcase manifest is empty")
    testcase_ids: list[str] = []
    groups: dict[str, str] = {}
    for item in manifest:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item.get("group") not in ("F2P", "P2P"):
            errors.append("required testcase entries need unique id and group F2P/P2P")
            continue
        testcase_ids.append(item["id"])
        groups[item["id"]] = item["group"]
    if len(testcase_ids) != len(set(testcase_ids)):
        errors.append("required testcase IDs are duplicated")
    if not any(g == "F2P" for g in groups.values()) or not any(g == "P2P" for g in groups.values()):
        errors.append("required testcase manifest must contain both F2P and P2P")
    rubric_file = task / "tests" / "rubric.json"
    judge_file = task / "tests" / "judge.toml"
    if rubric_file.is_file() and judge_file.is_file():
        try:
            judge = load_toml(judge_file)
            declared_hash = judge.get("source_sha256") or judge.get("rubric_sha256")
            actual_hash = sha256(rubric_file)
            if declared_hash and str(declared_hash).lower() != actual_hash:
                errors.append("judge.toml rubric hash does not match rubric.json")
        except Exception as exc:
            errors.append(f"judge.toml parse error: {type(exc).__name__}: {exc}")

    missing_refs: list[str] = []
    for ref in collect_referenced_paths(task):
        clean = ref.replace("\\", "/").replace("${TaskRoot}", "").replace("$PSScriptRoot", "")
        if any(token in clean for token in ("$", "%", "<", ">")):
            continue
        if clean.casefold() in {"powershell.exe", "cmd.exe", "go.exe", "dotnet.exe", "python.exe"}:
            continue
        if not (task / clean).exists() and not (task / "tests" / clean).exists() and not (task / "environment" / clean).exists():
            missing_refs.append(ref)
    if missing_refs:
        errors.append("referenced files are missing: " + ", ".join(sorted(set(missing_refs))[:12]))
    # The known failure mode is a wrapper that calls a hidden test which was never delivered.
    if (task / "tests" / "test.bat").is_file():
        text = (task / "tests" / "test.bat").read_text(encoding="utf-8-sig", errors="ignore")
        if re.search(r"hidden[_-]?test", text, re.I):
            errors.append("tests/test.bat references a hidden test file; deliver the file or fix the entrypoint")

    # Prevent common answer/test leakage through the participant workspace.
    workspace = task / "environment" / "workspace"
    if workspace.is_dir():
        leaked = [str(p.relative_to(task)).replace("\\", "/") for p in workspace.rglob("*")
                  if p.is_file() and any(token in p.name.casefold() for token in ("solution", "golden", "hidden_test", "reward"))]
        if leaked:
            errors.append("environment/workspace contains likely answer or hidden-test material: " + ", ".join(leaked[:8]))

    hashes = {str(p.relative_to(task)).replace("\\", "/"): sha256(p) for p in task.rglob("*") if p.is_file()}
    return {"task_id": task_id or task.name, "root": str(task), "errors": errors,
            "warnings": warnings, "required_testcases": manifest, "hashes": hashes,
            "static_pass": not errors}


def command_output(command: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              encoding="utf-8", errors="replace")
        return proc.returncode, proc.stdout
    except OSError as exc:
        return 127, str(exc)


def preflight() -> dict[str, Any]:
    harbor = shutil.which("harbor") or shutil.which("harbor.exe")
    docker = shutil.which("docker") or shutil.which("docker.exe")
    result: dict[str, Any] = {"harbor": harbor, "docker": docker, "checked_at": utc_now(), "ok": False}
    if not harbor or not docker:
        result["reason"] = "harbor or docker is not on PATH"
        return result
    result["harbor_version_code"], result["harbor_version"] = command_output([harbor, "--version"])
    result["docker_code"], result["docker_info"] = command_output([docker, "info", "--format", "{{.OSType}} {{.Architecture}}"])
    if result["harbor_version_code"] != 0 or result["docker_code"] != 0:
        result["reason"] = "Harbor or Docker is not responding"
        return result
    if not result["docker_info"].strip().lower().startswith("windows"):
        result["reason"] = "Docker is not in Windows container mode"
        return result
    result["ok"] = True
    return result


def classify_job(job: Path) -> list[dict[str, Any]]:
    trials: list[dict[str, Any]] = []
    for result_file in job.glob("*/result.json"):
        if result_file.parent.name == "logs":
            continue
        try:
            data = read_json(result_file)
        except Exception as exc:
            trials.append({"trial_id": result_file.parent.name, "exception": f"result parse: {exc}",
                           "rewards": None, "trial_root": str(result_file.parent), "result_path": str(result_file)})
            continue
        verifier = data.get("verifier_result") or {}
        trials.append({"trial_id": data.get("trial_name", result_file.parent.name),
                       "exception": data.get("exception_info"), "rewards": verifier.get("rewards"),
                       "trial_root": str(result_file.parent), "result_path": str(result_file)})
    return trials


def formal_result(trial: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    """Use the maintained strict parser from the bundled legacy implementation."""
    scripts = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts))
    from run_trials import formal_result as parser
    return parser(trial, {"root": task["root"]})


def run_one(task: dict[str, Any], agent: str, attempt: int, jobs_root: Path,
            environment: str | None, force_build: bool) -> dict[str, Any]:
    task_root = Path(task["root"])
    job_name = f"{task['task_id']}-{agent}-{attempt}"
    jobs_dir = jobs_root
    log = jobs_root / f"{job_name}.cli.log"
    harbor = shutil.which("harbor") or shutil.which("harbor.exe") or "harbor"
    command = [harbor, "run", "--path", str(task_root), "--agent", agent,
               "--n-attempts", "1", "--n-concurrent", "1", "--max-retries", "0",
               "--jobs-dir", str(jobs_dir), "--job-name", job_name]
    if environment:
        command.extend(["--env", environment])
    if force_build:
        command.append("--force-build")
    started = utc_now()
    code = 127
    output = ""
    try:
        child_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        scripts_dir = str(Path(__file__).resolve().parent)
        child_env["PYTHONPATH"] = scripts_dir + os.pathsep + child_env.get("PYTHONPATH", "")
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace", env=child_env)
        code, output = proc.returncode, proc.stdout
    except OSError as exc:
        output = str(exc)
    log.write_text(output, encoding="utf-8")
    trials = classify_job(jobs_dir / job_name)
    # Some Harbor versions place a result directly under jobs-dir.
    if not trials:
        trials = classify_job(jobs_dir)
    row: dict[str, Any] = {"task_id": task["task_id"], "agent": agent, "attempt": attempt,
                            "command": command, "started": started, "ended": utc_now(),
                            "exit_code": code, "cli_log": str(log), "trials": trials}
    row["formal_results"] = [formal_result(t, task) for t in trials]
    if code != 0 or not trials or any(t.get("exception") or t.get("rewards") is None for t in trials):
        row["status"] = "BLOCKED"
    elif any(r.get("validity") != "VALID" for r in row["formal_results"]):
        row["status"] = "INVALID"
    else:
        row["status"] = "VALID"
    return row


def cases_for(run: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for result in run.get("formal_results", []) for c in result.get("cases", [])]


def dynamic_gate(runs: list[dict[str, Any]], attempts: int) -> dict[str, Any]:
    by_agent = {agent: [r for r in runs if r["agent"] == agent] for agent in ("oracle", "nop")}
    reasons: list[str] = []
    oracle = by_agent["oracle"]
    nop = by_agent["nop"]
    if len(oracle) != attempts or len(nop) != attempts:
        reasons.append("not all requested Oracle/NOP attempts completed")
    if any(r["status"] != "VALID" for r in oracle):
        reasons.append("Oracle has BLOCKED/INVALID execution")
    oracle_scores = [x.get("score") for r in oracle for x in r.get("formal_results", [])]
    if len(oracle_scores) != attempts or any(s != 1 for s in oracle_scores):
        reasons.append("Oracle is not VALID/1 on every independent run")
    if any(r["status"] != "VALID" for r in nop):
        reasons.append("NOP has BLOCKED/INVALID execution")
    nop_scores = [x.get("score") for r in nop for x in r.get("formal_results", [])]
    if len(nop_scores) != attempts or any(s != 0 for s in nop_scores):
        reasons.append("NOP is not VALID/0 on every independent run")
    for r in nop:
        cases = cases_for(r)
        if cases and any(c.get("group") == "P2P" and c.get("status") != "PASS" for c in cases):
            reasons.append(f"NOP attempt {r['attempt']} has a P2P failure")
        if cases and not any(c.get("group") == "F2P" and c.get("status") == "FAIL" for c in cases):
            reasons.append(f"NOP attempt {r['attempt']} has no core F2P failure")
    passed = sum(c.get("status") == "PASS" for r in nop for c in cases_for(r))
    return {"pass": not reasons, "reasons": sorted(set(reasons)),
            "oracle_scores": oracle_scores, "nop_scores": nop_scores,
            "nop_testcase_pass_count": passed}


def markdown_report(payload: dict[str, Any]) -> str:
    lines = ["# Windows Harbor 质检报告", "", f"生成时间：`{payload['generated_at']}`", ""]
    lines.append(f"结论：**{payload['conclusion']}**")
    lines.append("")
    lines.append("本报告由本地真实 Harbor CLI 生成；输入题包未被修改。")
    lines.append("")
    for task in payload["tasks"]:
        lines.append(f"## {task['task_id']}")
        lines.append("")
        lines.append(f"静态结构：`{'PASS' if task['static']['static_pass'] else 'FAIL'}`")
        for item in task["static"].get("errors", []):
            lines.append(f"- 静态错误：{item}")
        for item in task["static"].get("warnings", []):
            lines.append(f"- 警告：{item}")
        gate = task.get("dynamic_gate")
        if gate is not None:
            lines.append(f"- Oracle：`{gate['oracle_scores']}`（要求每轮 VALID/1）")
            lines.append(f"- NOP：`{gate['nop_scores']}`（要求每轮 VALID/0）")
            lines.append(f"- 动态门禁：`{'PASS' if gate['pass'] else 'FAIL'}`")
            for reason in gate.get("reasons", []):
                lines.append(f"- 动态错误：{reason}")
    lines.append("")
    lines.append("## 证据")
    lines.append("")
    lines.append("- `inventory.json`：结构、入口和文件 Hash")
    lines.append("- `commands.json`：每轮实际 Harbor CLI 命令")
    lines.append("- `jobs/`：Harbor 原始 job/trial/verifier 结果")
    lines.append("- `*.cli.log`：Harbor CLI 原始输出，可作为 Oracle 成功的直接文字证据")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    input_path = args.input.resolve()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f"output directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    extracted = out / "extracted"
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        members = safe_extract(input_path, extracted)
        input_sha = sha256(input_path)
        input_type = "zip"
    elif input_path.is_dir():
        extracted = input_path
        members = []
        input_sha = None
        input_type = "directory"
    else:
        raise ValueError("--input must be a ZIP file or directory")
    tasks = discover_tasks(extracted)
    if not tasks:
        raise ValueError("no task.toml was found")
    inventory = {"generated_at": utc_now(), "input": str(input_path), "input_type": input_type,
                 "input_sha256": input_sha, "members": members, "tasks": []}
    for task_root in tasks:
        inventory["tasks"].append(static_check(task_root))
    write_json(out / "inventory.json", inventory)
    write_json(out / "hashes.json", {item["task_id"]: item["hashes"] for item in inventory["tasks"]})
    if any(not item["static_pass"] for item in inventory["tasks"]):
        payload = {"generated_at": utc_now(), "conclusion": "FAIL", "tasks": inventory["tasks"],
                   "preflight": None, "runs": []}
        write_json(out / "report.json", payload)
        (out / "report.md").write_text(markdown_report(payload), encoding="utf-8")
        return 1
    check = preflight()
    write_json(out / "preflight.json", check)
    if not check["ok"]:
        payload = {"generated_at": utc_now(), "conclusion": "BLOCKED", "tasks": inventory["tasks"],
                   "preflight": check, "runs": []}
        write_json(out / "report.json", payload)
        (out / "report.md").write_text(markdown_report(payload), encoding="utf-8")
        return 2

    staged = out / "staged"
    jobs = out / "jobs"
    staged.mkdir()
    jobs.mkdir()
    all_runs: list[dict[str, Any]] = []
    environment = args.environment or "windows_qc_env:WindowsQCEnvironment"
    commands: list[list[str]] = []
    for item in inventory["tasks"]:
        original = Path(item["root"])
        stage = staged / item["task_id"]
        shutil.copytree(original, stage)
        staged_item = dict(item)
        staged_item["root"] = str(stage)
        # Run Oracle first so a missing solution is reported immediately.
        for agent in ("oracle", "nop"):
            for attempt in range(1, args.attempts + 1):
                result = run_one(staged_item, agent, attempt, jobs, environment, args.force_build)
                commands.append(result["command"])
                all_runs.append(result)
                write_json(out / "runs.json", all_runs)
                # An infrastructure failure cannot be repaired by repeating it.
                if result["status"] == "BLOCKED":
                    break
    for item in inventory["tasks"]:
        task_runs = [r for r in all_runs if r["task_id"] == item["task_id"]]
        item["dynamic_gate"] = dynamic_gate(task_runs, args.attempts)
    write_json(out / "commands.json", commands)
    write_json(out / "inventory.json", inventory)
    conclusion = "PASS" if all(item.get("dynamic_gate", {}).get("pass") for item in inventory["tasks"]) else "FAIL"
    payload = {"generated_at": utc_now(), "conclusion": conclusion, "tasks": inventory["tasks"],
               "preflight": check, "runs": all_runs, "configuration": {"attempts": args.attempts,
               "environment": environment, "force_build": args.force_build}}
    write_json(out / "report.json", payload)
    (out / "report.md").write_text(markdown_report(payload), encoding="utf-8")
    return 0 if conclusion == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="task directory or ZIP")
    parser.add_argument("--out", type=Path, required=True, help="empty evidence output directory")
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS,
                        help="independent runs per agent; minimum 3, use 6 for strict stability")
    parser.add_argument("--environment", help="Harbor environment override; defaults to bundled WindowsQCEnvironment")
    parser.add_argument("--force-build", action="store_true", help="force a fresh Harbor image build")
    args = parser.parse_args()
    if args.attempts < 3:
        parser.error("--attempts must be at least 3")
    try:
        return run(args)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
