# rerun_models_216.ps1 —— 118 号返修：重跑 wfflab__wchunk-216 的候选模型轮次
#
# 目的：原始 agent log / test log / checks.json 已随 wff-task1 目录丢失，
#       为补交「绑定当前 Task 身份的八次原始模型轨迹、验证日志和结果证据」，
#       必须在真实 Windows 容器里重跑 8 个候选轮次：
#         QWEN x3、OPUS x3、GLM x1、KIMI x1
#
# 前置：Docker Desktop 必须处于 Windows 容器模式（需已启用系统功能 Containers 并重启）。
#   验证：docker info 第一行应输出 windows x86_64
#
# 用法：
#   .\rerun_models_216.ps1 -Models QWEN -Runs 3
#   .\rerun_models_216.ps1 -Models OPUS -Runs 3
#   .\rerun_models_216.ps1 -Models GLM -Runs 1
#   .\rerun_models_216.ps1 -Models KIMI -Runs 1
#   .\rerun_models_216.ps1 -Mode no-change -Runs 1     # 冒烟：不调用模型，只验证据落盘链路

[CmdletBinding()]
param(
    [string]$Models = 'QWEN',
    [int]$Runs = 3,
    [string]$Mode = 'candidate',
    [string]$Task = 'wfflab__wchunk-216',
    [string]$LogDir = 'C:\Users\Administrator\Desktop\wff-task\_qc_runs\rerun'
)

$ErrorActionPreference = 'Continue'
$runner = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner'
$python = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'

$env:DOCKER_CONTEXT = 'desktop-windows'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $runner

$tag = if ($Mode -eq 'candidate') { $Models.ToLower().Replace(',', '-') } else { $Mode }
$log = Join-Path $LogDir "216-$tag.log"
Write-Host "### $Task  mode=$Mode  $Models x$Runs  start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "### log -> $log"

if ($Mode -eq 'candidate') {
    & $python -X utf8 runner.py --task $Task --mode $Mode --models $Models --runs $Runs 2>&1 |
        Tee-Object -FilePath $log
} else {
    & $python -X utf8 runner.py --task $Task --mode $Mode --runs $Runs 2>&1 |
        Tee-Object -FilePath $log
}

Write-Host "### $Task mode=$Mode $Models exit=$LASTEXITCODE  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
