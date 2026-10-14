param([string]$Workspace = 'C:\testbed')
$ErrorActionPreference = 'Stop'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $csc)) { throw 'NET Framework 4.x C# compiler is required' }
if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'build.ps1'))) { throw 'workspace build entry is missing' }
if (-not (Test-Path -LiteralPath (Join-Path $Workspace 'src'))) { throw 'workspace src is missing' }
Write-Output 'environment-valid'
