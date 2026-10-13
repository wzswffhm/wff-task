# -*- coding: utf-8 -*-
"""sync_conditions.py -- 用 tests/rubric.json 同步 verifier/rubric.conditions.json。

只同步 weight 与 test_ids（以及条目集合），conditions 里的 description /
pass_condition / failure_reason 由人工维护、保持不动。

用法：python sync_conditions.py --task <包目录>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    a = ap.parse_args()
    pkg = Path(a.task)

    rub = json.loads((pkg / "tests" / "rubric.json").read_text(encoding="utf-8-sig"))
    cond_path = pkg / "verifier" / "rubric.conditions.json"
    cond = json.loads(cond_path.read_text(encoding="utf-8-sig"))

    want = {i["rubric_id"]: (float(i["weight"]), list(i["test_ids"])) for i in rub["items"]}
    have = {c["rubric_id"]: c for c in cond["programmatic"]}

    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    if missing or extra:
        print("FAIL: rubric-only groups=%s ; conditions-only groups=%s" % (missing, extra))
        return 2

    for rid, (weight, tids) in want.items():
        have[rid]["weight"] = weight
        have[rid]["test_ids"] = tids
        if not have[rid].get("description") or not have[rid].get("pass_condition"):
            print("FAIL: %s is missing description/pass_condition" % rid)
            return 2

    # keep the file ordered like the rubric so a diff reads naturally
    cond["programmatic"] = [have[i["rubric_id"]] for i in rub["items"]]
    cond["task_version"] = rub["task_version"]
    cond["programmatic_weight"] = 1.0
    cond["llm_judge_weight"] = 0.0
    cond_path.write_text(json.dumps(cond, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8", newline="\n")

    total = sum(w for w, _ in want.values())
    n_cases = sum(len(t) for _, t in want.values())
    print("synced %d groups, weight sum=%.6f, cases=%d" % (len(want), total, n_cases))
    if abs(total - 1.0) > 1e-9:
        print("FAIL: weights do not sum to 1.0")
        return 2

    # cross-check against required_testcases.json
    req_path = pkg / "tests" / "required_testcases.json"
    if req_path.is_file():
        req = {r["id"] for r in json.loads(req_path.read_text(encoding="utf-8-sig"))}
        rub_ids = {t for _, t in want.values() for t in t}
        if req != rub_ids:
            print("FAIL: required ids != rubric ids (missing %s / extra %s)"
                  % (sorted(req - rub_ids)[:5], sorted(rub_ids - req)[:5]))
            return 2
        print("required ids match the rubric (%d cases)" % len(req))
    return 0


if __name__ == "__main__":
    sys.exit(main())
