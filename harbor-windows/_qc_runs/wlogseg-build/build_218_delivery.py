# -*- coding: utf-8 -*-
"""build_218_delivery.py —— 组装并打包 wfflab__wlogseg-218 交付 ZIP。

结构照 215/216 的单根形态（zip 顶层只有同名目录）：

    wfflab__wlogseg-218-v1.0.0-delivery/
      instruction.md  task.toml
      environment/  jobs/  solution/  tests/  verifier/

排除项：extras/（伴随材料，不进交付包）、缓存目录、results/logs。

用法：
    python build_218_delivery.py [--skip-zip]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
PKG_NAME = "wfflab__wlogseg-218-v1.0.0-delivery"
SRC = ROOT / "harbor-windows" / PKG_NAME
DELIV = ROOT / "deliverables" / "2026-10-12_wlogseg218-交付"
DIST = DELIV / "build" / PKG_NAME
OUT = DELIV / "package"
ZIP_NAME = PKG_NAME + ".zip"

TOP_ITEMS = ["instruction.md", "task.toml", "environment", "jobs", "solution",
             "tests", "verifier"]
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".git", "results", "logs",
             "extras"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
STORE_SUFFIXES = {".zip", ".whl", ".png", ".jpg", ".jpeg", ".gz", ".7z", ".exe"}


def stage_dist() -> dict:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    missing = []
    counts = {}
    for item in TOP_ITEMS:
        s = SRC / item
        if not s.exists():
            missing.append(item)
            continue
        d = DIST / item
        if s.is_dir():
            n = 0
            for p in sorted(x for x in s.rglob("*") if x.is_file()):
                rel = p.relative_to(s)
                if set(rel.parts) & SKIP_DIRS or p.name in SKIP_FILES:
                    continue
                t = d / rel
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, t)
                n += 1
            counts[item] = n
        else:
            shutil.copy2(s, d)
            counts[item] = 1
    return {"counts": counts, "missing": missing}


def pack() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / ZIP_NAME
    if target.exists():
        target.unlink()
    count = 0
    raw = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(p for p in DIST.rglob("*") if p.is_file()):
            rel = path.relative_to(DIST)
            if set(rel.parts) & SKIP_DIRS or path.name in SKIP_FILES:
                continue
            method = (zipfile.ZIP_STORED if path.suffix.lower() in STORE_SUFFIXES
                      else zipfile.ZIP_DEFLATED)
            zf.write(path, "%s/%s" % (PKG_NAME, rel.as_posix()), compress_type=method)
            count += 1
            raw += path.stat().st_size
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / (ZIP_NAME + ".sha256")).write_text("%s  %s\n" % (digest, ZIP_NAME), encoding="ascii")

    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    lvl2 = sorted({"/".join(n.split("/")[:2]) for n in names if len(n.split("/")) > 1})
    report = {"zip": str(target), "entries": count, "raw_bytes": raw,
              "zip_bytes": target.stat().st_size, "sha256": digest,
              "top_level": tops, "second_level": lvl2}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if tops != [PKG_NAME]:
        raise SystemExit("!! zip 顶层不是单一同名目录：%s" % tops)
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-zip", action="store_true")
    a = ap.parse_args()
    info = stage_dist()
    print("staged:", json.dumps(info, ensure_ascii=False))
    if info["missing"]:
        raise SystemExit("!! 缺顶层要件：%s" % info["missing"])
    if not (DIST / "jobs").is_dir():
        raise SystemExit("!! 缺 jobs/（先跑 assemble_218_jobs_archive.py）")
    if not a.skip_zip:
        pack()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
