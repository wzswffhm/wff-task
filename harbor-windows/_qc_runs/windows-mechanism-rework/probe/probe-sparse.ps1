# NTFS sparse-file probe (ASCII only).
# Goal: confirm that FSCTL_SET_SPARSE / FSCTL_QUERY_ALLOCATED_RANGES /
# GetCompressedFileSizeW all work inside the Server Core container, and measure
# how allocation behaves with and without the sparse flag. All APIs used here are
# synchronous DeviceIoControl calls, so this family does not depend on the
# overlapped-IO path that was shown to be unusable in this environment.
$ErrorActionPreference = 'Continue'

$src = @'
using System;
using System.Text;
using System.IO;
using System.Runtime.InteropServices;

public static class SP {
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
    const uint FSCTL_SET_SPARSE            = 0x000900C4;
    const uint FSCTL_QUERY_ALLOCATED_RANGES = 0x000940CF;
    const uint FSCTL_GET_COMPRESSION        = 0x0009003C;
    const uint FILE_BEGIN = 0;

    static IntPtr Open(string p, uint disp) {
        return CreateFileW(p, GENERIC_READ | GENERIC_WRITE, SHARE_ALL, IntPtr.Zero, disp, 0, IntPtr.Zero);
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
            for (int i = 0; i < n; i++) {
                long o = Marshal.ReadInt64(outb, i * 16);
                long l = Marshal.ReadInt64(outb, i * 16 + 8);
                sb.Append(" [").Append(o).Append("+").Append(l).Append("]");
            }
            if (n == 0) sb.Append(" <no allocated ranges>");
        }
        Marshal.FreeHGlobal(inb);
        Marshal.FreeHGlobal(outb);
        return sb.ToString();
    }

    static string Compression(IntPtr h) {
        IntPtr outb = Marshal.AllocHGlobal(2);
        uint ret = 0;
        bool ok = DeviceIoControl(h, FSCTL_GET_COMPRESSION, IntPtr.Zero, 0, outb, 2, out ret, IntPtr.Zero);
        int e = Marshal.GetLastWin32Error();
        ushort v = ok ? (ushort)Marshal.ReadInt16(outb, 0) : (ushort)0;
        Marshal.FreeHGlobal(outb);
        return "ok=" + ok + " err=" + e + " format=" + v + " (0=NONE,1=DEFAULT,2=LZNT1,3=LZX)";
    }

    static string Sizes(string p, IntPtr h) {
        long logical = 0;
        GetFileSizeEx(h, out logical);
        uint high = 0;
        uint low = GetCompressedFileSizeW(p, out high);
        int e = Marshal.GetLastWin32Error();
        long phys = ((long)high << 32) | (uint)low;
        return "logical=" + logical + " physical=" + phys + " (err=" + e + ")";
    }

    static void Truncate(IntPtr h, long size) {
        long np = 0;
        SetFilePointerEx(h, size, out np, FILE_BEGIN);
        SetEndOfFile(h);
    }

    public static string Run() {
        StringBuilder o = new StringBuilder();
        string dir = @"C:\sparseprobe";
        if (Directory.Exists(dir)) Directory.Delete(dir, true);
        Directory.CreateDirectory(dir);

        // ---- 1. no sparse flag: extend then measure ----
        o.AppendLine("##### 1. extend WITHOUT sparse flag #####");
        string p1 = dir + @"\plain.bin";
        IntPtr h1 = Open(p1, CREATE_ALWAYS);
        o.AppendLine("create handle=" + (h1.ToInt64() != -1 ? "ok" : "FAIL err=" + Marshal.GetLastWin32Error()));
        byte[] head = new byte[4096];
        for (int i = 0; i < head.Length; i++) head[i] = 0x41;
        uint wrote = 0;
        WriteFile(h1, head, 4096, out wrote, IntPtr.Zero);
        o.AppendLine("wrote=" + wrote);
        Truncate(h1, 67108864L);
        o.AppendLine("after truncate to 64MB: " + Sizes(p1, h1));
        o.AppendLine("compression: " + Compression(h1));
        o.AppendLine("setsparse(now): " + SetSparse(h1, true));
        o.AppendLine("after late setsparse: " + Sizes(p1, h1));
        CloseHandle(h1);

        // ---- 2. sparse flag FIRST, then extend ----
        o.AppendLine();
        o.AppendLine("##### 2. set sparse flag FIRST, then extend #####");
        string p2 = dir + @"\sparse.bin";
        IntPtr h2 = Open(p2, CREATE_ALWAYS);
        o.AppendLine("create handle=" + (h2.ToInt64() != -1 ? "ok" : "FAIL err=" + Marshal.GetLastWin32Error()));
        o.AppendLine("setsparse(first): " + SetSparse(h2, true));
        WriteFile(h2, head, 4096, out wrote, IntPtr.Zero);
        Truncate(h2, 67108864L);
        o.AppendLine("after truncate to 64MB: " + Sizes(p2, h2));
        o.AppendLine("allocated ranges 0..64MB: " + AllocRanges(h2, 0, 67108864L));
        Truncate(h2, 134217728L);
        o.AppendLine("after truncate to 128MB: " + Sizes(p2, h2));
        o.AppendLine("allocated ranges 0..128MB: " + AllocRanges(h2, 0, 134217728L));
        o.AppendLine("compression: " + Compression(h2));
        CloseHandle(h2);

        // ---- 3. reopen and re-query, to see whether the flag is persistent ----
        o.AppendLine();
        o.AppendLine("##### 3. reopen the sparse file and re-query #####");
        IntPtr h3 = Open(p2, OPEN_EXISTING);
        o.AppendLine("reopen handle=" + (h3.ToInt64() != -1 ? "ok" : "FAIL err=" + Marshal.GetLastWin32Error()));
        o.AppendLine("sizes: " + Sizes(p2, h3));
        o.AppendLine("allocated ranges 0..128MB: " + AllocRanges(h3, 0, 134217728L));
        CloseHandle(h3);

        // ---- 4. clearing the flag on a file that already has sparse data ----
        o.AppendLine();
        o.AppendLine("##### 4. clear sparse flag afterwards #####");
        IntPtr h4 = Open(p2, OPEN_EXISTING);
        o.AppendLine("setsparse(false): " + SetSparse(h4, false));
        o.AppendLine("sizes after clear: " + Sizes(p2, h4));
        CloseHandle(h4);

        o.AppendLine();
        o.AppendLine("PROBE_SPARSE_DONE");
        return o.ToString();
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp -ErrorAction Stop
Write-Output ([SP]::Run())

Write-Output ""
Write-Output "##### fsutil cross-check #####"
& fsutil sparse queryflag C:\sparseprobe\plain.bin 2>&1 | Write-Output
& fsutil sparse queryflag C:\sparseprobe\sparse.bin 2>&1 | Write-Output
& fsutil file queryallocatedranges C:\sparseprobe\sparse.bin 0 67108864 2>&1 | Write-Output
Write-Output "##### volume info #####"
& fsutil fsinfo volumeinfo C:\ 2>&1 | Write-Output
