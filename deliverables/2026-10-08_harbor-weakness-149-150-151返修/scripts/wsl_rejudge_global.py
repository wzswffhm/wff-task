#!/usr/bin/env python3
"""FIN3-WKN-149/150/151 判官重跑驱动 —— WSL 版（独立 Docker 引擎，不占用 Docker Desktop）。

与 Windows 版 `run_rejudge_global.py` 的差异：
  1. 直接在 WSL 内调用 `docker`，使用 WSL 自带的 Docker Engine（Docker Desktop 留给 harbor-windows）；
  2. 路径走 /mnt/c/...（无需 wslpath，仓库固定在 C 盘同一位置）；
  3. 逻辑与判定口径保持一致：完成 = reward.json 存在且 criteria_counted >= 1 且无 reward_exit_message.json。

用法（在 WSL 内执行）:
    python3 wsl_rejudge_global.py --status
    python3 wsl_rejudge_global.py --workers 3 --timeout-min 180 --attempts 3 --cooldown 90
"""
import argparse
import collections
import json
import pathlib
import subprocess
import sys
import threading
import time

H = pathlib.Path("/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness")
CREDS = pathlib.Path("/mnt/c/Users/Administrator/.wff-creds/judge.env")

TASKS = {
    "FIN3-WKN-149": ("work-金融-资产管理-20261008", "fin3-wkn-149:local"),
    "FIN3-WKN-150": ("work-金融-私募股权投资-20261008", "fin3-wkn-150:local"),
    "FIN3-WKN-151": ("work-金融-商业银行-20261008", "fin3-wkn-151:local"),
}
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

LOCK = threading.Lock()
QLOCK = threading.Lock()
RESULTS = {}


def log(msg):
    with LOCK:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_creds():
    env = {}
    for ln in CREDS.read_text(encoding="utf-8-sig").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip()
    for k in ("JUDGE_API_KEY", "JUDGE_BASE_URL"):
        if not env.get(k):
            raise SystemExit(f"缺少 {k}（检查 {CREDS}）")
    return env


def cname(task, ex):
    return f"rejudge-{task}-{ex}"


