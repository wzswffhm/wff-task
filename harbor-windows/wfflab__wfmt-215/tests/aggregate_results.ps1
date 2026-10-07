# Generated for wfflab__wfmt-215 by the task authoring pipeline. Do not edit by hand.
#
# Maps the raw check results onto the authoritative rubric and writes the
# machine readable task result consumed by the evaluation runner.
#
# The reported `score` is a gate: 1 only when every rubric item is satisfied.

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
if ([string]::IsNullOrWhiteSpace($ChecksPath)) { $ChecksPath = Join-Path $TaskRoot 'results\checks.json' }
if ([string]::IsNullOrWhiteSpace($RubricPath)) { $RubricPath = Join-Path $TaskRoot 'tests\rubric.json' }
if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $TaskRoot 'results\result.json' }

if (-not (Test-Path -LiteralPath $ChecksPath)) { throw "Checks file not found: $ChecksPath" }
if (-not (Test-Path -LiteralPath $RubricPath)) { throw "Rubric file not found: $RubricPath" }

$checks = Get-Content -LiteralPath $ChecksPath -Raw -Encoding UTF8 | ConvertFrom-Json
$rubric = Get-Content -LiteralPath $RubricPath -Raw -Encoding UTF8 | ConvertFrom-Json

$statusById = @{}
foreach ($check in @($checks.checks)) { $statusById[[string]$check.test_id] = [string]$check.status }

$itemResults = New-Object System.Collections.ArrayList
$weightedScore = 0.0
$allPassed = $true

foreach ($item in @($rubric.items)) {
    $missing = New-Object System.Collections.ArrayList
    $failed = New-Object System.Collections.ArrayList
    foreach ($id in @($item.test_ids)) {
        if (-not $statusById.ContainsKey([string]$id)) { [void]$missing.Add([string]$id) }
        elseif ($statusById[[string]$id] -ne 'PASS') { [void]$failed.Add([string]$id) }
    }
    $passed = ($missing.Count -eq 0 -and $failed.Count -eq 0)
    if ($passed) { $weightedScore += [double]$item.weight } else { $allPassed = $false }
    [void]$itemResults.Add([pscustomobject][ordered]@{
            rubric_id = [string]$item.rubric_id
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

if ($score -eq 1) { $reason = 'All rubric items satisfied.' }
else {
    $names = @($itemResults | Where-Object { -not $_.passed } | ForEach-Object { $_.rubric_id })
    $reason = "Unsatisfied rubric items: $($names -join ', ')"
}

$result = [pscustomobject][ordered]@{
    task_id      = [string]$checks.task_id
    task_version = [string]$checks.task_version
    mode         = $null
    verdict      = $score
    reason       = $reason
    test         = [pscustomobject][ordered]@{
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
            items_total   = @($rubric.items).Count
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
