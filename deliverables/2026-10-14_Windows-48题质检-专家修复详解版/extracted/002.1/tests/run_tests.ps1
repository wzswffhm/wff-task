#Requires -Version 5.1
<#
.SYNOPSIS
    Sole scoring entry point for Harbor task windows-d4-litemonitor-001 (E1).

.DESCRIPTION
    Performs, in order:
      1. environment readiness self-check (environment/validate_environment.ps1)
      2. purge of stale build output and machine state (fresh, idempotent start)
      3. offline restore + Release build of the repository under test
      4. build of the hidden evaluator against that build output
      5. FAIL_TO_PASS, PASS_TO_PASS and Windows SYSTEM_STATE suites
      6. machine-state cleanup and residue audit
      7. aggregation into results/result.json + junit.xml + system_state.json + test.log

    Scoring is entirely programmatic; there is no LLM/agent judge and result.json
    never carries a judge_score field.

    Exit codes (contract required by the delivery specification):
      0 = the run executed and produced a verdict. Test failures are expressed in
          results/result.json (status FAILED / RESOLVED), never by a crash.
      2 = INVALID. The runner, environment, API or evaluator failed and no verdict
          about the model can be derived. Such a run must be repeated and must not be
          counted as a model failure.

    A repository under test that does not COMPILE is scored on what the evaluator could
    still execute: the frozen baseline is proven to build in this very environment by
    environment/prepare.ps1, so a later compile error is attributable to the change under
    test and stays a model failure (status FAILED) as long as assertions actually ran.
    If the compile error leaves the evaluator with NOTHING to execute (tests_total = 0),
    the run carries no usable signal and is reported as INVALID (exit code 2) so that it
    is repeated instead of being counted as a valid zero - see task.toml
    [scoring].invalid_policy and aggregate_results.ps1 section 6a.

.PARAMETER RepoRoot
    Working tree handed to the agent; must contain LiteMonitor.csproj.
    Defaults to $env:HARBOR_REPO_ROOT.

.PARAMETER ResultsDir
    Where the unified results/ payload is written. Defaults to <WorkDir>\results.

