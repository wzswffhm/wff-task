# rerun_models.ps1 —— 在整改后的题包上重跑指定模型的候选轮次
#
# 必须设置 DOCKER_CONTEXT=desktop-windows：runner 默认解析到
# dockerDesktopLinuxEngine，而本机 Docker Desktop 处于 Windows 容器模式，
# 不设置会立刻失败（docker server not reachable / 500）。
#
# 用法：
#   .\rerun_models.ps1 -Models QWEN -Runs 3
#   .\rerun_models.ps1 -Models OPUS -Runs 3
#   .\rerun_models.ps1 -Tasks wfflab__wfmt-215 -Models QWEN -Runs 1

[CmdletBinding()]
param(
    [string[]]$Tasks = @('wfflab__wreparse-217', 'wfflab__wfmt-215'),
    [string]$Models = 'QWEN',
    [int]$Runs = 3,
    [string]$LogDir = 'C:\Users\Administrator\Desktop\wff-task\_qc_runs\rerun'
)

$ErrorActionPreference = 'Continue'
$runner = 'C:\Users\Administrator\Desktop\wff-task1\deliverables\2026-10-04_outside-harbor-win\runner'
$python = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'

$env:DOCKER_CONTEXT = 'desktop-windows'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $runner

foreach ($task in $Tasks) {
    $short = ($task -split '__')[-1]
    $log = Join-Path $LogDir "$short-$($Models.ToLower()).log"
    Write-Host "### $task  $Models x$Runs  start $(Get-Date -Format 'HH:mm:ss')"
    & $python -X utf8 runner.py --task $task --mode candidate --models $Models --runs $Runs *> $log
    Write-Host "$task exit=$LASTEXITCODE  $(Get-Date -Format 'HH:mm:ss')"
}
Write-Host "all done $(Get-Date -Format 'HH:mm:ss')"
