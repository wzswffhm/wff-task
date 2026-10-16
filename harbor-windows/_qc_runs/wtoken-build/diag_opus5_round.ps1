# Run one Opus round with claude-opus-5 and capture what actually happens.
#
# Context: the same endpoint answers a direct POST with model=claude-opus-5 in
# 4-14 seconds for both short and full-instruction payloads, yet 18 consecutive
# Harbor rounds came back as a single step. Either the upstream is inconsistent
# between transports, or something about the agent's own payload differs. This
# prints the round's raw artifacts so the answer is evidence, not a guess.

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

$job = 'model-opus-1'
Remove-Item -LiteralPath (Join-Path $stage $job) -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ("=== running {0} with claude-opus-5 at {1} ===" -f $job, (Get-Date -Format 'HH:mm:ss'))
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

$dir = Get-ChildItem -LiteralPath (Join-Path $stage $job) -Directory -ErrorAction SilentlyContinue |
       Where-Object { $_.Name -like 'wfflab__*' } | Select-Object -First 1
if (-not $dir) { Write-Host '  no trial directory'; exit 0 }

Write-Host '--- artifacts ---'
Get-ChildItem -LiteralPath $dir.FullName -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host ("  {0,-44} {1,8:N0} B" -f $_.FullName.Substring($dir.FullName.Length + 1), $_.Length)
}

$mr = Join-Path $dir.FullName 'agent\model-result.json'
if (Test-Path -LiteralPath $mr) {
    $m = Get-Content -LiteralPath $mr -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ("--- model-result: steps={0} out={1} model={2} stop={3} submitted={4}" -f $m.steps, $m.output_tokens, $m.model, $m.last_stop_reason, $m.submitted)
}

Write-Host '--- trajectory (assistant turns) ---'
$tr = Join-Path $dir.FullName 'agent\trajectory.jsonl'
if (Test-Path -LiteralPath $tr) {
    Get-Content -LiteralPath $tr -Encoding UTF8 | ForEach-Object {
        $o = $_ | ConvertFrom-Json
        if ($o.kind -eq 'user') {
            Write-Host ("  [{0}] user: <{1} chars>" -f $o.step, $o.text.Length)
        } else {
            Write-Host ("  [{0}] {1}: {2}" -f $o.step, $o.kind, $_.Substring(0, [Math]::Min(220, $_.Length)))
        }
    }
}

$rw = Join-Path $dir.FullName 'verifier\reward.json'
if (Test-Path -LiteralPath $rw) {
    Write-Host ('--- reward: ' + (Get-Content -LiteralPath $rw -Raw -Encoding UTF8 | ConvertFrom-Json).reward)
}
