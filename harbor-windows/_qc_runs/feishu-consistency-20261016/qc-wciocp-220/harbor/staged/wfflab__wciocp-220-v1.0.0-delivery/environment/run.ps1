# Runs the wciocp checks against the candidate workspace.
#
# NOTE: keep this file pure ASCII (Windows PowerShell 5.1 reads BOM-less files
# as ANSI).

[CmdletBinding()]
param(
    [string]$TaskRoot = '',
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent $PSScriptRoot
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path (Join-Path $TaskRoot 'results') ('result' + '.json')
}

& (Join-Path $TaskRoot 'environment\prepare.ps1') -TaskRoot $TaskRoot
if ($LASTEXITCODE -ne 0) { exit 2 }

& (Join-Path $TaskRoot 'tests\test.ps1') -TaskRoot $TaskRoot -OutputPath $OutputPath -WorkspaceRoot (Join-Path $PSScriptRoot 'workspace')
exit $LASTEXITCODE
