[CmdletBinding()]
param([string]$TaskRoot=(Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$workspace = Join-Path $TaskRoot 'environment\workspace'
if (-not (Test-Path (Join-Path $workspace 'Lib\subprocess.py') -PathType Leaf)) { throw 'workspace source is missing' }
& (Join-Path $PSScriptRoot 'validate_environment.ps1')
$results = Join-Path $TaskRoot 'results'
if (Test-Path -LiteralPath $results) { Remove-Item -LiteralPath $results -Recurse -Force }
New-Item -ItemType Directory -Path $results -Force | Out-Null
