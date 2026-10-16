"""Smoke tests for the wcancel public API.

These are the tests that run while the collector's read layer is being
developed.  They pin down the parts of the contract that must hold whatever the
implementation does underneath: the shape of the API, the classification of bad
arguments, and the types the entry points hand back.  The end-to-end behaviour of
an outstanding read is exercised by the semantic suite, not here.
"""

import ctypes
import os
from ctypes import wintypes

import pytest

import wcancel
from wcancel import (
    Completion,
    Request,
    WCancelError,
    cancel,
    cancel_all,
    is_overlapped,
    submit,
    wait,
)

if os.name != "nt":
    pytest.skip("the read layer needs the Win32 overlapping-I/O API",
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


_open_pipes = []
_open_requests = []
_pipe_serial = [0]


def _open_pipe():
    """A duplex pipe whose server end is ready for an overlapping read."""
    _pipe_serial[0] += 1
    name = "\\\\.\\pipe\\wcancel-smoke-%d-%d" % (os.getpid(), _pipe_serial[0])
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
    _open_pipes.append(entry)
    return entry


def _submit(server, size, offset=0):
    """Submit a read and remember it so the end of the test can retire it."""
    request = submit(server, size, offset)
    _open_requests.append(request)
    return request


def _close(number):
    _kernel32.CloseHandle(wintypes.HANDLE(int(number)))


def _close_all():
    """Retire outstanding reads and close every pipe this module opened.

    An object must not be closed while an overlapping read on it is still
    outstanding: the system holds on to that request's control block until the
    read comes back.  Each read is therefore waited for (bounded) or brought
    back by the system before its handle goes away.
    """
    for request in _open_requests:
        try:
            wait(request, timeout=2.0)
        except WCancelError:
            for handle in list(_open_pipes):
                if int(handle[0]) == int(request.handle):
                    _kernel32.CancelIo(wintypes.HANDLE(int(handle[0])))
    del _open_requests[:]

    while _open_pipes:
        server, client = _open_pipes.pop()
        _close(client)
        # The far end is gone, so anything still outstanding comes back at once.
        _kernel32.WaitForSingleObject(wintypes.HANDLE(int(server)), 200)
        _close(server)


@pytest.fixture(autouse=True)
def _clean_slate():
    yield
    _close_all()


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
    for name in ("WCancelError", "Request", "Completion", "submit", "cancel",
                 "cancel_all", "wait", "is_overlapped"):
        assert hasattr(wcancel, name), "wcancel does not export %s" % name
    for name in ("submit", "cancel", "cancel_all", "wait"):
        assert callable(getattr(wcancel, name))


def test_error_kinds_are_the_documented_four():
    assert WCancelError.KINDS == ("unsupported", "badarg", "os", "timeout")
    error = WCancelError("a message", kind="timeout", handle=7)
    assert error.kind == "timeout"
    assert "7" in str(error)


def test_completion_status_vocabulary_is_stable():
    assert Completion(0, "completed").status == "completed"
    assert Completion(12, "cancelled").status == "cancelled"


def test_submit_rejects_bad_arguments():
    with pytest.raises(WCancelError) as not_a_handle:
        submit("not-a-handle", 8)
    assert not_a_handle.value.kind == "badarg"

    with pytest.raises(WCancelError) as null_handle:
        submit(0, 8)
    assert null_handle.value.kind in WCancelError.KINDS

    with pytest.raises(WCancelError) as bad_size:
        submit(1, "many")
    assert bad_size.value.kind == "badarg"

    with pytest.raises(WCancelError) as negative_size:
        submit(1, -8)
    assert negative_size.value.kind == "badarg"

    with pytest.raises(WCancelError) as negative_offset:
        submit(1, 8, -1)
    assert negative_offset.value.kind == "badarg"


def test_cancel_and_wait_reject_bad_arguments():
    with pytest.raises(WCancelError) as bad_request:
        cancel("not-a-request")
    assert bad_request.value.kind == "badarg"

    with pytest.raises(WCancelError) as bad_wait:
        wait(object())
    assert bad_wait.value.kind == "badarg"

    with pytest.raises(WCancelError) as bad_timeout:
        wait("not-a-request", timeout="soon")
    assert bad_timeout.value.kind == "badarg"


def test_is_overlapped_reports_a_boolean():
    server, _client = _open_pipe()
    assert isinstance(is_overlapped(server), bool)

    with pytest.raises(WCancelError) as caught:
        is_overlapped("not-a-handle")
    assert caught.value.kind == "badarg"


def test_submit_returns_a_request_that_names_its_read():
    server, _client = _open_pipe()
    request = _submit(server, size=64, offset=128)
    assert isinstance(request, Request)
    assert request.handle == server
    assert request.size == 64
    assert request.offset == 128


def test_cancel_returns_a_boolean_and_cancel_all_an_integer():
    server, _client = _open_pipe()
    request = _submit(server, size=64)
    assert isinstance(cancel(request), bool)
    assert isinstance(cancel_all(server), int)


def test_wait_reports_a_timeout_kind_when_nothing_arrives():
    server, _client = _open_pipe()
    request = _submit(server, size=64)
    with pytest.raises(WCancelError) as caught:
        wait(request, timeout=0.25)
    assert caught.value.kind == "timeout"


def test_a_read_that_completes_returns_a_completion():
    server, client = _open_pipe()
    request = _submit(server, size=64)
    assert _write(client, b"smoke-payload") == len(b"smoke-payload")
    completion = wait(request, timeout=5.0)
    assert isinstance(completion, Completion)
    assert completion.status in ("completed", "cancelled")
    assert isinstance(completion.bytes_read, int)
    assert completion.bytes_read >= 0
