# Detached entry point for a model-matrix shard.
#
# The matrix runs for hours. It must not be a child of an interactive shell or
# of a tool-managed background process: those are reaped at turn/session
# boundaries, which kills the runner mid-run and leaves an orphaned container.
# Task Scheduler owns this process instead, so it survives independently.
#
# Usage (registered once per shard):
#   matrix-task.ps1 -Tag qwen -Models QWEN -Runs 3

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [Parameter(Mandatory = $true)][string]$Models,
    [int]$Runs = 3,
    [string]$TaskId = 'wfflab__wreparse-217'
)

$ErrorActionPreference = 'Continue'

$RunnerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RunnerRoot 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$TaskLog = Join-Path $LogDir ("matrix-task-$Tag.log")
$DoneFlag = Join-Path $LogDir ("matrix-$Tag.done")
$FailFlag = Join-Path $LogDir ("matrix-$Tag.failed")

# Task Scheduler starts with a minimal PATH. The runner shells out to `docker`
# by name, so make the CLI reachable before anything else runs.
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path -LiteralPath $dockerBin) { $env:Path = $dockerBin + ';' + $env:Path }

Remove-Item -LiteralPath $DoneFlag, $FailFlag -Force -ErrorAction SilentlyContinue

"[{0}] shard start tag={1} models={2} runs={3} pid={4}" -f (Get-Date -Format o), $Tag, $Models, $Runs, $PID |
    Set-Content -LiteralPath $TaskLog -Encoding UTF8

# The runner calls `docker` by name; resolve it absolutely as well so a shard
# never fails on PATH resolution alone.
$dockerExe = Join-Path $dockerBin 'docker.exe'
if (-not (Test-Path -LiteralPath $dockerExe)) { $dockerExe = 'docker' }
"[{0}] docker probe: {1}" -f (Get-Date -Format o), ((& $dockerExe version --format '{{.Server.Os}}/{{.Server.Version}}' 2>&1) -join ' ') |
    Add-Content -LiteralPath $TaskLog -Encoding UTF8

# Task Scheduler runs with a minimal PATH, so `powershell.exe` cannot be
# resolved by name here; use the absolute path.
$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$runScript = Join-Path $RunnerRoot 'run_matrix.ps1'

& $psExe -NoProfile -ExecutionPolicy Bypass -File $runScript `
    -TaskId $TaskId -Models $Models -Runs $Runs -Tag $Tag *>> $TaskLog
$code = $LASTEXITCODE

"[{0}] shard exit={1}" -f (Get-Date -Format o), $code | Add-Content -LiteralPath $TaskLog -Encoding UTF8
if ($code -eq 0) {
    Set-Content -LiteralPath $DoneFlag -Value (Get-Date -Format o) -Encoding UTF8
} else {
    Set-Content -LiteralPath $FailFlag -Value ("exit={0} at {1}" -f $code, (Get-Date -Format o)) -Encoding UTF8
}
exit $code
