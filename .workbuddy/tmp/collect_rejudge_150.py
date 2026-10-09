# -*- coding: utf-8 -*-
"""收集 FIN3-WKN-150 四场重判结果，回填跑分产物与 summary.json。

- 从 `harbor-weakness/FIN3-WKN-150/_rejudge/<ex>/verifier/` 取 reward.json / reward-details.json
- 归档到 `<batch>/FIN3-WKN-150/跑分产物与轨迹/<ex>/`（验收口径原名）
- 重算 summary.json：runs / mean / gate_pass；保留原 trial 与 trajectory_from，
  另记 `rejudge` 字段标明本次判分批次
用法：python collect_rejudge_150.py [--write]
"""
import json
import os
import pathlib
import shutil
import sys
import time

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"
TASK = "FIN3-WKN-150"
BATCH = "work-金融-私募股权投资-20261008"
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
WRITE = "--write" in sys.argv


def task_dir():
    return H / TASK


def artifacts_root():
    new = H / BATCH / TASK / "跑分产物与轨迹"
    return new if new.is_dir() else H / BATCH / "跑分产物与轨迹"


def read_json(p):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


stamp = time.strftime("%Y%m%dT%H%M%S")
results = {}
print("=" * 84)
for ex in EXECUTORS:
    ver = task_dir() / "_rejudge" / ex / "verifier"
    rj, rd = ver / "reward.json", ver / "reward-details.json"
    rem = ver / "reward_exit_message.json"
    d = read_json(rj)
    ok = bool(d) and (d.get("criteria_counted") or 0) >= 1 and not rem.is_file()
    results[ex] = {"done": ok, "reward": (d or {}).get("reward"),
                   "criteria_counted": (d or {}).get("criteria_counted"),
                   "verifier_error": (d or {}).get("verifier_error")}
    print(f"{ex:20} done={ok}  reward={results[ex]['reward']}  "
          f"counted={results[ex]['criteria_counted']}  err={results[ex]['verifier_error']}")
    if not ok:
        err = read_json(rem)
        if err:
            print(f"    fail: {err.get('exit_code')}: {str(err.get('exit_reason'))[:90]}")

if not all(r["done"] for r in results.values()):
    print("\n四场未全部完成，暂不回填（可重复运行本脚本）")

if WRITE and all(r["done"] for r in results.values()):
    root = artifacts_root()
    # ① 归档 reward 两件套
    for ex in EXECUTORS:
        dst = root / ex
        dst.mkdir(parents=True, exist_ok=True)
        ver = task_dir() / "_rejudge" / ex / "verifier"
        for name in ("reward.json", "reward-details.json", "reward.txt"):
            s = ver / name
            if s.is_file():
                shutil.copy2(s, dst / name)
        print(f"  归档 {ex}: reward.json / reward-details.json / reward.txt")
    # ② 重算 summary.json（保留原 trial / trajectory_from）
    sp = root / "summary.json"
    summary = read_json(sp) or {}
    old = {r.get("model"): r for r in summary.get("runs", [])}
    runs = []
    for ex in EXECUTORS:
        prev = old.get(ex, {})
        runs.append({
            "model": ex,
            "reward": results[ex]["reward"],
            "verifier_error": results[ex]["verifier_error"] or 0.0,
            "scored": True,
            "criteria_counted": results[ex]["criteria_counted"],
            "trial": prev.get("trial"),
            "trajectory_from": prev.get("trajectory_from"),
            "rejudge": f"docker-run-{stamp}",
        })
    models = [r for r in runs if r["model"] != "oracle"]
    mean = sum(float(r["reward"]) for r in models) / len(models)
    summary.update({
        "task_id": TASK,
        "round": f"fix3(qc2-remediation)-{stamp}",
        "runs": runs,
        "mean": round(mean, 6),
        "mean_gate": "<0.70",
        "any_model_scored": all(float(r["reward"]) > 0 for r in models),
        "gate_pass": mean < 0.70 and all(float(r["reward"]) > 0 for r in models),
    })
    with open(sp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"\n已回填 summary.json：mean={summary['mean']} gate_pass={summary['gate_pass']}")
    for r in runs:
        print(f"  {r['model']:20} reward={r['reward']}")
