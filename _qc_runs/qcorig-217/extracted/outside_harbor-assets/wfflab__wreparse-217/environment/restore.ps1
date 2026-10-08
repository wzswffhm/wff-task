# Generated for wfflab__wreparse-217. Do not edit by hand.
#
# Restores the frozen baseline so the next run starts from a known state:
#   1. rebuild the fixture tree through prepare.ps1;
#   2. when -BaselinePath is given, mirror its WReparse payload back over the
#      working copy (used to undo a candidate or golden patch between runs);
#   3. drop the previous results unless -KeepResults is set.
#
# The script is idempotent: running it twice leaves the same state.
#
# Exit codes:
#   0  baseline restored
#   1  the baseline could not be restored (details on stdout)

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$BaselinePath = '',
    [switch]$KeepResults
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

$prepareScript = Join-Path $TaskRoot 'environment\prepare.ps1'
if (-not (Test-Path -LiteralPath $prepareScript)) { throw "prepare.ps1 not found: $prepareScript" }

& $prepareScript -TaskRoot $TaskRoot
if ($LASTEXITCODE -ne 0) { exit 1 }

if (-not [string]::IsNullOrWhiteSpace($BaselinePath)) {
    $baseline = (Resolve-Path -LiteralPath $BaselinePath).Path
    $sourcePayload = Join-Path $baseline 'WReparse'
    if (-not (Test-Path -LiteralPath $sourcePayload)) {
        Write-Host "restore: baseline payload not found at $sourcePayload"
        exit 1
    }
    $targetPayload = Join-Path $TaskRoot 'environment\workspace\WReparse'
    & robocopy $sourcePayload $targetPayload /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    # robocopy reports success through codes 0..7; 8 and above are real failures.
    if ($LASTEXITCODE -ge 8) { exit 1 }
    Write-Host "restore: workspace payload mirrored from $sourcePayload"
}

if (-not $KeepResults) {
    $resultsRoot = Join-Path $TaskRoot 'results'
    if (Test-Path -LiteralPath $resultsRoot) {
        Remove-Item -LiteralPath $resultsRoot -Recurse -Force
        Write-Host 'restore: previous results removed'
    }
}

Write-Host 'restore: baseline ready'
exit 0
