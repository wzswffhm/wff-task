param([Parameter(Mandatory=$true)][string]$WorkspaceRoot,[string]$RepoRoot,[switch]$SkipPrebuild,[switch]$SkipCleanup)
$ErrorActionPreference='Stop'
$workspace=[IO.Path]::GetFullPath($WorkspaceRoot).TrimEnd('\')
if (-not ($workspace.StartsWith('D:\bench-runs\windows-d6-0007\',[StringComparison]::OrdinalIgnoreCase) -or $workspace.StartsWith('C:\task-state\windows-d6-0007\',[StringComparison]::OrdinalIgnoreCase))) {throw 'Workspace is outside this task'}
if (-not $RepoRoot) {$RepoRoot=Join-Path $workspace 'repo'}
if ([IO.Path]::GetFullPath($RepoRoot) -ne (Join-Path $workspace 'repo')) {throw 'Repo must be the current run repo'}
if (Test-Path -LiteralPath $RepoRoot) {throw 'Refusing to reset an existing candidate'}
New-Item -ItemType Directory -Force -Path $RepoRoot | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot 'workspace\*') -Destination $RepoRoot -Recurse
if (-not $SkipCleanup) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'provision.ps1') -WorkspaceRoot $workspace
    if ($LASTEXITCODE) {throw 'Input provisioning failed'}
}
if (-not $SkipPrebuild) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot 'tools\build.ps1') -Root $RepoRoot
    if ($LASTEXITCODE) {throw 'Initial build failed'}
}
