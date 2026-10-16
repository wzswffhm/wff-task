"""ctypes bindings for the Win32/IOCP calls the wciocp contract needs.

Every byte this module moves travels through this file.  The design rests on
three kernel facts, and the bindings below exist to expose exactly those:

* An **I/O completion port** is created with
  ``CreateIoCompletionPort(INVALID_HANDLE_VALUE, 0, 0, 0)``; a handle joins that
  port -- and registers its **completion key**, a ``ULONG_PTR`` the kernel keeps
  for the handle itself -- with ``CreateIoCompletionPort(handle, port, key, 0)``.
* A completion packet is dequeued **atomically** with
  ``GetQueuedCompletionStatus``.  The packet carries the key *the kernel copied
  at completion time*, the ``OVERLAPPED*`` of the request, and the transfer
  count.  Two threads calling it concurrently never see the same packet and no
  user-mode queue is involved; that is why the key can never be looked up in a
  local dictionary and why "exactly once" needs no lock in this layer.
* The dequeued ``OVERLAPPED`` reports the *terminal state* of the request, read
  back with ``GetOverlappedResult``: ``ERROR_OPERATION_ABORTED`` (995) is how a
  request killed by ``CancelIoEx`` identifies itself, and it is the only way to
  tell "cancelled" apart from "completed".

Two environment notes drove the choices here:

* ``GetFileInformationByHandleEx(FileModeInformation)`` is *not* usable on this
  host (it answers 24/87), so the capability check goes through
  ``ntdll!NtQueryInformationFile`` with ``FileModeInformation`` (class 16).  The
  mode word is ``0x0`` for an asynchronous object and carries
  ``0x20 FILE_SYNCHRONOUS_IO_NONALERT`` for a synchronous one.  A handle opened
  without ``FILE_FLAG_OVERLAPPED`` accepts an ``OVERLAPPED*`` and completes the
  read inline, so this query is the only honest test.
* ``GetQueuedCompletionStatusEx`` (the batched variant) raises an access
  violation on this host, so the pool dequeues one packet at a time.
"""

import ctypes
import os
from ctypes import wintypes

# ---- creation flags ---------------------------------------------------------
FILE_FLAG_OVERLAPPED = 0x40000000

# ---- completion-port knobs --------------------------------------------------
INFINITE = 0xFFFFFFFF
WAIT_TIMEOUT = 0x00000102

# ---- file-object mode (FILE_INFORMATION_CLASS = 16) -------------------------
FILE_MODE_INFORMATION = 16
FILE_SYNCHRONOUS_IO_ALERT = 0x0010
FILE_SYNCHRONOUS_IO_NONALERT = 0x0020
SYNCHRONOUS_MODE_BITS = FILE_SYNCHRONOUS_IO_ALERT | FILE_SYNCHRONOUS_IO_NONALERT

# ---- NTSTATUS values --------------------------------------------------------
STATUS_SUCCESS = 0x00000000
STATUS_PENDING = 0x00000103
STATUS_INVALID_HANDLE = 0xC0000008
STATUS_INVALID_PARAMETER = 0xC000000D
STATUS_INVALID_INFO_CLASS = 0xC0000003
STATUS_NOT_SUPPORTED = 0xC00000BB
STATUS_INVALID_DEVICE_REQUEST = 0xC0000010
STATUS_CANCELLED = 0xC0000120

# ---- Win32 error codes ------------------------------------------------------
ERROR_INVALID_FUNCTION = 1
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_ACCESS_DENIED = 5
ERROR_INVALID_HANDLE = 6
ERROR_NOT_ENOUGH_MEMORY = 8
ERROR_NOT_SUPPORTED = 50
ERROR_INVALID_PARAMETER = 87
ERROR_BROKEN_PIPE = 109
ERROR_SEM_TIMEOUT = 121
ERROR_OPERATION_ABORTED = 995
ERROR_IO_INCOMPLETE = 996
ERROR_IO_PENDING = 997
ERROR_NOT_FOUND = 1168
ERROR_NOT_ENOUGH_QUOTA = 1816

