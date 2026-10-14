using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using LiteMonitor.src.Core;
using Microsoft.Win32;

namespace Harbor.Evaluator
{
    /// <summary>
    /// Entry point of the hidden Harbor evaluator.
    ///
    /// Exit codes (consumed by tests/run_tests.ps1):
    ///   0 = every collected check passed
    ///   1 = the run completed and at least one check failed  -> a real FAILED verdict
    ///   2 = INVALID: the evaluator could not produce a verdict (no checks collected,
    ///       a precondition/fixture problem, or an unhandled infrastructure error).
    ///       A 2 is never counted against the model.
    /// </summary>
    public static class Program
    {
        private static readonly (string Name, string Suite, Action Body)[] Groups =
        {
            // 组名只用于 --only 过滤与日志；判分分组看的是 Harness.Run 传进去的 rubric id。
            ("R1_notify_liveness_rearm", "fail_to_pass", NotifyChecks.Liveness),
            ("R2_notify_filter_subtree", "fail_to_pass", NotifyChecks.FilterSubtree),
            ("R3_notify_multi_watcher", "fail_to_pass", NotifyChecks.MultiWatcher),
            ("R4_notify_lifecycle_recovery", "fail_to_pass", NotifyChecks.Lifecycle),
            ("R5_notify_resource_failure", "fail_to_pass", NotifyChecks.ResourceFailure),
            ("R6_last_write_filetime_utc", "fail_to_pass", NotifyChecks.LastWriteTime),
            ("R7_mirror_refresher_integration", "fail_to_pass", IntegrationChecks.All),
            ("P2P", "pass_to_pass", P2PChecks.All),
            ("SS", "system_state", SystemStateChecks.All),
        };

        public static int Main(string[] argv)
        {
            try { Console.OutputEncoding = Encoding.UTF8; } catch { }
            try { Console.InputEncoding = Encoding.UTF8; } catch { }

            string? mode = GetOption(argv, "--mode");
            if (Array.IndexOf(argv, "--health") >= 0)
            {
                try
                {
                    using (var health = Microsoft.Win32.Registry.CurrentUser.CreateSubKey(@"Software\LiteMonitor\HarborHealth"))
                    {
                        health.SetValue("Probe", 17);
                        if (!Equals(health.GetValue("Probe"), 17)) return 2;
                    }
                    Microsoft.Win32.Registry.CurrentUser.DeleteSubKeyTree(@"Software\LiteMonitor\HarborHealth");
                    Console.WriteLine("HARBOR_HEALTH_OK");
                    return 0;
                }
                catch { return 2; }
            }
            Harness.OnlyCase = GetOption(argv, "--case");
            Harness.CaseStartedPath = GetOption(argv, "--case-started");
            if (mode is not null) return RunHelperMode(mode, argv);

            string suite = (GetOption(argv, "--suite") ?? "all").Trim().ToLowerInvariant();
            string? only = GetOption(argv, "--only");
            string workRoot = GetOption(argv, "--workroot") ?? Path.Combine(Path.GetTempPath(), "litemonitor-evaluator");
            string? resultsPath = GetOption(argv, "--results");

            Reporter.TaskId = GetOption(argv, "--task-id") ?? Reporter.TaskId;
            Reporter.TaskVersion = GetOption(argv, "--task-version") ?? Reporter.TaskVersion;
            Reporter.RunId = GetOption(argv, "--run-id") ?? Reporter.RunId;
            Reporter.Suite = suite;
            Reporter.TargetRepoOut = GetOption(argv, "--target-repo-out") ?? SafeTargetRepoOut();
            Reporter.RepoCommit = GetOption(argv, "--repo-commit") ?? "";
            Reporter.StartedAtUtc = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);

            Harness.WorkRoot = workRoot;
            Directory.CreateDirectory(workRoot);

