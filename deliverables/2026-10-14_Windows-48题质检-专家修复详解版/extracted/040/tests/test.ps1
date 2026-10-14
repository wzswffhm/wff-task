[CmdletBinding()]
param(
    [string]$TaskRoot = 'C:\task',
    [string]$WorkspaceRoot = '',
    [string]$OutputPath = 'C:\logs\verifier\report.json'
)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) { $WorkspaceRoot = Join-Path $TaskRoot 'environment\workspace' }
$python = if (Test-Path 'C:\Python\python.exe') { 'C:\Python\python.exe' } else { (Get-Command python -ErrorAction Stop).Source }
& $python (Join-Path $PSScriptRoot 'run_tests.py') --workspace $WorkspaceRoot --rubric (Join-Path $PSScriptRoot 'rubric.json') --output $OutputPath
exit $LASTEXITCODE
