#Requires -Version 5.1
<#
.SYNOPSIS
    Materialises the frozen initial state of Harbor task windows-d4-litemonitor-001.

.DESCRIPTION
    Unpacks the frozen baseline archive into the agent workspace, verifies its integrity
    and lineage, restores the vendor note the upstream project forgot to commit (without
    it LiteMonitor.csproj fails with MSB3030), proves the baseline builds completely
    offline, and clears any machine state left by a previous run.

    Idempotent: re-running on an already prepared, pristine tree reuses it and only
    re-asserts the invariants. Re-running on a dirtied tree (for example after the
    vendor note was deleted) repairs it to a byte-identical state. Use -Force to
    re-extract from scratch.

    The agent workspace only ever receives the task statement, the initial repository
    and the toolchain. tests/, solution/, evidence/ and metadata/ are never copied,
    mounted or referenced from here.

.OUTPUTS
    Exit code 0 = prepared. Exit code 2 = infrastructure fault (INVALID, not a model
    failure).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File environment\prepare.ps1 -WorkspaceRoot C:\ws\run1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)][string]$WorkspaceRoot,
    [Parameter(Mandatory = $false)][string]$RepoRoot,
    [Parameter(Mandatory = $false)][switch]$Force,
    [Parameter(Mandatory = $false)][switch]$SkipPrebuild,
    [Parameter(Mandatory = $false)][switch]$SkipCleanup,
    [Parameter(Mandatory = $false)][int]$TimeoutSeconds = 1800
)

$ErrorActionPreference = 'Stop'
$script:EnvDir = $PSScriptRoot
. (Join-Path $script:EnvDir 'env_common.ps1')

Write-Banner 'prepare'

if (-not $WorkspaceRoot) { $WorkspaceRoot = Get-DefaultWorkspaceRoot }
if (-not $RepoRoot) { $RepoRoot = Get-DefaultRepoRoot -WorkspaceRoot $WorkspaceRoot }
New-DirectorySafe $WorkspaceRoot | Out-Null
$WorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).ProviderPath

Write-Host "workspaceRoot=$WorkspaceRoot"
Write-Host "repoRoot=$RepoRoot"
Write-Host "baselineCommit=$BaselineCommitShort upstream=$UpstreamRepo@$UpstreamCommitShort"

function Fail-Prepare {
    param([string]$Reason)
    Write-Host "PREPARE_FAILED=$Reason"
    Write-Host 'PREPARED=0'
    exit 2
}

# --------------------------------------------------------------------------- #
# 1. frozen asset integrity
# --------------------------------------------------------------------------- #
$zipPath = Join-Path (Join-Path $script:EnvDir 'assets') $BaselineZipName
if (-not (Test-Path -LiteralPath $zipPath)) { Fail-Prepare "the frozen baseline archive is missing at $zipPath" }
$zipHash = Get-Sha256 $zipPath
if ($zipHash -ne $BaselineZipSha256) {
    Fail-Prepare "baseline archive SHA-256 mismatch: got sha256:$zipHash expected sha256:$BaselineZipSha256 (the initial state must be frozen)"
}
Write-Host "baselineArchive=$zipPath sha256:$zipHash bytes=$((Get-Item -LiteralPath $zipPath).Length)"

$tar = Get-TarCli
if (-not $tar) { Fail-Prepare 'no tar implementation is available to unpack the frozen baseline archive' }
$dotnet = Get-DotNetCli
if (-not $dotnet) { Fail-Prepare 'the .NET SDK CLI (dotnet) was not found on PATH' }

$feedDir = Join-Path (Join-Path $script:EnvDir 'assets') 'nuget'
$feedCount = 0
if (Test-Path -LiteralPath $feedDir) { $feedCount = @(Get-ChildItem -LiteralPath $feedDir -Filter '*.nupkg' -File).Count }
if ($feedCount -lt $MinimumFeedPackages) { Fail-Prepare "the vendored offline NuGet feed holds only $feedCount package(s), expected at least $MinimumFeedPackages" }

