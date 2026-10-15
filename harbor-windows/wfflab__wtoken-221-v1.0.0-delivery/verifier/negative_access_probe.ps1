# Proves, from inside a running container, that the withheld roots are absent.
#
# Run this in the AGENT container. Exit code 0 means the boundary held; exit
# code 1 means something the candidate must not see is reachable.
#
# NOTE: keep this file pure ASCII (Windows PowerShell 5.1 reads BOM-less files
# as ANSI).

[CmdletBinding()]
param(
    [string[]]$Withheld = @(
        'C:\verifier',
        'C:\solution',
        'C:\task\verifier',
        'C:\task\solution',
        'C:\task\tests',
        'C:\tests',
        'C:\testbed\tests\test_wtoken_semantics.py'
    )
)

$ErrorActionPreference = 'Stop'

$violations = New-Object System.Collections.ArrayList
foreach ($path in $Withheld) {
    if (Test-Path -LiteralPath $path) {
        [void]$violations.Add($path)
        Write-Host "REACHABLE: $path"
    }
}

$workspace = 'C:\testbed'
if (Test-Path -LiteralPath $workspace) {
    $leaked = Get-ChildItem -LiteralPath $workspace -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name.ToLowerInvariant() -match 'oracle|golden|reference|hidden|rubric|solution|reward' }
    foreach ($item in $leaked) {
        [void]$violations.Add($item.FullName)
        Write-Host "LEAK: $($item.FullName)"
    }
}

if ($violations.Count -gt 0) {
    Write-Host "negative probe FAILED: $($violations.Count) withheld path(s) reachable"
    exit 1
}

Write-Host 'negative probe PASSED: no withheld path is reachable from the agent container'
exit 0
