"""wcancel -- overlapped reads that can be cancelled one request at a time.

The async read layer of a collector keeps several reads in flight at once and
must be able to drop one of them -- the shard a user gave up on -- without
disturbing the others: the remaining requests still have to finish and still
have to deliver their bytes.

Public API
----------

``submit(handle, size, offset=0)``
    Post one overlapped read.  Returns a :class:`Request`; the read stays
    outstanding until it finishes or is cancelled.  An object that was not
    opened with ``FILE_FLAG_OVERLAPPED`` raises
    ``WCancelError(kind="unsupported")`` instead of quietly reading
    synchronously.
``cancel(request)``
    Cancel exactly that request; may be called from any thread.  Returns
    ``True`` when a cancellation really went out and ``False`` when the request
    had already finished -- a completed request is never reported as cancelled.
``cancel_all(handle)``
    Cancel every outstanding request this module posted on ``handle``; returns
    how many cancellations went out.
``wait(request, timeout=None)``
    Wait for one request and return its :class:`Completion`
    (``bytes_read`` plus ``status`` of ``"completed"`` or ``"cancelled"``).
    A request that was cancelled is a status, not an error;
    ``WCancelError(kind="timeout")`` is raised when the deadline passes first.
``is_overlapped(handle)``
    Report whether an object can carry cancellable overlapped I/O at all.
``WCancelError``
    Carries a ``kind`` of ``unsupported`` / ``badarg`` / ``os`` / ``timeout``.

See ``docs/NOTES.md`` for how the module was originally laid out.
"""

from .errors import WCancelError
from .kinds import is_overlapped
from .proc import Completion, Request, cancel, cancel_all, submit, wait

__all__ = [
    "WCancelError",
    "Completion",
    "Request",
    "submit",
    "cancel",
    "cancel_all",
    "wait",
    "is_overlapped",
]

__version__ = "1.0.0"
