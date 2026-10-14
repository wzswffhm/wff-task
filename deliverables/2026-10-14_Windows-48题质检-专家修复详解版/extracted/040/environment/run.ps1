[CmdletBinding()]
param([string]$TaskRoot=(Split-Path -Parent $PSScriptRoot), [string]$OutputPath='')
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $TaskRoot 'results\report.json' }
& (Join-Path $PSScriptRoot 'prepare.ps1') -TaskRoot $TaskRoot
& (Join-Path $TaskRoot 'tests\test.ps1') -TaskRoot $TaskRoot -OutputPath $OutputPath
exit $LASTEXITCODE
