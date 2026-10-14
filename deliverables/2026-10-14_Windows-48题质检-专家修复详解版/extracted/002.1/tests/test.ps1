$ErrorActionPreference = 'Stop'
# Harbor uploads the judge only after the agent has finished.
$taskRoot = 'C:\harbor\task'
$testsRoot = Join-Path $taskRoot 'tests'
New-Item -ItemType Directory -Force -Path $testsRoot | Out-Null
Get-ChildItem -LiteralPath $PSScriptRoot -Force | Copy-Item -Destination $testsRoot -Recurse -Force
$env:HARBOR_IMAGE_ROLE = 'verifier'
$results = 'C:\logs\verifier\results'
& (Join-Path $testsRoot 'run_tests.ps1') -RepoRoot $env:HARBOR_REPO_ROOT -ResultsDir $results
$code = $LASTEXITCODE
$result = Get-Content -LiteralPath (Join-Path $results 'result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($result.validity -eq 'VALID') { Set-Content -LiteralPath 'C:\logs\verifier\reward.txt' -Value $result.score -Encoding ASCII }
exit $code