.PARAMETER Suite
    'all' (the default, and the only mode that can decide RESOLVED) runs FAIL_TO_PASS,
    PASS_TO_PASS and SYSTEM_STATE. A single suite name runs only that suite, which is a
    scoped regression probe: the suites that were not requested are reported as
    NOT_REQUESTED instead of being counted as an infrastructure fault, so the run still
    exits 0 with a verdict and is never marked INVALID just because it was scoped.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File tests\run_tests.ps1 `
        -RepoRoot C:\ws\被测工程\repo -ResultsDir C:\ev\run1\results
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)][string]$RepoRoot,
    [Parameter(Mandatory = $false)][string]$ResultsDir,
    [Parameter(Mandatory = $false)][string]$WorkDir,
    [Parameter(Mandatory = $false)][string]$RunId,
    [Parameter(Mandatory = $false)][string]$RepoCommit = '',
    [Parameter(Mandatory = $false)][string]$BaseImageDigest = '',
    [Parameter(Mandatory = $false)][switch]$SkipReadiness,
    [Parameter(Mandatory = $false)][switch]$KeepWorkDir,
    [Parameter(Mandatory = $false)][int]$AgentBuildTimeoutSeconds = 1800,
    [Parameter(Mandatory = $false)][int]$EvaluatorBuildTimeoutSeconds = 900,
    [Parameter(Mandatory = $false)][int]$SuiteTimeoutSeconds = 900,
    [Parameter(Mandatory = $false)][ValidateSet('all', 'fail_to_pass', 'pass_to_pass', 'system_state')][string]$Suite = 'all'
)

$ErrorActionPreference = 'Stop'
$script:TestsDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$script:TaskDir = Split-Path -Parent $script:TestsDir
$script:EnvDir = Join-Path $script:TaskDir 'environment'
. (Join-Path $script:TestsDir 'harness_common.ps1')

function Write-BuildInfo {
    param(
        [bool]$AgentBuildOk,
        [int]$ErrorCount,
        [string]$Reason
    )
    $payload = [ordered]@{
        task_id                 = $TaskId
        run_id                  = $RunId
        repo_root               = $RepoRoot
        repo_commit             = $RepoCommit
        agent_build_ok          = $AgentBuildOk
        agent_build_error_count = $ErrorCount
        agent_build_reason      = $Reason
        agent_build_output      = $agentDll
        evaluator_build_ok      = $evaluatorBuildOk
        evaluator_exe           = $evaluatorOut
        offline_feed            = $feedDir
        offline_feed_packages   = $feedCount
        captured_at_utc         = [DateTime]::UtcNow.ToString('o')
    }
    Write-Utf8NoBom -Path (Join-Path $ResultsDir 'build_info.json') -Text ($payload | ConvertTo-Json -Depth 10)
}

function Finish-Run {
    param([string]$Status, [string]$Reason)
    # 早期中止同样必须收尾：先把本轮自建的临时工作目录处理掉并落盘 teardown.log，删不掉的
    # 故障并入 invalid_reason（此时 aggregate 还没跑，result.json 仍能如实带上）。
    $abortTeardown = Invoke-WorkDirTeardown -Phase 'early-abort'
    foreach ($fault in $abortTeardown.faults) { $Reason = ($Reason + ' | ' + $fault) }
    $aggregateScript = Join-Path $script:TestsDir 'aggregate_results.ps1'
    $psExeLocal = (Get-Process -Id $PID).Path
    $aggregateArgs = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $aggregateScript,
        '-ResultsDir', $ResultsDir,
        '-TaskId', $TaskId,
        '-TaskVersion', $TaskVersion,
        '-RunId', $RunId,
        '-RepoCommit', $RepoCommit,
        '-BaseImageDigest', $BaseImageDigest,
        '-BuildInfoPath', (Join-Path $ResultsDir 'build_info.json'),
        '-RequestedSuites', $Suite,
        '-InvalidReason', $Reason
    )
    $aggregate = Invoke-Native -FilePath $psExeLocal -Arguments $aggregateArgs -WorkingDirectory $script:TestsDir -TimeoutSeconds 600
    Write-NativeResult -Result $aggregate -StdOutPath (Join-Path $artifactsDir 'aggregate.log') -Label 'aggregate_results'
    Write-Host ([string]$aggregate.StdOut)
    Write-Host ''
    Write-Host "RESULT_JSON=$(Join-Path $ResultsDir 'result.json')"
    Write-Host "STATUS=$Status"
    Write-Host "INVALID_REASON=$Reason"
    exit 2
}

$script:AgentDll = ''
$script:AgentBuildOk = $false
$script:EvaluatorBuildOk = $false
$script:FeedDir = ''
$script:FeedCount = 0
$script:AgentBuildDir = ''
$script:EvaluatorBuildDir = ''

$runStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
if (-not $RunId) { $RunId = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff') }
if (-not $RepoRoot -and $env:HARBOR_REPO_ROOT) { $RepoRoot = $env:HARBOR_REPO_ROOT }
$script:AutoTempWorkDir = $false
if (-not $WorkDir) {
    if ($env:HARBOR_WORK_DIR) { $WorkDir = $env:HARBOR_WORK_DIR }
    else {
        $WorkDir = Join-Path ([System.IO.Path]::GetTempPath()) "harbor-litemonitor-$RunId"
        $script:AutoTempWorkDir = $true
    }
}
if (-not $ResultsDir) {
    if ($env:HARBOR_RESULTS_DIR) { $ResultsDir = $env:HARBOR_RESULTS_DIR }
    else { $ResultsDir = Join-Path $WorkDir 'results' }
}

$artifactsDir = Join-Path $ResultsDir 'artifacts'
New-DirectorySafe $ResultsDir | Out-Null
New-DirectorySafe $WorkDir | Out-Null
New-DirectorySafe $artifactsDir | Out-Null
$ResultsDir = (Resolve-Path -LiteralPath $ResultsDir).ProviderPath
$WorkDir = (Resolve-Path -LiteralPath $WorkDir).ProviderPath

$agentBuildDir = Join-Path $WorkDir 'agent-build'
$agentObj = Join-Path $agentBuildDir 'obj'
$agentBin = Join-Path $agentBuildDir 'bin'
# Non-ASCII on purpose: the evaluator has to run from a zh-CN install path so the
# Chinese-install-dir migration and path scenarios are genuinely exercised.
$evaluatorBuildDir = Join-Path $WorkDir '评测器'
$evaluatorObj = Join-Path $evaluatorBuildDir 'obj'
$evaluatorBin = Join-Path $evaluatorBuildDir 'bin'
$evaluatorOut = Join-Path (Join-Path (Join-Path $evaluatorBin 'Release') 'net8.0-windows') 'LiteMonitor.Evaluator.exe'

$invalidReasons = New-Object System.Collections.ArrayList
function Add-Invalid {
    param([string]$Reason)
    [void]$invalidReasons.Add($Reason)
    Write-Host "INVALID: $Reason"
}

# 收尾必须是「每条退出路径都走」的一件事，而不是主流程末尾的一段代码。KI-31 把 teardown 写在
# aggregate 之前的第 6b 节，但 Finish-Run（早期中止：RepoRoot 里没有 LiteMonitor.csproj、离线
# NuGet 源缺失、构建超时……）根本走不到第 6b 节，于是本轮在 %TEMP% 里自建的工作目录原样留在
# 机器上，而且既不写 artifacts/teardown.log、也不报任何故障——一次基础设施故障同时违反了甲方
# 4.5「结束后不得遗留临时状态」与「故障必须如实上报」。所以把这段逻辑收进一个幂等函数，由
# 第 6b 节、Finish-Run 与未预期错误的 trap 共同调用（见 KI-32）。
$script:TeardownDone = $false
$script:TeardownResult = $null

function Invoke-WorkDirTeardown {
    param(
        [Parameter(Mandatory = $true)][string]$Phase,
        [switch]$Escalate
    )
    if ($script:TeardownDone) { return $script:TeardownResult }
    $script:TeardownDone = $true
    $faults = New-Object System.Collections.ArrayList
    $retained = ''
    $partialRemoved = @()
    $tempRoot = ([System.IO.Path]::GetTempPath().TrimEnd('\') + '\')
    $resultsOutside = $ResultsDir -and (-not $ResultsDir.StartsWith($WorkDir + '\', [System.StringComparison]::OrdinalIgnoreCase))
    $ownTempDir = ($script:AutoTempWorkDir -and $WorkDir.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase))
    if (-not $ownTempDir) {
        # 调用方自己指定的工作目录（-WorkDir 或 HARBOR_WORK_DIR）：不是本轮自建的临时状态，
        # 一律不动，只如实记账。
        $retained = 'work-directory-supplied-by-caller'
    }
    elseif ($KeepWorkDir) {
        # 调用方显式要求保留：这是诊断开关，不是故障；判分调用不得使用它（见 KI-31）。
        $retained = 'requested-by-KeepWorkDir'
    }
    elseif ($resultsOutside) {
        # 三重护栏同时成立才整棵删：目录是本脚本自动生成的（调用方既没传 -WorkDir 也没有
        # HARBOR_WORK_DIR）、它确实位于系统临时目录之下、并且 ResultsDir 不在它里面。
        $lastError = ''
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            $lastError = ''
            try { Remove-TreeSafe $WorkDir } catch { $lastError = $_.Exception.Message }
            if (-not (Test-Path -LiteralPath $WorkDir)) { break }
            if ($attempt -lt 3) { Start-Sleep -Milliseconds 400 }
        }
        if (Test-Path -LiteralPath $WorkDir) {
            $suffix = ''
            if ($lastError) { $suffix = " : $lastError" }
            [void]$faults.Add("the evaluator working directory this run created under the system temp path is still present after 3 removal attempts ($WorkDir)$suffix")
        }
    }
    else {
        # ResultsDir 就在工作目录里面（默认 -ResultsDir = <WorkDir>\results）：整棵删掉等于删掉
        # 判分产物，所以 results 子树必须保留；但工作目录里其余的兄弟项（agent-build、评测器、
        # nuget-offline.config、wr-*）全是可重建的中间产物，也是本轮真正的大头，必须删干净，
        # 否则「早期中止 + 默认 ResultsDir」这条路仍然会在 %TEMP% 里留下几百 MB 临时状态。
        $retained = 'results-directory-inside-work-directory'
        if (Test-Path -LiteralPath $WorkDir) {
            foreach ($child in @(Get-ChildItem -LiteralPath $WorkDir -Force)) {
                if ([string]::Equals($child.FullName.TrimEnd('\'), $ResultsDir.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)) { continue }
                try { Remove-TreeSafe $child.FullName; $partialRemoved += $child.Name }
                catch { [void]$faults.Add("cannot remove $($child.FullName) that this run left under the system temp path : " + $_.Exception.Message) }
            }
        }
    }
    # reparse 探测不完整时 Remove-TreeSafe 已经失败关闭（见 KI-32）：真删不掉的情况会被上面的
    # 存在性核验抓成 fault；这里把探测故障如实落进 teardown.log 与 stdout，留下可审计痕迹，
    # 同时不在「目录其实已经删净」的情况下把一轮好结果误判成 INVALID。
    $inspectionFaults = @(Get-ReparseInspectionFaults -Clear)
    $lines = @(
        "# Harbor teardown report - $TaskId v$TaskVersion run=$RunId",
        "# generated at $([DateTime]::UtcNow.ToString('o'))",
        "phase=$Phase",
        "autoTempWorkDir=$($script:AutoTempWorkDir)",
        "keepWorkDir=$([bool]$KeepWorkDir)",
        "workDir=$WorkDir",
        "resultsDir=$ResultsDir",
        "resultsOutsideWorkDir=$resultsOutside",
        "ownTempWorkDir=$ownTempDir",
        "retained=$retained",
        "partialTeardownRemoved=$($partialRemoved -join ', ')",
        "teardownFaults=$($faults.Count)",
        "reparseInspectionFaults=$($inspectionFaults.Count)"
    )
    foreach ($fault in $faults) { $lines += "FAULT: $fault" }
    foreach ($fault in $inspectionFaults) { $lines += "REPARSE_INSPECTION_FAULT: $fault" }
    try {
        New-DirectorySafe $artifactsDir | Out-Null
        Write-Utf8NoBom -Path (Join-Path $artifactsDir 'teardown.log') -Text ($lines -join "`r`n")
    }
    catch { [void]$faults.Add("cannot write the teardown report under $artifactsDir : " + $_.Exception.Message) }
    # 故障一律同时打到 stdout：teardown.log 本身写不下去（磁盘满、artifacts 目录被占用、
    # 早期中止时还没建出来）时，调用方捕获的本脚本输出就是唯一还留着这份故障的地方。
    foreach ($fault in $faults) { Write-Host "TEARDOWN_FAULT: $fault" }
    foreach ($fault in $inspectionFaults) { Write-Host "REPARSE_INSPECTION_FAULT: $fault" }
    if ($Escalate) { foreach ($fault in $faults) { Add-Invalid $fault } }
    Write-Host "TEARDOWN_FAULTS=$($faults.Count) phase=$Phase retained=$retained partialRemoved=$($partialRemoved.Count) reparseInspectionFaults=$($inspectionFaults.Count)"
    $script:TeardownResult = [ordered]@{
        faults = @($faults); retained = $retained
        partial_removed = $partialRemoved; inspection_faults = $inspectionFaults
    }
    return $script:TeardownResult
}

trap {
    # 未预期的终止性错误同样不能把本轮自建的临时工作目录留在机器上。本脚本的退出码契约只有
    # 0（跑完并给出裁决）与 2（INVALID / 基础设施故障），所以这里如实按 2 退出。
    # 收尾自己再失败也绝不能吞掉：空 catch 会让「未预期错误 + 收尾失败」同时消失，机器上
    # 留下临时目录而输出里一个字都没有（见 KI-32 第二轮评审的 blocker）。
    $unhandledMessage = $_.Exception.Message
    try { [void](Invoke-WorkDirTeardown -Phase 'unhandled-error') }
    catch { Write-Host "TEARDOWN_FAULT: the unhandled-error teardown itself failed : $($_.Exception.Message)" }
    Write-Host "UNHANDLED_ERROR: $unhandledMessage"
    exit 2
}

Write-Banner 'run_tests'
Write-Host "runId=$RunId"
Write-Host "taskDir=$script:TaskDir"
Write-Host "repoRoot=$RepoRoot"
Write-Host "workDir=$WorkDir"
Write-Host "resultsDir=$ResultsDir"
Write-Host "suite=$Suite"

# Fresh start: previous results must not leak into this run.
foreach ($stale in @('result.json', 'junit.xml', 'system_state.json', 'test.log', 'build_info.json', 'cleanup_report.json',
                     'suite_fail_to_pass.json', 'suite_pass_to_pass.json', 'suite_system_state.json')) {
    $path = Join-Path $ResultsDir $stale
    if (Test-Path -LiteralPath $path) { [System.IO.File]::Delete($path) }
}

$psExe = (Get-Process -Id $PID).Path
$dotnet = Get-DotNetCli

# --------------------------------------------------------------------------- #
# 1. readiness
# --------------------------------------------------------------------------- #
if (-not $dotnet) { Add-Invalid 'the .NET SDK CLI (dotnet) was not found on PATH' }
# AP injects the verifier at C:\tests and mirrors only environment/ to
# C:\environment. The full task layout required by readiness lives under
# C:\harbor\task in the runtime image, so prefer that canonical copy.
$canonicalValidateScript = 'C:\harbor\task\environment\validate_environment.ps1'
$validateScript = if (Test-Path -LiteralPath $canonicalValidateScript) {
    $canonicalValidateScript
} else {
    Join-Path $script:EnvDir 'validate_environment.ps1'
}
if (-not $SkipReadiness) {
    if (-not (Test-Path -LiteralPath $validateScript)) {
        Add-Invalid "environment/validate_environment.ps1 is missing at $validateScript"
    }
    else {
        $readinessArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $validateScript, '-Quiet')
        $readiness = Invoke-Native -FilePath $psExe -Arguments $readinessArgs -WorkingDirectory $script:EnvDir -TimeoutSeconds 600
        Write-NativeResult -Result $readiness -StdOutPath (Join-Path $artifactsDir 'readiness.log') -Label 'validate_environment'
        if ($readiness.ExitCode -ne 0) { Add-Invalid "environment readiness check failed (exit=$($readiness.ExitCode)); see results/artifacts/readiness.log" }
    }
}

if (-not $RepoRoot) { Add-Invalid 'RepoRoot was not supplied (pass -RepoRoot or set HARBOR_REPO_ROOT)' }
elseif (-not (Test-Path -LiteralPath $RepoRoot)) { Add-Invalid "RepoRoot does not exist: $RepoRoot" }
else {
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
    $projectFile = Join-Path $RepoRoot 'LiteMonitor.csproj'
    if (-not (Test-Path -LiteralPath $projectFile)) { Add-Invalid "RepoRoot does not contain LiteMonitor.csproj: $RepoRoot" }
}

$feedDir = Join-Path (Join-Path $script:EnvDir 'assets') 'nuget'
if (-not (Test-Path -LiteralPath $feedDir)) {
    foreach ($imageFeed in @('C:\harbor\assets\nuget', 'C:\environment\assets\nuget')) {
        if (Test-Path -LiteralPath $imageFeed) { $feedDir = $imageFeed; break }
    }
}
if (-not (Test-Path -LiteralPath $feedDir)) { Add-Invalid "the vendored offline NuGet feed is missing at $feedDir" }
$feedCount = 0
if (Test-Path -LiteralPath $feedDir) { $feedCount = @(Get-ChildItem -LiteralPath $feedDir -Filter '*.nupkg' -File).Count }
if ($feedCount -lt 1) { Add-Invalid "the vendored offline NuGet feed at $feedDir holds no .nupkg file" }

if ($invalidReasons.Count -gt 0) {
    Write-BuildInfo -AgentBuildOk $false -ErrorCount 0 -Reason ($invalidReasons -join ' | ')
    Finish-Run -Status 'INVALID' -Reason ($invalidReasons -join ' | ')
}

Write-Host "offlineFeed=$feedDir ($feedCount packages)"

# --------------------------------------------------------------------------- #
# 2. clean slate
# --------------------------------------------------------------------------- #
$preClean = Clear-LiteMonitorMachineState
Write-Host "preRunCleanup=$($preClean | ConvertTo-Json -Compress -Depth 5)"
foreach ($stale in @($agentBuildDir, $evaluatorBuildDir)) {
    try { Remove-TreeSafe $stale } catch { Add-Invalid "cannot remove stale build output $stale : $($_.Exception.Message)" }
}
New-DirectorySafe $agentObj | Out-Null
New-DirectorySafe $agentBin | Out-Null

# --------------------------------------------------------------------------- #
# 3. offline restore + build of the repository under test
# --------------------------------------------------------------------------- #
$nugetConfig = Join-Path $WorkDir 'nuget-offline.config'
$nugetConfigText = @"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="harbor-offline" value="$feedDir" />
  </packageSources>
  <packageRestore>
    <add key="enabled" value="True" />
    <add key="automatic" value="False" />
  </packageRestore>
</configuration>
"@
Write-Utf8NoBom -Path $nugetConfig -Text $nugetConfigText

$projectFile = Join-Path $RepoRoot 'LiteMonitor.csproj'
$agentBuildOk = $false
$agentErrorCount = 0
$agentBuildReason = ''
$agentDll = ''
$agentBuildSeconds = 0.0

if ($RepoCommit -eq '' -and (Test-Path -LiteralPath (Join-Path $RepoRoot '.git'))) {
    $head = Invoke-Native -FilePath 'git' -Arguments @('-C', $RepoRoot, 'rev-parse', 'HEAD') -TimeoutSeconds 60
    if ($head.ExitCode -eq 0) { $RepoCommit = ([string]$head.StdOut).Trim() }
}

for ($attempt = 1; $attempt -le 2 -and -not $agentBuildOk; $attempt++) {
    if ($attempt -gt 1) {
        Write-Host "agent build attempt ${attempt}: clearing redirected obj/bin and retrying once to rule out a transient file lock"
        try { Remove-TreeSafe $agentBuildDir } catch { }
        New-DirectorySafe $agentObj | Out-Null
        New-DirectorySafe $agentBin | Out-Null
    }

    $restoreArgs = @(
        'restore', $projectFile,
        '--configfile', $nugetConfig,
        '--nologo', '-v', 'minimal',
        "-p:BaseIntermediateOutputPath=$agentObj\"
    )
    $restore = Invoke-Native -FilePath $dotnet -Arguments $restoreArgs -WorkingDirectory $RepoRoot -TimeoutSeconds $AgentBuildTimeoutSeconds
    Write-NativeResult -Result $restore -StdOutPath (Join-Path $artifactsDir "agent_restore_attempt$attempt.log") -StdErrPath (Join-Path $artifactsDir "agent_restore_attempt$attempt.err") -Label "dotnet restore (attempt $attempt)"

    $buildArgs = @(
        'build', $projectFile,
        '-c', 'Release', '--no-restore', '--nologo', '-v', 'minimal',
        "-p:BaseIntermediateOutputPath=$agentObj\",
        "-p:BaseOutputPath=$agentBin\",
        '-p:EnableWindowsTargeting=true'
    )
    $build = Invoke-Native -FilePath $dotnet -Arguments $buildArgs -WorkingDirectory $RepoRoot -TimeoutSeconds $AgentBuildTimeoutSeconds
    $buildLog = [string]$build.StdOut + "`r`n--- stderr ---`r`n" + [string]$build.StdErr
    Write-Utf8NoBom -Path (Join-Path $artifactsDir "agent_build_attempt$attempt.log") -Text $buildLog
    Write-NativeResult -Result $build -Label "dotnet build (attempt $attempt)"
    $agentBuildSeconds += [double]$build.Seconds + [double]$restore.Seconds

    if ($restore.TimedOut -or $build.TimedOut) {
        Add-Invalid "the build of the repository under test exceeded its ${AgentBuildTimeoutSeconds}s budget - infrastructure fault, not a model failure"
        Write-BuildInfo -AgentBuildOk $false -ErrorCount 0 -Reason ($invalidReasons -join ' | ')
        Finish-Run -Status 'INVALID' -Reason ($invalidReasons -join ' | ')
    }
    if ($restore.ExitCode -ne 0) {
        $agentBuildOk = $false
        $agentBuildReason = "offline restore failed with exit=$($restore.ExitCode)"
        continue
    }

    $agentErrorCount = Count-BuildErrors -Text $buildLog
    $candidateDll = Join-Path (Join-Path (Join-Path $agentBin 'Release') 'net8.0-windows') 'LiteMonitor.dll'
    if ($build.ExitCode -eq 0 -and $agentErrorCount -eq 0 -and (Test-Path -LiteralPath $candidateDll)) {
        $agentBuildOk = $true
        $agentDll = $candidateDll
        $agentBuildReason = ''
    }
    else {
        $agentBuildOk = $false
        $agentBuildReason = "compile failed: exit=$($build.ExitCode) errors=$agentErrorCount LiteMonitor.dll=$(Test-Path -LiteralPath $candidateDll)"
    }
}

# A model whose repository does not compile is a MODEL FAILURE (FAILED, reward=0), never an
# infrastructure fault. $agentDll stays '' in that case, so it must not be handed to
# Split-Path (which rejects an empty -Path and would abort the script with exit code 1,
# outside the frozen 0/2 contract). $targetRepoOut is only consumed inside `if ($agentBuildOk)`.
$targetRepoOut = ''
if ($agentDll -ne '') { $targetRepoOut = Split-Path -Parent $agentDll }
Write-Host "agentBuildOk=$agentBuildOk errors=$agentErrorCount dll=$agentDll"
if (-not $agentBuildOk) { Write-Host "agentBuildFailure=$agentBuildReason" }
Write-BuildInfo -AgentBuildOk $agentBuildOk -ErrorCount $agentErrorCount -Reason $agentBuildReason

# --------------------------------------------------------------------------- #
# 4. build the hidden evaluator against the agent build output
# --------------------------------------------------------------------------- #
$suiteExitCodes = @{}
$evaluatorBuildOk = $false
if ($agentBuildOk) {
    $evaluatorProject = Join-Path $script:TestsDir 'LiteMonitor.Evaluator\LiteMonitor.Evaluator.csproj'
    if (-not (Test-Path -LiteralPath $evaluatorProject)) {
        Add-Invalid "the hidden evaluator project is missing at $evaluatorProject"
    }
    else {
        $evalBuildArgs = @(
            'build', $evaluatorProject,
            '-c', 'Release', '--nologo', '-v', 'minimal',
            "-p:TargetRepoOut=$targetRepoOut",
            "-p:RestoreConfigFile=$nugetConfig",
            "-p:BaseIntermediateOutputPath=$evaluatorObj\",
            "-p:BaseOutputPath=$evaluatorBin\",
            '-p:EnableWindowsTargeting=true'
        )
        $evalBuild = Invoke-Native -FilePath $dotnet -Arguments $evalBuildArgs -WorkingDirectory $script:TestsDir -TimeoutSeconds $EvaluatorBuildTimeoutSeconds
        $evalLog = [string]$evalBuild.StdOut + "`r`n--- stderr ---`r`n" + [string]$evalBuild.StdErr
        Write-Utf8NoBom -Path (Join-Path $artifactsDir 'evaluator_build.log') -Text $evalLog
        Write-NativeResult -Result $evalBuild -Label 'dotnet build (evaluator)'
        if ($evalBuild.TimedOut) { Add-Invalid "building the evaluator exceeded its ${EvaluatorBuildTimeoutSeconds}s budget" }
        $evalErrors = Count-BuildErrors -Text $evalLog
        if ($evalBuild.ExitCode -eq 0 -and $evalErrors -eq 0 -and (Test-Path -LiteralPath $evaluatorOut)) {
            $evaluatorBuildOk = $true
        }
        else {
            Add-Invalid "the hidden evaluator failed to build (exit=$($evalBuild.ExitCode) errors=$evalErrors exe=$(Test-Path -LiteralPath $evaluatorOut)); this is a harness fault, see results/artifacts/evaluator_build.log"
        }
    }
}

# build_info.json was last written before the evaluator was built, so evaluator_build_ok
# stayed frozen at false even on a fully green run and contradicted status=RESOLVED.
# Refresh it now that both build verdicts are known.
Write-BuildInfo -AgentBuildOk $agentBuildOk -ErrorCount $agentErrorCount -Reason $agentBuildReason

if ($evaluatorBuildOk) {
    # Stage the product resources the evaluator needs next to its own binary.
    $resourceRoot = Join-Path $RepoRoot 'resources'
    $staged = 0
    foreach ($name in @('lang', 'themes', 'plugins')) {
        $source = Join-Path $resourceRoot $name
        if (Test-Path -LiteralPath $source) {
            $destination = Join-Path (Join-Path $evaluatorOut '..') "resources\$name"
            $destinationParent = Join-Path (Split-Path -Parent $evaluatorOut) 'resources'
            New-DirectorySafe $destinationParent | Out-Null
            Copy-Item -LiteralPath $source -Destination $destinationParent -Recurse -Force
            $staged++
        }
    }
    Write-Host "stagedResourceGroups=$staged"
    $zhPack = Join-Path (Join-Path (Split-Path -Parent $evaluatorOut) 'resources\lang') 'zh.json'
    if (-not (Test-Path -LiteralPath $zhPack)) {
        Add-Invalid "the zh language pack could not be staged next to the evaluator (expected $zhPack); LanguageManager assertions would be meaningless"
    }
}

# --------------------------------------------------------------------------- #
# 5. suites
# --------------------------------------------------------------------------- #
$suitesToRun = @('fail_to_pass', 'pass_to_pass', 'system_state')
if ($Suite -ne 'all') { $suitesToRun = @($Suite) }

if ($evaluatorBuildOk -and $invalidReasons.Count -eq 0) {
    foreach ($suiteName in $suitesToRun) {
        $suiteScript = Join-Path $script:TestsDir "test_$suiteName.ps1"
        if (-not (Test-Path -LiteralPath $suiteScript)) {
            Add-Invalid "tests/test_$suiteName.ps1 is missing at $suiteScript"
            continue
        }
        $suiteArgs = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $suiteScript,
            '-EvaluatorExe', $evaluatorOut,
            '-ResultsDir', $ResultsDir,
            '-WorkDir', $WorkDir,
            '-RunId', $RunId,
            '-TargetRepoOut', $targetRepoOut,
            '-RepoCommit', $RepoCommit,
            '-TimeoutSeconds', "$SuiteTimeoutSeconds"
        )
        $suiteRun = Invoke-Native -FilePath $psExe -Arguments $suiteArgs -WorkingDirectory $script:TestsDir -TimeoutSeconds ($SuiteTimeoutSeconds + 300)
        Write-NativeResult -Result $suiteRun `
            -StdOutPath (Join-Path $artifactsDir "suite_$suiteName.driver.log") `
            -StdErrPath (Join-Path $artifactsDir "suite_$suiteName.driver.err") `
            -Label "test_$suiteName"
        $suiteExitCodes[$suiteName] = $suiteRun.ExitCode
        if ($suiteRun.TimedOut) { Add-Invalid "test_$suiteName exceeded its budget" }
        elseif ($suiteRun.ExitCode -eq 2) { Add-Invalid "test_$suiteName reported INVALID (exit=2); see results/artifacts/suite_$suiteName.driver.log" }
        elseif ($suiteRun.ExitCode -ne 0) { Add-Invalid "test_$suiteName terminated abnormally with exit=$($suiteRun.ExitCode)" }
    }
}

