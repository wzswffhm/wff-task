# NTFS sparse-file probe #3 (ASCII only).
# Settles which "physical size" primitive is reliable, because probe #1 and
# probe #2 disagreed: GetCompressedFileSizeW returned 65536 in one run and 0 in
# the other, while FSCTL_QUERY_ALLOCATED_RANGES was correct in both.
# Candidates under test:
#   - GetCompressedFileSizeW                    (designed for compressed files)
#   - GetFileInformationByHandleEx(FileStandardInfo).AllocationSize  (actual allocation)
#   - FSCTL_QUERY_ALLOCATED_RANGES              (per-range truth)
$ErrorActionPreference = 'Continue'

$src = @'
using System;
using System.Text;
using System.IO;
using System.Runtime.InteropServices;

public static class SP4 {
    [StructLayout(LayoutKind.Sequential)]
    public struct FILE_STANDARD_INFO {
        public long AllocationSize;
        public long EndOfFile;
        public uint NumberOfLinks;
        public byte DeletePending;
        public byte Directory;
    }

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
    static extern bool GetFileInformationByHandleEx(IntPtr h, int cls, out FILE_STANDARD_INFO info, uint sz);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool FlushFileBuffers(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool WriteFile(IntPtr h, byte[] b, uint n, out uint written, IntPtr ov);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool CloseHandle(IntPtr h);

    const uint GENERIC_RW = 0xC0000000;
    const uint SHARE_ALL  = 0x0007;
    const uint CREATE_ALWAYS = 2;
    const uint OPEN_EXISTING = 3;
    const uint FSCTL_SET_SPARSE             = 0x000900C4;
    const uint FSCTL_QUERY_ALLOCATED_RANGES = 0x000940CF;
    const int  FileStandardInfo = 1;

    static IntPtr Open(string p, uint disp) {
        return CreateFileW(p, GENERIC_RW, SHARE_ALL, IntPtr.Zero, disp, 0, IntPtr.Zero);
    }

    static bool SetSparse(IntPtr h, bool on) {
        IntPtr inb = Marshal.AllocHGlobal(1);
        Marshal.WriteByte(inb, 0, (byte)(on ? 1 : 0));
        uint ret = 0;
        bool ok = DeviceIoControl(h, FSCTL_SET_SPARSE, inb, 1, IntPtr.Zero, 0, out ret, IntPtr.Zero);
        Marshal.FreeHGlobal(inb);
        return ok;
    }

    static string AllocRanges(IntPtr h, long off, long len) {
        IntPtr inb = Marshal.AllocHGlobal(16);
        Marshal.WriteInt64(inb, 0, off);
        Marshal.WriteInt64(inb, 8, len);
        IntPtr outb = Marshal.AllocHGlobal(16 * 64);
        uint ret = 0;
        bool ok = DeviceIoControl(h, FSCTL_QUERY_ALLOCATED_RANGES, inb, 16, outb, 16 * 64, out ret, IntPtr.Zero);
        StringBuilder sb = new StringBuilder();
        if (!ok) { sb.Append("FAIL err=").Append(Marshal.GetLastWin32Error()); }
        else {
            int n = (int)(ret / 16);
            if (n == 0) sb.Append("<none>");
            for (int i = 0; i < n; i++)
                sb.Append("[").Append(Marshal.ReadInt64(outb, i*16)).Append("+").Append(Marshal.ReadInt64(outb, i*16+8)).Append("]");
        }
        Marshal.FreeHGlobal(inb);
        Marshal.FreeHGlobal(outb);
        return sb.ToString();
    }

    static void Truncate(IntPtr h, long size) {
        long np = 0;
        SetFilePointerEx(h, size, out np, 0);
        SetEndOfFile(h);
    }

    static void Poke(IntPtr h, long off, int len) {
        long np = 0;
        SetFilePointerEx(h, off, out np, 0);
        byte[] b = new byte[len];
        for (int i = 0; i < len; i++) b[i] = 0x5A;
        uint w = 0;
        WriteFile(h, b, (uint)len, out w, IntPtr.Zero);
    }

    // One comparable measurement line.
    static string Probe(string label, string path, IntPtr h) {
        long logical = 0;
        GetFileSizeEx(h, out logical);

        FILE_STANDARD_INFO si = new FILE_STANDARD_INFO();
        bool okEx = GetFileInformationByHandleEx(h, FileStandardInfo, out si, (uint)Marshal.SizeOf(typeof(FILE_STANDARD_INFO)));
        int errEx = Marshal.GetLastWin32Error();

        uint high = 0;
        uint low = GetCompressedFileSizeW(path, out high);
        int errCs = Marshal.GetLastWin32Error();
        long comp = ((long)high << 32) | (uint)low;

        return label
            + " | logical=" + logical
            + " | std.AllocationSize=" + (okEx ? si.AllocationSize.ToString() : "FAIL err=" + errEx)
            + " | std.EndOfFile=" + (okEx ? si.EndOfFile.ToString() : "-")
            + " | GetCompressedFileSize=" + comp + " (low=" + low + " err=" + errCs + ")";
    }

    public static string Run() {
        StringBuilder o = new StringBuilder();
        string dir = @"C:\sparseprobe3";
        if (Directory.Exists(dir)) Directory.Delete(dir, true);
        Directory.CreateDirectory(dir);

        string sp = dir + @"\sp.bin";
        string dn = dir + @"\dn.bin";

        // ---------- sparse scenario ----------
        o.AppendLine("===== sparse file (set sparse flag BEFORE extending) =====");
        IntPtr h = Open(sp, CREATE_ALWAYS);
        o.AppendLine("setsparse=" + SetSparse(h, true));
        Truncate(h, 134217728L);
        o.AppendLine(Probe("A empty 128MB", sp, h));
        Poke(h, 33554432L, 8192);
        o.AppendLine(Probe("B wrote 8192@32MB", sp, h));
        Poke(h, 100663296L, 4096);
        o.AppendLine(Probe("C wrote 4096@96MB", sp, h));
        FlushFileBuffers(h);
        o.AppendLine(Probe("D after flush", sp, h));
        o.AppendLine("   ranges=" + AllocRanges(h, 0, 134217728L));
        CloseHandle(h);

        IntPtr h2 = Open(sp, OPEN_EXISTING);
        o.AppendLine(Probe("E reopened", sp, h2));
        o.AppendLine("   ranges=" + AllocRanges(h2, 0, 134217728L));
        CloseHandle(h2);

        // ---------- dense scenario ----------
        o.AppendLine();
        o.AppendLine("===== dense file (no sparse flag) =====");
        IntPtr hd = Open(dn, CREATE_ALWAYS);
        Truncate(hd, 134217728L);
        o.AppendLine(Probe("A dense empty 128MB", dn, hd));
        Poke(hd, 33554432L, 8192);
        o.AppendLine(Probe("B dense wrote 8192@32MB", dn, hd));
        o.AppendLine("   ranges=" + AllocRanges(hd, 0, 134217728L));
        FlushFileBuffers(hd);
        o.AppendLine(Probe("C dense after flush", dn, hd));
        CloseHandle(hd);
        IntPtr hd2 = Open(dn, OPEN_EXISTING);
        o.AppendLine(Probe("D dense reopened", dn, hd2));
        CloseHandle(hd2);

        // ---------- late setsparse on an already allocated file ----------
        o.AppendLine();
        o.AppendLine("===== late setsparse (flag applied AFTER clusters were allocated) =====");
        IntPtr hl = Open(dn, OPEN_EXISTING);
        o.AppendLine("setsparse(late)=" + SetSparse(hl, true));
        o.AppendLine(Probe("late setsparse, same handle", dn, hl));
        o.AppendLine("   ranges=" + AllocRanges(hl, 0, 134217728L));
        CloseHandle(hl);
        IntPtr hl2 = Open(dn, OPEN_EXISTING);
        o.AppendLine(Probe("late setsparse, reopened", dn, hl2));
        o.AppendLine("   ranges=" + AllocRanges(hl2, 0, 134217728L));
        CloseHandle(hl2);

        o.AppendLine();
        o.AppendLine("PROBE_SPARSE3_DONE");
        return o.ToString();
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp -ErrorAction Stop
Write-Output ([SP4]::Run())

Write-Output ""
Write-Output "##### fsutil cross-checks #####"
Write-Output "--- sparse queryflag ---"
& fsutil sparse queryflag C:\sparseprobe3\sp.bin 2>&1 | Write-Output
& fsutil sparse queryflag C:\sparseprobe3\dn.bin 2>&1 | Write-Output
Write-Output "--- file queryAllocRanges offset=0 length=134217728 ---"
& fsutil file queryAllocRanges offset=0 length=134217728 C:\sparseprobe3\sp.bin 2>&1 | Write-Output
& fsutil file queryAllocRanges offset=0 length=134217728 C:\sparseprobe3\dn.bin 2>&1 | Write-Output
Write-Output "--- file queryValidData ---"
& fsutil file queryValidData C:\sparseprobe3\sp.bin 2>&1 | Write-Output
Write-Output "--- file layout ---"
& fsutil file layout C:\sparseprobe3\sp.bin 2>&1 | Select-Object -First 40 | Write-Output
