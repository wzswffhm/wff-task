using System;
using System.Diagnostics;
using System.Threading;
using LiteMonitor.src.Core;
using Microsoft.Win32;

namespace Harbor.Evaluator
{
    /// <summary>
    /// FAIL_TO_PASS checks for the second half of the iteration: StatusMirror.StartRefresher
    /// must stop being a 200 ms Generation-comparing poller and become an event-driven
    /// subscription built on top of RegistryNotify.Watch.
    ///
    /// Every check below is deterministically red on the frozen baseline, because the
    /// legacy poller only reacts when the numeric value of "Generation" moves.
    /// </summary>
    public static class IntegrationChecks
    {
        private const string Suite = "fail_to_pass";
        private const string R7 = "R7_mirror_refresher_integration";

        private static long PublishFreshMirror()
        {
            StatusMirror.Purge();
            NotifyFixture.DeleteTree(NotifyFixture.Root);
            bool published = StatusMirror.Publish(
                new StatusSnapshot(true, 3, "DeepOcean_Blue", 12345678901L));
            Harness.Precondition(published && NotifyFixture.Exists(NotifyFixture.Status),
                "the baseline StatusMirror.Publish could not materialise HKCU\\" + NotifyFixture.Status);
            long generation = StatusMirror.ReadGeneration();
            Harness.Precondition(generation >= 1,
                "the baseline StatusMirror.Publish did not stamp a Generation (got " + generation + ")");
            return generation;
        }

        private static IDisposable StartRefresher(CallbackSink sink)
        {
            string error = "";
            IDisposable? handle = null;
            try { handle = StatusMirror.StartRefresher(sink.OnChange); }
            catch (Exception ex) { error = ex.GetType().Name + ": " + ex.Message; }
            Harness.Assert(error == "", "StatusMirror.StartRefresher threw " + error);
            Harness.Assert(handle is not null,
                "StatusMirror.StartRefresher returned null although HKCU\\" + NotifyFixture.Status + " exists");
            Thread.Sleep(600);
            sink.Reset();
            return handle!;
        }

