#Requires -Version 5.1
<#
.SYNOPSIS
    Shared plumbing for the Harbor test entry points of task
    windows-d4-litemonitor-001. Dot-sourced by run_tests.ps1 and by the three
    suite scripts; it is not an entry point itself.

.NOTES
    Every helper here is written for BOTH Windows PowerShell 5.1 and PowerShell 7:
    no null-coalescing (??), no null-conditional (?.), no ternary operator, no
    ForEach-Object -Parallel, no three-argument Join-Path, no pwsh-only cmdlets.
    All text files are written as UTF-8 without BOM so JSON/TOML parsers and the
    .NET toolchain read them correctly; the .ps1 files themselves are UTF-8 with
    BOM so Windows PowerShell 5.1 decodes the Chinese text correctly.
#>

$script:TaskId = 'windows-d4-litemonitor-001'
$script:TaskVersion = '2.1.2'
$script:EvaluatorVersion = '2.1.2'
$script:RegistryRootSubKey = 'Software\LiteMonitor'
$script:StoreDirectoryName = 'LiteMonitor'
$script:Inv = [System.Globalization.CultureInfo]::InvariantCulture

# 本进程的标准输出/错误输出统一按 UTF-8 编码。zh-CN 主机的控制台代码页是 936 (GBK)，
# PowerShell 5.1 在输出被重定向时会用它编码 stdout，于是路径里的中文字符（例如评测器工作目录
# 「评测器」、被测树「被测工程」）在上层按 UTF-8 读取时会变成乱码。上层脚本一律以 UTF-8 读取
# 子进程输出，所以这里把编码固定成 UTF-8，保证 test.log 与各类 artifacts 日志可读。
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# bind mount 与容器里的 .git 属主 SID 在容器内不可转换，git 2.35.2+ 会以
# "detected dubious ownership" 直接拒绝操作仓库。这里用 GIT_CONFIG_* 环境变量注入
# safe.directory 例外：它只对本进程派生的 git 子进程生效，不写任何 git 配置文件，
# 所以容器内和宿主机上都不会留下机器状态残留，cleanup.ps1 的 residue_count 不受影响。
# 索引接着调用方已有的 GIT_CONFIG_COUNT 往后排，不覆盖别人已经注入的配置项。
try {
    $script:GitConfigIndex = 0
    if ($env:GIT_CONFIG_COUNT) { [void][int]::TryParse($env:GIT_CONFIG_COUNT, [ref]$script:GitConfigIndex) }
    Set-Item -LiteralPath ('env:GIT_CONFIG_KEY_' + $script:GitConfigIndex) -Value 'safe.directory'
    Set-Item -LiteralPath ('env:GIT_CONFIG_VALUE_' + $script:GitConfigIndex) -Value '*'
    $env:GIT_CONFIG_COUNT = [string]($script:GitConfigIndex + 1)
}
catch { }

# Names of processes this task is allowed to terminate. Deliberately narrow: the
# build host may be running other dotnet/MSBuild work concurrently.
$script:KillableProcessNames = @('LiteMonitor', 'LiteMonitor.Evaluator')

# reparse point 探测（Get-ReparseState / Find-ReparsePointUnder）失败时如实累积在这里。
# Remove-TreeSafe 用它决定要不要拒绝递归快路径；run_tests.ps1 负责把它写进 artifacts/teardown.log。
$script:ReparseInspectionFaults = @()

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text
    )
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding $false))
}

function Read-Utf8 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}

function New-DirectorySafe {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
    return $Path
}

function Add-ReparseInspectionFault {
    param([Parameter(Mandatory = $true)][string]$Message)
    $script:ReparseInspectionFaults += $Message
}

function Get-ReparseInspectionFaults {
    param([switch]$Clear)
    $faults = @($script:ReparseInspectionFaults)
    if ($Clear) { $script:ReparseInspectionFaults = @() }
    return $faults
}

