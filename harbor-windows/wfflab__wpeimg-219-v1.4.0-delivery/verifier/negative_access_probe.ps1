# Negative-access probe for the withheld material of wfflab__wpeimg-219.
#
# Run it with the same identity the candidate agent uses, inside the task
# container, or against the package root when auditing the layout on a host.
# The probe is read-only: it writes nothing, scores nothing and never modifies
# the candidate workspace.
#
# It answers six questions:
#   1. is any withheld-looking name reachable from the agent-visible workspace?
#   2. does the workspace leak hidden-suite symbols or authoritative constants?
#   3. do the withheld roots (C:\solution, C:\verifier) resolve outside the agent
#      workspace?
#   4. do the hidden suite and the reference payload actually exist on the
#      verifier side (i.e. they were moved out of the agent surface, not lost)?
#   5. does the package test directory still carry a copy of the hidden suite?
#   6. is the public smoke suite still present and read-only in the workspace?
#
# Exit codes:
#   0  every isolation assertion holds
#   1  at least one assertion failed
#
# Output: a single JSON document on stdout, safe to archive as evidence.

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$TaskId = 'wfflab__wpeimg-219',
    [string]$WorkspaceRelative = 'environment\workspace',
    [string]$PackageRelative = 'environment\workspace\wpeimg',
    [string]$PublicSuiteRelative = 'environment\workspace\tests\test_wpeimg_basic.py',
    [string]$HiddenSuiteRelative = 'verifier\tests\test_wpeimg_semantics.py',
    [string]$ReferenceRelative = 'verifier\oracle\reference\wpeimg'
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
$workspace = (Resolve-Path -LiteralPath (Join-Path $TaskRoot $WorkspaceRelative)).Path

$checks = New-Object System.Collections.ArrayList

function Add-Check([string]$Id, [bool]$Passed, [string]$Detail) {
    [void]$checks.Add([pscustomobject][ordered]@{
            id     = $Id
            passed = $Passed
            detail = $Detail
        })
}

# ---- 1. withheld-looking names inside the agent-visible tree ---------------
$namePattern = 'oracle|golden|reference|hidden|rubric|solution|reward|semantics'
$named = New-Object System.Collections.ArrayList
foreach ($item in @(Get-ChildItem -LiteralPath $workspace -Recurse -File -Force -ErrorAction SilentlyContinue)) {
    if ($item.Name.ToLowerInvariant() -match $namePattern) { [void]$named.Add($item.FullName) }
}
Add-Check 'no-withheld-names-in-workspace' ($named.Count -eq 0) `
    ("matches: " + (@($named.ToArray()) -join '; '))

# ---- 2. hidden-suite symbols or authoritative constants leaking ------------
$symbols = @(
    'test_wpeimg_semantics',
    'test_iter_sections_does_not_slurp_the_stream',
    'test_checksum_matches_authoritative_values',
    'AUTHORITATIVE',
    'rubric.conditions.json',
    'oracle/reference'
)
$leaks = New-Object System.Collections.ArrayList
$candidates = @(Get-ChildItem -LiteralPath $workspace -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @('.py', '.md', '.json', '.txt') })
foreach ($item in $candidates) {
    $text = ''
    try { $text = Get-Content -LiteralPath $item.FullName -Raw -ErrorAction Stop } catch { continue }
    foreach ($symbol in $symbols) {
        if ($text -and $text.Contains($symbol)) {
            [void]$leaks.Add("$($item.FullName) :: $symbol")
        }
    }
}
Add-Check 'no-hidden-symbols-in-workspace' ($leaks.Count -eq 0) `
    ("matches: " + (@($leaks.ToArray()) -join '; '))

