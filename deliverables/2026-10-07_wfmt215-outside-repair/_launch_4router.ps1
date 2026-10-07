# Register + start 3 parallel OPUS singleton shards against wfflab__wfmt-215.
# Pattern copied from the established wfq4/5/6 and wfo6/7/8 launches:
#   - one shard per run (parallel singletons beat one serial Runs=3 shard)
#   - -Execute MUST be the ABSOLUTE powershell path (bare name -> 0x80070002)
#   - trigger pushed far into the future so the task never re-fires on its own
$ErrorActionPreference = 'Continue'

$runner = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner'
$psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$matrix = Join-Path $runner 'matrix-task.ps1'
$report = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-07_wfmt215-outside-repair\_launch_4router.txt'

"[{0}] psExe={1}" -f (Get-Date -Format o), $psExe | Set-Content -LiteralPath $report -Encoding UTF8
"matrix={0} exists={1}" -f $matrix, (Test-Path -LiteralPath $matrix) | Add-Content -LiteralPath $report -Encoding UTF8

$tags = @('wfp1', 'wfp2', 'wfp3')
foreach ($tag in $tags) {
    $name = 'oh-' + $tag
    $arg = '-File "' + $matrix + '" -Tag ' + $tag + ' -Models OPUS -Runs 1 -TaskId wfflab__wfmt-215'
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    $action = New-ScheduledTaskAction -Execute $psExe -Argument $arg -WorkingDirectory $runner
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddDays(90)
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -StartWhenAvailable
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName $name
    "[{0}] {1} registered+started" -f (Get-Date -Format o), $name | Add-Content -LiteralPath $report -Encoding UTF8
}

Start-Sleep -Seconds 12
Get-ScheduledTask | Where-Object { $_.TaskName -like 'oh-wfp*' } | ForEach-Object {
    $i = $_ | Get-ScheduledTaskInfo
    "{0}`t{1}`tLast={2}`tRes={3}" -f $_.TaskName, $_.State, $i.LastRunTime, $i.LastTaskResult
} | Add-Content -LiteralPath $report -Encoding UTF8
"=== containers ===" | Add-Content -LiteralPath $report -Encoding UTF8
(docker ps --format '{{.Names}}`t{{.Status}}' 2>&1) | Add-Content -LiteralPath $report -Encoding UTF8
"done" | Add-Content -LiteralPath $report -Encoding UTF8
