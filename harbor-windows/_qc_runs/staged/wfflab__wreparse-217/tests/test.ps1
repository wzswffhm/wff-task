# Generated for wfflab__wreparse-217 by the task authoring pipeline.
# Do not edit by hand: change tests/run_tests.ps1, tests/aggregate_results.ps1
# or tests/rubric.json instead.
#
# Stable entry point used by the evaluation platform. It runs the behavioural
# checks and then the rubric aggregation, returning the real test exit code.

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$OutputPath = '',
    [string]$WorkspaceRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { $WorkspaceRoot = Join-Path $TaskRoot 'environment\workspace' }
if ([string]::IsNullOrWhiteSpace($OutputPath)) { $OutputPath = Join-Path $TaskRoot 'results\result.json' }

$resultsDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $resultsDirectory)) { New-Item -ItemType Directory -Path $resultsDirectory -Force | Out-Null }
$checksPath = Join-Path $resultsDirectory 'checks.json'

& (Join-Path $PSScriptRoot 'run_tests.ps1') -WorkspaceRoot $WorkspaceRoot -ChecksPath $checksPath -TaskRoot $TaskRoot
$checksExit = $LASTEXITCODE
if ($checksExit -eq 2) {
    Write-Output '===SWELIVE_INVALID checks_execution_failed==='
    exit 2
}

& (Join-Path $PSScriptRoot 'aggregate_results.ps1') -ChecksPath $checksPath `
    -RubricPath (Join-Path $PSScriptRoot 'rubric.json') -OutputPath $OutputPath -TaskRoot $TaskRoot
$aggExit = $LASTEXITCODE

# ---- Harbor platform compatibility branch -----------------------------------
# Harbor pre-creates its log root inside the container (see the Windows branch of
# the bundled QC environment extension); that presence tells us we are running
# under Harbor, so the verdict report and the reward triplet are written into the
# verifier subdirectory of that root.
#
# Constraint: the reviewer accepts exactly ONE report file under its verifier
# directory; having both candidate names at once is rejected as ambiguous. We
# therefore write a single report.
#
# Contract: that report must follow the aggregate-v1 shape (schema_version /
# run_validity / total / passed / failed / invalid / formal_score / cases).
# Anything else is INVALID and exits 2 -- incomplete evidence or infrastructure
# failure is never a legitimate candidate score of 0.
# NOTE: keep this file pure ASCII: Windows PowerShell 5.1 reads BOM-less files as
# ANSI, and multi-byte comments can swallow the following newline.
$logsRoot = Join-Path $env:SystemDrive 'logs'
if (Test-Path -LiteralPath $logsRoot) {
    $verifierDir = Join-Path $logsRoot 'verifier'
    New-Item -ItemType Directory -Force -Path $verifierDir | Out-Null

    $validity = 'INVALID'
    $formalScore = 0
    $invalidateReason = 'missing_result_json'
    $doc = $null
    if (Test-Path -LiteralPath $OutputPath) {
        $invalidateReason = 'aggregate_report_invalid'
        $doc = Get-Content -Raw -LiteralPath $OutputPath | ConvertFrom-Json
        if ([string]$doc.run_validity -eq 'VALID') {
            $validity = 'VALID'
            $formalScore = [int]$doc.formal_score
        }
        Copy-Item -LiteralPath $OutputPath -Destination (Join-Path $verifierDir 'report.json') -Force
    }

    if ($validity -ne 'VALID') {
        Write-Output ('===SWELIVE_INVALID ' + $invalidateReason + '===')
        exit 2
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Join-Path $verifierDir 'reward.txt'), [string]$formalScore, $utf8NoBom)
    $rewardJson = [pscustomobject][ordered]@{ reward = $formalScore } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText((Join-Path $verifierDir 'reward.json'), $rewardJson, $utf8NoBom)
    $criterion = [pscustomobject][ordered]@{
        score    = $formalScore
        criteria = [pscustomobject][ordered]@{
            name        = 'windows_bench_regression'
            value       = $formalScore
            raw         = $doc
            weight      = 1.0
            description = 'All required FAIL_TO_PASS and PASS_TO_PASS testcases were observed and passed.'
        }
        kind     = 'programmatic'
    }
    $details = [pscustomobject][ordered]@{ reward = @($criterion) } | ConvertTo-Json -Depth 12
    [System.IO.File]::WriteAllText((Join-Path $verifierDir 'reward-details.json'), $details, $utf8NoBom)

    Write-Output ('===SWELIVE_GRADE score=' + $formalScore + '===')
    if ($formalScore -eq 1) { exit 0 }
    exit 1
}

exit $aggExit
