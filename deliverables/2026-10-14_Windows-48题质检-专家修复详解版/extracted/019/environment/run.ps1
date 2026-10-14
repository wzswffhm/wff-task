param([string]$Workspace = 'C:\testbed', [string]$Plan = '')
$ErrorActionPreference = 'Stop'
& (Join-Path $Workspace 'build.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($Plan) { & (Join-Path $Workspace 'bin\WinPublish.exe') apply $Plan; exit $LASTEXITCODE }
