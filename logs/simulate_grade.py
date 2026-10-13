# -*- coding: utf-8 -*-
"""simulate_grade.py -- 在跑分前模拟容器内的判分链。

它复现 tests/run_tests.ps1 的关键步骤，但不启动容器：
  1. 用候选工作区（或参考实现）铺一个 scratch runRoot；
  2. 按 run_tests.ps1 的现在逻辑把**隐藏套件及其同目录 helper** 复制进
     runRoot/tests（这一步正是容器内 ModuleNotFoundError 的来源）；
  3. 写 conftest.py；
  4. 以 runRoot/tests 为参数跑 pytest，报告通过/失败。

用途：把「只在容器里才会暴露的判分链问题」（helper 没被投放、cwd/sys.path
差异、__pycache__ 污染）提前到跑分之前发现。

用法：
    python simulate_grade.py --task 219                # 用参考实现（等价 oracle）
    python simulate_grade.py --task 219 --candidate    # 用 environment/workspace（等价 no-change）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
REL = ROOT / "harbor-windows" / "_qc_runs" / "relaunch-20261013"

TASKS = {
    "218": {"pkg": "wfflab__wlogseg-218-v1.1.0-delivery", "pkgname": "wlogseg",
            "suite": "test_wlogseg_semantics.py", "required": 26},
    "219": {"pkg": "wfflab__wpeimg-219-v1.4.0-delivery", "pkgname": "wpeimg",
            "suite": "test_wpeimg_semantics.py", "required": 43},
}

CONFTEST = """import pathlib
import sys

_root = str(pathlib.Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    ap.add_argument("--candidate", action="store_true",
                    help="use environment/workspace instead of the reference (no-change)")
    a = ap.parse_args()
    cfg = TASKS[a.task]
    pkg = REL / "staged" / cfg["pkg"]

    hidden_dir = pkg / "verifier" / "tests"
    hidden_suite = hidden_dir / cfg["suite"]
    delivered_dir = pkg / "tests"
    delivered_suite = delivered_dir / cfg["suite"]
    if not hidden_suite.is_file() or not delivered_suite.is_file():
        raise SystemExit("suite missing: %s / %s" % (hidden_suite, delivered_suite))

    # the delivered copy must be byte-identical to the hidden one
    if hidden_suite.read_bytes() != delivered_suite.read_bytes():
        print("FAIL: delivered suite != hidden suite (sha256 differs)")
        return 1

    run_root = Path(tempfile.mkdtemp(prefix="wpeimg-simgrade-"))
    problems: list[str] = []
    try:
        # 1) lay down the candidate workspace (run_tests.ps1 robocopies it)
        shutil.copytree(pkg / "environment" / "workspace", run_root, dirs_exist_ok=True)
        for junk in run_root.rglob("__pycache__"):
            shutil.rmtree(junk, ignore_errors=True)

        # 2) overlay the reference implementation when simulating oracle
        if not a.candidate:
            ref = pkg / "solution" / "reference" / cfg["pkgname"]
            for item in ref.glob("*.py"):
                shutil.copy2(item, run_root / cfg["pkgname"] / item.name)

        # 3) replicate the *current* run_tests.ps1 staging logic
        tests_dir = run_root / "tests"
        tests_dir.mkdir(exist_ok=True)
        shutil.copy2(hidden_suite, tests_dir / cfg["suite"])
        staged_helpers = []
        for helper in sorted(hidden_dir.glob("*.py")):
            if helper.name == cfg["suite"]:
                continue
            shutil.copy2(helper, tests_dir / helper.name)
            staged_helpers.append(helper.name)
        (run_root / "conftest.py").write_text(CONFTEST, encoding="utf-8")

        print("scratch root : %s" % run_root)
        print("staged tests : %s" % sorted(p.name for p in tests_dir.glob('*.py')))
        print("helpers      : %s" % (staged_helpers or "(none)"))

        # 4) helpers referenced by the suite must actually be staged
        suite_text = hidden_suite.read_text(encoding="utf-8")
        for helper in staged_helpers:
            stem = helper[:-3]
            if ("import %s" % stem) in suite_text and helper not in [
                    p.name for p in tests_dir.glob("*.py")]:
                problems.append("suite imports %s but it was not staged" % stem)

        # 5) run pytest exactly as the container does (cwd elsewhere, no PYTHONPATH
        #    pointing at tests/)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(run_root)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               str(tests_dir / cfg["suite"])]
        proc = subprocess.run(cmd, cwd=str(run_root), env=env,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        tail = (proc.stdout or "").strip().splitlines()
        print("\n--- pytest tail ---")
        for line in tail[-6:]:
            print("  %s" % line)

        passed = sum(1 for l in tail if l.startswith(("PASSED", ".")) )
        summary = tail[-1] if tail else ""
        import re
        m = re.search(r"(\d+) passed", summary)
        n_passed = int(m.group(1)) if m else 0
        m2 = re.search(r"(\d+) failed", summary)
        n_failed = int(m2.group(1)) if m2 else 0

        print()
        if a.candidate:
            print("no-change 模拟：passed=%d failed=%d（期望大量失败）" % (n_passed, n_failed))
        else:
            print("oracle 模拟：passed=%d failed=%d（期望 %d 全过）"
                  % (n_passed, n_failed, cfg["required"]))
            if n_failed or n_passed != cfg["required"]:
                problems.append("reference implementation does not reach %d/%d in the "
                                "simulated grading chain" % (n_passed, cfg["required"]))
        if "ModuleNotFoundError" in (proc.stdout or ""):
            problems.append("the simulated grading chain hit ModuleNotFoundError")
    finally:
        shutil.rmtree(run_root, ignore_errors=True)

    print()
    if problems:
        print("判分链模拟 FAILED：")
        for p in problems:
            print("  - %s" % p)
        return 1
    print("判分链模拟 PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
