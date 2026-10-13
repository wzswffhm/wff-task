# finalize_215.ps1 —— 215 收尾全流程（等待 -> 自检修正上传 -> git 推送 -> 关机）
#
# 安全原则：**只有前面每一步都成功，最后才关机**。任何一步失败都会写日志并直接退出，
# 不会执行 shutdown，便于人工介入。
#
# 用法（脱离本会话，用计划任务启动）：
#   schtasks /Create /TN wff-finalize-215 /TR "powershell -File finalize_215.ps1" /SC ONCE /ST 23:59 /F

[CmdletBinding()]
param(
    [string]$Package = 'wfflab__wfmt-215',
    [string]$LogRoot = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\refit-215-216\relaunch-logs',
    [int]$PollSeconds = 180,
    [int]$MaxWaitHours = 10,
    [int]$ShutdownDelaySeconds = 300
)

$ErrorActionPreference = 'Continue'
$WS = 'C:\Users\Administrator\Desktop\wff-task'
$runner = Join-Path $WS 'deliverables\2026-10-04_outside-harbor-win\runner'
$py = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$finalize = Join-Path $WS 'harbor-windows\_qc_runs\refit-215-216\finalize_215.py'
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path -LiteralPath $dockerBin) { $env:Path = $dockerBin + ';' + $env:Path }
$env:DOCKER_CONTEXT = 'desktop-windows'

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$log = Join-Path $LogRoot 'finalize-215.log'
$failFlag = Join-Path $LogRoot 'finalize-215.FAILED'
$doneFlag = Join-Path $LogRoot 'finalize-215.done'
Remove-Item -LiteralPath $failFlag, $doneFlag -Force -ErrorAction SilentlyContinue

function Write-Log([string]$m) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Write-Host $line
    Add-Content -LiteralPath $log -Value $line -Encoding UTF8
}

function Stop-WithFailure([string]$why) {
    Write-Log "!! 失败：$why"
    Write-Log '!! 不执行关机，请人工处理'
    Set-Content -LiteralPath $failFlag -Value ("{0} | {1}" -f (Get-Date -Format o), $why) -Encoding UTF8
    exit 1
}

# ---------------------------------------------------------------- 阶段 1：等待轮次齐备
Write-Log "finalize start package=$Package pid=$PID"
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

if (-not $ready) { Stop-WithFailure "等待超时（$MaxWaitHours 小时）仍未集齐 12 轮" }
Write-Log '轮次齐备（12 轮全 VALID）'

# ---------------------------------------------------------------- 阶段 2：自检 + 修正 + 归档 + 打包 + 上传 + 索引
Write-Log '调用 finalize_215.py（自检/修正/归档/打包/上传/索引）'
$out = & $py -X utf8 $finalize 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { Add-Content -LiteralPath $log -Value $_ -Encoding UTF8 }
if ($code -ne 0) { Stop-WithFailure "finalize_215.py 返回 $code" }
Write-Log 'finalize_215.py 成功'

# ---------------------------------------------------------------- 阶段 3：git 提交并推送
Write-Log 'git 提交并推送'
Set-Location $WS

$pkgDir = Join-Path $WS 'harbor-windows\wfflab__wfmt-215-v2.1.0-delivery'
& git add harbor-windows/_index 2>&1 | Out-Null
& git add harbor-windows/_qc_runs/tools 2>&1 | Out-Null
& git add $pkgDir 2>&1 | Out-Null
& git add 'harbor-windows/_qc_runs/refit-215-216/*.py' 'harbor-windows/_qc_runs/refit-215-216/*.ps1' 'harbor-windows/_qc_runs/refit-215-216/*.md' 'harbor-windows/_qc_runs/refit-215-216/*.json' 'harbor-windows/_qc_runs/refit-215-216/*.txt' 2>&1 | Out-Null

$staged = @(& git diff --cached --name-only 2>&1)
Write-Log ("  暂存文件数：{0}" -f $staged.Count)
if ($staged.Count -gt 0) {
    $msgFile = Join-Path $env:TEMP 'commit-msg-215.txt'
    $zipPath = Join-Path $WS 'harbor-windows\_qc_runs\refit-215-216\package\wfflab__wfmt-215-v2.1.0-delivery.zip'
    $zipSha = if (Test-Path -LiteralPath $zipPath) { (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLower() } else { 'n/a' }
    $msg = @"
215 返修收尾：按新规则重跑 12 轮、重建归档、上传飞书、同步身份

## 重跑（甲方 2026-10-13 规则：GLM/Kimi 不再必需）
- 控制组：golden 3/3 = 1、no-change 3/3 = 0
- 模型轮：Opus 5 x3、Qwen3.8-Max x3
- 全部 VALID，无无效槽位

## 结构与质检
- 移出 `REFIT-2026-10-12.md`（非交付文件），另存 `_qc_runs/refit-215-216/REFIT-215-20261012.md`
- 顶层结构与旧包一致（environment/instruction.md/jobs/solution/task.toml/tests/verifier）
- 无效槽位注解层更新为 2.1.1 口径：本归档无无效槽位，历史条目移入 superseded_history
- 质检 6 条要求材料逐项自检通过

## 归档与上传
- jobs 按新轮次重建为 12 trial（控制 6 + 模型 6）
- 交付 zip sha256 = $zipSha
- 已上传飞书记录 reczz28KwEOO3xHy（甲方ID 12），附件数 1，下载回验 sha256 一致

## 口径
本次说明不代表修改或重评了原始产物。
"@
    Set-Content -LiteralPath $msgFile -Value $msg -Encoding UTF8
    $commitOut = & git -c core.quotepath=false commit -F $msgFile 2>&1
    $commitOut | Select-Object -First 4 | ForEach-Object { Write-Log "  $_" }
    if ($LASTEXITCODE -ne 0) { Stop-WithFailure "git commit 失败" }
} else {
    Write-Log '  无暂存改动，跳过 commit'
}

$pushOut = & git push origin main 2>&1
$pushOut | ForEach-Object { Write-Log "  $_" }
if ($LASTEXITCODE -ne 0) { Stop-WithFailure "git push 失败" }
Write-Log 'git 推送完成'

# ---------------------------------------------------------------- 阶段 4：关机
Set-Content -LiteralPath $doneFlag -Value (Get-Date -Format o) -Encoding UTF8
Write-Log ("全部完成（zip sha256 见 package 目录）。{0} 秒后关机，可用 shutdown /a 取消" -f $ShutdownDelaySeconds)
& shutdown /s /t $ShutdownDelaySeconds /c "wfflab 215/216 返修收尾完成，自动关机" 2>&1 | ForEach-Object { Write-Log "  $_" }
Write-Log 'shutdown 指令已发出'
exit 0
