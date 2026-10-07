# Model matrix driver for wfflab__wreparse-217.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File run_matrix.ps1 -Models OPUS,GLM,KIMI
#
# Runs the requested aliases sequentially against the local Windows-container
# runner. Sequential execution is deliberate: the auxiliary models share one
# upstream key and parallel runs on a shared key starve each other.

[CmdletBinding()]
param(
    [string]$TaskId = 'wfflab__wreparse-217',
    [string[]]$Models = @('OPUS', 'GLM', 'KIMI'),
    [int]$Runs = 3,
    [string]$Tag = ''
)

$ErrorActionPreference = 'Continue'

# `-File script.ps1 -Models A,B,C` arrives as one comma-joined string, so split
# defensively rather than trusting the binder.
$Models = @($Models | ForEach-Object { $_ -split ',' } | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim().ToUpper() })
if ($Models.Count -eq 0) { throw 'no models requested' }

$RunnerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RunnerRoot 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
# Parallel shards must not collide on the log filename.
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$LogFile = if ($Tag) {
    Join-Path $LogDir ('matrix-' + $Tag + '-' + $stamp + '.log')
} else {
    Join-Path $LogDir ('matrix-' + $stamp + '.log')
}
$runScript = Join-Path $RunnerRoot 'run.ps1'
# Resolve PowerShell absolutely: Task Scheduler (and any detached context)
# starts with a minimal PATH where the bare name does not resolve.
$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Write-Log {
    param([string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $Message
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

Write-Log "matrix start models=$($Models -join ',') runs=$Runs"

foreach ($model in $Models) {
    # Auxiliary models are specified once each; primaries run the full count.
    $count = if ($model -in @('GLM', 'KIMI')) { 1 } else { $Runs }
    Write-Log "=== $model x$count ==="
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $psExe -NoProfile -ExecutionPolicy Bypass -File $runScript `
        -Task $TaskId -Mode candidate -Models $model -Runs $count -KeepWork 2>&1 |
        ForEach-Object { Write-Log $_ }
    $sw.Stop()
    Write-Log ("{0} exit={1} elapsed={2:N0}s" -f $model, $LASTEXITCODE, $sw.Elapsed.TotalSeconds)
}

Write-Log 'matrix complete'
$doneName = if ($Tag) { 'matrix-' + $Tag + '.done' } else { 'matrix.done' }
Set-Content -LiteralPath (Join-Path $LogDir $doneName) -Value (Get-Date -Format o) -Encoding UTF8
exit 0
