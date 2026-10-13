# -*- coding: utf-8 -*-
"""run_suite.py -- 在宿主上直接跑某个题包的真实判分链路。

用法：
    python run_suite.py --task <包目录> [--golden|--empty] [--keep] [--report <json>]

行为：
  * 建临时 runRoot；
  * 把 <包>/environment/workspace 复制到 runRoot（候选工作区）；
  * --golden 时叠加 <包>/solution/reference/<pkg> 的参考实现；
  * --empty 时不叠加（no-change 对照），只清掉包源码留下 __init__；
  * 从 <包>/verifier/tests 复制隐藏套件到 runRoot/tests；
  * 用 pytest 跑，输出逐条结果。

这与 tests/run_tests.ps1 的布局一致（assets 在 runRoot 根，包源码在 runRoot/<pkg>）。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PY = Path(sys.executable)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--golden", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    task = Path(a.task).resolve()
    ws = task / "environment" / "workspace"
    suite_src = task / "verifier" / "tests" / ("test_%s_semantics.py" % a.pkg)
    if not ws.is_dir():
        print("workspace missing: %s" % ws)
        return 2
    if not suite_src.is_file():
        print("hidden suite missing: %s" % suite_src)
        return 2

    run_root = Path(tempfile.mkdtemp(prefix="grade-%s-" % a.pkg))
    for item in ws.iterdir():
        if item.name in ("__pycache__", ".pytest_cache"):
            continue
        if item.is_dir():
            shutil.copytree(item, run_root / item.name)
        else:
            shutil.copy2(item, run_root / item.name)

    if a.golden:
        ref = task / "solution" / "reference" / a.pkg
        if not ref.is_dir():
            print("reference missing: %s" % ref)
            return 2
        for item in ref.iterdir():
            if item.is_dir():
                continue          # never copy __pycache__ or other subdirs
            shutil.copy2(item, run_root / a.pkg / item.name)

    tests = run_root / "tests"
    tests.mkdir(exist_ok=True)
    shutil.copy2(suite_src, tests / suite_src.name)
    # the hidden suite may import verifier-side helpers (e.g. win_services.py);
    # ship every non-test module next to it so the layout matches C:\tests.
    for helper in sorted(suite_src.parent.glob("*.py")):
        if helper.name == suite_src.name:
            continue
        shutil.copy2(helper, tests / helper.name)

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(run_root), env.get("PYTHONPATH", "")])
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    report = Path(a.report) if a.report else (run_root / "pytest-results.json")
    cmd = [str(PY), "-m", "pytest", "-rA", "--tb=short", "-p", "no:cacheprovider",
           "--json-report", "--json-report-file=%s" % report,
           str(tests / suite_src.name)]
    print("run root: %s" % run_root)
    print("golden  : %s" % a.golden)
    proc = subprocess.run(cmd, cwd=str(run_root), env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    tail = proc.stdout.splitlines()
    print("\n".join(tail[-40:]))
    if proc.stderr:
        print("--- stderr ---")
        print(proc.stderr[-3000:])
    if report.is_file():
        doc = json.loads(report.read_text(encoding="utf-8-sig"))
        summary = doc.get("summary", {})
        print("--- summary --- passed=%s failed=%s total=%s" % (
            summary.get("passed"), summary.get("failed"), summary.get("total")))
        per_test = []
        for t in doc.get("tests", []):
            per_test.append({"nodeid": t.get("nodeid"), "outcome": t.get("outcome")})
        if a.report:
            Path(a.report).with_suffix(".summary.json").write_text(
                json.dumps({"summary": summary, "tests": per_test}, ensure_ascii=False, indent=2),
                encoding="utf-8")
    if not a.keep:
        shutil.rmtree(run_root, ignore_errors=True)
    else:
        print("kept:", run_root)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
