# Generated for wfflab__wreparse-217. Do not hand-edit.
#
# The fixture builder itself lives with the evaluation assets in
# tests/prepare.ps1, so both consumers reach the same implementation:
#   * the local Outside Harbor runner invokes this path (C:\task\environment\prepare.ps1);
#   * standard Harbor uploads tests/ to C:\tests and has no prepare hook, so its
#     test entry point (tests/test.bat) calls tests/prepare.ps1 directly.
#
# Exit codes:
#   0  fixture ready
#   2  the builder could not be reached

[CmdletBinding()]
param(
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

$builder = Join-Path (Split-Path -Parent $PSScriptRoot) 'tests\prepare.ps1'
if (-not (Test-Path -LiteralPath $builder)) {
    Write-Host "prepare: fixture builder not found at $builder"
    exit 2
}

& $builder -TaskRoot $TaskRoot
exit $LASTEXITCODE
