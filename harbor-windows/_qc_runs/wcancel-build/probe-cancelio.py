"""CancelIoEx / CancelIo / GetOverlappedResult 语义探针（Windows 宿主机实测）。"""
import ctypes
import threading
import time
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

ERROR_IO_PENDING = 997
ERROR_IO_INCOMPLETE = 996
ERROR_OPERATION_ABORTED = 995
ERROR_NOT_FOUND = 1168

GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE, PIPE_READMODE_BYTE, PIPE_WAIT = 0, 0, 0


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_void_p), ("InternalHigh", ctypes.c_void_p),
                ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD),
                ("hEvent", wintypes.HANDLE)]


k32.CreateNamedPipeW.restype = wintypes.HANDLE
k32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)]
k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(OVERLAPPED)]
k32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED)]
k32.CancelIo.argtypes = [wintypes.HANDLE]
k32.GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.POINTER(OVERLAPPED),
                                    ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
k32.GetLastError.restype = wintypes.DWORD


def err() -> int:
    return ctypes.get_last_error()


def new_overlapped():
    ov = OVERLAPPED()
    ov.hEvent = k32.CreateEventW(None, True, False, None)
    return ov


def make_pipe(tag: str):
    name = rf"\\.\pipe\wcancel-probe-{tag}"
    srv = k32.CreateNamedPipeW(name, PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
                               PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                               1, 65536, 65536, 0, None)
    cli = k32.CreateFileW(name, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_EXISTING,
                          FILE_FLAG_OVERLAPPED, None)
    return srv, cli


def submit_read(handle):
    ov = new_overlapped()
    buf = ctypes.create_string_buffer(64)
    got = wintypes.DWORD(0)
    ok = k32.ReadFile(handle, buf, 64, ctypes.byref(got), ctypes.byref(ov))
    return ov, buf, got, ok, err()


def result(handle, ov):
    got = wintypes.DWORD(0)
    ok = k32.GetOverlappedResult(handle, ctypes.byref(ov), ctypes.byref(got), False)
    return bool(ok), err(), got.value


print("=== 1) 命名管道 + 重叠读是否必然挂起 ===")
srv, cli = make_pipe("a")
print("   server handle:", srv, " client handle:", cli)
ov1, buf1, got1, ok1, e1 = submit_read(srv)
print(f"   ReadFile -> ok={bool(ok1)} err={e1} (期望 False/997 = ERROR_IO_PENDING)")

print()
print("=== 2) 从【另一个线程】调 CancelIo（应为 ERROR_NOT_FOUND，取消不到）===")
out = {}
def other_thread_cancel_io():
    time.sleep(0.3)
    out["ok"] = bool(k32.CancelIo(srv))
    out["err"] = err()
t = threading.Thread(target=other_thread_cancel_io); t.start(); t.join()
print(f"   CancelIo -> ok={out['ok']} err={out['err']} (期望 False/1168 = ERROR_NOT_FOUND)")
print("   挂起请求是否仍在:", result(srv, ov1))

print()
print("=== 3) CancelIoEx 精确取消该请求 ===")
ok = bool(k32.CancelIoEx(srv, ctypes.byref(ov1)))
print(f"   CancelIoEx -> ok={ok} err={err()} (期望 True/0)")
print("   GetOverlappedResult 立即:", result(srv, ov1), "(期望 False/995 = ERROR_OPERATION_ABORTED)")

print()
print("=== 4) 同一句柄两个挂起读，只取消其中一个 ===")
srv2, cli2 = make_pipe("b")
ovA, bufA, gA, okA, eA = submit_read(srv2)
ovB, bufB, gB, okB, eB = submit_read(srv2)
print(f"   A ok={bool(okA)}/{eA}   B ok={bool(okB)}/{eB} (期望都是 False/997)")
okC = bool(k32.CancelIoEx(srv2, ctypes.byref(ovA)))
print(f"   只取消 A -> CancelIoEx ok={okC} err={err()}")
print("   A 结果:", result(srv2, ovA), "(期望 False/995)")
print("   B 结果:", result(srv2, ovB), "(期望 False/996 = ERROR_IO_INCOMPLETE，即未被取消)")
n = wintypes.DWORD(0)
data = ctypes.create_string_buffer(b"hello-cancel")
wok = k32.WriteFile(cli2, data, 12, ctypes.byref(n), None)
time.sleep(0.3)
print(f"   client 写入 {n.value} 字节后 B 结果:", result(srv2, ovB), "(期望 True/0，即未被取消的请求正常完成)")

print()
print("=== 5) 对【已完成】的请求再 CancelIoEx ===")
okD = bool(k32.CancelIoEx(srv2, ctypes.byref(ovB)))
print(f"   CancelIoEx(已完成) -> ok={okD} err={err()} (期望 False/1168 = ERROR_NOT_FOUND)")

print()
print("=== 6) CancelIo（同线程，作用于该句柄上全部挂起 I/O）===")
srv3, cli3 = make_pipe("c")
ovX, _, _, okX, eX = submit_read(srv3)
ovY, _, _, okY, eY = submit_read(srv3)
print(f"   X ok={bool(okX)}/{eX}  Y ok={bool(okY)}/{eY}")
okE = bool(k32.CancelIo(srv3))
print(f"   本线程 CancelIo -> ok={okE} err={err()} (期望 True/0)")
print("   X 结果:", result(srv3, ovX))
print("   Y 结果:", result(srv3, ovY), "(两者都会被取消 => CancelIo 无法做精确取消)")