#: A completion key is a ``ULONG_PTR``.  The public surface exposes it as a plain
#: Python int, so it is masked to pointer width and re-signed when the top bit is
#: set -- ``-1`` registered therefore comes back as ``-1``.
KEY_BITS = 32 if ctypes.sizeof(ctypes.c_void_p) == 4 else 64
KEY_MASK = (1 << KEY_BITS) - 1
KEY_SIGN = 1 << (KEY_BITS - 1)

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_IS_WINDOWS = os.name == "nt"

_kernel32 = None
_ntdll = None


class OVERLAPPED(ctypes.Structure):
    """The kernel's per-request bookkeeping block for an overlapping call.

    A request is identified by the *address* of this structure, which is what the
    completion packet hands back, so the block has to outlive the call: the pool
    keeps exactly one per :class:`~wciocp.pool.Request`.

    ``Internal`` holds the final ``NTSTATUS`` and ``InternalHigh`` the transfer
    count once the request has finished.  ``hEvent`` is deliberately left null:
    the completion port, not an event, is the notification path, and giving the
    block an event too would add a second, redundant ordering.
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
    """Return ``True`` when the host kernel is Windows."""
    return _IS_WINDOWS


def _declare_kernel32(k32):
    k32.CreateIoCompletionPort.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                           ctypes.c_void_p, wintypes.DWORD]
    k32.CreateIoCompletionPort.restype = wintypes.HANDLE
    k32.GetQueuedCompletionStatus.argtypes = [wintypes.HANDLE,
                                              ctypes.POINTER(wintypes.DWORD),
                                              ctypes.POINTER(ctypes.c_void_p),
                                              ctypes.POINTER(ctypes.c_void_p),
                                              wintypes.DWORD]
    k32.GetQueuedCompletionStatus.restype = wintypes.BOOL
    k32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED)]
    k32.CancelIoEx.restype = wintypes.BOOL
    k32.CancelIo.argtypes = [wintypes.HANDLE]
    k32.CancelIo.restype = wintypes.BOOL
    k32.GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED),
                                        ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
    k32.GetOverlappedResult.restype = wintypes.BOOL
    k32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                             ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)]
    k32.ReadFile.restype = wintypes.BOOL
    k32.GetFileType.argtypes = [wintypes.HANDLE]
    k32.GetFileType.restype = wintypes.DWORD
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL


def _declare_ntdll(nt):
    nt.NtQueryInformationFile.argtypes = [wintypes.HANDLE,
                                          ctypes.POINTER(IO_STATUS_BLOCK),
                                          wintypes.LPVOID, wintypes.ULONG, ctypes.c_int]
    nt.NtQueryInformationFile.restype = ctypes.c_long


def kernel32():
    """Load (once) and return the declared ``kernel32`` entry points."""
    global _kernel32
    if _kernel32 is None:
        if not _IS_WINDOWS:
            raise OSError("the Win32 completion-port API is only available on Windows")
        dll = ctypes.WinDLL("kernel32", use_last_error=True)
        _declare_kernel32(dll)
        _kernel32 = dll
    return _kernel32


def ntdll():
    """Load (once) and return the declared ``ntdll`` entry point.

    ``NtQueryInformationFile`` returns an ``NTSTATUS`` directly, so this DLL is
    loaded without ``use_last_error``: there is no last-error slot to race with.
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
    """The Win32 error left by the most recent ``use_last_error`` call.

    It has to be read *immediately* after the call that failed: any further
    ``use_last_error`` call overwrites the slot.
    """
    return ctypes.get_last_error()


# ---- error classification ---------------------------------------------------

_NT_TO_WIN32 = {
    STATUS_INVALID_HANDLE: ERROR_INVALID_HANDLE,
    STATUS_INVALID_PARAMETER: ERROR_INVALID_PARAMETER,
    STATUS_INVALID_INFO_CLASS: ERROR_NOT_SUPPORTED,
    STATUS_NOT_SUPPORTED: ERROR_NOT_SUPPORTED,
    STATUS_INVALID_DEVICE_REQUEST: ERROR_NOT_SUPPORTED,
    STATUS_CANCELLED: ERROR_OPERATION_ABORTED,
}

