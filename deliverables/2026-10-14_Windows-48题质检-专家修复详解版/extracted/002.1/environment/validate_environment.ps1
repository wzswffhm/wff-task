#Requires -Version 5.1
<#
.SYNOPSIS
    Readiness and dependency self-check for Harbor task windows-d4-litemonitor-001 (E1).

.DESCRIPTION
    Verifies everything tests/run_tests.ps1 depends on BEFORE any scoring happens, so a
    broken environment is reported as INVALID instead of being mistaken for a model
    failure:
      * Windows runtime, architecture, locale and PowerShell edition
      * .NET SDK >= 8 and a tar implementation able to unpack the frozen baseline
      * HKCU is writable in the 64-bit registry view (the task mirrors state there)
      * %LOCALAPPDATA% is writable (the task stores settings there)
      * the frozen baseline archive is present with the expected size and SHA-256
      * the baseline archive carries no tests/solution/rubric/golden-patch leakage
      * the vendored offline NuGet feed is complete (no download at build/score time)
      * the Harbor packages that THIS image role is allowed to carry expose their
        required entry points, and the ones it must NOT carry are proven absent
      * the frozen-input image stamp written by environment/image_stamp.ps1
      * E1 conformance: no E2-E4 adapter.toml / restore.ps1 in this package

    甲方 2026-09-09 复核整改项 ①：1.0.0 把 tests/ 与 solution/ 和 Agent 工作区烧进同一个
    镜像。1.1.0 起镜像一分为二，本脚本因此按 -Scope 分三种口径自检，缺省从
    $env:HARBOR_IMAGE_ROLE 推断：
      package  交付目录口径（宿主机上跑，四个包 + metadata 必须齐全）
      agent    Agent 镜像口径（tests/ solution/ metadata/ evidence/ 必须不存在）
      scorer   Scorer 镜像口径（tests/ solution/ 必须齐全，且继承的 Agent 层指纹必须匹配）

    Non-interactive, idempotent, propagates exit codes.

.OUTPUTS
    Exit code 0 = ready. Exit code 2 = NOT ready (infrastructure fault -> INVALID).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File environment\validate_environment.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File environment\validate_environment.ps1 -Scope agent
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)][switch]$Quiet,
    [Parameter(Mandatory = $false)][ValidateSet('', 'package', 'agent', 'scorer', 'verifier')][string]$Scope = ''
)

$ErrorActionPreference = 'Stop'
$script:EnvDir = $PSScriptRoot
. (Join-Path $script:EnvDir 'env_common.ps1')

# 缺省口径来自镜像自己声明的角色：Agent 镜像 ENV HARBOR_IMAGE_ROLE=agent，Scorer 镜像
# 覆盖成 scorer，交付目录（宿主机）两者都没有，于是落到 package。这样 run_tests.ps1 里
# 那句无参调用在每个镜像中自动用对口径，不需要调用方记住传参。
if (-not $Scope) {
    $role = ([string]$env:HARBOR_IMAGE_ROLE).Trim().ToLowerInvariant()
    if ($role -eq 'agent' -or $role -eq 'scorer' -or $role -eq 'verifier') { $Scope = $role } else { $Scope = 'package' }
}
$script:Scope = $Scope

$script:CheckCount = 0
$script:FailCount = 0

function Report-Check {
    param([bool]$Ok, [string]$Name, [string]$Detail)
    $script:CheckCount++
    if (-not $Ok) { $script:FailCount++ }
    if (-not $Quiet -or -not $Ok) {
        $mark = 'OK  '
        if (-not $Ok) { $mark = 'FAIL' }
        Write-Host ("[{0}] {1} :: {2}" -f $mark, $Name, $Detail)
    }
    return $Ok
}

if (-not $Quiet) { Write-Banner 'validate_environment' }

# --------------------------------------------------------------------------- #
# runtime
# --------------------------------------------------------------------------- #
$isWindows = $true
try { $isWindows = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows) } catch { $isWindows = ($env:OS -eq 'Windows_NT') }
[void](Report-Check $isWindows 'os_is_windows' ("RuntimeInformation says Windows={0}, OSDescription={1}" -f $isWindows, [System.Environment]::OSVersion.VersionString))

