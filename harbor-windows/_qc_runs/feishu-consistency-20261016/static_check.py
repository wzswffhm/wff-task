# -*- coding: utf-8 -*-
"""对本地题包跑甲方 QC 的静态门禁（不启动 Docker/Harbor）。

复用的是甲方 windows-harbor-qc 的原始脚本，保证口径一致：
  inspect_delivery  -> 交付目录/task 身份
  validate_model_jobs -> jobs/ 14 个原生 job 与原始证据
  validate_model_gate -> 四模型次数与区分度

用法: python static_check.py
输出: static-check.json
"""
from __future__ import annotations

import json
import pathlib
import sys
import traceback

HERE = pathlib.Path(__file__).resolve().parent
QC = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
                  r"\_reference\windows-harbor-qc\scripts")
sys.path.insert(0, str(QC))

from inspect_delivery import inspect_delivery  # noqa: E402
from validate_model_gate import evaluate  # noqa: E402
from validate_model_jobs import validate_jobs  # noqa: E402

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")


def check(pkg: pathlib.Path) -> dict:
    result: dict = {"package": pkg.name}
    try:
        layout = inspect_delivery(pkg)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"inspect_delivery: {type(exc).__name__}: {exc}"
        result["trace"] = traceback.format_exc()[-1500:]
        return result
    result["pass"] = layout.get("pass")
    result["errors"] = layout.get("errors")
    result["warnings"] = layout.get("warnings")
    result["task"] = layout.get("task")
    result["task_config"] = layout.get("task_config")
    result["required_testcases"] = len(layout.get("required_testcases") or [])
    try:
        jobs = validate_jobs(pkg / "jobs", pkg, layout.get("task") or {})
        result["jobs_pass"] = jobs.get("pass")
        result["jobs_errors"] = jobs.get("errors")
        result["jobs_warnings"] = jobs.get("warnings")
        result["jobs_stats"] = jobs.get("stats")
        gate = evaluate(jobs.get("evidence") or {}, layout.get("task") or None)
        result["gate_pass"] = gate.get("pass")
        result["gate_errors"] = gate.get("errors")
        result["gate_stats"] = gate.get("stats")
    except Exception as exc:  # noqa: BLE001
        result["jobs_error"] = f"{type(exc).__name__}: {exc}"
        result["trace"] = traceback.format_exc()[-1500:]
    return result


def main() -> int:
    pkgs = sorted(p for p in HW.glob("wfflab__*-delivery") if p.is_dir())
    print(f"发现 {len(pkgs)} 个本地题包")
    out = []
    for pkg in pkgs:
        print("=" * 60)
        print(pkg.name)
        r = check(pkg)
        out.append(r)
        print(f"  交付目录 pass={r.get('pass')}  错误={r.get('errors')}")
        print(f"  jobs pass={r.get('jobs_pass')}  错误={r.get('jobs_errors')}")
        print(f"  模型门禁 pass={r.get('gate_pass')}  错误={r.get('gate_errors')}")
        print(f"  task={json.dumps(r.get('task'), ensure_ascii=False)}")
    (HERE / "static-check.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n已写入 {HERE / 'static-check.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
