$ErrorActionPreference = 'Continue'
$runner = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner'
$report = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-07_wfmt215-outside-repair\_cleanup_4router.txt'

"[{0}] cleanup" -f (Get-Date -Format o) | Set-Content -LiteralPath $report -Encoding UTF8

# 1. Disable the wfp shards so a stale far-future trigger can never re-fire.
foreach ($t in @('oh-wfp1','oh-wfp2','oh-wfp3')) {
    try { Disable-ScheduledTask -TaskName $t -ErrorAction Stop | Out-Null; "$t disabled" | Add-Content $report }
    catch { "$t disable failed: $_" | Add-Content $report }
}
Get-ScheduledTask | Where-Object { $_.TaskName -like 'oh-*' } | ForEach-Object {
    "$($_.TaskName)`t$($_.State)" } | Add-Content $report

"=== all oh-* triggers (StartBoundary) ===" | Add-Content $report
Get-ScheduledTask | Where-Object { $_.TaskName -like 'oh-*' } | ForEach-Object {
    $b = ($_.Triggers | ForEach-Object { $_.StartBoundary }) -join ';'
    "$($_.TaskName)`t$b" } | Add-Content $report

"=== containers ===" | Add-Content $report
(docker ps -a --format '{{.Names}} {{.Status}}' 2>&1) | Add-Content $report
"done" | Add-Content $report
