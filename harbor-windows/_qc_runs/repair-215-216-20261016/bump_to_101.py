# -*- coding: utf-8 -*-
"""把 215/216 升版到 1.0.1：更新题包内的版本引用与构建/重跑脚本中的包路径。

只改“版本语义”的文件；environment/workspace/** 与 solution/** 是被测代码，
它们的 __version__ 不参与题包版本，保持原样。
"""
from __future__ import annotations

import pathlib

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")

PKG_FILES = {
    "wfflab__wsparse-215-v1.0.1-delivery": [
        "source.json", "task.toml", "environment/adapter.toml",
        "environment/agent_visible_paths.json", "tests/judge.toml",
        "tests/rubric.json", "tests/run_tests.ps1",
        "verifier/rubric.conditions.json",
        "evidence/author-design/contract-map.json",
    ],
    "wfflab__wvas-216-v1.0.1-delivery": [
        "REFIT-2026-10-14.md", "source.json", "task.toml",
        "environment/adapter.toml", "environment/agent_visible_paths.json",
        "tests/judge.toml", "tests/rubric.json", "tests/run_tests.ps1",
        "verifier/rubric.conditions.json", "verifier/WINDOWS_VALUE.md",
        "evidence/author-design/contract-map.json",
    ],
}

SCRIPT_FILES = [
    HW / "_qc_runs" / "wsparse-build" / "run_wsparse_controls.py",
    HW / "_qc_runs" / "wsparse-build" / "run_wsparse_model_rounds.py",
    HW / "_qc_runs" / "wsparse-build" / "assemble_wsparse_harbor_jobs.py",
    HW / "_qc_runs" / "wvas-build" / "run_wvas_controls.py",
    HW / "_qc_runs" / "wvas-build" / "run_wvas_model_rounds.py",
    HW / "_qc_runs" / "wvas-build" / "assemble_wvas_harbor_jobs.py",
    HW / "_qc_runs" / "repair-215-216-20261016" / "rerun_215_216_repair.py",
    HW / "_qc_runs" / "repair-215-216-20261016" / "resample_qwen_until_gap.py",
    HW / "_qc_runs" / "repair-215-216-20261016" / "check_gate.py",
]


def main() -> int:
    changed = 0
    for pkg, rels in PKG_FILES.items():
        for rel in rels:
            path = HW / pkg / rel
            if not path.is_file():
                print("missing:", path)
                continue
            text = path.read_text(encoding="utf-8")
            new = text.replace("v1.0.0", "v1.0.1").replace("1.0.0", "1.0.1")
            if new != text:
                path.write_text(new, encoding="utf-8")
                changed += 1
                print(f"updated package file: {pkg}/{rel}")
    for path in SCRIPT_FILES:
        if not path.is_file():
            print("missing script:", path)
            continue
        text = path.read_text(encoding="utf-8")
        new = text.replace("wfflab__wsparse-215-v1.0.0-delivery", "wfflab__wsparse-215-v1.0.1-delivery")
        new = new.replace("wfflab__wvas-216-v1.0.0-delivery", "wfflab__wvas-216-v1.0.1-delivery")
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
            print("updated script:", path.name)
    print("files changed:", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
