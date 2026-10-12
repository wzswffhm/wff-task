# cleanup_failed_runs.ps1 —— 清理失效产出（**必须在批次跑完、无容器时执行**）
#
# 清理两处：
#   1. runner/runs/wfflab__wchunk-216/ 下 verdict=INVALID 或没有 result.json 的
#      半截 run 目录（bind mount 失效轮、被中断的轮）——这些没有有效证据，
#      且会污染按目录扫描的归档脚本；
#   2. runner/work/ 下全部中间副本（case/view，每份含 vendor 51MB）。
#
# 保留：所有 verdict 为 0/1 的有效轮、控制轮、evidence/ 日志与诊断证据。
#
# 用法：pwsh -NoProfile -File cleanup_failed_runs.ps1 [-WhatIf]

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$AlsoRemoveLegacyTaskVersion   # 额外删除 task_version=1.1.0 的旧题包轮次
)

$ErrorActionPreference = 'Stop'
$env:DOCKER_CONTEXT = 'desktop-windows'

$runner = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner'
$runsRoot = Join-Path $runner 'runs\wfflab__wchunk-216'
$workRoot = Join-Path $runner 'work'

# ---- 安全闸：必须没有在跑的容器 -------------------------------------------
$live = docker ps --format '{{.Image}} {{.Names}}' 2>$null
$mine = @($live | Where-Object { $_ -like 'outside-harbor/wfflab__wchunk-216*' })
if ($mine.Count -gt 0) {
    throw "refusing to clean: $($mine.Count) 216 container(s) still running -> $($mine -join '; ')"
}
Write-Host "OK: no running 216 container."

# ---- 1. 失效 run 目录 ------------------------------------------------------
$invalid = @()
$validNames = @()
foreach ($d in (Get-ChildItem $runsRoot -Directory -ErrorAction SilentlyContinue)) {
    $label = Get-ChildItem $d.FullName -Directory | Select-Object -First 1
    $json = if ($label) { Join-Path $label.FullName 'result.json' } else { $null }
    $keep = $false
    if ($json -and (Test-Path $json)) {
        try {
            $doc = Get-Content $json -Raw | ConvertFrom-Json
            if ([string]$doc.verdict -ne 'INVALID') { $keep = $true }
        } catch { $keep = $false }
    }
    if ($keep) { $validNames += $d.Name; continue }

    # 旧题包轮次（task_version 1.1.0）另行处理
    $ident = if ($label) { Join-Path $label.FullName 'task_identity.json' } else { $null }
    $legacy = $false
    if ($ident -and (Test-Path $ident)) {
        try { $legacy = ((Get-Content $ident -Raw | ConvertFrom-Json).task_version -eq '1.1.0') } catch {}
    }
    if ($legacy -and -not $AlsoRemoveLegacyTaskVersion) {
        $validNames += $d.Name   # 不当失效删，留给显式开关
        continue
    }
    $invalid += $d
}

Write-Host ("invalid/broken runs to delete: {0}" -f $invalid.Count)
foreach ($d in $invalid) { Write-Host ("  DEL {0}" -f $d.Name) }
Write-Host ("valid runs kept: {0}" -f $validNames.Count)
$validNames | Sort-Object | ForEach-Object { Write-Host ("  KEEP {0}" -f $_) }

if ($PSCmdlet.ShouldProcess("$($invalid.Count) run dirs", "Remove-Item")) {
    foreach ($d in $invalid) { Remove-Item $d.FullName -Recurse -Force -ErrorAction SilentlyContinue }
}

# ---- 2. 全部 work 中间副本 -------------------------------------------------
$workDirs = @(Get-ChildItem $workRoot -Directory -ErrorAction SilentlyContinue)
Write-Host ("work dirs to delete: {0}" -f $workDirs.Count)
if ($PSCmdlet.ShouldProcess("$($workDirs.Count) work dirs", "Remove-Item")) {
    foreach ($w in $workDirs) { Remove-Item $w.FullName -Recurse -Force -ErrorAction SilentlyContinue }
}

$leftRuns = @(Get-ChildItem $runsRoot -Directory -ErrorAction SilentlyContinue)
$leftWork = @(Get-ChildItem $workRoot -Directory -ErrorAction SilentlyContinue)
Write-Host ""
Write-Host ("after cleanup: runs={0}  work={1}" -f $leftRuns.Count, $leftWork.Count)