$arch = [string]$env:PROCESSOR_ARCHITECTURE
[void](Report-Check ($arch -eq 'AMD64') 'os_architecture_x64' "PROCESSOR_ARCHITECTURE=$arch (the frozen contract requires an x64 registry view and x64 build)")

$psVersion = $PSVersionTable.PSVersion
$psOk = ($psVersion.Major -ge 5)
$edition = 'Windows PowerShell'
if ($psVersion.Major -ge 6) { $edition = 'PowerShell' }
[void](Report-Check $psOk 'powershell_supported' ("{0} {1} (this package is written for 5.1 AND 7)" -f $edition, $psVersion.ToString()))

$locale = (Get-Culture).Name
[void](Report-Check ($locale -ne '') 'locale_resolvable' ("current culture={0}, ui culture={1}; the task exercises zh-CN and non-ASCII paths" -f $locale, (Get-UICulture).Name))

# --------------------------------------------------------------------------- #
# toolchain
# --------------------------------------------------------------------------- #
$dotnet = Get-DotNetCli
if (-not $dotnet) {
    [void](Report-Check $false 'dotnet_cli_present' 'the .NET SDK CLI (dotnet) was not found on PATH')
}
else {
    $versionResult = Invoke-Native -FilePath $dotnet -Arguments @('--version') -TimeoutSeconds 120
    $versionText = ([string]$versionResult.StdOut).Trim()
    $major = 0
    if ($versionText -match '^(\d+)\.') { $major = [int]$Matches[1] }
    [void](Report-Check ($versionResult.ExitCode -eq 0 -and $major -ge $MinimumSdkMajor) 'dotnet_sdk_version' ("{0} reports SDK {1} (need >= {2}.x)" -f $dotnet, $versionText, $MinimumSdkMajor))

    $listResult = Invoke-Native -FilePath $dotnet -Arguments @('--list-runtimes') -TimeoutSeconds 120
    $hasDesktop = (([string]$listResult.StdOut) -match 'Microsoft\.WindowsDesktop\.App 8\.')
    [void](Report-Check $hasDesktop 'windowsdesktop_runtime_present' 'Microsoft.WindowsDesktop.App 8.x must be installed because LiteMonitor is a net8.0-windows WinForms project')
}

$tar = Get-TarCli
if (-not $tar) {
    [void](Report-Check $false 'tar_present' 'no tar implementation found; the frozen baseline archive cannot be unpacked')
}
else {
    $tarResult = Invoke-Native -FilePath $tar -Arguments @('--version') -TimeoutSeconds 60
    $firstLine = (([string]$tarResult.StdOut) -split "`n")[0].Trim()
    [void](Report-Check ($tarResult.ExitCode -eq 0) 'tar_version' ("{0} :: {1}" -f $tar, $firstLine))
}

# --------------------------------------------------------------------------- #
# machine state writability
# --------------------------------------------------------------------------- #
$registryOk = $false
$registryDetail = ''
try {
    $hive = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryView]::Registry64)
    try {
        $probe = $hive.CreateSubKey($script:RegistryProbeSubKey, $true)
        if ($null -ne $probe) {
            $probe.SetValue('Probe', 'harbor', [Microsoft.Win32.RegistryValueKind]::String)
            $probe.SetValue('ProbeQ', [long]9000000000, [Microsoft.Win32.RegistryValueKind]::QWord)
            $probe.SetValue('ProbeE', '%LOCALAPPDATA%\LiteMonitor', [Microsoft.Win32.RegistryValueKind]::ExpandString)
            $probe.Close()
            $read = $hive.OpenSubKey($script:RegistryProbeSubKey, $false)
            $registryOk = ($null -ne $read -and [string]$read.GetValue('Probe') -eq 'harbor')
            if ($null -ne $read) { $read.Close() }
            $hive.DeleteSubKeyTree($script:RegistryProbeSubKey, $false)
            $registryDetail = 'HKCU writable in the 64-bit view (REG_SZ / REG_QWORD / REG_EXPAND_SZ probe created, read back and removed)'
        }
        else { $registryDetail = 'CreateSubKey returned null' }
    }
    finally { $hive.Close() }
}
catch { $registryDetail = $_.Exception.GetType().Name + ': ' + $_.Exception.Message }
[void](Report-Check $registryOk 'hkc_registry_writable' $registryDetail)

