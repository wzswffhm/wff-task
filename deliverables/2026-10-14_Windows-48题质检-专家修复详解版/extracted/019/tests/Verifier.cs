using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using Microsoft.Win32.SafeHandles;

internal sealed class AssertionFailure : Exception { public AssertionFailure(string text) : base(text) {} }
internal sealed class CaseResult
{
    public string id, group, requirement, status, message, stdout, stderr;
    public double duration_ms;
}
internal sealed class CheckCase
{
    public string Id, Group, Requirement;
    public Action<Fixture> Check;
    public CheckCase(string id, string group, string requirement, Action<Fixture> check)
    { Id = id; Group = group; Requirement = requirement.Contains("R6") ? requirement : requirement + ",R6"; Check = check; }
}
internal sealed class Snapshot
{
    public byte[] Bytes;
    public long Creation;
    public string Dacl;
    public SortedDictionary<string, string> Streams;
}
internal sealed class Fixture : IDisposable
{
    public readonly string Root;
    public string Stdout = "", Stderr = "";
    public Fixture(string parent)
    { Root = Path.Combine(parent, Guid.NewGuid().ToString("N")); Directory.CreateDirectory(Root); }
    public string FileAt(string name, byte[] content)
    {
        string path = Path.Combine(Root, name);
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllBytes(path, content);
        return path;
    }
    public string TextFile(string name, string text) { return FileAt(name, Encoding.UTF8.GetBytes(text)); }
    public Dictionary<string, object> Entry(string source, string destination)
    { return new Dictionary<string, object> { {"source", source}, {"destination", destination}, {"sha256", Verifier.Hash(File.ReadAllBytes(source))} }; }
    public string Plan(params Dictionary<string, object>[] entries)
    {
        string path = Path.Combine(Root, "plan.json");
        File.WriteAllText(path, Verifier.Json.Serialize(new { files = entries }), new UTF8Encoding(false));
        return path;
    }
    public Dictionary<string, object> Run(string plan, int expectedCode, int count)
    {
        string guard = Environment.GetEnvironmentVariable("WINBENCH_GUARD");
        HashSet<string> tempBefore = guard == null ? null : Inventory("C:\\agenttmp");
        string receiptDirectory = Environment.GetEnvironmentVariable("WINBENCH_RECEIPT_DIR");
        if (guard != null && (String.IsNullOrEmpty(receiptDirectory) || !Directory.Exists(receiptDirectory)))
            throw new Exception("Protected execution receipt directory unavailable");
        string receiptPath = guard == null ? null : Path.Combine(receiptDirectory, "guard-" + Guid.NewGuid().ToString("N") + ".json");
        ProcessStartInfo info = new ProcessStartInfo(guard ?? Verifier.Candidate,
            guard == null ? "apply " + Verifier.Quote(plan) : Verifier.Quote(Verifier.Candidate) + " " +
                Verifier.Quote(plan) + " " + Verifier.Quote(receiptPath));
        info.WorkingDirectory = Path.GetDirectoryName(Verifier.Candidate);
        info.UseShellExecute = false;
        // The guard stays under the trusted verifier account. It alone performs the restricted logon.
        info.RedirectStandardInput = info.RedirectStandardOutput = info.RedirectStandardError = true;
        info.CreateNoWindow = true;
        using (Process process = new Process { StartInfo = info })
        {
            process.Start(); process.StandardInput.Close();
            var output = process.StandardOutput.ReadToEndAsync();
            var error = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(guard == null ? 15000 : 30000))
            {
                process.Kill(); process.WaitForExit();
                if (guard != null) throw new Exception("Execution guard did not complete its trusted deadline");
                throw new AssertionFailure("Candidate exceeded the declared 15-second deadline");
            }
            if (!System.Threading.Tasks.Task.WaitAll(new System.Threading.Tasks.Task[] { output, error }, 5000))
                throw new Exception("Execution output pipes did not close after process cleanup");
            Stdout += output.Result; Stderr += error.Result;
            long exitCode = process.ExitCode;
            if (guard != null)
            {
                if (!File.Exists(receiptPath)) throw new Exception("Execution guard receipt missing");
                var receipt = Verifier.Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(receiptPath));
                object validity, code, timedOut, remaining, cleaned;
                if (process.ExitCode != 0 || receipt == null ||
                    !receipt.TryGetValue("validity", out validity) || (validity as string) != "VALID" ||
                    !receipt.TryGetValue("exit_code", out code) || !(code is int || code is long) ||
                    !receipt.TryGetValue("timed_out", out timedOut) || !(timedOut is bool) ||
                    !receipt.TryGetValue("active_processes_after_exit", out remaining) || !(remaining is int || remaining is long) ||
                    !receipt.TryGetValue("job_cleanup_complete", out cleaned) || !(cleaned is bool) || !(bool)cleaned)
                    throw new Exception("Execution guard returned an invalid receipt: " + receiptPath);
                exitCode = Convert.ToInt64(code);
                long helpers = Convert.ToInt64(remaining);
                if (exitCode < 0 || exitCode > UInt32.MaxValue || helpers < 0 || helpers > UInt32.MaxValue)
                    throw new Exception("Execution guard receipt numeric fields out of range");
                if ((bool)timedOut) throw new AssertionFailure("Candidate exceeded 15-second runtime budget");
                Verifier.Require(helpers == 0, "Candidate left background processes after its main process exited");
                try { Verifier.Require(tempBefore.SetEquals(Inventory("C:\\agenttmp")), "Candidate left temporary files/directories or changed unrelated temporary entries"); }
                catch (IOException e) { throw new AssertionFailure("Candidate damaged its temporary directory: " + e.Message); }
                catch (UnauthorizedAccessException e) { throw new AssertionFailure("Candidate changed temporary-directory access: " + e.Message); }
            }
            Verifier.Require(exitCode == expectedCode, "Exit code expected " + expectedCode + ", got " + exitCode);
            Dictionary<string, object> response;
            try { response = Verifier.Json.Deserialize<Dictionary<string, object>>(output.Result.Trim()); }
            catch (ArgumentException) { throw new AssertionFailure("stdout is not the required JSON result"); }
            catch (InvalidOperationException) { throw new AssertionFailure("stdout is not the required JSON result"); }
            catch (InvalidCastException) { throw new AssertionFailure("stdout is not the required JSON result"); }
            catch (FormatException) { throw new AssertionFailure("stdout is not the required JSON result"); }
            catch (OverflowException) { throw new AssertionFailure("stdout is not the required JSON result"); }
            object status, published, kind;
            Verifier.Require(response != null && response.TryGetValue("status", out status) &&
                (status as string) == (expectedCode == 0 ? "ok" : "error"), "Wrong result status");
            if (expectedCode == 0)
                Verifier.Require(response.TryGetValue("published", out published) &&
                    (published is int || published is long || published is decimal || published is double) &&
                    Convert.ToDouble(published) == count, "Wrong published count");
            else
                Verifier.Require(response.TryGetValue("kind", out kind) && (kind as string) ==
                    (expectedCode == 2 ? "validation" : "io"), "Wrong error classification");
            return response;
        }
    }
    public HashSet<string> Files() { return Inventory(Root); }
    private static HashSet<string> Inventory(string root)
    {
        var entries = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var pending = new Stack<string>(); pending.Push(root);
        while (pending.Count != 0)
        {
            foreach (string path in Directory.GetFileSystemEntries(pending.Pop()))
            {
                FileAttributes attributes = File.GetAttributes(path);
                Verifier.Require((attributes & FileAttributes.ReparsePoint) == 0, "Created an unexpected reparse point");
                bool directory = (attributes & FileAttributes.Directory) != 0;
                entries.Add((directory ? "D|" : "F|") + path);
                if (directory) pending.Push(path);
            }
        }
        return entries;
    }
    public void NoResidue(HashSet<string> before)
    { Verifier.Require(before.SetEquals(Files()), "Created/deleted an unexpected file or directory, or left staging/backup residue"); }
    public void NoTransientTargetChanges(Action execute, params string[] targets)
    {
        string first = Path.Combine(Root, "health-start-" + Guid.NewGuid().ToString("N"));
        string last = Path.Combine(Root, "health-end-" + Guid.NewGuid().ToString("N"));
        var targetSet = new HashSet<string>(targets, StringComparer.OrdinalIgnoreCase);
        int changes = 0; Exception watcherError = null;
        using (ManualResetEvent started = new ManualResetEvent(false))
        using (ManualResetEvent ended = new ManualResetEvent(false))
        using (FileSystemWatcher watcher = new FileSystemWatcher(Root))
        {
            Action<string> notice = path => {
                if (targetSet.Contains(path)) Interlocked.Increment(ref changes);
            };
            watcher.IncludeSubdirectories = true;
            watcher.NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite | NotifyFilters.Security;
            watcher.InternalBufferSize = 65536;
            watcher.Created += (s, e) => {
                if (e.FullPath == first) started.Set();
                else if (e.FullPath == last) ended.Set();
                else notice(e.FullPath);
            };
            watcher.Changed += (s, e) => notice(e.FullPath);
            watcher.Deleted += (s, e) => notice(e.FullPath);
            watcher.Renamed += (s, e) => { notice(e.OldFullPath); notice(e.FullPath); };
            watcher.Error += (s, e) => Interlocked.CompareExchange(ref watcherError, e.GetException(), null);
            watcher.EnableRaisingEvents = true;
            try
            {
                File.WriteAllText(first, "health");
                if (!started.WaitOne(5000)) throw new Exception("Change observer did not become ready");
                execute();
                File.WriteAllText(last, "health");
                if (!ended.WaitOne(5000) || watcherError != null) throw new Exception("Change observer did not complete reliably", watcherError);
                Verifier.Require(changes == 0, "Validation failure transiently changed a target before returning");
            }
            finally { watcher.EnableRaisingEvents = false; File.Delete(first); File.Delete(last); }
        }
    }
    public void Dispose() { Directory.Delete(Root, true); }
}

