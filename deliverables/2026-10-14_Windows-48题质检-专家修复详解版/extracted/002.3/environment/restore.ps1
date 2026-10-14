param([Parameter(Mandatory=$true)][string]$WorkspaceRoot, [Parameter(Mandatory=$true)][string]$RepoRoot)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'prepare.ps1') -WorkspaceRoot $WorkspaceRoot -RepoRoot $RepoRoot
