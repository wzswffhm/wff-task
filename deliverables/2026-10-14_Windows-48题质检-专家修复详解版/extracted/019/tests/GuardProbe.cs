using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Web.Script.Serialization;

internal static class GuardProbe
{
    private static int Main(string[] args)
    {
        if (args.Length == 2 && args[0] == "--child")
        {
            Console.WriteLine("READY"); Console.Out.Flush();
            for (;;) { File.WriteAllText(args[1], DateTime.UtcNow.Ticks.ToString()); Thread.Sleep(100); }
        }
        try
        {
            bool readDenied = false, writeDenied = false, testsDenied = false;
            try { File.ReadAllText("C:\\tests\\Verifier.cs"); }
            catch (UnauthorizedAccessException) { testsDenied = true; }
            try { File.ReadAllText("C:\\logs\\verifier\\private-canary.txt"); }
            catch (UnauthorizedAccessException) { readDenied = true; }
            try { File.WriteAllText("C:\\logs\\verifier\\tampered.txt", "not allowed"); }
            catch (UnauthorizedAccessException) { writeDenied = true; }
            if (!readDenied || !writeDenied || !testsDenied) return 11;
            if (String.IsNullOrEmpty(File.ReadAllText("C:\\testbed\\build.ps1"))) return 12;
            string heartbeat = Path.Combine("C:\\agenttmp", "guard-heartbeat-" + Guid.NewGuid().ToString("N"));
            var info = new ProcessStartInfo(typeof(GuardProbe).Assembly.Location, "--child \"" + heartbeat + "\"");
            info.UseShellExecute = false; info.RedirectStandardOutput = true; info.CreateNoWindow = true;
            using (Process child = Process.Start(info))
            {
                var ready = child.StandardOutput.ReadLineAsync();
                if (!ready.Wait(5000) || ready.Result != "READY") return 13;
                Console.WriteLine(new JavaScriptSerializer().Serialize(new { status = "ok", published = 1,
                    read_denied = readDenied, write_denied = writeDenied, tests_denied = testsDenied,
                    candidate_sid = System.Security.Principal.WindowsIdentity.GetCurrent().User.Value, child_pid = child.Id, heartbeat = heartbeat }));
            }
            return 0;
        }
        catch (Exception e) { Console.Error.WriteLine(e.GetType().Name); return 14; }
    }
}