$localAppDataOk = $false
$localDetail = ''
try {
    $local = Resolve-LocalAppDataRoot
    $probeDir = Join-Path $local ("harbor-probe-" + [Guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $probeDir -Force | Out-Null
    $probeFile = Join-Path $probeDir 'probe.txt'
    Write-Utf8NoBom -Path $probeFile -Text 'harbor'
    $localAppDataOk = (Test-Path -LiteralPath $probeFile)
    Remove-TreeSafe $probeDir
    $localDetail = "%LOCALAPPDATA%=$local is writable (probe directory created, written and removed)"
}
catch { $localDetail = $_.Exception.GetType().Name + ': ' + $_.Exception.Message }
[void](Report-Check $localAppDataOk 'localappdata_writable' $localDetail)

# --------------------------------------------------------------------------- #
# frozen assets
# --------------------------------------------------------------------------- #
$assetDir = Join-Path $script:EnvDir 'assets'
$zipPath = Join-Path $assetDir $BaselineZipName
if (-not (Test-Path -LiteralPath $zipPath)) {
    [void](Report-Check $false 'baseline_archive_present' "missing $zipPath")
}
else {
    $size = (Get-Item -LiteralPath $zipPath).Length
    [void](Report-Check ($size -eq $BaselineZipBytes) 'baseline_archive_size' ("{0} bytes, expected {1}" -f $size, $BaselineZipBytes))
    $hash = Get-Sha256 $zipPath
    [void](Report-Check ($hash -eq $BaselineZipSha256) 'baseline_archive_sha256' ("sha256:$hash expected sha256:$BaselineZipSha256"))

    $listing = Invoke-Native -FilePath (Get-TarCli) -Arguments @('-tf', $zipPath) -TimeoutSeconds 300
    $entries = @(([string]$listing.StdOut) -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
    [void](Report-Check ($entries.Count -gt 50) 'baseline_archive_readable' ("{0} entries listed from the frozen archive" -f $entries.Count))

    $forbidden = @($entries | Where-Object {
            $_ -match '(^|/)(tests|solution|evidence|metadata)(/|$)' -or
            $_ -match 'reference\.patch$' -or $_ -match 'rubric\.json$' -or
            $_ -match 'solve\.ps1$' -or $_ -match 'run_tests\.ps1$' -or
            $_ -match 'golden' -or $_ -match 'RegistryNotify\.solved' -or $_ -match 'StatusMirror\.solved'
        })
    [void](Report-Check ($forbidden.Count -eq 0) 'baseline_archive_no_leakage' ("the agent-visible archive must not carry tests/solution/rubric/golden patch; found {0} offending entr(ies)" -f $forbidden.Count))

    $contract = @($entries | Where-Object { $_ -match 'src/Core/RegistryNotify\.cs$' })
    [void](Report-Check ($contract.Count -eq 1) 'baseline_archive_has_contract' ("src/Core/RegistryNotify.cs present {0} time(s) in the frozen archive" -f $contract.Count))

    $mirrorContract = @($entries | Where-Object { $_ -match 'src/Core/StatusMirror\.cs$' })
    [void](Report-Check ($mirrorContract.Count -eq 1) 'baseline_archive_has_mirror_contract' ("src/Core/StatusMirror.cs present {0} time(s) in the frozen archive" -f $mirrorContract.Count))

    $vendorEntry = @($entries | Where-Object { $_ -match '\.txt$' })
    [void](Report-Check ($vendorEntry.Count -ge 1) 'baseline_archive_has_vendor_txt' ("{0} .txt entr(ies); the csproj Content reference to the vendor note must resolve or the build fails with MSB3030" -f $vendorEntry.Count))
}

$feedDir = Join-Path $assetDir 'nuget'
$feedPackages = 0
if (Test-Path -LiteralPath $feedDir) { $feedPackages = @(Get-ChildItem -LiteralPath $feedDir -Filter '*.nupkg' -File).Count }
[void](Report-Check ($feedPackages -ge $MinimumFeedPackages) 'offline_nuget_feed' ("{0} vendored .nupkg file(s) at {1} (need >= {2}); no dependency may be downloaded at build or scoring time" -f $feedPackages, $feedDir, $MinimumFeedPackages))

foreach ($required in @(
        @('System.Text.Json.9.0.10.nupkg', 'System.Text.Json 9.0.10 is the JSON serializer LiteMonitor binds against'),
        @('LibreHardwareMonitorLib.0.9.6.nupkg', 'LibreHardwareMonitorLib 0.9.6 is the sensor backend LiteMonitor binds against'))) {
    $packagePath = Join-Path $feedDir $required[0]
    [void](Report-Check (Test-Path -LiteralPath $packagePath) ("feed_package_" + ($required[0] -replace '[^A-Za-z0-9]', '_')) $required[1])
}

$vendorTxt = Join-Path (Join-Path $assetDir 'vendor') $VendorTxtName
[void](Report-Check (Test-Path -LiteralPath $vendorTxt) 'vendor_note_asset' "prepare.ps1 restores $VendorTxtName from here if an agent run deletes it")

# --------------------------------------------------------------------------- #
# Harbor package entry points - per image role
# --------------------------------------------------------------------------- #
# environment/ 与 instruction.md、task.toml 是 Agent 可见的三个包，任何口径都必须齐全。
$requiredFiles = @(
    (Join-Path $script:TaskDir 'instruction.md'),
    (Join-Path $script:TaskDir 'task.toml'),
    (Join-Path $script:EnvDir 'prepare.ps1'),
    (Join-Path $script:EnvDir 'run.ps1'),
    (Join-Path $script:EnvDir 'cleanup.ps1'),
    (Join-Path $script:EnvDir 'image_stamp.ps1'),
    (Join-Path $script:EnvDir 'build_image.ps1'),
    (Join-Path $script:EnvDir 'metadata.json'),
    (Join-Path $script:EnvDir 'Dockerfile'),
    (Join-Path $script:EnvDir 'Dockerfile.scorer')
)
# tests/ 与 solution/ 只允许出现在 Scorer 镜像与交付目录里。
$scorerOnlyFiles = @(
    (Join-Path $script:TaskDir 'solution\solve.ps1'),
    (Join-Path $script:TaskDir 'solution\reference.patch'),
    (Join-Path $script:TaskDir 'solution\README.md'),
    (Join-Path $script:TaskDir 'tests\run_tests.ps1'),
    (Join-Path $script:TaskDir 'tests\test_fail_to_pass.ps1'),
    (Join-Path $script:TaskDir 'tests\test_pass_to_pass.ps1'),
    (Join-Path $script:TaskDir 'tests\test_system_state.ps1'),
    (Join-Path $script:TaskDir 'tests\rubric.json'),
    (Join-Path $script:TaskDir 'tests\aggregate_results.ps1'),
    (Join-Path $script:TaskDir 'tests\harness_common.ps1'),
    (Join-Path $script:TaskDir 'tests\LiteMonitor.Evaluator\LiteMonitor.Evaluator.csproj')
)
# metadata/ 是交付侧材料，不进任何镜像。
$packageOnlyFiles = @()
if ($script:Scope -eq 'package' -or $script:Scope -eq 'scorer') { $requiredFiles += $scorerOnlyFiles }
if ($script:Scope -eq 'verifier') { $requiredFiles += @($scorerOnlyFiles | Where-Object { $_ -notlike '*\solution\*' }) }
if ($script:Scope -eq 'package') { $requiredFiles += $packageOnlyFiles }

foreach ($required in $requiredFiles) {
    $leaf = $required.Substring($script:TaskDir.Length).TrimStart('\')
    [void](Report-Check (Test-Path -LiteralPath $required) 'required_artifact' ("{0} must exist for scope '{1}'" -f $leaf, $script:Scope))
}

# --------------------------------------------------------------------------- #
# leakage assertion - the whole point of splitting the image in two
# --------------------------------------------------------------------------- #
# Agent 镜像里出现 tests/ solution/ metadata/ evidence/ 中任何一个，都意味着参考解或判分
# 脚本对模型可见，属于甲方复核项 ① 的直接回归。这里反向断言它们不存在，让镜像构建本身
# 成为证据，而不是让评审去相信 Dockerfile 的 COPY 列表。
$forbiddenDirs = @('tests', 'solution', 'metadata', 'evidence')
if ($script:Scope -eq 'scorer') { $forbiddenDirs = @('metadata', 'evidence') }
if ($script:Scope -eq 'verifier') { $forbiddenDirs = @('solution', 'metadata', 'evidence') }
if ($script:Scope -eq 'package') { $forbiddenDirs = @() }
foreach ($dir in $forbiddenDirs) {
    $candidate = Join-Path $script:TaskDir $dir
    [void](Report-Check (-not (Test-Path -LiteralPath $candidate)) 'image_role_no_leakage' `
        ("scope '{0}' must not carry {1}\ under the task root ({2})" -f $script:Scope, $dir, $script:TaskDir))
}
if ($script:Scope -eq 'agent') {
    $leakNames = @('run_tests.ps1', 'aggregate_results.ps1', 'harness_common.ps1', 'rubric.json',
                   'reference.patch', 'solve.ps1', 'golden.patch', 'solution.diff')
    $leakedFiles = @()
    foreach ($name in $leakNames) {
        $leakedFiles += @(Get-ChildItem -LiteralPath $script:TaskDir -Recurse -File -Filter $name -Force -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    }
    [void](Report-Check ($leakedFiles.Count -eq 0) 'agent_image_no_judge_or_solution_file' `
        ("no scoring or reference-solution file may exist anywhere in the Agent image; found {0}: {1}" -f $leakedFiles.Count, ($leakedFiles -join ', ')))
}

# --------------------------------------------------------------------------- #
# frozen-input image stamp
# --------------------------------------------------------------------------- #
$stampPath = [string]$env:HARBOR_IMAGE_STAMP
if (-not $stampPath) { $stampPath = 'C:\harbor\image_stamp.json' }
if ($script:Scope -eq 'package') {
    # 交付目录不是镜像，本来就没有 stamp；只要求生成它的脚本在位（上面已断言）。
    [void](Report-Check $true 'image_stamp_not_applicable' 'scope ''package'' is the delivery directory, not a built image, so no C:\harbor\image_stamp.json is expected')
}
elseif (Test-Path -LiteralPath $stampPath) {
    $stampText = Read-Utf8 $stampPath
    $stampOk = $false
    $stampFingerprint = ''
    try {
        $stampJson = $stampText | ConvertFrom-Json
        $stampFingerprint = [string]$stampJson.fingerprint
        $stampOk = ($stampFingerprint -match '^[0-9a-f]{64}$' -and [string]$stampJson.task_id -eq $script:TaskId)
    }
    catch { $stampOk = $false }
    [void](Report-Check $stampOk 'image_stamp_wellformed' ("{0} carries a 64-hex fingerprint for {1}: {2}" -f $stampPath, $script:TaskId, $stampFingerprint))
    if ($script:Scope -eq 'scorer') {
        $expected = ([string]$env:HARBOR_AGENT_IMAGE_FINGERPRINT).Trim().ToLowerInvariant()
        [void](Report-Check ($expected -eq $stampFingerprint) 'scorer_inherits_frozen_agent_layer' `
            ("HARBOR_AGENT_IMAGE_FINGERPRINT={0} must equal the inherited stamp {1}" -f $expected, $stampFingerprint))
    }
}
else {
    [void](Report-Check $false 'image_stamp_present' ("scope '{0}' runs inside a built image, so the frozen-input stamp {1} written by environment/image_stamp.ps1 must exist" -f $script:Scope, $stampPath))
}

# --------------------------------------------------------------------------- #
# E1 conformance
# --------------------------------------------------------------------------- #
foreach ($forbidden in @('adapter.toml', 'restore.ps1')) {
    $path = Join-Path $script:EnvDir $forbidden
    [void](Report-Check (-not (Test-Path -LiteralPath $path)) 'e1_conformance' ("tier E1 must not ship {0} (that file belongs to E2-E4 VM/hardware adapters)" -f $forbidden))
}

$dockerfile = Join-Path $script:EnvDir 'Dockerfile'
if (Test-Path -LiteralPath $dockerfile) {
    $dockerText = Read-Utf8 $dockerfile
    $pinned = $dockerText.Contains($BaseImageDigest)
    [void](Report-Check $pinned 'base_image_immutable_digest' ("Dockerfile must pin the base image by digest {0}" -f $BaseImageDigest))
    $fromLines = @(([regex]::Matches($dockerText, '(?im)^\s*FROM\s+[^\r\n]+')) | ForEach-Object { $_.Value.Trim() })
    $unpinned = @($fromLines | Where-Object { $_ -notmatch '@sha256:' -and $_ -notmatch '(?i)^FROM\s+mcr\.microsoft\.com/windows/servercore' })
    [void](Report-Check ($unpinned.Count -eq 0 -and $fromLines.Count -eq 1) 'dockerfile_all_from_pinned' ("FROM lines: {0}" -f ($fromLines -join ' | ')))
    $copiesTests = ($dockerText -match '(?im)^\s*COPY\s+(\S*\btests/|\S*\bsolution/)')
    [void](Report-Check (-not $copiesTests) 'agent_dockerfile_copies_no_tests_or_solution' 'the Agent Dockerfile must not COPY tests/ or solution/ into the image (甲方 2026-09-09 整改项 ①)')
}

$scorerDockerfile = Join-Path $script:EnvDir 'Dockerfile.scorer'
if (Test-Path -LiteralPath $scorerDockerfile) {
    $scorerText = Read-Utf8 $scorerDockerfile
    $scorerFrom = @(([regex]::Matches($scorerText, '(?im)^\s*FROM\s+[^\r\n]+')) | ForEach-Object { $_.Value.Trim() })
    # Both builds use the immutable external SDK and identical agent build steps.
    $agentText = Read-Utf8 (Join-Path $script:EnvDir 'Dockerfile')
    $fromOk = ($scorerFrom.Count -eq 1 -and $scorerFrom[0].Contains('@' + $script:BaseImageDigest) -and $scorerText.StartsWith($agentText, [StringComparison]::Ordinal))
    [void](Report-Check $fromOk 'scorer_dockerfile_digest_and_agent_build' ("FROM lines: {0}; scorer must repeat the exact agent build prefix" -f ($scorerFrom -join ' | ')))
    $fpMatch = [regex]::Match($scorerText, 'HARBOR_AGENT_IMAGE_FINGERPRINT=([0-9a-fA-F]{64})')
    [void](Report-Check $fpMatch.Success 'scorer_dockerfile_pins_agent_fingerprint' 'Dockerfile.scorer must freeze a 64-hex HARBOR_AGENT_IMAGE_FINGERPRINT that image_stamp.ps1 -Assert verifies at build time')
    $asserts = ($scorerText -match 'build_image\.ps1\s+-Role\s+scorer')
    [void](Report-Check $asserts 'scorer_dockerfile_asserts_stamp' 'Dockerfile.scorer must invoke build_image.ps1 -Role scorer, which asserts the frozen input fingerprint')
    $copiesBoth = ($scorerText -match '(?im)^\s*COPY\s+tests/') -and ($scorerText -match '(?im)^\s*COPY\s+solution/')
    [void](Report-Check $copiesBoth 'scorer_dockerfile_adds_tests_and_solution' 'the Scorer image is where tests/ and solution/ live, and the only place they live')
}
else {
    [void](Report-Check $false 'scorer_dockerfile_present' 'environment/Dockerfile.scorer must exist: it is the image that carries tests/ and solution/')
}

# --------------------------------------------------------------------------- #
# verdict
# --------------------------------------------------------------------------- #
$ready = ($script:FailCount -eq 0)
Write-Host ''
Write-Host ("scope={0}" -f $script:Scope)
Write-Host ("checks={0} failed={1}" -f $script:CheckCount, $script:FailCount)
Write-Host ("baseImage={0}@{1}" -f $BaseImage, $BaseImageDigest)
Write-Host ("baselineCommit={0} upstreamCommit={1}" -f $BaselineCommitShort, $UpstreamCommitShort)
if ($ready) { Write-Host 'READY=1' } else { Write-Host 'READY=0' }
if ($ready) { exit 0 }
exit 2
