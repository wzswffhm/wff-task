"""wcancel -- overlapping reads with per-object cancellation.

The collector reads large inputs as *overlapping* (asynchronous) I/O: instead of
blocking on one read, it hands several reads to the operating system at once and
picks up their results later.  A download is split into shards, each shard is
one overlapping read of the same source object, and a user who drops a shard
asks the module to abandon that shard while the others keep running.

Typical use::

    request = submit(handle, size=65536, offset=0)
    ...
    if user_dropped_the_shard:
        cancel(request)
    completion = wait(request, timeout=5.0)
    print(completion.status, completion.bytes_read)

Public API
----------

``submit(handle, size, offset=0) -> Request``
    Start one overlapping read of ``size`` bytes at ``offset`` on ``handle``.
``cancel(request) -> bool``
    Abandon one outstanding read.  ``True`` when the read has been given up.
``cancel_all(handle) -> int``
    Abandon every outstanding read on ``handle``; the count given up is returned.
``wait(request, timeout=None) -> Completion``
    Wait for one read to finish.  ``timeout`` is in seconds and defaults to no
    deadline.
``is_overlapped(handle) -> bool``
    Whether ``handle`` can carry overlapping operations.
``handle_kind(handle) -> str``
    ``"file"`` / ``"pipe"`` / ``"console"`` / ``"unknown"``.
``WCancelError``
    Carries a ``kind`` of ``unsupported`` / ``badarg`` / ``os`` / ``timeout``.
``Request``
    One submitted read; exposes ``handle``, ``size`` and ``offset``.
``Completion``
    The outcome of a read; exposes ``bytes_read`` and ``status``, where
    ``status`` is ``"completed"`` or ``"cancelled"``.

See ``docs/NOTES.md`` for how the module was originally laid out.
"""

from .errors import WCancelError
from .kinds import handle_kind, is_overlapped
from .proc import Completion, Request, cancel, cancel_all, submit, wait

__all__ = [
    "WCancelError",
    "Request",
    "Completion",
    "submit",
    "cancel",
    "cancel_all",
    "wait",
    "is_overlapped",
    "handle_kind",
]

__version__ = "0.4.0"
