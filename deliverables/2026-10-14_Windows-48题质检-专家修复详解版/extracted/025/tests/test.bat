@echo off

pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0test.ps1" -WorkspaceRoot C:\workspace -OutputPath C:\logs\verifier\reward.json

exit /b %ERRORLEVEL%

