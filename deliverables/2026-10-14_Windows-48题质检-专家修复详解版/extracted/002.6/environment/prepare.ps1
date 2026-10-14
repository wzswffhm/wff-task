[CmdletBinding()]
param(
    [string]$TaskRoot = (Split-Path -Parent $PSScriptRoot)
)

$resultsRoot = Join-Path $TaskRoot 'results'
$logsRoot = Join-Path $TaskRoot 'logs'
New-Item -ItemType Directory -Force -Path $resultsRoot, $logsRoot | Out-Null

& (Join-Path $PSScriptRoot 'validate_environment.ps1') -TaskRoot $TaskRoot
if ($LASTEXITCODE -ne 0) {
    throw 'Environment validation failed.'
}

Write-Output 'Environment prepared for local Windows pilot.'
