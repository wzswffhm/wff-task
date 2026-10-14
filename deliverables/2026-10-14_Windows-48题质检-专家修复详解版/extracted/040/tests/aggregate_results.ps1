[CmdletBinding()]
param([string]$ResultPath='C:\logs\verifier\report.json')
$ErrorActionPreference = 'Stop'
$r = Get-Content -Raw -LiteralPath $ResultPath | ConvertFrom-Json
if ($r.validity -ne 'VALID' -or $r.status -ne 'VALID') { exit 2 }
$manifest = @(Get-Content -Raw (Join-Path $PSScriptRoot 'required_testcases.json') | ConvertFrom-Json)
$cases = @($r.testcases)
if ($cases.Count -ne $manifest.Count -or @($cases.id | Select-Object -Unique).Count -ne $manifest.Count) { exit 2 }
foreach ($expected in $manifest) {
    $actual = @($cases | Where-Object id -eq $expected.id)
    if ($actual.Count -ne 1 -or $actual[0].group -ne $expected.group -or $actual[0].status -notin @('PASS','FAIL')) { exit 2 }
}
$computed = [int](@($cases | Where-Object status -ne 'PASS').Count -eq 0)
if ($r.score -ne $computed) { exit 2 }
if ($computed -eq 1) { exit 0 }
exit 1
