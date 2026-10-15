"""Overlapped reads that can be cancelled one request at a time.

The layer exists for callers that split a slow source into several parallel
reads and then need to drop exactly one of them -- "the user cancelled this
shard" -- while the rest keep running and still deliver their bytes.

Two things make that possible, and both are kernel behaviour rather than
bookkeeping done here:

* every request gets its own ``OVERLAPPED`` block and its own completion event,
  so waiting on one request never waits on another;
* the cancellation is ``CancelIoEx(handle, &overlapped)``, which names a single
  request and may be called from any thread.  ``CancelIo(handle)`` is the wrong
  tool: it takes the handle's requests away from the calling thread, so from
  another thread it reports success while cancelling nothing.

A request the kernel has already finished cannot be cancelled.  The module never
claims otherwise: when ``CancelIoEx`` answers ``ERROR_NOT_FOUND`` the request was
gone before the call arrived, and :func:`cancel` returns ``False``.
"""

import ctypes
import threading
import time
from collections import namedtuple

from . import _winapi
from .errors import WCancelError
from .kinds import as_handle, kind_for_error, require_overlapped

#: How long ``wait`` keeps re-reading a request whose event signalled before the
#: kernel published its terminal state.  Measured in 1 ms steps.
_SETTLE_RETRIES = 50

#: Requests that are outstanding right now, grouped by the handle they use.
#: ``cancel_all`` works on this and nothing else, which is what makes it "every
#: request this module submitted on that handle" rather than "every request the
#: process happens to have".
_pending_reads = {}
_pending_lock = threading.Lock()


class Completion(namedtuple("Completion", "bytes_read status")):
    """The terminal state of one read.

    ``status`` is ``"completed"`` when the kernel delivered bytes (possibly
    zero, at end of file) and ``"cancelled"`` when the request was aborted;
    ``bytes_read`` is ``0`` for a cancelled request.
    """

    __slots__ = ()

    def __new__(cls, bytes_read=0, status="completed"):
        return super(Completion, cls).__new__(cls, int(bytes_read), status)


class Request(object):
    """One read submitted on a handle, outstanding until it ends.

    ``handle``, ``offset`` and ``size`` describe what was asked for.  The
    ``OVERLAPPED`` block, the completion event and the receive buffer are held
    privately: the kernel writes into all three until the request is settled, so
    none of them may be collected early.
    """

    def __init__(self, handle, size, offset, overlapped, event, buffer):
        self.handle = int(handle)
        self.size = int(size)
        self.offset = int(offset)
        self._overlapped = overlapped
        self._event = event
        self._buffer = buffer
        self._lock = threading.Lock()
        self._completion = None
        self._cancel_issued = False

    # -- observable state ----------------------------------------------------

    @property
    def pending(self):
        """``True`` while the request has no terminal state yet."""
        return self._completion is None

    @property
    def completion(self):
        """The cached :class:`Completion`, or ``None`` while still pending."""
        return self._completion

    @property
    def cancel_issued(self):
        """``True`` once a cancellation for this request was accepted."""
        return self._cancel_issued

    def bytes_read(self):
        """The bytes the kernel delivered, or ``0`` while pending/cancelled."""
        if self._completion is None:
            return 0
        return self._completion.bytes_read

    def data(self):
        """The bytes actually received by this request."""
        if self._completion is None or self._completion.status != "completed":
            return b""
        return self._buffer.raw[: self._completion.bytes_read]

    def __repr__(self):
        state = "pending" if self._completion is None else self._completion.status
        return "<wcancel.Request handle=%d offset=%d size=%d %s>" % (
            self.handle, self.offset, self.size, state)

    def __del__(self):
        try:
            _forget(self)
        except Exception:
            pass
        try:
            if self._event:
                _winapi.close(self._event)
                self._event = None
        except Exception:
            pass


# ---- the outstanding-request registry ---------------------------------------

