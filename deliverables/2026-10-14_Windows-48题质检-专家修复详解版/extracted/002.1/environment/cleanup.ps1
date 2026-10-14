#Requires -Version 5.1
<#
.SYNOPSIS
    Removes every piece of machine state introduced by Harbor task
    windows-d4-litemonitor-001, then audits what is left.

.DESCRIPTION
    Cleanup targets, in order:
      1. leftover LiteMonitor / LiteMonitor.Evaluator processes
      2. HKCU\Software\LiteMonitor (64-bit view, whole tree)
      3. %LOCALAPPDATA%\LiteMonitor (whole tree)
      4. settings.json / settings.json.bak / settings.json.tmp and the TrafficLogger
         ledger files inside a supplied install directory
      5. optionally the whole agent workspace (-RemoveWorkspace)

    Recursive deletion is refused unless the resolved absolute target is inside an
    explicit allow-list of roots (the system temp directory, $env:HARBOR_WORKSPACE_ROOT,
    or the <project>\work directory). Nothing is ever deleted from a computed path that
    has not been checked first.

    Non-interactive and idempotent: running it twice in a row is a no-op the second time.

.OUTPUTS
    Prints RESIDUE_COUNT=<n> and, with -ReportPath, writes a JSON receipt.
    Exit code 0 = nothing left behind. 1 = residue remains. 2 = infrastructure fault.

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File environment\cleanup.ps1 -ReportPath .\cleanup_report.json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)][switch]$Quiet,
    [Parameter(Mandatory = $false)][string]$ReportPath,
    [Parameter(Mandatory = $false)][string]$InstallDirectory,
    [Parameter(Mandatory = $false)][string]$WorkspaceRoot,
    [Parameter(Mandatory = $false)][switch]$RemoveWorkspace
)

$ErrorActionPreference = 'Stop'
$script:EnvDir = $PSScriptRoot
. (Join-Path $script:EnvDir 'env_common.ps1')

if (-not $Quiet) { Write-Banner 'cleanup' }

$infraFaults = New-Object System.Collections.ArrayList
$actions = New-Object System.Collections.ArrayList

