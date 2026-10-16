# Retry the Opus rounds until all three produce real work.
#
# Observation so far: 4router.net intermittently answers. Identical requests
# usually return the "upstream returned nothing" stub within seconds (one step,
# ~36 output tokens), but when the window opens the same call runs 13-26 minutes
# with 10k+ output tokens and a real reward. So this loops patiently.
#
# The model name must be claude-opus-5: QC's canonical_model() only recognises
# names in its ALIASES table (opus / opus-5 / claude-opus-5), so the endpoint's
# own label claude-opus-4-8 would be rejected as an unrecognised alias even
# though the endpoint serves it.
#
# A round counts only when the agent genuinely engaged AND the verifier wrote a
# reward. A 40-minute cap per round prevents the container deadlock seen earlier
# from silently consuming the night.

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

function Wait-Round([string]$job, [int]$capSeconds) {
    $t0 = Get-Date
    $proc = Start-Process -FilePath $harbor -ArgumentList @(
        'run', '--path', $pkg,
        '--agent', 'wtoken_model_agent:WindowsCodingModelAgent',
        '--model', 'claude-opus-5',
        '--ak', 'alias=opus',
        '--ak', ('base_url=' + $opus.base_url),
        '--ak', ('auth=' + $opus.auth),
        '--ak', 'api_key_env=WFF_OPUS_KEY',
        '--ak', ('max_tokens=' + $opus.max_tokens),
        '--jobs-dir', $stage, '--job-name', $job
    ) -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $build ($job + '.out')) -RedirectStandardError (Join-Path $build ($job + '.err'))

    while (-not $proc.HasExited -and ((Get-Date) - $t0).TotalSeconds -lt $capSeconds) {
        Start-Sleep -Seconds 15
    }
    if (-not $proc.HasExited) {
        Write-Host ("    {0} hit the {1}s cap, killing" -f $job, $capSeconds)
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 5
        $leftover = docker --context desktop-windows ps -aq --filter 'name=harbor-' 2>&1
        if ($leftover) { docker --context desktop-windows rm -f $leftover 2>&1 | Out-Null }
        Get-Process harbor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 10
    }
    return [int]((Get-Date) - $t0).TotalSeconds
}

for ($attempt = 1; $attempt -le 12; $attempt++) {
    $need = @()
    foreach ($i in 1..3) {
        $r = Get-Round "model-opus-$i"
        if ($null -eq $r -or $null -eq $r.reward -or $r.steps -le 5 -or $r.out -le 100) { $need += $i }
    }
    if ($need.Count -eq 0) {
        Write-Host 'all three opus rounds are valid'
        break
    }

    Write-Host ("=== attempt {0} at {1}: rerunning rounds {2} ===" -f $attempt, (Get-Date -Format 'HH:mm:ss'), ($need -join ','))

    foreach ($i in $need) {
        $job = "model-opus-$i"
        Remove-Item -LiteralPath (Join-Path $stage $job) -Recurse -Force -ErrorAction SilentlyContinue
        $sec = Wait-Round $job 2400
        $r = Get-Round $job
        if ($r) {
            Write-Host ("    {0}: steps={1} out={2} reward={3} ({4}s)" -f $job, $r.steps, $r.out, $r.reward, $sec)
        } else {
            Write-Host ("    {0}: no result ({1}s)" -f $job, $sec)
        }
    }

    Start-Sleep -Seconds 30
}

Write-Host '--- final opus status ---'
foreach ($i in 1..3) {
    $r = Get-Round "model-opus-$i"
    if ($r) {
        $ok = ($r.steps -gt 5) -and ($r.out -gt 100) -and ($null -ne $r.reward)
        Write-Host ("  model-opus-{0}: steps={1} out={2} reward={3} valid={4}" -f $i, $r.steps, $r.out, $r.reward, $ok)
    } else {
        Write-Host ("  model-opus-{0}: MISSING" -f $i)
    }
}
