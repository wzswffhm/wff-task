# Generated for wfflab__wfmt-215 by the task authoring pipeline.
#
# Readiness probe: answers whether this machine can host the task. It reports on
# the platform, the PowerShell runtime, the interpreter, the candidate package
# and the authoritative samples, and it never scores the candidate.
#
# It also proves the isolation claim: withheld material (the oracle reference
# payload and the hidden behavioural suite) must not be reachable from the
# agent-visible tree. A hit fails the probe instead of being reported as a
# warning.
#
# Exit codes:
#   0  the environment is ready
#   1  the environment is not ready (details on stdout)

[CmdletBinding()]
param(
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

$problems = New-Object System.Collections.ArrayList

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    [void]$problems.Add('the host platform is not Windows')
}

if ($PSVersionTable.PSVersion.Major -lt 5) {
    [void]$problems.Add("Windows PowerShell 5.1 or later is required (found $($PSVersionTable.PSVersion))")
}

$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
if (-not $python) {
    [void]$problems.Add('no python interpreter is available on PATH')
}
else {
    & $python.Source -c "import pytest" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { [void]$problems.Add('the pytest package is not importable') }
}

$workspace = Join-Path $TaskRoot 'environment\workspace'
$packageInit = Join-Path (Join-Path $workspace 'wfmt') '__init__.py'
if (-not (Test-Path -LiteralPath $packageInit)) {
    [void]$problems.Add("the candidate package is missing: $packageInit")
}
else {
    $env:PYTHONPATH = "$workspace;$env:PYTHONPATH"
    & $python.Source -c "import wfmt" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { [void]$problems.Add('the candidate package cannot be imported') }
}

foreach ($sample in @((Join-Path 'assets' 'sample.wfmt'), (Join-Path 'assets' 'sample_empty.wfmt'))) {
    if (-not (Test-Path -LiteralPath (Join-Path $workspace $sample))) {
        [void]$problems.Add("the authoritative sample is missing: $sample")
    }
}

# ---- isolation audit --------------------------------------------------------
# 1. Inside the agent-visible workspace nothing may look like an answer or a
#    hidden suite.
$leaked = New-Object System.Collections.ArrayList
foreach ($item in @(Get-ChildItem -LiteralPath $workspace -Recurse -File -Force -ErrorAction SilentlyContinue)) {
    $name = $item.Name.ToLowerInvariant()
    if ($name -match 'oracle|golden|reference|hidden|rubric|solution|reward') {
        [void]$leaked.Add($item.FullName)
    }
}
foreach ($item in $leaked) { [void]$problems.Add("agent workspace contains withheld material: $item") }

# 2. The verifier-side and oracle-side roots must be outside the agent-visible
#    tree. They are injected for grading only; if they resolve inside the
#    workspace the packaging is wrong.
foreach ($forbidden in @('C:\verifier', 'C:\solution')) {
    if (-not (Test-Path -LiteralPath $forbidden)) { continue }
    $resolved = (Resolve-Path -LiteralPath $forbidden).Path
    if ($resolved.ToLowerInvariant().StartsWith($workspace.ToLowerInvariant())) {
        [void]$problems.Add("withheld root is inside the agent workspace: $resolved")
    }
}

if ($problems.Count -gt 0) {
    foreach ($problem in $problems) { Write-Host "NOT READY: $problem" }
    exit 1
}

Write-Host "ready: $env:COMPUTERNAME / PowerShell $($PSVersionTable.PSVersion) / task root $TaskRoot"
Write-Host 'isolation: agent workspace is free of oracle, reference and hidden-suite material'
exit 0
