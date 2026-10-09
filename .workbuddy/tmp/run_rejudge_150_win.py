# -*- coding: utf-8 -*-
"""FIN3-WKN-150 判官重跑驱动（Windows + Docker Desktop Linux 引擎）。

基于 deliverables/2026-10-08_harbor-weakness-149-150-151返修/scripts/wsl_rejudge_global.py，
差异与理由：

1. **不用 WSL**：本机 WSL 发行版磁盘文件缺失（ext4.vhdx 不存在），改用 Windows 宿主上的
   docker CLI + Docker Desktop 的 Linux 引擎；判分镜像本身是 Linux（python:3.12-slim）✓
2. **跑分产物路径已变**：按质检报告第 7 条重组归档后，四执行体证据从批次级
   `<batch>/跑分产物与轨迹/` 移入题目目录内 `<batch>/<task>/跑分产物与轨迹/`。
3. **规避中文路径挂载**：批次与题包路径含中文（金融/私募股权投资/跑分产物与轨迹），
   先把判分所需材料复制到纯 ASCII 暂存目录再挂载，避免 Docker Desktop 路径编码问题。
4. **挂载用 --mount type=bind**：显式声明，避免 -v 的路径解析歧义。

用法：
    python run_rejudge_150_win.py --check                 # 只检查现状
    python run_rejudge_150_win.py --executors oracle      # 只跑 oracle（先验证判官可用）
    python run_rejudge_150_win.py --workers 3             # 跑全部四场
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
STAGE = pathlib.Path(r"C:\Users\Administrator\.wff-creds\rejudge-stage")

TASK = "FIN3-WKN-150"
BATCH = "work-金融-私募股权投资-20261008"
IMAGE = "fin3-wkn-150:local"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

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
    return H / TASK


def batch_dir():
    return H / BATCH


def artifacts_dir(ex):
    """四执行体交付物目录；优先新位置（重组成题目目录内），回退旧位置。"""
    new = batch_dir() / TASK / "跑分产物与轨迹" / ex / "output"
    if new.is_dir():
        return new
    old = batch_dir() / "跑分产物与轨迹" / ex / "output"
    return old


def logs_dir(ex):
    return task_dir() / "_rejudge" / ex


def cname(ex):
    return f"rejudge-{TASK}-{ex}"


def docker(*args, **kw):
    return subprocess.run(["docker", *args], capture_output=True, text=True, **kw)


def container_running(name):
    p = docker("ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}")
    return name in (p.stdout or "")


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


def stage_materials(ex):
    """把 tests / input_files / 该执行体交付物复制到纯 ASCII 暂存目录。"""
    root = STAGE / TASK
    tests_dst = root / "tests"
    inp_dst = root / "input_files"
    out_dst = root / "output" / ex
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


def launch(ex, creds):
    root = STAGE / TASK
    out_dst, note = stage_materials(ex)
    if out_dst is None:
        return False, note
    logs = logs_dir(ex)
    logs.mkdir(parents=True, exist_ok=True)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executors", default=",".join(EXECUTORS),
                    help="逗号分隔，默认全部四场")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--timeout-min", type=int, default=200)
    ap.add_argument("--attempts", type=int, default=2)
    ap.add_argument("--cooldown", type=int, default=60)
    ap.add_argument("--check", action="store_true", help="只打印现状")
    args = ap.parse_args()

    want = [e.strip() for e in args.executors.split(",") if e.strip()]
    if args.check:
        print(f"task      : {TASK}  image={IMAGE}")
        print(f"batch     : {batch_dir()}  exists={batch_dir().is_dir()}")
        print(f"task dir  : {task_dir()}  exists={task_dir().is_dir()}")
        for ex in EXECUTORS:
            st, d = read_state(ex)
            art = artifacts_dir(ex)
            n = sum(len(f) for _, _, f in os.walk(art)) if art.is_dir() else -1
            print(f"  {ex:20} state={st:8} artifacts={n:3} files  {art}")
            if st != "done":
                print(f"      last fail: {fail_reason(ex)}")
        return 0

    creds = load_creds()
    STAGE.mkdir(parents=True, exist_ok=True)
    print(f"判官: {creds.get('JUDGE_BASE_URL', '')[:32]}... model={creds.get('JUDGE_MODEL')} "
          f"protocol={creds.get('JUDGE_API_PROTOCOL')}")
    print(f"镜像: {IMAGE}  并发: {args.workers}  超时: {args.timeout_min}min  执行体: {want}")

    while True:
        pending = [e for e in want if read_state(e)[0] != "done"]
        if not pending:
            break
        batch = pending[:args.workers]
        for ex in batch:
            ok, note = launch(ex, creds)
            log(f"  启动 {ex}: {note}")
            if not ok:
                want.remove(ex) if ex in want else None
        t0 = time.time()
        while time.time() - t0 < args.timeout_min * 60:
            time.sleep(20)
            if not any(container_running(cname(e)) for e in batch):
                break
        for ex in batch:
            st, d = read_state(ex)
            if st == "done":
                log(f"  ✔ {ex} reward={d.get('reward')} counted={d.get('criteria_counted')}")
            else:
                log(f"  ✘ {ex} 未完成: {fail_reason(ex)}")
                docker("rm", "-f", cname(ex))
        if any(read_state(e)[0] != "done" for e in want):
            log(f"  冷却 {args.cooldown}s 后重试未完成场次")
            time.sleep(args.cooldown)

    print("\n=== 汇总 ===")
    for ex in want:
        st, d = read_state(ex)
        print(f"  {ex:20} {st:8} reward={d.get('reward') if d else None}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
