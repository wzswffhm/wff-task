param([Parameter(Mandatory)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $WorkspaceRoot){throw 'WorkspaceRoot must be new'}
$null=New-Item -ItemType Directory -Path $WorkspaceRoot
[IO.File]::WriteAllText((Join-Path $WorkspaceRoot '.outside-harbor-pipe-workspace'),'windows-named-pipe-framing-001')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'workspace/candidate.ps1') -Destination (Join-Path $WorkspaceRoot 'candidate.ps1')
exit 0
