@echo off
rem Standard Harbor entry point. Windows containers only discover .bat entry
rem points, so this file delegates to the package's own solve.ps1 unchanged.
rem The candidate workspace is baked into the image by environment/Dockerfile at
rem C:\testbed, which is also [environment].workdir in task.toml.
setlocal EnableExtensions
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%~dp0solve.ps1" -WorkspaceRoot "C:\testbed"
exit /b %ERRORLEVEL%