# ---- allow-list for recursive deletion ------------------------------------ #
$allowedRoots = New-Object System.Collections.ArrayList
[void]$allowedRoots.Add(([System.IO.Path]::GetTempPath().TrimEnd('\')))
if ($env:HARBOR_WORKSPACE_ROOT) { [void]$allowedRoots.Add($env:HARBOR_WORKSPACE_ROOT.TrimEnd('\')) }
# 交付目录在项目里位于 <root>\delivery-*\tasks\<task-id>，往上三级就是项目根，
# 项目根的 work\ 是宿主机跑评测时的临时区，需要进删除允许清单。但在镜像里
# $script:TaskDir 是 C:\harbor\task：往上一级 C:\harbor，两级 C:\，三级就是空串，
# 而 Join-Path 的 -Path 是 Mandatory，空串会以 "Cannot bind argument to parameter 'Path'
# because it is an empty string" 直接终止整个 cleanup —— 一个纯宿主机开发期的便利，
# 不该让镜像里的清理脚本崩溃。所以逐级向上，拿不到非空父目录就停。
$projectWorkRoot = [string]$script:TaskDir
for ($level = 0; $level -lt 3; $level++) {
    $parent = Split-Path -Parent $projectWorkRoot -ErrorAction SilentlyContinue
    if (-not $parent) { $projectWorkRoot = ''; break }
    $projectWorkRoot = [string]$parent
}
if ($projectWorkRoot) {
    $projectWork = (Resolve-Path -LiteralPath (Join-Path $projectWorkRoot 'work') -ErrorAction SilentlyContinue)
    if ($null -ne $projectWork) { [void]$allowedRoots.Add($projectWork.ProviderPath.TrimEnd('\')) }
}

function Test-DeletionAllowed {
    # 这里只做词法层面的前缀判定（GetFullPath + 大小写无关前缀），因为它负责的是“候选
    # 根目录本身是不是在允许清单里”。向下逃逸（候选目录里藏一个指向允许清单之外的
    # 目录联接）不是由这个函数负责的：它由 Remove-TreeSafe 负责——后者会先探测整棵树里的
    # reparse point，发现就自底向上删、遇到链接只删链接本身，绝不跟随进入目标。两者合起来
    # 才是完整的护栏；单看这一个函数会以为保证是纯词法的。
    param([string]$Path)
    if (-not $Path) { return $false }
    $resolved = $null
    try { $resolved = [System.IO.Path]::GetFullPath($Path) } catch { return $false }
    $resolved = $resolved.TrimEnd('\')
    foreach ($root in $allowedRoots) {
        if ($resolved.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
        if ([string]::Equals($resolved, $root, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

# ---- 1. processes ---------------------------------------------------------- #
$stopped = @(Stop-TaskProcesses)
[void]$actions.Add([ordered]@{ step = 'processes'; removed = $stopped })
if (-not $Quiet) { Write-Host ("processesStopped={0}" -f ($stopped -join ', ')) }

# ---- 2. registry ----------------------------------------------------------- #
$registryPresentBefore = $false
try {
    $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Registry64)
    try {
        $key = $hive.OpenSubKey($script:RegistryRootSubKey, $false)
        if ($null -ne $key) { $registryPresentBefore = $true; $key.Close() }
    }
    finally { $hive.Close() }
}
catch { [void]$infraFaults.Add('cannot open HKCU in the 64-bit view: ' + $_.Exception.Message) }

$registryRemoved = Remove-TaskRegistryState
$registryPresentAfter = $false
try {
    $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Registry64)
    try { $key = $hive.OpenSubKey($script:RegistryRootSubKey, $false); if ($null -ne $key) { $registryPresentAfter = $true; $key.Close() } }
    finally { $hive.Close() }
}
catch { [void]$infraFaults.Add('cannot re-open HKCU after cleanup: ' + $_.Exception.Message) }
[void]$actions.Add([ordered]@{
        step = 'registry'; path = "HKCU\$($script:RegistryRootSubKey)"; view = 'Registry64'
        present_before = $registryPresentBefore; removed = $registryRemoved; present_after = $registryPresentAfter
    })
if (-not $Quiet) { Write-Host ("registry HKCU\{0} present_before={1} removed={2} present_after={3}" -f $script:RegistryRootSubKey, $registryPresentBefore, $registryRemoved, $registryPresentAfter) }

# ---- 3. per-user store directory ------------------------------------------- #
$storeDir = Get-LocalAppDataStoreDirectory
$storePresentBefore = [System.IO.Directory]::Exists($storeDir)
$storeRemoved = Remove-TaskDirectoryState -Directory $storeDir
$storePresentAfter = [System.IO.Directory]::Exists($storeDir)
[void]$actions.Add([ordered]@{ step = 'store_directory'; path = $storeDir; present_before = $storePresentBefore; removed = $storeRemoved; present_after = $storePresentAfter })
if (-not $Quiet) { Write-Host ("storeDirectory {0} present_before={1} removed={2} present_after={3}" -f $storeDir, $storePresentBefore, $storeRemoved, $storePresentAfter) }

# ---- 4. install directory artifacts ---------------------------------------- #
$artifactRemoved = @()
if ($InstallDirectory) {
    if (Test-Path -LiteralPath $InstallDirectory) {
        foreach ($name in @($script:SettingsFileName, "$($script:SettingsFileName).bak", "$($script:SettingsFileName).tmp",
                            'TrafficHistory.json', 'TrafficHistory.json.bak', 'TrafficHistory.json.tmp')) {
            $path = Join-Path $InstallDirectory $name
            if (Test-Path -LiteralPath $path) {
                try { [System.IO.File]::Delete($path); $artifactRemoved += $name } catch { [void]$infraFaults.Add("cannot delete $path : " + $_.Exception.Message) }
            }
        }
    }
    elseif (-not $Quiet) { Write-Host "installDirectory not present, nothing to clean: $InstallDirectory" }
}
[void]$actions.Add([ordered]@{ step = 'install_artifacts'; path = $InstallDirectory; removed = $artifactRemoved })
if (-not $Quiet) { Write-Host ("installArtifactsRemoved={0}" -f ($artifactRemoved -join ', ')) }

# ---- 4b. evaluator working directories under the system temp path ----------- #
# tests/run_tests.ps1 在没有显式 -WorkDir 时会自建 %TEMP%\harbor-litemonitor-<RunId>。
# 甲方 4.5 要求结束后不得遗留临时状态，而 cleanup_report.json#probed_state 也声明了这一
# 探测面，所以这里必须真的删、并且删不掉的要如实计入 residue，而不是不看。
$tempPattern = ([System.IO.Path]::GetTempPath().TrimEnd('\') + '\' + $script:EvaluatorTempDirPrefix + '*')
$tempBefore = @(Get-EvaluatorTempDirectories)
foreach ($fault in @(Get-TempEnumerationFaults -Clear)) { [void]$infraFaults.Add($fault) }
$tempRemoved = @()
$tempFailed = @()
$tempReparse = @()
foreach ($path in $tempBefore) {
    if (-not (Test-DeletionAllowed $path)) {
        $tempFailed += $path
        [void]$infraFaults.Add("refusing to recursively delete $path - it is outside the allow-list: " + ($allowedRoots -join ' | '))
        continue
    }
    $candidateState = Get-ReparseState -Path $path
    if ($candidateState -ne 'plain') {
        # 候选根目录自己就是一个联接（'reparse'）、或者连它是不是联接都没探明（'unknown'）：
        # 词法前缀检查看到的是链接路径，真实目标可以在任何地方。两种情况都不删、不递归，
        # 如实记为未删除并上报基础设施故障——探测不出来时失败关闭，而不是当作普通目录删下去。
        $tempFailed += $path
        if ($candidateState -eq 'reparse') {
            $tempReparse += $path
            [void]$infraFaults.Add("refusing to recursively delete $path - it is a reparse point (directory junction or symbolic link), so its real target may live outside the allow-list")
        }
        else {
            $tempReparse += $path
            [void]$infraFaults.Add("refusing to recursively delete $path - its reparse state could not be determined, so it is treated as a possible link and left in place")
        }
        continue
    }
    try { Remove-TreeSafe $path; $tempRemoved += ([System.IO.Path]::GetFileName($path)) }
    catch { $tempFailed += $path; [void]$infraFaults.Add("cannot remove the evaluator working directory $path : " + $_.Exception.Message) }
}
$tempAfter = @(Get-EvaluatorTempDirectories)
foreach ($fault in @(Get-TempEnumerationFaults -Clear)) { [void]$infraFaults.Add($fault) }
foreach ($fault in @(Get-ReparseInspectionFaults -Clear)) { [void]$infraFaults.Add($fault) }
[void]$actions.Add([ordered]@{
        step = 'evaluator_temp_directories'; path = $tempPattern
        present_before = $tempBefore.Count; removed = $tempRemoved; failed = $tempFailed
        reparse_point_skipped = $tempReparse; present_after = $tempAfter.Count
    })
if (-not $Quiet) { Write-Host ("evaluatorTempDirs {0} present_before={1} removed={2} present_after={3}" -f $tempPattern, $tempBefore.Count, $tempRemoved.Count, $tempAfter.Count) }

# ---- 4c. named single-instance mutex --------------------------------------- #
$mutexAlive = Test-ExclusiveLockMutexAlive
[void]$actions.Add([ordered]@{
        step = 'named_mutex'; path = $script:ExclusiveLockMutexName; alive = $mutexAlive
        note = '命名内核互斥体在最后一个句柄关闭之后才不可打开；第 1 步已停止被测进程，这里只如实探测且不等待，仍可打开则由 residue 审计计数'
    })
if (-not $Quiet) { Write-Host ("namedMutex {0} alive={1}" -f $script:ExclusiveLockMutexName, $mutexAlive) }

# ---- 5. optional workspace -------------------------------------------------- #
$workspaceRemoved = $false
if ($RemoveWorkspace) {
    if (-not $WorkspaceRoot) { $WorkspaceRoot = Get-DefaultWorkspaceRoot }
    $resolvedWorkspace = $null
    try { $resolvedWorkspace = [System.IO.Path]::GetFullPath($WorkspaceRoot) } catch { }
    if ($null -eq $resolvedWorkspace) {
        [void]$infraFaults.Add("cannot resolve the workspace path: $WorkspaceRoot")
    }
    elseif (-not (Test-DeletionAllowed $resolvedWorkspace)) {
        [void]$infraFaults.Add("refusing to recursively delete $resolvedWorkspace - it is outside the allow-list: " + ($allowedRoots -join ' | '))
    }
    elseif (Test-Path -LiteralPath $resolvedWorkspace) {
        try { Remove-TreeSafe $resolvedWorkspace; $workspaceRemoved = $true }
        catch { [void]$infraFaults.Add("cannot remove the workspace $resolvedWorkspace : " + $_.Exception.Message) }
    }
    else { $workspaceRemoved = $true }
}
[void]$actions.Add([ordered]@{ step = 'workspace'; path = $WorkspaceRoot; removed = $workspaceRemoved })
if (-not $Quiet) { Write-Host ("workspaceRemoved={0} (requested={1})" -f $workspaceRemoved, [bool]$RemoveWorkspace) }

# ---- audit ------------------------------------------------------------------ #
$residue = Get-TaskResidue -InstallDirectory $InstallDirectory
# Get-TaskResidue 自己也会枚举 %TEMP%（探测残留的评测器工作目录），而 4b/5 节里
# Remove-TreeSafe 的 reparse 探测也可能在审计期间才失败。这两类故障发生在上面两次排干之后，
# 如果不在这儿再排一次，最终审计期间发生的基础设施故障就不会进入 receipt，conclusion 会带着
# 被掩盖的故障写成 ZERO_RESIDUE。排水必须在结论计算之前，所以 INFRA_FAULT 与退出码 2 仍然生效。
$postAuditDrained = 0
foreach ($fault in @(Get-TempEnumerationFaults -Clear)) { [void]$infraFaults.Add($fault); $postAuditDrained++ }
foreach ($fault in @(Get-ReparseInspectionFaults -Clear)) { [void]$infraFaults.Add($fault); $postAuditDrained++ }
if ($postAuditDrained -gt 0 -and -not $Quiet) { Write-Host ("postAuditInfraFaultsDrained={0}" -f $postAuditDrained) }
$residueCount = [int]$residue.residue_count
$residueDetail = @($residue.residue_detail)

$receipt = [ordered]@{
    task_id          = $TaskId
    task_version     = $TaskVersion
    cleaned_at_utc   = [DateTime]::UtcNow.ToString('o')
    host             = $env:COMPUTERNAME
    registry_root    = "HKCU\$($script:RegistryRootSubKey)"
    registry_view    = 'Registry64'
    store_directory  = $storeDir
    install_directory = $InstallDirectory
    workspace_root   = $WorkspaceRoot
    actions          = $actions
    allowed_roots    = @($allowedRoots)
    residue_count    = $residueCount
    residue_detail   = $residueDetail
    infra_faults     = @($infraFaults)
    post_audit_faults_drained = $postAuditDrained
    conclusion       = $(if ($infraFaults.Count -gt 0) { 'INFRA_FAULT' } elseif ($residueCount -eq 0) { 'ZERO_RESIDUE' } else { 'RESIDUE_PRESENT' })
}
$receiptJson = $receipt | ConvertTo-Json -Depth 12
if ($ReportPath) {
    Write-Utf8NoBom -Path $ReportPath -Text $receiptJson
    if (-not $Quiet) { Write-Host "REPORT=$([System.IO.Path]::GetFullPath($ReportPath))" }
}

if (-not $Quiet) {
    Write-Host ''
    Write-Host ($receiptJson)
}
Write-Host "RESIDUE_COUNT=$residueCount"
Write-Host "CONCLUSION=$($receipt.conclusion)"

if ($infraFaults.Count -gt 0) { exit 2 }
if ($residueCount -gt 0) { exit 1 }
exit 0