# --------------------------------------------------------------------------- #
# 6. cleanup + residue audit
# --------------------------------------------------------------------------- #
$postClean = Clear-LiteMonitorMachineState -InstallDirectory (Split-Path -Parent $evaluatorOut)
$residue = Get-LiteMonitorResidue -InstallDirectory (Split-Path -Parent $evaluatorOut)
$cleanupPayload = [ordered]@{
    task_id           = $TaskId
    task_version      = $TaskVersion
    run_id            = $RunId
    captured_at_utc   = [DateTime]::UtcNow.ToString('o')
    pre_run_cleanup   = $preClean
    post_run_cleanup  = $postClean
    registry_root     = "HKCU\$($script:RegistryRootSubKey)"
    registry_view     = 'Registry64'
    store_directory   = (Get-LocalAppDataStoreDirectory)
    residue_count     = $residue.residue_count
    residue_detail    = @($residue.residue_detail)
    conclusion        = $(if ([int]$residue.residue_count -eq 0) { 'ZERO_RESIDUE' } else { 'RESIDUE_PRESENT' })
}
Write-Utf8NoBom -Path (Join-Path $ResultsDir 'cleanup_report.json') -Text ($cleanupPayload | ConvertTo-Json -Depth 12)
Write-Host "residueCount=$($residue.residue_count) conclusion=$($cleanupPayload.conclusion)"

