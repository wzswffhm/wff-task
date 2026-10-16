"""Classification of the objects the host may hand to its helpers."""

import os

from . import _winapi
from .errors import WSpawnError

_KINDS = {
    _winapi.FILE_TYPE_DISK: "file",
    _winapi.FILE_TYPE_CHAR: "console",
    _winapi.FILE_TYPE_PIPE: "pipe",
}


def handle_kind(handle):
    """Return ``"file"``, ``"pipe"``, ``"console"`` or ``"unknown"``."""
    try:
        number = int(handle)
    except (TypeError, ValueError):
        raise WSpawnError("handle must be an integer, got %r" % (handle,), kind="badarg")
    if number <= 0:
        raise WSpawnError("not a usable object handle: %r" % (handle,), kind="os", handle=handle)
    if not _winapi.is_windows():
        raise WSpawnError(
            "object handles exist only on Windows",
            kind="unsupported",
            handle=number,
        )

    raw = _winapi.file_type(number)
    if raw == _winapi.FILE_TYPE_UNKNOWN:
        error = _winapi.last_error()
        if error:
            raise WSpawnError(
                "the object class could not be read (Win32 error %d)" % error,
                kind=_winapi.kind_for_error(error),
                handle=number,
            )
        return "unknown"
    return _KINDS.get(raw & ~_winapi.FILE_TYPE_REMOTE, "unknown")
