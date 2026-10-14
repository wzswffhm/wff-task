using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Harbor.Evaluator
{
    /// <summary>
    /// Emits the machine-readable evaluator verdict (evaluator_results.json) that
    /// tests/aggregate_results.ps1 folds into results/result.json.
    /// Everything here is derived from executed checks - no judge, no heuristics.
    /// </summary>
    public static class Reporter
    {
        public const string EvaluatorVersion = "2.1.1";
        public const string EvaluatorName = "LiteMonitor.Evaluator";

        public static string TaskId = "windows-d4-litemonitor-001";
        public static string TaskVersion = "2.1.1";
        public static string RunId = "";
        public static string Suite = "all";
        public static string TargetRepoOut = "";
        public static string RepoCommit = "";
        public static string StartedAtUtc = "";
        public static string FinishedAtUtc = "";
        public static double DurationSeconds = 0.0;
        public static int ResidueCount = -1;
        public static readonly List<string> ResidueDetail = new();

        public static string ComputeTargetAssemblyHash()
        {
            foreach (string candidate in new[]
                     {
                         string.IsNullOrEmpty(TargetRepoOut) ? null : Path.Combine(TargetRepoOut, "LiteMonitor.dll"),
                         Path.Combine(AppContext.BaseDirectory, "LiteMonitor.dll")
                     })
            {
                try
                {
                    if (candidate is not null && File.Exists(candidate))
                    {
                        using var sha = SHA256.Create();
                        using var fs = File.OpenRead(candidate);
                        return "sha256:" + Convert.ToHexString(sha.ComputeHash(fs)).ToLowerInvariant();
                    }
                }
                catch { }
            }
            return "sha256:<unavailable>";
        }

        public static void Write(string path)
        {
            string? dir = Path.GetDirectoryName(Path.GetFullPath(path));
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir!);

            var options = new JsonWriterOptions { Indented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping };
            using var stream = File.Create(path);
            using var writer = new Utf8JsonWriter(stream, options);

            writer.WriteStartObject();
            writer.WriteString("evaluator_name", EvaluatorName);
            writer.WriteString("evaluator_version", EvaluatorVersion);
            writer.WriteString("task_id", TaskId);
            writer.WriteString("task_version", TaskVersion);
            writer.WriteString("run_id", RunId);
            writer.WriteString("suite_requested", Suite);
            writer.WriteString("started_at_utc", StartedAtUtc);
            writer.WriteString("finished_at_utc", FinishedAtUtc);
            writer.WriteNumber("duration_seconds", DurationSeconds);
            writer.WriteString("target_repo_out", TargetRepoOut);
            writer.WriteString("target_assembly_sha256", ComputeTargetAssemblyHash());
            writer.WriteString("repo_commit", RepoCommit);

            writer.WritePropertyName("environment");
            WriteEnvironment(writer);

            writer.WritePropertyName("checks");
            writer.WriteStartArray();
            foreach (CheckResult r in Harness.Results)
            {
                writer.WriteStartObject();
                writer.WriteString("id", r.Id);
                writer.WriteString("rubric_id", r.Rubric);
                writer.WriteString("suite", r.Suite);
                writer.WriteString("status", r.Status);
                writer.WriteBoolean("passed", r.Passed);
                writer.WriteNumber("seconds", r.Seconds);
                writer.WriteString("detail", Redact(r.Detail));
                writer.WriteEndObject();
            }
            writer.WriteEndArray();

            writer.WritePropertyName("rubric_scores");
            writer.WriteStartObject();
            foreach (string rubric in Harness.Results.Select(r => r.Rubric).Distinct().OrderBy(x => x, StringComparer.Ordinal))
            {
                List<CheckResult> items = Harness.Results.Where(r => r.Rubric == rubric).ToList();
                writer.WritePropertyName(rubric);
                writer.WriteStartObject();
                writer.WriteNumber("checks", items.Count);
                writer.WriteNumber("passed", items.Count(r => r.Passed));
                writer.WriteNumber("invalid", items.Count(r => r.Status == "invalid"));
                writer.WriteNumber("score", items.Count > 0 && items.All(r => r.Passed) ? 1.0 : 0.0);
                writer.WriteEndObject();
            }
            writer.WriteEndObject();

            writer.WritePropertyName("suite_summary");
            writer.WriteStartObject();
            foreach (string s in new[] { "fail_to_pass", "pass_to_pass", "system_state" })
            {
                List<CheckResult> items = Harness.Results.Where(r => r.Suite == s).ToList();
                writer.WritePropertyName(s);
                writer.WriteStartObject();
                writer.WriteNumber("total", items.Count);
                writer.WriteNumber("passed", items.Count(r => r.Passed));
                writer.WriteNumber("failed", items.Count(r => !r.Passed && r.Status == "fail"));
                writer.WriteNumber("invalid", items.Count(r => r.Status == "invalid"));
                writer.WriteEndObject();
            }
            writer.WriteEndObject();

            writer.WritePropertyName("summary");
            writer.WriteStartObject();
            writer.WriteNumber("total", Harness.Results.Count);
            writer.WriteNumber("passed", Harness.Results.Count(r => r.Passed));
            writer.WriteNumber("failed", Harness.Results.Count(r => !r.Passed && r.Status == "fail"));
            writer.WriteNumber("invalid", Harness.Results.Count(r => r.Status == "invalid"));
            writer.WriteEndObject();

            writer.WriteNumber("residue_count", ResidueCount);
            writer.WritePropertyName("residue_detail");
            writer.WriteStartArray();
            foreach (string line in ResidueDetail) writer.WriteStringValue(Redact(line));
            writer.WriteEndArray();

            writer.WriteEndObject();
            writer.Flush();
        }

        private static void WriteEnvironment(Utf8JsonWriter writer)
        {
            writer.WriteStartObject();
            writer.WriteString("os_description", RuntimeInformation.OSDescription);
            writer.WriteString("os_architecture", RuntimeInformation.OSArchitecture.ToString());
            writer.WriteString("process_architecture", RuntimeInformation.ProcessArchitecture.ToString());
            writer.WriteString("framework_description", RuntimeInformation.FrameworkDescription);
            writer.WriteBoolean("is_windows", RuntimeInformation.IsOSPlatform(OSPlatform.Windows));
            writer.WriteString("os_version", Environment.OSVersion.Version.ToString());
            writer.WriteString("locale", CultureInfo.CurrentCulture.Name);
            writer.WriteString("ui_locale", CultureInfo.CurrentUICulture.Name);
            writer.WriteString("code_page_output", Console.OutputEncoding.WebName);
            writer.WriteString("time_zone", TimeZoneInfo.Local.Id);
            writer.WriteString("machine_name", Environment.MachineName);
            writer.WriteString("user_domain_name", Environment.UserDomainName);
            writer.WriteBoolean("is_64bit_process", Environment.Is64BitProcess);
            writer.WriteBoolean("user_is_administrator", IsAdministrator());
            writer.WriteEndObject();
        }

        private static bool IsAdministrator()
        {
            try
            {
                using var identity = System.Security.Principal.WindowsIdentity.GetCurrent();
                var principal = new System.Security.Principal.WindowsPrincipal(identity);
                return principal.IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
            }
            catch { return false; }
        }

        private static readonly string[] SensitiveFragments =
        {
            "sk-", "api_key", "apikey", "authorization", "bearer ", "password", "pwd=", "token="
        };

        /// <summary>
        /// Best-effort redaction so logs and result files can be shipped as evidence.
        /// </summary>
        private static string Redact(string? text)
        {
            if (string.IsNullOrEmpty(text)) return text ?? "";
            string result = text!;
            string lower = result.ToLowerInvariant();
            foreach (string fragment in SensitiveFragments)
            {
                if (lower.Contains(fragment, StringComparison.Ordinal)) return "[REDACTED]";
            }
            return result;
        }
    }
}