function Get-ReparseState {
    param([Parameter(Mandatory = $true)][string]$Path)
    # 三态而不是布尔：'reparse' / 'plain' / 'unknown'。探测本身失败（句柄被占用、ACL 拒绝、
    # 路径在探测途中消失）时必须如实返回 'unknown'，绝不能折叠成 'plain'——那等于宣称
    # “我确认这里没有链接”，于是调用方会放心地走上递归删除快路径，把没看清的树跟着链接一起删掉。
    try {
        $item = New-Object System.IO.DirectoryInfo($Path)
        if ($item.Exists) {
            if ((($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) -ne 0) { return 'reparse' }
            return 'plain'
        }
        $file = New-Object System.IO.FileInfo($Path)
        if ($file.Exists) {
            if ((($file.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) -ne 0) { return 'reparse' }
            return 'plain'
        }
        return 'plain'
    }
    catch {
        Add-ReparseInspectionFault ("cannot inspect $Path for reparse points : " + $_.Exception.Message)
        return 'unknown'
    }
}

function Test-ReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)
    return ((Get-ReparseState -Path $Path) -eq 'reparse')
}

function Find-ReparsePointUnder {
    param([Parameter(Mandatory = $true)][string]$Root)
    # 只枚举目录、只看属性，不读文件内容，所以这一趟探测比逐个删文件便宜得多。
    $found = New-Object System.Collections.ArrayList
    $pending = New-Object System.Collections.Stack
    $pending.Push($Root)
    while ($pending.Count -gt 0) {
        $current = [string]$pending.Pop()
        try {
            foreach ($sub in ([System.IO.DirectoryInfo]$current).GetDirectories()) {
                if ((($sub.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) -ne 0) { [void]$found.Add($sub.FullName) }
                else { $pending.Push($sub.FullName) }
            }
        }
        catch {
            # 枚举失败不再被空 catch 吞掉：漏看一个子树就等于漏看里面可能存在的联接，
            # 所以如实记为探测故障，Remove-TreeSafe 会据此拒绝递归快路径（失败关闭）。
            Add-ReparseInspectionFault ("cannot enumerate $current while probing for reparse points : " + $_.Exception.Message)
        }
    }
    return $found.ToArray()
}

function Remove-TreeNoFollow {
    param([Parameter(Mandatory = $true)][string]$Path)
    foreach ($sub in @([System.IO.Directory]::GetDirectories($Path))) {
        # 只有明确探明 'plain' 才递归进去；'reparse' 与 'unknown' 一律只删这一层、绝不进入目标。
        # 'unknown' 而其实是非空普通目录时这一层 Delete 会抛异常，由调用方如实上报为删除失败：
        # 这就是失败关闭的代价——宁可留下看得见、算得进 residue 的残留，也不跟着链接删到允许清单之外。
        if ((Get-ReparseState -Path $sub) -eq 'plain') { Remove-TreeNoFollow -Path $sub }
        else { [System.IO.Directory]::Delete($sub, $false) }
    }
    foreach ($file in @([System.IO.Directory]::GetFiles($Path))) { [System.IO.File]::Delete($file) }
    [System.IO.Directory]::Delete($Path, $false)
}

function Remove-TreeSafe {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not $Path) { return }
    if (-not (Test-Path -LiteralPath $Path)) { return }
    # 递归删除绝不能跟随目录联接/符号链接（reparse point）：在 .NET Framework 上
    # Directory.Delete($p, $true) 会穿进链接目标把里面的内容一起删掉，而目标完全可能
    # 位于 %TEMP% 允许清单之外。所以先探测整棵树里有没有 reparse point：只有确认干净
    # 才走原来的快路径；探到链接、或者探测本身不完整（unknown / 枚举失败），就自底向上
    # 逐个删，遇到链接只删链接本身、绝不进入目标。快路径的准入条件是“我确认过”，不是“我没看见”。
    $rootState = Get-ReparseState -Path $Path
    if ($rootState -eq 'reparse') {
        if ([System.IO.Directory]::Exists($Path)) { [System.IO.Directory]::Delete($Path, $false) }
        else { [System.IO.File]::Delete($Path) }
        return
    }
    if (-not [System.IO.Directory]::Exists($Path)) {
        # 普通文件（或指向文件的符号链接）：直接删。文件没有子树可跟随，File.Delete 对符号链接
        # 删的也是链接本身而不是目标，所以 'unknown' 状态下这样做同样是安全的；顺带修掉一个
        # 既有缺陷——改前把文件路径传进来会先被 Find-ReparsePointUnder 当成目录枚举失败记一笔
        # 探测故障，再由 Directory.Delete 抛异常（见 KI-32）。
        [System.IO.File]::Delete($Path)
        return
    }
    $faultsBefore = @(Get-ReparseInspectionFaults).Count
    $nestedReparse = @(Find-ReparsePointUnder -Root $Path)
    $inspectionIncomplete = ($rootState -eq 'unknown') -or (@(Get-ReparseInspectionFaults).Count -gt $faultsBefore)
    if ($nestedReparse.Count -gt 0 -or $inspectionIncomplete) { Remove-TreeNoFollow -Path $Path; return }
    [System.IO.Directory]::Delete($Path, $true)
}

