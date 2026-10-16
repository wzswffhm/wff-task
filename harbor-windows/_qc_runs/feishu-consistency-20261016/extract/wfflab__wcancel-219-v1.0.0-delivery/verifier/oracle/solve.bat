@echo off
rem Golden control wrapper for wfflab__wcancel-219. See solve.ps1 for the
rem contract: it installs the injected reference payload over the candidate
rem package so the Oracle control runs against the same checks the candidate is
rem graded by.
setlocal EnableExtensions

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%~dp0solve.ps1" %*
exit /b %ERRORLEVEL%
