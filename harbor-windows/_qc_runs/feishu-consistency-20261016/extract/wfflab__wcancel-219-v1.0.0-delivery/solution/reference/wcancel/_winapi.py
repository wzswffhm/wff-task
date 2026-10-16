"""ctypes bindings for the Win32 calls the wcancel contract needs.

Every byte the module reads travels through this file.  A request is issued with
``ReadFile`` plus an ``OVERLAPPED``, its completion event is awaited with
``WaitForSingleObject``, its terminal state is read back with
``GetOverlappedResult`` -- which reports the *original* error of the request --
and the cancellation itself is ``CancelIoEx``, the one call that names a single
outstanding request and works from any thread.

Two kernel facts shape the bindings below:

* ``CancelIoEx(handle, &overlapped)`` is per-request.  ``CancelIo(handle)`` is
  not: it cancels every request the *calling thread* issued on the handle, and
  from another thread it succeeds while cancelling nothing.
* Whether a handle can carry overlapped I/O at all is recorded in the file
  object, not in ``GetFileType``.  A handle opened without
  ``FILE_FLAG_OVERLAPPED`` happily accepts a pointer to an ``OVERLAPPED`` and
  finishes the read as if it had been synchronous, so the flag has to be read
  directly; ``NtQueryInformationFile(FileModeInformation)`` is what exposes it.
"""

import ctypes
import os
from ctypes import wintypes

# ---- access and sharing -----------------------------------------------------
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007

# ---- creation dispositions and flags ----------------------------------------
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_FLAG_OVERLAPPED = 0x40000000

# ---- GetFileType values -----------------------------------------------------
FILE_TYPE_UNKNOWN = 0x0000
FILE_TYPE_DISK = 0x00000001
FILE_TYPE_CHAR = 0x00000002
FILE_TYPE_PIPE = 0x00000003
FILE_TYPE_REMOTE = 0x00008000

# ---- the file object's own mode (FILE_INFORMATION_CLASS) --------------------
FILE_MODE_INFORMATION = 16
FILE_SYNCHRONOUS_IO_ALERT = 0x0010
FILE_SYNCHRONOUS_IO_NONALERT = 0x0020
SYNCHRONOUS_MODE_BITS = FILE_SYNCHRONOUS_IO_ALERT | FILE_SYNCHRONOUS_IO_NONALERT

# ---- NTSTATUS values --------------------------------------------------------
STATUS_SUCCESS = 0x00000000
STATUS_INVALID_HANDLE = 0xC0000008
STATUS_INVALID_INFO_CLASS = 0xC0000003
STATUS_INVALID_PARAMETER = 0xC000000D
STATUS_NOT_SUPPORTED = 0xC00000BB
STATUS_INVALID_DEVICE_REQUEST = 0xC0000010

# ---- Win32 error codes ------------------------------------------------------
ERROR_INVALID_FUNCTION = 1
ERROR_INVALID_HANDLE = 6
ERROR_NOT_ENOUGH_MEMORY = 8
ERROR_HANDLE_EOF = 38
ERROR_NOT_SUPPORTED = 50
ERROR_INVALID_PARAMETER = 87
ERROR_BROKEN_PIPE = 109
ERROR_OPERATION_ABORTED = 995
ERROR_IO_INCOMPLETE = 996
ERROR_IO_PENDING = 997
ERROR_NOT_FOUND = 1168

# ---- wait results -----------------------------------------------------------
WAIT_OBJECT_0 = 0x00000000
WAIT_ABANDONED = 0x00000080
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_IS_WINDOWS = os.name == "nt"

_kernel32 = None
_ntdll = None


class OVERLAPPED(ctypes.Structure):
    """The kernel's per-request bookkeeping block for an overlapped call.

    The request is identified by the *address* of this structure, so it has to
    outlive the call: the module keeps one block per :class:`Request`.
    """

    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


class IO_STATUS_BLOCK(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_void_p)]


def is_windows():
    """Return ``True`` when running on a Windows kernel."""
    return _IS_WINDOWS


def kind_for_error(error):
    """Map a Win32 error code onto the :class:`WCancelError` taxonomy."""
    if error in (ERROR_INVALID_HANDLE, ERROR_INVALID_PARAMETER, ERROR_INVALID_FUNCTION,
                 ERROR_NOT_ENOUGH_MEMORY):
        return "badarg"
    if error == ERROR_NOT_SUPPORTED:
        return "unsupported"
    return "os"


def _declare_kernel32(kernel32):
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL,
                                      wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.GetFileType.argtypes = [wintypes.HANDLE]
    kernel32.GetFileType.restype = wintypes.DWORD
    kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED)]
    kernel32.CancelIoEx.restype = wintypes.BOOL
    kernel32.GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED),
                                             ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
    kernel32.GetOverlappedResult.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD


def _declare_ntdll(ntdll):
    ntdll.NtQueryInformationFile.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO_STATUS_BLOCK),
                                             wintypes.LPVOID, wintypes.ULONG, ctypes.c_int]
    ntdll.NtQueryInformationFile.restype = ctypes.c_long


