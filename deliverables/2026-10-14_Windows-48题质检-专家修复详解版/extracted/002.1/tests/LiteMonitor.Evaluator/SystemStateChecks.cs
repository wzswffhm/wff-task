using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using LiteMonitor.src.Core;
using Microsoft.Win32;

namespace Harbor.Evaluator
{
    /// <summary>
    /// SYSTEM_STATE suite - proves the task's footprint is real machine state and that it
    /// is fully removable. These checks are deliberately independent of RegistryNotify:
    /// they must also pass on the frozen baseline, where the notify contract still throws.
    ///
    /// All checks are required PASS_TO_PASS cases.
    /// </summary>
    public static class SystemStateChecks
    {
        private const string Rubric = "SS_system_state";
        private const string Suite = "system_state";

        public static void All()
        {
            Harness.Run("SS_T1_mirror_is_machine_state_visible_from_a_second_process", Rubric, Suite, () =>
            {
                Harness.PurgeStoreState();
                var snapshot = new StatusSnapshot(true, 11, "DeepOcean_Blue", 13579246801L);
                Harness.Assert(StatusMirror.Publish(snapshot),
                    "StatusMirror.Publish returned false; the fixture could not create the mirror");

                (int exitCode, string stdout) = Native.RunSelf("--mode=mirrorchild", 60000);
                Harness.Assert(exitCode == 0,
                    $"the second process could not read the mirror back (exitCode={exitCode}): {Tail(stdout)}");
                Harness.Assert(stdout.Contains("MIRRORCHILD:OK", StringComparison.Ordinal),
                    "the second process did not report MIRRORCHILD:OK");

                Harness.AssertEqual(Program.FindChildField(stdout, "SchemaVersion="), StatusMirror.MirrorSchemaVersion,
                    "SchemaVersion as seen by a second OS process");
                Harness.AssertEqual(Program.FindChildField(stdout, "AutoStartEnabled="), "1",
                    "AutoStartEnabled as seen by a second OS process");
                Harness.AssertEqual(Program.FindChildField(stdout, "MonitorItemCount="), "11",
                    "MonitorItemCount as seen by a second OS process");
                Harness.AssertEqual(Program.FindChildField(stdout, "ThemeName="), "DeepOcean_Blue",
                    "ThemeName as seen by a second OS process");
                Harness.AssertEqual(Program.FindChildField(stdout, "TrafficUploadBytes="), "13579246801",
                    "TrafficUploadBytes as seen by a second OS process");
            });

            Harness.Run("SS_T2_mirror_value_kinds_match_the_documented_layout", Rubric, Suite, () =>
            {
                Harness.PurgeStoreState();
                Harness.Assert(StatusMirror.Publish(new StatusSnapshot(false, 4, "Monokai_Pro", 42L)),
                    "StatusMirror.Publish returned false; the fixture could not create the mirror");

                (int exitCode, string stdout) = Native.RunSelf("--mode=mirrorchild", 60000);
                Harness.Assert(exitCode == 0, $"the second process could not read the mirror back (exitCode={exitCode})");

                var expected = new Dictionary<string, string>(StringComparer.Ordinal)
                {
                    [StatusMirror.SchemaVersionValueName] = "String",
                    [StatusMirror.GenerationValueName] = "QWord",
                    [StatusMirror.AutoStartValueName] = "DWord",
                    [StatusMirror.MonitorItemCountValueName] = "DWord",
                    [StatusMirror.ThemeNameValueName] = "String",
                    [StatusMirror.TrafficUploadBytesValueName] = "QWord",
                };
                foreach (KeyValuePair<string, string> pair in expected)
                {
                    Harness.AssertEqual(Program.FindChildField(stdout, "Kind_" + pair.Key + "="), pair.Value,
                        $"registry value kind of {pair.Key}");
                }
                Harness.AssertEqual(Program.FindChildField(stdout, "ValueCount="),
                    expected.Count.ToString(CultureInfo.InvariantCulture), "value count in the mirror key");
            });

            Harness.Run("SS_T3_purge_removes_the_whole_registry_footprint", Rubric, Suite, () =>
            {
                Harness.PurgeStoreState();
                Harness.Assert(StatusMirror.Publish(new StatusSnapshot(true, 1, "SolarAmber_Warm", 1L)),
                    "StatusMirror.Publish returned false; the fixture could not create the mirror");
                using (RegistryKey baseKey = Native.OpenCurrentUser64())
                using (RegistryKey root = baseKey.CreateSubKey(StatusMirror.RootSubKey, writable: true)!)
                {
                    root.CreateSubKey("ScratchSub", writable: false).Dispose();
                }
                Harness.Precondition(Native.RootKeyExists(),
                    "the fixture could not materialise HKCU\\" + StatusMirror.RootSubKey);

                StatusMirror.Purge();
                Harness.Assert(!Native.RootKeyExists(),
                    "HKCU\\" + StatusMirror.RootSubKey + " survived StatusMirror.Purge()");

                (int exitCode, string stdout) = Native.RunSelf("--mode=mirrorchild", 60000);
                Harness.Assert(exitCode == 4 && stdout.Contains("MIRRORCHILD:MISSING", StringComparison.Ordinal),
                    $"a second OS process still sees the mirror after Purge (exitCode={exitCode}): {Tail(stdout)}");
            });

            Harness.Run("SS_T4_registry_state_does_not_accumulate_across_cycles", Rubric, Suite, () =>
            {
                for (int cycle = 0; cycle < 3; cycle++)
                {
                    Harness.PurgeStoreState();
                    Harness.Assert(StatusMirror.Publish(new StatusSnapshot(true, cycle, "CyberBlue_Neon", cycle)),
                        $"Publish returned false on cycle {cycle}");
                }

                using RegistryKey baseKey = Native.OpenCurrentUser64();
                using RegistryKey? root = baseKey.OpenSubKey(StatusMirror.RootSubKey, writable: false);
                Harness.Precondition(root is not null, "the fixture could not materialise the mirror root");
                string[] subKeys = root!.GetSubKeyNames();
                Harness.AssertEqual(subKeys.Length, 1, "subkey count under HKCU\\" + StatusMirror.RootSubKey);
                Harness.AssertEqual(subKeys[0], "Status", "the only subkey under the mirror root");

                using RegistryKey? status = baseKey.OpenSubKey(StatusMirror.StatusSubKey, writable: false);
                Harness.Precondition(status is not null, "the fixture could not materialise the mirror key");
                Harness.AssertEqual(status!.ValueCount, 6, "value count after three purge/publish cycles");
                Harness.AssertEqual(StatusMirror.ReadGeneration(), 1L,
                    "Generation must restart from 1 after a Purge, not accumulate across cycles");

                Harness.PurgeStoreState();
            });

            Harness.Run("SS_T5_application_directory_holds_no_task_residue", Rubric, Suite, () =>
            {
                P2PChecks.PurgeEverything();
                string dir = AppContext.BaseDirectory;
                List<string> leftovers = new List<string>();
                foreach (string name in new[]
                         {
                             "settings.json", "settings.json.bak", "settings.json.tmp",
                             "TrafficHistory.json", "TrafficHistory.json.bak", "TrafficHistory.json.tmp"
                         })
                {
                    string p = Path.Combine(dir, name);
                    if (File.Exists(p)) leftovers.Add(name);
                }
                Harness.Assert(leftovers.Count == 0,
                    "the application directory still holds task residue: " + string.Join(", ", leftovers));

                string[] stray = Directory.Exists(dir)
                    ? Directory.EnumerateFiles(dir, "*.tmp", SearchOption.TopDirectoryOnly).ToArray()
                    : Array.Empty<string>();
                Harness.AssertEqual(stray.Length, 0, "stray *.tmp files in " + dir);
            });
        }

        private static string Tail(string text)
        {
            if (string.IsNullOrEmpty(text)) return "<empty>";
            return text.Substring(Math.Max(0, text.Length - 300)).Replace('\r', ' ').Replace('\n', ' ');
        }
    }
}
