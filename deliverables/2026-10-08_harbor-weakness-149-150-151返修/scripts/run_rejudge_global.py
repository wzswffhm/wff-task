"""FIN3-WKN-149/150/151 判官重跑驱动（**全局队列 + 3 worker**）。

为何不用「题内串行」：那种调度下每题的 4 场必须排队，一旦某题多跑一轮
（如 150-qwen 撞 429 重试），该题就成了拖尾，而别的题跑完的并发槽位却闲置。

本版改为全局工作队列：共 MAX_CONCURRENT 个 worker，谁空谁领下一个 (题目, 执行体)，
从而让并发槽位始终被占满，显著缩短总时长。

完成判定：`test.sh` 开头即写入 fail-closed 占位 reward.json 并留下
reward_exit_message.json；只有 finalize.py 成功收尾才删除该错误文件。
因此「完成」= reward_exit_message.json 不存在 且 criteria_counted >= 1。
（注意：占位文件在运行期间一直存在，绝不能据此判为失败。）

用法:
    python run_rejudge_global.py --status
    python run_rejudge_global.py --workers 3 --attempts 3 --cooldown 90
"""
import argparse
import collections
import json
import pathlib
import subprocess
import sys
import threading
import time

PY = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
REJUDGE = pathlib.Path(r"C:\Users\Administrator\Desktop\weakness-data-construction\scripts\rejudge_by_docker.py")
REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"
CREDS = pathlib.Path(r"C:\Users\Administrator\.wff-creds\judge.env")

TASKS = {
    "FIN3-WKN-149": ("work-金融-资产管理-20261008", "fin3-wkn-149:local"),
    "FIN3-WKN-150": ("work-金融-私募股权投资-20261008", "fin3-wkn-150:local"),
    "FIN3-WKN-151": ("work-金融-商业银行-20261008", "fin3-wkn-151:local"),
}
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

LOCK = threading.Lock()
RESULTS = {}


def log(msg):
    with LOCK:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def cname(task, ex):
    return f"rejudge-{task}-{ex}"


def container_running(name):
    p = subprocess.run(["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
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


def launch(task, ex):
    batch, image = TASKS[task]
    art = H / batch / "跑分产物与轨迹" / ex / "output"
    if not art.is_dir():
        return False, f"交付物目录不存在 {art}"
    cmd = [PY, str(REJUDGE), str(H / task), image, f"{ex}={art}", "--creds", str(CREDS)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode == 0, ((p.stdout or "") + (p.stderr or ""))[-160:]


def wait_appear(name, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if container_running(name):
            return True
        time.sleep(4)
    return container_running(name)


def handle(task, ex, timeout_min, attempts, cooldown):
    """启动或接续等待一场判分，失败重试。返回结果 dict。"""
    name = cname(task, ex)

    for attempt in range(1, attempts + 1):
        if not container_running(name):
            st, d = read_state(task, ex)
            if st == "done":
                log(f"  == {task}/{ex} 已完成 reward={d.get('reward')}")
                return {"status": "done", **{k: d.get(k) for k in
                        ("reward", "criteria_counted", "verifier_error")}}
            ok, err = launch(task, ex)
            if not ok:
                log(f"  !! {task}/{ex} 启动失败: {err}")
                return {"status": "launch_failed"}
            wait_appear(name)
            if not container_running(name):
                st, d = read_state(task, ex)
                if st == "done":
                    log(f"  OK {task}/{ex}（极快完成）reward={d.get('reward')}")
                    return {"status": "done", **{k: d.get(k) for k in
                            ("reward", "criteria_counted", "verifier_error")}}
                log(f"  !! {task}/{ex} 启动后未见容器，20s 后复查")
                time.sleep(20)
            else:
                log(f"  >> {task}/{ex} 第 {attempt} 次起跑")
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
            log(f"  !! {task}/{ex} 超时 {timeout_min} min")
            return {"status": "timeout"}

        st, _ = read_state(task, ex)
        if st == "done":
            return {"status": "done"}
        log(f"  !! {task}/{ex} 第 {attempt} 次失败（{fail_reason(task, ex)}）；{cooldown}s 后重试")
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
        return f"待重试（{fail_reason(task, ex)[:52]}）"
    return "排队中"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout-min", type=int, default=180)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    pairs = [(t, e) for t in TASKS for e in EXECUTORS]
    if a.status:
        for t, e in pairs:
            print(f"  {t:14s} {e:20s} {status_line(t, e)}")
        return 0

    # 已在跑的容器先占用槽位；其余未完成项进全局队列
    inflight = [p for p in pairs if container_running(cname(*p))]

    # 队列优先级：先让「剩余场次少」的题收尾，从而更早拿到某题完整的三模型分数
    pending = [p for p in pairs if p not in inflight and read_state(*p)[0] != "done"]
    left_per_task = collections.Counter(t for t, _ in pending)
    queue = collections.deque(
        sorted(pending, key=lambda p: (left_per_task[p[0]], p[0], p[1])))

    log(f"全局调度：workers={a.workers}  在跑={len(inflight)}  队列={len(queue)}  "
        f"单场上限={a.timeout_min}min  最多 {a.attempts} 次")

    qlock = threading.Lock()

    def next_item():
        with qlock:
            return queue.popleft() if queue else None

    def worker(initial):
        # 关键：handle() 内部会调用 log()，而 log() 需要获取 LOCK。
        # threading.Lock 不可重入，因此**绝不能**在持锁状态下调用 handle()，
        # 否则 worker 会自我死锁（表现为启动后只有首行日志、再无任何输出）。
        # 正确做法：先无锁执行 handle()，拿到结果后再持锁写入 RESULTS。
        if initial is not None:
            r = handle(*initial, a.timeout_min, a.attempts, a.cooldown)
            with LOCK:
                RESULTS[initial] = r
        while True:
            item = next_item()
            if item is None:
                return
            r = handle(*item, a.timeout_min, a.attempts, a.cooldown)
            with LOCK:
                RESULTS[item] = r

    stop_hb = threading.Event()

    def heartbeat():
        """独立心跳线程：即便某个 worker 卡住，也能从日志一眼看出调度是否停滞。"""
        while not stop_hb.wait(180):
            running = [p for p in pairs if container_running(cname(*p))]
            done = sum(1 for p in pairs if read_state(*p)[0] == "done")
            with qlock:
                left = len(queue)
            log(f"心跳: 已完成 {done}/12  在跑 {len(running)}  队列剩余 {left}")

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
