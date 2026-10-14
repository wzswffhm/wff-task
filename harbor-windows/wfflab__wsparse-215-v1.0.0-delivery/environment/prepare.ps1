# Prepares the candidate workspace for a wsparse run.
#
# NOTE: keep this file pure ASCII. Windows PowerShell 5.1 reads BOM-less files
# as ANSI, so a multi-byte character would corrupt the surrounding syntax.

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
    'wsparse\__init__.py',
    'wsparse\alloc.py',
    'wsparse\errors.py',
    'wsparse\flags.py',
    'wsparse\ranges.py',
    'wsparse\usage.py',
    'assets\dense_64k.bin',
    'tests\test_wsparse_basic.py'
)

foreach ($relative in $required) {
    $item = Join-Path $workspace $relative
    if (-not (Test-Path -LiteralPath $item)) {
        Write-Host "prepare: required workspace item is missing: $relative"
        exit 1
    }
}

Get-ChildItem -LiteralPath $workspace -Recurse -Directory -Force |
    Where-Object { $_.Name -eq '__pycache__' -or $_.Name -eq '.pytest_cache' } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host 'prepare: workspace ready'
exit 0
