param([string]$Workspace = 'C:\testbed')
$ErrorActionPreference = 'SilentlyContinue'
Remove-Item -LiteralPath (Join-Path $Workspace 'bin') -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $Workspace 'bin') | Out-Null
Remove-Item -LiteralPath 'C:\agenttmp\*' -Recurse -Force
