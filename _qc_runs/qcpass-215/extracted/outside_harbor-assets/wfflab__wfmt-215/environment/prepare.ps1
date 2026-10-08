# Generated for wfflab__wfmt-215 by the task authoring pipeline. Do not edit by hand.
#
# One-time preparation of the graded workspace:
#   1. verify the frozen samples and the candidate package are both present;
#   2. drop interpreter caches so a stale bytecode artefact cannot mask a source
#      change between runs.
#
# The task has no external fixture: everything it needs lives under
# environment/workspace. The script is idempotent and performs no network access.
#
# Exit codes:
#   0  the workspace is prepared
#   1  preparation failed (details on stdout)

[CmdletBinding()]
param(
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

$workspace = Join-Path $TaskRoot 'environment\workspace'
$required = @(
    (Join-Path 'wfmt' '__init__.py'),
    (Join-Path 'assets' 'sample.wfmt'),
    (Join-Path 'assets' 'sample_empty.wfmt'),
    (Join-Path 'tests' 'test_wfmt_basic.py')
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $workspace $relative))) {
        Write-Host "prepare: required workspace item is missing: $relative"
        exit 1
    }
}

foreach ($cache in @(Get-ChildItem -LiteralPath $workspace -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @('__pycache__', '.pytest_cache') })) {
    Remove-Item -LiteralPath $cache.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host 'prepare: workspace ready'
exit 0
