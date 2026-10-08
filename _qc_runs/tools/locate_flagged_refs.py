"""Locate every string the QC static scan flags, so each can be rewritten deliberately."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\wff-task\_qc_runs")
PKG = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")

for tag, task in (("215", "wfflab__wfmt-215"), ("217", "wfflab__wreparse-217")):
    rp = BASE / f"qcorig-{tag}" / "report.json"
    d = json.loads(rp.read_text(encoding="utf-8-sig"))
    refs: list[str] = []
    for t in d["tasks"]:
        for e in t.get("errors") or []:
            if e.startswith("referenced files are missing:"):
                refs += [x.strip() for x in e.split(":", 1)[1].split(",")]

    root = PKG / task
    scripts = [p for p in root.rglob("*") if p.is_file()
               and p.suffix.lower() in {".ps1", ".psm1", ".bat", ".cmd"}
               and "jobs" not in p.relative_to(root).parts]
    print("=" * 100)
    print(f"{tag}  {task}   （报缺 {len(refs)} 项；扫描 {len(scripts)} 个脚本）")
    for ref in refs:
        base = ref.replace("\\", "/").split("/")[-1]
        needle = base
        if ref.startswith("dp0"):
            needle = base[3:]          # %~dp0solve.ps1 -> solve.ps1
        print(f"\n--- {ref}")
        found = False
        for sp in scripts:
            for i, line in enumerate(sp.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if needle in line:
                    rel = sp.relative_to(root).as_posix()
                    print(f"    {rel}:{i}  {line.strip()[:150]}")
                    found = True
        if not found:
            print("    (脚本中未定位到，可能来自其它扩展名文件)")
