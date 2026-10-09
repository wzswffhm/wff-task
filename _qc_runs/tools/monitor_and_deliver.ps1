# monitor_and_deliver.ps1
#
# 真·后台监控：轮询 runner 的 runs/ 直到 215 与 217 的 Opus 各满 3 轮（或超时），
# 然后自动汇总 Qwen/Opus 的 score_sum、判定区分度（Opus 严格大于 Qwen），
# 达标者调用 upload_zip_no_status.ps1 上传附件（**不修改状态字段**）。
#
# 不达标者只记录结论，交由 agent 继续加难度（脚本不做改题）。

[CmdletBinding()]
param(
    [int]$TimeoutMinutes = 300,
    [int]$PollSeconds = 60,
    [switch]$AutoUpload
)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$RUNS  = 'C:\Users\Administrator\Desktop\wff-task1\deliverables\2026-10-04_outside-harbor-win\runner\runs'
$TOOLS = 'C:\Users\Administrator\Desktop\wff-task\_qc_runs\tools'
$OUT   = 'C:\Users\Administrator\Desktop\wff-task\_qc_runs\delivery-monitor'
$PKG   = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-08_harbor-windows-整改\package'
$PY    = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
New-Item -ItemType Directory -Force -Path $OUT | Out-Null

$TASKS = @{
    'wfflab__wfmt-215'      = @{ Model = 'OPUS'; Need = 3 }
    'wfflab__wreparse-217'  = @{ Model = 'OPUS'; Need = 3 }
}

function Get-RoundInfo([string]$task, [string]$model) {
    $dir = Join-Path $RUNS $task
    if (-not (Test-Path $dir)) { return @() }
    $rows = @()
    foreach ($job in Get-ChildItem $dir -Directory | Sort-Object Name) {
        if ($job.Name -notlike "*$($model.ToLower())*") { continue }
        if ($job.Name -notlike "20261009T*" -and $job.Name -notlike "20261008T2*") { continue }
        $res = Get-ChildItem $job.FullName -Recurse -File -Filter result.json -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $res) { continue }
        $d = Get-Content $res.FullName -Raw | ConvertFrom-Json
        $rows += [pscustomobject]@{ Job = $job.Name; Verdict = [int]$d.verdict; Dur = $d.duration_seconds }
    }
    return $rows
}

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
Write-Host "monitor start $(Get-Date -Format 'HH:mm:ss')  timeout=${TimeoutMinutes}m"
while ((Get-Date) -lt $deadline) {
    $allDone = $true
    foreach ($t in $TASKS.Keys) {
        $n = @(Get-RoundInfo $t $TASKS[$t].Model).Count
        if ($n -lt $TASKS[$t].Need) { $allDone = $false }
    }
    if ($allDone) { break }
    Start-Sleep -Seconds $PollSeconds
}

# ---------------- 汇总与判定 ----------------
$summary = [ordered]@{ at = (Get-Date).ToString('o'); tasks = @{} }
foreach ($t in $TASKS.Keys) {
    $opus  = @(Get-RoundInfo $t 'OPUS')
    $qwen  = @(Get-RoundInfo $t 'QWEN')
    $oSum = ($opus | Measure-Object Verdict -Sum).Sum; if ($null -eq $oSum) { $oSum = 0 }
    $qSum = ($qwen | Measure-Object Verdict -Sum).Sum; if ($null -eq $qSum) { $qSum = 0 }
    $pass = ($oSum -gt $qSum)
    $summary.tasks[$t] = [ordered]@{
        opus_rounds = $opus.Count; opus_sum = $oSum; opus_detail = ($opus | ForEach-Object { $_.Verdict }) -join '/'
        qwen_rounds = $qwen.Count; qwen_sum = $qSum; qwen_detail = ($qwen | ForEach-Object { $_.Verdict }) -join '/'
        admission = if ($pass) { 'PASS' } else { 'FAIL' }
    }
    Write-Host ("{0}: Opus {1} ({2})  vs  Qwen {3} ({4})  -> {5}" -f `
        $t, $oSum, (($opus | ForEach-Object { $_.Verdict }) -join '/'), `
        $qSum, (($qwen | ForEach-Object { $_.Verdict }) -join '/'), $summary.tasks[$t].admission)
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OUT 'verdict.json') -Encoding utf8

# ---------------- 达标者上传（不碰状态） ----------------
if ($AutoUpload) {
    $map = @{
        'wfflab__wfmt-215'     = @{ Record = 'reczz28KwEOO3xHy'; Zip = (Join-Path $PKG 'wfflab__wfmt-215-v2.0.0-delivery.zip') }
        'wfflab__wreparse-217' = @{ Record = 'reczz28KQU8reW2k'; Zip = (Join-Path $PKG 'wfflab__wreparse-217-v1.1.0-delivery.zip') }
    }
    foreach ($t in $TASKS.Keys) {
        if ($summary.tasks[$t].admission -ne 'PASS') { Write-Host "$t 未达标，跳过上传"; continue }
        if (-not $map[$t].Record) { Write-Host "$t 没有既有记录（需新建行），交给 agent 处理"; continue }
        Write-Host "uploading $t ..."
        & (Join-Path $TOOLS 'upload_zip_no_status.ps1') -RecordId $map[$t].Record -ZipPath $map[$t].Zip -ConfirmWrite `
            *> (Join-Path $OUT "upload-$t.log")
        Write-Host "  exit=$LASTEXITCODE"
    }
}

Write-Host "monitor done $(Get-Date -Format 'HH:mm:ss')"

