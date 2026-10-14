param([string]$WorkspaceRoot)
& (Join-Path $PSScriptRoot "cleanup.ps1") $WorkspaceRoot; & (Join-Path $PSScriptRoot "prepare.ps1") $WorkspaceRoot
