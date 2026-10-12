@echo off
rem Generated for wfflab__wlogseg-218 by the task authoring pipeline.
rem Standard Harbor .bat entry point: delegates to solve.ps1 next to this file.
setlocal
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%~dp0solve.ps1" %*
exit /b %ERRORLEVEL%
