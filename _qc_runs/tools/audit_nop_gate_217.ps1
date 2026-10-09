$ErrorActionPreference = 'Stop'
$TaskRoot = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217'
$checksPath = Join-Path $TaskRoot 'results\checks.json'

$declared = Get-Content -LiteralPath (Join-Path $TaskRoot 'tests\required_testcases.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$payload = Get-Content -LiteralPath $checksPath -Raw -Encoding UTF8 | ConvertFrom-Json

$status = @{}
foreach ($c in $payload.checks) { $status[[string]$c.test_id] = [string]$c.status }

$f2pFail = 0; $f2pPass = 0; $p2pFail = 0; $p2pPass = 0
$problems = New-Object System.Collections.ArrayList

foreach ($d in $declared) {
    $id = [string]$d.id
    $group = [string]$d.group
    if (-not $status.ContainsKey($id)) {
        [void]$problems.Add("$id 未出现在 checks.json 中（声明为 $group）")
        continue
    }
    $st = $status[$id]
    if ($group -eq 'F2P') {
        if ($st -eq 'PASS') { $f2pPass++ } else { $f2pFail++ }
    }
    else {
        if ($st -eq 'PASS') { $p2pPass++ } else { $p2pFail++ }
    }
}

Write-Host "声明总数 = $($declared.Count)"
Write-Host "F2P: PASS=$f2pPass  FAIL=$f2pFail"
Write-Host "P2P: PASS=$p2pPass  FAIL=$p2pFail"
Write-Host ""

# NOP 门禁：全部 F2P 必须 FAIL，全部 P2P 必须 PASS
if ($p2pFail -ne 0) { [void]$problems.Add("NOP 下 $p2pFail 个 P2P 未通过（P2P 必须全过）") }
if ($f2pFail -eq 0) { [void]$problems.Add('NOP 下没有任何 F2P 失败（至少要有一个核心 F2P 失败）') }

# 未在 required 里声明却出现在 checks 里的
$declaredIds = @($declared | ForEach-Object { [string]$_.id })
$extra = @($payload.checks | Where-Object { $declaredIds -notcontains [string]$_.test_id })
if ($extra.Count -gt 0) { [void]$problems.Add("checks.json 里有 $($extra.Count) 个未声明的检查: $((@($extra | ForEach-Object { $_.test_id })) -join ', ')") }

Write-Host "task_version(checks.json) = $($payload.task_version)"
Write-Host ""
if ($problems.Count -gt 0) {
    Write-Host 'NOP 门禁问题：'
    $problems | ForEach-Object { "  - $_" }
    exit 1
}
Write-Host 'NOP 门禁：符合（全部 F2P FAIL、全部 P2P PASS）'
exit 0
