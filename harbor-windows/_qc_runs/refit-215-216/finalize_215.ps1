# finalize_215.ps1 —— 215 收尾全流程（等待 -> 摘要 -> 自检修正上传 -> git 推送 -> 关机）
#
# 行为（按用户要求）：
#   * 先等 12 轮齐备；超时也继续往下走（记为失败原因之一）。
#   * **先生成跑分结果摘要**（summarize_215_runs.py），保证结果被如实记录。
#   * 再跑 finalize_215.py 做自检/修正/归档/打包/上传/索引。
#   * **无论前面成功还是失败**，都执行 git add/commit/push，
#     提交信息中包含 215 的完整跑分结果与本次收尾的实际状态。
#   * 最后**无条件关机**。
#
# 用法（脱离本会话，用计划任务启动）：
#   schtasks /Create /TN wff-finalize-215 /TR "powershell -File finalize_215.ps1" /SC ONCE /ST 23:59 /F

[CmdletBinding()]
param(
    [string]$Package = 'wfflab__wfmt-215',
    [string]$LogRoot = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\refit-215-216\relaunch-logs',
    [int]$PollSeconds = 180,
    [int]$MaxWaitHours = 12,
    [int]$ShutdownDelaySeconds = 300
)

$ErrorActionPreference = 'Continue'
$WS = 'C:\Users\Administrator\Desktop\wff-task'
$REFIT = Join-Path $WS 'harbor-windows\_qc_runs\refit-215-216'
$runner = Join-Path $WS 'deliverables\2026-10-04_outside-harbor-win\runner'
$py = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path -LiteralPath $dockerBin) { $env:Path = $dockerBin + ';' + $env:Path }
$env:DOCKER_CONTEXT = 'desktop-windows'

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$log = Join-Path $LogRoot 'finalize-215.log'
Remove-Item -LiteralPath (Join-Path $LogRoot 'finalize-215.done'), (Join-Path $LogRoot 'finalize-215.FAILED') -Force -ErrorAction SilentlyContinue

function Write-Log([string]$m) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Write-Host $line
    Add-Content -LiteralPath $log -Value $line -Encoding UTF8
}

$problems = New-Object System.Collections.ArrayList
Write-Log "finalize start package=$Package pid=$PID"

# ---------------------------------------------------------------- 阶段 1：等待 12 轮齐备
$need = @{ 'no-change' = 3; 'golden' = 3; 'opus-5' = 3; 'qwen3.8-max-0902' = 3 }
$deadline = (Get-Date).AddHours($MaxWaitHours)
$ready = $false

while ((Get-Date) -lt $deadline) {
    $found = @{}
    $runsRoot = Join-Path $runner "runs\$Package"
    if (Test-Path -LiteralPath $runsRoot) {
        foreach ($run in Get-ChildItem -LiteralPath $runsRoot -Directory -ErrorAction SilentlyContinue) {
            if ($run.Name -like '_archive*') { continue }
            foreach ($ld in Get-ChildItem -LiteralPath $run.FullName -Directory -ErrorAction SilentlyContinue) {
                $rj = Join-Path $ld.FullName 'result.json'
                if (-not (Test-Path -LiteralPath $rj)) { continue }
                try { $doc = Get-Content -LiteralPath $rj -Raw | ConvertFrom-Json } catch { continue }
                if (([string]($doc.run_validity)) -eq 'VALID') {
                    if (-not $found.ContainsKey($ld.Name)) { $found[$ld.Name] = 0 }
                    $found[$ld.Name] = $found[$ld.Name] + 1
                }
            }
        }
    }
    $missing = @()
    foreach ($label in $need.Keys) {
        $have = if ($found.ContainsKey($label)) { $found[$label] } else { 0 }
        if ($have -lt $need[$label]) { $missing += "$label $have/$($need[$label])" }
    }
    if ($missing.Count -eq 0) { $ready = $true; break }
    Write-Log ("  等待中：{0}" -f ($missing -join '; '))
    Start-Sleep -Seconds $PollSeconds
}

if ($ready) {
    Write-Log '轮次齐备（12 轮全 VALID）'
} else {
    Write-Log "!! 等待超时（$MaxWaitHours 小时）仍未集齐 12 轮"
    [void]$problems.Add('等待超时：12 轮未集齐')
}

# ---------------------------------------------------------------- 阶段 2：生成跑分摘要
Write-Log '生成 215 跑分结果摘要'
$sumOut = & $py -X utf8 (Join-Path $REFIT 'summarize_215_runs.py') 2>&1
$sumOut | ForEach-Object { Add-Content -LiteralPath $log -Value $_ -Encoding UTF8 }
$sumFile = Join-Path $REFIT '215-run-summary.md'
if (-not (Test-Path -LiteralPath $sumFile)) {
    Write-Log '!! 跑分摘要未生成'
    [void]$problems.Add('跑分摘要未生成')
}
$summaryText = if (Test-Path -LiteralPath $sumFile) { Get-Content -LiteralPath $sumFile -Raw -Encoding UTF8 } else { '(summary generation failed)' }

