@echo off
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
