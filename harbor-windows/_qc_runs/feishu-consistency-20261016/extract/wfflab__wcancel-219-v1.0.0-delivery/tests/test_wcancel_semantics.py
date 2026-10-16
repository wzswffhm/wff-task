"""Hidden semantic suite for the wfflab__wcancel-219 Windows cancellation contract.

This file is injected by the evaluation side and is never shipped in the task
package.  Every assertion that decides whether the candidate is right is backed
by a measurement the suite performs itself:

* it creates its own named pipe and opens a client end with
  ``FILE_FLAG_OVERLAPPED``, so the objects really are cancellable;
* it issues its own pending reads **through the candidate's** ``submit`` and
  keeps no trust in what the candidate reports about them;
* it cancels from a second thread and then reads the terminal state back from
  the kernel, expecting ``cancelled`` for the aborted request and a normal
  completion for its neighbour;
* it writes into the client end itself to prove that an uncancelled request
  still delivers the exact bytes that were written.

The candidate never gets to describe its own result.
"""

import ctypes
import os
import subprocess
import sys
import threading
import time
import uuid
from ctypes import wintypes

import pytest

if os.name != "nt":
    pytest.skip(
        "the wcancel contract is a Windows overlapped-I/O contract",
        allow_module_level=True,
    )

from wcancel import (  # noqa: E402  (import after the platform guard on purpose)
    WCancelError,
    cancel,
    cancel_all,
    submit,
    wait,
)

# --------------------------------------------------------------- Win32 layer

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                       wintypes.DWORD, wintypes.LPVOID]
_kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
_kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.HANDLE]
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
_kernel32.WriteFile.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL


def _invalid(handle) -> bool:
    return handle in (None, 0, -1, INVALID_HANDLE_VALUE, 0xFFFFFFFFFFFFFFFF)


def _write(handle, payload: bytes) -> int:
    written = wintypes.DWORD(0)
    ok = _kernel32.WriteFile(handle, payload, len(payload), ctypes.byref(written), None)
    assert ok, f"the suite could not write into its own pipe (err={ctypes.get_last_error()})"
    return written.value


# ------------------------------------------------------------- suite fixtures


@pytest.fixture
def overlapped_pipe():
    """A named pipe server end plus a client end, both opened for overlapped I/O."""
    name = rf"\\.\pipe\wcancel-graded-{os.getpid()}-{uuid.uuid4().hex}"
    server = _kernel32.CreateNamedPipeW(
        name,
        PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        1, 65536, 65536, 0, None,
    )
    if _invalid(server):
        pytest.fail(f"the suite could not create its own named pipe (err={ctypes.get_last_error()})")
    client = _kernel32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_ALL, None,
                                   OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if _invalid(client):
        _kernel32.CloseHandle(server)
        pytest.fail(f"the suite could not open its own pipe client (err={ctypes.get_last_error()})")
    try:
        yield server, client
    finally:
        _kernel32.CloseHandle(client)
        _kernel32.CloseHandle(server)


@pytest.fixture
def plain_file(tmp_path):
    """A handle on a file that was deliberately opened WITHOUT overlapped I/O."""
    path = tmp_path / "plain.bin"
    path.write_bytes(b"x" * 256)
    handle = _kernel32.CreateFileW(str(path), GENERIC_READ, FILE_SHARE_ALL, None,
                                   OPEN_EXISTING, 0, None)
    if _invalid(handle):
        pytest.fail(f"the suite could not open a plain file handle (err={ctypes.get_last_error()})")
    try:
        yield handle
    finally:
        _kernel32.CloseHandle(handle)


def _pending(handle):
    """Submit a read that cannot complete: nothing has been written into the pipe."""
    return submit(handle, 64)


# ------------------------------------------------------- cancellation is exact


def test_cancel_affects_only_the_target_request(overlapped_pipe):
    server, _ = overlapped_pipe
    first = _pending(server)
    second = _pending(server)

    assert cancel(first) is True
    assert wait(first, timeout=5.0).status == "cancelled"

    # The neighbour must still be outstanding: nothing was written into the pipe.
    with pytest.raises(WCancelError) as excinfo:
        wait(second, timeout=0.4)
    assert excinfo.value.kind == "timeout", (
        "cancelling one request disturbed another request on the same handle"
    )


