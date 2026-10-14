# Generated from tools/build_batch.py. Do not edit this wrapper.
param([Parameter(Mandatory=$true)][string]$WorkspaceRoot,[Parameter(Mandatory=$true)][string]$OutputPath,[string]$Python='python')
& (Join-Path $PSScriptRoot 'run_tests.ps1') -WorkspaceRoot $WorkspaceRoot -OutputPath $OutputPath -Python $Python
exit $LASTEXITCODE
