param([Parameter(Mandatory=$true)][string]$ResultPath)
$ErrorActionPreference = 'Stop'
$rubric = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'rubric.json') -Raw | ConvertFrom-Json
$result = Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
$required = @($rubric.testcases | Where-Object required)
$seen = @($result.testcases)
$valid = $result.validity -eq 'VALID'
foreach ($test in $required) {
    $matches = @($seen | Where-Object { $_.id -eq $test.id })
    if ($matches.Count -ne 1 -or $matches[0].status -notin @('PASS','FAIL')) { $valid = $false }
}
if (-not $valid) { Write-Output '{"validity":"INVALID","score":null}'; exit 2 }
$score = if (@($seen | Where-Object { $_.status -eq 'FAIL' }).Count -eq 0) { 1 } else { 0 }
[pscustomobject]@{validity='VALID';score=$score} | ConvertTo-Json -Compress
if ($score -eq 1) { exit 0 }; exit 1
