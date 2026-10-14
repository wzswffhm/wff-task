param([Parameter(Mandatory=$true)][string]$RepoRoot)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Native Windows is required.' }
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'src\PathAclTool\PathAclTool.csproj'))) { throw 'Candidate project missing.' }
Push-Location $RepoRoot
try {
    $sdk = & dotnet --version
    if ($LASTEXITCODE -ne 0 -or $sdk -ne '8.0.424') { throw 'Frozen .NET SDK 8.0.424 is required.' }
} finally { Pop-Location }
Write-Output 'Native Windows / frozen SDK readiness passed.'
