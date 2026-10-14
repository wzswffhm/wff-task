# -*- coding: utf-8 -*-
"""用甲方质检包的 inspect_delivery() 静态检查 215/216/218/219 四个交付包。

判据来源：Windows 外采质检参考包（windows-harbor-qc）的 scripts/inspect_delivery.py，
其随附手册与《Windows-48题质检-专家修复详解版-20261012》逐字节一致。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
QC_SCRIPTS = ROOT / "harbor-windows" / "_reference" / "windows-harbor-qc" / "scripts"
sys.path.insert(0, str(QC_SCRIPTS))

from inspect_delivery import inspect_delivery, harbor_dirhash  # noqa: E402

PKGS = [
    "wfflab__wfmt-215-v2.1.0-delivery",
    "wfflab__wchunk-216-v1.2.0-delivery",
    "wfflab__wlogseg-218-v1.1.0-delivery",
    "wfflab__wpeimg-219-v1.4.0-delivery",
]

out = {}
for name in PKGS:
    pkg = ROOT / "harbor-windows" / name
    print("=" * 78)
    print(name)
    print("=" * 78)
    if not pkg.is_dir():
        print("  包不存在：%s" % pkg)
        out[name] = {"pass": False, "errors": ["package dir missing"], "warnings": []}
        continue
    try:
        doc = inspect_delivery(pkg)
    except Exception as exc:  # noqa: BLE001
        print("  inspect_delivery 抛异常：%r" % (exc,))
        out[name] = {"pass": False, "errors": ["exception: %r" % (exc,)], "warnings": []}
        continue
    ident = doc.get("task") or {}
    print("  pass            : %s" % doc.get("pass"))
    print("  task_id         : %s" % ident.get("task_id"))
    print("  task_version    : %s" % ident.get("task_version"))
    print("  dirhash         : %s" % ident.get("harbor_task_checksum"))
    print("  testcase_count  : %s" % doc.get("testcase_count"))
    for e in doc.get("errors") or []:
        print("  ERROR : %s" % e)
    for w in doc.get("warnings") or []:
        print("  WARN  : %s" % w)
    if not (doc.get("errors") or []):
        print("  -- 无 ERROR --")
    out[name] = {
        "pass": doc.get("pass"),
        "task_id": ident.get("task_id"),
        "task_version": ident.get("task_version"),
        "harbor_task_checksum": ident.get("harbor_task_checksum"),
        "testcase_count": doc.get("testcase_count"),
        "errors": doc.get("errors") or [],
        "warnings": doc.get("warnings") or [],
        "dirhash_verify": harbor_dirhash(pkg),
    }
    print()

result = ROOT / "harbor-windows" / "_qc_runs" / "qc-verify-4tasks" / "inspect-result.json"
result.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("结果已写入：%s" % result)
npass = sum(1 for v in out.values() if v.get("pass"))
print("通过 %d / %d" % (npass, len(out)))
