# Offline re-evaluation: replay round-7 candidate workspaces against the
# repaired check set, so the differentiation gate can be recomputed without a
# multi-hour rerun. Uses temporary copies only.
$ErrorActionPreference = 'Continue'

$ps51 = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$taskSrc  = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217'
$workRoot = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner\work'
$root     = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-06_wreparse217-task-surface-repair\_reeval'
Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue

$runs = @(
    @{ id = '20261005T232059-candidate-opus-5-01';                 model = 'OPUS'; old = 1 },
    @{ id = '20261005T232740-candidate-opus-5-02';                 model = 'OPUS'; old = 1 },
    @{ id = '20261005T234602-candidate-opus-5-03';                 model = 'OPUS'; old = 1 },
    @{ id = '20261005T232059-candidate-qwen3.8-max-0902-01';       model = 'QWEN'; old = 1 },
    @{ id = '20261005T235615-candidate-qwen3.8-max-0902-02';       model = 'QWEN'; old = 'error(excluded)' },
    @{ id = '20261006T004405-candidate-qwen3.8-max-0902-03';       model = 'QWEN'; old = 1 }
)

$sum = @{ OPUS = 0; QWEN = 0 }

foreach ($run in $runs) {
    $tmp = Join-Path $root $run.id
    New-Item -ItemType Directory -Path $tmp -Force | Out-Null
    Copy-Item -Recurse -Force $taskSrc $tmp
    $task = Join-Path $tmp 'wfflab__wreparse-217'

    $cand = Join-Path $workRoot "$($run.id)\case\environment\workspace\WReparse"
    if (-not (Test-Path -LiteralPath $cand)) {
        Write-Output ("{0,-46} {1}  MISSING WORKSPACE" -f $run.id, $run.model)
        continue
    }
    & robocopy $cand (Join-Path $task 'environment\workspace\WReparse') /MIR /NFL /NDL /NJH /NJS /NP | Out-Null

    & $ps51 -NoProfile -ExecutionPolicy Bypass -File (Join-Path $task 'environment\run.ps1') -TaskRoot $task 2>&1 | Out-Null
    $rc = $LASTEXITCODE

    $cPath = Join-Path $task 'results\checks.json'
    $rPath = Join-Path $task 'results\result.json'
    if (-not (Test-Path $rPath)) {
        Write-Output ("{0,-46} {1}  NO RESULT (runner exit=$rc)" -f $run.id, $run.model)
        continue
    }
    $res = Get-Content $rPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $checks = Get-Content $cPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $failed = @($checks.checks | Where-Object { $_.status -ne 'PASS' })
    $passCount = @($checks.checks | Where-Object { $_.status -eq 'PASS' }).Count

    $v = [int]$res.verdict
    $sum[$run.model] += $v
    Write-Output ("{0,-46} {1}  NEW verdict={2}  checks {3}/{4} passed  (was {5})" -f `
            $run.id, $run.model, $v, $passCount, @($checks.checks).Count, $run.old)
    if ($failed.Count -gt 0) {
        foreach ($f in $failed) { Write-Output ("        FAIL: {0} -- {1}" -f $f.test_id, $f.detail) }
    }
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}

Write-Output ''
Write-Output ("=== RECOMPUTED (new checks, round-7 workspaces) ===")
Write-Output ("sum(OPUS) = {0}" -f $sum.OPUS)
Write-Output ("sum(QWEN) = {0}" -f $sum.QWEN)
Write-Output ("opus_sum_greater_than_qwen = {0}" -f ($sum.OPUS -gt $sum.QWEN))
