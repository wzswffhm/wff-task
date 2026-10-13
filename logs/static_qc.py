# -*- coding: utf-8 -*-
"""static_qc.py -- 跑分**之前**的静态门禁。

用甲方 QC 自己的 inspect_delivery() 检查交付目录层，外加本项目的身份/配置自检，
这样「文档版本过时」「required 数目不符」「rubric 权重不对」这类问题在启动昂贵的
模型轮次之前就会被拦住，而不是跑完 75 分钟才发现。

用法：
    python static_qc.py --task 219
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

QC_SCRIPTS = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
                  r"\qc-pkg-new\windows-harbor-qc\scripts")
sys.path.insert(0, str(QC_SCRIPTS))

from inspect_delivery import harbor_dirhash, inspect_delivery  # noqa: E402

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"

TASKS = {
    "218": {"pkg": "wfflab__wlogseg-218-v1.1.0-delivery", "version": "1.1.0",
            "required": 26, "groups": 6},
    "219": {"pkg": "wfflab__wpeimg-219-v1.4.0-delivery", "version": "1.4.0",
            "required": 43, "groups": 10},
}

ALL_VERSIONS = ("1.0.0", "1.1.0", "1.2.0", "1.3.0")


def suspect_patterns(current: str) -> tuple[str, ...]:
    """Version claims that are stale *for this package* (any other version)."""
    pats = []
    for v in ALL_VERSIONS:
        if v == current:
            continue
        pats += ["task version %s" % v, "task_version = %s" % v,
                 '"task_version": "%s"' % v]
    return tuple(pats)


def is_history_line(line: str) -> bool:
    """A dated revision note about an *older* version is legitimate history."""
    low = line.lower()
    return ("revision " in low or "revision_note" in low or "deprecation record" in low)


def stale_claims(path: Path, patterns, required: int) -> list[str]:
    """Return stale version/count claims, ignoring dated historical notes."""
    found = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if is_history_line(line):
            continue
        for pat in patterns:
            if pat in line:
                found.append("L%d: %r" % (i, pat))
        for m in re.finditer(r"共\s*\*\*(\d+)\*\*\s*条", line):
            if int(m.group(1)) != required:
                found.append("L%d: required count claim %s != %d" % (i, m.group(1), required))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    a = ap.parse_args()
    cfg = TASKS[a.task]
    pkg = REL / "staged" / cfg["pkg"]
    if not pkg.is_dir():
        raise SystemExit("包不存在：%s" % pkg)

    print("=" * 74)
    print("静态门禁（跑分前）  %s  v%s" % (cfg["pkg"], cfg["version"]))
    print("=" * 74)
    problems = []

    # 1) the buyer's own delivery-layer inspection
    doc = inspect_delivery(pkg)
    errs = doc.get("errors") or []
    warns = doc.get("warnings") or []
    print("\n[甲方 inspect_delivery]")
    print("  task_id   : %s" % doc.get("task_id"))
    print("  version   : %s" % doc.get("task_version"))
    print("  dirhash   : %s" % doc.get("harbor_task_checksum"))
    for e in errs:
        # jobs/ only exists after the model rounds, so its absence is expected
        # here; the post-run QC still enforces it.
        if "root item: jobs/" in e:
            print("  (预期) %s —— 跑分前尚未组装，跑分后由 assemble_jobs.py 补齐" % e)
            continue
        print("  ERROR %s" % e)
        problems.append("inspect_delivery: %s" % e)
    for w in warns:
        print("  WARN  %s" % w)

    # 2) identity / config self-checks
    print("\n[身份与判分配置]")
    toml_text = (pkg / "task.toml").read_text(encoding="utf-8", errors="replace")
    version_ok = ('version = "%s"' % cfg["version"]) in toml_text
    print("  task.toml version == %s : %s" % (cfg["version"], version_ok))
    if not version_ok:
        problems.append("task.toml version != %s" % cfg["version"])

    rub = json.loads((pkg / "tests" / "rubric.json").read_text(encoding="utf-8-sig"))
    req = json.loads((pkg / "tests" / "required_testcases.json").read_text(encoding="utf-8-sig"))
    wsum = round(sum(float(i["weight"]) for i in rub["items"]), 6)
    print("  rubric groups  : %d (expect %d)" % (len(rub["items"]), cfg["groups"]))
    print("  rubric version : %s" % rub.get("task_version"))
    print("  weight sum     : %s" % wsum)
    print("  required count : %d (expect %d)" % (len(req), cfg["required"]))
    if len(rub["items"]) != cfg["groups"]:
        problems.append("rubric group count %d != %d" % (len(rub["items"]), cfg["groups"]))
    if rub.get("task_version") != cfg["version"]:
        problems.append("rubric.json task_version %s != %s"
                        % (rub.get("task_version"), cfg["version"]))
    if abs(wsum - 1.0) > 1e-9:
        problems.append("rubric weights sum to %s" % wsum)
    if len(req) != cfg["required"]:
        problems.append("required count %d != %d" % (len(req), cfg["required"]))

    ids = {r["id"] for r in req}
    rub_ids = {t for i in rub["items"] for t in i["test_ids"]}
    if ids != rub_ids:
        problems.append("required ids != rubric test_ids (missing %s / extra %s)"
                        % (sorted(ids - rub_ids)[:5], sorted(rub_ids - ids)[:5]))

    judge = (pkg / "tests" / "judge.toml").read_text(encoding="utf-8", errors="replace")
    import hashlib
    sha = hashlib.sha256((pkg / "tests" / "rubric.json").read_bytes()).hexdigest()
    src_ok = ('source_sha256 = "%s"' % sha) in judge
    print("  judge.toml source_sha256 bound : %s" % src_ok)
    if not src_ok:
        problems.append("judge.toml source_sha256 not bound to rubric.json")

    # 3) stale version / count claims inside the delivered docs
    print("\n[文档版本陈述]")
    stale = []
    for f in pkg.rglob("*"):
        if not f.is_file() or "__pycache__" in f.parts or f.suffix not in (".md", ".json", ".toml", ".ps1"):
            continue
        rel = str(f.relative_to(pkg)).replace("\\", "/")
        if rel.startswith("jobs/"):
            continue
        for hit in stale_claims(f, suspect_patterns(cfg["version"]), cfg["required"]):
            stale.append((rel, hit))
    for rel, hit in stale:
        print("  STALE %s: %s" % (rel, hit))
        problems.append("stale claim in %s: %s" % (rel, hit))
    if not stale:
        print("  无过时版本/计数陈述（带日期的历史修订注释不计）")

    print("\n" + "=" * 74)
    if problems:
        print("静态门禁 FAILED（%d 项）——先修这些，再启动跑分：" % len(problems))
        for p in problems:
            print("  - %s" % p)
        return 1
    frozen = doc.get("harbor_task_checksum") or harbor_dirhash(pkg)
    print("静态门禁 PASSED —— 包内容可冻结，可以启动跑分")
    print("冻结 dirhash: %s" % frozen)
    print("（跑分结束后 jobs/ 会补进包内；QC 侧 dirhash 排除 jobs/，因此该值不变）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