_BADARG_ERRORS = frozenset((
    ERROR_INVALID_HANDLE,
    ERROR_INVALID_PARAMETER,
    ERROR_INVALID_FUNCTION,
    ERROR_NOT_ENOUGH_MEMORY,
    ERROR_NOT_ENOUGH_QUOTA,
))

_UNSUPPORTED_ERRORS = frozenset((
    ERROR_NOT_SUPPORTED,
))


def ntstatus_to_error(status):
    """Translate an ``NTSTATUS`` into the Win32 error the taxonomy speaks."""
    status &= 0xFFFFFFFF
    if status == STATUS_SUCCESS:
        return 0
    if status == STATUS_PENDING:
        return ERROR_IO_PENDING
    return _NT_TO_WIN32.get(status, status)


def error_kind(error):
    """Map a Win32 error code onto the :class:`~wciocp.errors.WCIOCPError` kinds."""
    if error in _BADARG_ERRORS:
        return "badarg"
    if error in _UNSUPPORTED_ERRORS:
        return "unsupported"
    return "os"


def describe(error):
    """A short, stable rendering of a Win32 error code."""
    return "Win32 error %d" % (int(error),)


# ---- object capability ------------------------------------------------------

def query_file_mode(handle):
    """Read the file object's mode bits.  Returns ``(ntstatus, mode)``.

    ``FileModeInformation`` is the only place the kernel publishes the
    ``FILE_SYNCHRONOUS_IO_NONALERT`` bit that ``CreateFileW``/``CreateNamedPipeW``
    set when ``FILE_FLAG_OVERLAPPED`` is absent.  A null, closed or stale handle
    comes back as ``STATUS_INVALID_HANDLE``.
    """
    mode = wintypes.DWORD(0)
    block = IO_STATUS_BLOCK()
    status = ntdll().NtQueryInformationFile(
        wintypes.HANDLE(int(handle)), ctypes.byref(block), ctypes.byref(mode),
        ctypes.sizeof(mode), FILE_MODE_INFORMATION)
    return int(status) & 0xFFFFFFFF, int(mode.value)


def is_async_mode(handle):
    """Return ``(supported, ntstatus, mode)`` for an object handle.

    ``supported`` is ``True`` only when the kernel answered and the synchronous
    flag is clear -- i.e. the object really was opened for overlapping I/O.
    """
    status, mode = query_file_mode(handle)
    if status != STATUS_SUCCESS:
        return False, status, mode
    return (mode & SYNCHRONOUS_MODE_BITS) == 0, status, mode


def file_type(handle):
    """Return the ``GetFileType`` value for an object handle."""
    return int(kernel32().GetFileType(wintypes.HANDLE(int(handle))))


def close(handle):
    """Close a kernel handle; ignore one that is already unusable."""
    if handle in (None, 0, INVALID_HANDLE_VALUE):
        return
    try:
        kernel32().CloseHandle(wintypes.HANDLE(int(handle)))
    except (OSError, ValueError):
        pass


# ---- the completion port ----------------------------------------------------

def create_port():
    """Create a fresh, unbound I/O completion port.  Returns ``(port, error)``."""
    port = kernel32().CreateIoCompletionPort(
        wintypes.HANDLE(INVALID_HANDLE_VALUE), None, None, 0)
    return port, last_error()


def bind_handle(port, handle, key):
    """Bind ``handle`` to ``port`` and register ``key``.

    Returns ``(bound_or_none, error)``.  The call returns the port handle on
    success.  Calling it again for an already-bound handle *replaces* the
    completion key the kernel holds for that handle -- which is exactly the
    re-registration the contract asks for: packets already queued keep the key
    that was current when their request completed, so an earlier request still
    comes back with the earlier key.
    """
    bound = kernel32().CreateIoCompletionPort(
        wintypes.HANDLE(int(handle)), wintypes.HANDLE(int(port)),
        ctypes.c_void_p(int(key) & KEY_MASK), 0)
    return bound, last_error()


