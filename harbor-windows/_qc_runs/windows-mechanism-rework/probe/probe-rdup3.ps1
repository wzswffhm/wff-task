# ReadDirectoryChangesW probe #3 (ASCII only) -- cross-check notification delivery.
# probe #2 showed overlapped reads never completing (err=996), while handle-based
# operations (GetFinalPathNameByHandleW, MoveFileExW) worked. This run compares:
#   A) synchronous ReadDirectoryChangesW on a background thread
#   B) managed FileSystemWatcher
# so we can tell a P/Invoke mistake apart from an environment limitation.
$ErrorActionPreference = 'Stop'

$src = @'
using System;
using System.Text;
using System.IO;
using System.Threading;
using System.Runtime.InteropServices;

public static class RD3 {
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern IntPtr CreateFileW(string n, uint acc, uint share, IntPtr sa, uint disp, uint flags, IntPtr tpl);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool ReadDirectoryChangesW(IntPtr h, IntPtr buf, uint len, bool sub, uint filter, out uint ret, IntPtr ov, IntPtr cr);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool CloseHandle(IntPtr h);
    [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern bool MoveFileExW(string a, string b, uint f);

    const uint ACC_LIST = 0x0001;
    const uint SHARE_ALL = 0x0007;
    const uint OPEN_EXISTING = 3;
    const uint BACKUP_SEMANTICS = 0x02000000;
    const uint FILTER = 0x1F;

    static string Parse(IntPtr buf, int n) {
        if (n <= 0) return "<empty>";
        StringBuilder sb = new StringBuilder();
        int off = 0;
        int guard = 0;
        while (guard++ < 2000) {
            int next = Marshal.ReadInt32(buf, off);
            int act = Marshal.ReadInt32(buf, off + 4);
            int len = Marshal.ReadInt32(buf, off + 8);
            string nm = Marshal.PtrToStringUni(IntPtr.Add(buf, off + 12), len / 2);
            if (sb.Length > 0) sb.Append(" ");
            sb.Append(act).Append(":").Append(nm);
            if (next == 0) break;
            off += next;
        }
        return sb.ToString();
    }

    static void RmDir(string p) { if (Directory.Exists(p)) Directory.Delete(p, true); }

    public static string Run() {
        StringBuilder o = new StringBuilder();
        string root = @"C:\rdprobe3";
        RmDir(root);
        Directory.CreateDirectory(root);

        // ---------- A: synchronous ReadDirectoryChangesW on a worker thread ----------
        o.AppendLine("##### A. synchronous ReadDirectoryChangesW #####");
        File.WriteAllText(root + @"\a.txt", "aa");
        IntPtr h = CreateFileW(root, ACC_LIST, SHARE_ALL, IntPtr.Zero, OPEN_EXISTING, BACKUP_SEMANTICS, IntPtr.Zero);
        o.AppendLine("handle=" + (h.ToInt64() != -1 ? "ok" : "FAIL err=" + Marshal.GetLastWin32Error()));

        string res = null;
        Thread t = new Thread(delegate() {
            IntPtr buf = Marshal.AllocHGlobal(8192);
            try {
                uint ret = 0;
                bool ok = ReadDirectoryChangesW(h, buf, 8192, true, FILTER, out ret, IntPtr.Zero, IntPtr.Zero);
                int e = Marshal.GetLastWin32Error();
                res = "ok=" + ok + " ret=" + ret + " err=" + e + " [" + Parse(buf, (int)ret) + "]";
            } catch (Exception ex) {
                res = "EX:" + ex.Message;
            } finally {
                Marshal.FreeHGlobal(buf);
            }
        });
        t.IsBackground = true;
        t.Start();
        Thread.Sleep(600);
        bool mv = MoveFileExW(root + @"\a.txt", root + @"\b.txt", 0);
        o.AppendLine("driver MoveFileExW=" + mv + " err=" + Marshal.GetLastWin32Error());
        bool joined = t.Join(6000);
        o.AppendLine("thread joined=" + joined + " -> " + (res == null ? "<still blocked, NO NOTIFICATION>" : res));
        CloseHandle(h);

        // ---------- B: managed FileSystemWatcher ----------
        o.AppendLine();
        o.AppendLine("##### B. managed FileSystemWatcher #####");
        RmDir(root);
        Directory.CreateDirectory(root);
        FileSystemWatcher w = new FileSystemWatcher(root);
        w.IncludeSubdirectories = true;
        w.NotifyFilter = NotifyFilters.FileName | NotifyFilters.DirectoryName;
        w.InternalBufferSize = 8192;
        ManualResetEvent got = new ManualResetEvent(false);
        string ev = "<none>";
        w.Created += delegate(object s, FileSystemEventArgs e) { ev = "Created:" + e.Name; got.Set(); };
        w.Renamed += delegate(object s, RenamedEventArgs e) { ev = "Renamed:" + e.OldName + "->" + e.Name; got.Set(); };
        w.Changed += delegate(object s, FileSystemEventArgs e) { ev = "Changed:" + e.Name; got.Set(); };
        w.EnableRaisingEvents = true;
        Thread.Sleep(500);
        File.WriteAllText(root + @"\fsw.txt", "x");
        bool signalled = got.WaitOne(5000);
        o.AppendLine("FSW create signalled=" + signalled + " ev=" + ev);
        got.Reset();
        ev = "<none>";
        bool mv2 = MoveFileExW(root + @"\fsw.txt", root + @"\fsw2.txt", 0);
        bool signalled2 = got.WaitOne(5000);
        o.AppendLine("FSW rename driver=" + mv2 + " signalled=" + signalled2 + " ev=" + ev);
        w.EnableRaisingEvents = false;
        w.Dispose();

        o.AppendLine();
        o.AppendLine("PROBE3_DONE");
        return o.ToString();
    }
}
'@

Add-Type -TypeDefinition $src -Language CSharp -ErrorAction Stop
Write-Output ([RD3]::Run())
