"""Classification of the objects a read request may be issued against.

The collector reads from whichever object the caller hands it: a file on disk, a
private pipe between the collector and a worker, or a console-class device.  The
helpers here answer the questions the read layer asks about such an object.
"""

from . import _winapi
from .errors import WCancelError

_FILE_KINDS = {
    _winapi.FILE_TYPE_DISK: "file",
    _winapi.FILE_TYPE_CHAR: "console",
    _winapi.FILE_TYPE_PIPE: "pipe",
}


def handle_kind(handle):
    """Return ``"file"``, ``"pipe"``, ``"console"`` or ``"unknown"``."""
    number = _winapi.as_number(handle)
    if not _winapi.is_usable_handle(number):
        raise WCancelError("not a usable object handle: %r" % (handle,),
                           kind="os", handle=handle)

    raw = _winapi.file_type(number)
    if raw == _winapi.FILE_TYPE_UNKNOWN:
        error = _winapi.last_error()
        if error:
            raise WCancelError(
                "the object class could not be read (%s)" % _winapi.describe(error),
                kind=_winapi.error_kind(error),
                handle=number,
            )
        return "unknown"
    return _FILE_KINDS.get(raw & ~_winapi.FILE_TYPE_REMOTE, "unknown")


def is_overlapped(handle):
    """Return ``True`` when ``handle`` can carry overlapping operations.

    ``handle`` must be an integer object handle.
    """
    number = _winapi.as_number(handle)
    if not _winapi.is_usable_handle(number):
        raise WCancelError("not a usable object handle: %r" % (handle,),
                           kind="os", handle=handle)
    # The read layer has always taken its objects from the pipe factory, which
    # opens everything for overlapping use, so the answer is the same for every
    # object the module is asked about.
    return True
