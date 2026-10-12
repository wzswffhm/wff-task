# batch_remaining.ps1 —— 串联跑完 216 v1.2.0 的剩余全部轮次
#
# 顺序：先控制轮（快，且能立刻验证 1.2.0 判分链路），再模型轮。
# 每一阶段都走 run_rounds.ps1 的 INVALID 自动重跑逻辑。
# 某一阶段失败不会中断后续阶段，结束时汇总各阶段 exit code。

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$base = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修'
$stages = @(
    @{ Name = 'nop';    Args = @{ Mode = 'no-change'; Target = 3; Tag = 'nop-v120' } },
    @{ Name = 'oracle'; Args = @{ Mode = 'golden';    Target = 3; Tag = 'oracle-v120' } },
    @{ Name = 'opus';   Args = @{ Mode = 'candidate'; Models = 'OPUS'; Target = 3; Tag = 'opus-v120' } },
    @{ Name = 'kimi';   Args = @{ Mode = 'candidate'; Models = 'KIMI'; Target = 1; Tag = 'kimi-v120' } },
    @{ Name = 'glm';    Args = @{ Mode = 'candidate'; Models = 'GLM';  Target = 1; Tag = 'glm-v120' } }
)

$report = New-Object System.Collections.ArrayList
foreach ($stage in $stages) {
    $started = Get-Date -Format 'HH:mm:ss'
    Write-Host ""
    Write-Host "=== STAGE $($stage.Name) start $started ==="
    & (Join-Path $base 'run_rounds.ps1') -Mode $stage.Args.Mode -Models $stage.Args.Models `
        -Target $stage.Args.Target -Tag $stage.Args.Tag -MaxAttempts 8
    $code = $LASTEXITCODE
    [void]$report.Add("$($stage.Name) -> exit=$code (start $started, end $(Get-Date -Format 'HH:mm:ss'))")
    Write-Host "=== STAGE $($stage.Name) end exit=$code ==="
}

Write-Host ""
Write-Host "===== BATCH SUMMARY ====="
$report | ForEach-Object { Write-Host "  $_" }
if (@($report | Where-Object { $_ -match 'exit=1' }).Count -gt 0) { exit 1 }
exit 0
