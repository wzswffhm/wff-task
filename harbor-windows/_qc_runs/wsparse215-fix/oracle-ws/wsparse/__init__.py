"""wsparse -- space management for the collector's on-disk sink files.

The collector streams large payloads into *sink* files.  Two properties matter
to the rest of the pipeline:

* a sink is **pre-allocated** so that the writer never has to grow the file
  while it is streaming, and
* the pipeline can ask how much disk a sink really occupies, and which byte
  ranges of it are backed by allocated clusters, so that an interrupted
  transfer can be resumed without re-downloading what is already on disk.

Public API
----------

``preallocate(path, size)``
    Grow ``path`` to ``size`` bytes and reserve the space for it.
``disk_usage(path)``
    Number of bytes ``path`` occupies on disk.
``allocated_ranges(path)``
    ``[(offset, length), ...]`` of the byte ranges backed by disk clusters.
``sparse_flag(path, enabled)``
    Turn the sparse attribute of ``path`` on or off.
``sparse_state(path)``
    ``True`` when ``path`` currently carries the sparse attribute.
``WSParseError``
    Carries a ``kind`` classifier.

See ``docs/NOTES.md`` for the layout notes and ``README.md`` for the supported
Python versions.
"""

from .errors import WSParseError
from .alloc import preallocate
from .usage import disk_usage
from .ranges import allocated_ranges
from .flags import sparse_flag, sparse_state

__all__ = [
    "WSParseError",
    "preallocate",
    "disk_usage",
    "allocated_ranges",
    "sparse_flag",
    "sparse_state",
]

__version__ = "0.4.1"
