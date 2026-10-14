#Requires -Version 5.1
<#
.SYNOPSIS
    Harbor fail_to_pass suite for task windows-d4-litemonitor-001.

.DESCRIPTION
    Runs the hidden evaluator (tests/LiteMonitor.Evaluator) in fail_to_pass mode and
    writes the machine-readable verdict to <ResultsDir>\suite_fail_to_pass.json plus a
    full log. This script never decides pass/fail itself: the verdict lives in the
    result files, and tests/aggregate_results.ps1 folds it into results/result.json.

    Exit codes
      0 = the suite executed and produced a verdict (checks may have failed)
      2 = INVALID: the evaluator could not run or produced no verdict. Never counted
          against the model.

    Machine state is purged before and after the run so the three suites stay
    independent and repeated runs are idempotent.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EvaluatorExe,
    [Parameter(Mandatory = $true)][string]$ResultsDir,
    [Parameter(Mandatory = $false)][string]$WorkDir,
    [Parameter(Mandatory = $false)][string]$RunId = '',
    [Parameter(Mandatory = $false)][string]$TargetRepoOut = '',
    [Parameter(Mandatory = $false)][string]$RepoCommit = '',
    [Parameter(Mandatory = $false)][int]$TimeoutSeconds = 900
)

$ErrorActionPreference = 'Stop'
$script:TestsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
. (Join-Path $script:TestsDir 'harness_common.ps1')

$SuiteName = 'fail_to_pass'
Write-Banner "test_$SuiteName"
$sw = [System.Diagnostics.Stopwatch]::StartNew()

if (-not $RunId) { $RunId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff') }
if (-not $WorkDir) { $WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) "harbor-litemonitor-$RunId" }
New-DirectorySafe $ResultsDir | Out-Null
New-DirectorySafe $WorkDir | Out-Null
$ResultsDir = (Resolve-Path -LiteralPath $ResultsDir).ProviderPath

function Exit-Suite {
    param([int]$Code, [string]$Reason)
    if ($Reason) { Write-Host "INVALID_REASON=$Reason" }
    Write-Host "SUITE=$SuiteName EXIT=$Code"
    exit $Code
}

if (-not (Test-Path -LiteralPath $EvaluatorExe)) {
    Exit-Suite 2 "evaluator executable not found at $EvaluatorExe"
}
$evaluatorExeFull = (Resolve-Path -LiteralPath $EvaluatorExe).ProviderPath
$evaluatorDir = Split-Path -Parent $evaluatorExeFull

Write-Host "suite=$SuiteName"
Write-Host "evaluator=$evaluatorExeFull"
Write-Host "evaluatorDir=$evaluatorDir"
Write-Host "resultsDir=$ResultsDir"
Write-Host "workDir=$WorkDir"
Write-Host "runId=$RunId"

# The evaluator must run from a path that carries non-ASCII (zh-CN) characters so the
# Chinese-install-dir scenarios are genuinely exercised. Refuse to fake a verdict.
if (-not (Test-NonAsciiPath $evaluatorDir)) {
    Exit-Suite 2 "the evaluator output directory must contain non-ASCII (zh-CN) characters so the Chinese install-path scenarios are real, got $evaluatorDir"
}

# Independence: start every suite from an empty machine state.
$pre = Clear-LiteMonitorMachineState
Write-Host "preSuiteCleanup=$($pre | ConvertTo-Json -Compress -Depth 4)"

$suiteResults = Join-Path $ResultsDir "suite_$SuiteName.json"
$suiteLog = Join-Path $ResultsDir "suite_$SuiteName.log"
$suiteErr = Join-Path $ResultsDir "suite_$SuiteName.err"
$wr = Join-Path $WorkDir "wr-$SuiteName"
New-DirectorySafe $wr | Out-Null

if (Test-Path -LiteralPath $suiteResults) { [System.IO.File]::Delete($suiteResults) }

$arguments = @(
    '--suite', $SuiteName,
    '--workroot', $wr,
    '--results', $suiteResults,
    '--run-id', $RunId,
    '--task-id', $TaskId,
    '--task-version', $TaskVersion
)
if ($TargetRepoOut) { $arguments += @('--target-repo-out', $TargetRepoOut) }
if ($RepoCommit) { $arguments += @('--repo-commit', $RepoCommit) }