# --------------------------------------------------------------------------- #
# 6b. teardown of the working directory this run created for itself
# --------------------------------------------------------------------------- #
# 这一节必须发生在 aggregate 之前。cleanup_report.json 会被 aggregate_results.ps1 读走并
# 折算成 G_zero_residue 闸门，所以那份载荷一个字段都不能再动；但「这一轮有没有把自己在
# %TEMP% 里建的工作目录收干净」必须能影响本轮裁决，否则一次删除失败（目录被 MSBuild 节点、
# 杀软或索引服务短暂占用）就会在自报 ZERO_RESIDUE 的同时把 harbor-litemonitor-<RunId> 留在
# 机器上，与甲方 4.5「结束后不得遗留临时状态」直接冲突。口径与本脚本第 2 节对陈旧构建目录的
# 处理完全一致：删不掉就是基础设施故障，走 Add-Invalid -> result.json status=INVALID ->
# 退出码 2，本轮被排除并必须补跑，既不会被当成模型失败，也不可能带着遗留目录被计分。
# -Escalate：这一节在 aggregate 之前，删不掉的故障还能影响本轮裁决（Add-Invalid ->
# result.json#status=INVALID -> 退出码 2）。早期中止与 trap 走的是同一个函数、同一套护栏与
# 同一份 teardown.log，只是不再重复升级（那两条路径本来就已经是 INVALID）。
$teardown = Invoke-WorkDirTeardown -Phase 'pre-aggregate' -Escalate
$teardownRetained = $teardown.retained
$teardownFaults = $teardown.faults


