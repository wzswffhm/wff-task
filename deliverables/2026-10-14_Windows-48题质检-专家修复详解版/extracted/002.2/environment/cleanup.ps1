param([Parameter(Mandatory=$true)][string]$FixtureRoot,[string]$RunId,[string]$ReportPath)
$ErrorActionPreference='Stop'
$target=[IO.Path]::GetFullPath($FixtureRoot).TrimEnd('\')
$prefixes=@('D:\bench-runs\windows-d6-0007\','C:\task-state\windows-d6-0007\')
if (-not @($prefixes | Where-Object {$target.StartsWith($_,[StringComparison]::OrdinalIgnoreCase)}).Count -or [IO.Path]::GetFileName($target) -ne 'state') {throw 'Unsafe task cleanup boundary'}
$actualRun=[IO.Path]::GetFileName([IO.Path]::GetDirectoryName($target))
if ($actualRun -notmatch '^[a-zA-Z0-9_-]+$') {throw 'Unsafe run identifier'}
function Remove-MirrorEntry([string]$entry) {
    $attributes=[IO.File]::GetAttributes($entry)
    $directory=($attributes -band [IO.FileAttributes]::Directory) -ne 0
    if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        if ($directory) {[IO.Directory]::Delete($entry,$false)} else {[IO.File]::Delete($entry)}
    } elseif ($directory) {
        foreach ($child in [IO.Directory]::GetFileSystemEntries($entry)) {Remove-MirrorEntry $child}
        [IO.Directory]::Delete($entry,$false)
    } else {
        [IO.File]::SetAttributes($entry,[IO.FileAttributes]::Normal)
        [IO.File]::Delete($entry)
    }
}
$extended='\\?\'+$target
if ([IO.Directory]::Exists($extended)) {
    if (([IO.File]::GetAttributes($extended) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {throw 'State root is a link'}
    Remove-MirrorEntry $extended
}
function Repair-OwnedRegistryAcl($Root,[string]$Path) {
    $rights=[Security.AccessControl.RegistryRights]::ChangePermissions -bor [Security.AccessControl.RegistryRights]::ReadPermissions
    $key=$Root.OpenSubKey($Path,[Microsoft.Win32.RegistryKeyPermissionCheck]::ReadWriteSubTree,$rights)
    if (-not $key) {return}
    try {
        $security=New-Object Security.AccessControl.RegistrySecurity
        $security.SetAccessRuleProtection($true,$false)
        $rule=New-Object Security.AccessControl.RegistryAccessRule([Security.Principal.WindowsIdentity]::GetCurrent().User,[Security.AccessControl.RegistryRights]::FullControl,[Security.AccessControl.InheritanceFlags]::ContainerInherit,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
        $security.AddAccessRule($rule)
        $key.SetAccessControl($security)
    } finally {$key.Dispose()}
    $key=$Root.OpenSubKey($Path)
    try {$children=$key.GetSubKeyNames()} finally {$key.Dispose()}
    foreach ($child in $children) {Repair-OwnedRegistryAcl $Root ($Path+'\'+$child)}
}
$registry='SOFTWARE\Northgate\EvidenceMirrorBench\windows-d6-0007\'+$actualRun
$residue=[int][IO.Directory]::Exists($extended)
foreach ($view in @('Registry64','Registry32')) {
    $key=[Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine',$view)
    try {
        Repair-OwnedRegistryAcl $key $registry
        $key.DeleteSubKeyTree($registry,$false)
        $probe=$key.OpenSubKey($registry)
        if ($probe) {$residue++;$probe.Dispose()}
    } finally {$key.Dispose()}
}
if ($ReportPath) {
    @{task_id='windows-d6-0007';task_version='3.0.2';run_id=$RunId;fixture_root=$target;registry_root=$registry;residue_count=$residue} | ConvertTo-Json | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}
if ($residue) {throw 'Cleanup left task state'}
