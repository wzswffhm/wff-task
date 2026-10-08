@echo off
rem Standard Harbor entry point. Windows containers only discover .bat entry
rem points, so this file delegates to the package's own test.ps1 unchanged.
rem
rem Harbor layout: tests -> C:\tests, workspace -> C:\testbed, logs -> C:\logs.
rem This task has no fixture stage, so the checks run directly.
rem
rem NOTE: the task root is the drive root under Harbor and is passed with a
rem forward slash: a trailing backslash would escape the closing quote in
rem PowerShell's -File argument parser, and single quotes are literal there.
setlocal EnableExtensions
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -NonInteractive -File "%~dp0test.ps1" -TaskRoot "%SystemDrive%/" -WorkspaceRoot "C:\testbed"
exit /b %ERRORLEVEL%