def _remember(request):
    with _pending_lock:
        _pending_reads.setdefault(request.handle, []).append(request)


def _forget(request):
    with _pending_lock:
        bucket = _pending_reads.get(request.handle)
        if not bucket:
            return
        for index, item in enumerate(bucket):
            if item is request:
                del bucket[index]
                break
        if not bucket:
            del _pending_reads[request.handle]


def _outstanding(handle):
    with _pending_lock:
        return list(_pending_reads.get(handle, ()))


# ---- argument checks --------------------------------------------------------

def _badarg(message):
    return WCancelError(message, kind="badarg")


def _as_size(size):
    if isinstance(size, bool):
        raise _badarg("size must be a positive byte count, got %r" % (size,))
    try:
        number = int(size)
    except (TypeError, ValueError):
        raise _badarg("size must be a positive byte count, got %r" % (size,))
    if number <= 0:
        raise _badarg("size must be a positive byte count, got %r" % (size,))
    return number


def _as_offset(offset):
    if isinstance(offset, bool):
        raise _badarg("offset must be a non-negative byte position, got %r" % (offset,))
    try:
        number = int(offset)
    except (TypeError, ValueError):
        raise _badarg("offset must be a non-negative byte position, got %r" % (offset,))
    if number < 0:
        raise _badarg("offset must be a non-negative byte position, got %r" % (offset,))
    return number


def _as_request(request):
    if not isinstance(request, Request):
        raise _badarg("expected a Request, got %r" % (request,))
    return request


def _timeout_ms(timeout):
    if timeout is None:
        return _winapi.INFINITE
    if isinstance(timeout, bool):
        raise _badarg("timeout must be a number of seconds, got %r" % (timeout,))
    try:
        seconds = float(timeout)
    except (TypeError, ValueError):
        raise _badarg("timeout must be a number of seconds, got %r" % (timeout,))
    if seconds != seconds or seconds < 0:
        raise _badarg("timeout must be a non-negative number, got %r" % (timeout,))
    milliseconds = int(seconds * 1000)
    if milliseconds <= 0:
        return 0
    return min(milliseconds, _winapi.INFINITE - 1)


# ---- the kernel-side terminal state -----------------------------------------

def _settle(request):
    """Cache the request's terminal state, or return ``None`` if still running.

    ``GetOverlappedResult`` reports the request's own error, which is the only
    honest source for "was this cancelled, or did it finish?": a cancelled
    request comes back as ``ERROR_OPERATION_ABORTED``.
    """
    with request._lock:
        if request._completion is not None:
            return request._completion
        ok, error, transferred = _winapi.get_overlapped_result(
            request.handle, request._overlapped, False)
        if ok:
            completion = Completion(transferred, "completed")
        elif error == _winapi.ERROR_OPERATION_ABORTED:
            completion = Completion(0, "cancelled")
        elif error in (_winapi.ERROR_IO_INCOMPLETE, _winapi.ERROR_IO_PENDING):
            return None
        else:
            raise WCancelError(
                "the request ended without a usable result (Win32 error %d)" % error,
                kind=kind_for_error(error),
                handle=request.handle,
                error=error,
            )
        request._completion = completion
    _forget(request)
    return completion


# ---- public API -------------------------------------------------------------

