# Generated for wfflab__wreparse-217. Do not edit by hand.
#
# Golden entry point: mirrors the reference WReparse payload over the candidate
# workspace so the Oracle control can be reproduced from a clean checkout.
#
# The script is idempotent, performs no network access and leaves no temporary
# logs. It only replaces files inside environment/workspace/WReparse.
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

$sourcePayload = Join-Path (Join-Path $PSScriptRoot 'reference') 'WReparse'
# Two layouts share this entry point:
#   * local runner: workspace lives at <TaskRoot>\environment\workspace;
#   * standard Harbor: the image bakes it at C:\testbed and passes -WorkspaceRoot.
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $targetPayload = Join-Path $TaskRoot 'environment\workspace\WReparse'
} else {
    $targetPayload = Join-Path ((Resolve-Path -LiteralPath $WorkspaceRoot).Path) 'WReparse'
}

if (-not (Test-Path -LiteralPath $sourcePayload)) {
    Write-Host "solve: reference payload not found at $sourcePayload"
    exit 1
}
if (-not (Test-Path -LiteralPath $targetPayload)) {
    Write-Host "solve: candidate payload not found at $targetPayload"
    exit 1
}

& robocopy $sourcePayload $targetPayload /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
# robocopy reports success through exit codes 0..7; 8 and above are real failures.
if ($LASTEXITCODE -ge 8) {
    Write-Host "solve: robocopy failed with exit code $LASTEXITCODE"
    exit 1
}

$manifest = Join-Path $targetPayload ('WReparse' + '.psd1')
try {
    Import-Module $manifest -Force -ErrorAction Stop
}
catch {
    Write-Host "solve: the reference payload did not import: $($_.Exception.Message)"
    exit 1
}

Write-Host 'solve: reference payload installed at environment/workspace/WReparse'
exit 0
