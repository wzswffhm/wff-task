# ReadDirectoryChangesW probe #2 (ASCII only).
# Change vs probe #1: all logic lives in C# so every P/Invoke is well typed, reads use
# overlapped IO so they can time out instead of blocking forever, and the working
# directory is on the container's own volume instead of the bind-mounted host folder.
$ErrorActionPreference = 'Stop'

$src = @'
using System;
using System.Text;
using System.IO;
using System.Threading;
using System.Runtime.InteropServices;

public static class RD {
    [StructLayout(LayoutKind.Sequential)]
    public struct OVERLAPPED {
        public IntPtr Internal;
        public IntPtr InternalHigh;
        public uint Offset;
        public uint OffsetHigh;
        public IntPtr hEvent;
    }

    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern IntPtr CreateFileW(string n, uint acc, uint share, IntPtr sa, uint disp, uint flags, IntPtr tpl);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool ReadDirectoryChangesW(IntPtr h, IntPtr buf, uint len, bool sub, uint filter, out uint ret, IntPtr ov, IntPtr cr);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool GetOverlappedResult(IntPtr h, IntPtr ov, out uint transferred, bool wait);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern uint WaitForSingleObject(IntPtr h, uint ms);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern IntPtr CreateEventW(IntPtr sa, bool manual, bool initial, IntPtr name);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool CancelIoEx(IntPtr h, IntPtr ov);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern bool MoveFileExW(string a, string b, uint f);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern bool DeleteFileW(string a);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern uint GetFinalPathNameByHandleW(IntPtr h, StringBuilder sb, uint cch, uint flags);

    const uint ACC_LIST = 0x0001;
    const uint SHARE_ALL = 0x0007;
    const uint SHARE_NO_DELETE = 0x0003;
    const uint OPEN_EXISTING = 3;
    const uint BACKUP_SEMANTICS = 0x02000000;
    const uint FLAG_OVERLAPPED = 0x40000000;
    const uint FILTER = 0x1F;

    static IntPtr OpenDir(string p, uint share) {
        return CreateFileW(p, ACC_LIST, share, IntPtr.Zero, OPEN_EXISTING,
                           BACKUP_SEMANTICS | FLAG_OVERLAPPED, IntPtr.Zero);
    }

    static string ReadOnce(IntPtr h, int bufSize, int waitMs) {
        IntPtr ev = CreateEventW(IntPtr.Zero, true, false, IntPtr.Zero);
        int ovSize = Marshal.SizeOf(typeof(OVERLAPPED));
        IntPtr pov = Marshal.AllocHGlobal(ovSize);
        IntPtr buf = Marshal.AllocHGlobal(bufSize);
        try {
            byte[] zero = new byte[ovSize];
            Marshal.Copy(zero, 0, pov, ovSize);
            OVERLAPPED ov = new OVERLAPPED();
            ov.hEvent = ev;
            Marshal.StructureToPtr(ov, pov, false);

            uint ret = 0;
            bool ok = ReadDirectoryChangesW(h, buf, (uint)bufSize, true, FILTER, out ret, pov, IntPtr.Zero);
            int e0 = Marshal.GetLastWin32Error();
            if (!ok && e0 != 997) return "CALLFAIL err=" + e0;
            uint w = WaitForSingleObject(ev, (uint)waitMs);
            uint transferred = 0;
            bool g = GetOverlappedResult(h, pov, out transferred, false);
            int err = Marshal.GetLastWin32Error();
            if (!g && transferred == 0) {
                CancelIoEx(h, pov);
                return "ok=" + ok + " e0=" + e0 + " ret=" + ret + " wait=" + w + " gor=F err=" + err + " bytes=0";
            }
            StringBuilder sb = new StringBuilder();
            int count = 0;
            if (transferred > 0) {
                int off = 0;
                while (true) {
                    int next = Marshal.ReadInt32(buf, off);
                    int act = Marshal.ReadInt32(buf, off + 4);
                    int len = Marshal.ReadInt32(buf, off + 8);
                    string nm = Marshal.PtrToStringUni(IntPtr.Add(buf, off + 12), len / 2);
                    if (sb.Length > 0) sb.Append(" ");
                    sb.Append(act).Append(":").Append(nm);
                    count++;
                    if (next == 0) break;
                    off += next;
                }
            }
            return "ok=" + ok + " e0=" + e0 + " ret=" + ret + " wait=" + w + " gor=" + (g ? "T" : "F") +
                   " bytes=" + transferred + " err=" + err + " n=" + count + " [" + sb.ToString() + "]";
        } finally {
            Marshal.FreeHGlobal(buf);
            Marshal.FreeHGlobal(pov);
            CloseHandle(ev);
        }
    }

    static string HandlePath(IntPtr h) {
        StringBuilder sb = new StringBuilder(2048);
        uint n = GetFinalPathNameByHandleW(h, sb, 2048, 2);
        return "len=" + n + " err=" + Marshal.GetLastWin32Error() + " path=" + sb.ToString();
    }

    static void RmDir(string p) {
        if (Directory.Exists(p)) Directory.Delete(p, true);
    }

