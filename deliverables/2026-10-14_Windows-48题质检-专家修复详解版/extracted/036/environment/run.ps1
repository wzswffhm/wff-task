$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'prepare.ps1');if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
& 'C:\tests\test.ps1'
exit $LASTEXITCODE
