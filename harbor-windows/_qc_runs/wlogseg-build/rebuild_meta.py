# -*- coding: utf-8 -*-
"""重建被 --dry-run 覆盖的 meta.json（qwen x3 + kimi x1），并清理过时的 score_note。

数据来源：
  agent_result.json -> status / steps / 时间戳 / sandbox / base_commit / tools
  report.json       -> status（交叉校验）
  patch.diff        -> patch_extracted
  models.local.json -> model_label / model_identity / role / base_url
"""
import hashlib
import io
import json
import os

ROOT = r"C:\Users\Administrator\Desktop\wff-task"
PKG = os.path.join(ROOT, "harbor-windows", "wfflab__wlogseg-218-v1.0.0-delivery")
RUNS = os.path.join(PKG, "extras", "model_runs")
TASK_ID = "wfflab__wlogseg-218-v1.0.0-delivery"

cfg = json.load(io.open(os.path.join(ROOT, "models.local.json"), encoding="utf-8"))
eps = cfg["endpoints"] if isinstance(cfg, dict) else cfg
by_dir = {}
for e in eps:
    if e.get("status") != "deprecated":
        by_dir.setdefault(e.get("dir"), e)

TARGETS = [
    ("qwen3.8-max-0902", 1), ("qwen3.8-max-0902", 2), ("qwen3.8-max-0902", 3),
    ("kimi-k3", 1),
]

for mdir, n in TARGETS:
    d = os.path.join(RUNS, mdir, "run-%d" % n)
    ar = json.load(io.open(os.path.join(d, "agent_result.json"), encoding="utf-8"))
    rp = json.load(io.open(os.path.join(d, "report.json"), encoding="utf-8"))
    ep = by_dir.get(mdir, {})

    pdf = os.path.join(d, "patch.diff")
    patch_extracted = os.path.isfile(pdf) and os.path.getsize(pdf) > 0

    meta = {
        "task_id": TASK_ID,
        "model_label": ep.get("label", mdir),
        "model_dir": mdir,
        "model_identity": ep.get("model", ""),
        "role": ep.get("role", ""),
        "run_index": n,
        "base_url": ep.get("base_url", ""),
        "started_at_utc": ar.get("started_at_utc"),
        "mode": ar.get("mode", "agent"),
        "completed_at_utc": ar.get("completed_at_utc"),
        "elapsed_sec": ar.get("elapsed"),
        "steps": ar.get("steps"),
        "sandbox": ar.get("sandbox"),
        "base_commit": ar.get("base_commit"),
        "agent_max_steps": ar.get("agent_max_steps", 40),
        "tools": ar.get("tools", []),
        "submitted": ar.get("submitted"),
        "last_stop_reason": ar.get("last_stop_reason"),
        "input_tokens": ar.get("input_tokens"),
        "output_tokens": ar.get("output_tokens"),
        "patch_bytes": ar.get("patch_bytes"),
        "status": ar.get("status"),
        "invalid_reason": ar.get("invalid_reason"),
        "http_status": ar.get("http_status"),
        "patch_extracted": patch_extracted,
        "meta_rebuilt": "2026-10-12: 原 meta.json 被 --dry-run 占位覆盖，按 agent_result.json 重建",
    }
    with io.open(os.path.join(d, "meta.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 清理过时的占位说明（真实判分已回填 score）
    if "score_note" in rp:
        rp.pop("score_note")
        with io.open(os.path.join(d, "report.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(rp, f, ensure_ascii=False, indent=2)

    agree = "OK" if rp.get("status") == meta["status"] else "MISMATCH"
    print("  %-20s run-%d  status=%-8s report=%-8s %s  steps=%s score=%s"
          % (mdir, n, meta["status"], rp.get("status"), agree, meta["steps"], rp.get("score")))

print("\nrebuilt %d meta.json" % len(TARGETS))
