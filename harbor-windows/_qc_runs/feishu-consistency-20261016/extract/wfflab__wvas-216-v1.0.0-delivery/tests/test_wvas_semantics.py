"""Hidden semantic suite for the wfflab__wvas-216 Windows address-space contract.

This file is injected by the evaluation side and is never shipped inside the
task package.  Every assertion that decides whether the candidate is right is
backed by a measurement the suite performs itself:

* it starts its own target process and records the mappings that process
  created for it (a file mapping, an anonymous mapping, private committed
  memory and a multi-gigabyte reservation),
* it walks that process' address space with its own ``VirtualQueryEx`` /
  ``GetMappedFileNameW`` calls,
* it compares the candidate's answers against those measurements, never
  against another answer produced by the candidate.

The contract under test is a Windows/NTFS contract: the region descriptors,
the STATE/TYPE/PROTECT vocabulary and the device-path translation all come from
the Windows virtual memory API, and none of them exists on another system.
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import subprocess
import sys
import time

import pytest

if os.name != "nt":
    pytest.skip(
        "the wvas contract is a Windows virtual-memory contract and cannot be graded elsewhere",
        allow_module_level=True,
    )

MB = 1024 * 1024
GIB = 1024 * MB

# --------------------------------------------------------------- candidate

_IMPORT_ERROR = None
try:
    import wvas
except Exception as exc:  # pragma: no cover - reported through every check
    wvas = None
    _IMPORT_ERROR = "%s: %s" % (type(exc).__name__, exc)

WVasError = getattr(wvas, "WVasError", Exception) if wvas is not None else Exception


def _require_candidate():
    if _IMPORT_ERROR is not None:
        pytest.fail("the candidate package could not be imported: %s" % _IMPORT_ERROR)
    if wvas is None:
        pytest.fail("the candidate package is not importable")


# ------------------------------------------------------------ Win32 layer

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_FREE = 0x10000

MEM_IMAGE = 0x1000000
MEM_MAPPED = 0x40000
MEM_PRIVATE = 0x20000

_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL
_k32.QueryDosDeviceW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
_k32.QueryDosDeviceW.restype = wintypes.DWORD


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


_k32.VirtualQueryEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t,
]
_k32.VirtualQueryEx.restype = ctypes.c_size_t
_psapi.GetMappedFileNameW.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD,
]
_psapi.GetMappedFileNameW.restype = wintypes.DWORD


def _observed_regions(pid):
    """Walk ``pid``'s address space with the suite's own Win32 calls."""
    handle = _k32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid
    )
    if not handle:
        pytest.fail(
            "the suite could not open the target process (%d)" % ctypes.get_last_error()
        )
    regions = []
    buffer = ctypes.create_unicode_buffer(32768)
    try:
        mbi = MEMORY_BASIC_INFORMATION()
        address = 0
        while address < (1 << 47):
            written = _k32.VirtualQueryEx(
                handle,
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi),
            )
            if not written:
                break
            base = mbi.BaseAddress or 0
            if mbi.State in (MEM_COMMIT, MEM_RESERVE):
                raw = ""
                if mbi.Type in (MEM_IMAGE, MEM_MAPPED):
                    count = _psapi.GetMappedFileNameW(
                        handle, ctypes.c_void_p(base), buffer, 32768
                    )
                    raw = buffer.value[:count] if count else ""
                regions.append({
                    "base": int(base),
                    "size": int(mbi.RegionSize),
                    "state": "commit" if mbi.State == MEM_COMMIT else "reserve",
                    "raw_path": raw,
                })
            next_address = base + mbi.RegionSize
            if next_address <= address:
                break
            address = next_address
    finally:
        _k32.CloseHandle(handle)
    return regions


def _covering(regions, address):
    for item in regions:
        if item["base"] <= address < item["base"] + item["size"]:
            return item
    return None


# --------------------------------------------------------- target fixture

_TARGET_SOURCE = r'''
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
PAGE_READWRITE = 0x04
PAGE_NOACCESS = 0x01
FILE_MAP_READ = 0x0004
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MB = 1024 * 1024

k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                            wt.DWORD, wt.DWORD, wt.HANDLE]
k32.CreateFileMappingW.restype = wt.HANDLE
k32.CreateFileMappingW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD,
                                   wt.DWORD, wt.DWORD, wt.LPCWSTR]
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [wt.HANDLE, wt.DWORD, wt.DWORD, wt.DWORD,
                              ctypes.c_size_t]
k32.VirtualAlloc.restype = ctypes.c_void_p
k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wt.DWORD, wt.DWORD]

ready_path, stop_path, work = sys.argv[1], sys.argv[2], sys.argv[3]
info = {"pid": os.getpid()}

sample = os.path.join(work, "wvas-mapped-sample.bin")
with open(sample, "wb") as handle:
    handle.write(b"wvas-sample-payload" * 1024)
handle = k32.CreateFileW(sample, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_ALL,
                         None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
if not handle:
    raise SystemExit("CreateFileW failed: %d" % ctypes.get_last_error())
mapping = k32.CreateFileMappingW(handle, None, PAGE_READWRITE, 0, MB, None)
view = k32.MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, MB)
if not view:
    raise SystemExit("MapViewOfFile failed: %d" % ctypes.get_last_error())
info["file_path"] = sample
info["file_view"] = int(view)

anon = k32.CreateFileMappingW(INVALID_HANDLE_VALUE, None, PAGE_READWRITE,
                              0, 4 * MB, None)
anon_view = k32.MapViewOfFile(anon, FILE_MAP_READ, 0, 0, 4 * MB)
if not anon_view:
    raise SystemExit("anonymous MapViewOfFile failed: %d" % ctypes.get_last_error())
info["anon_view"] = int(anon_view)

private = k32.VirtualAlloc(None, MB, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)
info["private_view"] = int(private or 0)

reserved = k32.VirtualAlloc(None, 6 * 1024 * MB, MEM_RESERVE, PAGE_NOACCESS)
info["reserve_base"] = int(reserved or 0)
info["reserve_size"] = 6 * 1024 * MB

ctypes.WinDLL("version.dll")
info["dll"] = "version.dll"

with open(ready_path, "w") as handle:
    json.dump(info, handle)

while not os.path.exists(stop_path):
    time.sleep(0.05)
'''


@pytest.fixture(scope="session")
def target(tmp_path_factory):
    work = tmp_path_factory.mktemp("wvas-target")
    script = work / "wvas_target.py"
    script.write_text(_TARGET_SOURCE, encoding="utf-8")
    ready = work / "ready.json"
    stop = work / "stop.flag"
    log = work / "target.log"

    with open(str(log), "wb") as log_handle:
        process = subprocess.Popen(
            [sys.executable, str(script), str(ready), str(stop), str(work)],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(work),
        )
        deadline = time.time() + 120
        while time.time() < deadline:
            if ready.exists() and ready.stat().st_size > 0:
                break
            if process.poll() is not None:
                pytest.fail(
                    "the fixture target process exited early (%s):\n%s"
                    % (process.returncode, log.read_text(encoding="utf-8", errors="replace"))
                )
            time.sleep(0.1)
        else:
            process.kill()
            pytest.fail("the fixture target process never became ready")

    with open(str(ready), "r", encoding="utf-8") as handle:
        info = json.load(handle)
    info["work"] = str(work)
    info["log"] = str(log)

    if not info.get("reserve_base"):
        pytest.fail("the fixture could not reserve 6 GiB of address space")
    if not info.get("file_view") or not info.get("anon_view"):
        pytest.fail("the fixture could not create its mappings")

    yield info

    stop.write_text("go", encoding="utf-8")
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()


# ------------------------------------------------- FAIL_TO_PASS contract

def test_region_addresses_are_64_bit(target):
    _require_candidate()
    reported = wvas.regions(target["pid"])
    assert reported, "no region was reported for the target process"
    observed = _observed_regions(target["pid"])
    assert observed, "the suite could not observe any region itself"
    live = max(item["base"] for item in reported)
    truth = max(item["base"] for item in observed)
    assert live == truth, (
        "the highest reported base address is %#x but the target really uses %#x"
        % (live, truth)
    )
    assert any(item["base"] > 0xFFFFFFFF for item in reported), (
        "no reported region lives above 4 GiB, so the addresses were truncated"
    )


def test_region_sizes_are_64_bit(target):
    _require_candidate()
    reported = wvas.regions(target["pid"])
    region = _covering(reported, target["reserve_base"])
    assert region is not None, (
        "the 6 GiB reservation at %#x is missing from the report" % target["reserve_base"]
    )
    assert region["size"] >= target["reserve_size"], (
        "the reservation is reported as %d bytes instead of at least %d"
        % (region["size"], target["reserve_size"])
    )


def test_reserved_regions_are_reported(target):
    _require_candidate()
    reported = wvas.regions(target["pid"])
    region = _covering(reported, target["reserve_base"])
    assert region is not None, "the reserved range was not reported at all"
    assert region["state"] == "reserve", (
        "the reserved range is reported as state %r" % (region["state"],)
    )
    assert any(item["state"] == "reserve" for item in reported), (
        "no region is reported as reserved, so reserved memory is invisible"
    )


def test_file_mapping_path_is_a_dos_path(target):
    _require_candidate()
    reported = wvas.regions(target["pid"])
    region = _covering(reported, target["file_view"])
    assert region is not None, (
        "the file mapping at %#x is missing from the report" % target["file_view"]
    )
    path = region["path"]
    assert path, "the file-backed region has no path at all: %r" % (path,)
    assert os.path.normcase(path) == os.path.normcase(target["file_path"]), (
        "the mapped file is reported as %r instead of %r" % (path, target["file_path"])
    )
    assert os.path.isfile(path), "the reported path does not name an existing file"


def test_device_paths_are_translated(target):
    _require_candidate()
    reported = wvas.regions(target["pid"])
    paths = [item["path"] for item in reported if item["path"]]
    assert paths, "no file-backed region was reported for the target process"
    for path in paths:
        upper = path.upper()
        assert not upper.startswith("\\DEVICE\\"), path
        assert not upper.startswith("\\??\\"), path
        assert not upper.startswith("\\\\?\\"), path


def test_anonymous_mapping_has_no_path(target):
    _require_candidate()
    reported = wvas.regions(target["pid"])
    region = _covering(reported, target["anon_view"])
    assert region is not None, (
        "the anonymous mapping at %#x is missing from the report" % target["anon_view"]
    )
    assert region["path"] is None, (
        "an anonymous mapping is reported with the path %r" % (region["path"],)
    )


def test_missing_process_is_classified():
    _require_candidate()
    with pytest.raises(WVasError) as caught:
        wvas.regions(0x7FFFFFF0)
    assert caught.value.kind == "no-such-process", (
        "a missing process was classified as %r" % (caught.value.kind,)
    )


def test_modules_are_deduplicated(target):
    _require_candidate()
    modules = wvas.modules(target["pid"])
    assert modules, "no loaded image was reported for the target process"
    paths = [os.path.normcase(item["path"]) for item in modules]
    assert len(paths) == len(set(paths)), (
        "the same image is reported %d times" % (len(paths) - len(set(paths)) + 1)
    )


# ------------------------------------------------- PASS_TO_PASS surface

def test_regions_are_sorted_by_base(target):
    _require_candidate()
    bases = [item["base"] for item in wvas.regions(target["pid"])]
    assert bases == sorted(bases)


def test_region_records_are_well_formed(target):
    _require_candidate()
    reported = wvas.regions(target["pid"])
    assert reported
    for item in reported:
        assert set(item) == {
            "base", "size", "state", "type", "protect", "path", "image",
        }
        assert isinstance(item["base"], int) and item["base"] >= 0
        assert isinstance(item["size"], int) and item["size"] > 0
        assert item["state"] in ("commit", "reserve")
        assert item["type"] in ("image", "mapped", "private")
        assert isinstance(item["protect"], str)
        assert item["path"] is None or isinstance(item["path"], str)
        assert isinstance(item["image"], bool)


def test_own_process_reports_image_regions():
    _require_candidate()
    reported = wvas.regions(os.getpid())
    assert any(item["type"] == "image" for item in reported)


def test_file_backed_regions_are_a_subset(target):
    _require_candidate()
    reported = wvas.regions(target["pid"])
    backed = wvas.file_backed_regions(target["pid"])
    assert isinstance(backed, list)
    keys = {(item["base"], item["size"]) for item in reported}
    for item in backed:
        assert item["path"]
        assert (item["base"], item["size"]) in keys


def test_include_reserved_false_only_reports_committed_memory(target):
    _require_candidate()
    reported = wvas.regions(target["pid"], include_reserved=False)
    assert reported
    assert all(item["state"] == "commit" for item in reported)


def test_negative_pid_is_rejected():
    _require_candidate()
    with pytest.raises(WVasError) as caught:
        wvas.regions(-1)
    assert caught.value.kind == "badarg"


def test_modules_are_sorted_by_base(target):
    _require_candidate()
    modules = wvas.modules(target["pid"])
    bases = [item["base"] for item in modules]
    assert bases == sorted(bases)


def test_visible_smoke_suite_still_passes():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    smoke = os.path.join(here, "test_wvas_basic.py")
    assert os.path.isfile(smoke), "the visible smoke suite was not staged next to this file"
    env = dict(os.environ)
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", smoke],
        cwd=root, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
