param([string]$Workspace = 'C:\testbed', [string]$Logs = 'C:\logs\verifier', [string]$Scratch = 'C:\agenttmp', [switch]$TrustedLocal)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'test.ps1') -Workspace $Workspace -Logs $Logs -Scratch $Scratch -TrustedLocal:$TrustedLocal
exit $LASTEXITCODE
