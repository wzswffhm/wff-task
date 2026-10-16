"""Thin ctypes bindings for the Win32 calls that :mod:`wcancel` needs.

Only what the current implementation actually calls is bound here; ``kernel32``
is loaded lazily so that importing the package stays cheap.
"""

import ctypes
import os
from ctypes import wintypes

from .errors import WCancelError

# ---------------------------------------------------------------- constants

FILE_TYPE_UNKNOWN = 0x0000
FILE_TYPE_DISK = 0x0001
FILE_TYPE_CHAR = 0x0002
FILE_TYPE_PIPE = 0x0003
FILE_TYPE_REMOTE = 0x8000

ERROR_SUCCESS = 0
ERROR_INVALID_HANDLE = 6
ERROR_INVALID_PARAMETER = 87
ERROR_OPERATION_ABORTED = 995
ERROR_IO_INCOMPLETE = 996
ERROR_IO_PENDING = 997
ERROR_NOT_FOUND = 1168

WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF

FILE_MODE_INFORMATION_CLASS = 16

_IS_WINDOWS = os.name == "nt"

_kernel32 = None


class FILE_MODE_INFORMATION(ctypes.Structure):
    """Payload of ``GetFileInformationByHandleEx(FileModeInformation)``."""

    _fields_ = [("Mode", wintypes.DWORD)]


class OVERLAPPED(ctypes.Structure):
    """The asynchronous-I/O control block handed to ``ReadFile``/``WriteFile``."""

    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


def is_windows():
    """Return ``True`` when running on a Windows kernel."""
    return _IS_WINDOWS


def _win32_types_ok():
    """Whether the standard-library Win32 type aliases are usable here."""
    return all(hasattr(wintypes, name)
               for name in ("HANDLE", "DWORD", "BOOL", "LPCWSTR", "LPVOID"))


def _kernel32_dll():
    """The shared ``kernel32`` instance, loaded on first use."""
    global _kernel32
    if not _IS_WINDOWS:
        raise WCancelError(
            "overlapping I/O requires the Win32 API, which exists only on Windows",
            kind="unsupported",
        )
    if _kernel32 is None:
        if not _win32_types_ok():
            raise WCancelError(
                "this interpreter does not expose the Win32 ctypes types",
                kind="unsupported",
            )
        _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return _kernel32


def last_error():
    """The Win32 error code left by the most recent call."""
    return int(ctypes.get_last_error())


def is_usable_handle(handle):
    """Whether ``handle`` is a non-null object handle."""
    return isinstance(handle, int) and not isinstance(handle, bool) and handle > 0


def as_number(handle):
    """Return ``handle`` as an integer handle number.

    Anything that is not an integer handle is reported as an unusable argument.
    """
    if isinstance(handle, bool) or not isinstance(handle, int):
        raise WCancelError("handle must be an integer, got %r" % (handle,), kind="badarg")
    return int(handle)


def error_kind(error):
    """Classify a Win32 error code for :class:`WCancelError`."""
    if error in (ERROR_INVALID_HANDLE, ERROR_INVALID_PARAMETER):
        return "badarg"
    return "os"


def describe(error):
    """A short human-readable name for a Win32 error code."""
    names = {
        ERROR_INVALID_HANDLE: "ERROR_INVALID_HANDLE",
        ERROR_INVALID_PARAMETER: "ERROR_INVALID_PARAMETER",
        ERROR_OPERATION_ABORTED: "ERROR_OPERATION_ABORTED",
        ERROR_IO_INCOMPLETE: "ERROR_IO_INCOMPLETE",
        ERROR_IO_PENDING: "ERROR_IO_PENDING",
        ERROR_NOT_FOUND: "ERROR_NOT_FOUND",
    }
    label = names.get(int(error))
    if label is None:
        return "Win32 error %d" % int(error)
    return "%s (%d)" % (label, int(error))


# --------------------------------------------------------------- operations

def open_event():
    """Create the manual-reset event that carries one request's completion."""
    kernel32 = _kernel32_dll()
    create_event = kernel32.CreateEventW
    create_event.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    create_event.restype = wintypes.HANDLE
    event = create_event(None, True, False, None)
    if not event:
        raise WCancelError(
            "the completion event could not be created (%s)" % describe(last_error()),
            kind="os",
        )
    return int(event)


