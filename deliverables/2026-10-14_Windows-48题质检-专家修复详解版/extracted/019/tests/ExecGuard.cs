using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;
using System.Threading;

internal static class ExecGuard
{
    private const uint CreateSuspended = 4, CreateUnicodeEnvironment = 0x400, CreateNoWindow = 0x08000000;
    private const uint WaitTimeout = 258, KillOnJobClose = 0x2000;
    [StructLayout(LayoutKind.Sequential)] private struct Startup
    {
        public uint Size;
        public IntPtr Reserved, Desktop, Title;
        public uint X, Y, XSize, YSize, XChars, YChars, Fill, Flags;
        public ushort Show, ReservedSize;
        public IntPtr ReservedBytes, Input, Output, Error;
    }
    [StructLayout(LayoutKind.Sequential)] private struct ProcessInfo { public IntPtr Process, Thread; public uint ProcessId, ThreadId; }
    [StructLayout(LayoutKind.Sequential)] private struct BasicLimits
    {
        public long ProcessTime, JobTime;
        public uint Flags;
        public UIntPtr MinimumWorkingSet, MaximumWorkingSet;
        public uint ActiveProcesses;
        public UIntPtr Affinity;
        public uint Priority, Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] private struct IoCounters { public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
    [StructLayout(LayoutKind.Sequential)] private struct Limits
    {
        public BasicLimits Basic;
        public IoCounters Io;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [StructLayout(LayoutKind.Sequential)] private struct Accounting
    {
        public long UserTime, KernelTime, PeriodUserTime, PeriodKernelTime;
        public uint PageFaults, TotalProcesses, ActiveProcesses, TerminatedProcesses;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern IntPtr CreateJobObjectW(IntPtr attrs, string name);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool SetInformationJobObject(IntPtr job, int kind, ref Limits limits, uint size);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool QueryInformationJobObject(IntPtr job, int kind, out Accounting accounting, uint size, IntPtr returned);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool QueryInformationJobObject(IntPtr job, int kind, IntPtr data, uint size, IntPtr returned);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern IntPtr OpenProcess(uint access, bool inherit, uint processId);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool QueryFullProcessImageNameW(IntPtr process, uint flags, StringBuilder image, ref uint length);
    [DllImport("ntdll.dll")] private static extern int NtQueryInformationProcess(IntPtr process, int kind,
        out UIntPtr information, uint size, out uint returned);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateProcessWithLogonW(string user, string domain, string password, uint logonFlags,
        string app, StringBuilder command, uint flags, IntPtr env, string cwd, ref Startup startup, out ProcessInfo process);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool GetExitCodeProcess(IntPtr process, out uint code);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool TerminateProcess(IntPtr process, uint code);
    [DllImport("kernel32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool TerminateJobObject(IntPtr job, uint code);
    [DllImport("kernel32.dll")] private static extern IntPtr GetStdHandle(int which);
    [DllImport("kernel32.dll")] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool CloseHandle(IntPtr handle);
    [StructLayout(LayoutKind.Sequential)] private struct SecurityAttributes
    {
        public int Length;
        public IntPtr Descriptor;
        [MarshalAs(UnmanagedType.Bool)] public bool Inherit;
    }
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern IntPtr CreateWindowStationW(string name, uint flags, uint access, ref SecurityAttributes attributes);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)] private static extern IntPtr CreateDesktopW(string name, string device, IntPtr deviceMode, uint flags, uint access, ref SecurityAttributes attributes);
    [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr GetProcessWindowStation();
    [DllImport("user32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool SetProcessWindowStation(IntPtr station);
    [DllImport("user32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool CloseWindowStation(IntPtr station);
    [DllImport("user32.dll", SetLastError = true)] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool CloseDesktop(IntPtr desktop);
    private static void Check(bool ok) { if (!ok) throw new Win32Exception(Marshal.GetLastWin32Error()); }

    private static IntPtr UserObjectDescriptor(SecurityIdentifier user, uint rights)
    {
        // Only these new private objects admit the child. No access to the trusted desktop is added.
        var descriptor = new RawSecurityDescriptor("D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;0x" +
            rights.ToString("x", CultureInfo.InvariantCulture) + ";;;" + user.Value + ")");
        byte[] bytes = new byte[descriptor.BinaryLength]; descriptor.GetBinaryForm(bytes, 0);
        IntPtr native = Marshal.AllocHGlobal(bytes.Length); Marshal.Copy(bytes, 0, native, bytes.Length);
        return native;
    }

    private static IntPtr PrivateDesktop(string user, out IntPtr station, out IntPtr desktop)
    {
        station = desktop = IntPtr.Zero;
        string name = "winbench-" + Guid.NewGuid().ToString("N");
        var sid = (SecurityIdentifier)new NTAccount(Environment.MachineName, user).Translate(typeof(SecurityIdentifier));
        IntPtr stationDescriptor = IntPtr.Zero, desktopDescriptor = IntPtr.Zero;
        try
        {
            // Specific object access and READ_CONTROL, but no DELETE/WRITE_DAC/WRITE_OWNER for the child.
            stationDescriptor = UserObjectDescriptor(sid, 0x0002037F);
            desktopDescriptor = UserObjectDescriptor(sid, 0x000201FF);
            SecurityAttributes stationAttributes = new SecurityAttributes {
                Length = Marshal.SizeOf(typeof(SecurityAttributes)), Descriptor = stationDescriptor, Inherit = false };
            SecurityAttributes desktopAttributes = new SecurityAttributes {
                Length = Marshal.SizeOf(typeof(SecurityAttributes)), Descriptor = desktopDescriptor, Inherit = false };
            station = CreateWindowStationW(name, 0, 0x000F037F, ref stationAttributes); Check(station != IntPtr.Zero);
            IntPtr previous = GetProcessWindowStation(); Check(previous != IntPtr.Zero);
            Check(SetProcessWindowStation(station));
            try
            {
                desktop = CreateDesktopW("default", null, IntPtr.Zero, 0, 0x000F01FF, ref desktopAttributes);
                Check(desktop != IntPtr.Zero);
            }
            finally { Check(SetProcessWindowStation(previous)); }
            // An alternate logon cannot initialize user32/CLR on the administrator's inherited desktop.
            return Marshal.StringToHGlobalUni(name + "\\default");
        }
        finally
        {
            if (stationDescriptor != IntPtr.Zero) Marshal.FreeHGlobal(stationDescriptor);
            if (desktopDescriptor != IntPtr.Zero) Marshal.FreeHGlobal(desktopDescriptor);
        }
    }

    private static void ClosePrivateDesktop(IntPtr desktop, IntPtr station)
    {
        int error = 0; bool ok = true;
        if (desktop != IntPtr.Zero && !CloseDesktop(desktop)) { error = Marshal.GetLastWin32Error(); ok = false; }
        if (station != IntPtr.Zero && !CloseWindowStation(station))
        { if (ok) error = Marshal.GetLastWin32Error(); ok = false; }
        if (!ok) throw new Win32Exception(error);
    }

    private static IntPtr ChildEnvironment()
    {
        string windows = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
        if (String.IsNullOrEmpty(windows)) throw new InvalidOperationException("Windows directory unavailable");
        // Never inherit the guard environment, which contains the child logon password.
        var values = new SortedDictionary<string, string>(StringComparer.OrdinalIgnoreCase) {
            { "SystemRoot", windows }, { "WINDIR", windows },
            { "PATH", Path.Combine(windows, "System32") + ";" + windows + ";" + Path.Combine(windows, "System32\\WindowsPowerShell\\v1.0") },
            { "COMSPEC", Path.Combine(windows, "System32\\cmd.exe") },
            { "PATHEXT", ".COM;.EXE;.BAT;.CMD" }, { "TEMP", "C:\\agenttmp" }, { "TMP", "C:\\agenttmp" }
        };
        StringBuilder block = new StringBuilder();
        foreach (var entry in values) block.Append(entry.Key).Append('=').Append(entry.Value).Append('\0');
        block.Append('\0');
        return Marshal.StringToHGlobalUni(block.ToString());
    }

    private static uint ActiveProcesses(IntPtr job)
    {
        Accounting accounting;
        Check(QueryInformationJobObject(job, 1, out accounting, (uint)Marshal.SizeOf(typeof(Accounting)), IntPtr.Zero));
        return accounting.ActiveProcesses;
    }

    private static uint RootConsoleHost(IntPtr mainProcess, uint mainProcessId, out IntPtr pinnedHost)
    {
        pinnedHost = IntPtr.Zero;
        UIntPtr peer; uint returned;
        // ProcessConsoleHostProcess (49) is a pinned Windows-runtime compatibility dependency of
        // this trusted launcher, not an API requirement placed on candidate implementations.
        int status = NtQueryInformationProcess(mainProcess, 49, out peer, (uint)IntPtr.Size, out returned);
        if (status != 0 || returned != IntPtr.Size)
            throw new InvalidOperationException("Windows runtime console-host query incompatible: 0x" + status.ToString("x8"));
        ulong value = peer.ToUInt64();
        if ((value & 3UL) != 1UL || (value & ~3UL) == 0 || (value & ~3UL) > UInt32.MaxValue) return 0;
        uint id = (uint)(value & ~3UL);
        IntPtr host = OpenProcess(0x00100400, false, id); // SYNCHRONIZE | QUERY_INFORMATION
        if (host == IntPtr.Zero) return 0; // Already gone, or not provable: never exempt by name alone.
        try
        {
            status = NtQueryInformationProcess(host, 49, out peer, (uint)IntPtr.Size, out returned);
            if (status != 0 || returned != IntPtr.Size || peer.ToUInt64() != ((ulong)mainProcessId | 2UL)) return 0;
            StringBuilder image = new StringBuilder(32768); uint length = (uint)image.Capacity;
            if (!QueryFullProcessImageNameW(host, 0, image, ref length)) return 0;
            string expected = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "System32", "conhost.exe");
            if (!String.Equals(image.ToString(), expected, StringComparison.OrdinalIgnoreCase)) return 0;
            // Preserve the exact process identity against PID reuse until the whole job is reaped.
            pinnedHost = host; host = IntPtr.Zero;
            return id;
        }
        finally { if (host != IntPtr.Zero) CloseHandle(host); }
    }

    private static uint WaitForCandidate(IntPtr mainProcess, uint mainProcessId, out IntPtr consoleHost, out uint consoleHostId)
    {
        consoleHost = IntPtr.Zero; consoleHostId = 0;
        var timer = System.Diagnostics.Stopwatch.StartNew();
        while (true)
        {
            // Image-name queries can fail once conhost begins teardown, before its handle signals.
            // Bind the first reciprocal, canonical host while the candidate runs and keep its handle.
            // A later FreeConsole/AllocConsole must not exempt an additional candidate-created host.
            if (consoleHostId == 0) consoleHostId = RootConsoleHost(mainProcess, mainProcessId, out consoleHost);
            long remaining = 15000 - timer.ElapsedMilliseconds;
            uint wait = WaitForSingleObject(mainProcess, remaining <= 0 ? 0 : (uint)Math.Min(remaining, 10));
            if (wait != WaitTimeout || remaining <= 0) return wait;
        }
    }

    private static uint LiveHelpers(IntPtr job, uint mainProcessId, uint rootConsoleHostId)
    {
        // Never count the exited main or its proven kernel-bound OS console host. All other live
        // members remain failures, including console hosts belonging to candidate-spawned helpers.
        for (int size = 256; size <= 1024 * 1024; size *= 2)
        {
            IntPtr data = Marshal.AllocHGlobal(size);
            try
            {
                if (!QueryInformationJobObject(job, 3, data, (uint)size, IntPtr.Zero))
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error == 234 || error == 122) continue;
                    throw new Win32Exception(error);
                }
                int count = Marshal.ReadInt32(data, 4);
                if (count < 0 || count > (size - 8) / IntPtr.Size)
                    throw new InvalidOperationException("Invalid job process list");
                uint live = 0;
                for (int i = 0; i < count; ++i)
                {
                    uint id = checked((uint)Marshal.ReadIntPtr(data, 8 + i * IntPtr.Size).ToInt64());
                    if (id == mainProcessId || id == rootConsoleHostId) continue;
                    IntPtr process = OpenProcess(0x00100000, false, id); // SYNCHRONIZE only
                    if (process == IntPtr.Zero)
                    {
                        int error = Marshal.GetLastWin32Error();
                        if (error == 87) continue; // Member already disappeared.
                        throw new Win32Exception(error, "Cannot inspect a job member to establish complete process cleanup");
                    }
                    try
                    {
                        uint wait = WaitForSingleObject(process, 0);
                        if (wait == WaitTimeout) ++live;
                        else Check(wait == 0);
                    }
                    finally { CloseHandle(process); }
                }
                return live;
            }
            finally { Marshal.FreeHGlobal(data); }
        }
        throw new InvalidOperationException("Job process list exceeds guard capacity");
    }

    private static void StopJob(IntPtr job)
    {
        Check(TerminateJobObject(job, 124));
        var timer = System.Diagnostics.Stopwatch.StartNew();
        while (ActiveProcesses(job) != 0)
        {
            if (timer.ElapsedMilliseconds >= 5000) throw new TimeoutException("Job cleanup did not complete");
            Thread.Sleep(10);
        }
    }

    private static uint RunCandidate(string candidate, string plan, out bool timedOut, out uint remaining)
    {
        timedOut = false; remaining = 0;
        if (Environment.GetEnvironmentVariable("WINBENCH_DISPOSABLE_CONTAINER") != "1" ||
            !new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator))
            throw new InvalidOperationException("Execution guard requires the trusted container administrator");
        string user = Environment.GetEnvironmentVariable("WINBENCH_USER");
        string password = [REDACTED]"WINBENCH_PASSWORD");
        if (String.IsNullOrEmpty(user) || String.IsNullOrEmpty(password) ||
            String.Equals(user, Environment.UserName, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Separate candidate account credentials required");
        IntPtr job = IntPtr.Zero, environment = IntPtr.Zero;
        IntPtr station = IntPtr.Zero, desktop = IntPtr.Zero, desktopName = IntPtr.Zero, consoleHost = IntPtr.Zero;
        ProcessInfo child = new ProcessInfo();
        try
        {
            // The guard process and this non-inheritable job belong to the trusted account.
            job = CreateJobObjectW(IntPtr.Zero, null); Check(job != IntPtr.Zero);
            Limits limits = new Limits(); limits.Basic.Flags = KillOnJobClose;
            Check(SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(typeof(Limits))));
            environment = ChildEnvironment();
            desktopName = PrivateDesktop(user, out station, out desktop);
            Startup startup = new Startup { Size = (uint)Marshal.SizeOf(typeof(Startup)), Flags = 0x100, Desktop = desktopName,
                Input = GetStdHandle(-10), Output = GetStdHandle(-11), Error = GetStdHandle(-12) };
            string command = "\"" + candidate + "\" apply \"" + plan + "\"";
            Check(CreateProcessWithLogonW(user, Environment.MachineName, password, 0, candidate,
                new StringBuilder(command), CreateSuspended | CreateUnicodeEnvironment | CreateNoWindow,
                environment, Path.GetDirectoryName(candidate), ref startup, out child));
            Check(AssignProcessToJobObject(job, child.Process));
            Check(ResumeThread(child.Thread) != UInt32.MaxValue);
            uint consoleHostId;
            uint wait = WaitForCandidate(child.Process, child.ProcessId, out consoleHost, out consoleHostId);
            if (wait == WaitTimeout)
            {
                timedOut = true;
                StopJob(job);
                Check(WaitForSingleObject(child.Process, 5000) == 0);
            }
            else
            {
                Check(wait == 0);
                remaining = LiveHelpers(job, child.ProcessId, consoleHostId);
            }
            uint code; Check(GetExitCodeProcess(child.Process, out code));
            // Reap descendants even after normal main-process exit, but report the R6 violation.
            StopJob(job);
            return code;
        }
        finally
        {
            if (job != IntPtr.Zero) { TerminateJobObject(job, 125); CloseHandle(job); }
            if (child.Process != IntPtr.Zero)
            {
                // Covers failed job assignment while the newly created child is still suspended.
                if (WaitForSingleObject(child.Process, 0) != 0)
                { TerminateProcess(child.Process, 125); WaitForSingleObject(child.Process, 5000); }
                CloseHandle(child.Process);
            }
            if (child.Thread != IntPtr.Zero) CloseHandle(child.Thread);
            if (consoleHost != IntPtr.Zero) CloseHandle(consoleHost);
            if (environment != IntPtr.Zero) Marshal.FreeHGlobal(environment);
            if (desktopName != IntPtr.Zero) Marshal.FreeHGlobal(desktopName);
            ClosePrivateDesktop(desktop, station);
        }
    }

    private static void WriteReceipt(string path, uint? exitCode, bool timedOut, uint remaining, Exception failure)
    {
        FileSecurity security = new FileSecurity();
        security.SetAccessRuleProtection(true, false);
        foreach (SecurityIdentifier sid in new[] { WindowsIdentity.GetCurrent().User,
            new SecurityIdentifier(WellKnownSidType.BuiltinAdministratorsSid, null),
            new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null) })
            security.AddAccessRule(new FileSystemAccessRule(sid, FileSystemRights.FullControl, AccessControlType.Allow));
        string json = "{\"validity\":\"" + (failure == null ? "VALID" : "INVALID") + "\",\"exit_code\":" +
            (exitCode.HasValue ? exitCode.Value.ToString(CultureInfo.InvariantCulture) : "null") +
            ",\"timed_out\":" + (timedOut ? "true" : "false") +
            ",\"active_processes_after_exit\":" + remaining.ToString(CultureInfo.InvariantCulture) +
            ",\"job_cleanup_complete\":" + (failure == null ? "true" : "false") + ",\"error_type\":" +
            (failure == null ? "null" : "\"" + failure.GetType().Name + "\"") + ",\"win32_error\":" +
            (failure is Win32Exception ? ((Win32Exception)failure).NativeErrorCode.ToString(CultureInfo.InvariantCulture) : "null") + "}";
        // The parent chooses a unique path in its protected verifier log directory.
        using (FileStream file = new FileStream(path, FileMode.CreateNew, FileSystemRights.Write,
            FileShare.Read, 4096, FileOptions.None, security))
        using (StreamWriter writer = new StreamWriter(file, new UTF8Encoding(false))) writer.Write(json);
    }

    private static int Main(string[] args)
    {
        if (args.Length != 3 || Array.Exists(args, arg => String.IsNullOrEmpty(arg) || arg.Contains("\""))) return 125;
        uint? exitCode = null; bool timedOut = false; uint remaining = 0; Exception failure = null;
        try { exitCode = RunCandidate(Path.GetFullPath(args[0]), Path.GetFullPath(args[1]), out timedOut, out remaining); }
        catch (Exception e) { failure = e; Console.Error.WriteLine("EXEC_GUARD_INFRA: " + e.GetType().Name + ": " + e.Message); }
        try { WriteReceipt(Path.GetFullPath(args[2]), exitCode, timedOut, remaining, failure); }
        catch (Exception e) { Console.Error.WriteLine("EXEC_GUARD_RECEIPT_INFRA: " + e.GetType().Name); return 125; }
        // Candidate exit codes 124/125 are data, not guard status. GuardProbe may intentionally
        // leave a helper: only Fixture.Run enforces active_processes_after_exit == 0 for candidates.
        return failure == null ? 0 : 125;
    }
}
