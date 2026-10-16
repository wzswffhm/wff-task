"""The completion layer of the collector.

Every object the collector reads from is opened for overlapping use, so a read
comes back straight away and its result turns up later.  A :class:`Pool` is the
place where those results are collected: objects are registered with a
*completion key*, reads are submitted against registered objects, and worker
threads call :meth:`Pool.take` to collect the notifications that come back.

Typical use::

    pool = create_pool(threads=4)
    pool.register(pipe, 0x11)
    request = pool.submit(pipe, size=4096, offset=0)
    ...
    event = pool.take(timeout=5.0)
    print(hex(event.key), event.bytes_read)

The delivery thread below watches the reads the pool has outstanding and hands
their results over to the list the callers of :meth:`Pool.take` read from.
"""

import ctypes
import threading
import time

from . import _winapi
from .errors import WCIOCPError
from .kinds import is_overlapped

DEFAULT_TIMEOUT = None

# How long the delivery thread is willing to sleep in one go.
_IDLE_SLICE = 0.05
# How many notifications the layer keeps around to hand back to callers.
_HISTORY = 32
# How many ids of handled notifications the layer keeps track of.
_TRACKED = 4096
# How many finished reads the layer holds on to before folding the list over.
_KEPT = 4096


class Request(object):
    """One overlapping read that has been handed to the operating system."""

    def __init__(self, handle, size, offset, buffer, overlapped, kernel_event):
        self.handle = int(handle)
        self.size = int(size)
        self.offset = int(offset)
        self._buffer = buffer
        self._overlapped = overlapped
        self._kernel_event = kernel_event
        self._state = "outstanding"

    def __repr__(self):
        return "Request(handle=%d, offset=%d, size=%d)" % (self.handle, self.offset, self.size)


class Event(object):
    """One notification collected from the pool.

    ``key`` is the completion key of the object the read was issued against,
    ``request`` is the :class:`Request` that produced it, ``bytes_read`` is how
    many bytes the read delivered and ``status`` is ``"completed"`` or
    ``"cancelled"``.
    """

    def __init__(self, key, request, bytes_read=0, status="completed"):
        self.key = int(key)
        self.request = request
        self.bytes_read = int(bytes_read)
        self.status = status

    def __repr__(self):
        return "Event(key=%r, bytes_read=%d, status=%r)" % (
            self.key, self.bytes_read, self.status)


