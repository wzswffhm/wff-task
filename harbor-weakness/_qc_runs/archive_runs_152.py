#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把各执行体的 trial 目录归档到批次级 跑分产物与轨迹/，并生成 summary.json。

用法:
  python archive_runs_152.py --batch <批次目录> --runs <_qc_runs 目录>
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

TASK_ID = "FIN3-WKN-152"
GATE = "<0.70"

ORACLE_NOTE = """# oracle 执行体轨迹说明

## 为什么本目录没有 `claude-code.txt` / `trajectory.json`

`oracle` 是 harbor 内置的参考解执行体：它直接运行题包内的 `solution/solve.sh`，
把 `solution/golden_output/` 复制到 `/app/output/`，**不经过 claude-code agent 框架**，
因此不产生 claude-code 轨迹。这是 harbor 的设计使然，不是跑分缺失。

## 本目录取证材料

| 文件 | 说明 |
|---|---|
| `output/` | oracle 产出的 7 份交付物快照（与 `solution/golden_output/` 同源） |
| `reward.json` | 判分主分与 `criteria_counted` / `verifier_error` |
| `reward-details.json` | 逐条判据判定明细（审计件） |

## 有效性

轨迹框架核对要求（`claude-code` + `version 2.1.114` + `steps`）**仅适用于三模型执行体**；
oracle 按 harbor 内置 agent 口径豁免，与 FIN3-WKN-149/150/151 已验收题包的处理一致。
"""


def first(paths):
    for p in paths:
        if p and Path(p).exists():
            return Path(p)
    return None


def archive_one(trial: Path, dest: Path) -> dict:
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "output").mkdir(parents=True, exist_ok=True)
    (dest / "轨迹").mkdir(parents=True, exist_ok=True)

    # 产物：优先 artifacts/app/output
    out_src = first([trial / "artifacts" / "app" / "output",
                     trial / "artifacts" / "output"])
    n_out = 0
    if out_src and out_src.is_dir():
        for p in sorted(out_src.iterdir()):
            if p.is_file():
                shutil.copy2(p, dest / "output" / p.name)
                n_out += 1

    # 判分
    rj = first([trial / "verifier" / "reward.json"])
    if rj:
        shutil.copy2(rj, dest / "reward.json")
    rd = first([trial / "verifier" / "graded" / "reward-details.json",
                trial / "verifier" / "reward-details.json"])
    if rd:
        shutil.copy2(rd, dest / "reward-details.json")

    # 轨迹
    cc = first([trial / "agent" / "claude-code.txt"])
    if cc:
        shutil.copy2(cc, dest / "轨迹" / "claude-code.txt")
    tj = first([trial / "agent" / "trajectory.json"])
    if tj:
        shutil.copy2(tj, dest / "轨迹" / "trajectory.json")
    tl = first([trial / "trial.log", trial / "logs" / "trial.log"])
    if tl:
        shutil.copy2(tl, dest / "轨迹" / "trial.log")

    info = {}
    for name in ("reward.json", "reward-details.json"):
        f = dest / name
        if f.exists():
            try:
                info[name] = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                info[name] = None
    reward = None
    if isinstance(info.get("reward.json"), dict):
        d = info["reward.json"]
        reward = d.get("reward", d.get("graded_score"))
    return {
        "trial": trial.name,
        "outputs": n_out,
        "reward": reward,
        "criteria_counted": (info.get("reward.json") or {}).get("criteria_counted"),
        "verifier_error": (info.get("reward.json") or {}).get("verifier_error"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--tag", default="v2")
    a = ap.parse_args()

    batch = Path(a.batch)
    runs = Path(a.runs)
    dest_root = batch / "跑分产物与轨迹"
    dest_root.mkdir(parents=True, exist_ok=True)

    # 发现 trial：扫 _qc_runs/*/trials/*/
    found = []
    for tr in sorted(runs.glob("*/trials/*")):
        if not tr.is_dir():
            continue
        cfg_p = tr / "config.json"
        name = None
        model = None
        if cfg_p.exists():
            try:
                cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
                name = (cfg.get("agent") or {}).get("name")
                model = (cfg.get("agent") or {}).get("model_name")
            except Exception:
                pass
        ex = "oracle" if name == "oracle" else (model or tr.name)
        found.append((ex, tr))

    print(f"discovered {len(found)} trial(s):")
    runs_out = []
    for ex, tr in found:
        dest = dest_root / ex
        r = archive_one(tr, dest)
        print(f"  {ex:20s} <- {tr}  outputs={r['outputs']} reward={r['reward']}")
        runs_out.append({"model": ex, **r})

    # oracle 说明
    o = dest_root / "oracle"
    if o.is_dir():
        (o / "轨迹").mkdir(exist_ok=True)
        (o / "轨迹" / "说明.txt").write_text(ORACLE_NOTE, encoding="utf-8")

    # summary
    models = [r for r in runs_out if r["model"] != "oracle"]
    scores = [r["reward"] for r in models
              if isinstance(r["reward"], (int, float)) and r.get("verifier_error") in (0, 0.0)]
    mean = round(sum(scores) / len(scores), 6) if scores else None
    declared_task = None
    task_toml = Path(a.batch).parent / TASK_ID / "task.toml"
    if task_toml.exists():
        import re
        txt = task_toml.read_text(encoding="utf-8")
        m = re.search(r'^difficulty\s*=\s*"([^"]+)"', txt, re.M)
        c = re.search(r'^task_complexity\s*=\s*"([^"]+)"', txt, re.M)
        declared_task = (m.group(1) if m else None, c.group(1) if c else None)
    ver = "2.0.0"
    v = Path(a.batch).parent / TASK_ID / "task.toml"
    if v.exists():
        import re
        mv = re.search(r'^version\s*=\s*"([^"]+)"', v.read_text(encoding="utf-8"), re.M)
        ver = mv.group(1) if mv else ver

    summary = {
        "task_id": TASK_ID,
        "task_version": ver,
        "round": a.tag,
        "runs": runs_out,
        "invalid_runs": [],
        "three_model_mean": mean,
        "three_model_gate": GATE,
        "three_model_complete": len(scores) >= 3,
        "declared_difficulty": declared_task[0] if declared_task else None,
        "declared_complexity": declared_task[1] if declared_task else None,
        "gate_pass": bool(mean is not None and mean < 0.70 and len(scores) >= 3),
        "blocker": None if len(scores) >= 3 else
                   f"三模型未齐（已完成 {len(scores)} 个有效模型：{', '.join(r['model'] for r in models)}）；"
                   f"claude-opus-4-8 端点不可得",
    }
    (dest_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nsummary.json ->", dest_root / "summary.json")
    print(json.dumps({k: summary[k] for k in
                      ("three_model_mean", "three_model_complete", "gate_pass", "blocker")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
