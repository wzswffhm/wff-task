@echo off
rem Standard Harbor entry point. Windows containers only discover .bat entry
rem points, so this file delegates to the package's own test entry unchanged.
rem
rem Harbor layout: tests -> C:\tests, workspace -> C:\testbed, logs -> C:\logs.
rem Harbor has no prepare hook, so the fixture is rebuilt here first; the builder
rem lives in tests/prepare.ps1 (the same implementation the local runner reaches
rem through environment/prepare.ps1). The builder is idempotent, so running it on
rem every invocation is safe and keeps the fixture deterministic.
rem
rem NOTE: the task root is the drive root under Harbor and is passed with a
rem forward slash: a trailing backslash would escape the closing quote in
rem PowerShell's -File argument parser, and single quotes are literal there.
setlocal EnableExtensions

set "HERE=%~dp0"

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%HERE%prepare.ps1"
if errorlevel 1 exit /b 2

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%HERE%test.ps1" -TaskRoot "%SystemDrive%/" -WorkspaceRoot "C:\testbed"
exit /b %ERRORLEVEL%
