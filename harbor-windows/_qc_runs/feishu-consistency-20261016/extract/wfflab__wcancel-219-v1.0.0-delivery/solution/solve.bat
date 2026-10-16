@echo off
rem Golden entry point wrapper for wfflab__wcancel-219. See solve.ps1 for the
rem contract: it installs the injected reference payload over the candidate
rem package (environment/workspace/wcancel) so the Oracle control runs against
rem the same checks the candidate is graded by.
setlocal EnableExtensions

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%~dp0solve.ps1" %*
exit /b %ERRORLEVEL%
