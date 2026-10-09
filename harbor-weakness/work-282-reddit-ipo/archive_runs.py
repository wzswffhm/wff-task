#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G4/G5 跑分产物归档：按 149/151 验收口径落到批次级 跑分产物与轨迹/。
- 四执行体统一 output/
- 分数文件原名 reward.json / reward-details.json
- 轨迹放 轨迹/，先脱敏（凭据 sk-... 、U+3000/U+00A0）
- summary.json 记录 trial / 分数 / 门槛
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path("harbor-weakness")
BATCH = "work_fin-b01_20261009-152"
OUT = REPO / BATCH / "跑分产物与轨迹"
TRIALS = REPO / "_qc_runs"

SOURCES = {
    "oracle": TRIALS / "g4-152/trials/FIN3-WKN-152__Sa7ciyW",
    "qwen3.8-max-0902": TRIALS / "g5-152/trials/FIN3-WKN-152__vFbfvgm",
}

CRED = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")
NBSP = "\u00a0"
IDEO = "\u3000"


def scrub_text(t: str) -> str:
    t = CRED.sub("<REDACTED_CREDENTIAL>", t)
    t = t.replace(NBSP, " ").replace(IDEO, " ")
    return t


def dump_json_like(t: str) -> str:
    return scrub_text(t)


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    runs = []
    for model, src in SOURCES.items():
        if not src.is_dir():
            print(f"  [跳过] {model}: {src} 不存在")
            continue
        d = OUT / model
        (d / "轨迹").mkdir(parents=True)

        # 1) output/
        art = src / "artifacts/app/output"
        if art.is_dir():
            shutil.copytree(art, d / "output", dirs_exist_ok=True)
            print(f"  [OK] {model}: output/ {sum(1 for _ in (d/'output').rglob('*') if _.is_file())} 文件")

        # 2) 分数文件（原名）
        v = src / "verifier"
        for name in ("reward.json", "reward-details.json"):
            p = v / name
            if p.exists():
                (d / name).write_text(scrub_text(p.read_text(encoding="utf-8", errors="ignore")),
                                      encoding="utf-8", newline="\n")
        # graded 下的也要（若主目录没有）
        if not (d / "reward-details.json").exists():
            p = v / "graded/reward-details.json"
            if p.exists():
                (d / "reward-details.json").write_text(
                    scrub_text(p.read_text(encoding="utf-8", errors="ignore")),
                    encoding="utf-8", newline="\n")

        # 3) 轨迹
        a = src / "agent"
        for p in a.glob("*"):
            if p.is_file():
                dst = d / "轨迹" / p.name
                try:
                    dst.write_text(scrub_text(p.read_text(encoding="utf-8", errors="ignore")),
                                   encoding="utf-8", newline="\n")
                except Exception:
                    shutil.copy2(p, dst)
        tl = src / "trial.log"
        if tl.exists():
            (d / "轨迹" / "trial.log").write_text(
                scrub_text(tl.read_text(encoding="utf-8", errors="ignore")),
                encoding="utf-8", newline="\n")

        # 4) 分数
        rj = d / "reward.json"
        reward = None
        if rj.exists():
            try:
                reward = float(json.loads(rj.read_text(encoding="utf-8"))["reward"])
            except Exception:
                pass
        runs.append(dict(model=model, reward=reward,
                         trial=src.name,
                         trajectory_from=src.name,
                         scored=reward is not None,
                         verifier_error=(float(json.loads((d / "reward.json").read_text(encoding="utf-8")).get("verifier_error", -1))
                                         if rj.exists() else None)))
        print(f"  [OK] {model}: reward={reward} trial={src.name}")

    # 5) summary.json
    q = next((r["reward"] for r in runs if r["model"] == "qwen3.8-max-0902"), None)
    models3 = ["gpt-5.6-sol", "claude-opus-4-8", "qwen3.8-max-0902"]
    vals = [next((r["reward"] for r in runs if r["model"] == m), None) for m in models3]
    have = [v for v in vals if v is not None]
    mean = sum(have) / len(have) if len(have) == 3 else None
    summary = {
        "task_id": "FIN3-WKN-152",
        "task_version": "1.0.0",
        "run_task_version": "1.0.0",
        "round": "init",
        "version_note": "首版 1.0.0 跑分；判分前完成 prompt.md 平台原件替换、R20/R23 措辞量化、memo 去不可见空白三项修复，均在首次有效判分之前，无回溯重跑。",
        "runs": runs,
        "invalid_runs": [],
        "three_model_mean": mean,
        "three_model_gate": "<0.70",
        "three_model_complete": len(have) == 3,
        "declared_difficulty": "A1",
        "declared_complexity": "C3",
        "gate_pass": (mean is not None and mean < 0.7),
        "blocker": None if mean is not None else
                   "三模型未齐（gpt-5.6-sol / claude-opus-4-8 端点凭据缺失），难度档位未定",
        "risk_note": ("已跑执行体分数偏高，三模型均值存在破 0.70 风险，须补齐三模型后按实测定档"
                      if have and (sum(have) / len(have)) >= 0.6 else None),
    }
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print("\n" + "=" * 86)
    print(f"归档目录: {OUT}")
    for r in runs:
        print(f"  {r['model']:<22} reward={r['reward']}  trial={r['trial']}")
    print(f"  三模型齐备: {summary['three_model_complete']}   均值: {mean}   gate_pass: {summary['gate_pass']}")
    if summary["blocker"]:
        print(f"  ⚠ {summary['blocker']}")
    if summary["risk_note"]:
        print(f"  ⚠ {summary['risk_note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
