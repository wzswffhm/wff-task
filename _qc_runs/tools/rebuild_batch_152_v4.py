# -*- coding: utf-8 -*-
"""152 v4 跑分归档 + 批次目录重建（一次完成，符合质检第 7 条结构）。

批次目标结构：
    work_fin-b01_20261009-152/
    └── FIN3-WKN-152/                 ← 第二层唯一
        ├── 五件套（instruction/task.toml/rubrics.json/environment/solution/tests）
        ├── 交付文档.md               ← 由批次根移入
        └── 跑分产物与轨迹/           ← 由批次根移入 + 写入 v4 结果
            ├── oracle/{output/,轨迹/,reward.json,reward-details.json}
            ├── qwen3.8-max-0902/{…}
            ├── gpt-5.6-sol/{…}
            ├── claude-opus-4-8/{…}
            └── summary.json

只归档 **v4** trial（g4-152v4 / g5-152v4-*），绝不混入 v1/v2/v3。
用法: python rebuild_batch_152_v4.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

W = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = W / "harbor-weakness"
TASK = H / "FIN3-WKN-152"
BATCH = H / "work_fin-b01_20261009-152"
RUNS = H / "_qc_runs"
TASK_ID = "FIN3-WKN-152"

# v4 专用：输出目录 -> 归档目录名
V4 = [
    ("g4-152v4", "oracle"),
    ("g5-152v4-qwen", "qwen3.8-max-0902"),
    ("g5-152v4-gpt", "gpt-5.6-sol"),
    ("g5-152v4-opus", "claude-opus-4-8"),
]
GATE = 0.70

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

SKIP_DIRS = {"_rejudge", "__pycache__", ".pytest_cache", ".git"}
SKIP_EXT = {".pyc", ".out", ".err"}


def first(paths):
    for p in paths:
        if p and pathlib.Path(p).exists():
            return pathlib.Path(p)
    return None


def dsize(p: pathlib.Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def walk(root, exclude_top=()):
    for dirpath, dirnames, filenames in os_walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and d not in exclude_top)
        for f in sorted(filenames):
            if pathlib.Path(f).suffix in SKIP_EXT:
                continue
            p = pathlib.Path(dirpath) / f
            yield p.relative_to(root).as_posix(), p


def os_walk(root):
    import os
    return os.walk(root)


def archive_one(trial: pathlib.Path, dest: pathlib.Path) -> dict:
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "output").mkdir(parents=True, exist_ok=True)
    (dest / "轨迹").mkdir(parents=True, exist_ok=True)

    out_src = first([trial / "artifacts" / "app" / "output", trial / "artifacts" / "output"])
    n_out = 0
    if out_src and out_src.is_dir():
        for p in sorted(out_src.iterdir()):
            if p.is_file():
                shutil.copy2(p, dest / "output" / p.name)
                n_out += 1

    rj = first([trial / "verifier" / "reward.json"])
    if rj:
        shutil.copy2(rj, dest / "reward.json")
    rd = first([trial / "verifier" / "graded" / "reward-details.json",
                trial / "verifier" / "reward-details.json"])
    if rd:
        shutil.copy2(rd, dest / "reward-details.json")

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
        "trial": trial.name, "outputs": n_out, "reward": reward,
        "criteria_counted": (info.get("reward.json") or {}).get("criteria_counted"),
        "verifier_error": (info.get("reward.json") or {}).get("verifier_error"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tag", default="v4(qwen-weakness-rebuild)")
    a = ap.parse_args()

    print("=" * 96)
    print("1) 归档 v4 trial")
    print("=" * 96)
    dest_root = BATCH / TASK_ID / "跑分产物与轨迹"
    runs_out = []
    found_any = False
    for outdir, arch_name in V4:
        tdir = RUNS / outdir / "trials"
        trials = sorted(p for p in tdir.iterdir() if p.is_dir()) if tdir.is_dir() else []
        if not trials:
            print(f"  [缺] {outdir} （尚无 trial）")
            runs_out.append({"model": arch_name, "trial": None, "reward": None,
                             "criteria_counted": None, "verifier_error": None})
            continue
        if len(trials) > 1:
            print(f"  [!] {outdir} 有 {len(trials)} 个 trial，取第一个")
        tr = trials[0]
        found_any = True
        dest = dest_root / arch_name
        if a.dry_run:
            print(f"  [dry] {arch_name} <- {tr}")
            continue
        r = archive_one(tr, dest)
        print(f"  [OK] {arch_name:20s} <- {tr.name}  outputs={r['outputs']} "
              f"reward={r['reward']} counted={r['criteria_counted']} err={r['verifier_error']}")
        runs_out.append({"model": arch_name, **r})

    if a.dry_run:
        print("\n--dry-run 结束（未写入）")
        return 0

    if not dest_root.exists():
        print("  [!!] 无任何 v4 trial，终止")
        return 1

    # oracle 说明
    o = dest_root / "oracle"
    if o.is_dir():
        (o / "轨迹").mkdir(exist_ok=True)
        (o / "轨迹" / "说明.txt").write_text(ORACLE_NOTE, encoding="utf-8")

    # summary
    print()
    print("=" * 96)
    print("2) 生成 summary.json")
    print("=" * 96)
    models = [r for r in runs_out if r["model"] != "oracle"]
    scores = [r["reward"] for r in models
              if isinstance(r["reward"], (int, float)) and r.get("verifier_error") in (0, 0.0)]
    mean = round(sum(scores) / len(scores), 6) if scores else None
    oracle = next((r for r in runs_out if r["model"] == "oracle"), {})

    tt = TASK / "task.toml"
    txt = tt.read_text(encoding="utf-8")
    m = re.search(r'^difficulty\s*=\s*"([^"]+)"', txt, re.M)
    c = re.search(r'^task_complexity\s*=\s*"([^"]+)"', txt, re.M)
    mv = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)

    # 实测落档（甲方口径：由实测落，不看申报值）
    band = None
    if mean is not None:
        if mean < 0.5:
            band = "A3"
        elif mean < 0.6:
            band = "A2"
        elif mean < 0.7:
            band = "A1"
    complete = len(scores) >= 3
    gate_pass = bool(mean is not None and mean < GATE and complete
                     and isinstance(oracle.get("reward"), (int, float)) and oracle["reward"] >= 0.85)

    summary = {
        "task_id": TASK_ID,
        "task_version": mv.group(1) if mv else "?",
        "round": a.tag,
        "runs": runs_out,
        "invalid_runs": [r for r in runs_out
                         if r.get("verifier_error") not in (0, 0.0) and r.get("trial")],
        "oracle_reward": oracle.get("reward"),
        "three_model_mean": mean,
        "three_model_gate": "<0.70",
        "three_model_complete": complete,
        "measured_band": band,
        "declared_difficulty": m.group(1) if m else None,
        "declared_complexity": c.group(1) if c else None,
        "gate_pass": gate_pass,
        "blocker": None if complete else
                   f"三模型未齐（有效 {len(scores)} 个）",
    }
    (dest_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in
                      ("task_version", "oracle_reward", "three_model_mean",
                       "three_model_complete", "measured_band", "declared_difficulty",
                       "gate_pass", "blocker")}, ensure_ascii=False, indent=2))

    # 3) 批次结构：五件套 + 交付文档移入题目目录
    print()
    print("=" * 96)
    print("3) 批次目录结构（第二层仅题目目录）")
    print("=" * 96)
    tdest = BATCH / TASK_ID
    # 题包五件套从题包目录复制（保证与最新内容一致）
    for item in ["instruction.md", "task.toml", "rubrics.json",
                 "environment", "solution", "tests"]:
        src = TASK / item
        dst = tdest / item
        if not src.exists():
            print(f"  [!!] 源缺失 {src}")
            continue
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dst)
        print(f"  [OK] 复制 {item}")
    # 交付文档从批次根移入
    doc = BATCH / "交付文档.md"
    if doc.exists():
        shutil.copy2(doc, tdest / "交付文档.md")
        doc.unlink()
        print("  [OK] 交付文档.md 移入题目目录（批次根不再保留）")
    # 批次根若还残留旧的批次级 跑分产物与轨迹，移除其空壳（内容已在题目目录）
    old = BATCH / "跑分产物与轨迹"
    if old.exists():
        n = sum(1 for _ in old.rglob("*") if _.is_file())
        print(f"  [!!] 批次根仍有旧 跑分产物与轨迹（{n} 文件）——需人工确认后清理")
    tops = sorted(p.name for p in BATCH.iterdir())
    print(f"  批次根内容: {tops}")
    inner = sorted(p.name for p in tdest.iterdir()) if tdest.is_dir() else []
    print(f"  题目目录内容: {inner}")

    print()
    print(">>> 归档与结构重建完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
