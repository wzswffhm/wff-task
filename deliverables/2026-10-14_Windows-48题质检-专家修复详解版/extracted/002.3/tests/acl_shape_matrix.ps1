$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class AclShapeNative {
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, ExactSpelling=true)]
    private static extern uint GetNamedSecurityInfoW(string name, int kind, uint information, out IntPtr owner, out IntPtr group, out IntPtr dacl, out IntPtr sacl, out IntPtr descriptor);
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode, ExactSpelling=true)]
    private static extern uint SetNamedSecurityInfoW(string name, int kind, uint information, IntPtr owner, IntPtr group, byte[] dacl, IntPtr sacl);
    [DllImport("advapi32.dll", ExactSpelling=true)]
    private static extern uint GetSecurityDescriptorLength(IntPtr descriptor);
    [DllImport("kernel32.dll", ExactSpelling=true)]
    private static extern IntPtr LocalFree(IntPtr memory);
    public static byte[] Read(string path) {
        IntPtr owner, group, dacl, sacl, descriptor;
        uint error = GetNamedSecurityInfoW(path, 1, 7, out owner, out group, out dacl, out sacl, out descriptor);
        if (error != 0) throw new Win32Exception((int)error);
        try {
            byte[] bytes = new byte[GetSecurityDescriptorLength(descriptor)];
            Marshal.Copy(descriptor, bytes, 0, bytes.Length);
            return bytes;
        } finally { LocalFree(descriptor); }
    }
    public static void Write(string path, byte[] dacl) {
        uint error = SetNamedSecurityInfoW(path, 1, 4, IntPtr.Zero, IntPtr.Zero, dacl, IntPtr.Zero);
        if (error != 0) throw new Win32Exception((int)error);
    }
}
'@

