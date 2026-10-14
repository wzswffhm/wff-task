# -*- coding: utf-8 -*-
"""四个交付包的身份/格式一致性核对（对照甲方 checklist.md 的身份一致条款）。"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
STD_ROOT = {"task.toml", "instruction.md", "environment", "solution", "tests", "jobs"}

PKGS = [
    "wfflab__wfmt-215-v2.1.0-delivery",
    "wfflab__wchunk-216-v1.2.0-delivery",
    "wfflab__wlogseg-218-v1.1.0-delivery",
    "wfflab__wpeimg-219-v1.4.0-delivery",
]


def load_toml(p: Path):
    with p.open("rb") as s:
        return tomllib.load(s)


def try_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        return {"__error__": repr(exc)}


for name in PKGS:
    pkg = ROOT / "harbor-windows" / name
    print("=" * 78)
    print(name)
    print("=" * 78)

    m = re.search(r"-v(\d+\.\d+\.\d+)-delivery$", name)
    dir_ver = m.group(1) if m else "(unparsed)"
    print("  目录名版本            : %s" % dir_ver)

    top = sorted(p.name for p in pkg.iterdir())
    print("  顶层条目(%d)          : %s" % (len(top), ", ".join(top)))
    missing = STD_ROOT - set(top)
    extra = set(top) - STD_ROOT
    print("  标准结构缺失          : %s" % (sorted(missing) or "无"))
    print("  标准结构之外          : %s" % (sorted(extra) or "无"))

    t = load_toml(pkg / "task.toml")
    task_ver = (t.get("task") or {}).get("version")
    print("  task.toml [task].version: %s   %s" % (task_ver, "OK" if task_ver == dir_ver else "**与目录名不一致**"))
    img = t.get("docker_image") or ((t.get("environment") or {}).get("docker_image"))
    print("  task.toml docker_image : %s" % (img if img else "**缺失**"))

    for rel in ("tests/rubric.json", "verifier/rubric.conditions.json",
                "environment/agent_visible_paths.json", "tests/judge.toml",
                "environment/adapter.toml", "environment/Dockerfile"):
        p = pkg / rel
        if not p.is_file():
            print("  %-34s: (不存在)" % rel)
            continue
        if rel.endswith(".toml"):
            txt = p.read_text(encoding="utf-8", errors="replace")
        elif rel.endswith(".json"):
            txt = p.read_text(encoding="utf-8-sig", errors="replace")
        else:
            txt = p.read_text(encoding="utf-8", errors="replace")
        vers = sorted(set(re.findall(r'"?task_version"?\s*[:=]\s*"([0-9]+\.[0-9]+\.[0-9]+)"', txt)))
        if rel == "environment/Dockerfile":
            print("  %-34s: %s" % (rel, txt.strip().splitlines()[0][:90] if txt.strip() else "(空)"))
        else:
            print("  %-34s: task_version=%s" % (rel, vers or "未声明"))

    rub = try_json(pkg / "tests" / "rubric.json")
    if isinstance(rub, dict) and "items" in rub:
        wsum = round(sum(float(i["weight"]) for i in rub["items"]), 6)
        ids = [t2 for i in rub["items"] for t2 in i["test_ids"]]
        print("  rubric items/权重和   : %d / %s" % (len(rub["items"]), wsum))
        print("  rubric schema_version : %s" % rub.get("schema_version"))
        print("  rubric test_ids 总数  : %d (去重 %d)" % (len(ids), len(set(ids))))
    req = try_json(pkg / "tests" / "required_testcases.json")
    if isinstance(req, list):
        print("  required testcase 数  : %d" % len(req))
        rub_ids = {t2 for i in rub["items"] for t2 in i["test_ids"]} if isinstance(rub, dict) and "items" in rub else set()
        req_ids = {r.get("id") for r in req}
        print("  required 与 rubric 对齐: %s" % ("一致" if req_ids == rub_ids else "不一致 差集=%s" % sorted(req_ids ^ rub_ids)[:6]))
    jobs_dir = pkg / "jobs"
    if jobs_dir.is_dir():
        js = sorted(d.name for d in jobs_dir.iterdir() if d.is_dir())
        print("  jobs/ 目录(%d)        : %s" % (len(js), ", ".join(js)))

    for extra_file in ("source.json", "REFIT-2026-10-13.md"):
        print("  根级 %-20s: %s" % (extra_file, "存在" if (pkg / extra_file).exists() else "不存在"))
    print()
