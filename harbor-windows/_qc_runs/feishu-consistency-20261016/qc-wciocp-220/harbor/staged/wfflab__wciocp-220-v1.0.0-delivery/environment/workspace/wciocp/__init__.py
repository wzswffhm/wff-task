"""wciocp -- a completion pool for the collector's overlapping reads.

The collector reads its inputs and its pipes as *overlapping* (asynchronous)
I/O.  A read comes back straight away, the data arrives later, and the result
has to be collected again before the buffer can be handed on.  ``wciocp`` is the
layer that does the collecting: every object the collector reads is registered
with a :class:`Pool`, reads are submitted through that pool, and the worker
threads call :meth:`Pool.take` to collect whatever came back.

Every registration carries a *completion key*: the integer that says which job
an object belongs to.  The collector registers a pipe or a file under the key of
the job it serves, and the notification that comes back for a read carries that
key, so a worker that collects a notification can route it back to its job
without looking anything up.

Typical use::

    pool = create_pool(threads=4)

    pool.register(pipe, 0x11)
    pool.register(spool_file, 0x22)

    request = pool.submit(pipe, size=65536, offset=0)
    ...
    event = pool.take(timeout=5.0)
    print(hex(event.key), event.bytes_read, event.status)
    # -> which job the data belongs to, and how much of it arrived

Several workers may run :meth:`Pool.take` at the same time; the pool is shared
between them and it hands each notification it has to one of them.

Public API
----------

``create_pool(threads=4) -> Pool``
    Build a completion pool served by ``threads`` workers.
``Pool.register(handle, key) -> None``
    Register an object with the pool under the completion key ``key``.
``Pool.submit(handle, size, offset=0) -> Request``
    Start one overlapping read of ``size`` bytes at ``offset``.
``Pool.take(timeout=None) -> Event``
    Collect one notification.  ``timeout`` is in seconds and defaults to no
    deadline.
``Pool.close() -> None``
    Stop the pool.  Reads that are still outstanding are cancelled.
``Event``
    One collected notification; exposes ``key``, ``request``, ``bytes_read``
    and ``status``, where ``status`` is ``"completed"`` or ``"cancelled"``.
``Request``
    One submitted read; exposes ``handle``, ``offset`` and ``size``.
``WCIOCPError``
    Carries a ``kind`` of ``unsupported`` / ``badarg`` / ``os`` / ``timeout`` /
    ``closed``.

See ``docs/NOTES.md`` for how the module was originally laid out.
"""

from .errors import WCIOCPError
from .kinds import is_overlapped
from .pool import Event, Pool, Request, create_pool

__all__ = [
    "WCIOCPError",
    "Pool",
    "Event",
    "Request",
    "create_pool",
    "is_overlapped",
]

__version__ = "0.5.0"
