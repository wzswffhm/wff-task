param([Parameter(Mandatory=$true)][string]$WorkspaceRoot,[Parameter(Mandatory=$true)][string]$OutputPath,[string]$Python='python')
& $Python (Join-Path $PSScriptRoot 'verify_task.py') --task-root (Split-Path -Parent $PSScriptRoot) --workspace $WorkspaceRoot --output $OutputPath --run-id ([Guid]::NewGuid().ToString('N'))
exit $LASTEXITCODE
