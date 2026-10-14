[CmdletBinding()]
param([string]$RepoRoot = $env:HARBOR_REPO_ROOT, [string]$ResultsDir = 'C:\logs\verifier\results', [string]$RunId = '')
$ErrorActionPreference = 'Stop'
if (-not $RepoRoot) { throw 'RepoRoot is required.' }
if (-not $RunId) { $RunId = [guid]::NewGuid().ToString('N') }
$RepoRoot = [IO.Path]::GetFullPath($RepoRoot)
$ResultsDir = [IO.Path]::GetFullPath($ResultsDir)
if ((Test-Path -LiteralPath $ResultsDir) -and @(Get-ChildItem -LiteralPath $ResultsDir -Force).Count) { throw 'Results directory must be empty.' }
New-Item -ItemType Directory -Path (Join-Path $ResultsDir 'artifacts') -Force | Out-Null
$fixture = Join-Path (Split-Path -Parent $RepoRoot) 'state'
if (-not $fixture.StartsWith('D:\bench-runs\windows-d6-001\', [StringComparison]::OrdinalIgnoreCase)) { $fixture = Join-Path "C:\task-state\windows-d6-001\$RunId" 'state' }
$env:OUTSIDE_WORKSPACE = $RepoRoot
$env:PATHACL_FIXTURE_ROOT = $fixture
$env:PATHACL_RESULTS = $ResultsDir
$env:PATHACL_CANDIDATE_DLL = ''
. (Join-Path $PSScriptRoot 'tool_invoke.ps1')
$invalid = ''
$cleanup = Join-Path $PSScriptRoot '..\environment\cleanup.ps1'
try {
    & $cleanup -FixtureRoot $fixture
    & (Join-Path $PSScriptRoot '..\environment\validate_environment.ps1') -RepoRoot $RepoRoot | Out-File (Join-Path $ResultsDir 'artifacts\readiness.log') -Encoding UTF8
    New-Item -ItemType Directory -Path $fixture -Force | Out-Null
    $probe = Join-Path $fixture 'readiness.txt'
    [IO.File]::WriteAllText($probe, 'readiness')
    Set-Content -LiteralPath ($probe + ':readiness') -Value 'ads' -Encoding ASCII
    $probeAcl = Get-Acl -LiteralPath $probe
    Set-Acl -LiteralPath $probe -AclObject $probeAcl
    New-Item -ItemType SymbolicLink -Path (Join-Path $fixture 'readiness-link') -Target $probe | Out-Null
    & $cleanup -FixtureRoot $fixture
    [void](Invoke-PathAclBuild -Workspace $RepoRoot)
    $runtime = @{
        os_description=[Runtime.InteropServices.RuntimeInformation]::OSDescription
        os_architecture=[Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
        process_architecture=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()
        framework_description=((& dotnet --list-runtimes | Where-Object { $_ -match '^Microsoft.NETCore.App 8\.' }) -join '; ')
        os_version=[Environment]::OSVersion.Version.ToString()
        locale=[Globalization.CultureInfo]::CurrentCulture.Name
        ui_locale=[Globalization.CultureInfo]::CurrentUICulture.Name
        time_zone=[TimeZoneInfo]::Local.Id
    }
    foreach ($suite in @('fail_to_pass','pass_to_pass','system_state')) {
        $raw = if ($suite -eq 'system_state') { @{} } else { & (Join-Path $PSScriptRoot "test_$suite.ps1") -ResultsDir $ResultsDir }
        if ($suite -eq 'fail_to_pass') {
            $workflow = & (Join-Path $PSScriptRoot 'test_deployment_workflow.ps1') -ResultsDir $ResultsDir
            foreach ($identifier in $workflow.Keys) { $raw[$identifier] = $workflow[$identifier] }
        }
        if ($raw -isnot [Collections.IDictionary]) { throw "Suite $suite returned no unambiguous result dictionary." }
        $checks = @()
        foreach ($identifier in @($raw.Keys | Sort-Object)) {
            if ($raw[$identifier] -isnot [bool]) { throw 'Suite verdict must be boolean.' }
            $state = if ($raw[$identifier]) { 'PASS' } else { 'FAIL' }
            $checks += @{id=$identifier; suite=$suite; status=$state; passed=$raw[$identifier]; detail="Native NTFS behavior: $identifier"}
        }
        @{task_id='windows-d6-001'; task_version='3.0.3'; run_id=$RunId; environment=$runtime; checks=$checks} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ResultsDir "suite_$suite.json") -Encoding UTF8
    }
} catch {
    $invalid = $_.Exception.Message
    ($_ | Out-String) + $_.ScriptStackTrace | Set-Content -LiteralPath (Join-Path $ResultsDir 'artifacts\verifier_exception.txt') -Encoding UTF8
} finally {
    try { & $cleanup -FixtureRoot $fixture -RunId $RunId -ReportPath (Join-Path $ResultsDir 'cleanup_report.json') }
    catch { $invalid += ' | Cleanup: ' + $_.Exception.Message }
}
& (Join-Path $PSScriptRoot 'aggregate_results.ps1') -ResultsDir $ResultsDir -RunId $RunId -InvalidReason $invalid
exit $LASTEXITCODE
