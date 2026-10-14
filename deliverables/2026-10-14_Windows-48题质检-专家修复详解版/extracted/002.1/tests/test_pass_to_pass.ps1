#Requires -Version 5.1
<#
.SYNOPSIS
    Harbor pass_to_pass suite for task windows-d4-litemonitor-001.

.DESCRIPTION
    Runs the hidden evaluator (tests/LiteMonitor.Evaluator) in pass_to_pass mode and
    writes the machine-readable verdict to <ResultsDir>\suite_pass_to_pass.json plus a
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

$SuiteName = 'pass_to_pass'
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

$result = Invoke-Native -FilePath $evaluatorExeFull -Arguments $arguments -WorkingDirectory $evaluatorDir -TimeoutSeconds $TimeoutSeconds
Write-NativeResult -Result $result -StdOutPath $suiteLog -StdErrPath $suiteErr -Label "evaluator[$SuiteName]"

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
