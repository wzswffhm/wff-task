# resume_215.ps1 —— 等待在跑的轮次结束后，把 215 缺的轮次补齐
#
# 背景：relaunch_all.ps1 在遇到"某 label 已有轮次在跑"时会跳过该步以免重复起轮，
#       跳过之后整个脚本就走完了。等那轮结束后需要再补差额，本脚本负责这件事：
#       循环检查 -> 若有在跑的轮次就等待 -> 没有在跑的但未达标就补跑。
#
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File resume_215.ps1

[CmdletBinding()]
param(
    [string]$Package = 'wfflab__wfmt-215',
    [string]$LogRoot = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\refit-215-216\relaunch-logs',
    [int]$PollSeconds = 120,
    [int]$MaxHours = 8
)

$ErrorActionPreference = 'Continue'
$runner = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner'
$runRounds = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\refit-215-216\run_rounds.ps1'
$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path -LiteralPath $dockerBin) { $env:Path = $dockerBin + ';' + $env:Path }
$env:DOCKER_CONTEXT = 'desktop-windows'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$log = Join-Path $LogRoot 'resume-215.log'

function Write-Log([string]$m) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Write-Host $line
    Add-Content -LiteralPath $log -Value $line -Encoding UTF8
}

# 甲方 2026-10-13 规则：GLM/Kimi 不再必需
$plan = @(
    @{ Mode = 'no-change'; Label = 'no-change';        Target = 3; Models = '' },
    @{ Mode = 'golden';    Label = 'golden';           Target = 3; Models = '' },
    @{ Mode = 'candidate'; Label = 'opus-5';           Target = 3; Models = 'OPUS' },
    @{ Mode = 'candidate'; Label = 'qwen3.8-max-0902'; Target = 3; Models = 'QWEN' }
)

function Get-Count([string]$Label, [string]$Kind) {
    $runsRoot = Join-Path $runner "runs\$Package"
    if (-not (Test-Path -LiteralPath $runsRoot)) { return 0 }
    $n = 0
    foreach ($run in Get-ChildItem -LiteralPath $runsRoot -Directory -ErrorAction SilentlyContinue) {
        if ($run.Name -like '_archive*') { continue }
        foreach ($labelDir in Get-ChildItem -LiteralPath $run.FullName -Directory -ErrorAction SilentlyContinue) {
            if ($labelDir.Name -ne $Label) { continue }
            $rj = Join-Path $labelDir.FullName 'result.json'
            if ($Kind -eq 'valid') {
                if (-not (Test-Path -LiteralPath $rj)) { continue }
                try { $doc = Get-Content -LiteralPath $rj -Raw | ConvertFrom-Json } catch { continue }
                if (([string]($doc.run_validity)) -eq 'VALID') { $n++ }
            } else {
                if (Test-Path -LiteralPath $rj) { continue }
                if (((Get-Date) - $labelDir.LastWriteTime).TotalHours -lt 6) { $n++ }
            }
        }
    }
    return $n
}

Write-Log "resume start package=$Package pid=$PID"
$deadline = (Get-Date).AddHours($MaxHours)

while ((Get-Date) -lt $deadline) {
    $waiting = $false
    $progressed = $false

    foreach ($step in $plan) {
        $valid = Get-Count -Label $step.Label -Kind 'valid'
        $running = Get-Count -Label $step.Label -Kind 'running'
        $need = [int]$step.Target - [int]$valid
        if ($need -le 0) { continue }
        if ($running -gt 0) {
            Write-Log ("  {0}: valid {1}/{2} running={3} -> 等待在跑的轮次结束" -f $step.Label, $valid, $step.Target, $running)
            $waiting = $true
            continue
        }
        Write-Log ("  {0}: valid {1}/{2} -> 补跑 {3} 轮" -f $step.Label, $valid, $step.Target, $need)
        $tag = "$Package-$($step.Mode)-$($step.Label)-resume"
        $callArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $runRounds,
                      '-Mode', $step.Mode, '-Target', $need,
                      '-Task', $Package, '-TaskId', $Package, '-LogRoot', $LogRoot, '-Tag', $tag)
        if ($step.Models) { $callArgs += @('-Models', $step.Models) }
        & $psExe @callArgs 2>&1 | Out-Null
        Write-Log ("    退出码={0}" -f $LASTEXITCODE)
        $progressed = $true
    }

    if (-not $waiting -and -not $progressed) {
        Write-Log '全部达标，退出'
        break
    }
    if (-not $waiting -and $progressed) {
        Write-Log '本轮已补跑，重新检查'
        continue
    }
    Start-Sleep -Seconds $PollSeconds
}

# 最终核对
Write-Log '最终核对：'
foreach ($step in $plan) {
    $v = Get-Count -Label $step.Label -Kind 'valid'
    Write-Log ("  {0}: {1}/{2}" -f $step.Label, $v, $step.Target)
}
Set-Content -LiteralPath (Join-Path $LogRoot 'resume-215.done') -Value (Get-Date -Format o) -Encoding UTF8