# ---- 3. withheld roots must resolve outside the agent workspace ------------
$inside = New-Object System.Collections.ArrayList
foreach ($forbidden in @('C:\verifier', 'C:\solution')) {
    if (-not (Test-Path -LiteralPath $forbidden)) { continue }
    $resolved = (Resolve-Path -LiteralPath $forbidden).Path
    if ($resolved.ToLowerInvariant().StartsWith($workspace.ToLowerInvariant())) {
        [void]$inside.Add($resolved)
    }
}
Add-Check 'withheld-roots-outside-workspace' ($inside.Count -eq 0) `
    ("inside workspace: " + (@($inside.ToArray()) -join '; '))

# ---- 4. verifier-side material exists outside the agent surface ------------
$hiddenSuite = Join-Path $TaskRoot $HiddenSuiteRelative
$reference = Join-Path $TaskRoot $ReferenceRelative
$publicSuite = Join-Path $TaskRoot $PublicSuiteRelative
Add-Check 'hidden-suite-present-on-verifier-side' (Test-Path -LiteralPath $hiddenSuite) $hiddenSuite
Add-Check 'reference-present-on-verifier-side' (Test-Path -LiteralPath $reference) $reference
Add-Check 'public-smoke-suite-present-in-workspace' (Test-Path -LiteralPath $publicSuite) $publicSuite

# ---- 5. the platform-delivered copy under tests/ must match the verifier copy
# Harbor copies the package tests/ directory to C:\tests right before it runs
# tests/test.ps1, so a copy under tests/ is the platform contract. What must not
# happen is two copies drifting apart (v1.0.0 shipped divergent duplicates, one
# of them under tests/verifier/tests/).
$delivered = Join-Path $TaskRoot ('tests\' + (Split-Path -Leaf $HiddenSuiteRelative))
Add-Check 'platform-delivered-suite-present-under-tests' (Test-Path -LiteralPath $delivered) $delivered
if ((Test-Path -LiteralPath $delivered) -and (Test-Path -LiteralPath $hiddenSuite)) {
    $a = (Get-FileHash -LiteralPath $delivered -Algorithm SHA256).Hash
    $b = (Get-FileHash -LiteralPath $hiddenSuite -Algorithm SHA256).Hash
    Add-Check 'delivered-suite-matches-verifier-suite' ($a -eq $b) ($a + ' vs ' + $b)
} else {
    Add-Check 'delivered-suite-matches-verifier-suite' $false 'one of the two copies is missing'
}
$legacyCopies = New-Object System.Collections.ArrayList
foreach ($stray in @(Get-ChildItem -LiteralPath (Join-Path $TaskRoot 'tests\verifier') -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'test_*_semantics.py' })) {
    [void]$legacyCopies.Add($stray.FullName)
}
Add-Check 'no-legacy-duplicate-under-tests-verifier' ($legacyCopies.Count -eq 0) `
    (@($legacyCopies.ToArray()) -join '; ')

# ---- 6. the resolution order must not reach the candidate workspace ---------
$runner = Get-Content -LiteralPath (Join-Path $TaskRoot 'tests\run_tests.ps1') -Raw -ErrorAction SilentlyContinue
$blockMatch = [regex]::Match([string]$runner, '(?s)\$verifierCandidates = .*?\n\n')
$block = if ($blockMatch.Success) { $blockMatch.Value } else { '' }
$badLines = New-Object System.Collections.ArrayList
foreach ($line in ($block -split "`n")) {
    $t = $line.Trim()
    if ($t.Contains('Add(') -and ($t.Contains('$TaskRoot') -or $t.Contains('$WorkspaceRoot'))) {
        [void]$badLines.Add($t)
    }
}
Add-Check 'resolution-order-excludes-workspace-and-task-root' ($badLines.Count -eq 0) `
    (@($badLines.ToArray()) -join '; ')

# ---- 7. the single writable surface is the candidate package only ----------
$writable = Join-Path $TaskRoot $PackageRelative
Add-Check 'candidate-package-present' (Test-Path -LiteralPath (Join-Path $writable '__init__.py')) $writable

$failed = @($checks.ToArray() | Where-Object { -not $_.passed })
$document = [pscustomobject][ordered]@{
    schema_version = 'negative-access-probe-v1'
    task_id        = $TaskId
    identity       = "$env:USERDOMAIN\$env:USERNAME"
    host           = $env:COMPUTERNAME
    platform       = [string][System.Environment]::OSVersion.VersionString
    generated_at   = (Get-Date).ToString('o')
    task_root      = $TaskRoot
    workspace      = $workspace
    checks         = @($checks.ToArray())
    verdict        = $(if ($failed.Count -eq 0) { 'PASS' } else { 'FAIL' })
}

$document | ConvertTo-Json -Depth 6

if ($failed.Count -gt 0) { exit 1 }
exit 0
