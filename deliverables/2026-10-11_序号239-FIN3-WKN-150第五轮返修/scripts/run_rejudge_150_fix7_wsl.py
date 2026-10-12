# -*- coding: utf-8 -*-
"""在 WSL Ubuntu 独立 Docker Engine 中重跑 FIN3-WKN-150 第五轮判官。"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")

WSL_ROOT = pathlib.Path("/mnt/c/Users/Administrator/Desktop/wff-task")
H = WSL_ROOT / "harbor-weakness"
CREDS = pathlib.Path("/mnt/c/Users/Administrator/.wff-creds/judge.env")
TASK = "FIN3-WKN-150"
BATCH = "work_fin-b01_20261006_fix7-150"
IMAGE = "fin3-wkn-150:local"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
LOCK = threading.Lock()
QLOCK = threading.Lock()


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


def batch_task_dir() -> pathlib.Path:
    return H / BATCH / TASK


def native_output(executor: str) -> pathlib.Path:
    return batch_task_dir() / "跑分产物与轨迹" / executor / "output"


def logs_dir(executor: str) -> pathlib.Path:
    return H / TASK / "_rejudge" / executor


def cname(executor: str) -> str:
    return f"rejudge-{TASK}-{executor}"


def docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          errors="replace", encoding="utf-8")


def container_running(name: str) -> bool:
    result = docker("ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}")
    return name in (result.stdout or "")


def read_state(executor: str) -> tuple[str, dict | None]:
    verifier = logs_dir(executor) / "verifier"
    reward_path = verifier / "reward.json"
    error_path = verifier / "reward_exit_message.json"
    if reward_path.is_file() and not error_path.is_file():
        try:
            data = json.loads(reward_path.read_text(encoding="utf-8"))
            if float(data.get("criteria_counted") or 0) >= 1:
                return "done", data
        except Exception:  # noqa: BLE001
            pass
    return "pending", None


def fail_reason(executor: str) -> str:
    path = logs_dir(executor) / "verifier" / "reward_exit_message.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return f"{data.get('exit_code')}: {str(data.get('exit_reason'))[:110]}"
    except Exception:  # noqa: BLE001
        return "(no error file)"


def launch(executor: str, creds: dict[str, str]) -> tuple[bool, str]:
    output = native_output(executor)
    tests = batch_task_dir() / "tests"
    inputs = batch_task_dir() / "environment" / "input_files"
    if not output.is_dir():
        return False, f"missing native output {output}"
    if not tests.is_dir() or not inputs.is_dir():
        return False, "missing tests or input_files"
    logs = logs_dir(executor)
    logs.mkdir(parents=True, exist_ok=True)
    name = cname(executor)
    docker("rm", "-f", name)
    command = [
        "docker", "run", "--rm", "--name", name,
        "-v", f"{tests}:/tests",
        "-v", f"{inputs}:/app/input_files:ro",
        "-v", f"{output}:/app/output",
        "-v", f"{logs}:/logs",
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
    return True, f"pid={process.pid}"


def wait_appear(name: str, timeout: int = 180) -> bool:
    started = time.time()
    while time.time() - started < timeout:
        if container_running(name):
            return True
        time.sleep(4)
    return container_running(name)


def handle(executor: str, creds: dict[str, str], timeout_minutes: int,
           attempts: int, cooldown: int) -> dict:
    name = cname(executor)
    for attempt in range(1, attempts + 1):
        if not container_running(name):
            state, data = read_state(executor)
            if state == "done":
                return {"status": "done", "reward": data.get("reward"),
                        "criteria_counted": data.get("criteria_counted"),
                        "verifier_error": data.get("verifier_error")}
            ok, info = launch(executor, creds)
            if not ok:
                log(f"launch failed {executor}: {info}")
                return {"status": "launch_failed", "detail": info}
            wait_appear(name)
            if not container_running(name):
                state, data = read_state(executor)
                if state == "done":
                    return {"status": "done", "reward": data.get("reward"),
                            "criteria_counted": data.get("criteria_counted"),
                            "verifier_error": data.get("verifier_error")}
                log(f"container vanished {executor}: {fail_reason(executor)}; retry in 30s")
                time.sleep(30)
            else:
                log(f"started {executor} attempt={attempt} ({info})")
        else:
            log(f"waiting for running container {executor}")

        deadline = time.time() + timeout_minutes * 60
        while time.time() < deadline:
            state, data = read_state(executor)
            if state == "done":
                log(f"done {executor} reward={data.get('reward')} "
                    f"counted={data.get('criteria_counted')} err={data.get('verifier_error')}")
                return {"status": "done", "reward": data.get("reward"),
                        "criteria_counted": data.get("criteria_counted"),
                        "verifier_error": data.get("verifier_error")}
            if not container_running(name):
                break
            time.sleep(30)
        else:
            log(f"timeout {executor} after {timeout_minutes} minutes")
            docker("rm", "-f", name)
            return {"status": "timeout"}

        if read_state(executor)[0] == "done":
            return {"status": "done"}
        log(f"attempt {attempt} failed {executor}: {fail_reason(executor)}; cooldown {cooldown}s")
        docker("rm", "-f", name)
        time.sleep(cooldown)
    return {"status": "failed_after_retries"}


def status_line(executor: str) -> str:
    state, data = read_state(executor)
    if state == "done":
        return f"done reward={data.get('reward')} counted={data.get('criteria_counted')}"
    if container_running(cname(executor)):
        return "scoring"
    if (logs_dir(executor) / "verifier" / "reward_exit_message.json").is_file():
        return f"retry ({fail_reason(executor)[:52]})"
    return "queued"


def main() -> int:
    global EXECUTORS
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout-min", type=int, default=180)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--cooldown", type=int, default=90)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--only", default="", help="single executor, e.g. oracle")
    args = parser.parse_args()
    if args.only:
        if args.only not in EXECUTORS:
            raise SystemExit(f"unknown executor: {args.only}")
        EXECUTORS = [args.only]

    if not batch_task_dir().is_dir():
        raise SystemExit(f"missing batch: {batch_task_dir()}")
    if args.status:
        for executor in EXECUTORS:
            print(f"  {executor:20} {status_line(executor)}")
        return 0

    creds = load_creds()
    log(f"judge model={creds.get('JUDGE_MODEL')} protocol={creds.get('JUDGE_API_PROTOCOL')}")
    log(f"image={IMAGE} batch={BATCH} workers={args.workers}")

    results: dict[str, dict] = {}
    pending = [executor for executor in EXECUTORS if read_state(executor)[0] != "done"]
    queue = collections.deque(pending)
    log(f"pending={pending}")

    def worker() -> None:
        while True:
            with QLOCK:
                executor = queue.popleft() if queue else None
            if executor is None:
                return
            result = handle(executor, creds, args.timeout_min, args.attempts, args.cooldown)
            with LOCK:
                results[executor] = result

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    print("\n=== summary ===")
    ok = 0
    for executor in EXECUTORS:
        result = results.get(executor) or {"status": "already_done"}
        print(f"  {executor:20} {result}")
        if result.get("status") in {"done", "already_done"}:
            ok += 1
    print(f"success {ok}/{len(EXECUTORS)}")
    return 0 if ok == len(EXECUTORS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
