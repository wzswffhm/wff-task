"""win_probe_proc.py —— 进程生命周期相关的 Windows 语义实测。

出题前先验证假设，避免写出「no-change 也能通过」或「基线本就成立」的假 F2P。
每个用例独立建临时目录，结论打印 HIT / MISS。

用法：
    <python> win_probe_proc.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PY = sys.executable

GRANDCHILD = """
import sys, time
hb = sys.argv[1]
while True:
    with open(hb, "w", encoding="utf-8") as fh:
        fh.write(str(time.time()))
    time.sleep(0.15)
"""

PARENT = """
import subprocess, sys, time
hb, gc, mode = sys.argv[1], sys.argv[2], sys.argv[3]
print("parent-started", flush=True)
if mode == "spawn":
    subprocess.Popen([sys.executable, gc, hb])
elif mode == "spawn_and_exit":
    subprocess.Popen([sys.executable, gc, hb])
    sys.exit(0)
time.sleep(3600)
"""

ROOT = Path(tempfile.mkdtemp(prefix="wprobe-root-"))


def _scratch(name: str) -> Path:
    """建一个不会被 TemporaryDirectory 强删的临时目录（孙进程可能仍占用它）。"""
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _mk(tmp: Path) -> tuple[Path, Path]:
    gc = tmp / "grandchild.py"
    gc.write_text(GRANDCHILD, encoding="utf-8")
    par = tmp / "parent.py"
    par.write_text(PARENT, encoding="utf-8")
    return par, gc


def _hb_alive(hb: Path, wait: float = 1.0) -> bool:
    """删掉心跳文件后等一会儿，看它是否被重新写出来。"""
    if hb.exists():
        hb.unlink()
    time.sleep(wait)
    return hb.exists()


def _taskkill_tree(pid: int) -> int:
    r = subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, timeout=30)
    return r.returncode


def _spawn(tmp: Path, mode: str):
    par, gc = _mk(tmp)
    hb = tmp / "hb.txt"
    p = subprocess.Popen([PY, str(par), str(hb), str(gc), mode],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p, hb


def p1_communicate_times_out_when_grandchild_holds_pipe() -> bool:
    """孙进程持有 stdout 写句柄时，communicate(timeout) 到点仍未 EOF → TimeoutExpired。"""
    tmp = _scratch("p1")
    p, hb = _spawn(tmp, "spawn")
    try:
        time.sleep(1.0)
        if not _hb_alive(hb, 0.6):
            print("    孙进程未启动，用例无效")
            return False
        raised = False
        t0 = time.time()
        try:
            p.communicate(timeout=2.0)
        except subprocess.TimeoutExpired:
            raised = True
        dt = time.time() - t0
        print(f"    P1 elapsed={dt:.2f}s raised={raised} rc={p.returncode}")
        return raised
    finally:
        _taskkill_tree(p.pid)


def p2_popen_kill_leaves_grandchild_alive() -> bool:
    """proc.kill() 只杀直接子进程，孙进程继续心跳。"""
    tmp = _scratch("p2")
    p, hb = _spawn(tmp, "spawn")
    try:
        time.sleep(1.5)
        if not _hb_alive(hb, 0.6):
            print("    孙进程未启动，用例无效")
            return False
        p.kill()
        p.wait(timeout=10)
        time.sleep(0.5)
        alive = _hb_alive(hb, 1.5)
        print(f"    P2 killed_pid={p.pid} grandchild_alive={alive}")
        return alive
    finally:
        _taskkill_tree(p.pid)


def p3_taskkill_tree_kills_grandchild() -> bool:
    """taskkill /F /T /PID <直接子进程> 能把孙进程一起干掉。"""
    tmp = _scratch("p3")
    p, hb = _spawn(tmp, "spawn")
    time.sleep(1.5)
    if not _hb_alive(hb, 0.6):
        _taskkill_tree(p.pid)
        print("    孙进程未启动，用例无效")
        return False
    rc = _taskkill_tree(p.pid)
    p.wait(timeout=10)
    time.sleep(0.5)
    alive = _hb_alive(hb, 1.5)
    print(f"    P3 taskkill_rc={rc} grandchild_alive={alive}")
    return not alive


def _drain_with(p, use_read1: bool):
    buf = bytearray()

    def drain():
        try:
            if use_read1:
                while True:
                    chunk = p.stdout.read1(65536)
                    if not chunk:
                        break
                    buf.extend(chunk)
            else:
                while True:
                    chunk = p.stdout.read(4096)
                    if not chunk:
                        break
                    buf.extend(chunk)
        except Exception:
            pass

    th = threading.Thread(target=drain, daemon=True)
    th.start()
    return buf, th


def p4_reader_thread_returns_when_child_exits() -> bool:
    """读者线程 + proc.wait()：直接子进程已退出时不必等管道 EOF，可立即返回并拿到输出。"""
    ok = True
    for use_read1 in (False, True):
        tmp = _scratch(f"p4-{'read1' if use_read1 else 'read'}")
        p, hb = _spawn(tmp, "spawn_and_exit")
        buf, _th = _drain_with(p, use_read1)
        t0 = time.time()
        p.wait(timeout=20)
        rc = p.returncode
        time.sleep(0.2)
        dt = time.time() - t0
        alive = _hb_alive(hb, 1.0)
        text = bytes(buf).decode("utf-8", "replace")
        got = "parent-started" in text
        print(f"    P4 read1={use_read1} elapsed={dt:.2f}s rc={rc} "
              f"grandchild_alive={alive} got_output={got} output={text!r}")
        ok = ok and got
        _taskkill_tree(p.pid)
    return ok


def p5_taskkill_after_child_exit_is_noop() -> bool:
    """直接子进程已退出后再执行 taskkill /T 无法回收孙进程。"""
    tmp = _scratch("p5")
    p, hb = _spawn(tmp, "spawn_and_exit")
    p.wait(timeout=20)
    time.sleep(0.5)
    rc = _taskkill_tree(p.pid)
    alive = _hb_alive(hb, 1.0)
    print(f"    P5 taskkill_rc={rc} grandchild_alive={alive}")
    _taskkill_tree(p.pid)
    return alive


def p6_taskkill_makes_drain_thread_reach_eof() -> bool:
    """整棵树被 taskkill 之后，读者线程应立刻拿到 EOF（否则读线程会一直挂着）。"""
    tmp = _scratch("p6")
    p, hb = _spawn(tmp, "spawn")
    buf, th = _drain_with(p, True)
    time.sleep(1.5)
    _taskkill_tree(p.pid)
    p.wait(timeout=10)
    th.join(timeout=5.0)
    eof = not th.is_alive()
    print(f"    P6 drain_thread_finished={eof} output={bytes(buf)!r}")
    return eof


CASES = [
    ("P1 communicate 在孙进程持有管道时超时", p1_communicate_times_out_when_grandchild_holds_pipe),
    ("P2 Popen.kill 留下孙进程", p2_popen_kill_leaves_grandchild_alive),
    ("P3 taskkill /T 能杀掉孙进程", p3_taskkill_tree_kills_grandchild),
    ("P4 读者线程（read1）可立即返回并拿到输出", p4_reader_thread_returns_when_child_exits),
    ("P5 子进程已退出后 taskkill /T 对孙进程无效", p5_taskkill_after_child_exit_is_noop),
    ("P6 taskkill 后读者线程能拿到 EOF", p6_taskkill_makes_drain_thread_reach_eof),
]


def main() -> int:
    print(f"python = {PY}")
    print(f"os.name = {os.name}")
    print(f"scratch = {ROOT}")
    hits = 0
    for name, fn in CASES:
        print(f"== {name}")
        try:
            ok = bool(fn())
        except Exception as exc:  # noqa: BLE001
            print(f"    EXC {type(exc).__name__}: {exc}")
            ok = False
        print(f"    -> {'HIT ' if ok else 'MISS'}")
        hits += 1 if ok else 0
    # 兜底清理：（尽力而为）
    time.sleep(0.5)
    shutil.rmtree(ROOT, ignore_errors=True)
    print(f"\n命中 {hits}/{len(CASES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
