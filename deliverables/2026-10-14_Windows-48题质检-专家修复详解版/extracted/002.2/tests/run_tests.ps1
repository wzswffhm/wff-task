param([Parameter(Mandatory=$true)][string]$RepoRoot,[Parameter(Mandatory=$true)][string]$ResultsDir,[string]$RunId)
$ErrorActionPreference='Stop'
$task=Split-Path -Parent $PSScriptRoot
$workspace=Split-Path -Parent ([IO.Path]::GetFullPath($RepoRoot))
$state=Join-Path $workspace 'state'
if (-not $RunId) {$RunId=Split-Path -Leaf $workspace}
$env:OUTSIDE_WORKSPACE=$RepoRoot
$env:EVIDENCE_MIRROR_STATE=$state
$env:EVIDENCE_MIRROR_RESULTS=$ResultsDir
$env:EVIDENCE_MIRROR_REGISTRY_ROOT='SOFTWARE\Northgate\EvidenceMirrorBench\windows-d6-0007\'+(Split-Path -Leaf $workspace)
$build=Join-Path $workspace 'verifier-build'
$env:EVIDENCE_MIRROR_EXE=Join-Path $build 'EvidenceMirror.exe'
New-Item -ItemType Directory -Force -Path $ResultsDir,(Join-Path $ResultsDir 'artifacts') | Out-Null
$invalid=''
$all=@()
$runtime=@{os_description=(Get-CimInstance Win32_OperatingSystem).Caption;os_version=[Environment]::OSVersion.Version.ToString();os_architecture='X64';process_architecture='X64';framework_description=('.NET Framework CLR '+[Environment]::Version);locale=(Get-Culture).Name;ui_locale=(Get-UICulture).Name;time_zone=(Get-TimeZone).Id}
try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $task 'environment\provision.ps1') -WorkspaceRoot $workspace *> (Join-Path $ResultsDir 'artifacts\provision.log')
    if ($LASTEXITCODE) {throw 'Fixture provisioning failed'}
    & (Join-Path $task 'environment\validate_environment.ps1') -WorkspaceRoot $workspace
    if (Test-Path -LiteralPath $build) {throw 'Verifier build directory is not fresh'}
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot 'tools\build.ps1') -Root $RepoRoot -OutputDirectory $build *> (Join-Path $ResultsDir 'artifacts\build.log')
    if ($LASTEXITCODE -or -not (Test-Path -LiteralPath $env:EVIDENCE_MIRROR_EXE)) {throw 'Candidate compilation failed; required cases were not executed'}
    . (Join-Path $PSScriptRoot 'test_fail_to_pass.ps1')
    . (Join-Path $PSScriptRoot 'test_pass_to_pass.ps1')
    . (Join-Path $PSScriptRoot 'test_additional.ps1')
    . (Join-Path $PSScriptRoot 'test_batch.ps1')
    NG-RequireFieldShape
    $script:NG_SourceBefore=NG-InputSnapshot
    $manifest=Get-Content (Join-Path $PSScriptRoot 'rubric.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($expected in $manifest.required_tests) {
        $status='PASS'
        $detail='Observable contract satisfied'
        try {
            if (-not (Get-Command $expected.id -CommandType Function -ErrorAction SilentlyContinue)) {throw '[INVALID] Required function missing'}
            & $expected.id | Out-Null
        } catch {
            $detail=$_.Exception.Message
            if ($detail.StartsWith('[INVALID]') -or $_.CategoryInfo.Category -ne 'OperationStopped') {$status='ERROR'} else {$status='FAIL'}
        }
        $all+=@{id=$expected.id;suite=$expected.suite;status=$status;passed=($status -eq 'PASS');detail=$detail}
        Write-Host ($expected.id+' '+$status+' '+$detail)
        [GC]::Collect()
        [GC]::WaitForPendingFinalizers()
    }
} catch {
    $invalid=$_.Exception.Message+' '+$_.ScriptStackTrace
    Write-Host ('INVALID '+$invalid)
} finally {
    try {& (Join-Path $task 'environment\cleanup.ps1') -FixtureRoot $state -RunId $RunId -ReportPath (Join-Path $ResultsDir 'cleanup_report.json')}
    catch {$invalid+=' Cleanup: '+$_.Exception.Message}
}
foreach ($suite in @('fail_to_pass','pass_to_pass','system_state')) {
    @{task_id='windows-d6-0007';task_version='3.0.2';run_id=$RunId;environment=$runtime;checks=@($all | Where-Object {$_.suite -eq $suite})} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ResultsDir ('suite_'+$suite+'.json')) -Encoding UTF8
}
& (Join-Path $PSScriptRoot 'aggregate_results.ps1') -ResultsDir $ResultsDir -RunId $RunId -InvalidReason $invalid
exit $LASTEXITCODE
