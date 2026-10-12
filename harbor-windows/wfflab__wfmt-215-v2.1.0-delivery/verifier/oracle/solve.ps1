# Generated for wfflab__wfmt-215 by the task authoring pipeline.
#
# Golden entry point. The reference payload is deliberately NOT shipped inside
# the task package: it is injected by the evaluation side into a verifier-side
# directory, so the agent-visible tree never contains the answer.
#
# This script only locates that injected payload and mirrors it over the
# candidate workspace.
#
# Payload resolution order (first hit wins):
#   1. -ReferenceRoot <dir>
#   2. $env:WFMT_REFERENCE_ROOT
#   3. <script dir>\reference\wfmt                   (verifier-side sibling)
#   4. C:\verifier\wfflab__wfmt-215\oracle\reference\wfmt   (verifier injection)
#   5. C:\solution\reference\wfmt                    (platform injection point)
#   6. <package>\outside_harbor-verifier\wfflab__wfmt-215\oracle\reference\wfmt
#      (sibling of the agent-visible package; local reproduction only)
#
# The script is idempotent, performs no network access and leaves no logs.
#
# Exit codes:
#   0  the reference payload is in place
#   1  the payload could not be located or installed

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$WorkspaceRoot = '',
    [string]$ReferenceRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $TaskRoot 'environment\workspace'
} else {
    $WorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
}

function Test-Payload([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Path '__init__.py'))
}

$candidates = New-Object System.Collections.ArrayList
if (-not [string]::IsNullOrWhiteSpace($ReferenceRoot)) { [void]$candidates.Add($ReferenceRoot) }
if (-not [string]::IsNullOrWhiteSpace($env:WFMT_REFERENCE_ROOT)) { [void]$candidates.Add($env:WFMT_REFERENCE_ROOT) }
[void]$candidates.Add((Join-Path $PSScriptRoot 'reference\wfmt'))
[void]$candidates.Add('C:\verifier\wfflab__wfmt-215\oracle\reference\wfmt')
[void]$candidates.Add('C:\solution\reference\wfmt')
$packageRoot = Split-Path -Parent $TaskRoot
if (-not [string]::IsNullOrWhiteSpace($packageRoot)) {
    [void]$candidates.Add((Join-Path $packageRoot 'outside_harbor-verifier\wfflab__wfmt-215\oracle\reference\wfmt'))
}

$sourcePayload = ''
foreach ($candidate in $candidates) {
    if (Test-Payload $candidate) { $sourcePayload = $candidate; break }
}

if ([string]::IsNullOrWhiteSpace($sourcePayload)) {
    Write-Host 'solve: no injected reference payload was found; the Oracle control cannot run'
    exit 1
}

$sourcePayload = (Resolve-Path -LiteralPath $sourcePayload).Path
$targetPayload = Join-Path $WorkspaceRoot 'wfmt'
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

$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
if ($python) {
    $env:PYTHONPATH = "$WorkspaceRoot;$env:PYTHONPATH"
    & $python.Source -c "import wfmt" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'solve: the reference payload did not import'
        exit 1
    }
}

Write-Host 'solve: reference payload installed at environment/workspace/wfmt'
exit 0
