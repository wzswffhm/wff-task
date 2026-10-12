@echo off
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
if not exist "C:\task\environment\workspace\wfmt\__init__.py" (
  if not exist "C:\task\environment\workspace" mkdir "C:\task\environment\workspace"
  robocopy "C:\testbed" "C:\task\environment\workspace" /E /XD .git __pycache__ .pytest_cache /XF *.pyc /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 exit /b 1
)
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "C:\tests\test.ps1" -TaskRoot "C:\task" -WorkspaceRoot "C:\task\environment\workspace"
exit /b %ERRORLEVEL%
