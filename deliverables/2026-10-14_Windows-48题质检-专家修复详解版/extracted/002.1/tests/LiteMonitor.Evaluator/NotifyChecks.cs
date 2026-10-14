using System;
using System.Diagnostics;
using System.Globalization;
using System.Threading;
using LiteMonitor.src.Core;
using Microsoft.Win32;

namespace Harbor.Evaluator
{
    /// <summary>
    /// Shared fixture for the registry change-notification checks.
    /// Everything lives under HKCU\Software\LiteMonitor so the residue audit in
    /// tests/run_tests.ps1 can prove the whole footprint is removable.
    /// </summary>
    internal static class NotifyFixture
    {
        public const string Root = @"Software\LiteMonitor";
        public const string Status = @"Software\LiteMonitor\Status";
        public const string Sub = @"Software\LiteMonitor\Status\Sub";
        public const string Deep = @"Software\LiteMonitor\Status\Sub\Deep3";

        public static RegistryKey Base() =>
            RegistryKey.OpenBaseKey(RegistryHive.CurrentUser, RegistryView.Registry64);

        public static void DeleteTree(string sub)
        {
            try
            {
                using RegistryKey b = Base();
                b.DeleteSubKeyTree(sub, throwOnMissingSubKey: false);
            }
            catch { }
        }

        public static bool Exists(string sub)
        {
            try
            {
                using RegistryKey b = Base();
                using RegistryKey? k = b.OpenSubKey(sub, writable: false);
                return k is not null;
            }
            catch { return false; }
        }

        public static void WriteValue(string sub, string name, object value, RegistryValueKind kind)
        {
            using RegistryKey b = Base();
            using RegistryKey? k = b.CreateSubKey(sub, writable: true);
            Harness.Precondition(k is not null, "evaluator fixture could not create HKCU\\" + sub);
            k!.SetValue(name, value, kind);
            k.Flush();
        }

        public static void DeleteValue(string sub, string name)
        {
            using RegistryKey b = Base();
            using RegistryKey? k = b.OpenSubKey(sub, writable: true);
            Harness.Precondition(k is not null, "evaluator fixture could not open HKCU\\" + sub + " writable");
            k!.DeleteValue(name, throwOnMissingValue: false);
            k.Flush();
        }

        public static void ResetTree()
        {
            DeleteTree(Root);
            WriteValue(Status, "Seed", 1, RegistryValueKind.DWord);
            WriteValue(Sub, "Seed", 1, RegistryValueKind.DWord);
            Harness.Precondition(Exists(Status) && Exists(Sub),
                "evaluator fixture could not materialise HKCU\\" + Status);
        }

        /// <summary>Returns the elapsed milliseconds, or -1 when the predicate never became true.</summary>
        public static int WaitUntil(Func<bool> predicate, int timeoutMs)
        {
            var sw = Stopwatch.StartNew();
            while (sw.ElapsedMilliseconds < timeoutMs)
            {
                if (predicate()) return (int)sw.ElapsedMilliseconds;
                Thread.Sleep(4);
            }
            return predicate() ? (int)sw.ElapsedMilliseconds : -1;
        }

        public static string Ms(int v) => v < 0 ? "never" : v.ToString(CultureInfo.InvariantCulture) + "ms";
    }

    /// <summary>Counts callbacks from the code under test and measures write-to-callback latency.</summary>
    internal sealed class CallbackSink
    {
        private int _count;
        private long _writeTick;
        private long _notifyTick;
        private int _throwOnce;

        public int Count => Volatile.Read(ref _count);

        public void OnChange()
        {
            Interlocked.Exchange(ref _notifyTick, Stopwatch.GetTimestamp());
            Interlocked.Increment(ref _count);
            if (Interlocked.Exchange(ref _throwOnce, 0) == 1)
                throw new InvalidOperationException("evaluator callback probe exception");
        }

        public void Reset()
        {
            Interlocked.Exchange(ref _count, 0);
            Interlocked.Exchange(ref _notifyTick, 0);
        }

        public void ArmThrowOnce() => Interlocked.Exchange(ref _throwOnce, 1);

        public void MarkWrite() => Interlocked.Exchange(ref _writeTick, Stopwatch.GetTimestamp());

