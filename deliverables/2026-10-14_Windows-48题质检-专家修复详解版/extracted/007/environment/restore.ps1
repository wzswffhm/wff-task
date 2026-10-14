param([string]$Workspace = 'C:\testbed')
$ErrorActionPreference = 'Stop'
if (Test-Path (Join-Path $Workspace 'bin')) { Remove-Item (Join-Path $Workspace 'bin') -Recurse -Force }
& (Join-Path $Workspace 'build.ps1')
