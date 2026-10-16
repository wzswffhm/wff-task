# Readiness probe for wfflab__wspawn-218. It never scores a candidate: it only
# answers whether this machine can host the task at all. A non-zero exit means
# the environment is INVALID, not that the candidate failed.
#
# NOTE: keep this file pure ASCII (Windows PowerShell 5.1 reads BOM-less files
# as ANSI, and a multi-byte character would corrupt the surrounding syntax).

[CmdletBinding()]
param(
    [string]$TaskRoot = ''
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($TaskRoot)) {
    $TaskRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
$TaskRoot = (Resolve-Path -LiteralPath $TaskRoot).Path

function Fail([string]$problem) {
    Write-Host "NOT READY: $problem"
    exit 1
}

# ---- platform: the contract only exists on a real Windows kernel ------------
if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    Fail 'the host platform is not Windows (Win32NT), so the wspawn contract cannot be graded here'
}
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail "Windows PowerShell 5.1 or newer is required, found $($PSVersionTable.PSVersion)"
}
Write-Host 'readiness: the host is a Windows kernel'

# ---- capability: pipes, the inherit flag, and a real child process ----------
# The graded contract is about handing object handles to a child, so the probe
# performs the same three primitives the evaluator will use: create an anonymous
# pipe, read its inherit flag back through the operating system, and start a
# child process that can report which pipe it received.
$probeSource = @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

public static class WSpawnReadinessProbe
{
    [DllImport("kernel32", SetLastError = true)]
    private static extern bool CreatePipe(out IntPtr readEnd, out IntPtr writeEnd, IntPtr attributes, uint size);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool SetHandleInformation(IntPtr handle, uint mask, uint flags);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool GetHandleInformation(IntPtr handle, out uint flags);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    private const uint HANDLE_FLAG_INHERIT = 0x00000001;

    public static string Run()
    {
        IntPtr readEnd, writeEnd;
        if (!CreatePipe(out readEnd, out writeEnd, IntPtr.Zero, 0))
            return "CreatePipe failed (error " + Marshal.GetLastWin32Error() + ")";

        string verdict;
        try
        {
            uint flags;
            if (!GetHandleInformation(writeEnd, out flags))
                return "GetHandleInformation failed (error " + Marshal.GetLastWin32Error() + ")";
            if ((flags & HANDLE_FLAG_INHERIT) != 0)
                return "a fresh pipe unexpectedly starts out inheritable";

            if (!SetHandleInformation(writeEnd, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT))
                return "SetHandleInformation could not set the inherit flag (error " + Marshal.GetLastWin32Error() + ")";
            if (!GetHandleInformation(writeEnd, out flags))
                return "GetHandleInformation failed after setting the flag";
            if ((flags & HANDLE_FLAG_INHERIT) == 0)
                return "the inherit flag did not stick";

            if (!SetHandleInformation(writeEnd, HANDLE_FLAG_INHERIT, 0))
                return "SetHandleInformation could not clear the inherit flag";
            if (!GetHandleInformation(writeEnd, out flags))
                return "GetHandleInformation failed after clearing the flag";
            if ((flags & HANDLE_FLAG_INHERIT) != 0)
                return "the inherit flag could not be cleared";

            verdict = "ok";
        }
        finally
        {
            CloseHandle(readEnd);
            CloseHandle(writeEnd);
        }

        try
        {
            using (Process child = Process.Start(new ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = "/c exit 7",
                UseShellExecute = false,
                CreateNoWindow = true,
            }))
            {
                child.WaitForExit(60000);
                if (child.ExitCode != 7)
                    return "a child process did not report its exit code";
            }
        }
        catch (Exception error)
        {
            return "a child process could not be started: " + error.Message;
        }

        return verdict;
    }
}
'@

try {
    Add-Type -TypeDefinition $probeSource -Language CSharp -ErrorAction Stop
}
catch {
    Fail "the handle capability probe could not be compiled: $($_.Exception.Message)"
}

$probeResult = [WSpawnReadinessProbe]::Run()
if ($probeResult -ne 'ok') {
    Fail "the handle inheritance capability probe failed: $probeResult"
}
Write-Host 'readiness: an anonymous pipe can be created, the inherit flag can be read back and cleared, and a child process exits with the code it was given'

# ---- interpreter and test dependencies -------------------------------------
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) { $python = (Get-Command python3 -ErrorAction SilentlyContinue) }
if (-not $python) {
    Fail 'no python interpreter is available on PATH'
}
& $python.Source -c "import pytest" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail 'the pytest package is not importable'
}

# ---- candidate workspace ----------------------------------------------------
$workspace = Join-Path $TaskRoot 'environment\workspace'
$packageInit = Join-Path (Join-Path $workspace 'wspawn') '__init__.py'
if (-not (Test-Path -LiteralPath $packageInit)) {
    Fail "the candidate package is missing: $packageInit"
}
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$workspace;$previousPythonPath"
& $python.Source -c "import wspawn" 2>&1 | Out-Null
$importExit = $LASTEXITCODE
$env:PYTHONPATH = $previousPythonPath
if ($importExit -ne 0) {
    Fail 'the candidate package cannot be imported'
}
Write-Host 'readiness: the candidate package is in place and importable'

# ---- isolation audit --------------------------------------------------------
# The image build only copies workspace/ into the agent container. Verify that
# assumption here as well, so a packaging mistake cannot silently expose the
# reference implementation or the hidden suite.
$leaked = Get-ChildItem -LiteralPath $workspace -Recurse -File -Force |
    Where-Object { $item = $_; $item.Name.ToLowerInvariant() -match 'oracle|golden|reference|hidden|rubric|solution|reward' }
if ($leaked) {
    foreach ($item in $leaked) { Write-Host "LEAK: $($item.FullName)" }
    Fail 'the agent workspace contains withheld material'
}

foreach ($withheld in @('C:\verifier', 'C:\solution')) {
    if (Test-Path -LiteralPath $withheld) {
        $resolved = (Resolve-Path -LiteralPath $withheld).Path
        if ($resolved.ToLowerInvariant().StartsWith($workspace.ToLowerInvariant())) {
            Fail "withheld root is inside the agent workspace: $resolved"
        }
    }
}

$machineName = $env:COMPUTERNAME
Write-Host "ready: $machineName / PowerShell $($PSVersionTable.PSVersion) / task root $TaskRoot"
Write-Host 'isolation: agent workspace is free of oracle, reference and hidden-suite material'
exit 0