        public double LatencyMs()
        {
            long n = Interlocked.Read(ref _notifyTick);
            long w = Interlocked.Read(ref _writeTick);
            if (n == 0 || w == 0 || n < w) return -1;
            return (n - w) * 1000.0 / Stopwatch.Frequency;
        }
    }

    /// <summary>
    /// One watcher lifetime: rebuild the fixture tree, attach RegistryNotify.Watch,
    /// give the implementation time to arm, then expose the callback sink.
    /// </summary>
    internal sealed class WatcherScope : IDisposable
    {
        public CallbackSink Sink { get; } = new CallbackSink();
        public IDisposable? Handle { get; set; }
        public string Error { get; private set; } = "";

        public WatcherScope(bool watchSubtree, bool resetTree = true)
        {
            if (resetTree)
            {
                NotifyFixture.ResetTree();
                Thread.Sleep(120);
            }
            try { Handle = RegistryNotify.Watch(Sink.OnChange, watchSubtree); }
            catch (Exception ex) { Error = ex.GetType().Name + ": " + ex.Message; }
            if (Handle is not null) Thread.Sleep(600);
            Sink.Reset();
        }

        public void RequireStarted()
        {
            Harness.Assert(Error == "",
                "RegistryNotify.Watch threw " + Error + " even though HKCU\\" + NotifyFixture.Status + " exists");
            Harness.Assert(Handle is not null,
                "RegistryNotify.Watch returned null even though HKCU\\" + NotifyFixture.Status + " exists");
        }

        public int AwaitCallback(int timeoutMs = 2500) =>
            NotifyFixture.WaitUntil(() => Sink.Count > 0, timeoutMs);

        public void Dispose()
        {
            try { Handle?.Dispose(); } catch { }
            Handle = null;
        }
    }

    /// <summary>
    /// FAIL_TO_PASS checks for the frozen RegistryNotify contract (src/Core/RegistryNotify.cs).
    /// Every "must not fire" clause is paired with a positive control inside the same check,
    /// so a watcher that never delivers a callback can never satisfy it vacuously.
    /// </summary>
    public static class NotifyChecks
    {
        private const string Suite = "fail_to_pass";
        private const string R1 = "R1_notify_liveness_rearm";
        private const string R2 = "R2_notify_filter_subtree";
        private const string R3 = "R3_notify_multi_watcher";
        private const string R4 = "R4_notify_lifecycle_recovery";
        private const string R5 = "R5_notify_resource_failure";
        private const string R6 = "R6_last_write_filetime_utc";

        public static void Liveness()
        {
            Harness.Run("W_T01_watch_returns_handle", R1, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();
                Harness.Report("Watch(onChanged, false) returned a usable handle on an existing mirror key");
            });

            Harness.Run("W_T02_attach_is_silent_then_first_change_fires", R1, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                int leaked = NotifyFixture.WaitUntil(() => w.Sink.Count > 0, 1200);
                Harness.Assert(leaked < 0,
                    "attaching the watcher produced " + w.Sink.Count + " callback(s) within 1.2s although nothing was written");

                w.Sink.MarkWrite();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Probe", 1, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0,
                    "the first value write produced no callback within 2.5s - the watcher never fires at all");
                Harness.Report("silentAfterAttach=true firstChangeCallbackIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T03_first_change_within_200ms", R1, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                w.Sink.MarkWrite();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Latency", 1, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0, "no callback within 2.5s of the value write");

                double latency = w.Sink.LatencyMs();
                Harness.Assert(latency >= 0, "a callback was observed but its latency could not be measured");
                Harness.Assert(latency <= 200.0,
                    "write-to-callback latency was " + latency.ToString("F1", CultureInfo.InvariantCulture) +
                    "ms, the contract requires <= 200ms");
                Harness.Report("latencyMs=" + latency.ToString("F1", CultureInfo.InvariantCulture));
            });

