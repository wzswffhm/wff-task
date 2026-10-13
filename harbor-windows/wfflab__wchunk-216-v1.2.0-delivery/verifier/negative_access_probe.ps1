# Negative-access probe for the withheld material of wfflab__wchunk-216.
#
# Run it with the same identity the candidate agent uses, inside the task
# container, or against the package root when auditing the layout on a host.
# The probe is read-only: it writes nothing, scores nothing and never modifies
# the candidate workspace.
#
# It answers four questions:
#   1. is any withheld-looking name reachable from the agent-visible workspace?
#   2. does the workspace leak hidden-suite symbols or sample expectations?
#   3. do the withheld roots (C:\solution, C:\verifier) resolve outside the
#      agent workspace?
#   4. do the hidden suite and the reference payload actually exist on the
#      verifier side (i.e. they were moved out of the agent surface, not lost)?
#
# Exit codes:
#   0  every isolation assertion holds
#   1  at least one assertion failed
#
# Output: a single JSON document on stdout, safe to archive as evidence.

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$TaskId = 'wfflab__wchunk-216',
    [string]$WorkspaceRelative = 'environment\workspace',
    [string]$PublicSuiteRelative = 'environment\workspace\tests\test_wchunk_basic.py',
    [string]$HiddenSuiteRelative = 'verifier\tests\test_wchunk_semantics.py',
    [string]$ReferenceRelative = 'verifier\oracle\reference\wchunk'
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
$namePattern = 'oracle|golden|reference|hidden|rubric|solution|reward'
$named = New-Object System.Collections.ArrayList
foreach ($item in @(Get-ChildItem -LiteralPath $workspace -Recurse -File -Force -ErrorAction SilentlyContinue)) {
    if ($item.Name.ToLowerInvariant() -match $namePattern) { [void]$named.Add($item.FullName) }
}
Add-Check 'no-withheld-names-in-workspace' ($named.Count -eq 0) `
    ("matches: " + (@($named.ToArray()) -join '; '))

# ---- 2. hidden-suite symbols or expectations leaking into the workspace ----
$symbols = @(
    'test_wchunk_semantics',
    'test_iter_records_is_streaming',
    'test_stream_tail_checksum_is_rejected',
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