def container_running(name):
    p = subprocess.run(["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
                       capture_output=True, text=True)
    return name in (p.stdout or "")


def container_exists(name):
    p = subprocess.run(["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
                       capture_output=True, text=True)
    return name in (p.stdout or "")


def read_state(task, ex):
    ver = H / task / "_rejudge" / ex / "verifier"
    rj, rem = ver / "reward.json", ver / "reward_exit_message.json"
    if rj.is_file() and not rem.is_file():
        try:
            d = json.loads(rj.read_text(encoding="utf-8"))
            if float(d.get("criteria_counted") or 0) >= 1:
                return "done", d
        except Exception:  # noqa: BLE001
            pass
    return "pending", None


def fail_reason(task, ex):
    p = H / task / "_rejudge" / ex / "verifier" / "reward_exit_message.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return f"{d.get('exit_code')}: {str(d.get('exit_reason'))[:110]}"
    except Exception:  # noqa: BLE001
        return "(无错误文件)"


def launch(task, ex, creds):
    batch, image = TASKS[task]
    task_dir = H / task
    art = H / batch / "跑分产物与轨迹" / ex / "output"
    if not art.is_dir():
        return False, f"交付物目录不存在 {art}"
    tests = task_dir / "tests"
    inputs = task_dir / "environment" / "input_files"
    if not tests.is_dir():
        return False, f"tests 目录不存在 {tests}"
    logs = task_dir / "_rejudge" / ex
    logs.mkdir(parents=True, exist_ok=True)
    name = cname(task, ex)
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    args = ["docker", "run", "--rm", "--name", name,
            "-v", f"{tests}:/tests",
            "-v", f"{inputs}:/app/input_files:ro",
            "-v", f"{art}:/app/output",
            "-v", f"{logs}:/logs",
            "-e", f"JUDGE_API_KEY={creds['JUDGE_API_KEY']}",
            "-e", f"JUDGE_BASE_URL={creds['JUDGE_BASE_URL']}",
            "-e", f"JUDGE_MODEL={creds.get('JUDGE_MODEL', 'qwen3.7-plus')}",
            "-e", f"JUDGE_API_PROTOCOL={creds.get('JUDGE_API_PROTOCOL', 'anthropic')}",
            "-e", "LITELLM_LOCAL_MODEL_COST_MAP=True",
            "-e", "LITELLM_DROP_PARAMS=true",
            image,
            "bash", "-c",
            "sed -i 's/\\r$//' /tests/*.sh /tests/*.py 2>/dev/null; bash /tests/test.sh"]
    out = open(logs / f"{ex}.out", "ab")
    err = open(logs / f"{ex}.err", "ab")
    p = subprocess.Popen(args, stdout=out, stderr=err)
    return True, f"pid={p.pid}"


def wait_appear(name, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if container_running(name):
            return True
        time.sleep(4)
    return container_running(name)


def handle(task, ex, creds, timeout_min, attempts, cooldown):
    name = cname(task, ex)
    for attempt in range(1, attempts + 1):
        if not container_running(name):
            st, d = read_state(task, ex)
            if st == "done":
                log(f"  == {task}/{ex} 已完成 reward={d.get('reward')}")
                return {"status": "done", **{k: d.get(k) for k in
                        ("reward", "criteria_counted", "verifier_error")}}
            ok, info = launch(task, ex, creds)
            if not ok:
                log(f"  !! {task}/{ex} 启动失败: {info}")
                return {"status": "launch_failed", "detail": info}
            wait_appear(name)
            if not container_running(name):
                st, d = read_state(task, ex)
                if st == "done":
                    log(f"  OK {task}/{ex}（极快完成）reward={d.get('reward')}")
                    return {"status": "done", **{k: d.get(k) for k in
                            ("reward", "criteria_counted", "verifier_error")}}
                log(f"  !! {task}/{ex} 启动后未见容器（{fail_reason(task, ex)}），30s 后复查")
                time.sleep(30)
            else:
                log(f"  >> {task}/{ex} 第 {attempt} 次起跑 ({info})")
        else:
            log(f"  ~~ {task}/{ex} 接续等待已在运行的容器")

        deadline = time.time() + timeout_min * 60
        while time.time() < deadline:
            st, d = read_state(task, ex)
            if st == "done":
                log(f"  OK {task}/{ex}: reward={d.get('reward')} "
                    f"counted={d.get('criteria_counted')} verr={d.get('verifier_error')}")
                return {"status": "done", **{k: d.get(k) for k in
                        ("reward", "criteria_counted", "verifier_error")}}
            if not container_running(name):
                break
            time.sleep(30)
        else:
            log(f"  !! {task}/{ex} 超时 {timeout_min} min，强制结束容器")
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            return {"status": "timeout"}

        st, _ = read_state(task, ex)
        if st == "done":
            return {"status": "done"}
        log(f"  !! {task}/{ex} 第 {attempt} 次失败（{fail_reason(task, ex)}）；{cooldown}s 后重试")
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        time.sleep(cooldown)
    return {"status": "failed_after_retries"}


def status_line(task, ex):
    st, d = read_state(task, ex)
    if st == "done":
        return f"完成 reward={d.get('reward')} counted={d.get('criteria_counted')}"
    if container_running(cname(task, ex)):
        return "判分中"
    ver = H / task / "_rejudge" / ex / "verifier"
    if (ver / "reward_exit_message.json").is_file():
        return f"待重跑（{fail_reason(task, ex)[:52]}）"
    return "排队中"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout-min", type=int, default=180)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--only", default="", help="只跑指定场次，格式 TASK:EXECUTOR，如 FIN3-WKN-151:gpt-5.6-sol")
    ap.add_argument("--task", default="", help="只跑指定题包的全部执行体，如 FIN3-WKN-149")
    a = ap.parse_args()

    pairs = [(t, e) for t in TASKS for e in EXECUTORS]
    if a.task:
        want_t = a.task.strip()
        pairs = [p for p in pairs if p[0] == want_t]
        if not pairs:
            raise SystemExit(f"--task 不匹配任何题包: {want_t}")
    if a.only:
        want = a.only.strip()
        pairs = [p for p in pairs if f"{p[0]}:{p[1]}" == want]
        if not pairs:
            raise SystemExit(f"--only 不匹配任何场次: {want}")
    if a.status:
        for t, e in pairs:
            print(f"  {t:14s} {e:20s} {status_line(t, e)}")
        return 0

    creds = load_creds()
    log(f"凭据: model={creds.get('JUDGE_MODEL')} protocol={creds.get('JUDGE_API_PROTOCOL')} "
        f"base={creds['JUDGE_BASE_URL']}")

    inflight = [p for p in pairs if container_running(cname(*p))]
    pending = [p for p in pairs if p not in inflight and read_state(*p)[0] != "done"]
    left_per_task = collections.Counter(t for t, _ in pending)
    queue = collections.deque(sorted(pending, key=lambda p: (left_per_task[p[0]], p[0], p[1])))

    log(f"全局调度：workers={a.workers} 在跑={len(inflight)} 队列={len(queue)} "
        f"单场上限={a.timeout_min}min 最多 {a.attempts} 次")

    def next_item():
        with QLOCK:
            return queue.popleft() if queue else None

    def worker(initial):
        if initial is not None:
            r = handle(*initial, creds, a.timeout_min, a.attempts, a.cooldown)
            with LOCK:
                RESULTS[initial] = r
        while True:
            item = next_item()
            if item is None:
                return
            r = handle(*item, creds, a.timeout_min, a.attempts, a.cooldown)
            with LOCK:
                RESULTS[item] = r

    stop_hb = threading.Event()

    def heartbeat():
        while not stop_hb.wait(180):
            running = [p for p in pairs if container_running(cname(*p))]
            done = sum(1 for p in pairs if read_state(*p)[0] == "done")
            with QLOCK:
                left = len(queue)
            log(f"心跳: 已完成 {done}/12 在跑 {len(running)} 队列剩余 {left} "
                f"（{', '.join(cname(*p) for p in running)}）")

    ths = []
    threading.Thread(target=heartbeat, daemon=True).start()
    for i in range(a.workers):
        init = inflight[i] if i < len(inflight) else None
        ths.append(threading.Thread(target=worker, args=(init,), daemon=True))
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    stop_hb.set()

    print("\n==== 汇总 ====")
    ok = 0
    for (t, e), r in sorted(RESULTS.items()):
        print(f"  {t:14s} {e:20s} {r}")
        if r.get("status") == "done":
            ok += 1
    print(f"成功 {ok}/{len(RESULTS)}")
    return 0 if ok == len(RESULTS) else 2


if __name__ == "__main__":
    sys.exit(main())
