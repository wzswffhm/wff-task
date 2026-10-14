param([switch]$TrustedLocal)
& (Join-Path $PSScriptRoot 'test.ps1') -TrustedLocal:$TrustedLocal
exit $LASTEXITCODE
