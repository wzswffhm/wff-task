# -*- coding: utf-8 -*-
"""149 fix9 三模型重判官：复用 fix8 正式 trial 的 agent 产物 + 修复后 tests 重跑 test.sh。
oracle 已由 harbor trial start 重跑通过（G4=1.0），此脚本只处理三模型。
"""
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
TASK = "FIN3-WKN-149"
IMAGE = "fin3-wkn-149:local"
# 三模型：fix8 正式 trial 的 agent 产物 + 重判目标目录
MODELS = {
    "qwen3.8-max-0902": "/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-qwen/FIN3-WKN-149__uqNx7ti/artifacts/app/output",
    "gpt-5.6-sol": "/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-gpt/FIN3-WKN-149__qsFcMtD/artifacts/app/output",
    "claude-opus-4-8": "/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-opus/FIN3-WKN-149__vTPHQTW/artifacts/app/output",
}
CREDS = pathlib.Path("/mnt/c/Users/Administrator/.wff-creds/judge.env")
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


def tests_dir() -> pathlib.Path:
    return H / TASK / "tests"


def inputs_dir() -> pathlib.Path:
    return H / TASK / "environment" / "input_files"


def logs_dir(executor: str) -> pathlib.Path:
    return H / TASK / "_rejudge" / executor


def cname(executor: str) -> str:
    return f"rejudge-{TASK}-{executor}"


def docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          errors="replace", encoding="utf-8")


def container_running(name: str) -> bool:
    r = docker("ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}")
    return name in (r.stdout or "")


def read_state(executor: str) -> tuple[str, dict | None]:
    v = logs_dir(executor) / "verifier"
    rp, ep = v / "reward.json", v / "reward_exit_message.json"
    if rp.is_file() and not ep.is_file():
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
            if float(data.get("criteria_counted") or 0) >= 1:
                return "done", data
        except Exception:  # noqa: BLE001
            pass
    return "pending", None


def fail_reason(executor: str) -> str:
    p = logs_dir(executor) / "verifier" / "reward_exit_message.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return f"{d.get('exit_code')}: {str(d.get('exit_reason'))[:110]}"
    except Exception:  # noqa: BLE001
        return "(no error file)"


def launch(executor: str, creds: dict[str, str]) -> tuple[bool, str]:
    output = pathlib.Path(MODELS[executor])
    tests, inputs = tests_dir(), inputs_dir()
    if not output.is_dir():
        return False, f"missing output {output}"
    if not tests.is_dir() or not inputs.is_dir():
        return False, "missing tests or inputs"
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
    with open(logs / f"{executor}.out", "ab") as so, \
            open(logs / f"{executor}.err", "ab") as se:
        p = subprocess.Popen(command, stdout=so, stderr=se)
    return True, f"pid={p.pid}"


def wait_appear(name: str, timeout: int = 180) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if container_running(name):
            return True
        time.sleep(4)
    return container_running(name)


def handle(executor: str, creds: dict[str, str], timeout_min: int,
           attempts: int, cooldown: int) -> dict:
    name = cname(executor)
    for attempt in range(1, attempts + 1):
        if not container_running(name):
            state, data = read_state(executor)
            if state == "done":
                return {"status": "done", **data}
            ok, info = launch(executor, creds)
            if not ok:
                log(f"launch failed {executor}: {info}")
                return {"status": "launch_failed", "detail": info}
            wait_appear(name)
            if not container_running(name):
                state, data = read_state(executor)
                if state == "done":
                    return {"status": "done", **data}
                log(f"container vanished {executor}: {fail_reason(executor)}; retry 30s")
                time.sleep(30)
            else:
                log(f"started {executor} attempt={attempt} ({info})")
        else:
            log(f"waiting running {executor}")
        deadline = time.time() + timeout_min * 60
        while time.time() < deadline:
            state, data = read_state(executor)
            if state == "done":
                log(f"done {executor} reward={data.get('reward')} "
                    f"counted={data.get('criteria_counted')} err={data.get('verifier_error')}")
                return {"status": "done", **data}
            if not container_running(name):
                break
            time.sleep(30)
        else:
            log(f"timeout {executor} after {timeout_min}m")
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout-min", type=int, default=180)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--cooldown", type=int, default=90)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if not tests_dir().is_dir() or not inputs_dir().is_dir():
        raise SystemExit(f"missing tests/inputs under {H / TASK}")
    if args.status:
        for ex in MODELS:
            print(f"  {ex:20} {status_line(ex)}")
        return 0

    creds = load_creds()
    log(f"judge={creds.get('JUDGE_MODEL')} protocol={creds.get('JUDGE_API_PROTOCOL')} "
        f"image={IMAGE} workers={args.workers}")
    log(f"tests={tests_dir()}  inputs={inputs_dir()}")

    results: dict[str, dict] = {}
    pending = [ex for ex in MODELS if read_state(ex)[0] != "done"]
    queue = collections.deque(pending)
    log(f"pending={pending}")

    def worker() -> None:
        while True:
            with QLOCK:
                ex = queue.popleft() if queue else None
            if ex is None:
                return
            r = handle(ex, creds, args.timeout_min, args.attempts, args.cooldown)
            with LOCK:
                results[ex] = r

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("\n=== summary ===")
    ok = 0
    for ex in MODELS:
        r = results.get(ex) or {"status": "already_done"}
        print(f"  {ex:20} {r}")
        if r.get("status") in {"done", "already_done"}:
            ok += 1
    print(f"success {ok}/{len(MODELS)}")
    return 0 if ok == len(MODELS) else 2


if __name__ == "__main__":
    raise SystemExit(main())
