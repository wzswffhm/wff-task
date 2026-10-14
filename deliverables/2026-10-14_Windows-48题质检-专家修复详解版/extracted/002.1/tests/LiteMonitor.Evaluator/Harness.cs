using System;

using System.Collections.Generic;

using System.Diagnostics;

using System.Globalization;

using System.IO;

using System.Linq;

using System.Runtime.InteropServices;

using System.Text;

using System.Text.Json;

using System.Threading;

using LiteMonitor.src.Core;

using Microsoft.Win32;



namespace Harbor.Evaluator

{

    public sealed class AssertionFailedException : Exception

    {

        public AssertionFailedException(string message) : base(message) { }

    }



    /// <summary>

    /// A failed precondition means the evaluator itself could not exercise the

    /// behaviour under test (missing fixture, vacuous observation window, blocked

    /// resource). It is reported as INVALID and never counted as a model failure.

    /// </summary>

    public sealed class PreconditionFailedException : Exception

    {

        public PreconditionFailedException(string message) : base(message) { }

    }



    public sealed record CheckResult(string Id, string Rubric, string Suite, bool Passed, string Detail, double Seconds, string Status)

    {

        public CheckResult(string id, string rubric, string suite, bool passed, string detail, double seconds)

            : this(id, rubric, suite, passed, detail, seconds, passed ? "pass" : "fail") { }

    }



    public static class Harness

    {

        public static readonly List<CheckResult> Results = new();

        public static string WorkRoot = Path.Combine(Path.GetTempPath(), "harbor-verifier");
        public static string? OnlyCase;
        public static string? CaseStartedPath;


        public static void Assert(bool condition, string message)

        {

            if (condition) return;

            if (message.StartsWith("PRECONDITION:", StringComparison.Ordinal))

            {

                throw new PreconditionFailedException(message.Substring("PRECONDITION:".Length).Trim());

            }

            throw new AssertionFailedException(message);

        }



        public static void Precondition(bool condition, string message)

        {

            if (!condition) throw new PreconditionFailedException(message);

        }



        public static void AssertEqual<T>(T actual, T expected, string what)

        {

            if (!EqualityComparer<T>.Default.Equals(actual, expected))

            {

                throw new AssertionFailedException($"{what}: expected <{Format(expected)}> but was <{Format(actual)}>");

            }

        }



        public static string Format(object? value)

        {

            if (value is null) return "null";

            if (value is string s) return "\"" + s + "\"";

            return Convert.ToString(value, CultureInfo.InvariantCulture) ?? "null";

        }



        /// <summary>

        /// Optional measurement text a passing check wants to leave in the evidence.

        /// Without it a pass would only record "ok", which is not audit-worthy.

        /// </summary>

        public static void Report(string detail) => DetailOverride = detail;



        [ThreadStatic] private static string? DetailOverride;



        public static void Run(string id, string rubric, string suite, Action body)

        {

            var sw = Stopwatch.StartNew();
            if (OnlyCase is not null && !string.Equals(id, OnlyCase, StringComparison.Ordinal)) return;
            if (CaseStartedPath is not null) File.WriteAllText(CaseStartedPath, id);
            DetailOverride = null;

            string detail;

            bool passed;

            bool invalid = false;

            try

            {

                body();

                passed = true;

                detail = string.IsNullOrEmpty(DetailOverride) ? "ok" : DetailOverride;

            }

            catch (PreconditionFailedException ex)

            {

                passed = false;

                invalid = true;

                detail = "INVALID/PRECONDITION: " + ex.Message;

            }

            catch (AssertionFailedException ex)

            {

                passed = false;

                detail = "ASSERT: " + ex.Message;

            }

            catch (Exception ex)

            {

                passed = false;

                detail = ex.GetType().Name + ": " + ex.Message;

            }

            sw.Stop();

            Results.Add(new CheckResult(id, rubric, suite, passed, detail, Math.Round(sw.Elapsed.TotalSeconds, 3),

                passed ? "pass" : (invalid ? "invalid" : "fail")));

            Console.WriteLine($"CHECK {(passed ? "PASS" : (invalid ? "INVALID" : "FAIL"))} [{rubric}] {id} :: {detail}");

        }



        public static string NewWorkDir(string label)

        {

            string dir = Path.Combine(WorkRoot, label + "-" + Guid.NewGuid().ToString("N").Substring(0, 8));

            Directory.CreateDirectory(dir);

            return dir;

        }



        public static void DeleteTree(string path)