def test_cancel_works_from_another_thread(overlapped_pipe):
    server, _ = overlapped_pipe
    request = _pending(server)
    outcome = {}

    def worker():
        time.sleep(0.25)
        try:
            outcome["cancelled"] = cancel(request)
        except BaseException as exc:  # noqa: BLE001 - reported to the main thread
            outcome["error"] = exc

    thread = threading.Thread(target=worker, name="wcancel-canceller")
    thread.start()
    thread.join(15.0)
    assert not thread.is_alive(), "the cancelling thread did not return"
    assert "error" not in outcome, f"cancel() raised from another thread: {outcome.get('error')!r}"
    assert outcome.get("cancelled") is True

    done = wait(request, timeout=5.0)
    assert done.status == "cancelled", (
        "cancel() reported success from another thread but the request was never aborted"
    )


def test_uncancelled_request_still_delivers_the_bytes(overlapped_pipe):
    server, client = overlapped_pipe
    first = _pending(server)
    second = _pending(server)

    assert cancel(first) is True
    assert wait(first, timeout=5.0).status == "cancelled"

    payload = b"wcancel-payload"
    assert _write(client, payload) == len(payload)

    done = wait(second, timeout=5.0)
    assert done.status == "completed", "an uncancelled request was reported as cancelled"
    assert done.bytes_read == len(payload)


# --------------------------------------------- the terminal state is reported


def test_cancelled_request_reports_cancelled_status(overlapped_pipe):
    server, _ = overlapped_pipe
    request = _pending(server)

    assert cancel(request) is True
    done = wait(request, timeout=5.0)
    assert done.status == "cancelled"
    assert done.bytes_read == 0
    assert not isinstance(done, BaseException)


def test_completed_request_cannot_be_cancelled(overlapped_pipe):
    server, client = overlapped_pipe
    request = _pending(server)
    assert _write(client, b"abcdefgh") == 8

    done = wait(request, timeout=5.0)
    assert done.status == "completed"
    assert cancel(request) is False, "cancel() claimed success for a request that had finished"


def test_second_cancel_reports_false(overlapped_pipe):
    server, _ = overlapped_pipe
    request = _pending(server)

    assert cancel(request) is True
    assert wait(request, timeout=5.0).status == "cancelled"
    assert cancel(request) is False, "cancel() claimed success a second time for the same request"


# ------------------------------------------------- the object must be capable


def test_non_overlapped_handle_is_unsupported(plain_file):
    with pytest.raises(WCancelError) as excinfo:
        submit(plain_file, 16)
    assert excinfo.value.kind == "unsupported"


# ------------------------------------------------------------------ the rest


def test_submit_leaves_request_pending(overlapped_pipe):
    server, _ = overlapped_pipe
    request = _pending(server)
    with pytest.raises(WCancelError) as excinfo:
        wait(request, timeout=0.4)
    assert excinfo.value.kind == "timeout"


def test_cancel_returns_a_bool(overlapped_pipe):
    server, _ = overlapped_pipe
    request = _pending(server)
    answer = cancel(request)
    assert isinstance(answer, bool)
    try:
        wait(request, timeout=5.0)
    except WCancelError as exc:
        assert exc.kind != "timeout", "cancel() did not take the request off the wire"


def test_wait_returns_a_completion(overlapped_pipe):
    server, client = overlapped_pipe
    request = _pending(server)
    assert _write(client, b"hello") == 5
    done = wait(request, timeout=5.0)
    assert done.status == "completed"
    assert done.bytes_read == 5


def test_wait_timeout_raises_timeout_kind(overlapped_pipe):
    server, _ = overlapped_pipe
    request = _pending(server)
    with pytest.raises(WCancelError) as excinfo:
        wait(request, timeout=0.3)
    assert excinfo.value.kind == "timeout"


def test_invalid_handle_is_rejected():
    with pytest.raises(WCancelError) as excinfo:
        submit(-1, 16)
    assert excinfo.value.kind == "badarg"


def test_cancel_all_cancels_every_submitted_request(overlapped_pipe):
    server, _ = overlapped_pipe
    first = _pending(server)
    second = _pending(server)

    stopped = cancel_all(server)
    assert isinstance(stopped, int) and stopped >= 2
    for request in (first, second):
        try:
            wait(request, timeout=5.0)
        except WCancelError as exc:
            assert exc.kind != "timeout", "cancel_all left a request still pending"


def test_visible_smoke_suite_still_passes():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "test_wcancel_basic.py"),
        os.path.join(os.path.dirname(here), "tests", "test_wcancel_basic.py"),
    ]
    smoke = next((path for path in candidates if os.path.isfile(path)), None)
    assert smoke is not None, "the visible smoke suite was not staged next to this file"

    workspace = os.environ.get("WCANCEL_WORKSPACE_ROOT") or os.path.dirname(os.path.dirname(here))
    env = dict(os.environ)
    env["PYTHONPATH"] = workspace + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", smoke],
        capture_output=True, text=True, env=env,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
