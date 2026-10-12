# -*- coding: utf-8 -*-
"""验证 agent_harness._run_command_captured 相对旧实现的修复效果。

场景：被执行的命令自身长跑，并且又拉起一个同样长跑的后代（后代继承 stdout）。
这正是 agent 写探针脚本时的典型形态。

- 旧实现 subprocess.run(capture_output=True, timeout=10)：
    超时分支里 CPython 调无超时的 communicate() 回收 → 管道 EOF 永不到达 → 挂死。
- 新实现 _run_command_captured(..., timeout=10)：
    重定向到临时文件，无管道 EOF 语义 → 可靠返回，并用 taskkill /T 收掉整棵树。

安全约束：本脚本**不做任何按映像名的批量杀进程**，
所有清理都按记录下来的 PID 精确执行，避免误伤并行的模型运行。
外层用 45s 硬超时给旧实现兜底，避免验证脚本自己挂死。
"""
import json
import os
import subprocess
import sys
import tempfile
import time

PY = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

WORK = os.path.join(tempfile.gettempdir(), "wff-cmdtest")
os.makedirs(WORK, exist_ok=True)

# 长跑的直接子进程，并拉起一个长跑的后代；把两个 PID 落盘以便精确清理
TREE_SRC = os.path.join(WORK, "tree.py")
with open(TREE_SRC, "w", encoding="utf-8") as fh:
    fh.write(
        "import json, os, subprocess, sys, time\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(600)'])\n"
        "json.dump({'child': os.getpid(), 'grand': g.pid}, open(sys.argv[1], 'w'))\n"
        "print('child-started', flush=True)\n"
        "time.sleep(600)\n"
    )

OLD_SNIPPET = (
    "import subprocess, sys\n"
    "cmd = sys.argv[1]\n"
    "try:\n"
    "    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,\n"
    "                       encoding='utf-8', errors='replace', timeout=10)\n"
    "    print('返回 rc=%s' % r.returncode)\n"
    "except subprocess.TimeoutExpired:\n"
    "    print('TimeoutExpired')\n"
    "except Exception as e:\n"
    "    print('异常 %s' % e)\n"
    "print('旧实现已返回')\n"
)

NEW_SNIPPET = (
    "import os, sys, time\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import agent_harness as ah\n"
    "sb = os.path.join(os.environ.get('TEMP', '/tmp'), 'wff-cmdtest')\n"
    "t0 = time.time()\n"
    "rc, body, timed_out = ah._run_command_captured(sys.argv[2], sb, 10)\n"
    "print('rc=%s timed_out=%s 耗时=%.1fs 输出=%r'\n"
    "      % (rc, timed_out, time.time() - t0, body.strip()[:80]))\n"
)


def alive(pid):
    import ctypes
    import ctypes.wintypes as w
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k.OpenProcess(0x1000, False, int(pid))
    if not h:
        return False
    code = ctypes.wintypes.DWORD()
    k.GetExitCodeProcess(h, ctypes.byref(code))
    k.CloseHandle(h)
    return code.value == 259  # STILL_ACTIVE


def cleanup(pidfile):
    if not os.path.exists(pidfile):
        return []
    try:
        ids = json.load(open(pidfile, encoding="utf-8"))
    except Exception:
        return []
    killed = []
    for key in ("grand", "child"):
        pid = ids.get(key)
        if pid and alive(pid):
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True)
            killed.append(pid)
    return killed


def main():
    print("=" * 70)
    print("【A】旧实现：subprocess.run(capture_output=True, timeout=10)")
    print("=" * 70)
    pf_old = os.path.join(WORK, "old.pid")
    if os.path.exists(pf_old):
        os.unlink(pf_old)
    cmd = '"%s" "%s" "%s"' % (PY, TREE_SRC, pf_old)
    t0 = time.time()
    hung = False
    try:
        p = subprocess.run([PY, "-c", OLD_SNIPPET, cmd], capture_output=True,
                           text=True, errors="replace", timeout=45)
        print((p.stdout or "").strip() or (p.stderr or "").strip())
        print("旧实现耗时 %.1fs" % (time.time() - t0))
    except subprocess.TimeoutExpired:
        hung = True
        print("!!! 45s 硬超时：旧实现**没有返回** → 确认挂死（这就是 qwen 卡死 16 分钟的成因）")
    killed = cleanup(pf_old)
    print("已按 PID 精确清理：%s" % (killed or "无"))
    time.sleep(1)

    print()
    print("=" * 70)
    print("【B】新实现：_run_command_captured(..., timeout=10)")
    print("=" * 70)
    pf_new = os.path.join(WORK, "new.pid")
    if os.path.exists(pf_new):
        os.unlink(pf_new)
    cmd = '"%s" "%s" "%s"' % (PY, TREE_SRC, pf_new)
    t0 = time.time()
    p = subprocess.run([PY, "-c", NEW_SNIPPET, HERE, cmd], capture_output=True,
                       text=True, errors="replace", timeout=90)
    print((p.stdout or "").strip() or (p.stderr or "").strip())
    print("新实现耗时 %.1fs" % (time.time() - t0))
    left = []
    if os.path.exists(pf_new):
        ids = json.load(open(pf_new, encoding="utf-8"))
        left = [k for k in ("child", "grand") if alive(ids.get(k))]
        cleanup(pf_new)
    print("新实现遗留后代：%s" % (left or "无（taskkill /T 已收干净）"))

    print()
    print("=" * 70)
    print("【C】新实现：普通命令（正常路径不得回归）")
    print("=" * 70)
    p = subprocess.run([PY, "-c", NEW_SNIPPET, HERE, "echo hello-from-cmd"],
                       capture_output=True, text=True, errors="replace", timeout=60)
    print((p.stdout or "").strip() or (p.stderr or "").strip())

    print()
    print("结论：旧实现挂死=%s；新实现可靠返回且无遗留后代=%s"
          % (hung, not left))


if __name__ == "__main__":
    main()
