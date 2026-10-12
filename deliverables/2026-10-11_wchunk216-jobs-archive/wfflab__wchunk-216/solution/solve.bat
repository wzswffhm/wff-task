@echo off
rem Standard Harbor entry point. Windows containers only discover .bat entry
rem points, so this file delegates to the package's own solver script unchanged.
rem The candidate workspace is baked into the image by environment/Dockerfile at
rem C:\testbed, which is also [environment].workdir in task.toml.
setlocal EnableExtensions

set "HERE=%~dp0"
set "SOLVER=solve"
set "PS1EXT=.ps1"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%HERE%%SOLVER%%PS1EXT%" -WorkspaceRoot "C:\testbed"
exit /b %ERRORLEVEL%
