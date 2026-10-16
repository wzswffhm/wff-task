"""The overlapping-read layer of the collector.

A read is submitted against an object handle and stays outstanding until the
data arrives or the caller gives up on it.  A :class:`Request` is the handle the
caller keeps for one such read; a :class:`Completion` is what it finally
produced.  Requests made on one object may be abandoned either one at a time or
as a batch.
"""

import ctypes

from . import _winapi
from .errors import WCancelError

DEFAULT_TIMEOUT_MS = 0xFFFFFFFF

# The requests this process has submitted on each object, keyed by handle number.
_pending = {}


class Completion(object):
    """The outcome of one read request.

    ``bytes_read`` is how many bytes the request delivered and ``status`` is
    either ``"completed"`` or ``"cancelled"``.
    """

    def __init__(self, bytes_read=0, status="completed"):
        self.bytes_read = int(bytes_read)
        self.status = status

    def __repr__(self):
        return "Completion(bytes_read=%d, status=%r)" % (self.bytes_read, self.status)


class Request(object):
    """One overlapping read that has been handed to the operating system."""

    def __init__(self, handle, size, offset, buffer, overlapped, event):
        self.handle = int(handle)
        self.size = int(size)
        self.offset = int(offset)
        self._buffer = buffer
        self._overlapped = overlapped
        self._event = event
        self._submitted = False
        self._result = None
        self._state = "pending"

    def __repr__(self):
        return "Request(handle=%d, offset=%d, size=%d)" % (self.handle, self.offset, self.size)


def _as_request(request):
    if not isinstance(request, Request):
        raise WCancelError("request must be a Request, got %r" % (request,), kind="badarg")
    return request


def _as_timeout(timeout):
    if timeout is None:
        return DEFAULT_TIMEOUT_MS
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise WCancelError("timeout must be a number of seconds, got %r" % (timeout,),
                           kind="badarg")
    if timeout < 0:
        raise WCancelError("timeout must not be negative, got %r" % (timeout,), kind="badarg")
    return int(timeout * 1000)


def _outstanding(handle):
    return list(_pending.get(int(handle), ()))


def _forget(request):
    entries = _pending.get(request.handle)
    if not entries:
        return
    try:
        entries.remove(request)
    except ValueError:
        pass
    if not entries:
        _pending.pop(request.handle, None)


def submit(handle, size, offset=0):
    """Start one overlapping read of ``size`` bytes at ``offset``.

    Returns the :class:`Request` that keeps track of it.
    """
    number = _winapi.as_number(handle)
    if not _winapi.is_usable_handle(number):
        raise WCancelError("not a usable object handle: %r" % (handle,), kind="badarg",
                           handle=handle)
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise WCancelError("size must be a positive number of bytes, got %r" % (size,),
                           kind="badarg")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise WCancelError("offset must not be negative, got %r" % (offset,), kind="badarg")

    event = _winapi.open_event()
    buffer = ctypes.create_string_buffer(size)
    overlapped = _winapi.OVERLAPPED()
    overlapped.hEvent = event
    request = Request(number, size, offset, buffer, overlapped, event)
    try:
        ok, error = _winapi.start_read(number, buffer, size, offset, overlapped)
    except WCancelError:
        _winapi.close(event)
        raise

    request._submitted = True
    if ok:
        # The read was served straight away and never became outstanding.
        _done, _error, transferred = _winapi.read_status(number, overlapped)
        request._state = "done"
        request._result = Completion(transferred, "completed")
        _winapi.close(event)
        return request
    if error == _winapi.ERROR_IO_PENDING:
        _pending.setdefault(number, []).append(request)
        return request

    _winapi.close(event)
    raise WCancelError(
        "the read on object %r could not be started (%s)" % (handle, _winapi.describe(error)),
        kind=_winapi.error_kind(error),
        handle=handle,
    )


def cancel(request):
    """Abandon one outstanding read.

    Returns ``True`` when the read has been given up.
    """
    request = _as_request(request)
    if request._state == "cancelled":
        return True

    if request._state == "pending":
        done, _error, _transferred = _winapi.read_status(request.handle, request._overlapped)
        if done:
            request._state = "done"

    if request._state == "pending":
        _winapi.cancel(request.handle)
        request._state = "cancelled"

    _forget(request)
    return True


def cancel_all(handle):
    """Abandon every outstanding read on one object.

    Returns how many requests were given up.
    """
    number = _winapi.as_number(handle)
    if not _winapi.is_usable_handle(number):
        raise WCancelError("not a usable object handle: %r" % (handle,), kind="badarg",
                           handle=handle)

    outstanding = _outstanding(number)
    if not outstanding:
        return 0

    # The batch entry point of the read layer walks the objects it knows about
    # and asks the system to abandon what is outstanding on each of them.
    _winapi.cancel(number)
    for request in outstanding:
        request._state = "cancelled"
    _pending.pop(number, None)
    return len(outstanding)


def wait(request, timeout=None):
    """Wait for one read to finish and return its :class:`Completion`.

    Raises :class:`WCancelError` with ``kind="timeout"`` when the read is still
    outstanding after ``timeout`` seconds, and ``kind="os"`` when the read ended
    in failure.
    """
    request = _as_request(request)
    if request._state == "done" and request._result is not None:
        return request._result

    timeout_ms = _as_timeout(timeout)
    outcome, bytes_read, error = _winapi.wait_for_read(
        request.handle, request._overlapped, request._event, timeout_ms)

    if outcome == "timeout":
        raise WCancelError(
            "the read on object %r is still outstanding after %r seconds"
            % (request.handle, timeout),
            kind="timeout",
            handle=request.handle,
        )
    if outcome == "error":
        _forget(request)
        raise WCancelError(
            "the read on object %r failed (%s)" % (request.handle, _winapi.describe(error)),
            kind=_winapi.error_kind(error),
            handle=request.handle,
        )

    _forget(request)
    request._state = "done"
    request._result = Completion(bytes_read, "completed")
    return request._result
