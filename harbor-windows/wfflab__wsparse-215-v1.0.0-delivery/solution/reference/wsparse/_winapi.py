"""ctypes bindings for the Win32 calls the wsparse contract needs.

Everything the module does to a sink passes through this file: the sparse-file
control codes travel over ``DeviceIoControl``, the file length is set with
``SetFilePointerEx`` + ``SetEndOfFile``, and the physical size is read with
``GetCompressedFileSizeW`` and ``GetFileInformationByHandleEx``.

The DLL is loaded lazily, on first use, so that importing the package on a
platform without the Win32 API stays cheap and predictable.
"""

import ctypes
import os
from ctypes import wintypes

# ---- access and sharing -----------------------------------------------------
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007

# ---- creation dispositions --------------------------------------------------
CREATE_NEW = 1
CREATE_ALWAYS = 2
OPEN_EXISTING = 3
OPEN_ALWAYS = 4

# ---- attributes and flags ---------------------------------------------------
FILE_ATTRIBUTE_NORMAL = 0x00000080
SPARSE_ATTRIBUTE = 0x00000200  # FILE_ATTRIBUTE_SPARSE_FILE
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

# ---- move methods -----------------------------------------------------------
FILE_BEGIN = 0

# ---- control codes ----------------------------------------------------------
FSCTL_SET_SPARSE = 0x000900C4
FSCTL_QUERY_ALLOCATED_RANGES = 0x000940CF
FSCTL_SET_ZERO_DATA = 0x000980C8

# ---- Win32 error codes that mean "this object cannot do that" ---------------
ERROR_INVALID_FUNCTION = 1
ERROR_NOT_SUPPORTED = 50
ERROR_INVALID_PARAMETER = 87
UNSUPPORTED_ERRORS = (ERROR_INVALID_FUNCTION, ERROR_NOT_SUPPORTED, ERROR_INVALID_PARAMETER)

# ---- GetFileInformationByHandleEx classes -----------------------------------
FileStandardInfo = 1

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_IS_WINDOWS = os.name == "nt"

_kernel32 = None


class FILE_STANDARD_INFO(ctypes.Structure):
    _fields_ = [
        ("AllocationSize", ctypes.c_longlong),
        ("EndOfFile", ctypes.c_longlong),
        ("NumberOfLinks", wintypes.DWORD),
        ("DeletePending", ctypes.c_ubyte),
        ("Directory", ctypes.c_ubyte),
    ]


class FILE_ALLOCATED_RANGE_BUFFER(ctypes.Structure):
    _fields_ = [("FileOffset", ctypes.c_longlong), ("Length", ctypes.c_longlong)]


class FILE_SET_SPARSE_BUFFER(ctypes.Structure):
    _fields_ = [("SetSparse", ctypes.c_ubyte)]


def is_windows():
    """Return ``True`` when running on a Windows kernel."""
    return _IS_WINDOWS


def kind_for_error(error):
    """Map a Win32 error code onto the :class:`WSParseError` taxonomy."""
    if error in UNSUPPORTED_ERRORS:
        return "unsupported"
    return "os"


def _declare(kernel32):
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL
    kernel32.SetFilePointerEx.argtypes = [
        wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
    ]
    kernel32.SetFilePointerEx.restype = wintypes.BOOL
    kernel32.SetEndOfFile.argtypes = [wintypes.HANDLE]
    kernel32.SetEndOfFile.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel32.GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetCompressedFileSizeW.restype = wintypes.DWORD


def kernel32():
    """Load (once) and return the declared kernel32 entry points."""
    global _kernel32
    if _kernel32 is None:
        if not _IS_WINDOWS:
            raise OSError("the Win32 file-system API is only available on Windows")
        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        _declare(dll)
        _kernel32 = dll
    return _kernel32


def last_error():
    return ctypes.get_last_error()


# ---- handles ----------------------------------------------------------------

def open_file(path, access, disposition=OPEN_EXISTING, flags=FILE_ATTRIBUTE_NORMAL):
    """Open ``path`` and return its handle, or raise ``OSError``."""
    handle = kernel32().CreateFileW(
        str(path), access, FILE_SHARE_ALL, None, disposition, flags, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise OSError(last_error(), "CreateFileW failed", str(path))
    return handle


def close_handle(handle):
    if handle is not None:
        kernel32().CloseHandle(handle)


# ---- control codes ----------------------------------------------------------

def set_sparse(handle, enabled=True):
    """Issue ``FSCTL_SET_SPARSE``. Returns ``(ok, error)``."""
    request = FILE_SET_SPARSE_BUFFER(1 if enabled else 0)
    returned = wintypes.DWORD(0)
    ok = kernel32().DeviceIoControl(
        handle, FSCTL_SET_SPARSE, ctypes.byref(request), ctypes.sizeof(request),
        None, 0, ctypes.byref(returned), None,
    )
    return bool(ok), last_error()


def query_allocated_ranges(handle, offset, length):
    """Issue ``FSCTL_QUERY_ALLOCATED_RANGES``.

    Returns ``(ranges, error)``; ``ranges`` is ``None`` when the call failed.
    """
    if length <= 0:
        return [], 0
    request = FILE_ALLOCATED_RANGE_BUFFER(offset, length)
    entry = ctypes.sizeof(FILE_ALLOCATED_RANGE_BUFFER)
    capacity = 512
    result = (FILE_ALLOCATED_RANGE_BUFFER * capacity)()
    returned = wintypes.DWORD(0)
    ok = kernel32().DeviceIoControl(
        handle, FSCTL_QUERY_ALLOCATED_RANGES, ctypes.byref(request), entry,
        ctypes.byref(result), entry * capacity, ctypes.byref(returned), None,
    )
    if not ok:
        return None, last_error()
    count = returned.value // entry
    return [(result[i].FileOffset, result[i].Length) for i in range(count)], 0


# ---- length and size --------------------------------------------------------

def set_file_length(handle, size):
    """Move the end-of-file marker, without writing a single data byte."""
    new_position = ctypes.c_longlong(0)
    if not kernel32().SetFilePointerEx(
            handle, ctypes.c_longlong(size), ctypes.byref(new_position), FILE_BEGIN):
        raise OSError(last_error(), "SetFilePointerEx failed")
    if not kernel32().SetEndOfFile(handle):
        raise OSError(last_error(), "SetEndOfFile failed")


def flush(handle):
    """Commit pending metadata: allocation counters lag writes until this runs."""
    if not kernel32().FlushFileBuffers(handle):
        raise OSError(last_error(), "FlushFileBuffers failed")


def standard_info(handle):
    info = FILE_STANDARD_INFO()
    ok = kernel32().GetFileInformationByHandleEx(
        handle, FileStandardInfo, ctypes.byref(info), ctypes.sizeof(info))
    if not ok:
        raise OSError(last_error(), "GetFileInformationByHandleEx failed")
    return info


def allocation_size(handle):
    """Cluster-aligned number of bytes the file system has backed with space."""
    return standard_info(handle).AllocationSize


def file_length(handle):
    """Logical length of the file behind ``handle``."""
    return standard_info(handle).EndOfFile


def compressed_file_size(path):
    """Physical size of ``path`` without opening a handle of our own."""
    high = wintypes.DWORD(0)
    low = kernel32().GetCompressedFileSizeW(str(path), ctypes.byref(high))
    if low == 0xFFFFFFFF:
        error = last_error()
        if error != 0:
            raise OSError(error, "GetCompressedFileSizeW failed", str(path))
    return (high.value << 32) | low