def submit(handle, size, offset=0):
    """Post one overlapped read of ``size`` bytes at ``offset``.

    The call returns as soon as the request is with the kernel.  A request that
    finished inside the call carries its completion already; every other request
    stays outstanding until :func:`wait` collects it or :func:`cancel` aborts it.

    Raises ``WCancelError(kind="unsupported")`` when the object was not opened
    with ``FILE_FLAG_OVERLAPPED``: such a handle cannot hold a cancellable
    request, and pretending otherwise would silently make the read synchronous.
    """
    number = require_overlapped(as_handle(handle))
    count = _as_size(size)
    position = _as_offset(offset)

    try:
        buffer = ctypes.create_string_buffer(count)
    except (MemoryError, OverflowError, ValueError) as exc:
        raise WCancelError("a %d-byte receive buffer could not be allocated: %s"
                           % (count, exc), kind="badarg", handle=number) from exc

    overlapped, event = _winapi.create_overlapped(position)
    request = Request(number, count, position, overlapped, event, buffer)
    ok, error, transferred = _winapi.read_overlapped(number, buffer, count, overlapped)
    if ok:
        # The read finished inside the call: there is nothing left to cancel.
        request._completion = Completion(transferred, "completed")
        return request
    if error == _winapi.ERROR_IO_PENDING:
        _remember(request)
        return request
    _winapi.close(event)
    request._event = None
    raise WCancelError(
        "the read could not be issued (Win32 error %d)" % error,
        kind=kind_for_error(error),
        handle=number,
        error=error,
    )


def cancel(request):
    """Cancel exactly this request.  Returns ``True`` only if a cancel went out.

    ``False`` means there was nothing to cancel: the request had already reached
    its terminal state (or the kernel answered ``ERROR_NOT_FOUND``, which says
    the same thing).  The call may be made from any thread.
    """
    request = _as_request(request)
    missing = False
    with request._lock:
        if request._completion is not None:
            return False
        ok, error = _winapi.cancel_io_ex(request.handle, request._overlapped)
        if ok:
            request._cancel_issued = True
            return True
        if error == _winapi.ERROR_NOT_FOUND:
            missing = True
        elif error == _winapi.ERROR_INVALID_HANDLE:
            raise WCancelError("the handle behind this request is no longer valid",
                               kind="badarg", handle=request.handle, error=error)
        else:
            raise WCancelError(
                "the cancellation was refused (Win32 error %d)" % error,
                kind=kind_for_error(error),
                handle=request.handle,
                error=error,
            )
    if missing:
        # The request was already gone; pick up its real terminal state so a
        # later wait does not have to guess.  A request whose terminal state is
        # itself a failure is still "not cancellable", which is what False means.
        try:
            _settle(request)
        except WCancelError:
            pass
    return False


def cancel_all(handle):
    """Cancel every outstanding request this module posted on ``handle``.

    Returns how many cancellations actually went out -- a request that had
    already finished is not counted.
    """
    number = as_handle(handle)
    cancelled = 0
    for request in _outstanding(number):
        if cancel(request):
            cancelled += 1
    return cancelled


def wait(request, timeout=None):
    """Wait for one request to reach its terminal state.

    Returns a :class:`Completion`; a request that was cancelled reports
    ``status="cancelled"`` rather than an error.  ``timeout`` is a number of
    seconds (``None`` waits forever); on expiry a
    ``WCancelError(kind="timeout")`` is raised and the request stays usable.
    """
    request = _as_request(request)
    milliseconds = _timeout_ms(timeout)
    with request._lock:
        if request._completion is not None:
            return request._completion

    status = _winapi.wait_for(request._event, milliseconds)
    if status == _winapi.WAIT_TIMEOUT:
        raise WCancelError(
            "the request was still outstanding after %s seconds" % (timeout,),
            kind="timeout",
            handle=request.handle,
        )
    if status == _winapi.WAIT_FAILED:
        error = _winapi.last_error()
        raise WCancelError(
            "the completion event could not be waited on (Win32 error %d)" % error,
            kind=kind_for_error(error),
            handle=request.handle,
            error=error,
        )
    if status not in (_winapi.WAIT_OBJECT_0, _winapi.WAIT_ABANDONED):
        raise WCancelError("unexpected wait result %d" % status, kind="os",
                           handle=request.handle)

    completion = _settle(request)
    for _ in range(_SETTLE_RETRIES):
        if completion is not None:
            return completion
        time.sleep(0.001)
        completion = _settle(request)
    raise WCancelError(
        "the request signalled completion but the kernel reported no result",
        kind="os",
        handle=request.handle,
    )
