# Readiness probe for wfflab__wtoken-221. It never scores a candidate: it only
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
    Fail 'the host platform is not Windows (Win32NT), so the wtoken contract cannot be graded here'
}
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail "Windows PowerShell 5.1 or newer is required, found $($PSVersionTable.PSVersion)"
}
Write-Host 'readiness: the host is a Windows kernel'

# ---- capability: the token, its privilege array, and the enabled bit --------
# The graded contract is about a privilege being present-but-switched-off, so the
# probe performs the same three primitives the evaluator will use: open the
# process token, read the privilege array with its attribute words, and toggle
# the enabled bit of one privilege, checking the change through a fresh read.
$probeSource = @'
using System;
using System.Runtime.InteropServices;

public static class WTokenReadinessProbe
{
    [StructLayout(LayoutKind.Sequential)]
    private struct LUID { public uint LowPart; public int HighPart; }

    [StructLayout(LayoutKind.Sequential)]
    private struct LUID_AND_ATTRIBUTES { public LUID Luid; public uint Attributes; }

    [DllImport("advapi32", SetLastError = true)]
    private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);

    [DllImport("advapi32", SetLastError = true)]
    private static extern bool GetTokenInformation(IntPtr token, int infoClass, IntPtr buffer,
                                                   uint size, out uint returned);

    [DllImport("advapi32", SetLastError = true)]
    private static extern bool AdjustTokenPrivileges(IntPtr token, bool disableAll,
                                                     IntPtr newState, uint bufferLength,
                                                     IntPtr previousState, IntPtr returnLength);

    [DllImport("advapi32", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool LookupPrivilegeValue(string system, string name, out LUID luid);

    [DllImport("advapi32", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool LookupPrivilegeName(string system, ref LUID luid,
                                                   System.Text.StringBuilder name, ref uint size);

    [DllImport("kernel32")]
    private static extern IntPtr GetCurrentProcess();

    [DllImport("kernel32", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    private const uint TOKEN_QUERY = 0x0008;
    private const uint TOKEN_ADJUST_PRIVILEGES = 0x0020;
    private const uint SE_PRIVILEGE_ENABLED = 0x00000002;
    private const int TokenPrivileges = 3;
    private const int ERROR_NOT_ALL_ASSIGNED = 1300;

    private static uint[] ReadAttributes(IntPtr token, out string[] names)
    {
        uint needed;
        GetTokenInformation(token, TokenPrivileges, IntPtr.Zero, 0, out needed);
        if (needed == 0) { names = null; return null; }
        IntPtr buffer = Marshal.AllocHGlobal((int)needed);
        try
        {
            uint returned;
            if (!GetTokenInformation(token, TokenPrivileges, buffer, needed, out returned))
            { names = null; return null; }
            int count = Marshal.ReadInt32(buffer);
            int stride = Marshal.SizeOf(typeof(LUID_AND_ATTRIBUTES));
            long baseAddress = buffer.ToInt64() + 4;
            uint[] attributes = new uint[count];
            names = new string[count];
            for (int i = 0; i < count; i++)
            {
                IntPtr entry = new IntPtr(baseAddress + i * stride);
                LUID luid = (LUID)Marshal.PtrToStructure(entry, typeof(LUID));
                attributes[i] = (uint)Marshal.ReadInt32(new IntPtr(entry.ToInt64() + 8));
                uint size = 256;
                var text = new System.Text.StringBuilder(256);
                LookupPrivilegeName(null, ref luid, text, ref size);
                names[i] = text.ToString();
            }
            return attributes;
        }
        finally { Marshal.FreeHGlobal(buffer); }
    }

    public static string Run()
    {
        IntPtr token;
        if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY | TOKEN_ADJUST_PRIVILEGES, out token))
            return "OpenProcessToken failed (error " + Marshal.GetLastWin32Error() + ")";
        try
        {
            string[] names;
            uint[] before = ReadAttributes(token, out names);
            if (before == null || names == null || names.Length == 0)
                return "the token privilege array could not be read";
            if (names.Length < 2)
                return "the token holds too few privileges to probe";

            int target = -1;
            for (int i = 0; i < names.Length; i++)
                if ((before[i] & SE_PRIVILEGE_ENABLED) == 0) { target = i; break; }
            if (target < 0)
                return "every privilege on this token is already enabled; nothing to toggle";

            LUID luid;
            if (!LookupPrivilegeValue(null, names[target], out luid))
                return "LookupPrivilegeValue failed for " + names[target];

            int stride = Marshal.SizeOf(typeof(LUID_AND_ATTRIBUTES));
            IntPtr state = Marshal.AllocHGlobal(4 + stride);
            try
            {
                Marshal.WriteInt32(state, 1);
                Marshal.StructureToPtr(luid, new IntPtr(state.ToInt64() + 4), false);
                Marshal.WriteInt32(new IntPtr(state.ToInt64() + 4 + 8), (int)SE_PRIVILEGE_ENABLED);
                if (!AdjustTokenPrivileges(token, false, state, (uint)(4 + stride), IntPtr.Zero, IntPtr.Zero))
                    return "AdjustTokenPrivileges failed (error " + Marshal.GetLastWin32Error() + ")";
                int last = Marshal.GetLastWin32Error();
                if (last == ERROR_NOT_ALL_ASSIGNED)
                    return "the chosen privilege could not be assigned";
            }
            finally { Marshal.FreeHGlobal(state); }

            string[] namesAfter;
            uint[] after = ReadAttributes(token, out namesAfter);
            if (after == null) return "the token could not be re-read after the change";
            int found = -1;
            for (int i = 0; i < namesAfter.Length; i++)
                if (namesAfter[i] == names[target]) { found = i; break; }
            if (found < 0) return "the probed privilege disappeared from the token";
            if ((after[found] & SE_PRIVILEGE_ENABLED) == 0)
                return "the enabled bit did not stick";

            IntPtr restore = Marshal.AllocHGlobal(4 + stride);
            try
            {
                Marshal.WriteInt32(restore, 1);
                Marshal.StructureToPtr(luid, new IntPtr(restore.ToInt64() + 4), false);
                Marshal.WriteInt32(new IntPtr(restore.ToInt64() + 4 + 8), (int)before[target]);
                AdjustTokenPrivileges(token, false, restore, (uint)(4 + stride), IntPtr.Zero, IntPtr.Zero);
            }
            finally { Marshal.FreeHGlobal(restore); }

            return "ok";
        }
        finally { CloseHandle(token); }
    }
}
'@

try {
    Add-Type -TypeDefinition $probeSource -Language CSharp -ErrorAction Stop
}
catch {
    Fail "the token capability probe could not be compiled: $($_.Exception.Message)"
}

$probeResult = [WTokenReadinessProbe]::Run()
if ($probeResult -ne 'ok') {
    Fail "the token privilege capability probe failed: $probeResult"
}
Write-Host 'readiness: the process token can be opened, its privilege array read with attribute words, and the enabled bit toggled and re-read'

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
$packageInit = Join-Path (Join-Path $workspace 'wtoken') '__init__.py'
if (-not (Test-Path -LiteralPath $packageInit)) {
    Fail "the candidate package is missing: $packageInit"
}
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$workspace;$previousPythonPath"
& $python.Source -c "import wtoken" 2>&1 | Out-Null
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
