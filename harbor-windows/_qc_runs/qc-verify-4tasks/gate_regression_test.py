# -*- coding: utf-8 -*-
"""规则 3 回归测试：Qwen/Opus 总分平局（都满分）时按逐 testcase 通过数判定。

期望：
  1. 都满分 + Opus 逐 case 更多  -> PASS（Qwen 通过更少视为有区分）
  2. 都满分 + 逐 case 完全相同  -> FAIL（无区分力，对应 219 实测 129 vs 129）
  3. 全模型零分                -> PASS（零分平局例外）
  4. 只提供 qwen/opus（无 GLM/Kimi） -> PASS（不再要求 GLM/Kimi）
  5. 额外提供 GLM/Kimi          -> PASS（被忽略，不影响判定）
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
SCRIPTS = ROOT / "harbor-windows" / "_reference" / "windows-harbor-qc" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import validate_model_gate as gate  # noqa: E402

IDENT = {"task_id": "wfflab__demo", "task_version": "1.0.0", "task_hash": "deadbeef" * 8}


def run(rid: str, score: int, pass_cases: int, total: int = 3) -> dict:
    return {
        "run_id": rid, "validity": "VALID", "score": score,
        **IDENT,
        "cases": [
            {"id": "c%d" % i, "status": "PASS" if i < pass_cases else "FAIL"}
            for i in range(total)
        ],
    }


def evidence(qwen_passes, opus_passes, qwen_score=1, opus_score=1, extra=None):
    value = {
        "task": dict(IDENT),
        "models": {
            "qwen": [run("q%d" % i, qwen_score, qwen_passes) for i in (1, 2, 3)],
            "opus": [run("o%d" % i, opus_score, opus_passes) for i in (1, 2, 3)],
        },
    }
    if extra:
        value["models"].update(copy.deepcopy(extra))
    return value


CASES = [
    ("1 都满分 + Opus 逐 case 更多（Qwen 少）", evidence(2, 3), True),
    ("2 都满分 + 逐 case 完全相同（219 实况）", evidence(3, 3), False),
    ("3 全模型零分平局", evidence(0, 0, qwen_score=0, opus_score=0), True),
    ("4 只给 qwen/opus（无 GLM/Kimi）", evidence(2, 3), True),
    ("5 额外带 GLM/Kimi 轮次", evidence(2, 3, extra={
        "glm": [run("g1", 0, 1)],
        "kimi": [run("k1", 0, 1)],
    }), True),
]

fails = 0
for name, value, expect_pass in CASES:
    res = gate.evaluate(value)
    ok = res["pass"] is expect_pass
    if not ok:
        fails += 1
    print("[%s] %s  期望 pass=%s 实际 pass=%s" %
          ("OK " if ok else "BAD", name, expect_pass, res["pass"]))
    d = res["stats"].get("distinction", {})
    print("      qwen_score_sum=%s opus_score_sum=%s qwen_case_sum=%s opus_case_sum=%s"
          % (res["stats"]["qwen"]["model_score_sum"], res["stats"]["opus"]["model_score_sum"],
             res["stats"]["qwen"]["testcase_pass_sum"], res["stats"]["opus"]["testcase_pass_sum"]))
    print("      tiebreak_pass=%s full_score_tiebreak_pass=%s"
          % (d.get("testcase_tiebreak_pass"), d.get("full_score_tiebreak_pass")))
    for e in res["errors"]:
        print("      ERROR %s" % e)
    print()

print("结论：%d 个用例，%d 个不符合预期" % (len(CASES), fails))
sys.exit(1 if fails else 0)