# ---------------------------------------------------------------- 阶段 3：收尾
Write-Log '调用 finalize_215.py'
$finOut = & $py -X utf8 (Join-Path $REFIT 'finalize_215.py') 2>&1
$finCode = $LASTEXITCODE
$finOut | ForEach-Object { Add-Content -LiteralPath $log -Value $_ -Encoding UTF8 }
if ($finCode -eq 0) {
    Write-Log 'finalize_215.py 成功'
    $finishState = '成功：自检/修正/归档/打包/上传飞书/索引同步全部完成'
} else {
    Write-Log "!! finalize_215.py 返回 $finCode"
    $failedStep = ($finOut | Where-Object { $_ -match 'FAIL' } | Select-Object -First 1)
    $finishState = "失败：finalize_215.py 返回 $finCode；$failedStep"
    [void]$problems.Add("收尾脚本返回 $finCode")
}

# ---------------------------------------------------------------- 阶段 4：git 提交并推送（无论成败）
Write-Log 'git 提交并推送（无论前面成败都执行）'
Set-Location $WS
$pkgDir = Join-Path $WS 'harbor-windows\wfflab__wfmt-215-v2.1.0-delivery'

& git add harbor-windows/_index 2>&1 | Out-Null
& git add harbor-windows/_qc_runs/tools 2>&1 | Out-Null
& git add $pkgDir 2>&1 | Out-Null
& git add (Join-Path $REFIT '*.py') (Join-Path $REFIT '*.ps1') (Join-Path $REFIT '*.md') (Join-Path $REFIT '*.json') (Join-Path $REFIT '*.txt') 2>&1 | Out-Null
& git reset -q HEAD 'harbor-windows/_qc_runs/refit-215-216/ws-golden-215' 'harbor-windows/_qc_runs/refit-215-216/ws-golden-216' 'harbor-windows/_qc_runs/refit-215-216/ws-nochange-215' 'harbor-windows/_qc_runs/refit-215-216/ws-nochange-216' 2>&1 | Out-Null

$staged = @(& git diff --cached --name-only 2>&1)
Write-Log ("  暂存文件数：{0}" -f $staged.Count)

$zipPath = Join-Path $REFIT 'package\wfflab__wfmt-215-v2.1.0-delivery.zip'
$zipSha = if (Test-Path -LiteralPath $zipPath) { (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLower() } else { '(not generated)' }

$msgFile = Join-Path $env:TEMP 'commit-msg-215.txt'
$msg = @"
215 返修收尾：$finishState

## 一、收尾流程状态

- 12 轮齐备：$(if ($ready) { '是' } else { '否（等待超时）' })
- 收尾脚本：$finishState
- 交付 zip sha256：$zipSha
- 遇到的问题：$(if ($problems.Count -gt 0) { $problems -join '；' } else { '无' })

## 二、215 跑分结果（task_version 2.1.1）

以下摘自 `_qc_runs/refit-215-216/215-run-summary.md`：

$summaryText

## 三、口径说明

- 甲方 2026-10-13 规则：GLM/Kimi 不再必需，模型轮只跑 Opus 5 与 Qwen3.8-Max-0902。
- 本次说明不代表修改或重评了原始产物。
- 本提交由收尾脚本自动生成；无论收尾成败都会提交并推送，随后关机。
"@
Set-Content -LiteralPath $msgFile -Value $msg -Encoding UTF8

if ($staged.Count -gt 0) {
    $commitOut = & git -c core.quotepath=false commit -F $msgFile 2>&1
    $commitOut | Select-Object -First 5 | ForEach-Object { Write-Log "  $_" }
    if ($LASTEXITCODE -ne 0) { Write-Log '!! git commit 失败' }
} else {
    Write-Log '  无暂存改动，跳过 commit'
}

$pushOut = & git push origin main 2>&1
$pushOut | ForEach-Object { Write-Log "  $_" }
if ($LASTEXITCODE -ne 0) { Write-Log '!! git push 失败（已尽力，继续关机）' } else { Write-Log 'git 推送完成' }

# ---------------------------------------------------------------- 阶段 5：关机（无条件）
if ($problems.Count -gt 0) {
    Set-Content -LiteralPath (Join-Path $LogRoot 'finalize-215.FAILED') -Value (($problems -join '; ')) -Encoding UTF8
    Write-Log '已写 FAILED 标记（但仍按要求关机）'
} else {
    Set-Content -LiteralPath (Join-Path $LogRoot 'finalize-215.done') -Value (Get-Date -Format o) -Encoding UTF8
    Write-Log '已写 done 标记'
}

Write-Log ("{0} 秒后关机，可用 shutdown /a 取消" -f $ShutdownDelaySeconds)
& shutdown /s /t $ShutdownDelaySeconds /c "wfflab 215 返修收尾流程已结束，自动关机" 2>&1 | ForEach-Object { Write-Log "  $_" }
Write-Log 'shutdown 指令已发出'
exit 0
