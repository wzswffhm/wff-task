# Prepares the candidate workspace for a wvas run.
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
    'wvas\__init__.py',
    'wvas\errors.py',
    'wvas\vas.py',
    'wvas\_winapi.py',
    'docs\NOTES.md',
    'README.md',
    'tests\test_wvas_basic.py'
)

foreach ($relative in $required) {
    $item = Join-Path $workspace $relative
    if (-not (Test-Path -LiteralPath $item)) {
        Write-Host "prepare: required workspace item is missing: $relative"
        exit 1
    }
}

# Transient state only: the address space descriptors themselves are measured at
# grading time and are never cached in the workspace.
Get-ChildItem -LiteralPath $workspace -Recurse -Directory -Force |
    Where-Object { $_.Name -eq '__pycache__' -or $_.Name -eq '.pytest_cache' } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host 'prepare: workspace ready'
exit 0
