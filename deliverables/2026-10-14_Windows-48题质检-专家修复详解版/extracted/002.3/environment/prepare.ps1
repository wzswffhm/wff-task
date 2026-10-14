[CmdletBinding()]
param([string]$WorkspaceRoot = 'C:\workspace', [string]$RepoRoot = '', [switch]$SkipPrebuild, [switch]$SkipCleanup)
$ErrorActionPreference = 'Stop'
if (-not $RepoRoot) { $RepoRoot = Join-Path $WorkspaceRoot 'repo' }
$repo = [IO.Path]::GetFullPath($RepoRoot)
$workspace = [IO.Path]::GetFullPath($WorkspaceRoot).TrimEnd('\')
if (-not $repo.StartsWith($workspace + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Repository must be inside the independent workspace.' }
if (Test-Path -LiteralPath $repo) { throw 'Preparation requires a fresh repository path.' }
New-Item -ItemType Directory -Path $repo -Force | Out-Null
Copy-Item -Path (Join-Path $PSScriptRoot 'workspace\*') -Destination $repo -Recurse -Force
Write-Output "Prepared windows-d6-001 baseline at $repo"
