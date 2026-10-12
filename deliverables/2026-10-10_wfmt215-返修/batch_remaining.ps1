# batch_remaining.ps1 —— wfflab__wfmt-215 (v2.1.0) 剩余轮次串联
#
# QWEN×3 已跑完（全 verdict=0），本批次补：
#   nop×3 → oracle×3（控制轮）→ OPUS×3 → KIMI×1 → GLM×1
# 每阶段都走 run_rounds.ps1 的 INVALID 自动重跑（Windows 容器 bind mount 偶发失效）。

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$base    = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-10_wfmt215-返修'
$runner  = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修\run_rounds.ps1'
$task    = Join-Path $base 'build\outside_harbor-assets\wfflab__wfmt-215'
$logRoot = Join-Path $base 'evidence\model-runs'
$taskId  = 'wfflab__wfmt-215'

$stages = @(
    @{ Name = 'nop';    Mode = 'no-change'; Models = '';     Target = 3; Tag = 'nop-v210' },
    @{ Name = 'oracle'; Mode = 'golden';    Models = '';     Target = 3; Tag = 'oracle-v210' },
    @{ Name = 'opus';   Mode = 'candidate'; Models = 'OPUS'; Target = 3; Tag = 'opus-v210' },
    @{ Name = 'kimi';   Mode = 'candidate'; Models = 'KIMI'; Target = 1; Tag = 'kimi-v210' },
    @{ Name = 'glm';    Mode = 'candidate'; Models = 'GLM';  Target = 1; Tag = 'glm-v210' }
)

$report = New-Object System.Collections.ArrayList
foreach ($stage in $stages) {
    $started = Get-Date -Format 'HH:mm:ss'
    Write-Host ""
    Write-Host "=== STAGE $($stage.Name) start $started ==="
    & $runner -Mode $stage.Mode -Models $stage.Models -Target $stage.Target `
        -Task $task -TaskId $taskId -LogRoot $logRoot -Tag $stage.Tag -MaxAttempts 8
    $code = $LASTEXITCODE
    [void]$report.Add("$($stage.Name) -> exit=$code (start $started, end $(Get-Date -Format 'HH:mm:ss'))")
    Write-Host "=== STAGE $($stage.Name) end exit=$code ==="
}

Write-Host ""
Write-Host "===== BATCH SUMMARY (wfmt-215 v2.1.0) ====="
$report | ForEach-Object { Write-Host "  $_" }
if (@($report | Where-Object { $_ -match 'exit=1' }).Count -gt 0) { exit 1 }
exit 0