function Get-FileHashSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return '' }
    return 'sha256:' + (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-NonAsciiPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    foreach ($ch in $Path.ToCharArray()) {
        if ([int]$ch -gt 127) { return $true }
    }
    return $false
}

function Format-NativeArgument {
    <#
        MSVCRT argv quoting. A backslash immediately before the closing quote would
        escape it, so trailing backslashes are doubled. MSBuild properties such as
        -p:BaseOutputPath=<dir>\ rely on this.
    #>
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value)
    if ($Value -eq '') { return '""' }
    if ($Value -notmatch '[\s"]') { return $Value }
    $trailing = 0
    while ($trailing -lt $Value.Length -and $Value[$Value.Length - 1 - $trailing] -eq '\') { $trailing++ }
    $escaped = $Value + ('\' * $trailing)
    $escaped = $escaped.Replace('"', '\"')
    return '"' + $escaped + '"'
}

function Invoke-Native {
    <#
        Runs a native command, captures stdout/stderr as UTF-8, enforces a timeout
        and returns the real exit code. Never throws for a non-zero exit code: the
        caller decides whether that is a test failure or an infrastructure fault.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $false)][string[]]$Arguments = @(),
        [Parameter(Mandatory = $false)][string]$WorkingDirectory = '',
        [Parameter(Mandatory = $false)][int]$TimeoutSeconds = 900
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    if ($WorkingDirectory) { $psi.WorkingDirectory = $WorkingDirectory }

    $rendered = @()
    foreach ($argument in $Arguments) { $rendered += (Format-NativeArgument $argument) }
    $psi.Arguments = ($rendered -join ' ')

    $info = [ordered]@{
        FilePath         = $FilePath
        Arguments        = $Arguments
        RenderedArguments = $psi.Arguments
        WorkingDirectory = $psi.WorkingDirectory
        ExitCode         = -1
        StdOut           = ''
        StdErr           = ''
        TimedOut         = $false
        LaunchError      = ''
        Seconds          = 0.0
    }

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $process = $null
    try {
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $psi
        [void]$process.Start()
        $outTask = $process.StandardOutput.ReadToEndAsync()
        $errTask = $process.StandardError.ReadToEndAsync()

        $exited = $process.WaitForExit([int]($TimeoutSeconds * 1000))
        if (-not $exited) {
            $info.TimedOut = $true
            try { $process.Kill() } catch { }
            try { [void]$process.WaitForExit(15000) } catch { }
        }
        try { if ($outTask.Wait(15000)) { $info.StdOut = $outTask.Result } } catch { }
        try { if ($errTask.Wait(15000)) { $info.StdErr = $errTask.Result } } catch { }
        try { $info.ExitCode = $process.ExitCode } catch { $info.ExitCode = -1 }
    }
    catch {
        $info.LaunchError = $_.Exception.GetType().Name + ': ' + $_.Exception.Message
        $info.ExitCode = -1
    }
    finally {
        if ($null -ne $process) { try { $process.Dispose() } catch { } }
    }
    $sw.Stop()
    $info.Seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 3)
    return $info
}

