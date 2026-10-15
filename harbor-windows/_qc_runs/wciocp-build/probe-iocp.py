"""IOCP 语义探针（Windows 真机实测）：完成键回传、多线程唯一消费、批量取出、超时。"""
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
k32.GetQueuedCompletionStatusEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED_ENTRY), wintypes.ULONG,
                                            ctypes.POINTER(wintypes.ULONG), wintypes.DWORD, wintypes.BOOL]
k32.GetQueuedCompletionStatusEx.restype = wintypes.BOOL
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)]
k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k32.CloseHandle.argtypes = [wintypes.HANDLE]


def make_pipe(tag):
    name = rf"\\.\pipe\wciocp-probe-{tag}"
    srv = k32.CreateNamedPipeW(name, PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED, 0, 1,
                               65536, 65536, 0, None)
    cli = k32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING,
                          FILE_FLAG_OVERLAPPED, None)
    assert srv not in (None, INVALID) and cli not in (None, INVALID), "pipe creation failed"
    return srv, cli


def submit(handle, size=64):
    ov = OVERLAPPED()
    buf = ctypes.create_string_buffer(size)
    got = wintypes.DWORD(0)
    ok = k32.ReadFile(handle, buf, size, ctypes.byref(got), ctypes.byref(ov))
    return ov, buf, ok, ctypes.get_last_error()


def write(handle, payload):
    n = wintypes.DWORD(0)
    ok = k32.WriteFile(handle, payload, len(payload), ctypes.byref(n), None)
    return ok, n.value


print("=== 1) 新建完成端口并绑定句柄（完成键 0xAA）===")
port = k32.CreateIoCompletionPort(wintypes.HANDLE(INVALID), None, None, 0)
print("   port =", port, "err =", ctypes.get_last_error())
srv, cli = make_pipe(uuid.uuid4().hex[:8])
bound = k32.CreateIoCompletionPort(wintypes.HANDLE(srv), wintypes.HANDLE(port), ctypes.c_void_p(0xAA), 0)
print("   绑定结果 =", bound, "err =", ctypes.get_last_error())

print()
print("=== 2) 提交 3 个挂起读（应全部 ERROR_IO_PENDING）===")
reqs = []
for i in range(3):
    ov, buf, ok, err = submit(srv)
    reqs.append((ov, buf))
    print(f"   req{i}: ok={bool(ok)} err={err} ov_ptr={ctypes.addressof(ov)}")

print()
print("=== 3) 三个线程并发等待，每个完成包只能被一个线程取到 ===")
collected = []
lock = threading.Lock()


def waiter(tag):
    for _ in range(3):
        got = wintypes.DWORD(0)
        key = ctypes.c_void_p(0)
        ovp = ctypes.c_void_p(0)
        ok = k32.GetQueuedCompletionStatus(wintypes.HANDLE(port), ctypes.byref(got),
                                           ctypes.byref(key), ctypes.byref(ovp), 3000)
        if ok:
            with lock:
                collected.append((tag, key.value, ovp.value, got.value))
            return
        return


threads = [threading.Thread(target=waiter, args=(f"t{i}",)) for i in range(3)]
for t in threads:
    t.start()
time.sleep(0.3)
for i in range(3):
    ok, n = write(cli, bytes([65 + i]) * (i + 1))
    print(f"   client 写入 {n} 字节 ok={ok}")
for t in threads:
    t.join(5)

print(f"   共收到 {len(collected)} 个完成包：")
for tag, key, ovp, nbytes in collected:
    print(f"     {tag}: key=0x{key:X} ov=0x{ovp:X} bytes={nbytes}")
keys = {c[1] for c in collected}
ovs = {c[2] for c in collected}
req_ptrs = {ctypes.addressof(ov) for ov, _ in reqs}
print(f"   完成键集合 = {[hex(k) for k in keys]} （期望 {{0xAA}}）")
print(f"   完成包数 = {len(collected)}（期望 3）；唯一 OVERLAPPED 数 = {len(ovs)}（期望 3，无重复消费）")
print(f"   回传的 OVERLAPPED 是否都来自本进程提交的请求: {ovs <= req_ptrs}")

print()
print("=== 4) 批量取出（GetQueuedCompletionStatusEx）===")
srv2, cli2 = make_pipe(uuid.uuid4().hex[:8])
k32.CreateIoCompletionPort(wintypes.HANDLE(srv2), wintypes.HANDLE(port), ctypes.c_void_p(0xBB), 0)
for i in range(4):
    submit(srv2)
time.sleep(0.2)
for i in range(4):
    write(cli2, b"x" * (i + 1))
time.sleep(0.3)
entries = (OVERLAPPED_ENTRY * 8)()
removed = wintypes.ULONG(0)
ok = k32.GetQueuedCompletionStatusEx(wintypes.HANDLE(port), entries, 8, ctypes.byref(removed), 2000, False)
print(f"   批量取出 ok={bool(ok)} err={ctypes.get_last_error()} 取出数量={removed.value}")
for i in range(min(removed.value, 8)):
    e = entries[i]
    print(f"     entry{i}: key=0x{(e.lpCompletionKey or 0):X} ov=0x{(e.lpOverlapped or 0):X} bytes={e.dwNumberOfBytesTransferred}")

print()
print("=== 5) 超时语义 ===")
t0 = time.time()
got = wintypes.DWORD(0)
key = ctypes.c_void_p(0)
ovp = ctypes.c_void_p(0)
ok = k32.GetQueuedCompletionStatus(wintypes.HANDLE(port), ctypes.byref(got), ctypes.byref(key),
                                   ctypes.byref(ovp), 300)
dt = time.time() - t0
print(f"   空端口等待 300ms：ok={bool(ok)} err={ctypes.get_last_error()}（{WAIT_TIMEOUT}=WAIT_TIMEOUT）耗时={dt:.2f}s")

k32.CloseHandle(wintypes.HANDLE(cli)); k32.CloseHandle(wintypes.HANDLE(srv))
k32.CloseHandle(wintypes.HANDLE(cli2)); k32.CloseHandle(wintypes.HANDLE(srv2))
k32.CloseHandle(wintypes.HANDLE(port))
