param([Parameter(Mandatory=$true)][string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'
& (Join-Path $WorkspaceRoot 'build.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $WorkspaceRoot 'bin\candidate.exe')
exit $LASTEXITCODE
