"""Smoke tests for the wciocp public API.

These are the tests that run while the collector's completion layer is being
developed.  They pin down the parts of the contract that hold whatever the
implementation does underneath: the shape of the API, the classification of bad
arguments, and the types the entry points hand back.  The behaviour of a pool
that is actually carrying reads is exercised by the semantic suite, not here.
"""

import atexit
import ctypes
import os
from ctypes import wintypes

import pytest

import wciocp
from wciocp import Event, Pool, Request, WCIOCPError, create_pool, is_overlapped

if os.name != "nt":
    pytest.skip("the completion layer needs the Win32 overlapping-I/O API",
                allow_module_level=True)

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
PIPE_ACCESS_DUPLEX = 0x00000003
ERROR_IO_PENDING = 997
WAIT_OBJECT_0 = 0x00000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
_kernel32.CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
]
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_kernel32.CreateEventW.restype = wintypes.HANDLE
_kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL,
                                   wintypes.LPCWSTR]
_kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
_kernel32.WriteFile.restype = wintypes.BOOL
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.GetOverlappedResult.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
                                          ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
_kernel32.GetOverlappedResult.restype = wintypes.BOOL
_kernel32.CancelIo.argtypes = [wintypes.HANDLE]
_kernel32.CancelIo.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]

_open_handles = []
_open_requests = []
_pipe_serial = [0]


def _open_pipe():
    """A duplex pipe whose server end is open for overlapping use."""
    _pipe_serial[0] += 1
    name = "\\\\.\\pipe\\wciocp-smoke-%d-%d" % (os.getpid(), _pipe_serial[0])
    server = _kernel32.CreateNamedPipeW(name, PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
                                        0, 1, 65536, 65536, 0, None)
    if server == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateNamedPipeW failed")
    client = _kernel32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None,
                                   OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if client == INVALID_HANDLE_VALUE:
        _kernel32.CloseHandle(wintypes.HANDLE(server))
        raise OSError(ctypes.get_last_error(), "CreateFileW failed")
    entry = (int(server), int(client))
    _open_handles.append(entry)
    return entry


def _close(number):
    _kernel32.CloseHandle(wintypes.HANDLE(int(number)))


def _submit(pool, handle, size, offset=0):
    """Submit a read and remember it so the end of the test can retire it."""
    request = pool.submit(handle, size, offset)
    _open_requests.append((pool, request))
    return request


def _retire_all():
    """Bring every read this module started back before its pipe goes away.

    An object must not be closed while an overlapping read on it is still
    outstanding: the system keeps the request's control block and buffer until
    the read comes back.  Every read is therefore either collected from its pool
    (bounded) or cancelled and collected before its handle is closed.
    """
    for pool, request in _open_requests:
        _kernel32.CancelIo(wintypes.HANDLE(int(request.handle)))
    pending = [(pool, request) for pool, request in _open_requests]
    while pending:
        pool, request = pending[0]
        try:
            pool.take(timeout=2.0)
        except WCIOCPError:
            pass
        pending.pop(0)
    del _open_requests[:]


def _purge():
    """Retire every read this module started, then close every pipe it opened."""
    _retire_all()
    while _open_handles:
        server, client = _open_handles.pop()
        _close(client)
        # The far end is gone, so anything still outstanding comes back at once.
        _kernel32.WaitForSingleObject(wintypes.HANDLE(int(server)), 200)
        _close(server)


atexit.register(_purge)


@pytest.fixture(autouse=True)
def _clean_slate():
    """Retire outstanding reads and close every pipe once the test is over."""
    yield
    _purge()


def _write(handle, blob):
    """Write ``blob`` to ``handle`` and wait for the write to finish."""
    event = _kernel32.CreateEventW(None, True, False, None)
    overlapped = _Overlapped()
    overlapped.hEvent = event
    written = wintypes.DWORD(0)
    ok = _kernel32.WriteFile(wintypes.HANDLE(int(handle)), blob, len(blob),
                             ctypes.byref(written), ctypes.byref(overlapped))
    if not ok:
        if ctypes.get_last_error() != ERROR_IO_PENDING:
            _kernel32.CloseHandle(wintypes.HANDLE(event))
            raise OSError(ctypes.get_last_error(), "WriteFile failed")
        if _kernel32.WaitForSingleObject(event, 5000) != WAIT_OBJECT_0:
            _kernel32.CloseHandle(wintypes.HANDLE(event))
            raise OSError("the write never finished")
        result = wintypes.DWORD(0)
        _kernel32.GetOverlappedResult(wintypes.HANDLE(int(handle)),
                                      ctypes.byref(overlapped), ctypes.byref(result), False)
        written = result
    _kernel32.CloseHandle(wintypes.HANDLE(event))
    return int(written.value)


def test_public_api_is_exported():
    for name in ("WCIOCPError", "Pool", "Event", "Request", "create_pool",
                 "is_overlapped"):
        assert hasattr(wciocp, name), "wciocp does not export %s" % name


