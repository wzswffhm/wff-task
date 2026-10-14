[CmdletBinding()]
param(
    [string]$TaskRoot = (Split-Path -Parent $PSScriptRoot)
)

& (Join-Path $PSScriptRoot 'cleanup.ps1') -TaskRoot $TaskRoot
exit $LASTEXITCODE
