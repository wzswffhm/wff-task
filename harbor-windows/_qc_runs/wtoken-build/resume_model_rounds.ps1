# Resume the model rounds that are still missing.
#
# State: model-qwen-1 and model-qwen-2 already finished VALID with the frozen
# checksum. model-qwen-3 died because Harbor deadlocked waiting for a container
# that never exited (the container sat at 0.02% CPU with C:\verifier absent, so
# the verifier never even started). The three opus rounds have not run at all.
#
# This script therefore:
#   * skips rounds that already have a reward file,
#   * runs each remaining round in its own harbor process with a wall-clock cap,
#   * force-removes any container left behind when a round times out,
#   * re-checks the round after the cap so a late write still counts.
#
# PYTHONUTF8=1 is mandatory: without it Harbor decodes instruction.md with the
# platform default (GBK) and dies while loading the task.

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
$qwen = $cfg.endpoints | Where-Object { $_.key -eq 'qwen3.8-max' } | Select-Object -First 1
$opus = $cfg.endpoints | Where-Object { $_.key -eq 'opus-5' } | Select-Object -First 1

# alias, endpoint, round index, model name the endpoint expects
$plan = @(
    [pscustomobject]@{ alias = 'qwen'; ep = $qwen; idx = 3; model = 'qwen3.8-max-0902'; keyEnv = 'WFF_QWEN_KEY' },
    [pscustomobject]@{ alias = 'opus'; ep = $opus; idx = 1; model = 'claude-opus-5';     keyEnv = 'WFF_OPUS_KEY' },
    [pscustomobject]@{ alias = 'opus'; ep = $opus; idx = 2; model = 'claude-opus-5';     keyEnv = 'WFF_OPUS_KEY' },
    [pscustomobject]@{ alias = 'opus'; ep = $opus; idx = 3; model = 'claude-opus-5';     keyEnv = 'WFF_OPUS_KEY' }
)

function Get-Reward([string]$job) {
    $dir = Get-ChildItem -LiteralPath (Join-Path $stage $job) -Directory -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -like 'wfflab__*' } | Select-Object -First 1
    if (-not $dir) { return $null }
    $rw = Join-Path $dir.FullName 'verifier\reward.json'
    if (Test-Path -LiteralPath $rw) {
        return (Get-Content -LiteralPath $rw -Raw -Encoding UTF8 | ConvertFrom-Json).reward
    }
    return $null
}

foreach ($step in $plan) {
    $job = "model-" + $step.alias + "-" + $step.idx

    if ($null -ne (Get-Reward $job)) {
        Write-Host ("=== {0}: already has reward {1}, skipping ===" -f $job, (Get-Reward $job))
        continue
    }

    Set-Item -Path ("env:" + $step.keyEnv) -Value $step.ep.api_key
    Write-Host ("=== {0} starting {1} (model={2}) ===" -f $job, (Get-Date -Format 'HH:mm:ss'), $step.model)
    Remove-Item -LiteralPath (Join-Path $stage $job) -Recurse -Force -ErrorAction SilentlyContinue

    $t0 = Get-Date
    $proc = Start-Process -FilePath $harbor -ArgumentList @(
        'run', '--path', $pkg,
        '--agent', 'wtoken_model_agent:WindowsCodingModelAgent',
        '--model', $step.model,
        '--ak', ('alias=' + $step.alias),
        '--ak', ('base_url=' + $step.ep.base_url),
        '--ak', ('auth=' + $step.ep.auth),
        '--ak', ('api_key_env=' + $step.keyEnv),
        '--ak', ('max_tokens=' + $step.ep.max_tokens),
        '--jobs-dir', $stage, '--job-name', $job
    ) -PassThru -NoNewWindow -RedirectStandardOutput (Join-Path $build ($job + '.out')) -RedirectStandardError (Join-Path $build ($job + '.err'))

    # 40 minutes is generous for a round that normally takes 5-15, and stops the
    # deadlock from burning the whole night.
    $capSeconds = 2400
    while (-not $proc.HasExited -and ((Get-Date) - $t0).TotalSeconds -lt $capSeconds) {
        Start-Sleep -Seconds 15
    }

    if (-not $proc.HasExited) {
        Write-Host ("  {0} exceeded {1}s, killing" -f $job, $capSeconds)
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 5
        $leftover = docker --context desktop-windows ps -aq --filter 'name=harbor-' 2>&1
        if ($leftover) { docker --context desktop-windows rm -f $leftover 2>&1 | Out-Null }
        # Kill any harbor wrapper that survived.
        Get-Process harbor -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 10
    }

    $reward = Get-Reward $job
    Write-Host ("  {0} finished in {1}s reward={2}" -f $job, [int]((Get-Date) - $t0).TotalSeconds, $(if ($null -ne $reward) { $reward } else { 'NONE' }))
}

Write-Host '--- model round status ---'
foreach ($alias in @('qwen', 'opus')) {
    foreach ($i in 1..3) {
        $job = "model-$alias-$i"
        $r = Get-Reward $job
        Write-Host ("  {0,-16} reward={1}" -f $job, $(if ($null -ne $r) { $r } else { 'MISSING' }))
    }
}
Write-Host ("disk free: {0:N1} GB" -f ((Get-PSDrive C).Free / 1GB))
