# -*- coding: utf-8 -*-
"""从飞书 fix6 包构建第五轮 fix7 本地批次，保留原生候选交付物与轨迹。"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
SRC = (REPO / "deliverables" / "2026-10-11_序号239-FIN3-WKN-150第五轮返修"
       / "evidence" / "fix6_extract" / "work_fin-b01_20261006_fix6-150" / "FIN3-WKN-150")
TASK = REPO / "harbor-weakness" / "FIN3-WKN-150"
BATCH_NAME = "work_fin-b01_20261006_fix7-150"
DST = REPO / "harbor-weakness" / BATCH_NAME / "FIN3-WKN-150"
APPLY = "--apply" in sys.argv
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

REPLACE_FROM_TASK = [
    "instruction.md",
    "task.toml",
    "rubrics.json",
    "environment",
    "solution",
    "tests",
]


def copy_tree(src: pathlib.Path, dst: pathlib.Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def remove_if_exists(path: pathlib.Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def main() -> int:
    if not SRC.is_dir():
        raise SystemExit(f"missing source: {SRC}")
    if not TASK.is_dir():
        raise SystemExit(f"missing task: {TASK}")

    print(f"source fix6: {SRC}")
    print(f"target fix7: {DST}")
    print(f"replace from current task: {', '.join(REPLACE_FROM_TASK)}")
    for ex in EXECUTORS:
        output = SRC / "跑分产物与轨迹" / ex / "output"
        count = sum(1 for p in output.rglob("*") if p.is_file()) if output.is_dir() else -1
        print(f"  native output {ex:20} files={count}")

    if not APPLY:
        print("DRY RUN")
        return 0

    DST.parent.mkdir(parents=True, exist_ok=True)
    if DST.parent.exists():
        # Keep only this batch directory; replace its task directory atomically.
        pass
    copy_tree(SRC, DST)

    for rel in REPLACE_FROM_TASK:
        src = TASK / rel
        dst = DST / rel
        if not src.exists():
            raise SystemExit(f"missing current task source: {src}")
        remove_if_exists(dst)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    summary_path = DST / "跑分产物与轨迹" / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["task_version"] = "1.0.7"
    summary["round"] = "fix7(exit-assumption-remediation)+pending-rejudge"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
    print(f"staged: {DST}")
    print(f"summary version={summary['task_version']} round={summary['round']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
