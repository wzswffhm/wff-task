param([Parameter(Mandatory)][string]$WorkspaceRoot)
& (Join-Path $PSScriptRoot 'cleanup.ps1') -WorkspaceRoot $WorkspaceRoot
& (Join-Path $PSScriptRoot 'prepare.ps1') -WorkspaceRoot $WorkspaceRoot
exit $LASTEXITCODE
