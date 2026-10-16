"""Disk-usage accounting for sink files."""

import os

from .errors import WSParseError


def disk_usage(path):
    """Return the number of bytes ``path`` occupies on disk.

    This is what the quota tracker subtracts from the volume budget, so it has
    to describe the space the sink actually holds, not the number of bytes a
    reader would see.  The value is rounded up to a whole cluster by the file
    system.
    """
    path = os.fspath(path)
    try:
        info = os.stat(path)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
    return info.st_size
