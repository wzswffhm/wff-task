[CmdletBinding()]
param(
    [string]$TaskRoot = (Split-Path -Parent $PSScriptRoot)
)

foreach ($relativePath in @('results', 'logs')) {
    $path = Join-Path $TaskRoot $relativePath
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

Write-Output 'Pilot task state cleaned.'