            var total = Stopwatch.StartNew();
            Console.WriteLine($"=== LiteMonitor.Evaluator v{Reporter.EvaluatorVersion} suite={suite} only={only ?? "*"} ===");
            Console.WriteLine("evaluatorDir=" + AppContext.BaseDirectory);
            Console.WriteLine("workRoot=" + workRoot);
            Console.WriteLine("targetRepoOut=" + Reporter.TargetRepoOut);
            Console.WriteLine("targetAssemblySha256=" + Reporter.ComputeTargetAssemblyHash());
            Console.WriteLine("mirrorRoot=HKCU\\" + StatusMirror.RootSubKey);
            Console.WriteLine("mirrorKey=HKCU\\" + StatusMirror.StatusSubKey);
            Console.WriteLine("notifyTarget=HKCU\\" + RegistryNotify.TargetSubKey);

            int exitCode;
            try
            {
                exitCode = RunSuites(suite, only);
            }
            catch (Exception ex)
            {
                Console.WriteLine("EVALUATOR_INFRASTRUCTURE_ERROR " + ex.GetType().Name + ": " + ex);
                exitCode = 2;
            }

            Console.WriteLine("=== cleanup ===");
            Cleanup();
            Reporter.ResidueCount = CountResidue(Reporter.ResidueDetail);
            Console.WriteLine("RESIDUE_COUNT=" + Reporter.ResidueCount);
            foreach (string line in Reporter.ResidueDetail) Console.WriteLine("RESIDUE " + line);

            total.Stop();
            Reporter.DurationSeconds = Math.Round(total.Elapsed.TotalSeconds, 3);
            Reporter.FinishedAtUtc = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);

            if (resultsPath is not null)
            {
                try
                {
                    Reporter.Write(resultsPath);
                    Console.WriteLine("RESULTS_JSON=" + Path.GetFullPath(resultsPath));
                }
                catch (Exception ex)
                {
                    Console.WriteLine("RESULTS_JSON_ERROR " + ex.GetType().Name + ": " + ex.Message);
                    exitCode = 2;
                }
            }

