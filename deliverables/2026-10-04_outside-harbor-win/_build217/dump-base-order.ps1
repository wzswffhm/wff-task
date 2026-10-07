# Dev helper: dump the BASE record order to confirm why the ordering check fails.
$ErrorActionPreference = 'Stop'
$T = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217'
Import-Module (Join-Path $T 'environment\workspace\WReparse\WReparse.psd1') -Force
$fx = Get-Content -LiteralPath (Join-Path $T '.fixture\fixture.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Set-Location -LiteralPath $T
$r = Get-WReparseReport -Root $fx.ScanRoot
$i = 0
foreach ($rec in $r.Records) {
    $i++
    Write-Host ("{0,3}  {1,-30} {2,-13} depth={3}" -f $i, $rec.RelativePath, $rec.Kind, $rec.Depth)
}
