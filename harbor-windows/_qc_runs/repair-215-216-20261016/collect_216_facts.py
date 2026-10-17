# -*- coding: utf-8 -*-
"""collect_216_facts.py —— 采集 216 包的可测事实，用于生成 WIP94 / D01-D20。

只读。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PKG = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wvas-216-v1.0.1-delivery")
OUT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\repair-215-216-20261016\facts-216-base.json")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    f: dict = {"package": str(PKG), "name": PKG.name}
    files = [p for p in PKG.rglob("*") if p.is_file() and "jobs" not in p.parts]
    f["file_count_no_jobs"] = len(files)
    f["files"] = {p.relative_to(PKG).as_posix(): p.stat().st_size for p in files}

    # instruction
    ins = PKG / "instruction.md"
    raw = ins.read_bytes()
    txt = raw.decode("utf-8")
    f["instruction"] = {
        "bytes": len(raw), "chars": len(txt),
        "lines": len(txt.splitlines()),
        "h1": re.findall(r"^#\s+(.+)$", txt, re.M),
        "h2": re.findall(r"^##\s+(.+)$", txt, re.M),
        "has_replacement_char": "\ufffd" in txt,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

    # task.toml
    toml = (PKG / "task.toml").read_text(encoding="utf-8-sig")
    f["task_toml"] = {}
    for k in ("id", "name", "version", "task_type", "docker_image"):
        m = re.search(rf'^\s*{k}\s*=\s*"?([^"\n]+)"?', toml, re.M)
        f["task_toml"][k] = m.group(1).strip() if m else None
    f["task_toml"]["has_knowledge_tree"] = "knowledge_tree" in toml
    f["task_toml"]["has_authors"] = bool(re.search(r"^\[\[task\.authors\]\]|authors\s*=\s*\[", toml, re.M))

    # required testcases
    rq = json.loads((PKG / "tests" / "required_testcases.json").read_text(encoding="utf-8-sig"))
    rows = rq if isinstance(rq, list) else rq.get("testcases") or []
    f["required"] = {
        "total": len(rows),
        "ids": [r.get("id") for r in rows],
        "groups": {},
    }
    for r in rows:
        g = str(r.get("group") or "?").upper()
        f["required"]["groups"][g] = f["required"]["groups"].get(g, 0) + 1

    # judge / rubric
    judge = (PKG / "tests" / "judge.toml").read_text(encoding="utf-8-sig")
    f["judge"] = {
        "source_sha256": (re.search(r'source_sha256\s*=\s*"([0-9a-f]+)"', judge) or [None, None])[1],
        "rubric_blocks": len(re.findall(r"\[\[rubric\]\]", judge)),
        "tiers": re.findall(r'tier\s*=\s*"([^"]+)"', judge),
    }
    rub = PKG / "tests" / "rubric.json"
    f["rubric_sha256"] = sha(rub) if rub.is_file() else None
    try:
        rj = json.loads(rub.read_text(encoding="utf-8-sig"))
        f["rubric"] = {
            "keys": list(rj.keys())[:12] if isinstance(rj, dict) else None,
            "n_items": len(rj.get("testcases") or rj.get("items") or []) if isinstance(rj, dict) else None,
        }
    except Exception:
        f["rubric"] = None

    # mechanism
    mech = PKG / "metadata" / "windows_mechanism.json"
    if mech.is_file():
        m = json.loads(mech.read_text(encoding="utf-8-sig"))
        f["mechanism"] = {
            "keys": list(m.keys()),
            "anchors": len(m.get("anchors") or m.get("mechanisms") or []),
            "counterfactual": (m.get("counterfactual") or {}).get("answer"),
        }

    # scripts
    f["scripts"] = {}
    for p in files:
        rel = p.relative_to(PKG).as_posix()
        if rel.endswith((".ps1", ".bat")) and "/vendor/" not in rel:
            f["scripts"][rel] = p.stat().st_size

    # workspace modules
    f["workspace"] = {}
    for p in (PKG / "environment" / "workspace").rglob("*.py"):
        f["workspace"][p.relative_to(PKG).as_posix()] = p.stat().st_size

    # solution
    f["solution"] = {}
    for p in (PKG / "solution").rglob("*"):
        if p.is_file():
            f["solution"][p.relative_to(PKG).as_posix()] = p.stat().st_size

    # vendor inventory
    inv = PKG / "environment" / "vendor" / "INVENTORY.json"
    if inv.is_file():
        try:
            f["vendor_inventory"] = json.loads(inv.read_text(encoding="utf-8-sig"))
        except Exception:
            f["vendor_inventory"] = None

    # tests dir
    f["tests"] = {}
    for p in (PKG / "tests").rglob("*"):
        if p.is_file():
            f["tests"][p.relative_to(PKG).as_posix()] = p.stat().st_size

    OUT.write_text(json.dumps(f, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in f.items() if k not in ("files", "vendor_inventory")},
                     ensure_ascii=False, indent=2))
    print("\n-> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
