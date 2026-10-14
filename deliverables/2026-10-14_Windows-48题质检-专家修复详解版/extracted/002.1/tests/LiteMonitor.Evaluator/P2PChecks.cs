using System;
using System.IO;
using LiteMonitor;
using LiteMonitor.src.Core;
using Microsoft.Win32;

namespace Harbor.Evaluator
{
    public static class P2PChecks
    {
        private const string Rubric = "P2P_regression_guard";
        private const string Suite = "pass_to_pass";
        public static void All()
        {
            Harness.Run("P2P_T7_status_mirror_publish_read_purge", Rubric, Suite, () =>

            {

                PurgeEverything();



                var snapshot = new StatusSnapshot(true, 5, "Dracula_Vampire", 9876543210L);

                Harness.Assert(StatusMirror.Publish(snapshot),

                    "StatusMirror.Publish returned false on a clean machine");



                Harness.Assert(StatusMirror.TryRead(out StatusSnapshot read),

                    "StatusMirror.TryRead returned false right after a successful Publish");

                Harness.AssertEqual(read.AutoStartEnabled, snapshot.AutoStartEnabled, "AutoStartEnabled round-trip");

                Harness.AssertEqual(read.MonitorItemCount, snapshot.MonitorItemCount, "MonitorItemCount round-trip");

                Harness.AssertEqual(read.ThemeName, snapshot.ThemeName, "ThemeName round-trip");

                Harness.AssertEqual(read.TrafficUploadBytes, snapshot.TrafficUploadBytes, "TrafficUploadBytes round-trip");



                long first = StatusMirror.ReadGeneration();

                Harness.Assert(first >= 1, $"the first Publish must stamp Generation >= 1, got {first}");

                Harness.Assert(StatusMirror.Publish(snapshot), "second Publish returned false");

                long second = StatusMirror.ReadGeneration();

                Harness.Assert(second > first, $"Generation must strictly increase across publishes ({first} -> {second})");



                StatusMirror.Purge();

                Harness.Assert(!StatusMirror.TryRead(out _),

                    "StatusMirror.TryRead still succeeded after Purge removed HKCU\\" + StatusMirror.RootSubKey);

                Harness.AssertEqual(StatusMirror.ReadGeneration(), -1L, "ReadGeneration after Purge");

            });

        }



        internal static void CleanupTrafficFiles()

        {

            try { TrafficLogger.ClearHistory(); } catch { }

            foreach (string name in new[] { "TrafficHistory.json", "TrafficHistory.json.bak", "TrafficHistory.json.tmp" })

            {

                try

                {

                    string p = Path.Combine(AppContext.BaseDirectory, name);

                    if (File.Exists(p)) File.Delete(p);

                }

                catch { }

            }

        }



        /// <summary>

        /// Removes every piece of machine state this suite can create, so a later suite

        /// (and the residue audit) starts from a known-empty baseline.

        /// </summary>

        internal static void PurgeEverything()

        {

            try { SettingsHelper.DeleteStoredSettings(); } catch { }

            try { StatusMirror.Purge(); } catch { }

            try

            {

                using RegistryKey baseKey = Native.OpenCurrentUser64();

                baseKey.DeleteSubKeyTree(StatusMirror.RootSubKey, throwOnMissingSubKey: false);

            }

            catch { }

            foreach (string name in new[] { "settings.json", "settings.json.bak", "settings.json.tmp" })

            {

                try

                {

                    string p = Path.Combine(AppContext.BaseDirectory, name);

                    if (File.Exists(p)) File.Delete(p);

                }

                catch { }

            }

            CleanupTrafficFiles();

        }

    }

}
