param([string]$Workspace = 'C:\testbed')
$ErrorActionPreference = 'SilentlyContinue'
Get-Process WinPublish -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item -LiteralPath (Join-Path $Workspace 'bin') -Recurse -Force
Remove-Item -LiteralPath 'C:\agenttmp\*' -Recurse -Force
