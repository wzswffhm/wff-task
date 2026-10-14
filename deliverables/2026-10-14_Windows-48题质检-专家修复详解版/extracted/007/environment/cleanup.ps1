param([string]$Scratch = 'C:\bench-fixtures')
$ErrorActionPreference = 'SilentlyContinue'
if (Test-Path $Scratch) { Remove-Item $Scratch -Recurse -Force }
