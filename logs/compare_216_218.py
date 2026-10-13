# -*- coding: utf-8 -*-
"""compare_216_218.py -- 把 218 v1.1.0 与已通过验收的 216 v1.2.1 逐项对标。

用法：python compare_216_218.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
HW = ROOT / "harbor-windows"
STAGED = HW / "_qc_runs" / "relaunch-20261013" / "staged"

TASKS = {
    "216 (已验收)": HW / "wfflab__wchunk-216-v1.2.0-delivery",
    "218 (本轮)": STAGED / "wfflab__wlogseg-218-v1.1.0-delivery",
}


def read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return default


def tree(root: Path):
    out = set()
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".pytest_cache")]
        for f in fn:
            out.add(str(Path(dp, f).relative_to(root)).replace("\\", "/"))
    return out


def main() -> int:
    for label, root in TASKS.items():
        print("=" * 78)
        print("%s   %s" % (label, root.name))
        print("-" * 78)
        if not root.is_dir():
            print("  MISSING PACKAGE")
            continue
        names = tree(root)
        # 1) five-piece set
        for item in ("task.toml", "instruction.md", "environment", "solution", "tests", "jobs"):
            present = any(n == item or n.startswith(item + "/") for n in names)
            print("  %-16s %s" % (item, "OK" if present else "MISSING"))
        # 2) jobs
        jobs = root / "jobs"
        job_dirs = sorted(d.name for d in jobs.iterdir() if d.is_dir() and d.name != "_index") \
            if jobs.is_dir() else []
        print("  jobs count      : %d" % len(job_dirs))
        print("  jobs root files : %s" % ", ".join(
            sorted(p.name for p in jobs.iterdir() if p.is_file())) if jobs.is_dir() else "-")
        cks = set()
        cases = set()
        for jd in job_dirs:
            rp = jobs / jd / "verifier" / "report.json"
            if rp.is_file():
                rep = read_json(rp, {}) or {}
                cases.add(len(rep.get("cases") or []))
            vr = jobs / jd / "verifier" / "result.json"
            if vr.is_file():
                vdoc = read_json(vr, {}) or {}
                if isinstance(vdoc, dict):
                    df = vdoc.get("derived_from")
                    if isinstance(df, dict):
                        cks.add(df.get("harbor_task_checksum"))
                rj = jobs / jd / "result.json"
                if rj.is_file():
                    res = read_json(rj, {}) or {}
                    if isinstance(res, dict) and res.get("task_checksum"):
                        cks.add(res["task_checksum"])
        print("  unique checksums: %s" % (sorted({c[:16] for c in cks if c}) or "n/a"))
        print("  cases per job   : %s" % sorted(cases))
        # 3) judge config
        judge = (root / "tests" / "judge.toml").read_text(encoding="utf-8", errors="replace")
        for key in ("schema_version", "programmatic_weight", "llm_judge_weight"):
            for line in judge.splitlines():
                if line.strip().startswith(key):
                    print("  %-16s %s" % (key, line.split("=", 1)[1].strip()))
                    break
        rub = read_json(root / "tests" / "rubric.json", {}) or {}
        items = rub.get("items", [])
        print("  rubric groups   : %d, weight sum=%s" % (
            len(items), round(sum(float(i["weight"]) for i in items), 6)))
        req = read_json(root / "tests" / "required_testcases.json", []) or []
        print("  required        : %d (F2P %d / P2P %d)" % (
            len(req), sum(1 for r in req if r["group"] == "F2P"),
            sum(1 for r in req if r["group"] == "P2P")))
        # 4) verifier side
        for item, path in (
            ("WINDOWS_VALUE.md", root / "verifier" / "WINDOWS_VALUE.md"),
            ("ISOLATION.md", root / "verifier" / "ISOLATION.md"),
            ("negative_probe", root / "verifier" / "negative_access_probe.ps1"),
            ("SEALED_MANIFEST", root / "verifier" / "SEALED_MANIFEST.json"),
            ("rubric.conditions", root / "verifier" / "rubric.conditions.json"),
        ):
            print("  %-16s %s" % (item, "OK" if path.is_file() else "MISSING"))
        # 5) docker pin + identity
        import tomllib
        with open(root / "task.toml", "rb") as fh:
            t = tomllib.load(fh)
        df = (root / "environment" / "Dockerfile").read_text(encoding="utf-8", errors="replace")
        from_line = next((l for l in df.splitlines() if l.startswith("FROM")), "")
        print("  docker_image    : %s" % ("pinned" if t.get("docker_image") else "ABSENT"))
        print("  FROM == pin     : %s" % (
            t.get("docker_image") and t.get("docker_image") in from_line))
        print("  task.version    : %s" % t.get("task", {}).get("version"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
