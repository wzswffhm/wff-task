# Run all three Opus rounds with claude-opus-5 after the payload fixes.
#
# Two upstream constraints were isolated by direct boundary tests and are now
# worked around in the agent, without touching the model name or any recorded
# value:
#   * sending the `system` field      -> upstream returns a stub
#   * sending `tool_result` blocks    -> upstream returns a stub
# Both are handled by carrying the same content as plain text instead.
#
# A round counts as valid only when the agent genuinely worked (many steps, real
# output tokens) and the verifier produced a reward.

$ErrorActionPreference = 'Continue'

$build = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wtoken-build'
$stage = Join-Path $build 'model-rounds\jobs'
$pkg = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wtoken-221-v1.0.0-delivery'
$harbor = 'C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe'
$models = 'C:\Users\Administrator\Desktop\wff-task\models.local.json'

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:no_proxy = '*'
$env:NO_PROXY = '*'
$env:PATH = 'C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts;C:\Program Files\Docker\Docker\resources\bin;' + $env:PATH
$env:PYTHONPATH = (Join-Path $build 'harbor_agent') + [IO.Path]::PathSeparator + $env:PYTHONPATH

$cfg = Get-Content -LiteralPath $models -Raw -Encoding UTF8 | ConvertFrom-Json
$opus = $cfg.endpoints | Where-Object { $_.key -eq 'opus-5' } | Select-Object -First 1
$env:WFF_OPUS_KEY = $opus.api_key

function Get-Round([string]$job) {
    $dir = Get-ChildItem -LiteralPath (Join-Path $stage $job) -Directory -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -like 'wfflab__*' } | Select-Object -First 1
    if (-not $dir) { return $null }
    $rw = Join-Path $dir.FullName 'verifier\reward.json'
    $mr = Join-Path $dir.FullName 'agent\model-result.json'
    $r = if (Test-Path -LiteralPath $rw) { (Get-Content -LiteralPath $rw -Raw -Encoding UTF8 | ConvertFrom-Json).reward } else { $null }
    $s = $null; $o = $null
    if (Test-Path -LiteralPath $mr) {
        $m = Get-Content -LiteralPath $mr -Raw -Encoding UTF8 | ConvertFrom-Json
        $s = $m.steps; $o = $m.output_tokens
    }
    return [pscustomobject]@{ reward = $r; steps = $s; out = $o }
}

foreach ($i in 1..3) {
    $job = "model-opus-$i"
    $existing = Get-Round $job
    if ($existing -and $existing.steps -gt 5 -and $existing.out -gt 100 -and $null -ne $existing.reward) {
        Write-Host ("=== {0}: already valid (steps={1} out={2} reward={3}) ===" -f $job, $existing.steps, $existing.out, $existing.reward)
        continue
    }

    Write-Host ("=== {0} starting {1} (claude-opus-5) ===" -f $job, (Get-Date -Format 'HH:mm:ss'))
    Remove-Item -LiteralPath (Join-Path $stage $job) -Recurse -Force -ErrorAction SilentlyContinue

    $t0 = Get-Date
    & $harbor run --path $pkg `
        --agent 'wtoken_model_agent:WindowsCodingModelAgent' `
        --model 'claude-opus-5' `
        --ak 'alias=opus' `
        --ak ('base_url=' + $opus.base_url) `
        --ak ('auth=' + $opus.auth) `
        --ak 'api_key_env=WFF_OPUS_KEY' `
        --ak ('max_tokens=' + $opus.max_tokens) `
        --jobs-dir $stage --job-name $job 2>&1 |
        Select-Object -Last 2 | ForEach-Object { Write-Host ('  ' + $_) }
    Write-Host ("  elapsed {0}s" -f [int]((Get-Date) - $t0).TotalSeconds)

    $r = Get-Round $job
    if ($r) {
        Write-Host ("  steps={0} out={1} reward={2}" -f $r.steps, $r.out, $r.reward)
    } else {
        Write-Host '  no result produced'
    }
}

Write-Host '--- opus summary ---'
$sum = 0
foreach ($i in 1..3) {
    $r = Get-Round "model-opus-$i"
    if ($r) {
        $ok = ($r.steps -gt 5) -and ($r.out -gt 100) -and ($null -ne $r.reward)
        if ($ok -and $null -ne $r.reward) { $sum += [int]$r.reward }
        Write-Host ("  model-opus-{0}: steps={1} out={2} reward={3} valid={4}" -f $i, $r.steps, $r.out, $r.reward, $ok)
    } else {
        Write-Host ("  model-opus-{0}: MISSING" -f $i)
    }
}
Write-Host ("opus model_score_sum = {0}" -f $sum)
