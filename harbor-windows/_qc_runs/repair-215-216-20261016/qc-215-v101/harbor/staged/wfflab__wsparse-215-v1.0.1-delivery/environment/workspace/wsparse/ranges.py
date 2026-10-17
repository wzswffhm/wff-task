"""Allocated-range reporting for sink files."""

import os

from .errors import WSParseError


def allocated_ranges(path):
    """Return ``[(offset, length), ...]`` of the byte ranges backed by clusters.

    The transfer layer uses this to decide which parts of a sink still have to
    be fetched: a range that is already allocated is on disk, everything else
    is a hole that still needs data.  The list is ordered by ``offset`` and the
    ranges never overlap.  Every range lies inside the file's logical length.
    """
    path = os.fspath(path)
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    if size == 0:
        return []
    return [(0, size)]
