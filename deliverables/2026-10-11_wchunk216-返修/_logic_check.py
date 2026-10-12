"""Logic pre-check: the relocated hidden suite must still separate the broken
baseline (NOP) from the reference implementation (ORACLE).

Runs the hidden suite with the host interpreter against two staged workspaces:
  nop    = environment/workspace as shipped (defective)
  oracle = the same workspace with the verifier-side reference payload installed
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修")
TASK = ROOT / "build" / "outside_harbor-assets" / "wfflab__wchunk-216"
VER = ROOT / "build" / "outside_harbor-verifier" / "wfflab__wchunk-216"
OUT = ROOT / "evidence" / "logic-check"
HIDDEN = VER / "tests" / "test_wchunk_semantics.py"
REFERENCE = VER / "oracle" / "reference" / "wchunk"

CONFTEST = """import pathlib
import sys

_root = str(pathlib.Path(__file__).resolve().parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
"""


def stage(name: str, oracle: bool) -> Path:
    target = OUT / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(TASK / "environment" / "workspace", target)
    if oracle:
        payload = target / "wchunk"
        shutil.rmtree(payload)
        shutil.copytree(REFERENCE, payload)
    tests = target / "tests"
    tests.mkdir(exist_ok=True)
    shutil.copy2(HIDDEN, tests / "test_wchunk_semantics.py")
    (target / "conftest.py").write_text(CONFTEST, encoding="utf-8")
    return target


def run(name: str, target: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-rA", "--tb=line", "-q",
         str(target / "tests" / "test_wchunk_semantics.py")],
        cwd=str(target), text=True, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    (OUT / f"{name}.pytest.log").write_text(output, encoding="utf-8")
    passed = sorted(set(re.findall(r"PASSED [^:]+::(\w+)", output)))
    failed = sorted(set(re.findall(r"FAILED [^:]+::(\w+)", output)))
    print(f"--- {name}: exit={proc.returncode} passed={len(passed)} failed={len(failed)}")
    for item in failed:
        print(f"    FAIL {item}")
    return {"exit": proc.returncode, "passed": passed, "failed": failed}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nop_target = stage("nop", oracle=False)
    oracle_target = stage("oracle", oracle=True)
    report = {"nop": run("nop", nop_target), "oracle": run("oracle", oracle_target)}

    expected = {
        item["id"].replace("f2p-", "").replace("p2p-", "")
        for item in json.loads((TASK / "tests" / "required_testcases.json").read_text(encoding="utf-8"))
    }
    print()
    print("required checks:", len(expected))
    print("oracle failures :", report["oracle"]["failed"] or "none")
    print("nop failures    :", len(report["nop"]["failed"]))
    verdict = (
        report["oracle"]["exit"] == 0
        and not report["oracle"]["failed"]
        and report["nop"]["exit"] != 0
        and len(report["nop"]["failed"]) > 0
    )
    print("verdict:", "PASS - suite separates baseline from reference" if verdict else "FAIL")
    (OUT / "logic-check.json").write_text(
        json.dumps({"expected_checks": sorted(expected), "report": report, "verdict": verdict},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    raise SystemExit(0 if verdict else 1)


if __name__ == "__main__":
    main()
