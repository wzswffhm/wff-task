#Requires -Version 5.1
<#
.SYNOPSIS
    Builds and starts the project under test for Harbor task windows-d4-litemonitor-001.

.DESCRIPTION
    Three non-interactive modes, all of which propagate real exit codes:

      build  offline restore + Release build of LiteMonitor.csproj. Build output is
             redirected outside the repository so the agent tree stays byte-clean.
      smoke  build, then verify the produced artifacts and that LiteMonitor.dll is a
             loadable, correctly targeted managed assembly (metadata only - no product
             code is executed, so this stays safe on a headless build executor).
      run    build, then launch LiteMonitor.exe, keep it under observation for a fixed
             window and terminate it. If the product exits by itself inside that window
             its own exit code is propagated instead of being hidden. On a session-0 /
             headless container a WinForms tray application may legitimately refuse to
             start; that outcome is reported, never faked.

    Nothing here is a scoring entry point. tests/run_tests.ps1 is the only judge.

.OUTPUTS
    Exit code 0 = the requested mode succeeded.
    Any other non-zero value is the real exit code of the tool or product involved.
    Exit code 2 = infrastructure fault (missing repository, missing toolchain).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File environment\run.ps1 -RepoRoot C:\ws\被测工程\repo -Mode smoke
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)][string]$RepoRoot,
    [Parameter(Mandatory = $false)][ValidateSet('build', 'smoke', 'run')][string]$Mode = 'build',
    [Parameter(Mandatory = $false)][string]$WorkDir,
    [Parameter(Mandatory = $false)][string]$Configuration = 'Release',
    [Parameter(Mandatory = $false)][int]$TimeoutSeconds = 1800,
    [Parameter(Mandatory = $false)][int]$RunWindowSeconds = 10
)

$ErrorActionPreference = 'Stop'
$script:EnvDir = $PSScriptRoot
. (Join-Path $script:EnvDir 'env_common.ps1')

Write-Banner "run ($Mode)"

