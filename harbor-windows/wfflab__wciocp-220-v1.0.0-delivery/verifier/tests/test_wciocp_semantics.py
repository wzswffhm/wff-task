"""Hidden semantic suite for the wfflab__wciocp-220 Windows completion-port contract.

This file is injected by the evaluation side and is never shipped in the task
package.  Every assertion is backed by a measurement the suite performs itself:

* it creates its own named pipes opened with ``FILE_FLAG_OVERLAPPED``;
* it registers each handle with its **own** completion key and issues its own
  pending reads through the candidate's ``submit``;
* it draws events from several threads at once, so a process-local queue that
  every waiter scans will hand the same event to two threads or drop it;
* it checks the key that actually came back for each request, and it writes into
  its own client ends to confirm the byte counts.

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
        "the wciocp contract is a Windows completion-port contract",
        allow_module_level=True,
    )

from wciocp import (  # noqa: E402  (import after the platform guard on purpose)
    WCIOCPError,
    create_pool,
)

# --------------------------------------------------------------- Win32 layer

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
PIPE_ACCESS_DUPLEX = 0x00000003
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


def _make_pipe(name: str):
    server = _kernel32.CreateNamedPipeW(
        name,
        PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
        0, 1, 65536, 65536, 0, None,
    )
    if _invalid(server):
        pytest.fail(f"the suite could not create its own named pipe (err={ctypes.get_last_error()})")
    client = _kernel32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_ALL, None,
                                   OPEN_EXISTING, FILE_FLAG_OVERLAPPED, None)
    if _invalid(client):
        _kernel32.CloseHandle(server)
        pytest.fail(f"the suite could not open its own pipe client (err={ctypes.get_last_error()})")
    return server, client


# ------------------------------------------------------------- suite fixtures


@pytest.fixture
def pool_and_pipe():
    tag = uuid.uuid4().hex
    server, client = _make_pipe(rf"\\.\pipe\wciocp-graded-{os.getpid()}-{tag}")
    pool = create_pool(threads=4)
    try:
        yield pool, server, client
    finally:
        try:
            pool.close()
        except Exception:  # noqa: BLE001 - teardown must not mask the verdict
            pass
        _kernel32.CloseHandle(client)
        _kernel32.CloseHandle(server)


@pytest.fixture
def plain_file(tmp_path):
    """A handle on a file deliberately opened WITHOUT overlapped I/O."""
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


def _drain(pool, workers: int, budget: int):
    """Draw events from several threads at once and return what came back."""
    seen = []
    lock = threading.Lock()

    def worker():
        for _ in range(budget):
            try:
                event = pool.take(timeout=2.0)
            except WCIOCPError:
                return
            with lock:
                seen.append(event)

    threads = [threading.Thread(target=worker, name=f"wciocp-taker-{i}") for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30.0)
    assert all(not thread.is_alive() for thread in threads), "a take() never returned"
    return seen


# ------------------------------------------------------- the key comes back


def test_completion_key_is_the_registered_one(pool_and_pipe):
    pool, server, client = pool_and_pipe
    pool.register(server, 0xA1)
    pool.submit(server, 64)
    assert _write(client, b"k") == 1
    event = pool.take(timeout=5.0)
    assert event.key == 0xA1, "the completion did not carry the registered key"


def test_keys_distinguish_handles_on_one_port(pool_and_pipe):
    pool, server, client = pool_and_pipe
    other_server, other_client = _make_pipe(
        rf"\\.\pipe\wciocp-graded-b-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        pool.register(server, 0x11)
        pool.register(other_server, 0x22)
        first = pool.submit(server, 64)
        second = pool.submit(other_server, 64)
        assert _write(client, b"a") == 1
        assert _write(other_client, b"bb") == 2

        by_handle = {}
        for _ in range(2):
            event = pool.take(timeout=5.0)
            by_handle[event.request.handle] = event.key
        assert by_handle.get(first.handle) == 0x11
        assert by_handle.get(second.handle) == 0x22
    finally:
        _kernel32.CloseHandle(other_client)
        _kernel32.CloseHandle(other_server)


def test_reregistered_key_does_not_rewrite_past_completions(pool_and_pipe):
    pool, server, client = pool_and_pipe
    pool.register(server, 1)
    pool.submit(server, 64, offset=0)
    assert _write(client, b"a") == 1
    time.sleep(0.4)  # let the first completion reach the port

    pool.register(server, 2)
    pool.submit(server, 64, offset=4096)
    assert _write(client, b"b") == 1

    keys = []
    for _ in range(2):
        keys.append(pool.take(timeout=5.0).key)
    assert keys[0] == 1, "a completion that had already arrived was relabelled by a later register()"
    assert keys[1] == 2


def test_register_binds_the_handle(pool_and_pipe):
    pool, server, _ = pool_and_pipe
    pool.register(server, 5)
    request = pool.submit(server, 32)
    assert request.handle == server


# ----------------------------------------------------- exactly-once delivery


def test_each_completion_is_delivered_once(pool_and_pipe):
    pool, server, client = pool_and_pipe
    pool.register(server, 7)
    offsets = [index * 1000 for index in range(6)]
    for offset in offsets:
        pool.submit(server, 64, offset=offset)
    for _ in offsets:
        assert _write(client, b"x") == 1

    events = _drain(pool, workers=4, budget=4)
    observed = sorted(int(event.request.offset) for event in events)
    assert observed == sorted(offsets), (
        "completions were duplicated or lost under concurrent take(): "
        f"expected {sorted(offsets)}, observed {observed}"
    )


def test_submit_leaves_the_request_pending(pool_and_pipe):
    pool, server, _ = pool_and_pipe
    pool.register(server, 9)
    pool.submit(server, 32)
    with pytest.raises(WCIOCPError) as excinfo:
        pool.take(timeout=0.4)
    assert excinfo.value.kind == "timeout"


def test_take_returns_an_event(pool_and_pipe):
    pool, server, client = pool_and_pipe
    pool.register(server, 3)
    pool.submit(server, 64)
    assert _write(client, b"hello") == 5
    event = pool.take(timeout=5.0)
    assert event.key == 3
    assert event.bytes_read == 5
    assert event.status == "completed"


# -------------------------------------------------------------- timeout/close


def test_timeout_does_not_drop_queued_completions(pool_and_pipe):
    pool, server, client = pool_and_pipe
    pool.register(server, 4)
    with pytest.raises(WCIOCPError) as excinfo:
        pool.take(timeout=0.3)
    assert excinfo.value.kind == "timeout"

    # A deadline that expired must not damage the pool: work submitted afterwards
    # has to be delivered normally.
    pool.submit(server, 64)
    assert _write(client, b"z") == 1
    event = pool.take(timeout=5.0)
    assert event.key == 4
    assert event.bytes_read == 1


def test_close_rejects_further_use(pool_and_pipe):
    pool, server, _ = pool_and_pipe
    pool.register(server, 6)
    pool.close()
    with pytest.raises(WCIOCPError) as taken:
        pool.take(timeout=0.2)
    assert taken.value.kind == "closed"
    with pytest.raises(WCIOCPError) as submitted:
        pool.submit(server, 16)
    assert submitted.value.kind == "closed"


def test_take_timeout_raises_timeout_kind(pool_and_pipe):
    pool, server, _ = pool_and_pipe
    pool.register(server, 8)
    with pytest.raises(WCIOCPError) as excinfo:
        pool.take(timeout=0.3)
    assert excinfo.value.kind == "timeout"


def test_close_is_idempotent(pool_and_pipe):
    pool, server, _ = pool_and_pipe
    pool.register(server, 10)
    pool.close()
    pool.close()


# ----------------------------------------------------------- capability/args


def test_non_overlapped_handle_is_unsupported(pool_and_pipe, plain_file):
    pool, _, _ = pool_and_pipe
    with pytest.raises(WCIOCPError) as excinfo:
        pool.register(plain_file, 11)
    assert excinfo.value.kind == "unsupported"


def test_invalid_arguments_are_rejected(pool_and_pipe):
    pool, _, _ = pool_and_pipe
    with pytest.raises(WCIOCPError) as excinfo:
        pool.register(-1, 12)
    assert excinfo.value.kind == "badarg"


def test_visible_smoke_suite_still_passes():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "test_wciocp_basic.py"),
        os.path.join(os.path.dirname(here), "tests", "test_wciocp_basic.py"),
    ]
    smoke = next((path for path in candidates if os.path.isfile(path)), None)
    assert smoke is not None, "the visible smoke suite was not staged next to this file"

    candidates_root = [
        os.environ.get("WCIOCP_WORKSPACE_ROOT"),
        os.path.dirname(here),
        os.path.dirname(os.path.dirname(here)),
        r"C:\testbed",
    ]
    workspace = next(
        (root for root in candidates_root
         if root and os.path.isfile(os.path.join(root, "wciocp", "__init__.py"))),
        None,
    )
    assert workspace is not None, "the candidate workspace was not staged for the smoke suite"
    env = dict(os.environ)
    env["PYTHONPATH"] = workspace + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", smoke],
        capture_output=True, text=True, env=env,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
