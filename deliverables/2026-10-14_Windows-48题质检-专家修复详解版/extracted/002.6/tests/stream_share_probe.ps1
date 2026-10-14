# Public filesystem sharing probe for the rollback-report testcase. It never hooks a candidate
# function and never inspects candidate source: it just holds a real NTFS stream handle with a
# caller-chosen share mode, exactly like atomic_commit_probe.ps1 does for the deletion case.
function Lock-AdsStreamHandle {
    param(
        [Parameter(Mandatory = $true)][string]$StreamPath,
        [Parameter(Mandatory = $true)][int]$ShareMode
    )

    if ($null -eq ('OutsideAdsStreamShare' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class OutsideAdsStreamShare {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(string name, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
    public static SafeFileHandle Lock(string path, uint share) {
        // GENERIC_READ with a caller-supplied share mode: sharing mode 3 allows reads and writes
        // but not deletion, sharing mode 5 allows reads and deletion but not writing back.
        SafeFileHandle handle = CreateFile(path, 0x80000000u, share, IntPtr.Zero, 3, 0, IntPtr.Zero);
        if (handle.IsInvalid) {
            int code = Marshal.GetLastWin32Error();
            handle.Dispose();
            throw new Win32Exception(code);
        }
        return handle;
    }
}
'@
    }

    return [OutsideAdsStreamShare]::Lock($StreamPath, [uint32]$ShareMode)
}
