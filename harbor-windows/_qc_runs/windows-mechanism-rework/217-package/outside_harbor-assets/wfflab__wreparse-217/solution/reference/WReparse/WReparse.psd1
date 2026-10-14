@{
    RootModule        = 'WReparse.psm1'
    ModuleVersion     = '1.0.0'
    GUID              = 'b6a1f0d2-3c47-4f8e-9a51-0d7c2e5b8143'
    Author            = 'vendor'
    CompanyName       = 'vendor'
    Description       = 'Safe reparse-point traversal and deterministic audit reporting for Windows directory trees.'
    PowerShellVersion = '5.1'
    FunctionsToExport = @(
        'Get-WReparseReport'
        'ConvertTo-WReparseJson'
        'Get-WReparseSchemaVersion'
        'Test-WReparseWithinRoot'
        'Get-WReparseCanonicalPath'
        'Resolve-WReparseLinkTarget'
    )
    CmdletsToExport   = @()
    VariablesToExport = @()
    AliasesToExport   = @()
    PrivateData       = @{
        PSData = @{
            Tags       = @('windows', 'ntfs', 'reparse', 'powershell')
            ProjectUri = ''
        }
    }
}
