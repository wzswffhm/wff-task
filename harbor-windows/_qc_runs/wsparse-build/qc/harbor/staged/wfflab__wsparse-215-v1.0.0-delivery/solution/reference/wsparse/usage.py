"""Disk-usage accounting for sink files.

The quota tracker subtracts this number from the volume budget, so it has to
describe the space the sink really holds.  For a sparse file that is the
cluster-aligned allocation reported by the file system -- obtained either from
``GetCompressedFileSizeW`` or from the ``AllocationSize`` field of
``FILE_STANDARD_INFO`` -- and never the logical length a reader would see.
"""

import os

from . import _winapi
from .errors import WSParseError


def disk_usage(path):
    """Return the number of bytes ``path`` occupies on disk.

    The value is rounded up to a whole cluster by the file system.
    """
    path = os.fspath(path)
    if os.path.isdir(path):
        raise WSParseError(
            "a directory has no cluster allocation that could be reported",
            kind="unsupported",
            path=path,
        )
    if not os.path.exists(path):
        raise WSParseError("no such file: %s" % path, kind="os", path=path)
    if not _winapi.is_windows():
        raise WSParseError(
            "physical allocation can only be read through the Win32 file-system API",
            kind="unsupported",
            path=path,
        )
    try:
        return _winapi.compressed_file_size(path)
    except OSError as exc:
        raise WSParseError(str(exc), kind="os", path=path) from exc
