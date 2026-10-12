# stop_215_watchdog.ps1
#
# 用户只要 217 的结果。当前 rerun 任务的顺序是「217 x3 → 215 x3」，
# 217 跑完会自动接着跑 215。本看门狗轮询 217 是否已满 3 轮（新分租批次），
# 一旦满足就终止 runner，避免白跑 215。

[CmdletBinding()]
param(
    [string]$Since   = '20261009T0405',   # 本批次起始时间戳前缀
    [int]$PollSeconds = 45,
    [int]$TimeoutMinutes = 240
)

$RUNS = 'C:\Users\Administrator\Desktop\wff-task1\deliverables\2026-10-04_outside-harbor-win\runner\runs'
$OUT  = 'C:\Users\Administrator\Desktop\wff-task\_qc_runs\delivery-monitor'
New-Item -ItemType Directory -Force -Path $OUT | Out-Null

function Get-Rounds([string]$task) {
    $dir = Join-Path $RUNS $task
    if (-not (Test-Path $dir)) { return @() }
    return @(Get-ChildItem $dir -Directory |
        Where-Object { $_.Name -ge $Since -and $_.Name -like '*opus*' } |
        Where-Object { Get-ChildItem $_.FullName -Recurse -File -Filter result.json -ErrorAction SilentlyContinue })
}

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
Write-Host "watchdog start $(Get-Date -Format 'HH:mm:ss')  since=$Since"
$killed = $false
while ((Get-Date) -lt $deadline) {
    $n217 = (Get-Rounds 'wfflab__wreparse-217').Count
    $started215 = @(Get-ChildItem (Join-Path $RUNS 'wfflab__wfmt-215') -Directory -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -ge $Since }).Count
    Write-Host "  $(Get-Date -Format 'HH:mm:ss')  217 rounds=$n217  215 started=$started215"

    if ($n217 -ge 3) {
        if ($started215 -gt 0 -or $true) {
            $procs = Get-Process python -ErrorAction SilentlyContinue
            foreach ($p in $procs) {
                try { Stop-Process -Id $p.Id -Force -ErrorAction Stop; Write-Host "  killed python pid=$($p.Id)" } catch {}
            }
            $killed = $true
        }
        break
    }
    Start-Sleep -Seconds $PollSeconds
}

@{
    at              = (Get-Date).ToString('o')
    rounds_217      = (Get-Rounds 'wfflab__wreparse-217').Count
    killed_runner   = $killed
    note            = if ($killed) { '217 已满 3 轮，已终止 runner 以阻止 215 轮次' } else { '超时退出（未满足停止条件）' }
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OUT 'watchdog-217.json') -Encoding utf8
Write-Host "watchdog done $(Get-Date -Format 'HH:mm:ss') killed=$killed"
