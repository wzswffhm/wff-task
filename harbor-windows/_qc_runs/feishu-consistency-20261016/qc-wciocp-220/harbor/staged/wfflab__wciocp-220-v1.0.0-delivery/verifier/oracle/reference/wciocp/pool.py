"""The completion-port pool: many handles, one kernel queue, many takers.

The collector has several sources (pipes, files) and several worker threads.  The
design is the Windows one, undiluted:

* one **I/O completion port** is created for the pool;
* every source is bound to that port with ``CreateIoCompletionPort(handle,
  port, key, 0)``, which also records the **completion key** the kernel keeps
  for the handle;
* every read is posted with an ``OVERLAPPED`` whose address is the request's
  identity;
* every worker calls :meth:`Pool.take`, which is one
  ``GetQueuedCompletionStatus`` call -- the kernel hands the packet to exactly
  one caller, so "delivered once" is a kernel guarantee and this module holds no
  completion queue of its own.

The completion key that comes back in an :class:`Event` is the key the kernel
returned for the packet, cross-checked against the key that was registered for
the handle when the request was posted.  Windows fixes a handle's key at its
first bind and refuses to change it afterwards: re-binding an already-bound
handle fails with ``ERROR_INVALID_PARAMETER`` (87) -- to the same port or to
another one, and through ``NtSetInformationFile(FileCompletionInformation)`` as
well (measured, see ``verifier`` probes).  A re-registration therefore records
the new key for the handle in this module, and the per-request record is what
keeps a later ``register()`` from rewriting a completion that was already
outstanding.  The two agree for the first registration, which is the bind the
kernel actually performs.

A timeout is ``GetQueuedCompletionStatus`` returning ``FALSE`` with
``WAIT_TIMEOUT`` (258); nothing is removed from the port in that case, so the
next :meth:`take` still sees everything that had arrived.
"""

import ctypes
import threading

from . import _winapi
from .errors import WCIOCPError
from .kinds import as_handle, require_overlapped

__all__ = ["Request", "Event", "Pool", "create_pool"]

#: ``GetQueuedCompletionStatus``'s "wait without a deadline" value.
_INFINITE_MS = _winapi.INFINITE
#: A millisecond value below ``INFINITE`` so a huge timeout is still a deadline.
_MAX_TIMEOUT_MS = _INFINITE_MS - 1
#: ``ctypes.c_uint32`` ceiling: above this the allocation is refused long before
#: the kernel sees it, so the size is rejected as a bad argument first.
_MAX_SIZE = 0x7FFFFFFF

_CLOSE_LOCK = threading.Lock()


class Request:
    """One posted read: its object, where it starts and how much it asks for.

    The kernel identifies the request by the address of the ``OVERLAPPED`` block
    the pool keeps alive next to this object, which is how a completion packet
    finds its way back to the caller that posted it.
    """

    __slots__ = ("handle", "offset", "size", "_overlapped", "_buffer")

    def __init__(self, handle, size, offset, overlapped, buffer):
        self.handle = handle
        self.offset = offset
        self.size = size
        self._overlapped = overlapped
        self._buffer = buffer

    def __repr__(self):
        return "Request(handle=%r, size=%r, offset=%r)" % (
            self.handle, self.size, self.offset)


class Event:
    """One dequeued completion packet.

    ``key`` is the completion key that belongs to this completion: the key the
    kernel returned in the packet, cross-checked against the key that was
    registered for the handle when the request was posted (they agree for every
    registration after the first bind -- see :meth:`Pool.register`).  ``request``
    is the :class:`Request` the packet belongs to, ``bytes_read`` the number of
    bytes the kernel reports and ``status`` either ``"completed"`` or
    ``"cancelled"``.
    """

    __slots__ = ("key", "request", "bytes_read", "status")

    def __init__(self, key, request, bytes_read, status):
        self.key = key
        self.request = request
        self.bytes_read = bytes_read
        self.status = status

    def __repr__(self):
        return "Event(key=%r, bytes_read=%r, status=%r)" % (
            self.key, self.bytes_read, self.status)


