# -*- coding: utf-8 -*-
"""运行甲方自检包 run_qc.py 的 static_check()，逐项列出四个包的通过/失败。

判据来源：harbor-windows/_reference/windows-harbor-qc/scripts/run_qc.py::static_check
（该参考包手册与《Windows-48题质检-专家修复详解版-20261012》逐字节一致）
"""
from __future__ import annotations

import json
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

out = {}
for name in PKGS:
    pkg = ROOT / "harbor-windows" / name
    res = run_qc.static_check(pkg)
    print("=" * 88)
    print("%s" % name)
    print("  static_pass : %s" % res.get("static_pass"))
    print("  task_id     : %s" % res.get("task_id"))
    errs = res.get("errors") or []
    warns = res.get("warnings") or []
    print("  errors (%d):" % len(errs))
    for e in errs:
        print("    ERROR  %s" % e)
    print("  warnings (%d):" % len(warns))
    for w in warns:
        print("    WARN   %s" % w)
    out[name] = {"static_pass": res.get("static_pass"), "task_id": res.get("task_id"),
                 "errors": errs, "warnings": warns}
    print()

dest = ROOT / "harbor-windows" / "_qc_runs" / "qc-verify-4tasks" / "run-qc-static-result.json"
dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("结果已写入：%s" % dest)
