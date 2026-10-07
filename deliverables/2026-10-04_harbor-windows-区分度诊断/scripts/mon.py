#!/usr/bin/env python
"""wtask-216 模型运行状态速查（读沙箱差分 + 轨迹统计）。"""
import glob
import json
import os
import subprocess
import sys

SB = os.path.join(os.environ.get("TEMP", "/tmp"), "wff-agent", "wfflab__wtask-216")


def sh(cmd, cwd):
    try:
        p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=60)
        return (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return "ERR %s" % e


def traj_stats(path):
    steps = 0
    names = {}
    stop = {}
    last = None
    reads = 0
    writes = 0
    first_write_turn = None
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            try:
                o = json.loads(ln)
            except Exception:
                continue
            if o.get("kind") == "assistant":
                steps += 1
                sr = o.get("stop_reason")
                stop[sr] = stop.get(sr, 0) + 1
                for t in (o.get("tool_uses") or []):
                    n = t.get("name")
                    names[n] = names.get(n, 0) + 1
                    if n == "write_file" and first_write_turn is None:
                        first_write_turn = steps
            last = o
    return steps, names, stop, last, first_write_turn


def main():
    print("sandbox root:", SB)
    if not os.path.isdir(SB):
        print("  (missing)")
        return
    for model in sorted(os.listdir(SB)):
        md = os.path.join(SB, model)
        if not os.path.isdir(md):
            continue
        print("\n########## %s ##########" % model)
        for r in (1, 2, 3):
            rd = os.path.join(md, "run-%d" % r)
            if not os.path.isdir(rd):
                continue
            print("--- run-%d ---" % r)
            print(sh("git diff --stat | tail -4", rd).rstrip())
            t = os.path.join(md, "trajectory-run-%d.jsonl" % r)
            if os.path.exists(t):
                steps, names, stop, last, fw = traj_stats(t)
                print("    turns=%d first_write_turn=%s tools=%s" % (steps, fw, names))
                print("    stops=%s" % stop)
                if last:
                    print("    last: step=%s kind=%s" % (last.get("step"), last.get("kind")))
            else:
                print("    (no trajectory yet)")


if __name__ == "__main__":
    main()