function Write-NativeResult {
    param(
        [Parameter(Mandatory = $true)]$Result,
        [Parameter(Mandatory = $false)][string]$StdOutPath = '',
        [Parameter(Mandatory = $false)][string]$StdErrPath = '',
        [Parameter(Mandatory = $false)][string]$Label = ''
    )
    if ($StdOutPath) { Write-Utf8NoBom -Path $StdOutPath -Text ([string]$Result.StdOut) }
    if ($StdErrPath) { Write-Utf8NoBom -Path $StdErrPath -Text ([string]$Result.StdErr) }
    $name = $Label
    if (-not $name) { $name = [System.IO.Path]::GetFileName([string]$Result.FilePath) }
    Write-Host ("{0}: exit={1} timedOut={2} seconds={3}" -f $name, $Result.ExitCode, $Result.TimedOut, $Result.Seconds)
    if ($Result.LaunchError) { Write-Host ("{0}: launchError={1}" -f $name, $Result.LaunchError) }
}

function Get-DotNetCli {
    $candidate = (Get-Command 'dotnet' -ErrorAction SilentlyContinue)
    if ($null -ne $candidate -and $candidate.Source) { return $candidate.Source }
    foreach ($probe in @("$env:ProgramFiles\dotnet\dotnet.exe", "${env:ProgramFiles(x86)}\dotnet\dotnet.exe")) {
        if ($probe -and (Test-Path -LiteralPath $probe)) { return $probe }
    }
    return ''
}

function Resolve-LocalAppDataRoot {
    # 容器里没有交互式用户配置文件时 GetFolderPath(LocalApplicationData) 可能返回空串，
    # 而 Join-Path 的 -Path 是 Mandatory，喂空串会以 "Cannot bind argument to parameter
    # 'Path' because it is an empty string" 直接终止脚本 —— 一个「这台机器上没有
    # %LOCALAPPDATA%」的环境事实，不应该变成脚本崩溃。所以逐级退让，最后落到 temp 下
    # 一个专属目录，保证返回值永远是非空的绝对路径。
    $local = ''
    try { $local = [string][Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData) } catch { $local = '' }
    if (-not $local) { $local = [string]$env:LOCALAPPDATA }
    if (-not $local) {
        $profile = [string]$env:USERPROFILE
        if ($profile) { $local = (Join-Path $profile 'AppData\Local') }
    }
    if (-not $local) { $local = (Join-Path ([System.IO.Path]::GetTempPath()) 'harbor-localappdata') }
    return $local.TrimEnd('\')
}

function Get-LocalAppDataStoreDirectory {
    return (Join-Path (Resolve-LocalAppDataRoot) $script:StoreDirectoryName)
}

function Stop-TaskProcesses {
    $stopped = @()
    foreach ($name in $script:KillableProcessNames) {
        $procs = @(Get-Process -Name $name -ErrorAction SilentlyContinue)
        foreach ($proc in $procs) {
            try {
                $proc.Kill()
                $stopped += ("{0}:{1}" -f $name, $proc.Id)
            }
            catch { }
        }
    }
    if ($stopped.Count -gt 0) { Start-Sleep -Milliseconds 400 }
    return $stopped
}

function Remove-TaskRegistryState {
    $removed = $false
    try {
        $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Registry64)
        try {
            $existing = $hive.OpenSubKey($script:RegistryRootSubKey, $false)
            if ($null -ne $existing) {
                $existing.Close()
                $hive.DeleteSubKeyTree($script:RegistryRootSubKey, $false)
                $removed = $true
            }
        }
        finally { $hive.Close() }
    }
    catch { }
    return $removed
}

function Remove-TaskDirectoryState {
    $removed = $false
    try {
        $dir = Get-LocalAppDataStoreDirectory
        if ([System.IO.Directory]::Exists($dir)) {
            [System.IO.Directory]::Delete($dir, $true)
            $removed = $true
        }
    }
    catch { }
    return $removed
}

