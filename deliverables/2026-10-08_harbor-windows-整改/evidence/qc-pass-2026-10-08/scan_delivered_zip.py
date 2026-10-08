"""Scan the DELIVERED zip (not the repo working tree) with the client's own
collect_referenced_paths, so the fix list matches what QC actually sees.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

QC = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs\qc-original\windows-harbor-qc\scripts")
sys.path.insert(0, str(QC))
from run_qc import collect_referenced_paths  # noqa: E402

PKG = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-08_harbor-windows-整改\package")
ZIPS = {
    "215": PKG / "wfflab__wfmt-215-v2.0.0-delivery.zip",
    "217": PKG / "wfflab__wreparse-217-v1.0.0-delivery.zip",
}
SKIP = {"powershell.exe", "cmd.exe", "go.exe", "dotnet.exe", "python.exe"}

for tag, zp in ZIPS.items():
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zp) as zf:
            zf.extractall(tmp)
        # the task root inside the delivery layout
        roots = [p.parent for p in Path(tmp).rglob("task.toml")]
        if not roots:
            print(f"{tag}: 包内未找到 task.toml")
            continue
        task = roots[0]
        missing: list[str] = []
        for ref in collect_referenced_paths(task):
            clean = ref.replace("\\", "/").replace("${TaskRoot}", "").replace("$PSScriptRoot", "")
            if any(t in clean for t in ("$", "%", "<", ">")):
                continue
            if clean.casefold() in SKIP:
                continue
            if not (task / clean).exists() and not (task / "tests" / clean).exists() \
                    and not (task / "environment" / clean).exists():
                missing.append(ref)
        uniq = sorted(set(missing))
        print("=" * 96)
        print(f"{tag}  (包内 task root = {task.relative_to(tmp).as_posix()})  实际误报 {len(uniq)} 项")
        scripts = [p for p in task.rglob("*") if p.is_file()
                   and p.suffix.lower() in {".ps1", ".psm1", ".bat", ".cmd"}]
        print(f"  包内脚本 {len(scripts)} 个")
        for ref in uniq:
            key = ref.replace("\\", "/").split("/")[-1]
            hits = []
            for sp in scripts:
                for i, line in enumerate(sp.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if key in line:
                        hits.append(f"{sp.relative_to(task).as_posix()}:{i}")
            print(f"  - {ref:<32} {hits[:3] if hits else '(注释/其它)'}")
