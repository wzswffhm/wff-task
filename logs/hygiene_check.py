# -*- coding: utf-8 -*-
"""hygiene_check.py -- 交付卫生：找出旧数据残留。

检查三处：
  1. 交付包内（staged/<pkg>/）：非当前版本的文件、备份/临时/缓存文件、
     引用了旧版本或不存在的文件；
  2. 包内 jobs/：是否有旧 checksum 的轮次、失败轮次混在有效轮次里、
     无效槽位证据是否放在不会被 QC 误读的位置；
  3. 交付目录（deliverables/<...>/）：旧版本 zip、旧截图、旧审计产物。

用法：
    python hygiene_check.py --task 219
    python hygiene_check.py --task 218
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"

TASKS = {
    "218": {
        "pkg": "wfflab__wlogseg-218-v1.1.0-delivery",
        "version": "1.1.0",
        "old_versions": ("1.0.0",),
        "deliverable": ROOT / "deliverables" / "2026-10-13_wlogseg218-返修",
    },
    "219": {
        "pkg": "wfflab__wpeimg-219-v1.4.0-delivery",
        "version": "1.4.0",
        "old_versions": ("1.0.0", "1.1.0", "1.2.0", "1.3.0"),
        "deliverable": ROOT / "deliverables" / "2026-10-13_wpeimg219-返修",
    },
}

JUNK_SUFFIXES = (".bak", ".orig", ".old", ".tmp", ".rej", ".swp", "~")
JUNK_NAMES = ("Thumbs.db", ".DS_Store", "exception.txt")


def scan_package(pkg: Path, cfg: dict, problems: list, notes: list) -> None:
    print("\n=== 1) 交付包内 ===")
    files = [p for p in pkg.rglob("*") if p.is_file()]
    print("  文件总数: %d" % len(files))

    junk = []
    for p in files:
        rel = str(p.relative_to(pkg)).replace("\\", "/")
        name = p.name
        if "__pycache__" in p.parts or ".pytest_cache" in p.parts:
            junk.append((rel, "cache dir"))
        elif name.endswith(JUNK_SUFFIXES):
            junk.append((rel, "temp/backup suffix"))
        elif name in JUNK_NAMES:
            junk.append((rel, "junk file"))
        elif re.search(r"\.(py|json|md|toml|ps1)\.\d+$", name):
            junk.append((rel, "editor backup"))
    if junk:
        for rel, why in junk:
            print("  JUNK  %s (%s)" % (rel, why))
            problems.append("包内残留 %s: %s" % (rel, why))
    else:
        print("  无缓存/备份/临时文件")

    # stale version strings inside the package (excluding dated history notes)
    stale = []
    for p in files:
        rel = str(p.relative_to(pkg)).replace("\\", "/")
        if rel.startswith("jobs/") or p.suffix not in (".md", ".json", ".toml", ".ps1", ".py"):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            low = line.lower()
            if "revision" in low or "revision_note" in low or "deprecation record" in low:
                continue
            for v in cfg["old_versions"]:
                for pat in ("task version %s" % v, "task_version = %s" % v,
                            '"task_version": "%s"' % v):
                    if pat in line:
                        stale.append((rel, i, pat))
    if stale:
        for rel, i, pat in stale:
            print("  STALE %s:%d %r" % (rel, i, pat))
            problems.append("包内过时版本陈述 %s:%d %r" % (rel, i, pat))
    else:
        print("  无过时版本陈述（带日期的历史修订注释不计）")

    # dangling references: files named in the docs that are not delivered
    print("\n  外部引用检查:")
    names = {p.name for p in files}
    rels = {str(p.relative_to(pkg)).replace("\\", "/") for p in files}
    refs = Counter()
    for p in files:
        if p.suffix not in (".md", ".json", ".toml", ".ps1"):
            continue
        rel = str(p.relative_to(pkg)).replace("\\", "/")
        if rel.startswith("jobs/"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"`([A-Za-z0-9_./\\-]+\.(?:md|json|toml|ps1|py|bin|zip))`", text):
            refs[m.group(1)] += 1
    missing = []
    for ref in sorted(refs):
        base = ref.replace("\\", "/").split("/")[-1]
        if ref in rels or base in names:
            continue
        if ref.startswith(("http", "jobs/")):
            continue
        missing.append(ref)
    if missing:
        print("    → %d 个引用指向包外（构建工具／出题方工作区，非交付物）:" % len(missing))
        for m in missing:
            print("      %s" % m)
        notes.append("文档引用了包外构建产物（交付方不可见）: %s"
                     % ", ".join(missing[:8]))
    else:
        print("    所有被引用的文件都在包内")

    # section references such as "REFIT-2026-10-13.md §R8" must resolve to a
    # real heading, otherwise a reviewer follows a pointer that leads nowhere.
    print("\n  章节引用检查:")
    section_refs = Counter()
    for p in files:
        if p.suffix not in (".md", ".json"):
            continue
        rel = str(p.relative_to(pkg)).replace("\\", "/")
        if rel.startswith("jobs/"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"§(R\d+)", text):
            section_refs[m.group(1)] += 1
    headings = set()
    for doc in ("REFIT-2026-10-13.md", "verifier/README.md", "verifier/ISOLATION.md",
                "verifier/WINDOWS_VALUE.md"):
        dpath = pkg / doc
        if dpath.is_file():
            for line in dpath.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r"^#{2,4}\s*(R\d+)", line.strip())
                if m:
                    headings.add(m.group(1))
    dangling = sorted(r for r in section_refs if r not in headings)
    if dangling:
        for r in dangling:
            print("    DANGLING §%s（被引用 %d 次，但包内没有该章节）"
                  % (r, section_refs[r]))
            problems.append("章节引用悬空: §%s" % r)
    else:
        print("    所有 §R* 引用都能在包内找到对应章节（%s）"
              % (", ".join(sorted(section_refs)) or "无引用"))


def scan_jobs(pkg: Path, cfg: dict, problems: list, notes: list) -> None:
    print("\n=== 2) 包内 jobs/ ===")
    jobs = pkg / "jobs"
    if not jobs.is_dir():
        print("  jobs/ 尚未组装（跑分前）")
        notes.append("jobs/ 尚未组装")
        return
    job_dirs = sorted(d for d in jobs.iterdir()
                      if d.is_dir() and (d / "result.json").is_file())
    print("  QC 可见 job 数: %d" % len(job_dirs))
    cks = Counter()
    for jd in job_dirs:
        rj = jd / "result.json"
        try:
            doc = json.loads(rj.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001
            continue
        cks[(doc.get("task_checksum") or "-")[:16]] += 1
    print("  task_checksum 分布: %s" % dict(cks))
    if len(cks) != 1:
        problems.append("jobs/ 内 task_checksum 不唯一: %s" % dict(cks))
    else:
        print("  单一 checksum OK")

    # a replaced round must NOT sit directly under jobs/
    leaked = []
    for d in jobs.iterdir():
        if not d.is_dir():
            continue
        for trial in d.iterdir():
            rj = trial / "result.json" if trial.is_dir() else None
            if rj and rj.is_file():
                try:
                    doc = json.loads(rj.read_text(encoding="utf-8-sig"))
                except Exception:  # noqa: BLE001
                    continue
                if (doc.get("exception_info") or {}).get("exception_type"):
                    leaked.append(d.name)
    if leaked:
        for name in leaked:
            print("  LEAK  失败轮次暴露在 jobs/ 顶层: %s" % name)
            problems.append("失败轮次 %s 位于 jobs/ 顶层（会被 QC 读成模型轮次）" % name)
    else:
        print("  无失败轮次混入 jobs/ 顶层")

    inv = jobs / "_index" / "invalid-rounds"
    if inv.is_dir():
        n = sum(1 for d in inv.iterdir() if d.is_dir())
        print("  无效槽位证据归档: %d 轮（位于 _index/，QC 不扫描）" % n)
    for f in ("invalid-slots.json", "INVALID-SLOTS.md"):
        print("  %s: %s" % (f, "存在" if (jobs / f).is_file() else "缺失"))
        if not (jobs / f).is_file():
            notes.append("jobs/%s 缺失" % f)


def scan_deliverable(cfg: dict, problems: list, notes: list) -> None:
    print("\n=== 3) 交付目录 ===")
    deliv = cfg["deliverable"]
    if not deliv.is_dir():
        print("  目录不存在: %s" % deliv)
        notes.append("交付目录尚未生成")
        return
    files = sorted(p for p in deliv.rglob("*") if p.is_file())
    print("  文件数: %d" % len(files))
    for p in files:
        rel = str(p.relative_to(deliv)).replace("\\", "/")
        mark = ""
        for v in cfg["old_versions"]:
            if v in rel:
                mark = "  <-- 旧版本(%s)" % v
                problems.append("交付目录含旧版本文件: %s" % rel)
        if p.name.endswith(JUNK_SUFFIXES):
            mark = "  <-- 临时/备份"
            problems.append("交付目录含临时文件: %s" % rel)
        print("    %-64s %8d%s" % (rel, p.stat().st_size, mark))

    zips = [p for p in files if p.suffix == ".zip"]
    if len(zips) > 1:
        problems.append("交付目录有 %d 个 zip（应只保留当前版本）" % len(zips))
    elif zips:
        print("  当前 zip: %s" % zips[0].name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    a = ap.parse_args()
    cfg = TASKS[a.task]
    pkg = REL / "staged" / cfg["pkg"]

    print("=" * 74)
    print("交付卫生检查  %s  (v%s)" % (cfg["pkg"], cfg["version"]))
    print("=" * 74)

    problems: list[str] = []
    notes: list[str] = []
    scan_package(pkg, cfg, problems, notes)
    scan_jobs(pkg, cfg, problems, notes)
    scan_deliverable(cfg, problems, notes)

    print("\n" + "=" * 74)
    if problems:
        print("发现 %d 项旧数据残留/污染：" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    print("未发现旧数据残留")
    if notes:
        print("备注:")
        for n in notes:
            print("  - %s" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
