@echo off
setlocal EnableExtensions
rem QC adaptation wrapper -- calls the package's own solve.ps1 unchanged.
if not exist "C:\task\environment\workspace\wfmt\__init__.py" (
  if not exist "C:\task\environment\workspace" mkdir "C:\task\environment\workspace"
  robocopy "C:\testbed" "C:\task\environment\workspace" /E /XD .git __pycache__ .pytest_cache /XF *.pyc /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 exit /b 1
)
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "C:\solution\solve.ps1" -TaskRoot "C:\task"
exit /b %ERRORLEVEL%
