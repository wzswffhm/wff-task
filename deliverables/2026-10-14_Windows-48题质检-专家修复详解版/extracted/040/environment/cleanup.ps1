[CmdletBinding()]
param([string]$TaskRoot=(Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $TaskRoot 'environment\workspace'))
# Only terminate fixture processes whose command line names this workspace.
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine.IndexOf($workspace, [StringComparison]::OrdinalIgnoreCase) -ge 0
} | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
$results = Join-Path $TaskRoot 'results'
if (Test-Path -LiteralPath $results) { Remove-Item -LiteralPath $results -Recurse -Force }
# All inline child processes are terminated by verifier finally blocks. Harbor
# removes the per-trial container, which is the process isolation boundary.
