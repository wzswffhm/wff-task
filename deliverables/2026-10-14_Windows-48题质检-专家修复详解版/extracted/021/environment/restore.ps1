param([Parameter(Mandatory)][string]$WorkspaceRoot)
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'workspace/candidate.ps1') -Destination (Join-Path $WorkspaceRoot 'candidate.ps1') -Force
exit 0
