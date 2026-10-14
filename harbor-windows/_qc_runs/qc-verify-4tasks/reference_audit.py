# -*- coding: utf-8 -*-
"""精确列出甲方 static_check 判定为「引用缺失」的每条路径，并回溯其来源文件与行号。

复刻 run_qc.static_check() 第 299–337 行的过滤逻辑，但保留逐条明细与出处。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
QC_SCRIPTS = ROOT / "harbor-windows" / "_reference" / "windows-harbor-qc" / "scripts"
sys.path.insert(0, str(QC_SCRIPTS))
import run_qc  # noqa: E402

PKGS = [
    "wfflab__wfmt-215-v2.1.0-delivery",
    "wfflab__wchunk-216-v1.2.0-delivery",
    "wfflab__wlogseg-218-v1.1.0-delivery",
    "wfflab__wpeimg-219-v1.4.0-delivery",
]

KNOWN_PREFIXES = ("tests/", "environment/", "solution/", "src/", "testbed/", "task/")
SKIP_PREFIXES = ("results/", "logs/", "work/", "temp/", "testbed/", "tools/",
                 "app/", "bin/", "ref/", "packs/")
SKIP_LOWER = {"powershell.exe", "cmd.exe", "go.exe", "dotnet.exe", "python.exe",
              "kernel32.dll", "shell32.dll", "harbor-probe.exe"}


def sources_of(pkg: Path, needle: str) -> list[str]:
    """在包内 .ps1/.bat/.cmd 中查找某条引用的出处。"""
    hits = []
    variants = {needle, needle.replace("/", "\\"), needle.replace("\\", "/")}
    bare = needle.split("/")[-1].split("\\")[-1]
    for f in pkg.rglob("*"):
        if not f.is_file() or "jobs" in f.relative_to(pkg).parts:
            continue
        if f.suffix.lower() not in {".ps1", ".psm1", ".bat", ".cmd"}:
            continue
        try:
            lines = f.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if any(v in ln for v in variants) or (bare and bare in ln and len(bare) > 8):
                rel = str(f.relative_to(pkg)).replace("\\", "/")
                hits.append("%s:%d  %s" % (rel, i, ln.strip()[:120]))
    return hits


for name in PKGS:
    pkg = ROOT / "harbor-windows" / name
    print("=" * 96)
    print(name)
    print("=" * 96)
    refs = run_qc.collect_referenced_paths(pkg)
    roots = [pkg, pkg / "tests", pkg / "environment", pkg / "solution",
             pkg / "environment" / "workspace"]
    missing = []
    for ref in refs:
        clean = ref.replace("\\", "/").replace("${TaskRoot}", "").replace("$PSScriptRoot", "")
        clean = re.sub(r"^\./+", "", clean)
        if clean.casefold().startswith("task/"):
            clean = clean[5:]
        if any(t in clean for t in ("$", "%", "<", ">")):
            continue
        lower = clean.casefold()
        if lower in SKIP_LOWER:
            continue
        if lower.startswith(SKIP_PREFIXES):
            continue
        if lower.startswith(("dp0solve.", "dp0test.")) or lower.endswith(".runtimeconfig.json"):
            continue
        if Path(clean).name.startswith(".") and "." not in Path(clean).name[1:]:
            continue
        if "/" in clean and not lower.startswith(KNOWN_PREFIXES) and len(clean.split("/")) > 2:
            continue
        cands = [r / clean for r in roots]
        if "/" not in clean:
            cands.extend(p for r in roots for p in r.rglob(Path(clean).name))
        explicit = "/" in clean and lower.startswith(KNOWN_PREFIXES)
        if not any(p.exists() for p in cands) and (
                explicit or ("/" not in clean and lower.endswith((".ps1", ".psm1", ".bat", ".cmd", ".go")))):
            missing.append(ref)

    missing = sorted(set(missing))
    print("  引用缺失条目: %d" % len(missing))
    for ref in missing:
        print("\n  ▶ %s" % ref)
        for s in sources_of(pkg, ref)[:4]:
            print("      %s" % s)
    print()