def close(handle):
    """Close an object handle, ignoring handles that are already gone."""
    if not is_usable_handle(handle):
        return
    try:
        kernel32 = _kernel32_dll()
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL
        close_handle(wintypes.HANDLE(int(handle)))
    except Exception:
        # Releasing an object must never be the thing that fails a caller.
        pass


def file_type(handle):
    """Return the ``GetFileType`` value for an object handle."""
    kernel32 = _kernel32_dll()
    get_file_type = kernel32.GetFileType
    get_file_type.argtypes = [wintypes.HANDLE]
    get_file_type.restype = wintypes.DWORD
    return int(get_file_type(wintypes.HANDLE(int(handle))))


def file_mode(handle):
    """Return the ``Mode`` word of ``GetFileInformationByHandleEx``."""
    kernel32 = _kernel32_dll()
    query = kernel32.GetFileInformationByHandleEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    query.restype = wintypes.BOOL
    info = FILE_MODE_INFORMATION()
    ok = query(wintypes.HANDLE(int(handle)), FILE_MODE_INFORMATION_CLASS,
               ctypes.byref(info), ctypes.sizeof(info))
    if not ok:
        error = last_error()
        raise WCancelError(
            "the mode of object %r could not be read (%s)" % (handle, describe(error)),
            kind=error_kind(error),
            handle=handle,
        )
    return int(info.Mode)


def start_read(handle, buffer, size, offset, overlapped):
    """Issue a ``ReadFile`` for ``handle`` and report how it ended.

    Returns ``(ok, error)``: ``ok`` is the ``ReadFile`` result and ``error`` is
    the Win32 error code that came with it.
    """
    kernel32 = _kernel32_dll()
    read_file = kernel32.ReadFile
    read_file.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)]
    read_file.restype = wintypes.BOOL

    # The byte offset of the request lives in the control block, split into its
    # low and high halves; named pipes ignore both halves.
    overlapped.Offset = int(offset) & 0xFFFFFFFF
    overlapped.OffsetHigh = (int(offset) >> 32) & 0xFFFFFFFF

    transferred = wintypes.DWORD(0)
    ok = read_file(wintypes.HANDLE(int(handle)), buffer, int(size),
                   ctypes.byref(transferred), ctypes.byref(overlapped))
    if ok:
        return True, ERROR_SUCCESS
    return False, last_error()


def wait_for_read(handle, overlapped, event, timeout_ms):
    """Wait for one outstanding read and report how it ended.

    Returns ``(outcome, bytes_read, error)`` with ``outcome`` one of
    ``"completed"``, ``"timeout"`` or ``"error"``.
    """
    kernel32 = _kernel32_dll()
    wait = kernel32.WaitForSingleObject
    wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait.restype = wintypes.DWORD

    status = int(wait(wintypes.HANDLE(int(event)), wintypes.DWORD(int(timeout_ms))))
    if status == WAIT_TIMEOUT:
        return "timeout", 0, ERROR_IO_INCOMPLETE
    if status == WAIT_FAILED:
        error = last_error()
        raise WCancelError(
            "waiting for the request failed (%s)" % describe(error),
            kind=error_kind(error),
            handle=handle,
        )

    completed, error, transferred = read_status(handle, overlapped)
    if completed:
        return "completed", transferred, ERROR_SUCCESS
    return "error", transferred, error


def read_status(handle, overlapped):
    """Read the state of one request without blocking.

    Returns ``(completed, error, bytes_read)``.
    """
    kernel32 = _kernel32_dll()
    result = kernel32.GetOverlappedResult
    result.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED),
                       ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
    result.restype = wintypes.BOOL

    transferred = wintypes.DWORD(0)
    ok = result(wintypes.HANDLE(int(handle)), ctypes.byref(overlapped),
                ctypes.byref(transferred), False)
    if ok:
        return True, ERROR_SUCCESS, int(transferred.value)
    return False, last_error(), int(transferred.value)


def cancel(handle):
    """Ask the system to abandon the I/O that this thread has outstanding.

    Returns ``True`` when the system accepted the request.
    """
    kernel32 = _kernel32_dll()
    cancel_io = kernel32.CancelIo
    cancel_io.argtypes = [wintypes.HANDLE]
    cancel_io.restype = wintypes.BOOL

    ok = cancel_io(wintypes.HANDLE(int(handle)))
    if not ok:
        error = last_error()
        raise WCancelError(
            "the outstanding I/O of object %r could not be abandoned (%s)"
            % (handle, describe(error)),
            kind=error_kind(error),
            handle=handle,
        )
    return True