def kernel32():
    """Load (once) and return the declared kernel32 entry points."""
    global _kernel32
    if _kernel32 is None:
        if not _IS_WINDOWS:
            raise OSError("the Win32 overlapped-I/O API is only available on Windows")
        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        _declare_kernel32(dll)
        _kernel32 = dll
    return _kernel32


def ntdll():
    """Load (once) and return the declared ntdll entry point.

    ``NtQueryInformationFile`` returns an ``NTSTATUS`` directly, so this DLL is
    loaded without ``use_last_error`` -- there is no last-error to race with.
    """
    global _ntdll
    if _ntdll is None:
        if not _IS_WINDOWS:
            raise OSError("the NT object API is only available on Windows")
        dll = ctypes.WinDLL("ntdll")
        _declare_ntdll(dll)
        _ntdll = dll
    return _ntdll


def last_error():
    """The Win32 error left by the most recent ``use_last_error`` call."""
    return ctypes.get_last_error()


# ---- object inspection ------------------------------------------------------

def file_type(handle):
    """Return the ``GetFileType`` value for an object handle."""
    return int(kernel32().GetFileType(wintypes.HANDLE(int(handle))))


def query_mode(handle):
    """Read the file object's mode bits.  Returns ``(status, mode)``.

    The ``FileModeInformation`` class is the only place the kernel publishes the
    synchronous-I/O flag that ``CreateFileW`` sets when ``FILE_FLAG_OVERLAPPED``
    is absent.  A null or stale handle comes back as ``STATUS_INVALID_HANDLE``.
    """
    mode = wintypes.DWORD(0)
    block = IO_STATUS_BLOCK()
    status = ntdll().NtQueryInformationFile(
        wintypes.HANDLE(int(handle)), ctypes.byref(block), ctypes.byref(mode),
        ctypes.sizeof(mode), FILE_MODE_INFORMATION)
    return int(status) & 0xFFFFFFFF, int(mode.value)


def close(handle):
    """Close a kernel object handle; ignore an already-invalid one."""
    if handle in (None, 0, INVALID_HANDLE_VALUE):
        return
    try:
        kernel32().CloseHandle(wintypes.HANDLE(int(handle)))
    except (OSError, ValueError):
        pass


# ---- the overlapped request -------------------------------------------------

def create_overlapped(offset):
    """A fresh ``OVERLAPPED`` for ``offset`` with its own manual-reset event.

    Returns ``(overlapped, event)``.  The event is what makes waiting on *this*
    request possible without touching the handle's other outstanding reads.
    """
    overlapped = OVERLAPPED()
    overlapped.Offset = offset & 0xFFFFFFFF
    overlapped.OffsetHigh = (offset >> 32) & 0xFFFFFFFF
    event = kernel32().CreateEventW(None, True, False, None)
    if not event:
        raise OSError(last_error(), "CreateEventW failed")
    overlapped.hEvent = event
    return overlapped, event


def read_overlapped(handle, buffer, size, overlapped):
    """Issue one overlapped read.  Returns ``(ok, error, transferred)``.

    ``ok`` is ``True`` when the read finished inside the call; ``False`` with
    ``ERROR_IO_PENDING`` means the request is now outstanding and the kernel
    will signal ``overlapped.hEvent`` when it ends.
    """
    got = wintypes.DWORD(0)
    ok = kernel32().ReadFile(wintypes.HANDLE(int(handle)), ctypes.cast(buffer, wintypes.LPVOID),
                             wintypes.DWORD(size), ctypes.byref(got),
                             ctypes.byref(overlapped))
    return bool(ok), last_error(), int(got.value)


def cancel_io_ex(handle, overlapped):
    """Cancel exactly one outstanding request.  Returns ``(ok, error)``.

    ``True`` means the kernel accepted the cancellation for that request;
    ``False`` with ``ERROR_NOT_FOUND`` means the request was no longer
    outstanding -- it had already finished, so nothing was cancelled.
    """
    ok = kernel32().CancelIoEx(wintypes.HANDLE(int(handle)), ctypes.byref(overlapped))
    return bool(ok), last_error()


def get_overlapped_result(handle, overlapped, block=False):
    """Read a request's terminal state.  Returns ``(ok, error, transferred)``.

    ``ERROR_OPERATION_ABORTED`` (995) is how a cancelled request reports itself;
    ``ERROR_IO_INCOMPLETE`` (996) means it is still outstanding.
    """
    got = wintypes.DWORD(0)
    ok = kernel32().GetOverlappedResult(wintypes.HANDLE(int(handle)), ctypes.byref(overlapped),
                                        ctypes.byref(got), bool(block))
    return bool(ok), last_error(), int(got.value)


def wait_for(event, timeout_ms):
    """Wait on a completion event.  Returns the ``WaitForSingleObject`` value."""
    return int(kernel32().WaitForSingleObject(wintypes.HANDLE(int(event)),
                                              wintypes.DWORD(timeout_ms)))