def dequeue(port, timeout_ms):
    """Atomically dequeue one completion packet.  Returns ``(ok, error, packet)``.

    ``packet`` is ``None`` when nothing came back within ``timeout_ms``.  On a
    timeout ``GetQueuedCompletionStatus`` returns ``FALSE`` with
    ``WAIT_TIMEOUT`` (258) and the port is untouched: whatever had already been
    queued stays queued for the next call.  ``timeout_ms == INFINITE`` waits
    without a deadline.
    """
    transferred = wintypes.DWORD(0)
    key = ctypes.c_void_p(0)
    overlapped = ctypes.c_void_p(0)
    ok = kernel32().GetQueuedCompletionStatus(
        wintypes.HANDLE(int(port)), ctypes.byref(transferred), ctypes.byref(key),
        ctypes.byref(overlapped), wintypes.DWORD(int(timeout_ms) & 0xFFFFFFFF))
    error = last_error()
    if not ok and not overlapped.value:
        # No packet: either the deadline passed (WAIT_TIMEOUT) or the call
        # itself failed.  Both leave the port's queue alone.
        return False, error, None
    return bool(ok), error, (key.value, overlapped.value, int(transferred.value))


def normalize_key(raw):
    """Re-sign a completion key that came back as an unsigned ``ULONG_PTR``."""
    value = int(raw) & KEY_MASK
    if value >= KEY_SIGN:
        value -= KEY_MASK + 1
    return value


# ---- the overlapping request -------------------------------------------------

def create_overlapped(offset):
    """A fresh ``OVERLAPPED`` positioned at ``offset``, with no event."""
    overlapped = OVERLAPPED()
    overlapped.Offset = offset & 0xFFFFFFFF
    overlapped.OffsetHigh = (offset >> 32) & 0xFFFFFFFF
    overlapped.hEvent = None
    return overlapped


def read_overlapped(handle, buffer, size, overlapped):
    """Issue one overlapping read.  Returns ``(ok, error, transferred)``.

    ``ok`` is ``True`` when the read finished inside the call (the completion is
    still reported through the port, because the handle is bound to one).
    ``False`` with ``ERROR_IO_PENDING`` means the request is outstanding and a
    completion packet will arrive later.
    """
    got = wintypes.DWORD(0)
    ok = kernel32().ReadFile(wintypes.HANDLE(int(handle)),
                             ctypes.cast(buffer, wintypes.LPVOID),
                             wintypes.DWORD(int(size)), ctypes.byref(got),
                             ctypes.byref(overlapped))
    return bool(ok), last_error(), int(got.value)


def get_overlapped_result(handle, overlapped):
    """Read a dequeued request's terminal state.  Returns ``(ok, error, bytes)``.

    Once ``GetQueuedCompletionStatus`` has handed the ``OVERLAPPED`` over, this
    reads the final status out of the block without waiting:
    ``ERROR_OPERATION_ABORTED`` means the request was cancelled,
    ``ERROR_IO_INCOMPLETE`` would mean it is somehow still pending (which the
    port makes impossible for a dequeued request).
    """
    got = wintypes.DWORD(0)
    ok = kernel32().GetOverlappedResult(wintypes.HANDLE(int(handle)),
                                        ctypes.byref(overlapped), ctypes.byref(got),
                                        False)
    return bool(ok), last_error(), int(got.value)


def cancel_io_ex(handle, overlapped):
    """Cancel exactly one outstanding request.  Returns ``(ok, error)``.

    ``False`` with ``ERROR_NOT_FOUND`` means the request was no longer
    outstanding -- it had already completed, so nothing was cancelled.
    """
    ok = kernel32().CancelIoEx(wintypes.HANDLE(int(handle)),
                               ctypes.byref(overlapped))
    return bool(ok), last_error()


def cancel_io_all(handle):
    """Cancel every request outstanding on ``handle``.  Returns ``(ok, error)``.

    Used only as a fallback when the per-request form cannot be issued because
    the object handle itself has already gone away.
    """
    ok = kernel32().CancelIoEx(wintypes.HANDLE(int(handle)), None)
    return bool(ok), last_error()
