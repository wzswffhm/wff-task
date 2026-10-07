# Generated for wfflab__wreparse-217. Do not edit by hand.
#
# Removes everything this task creates outside the frozen sources: the fixture
# tree, the results directory and the temporary staging directories used when a
# reparse-point fixture has to be rebuilt. It never touches environment/workspace.
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
# The fixture is built on the container's writable layer, not inside the task
# tree; see environment/prepare.ps1. A legacy in-tree location is swept as well
# so a stale checkout cannot leave residue behind.
[void]$targets.Add((Join-Path $env:SystemDrive 'wreparse-fixture'))
[void]$targets.Add((Join-Path $TaskRoot '.fixture'))
[void]$targets.Add((Join-Path $TaskRoot 'results'))

foreach ($staging in @(Get-ChildItem -LiteralPath $TaskRoot -Directory -Filter 'wreparse-*' -ErrorAction SilentlyContinue)) {
    [void]$targets.Add($staging.FullName)
}

foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target)) { continue }
    # Junctions inside the fixture make a plain recursive delete unreliable on
    # some builds, so remove the reparse links first and then the tree.
    foreach ($link in @(Get-ChildItem -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue |
            Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint })) {
        cmd.exe /c "rmdir `"$($link.FullName)`"" | Out-Null
    }
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
