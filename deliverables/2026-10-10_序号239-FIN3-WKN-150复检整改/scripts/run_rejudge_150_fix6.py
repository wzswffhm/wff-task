# -*- coding: utf-8 -*-
"""FIN3-WKN-150 复检整改（序号 239 / 2026-10-09 报告）后的判官重跑驱动（v2·加固版）。

与 v1（`.workbuddy/tmp/run_rejudge_150_win.py`）及本目录 v1 的差异：
1. 批次目录换为 `work_fin-b01_20261006_fix6-150`（本轮整改产物）；
2. 判分暂存换为全新 ASCII 路径 `rejudge-stage-fix6`，且**首次运行强制重建 tests/**，
   避免复用上一轮旧 `tests/`（本轮改了 `tests/__golden_output`）；
3. **等待逻辑加固**：v1 用 `docker ps`（只看运行中容器）判断结束，在
   (a) 容器启动尚未进入 Up、(b) Docker 引擎掉线（`docker ps` 报错返回空）两种情况下
   都会误判为"已结束"并 `docker rm -f` 杀掉正在判分的容器 —— 2026-10-10 首轮实测
   即因此把 oracle 判分中途杀掉（占位 `reward_exit_message.json`）。
   现改为：区分 `running / gone / engine-down`，引擎掉线时**自动拉起 Docker Desktop
   并等待恢复**，并设 75 秒启动宽限期，绝不误杀。

用法:
    python run_rejudge_150_fix6.py --check
    python run_rejudge_150_fix6.py --executors oracle --workers 1
    python run_rejudge_150_fix6.py --workers 1            # 四场串行
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"
CREDS = pathlib.Path(r"C:\Users\Administrator\.wff-creds\judge.env")
STAGE = pathlib.Path(r"C:\Users\Administrator\.wff-creds\rejudge-stage-fix6")
DOCKER_CLI = r"C:\Program Files\Docker\Docker\DockerCli.exe"
DOCKER_EXE = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"

TASK = "FIN3-WKN-150"
BATCH = "work_fin-b01_20261006_fix6-150"
IMAGE = "fin3-wkn-150:local"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
GRACE_SEC = 75

LOCK = threading.Lock()


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


def task_dir():
    return H / BATCH / TASK


def artifacts_dir(ex):
    return task_dir() / "跑分产物与轨迹" / ex / "output"


def logs_dir(ex):
    return task_dir() / "_rejudge" / ex


def cname(ex):
    return f"rejudge-{TASK}-{ex}"


def docker_out(*args):
    p = subprocess.run(["docker", *args], capture_output=True, text=True, errors="replace")
    return p.returncode, (p.stdout or "")


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True, errors="replace")


def engine_ok():
    return docker_out("version", "--format", "{{.Server.Version}}")[0] == 0


def ensure_engine(tries=40):
    """引擎不可用时自动拉起 Docker Desktop 并等待就绪。"""
    if engine_ok():
        return True
    for i in range(tries):
        if i == 0:
            subprocess.run([DOCKER_CLI, "-Shutdown"], capture_output=True)
            time.sleep(10)
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f'Start-Process "{DOCKER_EXE}"'], capture_output=True)
        log(f"  Docker 引擎不可用，正在拉起并等待就绪（{i + 1}/{tries}）…")
        for _ in range(6):
            time.sleep(10)
            if engine_ok():
                log("  Docker 引擎已就绪")
                return True
    return False


def container_state(name):
    rc, out = docker_out("ps", "-a", "--format", "{{.Names}}")
    if rc != 0:
        return "engine-down"
    return "running" if name in out.split() else "gone"


def read_state(ex):
    ver = logs_dir(ex) / "verifier"
    rj, rem = ver / "reward.json", ver / "reward_exit_message.json"
    if rj.is_file() and not rem.is_file():
        try:
            d = json.loads(rj.read_text(encoding="utf-8"))
            if float(d.get("criteria_counted") or 0) >= 1:
                return "done", d
        except Exception:  # noqa: BLE001
            pass
    return "pending", None


def fail_reason(ex):
    p = logs_dir(ex) / "verifier" / "reward_exit_message.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return f"{d.get('exit_code')}: {str(d.get('exit_reason'))[:110]}"
    except Exception:  # noqa: BLE001
        return "(无错误文件)"


def stage_materials(ex, reset_tests=False):
    """tests / input_files / 该执行体交付物 → 纯 ASCII 暂存目录（规避中文路径挂载）。"""
    root = STAGE / TASK
    tests_dst = root / "tests"
    inp_dst = root / "input_files"
    out_dst = root / "output" / ex
    if reset_tests and tests_dst.exists():
        shutil.rmtree(tests_dst)
    if not tests_dst.is_dir():
        shutil.copytree(task_dir() / "tests", tests_dst,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if not inp_dst.is_dir():
        shutil.copytree(task_dir() / "environment" / "input_files", inp_dst)
    out_dst.mkdir(parents=True, exist_ok=True)
    src = artifacts_dir(ex)
    if not src.is_dir():
        return None, f"交付物目录不存在 {src}"
    n = 0
    for dirpath, _dn, filenames in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        target = out_dst / rel if rel != "." else out_dst
        target.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            s, d = os.path.join(dirpath, name), os.path.join(target, name)
            if os.path.isfile(d) and open(s, "rb").read() == open(d, "rb").read():
                continue
            shutil.copy2(s, d)
            n += 1
    return out_dst, f"复制 {n} 个文件"


def launch(ex, creds, reset_tests=False):
    root = STAGE / TASK
    out_dst, note = stage_materials(ex, reset_tests=reset_tests)
    if out_dst is None:
        return False, note
    logs = logs_dir(ex)
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "verifier").mkdir(parents=True, exist_ok=True)
    for stale in ("reward.json", "reward.txt", "reward_exit_message.json"):
        (logs / "verifier" / stale).unlink(missing_ok=True)
    name = cname(ex)
    docker("rm", "-f", name)
    args = ["docker", "run", "--rm", "--name", name,
            "--mount", f"type=bind,source={root / 'tests'},target=/tests",
            "--mount", f"type=bind,source={root / 'input_files'},target=/app/input_files,readonly",
            "--mount", f"type=bind,source={out_dst},target=/app/output",
            "--mount", f"type=bind,source={logs},target=/logs",
            "-e", f"JUDGE_API_KEY={creds['JUDGE_API_KEY']}",
            "-e", f"JUDGE_BASE_URL={creds['JUDGE_BASE_URL']}",
            "-e", f"JUDGE_MODEL={creds.get('JUDGE_MODEL', 'qwen3.7-plus')}",
            "-e", f"JUDGE_PROVIDER={creds.get('JUDGE_PROVIDER', 'anthropic')}",
            "-e", f"JUDGE_API_PROTOCOL={creds.get('JUDGE_API_PROTOCOL', 'anthropic')}",
            "-e", "LITELLM_LOCAL_MODEL_COST_MAP=True",
            "-e", "LITELLM_DROP_PARAMS=true",
            IMAGE, "bash", "-c",
            "sed -i 's/\\r$//' /tests/*.sh /tests/*.py 2>/dev/null; bash /tests/test.sh"]
    out = open(logs / f"{ex}.out", "ab")
    err = open(logs / f"{ex}.err", "ab")
    p = subprocess.Popen(args, stdout=out, stderr=err)
    return True, f"{note}; pid={p.pid}"


def wait_match(ex, timeout_min):
    """等待单场判分结束。返回 ('done'|'failed'|'timeout', 结果 dict|None)。"""
    name = cname(ex)
    t0 = time.time()
    while True:
        time.sleep(20)
        el = time.time() - t0
        st, d = read_state(ex)
        if st == "done":
            return "done", d
        if el > timeout_min * 60:
            docker("rm", "-f", name)
            return "timeout", None
        cs = container_state(name)
        if cs == "engine-down":
            log(f"  {ex}: Docker 引擎掉线，等待自动恢复…")
            t1 = time.time()
            while time.time() - t1 < 1800:
                if ensure_engine(tries=1):
                    break
                time.sleep(20)
            continue
        if cs == "gone" and el > GRACE_SEC:
            st, d = read_state(ex)
            return ("done", d) if st == "done" else ("failed", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executors", default=",".join(EXECUTORS))
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--timeout-min", type=int, default=120)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    want = [e.strip() for e in args.executors.split(",") if e.strip()]
    if args.check:
        print(f"task     : {TASK}  image={IMAGE}  engine_ok={engine_ok()}")
        print(f"task dir : {task_dir()}  exists={task_dir().is_dir()}")
        print(f"stage    : {STAGE}")
        for ex in EXECUTORS:
            st, d = read_state(ex)
            art = artifacts_dir(ex)
            n = sum(len(f) for _, _, f in os.walk(art)) if art.is_dir() else -1
            print(f"  {ex:20} state={st:8} artifacts={n:3} files")
            if st != "done":
                print(f"      last: {fail_reason(ex)}")
        return 0

    creds = load_creds()
    print(f"判官: {creds.get('JUDGE_BASE_URL', '')[:32]}... model={creds.get('JUDGE_MODEL')} "
          f"protocol={creds.get('JUDGE_API_PROTOCOL')}")
    print(f"镜像: {IMAGE}  并发: {args.workers}  超时: {args.timeout_min}min  执行体: {want}")

    first_launch = True
    for attempt in range(1, args.attempts + 1):
        pending = [e for e in want if read_state(e)[0] != "done"]
        if not pending:
            break
        log(f"第 {attempt}/{args.attempts} 轮，待跑 {pending}")
        for i in range(0, len(pending), args.workers):
            batch = pending[i:i + args.workers]
            for ex in batch:
                if not ensure_engine():
                    log("✘ Docker 引擎无法恢复，中止")
                    return 3
                ok, note = launch(ex, creds, reset_tests=first_launch)
                log(f"  启动 {ex}: {note}" if ok else f"  ✘ {ex} 未启动: {note}")
                first_launch = False
            for ex in batch:
                status, d = wait_match(ex, args.timeout_min)
                if status == "done":
                    log(f"  ✔ {ex} reward={d.get('reward')} counted={d.get('criteria_counted')} "
                        f"err={d.get('verifier_error')}")
                else:
                    log(f"  ✘ {ex} {status}: {fail_reason(ex)}")
                    docker("rm", "-f", cname(ex))
        if any(read_state(e)[0] != "done" for e in want):
            log(f"冷却 {args.cooldown}s 后重试未完成场次")
            time.sleep(args.cooldown)

    print("\n=== 汇总 ===")
    for ex in EXECUTORS:
        st, d = read_state(ex)
        if d:
            print(f"  {ex:20} {st:8} reward={d.get('reward')} counted={d.get('criteria_counted')} "
                  f"verifier_error={d.get('verifier_error')}")
        else:
            print(f"  {ex:20} {st:8} reward=None  last={fail_reason(ex)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
