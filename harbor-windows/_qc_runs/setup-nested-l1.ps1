# 在物理机 Hyper-V 上创建 L1 Windows Server 2022 虚拟机，并启用嵌套虚拟化。
#
# 链路：物理机(L0, Hyper-V) -> L1 Windows Server 2022 VM -> L1 内的 Docker/Hyper-V 容器(L2)
# 门禁要求 L1 必须真实是外层 VM，且向 L1 暴露虚拟化扩展（ExposeVirtualizationExtensions）。
#
# 用法：
#   pwsh -File setup-nested-l1.ps1                 # 创建并启动
#   pwsh -File setup-nested-l1.ps1 -Status         # 只查看现状
#   pwsh -File setup-nested-l1.ps1 -Start          # 只启动已有 VM

[CmdletBinding()]
param(
    [string]$VMName    = 'L1-WinSrv2022',
    [string]$VHDPath   = 'E:\Hyper-V\VHD\server2022eval.vhd',
    [int]$MemoryGB     = 12,
    [int]$CPUCount     = 6,
    [string]$SwitchName = '',
    [switch]$Status,
    [switch]$Start
)

$ErrorActionPreference = 'Stop'
Import-Module Hyper-V -ErrorAction Stop

function Show-Status {
    Write-Host '=== L1 虚拟机状态 ==='
    $vm = Get-VM -Name $VMName -ErrorAction SilentlyContinue
    if (-not $vm) { Write-Host "  ($VMName 不存在)"; return }
    $vm | Select-Object Name, State, Generation, ProcessorCount, MemoryStartup, Path | Format-List
    $p = Get-VMProcessor -VMName $VMName
    "  ExposeVirtualizationExtensions = $($p.ExposeVirtualizationExtensions)"
    $m = Get-VMMemory -VMName $VMName
    "  DynamicMemoryEnabled = $($m.DynamicMemoryEnabled)"
    Get-VMNetworkAdapter -VMName $VMName | Select-Object Name, SwitchName, MacAddressSpoofing, Status | Format-Table -AutoSize
    $d = Get-VMHardDiskDrive -VMName $VMName
    $d | Select-Object ControllerType, ControllerNumber, ControllerLocation, Path | Format-Table -AutoSize
}

if ($Status) { Show-Status; exit 0 }

if ($Start) {
    $vm = Get-VM -Name $VMName -ErrorAction SilentlyContinue
    if (-not $vm) { throw "VM $VMName 不存在" }
    if ($vm.State -ne 'Running') { Start-VM -Name $VMName }
    Write-Host "已启动 $VMName"
    Show-Status
    exit 0
}

# ---- 前置检查 ---------------------------------------------------------------
if (-not (Test-Path -LiteralPath $VHDPath)) {
    throw "VHD 不存在：$VHDPath（先下载 Server 2022 Eval VHD）"
}
$vhd = Get-Item -LiteralPath $VHDPath
Write-Host ("VHD: {0}  {1:N2} GB" -f $vhd.FullName, ($vhd.Length / 1GB))
$expected = 10208214528
if ($vhd.Length -ne $expected) {
    throw ("VHD 大小不符：{0} != {1}，下载可能未完成" -f $vhd.Length, $expected)
}

if (Get-VM -Name $VMName -ErrorAction SilentlyContinue) {
    Write-Host "VM $VMName 已存在，跳过创建"
    Show-Status
    exit 0
}

# ---- 选择虚拟交换机 ---------------------------------------------------------
$switch = $null
if ($SwitchName) {
    $switch = Get-VMSwitch -Name $SwitchName -ErrorAction SilentlyContinue
    if (-not $switch) { throw "交换机不存在：$SwitchName" }
} else {
    # 优先外部交换机（L1 需要访问网络拉取镜像）；没有则退回 Default Switch
    $switch = Get-VMSwitch | Where-Object { $_.SwitchType -eq 'External' } | Select-Object -First 1
    if (-not $switch) {
        Write-Host '未发现外部交换机，尝试用物理网卡创建...'
        $adapter = Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' } | Select-Object -First 1
        if ($adapter) {
            $switch = New-VMSwitch -Name 'Nested-External' -NetAdapterName $adapter.Name -AllowManagementOS $true
            Write-Host "  已创建外部交换机 Nested-External（绑定 $($adapter.Name)）"
        } else {
            $switch = Get-VMSwitch | Where-Object { $_.SwitchType -eq 'Internal' } | Select-Object -First 1
            if (-not $switch) { $switch = Get-VMSwitch | Select-Object -First 1 }
            Write-Host "  退回使用交换机 $($switch.Name)（$($switch.SwitchType)）"
        }
    }
}
Write-Host "使用交换机：$($switch.Name)（$($switch.SwitchType)）"

# ---- 创建 VM（VHD 是 Gen1 格式）---------------------------------------------
Write-Host '=== 创建虚拟机 ==='
$vm = New-VM -Name $VMName -Generation 1 -MemoryStartupBytes ($MemoryGB * 1GB) `
             -VHDPath $VHDPath -SwitchName $switch.Name
Set-VM -Name $VMName -ProcessorCount $CPUCount -StaticMemory -AutomaticStopAction TurnOff
# 嵌套虚拟化：必须静态内存 + VM 关闭状态下设置
Set-VMProcessor -VMName $VMName -ExposeVirtualizationExtensions $true
# 嵌套场景需要 MAC 地址欺骗，否则 L2 拿不到网络
Set-VMNetworkAdapter -VMName $VMName -MacAddressSpoofing On
Set-VMMemory -VMName $VMName -DynamicMemoryEnabled $false
# 启动顺序：硬盘优先（VHD 已含系统）
Set-VMBios -VMName $VMName -StartupOrder @('IDE', 'CD', 'LegacyNetworkAdapter', 'Floppy')

Write-Host '=== 启动 ==='
Start-VM -Name $VMName
Show-Status
Write-Host ''
Write-Host 'VM 已启动。首次启动 Windows Eval 需要设置 Administrator 密码（交互一次），'
Write-Host '之后可用 PowerShell Direct 自动化：Enter-PSSession -VMName ' + $VMName + ' -Credential (Get-Credential)'