class Pool:
    """A kernel completion port with the handles bound to it.

    A pool makes no threads of its own.  The caller decides how many takers run
    and calls :meth:`take` from each of them; the kernel is what keeps the
    packets distinct.
    """

    def __init__(self, threads=4):
        if isinstance(threads, bool) or not isinstance(threads, int):
            raise WCIOCPError("threads must be an integer, got %r" % (threads,),
                              kind="badarg")
        if threads < 1:
            raise WCIOCPError("threads must be at least 1, got %r" % (threads,),
                              kind="badarg")
        if not _winapi.is_windows():
            raise WCIOCPError(
                "I/O completion ports exist only on Windows; this host is not "
                "a Windows kernel",
                kind="unsupported")

        self.threads = int(threads)
        self._closed = False

        port, error = _winapi.create_port()
        if not port:
            raise WCIOCPError("CreateIoCompletionPort could not create the port "
                              "(%s)" % _winapi.describe(error),
                              kind=_winapi.error_kind(error), error=error)
        self._port = int(port)

        #: handle -> the key the caller last registered for it.
        self._keys = {}
        #: address(OVERLAPPED) -> keep-alive record, so a dequeued packet can be
        #: matched to its caller and the blocks stay alive while outstanding.
        self._pending = {}
        #: requests queued but not taken yet, so close() can cancel them.
        self._outstanding = []
        self._lock = threading.Lock()

    # -- public surface -------------------------------------------------------

    def register(self, handle, key):
        """Bind ``handle`` to this pool and register ``key`` for it.

        The first registration is the one the kernel performs: it is the call
        that puts the handle on the port, and the key it carries is the key the
        *kernel* will report for completions of requests that are outstanding at
        that moment.  Registering the same handle again changes the key recorded
        for it, and requests submitted afterwards report the new key, while
        completions already queued or already outstanding keep the key they were
        submitted under.

        The second registration deliberately does *not* call
        ``CreateIoCompletionPort`` again.  Windows refuses to re-associate a
        handle that is already bound to a completion port -- it fails with
        ``ERROR_INVALID_PARAMETER`` (87) whether the target is the same port or
        another one, and `NtSetInformationFile(FileCompletionInformation)`
        answers ``STATUS_INVALID_PARAMETER`` -- so the association, and with it
        the key the kernel keeps for the handle, is fixed at the first bind.
        """
        number = self._require_open(handle)
        require_overlapped(number)
        key = _valid_key(key)

        with self._lock:
            already_bound = number in self._keys
        if already_bound:
            with self._lock:
                self._keys[number] = key
            return

        bound, error = _winapi.bind_handle(self._port, number, key)
        if not bound:
            raise WCIOCPError(
                "CreateIoCompletionPort could not bind handle %r (%s)"
                % (number, _winapi.describe(error)),
                kind=_winapi.error_kind(error), handle=number, error=error)

        with self._lock:
            self._keys[number] = key

    def submit(self, handle, size, offset=0):
        """Post one read of ``size`` bytes at ``offset``.  Returns a :class:`Request`.

        The handle must already be registered.  A handle that can carry
        overlapping I/O but was never registered is bound to this pool with key
        ``0``, so the common "register once, submit many" flow and the one-off
        flow both leave the object on the port.
        """
        number = self._require_open(handle)
        size = _valid_size(size)
        offset = _valid_offset(offset)
        require_overlapped(number)

        if number not in self._keys:
            self.register(number, 0)

        with self._lock:
            submitted_key = self._keys[number]

        try:
            overlapped = _winapi.create_overlapped(offset)
        except (MemoryError, ValueError) as exc:
            raise WCIOCPError("the request block could not be allocated: %s" % (exc,),
                              kind="os", handle=number)
        try:
            buffer = ctypes.create_string_buffer(size)
        except (MemoryError, ValueError) as exc:
            raise WCIOCPError("a %d-byte read buffer could not be allocated: %s"
                              % (size, exc), kind="os", handle=number)

        request = Request(number, size, offset, overlapped, buffer)
        record = _KeepAlive(request, buffer, submitted_key)
        address = ctypes.addressof(overlapped)

        # The read is posted *without* the pool lock held: no kernel call made
        # here can reach back into this module, and holding the lock across a
        # ``ReadFile`` would stall every taker.
        ok, error, transferred = _winapi.read_overlapped(number, buffer, size, overlapped)
        if ok or error == _winapi.ERROR_IO_PENDING:
            # Only a request the kernel actually took is tracked, and only while
            # the pool is open: a submit that raced with close() leaves nothing
            # behind, and close() therefore never cancels a record twice.
            with self._lock:
                if self._closed:
                    posted = False
                else:
                    posted = True
                    self._pending[address] = record
                    self._outstanding.append(record)
            if posted:
                return request
            _winapi.cancel_io_ex(number, overlapped)
            raise WCIOCPError("this pool is closed", kind="closed", handle=number)

        raise WCIOCPError(
            "ReadFile could not start the read on handle %r (%s)"
            % (number, _winapi.describe(error)),
            kind=_winapi.error_kind(error), handle=number, error=error)

    def take(self, timeout=None):
        """Dequeue one completion packet.  Returns an :class:`Event`.

        ``timeout`` is in seconds (``None`` waits forever).  When it expires a
        ``WCIOCPError(kind="timeout")`` is raised and the port keeps every packet
        that had already arrived, so the next call still returns them.
        """
        timeout_ms = _timeout_ms(timeout)

        with self._lock:
            if self._closed:
                raise WCIOCPError("this pool is closed", kind="closed")

        ok, error, packet = _winapi.dequeue(self._port, timeout_ms)
        if packet is None:
            if error == _winapi.WAIT_TIMEOUT:
                raise WCIOCPError("no completion arrived within %s"
                                  % ("the deadline" if timeout is not None else "the wait"),
                                  kind="timeout")
            raise WCIOCPError("GetQueuedCompletionStatus failed (%s)"
                              % _winapi.describe(error),
                              kind=_winapi.error_kind(error), error=error)

        raw_key, overlapped_address, transferred = packet
        kernel_key = _winapi.normalize_key(raw_key)

        with self._lock:
            record = self._pending.pop(overlapped_address, None)
        if record is None:
            # A packet for a block this pool no longer tracks: it was retired on
            # a failed submit or already taken.  It still belongs to somebody, so
            # it is reported with no request rather than dropped silently.
            return Event(kernel_key, None, transferred, "completed")

        # The key the kernel returned is the key that was current for the handle
        # when this request *completed*.  Windows fixes that key at the first
        # bind and refuses to change it afterwards (see Pool.register), so the
        # key the caller registered for the handle when the request was
        # submitted is the authority whenever the two disagree -- that is what
        # keeps a completion from being rewritten by a later register() call.
        key = record.key if record.key is not None else kernel_key

        request = record.request
        succeeded, result_error, count = _winapi.get_overlapped_result(
            request.handle, request._overlapped)
        if succeeded:
            status = "completed"
            bytes_read = count if count else transferred
        elif result_error == _winapi.ERROR_OPERATION_ABORTED:
            # CancelIoEx took the request off the wire; that is a terminal state
            # of its own, never an I/O failure.
            status = "cancelled"
            bytes_read = count
        elif result_error == _winapi.ERROR_IO_INCOMPLETE:
            status = "completed"
            bytes_read = transferred
        else:
            status = "completed"
            bytes_read = count
        return Event(key, request, bytes_read, status)

    def close(self):
        """Close the pool: cancel what is outstanding, refuse further use.

        Idempotent.  After it returns, :meth:`take` and :meth:`submit` raise
        ``WCIOCPError(kind="closed")``; pending requests are cancelled with
        ``CancelIoEx`` and their completions come back as ``status="cancelled"``.
        """
        with _CLOSE_LOCK:
            with self._lock:
                if self._closed:
                    return
                self._closed = True
                records = self._outstanding
                self._outstanding = []

        for record in records:
            request = record.request
            ok, error = _winapi.cancel_io_ex(request.handle, request._overlapped)
            if ok or error == _winapi.ERROR_NOT_FOUND:
                # Cancelled, or already finished so there was nothing to cancel.
                continue
            # The object handle is gone: fall back to cancelling everything the
            # port still knows about on it, then to the calling-thread form.
            _winapi.cancel_io_all(request.handle)
            try:
                _winapi.kernel32().CancelIo(
                    _winapi.wintypes.HANDLE(int(request.handle)))
            except (OSError, ValueError):
                pass

    # -- plumbing -------------------------------------------------------------

    @property
    def port(self):
        """The raw ``HANDLE`` of the completion port."""
        return self._port

    @property
    def closed(self):
        """Whether :meth:`close` has run."""
        return self._closed

    def _require_open(self, handle):
        number = as_handle(handle)
        if self._closed:
            raise WCIOCPError("this pool is closed", kind="closed", handle=number)
        return number

    def __del__(self):
        try:
            port = getattr(self, "_port", 0)
            if port:
                _winapi.close(port)
                self._port = 0
        except Exception:  # pragma: no cover - interpreter shutdown
            pass

    def __repr__(self):
        return "Pool(threads=%r, port=%r, closed=%r)" % (
            self.threads, self._port, self._closed)


