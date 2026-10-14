param([Parameter(Mandatory=$true)][string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'cleanup.ps1') -WorkspaceRoot $WorkspaceRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $PSScriptRoot 'prepare.ps1') -WorkspaceRoot $WorkspaceRoot
exit $LASTEXITCODE
