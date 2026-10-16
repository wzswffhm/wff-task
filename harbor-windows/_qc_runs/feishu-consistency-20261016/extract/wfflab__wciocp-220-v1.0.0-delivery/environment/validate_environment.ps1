# Readiness probe for wfflab__wciocp-220. It never scores a candidate: it only
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
    Fail 'the host platform is not Windows (Win32NT), so the wciocp contract cannot be graded here'
}
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail "Windows PowerShell 5.1 or newer is required, found $($PSVersionTable.PSVersion)"
}
Write-Host 'readiness: the host is a Windows kernel'

# ---- capability: a completion port that hands a key back --------------------
# The graded contract is about one completion packet being drawn exactly once and
# carrying the key that was registered for its handle, so the probe performs the
# same primitives the evaluator will use: create a named pipe opened for
# overlapped I/O, bind it to a completion port with a known key, issue a read
# that cannot finish, then write into the other end and confirm that the packet
# arriving at the port carries that key. A second, empty wait must report
# WAIT_TIMEOUT without disturbing anything.
$probeSource = @'
using System;
using System.Runtime.InteropServices;

public static class WCIocpReadinessProbe
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
    private static extern IntPtr CreateIoCompletionPort(IntPtr fileHandle, IntPtr existingPort,
        IntPtr completionKey, uint numberOfConcurrentThreads);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool GetQueuedCompletionStatus(IntPtr port, out uint transferred,
        out IntPtr completionKey, out IntPtr overlapped, uint timeout);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool ReadFile(IntPtr handle, byte[] buffer, uint toRead,
        out uint read, ref OVERLAPPED overlapped);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool WriteFile(IntPtr handle, byte[] buffer, uint toWrite,
        out uint written, IntPtr overlapped);

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    private const uint PIPE_ACCESS_DUPLEX = 0x00000003;
    private const uint FILE_FLAG_OVERLAPPED = 0x40000000;
    private const uint GENERIC_READ = 0x80000000;
    private const uint GENERIC_WRITE = 0x40000000;
    private const uint OPEN_EXISTING = 3;
    private const int ERROR_IO_PENDING = 997;
    private const int WAIT_TIMEOUT = 258;
    private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);
    private const long EXPECTED_KEY = 0xA1;

    public static string Run()
    {
        string name = @"\\.\pipe\wciocp-readiness-" + Guid.NewGuid().ToString("N");
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

        IntPtr port = CreateIoCompletionPort(INVALID_HANDLE_VALUE, IntPtr.Zero, IntPtr.Zero, 0);
        if (port == IntPtr.Zero)
        {
            CloseHandle(client);
            CloseHandle(server);
            return "CreateIoCompletionPort (new port) failed (error " + Marshal.GetLastWin32Error() + ")";
        }

        IntPtr bound = CreateIoCompletionPort(server, port, new IntPtr(EXPECTED_KEY), 0);
        if (bound != port)
        {
            CloseHandle(port);
            CloseHandle(client);
            CloseHandle(server);
            return "binding the pipe to the completion port failed (error "
                + Marshal.GetLastWin32Error() + ")";
        }

        try
        {
            OVERLAPPED ov = new OVERLAPPED();
            byte[] buffer = new byte[64];
            uint read;
            bool ok = ReadFile(server, buffer, 64, out read, ref ov);
            int pending = Marshal.GetLastWin32Error();
            if (ok || pending != ERROR_IO_PENDING)
                return "a read on an empty overlapped pipe did not go pending (ok=" + ok
                    + ", error=" + pending + ")";

            byte[] payload = new byte[] { 0x5A };
            uint written;
            if (!WriteFile(client, payload, 1, out written, IntPtr.Zero) || written != 1)
                return "writing into the probe pipe failed (error " + Marshal.GetLastWin32Error() + ")";

            uint transferred;
            IntPtr key;
            IntPtr overlapped;
            ok = GetQueuedCompletionStatus(port, out transferred, out key, out overlapped, 10000);
            if (!ok)
                return "no completion packet arrived for the finished read (error "
                    + Marshal.GetLastWin32Error() + ")";
            if (key.ToInt64() != EXPECTED_KEY)
                return "the completion packet carried key " + key.ToInt64()
                    + " instead of the registered " + EXPECTED_KEY;
            if (transferred != 1)
                return "the completion packet reported " + transferred + " bytes instead of 1";

            ok = GetQueuedCompletionStatus(port, out transferred, out key, out overlapped, 300);
            int empty = Marshal.GetLastWin32Error();
            if (ok || empty != WAIT_TIMEOUT)
                return "waiting on an empty port did not report WAIT_TIMEOUT (ok=" + ok
                    + ", error=" + empty + ")";
        }
        finally
        {
            CloseHandle(port);
            CloseHandle(client);
            CloseHandle(server);
        }

        return "ok";
    }
}
'@

try {
    Add-Type -TypeDefinition $probeSource -Language CSharp -ErrorAction Stop
}
catch {
    Fail "the completion-port capability probe could not be compiled: $($_.Exception.Message)"
}

$probeResult = [WCIocpReadinessProbe]::Run()
if ($probeResult -ne 'ok') {
    Fail "the completion-port capability probe failed: $probeResult"
}
Write-Host 'readiness: a named pipe can be bound to a completion port, a finished read delivers a packet carrying the registered key, and an empty wait reports WAIT_TIMEOUT'

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
$packageInit = Join-Path (Join-Path $workspace 'wciocp') '__init__.py'
if (-not (Test-Path -LiteralPath $packageInit)) {
    Fail "the candidate package is missing: $packageInit"
}
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$workspace;$previousPythonPath"
& $python.Source -c "import wciocp" 2>&1 | Out-Null
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
