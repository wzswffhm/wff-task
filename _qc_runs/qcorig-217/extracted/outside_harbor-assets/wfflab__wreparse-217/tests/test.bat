@echo off
rem Standard Harbor entry point. Windows containers only discover .bat entry
rem points, so this file delegates to the package's own test.ps1 unchanged.
rem
rem Harbor layout: tests -> C:\tests, workspace -> C:\testbed, logs -> C:\logs.
rem Harbor has no prepare hook, so the NTFS fixture is built here first; the
rem builder lives in tests/prepare.ps1 (the same implementation the local runner
rem calls through environment/prepare.ps1).
rem
rem NOTE: the task root is the drive root under Harbor and is passed with a
rem forward slash: a trailing backslash would escape the closing quote in
rem PowerShell's -File argument parser, and single quotes are literal there.
setlocal EnableExtensions

if not exist "%SystemDrive%\wreparse-fixture\fixture.json" (
  powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%~dp0prepare.ps1"
  if errorlevel 1 exit /b 2
)

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%~dp0test.ps1" -TaskRoot "%SystemDrive%/" -WorkspaceRoot "C:\testbed"
exit /b %ERRORLEVEL%
