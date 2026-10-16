# 在 L1（Windows Server 2022 VM）内配置 Windows 容器运行时。
#
# 这一步之后，L1 内运行的容器就是门禁要求的 L2：
#   物理机(L0, Hyper-V) -> L1 Windows Server 2022 VM -> L1 内容器(L2)
#
# 用法（在 L1 内以管理员身份运行）：
#   pwsh -File configure-l1.ps1
#   pwsh -File configure-l1.ps1 -PullImage mcr.microsoft.com/windows/server:ltsc2022

[CmdletBinding()]
param(
    [string]$DockerVersion = '27.3.1',
    [string]$PullImage = '',
    [string]$EvidenceDir = 'C:\nested-evidence'
)

$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
$log = Join-Path $EvidenceDir 'configure-l1.log'
function Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -LiteralPath $log -Value $line
}

Log '=== L1 环境身份 ==='
$os = Get-CimInstance Win32_OperatingSystem
Log ("  OS: {0} build {1}" -f $os.Caption, $os.BuildNumber)
Log ("  CS: {0} {1}" -f (Get-CimInstance Win32_ComputerSystem).Manufacturer, (Get-CimInstance Win32_ComputerSystem).Model)
Log ("  HypervisorPresent: {0}" -f (Get-CimInstance Win32_ComputerSystem).HypervisorPresent)
Log ("  CPU: {0}" -f (Get-CimInstance Win32_Processor).Name)
# L1 里应能看到虚拟化扩展已暴露
try {
    $p = Get-CimInstance Win32_Processor
    Log ("  VirtualizationFirmwareEnabled: {0}" -f $p.VirtualizationFirmwareEnabled)
    Log ("  SecondLevelAddressTranslation: {0}" -f $p.SecondLevelAddressTranslationExtensions)
} catch {}

Log '=== 1) 启用 Containers 功能 ==='
$f = Get-WindowsFeature -Name Containers
Log ("  当前状态: {0}" -f $f.InstallState)
if ($f.InstallState -ne 'Installed') {
    $r = Install-WindowsFeature -Name Containers -IncludeManagementTools
    Log ("  安装结果: Success={0} RestartNeeded={1}" -f $r.Success, $r.RestartNeeded)
} else {
    Log '  已安装，跳过'
}

Log '=== 2) 安装 Docker Engine（静态二进制）==='
$dockerDir = 'C:\Program Files\Docker'
$dockerd = Join-Path $dockerDir 'dockerd.exe'
if (-not (Test-Path $dockerd)) {
    $zip = "$env:TEMP\docker-$DockerVersion.zip"
    $url = "https://download.docker.com/win/static/stable/x86_64/docker-$DockerVersion.zip"
    Log "  下载 $url"
    $ProgressPreference = 'SilentlyContinue'
    try {
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 900
        Log ("  下载完成 {0:N1} MB" -f ((Get-Item $zip).Length / 1MB))
    } catch {
        Log ("  !! 下载失败: {0}" -f $_.Exception.Message)
        Log '  提示：如 L1 无外网，可先把 zip 拷进 L1 再解压'
        exit 1
    }
    Expand-Archive -LiteralPath $zip -DestinationPath $env:TEMP -Force
    New-Item -ItemType Directory -Force -Path $dockerDir | Out-Null
    Copy-Item "$env:TEMP\docker\*" $dockerDir -Recurse -Force
    Log "  已解压到 $dockerDir"
} else {
    Log '  已存在 dockerd.exe，跳过'
}

Log '=== 3) 注册并启动 Docker 服务 ==='
$svc = Get-Service docker -ErrorAction SilentlyContinue
if (-not $svc) {
    & $dockerd --register-service 2>&1 | ForEach-Object { Log "  $_" }
    Start-Sleep -Seconds 3
}
$env:Path = "$dockerDir;$env:Path"
Set-Service docker -StartupType Automatic -ErrorAction SilentlyContinue
$svc = Get-Service docker -ErrorAction SilentlyContinue
if ($svc.Status -ne 'Running') { Start-Service docker; Start-Sleep -Seconds 10 }
Log ("  服务状态: {0}" -f (Get-Service docker).Status)
& docker version --format '{{.Server.Os}} {{.Server.Version}}' 2>&1 | ForEach-Object { Log "  docker server: $_" }

Log '=== 4) 验证容器隔离与 L2 运行 ==='
& docker info --format 'OSType={{.OSType}} Isolation={{.Isolation}}' 2>&1 | ForEach-Object { Log "  $_" }

if ($PullImage) {
    Log "=== 5) 拉取基础镜像 $PullImage ==="
    $t0 = Get-Date
    & docker pull $PullImage 2>&1 | Select-Object -Last 4 | ForEach-Object { Log "  $_" }
    Log ("  拉取耗时 {0:N0}s" -f ((Get-Date) - $t0).TotalSeconds)
    & docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' 2>&1 | ForEach-Object { Log "  $_" }
    Log '=== 6) L2 冒烟：在 L1 内启动一个容器 ==='
    & docker run --rm $PullImage cmd /c "echo L2-CONTAINER-OK && ver" 2>&1 | ForEach-Object { Log "  $_" }
}

Log '完成。证据目录：' + $EvidenceDir