# --------------------------------------------------------------------------- #
# 2. reuse or (re-)extract
# --------------------------------------------------------------------------- #
function Test-PristineTree {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return 'missing directory' }
    if (-not (Test-Path -LiteralPath (Join-Path $Path 'LiteMonitor.csproj'))) { return 'LiteMonitor.csproj is missing' }
    if (-not (Test-Path -LiteralPath (Join-Path $Path 'src\Core\RegistryNotify.cs'))) { return 'the frozen contract src\Core\RegistryNotify.cs is missing' }
    if (-not (Test-Path -LiteralPath (Join-Path $Path 'src\Core\StatusMirror.cs'))) { return 'the frozen contract src\Core\StatusMirror.cs is missing' }
    if (-not (Test-Path -LiteralPath (Join-Path $Path $VendorTxtName))) { return "the vendor note $VendorTxtName is missing (upstream forgot to commit it; the csproj Content reference then fails with MSB3030)" }
    if (-not (Test-Path -LiteralPath (Join-Path $Path '.git'))) { return 'the .git lineage directory is missing' }
    $head = Invoke-Native -FilePath 'git' -Arguments @('-C', $Path, 'rev-parse', 'HEAD') -TimeoutSeconds 60
    if ($head.ExitCode -ne 0) { return 'git could not resolve HEAD' }
    $headText = ([string]$head.StdOut).Trim()
    if ($headText -ne $BaselineCommit) { return "HEAD is $headText, expected the frozen baseline commit $BaselineCommit" }
    $status = Invoke-Native -FilePath 'git' -Arguments @('-C', $Path, 'status', '--porcelain') -TimeoutSeconds 120
    if ($status.ExitCode -ne 0) { return 'git status failed' }
    $statusText = ([string]$status.StdOut).Trim()
    if ($statusText -ne '') { return "the working tree is dirty: $statusText" }
    return ''
}

# A tree that drifted (most often the vendor note was deleted by an agent run) is repaired
# IN PLACE instead of being recursively deleted: the vendored byte-identical copy of
# 使用说明(必读).txt is put back and every other tracked file is checked out again from the
# frozen baseline commit. Nothing outside $Path is touched, so the repair is safe even when
# the tree lives outside $WorkspaceRoot, and it stays idempotent (a pristine tree is a no-op).
function Repair-PristineTree {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return 'missing directory' }
    if (-not (Test-Path -LiteralPath (Join-Path $Path '.git'))) { return 'the .git lineage directory is missing; there is nothing to repair from' }
    $vendorTarget = Join-Path $Path $VendorTxtName
    if (-not (Test-Path -LiteralPath $vendorTarget)) {
        $vendorAsset = Join-Path (Join-Path (Join-Path $script:EnvDir 'assets') 'vendor') $VendorTxtName
        if (-not (Test-Path -LiteralPath $vendorAsset)) { return "the vendored copy of $VendorTxtName is missing at $vendorAsset" }
        [System.IO.File]::Copy($vendorAsset, $vendorTarget, $true)
        $restoredHash = (Get-FileHash -LiteralPath $vendorTarget -Algorithm SHA256).Hash.ToLowerInvariant()
        Write-Host "restored $VendorTxtName from the vendored asset sha256:$restoredHash"
    }
    $checkout = Invoke-Native -FilePath 'git' -Arguments @('-C', $Path, 'checkout', '--', '.') -TimeoutSeconds 300
    Write-Host ("git checkout -- . exit={0} seconds={1}" -f $checkout.ExitCode, $checkout.Seconds)
    if ($checkout.ExitCode -ne 0) { return ('git checkout -- . failed with exit=' + $checkout.ExitCode + ' stderr=' + ([string]$checkout.StdErr)) }
    return (Test-PristineTree -Path $Path)
}

$reused = $false
if ((Test-Path -LiteralPath $RepoRoot) -and -not $Force) {
    $defect = Test-PristineTree -Path $RepoRoot
    if ($defect -eq '') {
        $reused = $true
        Write-Host "reusing the already prepared pristine tree at $RepoRoot"
    }
    else {
        Write-Host "existing tree is not reusable ($defect); attempting a non-destructive in-place repair first"
        $defect = Repair-PristineTree -Path $RepoRoot
        if ($defect -eq '') {
            $reused = $true
            Write-Host "repaired the tree in place; it is byte-identical to the frozen baseline again"
        }
        else {
            Write-Host "in-place repair left the tree unusable ($defect); re-extracting from the frozen archive"
        }
    }
}

