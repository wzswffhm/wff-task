"""Reproduce the QC static scan locally WITHOUT the [:12] truncation, so the full
set of flagged strings (and their originating scripts) is known before editing.
"""
from __future__ import annotations

import sys
from pathlib import Path

QC = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\qc-original\windows-harbor-qc\scripts")
sys.path.insert(0, str(QC))
from run_qc import collect_referenced_paths  # noqa: E402

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
SKIP = {"powershell.exe", "cmd.exe", "go.exe", "dotnet.exe", "python.exe"}

for task_name in ("wfflab__wfmt-215", "wfflab__wreparse-217"):
    task = ROOT / task_name
    missing: list[str] = []
    for ref in collect_referenced_paths(task):
        clean = ref.replace("\\", "/").replace("${TaskRoot}", "").replace("$PSScriptRoot", "")
        if any(tok in clean for tok in ("$", "%", "<", ">")):
            continue
        if clean.casefold() in SKIP:
            continue
        if not (task / clean).exists() and not (task / "tests" / clean).exists() \
                and not (task / "environment" / clean).exists():
            missing.append(ref)
    uniq = sorted(set(missing))
    print("=" * 96)
    print(f"{task_name}: 完整误报 {len(uniq)} 项（QC 报告只显示前 12）")
    for ref in uniq:
        srcline = "<-- 是目录" if (task / ref.replace("\\", "/")).is_dir() else ""
        print(f"  {ref}{srcline}")