# --------------------------------------------------------------------------- #
# 7. aggregate + unified test.log
# --------------------------------------------------------------------------- #
$logParts = New-Object System.Text.StringBuilder
[void]$logParts.AppendLine("# Harbor test.log - $TaskId v$TaskVersion run=$RunId")
[void]$logParts.AppendLine("# generated at $([DateTime]::UtcNow.ToString('o'))")
[void]$logParts.AppendLine("# repoRoot=$RepoRoot")
[void]$logParts.AppendLine("# repoCommit=$RepoCommit")
[void]$logParts.AppendLine("# agentBuildOk=$agentBuildOk errors=$agentErrorCount")
[void]$logParts.AppendLine("# evaluatorBuildOk=$evaluatorBuildOk")
[void]$logParts.AppendLine('')
foreach ($entry in @(
        @('readiness.log', 'validate_environment.ps1'),
        @('agent_restore_attempt1.log', 'dotnet restore (attempt 1)'),
        @('agent_build_attempt1.log', 'dotnet build repository under test (attempt 1)'),
        @('agent_restore_attempt2.log', 'dotnet restore (attempt 2)'),
        @('agent_build_attempt2.log', 'dotnet build repository under test (attempt 2)'),
        @('evaluator_build.log', 'dotnet build hidden evaluator'),
        @('suite_fail_to_pass.driver.log', 'test_fail_to_pass.ps1 driver'),
        @('suite_fail_to_pass.log', 'evaluator suite fail_to_pass'),
        @('suite_pass_to_pass.driver.log', 'test_pass_to_pass.ps1 driver'),
        @('suite_pass_to_pass.log', 'evaluator suite pass_to_pass'),
        @('suite_system_state.driver.log', 'test_system_state.ps1 driver'),
        @('suite_system_state.log', 'evaluator suite system_state')
    )) {
    $candidate = Join-Path $artifactsDir $entry[0]
    if (-not (Test-Path -LiteralPath $candidate)) { $candidate = Join-Path $ResultsDir $entry[0] }
    if (Test-Path -LiteralPath $candidate) {
        [void]$logParts.AppendLine("===== BEGIN $($entry[1]) [$candidate] =====")
        [void]$logParts.AppendLine((Read-Utf8 $candidate))
        [void]$logParts.AppendLine("===== END $($entry[1]) =====")
        [void]$logParts.AppendLine('')
    }
}
$redacted = [regex]::Replace($logParts.ToString(), 'sk-[A-Za-z0-9_\-]{6,}', '[REDACTED_API_KEY]')
$redacted = [regex]::Replace($redacted, '(?i)(api[_-]?key|authorization|bearer)["'']?\s*[:=]\s*\S+', '$1=[REDACTED]')
Write-Utf8NoBom -Path (Join-Path $ResultsDir 'test.log') -Text $redacted

