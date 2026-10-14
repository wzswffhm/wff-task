# NTFS sparse-file probe #2 (ASCII only).
# Confirms the exact judging primitives we would rely on in an evaluator:
#   - correct fsutil syntax for allocated ranges and volume info
#   - multi-range reporting after writing into the middle of a sparse file
#   - FSCTL_SET_ZERO_DATA deallocating previously allocated clusters
#   - shrink behaviour (does truncating down free clusters?)
#   - FSCTL_SET_SPARSE against a directory handle
$ErrorActionPreference = 'Continue'

$src = @'
using System;
using System.Text;
using System.IO;
using System.Runtime.InteropServices;

public static class SP2 {
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern IntPtr CreateFileW(string n, uint acc, uint share, IntPtr sa, uint disp, uint flags, IntPtr tpl);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool DeviceIoControl(IntPtr h, uint code, IntPtr inb, uint insz, IntPtr outb, uint outsz, out uint ret, IntPtr ov);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool SetEndOfFile(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool SetFilePointerEx(IntPtr h, long dist, out long np, uint method);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern uint GetCompressedFileSizeW(string n, out uint high);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool GetFileSizeEx(IntPtr h, out long sz);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool WriteFile(IntPtr h, byte[] b, uint n, out uint written, IntPtr ov);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool CloseHandle(IntPtr h);

    const uint GENERIC_WRITE = 0x40000000;
    const uint GENERIC_READ  = 0x80000000;
    const uint SHARE_ALL     = 0x0007;
    const uint CREATE_ALWAYS = 2;
    const uint OPEN_EXISTING = 3;
    const uint BACKUP_SEMANTICS = 0x02000000;
    const uint FSCTL_SET_SPARSE             = 0x000900C4;
    const uint FSCTL_QUERY_ALLOCATED_RANGES = 0x000940CF;
    const uint FSCTL_SET_ZERO_DATA          = 0x000980C8;
    const uint FILE_BEGIN = 0;

    static IntPtr Open(string p, uint disp, uint flags) {
        return CreateFileW(p, GENERIC_READ | GENERIC_WRITE, SHARE_ALL, IntPtr.Zero, disp, flags, IntPtr.Zero);
    }

    static string SetSparse(IntPtr h, bool on) {
        IntPtr inb = Marshal.AllocHGlobal(1);
        Marshal.WriteByte(inb, 0, (byte)(on ? 1 : 0));
        uint ret = 0;
        bool ok = DeviceIoControl(h, FSCTL_SET_SPARSE, inb, 1, IntPtr.Zero, 0, out ret, IntPtr.Zero);
        int e = Marshal.GetLastWin32Error();
        Marshal.FreeHGlobal(inb);
        return "ok=" + ok + " err=" + e;
    }

    static string ZeroData(IntPtr h, long off, long beyond) {
        IntPtr inb = Marshal.AllocHGlobal(16);
        Marshal.WriteInt64(inb, 0, off);
        Marshal.WriteInt64(inb, 8, beyond);
        uint ret = 0;
        bool ok = DeviceIoControl(h, FSCTL_SET_ZERO_DATA, inb, 16, IntPtr.Zero, 0, out ret, IntPtr.Zero);
        int e = Marshal.GetLastWin32Error();
        Marshal.FreeHGlobal(inb);
        return "ok=" + ok + " err=" + e;
    }

    static string AllocRanges(IntPtr h, long off, long len) {
        IntPtr inb = Marshal.AllocHGlobal(16);
        Marshal.WriteInt64(inb, 0, off);
        Marshal.WriteInt64(inb, 8, len);
        IntPtr outb = Marshal.AllocHGlobal(16 * 64);
        uint ret = 0;
        bool ok = DeviceIoControl(h, FSCTL_QUERY_ALLOCATED_RANGES, inb, 16, outb, 16 * 64, out ret, IntPtr.Zero);
        int e = Marshal.GetLastWin32Error();
        StringBuilder sb = new StringBuilder();
        sb.Append("ok=").Append(ok).Append(" err=").Append(e).Append(" ret=").Append(ret);
        if (ok) {
            int n = (int)(ret / 16);
            if (n == 0) sb.Append(" <none>");
            for (int i = 0; i < n; i++) {
                sb.Append(" [").Append(Marshal.ReadInt64(outb, i * 16)).Append("+").Append(Marshal.ReadInt64(outb, i * 16 + 8)).Append("]");
            }
        }
        Marshal.FreeHGlobal(inb);
        Marshal.FreeHGlobal(outb);
        return sb.ToString();
    }

    static string Sizes(string p, IntPtr h) {
        long logical = 0;
        GetFileSizeEx(h, out logical);
        uint high = 0;
        uint low = GetCompressedFileSizeW(p, out high);
        long phys = ((long)high << 32) | (uint)low;
        return "logical=" + logical + " physical=" + phys;
    }

    static void Truncate(IntPtr h, long size) {
        long np = 0;
        SetFilePointerEx(h, size, out np, FILE_BEGIN);
        SetEndOfFile(h);
    }

    static void Poke(IntPtr h, long off, int len) {
        long np = 0;
        SetFilePointerEx(h, off, out np, FILE_BEGIN);
        byte[] b = new byte[len];
        for (int i = 0; i < len; i++) b[i] = 0x5A;
        uint w = 0;
        WriteFile(h, b, (uint)len, out w, IntPtr.Zero);
    }

    public static string Run() {
        StringBuilder o = new StringBuilder();
        string dir = @"C:\sparseprobe2";
        if (Directory.Exists(dir)) Directory.Delete(dir, true);
        Directory.CreateDirectory(dir);

        o.AppendLine("##### 1. multi-range after writing into the middle #####");
        string p = dir + @"\multi.bin";
        IntPtr h = Open(p, CREATE_ALWAYS, 0);
        o.AppendLine("create=" + (h.ToInt64() != -1 ? "ok" : "FAIL err=" + Marshal.GetLastWin32Error()));
        o.AppendLine("setsparse: " + SetSparse(h, true));
        Truncate(h, 134217728L);
        o.AppendLine("empty sparse file: " + Sizes(p, h) + " ranges: " + AllocRanges(h, 0, 134217728L));
        Poke(h, 33554432L, 8192);
        o.AppendLine("after writing 8192 bytes at 32MB: " + Sizes(p, h) + " ranges: " + AllocRanges(h, 0, 134217728L));
        Poke(h, 100663296L, 4096);
        o.AppendLine("after writing 4096 bytes at 96MB: " + Sizes(p, h) + " ranges: " + AllocRanges(h, 0, 134217728L));

        o.AppendLine();
        o.AppendLine("##### 2. FSCTL_SET_ZERO_DATA deallocation #####");
        o.AppendLine("zero [32MB, 32MB+8192): " + ZeroData(h, 33554432L, 33554432L + 8192L));
        o.AppendLine("after zero: " + Sizes(p, h) + " ranges: " + AllocRanges(h, 0, 134217728L));
        o.AppendLine("zero [0, 65536): " + ZeroData(h, 0, 65536));
        o.AppendLine("after zero head: " + Sizes(p, h) + " ranges: " + AllocRanges(h, 0, 134217728L));

        o.AppendLine();
        o.AppendLine("##### 3. shrink #####");
        Truncate(h, 16777216L);
        o.AppendLine("after truncate to 16MB: " + Sizes(p, h) + " ranges: " + AllocRanges(h, 0, 16777216L));
        Truncate(h, 0L);
        o.AppendLine("after truncate to 0: " + Sizes(p, h) + " ranges: " + AllocRanges(h, 0, 16777216L));
        Truncate(h, 67108864L);
        o.AppendLine("after re-extend to 64MB: " + Sizes(p, h) + " ranges: " + AllocRanges(h, 0, 67108864L));
        CloseHandle(h);

        o.AppendLine();
        o.AppendLine("##### 4. FSCTL_SET_SPARSE against a DIRECTORY handle #####");
        IntPtr hd = Open(dir, OPEN_EXISTING, BACKUP_SEMANTICS);
        o.AppendLine("dir handle=" + (hd.ToInt64() != -1 ? "ok" : "FAIL err=" + Marshal.GetLastWin32Error()));
        if (hd.ToInt64() != -1) {
            o.AppendLine("setsparse(dir): " + SetSparse(hd, true));
            CloseHandle(hd);
        }

        o.AppendLine();
        o.AppendLine("##### 5. non-sparse file: does a query still work? #####");
        string p3 = dir + @"\dense.bin";
        IntPtr h3 = Open(p3, CREATE_ALWAYS, 0);
        Poke(h3, 4096L, 4096);
        o.AppendLine("dense file: " + Sizes(p3, h3) + " ranges 0..4096: " + AllocRanges(h3, 0, 4096));
        o.AppendLine("ranges 4096..8192 (past EOF): " + AllocRanges(h3, 4096, 4096));
        CloseHandle(h3);

        o.AppendLine();
        o.AppendLine("PROBE_SPARSE2_DONE");
        return o.ToString();
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp -ErrorAction Stop
Write-Output ([SP2]::Run())

Write-Output ""
Write-Output "##### fsutil: correct syntax #####"
Write-Output "--- sparse queryflag ---"
& fsutil sparse queryflag C:\sparseprobe2\multi.bin 2>&1 | Write-Output
& fsutil sparse queryflag C:\sparseprobe2\dense.bin 2>&1 | Write-Output
Write-Output "--- file queryAllocRanges (no args) ---"
& fsutil file queryAllocRanges C:\sparseprobe2\multi.bin 2>&1 | Write-Output
Write-Output "--- file queryValidData ---"
& fsutil file queryValidData C:\sparseprobe2\multi.bin 2>&1 | Write-Output
Write-Output "--- fsinfo volumeinfo C: ---"
& fsutil fsinfo volumeinfo C: 2>&1 | Write-Output
Write-Output "--- fsinfo drivetype C: ---"
& fsutil fsinfo drivetype C: 2>&1 | Write-Output