if (-not $RepoRoot) { $RepoRoot = Get-DefaultRepoRoot -WorkspaceRoot (Get-DefaultWorkspaceRoot) }
if (-not (Test-Path -LiteralPath $RepoRoot)) {
    Write-Host "RUN_FAILED=the repository under test does not exist at $RepoRoot"
    Write-Host 'RUN_OK=0'
    exit 2
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
$projectFile = Join-Path $RepoRoot 'LiteMonitor.csproj'
if (-not (Test-Path -LiteralPath $projectFile)) {
    Write-Host "RUN_FAILED=$projectFile is missing"
    Write-Host 'RUN_OK=0'
    exit 2
}

if (-not $WorkDir) {
    if ($env:HARBOR_WORK_DIR) { $WorkDir = $env:HARBOR_WORK_DIR }
    else { $WorkDir = Join-Path (Split-Path -Parent $RepoRoot) 'run-build' }
}
New-DirectorySafe $WorkDir | Out-Null
$WorkDir = (Resolve-Path -LiteralPath $WorkDir).ProviderPath
$objDir = Join-Path $WorkDir 'obj'
$binDir = Join-Path $WorkDir 'bin'
New-DirectorySafe $objDir | Out-Null
New-DirectorySafe $binDir | Out-Null

$dotnet = Get-DotNetCli
if (-not $dotnet) {
    Write-Host 'RUN_FAILED=the .NET SDK CLI (dotnet) was not found on PATH'
    Write-Host 'RUN_OK=0'
    exit 2
}
$feedDir = Join-Path (Join-Path $script:EnvDir 'assets') 'nuget'
if (-not (Test-Path -LiteralPath $feedDir)) {
    Write-Host "RUN_FAILED=the vendored offline NuGet feed is missing at $feedDir"
    Write-Host 'RUN_OK=0'
    exit 2
}

$offlineConfig = Join-Path $WorkDir 'nuget-offline.config'
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

Write-Host "repoRoot=$RepoRoot"
Write-Host "workDir=$WorkDir"
Write-Host "offlineFeed=$feedDir"

$restore = Invoke-Native -FilePath $dotnet -Arguments @(
    'restore', $projectFile, '--configfile', $offlineConfig, '--nologo', '-v', 'minimal',
    "-p:BaseIntermediateOutputPath=$objDir\") -WorkingDirectory $RepoRoot -TimeoutSeconds $TimeoutSeconds
Write-Host ("restore exit={0} seconds={1}" -f $restore.ExitCode, $restore.Seconds)
if ($restore.ExitCode -ne 0) {
    Write-Utf8NoBom -Path (Join-Path $WorkDir 'restore.log') -Text (([string]$restore.StdOut) + "`r`n" + ([string]$restore.StdErr))
    Write-Host "RUN_FAILED=offline restore failed with exit=$($restore.ExitCode); see $(Join-Path $WorkDir 'restore.log')"
    Write-Host 'RUN_OK=0'
    exit $restore.ExitCode
}

$build = Invoke-Native -FilePath $dotnet -Arguments @(
    'build', $projectFile, '-c', $Configuration, '--no-restore', '--nologo', '-v', 'minimal',
    "-p:BaseIntermediateOutputPath=$objDir\", "-p:BaseOutputPath=$binDir\",
    '-p:EnableWindowsTargeting=true') -WorkingDirectory $RepoRoot -TimeoutSeconds $TimeoutSeconds
$buildLog = [string]$build.StdOut + "`r`n--- stderr ---`r`n" + [string]$build.StdErr
Write-Utf8NoBom -Path (Join-Path $WorkDir 'build.log') -Text $buildLog
$errorMatches = [regex]::Matches($buildLog, '(?m)\berror\s+(CS|MSB|NU|NETSDK)[0-9]+')
Write-Host ("build exit={0} errors={1} seconds={2}" -f $build.ExitCode, $errorMatches.Count, $build.Seconds)

$outputDir = Join-Path (Join-Path $binDir $Configuration) 'net8.0-windows'
$appDll = Join-Path $outputDir 'LiteMonitor.dll'
$appExe = Join-Path $outputDir 'LiteMonitor.exe'
Write-Host "outputDir=$outputDir"
Write-Host "appDll=$(Test-Path -LiteralPath $appDll) appExe=$(Test-Path -LiteralPath $appExe)"

if ($build.ExitCode -ne 0 -or $errorMatches.Count -gt 0 -or -not (Test-Path -LiteralPath $appDll)) {
    Write-Host "RUN_FAILED=the build did not succeed (exit=$($build.ExitCode) errors=$($errorMatches.Count) dll=$(Test-Path -LiteralPath $appDll)); see $(Join-Path $WorkDir 'build.log')"
    Write-Host 'RUN_OK=0'
    if ($build.ExitCode -ne 0) { exit $build.ExitCode }
    exit 1
}

if ($Mode -eq 'build') {
    Write-Host 'RUN_OK=1'
    exit 0
}

if ($Mode -eq 'smoke') {
    $problems = @()
    if (-not (Test-Path -LiteralPath $appExe)) { $problems += "the apphost $appExe was not produced" }
    try {
        $assemblyName = [System.Reflection.AssemblyName]::GetAssemblyName($appDll)
        Write-Host ("assembly={0} version={1} processorArchitecture={2}" -f $assemblyName.Name, $assemblyName.Version.ToString(), $assemblyName.ProcessorArchitecture.ToString())
        if ($assemblyName.Name -ne 'LiteMonitor') { $problems += "unexpected assembly identity $($assemblyName.Name)" }
    }
    catch { $problems += ('the produced LiteMonitor.dll is not a readable managed assembly: ' + $_.Exception.Message) }

    # 这两个锁定依赖在输出目录里的落点由 NuGet 的资产规则决定，不是由我们决定：
    #   System.Text.Json 9.0.10 带 lib/<tfm>，运行时资产直接拷到产物旁边；
    #   LibreHardwareMonitorLib 0.9.6 是 RID 专属包（只有 ref/<tfm> 与
    #   runtimes/win-*/lib/<tfm>，没有 lib/），在没有 RuntimeIdentifier 的框架依赖
    #   构建里，按 NuGet 规范运行时资产落在 runtimes\win-x64\lib\net8.0\ 下。
    # 所以两个落点都接受，两个都没有才算真问题；把实际解析到的相对路径打出来，
    # 让「依赖确实被还原并拷贝了」这件事在日志里可核对，而不是靠猜。
    foreach ($dependency in @('System.Text.Json.dll', 'LibreHardwareMonitorLib.dll')) {
        $resolved = @()
        if (Test-Path -LiteralPath (Join-Path $outputDir $dependency)) { $resolved += $dependency }
        $ridHits = @(Get-ChildItem -LiteralPath $outputDir -Recurse -File -Filter $dependency -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\runtimes\\win(-x64)?\\lib\\' } |
            ForEach-Object { $_.FullName.Substring($outputDir.Length).TrimStart('\') })
        $resolved += $ridHits
        if ($resolved.Count -eq 0) {
            $problems += "the locked dependency $dependency was produced neither next to the app nor under runtimes\win-x64\lib\ (offline restore did not flow the asset)"
        }
        else {
            Write-Host ("dependency={0} resolved={1}" -f $dependency, ($resolved -join ', '))
        }
    }
    foreach ($resource in @('lang\zh.json', 'lang\en.json')) {
        $path = Join-Path (Join-Path $RepoRoot 'resources') $resource
        if (-not (Test-Path -LiteralPath $path)) { $problems += "the product resource resources\$resource is missing from the repository" }
    }

    if ($problems.Count -gt 0) {
        foreach ($problem in $problems) { Write-Host "SMOKE_PROBLEM=$problem" }
        Write-Host 'RUN_OK=0'
        exit 1
    }
    Write-Host "SMOKE_PROBLEMS=0"
    Write-Host 'RUN_OK=1'
    exit 0
}

# ---- Mode = run ------------------------------------------------------------- #
Write-Host "launching $appExe for up to $RunWindowSeconds second(s)"
$started = $null
try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $appExe
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WorkingDirectory = $outputDir
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $started = [System.Diagnostics.Process]::Start($psi)
}
catch {
    Write-Host ('RUN_FAILED=cannot launch the product: ' + $_.Exception.GetType().Name + ': ' + $_.Exception.Message)
    Write-Host 'RUN_OK=0'
    exit 1
}

$outTask = $started.StandardOutput.ReadToEndAsync()
$errTask = $started.StandardError.ReadToEndAsync()
$survived = -not $started.WaitForExit([int]($RunWindowSeconds * 1000))
$exitCode = 0
if ($survived) {
    Write-Host ("product pid={0} was still alive after {1}s; terminating it" -f $started.Id, $RunWindowSeconds)
    try { $started.Kill() } catch { }
    try { [void]$started.WaitForExit(15000) } catch { }
    $exitCode = 0
}
else {
    $exitCode = $started.ExitCode
    Write-Host ("product pid={0} exited on its own after {1}s with code {2}" -f $started.Id, $RunWindowSeconds, $exitCode)
}
try { if ($outTask.Wait(5000)) { Write-Utf8NoBom -Path (Join-Path $WorkDir 'product.out.log') -Text $outTask.Result } } catch { }
try { if ($errTask.Wait(5000)) { Write-Utf8NoBom -Path (Join-Path $WorkDir 'product.err.log') -Text $errTask.Result } } catch { }
try { $started.Dispose() } catch { }

$stopped = @(Stop-TaskProcesses)
if ($stopped.Count -gt 0) { Write-Host ("terminatedLeftovers={0}" -f ($stopped -join ', ')) }

if (-not $survived -and $exitCode -ne 0) {
    Write-Host "RUN_FAILED=the product terminated by itself with exit code $exitCode; see $(Join-Path $WorkDir 'product.err.log')"
    Write-Host 'RUN_OK=0'
    exit $exitCode
}
Write-Host "productSurvivedWindow=$survived"
Write-Host 'RUN_OK=1'
exit 0
