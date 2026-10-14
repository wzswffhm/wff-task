[CmdletBinding()]
param(
    [string]$TaskRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputPath = $null
)

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $TaskRoot 'results\result.json'
}

& (Join-Path $PSScriptRoot 'prepare.ps1') -TaskRoot $TaskRoot
if ($LASTEXITCODE -ne 0) {
    exit 2
}

& (Join-Path $TaskRoot 'tests\run_tests.ps1') -WorkspaceRoot (Join-Path $TaskRoot 'workspace') -OutputPath $OutputPath
exit $LASTEXITCODE
