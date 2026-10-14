$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'cleanup.ps1')
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
Copy-Item -LiteralPath 'C:\task-baseline\RegistryPatchApplier.ps1' -Destination 'C:\workspace\RegistryPatchApplier.ps1' -Force
exit 0
