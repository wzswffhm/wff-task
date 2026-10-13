# -*- coding: utf-8 -*-
"""patch_rubric_conditions.py -- 把 verifier/rubric.conditions.json 升到 v3。

用法：
    python patch_rubric_conditions.py --task <包目录>

做四件事：
  1. schema_version -> rubric-conditions-v3，programmatic_weight=1.0、
     llm_judge_weight=0.0，llm_judge 数组清空（保留字段，显式声明没有评审项）；
  2. 程序化各项权重按传入的 weights JSON 重设，并校验合计为 1.0；
  3. 各组的 test_ids 按传入的 groups JSON 重设（与 tests/rubric.json 对齐）；
  4. 写入 revision_note。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--weights", required=True, help="JSON: {rubric_id: weight}")
    ap.add_argument("--groups", required=True, help="JSON: {rubric_id: [test_id,...]}")
    a = ap.parse_args()

    task = Path(a.task).resolve()
    path = task / "verifier" / "rubric.conditions.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    weights = json.loads(a.weights)
    groups = json.loads(a.groups)

    rubric = json.loads((task / "tests" / "rubric.json").read_text(encoding="utf-8"))
    expected = {item["rubric_id"]: item["test_ids"] for item in rubric["items"]}

    doc["schema_version"] = "rubric-conditions-v3"
    doc["programmatic_weight"] = 1.0
    doc["llm_judge_weight"] = 0.0

    seen = set()
    total = 0.0
    for item in doc["programmatic"]:
        rid = item["rubric_id"]
        if rid not in weights or rid not in groups:
            print("FAIL: no weight/group supplied for %s" % rid)
            return 2
        item["weight"] = weights[rid]
        item["test_ids"] = groups[rid]
        total += float(weights[rid])
        seen.add(rid)
        if rid in expected and expected[rid] != groups[rid]:
            print("FAIL: %s test_ids differ from tests/rubric.json" % rid)
            print("  conditions:", groups[rid])
            print("  rubric    :", expected[rid])
            return 2
    missing = set(expected) - seen
    if missing:
        print("FAIL: groups missing from conditions: %s" % sorted(missing))
        return 2
    if round(total, 6) != 1.0:
        print("FAIL: programmatic weights sum to %s" % total)
        return 2

    doc["llm_judge"] = []
    doc["revision_note"] = (
        "v3 (2026-10-13, task version 1.1.0): the llm_judge reviewer items are "
        "retired. The effective score has always been the binary required "
        "F2P/P2P gate, so declaring 0.5 of reviewer weight next to it described "
        "a score that was never produced. The four reviewer items are removed, "
        "the programmatic weights are normalised to 1.0, and the test_ids now "
        "match tests/rubric.json exactly. Deprecation record: "
        "REFIT-2026-10-13.md.")

    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
    print("rubric.conditions.json -> v3; %d programmatic groups, weight sum=%s"
          % (len(doc["programmatic"]), total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
