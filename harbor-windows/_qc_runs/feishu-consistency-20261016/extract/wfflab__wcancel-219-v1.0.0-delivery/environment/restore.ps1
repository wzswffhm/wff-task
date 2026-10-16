# Restores the candidate workspace to a pristine checkout.
#
# NOTE: keep this file pure ASCII (Windows PowerShell 5.1 reads BOM-less files
# as ANSI).

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

$prepare = Join-Path $TaskRoot 'environment\prepare.ps1'
if (-not (Test-Path -LiteralPath $prepare)) {
    throw "restore: prepare entry point not found at $prepare"
}

& $prepare -TaskRoot $TaskRoot
if ($LASTEXITCODE -ne 0) { exit 1 }

if (-not [string]::IsNullOrWhiteSpace($BaselinePath)) {
    $baseline = (Resolve-Path -LiteralPath $BaselinePath).Path
    $sourcePayload = Join-Path $baseline 'wcancel'
    if (-not (Test-Path -LiteralPath $sourcePayload)) {
        Write-Host "restore: baseline payload not found at $sourcePayload"
        exit 1
    }
    $targetPayload = Join-Path $TaskRoot 'environment\workspace\wcancel'
    robocopy $sourcePayload $targetPayload /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    # robocopy exit codes below 8 are success (0 = nothing copied).
    if ($LASTEXITCODE -ge 8) { exit 1 }
}

if (-not $KeepResults) {
    $results = Join-Path $TaskRoot 'results'
    if (Test-Path -LiteralPath $results) {
        Remove-Item -LiteralPath $results -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'restore: baseline ready'
exit 0
