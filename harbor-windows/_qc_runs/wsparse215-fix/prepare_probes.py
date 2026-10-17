# -*- coding: utf-8 -*-
"""准备两个反例，用来证明 215 的修复真的生效。

1. old-verifier/  : 来自 git 1568cfb3 的修复前隐藏套件（用作对照）
2. wrong-ws/      : 参考实现，但 allocated_ranges 把每个区间长度多报 1 字节
                    （正是甲方探针描述的错误：实测 8192、候选报 8193）
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

REPO = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG = "wfflab__wsparse-215-v1.0.0-delivery"
BASE = REPO / "harbor-windows" / "_qc_runs" / "wsparse215-fix"
ORACLE = BASE / "oracle-ws"


def main() -> int:
    old = BASE / "old-verifier" / "tests"
    old.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(
        ["git", "-C", str(REPO), "show",
         f"1568cfb3:harbor-windows/{PKG}/tests/test_wsparse_semantics.py"],
        capture_output=True, check=True)
    (old / "test_wsparse_semantics.py").write_bytes(out.stdout)
    print("旧套件 ->", (old / "test_wsparse_semantics.py"), len(out.stdout), "B")

    wrong = BASE / "wrong-ws"
    if wrong.exists():
        shutil.rmtree(wrong)
    shutil.copytree(ORACLE, wrong)
    ranges = wrong / "wsparse" / "ranges.py"
    text = ranges.read_text(encoding="utf-8")
    assert text.count("        return ranges") == 1, "unexpected ranges.py shape"
    text = text.replace(
        "        return ranges",
        "        # PROBE: report every extent one byte longer than reality.\n"
        "        return [(offset, length + 1) for offset, length in ranges]")
    ranges.write_text(text, encoding="utf-8")
    print("错误实现 ->", ranges)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
