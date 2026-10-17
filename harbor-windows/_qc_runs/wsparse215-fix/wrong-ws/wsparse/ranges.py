"""Allocated-range reporting for sink files.

``FSCTL_QUERY_ALLOCATED_RANGES`` answers exactly the question the transfer layer
asks: which byte ranges of this file are backed by disk clusters?  The result is
already cluster aligned, ascending and disjoint, so it is passed through
unchanged.  A file that is a single hole reports nothing at all.
"""

import os

from . import _winapi
from .errors import WSParseError


def allocated_ranges(path):
    """Return ``[(offset, length), ...]`` of the byte ranges backed by clusters.

    The list is ordered by ``offset`` and the ranges never overlap.  Every range
    lies inside the file's logical length.
    """
    path = os.fspath(path)
    if os.path.isdir(path):
        raise WSParseError(
            "a directory has no allocated ranges",
            kind="unsupported",
            path=path,
        )
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    if size == 0:
        return []
    if not _winapi.is_windows():
        raise WSParseError(
            "the allocated ranges can only be read through the Win32 file-system API",
            kind="unsupported",
            path=path,
        )

    try:
        handle = _winapi.open_file(path, _winapi.GENERIC_READ)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc

    try:
        ranges, error = _winapi.query_allocated_ranges(handle, 0, size)
        if ranges is None:
            raise WSParseError(
                "FSCTL_QUERY_ALLOCATED_RANGES was rejected (Win32 error %d)" % error,
                kind=_winapi.kind_for_error(error),
                path=path,
            )
        # PROBE: report every extent one byte longer than reality.
        return [(offset, length + 1) for offset, length in ranges]
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    finally:
        _winapi.close_handle(handle)
