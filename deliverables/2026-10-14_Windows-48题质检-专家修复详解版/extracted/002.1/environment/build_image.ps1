#Requires -Version 5.1
<#
.SYNOPSIS
    Build-time orchestrator for the two Harbor images of windows-d4-litemonitor-001.

.DESCRIPTION
    `RUN powershell -Command "& { ... }"` inside a Dockerfile whose SHELL is already
    powershell means the same line is parsed twice, and any non-trivial script block
    dies on quoting rather than on a real fault. This script exists so each Dockerfile
    RUN is a single `-File` invocation with no nested quoting at all, and so the exact
    same sequence can be re-run by hand on the host to reproduce a build step.

    -Role agent   (environment/Dockerfile)
        1. environment/image_stamp.ps1 -Write   freeze the agent-visible input fingerprint
        2. hard no-leakage assertion            tests/ solution/ metadata/ evidence/ must be
                                                absent, and no judge or reference-solution
                                                file may exist anywhere under the task root
        3. environment/validate_environment.ps1 -Scope agent
        4. environment/prepare.ps1              materialise the frozen baseline and prove it
                                                builds completely offline
        5. environment/run.ps1 -Mode smoke      prove the artifact is a loadable net8.0-windows
                                                managed assembly
        6. drop the throw-away prebuild tree and run environment/cleanup.ps1

    -Role scorer  (environment/Dockerfile.scorer)
        1. environment/image_stamp.ps1 -Assert  prove the inherited Agent layer is exactly the
                                                frozen one; a drifted layer fails the build
        2. environment/validate_environment.ps1 -Scope scorer

    Every step propagates its real exit code. Any non-zero step aborts the image build.

.OUTPUTS
    Exit code 0 = every build step succeeded.
    Exit code 2 = a build step failed (the image must not be produced).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File environment\build_image.ps1 -Role agent
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)][ValidateSet('agent', 'scorer')][string]$Role = 'agent',
    [Parameter(Mandatory = $false)][string]$WorkspaceRoot,
    [Parameter(Mandatory = $false)][string]$RepoRoot,
    [Parameter(Mandatory = $false)][int]$TimeoutSeconds = 3600
)

$ErrorActionPreference = 'Stop'
$script:EnvDir = $PSScriptRoot
. (Join-Path $script:EnvDir 'env_common.ps1')

$script:TaskRoot = $script:TaskDir
$psExe = (Get-Process -Id $PID).Path

Write-Banner "build_image ($Role)"
Write-Host "taskRoot=$script:TaskRoot"
Write-Host "imageRole=$Role taskVersion=$script:TaskVersion"

function Invoke-Step {
    param([string]$Name, [string]$Script, [string[]]$StepArgs)
    $path = Join-Path $script:EnvDir $Script
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "BUILD_STEP_FAILED=$Name ($Script is missing at $path)"
        exit 2
    }
    $argv = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', $path) + $StepArgs
    $result = Invoke-Native -FilePath $psExe -Arguments $argv -WorkingDirectory $script:EnvDir -TimeoutSeconds $TimeoutSeconds
    $out = ([string]$result.StdOut)
    if ($out.Trim() -ne '') { Write-Host $out.TrimEnd() }
    $err = ([string]$result.StdErr)
    if ($err.Trim() -ne '') { Write-Host $err.TrimEnd() }
    if ($result.ExitCode -ne 0) {
        Write-Host ("BUILD_STEP_FAILED={0} ({1} exit={2} seconds={3})" -f $Name, $Script, $result.ExitCode, $result.Seconds)
        exit 2
    }
    Write-Host ("BUILD_STEP_OK={0} (seconds={1})" -f $Name, $result.Seconds)
    return $out
}

if ($Role -eq 'scorer') {
    $expected = ([string]$env:HARBOR_AGENT_IMAGE_FINGERPRINT).Trim()
    if ($expected -notmatch '^[0-9a-fA-F]{64}$') {
        Write-Host "BUILD_STEP_FAILED=agent_layer_fingerprint (HARBOR_AGENT_IMAGE_FINGERPRINT is not a 64-hex digest: '$expected')"
        exit 2
    }
    [void](Invoke-Step 'agent_layer_fingerprint' 'image_stamp.ps1' @('-Assert', $expected))
    [void](Invoke-Step 'readiness_scorer' 'validate_environment.ps1' @('-Scope', 'scorer'))
    Write-Host ''
    Write-Host "BUILD_IMAGE_ROLE=scorer OK=1"
    exit 0
}

