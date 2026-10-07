# Post-reboot resume for the Outside Harbor task.
#
# Registered as a scheduled task (trigger: at log on of the current user) so the
# qualification controls and the official model matrix continue unattended after
# the machine reboots to activate the Hyper-V container stack.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File resume-after-reboot.ps1
#
# It is safe to run by hand as well: it resumes from whatever already exists.

[CmdletBinding()]
param(
    [string]$TaskId = 'wfflab__wreparse-217',
    [int]$ControlRuns = 3,
    [switch]$Force
)

$ErrorActionPreference = 'Continue'

$RunnerRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RunnerRoot 'logs'
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir ('resume-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
$DoneMarker = Join-Path $LogDir 'resume.done'
$FailMarker = Join-Path $LogDir 'resume.failed'

foreach ($stale in @($DoneMarker, $FailMarker, (Join-Path $LogDir 'resume.running'))) {
    if (Test-Path -LiteralPath $stale) { Remove-Item -LiteralPath $stale -Force }
}

function Write-Log {
    param([string]$Message)
    $line = '[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $Message
    Write-Host $line
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

function Wait-ForWindowsEngine {
    param([int]$TimeoutMinutes = 25)
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    while ((Get-Date) -lt $deadline) {
        $probe = & docker version --format '{{.Server.Os}}' 2>$null
        if ($LASTEXITCODE -eq 0 -and "$probe".Trim() -eq 'windows') { return $true }
        Start-Sleep -Seconds 15
    }
    return $false
}

Set-Content -LiteralPath (Join-Path $LogDir 'resume.running') -Value (Get-Date -Format o) -Encoding UTF8
Add-Content -LiteralPath $LogFile -Value '=== resume start ===' -Encoding UTF8
$epoch = (Get-Date).ToString('o')

try {
    $python = Join-Path $env:USERPROFILE '.workbuddy\binaries\python\versions\3.13.12\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw "python not found at $python" }
    $runScript = Join-Path $RunnerRoot 'run.ps1'
    $summarize = 'C:\Users\Administrator\Desktop\generate-win\scripts\summarize_model_runs.py'

    if ((Test-Path -LiteralPath $DoneMarker) -and (-not $Force)) {
        Write-Log 'resume.done already present and -Force not given; nothing to do'
        exit 0
    }

    Write-Log 'starting Docker Desktop'
    $desktopExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
    if (Test-Path -LiteralPath $desktopExe) {
        Start-Process -FilePath $desktopExe | Out-Null
    }
    else {
        & docker desktop start 2>&1 | Out-Null
    }

    if (-not (Wait-ForWindowsEngine -TimeoutMinutes 25)) {
        Write-Log 'engine is not reporting windows yet; trying an explicit engine switch'
        & docker desktop engine use windows 2>&1 | Out-Null
        if (-not (Wait-ForWindowsEngine -TimeoutMinutes 15)) {
            throw 'Docker Desktop never came up in Windows container mode'
        }
    }
    Write-Log 'windows container engine is ready'

    $smoke = & docker run --rm mcr.microsoft.com/windows/servercore:ltsc2022 cmd /c ver 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "windows container smoke test failed: $smoke" }
    Write-Log ('smoke test: ' + ($smoke.Trim()))

    Write-Log '=== NOP / no-change control x3 ==='
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runScript -Task $TaskId -Mode no-change -Runs $ControlRuns 2>&1 |
        ForEach-Object { Write-Log $_ }
    Write-Log ("no-change exit=" + $LASTEXITCODE)

    Write-Log '=== Oracle / golden control x3 ==='
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runScript -Task $TaskId -Mode golden -Runs $ControlRuns 2>&1 |
        ForEach-Object { Write-Log $_ }
    Write-Log ("golden exit=" + $LASTEXITCODE)

    Write-Log '=== model matrix: QWEN x3 and OPUS x3 in parallel ==='
    $common = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $runScript, '-Task', $TaskId, '-Mode', 'candidate', '-Runs', '3')
    $qw = Start-Process -FilePath 'powershell' -ArgumentList ($common + @('-Models', 'QWEN')) -PassThru -WindowStyle Hidden
    $op = Start-Process -FilePath 'powershell' -ArgumentList ($common + @('-Models', 'OPUS')) -PassThru -WindowStyle Hidden
    $qw.WaitForExit()
    Write-Log ("QWEN exit=" + $qw.ExitCode)
    $op.WaitForExit()
    Write-Log ("OPUS exit=" + $op.ExitCode)

    Write-Log '=== model matrix: GLM x1 then KIMI x1 (shared Ark key) ==='
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runScript -Task $TaskId -Mode candidate -Models GLM -Runs 1 2>&1 |
        ForEach-Object { Write-Log $_ }
    Write-Log ("GLM exit=" + $LASTEXITCODE)
    & powershell -NoProfile -ExecutionPolicy Bypass -File $runScript -Task $TaskId -Mode candidate -Models KIMI -Runs 1 2>&1 |
        ForEach-Object { Write-Log $_ }
    Write-Log ("KIMI exit=" + $LASTEXITCODE)

    Write-Log '=== qualification summary ==='
    $summaryPath = Join-Path $LogDir 'qualification_summary.json'
    & $python -X utf8 $summarize --workspace-root $RunnerRoot --task-id $TaskId --after $epoch --output $summaryPath 2>&1 |
        ForEach-Object { Write-Log $_ }
    Write-Log ("summary exit=" + $LASTEXITCODE)

    Set-Content -LiteralPath $DoneMarker -Value (Get-Date -Format o) -Encoding UTF8
    Write-Log '=== resume complete ==='
    exit 0
}
catch {
    $message = $_.Exception.Message
    Write-Log ("RESUME FAILED: " + $message)
    Set-Content -LiteralPath $FailMarker -Value $message -Encoding UTF8
    exit 1
}
finally {
    $running = Join-Path $LogDir 'resume.running'
    if (Test-Path -LiteralPath $running) { Remove-Item -LiteralPath $running -Force }
}
