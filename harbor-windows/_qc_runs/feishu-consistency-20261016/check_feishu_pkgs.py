# -*- coding: utf-8 -*-
"""把 5 个飞书交付附件解压到 extract/ 下，然后跑甲方 QC 的静态门禁。

只读检查：不解压覆盖任何本地题包，不改飞书。
输出：feishu-static-check.json / feishu-static-check.md
"""
from __future__ import annotations

import json
import pathlib
import sys
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
QC = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
                  r"\_reference\windows-harbor-qc\scripts")
sys.path.insert(0, str(QC))

from inspect_delivery import inspect_delivery  # noqa: E402
from validate_model_gate import evaluate  # noqa: E402
from validate_model_jobs import validate_jobs  # noqa: E402

ZIPDIR = HERE / "feishu-zip"
EXTRACT = HERE / "extract"


def unpack() -> list[pathlib.Path]:
    EXTRACT.mkdir(parents=True, exist_ok=True)
    roots = []
    for zp in sorted(ZIPDIR.glob("*.zip")):
        target = EXTRACT / zp.stem
        if not target.is_dir():
            with zipfile.ZipFile(zp) as zf:
                zf.extractall(EXTRACT)
        roots.append(target)
    return roots


def check(pkg: pathlib.Path) -> dict:
    r: dict = {"package": pkg.name}
    try:
        layout = inspect_delivery(pkg)
    except Exception as exc:  # noqa: BLE001
        r["error"] = f"{type(exc).__name__}: {exc}"
        return r
    r["layout_pass"] = layout.get("pass")
    r["layout_errors"] = layout.get("errors")
    r["task"] = layout.get("task")
    r["required_testcases"] = len(layout.get("required_testcases") or [])
    try:
        jobs = validate_jobs(pkg / "jobs", pkg, layout.get("task") or {})
        r["jobs_pass"] = jobs.get("pass")
        r["jobs_errors"] = jobs.get("errors")
        gate = evaluate(jobs.get("evidence") or {}, layout.get("task") or None)
        r["gate_pass"] = gate.get("pass")
        r["gate_errors"] = gate.get("errors")
    except Exception as exc:  # noqa: BLE001
        r["jobs_error"] = f"{type(exc).__name__}: {exc}"
    return r


def main() -> int:
    roots = unpack()
    rows = [check(p) for p in roots]
    (HERE / "feishu-static-check.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 飞书交付附件（解压后）的 QC 静态门禁", "",
             "| 附件 | 交付目录 | jobs | 模型门禁 | required | 关键错误 |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            lines.append(f"| {r['package']} | - | - | - | - | {r['error']} |")
            continue
        errs = (r.get("layout_errors") or []) + (r.get("jobs_errors") or []) + (r.get("gate_errors") or [])
        lines.append("| {p} | {l} | {j} | {g} | {n} | {e} |".format(
            p=r["package"], l="✔" if r.get("layout_pass") else "✘",
            j="✔" if r.get("jobs_pass") else "✘", g="✔" if r.get("gate_pass") else "✘",
            n=r.get("required_testcases"), e="；".join(errs[:3]) or "无"))
    (HERE / "feishu-static-check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for r in rows:
        print(json.dumps({k: r.get(k) for k in ("package", "layout_pass", "jobs_pass",
                                                "gate_pass", "required_testcases",
                                                "layout_errors", "jobs_errors", "gate_errors", "error")},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
