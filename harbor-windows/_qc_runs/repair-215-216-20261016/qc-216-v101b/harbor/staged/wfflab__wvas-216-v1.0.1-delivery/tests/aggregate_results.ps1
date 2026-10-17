# Generated for wfflab__wvas-216 by the task authoring pipeline.
#
# Maps the raw check results onto the required FAIL_TO_PASS / PASS_TO_PASS
# testcases and writes the machine readable task result consumed by the
# evaluation runner.
#
# Scoring is binary by construction: every testcase declared in
# tests/required_testcases.json gates the run, and the formal score is 1 only
# when all of them were observed and passed. There are no testcase weights and
# no partial credit anywhere in this chain, which is why this file consults the
# required-testcase list directly instead of a weighted rubric.
#
# NOTE: keep this file pure ASCII: Windows PowerShell 5.1 reads BOM-less files as
# ANSI, and multi-byte comments can swallow the following newline.

[CmdletBinding()]
param(
    [string]$ChecksPath = '',
    [string]$RequiredPath = '',
    [string]$OutputPath = '',
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($ChecksPath)) { $ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json') }
if ([string]::IsNullOrWhiteSpace($RequiredPath)) { $RequiredPath = Join-Path (Join-Path $TaskRoot 'tests') ('required_testcases' + '.json') }
if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json') }

if (-not (Test-Path -LiteralPath $ChecksPath)) { throw "Checks file not found: $ChecksPath" }
if (-not (Test-Path -LiteralPath $RequiredPath)) { throw "Required testcase file not found: $RequiredPath" }

$checks = Get-Content -LiteralPath $ChecksPath -Raw -Encoding UTF8 | ConvertFrom-Json
$required = Get-Content -LiteralPath $RequiredPath -Raw -Encoding UTF8 | ConvertFrom-Json

$statusById = @{}
foreach ($check in @($checks.checks)) { $statusById[[string]$check.test_id] = [string]$check.status }

# The required list is a bare JSON array of { id, group } rows, which is the shape
# the delivery protocol expects. Raw check ids are bare slugs while the declared
# ids carry the f2p or p2p protocol prefix, so strip it before lookup.
# A check whose terminal status is neither PASS nor FAIL means the harness could
# not observe it: that is incomplete evidence and must not be scored as 0.
$cases = New-Object System.Collections.ArrayList
$invalidTotal = 0
$f2pFailed = 0
$p2pFailed = 0
foreach ($row in @($required)) {
    $declaredId = [string]$row.id
    $group = ([string]$row.group).ToUpperInvariant()
    $bareId = $declaredId -replace '^(f2p|p2p)-', ''
    $status = ''
    if ($statusById.ContainsKey($bareId)) { $status = [string]$statusById[$bareId] }
    if ($status -ne 'PASS' -and $status -ne 'FAIL') { $invalidTotal++ }
    $passed = ($status -eq 'PASS')
    if (-not $passed) {
        if ($group -eq 'F2P') { $f2pFailed++ } else { $p2pFailed++ }
    }
    [void]$cases.Add([pscustomobject][ordered]@{
            test_id = $declaredId
            group   = $group
            status  = $status
            passed  = $passed
        })
}

$casesArray = @($cases.ToArray())
$casesTotal = $casesArray.Count
$casesPassed = @($casesArray | Where-Object { $_.passed }).Count
$casesFailed = $casesTotal - $casesPassed
$runValidity = if ($casesTotal -gt 0 -and $invalidTotal -eq 0) { 'VALID' } else { 'INVALID' }
# An INVALID run means the harness could not observe the contract at all. That is
# incomplete evidence, never a candidate score: keep every score field empty
# instead of collapsing to 0, and let the exit code carry the INVALID verdict.
$formalScore = if ($runValidity -ne 'VALID') { $null }
elseif ($casesPassed -eq $casesTotal) { 1 }
else { 0 }

if ($casesPassed -eq $casesTotal -and $invalidTotal -eq 0) {
    $reason = 'All required FAIL_TO_PASS and PASS_TO_PASS testcases were observed and passed.'
}
else {
    $reason = "Unmet required testcases: $casesFailed of $casesTotal (F2P failed: $f2pFailed, P2P failed: $p2pFailed)"
}
$reasonReported = if ($runValidity -ne 'VALID') { "Run invalid: $invalidTotal required check(s) were not observed." } else { $reason }

$result = [pscustomobject][ordered]@{
    schema_version = 'aggregate-v1'
    run_validity   = $runValidity
    task_id        = [string]$checks.task_id
    task_version   = [string]$checks.task_version
    total          = $casesTotal
    passed         = $casesPassed
    failed         = $casesFailed
    invalid        = $invalidTotal
    formal_score   = $formalScore
    cases          = $casesArray
    required       = @($casesArray | ForEach-Object { $_.test_id })
    mode           = $null
    verdict        = $formalScore
    reason         = $reasonReported
    scoring        = [pscustomobject][ordered]@{
        scheme       = 'binary-required-testcases'
        weights      = $null
        required     = $casesTotal
        f2p_required = @($casesArray | Where-Object { $_.group -eq 'F2P' }).Count
        p2p_required = @($casesArray | Where-Object { $_.group -eq 'P2P' }).Count
    }
    test           = [pscustomobject][ordered]@{
        report  = [pscustomobject][ordered]@{
            status       = $runValidity
            score        = $formalScore
            task_id      = [string]$checks.task_id
            task_version = [string]$checks.task_version
        }
        summary = [pscustomobject][ordered]@{
            checks_total    = @($checks.checks).Count
            checks_failed   = @($checks.checks | Where-Object { [string]$_.status -ne 'PASS' }).Count
            required_total  = $casesTotal
            required_failed = $casesFailed
        }
        checks  = @($checks.checks)
    }
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) { New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null }
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

Write-Host ("aggregate: validity={0} score={1} ({2})" -f $runValidity, $formalScore, $reasonReported)
if ($runValidity -ne 'VALID') { exit 2 }
if ($formalScore -eq 1) { exit 0 }
exit 1
