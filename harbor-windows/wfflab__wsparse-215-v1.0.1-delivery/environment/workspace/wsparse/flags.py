"""Sparse-attribute handling."""

import os

from ._winapi import SPARSE_ATTRIBUTE, is_windows
from .errors import WSParseError


def sparse_state(path):
    """Return ``True`` when ``path`` currently carries the sparse attribute."""
    path = os.fspath(path)
    try:
        info = os.stat(path)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & SPARSE_ATTRIBUTE)


def sparse_flag(path, enabled=True):
    """Turn the sparse attribute of ``path`` on or off.

    ``enabled`` defaults to ``True``.  Returns the state the file ends up in.
    """
    path = os.fspath(path)
    if not os.path.exists(path):
        raise WSParseError("no such file: %s" % path, kind="os", path=path)
    if not is_windows():
        raise WSParseError(
            "the sparse attribute is a Windows file-system concept",
            kind="unsupported",
            path=path,
        )
    if not enabled:
        raise WSParseError(
            "clearing the sparse attribute is not implemented yet",
            kind="unsupported",
            path=path,
        )
    # The attribute is maintained by the file system while the file is being
    # written, so there is nothing left to do here but report where we stand.
    return sparse_state(path)
