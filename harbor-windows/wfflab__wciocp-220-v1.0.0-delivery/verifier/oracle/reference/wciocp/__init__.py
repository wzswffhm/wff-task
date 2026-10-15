"""wciocp -- one kernel completion port, many handles, many takers.

Several sources (pipes, files) are read with overlapping (asynchronous) I/O and
every completion is funnelled into a single **I/O completion port**.  A worker
thread picks a completion up with one ``GetQueuedCompletionStatus`` call, so the
kernel, not this module, decides which thread sees which completion: each packet
is delivered to exactly one taker, and the **completion key** it carries is the
one the kernel copied when the request finished.

Public API
----------

``create_pool(threads=4) -> Pool``
    Create a completion port with room for ``threads`` takers.  The pool spawns
    no threads; the caller runs the takers.
``Pool.register(handle, key) -> None``
    Bind an object to the pool and register its completion key.  An object that
    was not opened with ``FILE_FLAG_OVERLAPPED`` raises
    ``WCIOCPError(kind="unsupported")`` instead of being accepted silently, and
    registering the same handle again simply replaces the key the kernel keeps
    for it.
``Pool.submit(handle, size, offset=0) -> Request``
    Post one read of ``size`` bytes at ``offset``.
``Pool.take(timeout=None) -> Event``
    Dequeue one completion.  ``Event.key`` is the key the kernel returned,
    ``Event.request`` the request it belongs to, ``Event.bytes_read`` the
    transfer count and ``Event.status`` either ``"completed"`` or
    ``"cancelled"``.  When the deadline passes first, ``WCIOCPError`` with
    ``kind="timeout"`` is raised and nothing is removed from the port.
``Pool.close() -> None``
    Idempotent.  Pending requests are cancelled with ``CancelIoEx`` -- their
    completions report ``status="cancelled"`` -- and any later ``take`` or
    ``submit`` raises ``WCIOCPError(kind="closed")``.
``WCIOCPError``
    Carries a ``kind`` of ``unsupported`` / ``badarg`` / ``os`` / ``timeout`` /
    ``closed``.

The module is a Windows module: it is built on ``CreateIoCompletionPort`` and
``GetQueuedCompletionStatus``, which have no counterpart elsewhere.  On a
non-Windows host ``create_pool`` raises ``WCIOCPError(kind="unsupported")``.
"""

from .errors import WCIOCPError
from .kinds import handle_kind, is_overlapped
from .pool import Event, Pool, Request, create_pool

__all__ = [
    "WCIOCPError",
    "Event",
    "Pool",
    "Request",
    "create_pool",
    "handle_kind",
    "is_overlapped",
]

__version__ = "1.0.0"
