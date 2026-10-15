# Rerun the Opus rounds until three rounds genuinely engage.
#
# The 4router.net endpoint is intermittently reachable: identical requests time
# out most of the time and occasionally answer in a few seconds. An interrupted
# round leaves a single-step trajectory whose assistant text says the upstream
# returned nothing, so a round only counts when the agent actually worked
# (many steps and a real token count).

$ErrorActionPreference = 'Continue'

$py = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$build = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\wtoken-build'
$stage = Join-Path $build 'model-rounds\jobs'

$env:HARBOR_EXE = 'C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\harbor.exe'
$env:PATH = 'C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts;C:\Program Files\Docker\Docker\resources\bin;' + $env:PATH
$env:no_proxy = '*'
$env:NO_PROXY = '*'

function Get-RoundStats([string]$jobName) {
    $dir = Get-ChildItem -LiteralPath (Join-Path $stage $jobName) -Directory -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -like 'wfflab__*' } | Select-Object -First 1
    if (-not $dir) { return $null }
    $mr = Join-Path $dir.FullName 'agent\model-result.json'
    if (-not (Test-Path -LiteralPath $mr)) { return $null }
    try { return Get-Content -LiteralPath $mr -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return $null }
}

$maxAttempts = 8
for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    Write-Host ("=== attempt {0} : running opus x3 ===" -f $attempt)

    & $py (Join-Path $build 'run_wtoken_model_rounds.py') --only opus 2>&1 |
        Select-Object -Last 8 | ForEach-Object { Write-Host ('  ' + $_) }

    $engaged = 0
    foreach ($i in 1..3) {
        $name = "model-opus-$i"
        $stats = Get-RoundStats $name
        if ($stats) {
            $ok = ($stats.steps -gt 5) -and ($stats.output_tokens -gt 100)
            Write-Host ("  {0}: steps={1} out={2} sec={3} engaged={4}" -f $name, $stats.steps, $stats.output_tokens, [math]::Round($stats.elapsed_sec), $ok)
            if ($ok) { $engaged++ }
        } else {
            Write-Host ("  {0}: no model-result yet" -f $name)
        }
    }

    if ($engaged -ge 3) {
        Write-Host ("all three opus rounds engaged on attempt {0}" -f $attempt)
        break
    }
    Write-Host ("only {0}/3 rounds engaged; waiting before retry" -f $engaged)
    Start-Sleep -Seconds 30
}

Write-Host '--- final opus round stats ---'
foreach ($i in 1..3) {
    $stats = Get-RoundStats "model-opus-$i"
    if ($stats) {
        Write-Host ("  model-opus-{0}: steps={1} out={2} sec={3}" -f $i, $stats.steps, $stats.output_tokens, [math]::Round($stats.elapsed_sec))
    }
}
Write-Host ("disk free: {0:N1} GB" -f ((Get-PSDrive C).Free / 1GB))
