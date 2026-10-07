# Local oracle/candidate verification for the wreparse-217 task-surface repair.
# Runs entirely on temporary copies; the real task tree is never touched.
$ErrorActionPreference = 'Stop'

$src  = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217'
$root = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-06_wreparse217-task-surface-repair\_verify'
Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue

foreach ($case in @(@{ n = 'golden'; g = $true }, @{ n = 'candidate'; g = $false })) {
    $tmp = Join-Path $root $case.n
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    Copy-Item -Recurse -Force $src $tmp
    $task = Join-Path $tmp 'wfflab__wreparse-217'
    if ($case.g) {
        & robocopy (Join-Path $task 'solution\reference\WReparse') (Join-Path $task 'environment\workspace\WReparse') /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    }
    $runner = Join-Path $task 'environment\run.ps1'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $runner -TaskRoot $task 2>&1 | Out-Null
    $rc = $LASTEXITCODE
    Write-Output "### $($case.n) : runner exit=$rc"
    $cj = Join-Path $task 'results\checks.json'
    if (Test-Path $cj) {
        $checks = Get-Content $cj -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($c in $checks.checks) {
            $mark = if ($c.status -eq 'PASS') { '  ' } else { '<<' }
            Write-Output ("   {0,-4} {1} {2}" -f $c.status, $c.test_id, $mark)
        }
    }
    else { Write-Output '   (no checks.json produced)' }
    $rj = Join-Path $task 'results\result.json'
    if (Test-Path $rj) {
        $res = Get-Content $rj -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-Output ("   RESULT verdict={0}  reason={1}" -f $res.verdict, $res.reason)
    }
    Write-Output ''
}