    public static string Run() {
        StringBuilder o = new StringBuilder();
        string root = @"C:\rdprobe";
        string mounted = @"C:\probe\w";
        RmDir(root);
        Directory.CreateDirectory(root);

        o.AppendLine("##### A. rename a.txt -> b.txt (same dir) #####");
        File.WriteAllText(root + @"\a.txt", "aa");
        IntPtr h = OpenDir(root, SHARE_ALL);
        bool mv = MoveFileExW(root + @"\a.txt", root + @"\b.txt", 0);
        o.AppendLine("MoveFileExW=" + mv + " err=" + Marshal.GetLastWin32Error());
        o.AppendLine("read: " + ReadOnce(h, 4096, 5000));
        CloseHandle(h);

        o.AppendLine();
        o.AppendLine("##### A2. rename c.txt -> sub\\c.txt #####");
        RmDir(root); Directory.CreateDirectory(root);
        Directory.CreateDirectory(root + @"\sub");
        File.WriteAllText(root + @"\c.txt", "cc");
        h = OpenDir(root, SHARE_ALL);
        mv = MoveFileExW(root + @"\c.txt", root + @"\sub\c.txt", 0);
        o.AppendLine("MoveFileExW=" + mv + " err=" + Marshal.GetLastWin32Error());
        o.AppendLine("read: " + ReadOnce(h, 4096, 5000));
        CloseHandle(h);

        o.AppendLine();
        o.AppendLine("##### B. delete + recreate the same name #####");
        RmDir(root); Directory.CreateDirectory(root);
        File.WriteAllText(root + @"\x.txt", "aa");
        h = OpenDir(root, SHARE_ALL);
        DeleteFileW(root + @"\x.txt");
        File.WriteAllText(root + @"\x.txt", "bb");
        o.AppendLine("read: " + ReadOnce(h, 4096, 5000));
        CloseHandle(h);

        int[] sizes = new int[] { 2048, 8192, 64000 };
        for (int i = 0; i < sizes.Length; i++) {
            int bs = sizes[i];
            o.AppendLine();
            o.AppendLine("##### C. overflow test buffer=" + bs + " 500 files #####");
            RmDir(root); Directory.CreateDirectory(root);
            h = OpenDir(root, SHARE_ALL);
            for (int k = 1; k <= 500; k++) File.WriteAllText(root + @"\g" + k + ".txt", "x");
            o.AppendLine("read#1: " + ReadOnce(h, bs, 8000));
            o.AppendLine("read#2: " + ReadOnce(h, bs, 3000));
            CloseHandle(h);
        }

        o.AppendLine();
        o.AppendLine("##### D. watched directory itself moved away #####");
        string inner = root + @"\inner";
        RmDir(root); Directory.CreateDirectory(inner);
        h = OpenDir(inner, SHARE_ALL);
        o.AppendLine("handle path before: " + HandlePath(h));
        mv = MoveFileExW(inner, root + @"\moved", 0);
        o.AppendLine("MoveFileExW(inner->moved)=" + mv + " err=" + Marshal.GetLastWin32Error());
        Thread.Sleep(300);
        o.AppendLine("handle path after : " + HandlePath(h));
        o.AppendLine("read: " + ReadOnce(h, 4096, 3000));
        CloseHandle(h);

        o.AppendLine();
        o.AppendLine("##### E. bind-mounted host folder C:\\probe #####");
        try {
            RmDir(mounted);
            Directory.CreateDirectory(mounted);
            File.WriteAllText(mounted + @"\m.txt", "mm");
            h = OpenDir(mounted, SHARE_ALL);
            o.AppendLine("handle=" + (h.ToInt64() != -1 && h != IntPtr.Zero ? "ok" : "FAIL"));
            mv = MoveFileExW(mounted + @"\m.txt", mounted + @"\n.txt", 0);
            o.AppendLine("MoveFileExW=" + mv + " err=" + Marshal.GetLastWin32Error());
            o.AppendLine("read: " + ReadOnce(h, 4096, 5000));
            CloseHandle(h);
        } catch (Exception ex) {
            o.AppendLine("EX: " + ex.Message);
        }

        o.AppendLine();
        o.AppendLine("##### F. dir handle opened WITHOUT FILE_SHARE_DELETE #####");
        RmDir(root); Directory.CreateDirectory(root + @"\inner2");
        h = OpenDir(root + @"\inner2", SHARE_NO_DELETE);
        mv = MoveFileExW(root + @"\inner2", root + @"\moved2", 0);
        o.AppendLine("move while open (no share delete)=" + mv + " err=" + Marshal.GetLastWin32Error() + " (32=SHARING_VIOLATION)");
        CloseHandle(h);
        mv = MoveFileExW(root + @"\inner2", root + @"\moved2", 0);
        o.AppendLine("move after close=" + mv + " err=" + Marshal.GetLastWin32Error());

        o.AppendLine();
        o.AppendLine("PROBE_DONE");
        return o.ToString();
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp -ErrorAction Stop
Write-Output ([RD]::Run())
