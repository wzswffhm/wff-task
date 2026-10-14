[CmdletBinding()]
param([string]$TaskRoot='C:\task', [string]$WorkspaceRoot='', [string]$OutputPath='C:\logs\verifier\report.json')
& (Join-Path $PSScriptRoot 'test.ps1') -TaskRoot $TaskRoot -WorkspaceRoot $WorkspaceRoot -OutputPath $OutputPath
exit $LASTEXITCODE
