param([Parameter(Mandatory)][string]$WorkspaceRoot,[Parameter(Mandatory)][ValidateSet('Set','Get','Remove')][string]$Action,[Parameter(Mandatory)][string]$StoreRoot,[Parameter(Mandatory)][string]$Name,[AllowEmptyString()][string]$Value='')
$ErrorActionPreference='Stop'
try { & (Join-Path $WorkspaceRoot 'candidate.ps1') -Action $Action -StoreRoot $StoreRoot -Name $Name -Value $Value; exit 0 } catch { Write-Error $_; exit 1 }
