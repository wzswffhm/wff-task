param([string]$Workspace = 'C:\testbed')
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Workspace)) { throw 'Workspace missing' }
& (Join-Path $Workspace 'build.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Workspace build failed' }
