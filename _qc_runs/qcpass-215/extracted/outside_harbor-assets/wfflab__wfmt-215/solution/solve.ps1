# Generated for wfflab__wfmt-215 by the task authoring pipeline. Do not edit by hand.
#
# Golden entry point: mirrors the reference wfmt payload over the candidate
# workspace so the Oracle control can be reproduced from a clean checkout.
#
# The script is idempotent, performs no network access and leaves no temporary
# logs. It only replaces files inside environment/workspace/wfmt.
#
# Exit codes:
#   0  the reference payload is in place
#   1  the payload could not be installed

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$WorkspaceRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

# Two layouts share this entry point:
#   * local runner: workspace lives at <TaskRoot>\environment\workspace;
#   * standard Harbor: the image bakes it at C:\testbed and passes -WorkspaceRoot.
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $TaskRoot 'environment\workspace'
} else {
    $WorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
}

$sourcePayload = Join-Path (Join-Path $PSScriptRoot 'reference') 'wfmt'
$targetPayload = Join-Path $WorkspaceRoot 'wfmt'

if (-not (Test-Path -LiteralPath $sourcePayload)) {
    Write-Host "solve: reference payload not found at $sourcePayload"
    exit 1
}
if (-not (Test-Path -LiteralPath $targetPayload)) {
    Write-Host "solve: candidate payload not found at $targetPayload"
    exit 1
}

& robocopy $sourcePayload $targetPayload /MIR /XF *.pyc /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
# robocopy reports success through exit codes 0..7; 8 and above are real failures.
if ($LASTEXITCODE -ge 8) {
    Write-Host "solve: robocopy failed with exit code $LASTEXITCODE"
    exit 1
}
$global:LASTEXITCODE = 0

$workspace = $WorkspaceRoot
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
if ($python) {
    $env:PYTHONPATH = "$workspace;$env:PYTHONPATH"
    & $python.Source -c "import wfmt" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'solve: the reference payload did not import'
        exit 1
    }
}

Write-Host 'solve: reference payload installed at environment/workspace/wfmt'
exit 0
