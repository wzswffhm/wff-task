"""Sparse-attribute handling.

The attribute is read from ``FILE_ATTRIBUTE_SPARSE_FILE`` and written with
``FSCTL_SET_SPARSE``.  Writing it is not a request to reclaim space: already
allocated clusters stay allocated, which is why a file that was extended dense
and only then flagged still occupies its full logical length.
"""

import os

from . import _winapi
from .errors import WSParseError


def sparse_state(path):
    """Return ``True`` when ``path`` currently carries the sparse attribute."""
    path = os.fspath(path)
    try:
        info = os.stat(path)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    return bool(getattr(info, "st_file_attributes", 0) & _winapi.SPARSE_ATTRIBUTE)


def sparse_flag(path, enabled=True):
    """Turn the sparse attribute of ``path`` on or off.

    ``enabled`` defaults to ``True``.  Returns the state the file ends up in.
    Setting the flag never releases clusters that are already allocated.
    """
    path = os.fspath(path)
    if not os.path.exists(path):
        raise WSParseError("no such file: %s" % path, kind="os", path=path)
    if os.path.isdir(path):
        raise WSParseError(
            "the sparse attribute does not apply to a directory",
            kind="unsupported",
            path=path,
        )
    if not _winapi.is_windows():
        raise WSParseError(
            "the sparse attribute can only be written through the Win32 "
            "file-system control codes",
            kind="unsupported",
            path=path,
        )

    try:
        handle = _winapi.open_file(
            path, _winapi.GENERIC_READ | _winapi.GENERIC_WRITE)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc

    try:
        ok, error = _winapi.set_sparse(handle, enabled)
        if not ok:
            raise WSParseError(
                "FSCTL_SET_SPARSE was rejected (Win32 error %d)" % error,
                kind=_winapi.kind_for_error(error),
                path=path,
            )
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    finally:
        _winapi.close_handle(handle)

    return sparse_state(path)
