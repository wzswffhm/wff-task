# run_rounds.ps1 —— 跑到拿到 N 个有效轮次为止（INVALID 自动重跑）
#
# 背景：Windows 容器 bind mount 偶发失效会让验证阶段拿不到 verifier 注入，
#       runner 记为 verdict=INVALID（"verifier produced no result.json"）。
#       这类轮次不是模型失败，而是基础设施失败，必须重跑，不能计入交付。
#
# 用法：
#   .\run_rounds.ps1 -Mode candidate -Models QWEN -Target 3
#   .\run_rounds.ps1 -Mode no-change -Target 3        # NOP 控制轮
#   .\run_rounds.ps1 -Mode golden   -Target 3         # Oracle 控制轮

[CmdletBinding()]
param(
    [ValidateSet('candidate', 'no-change', 'golden')][string]$Mode = 'candidate',
    [string]$Models = 'QWEN',
    [int]$Target = 3,
    [int]$MaxAttempts = 6,
    [string]$Task = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修\build\outside_harbor-assets\wfflab__wchunk-216',
    [string]$TaskId = 'wfflab__wchunk-216',
    [string]$LogRoot = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修\evidence\model-runs',
    [string]$Tag = ''
)

$ErrorActionPreference = 'Continue'
$env:DOCKER_CONTEXT = 'desktop-windows'
$py = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$runner = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner'
$runsRoot = Join-Path $runner "runs\$TaskId"
$logRoot = $LogRoot
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
if ([string]::IsNullOrWhiteSpace($Tag)) { $Tag = "$Mode-$Models" }

function Get-RunVerdict([string]$RunDir) {
    $label = Get-ChildItem $RunDir -Directory | Select-Object -First 1
    if (-not $label) { return $null }
    $json = Join-Path $label.FullName 'result.json'
    if (-not (Test-Path $json)) { return $null }
    try {
        $doc = Get-Content $json -Raw | ConvertFrom-Json
        return @{ verdict = [string]$doc.verdict; run_validity = [string]$doc.run_validity; reason = [string]$doc.reason }
    } catch { return $null }
}

$valid = 0
$attempt = 0
$seenValid = New-Object System.Collections.ArrayList

while ($valid -lt $Target -and $attempt -lt $MaxAttempts) {
    $attempt++
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $log = Join-Path $logRoot "$Tag-a$attempt-$stamp.log"
    $before = @(Get-ChildItem $runsRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object Name)

    Write-Host "### attempt $attempt/$MaxAttempts  mode=$Mode models=$Models target=$Target valid=$valid  $(Get-Date -Format 'HH:mm:ss')"

    Push-Location $runner
    try {
        if ($Mode -eq 'candidate') {
            & $py -X utf8 runner.py --task $Task --mode candidate --models $Models --runs 1 2>&1 |
                Tee-Object -FilePath $log | Out-Null
        } else {
            & $py -X utf8 runner.py --task $Task --mode $Mode --runs 1 2>&1 |
                Tee-Object -FilePath $log | Out-Null
        }
    } finally { Pop-Location }

    $after = @(Get-ChildItem $runsRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object Name)
    $new = @($after | Where-Object { $before -notcontains $_ })

    if ($new.Count -eq 0) {
        Write-Host "    !! no new run directory produced; will retry"
        Start-Sleep -Seconds 10
        continue
    }

    foreach ($name in $new) {
        $info = Get-RunVerdict (Join-Path $runsRoot $name)
        if ($null -eq $info) {
            Write-Host "    $name -> result.json missing (infrastructure), retrying"
            continue
        }
        if ($info.verdict -eq 'INVALID') {
            Write-Host "    $name -> INVALID (mount/injection fault): $($info.reason)"
            continue
        }
        $valid++
        [void]$seenValid.Add($name)
        Write-Host "    $name -> OK verdict=$($info.verdict)  (valid $valid/$Target)"
    }
}

Write-Host ""
Write-Host "### done: valid=$valid/$Target attempts=$attempt"
if ($seenValid.Count -gt 0) { $seenValid | ForEach-Object { Write-Host "    valid run: $_" } }
if ($valid -lt $Target) {
    Write-Host "### WARNING: only $valid valid rounds after $attempt attempts"
    exit 1
}
exit 0
