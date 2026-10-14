# -*- coding: utf-8 -*-
"""调用甲方 validate_model_jobs.validate_jobs() 校验四个包的 jobs/ 层。

两份质检包副本（_reference 与 qc-pkg-new）分别运行以便对比。
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
QC_DIRS = {
    "_reference": ROOT / "harbor-windows" / "_reference" / "windows-harbor-qc" / "scripts",
    "qc-pkg-new": ROOT / "harbor-windows" / "_qc_runs" / "qc-pkg-new" / "windows-harbor-qc" / "scripts",
}
PKGS = [
    "wfflab__wfmt-215-v2.1.0-delivery",
    "wfflab__wchunk-216-v1.2.0-delivery",
    "wfflab__wlogseg-218-v1.1.0-delivery",
    "wfflab__wpeimg-219-v1.4.0-delivery",
]

summary = {}
for label, scripts in QC_DIRS.items():
    print("#" * 96)
    print("# 质检包副本：%s" % label)
    print("#" * 96)
    for m in [k for k in list(sys.modules) if k in ("validate_model_jobs", "validate_model_gate", "inspect_delivery")]:
        del sys.modules[m]
    sys.path.insert(0, str(scripts))
    try:
        vmj = importlib.import_module("validate_model_jobs")
        insp = importlib.import_module("inspect_delivery")
    except Exception as exc:  # noqa: BLE001
        print("  导入失败：%r" % (exc,))
        continue

    for name in PKGS:
        pkg = ROOT / "harbor-windows" / name
        doc = insp.inspect_delivery(pkg)
        identity = doc.get("task") or {}
        print("=" * 92)
        print("%s   （交付包 dirhash=%s）" % (name, str(identity.get("harbor_task_checksum"))[:16]))
        try:
            res = vmj.validate_jobs(pkg / "jobs", pkg, identity)
        except Exception as exc:  # noqa: BLE001
            print("  validate_jobs 抛异常：%r" % (exc,))
            continue
        print("  pass : %s" % res.get("pass"))
        errs = res.get("errors") or []
        print("  errors (%d):" % len(errs))
        for e in errs[:18]:
            print("    - %s" % e)
        if len(errs) > 18:
            print("    …（其余 %d 条省略）" % (len(errs) - 18))
        ws = res.get("warnings") or []
        if ws:
            print("  warnings (%d): %s" % (len(ws), ws[:4]))
        summary.setdefault(label, {})[name] = {"pass": res.get("pass"),
                                               "error_count": len(errs),
                                               "errors": errs}
        print()
    sys.path.remove(str(scripts))

dest = ROOT / "harbor-windows" / "_qc_runs" / "qc-verify-4tasks" / "validate-jobs-result.json"
dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print("结果已写入：%s" % dest)
