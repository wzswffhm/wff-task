[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$FixtureRoot, [string]$RunId, [string]$ReportPath)
$ErrorActionPreference = 'Stop'
$target = [IO.Path]::GetFullPath($FixtureRoot).TrimEnd('\')
$allowed = @('D:\bench-runs\windows-d6-001\', 'C:\task-state\windows-d6-001\')
if (-not @($allowed | Where-Object { $target.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }).Count) { throw 'Cleanup target is outside the task state boundary.' }
if ([IO.Path]::GetFileName($target) -ne 'state') { throw 'Cleanup only accepts the per-run state directory.' }
function Remove-StateEntry([string]$Path) {
    $entry = Get-Item -LiteralPath $Path -Force
    if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        if ($entry.PSIsContainer) { [IO.Directory]::Delete($entry.FullName, $false) } else { [IO.File]::Delete($entry.FullName) }
        return
    }
    if ($entry.PSIsContainer) {
        foreach ($child in @(Get-ChildItem -LiteralPath $entry.FullName -Force)) { Remove-StateEntry $child.FullName }
        [IO.Directory]::Delete($entry.FullName, $false)
    } else {
        [IO.File]::SetAttributes($entry.FullName, [IO.FileAttributes]::Normal)
        [IO.File]::Delete($entry.FullName)
    }
}
if (Test-Path -LiteralPath $target) {
    if (((Get-Item -LiteralPath $target -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'State root must not be a reparse point.' }
    Remove-StateEntry $target
}
$residue = [int](Test-Path -LiteralPath $target)
if ($ReportPath) {
    @{ task_id='windows-d6-001'; task_version='3.0.3'; run_id=$RunId; residue_count=$residue; fixture_root=$target } | ConvertTo-Json | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}
if ($residue -ne 0) { throw 'State cleanup left residue.' }