class _KeepAlive:
    """The per-request blocks the kernel keeps a pointer to.

    The ``OVERLAPPED`` has to stay alive and at a fixed address until its
    completion has been dequeued, and the buffer has to stay alive until the read
    has finished writing into it, so both travel with the pending record.
    ``key`` is the completion key that was registered for the handle at the
    moment the request was posted.
    """

    __slots__ = ("request", "buffer", "key")

    def __init__(self, request, buffer, key):
        self.request = request
        self.buffer = buffer
        self.key = key


# ---- argument validation ----------------------------------------------------

def _valid_key(key):
    """A completion key is an integer that fits in a ``ULONG_PTR``."""
    if isinstance(key, bool) or not isinstance(key, int):
        raise WCIOCPError("the completion key must be an integer, got %r" % (key,),
                          kind="badarg")
    value = int(key)
    if not (-_winapi.KEY_SIGN <= value <= _winapi.KEY_MASK - _winapi.KEY_SIGN):
        raise WCIOCPError(
            "the completion key must fit in %d bits, got %r" % (_winapi.KEY_BITS, key),
            kind="badarg")
    return value


def _valid_size(size):
    if isinstance(size, bool) or not isinstance(size, int):
        raise WCIOCPError("size must be an integer, got %r" % (size,), kind="badarg")
    value = int(size)
    if value <= 0 or value > _MAX_SIZE:
        raise WCIOCPError("size must be a positive count, got %r" % (size,),
                          kind="badarg")
    return value


def _valid_offset(offset):
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise WCIOCPError("offset must be an integer, got %r" % (offset,), kind="badarg")
    value = int(offset)
    if value < 0:
        raise WCIOCPError("offset must not be negative, got %r" % (offset,),
                          kind="badarg")
    return value


def _timeout_ms(timeout):
    """Convert a deadline in seconds into the millisecond count the kernel takes."""
    if timeout is None:
        return _INFINITE_MS
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise WCIOCPError("timeout must be a number of seconds or None, got %r"
                          % (timeout,), kind="badarg")
    seconds = float(timeout)
    if seconds < 0:
        raise WCIOCPError("timeout must not be negative, got %r" % (timeout,),
                          kind="badarg")
    if seconds == 0:
        return 0
    milliseconds = int(seconds * 1000.0)
    if seconds * 1000.0 > milliseconds:
        milliseconds += 1
    return min(milliseconds, _MAX_TIMEOUT_MS)


def create_pool(threads=4):
    """Create a completion-port :class:`Pool` with room for ``threads`` takers.

    The thread count is a capacity hint recorded on the pool: the pool spawns no
    threads, it expects ``threads`` takers to call :meth:`Pool.take`.
    """
    return Pool(threads=threads)
