"""Capability checks for the objects that overlapped reads may be posted to.

The whole contract rests on one bit of kernel state: a file object either was
created with ``FILE_FLAG_OVERLAPPED`` or it was not.  If it was not, the handle
cannot hold several outstanding reads, ``CancelIoEx`` can never name one of
them, and a read on it has to be rejected up front instead of quietly running
synchronously -- that "quietly" is exactly the degradation the contract bans.
"""

from . import _winapi
from .errors import WCancelError


def kind_for_error(error):
    """Map a Win32 error code onto the :class:`WCancelError` taxonomy."""
    return _winapi.kind_for_error(error)


def as_handle(handle):
    """Normalise a caller-supplied handle, or raise ``kind="badarg"``."""
    if isinstance(handle, bool):
        raise WCancelError("handle must be an integer, got %r" % (handle,), kind="badarg")
    try:
        number = int(handle)
    except (TypeError, ValueError):
        raise WCancelError("handle must be an integer, got %r" % (handle,), kind="badarg")
    if number <= 0 or number == _winapi.INVALID_HANDLE_VALUE:
        raise WCancelError("not a usable object handle: %r" % (handle,), kind="badarg",
                           handle=handle)
    return number


def is_overlapped(handle):
    """Report whether the object can carry cancellable overlapped I/O.

    The answer comes from the file object itself (``FileModeInformation``), not
    from ``GetFileType``: a synchronous handle accepts an ``OVERLAPPED`` pointer
    without complaining, so asking the object is the only honest test.
    """
    number = as_handle(handle)
    if not _winapi.is_windows():
        raise WCancelError(
            "cancellable overlapped I/O requires the Win32 completion API, which "
            "exists only on Windows",
            kind="unsupported",
            handle=number,
        )
    status, mode = _winapi.query_mode(number)
    if status == _winapi.STATUS_SUCCESS:
        return not (mode & _winapi.SYNCHRONOUS_MODE_BITS)
    if status == _winapi.STATUS_INVALID_HANDLE:
        raise WCancelError("there is no object behind this handle", kind="badarg",
                           handle=number)
    return False


def require_overlapped(handle):
    """Assert that ``handle`` can carry a precisely cancellable request.

    Raises ``kind="unsupported"`` for an object opened without
    ``FILE_FLAG_OVERLAPPED`` (a plain ``CreateFileW``, an ``open()`` file
    descriptor) and ``kind="badarg"`` for a handle that names no object.
    """
    number = as_handle(handle)
    if not _winapi.is_windows():
        raise WCancelError(
            "cancellable overlapped I/O requires the Win32 completion API, which "
            "exists only on Windows",
            kind="unsupported",
            handle=number,
        )
    status, mode = _winapi.query_mode(number)
    if status == _winapi.STATUS_SUCCESS:
        if mode & _winapi.SYNCHRONOUS_MODE_BITS:
            raise WCancelError(
                "this handle was opened without FILE_FLAG_OVERLAPPED, so a pending "
                "read on it could never be cancelled on its own (mode 0x%04X)" % (mode,),
                kind="unsupported",
                handle=number,
            )
        return number
    if status == _winapi.STATUS_INVALID_HANDLE:
        raise WCancelError("there is no object behind this handle", kind="badarg",
                           handle=number)
    raise WCancelError(
        "this handle does not report a mode that can carry overlapped I/O "
        "(NTSTATUS 0x%08X)" % (status,),
        kind="unsupported",
        handle=number,
    )
