# l1_rerun_all.ps1 -- run the full 215 + 216 pipeline INSIDE the L1 nested VM.
#
# Layer model (buyer nested-virtualization gate):
#     L0  physical Hyper-V host
#     L1  this Windows Server 2022 VM            <- this script runs here
#     L2  Windows container started per trial    <- Docker (process isolation)
#
# For each package: quarantine any jobs/ that was produced outside L1, purge the
# stale per-build job products, then run 3 Oracle + 3 NOP controls, 6 model
# rounds (Qwen x3, Opus x3), and assemble the 12-job jobs/ tree.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$PY  = 'C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Scripts\python.exe'
$HW  = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows'
$LOG = "$HW\_qc_runs\l1-rerun.log"
$STAMP = Get-Date -Format 'yyyyMMdd-HHmmss'

function L([string]$m) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
    Write-Output $line
    Add-Content -Path $LOG -Value $line -Encoding UTF8
}

New-Item -ItemType Directory -Force -Path "$HW\_qc_runs" | Out-Null
L "=== L1 rerun start  host=$env:COMPUTERNAME  stamp=$STAMP ==="
L ("docker: " + ((docker --version) 2>&1 | Select-Object -First 1))

$PKGS = [ordered]@{
    'wsparse' = "$HW\wfflab__wsparse-215-v1.0.1-delivery"
    'wvas'    = "$HW\wfflab__wvas-216-v1.0.1-delivery"
}

foreach ($b in $PKGS.Keys) {
    $pkg   = $PKGS[$b]
    $build = "$HW\_qc_runs\$b-build"

    L "--- [$b] prepare ---"
    if (-not (Test-Path "$pkg\task.toml")) { L "[$b] !! package missing: $pkg"; continue }

    if (Test-Path "$pkg\jobs") {
        $q = "$build\jobs-outside-L1-$STAMP"
        New-Item -ItemType Directory -Force -Path $build | Out-Null
        Move-Item -LiteralPath "$pkg\jobs" -Destination $q -Force
        L "[$b] quarantined foreign jobs/ -> $q"
    }
    foreach ($stale in @('controls', 'model-rounds')) {
        if (Test-Path "$build\$stale") {
            Remove-Item -LiteralPath "$build\$stale" -Recurse -Force -ErrorAction SilentlyContinue
            L "[$b] purged stale $stale"
        }
    }
}

$flow = {
    param($b, $pkg, $build, $PY, $LOG)

    function L2([string]$m) {
        $line = "[{0}][{1}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $b, $m
        Write-Output $line
        Add-Content -Path $LOG -Value $line -Encoding UTF8
    }

    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:no_proxy = '*'
    $env:NO_PROXY = '*'
    $env:PATH = 'C:\Program Files\Docker;' + $env:PATH

    L2 "controls start (3 oracle + 3 nop)"
    & $PY "$build\run_${b}_controls.py" --rounds 3 2>&1 |
        ForEach-Object { Add-Content -Path "$build\controls-run.out" -Value $_ -Encoding UTF8; $_ }
    L2 ("controls exit=" + $LASTEXITCODE)

    L2 "model rounds start (qwen x3 + opus x3)"
    & $PY "$build\run_${b}_model_rounds.py" 2>&1 |
        ForEach-Object { Add-Content -Path "$build\model-rounds-run.out" -Value $_ -Encoding UTF8; $_ }
    L2 ("model rounds exit=" + $LASTEXITCODE)

    L2 "assemble jobs/"
    & $PY "$build\assemble_${b}_harbor_jobs.py" 2>&1 |
        ForEach-Object { Add-Content -Path "$build\assemble.out" -Value $_ -Encoding UTF8; $_ }
    L2 ("assemble exit=" + $LASTEXITCODE)

    $n = 0
    if (Test-Path "$pkg\jobs") { $n = (Get-ChildItem "$pkg\jobs" -Directory | Measure-Object).Count }
    L2 "DONE  jobs/ dirs = $n"
}

# Run the two packages concurrently: at most one L2 container per stream.
$j1 = Start-Job -ScriptBlock $flow -ArgumentList 'wsparse', $PKGS['wsparse'], "$HW\_qc_runs\wsparse-build", $PY, $LOG
$j2 = Start-Job -ScriptBlock $flow -ArgumentList 'wvas',    $PKGS['wvas'],    "$HW\_qc_runs\wvas-build",    $PY, $LOG
L "launched jobs: $($j1.Id) (wsparse), $($j2.Id) (wvas)"

Wait-Job -Job $j1, $j2 | Out-Null
foreach ($j in @($j1, $j2)) {
    Receive-Job -Job $j -ErrorAction SilentlyContinue | Out-Null
}
L "=== L1 rerun finished: j1=$($j1.State) j2=$($j2.State) ==="
Remove-Job -Job $j1, $j2 -Force -ErrorAction SilentlyContinue