        {

            try { if (Directory.Exists(path)) Directory.Delete(path, true); } catch { }

        }



        /// <summary>

        /// Removes every piece of machine state the suites can create, so the residue

        /// audit starts from a known-empty baseline.

        /// </summary>

        public static void PurgeStoreState()

        {

            try { StatusMirror.Purge(); } catch { }

            try

            {

                using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry64);

                baseKey.DeleteSubKeyTree(StatusMirror.RootSubKey, throwOnMissingSubKey: false);

            }

            catch { }

        }



        public static int SummarizeAndExit()

        {

            int total = Results.Count;

            int passed = Results.Count(r => r.Passed);

            Console.WriteLine($"SUMMARY total={total} passed={passed} failed={total - passed} invalid={Results.Count(r => r.Status == "invalid")}");

            foreach (var rubric in Results.Select(r => r.Rubric).Distinct().OrderBy(x => x, StringComparer.Ordinal))

            {

                var items = Results.Where(r => r.Rubric == rubric).ToList();

                bool ok = items.All(r => r.Passed);

                Console.WriteLine($"RUBRIC {rubric} score={(ok ? "1.0" : "0.0")} checks={items.Count} passed={items.Count(r => r.Passed)}");

            }

            if (Results.Any(r => r.Status == "invalid")) return 2;

            return total == passed ? 0 : 1;

        }

    }



    public static class Native

    {

        private static readonly Guid FolderIdLocalAppData = new Guid("F1B32785-6FBA-4FCF-9D55-7B8E7F157091");



        [DllImport("shell32.dll", CharSet = CharSet.Unicode, SetLastError = true)]

        private static extern int SHGetKnownFolderPath(ref Guid rfid, uint dwFlags, IntPtr hToken, out IntPtr ppszPath);



        public static string IndependentLocalAppData()

        {

            Guid id = FolderIdLocalAppData;

            IntPtr buffer = IntPtr.Zero;

            try

            {

                int hr = SHGetKnownFolderPath(ref id, 0, IntPtr.Zero, out buffer);

                if (hr != 0 || buffer == IntPtr.Zero) throw new InvalidOperationException("SHGetKnownFolderPath hr=0x" + hr.ToString("X8"));

                return Marshal.PtrToStringUni(buffer) ?? throw new InvalidOperationException("null path");

            }

            finally

            {

                if (buffer != IntPtr.Zero) Marshal.FreeCoTaskMem(buffer);

            }

        }



        public static RegistryKey OpenCurrentUser64() => RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry64);



        public static RegistryKey? OpenStatusKey()

        {

            using RegistryKey baseKey = OpenCurrentUser64();

            return baseKey.OpenSubKey(StatusMirror.StatusSubKey, writable: false);

        }



        public static RegistryKey CreateStatusKey()

        {

            using RegistryKey baseKey = OpenCurrentUser64();

            return baseKey.CreateSubKey(StatusMirror.StatusSubKey, writable: true)!;

        }



        public static bool RootKeyExists()

        {

            using RegistryKey baseKey = OpenCurrentUser64();

            using RegistryKey? key = baseKey.OpenSubKey(StatusMirror.RootSubKey, writable: false);

            return key is not null;

        }



        public static string[] TempFilesIn(string dir, string pattern)

        {

            if (!Directory.Exists(dir)) return Array.Empty<string>();

            return Directory.EnumerateFiles(dir, pattern, SearchOption.TopDirectoryOnly).ToArray();

        }



        public static (int exitCode, string stdout) RunSelf(string args, int timeoutMs = 60000)

        {

            var psi = new ProcessStartInfo

            {

                FileName = Environment.ProcessPath!,

                Arguments = args,

                UseShellExecute = false,

                CreateNoWindow = true,

                RedirectStandardOutput = true,

                RedirectStandardError = true,

                StandardOutputEncoding = Encoding.UTF8,

                WorkingDirectory = AppContext.BaseDirectory

            };

            using var process = Process.Start(psi)!;

            string stdout = process.StandardOutput.ReadToEnd();

            string stderr = process.StandardError.ReadToEnd();

            if (!process.WaitForExit(timeoutMs))

            {

                try { process.Kill(entireProcessTree: true); } catch { }

                throw new AssertionFailedException($"child process timed out: {args}");

            }

            if (!string.IsNullOrWhiteSpace(stderr)) stdout += "\n[stderr] " + stderr;

            return (process.ExitCode, stdout);

        }

    }

}
