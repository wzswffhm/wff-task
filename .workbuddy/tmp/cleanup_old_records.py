# -*- coding: utf-8 -*-
"""清理 FIN3-WKN-150 的旧残留记录。

处理对象：
1. `_rejudge/_history/`（2026-10-09 归档的上一轮失败/作废产物）——先把关键数字与作废原因
   如实记入 `跑分产物与轨迹/summary.json` 的 `invalid_runs`，再删除目录，
   保证「清理残留」不丢可追溯性。
2. 题包内 `tests/__pycache__` 等构建残留。

**不动**：`_rejudge/<ex>/`（判分进行中会持续写入，须等判分收口后再清）。

用法：python cleanup_old_records.py [--dry-run]
"""
import json
import os
import pathlib
import shutil
import sys

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = REPO / "harbor-weakness"
TASK = "FIN3-WKN-150"
BATCH = "work-金融-私募股权投资-20261008"
DRY = "--dry-run" in sys.argv

task_dir = H / TASK
history = task_dir / "_rejudge" / "_history"


def artifacts_root():
    new = H / BATCH / TASK / "跑分产物与轨迹"
    return new if new.is_dir() else H / BATCH / "跑分产物与轨迹"


def read_json(p):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


# ---- 1) 先把 _history 里的关键数字记入 summary.json --------------------------
records = []
if history.is_dir():
    for d in sorted(history.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        ex = name.rsplit("-", 1)[0] if name[-5:].isdigit() or "-" in name else name
        rj = read_json(d / "verifier" / "reward.json")
        rem = read_json(d / "verifier" / "reward_exit_message.json")
        records.append({
            "round": "qc2/pre-remediation(2026-10-09 archived)",
            "executor": ex,
            "reward": (rj or {}).get("reward"),
            "criteria_counted": (rj or {}).get("criteria_counted"),
            "verifier_error": (rj or {}).get("verifier_error"),
            "reason": (f"{rem.get('exit_code')}: {rem.get('exit_reason')}" if rem
                       else "金标/判据已修改，该轮判分作废，按质检要求重跑"),
        })
    print(f"_history 中记录 {len(records)} 条：")
    for r in records:
        print(f"  {r['executor']:22} reward={r['reward']} counted={r['criteria_counted']} "
              f"err={r['verifier_error']}")

    if not DRY and records:
        sp = artifacts_root() / "summary.json"
        summary = read_json(sp) or {}
        inv = summary.setdefault("invalid_runs", [])
        existing = {(str(x.get("round")), str(x.get("executor"))) for x in inv}
        added = 0
        for r in records:
            key = (r["round"], r["executor"])
            if key in existing:
                continue
            inv.append(r)
            added += 1
        with open(sp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"已追加 {added} 条到 summary.json 的 invalid_runs")

    # ---- 2) 删除 _history -------------------------------------------------
    if DRY:
        print(f"[dry-run] 将删除 {history}")
    else:
        shutil.rmtree(history)
        print(f"已删除 {history}")

# ---- 3) 题包内构建残留 ------------------------------------------------------
removed = []
for pattern in ("__pycache__",):
    for dirpath, dirnames, _files in os.walk(task_dir):
        for name in list(dirnames):
            if name == pattern and "_rejudge" not in dirpath:
                p = pathlib.Path(dirpath) / name
                removed.append(str(p.relative_to(REPO)))
                if not DRY:
                    shutil.rmtree(p, ignore_errors=True)
print(f"构建残留清理: {removed if removed else '无'}")
print("注意：_rejudge/<ex>/ 为判分进行中产物，待判分收口后再清。")
