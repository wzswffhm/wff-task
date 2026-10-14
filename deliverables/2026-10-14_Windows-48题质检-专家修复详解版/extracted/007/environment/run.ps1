param([string]$Workspace = 'C:\testbed')
$ErrorActionPreference = 'Stop'
& (Join-Path $Workspace 'build.ps1')
exit $LASTEXITCODE
