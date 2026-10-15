"""IOCP 语义探针 v2：完成键、多线程唯一消费、跨句柄完成包、超时、批量 API（最后单独试）。"""
import ctypes
import threading
import time
import uuid
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
PIPE_ACCESS_DUPLEX = 0x00000003
INVALID = ctypes.c_void_p(-1).value
WAIT_TIMEOUT = 258


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
                ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE)]


class OVERLAPPED_ENTRY(ctypes.Structure):
    _fields_ = [("lpCompletionKey", ctypes.c_void_p), ("lpOverlapped", ctypes.c_void_p),
                ("Internal", ctypes.c_void_p), ("dwNumberOfBytesTransferred", wintypes.DWORD)]


k32.CreateNamedPipeW.restype = wintypes.HANDLE
k32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
k32.CreateIoCompletionPort.restype = wintypes.HANDLE
k32.CreateIoCompletionPort.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
k32.GetQueuedCompletionStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD),
                                          ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
                                          wintypes.DWORD]
k32.GetQueuedCompletionStatus.restype = wintypes.BOOL
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)]
k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k32.CloseHandle.argtypes = [wintypes.HANDLE]


def make_pipe(tag):
    name = rf"\\.\pipe\wciocp-probe-{tag}"
    srv = k32.CreateNamedPipeW(name, PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED, 0, 1, 65536, 65536, 0, None)
    cli = k32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING,
                          FILE_FLAG_OVERLAPPED, None)
    assert srv not in (None, INVALID) and cli not in (None, INVALID), "pipe creation failed"
    return srv, cli


def submit(handle, size=64):
    ov = OVERLAPPED()
    buf = ctypes.create_string_buffer(size)
    got = wintypes.DWORD(0)
    ok = k32.ReadFile(handle, buf, size, ctypes.byref(got), ctypes.byref(ov))
    return ov, buf


def write(handle, payload):
    n = wintypes.DWORD(0)
    ok = k32.WriteFile(handle, payload, len(payload), ctypes.byref(n), None)
    return ok, n.value


def take(port, timeout_ms):
    got = wintypes.DWORD(0)
    key = ctypes.c_void_p(0)
    ovp = ctypes.c_void_p(0)
    ok = k32.GetQueuedCompletionStatus(wintypes.HANDLE(port), ctypes.byref(got), ctypes.byref(key),
                                       ctypes.byref(ovp), timeout_ms)
    return bool(ok), key.value, ovp.value, got.value, ctypes.get_last_error()


port = k32.CreateIoCompletionPort(wintypes.HANDLE(INVALID), None, None, 0)
srv, cli = make_pipe(uuid.uuid4().hex[:8])
bound = k32.CreateIoCompletionPort(wintypes.HANDLE(srv), wintypes.HANDLE(port), ctypes.c_void_p(0xAA), 0)
print(f"port={port} bound={bound} err={ctypes.get_last_error()}")

reqs = [submit(srv) for _ in range(3)]
print("submitted 3 pending reads:", all(True for _ in reqs))

collected = []
lock = threading.Lock()


def waiter(tag):
    ok, key, ovp, n, err = take(port, 3000)
    if ok:
        with lock:
            collected.append((tag, key, ovp, n))


threads = [threading.Thread(target=waiter, args=(f"t{i}",)) for i in range(3)]
for t in threads:
    t.start()
time.sleep(0.3)
for i in range(3):
    write(cli, bytes([65 + i]) * (i + 1))
for t in threads:
    t.join(5)
req_ptrs = {ctypes.addressof(ov) for ov, _ in reqs}
print(f"[3-thread] packets={len(collected)} keys={ {hex(c[1]) for c in collected} } "
      f"unique_ov={len({c[2] for c in collected})} all_ours={ {c[2] for c in collected} <= req_ptrs }")

print("--- 跨句柄：同一端口绑定第二个句柄，完成键区分 ---")
srv2, cli2 = make_pipe(uuid.uuid4().hex[:8])
k32.CreateIoCompletionPort(wintypes.HANDLE(srv2), wintypes.HANDLE(port), ctypes.c_void_p(0xBB), 0)
reqs2 = [submit(srv2) for _ in range(3)]
time.sleep(0.2)
for i in range(3):
    write(cli2, b"y" * (i + 1))
time.sleep(0.3)
got2 = [take(port, 2000) for _ in range(3)]
print(f"[cross-handle] keys={ [hex(g[1]) for g in got2] } bytes={ [g[3] for g in got2] } "
      f"count={sum(1 for g in got2 if g[0])}/3")

print("--- 超时语义 ---")
t0 = time.time()
ok, key, ovp, n, err = take(port, 300)
print(f"[timeout] ok={ok} err={err} (258=WAIT_TIMEOUT) elapsed={time.time()-t0:.2f}s")

k32.CloseHandle(wintypes.HANDLE(cli)); k32.CloseHandle(wintypes.HANDLE(srv))
k32.CloseHandle(wintypes.HANDLE(cli2)); k32.CloseHandle(wintypes.HANDLE(srv2))
k32.CloseHandle(wintypes.HANDLE(port))
print("probe finished OK (without the batch API)")
