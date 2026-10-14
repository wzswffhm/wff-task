param([string]$Workspace = 'C:\testbed')
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $Workspace, (Join-Path $Workspace 'src'), (Join-Path $Workspace 'bin'), 'C:\agenttmp' | Out-Null
if (-not (Get-LocalUser -Name BenchAgent -ErrorAction SilentlyContinue)) { New-LocalUser -Name BenchAgent -NoPassword | Out-Null }
icacls $Workspace /grant 'BenchAgent:(OI)(CI)RX' | Out-Null
icacls (Join-Path $Workspace 'src') /grant 'BenchAgent:(OI)(CI)M' | Out-Null
icacls 'C:\agenttmp' /grant 'BenchAgent:(OI)(CI)M' | Out-Null
