# Generated for wfflab__wreparse-217. Do not edit by hand.
#
# Readiness probe: answers whether this machine can host the task. It reports on
# the platform, the PowerShell runtime, the candidate module and the fixture,
# and it never scores the candidate.
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

$modulePath = Join-Path $TaskRoot 'environment\workspace\WReparse\WReparse.psd1'
if (-not (Test-Path -LiteralPath $modulePath)) {
    [void]$problems.Add("the candidate module manifest is missing: $modulePath")
}
else {
    try {
        Import-Module $modulePath -Force -ErrorAction Stop
        $exported = @(Get-Command -Module 'WReparse' -CommandType Function -ErrorAction Stop)
        if ($exported.Count -eq 0) {
            [void]$problems.Add('the candidate module exports no functions')
        }
    }
    catch {
        [void]$problems.Add("the candidate module cannot be imported: $($_.Exception.Message)")
    }
}

# The fixture lives on the container's writable layer; see environment/prepare.ps1
# for why it cannot sit inside a bind-mounted task tree.
$fixtureRoot = Join-Path $env:SystemDrive 'wreparse-fixture'
if (-not (Test-Path -LiteralPath $fixtureRoot)) {
    [void]$problems.Add('the fixture has not been created; run environment/prepare.ps1 first')
}
else {
    $scanRoot = Join-Path $fixtureRoot 'scanroot'
    if (-not (Test-Path -LiteralPath $scanRoot)) {
        [void]$problems.Add("the fixture scan root is missing: $scanRoot")
    }
}

if ($problems.Count -gt 0) {
    foreach ($problem in $problems) { Write-Host "NOT READY: $problem" }
    exit 1
}

Write-Host "ready: $env:COMPUTERNAME / PowerShell $($PSVersionTable.PSVersion) / task root $TaskRoot"
exit 0
