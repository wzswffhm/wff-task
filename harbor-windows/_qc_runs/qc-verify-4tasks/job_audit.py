# -*- coding: utf-8 -*-
"""审计四个交付包的 jobs/：身份、轮次、reward，以及与交付包 Harbor dirhash 的一致性。

判据（甲方参考包 06-acceptance-gates.md 身份门）：
    全部 job 的 task_checksum == 交付包的 Harbor dirhash
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
sys.path.insert(0, str(ROOT / "harbor-windows" / "_reference" / "windows-harbor-qc" / "scripts"))
from inspect_delivery import harbor_dirhash  # noqa: E402

PKGS = [
    "wfflab__wfmt-215-v2.1.0-delivery",
    "wfflab__wchunk-216-v1.2.0-delivery",
    "wfflab__wlogseg-218-v1.1.0-delivery",
    "wfflab__wpeimg-219-v1.4.0-delivery",
]


def jload(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        try:
            return json.loads(p.read_text(encoding="utf-8-sig", errors="replace"))
        except Exception:  # noqa: BLE001
            return None


for name in PKGS:
    pkg = ROOT / "harbor-windows" / name
    dh = harbor_dirhash(pkg)
    print("=" * 96)
    print("%s" % name)
    print("  交付包 Harbor dirhash : %s" % dh)
    jobs = pkg / "jobs"
    rows = []
    for jd in sorted(d for d in jobs.iterdir() if d.is_dir()):
        rj = jd / "result.json"
        if not rj.is_file():
            rows.append((jd.name, "(无 result.json)", "", "", "", "", ""))
            continue
        doc = jload(rj) or {}
        ai = (doc.get("agent_info") or {}).get("model_info") or {}
        ar = ((doc.get("agent_result") or {}).get("metadata") or {})
        trial = doc.get("trial_name") or ""
        alias = ai.get("alias") or ar.get("alias") or ""
        label = ai.get("label") or ar.get("label") or ""
        role = ar.get("role") or ""
        model = ar.get("model") or ""
        cks = (doc.get("task_checksum") or "")[:16]
        rew = ((doc.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        status = ((ar.get("result") or {}).get("status")) or ""
        rows.append((jd.name, trial, alias, label, role or model, cks, rew, status))
    print("  job 数: %d" % len(rows))
    print("  %-22s %-40s %-10s %-12s %-6s %-18s %s" %
          ("目录", "trial_name", "alias", "label", "role", "checksum(16)", "reward"))
    for r in rows:
        print("  %-22s %-40s %-10s %-12s %-6s %-18s %s" %
              (r[0][:22], str(r[1])[:40], str(r[2])[:10], str(r[3])[:12],
               str(r[4])[:6], str(r[5])[:18], r[6]))
    cks = Counter(r[5] for r in rows)
    ok = [r[5] for r in rows if r[5]]
    uniq = set(ok)
    print("  checksum 唯一: %s（取值 %s）" % (len(uniq) == 1, sorted(uniq)))
    matched = [c for c in uniq if dh.startswith(c) or c and dh[:16] == c]
    print("  与交付包 dirhash 一致: %s" % ("是" if matched else "**否 —— 身份门 FAIL**"))
    print()
