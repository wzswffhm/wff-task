# relaunch_all.ps1 —— 在 215 v2.1.1 / 216 v1.2.1 上重跑全部 14 轮（每包）
#
# 背景：本轮返修改动了 task.toml / environment/adapter.toml / tests/ / verifier/，
#       历史 jobs/ 的 task_checksum 与交付包 Harbor dirhash 不再一致（known_issues K28），
#       正式提交前必须在**同一份内容**上整批重跑对照组与模型轮次。
#
# 轮次计划（与 harbor 门禁一致）：
#   no-change x3   NOP 控制轮        （期望 0）
#   golden    x3   Oracle 控制轮     （期望 1）
#   OPUS      x3   主模型
#   QWEN      x3   主模型
#   KIMI      x1   辅助模型
#   GLM       x1   辅助模型
#
# 特性：
#   * 断点续跑：每步先统计 runs/<pkg>/ 下已存在的**有效**轮次（run_validity=VALID），
#     只补差额；重复执行不会重复烧模型额度。
#   * 复用 runner 自带的 run_rounds.ps1：单轮执行、verdict=INVALID 自动重跑，
#     因为 Windows 容器 bind mount 偶发失效会造成基础设施性 INVALID（非模型失败）。
#   * 串行执行：QWEN/GLM/KIMI 共用上游 key，并行会互相饿死。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File relaunch_all.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File relaunch_all.ps1 -Packages wfflab__wchunk-216

[CmdletBinding()]
param(
    [string[]]$Packages = @('wfflab__wchunk-216', 'wfflab__wfmt-215'),
    [string]$LogRoot = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\refit-215-216\relaunch-logs'
)

$ErrorActionPreference = 'Continue'

$runner = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner'
$runRounds = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\refit-215-216\run_rounds.ps1'
$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path -LiteralPath $dockerBin) { $env:Path = $dockerBin + ';' + $env:Path }
$env:DOCKER_CONTEXT = 'desktop-windows'

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$log = Join-Path $LogRoot 'relaunch-all.log'
$doneFlag = Join-Path $LogRoot 'relaunch.done'
$failFlag = Join-Path $LogRoot 'relaunch.failed'
Remove-Item -LiteralPath $doneFlag, $failFlag -Force -ErrorAction SilentlyContinue

function Write-Log {
    param([string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    Add-Content -LiteralPath $log -Value $line -Encoding UTF8
}

# 轮次计划：mode / 期望的 runner.label / 目标轮数 / 模型别名
# 甲方 2026-10-13 最新规则：不再要求 GLM / KIMI 轮次。
# 因此本编排只跑 控制组(no-change/golden) + 主模型(opus-5/qwen3.8-max-0902)。
# 216 在规则变更前已按旧口径跑完并上传（14 trial），不回退、不改写。
$plan = @(
    @{ Mode = 'no-change'; Label = 'no-change';        Target = 3; Models = '' },
    @{ Mode = 'golden';    Label = 'golden';           Target = 3; Models = '' },
    @{ Mode = 'candidate'; Label = 'opus-5';           Target = 3; Models = 'OPUS' },
    @{ Mode = 'candidate'; Label = 'qwen3.8-max-0902'; Target = 3; Models = 'QWEN' }
)

# 统计某包在 runs/<pkg>/ 下已存在的有效轮次（按 result.json 的 mode + runner.label 判定）
function Get-ValidCount {
    param([string]$Package, [string]$Mode, [string]$Label)
    $runsRoot = Join-Path $runner "runs\$Package"
    if (-not (Test-Path -LiteralPath $runsRoot)) { return 0 }
    $count = 0
    foreach ($run in Get-ChildItem -LiteralPath $runsRoot -Directory -ErrorAction SilentlyContinue) {
        if ($run.Name -like '_archive*') { continue }
        foreach ($labelDir in Get-ChildItem -LiteralPath $run.FullName -Directory -ErrorAction SilentlyContinue) {
            $rj = Join-Path $labelDir.FullName 'result.json'
            if (-not (Test-Path -LiteralPath $rj)) { continue }
            try { $doc = Get-Content -LiteralPath $rj -Raw | ConvertFrom-Json } catch { continue }
            if ([string]($doc.run_validity) -ne 'VALID') { continue }
            if ([string]($doc.mode) -ne $Mode) { continue }
            if ([string]($doc.runner.label) -ne $Label) { continue }
            $count++
        }
    }
    return $count
}

# 统计"已在跑但还没落 result.json"的轮次：重启编排时据此跳过，避免重复起轮
function Get-RunningCount {
    param([string]$Package, [string]$Mode, [string]$Label)
    $runsRoot = Join-Path $runner "runs\$Package"
    if (-not (Test-Path -LiteralPath $runsRoot)) { return 0 }
    $count = 0
    foreach ($run in Get-ChildItem -LiteralPath $runsRoot -Directory -ErrorAction SilentlyContinue) {
        if ($run.Name -like '_archive*') { continue }
        foreach ($labelDir in Get-ChildItem -LiteralPath $run.FullName -Directory -ErrorAction SilentlyContinue) {
            if ($labelDir.Name -ne $Label) { continue }
            if (Test-Path -LiteralPath (Join-Path $labelDir.FullName 'result.json')) { continue }
            if (((Get-Date) - $labelDir.LastWriteTime).TotalHours -lt 6) { $count++ }
        }
    }
    return $count
}
Write-Log ("relaunch start packages={0} pid={1}" -f ($Packages -join ','), $PID)

$failed = $false
foreach ($pkg in $Packages) {
    Write-Log "===== $pkg ====="
    foreach ($step in $plan) {
        $have = Get-ValidCount -Package $pkg -Mode $step.Mode -Label $step.Label
        $running = Get-RunningCount -Package $pkg -Mode $step.Mode -Label $step.Label
        $need = [int]$step.Target - [int]$have
        Write-Log ("  {0}/{1}: valid {2}/{3} running={4}" -f $step.Mode, $step.Label, $have, $step.Target, $running)
        if ($need -le 0) { Write-Log '    达标，跳过'; continue }
        if ($running -gt 0) {
            Write-Log "    已有 $running 轮在跑，跳过本步以免重复；等其结束后再跑一次本脚本即可补差额"
            continue
        }

        $tag = "$pkg-$($step.Mode)-$($step.Label)"
        Write-Log "    补跑 $need 轮 (tag=$tag) 开始 $(Get-Date -Format 'HH:mm:ss')"
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $callArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $runRounds,
                      '-Mode', $step.Mode, '-Target', $need,
                      '-Task', $pkg, '-TaskId', $pkg, '-LogRoot', $LogRoot, '-Tag', $tag)
        if ($step.Models) { $callArgs += @('-Models', $step.Models) }
        & $psExe @callArgs 2>&1 | Out-Null
        $code = $LASTEXITCODE
        $sw.Stop()
        Write-Log ("    退出码={0} 耗时={1:N0}s" -f $code, $sw.Elapsed.TotalSeconds)
        if ($code -ne 0) { $failed = $true }
    }
    Write-Log "===== $pkg 结束 ====="
}

Write-Log 'relaunch complete'
if ($failed) {
    Set-Content -LiteralPath $failFlag -Value ("partial failure at {0}" -f (Get-Date -Format o)) -Encoding UTF8
    exit 1
}
Set-Content -LiteralPath $doneFlag -Value (Get-Date -Format o) -Encoding UTF8
exit 0
