#!/usr/bin/env python
"""等待 wtask-216 的 6 个 run 全部产出 meta.json（agent 阶段结束）。"""
import os
import sys
import time

TASK = r"C:/Users/Administrator/Desktop/wff-task/harbor-windows/wfflab__wtask-216/extras/model_runs"
MODELS = ["qwen3.8-max-0902", "opus-5"]
DEADLINE = float(sys.argv[1]) if len(sys.argv) > 1 else 1500.0

t0 = time.time()
while time.time() - t0 < DEADLINE:
    done = []
    for m in MODELS:
        for r in (1, 2, 3):
            p = os.path.join(TASK, m, "run-%d" % r, "meta.json")
            done.append(os.path.exists(p))
    if all(done):
        print("ALL_DONE after %.0fs" % (time.time() - t0))
        sys.exit(0)
    print("[%5.0fs] done=%d/6 %s" % (time.time() - t0, sum(done), done), flush=True)
    time.sleep(30)
print("TIMEOUT after %.0fs done=%d/6" % (time.time() - t0, sum(done)))
