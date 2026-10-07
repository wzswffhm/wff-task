#!/usr/bin/env python3
"""Unified diff base workspace vs oracle reference for the WReparse module."""
from __future__ import annotations

import difflib
from pathlib import Path

BASE = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217\environment\workspace\WReparse")
REF = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217\solution\reference\WReparse")

for name in ["WReparse.psd1", "WReparse.psm1", "Model.ps1", "PathSemantics.ps1", "Walker.ps1", "Audit.ps1"]:
    a = (BASE / name).read_text(encoding="utf-8", errors="replace").splitlines()
    b = (REF / name).read_text(encoding="utf-8", errors="replace").splitlines()
    d = list(difflib.unified_diff(a, b, fromfile=f"base/{name}", tofile=f"ref/{name}", lineterm="", n=3))
    print("=" * 100)
    print(f"### {name}   (base {len(a)} lines, ref {len(b)} lines, diff {len(d)} lines)")
    print("=" * 100)
    if not d:
        print("  (identical)")
    else:
        for line in d:
            print(line)
    print()
