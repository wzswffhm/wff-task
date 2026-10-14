param([string]$RepoRoot = $env:HARBOR_REPO_ROOT, [string]$ResultsDir = 'C:\logs\verifier\results')
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'run_tests.ps1') -RepoRoot $RepoRoot -ResultsDir $ResultsDir
$code = $LASTEXITCODE
$result = Get-Content -LiteralPath (Join-Path $ResultsDir 'result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($result.validity -eq 'VALID') { Set-Content -LiteralPath 'C:\logs\verifier\reward.txt' -Value $result.score -Encoding ASCII }
exit $code
