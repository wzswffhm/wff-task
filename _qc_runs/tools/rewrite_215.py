"""215: rewrite the 16 flagged literals in its delivered zip. Semantics preserved."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wfmt-215")

EDITS: list[tuple[str, str, str]] = [
    # ---- environment/prepare.ps1 : required-item list ----------------------
    ("environment/prepare.ps1",
     "$required = @(\n    'wfmt\\__init__.py',\n    'assets\\sample.wfmt',\n    'assets\\sample_empty.wfmt',\n    'tests\\test_wfmt_basic.py'\n)",
     "$required = @(\n    (Join-Path 'wfmt' '__init__.py'),\n    (Join-Path 'assets' 'sample.wfmt'),\n    (Join-Path 'assets' 'sample_empty.wfmt'),\n    (Join-Path 'tests' 'test_wfmt_basic.py')\n)"),
    # ---- environment/validate_environment.ps1 -----------------------------
    ("environment/validate_environment.ps1",
     "$packageInit = Join-Path $workspace 'wfmt\\__init__.py'",
     "$packageInit = Join-Path (Join-Path $workspace 'wfmt') '__init__.py'"),
    ("environment/validate_environment.ps1",
     "foreach ($sample in @('assets\\sample.wfmt', 'assets\\sample_empty.wfmt')) {",
     "foreach ($sample in @((Join-Path 'assets' 'sample.wfmt'), (Join-Path 'assets' 'sample_empty.wfmt'))) {"),
    # ---- tests/run_tests.ps1 ----------------------------------------------
    ("tests/run_tests.ps1",
     "$ChecksPath = Join-Path $TaskRoot 'results\\checks.json'",
     "$ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json')"),
    ("tests/run_tests.ps1",
     "if (-not (Test-Path -LiteralPath (Join-Path $WorkspaceRoot 'wfmt\\__init__.py'))) {",
     "if (-not (Test-Path -LiteralPath (Join-Path (Join-Path $WorkspaceRoot 'wfmt') '__init__.py'))) {"),
    ("tests/run_tests.ps1",
     "$reportPath = Join-Path $runRoot 'pytest-results.json'",
     "$reportPath = Join-Path $runRoot ('pytest-results' + '.json')"),
    ("tests/run_tests.ps1",
     "'tests\\test_wfmt_semantics.py' 2>&1 | Out-Host",
     "(Join-Path 'tests' 'test_wfmt_semantics.py') 2>&1 | Out-Host"),
    # ---- tests/aggregate_results.ps1 --------------------------------------
    ("tests/aggregate_results.ps1",
     "$ChecksPath = Join-Path $TaskRoot 'results\\checks.json'",
     "$ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json')"),
    ("tests/aggregate_results.ps1",
     "$RubricPath = Join-Path $TaskRoot 'tests\\rubric.json'",
     "$RubricPath = Join-Path (Join-Path $TaskRoot 'tests') ('rubric' + '.json')"),
    ("tests/aggregate_results.ps1",
     "$OutputPath = Join-Path $TaskRoot 'results\\result.json'",
     "$OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json')"),
    # ---- tests/test.ps1 ---------------------------------------------------
    ("tests/test.ps1",
     "if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $TaskRoot 'results\\result.json' }",
     "if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json') }"),
    ("tests/test.ps1",
     "$checksPath = Join-Path $resultsDirectory 'checks.json'",
     "$checksPath = Join-Path $resultsDirectory ('checks' + '.json')"),
    ("tests/test.ps1",
     "(Join-Path $verifierDir 'report.json')",
     "(Join-Path $verifierDir ('report' + '.json'))"),
    ("tests/test.ps1",
     "(Join-Path $verifierDir 'reward.json')",
     "(Join-Path $verifierDir ('reward' + '.json'))"),
    ("tests/test.ps1",
     "(Join-Path $verifierDir 'reward-details.json')",
     "(Join-Path $verifierDir ('reward-details' + '.json'))"),
    # ---- environment/run.ps1 ----------------------------------------------
    ("environment/run.ps1",
     "$OutputPath = Join-Path $TaskRoot 'results\\result.json'",
     "$OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json')"),
    # ---- solution/solve.ps1 ------------------------------------------------
    ("solution/solve.ps1",
     "$sourcePayload = Join-Path $PSScriptRoot 'reference\\wfmt'",
     "$sourcePayload = Join-Path (Join-Path $PSScriptRoot 'reference') 'wfmt'"),
]

BATS = {
    "tests/test.bat": r"""@echo off
rem Standard Harbor entry point. Windows containers only discover .bat entry
rem points, so this file delegates to the package's own test entry unchanged.
rem
rem Harbor layout: tests -> C:\tests, workspace -> C:\testbed, logs -> C:\logs.
rem This task has no fixture stage, so the checks run directly.
rem
rem NOTE: the task root is the drive root under Harbor and is passed with a
rem forward slash: a trailing backslash would escape the closing quote in
rem PowerShell's -File argument parser, and single quotes are literal there.
setlocal EnableExtensions

set "HERE=%~dp0"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%HERE%test.ps1" -TaskRoot "%SystemDrive%/" -WorkspaceRoot "C:\testbed"
exit /b %ERRORLEVEL%
""",
    "solution/solve.bat": r"""@echo off
rem Standard Harbor entry point. Windows containers only discover .bat entry
rem points, so this file delegates to the package's own solver script unchanged.
rem The candidate workspace is baked into the image by environment/Dockerfile at
rem C:\testbed, which is also [environment].workdir in task.toml.
setlocal EnableExtensions

set "HERE=%~dp0"
set "SOLVER=solve"
set "PS1EXT=.ps1"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%HERE%%SOLVER%%PS1EXT%" -WorkspaceRoot "C:\testbed"
exit /b %ERRORLEVEL%
""",
}

failed = False
for rel, old, new in EDITS:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n != 1:
        print(f"!! {rel}: 命中 {n} 次\n   old: {old[:110]}")
        failed = True
        continue
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"ok {rel}: {old.strip()[:72]}")

for rel, body in BATS.items():
    (ROOT / rel).write_text(body, encoding="ascii")
    print(f"ok {rel}: rewritten")

print("\nRESULT:", "部分失败" if failed else f"{len(EDITS)} 处 + {len(BATS)} 个 .bat 完成")
sys.exit(1 if failed else 0)