function Read-ShapeDescriptor([string]$Path) {
    [Security.AccessControl.RawSecurityDescriptor]::new([AclShapeNative]::Read($Path), 0)
}
function Write-ShapeDacl([string]$Path, [Security.AccessControl.RawAcl]$Acl) {
    $bytes = New-Object byte[] $Acl.BinaryLength
    $Acl.GetBinaryForm($bytes, 0)
    [AclShapeNative]::Write($Path, $bytes)
}
function New-ShapeAce([string]$Sid, [int]$Mask, [int]$Flags) {
    [Security.AccessControl.CommonAce]::new([Security.AccessControl.AceFlags]$Flags, [Security.AccessControl.AceQualifier]::AccessAllowed, $Mask, [Security.Principal.SecurityIdentifier]::new($Sid), $false, $null)
}
function Test-ShapeManaged($Ace) {
    $Ace -is [Security.AccessControl.CommonAce] -and $Ace.AceType -eq [Security.AccessControl.AceType]::AccessAllowed -and
    $Ace.SecurityIdentifier.Value -eq 'S-1-5-32-545' -and (($Ace.AccessMask -band (-bnot 0x100000)) -eq 0x301bf)
}
function Get-ShapeExplicitManaged($Descriptor) {
    @($Descriptor.DiscretionaryAcl | Where-Object { (Test-ShapeManaged $_) -and (($_.AceFlags.value__ -band 16) -eq 0) })
}
function Get-ShapeForeign([string]$Path) {
    $descriptor = Read-ShapeDescriptor $Path
    @($descriptor.DiscretionaryAcl | Where-Object { ($_.AceFlags.value__ -band 16) -eq 0 -and -not (Test-ShapeManaged $_) } | ForEach-Object {
        $bytes = New-Object byte[] $_.BinaryLength
        $_.GetBinaryForm($bytes, 0)
        [Convert]::ToBase64String($bytes)
    } | Sort-Object) -join '|'
}
function Test-ShapeInherited([string]$Path) {
    $descriptor = Read-ShapeDescriptor $Path
    @($descriptor.DiscretionaryAcl | Where-Object { (Test-ShapeManaged $_) -and (($_.AceFlags.value__ -band 16) -ne 0) -and (($_.AceFlags.value__ -band 8) -eq 0) }).Count -gt 0
}
function Invoke-AclShapeMatrix([string]$Workspace, [string]$FixtureRoot, [string]$ResultsDir) {
    $rows = @()
    $scenarios = @(
        @{name='mixed_stale_flags'; flags=@(0, 11, 5)},
        @{name='canonical_and_stale'; flags=@(3, 0)},
        @{name='container_only'; flags=@(2)},
        @{name='object_only'; flags=@(1)},
        @{name='no_propagate'; flags=@(7)}
    )
    foreach ($scenario in $scenarios) {
        $root = Join-Path $FixtureRoot ('shape-' + $scenario.name)
        New-Item -ItemType Directory -Path $root | Out-Null
        $security = Get-Acl -LiteralPath $root
        $security.SetAccessRuleProtection($true, $false)
        $security.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-11'), 'FullControl', 'ContainerInherit, ObjectInherit', 'None', 'Allow'))
        Set-Acl -LiteralPath $root -AclObject $security
        $descriptor = Read-ShapeDescriptor $root
        foreach ($flags in $scenario.flags) { $descriptor.DiscretionaryAcl.InsertAce($descriptor.DiscretionaryAcl.Count, (New-ShapeAce 'S-1-5-32-545' 0x1301bf $flags)) }
        $descriptor.DiscretionaryAcl.InsertAce($descriptor.DiscretionaryAcl.Count, (New-ShapeAce 'S-1-5-32-545' 0x1200a9 0))
        $descriptor.DiscretionaryAcl.InsertAce($descriptor.DiscretionaryAcl.Count, (New-ShapeAce 'S-1-3-0' 0x1f01ff 11))
        Write-ShapeDacl $root $descriptor.DiscretionaryAcl
        $before = Read-ShapeDescriptor $root
        $seed = @(Get-ShapeExplicitManaged $before)
        @{scenario=$scenario.name; expected_flags=$scenario.flags; observed_flags=@($seed | ForEach-Object { $_.AceFlags.value__ }); sddl=$before.GetSddlForm('All')} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $ResultsDir ('shape-fixture-' + $scenario.name + '.json')) -Encoding UTF8
        if ($seed.Count -ne $scenario.flags.Count -or (@($seed | ForEach-Object { $_.AceFlags.value__ }) -join ',') -ne ($scenario.flags -join ',')) { throw ('Raw ACL shape fixture did not persist: ' + $scenario.name) }
        $oldDirectory = Join-Path $root '旧部署目录'
        New-Item -ItemType Directory -Path $oldDirectory | Out-Null
        $oldDescriptor = Read-ShapeDescriptor $oldDirectory
        $oldDescriptor.DiscretionaryAcl.InsertAce(0, (New-ShapeAce 'S-1-5-32-545' 0x1301bf 11))
        Write-ShapeDacl $oldDirectory $oldDescriptor.DiscretionaryAcl
        if (@(Get-ShapeExplicitManaged (Read-ShapeDescriptor $oldDirectory)).Count -ne 1) { throw 'Managed descendant fixture did not persist.' }
        $oldFile = Join-Path $oldDirectory '旧文件.txt'
        [IO.File]::WriteAllText($oldFile, 'legacy-content')
        $rootForeign = Get-ShapeForeign $root
        $directoryForeign = Get-ShapeForeign $oldDirectory
        $owner = $before.Owner.Value
        $first = Invoke-PathAclTool -Workspace $Workspace -Argument $root
        $after = Read-ShapeDescriptor $root
        $managed = @(Get-ShapeExplicitManaged $after)
        $rootOk = $first.code -eq 0 -and $managed.Count -eq 1 -and $managed[0].AceFlags.value__ -eq 3 -and $rootForeign -ceq (Get-ShapeForeign $root) -and $owner -eq $after.Owner.Value
        $existingOk = $first.code -eq 0 -and @(Get-ShapeExplicitManaged (Read-ShapeDescriptor $oldDirectory)).Count -eq 0 -and (Test-ShapeInherited $oldDirectory) -and (Test-ShapeInherited $oldFile) -and $directoryForeign -ceq (Get-ShapeForeign $oldDirectory) -and [IO.File]::ReadAllText($oldFile) -ceq 'legacy-content'
        $newDirectory = Join-Path $oldDirectory '新一级\新二级\新三级'
        New-Item -ItemType Directory -Path $newDirectory -Force | Out-Null
        $newFile = Join-Path $newDirectory '新文件.txt'
        [IO.File]::WriteAllText($newFile, 'new-content')
        $futureOk = $first.code -eq 0 -and (Test-ShapeInherited $newDirectory) -and (Test-ShapeInherited $newFile)
        $paths = @($root, $oldDirectory, $oldFile, $newDirectory, $newFile)
        $snapshots = @{}
        foreach ($path in $paths) { $snapshots[$path] = Get-DescriptorSignature $path }
        $second = Invoke-PathAclTool -Workspace $Workspace -Argument $root
        $stable = $first.code -eq 0 -and $second.code -eq 0
        foreach ($path in $paths) { if ($snapshots[$path] -cne (Get-DescriptorSignature $path)) { $stable = $false } }
        $rows += @{scenario=$scenario.name; seed_flags=$scenario.flags; root_ok=[bool]$rootOk; existing_ok=[bool]$existingOk; future_ok=[bool]$futureOk; stable=[bool]$stable; root_before=$before.GetSddlForm('All'); root_after=$after.GetSddlForm('All'); first_exit=$first.code; second_exit=$second.code}
    }
    @{scenarios=$rows} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ResultsDir 'acl-shape-observations.json') -Encoding UTF8
    return @{root_ok=(@($rows | Where-Object { -not $_.root_ok }).Count -eq 0); existing_ok=(@($rows | Where-Object { -not $_.existing_ok }).Count -eq 0); future_ok=(@($rows | Where-Object { -not $_.future_ok }).Count -eq 0); stable=(@($rows | Where-Object { -not $_.stable }).Count -eq 0)}
}
