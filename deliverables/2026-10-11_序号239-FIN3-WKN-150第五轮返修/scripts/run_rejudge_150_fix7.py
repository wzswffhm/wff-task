# -*- coding: utf-8 -*-
"""序号 239 第五轮：使用现有原生交付物重跑受影响判官。"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"
CREDS = pathlib.Path(r"C:\Users\Administrator\.wff-creds\judge.env")
STAGE = pathlib.Path(r"C:\Users\Administrator\.wff-creds\rejudge-stage-fix7")
TASK = "FIN3-WKN-150"
BATCH = "work_fin-b01_20261006_fix7-150"
IMAGE = "fin3-wkn-150:local"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
DEFAULT_EXECUTORS = EXECUTORS
GRACE_SEC = 75
DOCKER_CLI = r"C:\Program Files\Docker\Docker\DockerCli.exe"
DOCKER_EXE = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
LOCK = threading.Lock()


def log(message: str) -> None:
    with LOCK:
        print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def load_creds() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in CREDS.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    for key in ("JUDGE_API_KEY", "JUDGE_BASE_URL"):
        if not env.get(key):
            raise SystemExit(f"missing {key} in {CREDS}")
    return env


def task_dir() -> pathlib.Path:
    return H / BATCH / TASK


def artifacts_dir(executor: str) -> pathlib.Path:
    return task_dir() / "跑分产物与轨迹" / executor / "output"


def logs_dir(executor: str) -> pathlib.Path:
    return task_dir() / "_rejudge" / executor


def container_name(executor: str) -> str:
    return f"rejudge-{TASK}-{executor}"


def docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          errors="replace", encoding="utf-8")


def engine_ok() -> bool:
    return docker("version", "--format", "{{.Server.Version}}").returncode == 0


def ensure_engine(tries: int = 40) -> bool:
    if engine_ok():
        return True
    for attempt in range(tries):
        if attempt == 0:
            subprocess.run([DOCKER_CLI, "-Shutdown"], capture_output=True)
            time.sleep(10)
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f'Start-Process "{DOCKER_EXE}"'], capture_output=True)
        log(f"Docker engine unavailable, starting and waiting ({attempt + 1}/{tries})")
        for _ in range(6):
            time.sleep(10)
            if engine_ok():
                log("Docker engine ready")
                return True
    return False


def container_state(name: str) -> str:
    result = docker("ps", "-a", "--format", "{{.Names}}")
    if result.returncode != 0:
        return "engine-down"
    return "running" if name in (result.stdout or "").split() else "gone"


def read_state(executor: str) -> tuple[str, dict | None]:
    verifier = logs_dir(executor) / "verifier"
    reward_path = verifier / "reward.json"
    error_path = verifier / "reward_exit_message.json"
    if reward_path.is_file() and not error_path.is_file():
        data = json.loads(reward_path.read_text(encoding="utf-8"))
        if float(data.get("criteria_counted") or 0) >= 1:
            return "done", data
    return "pending", None


def fail_reason(executor: str) -> str:
    path = logs_dir(executor) / "verifier" / "reward_exit_message.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return f"{data.get('exit_code')}: {str(data.get('exit_reason'))[:110]}"
    except Exception:  # noqa: BLE001
        return "(no error file)"


def stage_materials(executor: str, reset_tests: bool) -> tuple[pathlib.Path | None, str]:
    root = STAGE / TASK
    tests_dst = root / "tests"
    input_dst = root / "input_files"
    output_dst = root / "output" / executor
    if reset_tests and tests_dst.exists():
        shutil.rmtree(tests_dst)
    if not tests_dst.is_dir():
        shutil.copytree(task_dir() / "tests", tests_dst,
                       ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if not input_dst.is_dir():
        shutil.copytree(task_dir() / "environment" / "input_files", input_dst)
    output_dst.mkdir(parents=True, exist_ok=True)
    source = artifacts_dir(executor)
    if not source.is_dir():
        return None, f"missing native output {source}"
    copied = 0
    for dirpath, _dirnames, filenames in os.walk(source):
        relative = os.path.relpath(dirpath, source)
        target = output_dst / relative if relative != "." else output_dst
        target.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            src = pathlib.Path(dirpath) / name
            dst = target / name
            if not dst.is_file() or src.read_bytes() != dst.read_bytes():
                shutil.copy2(src, dst)
                copied += 1
    return output_dst, f"copied {copied} files"


def launch(executor: str, creds: dict[str, str], reset_tests: bool) -> tuple[bool, str]:
    output_dst, note = stage_materials(executor, reset_tests)
    if output_dst is None:
        return False, note
    logs = logs_dir(executor)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "verifier").mkdir(parents=True, exist_ok=True)
    for stale in ("reward.json", "reward.txt", "reward_exit_message.json"):
        (logs / "verifier" / stale).unlink(missing_ok=True)
    name = container_name(executor)
    docker("rm", "-f", name)
    root = STAGE / TASK
    command = [
        "docker", "run", "--rm", "--name", name,
        "--mount", f"type=bind,source={root / 'tests'},target=/tests",
        "--mount", f"type=bind,source={root / 'input_files'},target=/app/input_files,readonly",
        "--mount", f"type=bind,source={output_dst},target=/app/output",
        "--mount", f"type=bind,source={logs},target=/logs",
        "-e", f"JUDGE_API_KEY={creds['JUDGE_API_KEY']}",
        "-e", f"JUDGE_BASE_URL={creds['JUDGE_BASE_URL']}",
        "-e", f"JUDGE_MODEL={creds.get('JUDGE_MODEL', 'qwen3.7-plus')}",
        "-e", f"JUDGE_PROVIDER={creds.get('JUDGE_PROVIDER', 'anthropic')}",
        "-e", f"JUDGE_API_PROTOCOL={creds.get('JUDGE_API_PROTOCOL', 'anthropic')}",
        "-e", "LITELLM_LOCAL_MODEL_COST_MAP=True",
        "-e", "LITELLM_DROP_PARAMS=true",
        IMAGE, "bash", "-c",
        "sed -i 's/\\r$//' /tests/*.sh /tests/*.py 2>/dev/null; bash /tests/test.sh",
    ]
    with open(logs / f"{executor}.out", "ab") as stdout, \
            open(logs / f"{executor}.err", "ab") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
    return True, f"{note}; pid={process.pid}"


def wait_match(executor: str, timeout_minutes: int) -> tuple[str, dict | None]:
    name = container_name(executor)
    started = time.time()
    while True:
        time.sleep(20)
        elapsed = time.time() - started
        state, data = read_state(executor)
        if state == "done":
            return "done", data
        if elapsed > timeout_minutes * 60:
            docker("rm", "-f", name)
            return "timeout", None
        container = container_state(name)
        if container == "engine-down":
            log(f"{executor}: Docker engine lost, waiting for recovery")
            recovery_started = time.time()
            while time.time() - recovery_started < 1800:
                if ensure_engine(tries=1):
                    break
                time.sleep(20)
            continue
        if container == "gone" and elapsed > GRACE_SEC:
            state, data = read_state(executor)
            return ("done", data) if state == "done" else ("failed", None)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executors", default=",".join(DEFAULT_EXECUTORS))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-min", type=int, default=120)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--cooldown", type=int, default=90)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    wanted = [item.strip() for item in args.executors.split(",") if item.strip()]

    if args.check:
        print(f"engine_ok={engine_ok()} image={IMAGE} task_dir={task_dir()} exists={task_dir().is_dir()}")
        for executor in EXECUTORS:
            state, data = read_state(executor)
            print(f"  {executor:20} state={state:8} "
                  f"reward={data.get('reward') if data else None} "
                  f"last={fail_reason(executor)}")
        return 0

    if not task_dir().is_dir():
        raise SystemExit(f"missing batch task directory: {task_dir()}")
    creds = load_creds()
    log(f"judge={creds.get('JUDGE_BASE_URL', '')[:32]}... model={creds.get('JUDGE_MODEL')}")
    log(f"executors={wanted} workers={args.workers} timeout={args.timeout_min}m")

    first_launch = True
    for attempt in range(1, args.attempts + 1):
        pending = [executor for executor in wanted if read_state(executor)[0] != "done"]
        if not pending:
            break
        log(f"attempt {attempt}/{args.attempts}, pending={pending}")
        for index in range(0, len(pending), args.workers):
            wave = pending[index:index + args.workers]
            for executor in wave:
                if not ensure_engine():
                    log("Docker engine could not be recovered; aborting")
                    return 3
                ok, note = launch(executor, creds, reset_tests=first_launch)
                log(f"launch {executor}: {note}" if ok else f"FAILED {executor}: {note}")
                first_launch = False
            for executor in wave:
                status, data = wait_match(executor, args.timeout_min)
                if status == "done":
                    log(f"done {executor} reward={data.get('reward')} "
                        f"counted={data.get('criteria_counted')} err={data.get('verifier_error')}")
                else:
                    log(f"FAILED {executor} {status}: {fail_reason(executor)}")
                    docker("rm", "-f", container_name(executor))
        if any(read_state(executor)[0] != "done" for executor in wanted):
            log(f"cooldown {args.cooldown}s before retry")
            time.sleep(args.cooldown)

    print("\n=== summary ===")
    failed = False
    for executor in EXECUTORS:
        state, data = read_state(executor)
        print(f"  {executor:20} {state:8} reward={data.get('reward') if data else None} "
              f"counted={data.get('criteria_counted') if data else None} "
              f"err={data.get('verifier_error') if data else None}")
        if data is None and executor in wanted:
            failed = True
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