$aggregateScript = Join-Path $script:TestsDir 'aggregate_results.ps1'
$aggregateArgs = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $aggregateScript,
    '-ResultsDir', $ResultsDir,
    '-RubricPath', (Join-Path $script:TestsDir 'rubric.json'),
    '-TaskId', $TaskId,
    '-TaskVersion', $TaskVersion,
    '-RunId', $RunId,
    '-RepoCommit', $RepoCommit,
    '-BaseImageDigest', $BaseImageDigest,
    '-BuildInfoPath', (Join-Path $ResultsDir 'build_info.json'),
    '-RequestedSuites', $Suite
)
if ($invalidReasons.Count -gt 0) { $aggregateArgs += @('-InvalidReason', ($invalidReasons -join ' | ')) }
$aggregate = Invoke-Native -FilePath $psExe -Arguments $aggregateArgs -WorkingDirectory $script:TestsDir -TimeoutSeconds 600
Write-NativeResult -Result $aggregate -StdOutPath (Join-Path $artifactsDir 'aggregate.log') -Label 'aggregate_results'
Write-Host ''
Write-Host ([string]$aggregate.StdOut)

# 自己创建的 %TEMP% 工作目录已经在第 6b 节（aggregate 之前）删除并核验过，删不掉会走
# Add-Invalid 把本轮判成 INVALID；这里只负责清掉可能还剩下的构建目录。此时工作目录很可能
# 已经不存在，Remove-TreeSafe 对不存在的路径是 no-op。失败不再被静默吞掉，而是如实追加到
# artifacts/teardown.log 与 stdout——这一节在 aggregate 之后，已经不能也不应该再改变本轮裁决。
$postAggregateFaults = New-Object System.Collections.ArrayList
if (-not $KeepWorkDir) {
    foreach ($stale in @($agentBuildDir, $evaluatorBuildDir, (Join-Path $WorkDir 'wr-fail_to_pass'), (Join-Path $WorkDir 'wr-pass_to_pass'), (Join-Path $WorkDir 'wr-system_state'))) {
        try { Remove-TreeSafe $stale }
        catch { [void]$postAggregateFaults.Add("cannot remove the stale build directory $stale : " + $_.Exception.Message) }
    }
    foreach ($fault in @(Get-ReparseInspectionFaults -Clear)) {
        [void]$postAggregateFaults.Add("reparse point inspection did not complete while removing the stale build directories : $fault")
    }
}
if ($postAggregateFaults.Count -gt 0) {
    $teardownLogPath = Join-Path $artifactsDir 'teardown.log'
    $existingTeardown = '# Harbor teardown report'
    if (Test-Path -LiteralPath $teardownLogPath) { $existingTeardown = Read-Utf8 $teardownLogPath }
    $mergedTeardown = @($existingTeardown)
    foreach ($fault in $postAggregateFaults) {
        $mergedTeardown += "POST_AGGREGATE_FAULT: $fault"
        Write-Host "TEARDOWN_FAULT=$fault"
    }
    Write-Utf8NoBom -Path $teardownLogPath -Text ($mergedTeardown -join "`r`n")
}
Write-Host "POST_AGGREGATE_TEARDOWN_FAULTS=$($postAggregateFaults.Count)"