internal static class Verifier
{
    internal static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };
    internal static string Candidate;
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct StreamData
    {
        public long Size;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 296)] public string Name;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr FindFirstStreamW(string path, int level, out StreamData data, uint flags);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool FindNextStreamW(IntPtr search, out StreamData data);
    [DllImport("kernel32.dll")] [return: MarshalAs(UnmanagedType.Bool)] private static extern bool FindClose(IntPtr search);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFileW(string path, uint access, uint share, IntPtr security, uint disposition, uint flags, IntPtr template);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool CreateHardLinkW(string path, string existing, IntPtr security);

    internal static void Require(bool condition, string reason)
    { if (!condition) throw new AssertionFailure(reason); }
    internal static string Hash(byte[] bytes)
    { using (SHA256 sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant(); }
    internal static string Quote(string path) { return "\"" + path.Replace("\"", "\\\"") + "\""; }
    private static byte[] ReadAll(Stream stream)
    { using (MemoryStream output = new MemoryStream()) { stream.CopyTo(output); return output.ToArray(); } }
    private static byte[] Bytes(int count, byte value)
    { byte[] data = new byte[count]; for (int i = 0; i < count; ++i) data[i] = (byte)(value ^ (i % 239)); return data; }
    private static void Equal(byte[] expected, byte[] actual, string reason)
    { Require(expected.SequenceEqual(actual), reason); }
    private static FileStream NativeStream(string path, bool write)
    {
        // The admitted base filename is <=240 characters, but its ADS suffix may cross MAX_PATH.
        path = path.Replace('/', '\\');
        string nativePath = path.StartsWith(@"\\?\", StringComparison.Ordinal) ? path : @"\\?\" + path;
        SafeFileHandle handle = CreateFileW(nativePath, write ? 0x40000000u : 0x80000000u, 7, IntPtr.Zero, write ? 2u : 3u, 0, IntPtr.Zero);
        if (handle.IsInvalid) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        return new FileStream(handle, write ? FileAccess.Write : FileAccess.Read);
    }
    private static void SetStream(string path, string name, byte[] content)
    { using (FileStream file = NativeStream(path + ":" + name, true)) file.Write(content, 0, content.Length); }
    private static SortedDictionary<string, string> Streams(string path)
    {
        SortedDictionary<string, string> streams = new SortedDictionary<string, string>(StringComparer.Ordinal);
        StreamData data;
        IntPtr search = FindFirstStreamW(path, 0, out data, 0);
        if (search == new IntPtr(-1)) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        try
        {
            do
            {
                if (data.Name != "::$DATA")
                    using (FileStream file = NativeStream(path + data.Name, false)) streams.Add(data.Name, Hash(ReadAll(file)));
            } while (FindNextStreamW(search, out data));
            int error = Marshal.GetLastWin32Error();
            if (error != 38) throw new System.ComponentModel.Win32Exception(error);
        }
        finally { FindClose(search); }
        return streams;
    }
    private static Snapshot Snap(string path)
    {
        return new Snapshot { Bytes = File.ReadAllBytes(path), Creation = File.GetCreationTimeUtc(path).Ticks,
            Dacl = File.GetAccessControl(path, AccessControlSections.Access).GetSecurityDescriptorSddlForm(AccessControlSections.Access),
            Streams = Streams(path) };
    }
    private static void MetadataEqual(Snapshot before, Snapshot after)
    {
        Require(before.Creation == after.Creation, "Destination creation time changed");
        Require(before.Dacl == after.Dacl, "DACL or inheritance protection changed");
        Require(Json.Serialize(before.Streams) == Json.Serialize(after.Streams), "Named streams changed or leaked from source");
    }
    private static byte[] ResultBytes(string path)
    {
        try { return File.ReadAllBytes(path); }
        catch (FileNotFoundException) { throw new AssertionFailure("Candidate removed required file: " + path); }
        catch (DirectoryNotFoundException) { throw new AssertionFailure("Candidate removed required file directory: " + path); }
    }
    private static Snapshot ResultSnap(string path)
    {
        try { return Snap(path); }
        catch (FileNotFoundException) { throw new AssertionFailure("Candidate removed required file: " + path); }
        catch (DirectoryNotFoundException) { throw new AssertionFailure("Candidate removed required file directory: " + path); }
    }
    private static void Unchanged(Snapshot before, string path)
    { Snapshot after = ResultSnap(path); Equal(before.Bytes, after.Bytes, "File content changed on failure"); MetadataEqual(before, after); }
    private static void Decorate(string path)
    {
        File.SetCreationTimeUtc(path, new DateTime(2020, 3, 4, 5, 6, 7, DateTimeKind.Utc));
        FileSecurity acl = File.GetAccessControl(path);
        acl.SetAccessRuleProtection(true, true);
        acl.AddAccessRule(new FileSystemAccessRule(WindowsIdentity.GetCurrent().User,
            FileSystemRights.FullControl, AccessControlType.Allow));
        File.SetAccessControl(path, acl);
        SetStream(path, "deployment-note", Bytes(57, 93));
        SetStream(path, "empty-note", new byte[0]);
        SetStream(path, "shared-note", Bytes(113, 19));
    }
    private static void Link(string path, string existing)
    { if (!CreateHardLinkW(path, existing, IntPtr.Zero)) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error()); }

    private static void Basic(Fixture f)
    {
        byte[] bytes = Bytes(78901, 197);
        string source = f.FileAt("stage/payload.bin", bytes), dest = f.TextFile("live/output.bin", "old");
        Snapshot original = Snap(source); string plan = f.Plan(f.Entry(source, dest)); var files = f.Files();
        f.Run(plan, 0, 1); Equal(bytes, ResultBytes(dest), "Published bytes differ"); Unchanged(original, source); f.NoResidue(files);
    }
    private static void Empty(Fixture f)
    {
        string source = f.FileAt("empty", new byte[0]), dest = f.TextFile("target", "not empty");
        Snapshot sourceBefore = Snap(source);
        string plan = f.Plan(f.Entry(source, dest)); var files = f.Files(); f.Run(plan, 0, 1);
        Require(ResultBytes(dest).Length == 0, "Empty source not published"); Unchanged(sourceBefore, source); f.NoResidue(files);
    }
    private static void UnicodeBom(Fixture f)
    {
        string source = f.TextFile("暂存 空格/发布.bin", "中文\0payload"), dest = f.TextFile("上线/目标.bin", "old");
        var entry = f.Entry(source, dest); entry["source"] = "暂存 空格/发布.bin"; entry["destination"] = "上线/../上线/目标.bin";
        entry["sha256"] = ((string)entry["sha256"]).ToUpperInvariant(); string plan = f.Plan(entry);
        File.WriteAllText(plan, File.ReadAllText(plan), new UTF8Encoding(true));
        f.Run(plan, 0, 1); Equal(ResultBytes(source), ResultBytes(dest), "Relative Unicode/BOM handling wrong");
    }
    private static void ReusedSource(Fixture f)
    {
        string source = f.TextFile("source", "payload"), a = f.TextFile("a", "a"), b = f.TextFile("b", "b");
        Snapshot sourceBefore = Snap(source);
        string plan = f.Plan(f.Entry(source, a), f.Entry(source, b)); f.Run(plan, 0, 2);
        Equal(sourceBefore.Bytes, ResultBytes(a), "First reused-source target wrong");
        Equal(sourceBefore.Bytes, ResultBytes(b), "Second reused-source target wrong");
        Unchanged(sourceBefore, source);
    }
    private static void DistinctBatch(Fixture f)
    {
        List<Dictionary<string, object>> entries = new List<Dictionary<string, object>>();
        for (int i = 0; i < 32; ++i)
        {
            string s = f.FileAt("source-" + i, Bytes(500 + i * 17, (byte)(i + 40)));
            string d = f.TextFile("dest-" + i, "old-" + i);
            entries.Add(f.Entry(s, d));
        }
        string plan = f.Plan(entries.ToArray()); var files = f.Files();
        var sources = entries.ToDictionary(e => (string)e["source"], e => Snap((string)e["source"]));
        f.Run(plan, 0, 32);
        foreach (var e in entries)
        {
            Snapshot before = sources[(string)e["source"]];
            Equal(before.Bytes, ResultBytes((string)e["destination"]), "Batch entry content mismatch");
            Unchanged(before, (string)e["source"]);
        }
        f.NoResidue(files);
    }
    private static void ExternalHardlink(Fixture f)
    {
        string s = f.TextFile("source", "new"), d = f.TextFile("dest", "original"), other = Path.Combine(f.Root, "unrelated-link");
        Link(other, d); Decorate(d); Snapshot before = Snap(other);
        string plan = f.Plan(f.Entry(s, d)); var files = f.Files(); f.Run(plan, 0, 1);
        Equal(ResultBytes(s), ResultBytes(d), "Destination did not change");
        Unchanged(before, other); MetadataEqual(before, ResultSnap(d)); f.NoResidue(files);
    }
    private static void InvalidHash(Fixture f)
    {
        string s = f.TextFile("s", "new"), a = f.TextFile("a", "old-a"), b = f.TextFile("b", "old-b");
        var second = f.Entry(s, b); second["sha256"] = new string('0', 64);
        string plan = f.Plan(f.Entry(s, a), second); Snapshot oldA = Snap(a), oldB = Snap(b); var files = f.Files();
        f.NoTransientTargetChanges(() => f.Run(plan, 2, 0), a, b);
        Unchanged(oldA, a); Unchanged(oldB, b); f.NoResidue(files);
    }
    private static void InvalidShape(Fixture f)
    {
        string plan = f.TextFile("plan.json", "{\"files\":[]}"); f.Run(plan, 2, 0);
        File.WriteAllText(plan, "{\"files\":[null]}"); f.Run(plan, 2, 0);
        File.WriteAllText(plan, "{bad json}"); f.Run(plan, 2, 0);
        string s = f.TextFile("s", "source"), d = f.TextFile("d", "target");
        var entry = f.Entry(s, d); entry["sha256"] = "not-a-sha256";
        f.Run(f.Plan(entry), 2, 0);
        var overLimit = new List<Dictionary<string, object>>();
        for (int i = 0; i < 33; ++i)
            overLimit.Add(f.Entry(s, f.TextFile("over-limit-" + i, "old-" + i)));
        var before = overLimit.ToDictionary(e => (string)e["destination"], e => Snap((string)e["destination"]));
        string tooMany = f.Plan(overLimit.ToArray()); var files = f.Files();
        f.NoTransientTargetChanges(() => f.Run(tooMany, 2, 0), before.Keys.ToArray());
        foreach (var target in before) Unchanged(target.Value, target.Key);
        f.NoResidue(files);
    }
    private static void MissingLateSource(Fixture f)
    {
        string s = f.TextFile("s", "new"), a = f.TextFile("a", "old-a"), b = f.TextFile("b", "old-b");
        var second = f.Entry(s, b); second["source"] = "does-not-exist";
        string plan = f.Plan(f.Entry(s, a), second); Snapshot oldA = Snap(a), oldB = Snap(b);
        f.NoTransientTargetChanges(() => f.Run(plan, 2, 0), a, b);
        Unchanged(oldA, a); Unchanged(oldB, b);
    }
    private static void Metadata(Fixture f)
    {
        string source = f.FileAt("source", Bytes(12873, 77)), dest = f.TextFile("target", "old");
        Decorate(dest); SetStream(source, "shared-note", Bytes(113, 241)); SetStream(source, "source-only", Bytes(23, 55));
        Snapshot before = Snap(dest), sourceBefore = Snap(source); string plan = f.Plan(f.Entry(source, dest)); var files = f.Files();
        f.Run(plan, 0, 1); Equal(sourceBefore.Bytes, ResultBytes(dest), "Default stream wrong");
        MetadataEqual(before, ResultSnap(dest)); Unchanged(sourceBefore, source); f.NoResidue(files);
    }
    private static void UnprotectedDacl(Fixture f)
    {
        string source = f.TextFile("source", "new-payload"), dest = f.TextFile("live/target", "old-payload");
        FileSecurity acl = File.GetAccessControl(dest);
        acl.SetAccessRuleProtection(false, true);
        // An explicit ACE distinguishes the target from a newly staged sibling's inherited DACL.
        acl.AddAccessRule(new FileSystemAccessRule(WindowsIdentity.GetCurrent().User,
            FileSystemRights.ReadAttributes, AccessControlType.Allow));
        File.SetAccessControl(dest, acl);
        acl = File.GetAccessControl(dest);
        if (acl.AreAccessRulesProtected || acl.GetAccessRules(true, false, typeof(SecurityIdentifier)).Count == 0)
            throw new Exception("Unprotected explicit-DACL fixture was not established");
        Snapshot before = Snap(dest), sourceBefore = Snap(source);
        string plan = f.Plan(f.Entry(source, dest)); var files = f.Files();
        f.Run(plan, 0, 1);
        Snapshot after = ResultSnap(dest);
        Equal(sourceBefore.Bytes, after.Bytes, "Unprotected-DACL destination content wrong");
        MetadataEqual(before, after); Unchanged(sourceBefore, source); f.NoResidue(files);
    }
    private static void DenyDelete(Fixture f)
    {
        string source = f.TextFile("source", "new"), dest = f.TextFile("dest", "old");
        Snapshot before = Snap(dest); string plan = f.Plan(f.Entry(source, dest)); var files = f.Files();
        using (FileStream holder = new FileStream(dest, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        { f.Run(plan, 3, 0); Equal(before.Bytes, ReadAll(holder), "External holder was changed"); Unchanged(before, dest); }
        f.NoResidue(files);
    }
    private static string NearLimitDestination(Fixture f, int length, string content)
    {
        const string leaf = "target.bin";
        int directoryLength = length - f.Root.Length - leaf.Length - 2;
        if (directoryLength < 1 || directoryLength > 255) throw new Exception("Scratch path cannot host declared near-limit fixture");
        string destination = f.TextFile(Path.Combine(new string('p', directoryLength), leaf), content);
        if (destination.Length != length) throw new Exception("Near-limit fixture path length mismatch");
        return destination;
    }
    private static void NearLimitPublish(Fixture f)
    {
        string source = f.FileAt("source", Bytes(8129, 61));
        string[] destinations = { NearLimitDestination(f, 232, "old-a"), NearLimitDestination(f, 240, "old-b") };
        Snapshot sourceBefore = Snap(source);
        string plan = f.Plan(destinations.Select(destination => f.Entry(source, destination)).ToArray()); var files = f.Files();
        f.Run(plan, 0, destinations.Length);
        foreach (string destination in destinations)
            Equal(sourceBefore.Bytes, ResultBytes(destination), "Near-limit target content wrong");
        Unchanged(sourceBefore, source); f.NoResidue(files);
    }
    private static void Rollback(Fixture f) { Rollback(f, false); }
    private static void NearLimitRollback(Fixture f) { Rollback(f, true); }
    private static void Rollback(Fixture f, bool nearLimit)
    {
        string source = f.FileAt("source", Bytes(7293, 31));
        string[] dest = { nearLimit ? NearLimitDestination(f, 240, "old-a") : f.TextFile("a", "old-a"),
            f.TextFile("b", "old-b"), f.TextFile("c", "old-c") };
        foreach (string path in dest) Decorate(path);
        Snapshot[] before = dest.Select(Snap).ToArray();
        string plan = f.Plan(dest.Select(path => f.Entry(source, path)).ToArray()); var files = f.Files();
        using (FileStream holder = new FileStream(dest[1], FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            f.Run(plan, 3, 0);
            for (int i = 0; i < dest.Length; ++i) Unchanged(before[i], dest[i]);
            Equal(before[1].Bytes, ReadAll(holder), "Blocking process no longer reads original data");
        }
        f.NoResidue(files); f.Run(plan, 0, 3);
        for (int i = 0; i < dest.Length; ++i)
        { Equal(ResultBytes(source), ResultBytes(dest[i]), "Retry failed"); MetadataEqual(before[i], ResultSnap(dest[i])); }
        f.NoResidue(files);
    }
    private static void DestinationAlias(Fixture f, bool hardlink)
    {
        string s = f.TextFile("s", "new"), a = f.TextFile("a", "old"); string b;
        if (hardlink) { b = Path.Combine(f.Root, "linked"); Link(b, a); }
        else { b = Path.Combine(f.Root, ".", "A"); }
        Snapshot before = Snap(a); string plan = f.Plan(f.Entry(s, a), f.Entry(s, b)); var files = f.Files();
        f.NoTransientTargetChanges(() => f.Run(plan, 2, 0), a, b);
        Unchanged(before, a); f.NoResidue(files);
    }
    private static void SourceAlias(Fixture f, bool cross)
    {
        string a = f.TextFile("a", "original-a"), alias = Path.Combine(f.Root, "alias"); Link(alias, a);
        string s = f.TextFile("source", "new"), b = f.TextFile("b", "original-b");
        string plan = cross ? f.Plan(f.Entry(s, a), f.Entry(alias, b)) : f.Plan(f.Entry(alias, a));
        Snapshot beforeA = Snap(a), beforeB = Snap(b); var files = f.Files();
        f.NoTransientTargetChanges(() => f.Run(plan, 2, 0), a, b, alias);
        Unchanged(beforeA, a); Unchanged(beforeB, b); f.NoResidue(files);
    }
    private static void ReaderVisibility(Fixture f)
    {
        byte[] old = Bytes(4 * 1024 * 1024, 11), fresh = Bytes(4 * 1024 * 1024, 211);
        string source = f.FileAt("source", fresh), dest = f.FileAt("dest", old);
        string plan = f.Plan(f.Entry(source, dest)); var files = f.Files();
        var info = new ProcessStartInfo(typeof(Verifier).Assembly.Location,
            "--observe " + Quote(dest) + " " + Hash(old) + " " + Hash(fresh));
        info.UseShellExecute = false;
        info.RedirectStandardInput = info.RedirectStandardOutput = info.RedirectStandardError = true;
        info.CreateNoWindow = true;
        using (FileStream holder = new FileStream(dest, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
        using (Process observer = Process.Start(info))
        {
            try
            {
                var observerError = observer.StandardError.ReadToEndAsync();
                var ready = observer.StandardOutput.ReadLineAsync();
                if (!ready.Wait(10000) || ready.Result != "READY") throw new Exception("Observer failed startup health handshake");
                var reportOutput = observer.StandardOutput.ReadToEndAsync();
                Exception candidateFailure = null;
                try
                {
                    for (int publication = 0; publication < 65; ++publication)
                    {
                        File.WriteAllBytes(source, publication % 2 == 0 ? fresh : old);
                        plan = f.Plan(f.Entry(source, dest));
                        f.Run(plan, 0, 1);
                    }
                }
                catch (AssertionFailure e) { candidateFailure = e; }
                // Only the trusted parent has the write end. No candidate-writable filesystem sentinel.
                observer.StandardInput.WriteLine("STOP"); observer.StandardInput.Flush(); observer.StandardInput.Close();
                if (!observer.WaitForExit(10000)) throw new Exception("Observer failed completion handshake");
                if (!System.Threading.Tasks.Task.WaitAll(new System.Threading.Tasks.Task[] { reportOutput, observerError }, 5000))
                    throw new Exception("Observer result pipes did not complete");
                string reportText = reportOutput.Result;
                var report = Json.Deserialize<Dictionary<string, object>>(reportText);
                if (observer.ExitCode != 0 || report == null || Convert.ToInt32(report["reads"]) < 2 ||
                    !report.ContainsKey("final_hash"))
                    throw new Exception("Observer unhealthy or did not complete its independent final read");
                Require(Convert.ToInt32(report["invalid"]) == 0, "Reader observed missing/partial/invalid content: " + reportText.Trim());
                if (candidateFailure != null) throw candidateFailure;
                Require((report["final_hash"] as string) == Hash(fresh), "Observer final read after STOP did not see published content");
                Equal(old, ReadAll(holder), "Existing shared-delete handle did not retain old content");
                Equal(fresh, ResultBytes(dest), "New open did not see new content");
            }
            finally
            {
                if (!observer.HasExited) { observer.Kill(); observer.WaitForExit(); }
            }
        }
        f.NoResidue(files);
    }
    private static int Observe(string[] args)
    {
        if (args.Length != 4) return 9;
        int reads = 0, invalid = 0;
        List<int> errors = new List<int>();
        try
        {
            // Console.In can implement ReadLineAsync synchronously; keep it off the sampling thread.
            var stop = System.Threading.Tasks.Task.Run(() => Console.In.ReadLineAsync());
            Func<string> sample = () => {
                string hash = null;
                try
                {
                    using (FileStream file = new FileStream(args[1], FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                        hash = Hash(ReadAll(file));
                    if (hash != args[2] && hash != args[3]) ++invalid;
                }
                catch (IOException e) { ++invalid; if (errors.Count < 32) errors.Add(e.HResult & 65535); }
                catch (UnauthorizedAccessException e) { ++invalid; if (errors.Count < 32) errors.Add(e.HResult & 65535); }
                ++reads;
                return hash;
            };
            do
            {
                sample();
                if (reads == 1) { Console.WriteLine("READY"); Console.Out.Flush(); }
            } while (!stop.IsCompleted);
            if (stop.Result != "STOP") throw new InvalidDataException("Observer stop command missing or invalid");
            string finalHash = sample();
            Console.WriteLine(Json.Serialize(new { reads = reads, invalid = invalid, errors = errors, final_hash = finalHash }));
            return 0;
        }
        catch (Exception e) { Console.Error.WriteLine("OBSERVER_INFRA: " + e.GetType().Name); return 9; }
    }
    private static List<CheckCase> Cases()
    {
        return new List<CheckCase> {
            new CheckCase("basic_binary", "P2P", "R1,R6", Basic),
            new CheckCase("empty_payload", "P2P", "R1", Empty),
            new CheckCase("unicode_bom_relative", "P2P", "R1", UnicodeBom),
            new CheckCase("reused_source", "P2P", "R5", ReusedSource),
            new CheckCase("distinct_32_file_batch", "P2P", "R1,R5,R6", DistinctBatch),
            new CheckCase("near_limit_destination", "P2P", "R1,R6", NearLimitPublish),
            new CheckCase("unrelated_hardlink_unchanged", "F2P", "R2,R3,R6", ExternalHardlink),
            new CheckCase("hash_preflight", "P2P", "R1,R5,R6", InvalidHash),
            new CheckCase("invalid_plan", "P2P", "R5,R6", InvalidShape),
            new CheckCase("missing_late_source", "P2P", "R5", MissingLateSource),
            new CheckCase("reader_atomic_visibility", "F2P", "R2,R6", ReaderVisibility),
            new CheckCase("ntfs_metadata_and_source_streams", "F2P", "R3", Metadata),
            new CheckCase("unprotected_dacl", "P2P", "R1,R3,R6", UnprotectedDacl),
            new CheckCase("deny_delete_sharing", "F2P", "R4,R6", DenyDelete),
            new CheckCase("batch_rollback_retry", "F2P", "R3,R4,R6", Rollback),
            new CheckCase("near_limit_rollback_retry", "F2P", "R1,R3,R4,R6", NearLimitRollback),
            new CheckCase("destination_path_alias", "F2P", "R5", f => DestinationAlias(f, false)),
            new CheckCase("destination_hardlink_alias", "F2P", "R5", f => DestinationAlias(f, true)),
            new CheckCase("source_self_hardlink_alias", "F2P", "R5", f => SourceAlias(f, false)),
            new CheckCase("source_cross_target_alias", "F2P", "R5", f => SourceAlias(f, true))
        };
    }
    private static int Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "--observe") return Observe(args);
        if (args.Length != 3) return 8;
        Candidate = Path.GetFullPath(args[0]); string resultPath = Path.GetFullPath(args[1]), scratch = Path.GetFullPath(args[2]);
        bool candidateBuildFailed = Environment.GetEnvironmentVariable("WINBENCH_CANDIDATE_BUILD") == "FAILED";
        List<CaseResult> results = new List<CaseResult>(); string preflightError = null;
        try
        {
            if (Environment.OSVersion.Platform != PlatformID.Win32NT) throw new Exception("Real Windows required");
            if (new DriveInfo(Path.GetPathRoot(scratch)).DriveFormat != "NTFS") throw new Exception("NTFS required");
            if (!candidateBuildFailed && !File.Exists(Candidate)) throw new Exception("Freshly built candidate executable missing");
            Directory.CreateDirectory(scratch);
            using (Fixture probe = new Fixture(scratch))
            {
                string a = probe.TextFile("a", "probe"); Decorate(a); Snap(a);
                Link(Path.Combine(probe.Root, "b"), a);
            }
        }
        catch (Exception e) { preflightError = e.GetType().Name + ": " + e.Message; }
        foreach (CheckCase test in Cases())
        {
            CaseResult result = new CaseResult { id = test.Id, group = test.Group, requirement = test.Requirement,
                status = "NOT_RUN", message = preflightError, stdout = "", stderr = "" };
            Stopwatch watch = Stopwatch.StartNew(); Fixture fixture = null;
            if (preflightError == null)
            {
                try
                {
                    // Buildability is an executed prerequisite of every required runtime case.
                    Require(!candidateBuildFailed, "Candidate C# build rejected; see candidate-build.log");
                    fixture = new Fixture(scratch); test.Check(fixture); result.status = "PASS"; result.message = null;
                }
                catch (AssertionFailure e) { result.status = "FAIL"; result.message = e.Message; }
                catch (Exception e) { result.status = "ERROR"; result.message = e.GetType().Name + ": " + e.Message; }
                finally
                {
                    if (fixture != null)
                    {
                        result.stdout = fixture.Stdout; result.stderr = fixture.Stderr;
                        try { fixture.Dispose(); }
                        catch (Exception e) { result.status = "ERROR"; result.message = "Fixture cleanup failed: " + e.Message; }
                    }
                }
            }
            result.duration_ms = watch.Elapsed.TotalMilliseconds; results.Add(result);
            Console.WriteLine(test.Id + " " + result.status + (result.message == null ? "" : " " + result.message));
        }
        bool valid = results.Count == Cases().Count && results.All(r => r.status == "PASS" || r.status == "FAIL");
        int? score = valid ? (int?)(results.All(r => r.status == "PASS") ? 1 : 0) : null;
        Directory.CreateDirectory(Path.GetDirectoryName(resultPath));
        File.WriteAllText(resultPath, Json.Serialize(new { validity = valid ? "VALID" : "INVALID", score = score,
            required = Cases().Select(c => c.Id).ToArray(), testcases = results, preflight_error = preflightError }), new UTF8Encoding(false));
        return valid ? 0 : 4;
    }
}
