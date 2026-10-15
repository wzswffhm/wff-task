"""本地差分校准：对指定实现跑 wcancel 契约的核心判据（真机 Windows 实测）。

用法：python local-differential.py --impl <包含 wcancel 包的目录>
"""
import argparse
import ctypes
import os
import sys
import threading
import time
import uuid
from ctypes import wintypes

parser = argparse.ArgumentParser()
parser.add_argument("--impl", required=True)
args = parser.parse_args()

sys.path.insert(0, args.impl)
import wcancel  # noqa: E402

print(f"impl        : {args.impl}")
print(f"public api  : {sorted(n for n in dir(wcancel) if not n.startswith('_'))}")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
PIPE_ACCESS_DUPLEX = 0x00000003
INVALID = ctypes.c_void_p(-1).value

k32.CreateNamedPipeW.restype = wintypes.HANDLE
k32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
k32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k32.CloseHandle.argtypes = [wintypes.HANDLE]


def make_pipe():
    name = rf"\\.\pipe\wcancel-diff-{os.getpid()}-{uuid.uuid4().hex}"
    srv = k32.CreateNamedPipeW(name, PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED, 0, 1,
                               65536, 65536, 0, None)
    cli = k32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING,
                          FILE_FLAG_OVERLAPPED, None)
    assert srv not in (None, INVALID) and cli not in (None, INVALID), "pipe creation failed"
    return srv, cli


def write(handle, payload):
    n = wintypes.DWORD(0)
    assert k32.WriteFile(handle, payload, len(payload), ctypes.byref(n), None)
    return n.value


results = []


def check(name, fn):
    try:
        verdict, detail = fn()
    except Exception as exc:  # noqa: BLE001
        verdict, detail = False, f"{type(exc).__name__}: {exc}"
    results.append((name, verdict, detail))
    print(f"  [{'PASS' if verdict else 'FAIL'}] {name} :: {detail}")


print("\n--- 判据 ---")


def precise():
    srv, _ = make_pipe()
    a = wcancel.submit(srv, 64)
    b = wcancel.submit(srv, 64)
    first = wcancel.cancel(a)
    done_a = wcancel.wait(a, timeout=5.0)
    try:
        wcancel.wait(b, timeout=0.4)
        neighbour = "completed/cancelled too early"
    except wcancel.WCancelError as exc:
        neighbour = "still pending" if exc.kind == "timeout" else f"raised kind={exc.kind}"
    ok = first is True and done_a.status == "cancelled" and neighbour == "still pending"
    return ok, f"cancel(a)={first} a.status={done_a.status} neighbour={neighbour}"


def cross_thread():
    srv, _ = make_pipe()
    r = wcancel.submit(srv, 64)
    out = {}

    def worker():
        time.sleep(0.25)
        try:
            out["cancelled"] = wcancel.cancel(r)
        except BaseException as exc:  # noqa: BLE001
            out["error"] = exc

    t = threading.Thread(target=worker)
    t.start()
    t.join(15)
    try:
        status = wcancel.wait(r, timeout=5.0).status
    except wcancel.WCancelError as exc:
        status = f"raised kind={exc.kind}"
    ok = out.get("cancelled") is True and status == "cancelled"
    return ok, f"cancel()={out.get('cancelled')} terminal={status}"


def completed_not_cancellable():
    srv, cli = make_pipe()
    r = wcancel.submit(srv, 64)
    write(cli, b"abcdefgh")
    done = wcancel.wait(r, timeout=5.0)
    again = wcancel.cancel(r)
    ok = done.status == "completed" and done.bytes_read == 8 and again is False
    return ok, f"status={done.status} bytes={done.bytes_read} cancel_after_completion={again}"


def second_cancel():
    srv, _ = make_pipe()
    r = wcancel.submit(srv, 32)
    first = wcancel.cancel(r)
    wcancel.wait(r, timeout=5.0)
    second = wcancel.cancel(r)
    ok = first is True and second is False
    return ok, f"first={first} second={second}"


def unsupported():
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as fh:
        fh.write(b"x" * 256)
        path = fh.name
    h = k32.CreateFileW(path, GENERIC_READ, 0x7, None, OPEN_EXISTING, 0, None)
    try:
        wcancel.submit(h, 16)
        return False, "submit() accepted a non-overlapped handle"
    except wcancel.WCancelError as exc:
        return exc.kind == "unsupported", f"kind={exc.kind}"
    finally:
        k32.CloseHandle(h)
        os.unlink(path)


def uncancelled_bytes():
    srv, cli = make_pipe()
    a = wcancel.submit(srv, 64)
    b = wcancel.submit(srv, 64)
    wcancel.cancel(a)
    wcancel.wait(a, timeout=5.0)
    payload = b"wcancel-payload"
    write(cli, payload)
    try:
        done = wcancel.wait(b, timeout=5.0)
        ok = done.status == "completed" and done.bytes_read == len(payload)
        return ok, f"status={done.status} bytes={done.bytes_read}"
    except wcancel.WCancelError as exc:
        return False, f"neighbour raised kind={exc.kind}"


def cancel_all():
    srv, _ = make_pipe()
    a = wcancel.submit(srv, 32)
    b = wcancel.submit(srv, 32)
    stopped = wcancel.cancel_all(srv)
    states = []
    for request in (a, b):
        try:
            states.append(wcancel.wait(request, timeout=5.0).status)
        except wcancel.WCancelError as exc:
            states.append(f"raised:{exc.kind}")
    ok = stopped == 2 and all(state != "raised:timeout" for state in states)
    return ok, f"stopped={stopped} terminal={states}"


def badarg():
    try:
        wcancel.submit(-1, 16)
        return False, "submit(-1) was accepted"
    except wcancel.WCancelError as exc:
        return exc.kind == "badarg", f"kind={exc.kind}"


check("cancel-affects-only-the-target-request", precise)
check("cancel-works-from-another-thread", cross_thread)
check("completed-request-cannot-be-cancelled", completed_not_cancellable)
check("second-cancel-reports-false", second_cancel)
check("non-overlapped-handle-is-unsupported", unsupported)
check("uncancelled-request-still-delivers-the-bytes", uncancelled_bytes)
check("cancel-all-cancels-every-submitted-request", cancel_all)
check("invalid-handle-is-rejected", badarg)

passed = sum(1 for _, ok, _ in results if ok)
print(f"\n合计：{passed}/{len(results)} PASS")
sys.exit(0 if passed == len(results) else 1)
