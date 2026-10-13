# -*- coding: utf-8 -*-
"""gen_judge_bindings.py -- 从 rubric.json / 隐藏套件派生判分绑定。

用法：
    python gen_judge_bindings.py --task <包目录>

做三件事，全部幂等：
  1. 把 judge.toml 的 source_sha256 写成 tests/rubric.json 的真实 sha256；
  2. 从 rubric.json 生成 tests/required_testcases.json（F2P/P2P 由 id 前缀决定）；
  3. 核对 rubric 的每个 test_id 都能在 run_tests.ps1 的 slug 映射里找到，
     反之亦然；不一致就报错退出（防止配置与套件漂移）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    a = ap.parse_args()

    task = Path(a.task).resolve()
    tests = task / "tests"
    rubric_path = tests / "rubric.json"
    judge_path = tests / "judge.toml"
    req_path = tests / "required_testcases.json"
    runner_path = tests / "run_tests.ps1"

    rubric_bytes = rubric_path.read_bytes()
    sha = hashlib.sha256(rubric_bytes).hexdigest()
    judge = judge_path.read_text(encoding="utf-8")
    judge = re.sub(r'source_sha256 = "[0-9a-f]*"|source_sha256 = "__RUBRIC_SHA256__"',
                   'source_sha256 = "%s"' % sha, judge)
    judge_path.write_text(judge, encoding="utf-8", newline="\n")
    print("judge.toml source_sha256 =", sha)

    rubric = json.loads(rubric_bytes.decode("utf-8"))
    items = rubric["items"]
    total = round(sum(float(i["weight"]) for i in items), 6)
    if total != 1.0:
        print("FAIL: rubric weights sum to %s" % total)
        return 2
    non_programmatic = [i for i in items if i.get("type") != "programmatic"]
    if non_programmatic:
        print("FAIL: non-programmatic items remain: %s"
              % [i["rubric_id"] for i in non_programmatic])
        return 2

    ids = []
    for item in items:
        for tid in item["test_ids"]:
            if tid in ids:
                print("FAIL: duplicate test id %s" % tid)
                return 2
            ids.append(tid)

    required = []
    for tid in ids:
        if tid.startswith("f2p-"):
            group = "F2P"
        elif tid.startswith("p2p-"):
            group = "P2P"
        else:
            print("FAIL: test id without f2p-/p2p- prefix: %s" % tid)
            return 2
        required.append({"id": tid, "group": group})
    req_path.write_text(json.dumps(required, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
    print("required_testcases.json: %d entries (%d F2P / %d P2P)" % (
        len(required),
        sum(1 for r in required if r["group"] == "F2P"),
        sum(1 for r in required if r["group"] == "P2P")))

    # 3. cross-check against the slug map in run_tests.ps1
    runner = runner_path.read_text(encoding="utf-8", errors="replace")
    block = re.search(r"\$slugByFunction = \[ordered\]@\{(.*?)\n\s*\}", runner, re.S)
    if not block:
        print("FAIL: could not locate $slugByFunction in run_tests.ps1")
        return 2
    slugs = re.findall(r"=\s*'([a-z0-9\-]+)'", block.group(1))
    slugs = sorted(set(slugs))
    expected = sorted(set(tid.split("-", 1)[1] for tid in ids))
    missing_in_map = [s for s in expected if s not in slugs]
    extra_in_map = [s for s in slugs if s not in expected]
    if missing_in_map or extra_in_map:
        print("FAIL: slug map drift")
        print("  missing in run_tests.ps1:", missing_in_map)
        print("  extra in run_tests.ps1  :", extra_in_map)
        return 2
    print("run_tests.ps1 slug map matches the rubric (%d slugs)" % len(slugs))

    # 4. the hidden suite must actually define those functions
    suite = task / "verifier" / "tests"
    if not suite.is_dir():
        print("FAIL: verifier/tests is missing")
        return 2
    py_files = sorted(suite.glob("test_*.py"))
    if len(py_files) != 1:
        print("FAIL: expected exactly one hidden suite, found %s" % [p.name for p in py_files])
        return 2
    text = py_files[0].read_text(encoding="utf-8")
    funcs = set(re.findall(r"^def (test_\w+)", text, re.M))
    want = set()
    for slug in slugs:
        if not any(slug == s for s in expected):
            continue
    # rebuild function name from the map for exactness
    pairs = re.findall(r"'(test_\w+)'\s*=\s*'([a-z0-9\-]+)'", block.group(1))
    want_funcs = {fn for fn, slug in pairs if slug in expected}
    missing_funcs = sorted(want_funcs - funcs)
    if missing_funcs:
        print("FAIL: hidden suite does not define: %s" % missing_funcs)
        return 2
    print("hidden suite defines all %d mapped test functions" % len(want_funcs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
