param([Parameter(Mandatory)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $WorkspaceRoot){throw 'New isolated workspace required'}
$null=New-Item -ItemType Directory -Path $WorkspaceRoot
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'workspace/candidate.ps1') -Destination (Join-Path $WorkspaceRoot 'candidate.ps1')
exit 0
