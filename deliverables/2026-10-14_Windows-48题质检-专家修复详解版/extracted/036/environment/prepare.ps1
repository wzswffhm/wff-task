$ErrorActionPreference='Stop'
if(-not (Test-Path -LiteralPath 'C:\workspace\RegistryPatchApplier.ps1')){throw 'Workspace missing'}
& (Join-Path $PSScriptRoot 'validate_environment.ps1')
exit $LASTEXITCODE