        public static void All()
        {
            Harness.Run("I_T1_refresher_fires_for_a_value_that_is_not_generation", R7, Suite, () =>
            {
                long generation = PublishFreshMirror();
                CallbackSink sink = new CallbackSink();
                IDisposable handle = StartRefresher(sink);
                try
                {
                    NotifyFixture.WriteValue(NotifyFixture.Status, StatusMirror.ThemeNameValueName,
                        "MatrixGreen_Terminal", RegistryValueKind.String);
                    int fired = NotifyFixture.WaitUntil(() => sink.Count > 0, 2500);
                    long generationAfter = StatusMirror.ReadGeneration();
                    Harness.Assert(generationAfter == generation,
                        "fixture invariant broken: Generation moved from " + generation + " to " + generationAfter);
                    Harness.Assert(fired >= 0,
                        "rewriting " + StatusMirror.ThemeNameValueName + " produced no callback within 2.5s while Generation stayed at " +
                        generation + "; the refresher is still only comparing the Generation number instead of watching value writes");

                    // Windows does not emit REG_NOTIFY_CHANGE_LAST_SET for a
                    // byte-for-byte same-kind rewrite.  Keep the logical theme value
                    // identical while changing only the registry value kind; this is
                    // an observable write and still distinguishes the event-driven
                    // path from a poller that only compares Generation or the value.
                    sink.Reset();
                    NotifyFixture.WriteValue(NotifyFixture.Status, StatusMirror.ThemeNameValueName,
                        "MatrixGreen_Terminal", RegistryValueKind.ExpandString);
                    int sameValue = NotifyFixture.WaitUntil(() => sink.Count > 0, 2500);
                    Harness.Assert(sameValue >= 0,
                        "rewriting the same mirror value produced no callback; " +
                        "StartRefresher is behaving like a value-difference poller");
                    Harness.Report("themeRewritten=true generationUnchanged=" + generation +
                                   " callbackIn=" + NotifyFixture.Ms(fired) +
                                   " sameValueCallbackIn=" + NotifyFixture.Ms(sameValue));
                }
                finally { try { handle.Dispose(); } catch { } }
            });

            Harness.Run("I_T2_refresher_rearms_for_consecutive_mirror_writes", R7, Suite, () =>
            {
                long generation = PublishFreshMirror();
                CallbackSink sink = new CallbackSink();
                IDisposable handle = StartRefresher(sink);
                try
                {
                    string[] themes = { "MatrixGreen_Terminal", "SolarAmber_Warm", "Monokai_Pro" };
                    string latencies = "";
                    foreach (string theme in themes)
                    {
                        sink.Reset();
                        NotifyFixture.WriteValue(NotifyFixture.Status, StatusMirror.ThemeNameValueName,
                            theme, RegistryValueKind.String);
                        int fired = NotifyFixture.WaitUntil(() => sink.Count > 0, 2500);
                        long generationNow = StatusMirror.ReadGeneration();
                        Harness.Assert(generationNow == generation,
                            "fixture invariant broken: Generation moved from " + generation + " to " + generationNow);
                        Harness.Assert(fired >= 0,
                            "rewriting " + StatusMirror.ThemeNameValueName + " to \"" + theme + "\" produced no callback within 2.5s while Generation stayed at " +
                            generation + "; the refresher must keep reporting every mirror write, not only the first one after it starts");
                        latencies += (latencies.Length == 0 ? "" : " ") + NotifyFixture.Ms(fired);
                    }

                    Harness.Report("consecutiveMirrorWrites=" + themes.Length + " generationUnchanged=" + generation +
                                   " callbackIn=" + latencies);
                }
                finally { try { handle.Dispose(); } catch { } }
            });

            Harness.Run("I_T3_refresher_scopes_to_the_mirror_key_and_stops_on_dispose", R7, Suite, () =>
            {
                PublishFreshMirror();
                CallbackSink sink = new CallbackSink();
                IDisposable handle = StartRefresher(sink);
                try
                {
                    NotifyFixture.WriteValue(NotifyFixture.Status, StatusMirror.ThemeNameValueName,
                        "Monokai_Pro", RegistryValueKind.String);
                    int alive = NotifyFixture.WaitUntil(() => sink.Count > 0, 2500);
                    Harness.Assert(alive >= 0,
                        "the refresher never reported the mirror write, so the scoping and Dispose assertions below would be vacuous");

                    sink.Reset();
                    NotifyFixture.WriteValue(NotifyFixture.Sub, "NestedProbe", 9, RegistryValueKind.DWord);
                    int leak = NotifyFixture.WaitUntil(() => sink.Count > 0, 1200);
                    int nested = sink.Count;
                    Harness.Assert(leak < 0 && nested == 0,
                        "the refresher must watch only " + StatusMirror.StatusSubKey + " itself; a value written into HKCU\\" +
                        NotifyFixture.Sub + " produced " + nested + " callback(s)");

                    sink.Reset();
                    string error = "";
                    long d1 = -1, d2 = -1;
                    var sw = Stopwatch.StartNew();
                    try { handle.Dispose(); d1 = sw.ElapsedMilliseconds; }
                    catch (Exception ex) { error = ex.GetType().Name + ": " + ex.Message; }
                    sw.Restart();
                    try { handle.Dispose(); d2 = sw.ElapsedMilliseconds; }
                    catch (Exception ex) { error += " / second call: " + ex.GetType().Name + ": " + ex.Message; }

                    NotifyFixture.WriteValue(NotifyFixture.Status, StatusMirror.ThemeNameValueName,
                        "SolarAmber_Warm", RegistryValueKind.String);
                    Thread.Sleep(1200);
                    int afterDispose = sink.Count;

                    Harness.Assert(error == "", "disposing the refresher threw " + error);
                    Harness.Assert(d1 >= 0 && d1 < 2000 && d2 >= 0 && d2 < 2000,
                        "Dispose must be idempotent and return in under 2s; measured " + d1 + "ms then " + d2 + "ms");
                    Harness.Assert(afterDispose == 0,
                        "Dispose returned but " + afterDispose + " further callback(s) arrived");
                    Harness.Report("aliveIn=" + NotifyFixture.Ms(alive) + " nestedCallbacks=" + nested +
                                   " dispose1Ms=" + d1 + " dispose2Ms=" + d2 + " callbacksAfterDispose=" + afterDispose);
                }
                finally { try { handle.Dispose(); } catch { } }
            });

            Harness.Run("I_T4_refresher_survives_a_full_purge_and_republish_cycle", R7, Suite, () =>
            {
                long generation = PublishFreshMirror();
                CallbackSink sink = new CallbackSink();
                IDisposable handle = StartRefresher(sink);
                try
                {
                    NotifyFixture.WriteValue(NotifyFixture.Status, StatusMirror.ThemeNameValueName,
                        "Gruvbox_Earth", RegistryValueKind.String);
                    int alive = NotifyFixture.WaitUntil(() => sink.Count > 0, 2500);
                    Harness.Assert(alive >= 0,
                        "the refresher never reported a mirror write, so the purge/republish assertions below would be vacuous");

                    // Purge() drops the whole HKCU\Software\LiteMonitor tree and a later Publish() brings the
                    // mirror back with a fresh Generation. The consumer still holds the SAME subscription handle,
                    // so it must keep working across that cycle.
                    StatusMirror.Purge();
                    Harness.Precondition(!NotifyFixture.Exists(NotifyFixture.Root),
                        "StatusMirror.Purge did not remove HKCU\\" + NotifyFixture.Root);
                    Thread.Sleep(400);
                    bool published = StatusMirror.Publish(new StatusSnapshot(false, 5, "Nord_Frost", 4242L));
                    Harness.Precondition(published && NotifyFixture.Exists(NotifyFixture.Status),
                        "StatusMirror.Publish could not bring the mirror back after Purge");
                    Thread.Sleep(900);
                    sink.Reset();

                    NotifyFixture.WriteValue(NotifyFixture.Status, StatusMirror.ThemeNameValueName,
                        "Nord_Frost_Late", RegistryValueKind.String);
                    int fired = NotifyFixture.WaitUntil(() => sink.Count > 0, 6000);
                    Harness.Assert(fired >= 0,
                        "after a full Purge + Publish cycle the refresher stayed silent for 6s even though " +
                        StatusMirror.ThemeNameValueName + " was rewritten; the subscription handed out by StartRefresher " +
                        "must survive the mirror key being removed and recreated");
                    Harness.Report("aliveBeforePurgeIn=" + NotifyFixture.Ms(alive) +
                                   " generationBeforePurge=" + generation +
                                   " generationAfterRepublish=" + StatusMirror.ReadGeneration() +
                                   " callbackAfterRepublishIn=" + NotifyFixture.Ms(fired));
                }
                finally { try { handle.Dispose(); } catch { } }
            });
        }
    }
}
