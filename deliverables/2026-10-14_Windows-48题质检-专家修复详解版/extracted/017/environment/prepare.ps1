param([Parameter(Mandatory)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $WorkspaceRoot){throw 'WorkspaceRoot must be a new isolated directory'}
New-Item -ItemType Directory -Path $WorkspaceRoot|Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'workspace/candidate.ps1') -Destination (Join-Path $WorkspaceRoot 'candidate.ps1')
