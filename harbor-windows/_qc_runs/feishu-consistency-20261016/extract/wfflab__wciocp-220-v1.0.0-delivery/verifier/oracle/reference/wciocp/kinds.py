"""Capability checks for the objects completions may be queued for.

The whole contract rests on one bit of kernel state: a file object either was
created with ``FILE_FLAG_OVERLAPPED`` or it was not.  If it was not, the kernel
will never put a completion packet on the port for that handle and there is
nothing to register; a read posted to it runs inline and reports itself as an
ordinary synchronous call.  That is exactly the silent degradation the contract
bans, so the check happens on ``register()`` and again on ``submit()``.

The answer comes from the file object itself (``FileModeInformation``), not from
``GetFileType``: a synchronous handle accepts an ``OVERLAPPED`` pointer without
complaining, so asking the kernel is the only honest test.
"""

from . import _winapi
from .errors import WCIOCPError

__all__ = ["as_handle", "is_usable_handle", "require_overlapped", "is_overlapped",
           "handle_kind"]

#: ``GetFileType`` values that name a device class.
_FILE_KINDS = {
    0x0001: "file",
    0x0002: "console",
    0x0003: "pipe",
}
_FILE_TYPE_REMOTE = 0x00008000


def is_usable_handle(handle):
    """Return ``True`` when ``handle`` is an integer that is not obviously dead."""
    if isinstance(handle, bool) or not isinstance(handle, int):
        return False
    return handle > 0 and handle != _winapi.INVALID_HANDLE_VALUE


def as_handle(handle):
    """Normalise a caller-supplied handle, or raise ``kind="badarg"``."""
    if isinstance(handle, bool) or not isinstance(handle, int):
        raise WCIOCPError("handle must be an integer, got %r" % (handle,),
                          kind="badarg", handle=handle)
    number = int(handle)
    if not is_usable_handle(number):
        raise WCIOCPError("not a usable object handle: %r" % (handle,),
                          kind="badarg", handle=handle)
    return number


def require_overlapped(handle):
    """Assert that ``handle`` can carry completions.  Returns the handle number.

    Raises ``kind="unsupported"`` for an object opened without
    ``FILE_FLAG_OVERLAPPED`` (a plain ``CreateFileW``, an ``open()`` descriptor,
    a synchronous console) and ``kind="badarg"`` for a handle that names no
    object at all.
    """
    number = as_handle(handle)
    if not _winapi.is_windows():
        raise WCIOCPError(
            "completions require the Win32 completion-port API, which exists "
            "only on Windows",
            kind="unsupported", handle=number)

    status, mode = _winapi.query_file_mode(number)
    if status == _winapi.STATUS_SUCCESS:
        if mode & _winapi.SYNCHRONOUS_MODE_BITS:
            raise WCIOCPError(
                "this handle was opened without FILE_FLAG_OVERLAPPED, so the "
                "kernel will never queue a completion for it (mode 0x%04X)" % (mode,),
                kind="unsupported", handle=number)
        return number
    if status == _winapi.STATUS_INVALID_HANDLE:
        raise WCIOCPError("there is no object behind this handle", kind="badarg",
                          handle=number)
    error = _winapi.ntstatus_to_error(status)
    raise WCIOCPError(
        "this handle does not report a file mode that can carry overlapping I/O "
        "(NTSTATUS 0x%08X)" % (status,),
        kind=_winapi.error_kind(error), handle=number, error=error)


def is_overlapped(handle):
    """Report whether the object can carry asynchronous operations."""
    try:
        require_overlapped(handle)
    except WCIOCPError as exc:
        if exc.kind == "unsupported":
            return False
        raise
    return True


def handle_kind(handle):
    """Return ``"file"``, ``"pipe"``, ``"console"`` or ``"unknown"``."""
    number = as_handle(handle)
    raw = int(_winapi.file_type(number))
    if raw == 0:
        return "unknown"
    return _FILE_KINDS.get(raw & ~_FILE_TYPE_REMOTE, "unknown")