class Pool(object):
    """A set of registered objects and the notifications they produce."""

    def __init__(self, threads=4):
        self.threads = int(threads)
        self._keys = {}
        self._outstanding = []
        self._retired = []
        self._staging = []
        self._ready = []
        self._recent = []
        self._served = 0
        self._handled = set()
        self._mutex = threading.Lock()
        self._ready_lock = threading.Lock()
        self._cond = threading.Condition()
        self._closing = False
        self._dropped = False
        self._deliverer = threading.Thread(
            target=self._deliver_loop, name="wciocp-deliver")
        self._deliverer.daemon = True
        self._deliverer.start()

    def __repr__(self):
        return "Pool(threads=%d, registered=%d)" % (self.threads, len(self._keys))

    # ------------------------------------------------------------ public API

    def register(self, handle, key):
        """Register ``handle`` with the pool under the completion key ``key``."""
        number = _winapi.as_number(handle)
        if not _winapi.is_usable_handle(number):
            raise WCIOCPError("not a usable object handle: %r" % (handle,),
                              kind="badarg", handle=handle)
        if isinstance(key, bool) or not isinstance(key, int):
            raise WCIOCPError("the completion key must be an integer, got %r" % (key,),
                              kind="badarg", handle=number)
        if not is_overlapped(number):
            raise WCIOCPError(
                "object %r was not opened for overlapping use" % (handle,),
                kind="unsupported", handle=number)
        with self._mutex:
            self._keys[number] = int(key)

    def submit(self, handle, size, offset=0):
        """Start one overlapping read of ``size`` bytes at ``offset``."""
        self._ensure_open()
        number = _winapi.as_number(handle)
        if not _winapi.is_usable_handle(number):
            raise WCIOCPError("not a usable object handle: %r" % (handle,),
                              kind="badarg", handle=handle)
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise WCIOCPError("size must be a positive number of bytes, got %r" % (size,),
                              kind="badarg")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise WCIOCPError("offset must not be negative, got %r" % (offset,),
                              kind="badarg")

        kernel_event = _winapi.Event.create()
        buffer = ctypes.create_string_buffer(size)
        overlapped = _winapi.OVERLAPPED()
        overlapped.hEvent = kernel_event.handle
        request = Request(number, size, offset, buffer, overlapped, kernel_event)

        try:
            ok, error = _winapi.start_read(number, buffer, size, offset, overlapped)
        except WCIOCPError:
            kernel_event.close()
            raise

        if ok:
            request._state = "done"
            self._retire(request)
            self._deliver(number, request, _winapi.transferred_bytes(overlapped))
            return request

        if error == _winapi.ERROR_IO_PENDING:
            with self._mutex:
                self._outstanding.append(request)
            return request

        kernel_event.close()
        raise WCIOCPError(
            "the read on object %r could not be started (%s)"
            % (handle, _winapi.describe(error)),
            kind=_winapi.error_kind(error),
            handle=handle,
        )

    def take(self, timeout=DEFAULT_TIMEOUT):
        """Collect one notification from the pool.

        ``timeout`` is in seconds; ``None`` means the caller is willing to wait
        for as long as it takes.
        """
        deadline = None if timeout is None else time.monotonic() + _seconds(timeout)

        while True:
            measured = len(self._staging) + len(self._ready)
            event = self._collect(measured)
            if event is not None:
                return event

            if self._closing:
                raise WCIOCPError("the pool has been closed", kind="closed")

            if deadline is None:
                remaining = _IDLE_SLICE
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._expire(timeout)
                remaining = min(remaining, _IDLE_SLICE)

            with self._cond:
                self._cond.wait(remaining)

    def close(self):
        """Stop the pool and cancel the reads that are still outstanding."""
        if self._closing:
            return
        # The delivery thread is taken out of the picture first: from here on
        # nothing else touches the reads this pool holds.
        self._closing = True
        with self._cond:
            self._cond.notify_all()
        if self._deliverer is not threading.current_thread():
            self._deliverer.join(5.0)

        with self._mutex:
            outstanding = list(self._outstanding)
            del self._outstanding[:]
        for request in outstanding:
            request._state = "cancelled"
            self._retire(request)
            self._deliver(request.handle, request, 0, "cancelled")

    # ------------------------------------------------------------- internals

    def _ensure_open(self):
        if self._closing:
            raise WCIOCPError("the pool has been closed", kind="closed")

    def _collect(self, measured):
        """Hand back one of the notifications that have arrived."""
        if len(self._ready) == 0:
            # The delivery thread hands its list over to the ready list.
            self._ready = list(self._staging)
            del self._staging[:]

        with self._ready_lock:
            if self._ready:
                # Take the notification that sits at the place this caller was
                # given when it measured the list.
                if measured > len(self._ready):
                    position = len(self._ready) - 1
                else:
                    position = measured - 1
                event = self._ready.pop(position)
                self._recent.append(event)
                if len(self._recent) > _HISTORY:
                    del self._recent[0]
                self._served = len(self._recent)
            elif self._recent:
                # Everything the layer has collected has been handed out
                # already; hand back one of the notifications it holds.
                event = self._recent[self._served % len(self._recent)]
                self._served += 1
            else:
                event = None
            if event is not None:
                self._handled.add(id(event))
                if len(self._handled) > _TRACKED:
                    self._handled.clear()
            return event

    def _expire(self, timeout):
        """Report that the caller's deadline passed."""
        self._dropped = True
        with self._ready_lock:
            del self._ready[:]
        raise WCIOCPError("nothing arrived within %r seconds" % (timeout,),
                          kind="timeout")

    def _deliver(self, handle, request, bytes_read, status="completed"):
        """Record one finished read for the callers of :meth:`take`."""
        if self._closing or self._dropped:
            return
        event = Event(self._key_of(handle), request, bytes_read, status)
        with self._ready_lock:
            self._staging.append(event)
        with self._cond:
            self._cond.notify_all()

    def _key_of(self, handle):
        """The completion key that is registered for ``handle``."""
        with self._mutex:
            return self._keys.get(int(handle), 0)

    def _retire(self, request):
        """Hold on to a finished read so its control block stays where it is.

        The system goes on writing into the control block and the buffer of a
        read until the read has been dealt with, so the layer keeps a hand on
        both instead of letting them go the moment the read shows up as done.
        """
        with self._mutex:
            self._retired.append(request)
            if len(self._retired) > _KEPT:
                del self._retired[:-_KEPT]

    def _harvest(self):
        """Move the reads that have finished into the ready list."""
        with self._mutex:
            outstanding = list(self._outstanding)
        for request in outstanding:
            kernel_event = request._kernel_event
            overlapped = request._overlapped
            if kernel_event is None or overlapped is None:
                continue
            outcome = _winapi.wait_for(kernel_event.handle, 0)
            if outcome != "signalled":
                continue
            with self._mutex:
                try:
                    self._outstanding.remove(request)
                except ValueError:
                    continue
            request._state = "done"
            self._retire(request)
            self._deliver(request.handle, request,
                          _winapi.transferred_bytes(overlapped))

    def _deliver_loop(self):
        """Collect finished reads for as long as the pool is open."""
        while not self._closing:
            self._harvest()
            with self._cond:
                self._cond.wait(_IDLE_SLICE)


def _seconds(value):
    """Turn a number of seconds into a float, rejecting unusable values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WCIOCPError("timeout must be a number of seconds, got %r" % (value,),
                          kind="badarg")
    if value < 0:
        raise WCIOCPError("timeout must not be negative, got %r" % (value,),
                          kind="badarg")
    return float(value)


def create_pool(threads=4):
    """Create a completion :class:`Pool` served by ``threads`` workers."""
    if isinstance(threads, bool) or not isinstance(threads, int) or threads <= 0:
        raise WCIOCPError("threads must be a positive integer, got %r" % (threads,),
                          kind="badarg")
    return Pool(threads)
