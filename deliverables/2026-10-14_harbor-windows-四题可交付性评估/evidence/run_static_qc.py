"""对 harbor-windows 下 4 个 wff 题包执行 windows-harbor-qc 的非 Docker 静态门禁。

用法：
  python run_static_qc.py --qc-root <windows-harbor-qc 目录> --out <结果 json>
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def load(qc_root: Path):
    scripts = qc_root / "scripts"
    for name in ("inspect_delivery", "validate_model_jobs", "validate_model_gate"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(scripts))
    inspect_delivery = importlib.import_module("inspect_delivery")
    validate_model_jobs = importlib.import_module("validate_model_jobs")
    validate_model_gate = importlib.import_module("validate_model_gate")
    sys.path.pop(0)
    return inspect_delivery, validate_model_jobs, validate_model_gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qc-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--packages", nargs="*", default=[
        "wfflab__wchunk-216-v1.2.0-delivery",
        "wfflab__wfmt-215-v2.1.0-delivery",
        "wfflab__wlogseg-218-v1.1.0-delivery",
        "wfflab__wpeimg-219-v1.4.0-delivery",
    ])
    args = parser.parse_args()

    inspect_delivery, validate_model_jobs, validate_model_gate = load(args.qc_root.resolve())
    out: dict[str, object] = {}
    for name in args.packages:
        root = REPO / "harbor-windows" / name
        layout = inspect_delivery.inspect_delivery(root)
        try:
            jobs = validate_model_jobs.validate_jobs(root / "jobs", root, layout.get("task") or {})
            gate = validate_model_gate.evaluate(jobs.get("evidence") or {}, layout.get("task") or None)
        except Exception as exc:  # noqa: BLE001
            jobs = {"pass": False, "errors": [f"{type(exc).__name__}: {exc}"], "warnings": [], "jobs": []}
            gate = {"pass": False, "errors": [f"{type(exc).__name__}: {exc}"], "stats": {}}
        out[name] = {
            "layout_pass": layout["pass"],
            "layout_errors": layout["errors"],
            "layout_warnings": layout["warnings"],
            "task_id": (layout.get("task") or {}).get("task_id"),
            "task_version": (layout.get("task") or {}).get("task_version"),
            "task_checksum": (layout.get("task") or {}).get("harbor_task_checksum"),
            "testcase_count": layout.get("testcase_count"),
            "jobs_pass": jobs.get("pass"),
            "jobs_error_count": len(jobs.get("errors") or []),
            "jobs_errors": jobs.get("errors"),
            "jobs_warnings": jobs.get("warnings"),
            "gate_pass": gate.get("pass"),
            "gate_stats": gate.get("stats"),
            "gate_errors": [e for e in (gate.get("errors") or []) if "testcase" not in e],
        }
        print(f"{name}: layout={layout['pass']} jobs={jobs.get('pass')} "
              f"(errors={len(jobs.get('errors') or [])}) gate={gate.get('pass')}")
        for err in (layout["errors"] or []) + [e for e in (jobs.get("errors") or []) if "testcase" not in e][:6]:
            print(f"   - {err}")
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
