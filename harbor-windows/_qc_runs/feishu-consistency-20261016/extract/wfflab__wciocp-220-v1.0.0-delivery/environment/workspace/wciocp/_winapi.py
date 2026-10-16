"""Thin ctypes bindings for the Win32 calls that :mod:`wciocp` needs.

Only what the current implementation actually calls is bound here; ``kernel32``
is loaded lazily so that importing the package stays cheap.
"""

import ctypes
import os
from ctypes import wintypes

from .errors import WCIOCPError

# ---------------------------------------------------------------- constants

ERROR_SUCCESS = 0
ERROR_INVALID_HANDLE = 6
ERROR_INVALID_PARAMETER = 87
ERROR_NOT_ENOUGH_MEMORY = 8
ERROR_IO_PENDING = 997
ERROR_HANDLE_EOF = 38

WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF

_IS_WINDOWS = os.name == "nt"

_kernel32 = None


class OVERLAPPED(ctypes.Structure):
    """The asynchronous-I/O control block handed to ``ReadFile``.

    ``hEvent`` carries the manual-reset event that the system signals once the
    read it belongs to has finished; ``InternalHigh`` carries the number of
    bytes that were transferred.
    """

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
        raise WCIOCPError(
            "the completion layer needs the Win32 API, which exists only on Windows",
            kind="unsupported",
        )
    if _kernel32 is None:
        if not _win32_types_ok():
            raise WCIOCPError(
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
        raise WCIOCPError("handle must be an integer, got %r" % (handle,), kind="badarg")
    return int(handle)


def error_kind(error):
    """Classify a Win32 error code for :class:`WCIOCPError`."""
    if error in (ERROR_INVALID_HANDLE, ERROR_INVALID_PARAMETER):
        return "badarg"
    return "os"


def describe(error):
    """A short human-readable name for a Win32 error code."""
    names = {
        ERROR_SUCCESS: "ERROR_SUCCESS",
        ERROR_INVALID_HANDLE: "ERROR_INVALID_HANDLE",
        ERROR_INVALID_PARAMETER: "ERROR_INVALID_PARAMETER",
        ERROR_NOT_ENOUGH_MEMORY: "ERROR_NOT_ENOUGH_MEMORY",
        ERROR_IO_PENDING: "ERROR_IO_PENDING",
        ERROR_HANDLE_EOF: "ERROR_HANDLE_EOF",
    }
    label = names.get(int(error))
    if label is None:
        return "Win32 error %d" % int(error)
    return "%s (%d)" % (label, int(error))


# --------------------------------------------------------------- common I/O

def as_text(value):
    """Return a Win32 string argument as text."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def create_named_pipe(name, open_mode=None, max_instances=1, out_size=65536,
                      in_size=65536, timeout=0):
    """Create a named-pipe end and return its handle number.

    ``open_mode`` defaults to a duplex pipe opened for overlapping use.
    """
    kernel32 = _kernel32_dll()
    create_pipe = kernel32.CreateNamedPipeW
    create_pipe.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                            wintypes.DWORD, wintypes.LPVOID]
    create_pipe.restype = wintypes.HANDLE

    if open_mode is None:
        open_mode = PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED
    handle = create_pipe(as_text(name), int(open_mode), PIPE_TYPE_BYTE,
                         int(max_instances), int(out_size), int(in_size),
                         int(timeout), None)
    if not handle or int(handle) == INVALID_HANDLE_VALUE:
        error = last_error()
        raise WCIOCPError(
            "the pipe %r could not be created (%s)" % (name, describe(error)),
            kind=error_kind(error),
        )
    return int(handle)


def open_file(name, access=None, share=0, flags=None):
    """Open an existing object by name and return its handle number."""
    kernel32 = _kernel32_dll()
    open_it = kernel32.CreateFileW
    open_it.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                        wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                        wintypes.HANDLE]
    open_it.restype = wintypes.HANDLE

    if access is None:
        access = FILE_GENERIC_READ | FILE_GENERIC_WRITE
    if flags is None:
        flags = FILE_FLAG_OVERLAPPED
    handle = open_it(as_text(name), int(access), int(share), None,
                     OPEN_EXISTING, int(flags), None)
    if not handle or int(handle) == INVALID_HANDLE_VALUE:
        error = last_error()
        raise WCIOCPError(
            "the object %r could not be opened (%s)" % (name, describe(error)),
            kind=error_kind(error),
        )
    return int(handle)


def close_handle(handle):
    """Close an object handle, ignoring handles that are already gone."""
    if not is_usable_handle(handle):
        return
    try:
        kernel32 = _kernel32_dll()
        close_it = kernel32.CloseHandle
        close_it.argtypes = [wintypes.HANDLE]
        close_it.restype = wintypes.BOOL
        close_it(wintypes.HANDLE(int(handle)))
    except Exception:
        # Releasing an object must never be the thing that fails a caller.
        pass


# ------------------------------------------------------------- kernel events

class Event(object):
    """A manual-reset kernel event, used to carry one read's completion."""

    def __init__(self, handle):
        self.handle = int(handle)

    @classmethod
    def create(cls):
        """Create an unsignalled manual-reset event."""
        kernel32 = _kernel32_dll()
        create_event = kernel32.CreateEventW
        create_event.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL,
                                 wintypes.LPCWSTR]
        create_event.restype = wintypes.HANDLE
        handle = create_event(None, True, False, None)
        if not handle:
            error = last_error()
            raise WCIOCPError(
                "the completion event could not be created (%s)" % describe(error),
                kind="os",
            )
        return cls(int(handle))

    def wait(self, timeout_ms):
        """Wait for the event and report how the wait ended.

        Returns one of ``"signalled"``, ``"timeout"`` or ``"error"``.
        """
        kernel32 = _kernel32_dll()
        wait = kernel32.WaitForSingleObject
        wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        wait.restype = wintypes.DWORD

        status = int(wait(wintypes.HANDLE(self.handle), wintypes.DWORD(int(timeout_ms))))
        if status == WAIT_TIMEOUT:
            return "timeout"
        if status == WAIT_FAILED:
            return "error"
        return "signalled"

    def close(self):
        """Release the event."""
        close_handle(self.handle)

    def __repr__(self):
        return "Event(handle=%d)" % self.handle


# --------------------------------------------------------------- operations

def start_read(handle, buffer, size, offset, overlapped):
    """Issue a ``ReadFile`` for ``handle`` and report how it ended.

    Returns ``(ok, error)``: ``ok`` is the ``ReadFile`` result and ``error`` is
    the Win32 error code that came with it.
    """
    kernel32 = _kernel32_dll()
    read_file = kernel32.ReadFile
    read_file.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD),
                          ctypes.POINTER(OVERLAPPED)]
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


def transferred_bytes(overlapped):
    """The byte count that the system wrote into an overlapping control block."""
    return int(overlapped.InternalHigh or 0)


def wait_for(event_handle, timeout_ms):
    """Wait for one kernel event and report how the wait ended."""
    kernel32 = _kernel32_dll()
    wait = kernel32.WaitForSingleObject
    wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait.restype = wintypes.DWORD

    status = int(wait(wintypes.HANDLE(int(event_handle)), wintypes.DWORD(int(timeout_ms))))
    if status == WAIT_TIMEOUT:
        return "timeout"
    if status == WAIT_FAILED:
        return "error"
    return "signalled"


# ------------------------------------------------------------- open modes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_GENERIC_READ = 0x0012019F
FILE_GENERIC_WRITE = 0x00120116
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
FILE_FLAG_OVERLAPPED = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