$runStopwatch.Stop()
$finalStatus = 'FAILED'
$resultPath = Join-Path $ResultsDir 'result.json'
$aggregateInvalidReason = ''
if (Test-Path -LiteralPath $resultPath) {
    try {
        $parsed = (Read-Utf8 $resultPath) | ConvertFrom-Json
        if ($parsed.status) { $finalStatus = [string]$parsed.status }
        if ($parsed.invalid_reason) { $aggregateInvalidReason = [string]$parsed.invalid_reason }
    }
    catch { }
}
if ($invalidReasons.Count -gt 0) { $finalStatus = 'INVALID' }
# aggregate_results.ps1 owns the zero-tests gate (section 6a); when it turns the run
# INVALID this script has no local reason of its own, so surface the aggregated one
# instead of printing an empty INVALID_REASON.
if ($finalStatus -eq 'INVALID' -and $invalidReasons.Count -eq 0 -and $aggregateInvalidReason) {
    [void]$invalidReasons.Add($aggregateInvalidReason)
}

Write-Host ''
Write-Host "totalSeconds=$([Math]::Round($runStopwatch.Elapsed.TotalSeconds, 3))"
Write-Host "RESULT_JSON=$resultPath"
Write-Host "STATUS=$finalStatus"
if ($finalStatus -eq 'INVALID') {
    Write-Host "INVALID_REASON=$($invalidReasons -join ' | ')"
    exit 2
}
exit 0
