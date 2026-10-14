param([Parameter(Mandatory=$true)][string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'validate_environment.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (Test-Path -LiteralPath $WorkspaceRoot) { throw 'Prepare requires a fresh workspace path' }
New-Item -ItemType Directory -Path $WorkspaceRoot -Force | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot 'workspace\*') -Destination $WorkspaceRoot -Recurse
exit 0
