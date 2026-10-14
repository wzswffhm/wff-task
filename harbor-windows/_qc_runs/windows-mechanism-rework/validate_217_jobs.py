# -*- coding: utf-8 -*-
"""用甲方最新 validate_model_jobs 校验 generate-win 路线产物（wfflab__wreparse-217）的 jobs/ 层。

目的：判断「改用 generate-win 路线」是否能满足飞书返修原因里的 job 归档层要求
（task_checksum 绑定、required 集合一致、verifier.log、INVALID/FAIL 语义等）。
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
SCRIPTS = ROOT / "harbor-windows" / "_reference" / "windows-harbor-qc" / "scripts"
PKG = ROOT / "deliverables" / "2026-10-14_Windows-48题质检-专家修复详解版" / "extracted" / "_217"

sys.path.insert(0, str(SCRIPTS))
vmj = importlib.import_module("validate_model_jobs")
insp = importlib.import_module("inspect_delivery")

print("包根:", PKG)
print("子项:", sorted(p.name for p in PKG.iterdir()))

task_root = PKG / "outside_harbor-assets" / "wfflab__wreparse-217"
jobs_root = PKG / "jobs"
print("task_root 存在:", task_root.is_dir(), "| jobs_root 存在:", jobs_root.is_dir())
if jobs_root.is_dir():
    dirs = sorted(p.name for p in jobs_root.iterdir() if p.is_dir())
    print("jobs 子目录(%d):" % len(dirs), dirs[:6], "…" if len(dirs) > 6 else "")

doc = insp.inspect_delivery(PKG)
identity = doc.get("task") or {}
print("inspect_delivery task 身份:", json.dumps(identity, ensure_ascii=False)[:300])

try:
    res = vmj.validate_jobs(jobs_root, task_root, identity)
except Exception as exc:  # noqa: BLE001
    print("validate_jobs 抛异常:", repr(exc))
    raise SystemExit(0)

errs = res.get("errors") or []
print()
print("pass  :", res.get("pass"))
print("errors:", len(errs))
for e in errs[:25]:
    print("  -", e)
if len(errs) > 25:
    print("  …（其余 %d 条省略）" % (len(errs) - 25))
ws = res.get("warnings") or []
print("warnings:", len(ws))
for w in ws[:5]:
    print("  ~", w)

out = ROOT / "harbor-windows" / "_qc_runs" / "windows-mechanism-rework" / "validate-217-jobs-result.json"
out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print("结果已写入:", out)
