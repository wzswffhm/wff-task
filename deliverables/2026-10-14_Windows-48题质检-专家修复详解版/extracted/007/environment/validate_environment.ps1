param([string]$Workspace = 'C:\testbed')
$ErrorActionPreference = 'Stop'
$required = @('build.ps1', 'src')
foreach ($item in $required) { if (-not (Test-Path (Join-Path $Workspace $item))) { throw "Missing $item" } }
