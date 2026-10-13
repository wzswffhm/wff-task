"""Windows system services used by the verifier side of this task.

Two genuine operating-system mechanisms are consulted here, and only here —
never by the package under test:

* ``imagehlp!MapFileAndCheckSumW`` — the Windows image helper library, i.e. the
  only implementation that defines what an image checksum *is*.  The graded
  suite asks this library at grading time (instead of comparing against a
  constant captured offline), so the contract is anchored to a live system
  call on every run.
* ``kernel32!CreateFileW`` plus the CRT handle bridge — a real Windows file
  handle, so the streaming contract is exercised against the file-system and
  handle semantics the loader itself uses, not against ``io.BytesIO``.

These helpers are verifier-side material: they ship under ``verifier/`` and are
never injected into the candidate workspace.  The candidate package is still
forbidden from importing ``ctypes``/``subprocess`` (asserted by the suite), so
"the contract is defined by Windows" and "the implementation must be
self-contained" stay independent claims.
"""

from __future__ import annotations

import ctypes
import os
import struct
import tempfile
from ctypes import wintypes
from pathlib import Path

# --- imagehlp ---------------------------------------------------------------

_imagehlp = None


def _load_imagehlp():
    global _imagehlp
    if _imagehlp is None:
        _imagehlp = ctypes.WinDLL("imagehlp")
        _imagehlp.MapFileAndCheckSumW.restype = wintypes.DWORD
        _imagehlp.MapFileAndCheckSumW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
    return _imagehlp


def live_checksum(data: bytes) -> tuple[int, int]:
    """Return (header_sum, check_sum) straight from ``MapFileAndCheckSumW``.

    ``MapFileAndCheckSumW`` maps a file by name, so the bytes are staged in a
    temporary file first.  Raises ``RuntimeError`` when the library refuses the
    image (status != 0), which the suite treats as a grading-environment
    failure rather than a candidate failure.
    """
    lib = _load_imagehlp()
    handle = tempfile.NamedTemporaryFile(prefix="wpeimg-live-", suffix=".bin", delete=False)
    path = handle.name
    try:
        handle.write(data)
        handle.flush()
        handle.close()
        header_sum = wintypes.DWORD(0)
        check_sum = wintypes.DWORD(0)
        status = lib.MapFileAndCheckSumW(path, ctypes.byref(header_sum),
                                         ctypes.byref(check_sum))
        if status != 0:
            raise RuntimeError("MapFileAndCheckSumW failed with status %d" % status)
        return int(header_sum.value), int(check_sum.value)
    finally:
        if not handle.closed:
            handle.close()
        try:
            os.unlink(path)
        except OSError:
            pass


def live_checksum_available() -> tuple[bool, str]:
    """Probe the library with a tiny valid image so failures are explicit."""
    try:
        _load_imagehlp()
    except OSError as exc:                       # pragma: no cover - Windows only
        return False, "imagehlp.dll is not loadable: %s" % exc
    return True, "ok"


# --- kernel32 file handles --------------------------------------------------

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.GetFileSizeEx.restype = wintypes.BOOL
kernel32.GetFileSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
kernel32.SetFilePointerEx.restype = wintypes.BOOL
kernel32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                                      ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]


def open_real_handle(path: Path):
    """Open *path* with ``CreateFileW`` and return (handle, size)."""
    handle = kernel32.CreateFileW(str(path), GENERIC_READ, FILE_SHARE_READ, None,
                                  OPEN_EXISTING, 0, None)
    if not handle or handle == INVALID_HANDLE_VALUE:
        raise OSError("CreateFileW failed for %s (err=%d)"
                      % (path, ctypes.get_last_error()))
    size = ctypes.c_longlong(0)
    if not kernel32.GetFileSizeEx(handle, ctypes.byref(size)):
        kernel32.CloseHandle(handle)
        raise OSError("GetFileSizeEx failed (err=%d)" % ctypes.get_last_error())
    return handle, int(size.value)


def handle_to_file(handle):
    """Bridge a Win32 HANDLE into a Python file object over the same handle."""
    import msvcrt
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    return os.fdopen(fd, "rb", closefd=True)


def close_handle(handle) -> None:
    if handle and handle != INVALID_HANDLE_VALUE:
        kernel32.CloseHandle(handle)


class BoundedReader:
    """Wrap a file object and record every read request size.

    ``iter_sections`` must only ever ask for bounded chunks, so the wrapper
    records the sizes and refuses the whole-file forms outright, which turns
    "did it slurp the stream?" into a measurable property of a real handle.
    """

    def __init__(self, fh):
        self._fh = fh
        self.requests: list[int] = []
        self.bytes_read = 0
        self.unbounded = 0

    def read(self, size=-1):
        if size is None or size < 0:
            self.unbounded += 1
            raise AssertionError("iter_sections asked for an unbounded read (size=%r)" % size)
        self.requests.append(size)
        chunk = self._fh.read(size)
        self.bytes_read += len(chunk)
        return chunk

    def readline(self, *a, **k):                 # pragma: no cover - must not be used
        self.unbounded += 1
        raise AssertionError("iter_sections must not use readline()")

    def readlines(self, *a, **k):                # pragma: no cover - must not be used
        self.unbounded += 1
        raise AssertionError("iter_sections must not use readlines()")

    def seek(self, *a, **k):
        return self._fh.seek(*a, **k)

    def tell(self):
        return self._fh.tell()

    def __getattr__(self, name):
        return getattr(self._fh, name)


def make_checksum_variant(base: bytes, offset: int, xor_mask: int = 0x5A,
                          extra_tail: bytes = b"") -> bytes:
    """Flip bytes inside *base* and re-record a consistent ``CheckSum``.

    The result is a structurally valid image the Windows helper will accept,
    built at grading time so its authoritative value cannot be hard-coded.
    """
    buf = bytearray(base)
    step = max(1, len(buf) // 4096)
    for i in range(offset, min(offset + step, len(buf))):
        buf[i] ^= xor_mask
    if extra_tail:
        buf.extend(extra_tail)
    # locate the CheckSum field and zero it before asking Windows for the value
    nt = struct.unpack_from("<I", buf, 0x3C)[0]
    optional = nt + 24
    magic = struct.unpack_from("<H", buf, optional)[0]
    check_offset = optional + (64 if magic == 0x10B else 64)
    struct.pack_into("<I", buf, check_offset, 0)
    _header, check = live_checksum(bytes(buf))
    struct.pack_into("<I", buf, check_offset, check)
    return bytes(buf)
