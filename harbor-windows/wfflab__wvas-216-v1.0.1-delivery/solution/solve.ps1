# Golden entry point for wfflab__wvas-216.
#
# This script installs the reference payload over the candidate package so that
# the Oracle control can be run against the very same checks the candidate is
# graded by. It is idempotent, it never reaches the network and it writes no
# logs.
#
# Harbor uploads solution/ (and only solution/) for the Oracle control, so the
# reference payload travels with this file as solution/reference/wvas. See
# solution/README.md.
#
# NOTE: keep this file pure ASCII (Windows PowerShell 5.1 reads BOM-less files
# as ANSI).

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
if (Test-Path -LiteralPath $TaskRoot) {
    $TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
}

function Test-Payload([string]$Directory) {
    if ([string]::IsNullOrWhiteSpace($Directory)) { return $false }
    return (Test-Path -LiteralPath (Join-Path $Directory '__init__.py'))
}

function Resolve-Workspace([string]$Explicit, [string]$Root) {
    if (-not [string]::IsNullOrWhiteSpace($Explicit)) { return $Explicit }
    $candidates = New-Object System.Collections.ArrayList
    if (-not [string]::IsNullOrWhiteSpace($env:WVAS_WORKSPACE_ROOT)) { [void]$candidates.Add($env:WVAS_WORKSPACE_ROOT) }
    # Harbor runs this entry point inside the task container, whose workdir is
    # C:\testbed; the package layout only exists on the local runner.
    [void]$candidates.Add('C:\testbed')
    if (-not [string]::IsNullOrWhiteSpace($Root)) { [void]$candidates.Add((Join-Path $Root 'environment\workspace')) }
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        if (Test-Path -LiteralPath (Join-Path $candidate 'wvas')) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return ''
}

$WorkspaceRoot = Resolve-Workspace $WorkspaceRoot $TaskRoot
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    Write-Host 'solve: no candidate workspace was found (looked at C:\testbed and the package layout)'
    exit 1
}
Write-Host "solve: workspace resolved to $WorkspaceRoot"

$candidates = New-Object System.Collections.ArrayList
if (-not [string]::IsNullOrWhiteSpace($ReferenceRoot)) { [void]$candidates.Add($ReferenceRoot) }
if (-not [string]::IsNullOrWhiteSpace($env:WVAS_REFERENCE_ROOT)) { [void]$candidates.Add($env:WVAS_REFERENCE_ROOT) }
[void]$candidates.Add((Join-Path $PSScriptRoot 'reference\wvas'))
[void]$candidates.Add('C:\verifier\wfflab__wvas-216\oracle\reference\wvas')
[void]$candidates.Add('C:\solution\reference\wvas')
$packageRoot = Split-Path -Parent $TaskRoot
if (-not [string]::IsNullOrWhiteSpace($packageRoot)) {
    [void]$candidates.Add((Join-Path $packageRoot 'outside_harbor-verifier\wfflab__wvas-216\oracle\reference\wvas'))
}

$sourcePayload = ''
foreach ($candidate in $candidates) {
    if (Test-Payload $candidate) {
        $sourcePayload = (Resolve-Path -LiteralPath $candidate).Path
        break
    }
}
if ([string]::IsNullOrWhiteSpace($sourcePayload)) {
    Write-Host 'solve: no injected reference payload was found; the Oracle control cannot run'
    exit 1
}

$targetPayload = Join-Path $WorkspaceRoot 'wvas'
if (-not (Test-Path -LiteralPath $targetPayload)) {
    Write-Host "solve: candidate payload not found at $targetPayload"
    exit 1
}

robocopy $sourcePayload $targetPayload /MIR /XF *.pyc /XD __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
# robocopy exit codes below 8 are success (0 = nothing copied).
if ($LASTEXITCODE -ge 8) { exit 1 }
$global:LASTEXITCODE = 0

$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
if (-not $python) {
    Write-Host 'solve: no python interpreter is available on PATH'
    exit 1
}
$env:PYTHONPATH = "$WorkspaceRoot;$env:PYTHONPATH"
& $python.Source -c "import wvas" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'solve: the reference payload did not import'
    exit 1
}

Write-Host 'solve: reference payload installed at environment/workspace/wvas'
exit 0
