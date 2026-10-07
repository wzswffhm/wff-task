"""kernel32 命名管道最小绑定（ctypes，纯标准库）。

本模块只做「薄封装」：原样暴露 Win32 的返回值与 ``GetLastError`` 取值，
不做任何策略判断（重试、错误分类、分帧都留给上层）。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

__all__ = [
    "ERROR_ACCESS_DENIED",
    "ERROR_ALREADY_EXISTS",
    "ERROR_BROKEN_PIPE",
    "ERROR_INVALID_NAME",
    "ERROR_NO_DATA",
    "ERROR_PIPE_BUSY",
    "ERROR_PIPE_CONNECTED",
    "ERROR_SEM_TIMEOUT",
    "FILE_FLAG_FIRST_PIPE_INSTANCE",
    "GENERIC_READ",
    "GENERIC_WRITE",
    "INVALID_HANDLE_VALUE",
    "PIPE_ACCESS_DUPLEX",
    "PIPE_ACCESS_INBOUND",
    "PIPE_ACCESS_OUTBOUND",
    "PIPE_PREFIX",
    "PIPE_READMODE_MESSAGE",
    "PIPE_TYPE_BYTE",
    "PIPE_TYPE_MESSAGE",
    "PIPE_UNLIMITED_INSTANCES",
    "close",
    "connect",
    "create_pipe",
    "disconnect",
    "is_valid",
    "last_error",
    "open_pipe",
    "peek",
    "read",
    "wait_pipe",
    "write",
]

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------------------------------------------------------------- Win32 错误码
ERROR_ACCESS_DENIED = 5
ERROR_INVALID_NAME = 123
ERROR_BROKEN_PIPE = 109
ERROR_NO_DATA = 232
ERROR_PIPE_BUSY = 231
ERROR_SEM_TIMEOUT = 121
ERROR_PIPE_CONNECTED = 535
ERROR_ALREADY_EXISTS = 183

# ---------------------------------------------------------------- 管道常量
PIPE_ACCESS_INBOUND = 0x00000001
PIPE_ACCESS_OUTBOUND = 0x00000002
PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_WAIT = 0x00000000
PIPE_NOWAIT = 0x00000001
PIPE_UNLIMITED_INSTANCES = 255
FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
PIPE_PREFIX = "\\\\.\\pipe\\"

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# ---------------------------------------------------------------- 原型声明
_k32.CreateNamedPipeW.restype = wintypes.HANDLE
_k32.CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
]
_k32.ConnectNamedPipe.restype = wintypes.BOOL
_k32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
_k32.CreateFileW.restype = wintypes.HANDLE
_k32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
]
_k32.ReadFile.restype = wintypes.BOOL
_k32.ReadFile.argtypes = [
    wintypes.HANDLE, ctypes.c_char_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_k32.WriteFile.restype = wintypes.BOOL
_k32.WriteFile.argtypes = [
    wintypes.HANDLE, ctypes.c_char_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
_k32.PeekNamedPipe.restype = wintypes.BOOL
_k32.PeekNamedPipe.argtypes = [
    wintypes.HANDLE, ctypes.c_char_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
_k32.WaitNamedPipeW.restype = wintypes.BOOL
_k32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
_k32.DisconnectNamedPipe.restype = wintypes.BOOL
_k32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]


def last_error() -> int:
    """返回最近一次 Win32 调用设置的 ``GetLastError`` 值。"""
    return ctypes.get_last_error()


def is_valid(handle) -> bool:
    """判断句柄是否为有效值（``INVALID_HANDLE_VALUE`` / ``None`` / ``0`` 视为无效）。"""
    return handle not in (None, 0, INVALID_HANDLE_VALUE)


def create_pipe(name, instances=1, buffer_size=4096, message_mode=False,
                first_instance=False, wait=True):
    """创建命名管道的一个实例，返回句柄（失败时返回 ``INVALID_HANDLE_VALUE``）。

    ``last_error()`` 在失败时给出 Win32 错误码。注意：成功「复用」一个已存在
    的管道名时，``last_error()`` 可能仍为 ``ERROR_ALREADY_EXISTS``。
    """
    flags = PIPE_ACCESS_DUPLEX
    if first_instance:
        flags |= FILE_FLAG_FIRST_PIPE_INSTANCE
    ptype = PIPE_TYPE_MESSAGE if message_mode else PIPE_TYPE_BYTE
    if message_mode:
        ptype |= PIPE_READMODE_MESSAGE
    ptype |= (PIPE_WAIT if wait else PIPE_NOWAIT)
    ctypes.set_last_error(0)
    return _k32.CreateNamedPipeW(name, flags, ptype, int(instances),
                                 int(buffer_size), int(buffer_size), 0, None)


def connect(handle):
    """调用 ``ConnectNamedPipe``，**原样**返回其布尔结果。

    失败时的 ``last_error()`` 可能是 ``ERROR_PIPE_CONNECTED``，此时管道
    实际上已经连接成功。
    """
    ctypes.set_last_error(0)
    return bool(_k32.ConnectNamedPipe(ctypes.c_void_p(handle), None))


def open_pipe(name, access=GENERIC_READ | GENERIC_WRITE):
    """以客户端身份打开命名管道，返回句柄（失败时 ``INVALID_HANDLE_VALUE``）。"""
    ctypes.set_last_error(0)
    return _k32.CreateFileW(name, access, 0, None, OPEN_EXISTING, 0, None)


def wait_pipe(name, timeout_ms):
    """``WaitNamedPipeW``：等待某个实例变为可用。返回是否等到了可用实例。"""
    ctypes.set_last_error(0)
    return bool(_k32.WaitNamedPipeW(name, int(timeout_ms)))


def read(handle, size):
    """从管道读取至多 ``size`` 字节。

    成功返回 ``bytes``（可能为空）。失败时抛 ``OSError``，其 ``winerror``
    给出 Win32 错误码（例如管道被对端关闭是 ``ERROR_BROKEN_PIPE``）。
    """
    buf = ctypes.create_string_buffer(size)
    n = wintypes.DWORD(0)
    ok = _k32.ReadFile(ctypes.c_void_p(handle), buf, size, ctypes.byref(n), None)
    if not ok:
        raise OSError(0, "ReadFile failed", None, ctypes.get_last_error())
    return buf.raw[: n.value]


def write(handle, data):
    """向管道写入 ``data``（``bytes``），返回写入字节数。失败时抛 ``OSError``。"""
    if not data:
        return 0
    n = wintypes.DWORD(0)
    ok = _k32.WriteFile(ctypes.c_void_p(handle), data, len(data), ctypes.byref(n), None)
    if not ok:
        raise OSError(0, "WriteFile failed", None, ctypes.get_last_error())
    return n.value


def peek(handle):
    """``PeekNamedPipe``：返回管道中当前可读的字节数（不消费数据）。"""
    avail = wintypes.DWORD(0)
    ok = _k32.PeekNamedPipe(ctypes.c_void_p(handle), None, 0,
                            ctypes.byref(avail), None, None)
    if not ok:
        raise OSError(0, "PeekNamedPipe failed", None, ctypes.get_last_error())
    return avail.value


def disconnect(handle):
    """``DisconnectNamedPipe``：断开服务端实例与其当前客户端。"""
    ctypes.set_last_error(0)
    return bool(_k32.DisconnectNamedPipe(ctypes.c_void_p(handle)))


def close(handle):
    """关闭句柄（幂等）。"""
    if is_valid(handle):
        _k32.CloseHandle(ctypes.c_void_p(handle))
