# Development helper (not part of the task package).
#
# Runs the WReparse checks twice on isolated copies of the task tree:
#   base   -> the shipped workspace, defects present, must fail
#   oracle -> solution/solve.ps1 applied, must pass every check
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File verify-local.ps1 -TaskRoot <task dir>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TaskRoot,
    [string]$WorkRoot = ''
)

$ErrorActionPreference = 'Stop'

$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path
if ([string]::IsNullOrWhiteSpace($WorkRoot)) { $WorkRoot = Join-Path $env:TEMP 'wreparse-verify' }

if (Test-Path -LiteralPath $WorkRoot) { Remove-Item -LiteralPath $WorkRoot -Recurse -Force }
New-Item -ItemType Directory -Path $WorkRoot -Force | Out-Null

function Copy-Payload {
    param([string]$Destination)
    # Exclude runtime state so each copy starts clean.
    & robocopy $TaskRoot $Destination /E /NFL /NDL /NJH /NJS /NP /XD .fixture results /XF '' | Out-Null
}

function Show-Checks {
    param([string]$ChecksPath, [string]$Label)
    if (-not (Test-Path -LiteralPath $ChecksPath)) { Write-Host "$Label : no checks file"; return }
    $checks = Get-Content -LiteralPath $ChecksPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $failed = @($checks.checks | Where-Object { $_.status -ne 'PASS' })
    $passed = @($checks.checks | Where-Object { $_.status -eq 'PASS' })
    Write-Host ("$Label : {0} passed / {1} failed / {2} total" -f $passed.Count, $failed.Count, @($checks.checks).Count)
    foreach ($item in $failed) { Write-Host ("    FAIL {0} -- {1}" -f $item.test_id, $item.detail) }
}

function Invoke-Task {
    param([string]$Root)
    & (Join-Path $Root 'environment\run.ps1') -TaskRoot $Root -OutputPath (Join-Path $Root 'results\result.json') | Out-Null
    return $LASTEXITCODE
}

# ---- base ------------------------------------------------------------------
$baseRoot = Join-Path $WorkRoot 'base'
Copy-Payload -Destination $baseRoot
$baseExit = Invoke-Task -Root $baseRoot
Show-Checks -ChecksPath (Join-Path $baseRoot 'results\checks.json') -Label 'BASE'
$baseResult = Get-Content -LiteralPath (Join-Path $baseRoot 'results\result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host ("BASE exit={0} verdict={1} status={2}" -f $baseExit, $baseResult.verdict, $baseResult.test.report.status)

# ---- oracle ----------------------------------------------------------------
$oracleRoot = Join-Path $WorkRoot 'oracle'
Copy-Payload -Destination $oracleRoot
& (Join-Path $oracleRoot 'solution\solve.ps1') -TaskRoot $oracleRoot | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'solve.ps1 failed' }
$oracleExit = Invoke-Task -Root $oracleRoot
Show-Checks -ChecksPath (Join-Path $oracleRoot 'results\checks.json') -Label 'ORACLE'
$oracleResult = Get-Content -LiteralPath (Join-Path $oracleRoot 'results\result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host ("ORACLE exit={0} verdict={1} status={2}" -f $oracleExit, $oracleResult.verdict, $oracleResult.test.report.status)

# ---- cleanup idempotence ---------------------------------------------------
foreach ($root in @($baseRoot, $oracleRoot)) {
    & (Join-Path $root 'environment\cleanup.ps1') -TaskRoot $root | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "cleanup.ps1 failed for $root" }
}
Write-Host 'CLEANUP: both trees clean'

Write-Host ''
Write-Host ("SUMMARY baseExit={0} baseVerdict={1} oracleExit={2} oracleVerdict={3}" -f `
        $baseExit, $baseResult.verdict, $oracleExit, $oracleResult.verdict)
