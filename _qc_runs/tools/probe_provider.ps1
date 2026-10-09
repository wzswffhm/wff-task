# 探针：实测 provider 对各类重解析点的 LinkType / Target 返回类型。
param([string]$TaskRoot)

$sr = Join-Path $env:SystemDrive 'wreparse-fixture\scanroot'
Import-Module (Join-Path $TaskRoot 'environment\workspace\WReparse\WReparse.psd1') -Force

Write-Host "=== 重解析点 ==="
Get-ChildItem -LiteralPath $sr -Force |
    Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint } |
    ForEach-Object {
        $t = $_.Target
        $tt = if ($null -eq $t) { '<null>' } else { $t.GetType().FullName }
        $tv = if ($t -is [array]) { '[' + (($t | ForEach-Object { $_.ToString() }) -join ' | ') + ']' } else { "$t" }
        "{0,-16} LinkType={1,-14} TargetType={2,-26} Target={3}" -f $_.Name, $_.LinkType, $tt, $tv
    }

Write-Host ""
Write-Host "=== 硬链接 ==="
$hl = Get-ChildItem -LiteralPath $sr -Force | Where-Object { $_.Name -eq 'hardlink.txt' }
"  LinkType={0}  Attributes={1}  TargetType={2}" -f $hl.LinkType, $hl.Attributes, $(if ($null -eq $hl.Target) { '<null>' } else { $hl.Target.GetType().FullName })

Write-Host ""
Write-Host "=== 模块导出面 ==="
$cmds = @(Get-Command -Module 'WReparse' -CommandType Function -ErrorAction SilentlyContinue)
"  导出函数数 = {0}" -f $cmds.Count
$cmds | ForEach-Object { "    $($_.Name)" }
