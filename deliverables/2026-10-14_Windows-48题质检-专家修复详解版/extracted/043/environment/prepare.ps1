param([string]$WorkspaceRoot)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $WorkspaceRoot){throw 'Require fresh workspace'}
New-Item -ItemType Directory -Path $WorkspaceRoot|Out-Null
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'workspace') -File|Copy-Item -Destination $WorkspaceRoot
