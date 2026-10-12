"""QC-only adaptation: add the Windows entrypoints harbor discovers.

harbor resolves Windows tasks to solution/solve.bat and tests/test.bat
(harbor.utils.scripts.WINDOWS_EXTENSIONS == ['.bat']); the delivered packages ship
.solve.ps1 / test.ps1 only, so Task.is_valid_dir() rejects them and the CLI sees
zero tasks.

The wrappers below do NOT change any grading logic. They only rebuild the
C:\\task\\... layout the package scripts document in environment/adapter.toml
(task_root=C:\\task, workspace_root=C:\\task\\environment\\workspace) from
harbor's own layout (workdir C:\\testbed, C:\\solution, C:\\tests) and then call
the package's original .ps1 entry unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SOLVE_BAT = r"""@echo off
setlocal EnableExtensions
rem QC adaptation wrapper -- calls the package's own solve.ps1 unchanged.
if not exist "C:\task\environment\workspace\{payload}\{marker}" (
  if not exist "C:\task\environment\workspace" mkdir "C:\task\environment\workspace"
  robocopy "C:\testbed" "C:\task\environment\workspace" /E /XD .git __pycache__ .pytest_cache /XF *.pyc /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 exit /b 1
)
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "C:\solution\solve.ps1" -TaskRoot "C:\task"
exit /b %ERRORLEVEL%
"""

TEST_BAT_GENERIC = r"""@echo off
setlocal EnableExtensions
rem QC adaptation wrapper -- calls the package's own test.ps1 unchanged.
echo [qc] source tests dir %~dp0
dir /b "%~dp0"
if not exist "C:\task\tests" (
  mkdir "C:\task\tests"
  robocopy "%~dp0." "C:\task\tests" /E /NFL /NDL /NJH /NJS /NP
)
echo [qc] staged tests dir C:\task\tests
dir /b /s "C:\task\tests"
if not exist "C:\task\environment\workspace\{payload}\{marker}" (
  if not exist "C:\task\environment\workspace" mkdir "C:\task\environment\workspace"
  robocopy "C:\testbed" "C:\task\environment\workspace" /E /XD .git __pycache__ .pytest_cache /XF *.pyc /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 exit /b 1
)
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "C:\tests\test.ps1" -TaskRoot "C:\task" -WorkspaceRoot "C:\task\environment\workspace"
exit /b %ERRORLEVEL%
"""

# 217's run_tests.ps1 refuses to score unless environment/prepare.ps1 has built
# the reparse-point fixture outside the task tree. harbor has no prepare hook, so
# the QC wrapper runs the package's own prepare.ps1 first (copied into tests/).
TEST_BAT_217 = r"""@echo off
setlocal EnableExtensions
rem QC adaptation wrapper -- calls the package's own prepare.ps1 then test.ps1.
if not exist "C:\task\tests" (
  mkdir "C:\task\tests"
  robocopy "%~dp0." "C:\task\tests" /E /NFL /NDL /NJH /NJS /NP >nul
)
if not exist "C:\task\environment\workspace\WReparse\WReparse.psd1" (
  if not exist "C:\task\environment\workspace" mkdir "C:\task\environment\workspace"
  robocopy "C:\testbed" "C:\task\environment\workspace" /E /XD .git __pycache__ /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 exit /b 1
)
if not exist "C:\wreparse-fixture\fixture.json" (
  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "C:\tests\prepare.ps1" -TaskRoot "C:\task" 2>&1
  if errorlevel 1 exit /b 2
)
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "C:\tests\test.ps1" -TaskRoot "C:\task" -WorkspaceRoot "C:\task\environment\workspace" 2>&1
echo [qc] test.ps1 exit=%ERRORLEVEL%
exit /b %ERRORLEVEL%
"""

SPEC = {
    "wfflab__wfmt-215": {"payload": "wfmt", "marker": "__init__.py", "prepare": False},
    "wfflab__wreparse-217": {"payload": "WReparse", "marker": "WReparse.psd1", "prepare": True},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True, help="original task root")
    args = parser.parse_args()

    record: list[dict] = []
    for task_id, spec in SPEC.items():
        stage = args.staged / task_id
        if not stage.is_dir():
            continue
        notes: list[str] = []
        solve = stage / "solution" / "solve.bat"
        solve.write_text(SOLVE_BAT.format(payload=spec["payload"], marker=spec["marker"]), encoding="ascii", newline="")
        notes.append("solution/solve.bat (wrapper -> solve.ps1, rebuilds C:\\task layout)")
        test = stage / "tests" / "test.bat"
        if spec["prepare"]:
            test.write_text(TEST_BAT_217, encoding="ascii", newline="")
            notes.append("tests/test.bat (wrapper -> prepare.ps1 + test.ps1)")
            src = args.source / task_id / "environment" / "prepare.ps1"
            dst = stage / "tests" / "prepare.ps1"
            dst.write_bytes(src.read_bytes())
            notes.append("tests/prepare.ps1 (copy of environment/prepare.ps1; harbor has no prepare hook)")
        else:
            test.write_text(
                TEST_BAT_GENERIC.format(payload=spec["payload"], marker=spec["marker"]),
                encoding="ascii", newline="")
            notes.append("tests/test.bat (wrapper -> test.ps1, rebuilds C:\\task layout)")
        record.append({"task_id": task_id, "adaptations": notes})

    print(json.dumps(record, ensure_ascii=False, indent=2))
    (args.staged / "entrypoint_adaptations.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
