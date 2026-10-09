# 用 Gold 实跑生成 REPARSE-CONTRACT.md 的行为样例（不手写，避免样例本身出错）。
#
# 流程：复制题包 -> prepare.ps1 造固定夹具 -> solve.ps1 应用 Gold ->
#       Import-Module 跑各情形 -> 取样例（平面 hashtable，避免深嵌套解析陷阱）。
#
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File make_contract_samples.ps1

[CmdletBinding()]
param(
    [string]$TaskRoot = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217',
    [string]$OutFile  = 'C:\Users\Administrator\Desktop\wff-task\.workbuddy\tmp\contract_samples.json'
)

$ErrorActionPreference = 'Stop'
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

$stage = Join-Path $env:TEMP ('wreparse-sample-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
Write-Host ('[1/6] copy task -> ' + $stage)
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
Copy-Item -LiteralPath $TaskRoot -Destination $stage -Recurse -Force

Write-Host '[2/6] prepare.ps1 builds the fixed fixture'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $stage 'tests\prepare.ps1') -TaskRoot $stage
if ($LASTEXITCODE -ne 0) { throw ('prepare.ps1 failed exit=' + $LASTEXITCODE) }

Write-Host '[3/6] solve.ps1 applies the golden payload'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $stage 'solution\solve.ps1') -TaskRoot $stage
if ($LASTEXITCODE -ne 0) { throw ('solve.ps1 failed exit=' + $LASTEXITCODE) }

$mod = Join-Path $stage 'environment\workspace\WReparse\WReparse.psd1'
Write-Host ('[4/6] Import-Module ' + $mod)
Import-Module $mod -Force

$fixture = Join-Path $env:SystemDrive 'wreparse-fixture'
$scan = Join-Path $fixture 'scanroot'
$missing = Join-Path $fixture 'no-such-root'
$plainFile = Join-Path $fixture 'outside\plain.txt'
$empty = Join-Path $env:TEMP ('wreparse-empty-' + [guid]::NewGuid().ToString('N').Substring(0, 6))

function J([object]$report) { ConvertTo-WReparseJson -Report $report }

Write-Host '[5/6] collect samples'
$h = @{}
$r = Get-WReparseReport -Root $scan
$j = J $r

$h['schema_version'] = Get-WReparseSchemaVersion
$h['module_exports'] = @((Get-Command -Module 'WReparse' -ErrorAction SilentlyContinue).Name | Sort-Object)
$h['report_field_order'] = @($r.PSObject.Properties.Name)
$h['root'] = $r.Root
$h['stats'] = $r.Stats
$h['errors'] = $r.Errors
$h['records_head'] = @($r.Records | Select-Object -First 6)
$h['records_reparse'] = @($r.Records | Where-Object { $_.Kind -eq 'ReparsePoint' } | Select-Object -First 6)
$h['records_nonascii'] = @($r.Records | Where-Object { $_.RelativePath -match '^[^\u0000-\u007F]' } | Select-Object -First 4)
$h['records_by_depth_desc'] = @($r.Records | Sort-Object -Property Depth -Descending | Select-Object -First 3)
$h['records_first8_paths'] = @($r.Records | Select-Object -First 8 | ForEach-Object { $_.RelativePath })

$rf = Get-WReparseReport -Root $scan -Follow
$h['follow_field_order'] = @($rf.PSObject.Properties.Name)
$h['follow_stats'] = $rf.Stats
$h['follow_errors'] = $rf.Errors
$h['follow_prefix_records'] = @($rf.Records | Where-Object { $_.RelativePath -match '^(j|s|rel|relfile|dangling|up)\\' } | Select-Object -First 6)

$h['md0_stats'] = (Get-WReparseReport -Root $scan -MaxDepth 0).Stats
$h['mdneg_stats'] = (Get-WReparseReport -Root $scan -MaxDepth -1).Stats
$h['md1_stats'] = (Get-WReparseReport -Root $scan -MaxDepth 1).Stats
$h['md0_errors'] = (Get-WReparseReport -Root $scan -MaxDepth 0).Errors

$h['not_found_errors'] = (Get-WReparseReport -Root $missing).Errors
$h['structure_errors'] = (Get-WReparseReport -Root $plainFile).Errors

$h['canonical_outside'] = Get-WReparseCanonicalPath -Path (Join-Path $fixture 'outside')
$h['canonical_with_inner_case'] = Get-WReparseCanonicalPath -Path (Join-Path (Join-Path $fixture 'outside') 'PLAIN.TXT')
$h['canonical_trailing_sep'] = Get-WReparseCanonicalPath -Path (Join-Path $fixture 'outside\')
$h['within_root_inside'] = Test-WReparseWithinRoot -Path (Join-Path $scan 'docs') -Root $scan
$h['within_root_prefix_sibling'] = Test-WReparseWithinRoot -Path (Join-Path $fixture 'scanroot-extra') -Root $scan
$h['within_root_equal'] = Test-WReparseWithinRoot -Path $scan -Root $scan

$h['byte_identical_two_calls'] = ((J $r) -ceq (J (Get-WReparseReport -Root $scan)))
$h['json_first_600_chars'] = $j.Substring(0, [Math]::Min(600, $j.Length))
$h['json_last_400_chars'] = $j.Substring([Math]::Max(0, $j.Length - 400))

New-Item -ItemType Directory -Path $empty -Force | Out-Null
$er = Get-WReparseReport -Root $empty
$h['empty_report_json'] = J $er
$h['empty_records'] = $er.Records
$h['empty_errors'] = $er.Errors
Remove-Item -LiteralPath $empty -Recurse -Force -ErrorAction SilentlyContinue

$h['full_scanroot_report_json'] = $j

Write-Host '[6/6] write samples'
$dir = Split-Path -Parent $OutFile
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$out = $h | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($OutFile, $out, (New-Object System.Text.UTF8Encoding($false)))
Write-Host ('done -> ' + $OutFile + '  (' + (Get-Item $OutFile).Length + ' B)')
