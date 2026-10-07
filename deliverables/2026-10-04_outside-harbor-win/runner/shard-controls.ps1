# Detached controls shard for a qualification epoch.
#
#   shard-controls.ps1 -Tag r8c
#
# Runs the no-change and golden controls for the given task, sequentially, with
# its own .done / .failed flag so a watcher can tell when the epoch's controls
# are complete. Task Scheduler owns this process (see matrix-task.ps1 for why a
# long shard must not be a child of an interactive shell).

[CmdletBinding()]
param(
    [string]$Tag = 'r8c',
    [string]$TaskId = 'wfflab__wreparse-217',
    [int]$Runs = 3
)

$ErrorActionPreference = 'Continue'

$RunnerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RunnerRoot 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$TaskLog = Join-Path $LogDir ("controls-task-$Tag.log")
$DoneFlag = Join-Path $LogDir ("matrix-$Tag.done")
$FailFlag = Join-Path $LogDir ("matrix-$Tag.failed")

# Task Scheduler starts with a minimal PATH; the runner shells out to `docker`
# by name, so make the CLI reachable before anything else runs.
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path -LiteralPath $dockerBin) { $env:Path = $dockerBin + ';' + $env:Path }

Remove-Item -LiteralPath $DoneFlag, $FailFlag -Force -ErrorAction SilentlyContinue
"[{0}] controls shard start tag={1} runs={2} pid={3}" -f (Get-Date -Format o), $Tag, $Runs, $PID |
    Set-Content -LiteralPath $TaskLog -Encoding UTF8

$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$runScript = Join-Path $RunnerRoot 'run.ps1'

$code = 0
foreach ($mode in @('no-change', 'golden')) {
    "[{0}] === {1} x{2} ===" -f (Get-Date -Format o), $mode, $Runs | Add-Content -LiteralPath $TaskLog -Encoding UTF8
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $psExe -NoProfile -ExecutionPolicy Bypass -File $runScript `
        -Task $TaskId -Mode $mode -Runs $Runs -WorkspaceRoot $RunnerRoot -KeepWork *>> $TaskLog
    $rc = $LASTEXITCODE
    $sw.Stop()
    "[{0}] {1} exit={2} elapsed={3:N0}s" -f (Get-Date -Format o), $mode, $rc, $sw.Elapsed.TotalSeconds |
        Add-Content -LiteralPath $TaskLog -Encoding UTF8
    if ($rc -ne 0) { $code = $rc }
}

"[{0}] controls shard exit={1}" -f (Get-Date -Format o), $code | Add-Content -LiteralPath $TaskLog -Encoding UTF8
if ($code -eq 0) {
    Set-Content -LiteralPath $DoneFlag -Value (Get-Date -Format o) -Encoding UTF8
} else {
    Set-Content -LiteralPath $FailFlag -Value ("exit={0} at {1}" -f $code, (Get-Date -Format o)) -Encoding UTF8
}
exit $code
