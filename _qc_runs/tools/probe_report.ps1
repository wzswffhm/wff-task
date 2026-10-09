$ErrorActionPreference = 'Continue'
$TaskRoot = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217'
$modulePath = Join-Path $TaskRoot 'environment\workspace\WReparse\WReparse.psd1'
Import-Module $modulePath -Force
Write-Host "module imported: $((Get-Module WReparse) -ne $null)"

$fixture = Get-Content -LiteralPath (Join-Path $env:SystemDrive 'wreparse-fixture\fixture.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$scanRoot = [string]$fixture.ScanRoot
Write-Host "scanRoot = $scanRoot"

$report = Get-WReparseReport -Root $scanRoot
Write-Host ""
Write-Host "=== 报告字段 ==="
$report.PSObject.Properties | ForEach-Object { "  $($_.Name) : $($_.Value.GetType().Name)" }

Write-Host ""
Write-Host "=== link-rel 记录 ==="
$link = $report.Records | Where-Object { $_.RelativePath -eq 'link-rel' }
if ($link) {
    $t = $link.Target
    "  Kind        = $($link.Kind)"
    "  Target      = $(if ($t -is [array]) { '[' + ($t -join ' | ') + ']' } else { $t })"
    "  TargetType  = $(if ($null -eq $t) { '<null>' } else { $t.GetType().FullName })"
    "  is [string] = $($t -is [string])"
}

Write-Host ""
Write-Host "=== 普通条目 InScope（应为 false）==="
foreach ($p in @('plain.txt', 'docs', 'hardlink.txt')) {
    $r = $report.Records | Where-Object { $_.RelativePath -eq $p }
    if ($r) { "  {0,-14} Kind={1,-10} InScope={2}" -f $p, $r.Kind, $r.InScope }
}

Write-Host ""
Write-Host "=== 导出面 ==="
$cmds = @(Get-Command -Module 'WReparse' -CommandType Function -ErrorAction SilentlyContinue)
"  数量 = $($cmds.Count)"
$cmds | ForEach-Object { "    $($_.Name)" }

Write-Host ""
Write-Host "=== 记录顺序（前 12）==="
@($report.Records | Select-Object -First 12 | ForEach-Object { [string]$_.RelativePath }) | ForEach-Object { "    $_" }

Write-Host ""
Write-Host "=== 非 ASCII 名字的相对次序 ==="
$paths = @($report.Records | ForEach-Object { [string]$_.RelativePath })
$idx = @{}
for ($i = 0; $i -lt $paths.Count; $i++) { if (-not $idx.ContainsKey($paths[$i])) { $idx[$paths[$i]] = $i } }
foreach ($n in @(([string][char]0x005A + '.txt'), ([string][char]0x00C4 + '.txt'), ([string][char]0x00F6 + '.txt'))) {
    "  {0} -> 位置 {1}" -f $n, $(if ($idx.ContainsKey($n)) { $idx[$n] } else { '<缺失>' })
}

Write-Host ""
Write-Host "=== 默认扫描的 Errors ==="
@($report.Errors | ForEach-Object { "  $($_.Code) @ $($_.RelativePath)" })