if (-not $reused) {
    if (Test-Path -LiteralPath $RepoRoot) {
        $resolved = [System.IO.Path]::GetFullPath($RepoRoot)
        $insideWorkspace = $resolved.StartsWith($WorkspaceRoot.TrimEnd('\') + '\', [System.StringComparison]::OrdinalIgnoreCase)
        if (-not $insideWorkspace) { Fail-Prepare "refusing to recursively delete $resolved because it is not inside the workspace $WorkspaceRoot" }
        Write-Host "removing the previous tree at $resolved"
        try { Remove-TreeSafe $resolved } catch { Fail-Prepare ("cannot remove the previous tree: " + $_.Exception.Message) }
    }
    New-DirectorySafe $RepoRoot | Out-Null
    # tar.exe(bsdtar) 收到的是 MSVCRT 按 ANSI 转换过的 argv，非 ASCII 的 -C 目标会退化成
    # 问号并报 "could not chdir"；把目标目录改由 CreateProcess 的 UTF-16
    # lpCurrentDirectory 传进去就正常了（纯 ASCII 路径下两种写法完全等价）。
    $extract = Invoke-Native -FilePath $tar -Arguments @('-xf', $zipPath) -WorkingDirectory $RepoRoot -TimeoutSeconds $TimeoutSeconds
    Write-Host ("tar -xf exit={0} seconds={1}" -f $extract.ExitCode, $extract.Seconds)
    if ($extract.ExitCode -ne 0) { Fail-Prepare ("unpacking the frozen baseline failed with exit=" + $extract.ExitCode + ' stderr=' + ([string]$extract.StdErr)) }
    $defect = Test-PristineTree -Path $RepoRoot
    if ($defect -ne '') { Fail-Prepare "the freshly extracted tree is not pristine: $defect" }
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath

# --------------------------------------------------------------------------- #
# 3. leakage guard
# --------------------------------------------------------------------------- #
$forbiddenNames = @('reference.patch', 'rubric.json', 'solve.ps1', 'run_tests.ps1', 'aggregate_results.ps1', 'golden.patch', 'solution.diff')
$forbiddenDirs = @('tests', 'solution', 'evidence', 'metadata')
$leaks = @()
foreach ($name in $forbiddenNames) {
    $hits = @(Get-ChildItem -LiteralPath $RepoRoot -Recurse -File -Filter $name -ErrorAction SilentlyContinue)
    foreach ($hit in $hits) { $leaks += $hit.FullName }
}
foreach ($dir in $forbiddenDirs) {
    $candidate = Join-Path $RepoRoot $dir
    if (Test-Path -LiteralPath $candidate) { $leaks += $candidate }
}
$trackedLeaks = @()
$tracked = Invoke-Native -FilePath 'git' -Arguments @('-C', $RepoRoot, 'ls-files') -TimeoutSeconds 120
foreach ($line in @(([string]$tracked.StdOut) -split "`n")) {
    $entry = $line.Trim()
    if ($entry -eq '') { continue }
    foreach ($name in $forbiddenNames) { if ($entry.EndsWith($name)) { $trackedLeaks += $entry } }
    foreach ($dir in $forbiddenDirs) { if ($entry.StartsWith($dir + '/')) { $trackedLeaks += $entry } }
}
if ($leaks.Count -gt 0 -or $trackedLeaks.Count -gt 0) {
    Fail-Prepare ("the agent-visible tree must not contain tests/solution/evidence/metadata or a golden patch; found: " + (($leaks + $trackedLeaks) -join ', '))
}
Write-Host 'leakageGuard=CLEAN (no tests/, solution/, evidence/, metadata/, rubric, golden patch in the tree or in git history)'

# --------------------------------------------------------------------------- #
# 4. offline pre-build (proves the frozen initial state is buildable)
# --------------------------------------------------------------------------- #
$prebuildOk = $false
$prebuildErrors = 0
$prebuildDir = Join-Path (Split-Path -Parent $RepoRoot) 'prebuild'
if ($SkipPrebuild) {
    Write-Host 'prebuild=SKIPPED (-SkipPrebuild)'
    $prebuildOk = $true
}
else {
    try { Remove-TreeSafe $prebuildDir } catch { }
    $prebuildObj = Join-Path $prebuildDir 'obj'
    $prebuildBin = Join-Path $prebuildDir 'bin'
    New-DirectorySafe $prebuildObj | Out-Null
    New-DirectorySafe $prebuildBin | Out-Null

    $offlineConfig = Join-Path $prebuildDir 'nuget-offline.config'
    $configText = @"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="harbor-offline" value="$feedDir" />
  </packageSources>
  <packageRestore>
    <add key="enabled" value="True" />
    <add key="automatic" value="False" />
  </packageRestore>
</configuration>
"@
    Write-Utf8NoBom -Path $offlineConfig -Text $configText

    $projectFile = Join-Path $RepoRoot 'LiteMonitor.csproj'
    $restore = Invoke-Native -FilePath $dotnet -Arguments @(
        'restore', $projectFile, '--configfile', $offlineConfig, '--nologo', '-v', 'minimal',
        "-p:BaseIntermediateOutputPath=$prebuildObj\") -WorkingDirectory $RepoRoot -TimeoutSeconds $TimeoutSeconds
    Write-Host ("prebuild restore exit={0} seconds={1}" -f $restore.ExitCode, $restore.Seconds)

    if ($restore.ExitCode -eq 0) {
        $build = Invoke-Native -FilePath $dotnet -Arguments @(
            'build', $projectFile, '-c', 'Release', '--no-restore', '--nologo', '-v', 'minimal',
            "-p:BaseIntermediateOutputPath=$prebuildObj\", "-p:BaseOutputPath=$prebuildBin\",
            '-p:EnableWindowsTargeting=true') -WorkingDirectory $RepoRoot -TimeoutSeconds $TimeoutSeconds
        $buildLog = [string]$build.StdOut + "`r`n" + [string]$build.StdErr
        $matches = [regex]::Matches($buildLog, '(?m)\berror\s+(CS|MSB|NU|NETSDK)[0-9]+')
        $prebuildErrors = $matches.Count
        $prebuildDll = Join-Path (Join-Path (Join-Path $prebuildBin 'Release') 'net8.0-windows') 'LiteMonitor.dll'
        $prebuildOk = ($build.ExitCode -eq 0 -and $prebuildErrors -eq 0 -and (Test-Path -LiteralPath $prebuildDll))
        Write-Host ("prebuild build exit={0} errors={1} seconds={2} dll={3}" -f $build.ExitCode, $prebuildErrors, $build.Seconds, (Test-Path -LiteralPath $prebuildDll))
        $logPath = Join-Path $prebuildDir 'prebuild.log'
        Write-Utf8NoBom -Path $logPath -Text $buildLog
        Write-Host "prebuildLog=$logPath"
    }
    else {
        Write-Utf8NoBom -Path (Join-Path $prebuildDir 'restore.log') -Text (([string]$restore.StdOut) + "`r`n" + ([string]$restore.StdErr))
    }

    # The pre-build must not dirty the tree the agent is about to work in.
    $postStatus = Invoke-Native -FilePath 'git' -Arguments @('-C', $RepoRoot, 'status', '--porcelain') -TimeoutSeconds 120
    $postStatusText = ([string]$postStatus.StdOut).Trim()
    if ($postStatusText -ne '') { Fail-Prepare "the offline pre-build dirtied the agent tree: $postStatusText" }
}
if (-not $prebuildOk) { Fail-Prepare "the frozen baseline does not build offline in this environment (errors=$prebuildErrors); this is an infrastructure fault" }

# --------------------------------------------------------------------------- #
# 5. start from empty machine state
# --------------------------------------------------------------------------- #
if (-not $SkipCleanup) {
    $cleanupScript = Join-Path $script:EnvDir 'cleanup.ps1'
    $psExe = (Get-Process -Id $PID).Path
    $cleanup = Invoke-Native -FilePath $psExe -Arguments @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $cleanupScript, '-Quiet') -WorkingDirectory $script:EnvDir -TimeoutSeconds 600
    Write-Host ("initialCleanup exit={0}" -f $cleanup.ExitCode)
    Write-Host (([string]$cleanup.StdOut).Trim())
    if ($cleanup.ExitCode -eq 2) { Fail-Prepare 'the initial machine-state cleanup reported an infrastructure fault' }
}

Write-Host ''
Write-Host "REPO_ROOT=$RepoRoot"
Write-Host "BASELINE_COMMIT=$BaselineCommit"
Write-Host "BASELINE_ZIP_SHA256=$BaselineZipSha256"
Write-Host "PREBUILD_OK=$prebuildOk"
Write-Host 'PREPARED=1'
exit 0
