@echo off

C:\PowerShell\pwsh.exe -NoLogo -NoProfile -NonInteractive -File "%~dp0test.ps1"

exit /b %ERRORLEVEL%