function Remove-InstallDirectoryArtifacts {
    param([Parameter(Mandatory = $false)][string]$Directory)
    $removed = @()
    if (-not $Directory) { return $removed }
    if (-not (Test-Path -LiteralPath $Directory)) { return $removed }
    $names = @('settings.json', 'settings.json.bak', 'settings.json.tmp',
               'TrafficHistory.json', 'TrafficHistory.json.bak', 'TrafficHistory.json.tmp')
    foreach ($name in $names) {
        $path = Join-Path $Directory $name
        if (Test-Path -LiteralPath $path) {
            try { [System.IO.File]::Delete($path); $removed += $name } catch { }
        }
    }
    return $removed
}

function Clear-LiteMonitorMachineState {
    <#
        Removes every piece of machine state this task can create. Safe to call when
        nothing exists, so it is idempotent and can be used between runs and between
        suites.
    #>
    param([Parameter(Mandatory = $false)][string]$InstallDirectory = '')
    $stopped = Stop-TaskProcesses
    $registryRemoved = Remove-TaskRegistryState
    $directoryRemoved = Remove-TaskDirectoryState
    $artifacts = Remove-InstallDirectoryArtifacts -Directory $InstallDirectory
    return [ordered]@{
        processes_stopped   = @($stopped)
        registry_removed    = $registryRemoved
        store_dir_removed   = $directoryRemoved
        install_artifacts   = @($artifacts)
    }
}

function Get-LiteMonitorResidue {
    param([Parameter(Mandatory = $false)][string]$InstallDirectory = '')
    $detail = @()
    $count = 0

    $procs = @()
    foreach ($name in $script:KillableProcessNames) {
        $procs += @(Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object { "{0}:{1}" -f $name, $_.Id })
    }
    if ($procs.Count -gt 0) { $count++; $detail += ('leftover process(es): ' + ($procs -join ', ')) }

    $registryPresent = $false
    try {
        $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Registry64)
        try {
            $key = $hive.OpenSubKey($script:RegistryRootSubKey, $false)
            if ($null -ne $key) { $registryPresent = $true; $key.Close() }
        }
        finally { $hive.Close() }
    }
    catch { }
    if ($registryPresent) { $count++; $detail += "registry HKCU\$($script:RegistryRootSubKey) still present" }

    $dir = Get-LocalAppDataStoreDirectory
    if ([System.IO.Directory]::Exists($dir)) {
        $files = @([System.IO.Directory]::GetFiles($dir, '*', [System.IO.SearchOption]::AllDirectories))
        if ($files.Count -gt 0) { $count++; $detail += ("{0} file(s) left in {1}" -f $files.Count, $dir) }
    }

    if ($InstallDirectory -and (Test-Path -LiteralPath $InstallDirectory)) {
        $names = @('settings.json', 'settings.json.bak', 'settings.json.tmp',
                   'TrafficHistory.json', 'TrafficHistory.json.bak', 'TrafficHistory.json.tmp')
        foreach ($name in $names) {
            $path = Join-Path $InstallDirectory $name
            if (Test-Path -LiteralPath $path) { $count++; $detail += "leftover file $path" }
        }
    }

    return [ordered]@{ residue_count = $count; residue_detail = $detail }
}

function Write-Banner {
    param([Parameter(Mandatory = $true)][string]$Title)
    Write-Host ''
    Write-Host "=== $TaskId v$TaskVersion :: $Title ==="
    Write-Host ("startedAtUtc={0}" -f [DateTime]::UtcNow.ToString('o'))
    Write-Host ("host={0} | os={1} | psVersion={2}" -f $env:COMPUTERNAME, [Environment]::OSVersion.Version.ToString(), $PSVersionTable.PSVersion.ToString())
}

function Count-BuildErrors {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text)
    if (-not $Text) { return 0 }
    $matches = [regex]::Matches($Text, '(?m)^\s*[^\r\n]*?\berror\s+(CS|MSB|NU|NETSDK|MSB\d)[0-9A-Za-z_]*')
    $unique = @{}
    foreach ($m in $matches) { $unique[$m.Value.Trim()] = $true }
    $counted = [regex]::Matches($Text, '(?m)\berror\s+(CS|MSB|NU|NETSDK)[0-9]+')
    if ($counted.Count -gt 0) { return $counted.Count }
    return $unique.Count
}
