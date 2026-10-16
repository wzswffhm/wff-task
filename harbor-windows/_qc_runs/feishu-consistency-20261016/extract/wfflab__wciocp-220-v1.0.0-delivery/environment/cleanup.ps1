# Removes everything a graded run leaves behind.
#
# NOTE: keep this file pure ASCII (Windows PowerShell 5.1 reads BOM-less files
# as ANSI).

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

$results = Join-Path $TaskRoot 'results'
if (Test-Path -LiteralPath $results) { [void]$targets.Add($results) }

Get-ChildItem -LiteralPath $TaskRoot -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq '__pycache__' -or $_.Name -eq '.pytest_cache' } |
    ForEach-Object { [void]$targets.Add($_.FullName) }

$tempRoot = [System.IO.Path]::GetTempPath()
Get-ChildItem -LiteralPath $tempRoot -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like 'wciocp-graded-*' } |
    ForEach-Object { [void]$targets.Add($_.FullName) }

foreach ($target in $targets) {
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
