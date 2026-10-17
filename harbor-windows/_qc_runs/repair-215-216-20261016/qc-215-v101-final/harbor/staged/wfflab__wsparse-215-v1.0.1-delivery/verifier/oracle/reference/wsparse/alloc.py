"""Pre-allocation of sink files.

A sink is reserved by setting the sparse attribute and then moving the
end-of-file marker, so the reserved tail becomes a hole: the file system records
the new length without backing it with disk clusters, and the writer can fill
the bytes in later without the file growing underneath it.

Note the order. ``FSCTL_SET_SPARSE`` only affects clusters that are allocated
*after* it is issued; issuing it on a file whose clusters already exist does not
give them back, so a sink that was extended dense first stays dense.
"""

import os

from . import _winapi
from .errors import WSParseError


def _check_size(size):
    if isinstance(size, bool) or not isinstance(size, int):
        raise WSParseError("size must be an integer, got %r" % (size,), kind="badarg")
    if size < 0:
        raise WSParseError("size must not be negative, got %r" % (size,), kind="badarg")


def _reject_directory(path):
    if os.path.isdir(path):
        raise WSParseError(
            "the sparse-file control codes do not apply to a directory",
            kind="unsupported",
            path=path,
        )


def _reject_other_platform(path):
    if not _winapi.is_windows():
        raise WSParseError(
            "reserving a sink without writing it out requires the Win32 sparse-file "
            "control codes, which exist only on Windows",
            kind="unsupported",
            path=path,
        )


def preallocate(path, size):
    """Grow ``path`` to ``size`` bytes and reserve the space for it.

    The sink is created when it does not exist yet.  Existing content is
    preserved; the file is only ever extended, never shrunk.  The call is
    idempotent -- calling it again with the same ``size`` leaves the file
    untouched and keeps it sparse.

    Returns the resulting file length in bytes.
    """
    _check_size(size)
    path = os.fspath(path)
    _reject_directory(path)
    _reject_other_platform(path)

    try:
        handle = _winapi.open_file(
            path,
            _winapi.GENERIC_READ | _winapi.GENERIC_WRITE,
            disposition=_winapi.OPEN_ALWAYS,
        )
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc

    try:
        ok, error = _winapi.set_sparse(handle, True)
        if not ok:
            raise WSParseError(
                "FSCTL_SET_SPARSE was rejected (Win32 error %d)" % error,
                kind=_winapi.kind_for_error(error),
                path=path,
            )
        if _winapi.file_length(handle) < size:
            _winapi.set_file_length(handle, size)
        _winapi.flush(handle)
        return _winapi.file_length(handle)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    finally:
        _winapi.close_handle(handle)
