"""用 claude-opus-5 反复补跑 Opus 轮次，直到 3 轮都是有效轮次。

有效 = 轨迹里不含上游兜底文本（"上游模型未返回任何内容"）且已产出正式分。
含兜底文本的轮次按无效槽位归档后补跑（不丢弃任何证据）。
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
BUILD = ROOT / "harbor-windows" / "_qc_runs" / "wciocp-build"
MODEL_ROUNDS = BUILD / "model-rounds"
JOBS = MODEL_ROUNDS / "jobs"
ARCHIVE = MODEL_ROUNDS / "invalid-slots-archive" / "opus-5-fallback-text-20261015"
RUNNER = BUILD / "run_wciocp_model_rounds.py"
PY = r"C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
FALLBACK = "上游模型未返回任何内容"


def trial_dir(idx: int):
    """取该轮最新的 trial 目录（目录里可能堆积多次尝试的残留）。"""
    d = JOBS / f"model-opus-{idx}"
    if not d.is_dir():
        return None
    subs = [x for x in d.iterdir() if x.is_dir()]
    if not subs:
        return None
    return max(subs, key=lambda p: p.stat().st_mtime)


MIN_STEPS = 10
MIN_OUT_TOKENS = 2000


def verdict(idx: int) -> str:
    """有效轮次 = 无上游兜底文本 + 模型确实工作过 + 已产出正式分。

    这里有第三类无效：上游只回了几百 token 就 end_turn（实测正常轮 29-40 步、
    1.7 万-4.3 万输出 token；截断轮 5-6 步、139-188 token、零补丁），属于上游
    输出截断而非模型的真实发挥。
    """
    t = trial_dir(idx)
    if t is None:
        return "missing"
    traj = t / "agent" / "trajectory.jsonl"
    if not traj.is_file():
        return "missing"
    if FALLBACK in traj.read_text(encoding="utf-8", errors="replace"):
        return "fallback"
    mr_path = t / "agent" / "model-result.json"
    if mr_path.is_file():
        meta = json.loads(mr_path.read_text(encoding="utf-8"))
        if int(meta.get("steps") or 0) < MIN_STEPS or int(meta.get("output_tokens") or 0) < MIN_OUT_TOKENS:
            return "truncated"
    if not (t / "verifier" / "reward.txt").is_file():
        return "incomplete"
    return "valid"


def _stop_harbor_containers() -> None:
    """清掉可能仍持有旧 job 目录句柄的残留容器。"""
    try:
        out = subprocess.run(["docker", "--context", "desktop-windows", "ps", "-q",
                              "--filter", "name=harbor-"],
                             capture_output=True, text=True, timeout=120).stdout.split()
        for cid in out:
            if cid.strip():
                subprocess.run(["docker", "--context", "desktop-windows", "stop", cid.strip()],
                               capture_output=True, text=True, timeout=180)
    except Exception as exc:  # noqa: BLE001
        print(f"    [warn] 停止残留容器失败: {exc}", flush=True)


def archive(idx: int, tag: str) -> bool:
    """把一轮 job 连同日志移到归档目录；被占用时停容器重试，最后用 robocopy 兜底。"""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    d = JOBS / f"model-opus-{idx}"
    dest = ARCHIVE / f"{tag}-model-opus-{idx}"
    if d.is_dir():
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        for attempt in (1, 2, 3):
            if not d.exists():
                break
            try:
                shutil.move(str(d), str(dest))
                break
            except (PermissionError, OSError) as exc:
                print(f"    [warn] 归档 opus #{idx} 第 {attempt} 次失败: {exc}", flush=True)
                _stop_harbor_containers()
                time.sleep(3)
        if d.exists():
            subprocess.run(["robocopy", str(d), str(dest), "/E", "/MOVE",
                            "/NFL", "/NDL", "/NJH", "/NJS", "/NP"],
                           capture_output=True, text=True)
        if d.exists():
            subprocess.run(["cmd", "/c", "rd", "/s", "/q", str(d)], capture_output=True, text=True)
    log = MODEL_ROUNDS / f"model-opus-{idx}.log"
    if log.is_file():
        try:
            log.rename(ARCHIVE / f"{tag}-model-opus-{idx}.log")
        except OSError:
            pass
    return not d.exists()


env = dict(os.environ)
env["wciocp_OPUS_MODEL"] = "claude-opus-5"
env["no_proxy"] = "*"
env["NO_PROXY"] = "*"
env["PYTHONIOENCODING"] = "utf-8"

max_attempts = int(sys.argv[1]) if len(sys.argv) > 1 else 10
for attempt in range(1, max_attempts + 1):
    todo = []
    for idx in (1, 2, 3):
        v = verdict(idx)
        print(f"[attempt {attempt}] opus #{idx}: {v}", flush=True)
        if v in ("fallback", "truncated"):
            archive(idx, f"attempt{attempt}-{v}")
            todo.append(idx)
        elif v in ("missing", "incomplete"):
            if v == "incomplete":
                archive(idx, f"attempt{attempt}-incomplete")
            todo.append(idx)
    if not todo:
        print("[done] 三轮都是有效轮次", flush=True)
        break
    print(f"[attempt {attempt}] 补跑: {todo}", flush=True)
    cmd = [PY, str(RUNNER), "--only", "opus", "--index", ",".join(str(i) for i in todo),
           "--max-steps", "40"]
    subprocess.run(cmd, env=env, cwd=str(BUILD), check=False)
else:
    print(f"[warn] 达到最大尝试次数 {max_attempts}", flush=True)

print("\n=== 最终状态 ===", flush=True)
total = 0
for idx in (1, 2, 3):
    t = trial_dir(idx)
    reward = "-"
    if t and (t / "verifier" / "reward.txt").is_file():
        reward = (t / "verifier" / "reward.txt").read_text().strip()
        try:
            total += int(reward)
        except ValueError:
            pass
    print(f"  opus #{idx}: {verdict(idx)} reward={reward}", flush=True)
print(f"  Opus 合计 = {total}", flush=True)
