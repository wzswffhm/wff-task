# Readiness probe for wfflab__wvas-216. It never scores a candidate: it only
# answers whether this machine can host the task at all. A non-zero exit means
# the environment is INVALID, not that the candidate failed.
#
# The contract under test is the Windows virtual memory API, so this probe
# exercises those calls directly rather than trusting the candidate package to
# tell us whether they work.
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
    Fail 'the host platform is not Windows (Win32NT), so the wvas contract cannot be graded here'
}
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Fail "Windows PowerShell 5.1 or newer is required, found $($PSVersionTable.PSVersion)"
}

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

# ---- Windows virtual memory capability --------------------------------------
$probe = Join-Path ([System.IO.Path]::GetTempPath()) ('wvas-readiness-' + [Guid]::NewGuid().ToString('N') + '.py')
$probeSource = @'
import ctypes
import ctypes.wintypes as wt
import os

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
MEM_IMAGE = 0x1000000
MEM_MAPPED = 0x40000


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.CloseHandle.restype = wt.BOOL
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.QueryDosDeviceW.argtypes = [wt.LPCWSTR, wt.LPWSTR, wt.DWORD]
k32.QueryDosDeviceW.restype = wt.DWORD
psapi.GetMappedFileNameW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]
psapi.GetMappedFileNameW.restype = wt.DWORD

handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, os.getpid())
if not handle:
    raise SystemExit("OpenProcess failed: %d" % ctypes.get_last_error())

mbi = MBI()
buffer = ctypes.create_unicode_buffer(32768)
regions = 0
mapped = 0
address = 0
while address < (1 << 47):
    if not k32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
        break
    regions += 1
    base = mbi.BaseAddress or 0
    if mbi.State == MEM_COMMIT and mbi.Type in (MEM_IMAGE, MEM_MAPPED):
        if psapi.GetMappedFileNameW(handle, ctypes.c_void_p(base), buffer, 32768):
            mapped += 1
    if base + mbi.RegionSize <= address:
        break
    address = base + mbi.RegionSize
k32.CloseHandle(handle)

if regions == 0:
    raise SystemExit("VirtualQueryEx returned no regions for the probe process")
if mapped == 0:
    raise SystemExit("GetMappedFileNameW named no file-backed region, so mapped paths cannot be audited")

dos = ctypes.create_unicode_buffer(1024)
if not k32.QueryDosDeviceW("C:", dos, 1024):
    raise SystemExit("QueryDosDeviceW failed: %d" % ctypes.get_last_error())
if not dos.value.upper().startswith("\\DEVICE\\"):
    raise SystemExit("QueryDosDeviceW returned an unexpected device name: %r" % dos.value)

print("regions=%d mapped=%d device=%s" % (regions, mapped, dos.value))
'@
Set-Content -LiteralPath $probe -Value $probeSource -Encoding ASCII
$probeOutput = & $python.Source $probe 2>&1
$probeExit = $LASTEXITCODE
Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
if ($probeExit -ne 0) {
    Fail "the Windows virtual memory probe failed: $probeOutput"
}
Write-Host "readiness: $probeOutput"

# ---- candidate workspace ----------------------------------------------------
$workspace = Join-Path $TaskRoot 'environment\workspace'
$packageInit = Join-Path (Join-Path $workspace 'wvas') '__init__.py'
if (-not (Test-Path -LiteralPath $packageInit)) {
    Fail "the candidate package is missing: $packageInit"
}
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = "$workspace;$previousPythonPath"
& $python.Source -c "import wvas" 2>&1 | Out-Null
$importExit = $LASTEXITCODE
$env:PYTHONPATH = $previousPythonPath
if ($importExit -ne 0) {
    Fail 'the candidate package cannot be imported'
}

foreach ($item in @('docs\NOTES.md', 'README.md', 'tests\test_wvas_basic.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $workspace $item))) {
        Fail "the workspace is incomplete: $item is missing"
    }
}
Write-Host 'readiness: the candidate package and its visible material are in place'

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
