"""FIN3-WKN-149/150/151 判官重跑驱动（低并发 + 失败重试）。

并发策略：**题间并行、题内串行** → 同时最多 3 个判官会话。
原因：判官端点对并发敏感。实测 12 路并发时单场判分跑到约 23 轮即被
HTTP 429 拒绝（`judge:scorer_error` / `api_error_status: 429`），整场白跑。

失败重试：容器退出但未成功收尾（多为 429）时，等待冷却后原样重跑，最多 3 次。

完成判定：`test.sh` 开头即写入 fail-closed 占位 reward.json 并留下
reward_exit_message.json；只有 finalize.py 成功收尾才删除该错误文件。
故「完成」= reward_exit_message.json 不存在 且 criteria_counted >= 1。

用法:
    python run_rejudge.py --status
    python run_rejudge.py                 # 题间并行、题内串行跑全部 12 场
"""
import argparse
import json
import pathlib
import subprocess
import sys
import threading
import time

PY = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
REJUDGE = pathlib.Path(r"C:\Users\Administrator\Desktop\weakness-data-construction\scripts\rejudge_by_docker.py")
REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK_ROOT = REPO / "harbor-weakness"
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
    ver = TASK_ROOT / task / "_rejudge" / ex / "verifier"
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
    p = TASK_ROOT / task / "_rejudge" / ex / "verifier" / "reward_exit_message.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return f"{d.get('exit_code')}: {str(d.get('exit_reason'))[:120]}"
    except Exception:  # noqa: BLE001
        return "(无错误文件)"


def launch(task, ex):
    batch, image = TASKS[task]
    art = TASK_ROOT / batch / "跑分产物与轨迹" / ex / "output"
    if not art.is_dir():
        return False, f"交付物目录不存在 {art}"
    cmd = [PY, str(REJUDGE), str(TASK_ROOT / task), image, f"{ex}={art}", "--creds", str(CREDS)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode == 0, (p.stdout or "")[-160:] + (p.stderr or "")[-160:]


def wait_appear(name, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if container_running(name):
            return True
        st_done = False
        time.sleep(4)
        if st_done:
            break
    return container_running(name)


def run_one(task, ex, timeout_min, max_attempts, cooldown_sec):
    name = cname(task, ex)

    # 已在跑（例如上一轮保留的容器）→ 直接等待
    if container_running(name):
        log(f"  ~~ {task}/{ex} 容器已在运行，接续等待")
    else:
        st, d = read_state(task, ex)
        if st == "done":
            log(f"  == {task}/{ex} 已完成 reward={d.get('reward')}")
            return {"status": "done", **{k: d.get(k) for k in ("reward", "criteria_counted", "verifier_error")}}

    for attempt in range(1, max_attempts + 1):
        if not container_running(name):
            ok, err = launch(task, ex)
            if not ok:
                log(f"  !! {task}/{ex} 启动失败: {err}")
                return {"status": "launch_failed"}
            wait_appear(name)
            if not container_running(name):
                st, d = read_state(task, ex)
                if st == "done":
                    log(f"  OK {task}/{ex}（极快完成）reward={d.get('reward')}")
                    return {"status": "done", **{k: d.get(k) for k in ("reward", "criteria_counted", "verifier_error")}}
                log(f"  !! {task}/{ex} 启动后未见容器，20s 后复查")
                time.sleep(20)
            else:
                log(f"  >> {task}/{ex} 起跑（第 {attempt} 次尝试）")

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
        log(f"  !! {task}/{ex} 第 {attempt} 次判分失败（{fail_reason(task, ex)}）；"
            f"{cooldown_sec}s 后重试")
        time.sleep(cooldown_sec)

    return {"status": "failed_after_retries"}


def run_task(task, executors, timeout_min, max_attempts, cooldown_sec):
    for ex in executors:
        r = run_one(task, ex, timeout_min, max_attempts, cooldown_sec)
        with LOCK:
            RESULTS[(task, ex)] = r


def status_line(task, ex):
    st, d = read_state(task, ex)
    if st == "done":
        return f"完成 reward={d.get('reward')} counted={d.get('criteria_counted')}"
    if container_running(cname(task, ex)):
        return "判分中"
    ver = TASK_ROOT / task / "_rejudge" / ex / "verifier"
    if (ver / "reward_exit_message.json").is_file():
        return f"未成功收尾（{fail_reason(task, ex)[:60]}）"
    return "未启动"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout-min", type=int, default=180, help="单场判分上限")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--cooldown", type=int, default=90, help="失败重试前冷却秒数")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    pairs = [(t, e) for t in TASKS for e in EXECUTORS]
    if a.status:
        for t, e in pairs:
            print(f"  {t:14s} {e:20s} {status_line(t, e)}")
        return 0

    log(f"判官重跑：题间并行(3)、题内串行；单场上限 {a.timeout_min}min，最多 {a.attempts} 次")
    ths = [threading.Thread(target=run_task,
                            args=(t, EXECUTORS, a.timeout_min, a.attempts, a.cooldown))
           for t in TASKS]
    for t in ths:
        t.start()
    for t in ths:
        t.join()

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
