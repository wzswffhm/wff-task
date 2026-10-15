# Readiness probe for wfflab__wcancel-219. It never scores a candidate: it only
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
    Fail 'the host platform is not Windows (Win32NT), so the wcancel contract cannot be graded here'
}
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail "Windows PowerShell 5.1 or newer is required, found $($PSVersionTable.PSVersion)"
}
Write-Host 'readiness: the host is a Windows kernel'

# ---- capability: a cancellable pending request ------------------------------
# The graded contract is about stopping exactly one pending request, so the
# probe performs the same primitives the evaluator will use: create a named pipe
# opened for overlapped I/O, issue a read that cannot complete (nothing has been
# written), and confirm that the kernel reports a pending request and that
# cancelling that one request surfaces as an aborted operation.
$probeSource = @'
using System;
using System.Runtime.InteropServices;

public static class WCancelReadinessProbe
{
    [StructLayout(LayoutKind.Sequential)]
    private struct OVERLAPPED
    {
        public IntPtr Internal;
        public IntPtr InternalHigh;
        public uint Offset;
        public uint OffsetHigh;
        public IntPtr hEvent;
    }

    [DllImport("kernel32", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateNamedPipeW(string name, uint openMode, uint pipeMode,
        uint maxInstances, uint outBuffer, uint inBuffer, uint timeout, IntPtr securityAttributes);

    [DllImport("kernel32", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateFileW(string name, uint desiredAccess, uint shareMode,
        IntPtr securityAttributes, uint creationDisposition, uint flags, IntPtr template);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool ReadFile(IntPtr handle, byte[] buffer, uint toRead,
        out uint read, ref OVERLAPPED overlapped);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool CancelIoEx(IntPtr handle, ref OVERLAPPED overlapped);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool GetOverlappedResult(IntPtr handle, ref OVERLAPPED overlapped,
        out uint transferred, bool wait);

    [DllImport("kernel32", SetLastError = true)]
    private static extern IntPtr CreateEventW(IntPtr attributes, bool manualReset,
        bool initialState, string name);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    private const uint PIPE_ACCESS_DUPLEX = 0x00000003;
    private const uint FILE_FLAG_OVERLAPPED = 0x40000000;
    private const uint GENERIC_READ = 0x80000000;
    private const uint GENERIC_WRITE = 0x40000000;
    private const uint OPEN_EXISTING = 3;
    private const int ERROR_IO_PENDING = 997;
    private const int ERROR_OPERATION_ABORTED = 995;
    private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

    public static string Run()
    {
        string name = @"\\.\pipe\wcancel-readiness-" + Guid.NewGuid().ToString("N");
        IntPtr server = CreateNamedPipeW(name, PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED, 0,
            1, 65536, 65536, 0, IntPtr.Zero);
        if (server == INVALID_HANDLE_VALUE)
            return "CreateNamedPipeW failed (error " + Marshal.GetLastWin32Error() + ")";

        IntPtr client = CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, IntPtr.Zero,
            OPEN_EXISTING, FILE_FLAG_OVERLAPPED, IntPtr.Zero);
        if (client == INVALID_HANDLE_VALUE)
        {
            CloseHandle(server);
            return "CreateFileW on the probe pipe failed (error " + Marshal.GetLastWin32Error() + ")";
        }

        IntPtr evt = CreateEventW(IntPtr.Zero, true, false, null);
        if (evt == IntPtr.Zero)
        {
            CloseHandle(client);
            CloseHandle(server);
            return "CreateEventW failed (error " + Marshal.GetLastWin32Error() + ")";
        }

        string verdict = "ok";
        try
        {
            OVERLAPPED ov = new OVERLAPPED();
            ov.hEvent = evt;
            byte[] buffer = new byte[64];
            uint read;
            bool ok = ReadFile(server, buffer, 64, out read, ref ov);
            int pending = Marshal.GetLastWin32Error();
            if (ok || pending != ERROR_IO_PENDING)
            {
                verdict = "a read on an empty overlapped pipe did not go pending (ok=" + ok
                    + ", error=" + pending + ")";
                return verdict;
            }

            if (!CancelIoEx(server, ref ov))
            {
                verdict = "CancelIoEx failed (error " + Marshal.GetLastWin32Error() + ")";
                return verdict;
            }

            uint transferred;
            ok = GetOverlappedResult(server, ref ov, out transferred, true);
            int terminal = Marshal.GetLastWin32Error();
            if (ok || terminal != ERROR_OPERATION_ABORTED)
            {
                verdict = "a cancelled request did not report ERROR_OPERATION_ABORTED (ok=" + ok
                    + ", error=" + terminal + ")";
                return verdict;
            }
        }
        finally
        {
            CloseHandle(evt);
            CloseHandle(client);
            CloseHandle(server);
        }

        return verdict;
    }
}
'@

try {
    Add-Type -TypeDefinition $probeSource -Language CSharp -ErrorAction Stop
}
catch {
    Fail "the cancellation capability probe could not be compiled: $($_.Exception.Message)"
}

$probeResult = [WCancelReadinessProbe]::Run()
if ($probeResult -ne 'ok') {
    Fail "the overlapped-I/O cancellation capability probe failed: $probeResult"
}
Write-Host 'readiness: a named pipe can be opened for overlapped I/O, an empty read goes pending, and cancelling that one request surfaces as an aborted operation'

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
$packageInit = Join-Path (Join-Path $workspace 'wcancel') '__init__.py'
if (-not (Test-Path -LiteralPath $packageInit)) {
    Fail "the candidate package is missing: $packageInit"
}
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$workspace;$previousPythonPath"
& $python.Source -c "import wcancel" 2>&1 | Out-Null
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