$required = @( (Get-Content -Raw -Encoding UTF8 (Join-Path $PSScriptRoot 'rubric.json') | ConvertFrom-Json).required_tests | Where-Object suite -eq $SuiteName )
$collected = @()
$caseRoot = Join-Path $ResultsDir 'isolated_cases'
New-DirectorySafe $caseRoot | Out-Null
foreach ($expected in $required) {
    $caseId = [string]$expected.id
    $caseResult = Join-Path $caseRoot ($caseId+'.json')
    $witness = Join-Path $caseRoot ($caseId+'.started')
    $caseLog = Join-Path $caseRoot ($caseId+'.log')
    $caseErr = Join-Path $caseRoot ($caseId+'.err')
    $preHealth = Invoke-Native -FilePath $evaluatorExeFull -Arguments @('--health') -WorkingDirectory $evaluatorDir -TimeoutSeconds 30
    Write-NativeResult -Result $preHealth -StdOutPath (Join-Path $caseRoot ($caseId+'.health-before.log')) -StdErrPath (Join-Path $caseRoot ($caseId+'.health-before.err')) -Label ('health-before '+$caseId)
    if ($preHealth.ExitCode -ne 0 -or $preHealth.TimedOut) {Exit-Suite 2 ('Health check failed before '+$caseId)}
    $caseArguments = @('--suite',$SuiteName,'--case',$caseId,'--case-started',$witness,'--workroot',$wr,'--results',$caseResult,'--run-id',$RunId,'--task-id',$TaskId,'--task-version',$TaskVersion)
    if ($TargetRepoOut) {$caseArguments += @('--target-repo-out',$TargetRepoOut)}
    if ($RepoCommit) {$caseArguments += @('--repo-commit',$RepoCommit)}
    $child = Invoke-Native -FilePath $evaluatorExeFull -Arguments $caseArguments -WorkingDirectory $evaluatorDir -TimeoutSeconds $TimeoutSeconds
    Write-NativeResult -Result $child -StdOutPath $caseLog -StdErrPath $caseErr -Label ('isolated '+$caseId)
    $postHealth = Invoke-Native -FilePath $evaluatorExeFull -Arguments @('--health') -WorkingDirectory $evaluatorDir -TimeoutSeconds 30
    Write-NativeResult -Result $postHealth -StdOutPath (Join-Path $caseRoot ($caseId+'.health-after.log')) -StdErrPath (Join-Path $caseRoot ($caseId+'.health-after.err')) -Label ('health-after '+$caseId)
    if ($postHealth.ExitCode -ne 0 -or $postHealth.TimedOut) {Exit-Suite 2 ('Health check failed after '+$caseId)}
    if ($child.TimedOut) {Exit-Suite 2 ('Isolated testcase timed out: '+$caseId)}
    if (Test-Path -LiteralPath $caseResult) {
        $payload = Get-Content -Raw -Encoding UTF8 -LiteralPath $caseResult | ConvertFrom-Json
        $checks = @($payload.checks)
        if ($payload.task_id -ne $TaskId -or $payload.task_version -ne $TaskVersion -or $payload.run_id -ne $RunId -or $checks.Count -ne 1 -or $checks[0].id -ne $caseId -or $child.ExitCode -eq 2) {Exit-Suite 2 ('Invalid isolated testcase receipt: '+$caseId)}
        $collected += $checks[0]
    } elseif ($child.ExitCode -eq -1073741819 -and (Test-Path -LiteralPath $witness) -and (Get-Content -Raw -Encoding UTF8 -LiteralPath $witness) -ceq $caseId) {
        $collected += @{id=$caseId;suite=$SuiteName;status='fail';passed=$false;seconds=$child.Seconds;detail='Testcase entered and candidate process terminated with Windows access violation (0xC0000005); independent registry/runtime health checks passed before and after. See isolated_cases receipts.'}
    } else {
        Exit-Suite 2 ('No trustworthy isolated testcase receipt: '+$caseId+' exit='+$child.ExitCode)
    }
    $caseCleanup = Clear-LiteMonitorMachineState
    Write-Host ('caseCleanup '+$caseId+' '+($caseCleanup | ConvertTo-Json -Compress -Depth 4))
}
@{task_id=$TaskId;task_version=$TaskVersion;run_id=$RunId;suite_requested=$SuiteName;checks=$collected} | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $suiteResults -Encoding UTF8
$result = @{ExitCode=0;TimedOut=$false}

$post = Clear-LiteMonitorMachineState
Write-Host "postSuiteCleanup=$($post | ConvertTo-Json -Compress -Depth 4)"

$sw.Stop()

if ($result.TimedOut) {
    Exit-Suite 2 "the evaluator exceeded its ${TimeoutSeconds}s budget in suite $SuiteName"
}
if (-not (Test-Path -LiteralPath $suiteResults)) {
    Exit-Suite 2 "the evaluator produced no suite_$SuiteName.json (exit=$($result.ExitCode)); see $suiteLog"
}
$parsed = $null
try { $parsed = (Read-Utf8 $suiteResults) | ConvertFrom-Json } catch { $parsed = $null }
if ($null -eq $parsed) {
    Exit-Suite 2 "suite_$SuiteName.json is not parseable JSON"
}
$checkCount = 0
if ($parsed.checks) { $checkCount = @($parsed.checks).Count }
if ($checkCount -eq 0) {
    Exit-Suite 2 "the evaluator collected 0 checks in suite $SuiteName - no verdict can be derived"
}
if ($result.ExitCode -eq 2) {
    Exit-Suite 2 "the evaluator itself reported INVALID for suite $SuiteName (exit=2)"
}

Write-Host "checksCollected=$checkCount evaluatorExit=$($result.ExitCode)"
Write-Host ("elapsedSeconds={0}" -f ([double]$sw.Elapsed.TotalSeconds).ToString('F3', $Inv))
Write-Host "SUITE=$SuiteName EXIT=0"
exit 0