# --------------------------------------------------------------------------- #
# agent
# --------------------------------------------------------------------------- #
[void](Invoke-Step 'freeze_input_fingerprint' 'image_stamp.ps1' @('-Write'))

# Hard no-leakage assertion. 甲方 2026-09-09 复核整改项 ①：solution/ 与 tests/ 绝不进入
# Agent 镜像。这里让镜像构建本身成为证据 —— 命中即 throw，镜像根本不会产出。
$leaks = @()
foreach ($dir in @('tests', 'solution', 'metadata', 'evidence')) {
    $candidate = Join-Path $script:TaskRoot $dir
    if (Test-Path -LiteralPath $candidate) { $leaks += ($dir + '\') }
}
$judgeOrSolutionNames = @('run_tests.ps1', 'aggregate_results.ps1', 'harness_common.ps1', 'rubric.json',
                          'reference.patch', 'solve.ps1', 'golden.patch', 'solution.diff',
                          'test_fail_to_pass.ps1', 'test_pass_to_pass.ps1', 'test_system_state.ps1')
foreach ($name in $judgeOrSolutionNames) {
    $hits = @(Get-ChildItem -LiteralPath $script:TaskRoot -Recurse -File -Filter $name -Force -ErrorAction SilentlyContinue)
    foreach ($hit in $hits) { $leaks += $hit.FullName }
}
if ($leaks.Count -gt 0) {
    Write-Host ("AGENT_IMAGE_LEAKAGE={0} offending path(s): {1}" -f $leaks.Count, ($leaks -join ', '))
    Write-Host 'BUILD_STEP_FAILED=no_leakage_assertion'
    exit 2
}
Write-Host 'AGENT_IMAGE_NO_LEAKAGE=1 (tests/ solution/ metadata/ evidence/ absent and no judge or reference-solution file anywhere under the task root)'
Write-Host 'BUILD_STEP_OK=no_leakage_assertion'

[void](Invoke-Step 'readiness_agent' 'validate_environment.ps1' @('-Scope', 'agent'))

if (-not $WorkspaceRoot) { $WorkspaceRoot = $env:HARBOR_WORKSPACE_ROOT }
if (-not $WorkspaceRoot) { $WorkspaceRoot = 'C:\harbor\workspace' }
# 不从 $env:HARBOR_REPO_ROOT 取：Windows 容器会把 ENV 里的非 ASCII 值按 CP936 还原成乱码，
# 于是 tar.exe chdir 不到工作区。中文目录名 被测工程 由 env_common.ps1（UTF-8 带 BOM，
# Windows PowerShell 5.1 解码正确）里的 $script:AgentRepoRelative 提供。
if (-not $RepoRoot) { $RepoRoot = (Get-DefaultRepoRoot -WorkspaceRoot $WorkspaceRoot) }
$expectedLeaf = $script:AgentRepoRelative
if (-not $RepoRoot.EndsWith($expectedLeaf, [System.StringComparison]::Ordinal)) {
    Write-Host ("BUILD_STEP_FAILED=workspace_layout (repoRoot '$RepoRoot' does not end with the frozen layout '$expectedLeaf'; a non-ASCII workspace path that cannot round-trip is an infrastructure fault)")
    exit 2
}
Write-Host "repoRoot=$RepoRoot"

[void](Invoke-Step 'prepare_frozen_baseline' 'prepare.ps1' @('-WorkspaceRoot', $WorkspaceRoot, '-TimeoutSeconds', "$TimeoutSeconds"))
[void](Invoke-Step 'smoke_build_artifact' 'run.ps1' @('-RepoRoot', $RepoRoot, '-Mode', 'smoke'))

# The pre-build tree is throw-away; the runner rebuilds per run so no stale binary can
# ever leak into a verdict.
$prebuild = Join-Path (Split-Path -Parent $RepoRoot) 'prebuild'
if (Test-Path -LiteralPath $prebuild) {
    try { Remove-TreeSafe $prebuild } catch { Write-Host ("prebuild removal fault: " + $_.Exception.Message) }
}
Write-Host ("prebuildRemoved={0}" -f (-not (Test-Path -LiteralPath $prebuild)))
[void](Invoke-Step 'initial_machine_state_cleanup' 'cleanup.ps1' @('-Quiet'))

Write-Host ''
Write-Host "BUILD_IMAGE_ROLE=agent OK=1"
exit 0
