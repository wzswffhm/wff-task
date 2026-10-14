@echo off
pwsh -NoProfile -File C:\tests\test.ps1
exit /b %ERRORLEVEL%
