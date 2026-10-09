# Gate audit for wfflab__wreparse-217.
#
# Mirrors aggregate_results.ps1: rubric/required ids carry the f2p-/p2p- protocol
# prefix while checks.json holds bare ids, so strip the prefix before matching.
#
# PowerShell 5.1 caveat: ConvertFrom-Json returns a single Object[] through the
# pipeline, so @(...) does not enumerate it - iterate explicitly.
# Keep this file pure ASCII: a BOM-less file with multi-byte comments is read as
# ANSI, and a multi-byte comment can swallow the following newline.
#
# Usage: audit_gate_217.ps1 NOP|GOLDEN
param([string]$Mode = 'NOP')

$ErrorActionPreference = 'Stop'

$TaskRoot = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217'

$declaredRaw = Get-Content -LiteralPath (Join-Path $TaskRoot 'tests\required_testcases.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$declared = New-Object System.Collections.ArrayList
foreach ($d in $declaredRaw) { [void]$declared.Add($d) }

$payload = Get-Content -LiteralPath (Join-Path $TaskRoot 'results\checks.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$checks = New-Object System.Collections.ArrayList
foreach ($c in $payload.checks) { [void]$checks.Add($c) }

$status = @{}
foreach ($c in $checks) { $status[[string]$c.test_id] = [string]$c.status }

$f2pPass = 0; $f2pFail = 0; $p2pPass = 0; $p2pFail = 0
$problems = New-Object System.Collections.ArrayList

foreach ($d in $declared) {
    $id = [string]$d.id
    $bare = $id -replace '^(f2p|p2p)-', ''
    $group = [string]$d.group
    if (-not $status.ContainsKey($bare)) {
        [void]$problems.Add("$id (bare=$bare) is absent from checks.json")
        continue
    }
    $st = $status[$bare]
    if ($group -eq 'F2P') { if ($st -eq 'PASS') { $f2pPass++ } else { $f2pFail++ } }
    else { if ($st -eq 'PASS') { $p2pPass++ } else { $p2pFail++ } }
}

$declaredBare = @{}
foreach ($d in $declared) { $declaredBare[([string]$d.id) -replace '^(f2p|p2p)-', ''] = $true }
$extra = New-Object System.Collections.ArrayList
foreach ($c in $checks) { if (-not $declaredBare.ContainsKey([string]$c.test_id)) { [void]$extra.Add([string]$c.test_id) } }

Write-Host "mode            = $Mode"
Write-Host "declared        = $($declared.Count)   checks.json = $($checks.Count)"
Write-Host "F2P: PASS=$f2pPass  FAIL=$f2pFail"
Write-Host "P2P: PASS=$p2pPass  FAIL=$p2pFail"
if ($extra.Count -gt 0) { [void]$problems.Add("checks.json carries $($extra.Count) undeclared checks: $($extra -join ', ')") }

if ($Mode -eq 'NOP') {
    if ($p2pFail -ne 0) { [void]$problems.Add("NOP: $p2pFail P2P did not pass (all P2P must pass)") }
    if ($f2pPass -ne 0) { [void]$problems.Add("NOP: $f2pPass F2P passed (all F2P must fail)") }
    if ($f2pFail -eq 0) { [void]$problems.Add('NOP: no F2P failed') }
}
elseif ($Mode -eq 'GOLDEN') {
    if ($f2pFail -ne 0) { [void]$problems.Add("GOLDEN: $f2pFail F2P did not pass") }
    if ($p2pFail -ne 0) { [void]$problems.Add("GOLDEN: $p2pFail P2P did not pass") }
}

$r = Get-Content -LiteralPath (Join-Path $TaskRoot 'results\result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host ""
Write-Host "result.json: run_validity=$($r.run_validity) total=$($r.total) passed=$($r.passed) failed=$($r.failed) invalid=$($r.invalid) formal_score=$($r.formal_score) task_version=$($r.task_version)"
if ([string]$r.run_validity -ne 'VALID') { [void]$problems.Add("run_validity=$($r.run_validity) (must be VALID)") }
if ([int]$r.invalid -ne 0) { [void]$problems.Add("invalid=$($r.invalid) (must be 0)") }

Write-Host ""
if ($problems.Count -gt 0) {
    Write-Host "GATE PROBLEMS ($Mode):"
    $problems | ForEach-Object { "  - $_" }
    exit 1
}
Write-Host "GATE OK ($Mode)"
exit 0
