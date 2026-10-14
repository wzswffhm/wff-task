param([Parameter(Mandatory=$true)][string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'
$resolved = [IO.Path]::GetFullPath($WorkspaceRoot)
$allowed = [IO.Path]::GetFullPath('C:\OutsideHarborRuns\')
if (-not $resolved.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase) -or $resolved.TrimEnd('\') -eq $allowed.TrimEnd('\')) { throw 'Cleanup outside assigned run root refused' }
if (Test-Path -LiteralPath $resolved) { Remove-Item -LiteralPath $resolved -Recurse -Force }
exit 0
