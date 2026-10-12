# Generated for wfflab__wreparse-217. Do not edit by hand.
#
# Main run entry point. Prepares the fixed fixture once, then drives the real
# test path and propagates its exit code.

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $TaskRoot 'results\result.json'
}

& (Join-Path $PSScriptRoot 'prepare.ps1') -TaskRoot $TaskRoot
if ($LASTEXITCODE -ne 0) { exit 2 }

& (Join-Path $TaskRoot 'tests\test.ps1') -TaskRoot $TaskRoot -OutputPath $OutputPath `
    -WorkspaceRoot (Join-Path $PSScriptRoot 'workspace')
exit $LASTEXITCODE
