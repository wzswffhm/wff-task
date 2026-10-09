# Generated for wfflab__wchunk-216 by the task authoring pipeline. Do not edit by hand.
#
# Removes everything this task creates outside the frozen sources: the results
# directory, interpreter caches and any grading scratch directories. It never
# touches environment/workspace sources.
#
# The script is idempotent and verifies its own work: if anything it claims to
# have removed is still present the run fails.
#
# Exit codes:
#   0  the task left no residue
#   1  residue remained after cleanup

[CmdletBinding()]
param(
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

$targets = New-Object System.Collections.ArrayList
[void]$targets.Add((Join-Path $TaskRoot 'results'))

foreach ($cache in @(Get-ChildItem -LiteralPath $TaskRoot -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @('__pycache__', '.pytest_cache') })) {
    [void]$targets.Add($cache.FullName)
}

foreach ($scratch in @(Get-ChildItem -LiteralPath ([System.IO.Path]::GetTempPath()) -Directory -Filter 'wchunk-graded-*' -ErrorAction SilentlyContinue)) {
    [void]$targets.Add($scratch.FullName)
}

foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target)) { continue }
    Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "cleanup: removed $target"
}

$residue = New-Object System.Collections.ArrayList
foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) { [void]$residue.Add($target) }
}

if ($residue.Count -gt 0) {
    foreach ($item in $residue) { Write-Host "RESIDUE: $item" }
    exit 1
}

Write-Host 'cleanup: no residue'
exit 0
