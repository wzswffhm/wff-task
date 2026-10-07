# Local Outside Harbor runner entry point.
#
#   .\run.ps1 -Task wfflab__wreparse-217 -Mode no-change -Runs 3
#   .\run.ps1 -Task wfflab__wreparse-217 -Mode golden    -Runs 3
#   .\run.ps1 -Task wfflab__wreparse-217 -Mode candidate -Models QWEN,OPUS -Runs 3
#
# Docker Desktop must be serving Windows containers:
#   docker desktop engine use windows
#
# The runner never reads or writes credentials itself; it only reads .env.local.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Task,
    [Parameter(Mandatory = $true)]
    [ValidateSet('no-change', 'golden', 'candidate', 'matrix', 'run')]
    [string]$Mode,
    [string]$Models = '',
    [int]$Runs = 1,
    [string]$WorkspaceRoot = '',
    [switch]$KeepWork
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$WorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path

$pythonCandidates = @(
    (Join-Path $env:USERPROFILE '.workbuddy\binaries\python\versions\3.13.12\python.exe'),
    'C:\Program Files\Python39\python.exe'
)
$python = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-Path -LiteralPath $candidate) { $python = $candidate; break }
}
if (-not $python) {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $python = $command.Source }
}
if (-not $python) { throw 'Python interpreter not found' }

$arguments = @(
    (Join-Path $WorkspaceRoot 'runner.py'),
    '--task', $Task,
    '--mode', $Mode,
    '--runs', $Runs,
    '--workspace-root', $WorkspaceRoot
)
if (-not [string]::IsNullOrWhiteSpace($Models)) { $arguments += @('--models', $Models) }
if ($KeepWork) { $arguments += '--keep-work' }

& $python @arguments
exit $LASTEXITCODE
