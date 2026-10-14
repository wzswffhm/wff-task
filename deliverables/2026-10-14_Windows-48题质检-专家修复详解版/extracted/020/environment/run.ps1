param([string]$WorkspaceRoot,[hashtable]$Arguments)
& (Join-Path $WorkspaceRoot 'candidate.ps1') @Arguments
