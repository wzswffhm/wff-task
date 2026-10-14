<#
.SYNOPSIS
  镜像构建期专用：把采集端交来的现场文件按【交到本机时的既有安全属性】落地。
.DESCRIPTION
  现场案卷夹 CASE-2231 里有两类文件是保管链上另一个账户交过来的，交来时它们带着
  自己的所有者与自己的访问控制列表（不是从父目录继承来的）；另有三个文件交来时带着
  采集端登记的审计规则（SACL）。本脚本把这些既有安全属性施加到已落地的文件上，
  使冻结输入数据与现场交来的形状一致。

  实测（2026-09-08）：审计规则可以在构建期施加并【能】穿过镜像层保留下来
  （运行期回读 auditRules 数量一致），这一点与硬链接/NTFS 压缩不同——后两者会在
  hcsshim 导出镜像层时丢失，只能由 prepare.ps1 在运行期落地。

  本脚本只在【构建镜像】时执行一次，执行完立即从镜像里删除：它是环境预置的一部分，
  不是组件行为，留在镜像里会让运行期看到与解题无关的特权操作样例。
.NOTES
  非交互、幂等。退出码：0=成功；1=施加失败（数据缺陷）；2=INVALID。
#>
[CmdletBinding()]
param(
    [string]$CasesRoot = 'C:\cases',
    [string]$CaseId = 'CASE-2231',
    [string]$CustodianSid = 'S-1-5-21-100-200-300-1001',
    [string]$LocalSid = 'S-1-5-93-2-1'
)
$ErrorActionPreference = 'Stop'
function Say([string]$m) { Write-Host "[case-sec] $m" }
function Get-Ext([string]$p) { if ($p.StartsWith('\\?\')) { return $p }; return '\\?\' + $p }

$native = @"
using System;
using System.Runtime.InteropServices;
public static class CaseSecNative {
    [StructLayout(LayoutKind.Sequential)] public struct LUID { public uint LowPart; public int HighPart; }
    [StructLayout(LayoutKind.Sequential)] public struct LUID_AND_ATTRIBUTES { public LUID Luid; public uint Attributes; }
    [StructLayout(LayoutKind.Sequential)] public struct TOKEN_PRIVILEGES { public uint PrivilegeCount; public LUID_AND_ATTRIBUTES Privileges; }
    [DllImport("advapi32.dll", SetLastError = true)] public static extern bool OpenProcessToken(IntPtr h, uint desired, out IntPtr token);
    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)] public static extern bool LookupPrivilegeValue(string system, string name, out LUID luid);
    [DllImport("advapi32.dll", SetLastError = true)] public static extern bool AdjustTokenPrivileges(IntPtr token, bool disableAll, ref TOKEN_PRIVILEGES newState, uint bufferLength, IntPtr previous, IntPtr returnLength);
    [DllImport("kernel32.dll")] public static extern IntPtr GetCurrentProcess();
    public static int Enable(string name) {
        IntPtr token;
        if (!OpenProcessToken(GetCurrentProcess(), 0x28, out token)) { return Marshal.GetLastWin32Error(); }
        LUID luid;
        if (!LookupPrivilegeValue(null, name, out luid)) { return Marshal.GetLastWin32Error(); }
        TOKEN_PRIVILEGES tp = new TOKEN_PRIVILEGES();
        tp.PrivilegeCount = 1;
        tp.Privileges.Luid = luid;
        tp.Privileges.Attributes = 0x2;
        if (!AdjustTokenPrivileges(token, false, ref tp, 0, IntPtr.Zero, IntPtr.Zero)) { return Marshal.GetLastWin32Error(); }
        return Marshal.GetLastWin32Error();
    }
}
"@

try {
    Add-Type -TypeDefinition $native -Language CSharp
    foreach ($priv in @('SeRestorePrivilege', 'SeTakeOwnershipPrivilege', 'SeSecurityPrivilege')) {
        $rc = [CaseSecNative]::Enable($priv)
        if ($rc -ne 0) { Say ('[FAILED] 启用 ' + $priv + ' 失败，Win32 错误码 ' + $rc); exit 1 }
        Say ('已启用 ' + $priv)
    }

    $caseDir = Join-Path $CasesRoot $CaseId
    $targets = @(
        (Join-Path $caseDir 'custody\chain-01.bin'),
        (Join-Path $caseDir 'MEDIA\frame-0001.bin')
    )
    $sddl = 'O:' + $CustodianSid + 'D:P(A;;FA;;;' + $LocalSid + ')(A;;FR;;;' + $CustodianSid + ')'

    foreach ($t in $targets) {
        $ext = Get-Ext $t
        if (-not [System.IO.File]::Exists($ext)) { Say ('[FAILED] 目标文件不存在：' + $t); exit 1 }
        $security = New-Object System.Security.AccessControl.FileSecurity
        $security.SetSecurityDescriptorSddlForm($sddl)
        [System.IO.File]::SetAccessControl($ext, $security)
        $back = [System.IO.File]::GetAccessControl($ext, [System.Security.AccessControl.AccessControlSections]::All)
        $owner = $back.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
        if ($owner -ne $CustodianSid) { Say ('[FAILED] 所有者回读不一致：' + $owner); exit 1 }
        if (-not $back.AreAccessRulesProtected) { Say ('[FAILED] 访问控制列表未变成受保护：' + $t); exit 1 }
        $rules = @($back.GetAccessRules($true, $false, [System.Security.Principal.SecurityIdentifier]))
        Say ('已施加 ' + $t + ' owner=' + $owner + ' protected=' + $back.AreAccessRulesProtected + ' explicitRules=' + $rules.Count)
        if ($rules.Count -ne 2) { Say ('[FAILED] 显式访问控制项应为 2 条，实际 ' + $rules.Count); exit 1 }
    }

    # ---- 审计规则（SACL）：采集端在交来之前登记在这些文件上的既有审计项 ----
    $custodian = New-Object System.Security.Principal.SecurityIdentifier($CustodianSid)
    $local = New-Object System.Security.Principal.SecurityIdentifier($LocalSid)
    $auditPlan = @(
        @{ path = (Join-Path $caseDir 'names\archive.dat');       sid = $custodian; rights = ([System.Security.AccessControl.FileSystemRights]::ReadData); flags = ([System.Security.AccessControl.AuditFlags]::Success) },
        @{ path = (Join-Path $caseDir 'custody\chain-01.bin');    sid = $custodian; rights = ([System.Security.AccessControl.FileSystemRights]::ReadData -bor [System.Security.AccessControl.FileSystemRights]::ReadAttributes); flags = ([System.Security.AccessControl.AuditFlags]::Success) },
        @{ path = (Join-Path $caseDir 'custody\chain-01.bin');    sid = $local;     rights = ([System.Security.AccessControl.FileSystemRights]::WriteData -bor [System.Security.AccessControl.FileSystemRights]::Delete); flags = ([System.Security.AccessControl.AuditFlags]::Success -bor [System.Security.AccessControl.AuditFlags]::Failure) },
        @{ path = (Join-Path $caseDir 'MEDIA\frame-0001.bin');    sid = $local;     rights = ([System.Security.AccessControl.FileSystemRights]::ReadData); flags = ([System.Security.AccessControl.AuditFlags]::Failure) }
    )
    foreach ($group in ($auditPlan | Group-Object { $_.path })) {
        $ext = Get-Ext $group.Name
        if (-not [System.IO.File]::Exists($ext)) { Say ('[FAILED] 审计目标文件不存在：' + $group.Name); exit 1 }
        $fi = New-Object System.IO.FileInfo($ext)
        $sec = $fi.GetAccessControl([System.Security.AccessControl.AccessControlSections]::Audit)
        foreach ($old in @($sec.GetAuditRules($true, $true, [System.Security.Principal.SecurityIdentifier]))) { $sec.RemoveAuditRule($old) | Out-Null }
        foreach ($spec in $group.Group) {
            $sec.AddAuditRule((New-Object System.Security.AccessControl.FileSystemAuditRule($spec.sid, $spec.rights, $spec.flags)))
        }
        $fi.SetAccessControl($sec)
        $back = (New-Object System.IO.FileInfo($ext)).GetAccessControl([System.Security.AccessControl.AccessControlSections]::All)
        $n = @($back.GetAuditRules($true, $true, [System.Security.Principal.SecurityIdentifier])).Count
        $want = @($group.Group).Count
        if ($n -ne $want) { Say ('[FAILED] 审计规则回读条数 ' + $n + ' != ' + $want + '：' + $group.Name); exit 1 }
        if ($back.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $CustodianSid -and $group.Name -like '*chain-01.bin*') { Say ('[FAILED] 施加审计规则后所有者被改动：' + $group.Name); exit 1 }
        Say ('已施加审计规则 ' + $group.Name + ' rules=' + $n)
    }

    Say 'OK'
    exit 0
}
catch {
    Say ('[INVALID] ' + $_.Exception.Message)
    exit 2
}