def test_create_pool_is_callable_with_the_documented_signature():
    import inspect

    parameters = inspect.signature(create_pool).parameters
    assert list(parameters) == ["threads"]
    assert parameters["threads"].default == 4

    for name in ("register", "submit", "take", "close"):
        assert callable(getattr(Pool, name)), "Pool does not expose %s" % name

    take = inspect.signature(Pool.take).parameters
    assert take["timeout"].default is None

    submit = inspect.signature(Pool.submit).parameters
    assert submit["offset"].default == 0


def test_error_kinds_are_the_documented_five():
    assert WCIOCPError.KINDS == ("unsupported", "badarg", "os", "timeout", "closed")
    error = WCIOCPError("a message", kind="closed", handle=7)
    assert error.kind == "closed"
    assert "7" in str(error)


def test_event_carries_the_documented_fields():
    request = Request.__new__(Request)
    event = Event.__new__(Event)
    event.key = 0x11
    event.request = request
    event.bytes_read = 5
    event.status = "completed"
    assert event.key == 0x11
    assert event.request is request
    assert event.bytes_read == 5
    assert event.status == "completed"


def test_request_names_its_read():
    request = Request.__new__(Request)
    request.handle = 9
    request.size = 64
    request.offset = 128
    assert request.handle == 9
    assert request.size == 64
    assert request.offset == 128


def test_submit_rejects_bad_arguments():
    pool = create_pool(threads=2)
    try:
        with pytest.raises(WCIOCPError) as not_a_handle:
            pool.submit("not-a-handle", 8)
        assert not_a_handle.value.kind == "badarg"

        with pytest.raises(WCIOCPError) as null_handle:
            pool.submit(0, 8)
        assert null_handle.value.kind in WCIOCPError.KINDS

        with pytest.raises(WCIOCPError) as bad_size:
            pool.submit(1, "many")
        assert bad_size.value.kind == "badarg"

        with pytest.raises(WCIOCPError) as negative_size:
            pool.submit(1, -8)
        assert negative_size.value.kind == "badarg"

        with pytest.raises(WCIOCPError) as negative_offset:
            pool.submit(1, 8, -1)
        assert negative_offset.value.kind == "badarg"
    finally:
        pool.close()


def test_register_rejects_bad_arguments():
    pool = create_pool(threads=2)
    try:
        with pytest.raises(WCIOCPError) as not_a_handle:
            pool.register("not-a-handle", 1)
        assert not_a_handle.value.kind == "badarg"

        with pytest.raises(WCIOCPError) as not_a_key:
            pool.register(1, "job")
        assert not_a_key.value.kind == "badarg"
    finally:
        pool.close()


def test_take_rejects_an_unusable_timeout():
    pool = create_pool(threads=2)
    try:
        with pytest.raises(WCIOCPError) as caught:
            pool.take(timeout="soon")
        assert caught.value.kind == "badarg"
    finally:
        pool.close()


def test_a_pool_can_be_built_and_closed():
    pool = create_pool(threads=2)
    assert isinstance(pool, Pool)
    pool.close()
    pool.close()


def test_register_accepts_an_overlapping_handle():
    pool = create_pool(threads=2)
    try:
        server, _client = _open_pipe()
        assert pool.register(server, 0x21) is None
    finally:
        pool.close()


def test_submit_returns_a_request_that_names_its_read():
    pool = create_pool(threads=2)
    try:
        server, _client = _open_pipe()
        pool.register(server, 0x21)
        request = _submit(pool, server, size=64, offset=128)
        assert isinstance(request, Request)
        assert request.handle == server
        assert request.size == 64
        assert request.offset == 128
    finally:
        pool.close()


def test_take_returns_an_event_for_a_finished_read():
    pool = create_pool(threads=2)
    try:
        server, client = _open_pipe()
        pool.register(server, 0x21)
        _submit(pool, server, size=64)
        assert _write(client, b"smoke-payload") == len(b"smoke-payload")
        event = pool.take(timeout=1.0)
        assert isinstance(event, Event)
        assert isinstance(event.key, int)
        assert isinstance(event.bytes_read, int)
        assert event.status in ("completed", "cancelled")
    finally:
        pool.close()


def test_take_reports_a_timeout_kind_when_nothing_arrives():
    pool = create_pool(threads=2)
    try:
        server, _client = _open_pipe()
        pool.register(server, 0x21)
        with pytest.raises(WCIOCPError) as caught:
            pool.take(timeout=0.1)
        assert caught.value.kind == "timeout"
    finally:
        pool.close()


def test_is_overlapped_reports_a_boolean():
    server, _client = _open_pipe()
    assert isinstance(is_overlapped(server), bool)

    with pytest.raises(WCIOCPError) as caught:
        is_overlapped("not-a-handle")
    assert caught.value.kind == "badarg"