            Harness.Run("W_T04_callback_for_new_value_name", R1, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                string name = "BrandNew_" + Guid.NewGuid().ToString("N").Substring(0, 8);
                NotifyFixture.WriteValue(NotifyFixture.Status, name, 5, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0, "adding a brand new value '" + name + "' produced no callback within 2.5s");
                Harness.Report("newValue=" + name + " callbackIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T05_callback_for_value_overwrite", R1, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Status, "Seed", 4242, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0, "overwriting an existing value produced no callback within 2.5s");

                // Windows does not advance a key's last-write stamp for a byte-for-byte
                // same-kind rewrite, so that operation is not observable through
                // REG_NOTIFY_CHANGE_LAST_SET.  Rewrite the same logical value with a
                // different registry kind instead; the stored value is still 4242, but
                // the metadata change is a real registry write.  This remains a
                // mechanism-specific control against a Generation/value-diff poller.
                w.Sink.Reset();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Seed", 4242L, RegistryValueKind.QWord);
                int sameValue = w.AwaitCallback();
                Harness.Assert(sameValue >= 0,
                    "rewriting Seed with the identical value produced no callback; " +
                    "the implementation is behaving like a value-difference poller");
                Harness.Report("overwrite Seed=4242 callbackIn=" + NotifyFixture.Ms(fired) +
                               " sameValueCallbackIn=" + NotifyFixture.Ms(sameValue));
            });

            Harness.Run("W_T06_callback_for_value_delete", R1, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                string name = "ToDelete_" + Guid.NewGuid().ToString("N").Substring(0, 8);
                NotifyFixture.WriteValue(NotifyFixture.Status, name, 7, RegistryValueKind.DWord);
                w.AwaitCallback();
                w.Sink.Reset();
                Thread.Sleep(250);

                NotifyFixture.DeleteValue(NotifyFixture.Status, name);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0, "deleting value '" + name + "' produced no callback within 2.5s");
                Harness.Report("deletedValue=" + name + " callbackIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T07_rearm_five_spaced_changes", R1, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                for (int i = 0; i < 5; i++)
                {
                    NotifyFixture.WriteValue(NotifyFixture.Status, "Probe", 100 + i, RegistryValueKind.DWord);
                    Thread.Sleep(200);
                }
                NotifyFixture.WaitUntil(() => w.Sink.Count >= 5, 3000);
                int n = w.Sink.Count;
                Harness.Assert(n >= 5,
                    "5 value writes spaced 200ms apart produced only " + n + " callback(s); the watcher does not re-arm");
                Harness.Report("callbacks=" + n + " for 5 spaced writes");
            });

            Harness.Run("W_T08_still_alive_after_burst_of_40_writes", R1, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                for (int i = 0; i < 40; i++)
                    NotifyFixture.WriteValue(NotifyFixture.Status, "Burst", i, RegistryValueKind.DWord);
                int duringBurst = w.Sink.Count;
                Thread.Sleep(700);
                w.Sink.Reset();

                NotifyFixture.WriteValue(NotifyFixture.Status, "AfterBurst", 1, RegistryValueKind.DWord);
                int fired = w.AwaitCallback(3000);
                Harness.Assert(fired >= 0,
                    "after a 40-write burst the watcher went permanently silent (callbacksDuringBurst=" + duringBurst + ")");
                Harness.Report("callbacksDuringBurst=" + duringBurst + " callbackAfterBurstIn=" + NotifyFixture.Ms(fired));
            });
        }

        public static void FilterSubtree()
        {
            Harness.Run("W_T09_subtree_false_ignores_nested_but_sees_own", R2, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Sub, "NestProbe", 7, RegistryValueKind.DWord);
                int leak = NotifyFixture.WaitUntil(() => w.Sink.Count > 0, 1200);
                int nested = w.Sink.Count;
                Harness.Assert(leak < 0 && nested == 0,
                    "watchSubtree=false delivered " + nested + " callback(s) for a value written into the nested key HKCU\\" + NotifyFixture.Sub);

                w.Sink.Reset();
                NotifyFixture.WriteValue(NotifyFixture.Status, "OwnProbe", 7, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0,
                    "the same watcher never fired for its own key either, so the 'ignores nested' half above was vacuous");
                Harness.Report("nestedCallbacks=" + nested + " ownKeyCallbackIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T10_subtree_true_notifies_nested_subkey", R2, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(true);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Sub, "NestT", 11, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0,
                    "watchSubtree=true delivered no callback for a value written into HKCU\\" + NotifyFixture.Sub);
                Harness.Report("nestedCallbackIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T11_subtree_true_notifies_depth3_subkey", R2, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(true);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Deep, "DeepT", 12, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0,
                    "watchSubtree=true delivered no callback for a value written three levels down at HKCU\\" + NotifyFixture.Deep);
                Harness.Report("depth3CallbackIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T12_subtree_true_also_notifies_own_values", R2, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(true);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Status, "OwnT", 13, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0,
                    "watchSubtree=true delivered no callback for a value written into the watched key itself");
                Harness.Report("ownKeyCallbackIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T13_subkey_add_delete_alone_does_not_fire", R2, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                string churn = NotifyFixture.Status + @"\SubChurn";
                using (RegistryKey b = NotifyFixture.Base())
                {
                    using (RegistryKey? k = b.CreateSubKey(churn, writable: true))
                        Harness.Precondition(k is not null, "evaluator fixture could not create HKCU\\" + churn);
                    Thread.Sleep(600);
                    b.DeleteSubKey(churn, throwOnMissingSubKey: false);
                }
                Thread.Sleep(700);
                int spurious = w.Sink.Count;
                Harness.Assert(spurious == 0,
                    "creating and deleting the subkey SubChurn (no value was touched) produced " + spurious +
                    " callback(s); the notify filter must be REG_NOTIFY_CHANGE_LAST_SET only");

                w.Sink.Reset();
                NotifyFixture.WriteValue(NotifyFixture.Status, "OwnProbe2", 8, RegistryValueKind.DWord);
                int fired = w.AwaitCallback();
                Harness.Assert(fired >= 0,
                    "the same watcher never fired for a real value write either, so the 'no subkey notification' half above was vacuous");
                Harness.Report("subkeyChurnCallbacks=" + spurious + " valueCallbackIn=" + NotifyFixture.Ms(fired));
            });
        }

        public static void MultiWatcher()
        {
            Harness.Run("W_T14_two_watchers_both_receive_same_change", R3, Suite, () =>
            {
                using WatcherScope a = new WatcherScope(false);
                a.RequireStarted();
                using WatcherScope b = new WatcherScope(false, resetTree: false);
                b.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Status, "TwoWatchers", 1, RegistryValueKind.DWord);
                int both = NotifyFixture.WaitUntil(() => a.Sink.Count > 0 && b.Sink.Count > 0, 4000);
                Harness.Assert(a.Sink.Count >= 1 && b.Sink.Count >= 1,
                    "one value write reached watcherA=" + a.Sink.Count + " watcherB=" + b.Sink.Count +
                    " callback(s); every live handle must be notified independently (waited " + NotifyFixture.Ms(both) + ")");
                Harness.Report("watcherA=" + a.Sink.Count + " watcherB=" + b.Sink.Count + " in " + NotifyFixture.Ms(both));
            });

            Harness.Run("W_T15_disposing_one_watcher_leaves_the_other_alive", R3, Suite, () =>
            {
                using WatcherScope a = new WatcherScope(false);
                a.RequireStarted();
                using WatcherScope b = new WatcherScope(false, resetTree: false);
                b.RequireStarted();

                string disposeError = "";
                var sw = Stopwatch.StartNew();
                try { b.Handle!.Dispose(); }
                catch (Exception ex) { disposeError = ex.GetType().Name + ": " + ex.Message; }
                long disposeMs = sw.ElapsedMilliseconds;
                b.Handle = null;

                Harness.Assert(disposeError == "", "disposing the second watcher threw " + disposeError);
                Harness.Assert(disposeMs < 2000,
                    "disposing the second watcher took " + disposeMs + "ms, the contract requires < 2000ms");

                Thread.Sleep(300);
                a.Sink.Reset();
                NotifyFixture.WriteValue(NotifyFixture.Status, "AfterDisposeB", 1, RegistryValueKind.DWord);
                int fired = a.AwaitCallback();
                Harness.Assert(fired >= 0,
                    "disposing one watcher silenced the surviving one (no callback within 2.5s, dispose took " + disposeMs + "ms)");
                Harness.Report("disposeMs=" + disposeMs + " survivorCallbackIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T16_new_watcher_after_dispose_still_fires", R3, Suite, () =>
            {
                WatcherScope a = new WatcherScope(false);
                a.RequireStarted();
                a.Dispose();

                using WatcherScope c = new WatcherScope(false, resetTree: false);
                c.RequireStarted();
                NotifyFixture.WriteValue(NotifyFixture.Status, "NewWatcher", 1, RegistryValueKind.DWord);
                int fired = c.AwaitCallback();
                Harness.Assert(fired >= 0,
                    "a watcher created after a previous one was disposed never fired within 2.5s");
                Harness.Report("replacementWatcherCallbackIn=" + NotifyFixture.Ms(fired));
            });
        }

        public static void Lifecycle()
        {
            Harness.Run("W_T17_dispose_stops_callbacks", R4, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Status, "PreDispose", 1, RegistryValueKind.DWord);
                int alive = w.AwaitCallback();
                Harness.Assert(alive >= 0,
                    "the watcher was already dead before Dispose was called, so 'Dispose stops callbacks' would be vacuous");

                w.Sink.Reset();
                w.Handle!.Dispose();
                w.Handle = null;
                NotifyFixture.WriteValue(NotifyFixture.Status, "PostDispose", 999, RegistryValueKind.DWord);
                int leak = NotifyFixture.WaitUntil(() => w.Sink.Count > 0, 1500);
                Harness.Assert(leak < 0 && w.Sink.Count == 0,
                    "Dispose returned but the watcher still delivered " + w.Sink.Count + " callback(s) afterwards");
                Harness.Report("aliveBeforeDisposeIn=" + NotifyFixture.Ms(alive) + " callbacksAfterDispose=" + w.Sink.Count);
            });

            Harness.Run("W_T18_dispose_fast_and_idempotent", R4, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Status, "PreDispose2", 1, RegistryValueKind.DWord);
                int alive = w.AwaitCallback();
                Harness.Assert(alive >= 0,
                    "the watcher never delivered a callback, so the Dispose timing below would measure a dead object");

                string error = "";
                long d1 = -1, d2 = -1;
                var sw = Stopwatch.StartNew();
                try { w.Handle!.Dispose(); d1 = sw.ElapsedMilliseconds; }
                catch (Exception ex) { error = ex.GetType().Name + ": " + ex.Message; }
                sw.Restart();
                try { w.Handle!.Dispose(); d2 = sw.ElapsedMilliseconds; }
                catch (Exception ex) { error += " / second call: " + ex.GetType().Name + ": " + ex.Message; }
                w.Handle = null;

                Harness.Assert(error == "", "Dispose threw " + error);
                Harness.Assert(d1 >= 0 && d1 < 2000,
                    "first Dispose took " + d1 + "ms, the contract requires < 2000ms");
                Harness.Assert(d2 >= 0 && d2 < 2000,
                    "second (idempotent) Dispose took " + d2 + "ms, the contract requires < 2000ms");
                Harness.Report("dispose1Ms=" + d1 + " dispose2Ms=" + d2);
            });

            Harness.Run("W_T19_recovers_after_key_delete_and_recreate", R4, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Status, "Pre3", 1, RegistryValueKind.DWord);
                int alive = w.AwaitCallback();
                Harness.Assert(alive >= 0,
                    "the watcher never fired before the key was deleted, so recovery cannot be assessed");

                NotifyFixture.DeleteTree(NotifyFixture.Status);
                Thread.Sleep(600);
                NotifyFixture.WriteValue(NotifyFixture.Status, "Recreated", 0, RegistryValueKind.DWord);
                NotifyFixture.WriteValue(NotifyFixture.Sub, "Recreated", 0, RegistryValueKind.DWord);
                Thread.Sleep(1500);
                w.Sink.Reset();

                NotifyFixture.WriteValue(NotifyFixture.Status, "Post3", 5, RegistryValueKind.DWord);
                int fired = w.AwaitCallback(5000);
                Harness.Assert(fired >= 0,
                    "after HKCU\\" + NotifyFixture.Status +
                    " was deleted and recreated the watcher stayed silent for 5s - it is still holding the stale key handle");
                Harness.Report("aliveBeforeDeleteIn=" + NotifyFixture.Ms(alive) +
                               " callbackAfterRecreateIn=" + NotifyFixture.Ms(fired));
            });

            Harness.Run("W_T20_survives_callback_exception_and_keeps_firing", R4, Suite, () =>
            {
                // Runs in a child process: an implementation that lets the callback
                // exception escape onto a system thread kills the CLR, and that must
                // not be able to take the whole evaluator down with it.
                (int exitCode, string stdout) = Native.RunSelf("--mode=notifythrow", 180000);
                string marker = "";
                foreach (string line in stdout.Split('\n'))
                    if (line.StartsWith("NOTIFYTHROW:", StringComparison.Ordinal)) marker = line.Trim();

                string tail = stdout.Substring(Math.Max(0, stdout.Length - 400)).Replace('\r', ' ').Replace('\n', ' ');
                Harness.Assert(marker != "",
                    "the child process died without reporting (exitCode=" + exitCode +
                    "); a callback exception escaped onto a system thread and crashed the CLR. output tail: " + tail);
                Harness.Assert(exitCode == 0, "child reported '" + marker + "' and exited with " + exitCode);
                Harness.Report(marker + " exitCode=" + exitCode);
            });

            Harness.Run("W_T24_recovers_after_the_whole_mirror_tree_is_purged_and_republished", R4, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Status, "Pre4", 1, RegistryValueKind.DWord);
                int alive = w.AwaitCallback();
                Harness.Assert(alive >= 0,
                    "the watcher never fired before the mirror tree was removed, so recovery cannot be assessed");

                // StatusMirror.Purge() removes the WHOLE HKCU\Software\LiteMonitor tree (uninstall / reset),
                // and a later Publish() brings the mirror back. The caller only ever gets one handle from
                // Watch, so that handle has to survive the parent key disappearing as well.
                NotifyFixture.DeleteTree(NotifyFixture.Root);
                Harness.Precondition(!NotifyFixture.Exists(NotifyFixture.Root),
                    "evaluator fixture could not remove HKCU\\" + NotifyFixture.Root);
                Thread.Sleep(800);

                NotifyFixture.WriteValue(NotifyFixture.Status, "Republished", 1, RegistryValueKind.DWord);
                NotifyFixture.WriteValue(NotifyFixture.Sub, "Republished", 1, RegistryValueKind.DWord);
                Thread.Sleep(1500);
                w.Sink.Reset();

                NotifyFixture.WriteValue(NotifyFixture.Status, "Post4", 7, RegistryValueKind.DWord);
                int fired = w.AwaitCallback(6000);
                Harness.Assert(fired >= 0,
                    "after the whole HKCU\\" + NotifyFixture.Root +
                    " tree was removed and the mirror was published again the watcher stayed silent for 6s - " +
                    "it gave up permanently instead of re-attaching to the recreated key");
                Harness.Report("aliveBeforePurgeIn=" + NotifyFixture.Ms(alive) +
                               " callbackAfterRepublishIn=" + NotifyFixture.Ms(fired));
            });
        }

        public static void ResourceFailure()
        {
            Harness.Run("W_T21_idle_cpu_under_40ms_in_5s_and_alive_around_it", R5, Suite, () =>
            {
                using WatcherScope w = new WatcherScope(false);
                w.RequireStarted();

                NotifyFixture.WriteValue(NotifyFixture.Status, "PreIdle", 1, RegistryValueKind.DWord);
                Harness.Assert(w.AwaitCallback() >= 0,
                    "the watcher was already silent before the idle window, so a low CPU delta would be vacuous");

                Process p = Process.GetCurrentProcess();
                p.Refresh();
                TimeSpan before = p.TotalProcessorTime;
                Thread.Sleep(5000);
                p.Refresh();
                double cpuMs = (p.TotalProcessorTime - before).TotalMilliseconds;

                w.Sink.Reset();
                NotifyFixture.WriteValue(NotifyFixture.Status, "PostIdle", 1, RegistryValueKind.DWord);
                int after = w.AwaitCallback();
                Harness.Assert(after >= 0, "the watcher was alive before the 5s idle window but dead afterwards");
                Harness.Assert(cpuMs >= 0 && cpuMs < 40.0,
                    "an idle watcher consumed " + cpuMs.ToString("F1", CultureInfo.InvariantCulture) +
                    "ms of process CPU in 5s, the contract requires < 40ms");
                Harness.Report("idleCpuMs=" + cpuMs.ToString("F1", CultureInfo.InvariantCulture) +
                               " aliveBefore=true aliveAfterIn=" + NotifyFixture.Ms(after));
            });

            Harness.Run("W_T22_missing_key_returns_null_and_does_not_create", R5, Suite, () =>
            {
                NotifyFixture.DeleteTree(NotifyFixture.Root);
                Harness.Precondition(!NotifyFixture.Exists(NotifyFixture.Status),
                    "evaluator fixture could not remove HKCU\\" + NotifyFixture.Status);

                CallbackSink sink = new CallbackSink();
                IDisposable? handle = null;
                string error = "";
                try { handle = RegistryNotify.Watch(sink.OnChange, false); }
                catch (Exception ex) { error = ex.GetType().Name + ": " + ex.Message; }

                bool created = NotifyFixture.Exists(NotifyFixture.Status);
                try { handle?.Dispose(); } catch { }

                Harness.Assert(error == "",
                    "Watch threw " + error + " on a missing target key; the contract requires null instead");
                Harness.Assert(handle is null,
                    "Watch returned a handle even though HKCU\\" + NotifyFixture.Status + " does not exist");
                Harness.Assert(!created,
                    "Watch created HKCU\\" + NotifyFixture.Status + " although the contract forbids creating the key");
                Harness.Report("handle=null keyCreated=false noException=true");
            });

            Harness.Run("W_T23_never_throws_across_repeated_start_stop", R5, Suite, () =>
            {
                NotifyFixture.ResetTree();
                string error = "";
                int started = 0;
                for (int i = 0; i < 6; i++)
                {
                    CallbackSink sink = new CallbackSink();
                    IDisposable? handle = null;
                    try { handle = RegistryNotify.Watch(sink.OnChange, i % 2 == 0); }
                    catch (Exception ex) { error = "iteration " + i + " Watch: " + ex.GetType().Name + ": " + ex.Message; break; }
                    if (handle is null) { error = "iteration " + i + ": Watch returned null on an existing key"; break; }
                    started++;
                    try
                    {
                        NotifyFixture.WriteValue(NotifyFixture.Status, "Churn" + i, i, RegistryValueKind.DWord);
                        Thread.Sleep(90);
                        handle.Dispose();
                        handle.Dispose();
                    }
                    catch (Exception ex) { error = "iteration " + i + " Dispose: " + ex.GetType().Name + ": " + ex.Message; break; }
                }
                Harness.Assert(error == "", "start/stop churn failed after " + started + " clean iteration(s): " + error);

                using WatcherScope last = new WatcherScope(false, resetTree: false);
                last.RequireStarted();
                NotifyFixture.WriteValue(NotifyFixture.Status, "AfterChurn", 1, RegistryValueKind.DWord);
                int fired = last.AwaitCallback();
                Harness.Assert(fired >= 0, "after 6 start/stop cycles the API was left unusable (no callback within 2.5s)");
                Harness.Report("cleanIterations=" + started + " watcherStillUsableIn=" + NotifyFixture.Ms(fired));
            });
        }

        public static void LastWriteTime()
        {
            Harness.Run("L_T01_lastwrite_true_and_kind_is_utc", R6, Suite, () =>
            {
                NotifyFixture.ResetTree();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Lwt", 1, RegistryValueKind.DWord);

                DateTime value = default;
                bool ok = false;
                string error = "";
                try { ok = RegistryNotify.TryGetLastWriteTimeUtc(out value); }
                catch (Exception ex) { error = ex.GetType().Name + ": " + ex.Message; }

                Harness.Assert(error == "", "TryGetLastWriteTimeUtc threw " + error);
                Harness.Assert(ok, "TryGetLastWriteTimeUtc returned false for an existing key that was just written");
                Harness.Assert(value.Kind == DateTimeKind.Utc,
                    "the returned DateTime.Kind was " + value.Kind +
                    "; FILETIME is a UTC count so Kind must be exactly Utc");
                Harness.Report("ok=true kind=" + value.Kind + " value=" + value.ToString("o", CultureInfo.InvariantCulture));
            });

            Harness.Run("L_T02_lastwrite_within_120s_of_utcnow", R6, Suite, () =>
            {
                NotifyFixture.ResetTree();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Lwt", 1, RegistryValueKind.DWord);

                bool ok = RegistryNotify.TryGetLastWriteTimeUtc(out DateTime value);
                Harness.Assert(ok, "TryGetLastWriteTimeUtc returned false for an existing key that was just written");

                DateTime now = DateTime.UtcNow;
                double skew = Math.Abs((value - now).TotalSeconds);
                Harness.Assert(skew < 120.0,
                    "the key was written moments ago but the reported time is " +
                    skew.ToString("F1", CultureInfo.InvariantCulture) + "s away from DateTime.UtcNow (" +
                    value.ToString("o", CultureInfo.InvariantCulture) + " vs " +
                    now.ToString("o", CultureInfo.InvariantCulture) +
                    "); interpreting FILETIME as local time is off by the whole UTC offset");
                Harness.Report("skewSeconds=" + skew.ToString("F1", CultureInfo.InvariantCulture) +
                               " value=" + value.ToString("o", CultureInfo.InvariantCulture));
            });

            Harness.Run("L_T03_lastwrite_strictly_increases", R6, Suite, () =>
            {
                NotifyFixture.ResetTree();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Lwt", 1, RegistryValueKind.DWord);
                bool ok1 = RegistryNotify.TryGetLastWriteTimeUtc(out DateTime t1);
                Harness.Assert(ok1, "first TryGetLastWriteTimeUtc returned false on an existing key");

                Thread.Sleep(1500);
                bool unchangedOk = RegistryNotify.TryGetLastWriteTimeUtc(out DateTime unchanged);
                Harness.Assert(unchangedOk && unchanged == t1,
                    "the recorded key timestamp changed while no registry write occurred; current wall-clock time is not the key's last-write time");
                NotifyFixture.WriteValue(NotifyFixture.Status, "Lwt", 2, RegistryValueKind.DWord);
                bool ok2 = RegistryNotify.TryGetLastWriteTimeUtc(out DateTime t2);
                Harness.Assert(ok2, "second TryGetLastWriteTimeUtc returned false on an existing key");
                Harness.Assert(t2 > t1,
                    "the second read (" + t2.ToString("o", CultureInfo.InvariantCulture) +
                    ") was not strictly greater than the first (" + t1.ToString("o", CultureInfo.InvariantCulture) +
                    ") after a 1.5s gap");
                Harness.Report("t1=" + t1.ToString("o", CultureInfo.InvariantCulture) +
                               " t2=" + t2.ToString("o", CultureInfo.InvariantCulture));
            });

            Harness.Run("L_T04_lastwrite_delta_matches_wall_clock", R6, Suite, () =>
            {
                NotifyFixture.ResetTree();
                NotifyFixture.WriteValue(NotifyFixture.Status, "Lwt", 1, RegistryValueKind.DWord);
                bool ok1 = RegistryNotify.TryGetLastWriteTimeUtc(out DateTime t1);
                Harness.Assert(ok1, "first TryGetLastWriteTimeUtc returned false on an existing key");

                Thread.Sleep(1500);
                NotifyFixture.WriteValue(NotifyFixture.Status, "Lwt", 2, RegistryValueKind.DWord);
                bool ok2 = RegistryNotify.TryGetLastWriteTimeUtc(out DateTime t2);
                Harness.Assert(ok2, "second TryGetLastWriteTimeUtc returned false on an existing key");

                double delta = (t2 - t1).TotalSeconds;
                Harness.Assert(delta >= 1.0 && delta <= 3.0,
                    "two writes 1.5s apart produced a last-write delta of " +
                    delta.ToString("F3", CultureInfo.InvariantCulture) +
                    "s; expected 1.0..3.0s, so the 100-nanosecond FILETIME tick conversion is wrong");
                Harness.Report("deltaSeconds=" + delta.ToString("F3", CultureInfo.InvariantCulture) + " for a 1.5s wall-clock gap");
            });

            Harness.Run("L_T05_lastwrite_missing_key_false_default_no_create", R6, Suite, () =>
            {
                NotifyFixture.DeleteTree(NotifyFixture.Root);
                Harness.Precondition(!NotifyFixture.Exists(NotifyFixture.Status),
                    "evaluator fixture could not remove HKCU\\" + NotifyFixture.Status);

                DateTime value = DateTime.MaxValue;
                bool ok = true;
                string error = "";
                try { ok = RegistryNotify.TryGetLastWriteTimeUtc(out value); }
                catch (Exception ex) { error = ex.GetType().Name + ": " + ex.Message; }
                bool created = NotifyFixture.Exists(NotifyFixture.Status);

                Harness.Assert(error == "", "TryGetLastWriteTimeUtc threw " + error + " on a missing key");
                Harness.Assert(!ok,
                    "TryGetLastWriteTimeUtc returned true although HKCU\\" + NotifyFixture.Status + " does not exist");
                Harness.Assert(value == default,
                    "the out parameter was " + value.ToString("o", CultureInfo.InvariantCulture) +
                    " instead of default(DateTime) for a missing key");
                Harness.Assert(!created, "TryGetLastWriteTimeUtc created HKCU\\" + NotifyFixture.Status);
                Harness.Report("ok=false value=default keyCreated=false noException=true");
            });
        }
    }
}
