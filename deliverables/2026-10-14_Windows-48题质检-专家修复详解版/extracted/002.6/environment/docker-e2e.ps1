[CmdletBinding()]
param(
    [string]$TaskMount = 'C:\task'
)

$ErrorActionPreference = 'Stop'
$e2eRoot = 'C:\e2e'
if (-not (Test-Path -LiteralPath (Join-Path $TaskMount 'solution\solve.ps1') -PathType Leaf)) {
    throw "Task mount is missing solution\solve.ps1: $TaskMount"
}
if (-not (Test-Path -LiteralPath (Join-Path $TaskMount 'tests\run_tests.ps1') -PathType Leaf)) {
    throw "Task mount is missing tests\run_tests.ps1: $TaskMount"
}

if (Test-Path -LiteralPath $e2eRoot) { Remove-Item -LiteralPath $e2eRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $e2eRoot | Out-Null
Copy-Item -LiteralPath 'C:\workspace' -Destination (Join-Path $e2eRoot 'workspace') -Recurse -Force
Copy-Item -LiteralPath (Join-Path $TaskMount 'solution') -Destination (Join-Path $e2eRoot 'solution') -Recurse -Force
Copy-Item -LiteralPath (Join-Path $TaskMount 'tests') -Destination (Join-Path $e2eRoot 'tests') -Recurse -Force

& (Join-Path $e2eRoot 'solution\solve.ps1') -TaskRoot $e2eRoot
if (-not $?) { throw 'Reference solution failed.' }

$resultPath = Join-Path $e2eRoot 'results.json'
& (Join-Path $e2eRoot 'tests\run_tests.ps1') -WorkspaceRoot (Join-Path $e2eRoot 'workspace') -OutputPath $resultPath
if (-not $?) { throw 'Evaluator failed.' }
$result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
$summary = [ordered]@{
    status = [string]$result.status
    resolved = [bool]$result.resolved
    tests_total = [int]$result.tests_total
    tests_passed = [int]$result.tests_passed
    tests_failed = [int]$result.tests_failed
    programmatic_score = [double]$result.programmatic_score
    environment_digest = [string]$result.environment_digest
}
$summaryJson = $summary | ConvertTo-Json -Compress
Write-Output ('DOCKER_E2E_OK ' + $summaryJson)
if ($result.status -ne 'RESOLVED' -or [double]$result.programmatic_score -ne 1.0) { exit 3 }
