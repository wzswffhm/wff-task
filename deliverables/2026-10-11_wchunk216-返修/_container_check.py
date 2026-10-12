"""Dynamic container check with the freshly built image.

Two runs, each in a throwaway container:

  nop    : C:\\testbed as baked (defective)          -> expect run_tests exit 1
  oracle : reference payload installed, then graded  -> expect run_tests exit 0

The verifier-side tree is bind-mounted at C:\\verifier\\wfflab__wchunk-216, which is
exactly where the grading side injects it, so this also exercises the injection
contract end to end.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修")
TASK = ROOT / "build" / "outside_harbor-assets" / "wfflab__wchunk-216"
VER = ROOT / "build" / "outside_harbor-verifier" / "wfflab__wchunk-216"
OUT = ROOT / "evidence" / "container-check"
IMAGE = "outside-harbor/wfflab__wchunk-216:1.2.0"

GRADE = r"""
& C:\task\tests\run_tests.ps1 -TaskRoot C:\task -WorkspaceRoot C:\testbed `
    -ChecksPath C:\out\checks-{name}.json `
    -VerifierRoot C:\verifier\wfflab__wchunk-216
Write-Output ('RUN_TESTS_EXIT=' + $LASTEXITCODE)
& C:\task\tests\aggregate_results.ps1 -ChecksPath C:\out\checks-{name}.json `
    -RubricPath C:\task\tests\rubric.json `
    -OutputPath C:\out\result-{name}.json -TaskRoot C:\task
Write-Output ('AGGREGATE_EXIT=' + $LASTEXITCODE)
Get-Content C:\out\result-{name}.json -Raw
"""

ORACLE_SOLVE = r"""
& C:\verifier\wfflab__wchunk-216\oracle\solve.ps1 -WorkspaceRoot C:\testbed `
    -ReferenceRoot C:\verifier\wfflab__wchunk-216\oracle\reference\wchunk
Write-Output ('SOLVE_EXIT=' + $LASTEXITCODE)
"""


def docker_run(name: str, script: str) -> str:
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{TASK}:C:\\task",
        "-v", f"{VER}:C:\\verifier\\wfflab__wchunk-216",
        "-v", f"{OUT}:C:\\out",
        IMAGE,
        "powershell", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-Command", script,
    ]
    print(f"--- {name}: docker run", flush=True)
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=3600)
    output = (proc.stdout or "") + (proc.stderr or "")
    (OUT / f"{name}.log").write_text(output, encoding="utf-8")
    print(f"--- {name}: docker exit={proc.returncode}")
    return output


def parse(name: str, output: str) -> dict:
    result = {}
    for line in output.splitlines():
        for key, field in (("RUN_TESTS_EXIT=", "run_tests_exit"),
                           ("AGGREGATE_EXIT=", "aggregate_exit"),
                           ("SOLVE_EXIT=", "solve_exit")):
            if line.startswith(key):
                raw = line.split("=", 1)[1].strip()
                if raw.lstrip("-").isdigit():
                    result[field] = int(raw)
    # Read the aggregate report from the mounted output directory: it is the file
    # the reviewer consumes, and it survives any stdout reshaping.
    report = OUT / f"result-{name}.json"
    doc = None
    if report.exists():
        try:
            doc = json.loads(report.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            doc = None
        if not isinstance(doc, dict):
            doc = None
    if doc is None:
        start = output.find('{\n  "schema_version"')
        if start >= 0:
            try:
                doc = json.loads(output[start:output.rfind("}") + 1])
            except json.JSONDecodeError:
                doc = None
    if isinstance(doc, dict):
        for key in ("run_validity", "formal_score", "passed", "failed", "invalid",
                    "rubric_split", "verdict", "reason"):
            result[key] = doc.get(key)
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nop = parse("nop", docker_run("nop", GRADE.format(name="nop")))
    oracle_out = docker_run("oracle", ORACLE_SOLVE + GRADE.format(name="oracle"))
    oracle = parse("oracle", oracle_out)

    print()
    print("nop    :", json.dumps(nop, ensure_ascii=False))
    print("oracle :", json.dumps(oracle, ensure_ascii=False))

    verdict = (
        nop.get("run_tests_exit") == 1
        and nop.get("run_validity") == "VALID"
        and nop.get("formal_score") == 0
        and oracle.get("solve_exit") == 0
        and oracle.get("run_tests_exit") == 0
        and oracle.get("run_validity") == "VALID"
        and oracle.get("formal_score") == 1
    )
    print("verdict:", "PASS - VALID/0 baseline, VALID/1 oracle" if verdict else "FAIL")
    (OUT / "container-check.json").write_text(
        json.dumps({"nop": nop, "oracle": oracle, "verdict": verdict},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
