"""Hidden semantic suite for the wfflab__wsparse-215 Windows/NTFS contract.

This file is injected by the evaluation side and is never shipped in the task
package.  Every assertion that decides whether the candidate is right is backed
by a measurement the suite performs itself:

* it opens its own handles with ``CreateFileW``,
* it drives ``DeviceIoControl`` with the NTFS sparse control codes,
* it reads the physical size with ``GetCompressedFileSizeW`` and
  ``GetFileInformationByHandleEx(FileStandardInfo)``, and
* it shells out to ``fsutil`` for an observation the candidate cannot forge.

No value returned by the candidate package is ever used as the reference for
its own correctness.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

import pytest

if os.name != "nt":
    pytest.skip(
        "the wsparse contract is a Windows/NTFS contract and cannot be graded elsewhere",
        allow_module_level=True,
    )

from wsparse import (  # noqa: E402  (import after the platform guard on purpose)
    WSParseError,
    allocated_ranges,
    disk_usage,
    preallocate,
    sparse_flag,
    sparse_state,
)

# --------------------------------------------------------------- Win32 layer

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007
CREATE_ALWAYS = 2
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_SPARSE_FILE = 0x00000200
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_BEGIN = 0
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

FSCTL_SET_SPARSE = 0x000900C4
FSCTL_QUERY_ALLOCATED_RANGES = 0x000940CF

MB = 1024 * 1024
CLUSTER = 4096

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.DeviceIoControl.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
    wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
]
_kernel32.DeviceIoControl.restype = wintypes.BOOL
_kernel32.SetFilePointerEx.argtypes = [
    wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
]
_kernel32.SetFilePointerEx.restype = wintypes.BOOL
_kernel32.SetEndOfFile.argtypes = [wintypes.HANDLE]
_kernel32.SetEndOfFile.restype = wintypes.BOOL
_kernel32.WriteFile.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
]
_kernel32.WriteFile.restype = wintypes.BOOL
_kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
_kernel32.FlushFileBuffers.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
_kernel32.GetCompressedFileSizeW.restype = wintypes.DWORD


class FILE_STANDARD_INFO(ctypes.Structure):
    _fields_ = [
        ("AllocationSize", ctypes.c_longlong),
        ("EndOfFile", ctypes.c_longlong),
        ("NumberOfLinks", wintypes.DWORD),
        ("DeletePending", ctypes.c_ubyte),
        ("Directory", ctypes.c_ubyte),
    ]


class ALLOCATED_RANGE(ctypes.Structure):
    _fields_ = [("FileOffset", ctypes.c_longlong), ("Length", ctypes.c_longlong)]


def _last_error():
    return ctypes.get_last_error()


def _create(path, sparse):
    """Create ``path``, optionally setting the sparse flag before extending it."""
    handle = _kernel32.CreateFileW(
        str(path), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_ALL, None,
        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise OSError(_last_error(), "CreateFileW failed", str(path))
    if sparse:
        flag = ctypes.c_byte(1)
        returned = wintypes.DWORD(0)
        ok = _kernel32.DeviceIoControl(
            handle, FSCTL_SET_SPARSE, ctypes.byref(flag), 1, None, 0,
            ctypes.byref(returned), None,
        )
        if not ok:
            _kernel32.CloseHandle(handle)
            raise OSError(_last_error(), "FSCTL_SET_SPARSE failed", str(path))
    return handle


def _open_existing(path):
    handle = _kernel32.CreateFileW(
        str(path), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_ALL, None,
        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise OSError(_last_error(), "CreateFileW failed", str(path))
    return handle


def _close(handle):
    _kernel32.CloseHandle(handle)


def _set_length(handle, size):
    position = ctypes.c_longlong(0)
    if not _kernel32.SetFilePointerEx(handle, ctypes.c_longlong(size), ctypes.byref(position), FILE_BEGIN):
        raise OSError(_last_error(), "SetFilePointerEx failed")
    if not _kernel32.SetEndOfFile(handle):
        raise OSError(_last_error(), "SetEndOfFile failed")


def _poke(handle, offset, blob):
    position = ctypes.c_longlong(0)
    if not _kernel32.SetFilePointerEx(handle, ctypes.c_longlong(offset), ctypes.byref(position), FILE_BEGIN):
        raise OSError(_last_error(), "SetFilePointerEx failed")
    written = wintypes.DWORD(0)
    if not _kernel32.WriteFile(handle, blob, len(blob), ctypes.byref(written), None):
        raise OSError(_last_error(), "WriteFile failed")
    if written.value != len(blob):
        raise OSError("short write at %d" % offset)


def _flush(handle):
    """Push the writes out: allocation metadata only settles after a flush."""
    if not _kernel32.FlushFileBuffers(handle):
        raise OSError(_last_error(), "FlushFileBuffers failed")


def _allocation_size(handle):
    info = FILE_STANDARD_INFO()
    ok = _kernel32.GetFileInformationByHandleEx(handle, 1, ctypes.byref(info), ctypes.sizeof(info))
    if not ok:
        raise OSError(_last_error(), "GetFileInformationByHandleEx failed")
    return info.AllocationSize


def _query_ranges(handle, offset, length):
    """Return the really allocated ``[(offset, length), ...]`` of a live handle."""
    if length <= 0:
        return []
    request = ALLOCATED_RANGE(offset, length)
    result = (ALLOCATED_RANGE * 256)()
    returned = wintypes.DWORD(0)
    ok = _kernel32.DeviceIoControl(
        handle, FSCTL_QUERY_ALLOCATED_RANGES, ctypes.byref(request),
        ctypes.sizeof(request), ctypes.byref(result), ctypes.sizeof(result),
        ctypes.byref(returned), None,
    )
    if not ok:
        raise OSError(_last_error(), "FSCTL_QUERY_ALLOCATED_RANGES failed")
    count = returned.value // ctypes.sizeof(ALLOCATED_RANGE)
    return [(result[i].FileOffset, result[i].Length) for i in range(count)]


def _compressed_size(path):
    """Physical size as reported by the file system, for a closed file."""
    high = wintypes.DWORD(0)
    low = _kernel32.GetCompressedFileSizeW(str(path), ctypes.byref(high))
    if low == 0xFFFFFFFF:
        error = _last_error()
        if error != 0:
            raise OSError(error, "GetCompressedFileSizeW failed", str(path))
    return (high.value << 32) | low


def _fsutil(args):
    proc = subprocess.run(["fsutil"] + args, capture_output=True, text=True)
    return (proc.stdout or "") + (proc.stderr or "")


def _fsutil_query_flag(path):
    """External, unforgeable verdict: 'sparse', 'not-sparse' or 'unknown'."""
    text = _fsutil(["sparse", "queryflag", str(path)]).lower()
    if "is not set as sparse" in text:
        return "not-sparse"
    if "is set as sparse" in text:
        return "sparse"
    return "unknown"


def _fsutil_alloc_ranges(path, length):
    return _fsutil(["file", "queryAllocRanges", "offset=0", "length=%d" % length, str(path)])


def _attribute_sparse_bit(path):
    return bool(os.stat(str(path)).st_file_attributes & FILE_ATTRIBUTE_SPARSE_FILE)


def _measure(path):
    """(allocation, ranges) measured by this suite on its own handle."""
    logical = os.path.getsize(str(path))
    handle = _open_existing(path)
    try:
        _flush(handle)
        allocation = _allocation_size(handle)
        ranges = _query_ranges(handle, 0, logical)
    finally:
        _close(handle)
    return allocation, ranges


def _make_sparse_sink(path, logical, pokes=()):
    """Build a sparse file of ``logical`` bytes with the given written extents."""
    handle = _create(path, sparse=True)
    try:
        _set_length(handle, logical)
        for offset, blob in pokes:
            _poke(handle, offset, blob)
        _flush(handle)
    finally:
        _close(handle)
    return str(path)


def _covers(ranges, offset):
    return any(start <= offset < start + length for start, length in ranges)


CLUSTER = 4096


def _cluster_spans(ranges):
    """Normalise ``(offset, length)`` pairs onto cluster-aligned spans.

    Allocation is reported at cluster granularity, so two descriptions that
    differ only inside a cluster describe the same on-disk layout. An extent
    whose length is not a multiple of the cluster size (8193 instead of 8192)
    does not describe the same layout and must be rejected: a coverage-only
    check cannot see that difference, which is exactly how a wrong extent used
    to slip through.
    """
    spans = set()
    for start, length in ranges:
        begin = (int(start) // CLUSTER) * CLUSTER
        end = ((int(start) + int(length) + CLUSTER - 1) // CLUSTER) * CLUSTER
        spans.add((begin, end))
    return spans


# ------------------------------------------------------------------ fixtures

@pytest.fixture()
def sparse_64m(tmp_path):
    """64 MiB logical, two small written extents, ~128 KiB allocated."""
    return _make_sparse_sink(
        tmp_path / "sparse_64m.bin", 64 * MB,
        [(0, b"A" * 4096), (32 * MB, b"B" * 8192)],
    )


@pytest.fixture()
def hole_8m(tmp_path):
    """8 MiB logical, nothing written at all."""
    return _make_sparse_sink(tmp_path / "hole_8m.bin", 8 * MB)


# ------------------------------------------------------- mechanism: pre-allocation

def test_preallocate_marks_file_sparse(tmp_path):
    sink = tmp_path / "flagged.bin"
    preallocate(str(sink), 64 * MB)
    assert sparse_state(str(sink)) is True, "the sparse attribute was not set"
    assert _attribute_sparse_bit(sink) is True, "FILE_ATTRIBUTE_SPARSE_FILE is not on the file"
    assert _fsutil_query_flag(sink) == "sparse", _fsutil(["sparse", "queryflag", str(sink)])


def test_preallocate_does_not_materialise_the_file(tmp_path):
    sink = tmp_path / "gigabyte.bin"
    preallocate(str(sink), 1024 * MB)
    assert os.path.getsize(str(sink)) == 1024 * MB, "the file was not extended to the requested size"
    assert sparse_state(str(sink)) is True
    physical = _compressed_size(sink)
    assert physical < 8 * MB, "pre-allocation wrote %.1f MiB to disk" % (physical / float(MB))
    allocation, _ranges = _measure(sink)
    assert allocation < 8 * MB, "allocation size is %.1f MiB" % (allocation / float(MB))


def test_written_extent_is_the_only_allocation(tmp_path):
    sink = tmp_path / "extents.bin"
    preallocate(str(sink), 64 * MB)
    with open(str(sink), "r+b") as handle:
        handle.seek(0)
        handle.write(b"A" * 4096)
        handle.seek(32 * MB)
        handle.write(b"B" * 8192)
        handle.flush()
        os.fsync(handle.fileno())
    reported = allocated_ranges(str(sink))
    measured = _measure(sink)[1]
    assert reported != [(0, 64 * MB)], "the whole pre-allocated file was reported as allocated"
    total = sum(length for _offset, length in reported)
    assert total < 8 * MB, "reported allocation is %.1f MiB" % (total / float(MB))
    assert _covers(reported, 0), "the extent written at offset 0 was not reported"
    assert _covers(reported, 32 * MB), "the extent written at 32 MiB was not reported"
    assert not _covers(reported, 16 * MB), "the hole at 16 MiB was reported as allocated"
    assert not _covers(reported, 48 * MB), "the hole at 48 MiB was reported as allocated"
    # Same reference as above: the extents the volume really allocated.
    assert measured, "the fixture has no allocated extent at all"
    measured_total = sum(length for _start, length in measured)
    assert abs(total - measured_total) <= CLUSTER, (
        "reported %d bytes of allocation but the volume allocated %d bytes"
        % (total, measured_total)
    )
    assert _cluster_spans(reported) == _cluster_spans(measured), (
        "reported spans %s do not match the spans the volume really allocated %s"
        % (sorted(reported), sorted(measured))
    )


# ------------------------------------------------------- mechanism: occupancy

def test_disk_usage_is_physical_not_logical(sparse_64m):
    physical = _compressed_size(sparse_64m)
    assert physical < 1 * MB, "the fixture itself is not sparse (%.1f MiB)" % (physical / float(MB))
    reported = disk_usage(sparse_64m)
    assert reported < 1 * MB, "disk_usage returned %.1f MiB for a sparse file" % (reported / float(MB))
    assert abs(reported - physical) <= 64 * 1024, (
        "disk_usage=%d but the file system reports %d" % (reported, physical)
    )


# --------------------------------------------- mechanism: allocated extents

def test_allocated_ranges_are_the_real_extents(tmp_path):
    sink = _make_sparse_sink(tmp_path / "one_extent.bin", 16 * MB, [(8 * MB, b"C" * 8192)])
    measured = _measure(sink)[1]
    assert measured, "the fixture has no allocated extent at all"
    reported = allocated_ranges(sink)
    assert reported != [(0, 16 * MB)], "the whole file was reported as allocated"
    total = sum(length for _offset, length in reported)
    assert 8192 <= total <= 256 * 1024, "reported allocation is %d bytes" % total
    assert _covers(reported, 8 * MB), "the written extent at 8 MiB was not reported"
    assert not _covers(reported, 0), "offset 0 is a hole and must not be reported as allocated"
    assert not _covers(reported, 15 * MB), "the tail is a hole and must not be reported"

    # The volume's own answer is the reference. A coverage-only check accepts an
    # extent that merely contains the written byte (8193 for a measured 8192), so
    # the reported spans are compared with the spans the volume really allocated.
    measured_total = sum(length for _start, length in measured)
    assert abs(total - measured_total) <= CLUSTER, (
        "reported %d bytes of allocation but the volume allocated %d bytes"
        % (total, measured_total)
    )
    assert _cluster_spans(reported) == _cluster_spans(measured), (
        "reported spans %s do not match the spans the volume really allocated %s"
        % (sorted(reported), sorted(measured))
    )


def test_hole_only_file_has_no_allocated_range(hole_8m):
    assert disk_usage(hole_8m) == 0, "a file with no written byte must occupy nothing"
    assert allocated_ranges(hole_8m) == [], "a file with no written byte has no allocated range"


# ------------------------------------------- mechanism: sparse-flag ordering

def test_sparse_flag_is_actually_set(tmp_path):
    sink = tmp_path / "flag.bin"
    sink.write_bytes(b"D" * 4096)
    assert sparse_state(str(sink)) is False, "the fixture unexpectedly starts out sparse"
    result = sparse_flag(str(sink), True)
    assert result is True, "sparse_flag did not report the resulting state as set"
    assert sparse_state(str(sink)) is True, "the sparse attribute was not set"
    assert _attribute_sparse_bit(sink) is True
    assert _fsutil_query_flag(sink) == "sparse", _fsutil(["sparse", "queryflag", str(sink)])


def test_late_sparse_flag_does_not_free_clusters(tmp_path):
    sink = tmp_path / "late.bin"
    payload = b"E" * (16 * MB)
    with open(str(sink), "wb") as handle:
        handle.write(payload)
    dense = _compressed_size(sink)
    assert dense >= 16 * MB, "the fixture is not dense"
    sparse_flag(str(sink), True)
    assert sparse_state(str(sink)) is True, "the flag was not set on an already extended file"
    assert _fsutil_query_flag(sink) == "sparse"
    after = disk_usage(sink)
    assert after >= 16 * MB, (
        "setting the sparse flag silently released %d bytes of already allocated clusters"
        % (dense - after)
    )


# ------------------------------------------------- object without support

def test_disk_usage_of_a_directory_is_unsupported(tmp_path):
    with pytest.raises(WSParseError) as caught:
        disk_usage(str(tmp_path))
    assert caught.value.kind == "unsupported", "kind was %r" % (caught.value.kind,)


def test_allocated_ranges_of_a_directory_is_unsupported(tmp_path):
    with pytest.raises(WSParseError) as caught:
        allocated_ranges(str(tmp_path))
    assert caught.value.kind == "unsupported", "kind was %r" % (caught.value.kind,)


# --------------------------------------------------------- regression surface

def test_preallocated_tail_is_readable_as_zeros(tmp_path):
    sink = tmp_path / "zeros.bin"
    preallocate(str(sink), 8 * MB)
    with open(str(sink), "r+b") as handle:
        handle.seek(4 * MB)
        handle.write(b"tail-marker")
    with open(str(sink), "rb") as handle:
        handle.seek(4 * MB)
        assert handle.read(11) == b"tail-marker"
        handle.seek(7 * MB)
        assert handle.read(4096) == b"\x00" * 4096


def test_preallocate_returns_the_length(tmp_path):
    sink = tmp_path / "length.bin"
    assert preallocate(str(sink), 1 * MB) == 1 * MB
    assert os.path.getsize(str(sink)) == 1 * MB


def test_preallocate_is_idempotent(tmp_path):
    sink = tmp_path / "idem.bin"
    preallocate(str(sink), 1 * MB)
    preallocate(str(sink), 1 * MB)
    assert os.path.getsize(str(sink)) == 1 * MB


def test_preallocate_never_shrinks(tmp_path):
    sink = tmp_path / "keep.bin"
    sink.write_bytes(b"payload")
    preallocate(str(sink), 1 * MB)
    preallocate(str(sink), 16)
    assert os.path.getsize(str(sink)) == 1 * MB
    assert sink.read_bytes()[:7] == b"payload"


def test_preallocate_rejects_a_negative_size(tmp_path):
    with pytest.raises(WSParseError) as caught:
        preallocate(str(tmp_path / "negative.bin"), -1)
    assert caught.value.kind == "badarg"


def test_disk_usage_of_a_dense_file_is_about_its_length(tmp_path):
    sink = tmp_path / "dense.bin"
    sink.write_bytes(b"x" * 65536)
    used = disk_usage(str(sink))
    assert isinstance(used, int)
    assert 65536 <= used <= 1 * MB, "disk_usage returned %d for a 64 KiB dense file" % used


def test_allocated_ranges_are_ordered_and_inside_the_file(tmp_path):
    sink = tmp_path / "ordered.bin"
    sink.write_bytes(b"y" * 65536)
    size = os.path.getsize(str(sink))
    ranges = allocated_ranges(str(sink))
    assert ranges, "a dense file must report at least one allocated range"
    previous_end = -1
    for offset, length in ranges:
        assert offset >= 0
        assert length > 0
        assert offset + length <= size
        assert offset >= previous_end, "the ranges overlap or are out of order"
        previous_end = offset + length


def test_allocated_ranges_of_an_empty_file_is_empty(tmp_path):
    sink = tmp_path / "empty.bin"
    sink.write_bytes(b"")
    assert allocated_ranges(str(sink)) == []


def test_sparse_state_of_a_fresh_file_is_a_boolean(tmp_path):
    sink = tmp_path / "state.bin"
    sink.write_bytes(b"z")
    assert isinstance(sparse_state(str(sink)), bool)


def test_visible_smoke_suite_still_passes():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    smoke = os.path.join(here, "test_wsparse_basic.py")
    assert os.path.isfile(smoke), "the visible smoke suite was not staged next to this file"
    env = dict(os.environ)
    env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", smoke],
        cwd=root, capture_output=True, text=True, env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
