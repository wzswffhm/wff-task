# Counterfactual probe (ASCII only): is there a non-NTFS volume inside the
# container on which FSCTL_SET_SPARSE must fail? Builds a ReFS VHD via diskpart
# and, if that succeeds, repeats the sparse ioctl against the new volume.
$ErrorActionPreference = 'Continue'

$dp = @"
create vdisk file=C:\refs.vhd maximum=512 type=expandable
select vdisk file=C:\refs.vhd
attach vdisk
create partition primary
format fs=refs quick label=REFSTEST
assign letter=R
"@
Set-Content -Path C:\dp.txt -Value $dp -Encoding ascii

Write-Output "##### diskpart #####"
& diskpart /s C:\dp.txt 2>&1 | Write-Output
Write-Output "diskpart exit=$LASTEXITCODE"

Write-Output ""
Write-Output "##### volumes #####"
& fsutil fsinfo drives 2>&1 | Write-Output
& fsutil fsinfo volumeinfo R: 2>&1 | Write-Output
& fsutil fsinfo drivetype R: 2>&1 | Write-Output

Write-Output ""
Write-Output "##### sparse ioctl against R: #####"
$src = @'
using System;
using System.Text;
using System.IO;
using System.Runtime.InteropServices;

public static class SP3 {
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern IntPtr CreateFileW(string n, uint acc, uint share, IntPtr sa, uint disp, uint flags, IntPtr tpl);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool DeviceIoControl(IntPtr h, uint code, IntPtr inb, uint insz, IntPtr outb, uint outsz, out uint ret, IntPtr ov);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool SetEndOfFile(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool SetFilePointerEx(IntPtr h, long dist, out long np, uint method);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool CloseHandle(IntPtr h);
    const uint GENERIC_RW = 0xC0000000;
    const uint SHARE_ALL = 0x0007;
    const uint CREATE_ALWAYS = 2;
    const uint FSCTL_SET_SPARSE = 0x000900C4;
    const uint FSCTL_QUERY_ALLOCATED_RANGES = 0x000940CF;

    public static string Run(string dir) {
        StringBuilder o = new StringBuilder();
        Directory.CreateDirectory(dir);
        string p = dir + @"\t.bin";
        IntPtr h = CreateFileW(p, GENERIC_RW, SHARE_ALL, IntPtr.Zero, CREATE_ALWAYS, 0, IntPtr.Zero);
        if (h.ToInt64() == -1) return "create FAIL err=" + Marshal.GetLastWin32Error();
        IntPtr inb = Marshal.AllocHGlobal(1);
        Marshal.WriteByte(inb, 0, 1);
        uint ret = 0;
        bool ok = DeviceIoControl(h, FSCTL_SET_SPARSE, inb, 1, IntPtr.Zero, 0, out ret, IntPtr.Zero);
        o.AppendLine("FSCTL_SET_SPARSE on " + dir + ": ok=" + ok + " err=" + Marshal.GetLastWin32Error());
        Marshal.FreeHGlobal(inb);
        long np = 0;
        SetFilePointerEx(h, 67108864L, out np, 0);
        SetEndOfFile(h);
        IntPtr ib2 = Marshal.AllocHGlobal(16);
        Marshal.WriteInt64(ib2, 0, 0);
        Marshal.WriteInt64(ib2, 8, 67108864L);
        IntPtr ob2 = Marshal.AllocHGlobal(256);
        uint r2 = 0;
        bool ok2 = DeviceIoControl(h, FSCTL_QUERY_ALLOCATED_RANGES, ib2, 16, ob2, 256, out r2, IntPtr.Zero);
        o.AppendLine("FSCTL_QUERY_ALLOCATED_RANGES: ok=" + ok2 + " err=" + Marshal.GetLastWin32Error() + " ret=" + r2);
        Marshal.FreeHGlobal(ib2);
        Marshal.FreeHGlobal(ob2);
        CloseHandle(h);
        return o.ToString();
    }
}
'@
Add-Type -TypeDefinition $src -Language CSharp -ErrorAction Stop
Write-Output ([SP3]::Run("R:\sptest"))
Write-Output ([SP3]::Run("C:\sptest_ntfs"))

Write-Output ""
Write-Output "PROBE_REFS_DONE"
