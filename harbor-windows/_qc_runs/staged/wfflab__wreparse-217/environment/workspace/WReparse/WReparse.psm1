# WReparse - WReparse.psm1
# Root module. Loads the implementation files and publishes the public surface
# described in docs/REPARSE-CONTRACT.md.

$moduleRoot = $PSScriptRoot

. (Join-Path $moduleRoot 'Model.ps1')
. (Join-Path $moduleRoot 'PathSemantics.ps1')
. (Join-Path $moduleRoot 'Walker.ps1')
. (Join-Path $moduleRoot 'Audit.ps1')

Export-ModuleMember -Function @(
    'Get-WReparseReport'
    'ConvertTo-WReparseJson'
    'Get-WReparseSchemaVersion'
    'Test-WReparseWithinRoot'
    'Get-WReparseCanonicalPath'
    'Resolve-WReparseLinkTarget'
)
