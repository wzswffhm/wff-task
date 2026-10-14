param([Parameter(Mandatory=$true)][string]$WorkspaceRoot)
$ErrorActionPreference='Stop'
$workspace=[IO.Path]::GetFullPath($WorkspaceRoot).TrimEnd('\')
$state=Join-Path $workspace 'state'
& (Join-Path $PSScriptRoot 'cleanup.ps1') -FixtureRoot $state
$cases=Join-Path $state 'cases'
$calibration=Join-Path $state 'calibration'
New-Item -ItemType Directory -Force -Path $calibration,(Join-Path $state 'staging') | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'calibration\expected.json') $calibration
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'make_case_data.ps1') -CasesRoot $cases -CalibrationRoot $calibration
if ($LASTEXITCODE) {throw 'Input data creation failed'}
$field=Join-Path $cases 'CASE-2231'
$recording=Join-Path $field 'MEDIA\field-recording-0001.bin'
$info=New-Object IO.FileInfo($recording)
$created=$info.CreationTimeUtc
$written=$info.LastWriteTimeUtc
& fsutil.exe sparse setflag $recording | Out-Null
if ($LASTEXITCODE) {throw 'Sparse provisioning failed'}
$stream=[IO.File]::Open($recording,'Open','Write','ReadWrite')
try {$stream.SetLength(2200000000)} finally {$stream.Dispose()}
[IO.File]::SetCreationTimeUtc($recording,$created)
[IO.File]::SetLastWriteTimeUtc($recording,$written)
& fsutil.exe hardlink create (Join-Path $field 'names\intake-manifest.bin') (Join-Path $field 'intake\intake-manifest.bin') | Out-Null
if ($LASTEXITCODE) {throw 'Hardlink provisioning failed'}
$compressed=Join-Path $field 'bulk\transcode-cache.bin'
$info=New-Object IO.FileInfo($compressed)
$created=$info.CreationTimeUtc
$written=$info.LastWriteTimeUtc
& compact.exe /c $compressed | Out-Null
if ($LASTEXITCODE) {throw 'Compression provisioning failed'}
[IO.File]::SetCreationTimeUtc($compressed,$created)
[IO.File]::SetLastWriteTimeUtc($compressed,$written)
$local=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'apply_case_security.ps1') -CasesRoot $cases -LocalSid $local
if ($LASTEXITCODE) {throw 'Security fixture provisioning failed'}
$rows=@()
foreach ($root in @($cases,(Join-Path $calibration 'cases'))) {
    foreach ($file in [IO.Directory]::GetFiles(('\\?\'+$root),'*','AllDirectories')) {
        $info=New-Object IO.FileInfo($file)
        $security=[IO.File]::GetAccessControl($file,[Security.AccessControl.AccessControlSections]::All)
        $streams=@(Get-Item -LiteralPath $file -Stream * | ForEach-Object {@{name=$_.Stream;length=$_.Length}})
        $rows+=@{path=$file.Substring(('\\?\'+$state).Length+1);length=$info.Length;attributes=[string]$info.Attributes;streams=$streams;security_sddl=$security.GetSecurityDescriptorSddlForm([Security.AccessControl.AccessControlSections]::All);creation_utc=$info.CreationTimeUtc.ToString('o');last_write_utc=$info.LastWriteTimeUtc.ToString('o')}
    }
}
@{task_id='windows-d6-0007';files=$rows} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $state 'input_manifest.json') -Encoding UTF8
Write-Host 'Per-run NTFS inputs provisioned'
