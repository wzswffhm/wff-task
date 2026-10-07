# Generated for wfflab__wreparse-217 by the task authoring pipeline.
# Do not edit by hand: change tests/run_tests.ps1, tests/aggregate_results.ps1
# or tests/rubric.json instead.
#
# Stable entry point used by the evaluation platform. It runs the behavioural
# checks and then the rubric aggregation, returning the real test exit code.

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$OutputPath = '',
    [string]$WorkspaceRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { $WorkspaceRoot = Join-Path $TaskRoot 'environment\workspace' }
if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $TaskRoot 'results\result.json' }

$resultsDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $resultsDirectory)) { New-Item -ItemType Directory -Path $resultsDirectory -Force | Out-Null }
$checksPath = Join-Path $resultsDirectory 'checks.json'

& (Join-Path $PSScriptRoot 'run_tests.ps1') -WorkspaceRoot $WorkspaceRoot -ChecksPath $checksPath -TaskRoot $TaskRoot
$checksExit = $LASTEXITCODE
if ($checksExit -eq 2) { exit 2 }

& (Join-Path $PSScriptRoot 'aggregate_results.ps1') -ChecksPath $checksPath `
    -RubricPath (Join-Path $PSScriptRoot 'rubric.json') -OutputPath $OutputPath -TaskRoot $TaskRoot
exit $LASTEXITCODE
