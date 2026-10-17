# -*- coding: utf-8 -*-
"""准备“基础设施故障”探针：修复前的 run_tests/aggregate + 一个什么都收集不到的套件。

复现甲方第 2 条探针：依赖缺失导致一个测试都没收集到时，修复前的链路仍输出
VALID / 正式分数 0；修复后必须是 INVALID / 正式分数为空。
"""
from __future__ import annotations

import pathlib
import subprocess

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = "wfflab__wsparse-215-v1.0.0-delivery"
BASE = REPO / "harbor-windows" / "_qc_runs" / "wsparse215-fix"
REV = "1568cfb3"


def show(rel: str, dest: pathlib.Path) -> None:
    out = subprocess.run(["git", "-C", str(REPO), "show", f"{REV}:{rel}"],
                         capture_output=True, check=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out.stdout)
    print(f"{rel} -> {dest} ({len(out.stdout)} B)")


def main() -> int:
    old = BASE / "old-harness"
    show(f"harbor-windows/{PKG}/tests/run_tests.ps1", old / "run_tests.ps1")
    show(f"harbor-windows/{PKG}/tests/aggregate_results.ps1", old / "aggregate_results.ps1")

    empty = BASE / "empty-verifier" / "tests" / "test_wsparse_semantics.py"
    empty.parent.mkdir(parents=True, exist_ok=True)
    empty.write_text("# Intentionally collects nothing: simulates a missing dependency.\n",
                     encoding="utf-8")
    print("empty suite ->", empty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
