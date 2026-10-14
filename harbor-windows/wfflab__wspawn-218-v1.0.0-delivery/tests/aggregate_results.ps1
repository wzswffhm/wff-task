# Generated for wfflab__wspawn-218 by the task authoring pipeline.
#
# Maps the raw check results onto the authoritative rubric and writes the
# machine readable task result consumed by the evaluation runner.
#
# The rubric is programmatic only (weights sum to 1.0). Every required F2P/P2P
# testcase gates the run, so the candidate score stays 0/1 and never turns into
# a partial credit. rubric_split is still reported so a consumer can see the
# split at a glance (programmatic_weight=1.0, llm_judge_weight=0.0).
#
# NOTE: keep this file pure ASCII: Windows PowerShell 5.1 reads BOM-less files as
# ANSI, and multi-byte comments can swallow the following newline.

[CmdletBinding()]
param(
    [string]$ChecksPath = '',
    [string]$RubricPath = '',
    [string]$OutputPath = '',
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($ChecksPath)) { $ChecksPath = Join-Path (Join-Path $TaskRoot 'results') ('checks' + '.json') }
if ([string]::IsNullOrWhiteSpace($RubricPath)) { $RubricPath = Join-Path (Join-Path $TaskRoot 'tests') ('rubric' + '.json') }
if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json') }

if (-not (Test-Path -LiteralPath $ChecksPath)) { throw "Checks file not found: $ChecksPath" }
if (-not (Test-Path -LiteralPath $RubricPath)) { throw "Rubric file not found: $RubricPath" }

$checks = Get-Content -LiteralPath $ChecksPath -Raw -Encoding UTF8 | ConvertFrom-Json
$rubric = Get-Content -LiteralPath $RubricPath -Raw -Encoding UTF8 | ConvertFrom-Json

$statusById = @{}
foreach ($check in @($checks.checks)) { $statusById[[string]$check.test_id] = [string]$check.status }

$programmaticItems = @(@($rubric.items) | Where-Object { [string]$_.type -eq 'programmatic' })
$llmItems = @(@($rubric.items) | Where-Object { [string]$_.type -ne 'programmatic' })
$programmaticBudget = 0.0
foreach ($item in $programmaticItems) { $programmaticBudget += [double]$item.weight }
$llmBudget = 0.0
foreach ($item in $llmItems) { $llmBudget += [double]$item.weight }
$programmaticBudget = [Math]::Round($programmaticBudget, 6)
$llmBudget = [Math]::Round($llmBudget, 6)

$itemResults = New-Object System.Collections.ArrayList
$weightedScore = 0.0
$allPassed = $true

foreach ($item in $programmaticItems) {
    $missing = New-Object System.Collections.ArrayList
    $failed = New-Object System.Collections.ArrayList
    foreach ($id in @($item.test_ids)) {
        # rubric test_ids carry the f2p or p2p protocol prefix required by the
        # reviewer contract, while the raw check ids are bare; strip it first.
        $bareId = ([string]$id) -replace '^(f2p|p2p)-', ''
        if (-not $statusById.ContainsKey($bareId)) { [void]$missing.Add($bareId) }
        elseif ($statusById[$bareId] -ne 'PASS') { [void]$failed.Add($bareId) }
    }
    $passed = ($missing.Count -eq 0 -and $failed.Count -eq 0)
    if ($passed) { $weightedScore += [double]$item.weight } else { $allPassed = $false }
    [void]$itemResults.Add([pscustomobject][ordered]@{
            rubric_id = [string]$item.rubric_id
            type      = 'programmatic'
            weight    = [double]$item.weight
            passed    = $passed
            failed    = @($failed.ToArray())
            missing   = @($missing.ToArray())
        })
}

$weightedScore = [Math]::Round($weightedScore, 6)
$score = if ($allPassed) { 1 } else { 0 }
$total = @($checks.checks).Count
$failedTotal = @($checks.checks | Where-Object { [string]$_.status -ne 'PASS' }).Count

if ($score -eq 1) { $reason = 'All programmatic rubric items satisfied.' }
else {
    $names = @($itemResults | Where-Object { -not $_.passed } | ForEach-Object { $_.rubric_id })
    $reason = "Unsatisfied rubric items: $($names -join ', ')"
}

# ---- Reviewer aggregate-v1 contract (bundled QC checker) --------------------
# cases cover every testcase declared by the programmatic rubric. A terminal
# status other than PASS or FAIL means the harness could not observe the case
# (missing collection, pytest error or skip): that is incomplete evidence, so
# invalid>0 forces run_validity=INVALID and the run must not be reported as a
# legitimate candidate score of 0.
$cases = New-Object System.Collections.ArrayList
$invalidTotal = 0
foreach ($item in $programmaticItems) {
    foreach ($id in @($item.test_ids)) {
        $bareId = ([string]$id) -replace '^(f2p|p2p)-', ''
        $st = ''
        if ($statusById.ContainsKey($bareId)) { $st = [string]$statusById[$bareId] }
        if ($st -ne 'PASS' -and $st -ne 'FAIL') { $invalidTotal++ }
        [void]$cases.Add([pscustomobject][ordered]@{
                test_id = [string]$id
                passed  = ($st -eq 'PASS')
            })
    }
}
$casesArray = @($cases.ToArray())
$casesTotal = $casesArray.Count
$casesPassed = @($casesArray | Where-Object { $_.passed }).Count
$casesFailed = $casesTotal - $casesPassed
$runValidity = if ($casesTotal -gt 0 -and $invalidTotal -eq 0) { 'VALID' } else { 'INVALID' }
$formalScore = if ($casesTotal -gt 0 -and $casesPassed -eq $casesTotal) { 1 } else { 0 }

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
    verdict        = $score
    reason         = $reason
    rubric_split   = [pscustomobject][ordered]@{
        programmatic_weight = $programmaticBudget
        llm_judge_weight    = $llmBudget
        programmatic_items  = @($programmaticItems).Count
        llm_judge_items     = @($llmItems).Count
    }
    test           = [pscustomobject][ordered]@{
        report = [pscustomobject][ordered]@{
            status       = 'VALID'
            score        = $score
            task_id      = [string]$checks.task_id
            task_version = [string]$checks.task_version
        }
        weighted_score = $weightedScore
        summary        = [pscustomobject][ordered]@{
            checks_total  = $total
            checks_failed = $failedTotal
            items_total   = @($programmaticItems).Count
            items_failed  = @($itemResults | Where-Object { -not $_.passed }).Count
        }
        rubric_items = @($itemResults.ToArray())
        checks       = @($checks.checks)
    }
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) { New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null }
$result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $OutputPath -Encoding UTF8

Write-Host ("aggregate: score={0} weighted={1} ({2})" -f $score, $weightedScore, $reason)
if ($score -eq 1) { exit 0 }
exit 1