            Console.WriteLine("EXIT_CODE=" + exitCode);
            return exitCode;
        }

        private static int RunSuites(string suite, string? only)
        {
            bool ranAny = false;
            foreach (var group in Groups)
            {
                bool suiteMatch = suite == "all" || string.Equals(suite, group.Suite, StringComparison.Ordinal);
                if (!suiteMatch) continue;
                if (only is not null && !string.Equals(only, group.Name, StringComparison.OrdinalIgnoreCase)) continue;
                ranAny = true;
                try
                {
                    group.Body();
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"GROUP {group.Name} CRASHED {ex.GetType().Name}: {ex.Message}");
                    Harness.Results.Add(new CheckResult(group.Name + "_GROUP_CRASH", group.Name, group.Suite, false,
                        "INVALID/GROUP_CRASH " + ex.GetType().Name + ": " + ex.Message, 0, "invalid"));
                }
            }

            if (!ranAny)
            {
                Console.WriteLine($"NO GROUP SELECTED for suite='{suite}' only='{only}'");
                return 2;
            }
            if (Harness.Results.Count == 0)
            {
                Console.WriteLine("NO CHECKS COLLECTED - the evaluator produced no verdict, this run is INVALID");
                return 2;
            }
            return Harness.SummarizeAndExit();
        }

        private static void Cleanup()
        {
            try { SettingsHelperBridge.DeleteStored(); } catch { }
            try { StatusMirror.Purge(); } catch { }
            try { NotifyFixture.DeleteTree(NotifyFixture.Root); } catch { }
            foreach (string name in new[]
                     {
                         "settings.json", "settings.json.bak", "settings.json.tmp",
                         "TrafficHistory.json", "TrafficHistory.json.bak", "TrafficHistory.json.tmp"
                     })
            {
                try
                {
                    string p = Path.Combine(AppContext.BaseDirectory, name);
                    if (File.Exists(p)) File.Delete(p);
                }
                catch { }
            }
            try
            {
                if (Directory.Exists(Harness.WorkRoot)) Directory.Delete(Harness.WorkRoot, true);
            }
            catch { }
        }

        private static int CountResidue(List<string> detail)
        {
            int residue = 0;
            try
            {
                if (Native.RootKeyExists())
                {
                    residue++;
                    detail.Add("registry HKCU\\" + StatusMirror.RootSubKey + " still present");
                }
            }
            catch { }
            foreach (string name in new[]
                     {
                         "settings.json", "settings.json.bak", "settings.json.tmp",
                         "TrafficHistory.json", "TrafficHistory.json.bak", "TrafficHistory.json.tmp"
                     })
            {
                try
                {
                    string p = Path.Combine(AppContext.BaseDirectory, name);
                    if (File.Exists(p)) { residue++; detail.Add("leftover file " + p); }
                }
                catch { }
            }
            return residue;
        }

        private static string? GetOption(string[] argv, string name)
        {
            for (int i = 0; i < argv.Length; i++)
            {
                string token = argv[i];
                if (string.Equals(token, name, StringComparison.Ordinal))
                {
                    return i + 1 < argv.Length ? argv[i + 1] : null;
                }

                if (token.StartsWith(name + "=", StringComparison.Ordinal))
                {
                    return token.Substring(name.Length + 1);
                }
            }

            return null;
        }

        private static string SafeTargetRepoOut()
        {
            try
            {
                string loc = typeof(StatusMirror).Assembly.Location;
                return string.IsNullOrEmpty(loc) ? "<in-memory>" : Path.GetDirectoryName(loc) ?? "<unknown>";
            }
            catch (Exception ex) { return "<threw " + ex.GetType().Name + ">"; }
        }

        private static int RunHelperMode(string mode, string[] argv)
        {
            switch (mode)
            {
                case "notifythrow": return ModeNotifyThrow();
                case "mirrorchild": return ModeMirrorChild();
                case "publishchild": return ModePublishChild();
                default:
                    Console.WriteLine("UNKNOWN MODE: " + mode);
                    return 2;
            }
        }

        /// <summary>
        /// Proves that a callback which throws does not kill the watcher. Runs in its own
        /// process on purpose: an implementation that lets the exception escape onto a
        /// system thread takes the CLR down, and that must not be able to take the
        /// evaluator (and therefore the verdict for every other rubric item) with it.
        /// </summary>
        private static int ModeNotifyThrow()
        {
            CallbackSink sink = new CallbackSink();
            IDisposable? handle = null;
            try
            {
                NotifyFixture.ResetTree();
                Thread.Sleep(150);
                try { handle = RegistryNotify.Watch(sink.OnChange, false); }
                catch (Exception ex)
                {
                    Console.WriteLine("NOTIFYTHROW:WATCH_EX " + ex.GetType().Name + ": " + ex.Message);
                    Console.Out.Flush();
                    return 6;
                }
                if (handle is null)
                {
                    Console.WriteLine("NOTIFYTHROW:WATCH_NULL");
                    Console.Out.Flush();
                    return 6;
                }

                Thread.Sleep(600);
                sink.ArmThrowOnce();
                sink.Reset();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Ex1", 1, RegistryValueKind.DWord);
                int first = NotifyFixture.WaitUntil(() => sink.Count > 0, 3000);
                int firstCount = sink.Count;

                Thread.Sleep(400);
                sink.Reset();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Ex2", 2, RegistryValueKind.DWord);
                int second = NotifyFixture.WaitUntil(() => sink.Count > 0, 3000);
                int secondCount = sink.Count;

                Console.WriteLine("NOTIFYTHROW:first=" + (first < 0 ? "never" : first.ToString(CultureInfo.InvariantCulture))
                    + " firstCount=" + firstCount
                    + " second=" + (second < 0 ? "never" : second.ToString(CultureInfo.InvariantCulture))
                    + " secondCount=" + secondCount);
                Console.Out.Flush();

                if (first < 0 || firstCount < 1) return 7;
                if (second < 0 || secondCount < 1) return 8;
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine("NOTIFYTHROW:EX " + ex.GetType().Name + ": " + ex.Message);
                Console.Out.Flush();
                return 9;
            }
            finally
            {
                try { handle?.Dispose(); } catch { }
                NotifyFixture.DeleteTree(NotifyFixture.Root);
            }
        }

        /// <summary>
        /// Reads the registry status mirror from a SEPARATE OS process so the system_state
        /// suite proves real machine state rather than in-process memory.
        /// </summary>
        private static int ModeMirrorChild()
        {
            try
            {
                using RegistryKey baseKey = RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry64);
                using RegistryKey? key = baseKey.OpenSubKey(StatusMirror.StatusSubKey, writable: false);
                if (key is null)
                {
                    Console.WriteLine("MIRRORCHILD:MISSING");
                    Console.Out.Flush();
                    return 4;
                }
                Emit("SchemaVersion", key.GetValue(StatusMirror.SchemaVersionValueName));
                Emit("Generation", key.GetValue(StatusMirror.GenerationValueName));
                Emit("AutoStartEnabled", key.GetValue(StatusMirror.AutoStartValueName));
                Emit("MonitorItemCount", key.GetValue(StatusMirror.MonitorItemCountValueName));
                Emit("ThemeName", key.GetValue(StatusMirror.ThemeNameValueName));
                Emit("TrafficUploadBytes", key.GetValue(StatusMirror.TrafficUploadBytesValueName));
                Emit("ValueCount", key.ValueCount);
                foreach (string name in key.GetValueNames().OrderBy(x => x, StringComparer.Ordinal))
                    Emit("Kind_" + name, key.GetValueKind(name));
                Console.WriteLine("MIRRORCHILD:OK");
            }
            catch (Exception ex)
            {
                Console.WriteLine("MIRRORCHILD:EX " + ex.GetType().Name + ": " + ex.Message);
                Console.Out.Flush();
                return 5;
            }
            Console.Out.Flush();
            return 0;
        }

        /// <summary>
        /// Publishes the mirror once from a SEPARATE OS process, so the system_state suite can
        /// prove the mirror is machine-wide state and not an in-process cache.
        /// </summary>
        private static int ModePublishChild()
        {
            try
            {
                bool ok = StatusMirror.Publish(new StatusSnapshot(false, 7, "Dracula_Vampire", 987654321L));
                Console.WriteLine("PUBLISHCHILD:OK=" + (ok ? "true" : "false"));
                Console.WriteLine("PUBLISHCHILD:GENERATION=" + StatusMirror.ReadGeneration().ToString(CultureInfo.InvariantCulture));
            }
            catch (Exception ex)
            {
                Console.WriteLine("PUBLISHCHILD:EX " + ex.GetType().Name + ": " + ex.Message);
                Console.Out.Flush();
                return 5;
            }
            Console.Out.Flush();
            return 0;
        }

        internal static string FindChildField(string stdout, string prefix)
        {
            foreach (string line in (stdout ?? string.Empty).Split('\n'))
            {
                string trimmed = line.Trim();
                if (trimmed.StartsWith(prefix, StringComparison.Ordinal)) return trimmed.Substring(prefix.Length).Trim();
            }
            return "";
        }

        private static void Emit(string name, object? value)
        {
            Console.WriteLine(name + "=" + (Convert.ToString(value, CultureInfo.InvariantCulture) ?? "<null>"));
        }
    }

    /// <summary>
    /// Small indirection so cleanup keeps working when SettingsHelper itself is broken
    /// in the state under test.
    /// </summary>
    internal static class SettingsHelperBridge
    {
        internal static void DeleteStored() => LiteMonitor.SettingsHelper.DeleteStoredSettings();
    }
}
