# -*- coding: utf-8 -*-
"""Windows 字节范围锁机制探针。

目的：确认 msvcrt.locking 与 LockFileEx 的语义差异
  1) LockFileEx 不带 LOCKFILE_EXCLUSIVE_LOCK 时是共享锁，多个句柄可同时持有
  2) msvcrt.locking(LK_NBLCK) 是排他锁，与共享锁互斥
  3) 排他锁与任何其他锁互斥
这决定「共享锁在 Windows 上无法用 msvcrt 实现」这一真实缺陷是否可评测。
"""
import ctypes
import msvcrt
import os
import sys
import tempfile
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
LOCKFILE_FAIL_IMMEDIATELY = 0x00000001
LOCKFILE_EXCLUSIVE_LOCK = 0x00000002
ERROR_LOCK_VIOLATION = 33


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_void_p),
        ("InternalHigh", ctypes.c_void_p),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
k32.LockFileEx.restype = wintypes.BOOL
k32.LockFileEx.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(OVERLAPPED),
]
k32.UnlockFileEx.restype = wintypes.BOOL
k32.UnlockFileEx.argtypes = [
    wintypes.HANDLE, wintypes.DWORD,
    wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(OVERLAPPED),
]
k32.CloseHandle.argtypes = [wintypes.HANDLE]


def open_file(path):
    h = k32.CreateFileW(path, GENERIC_READ | GENERIC_WRITE, 0x7, None,
                        OPEN_EXISTING, 0, None)
    if h == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return h


def lock_ex(h, flags, nbytes=10):
    ov = OVERLAPPED()
    ok = k32.LockFileEx(h, flags, 0, nbytes, 0, ctypes.byref(ov))
    return bool(ok), ctypes.get_last_error()


def unlock(h, nbytes=10):
    ov = OVERLAPPED()
    return bool(k32.UnlockFileEx(h, 0, nbytes, 0, ctypes.byref(ov)))


def msvcrt_lock(fd, mode, nbytes=10):
    os.lseek(fd, 0, os.SEEK_SET)
    try:
        msvcrt.locking(fd, mode, nbytes)
        return True, 0
    except OSError as e:
        return False, e.errno


def main():
    d = tempfile.mkdtemp(prefix="probelock")
    p = os.path.join(d, "lock.bin")
    with open(p, "wb") as f:
        f.write(b"0123456789" * 4)

    print("=== 1. 两个 LockFileEx 共享锁（flags=FAIL_IMMEDIATELY）===")
    h1 = open_file(p)
    h2 = open_file(p)
    ok1, e1 = lock_ex(h1, LOCKFILE_FAIL_IMMEDIATELY)
    ok2, e2 = lock_ex(h2, LOCKFILE_FAIL_IMMEDIATELY)
    print("  句柄1 共享锁: ok=%s err=%s" % (ok1, e1))
    print("  句柄2 共享锁: ok=%s err=%s" % (ok2, e2))
    print("  => 共享锁可并发持有: %s" % (ok1 and ok2))

    print("=== 2. 共享锁已持有时，排他锁必须失败 ===")
    h3 = open_file(p)
    ok3, e3 = lock_ex(h3, LOCKFILE_FAIL_IMMEDIATELY | LOCKFILE_EXCLUSIVE_LOCK)
    print("  句柄3 排他锁: ok=%s err=%s (期望 33=ERROR_LOCK_VIOLATION)" % (ok3, e3))

    print("=== 3. 共享锁已持有时，msvcrt.locking(LK_NBLCK) 行为 ===")
    fd = os.open(p, os.O_RDWR)
    okm, em = msvcrt_lock(fd, msvcrt.LK_NBLCK)
    print("  msvcrt 排他: ok=%s errno=%s" % (okm, em))
    if okm:
        msvcrt_lock(fd, msvcrt.LK_UNLCK)
    os.close(fd)

    unlock(h1)
    unlock(h2)

    print("=== 4. 对照：先由 msvcrt 持有排他锁，再看 LockFileEx 共享锁 ===")
    fd2 = os.open(p, os.O_RDWR)
    okm2, em2 = msvcrt_lock(fd2, msvcrt.LK_NBLCK)
    print("  msvcrt 排他: ok=%s errno=%s" % (okm2, em2))
    h4 = open_file(p)
    ok4, e4 = lock_ex(h4, LOCKFILE_FAIL_IMMEDIATELY)
    print("  LockFileEx 共享: ok=%s err=%s (期望 False/33)" % (ok4, e4))
    ok5, e5 = lock_ex(h4, LOCKFILE_FAIL_IMMEDIATELY | LOCKFILE_EXCLUSIVE_LOCK)
    print("  LockFileEx 排他: ok=%s err=%s (期望 False/33)" % (ok5, e5))
    if okm2:
        msvcrt_lock(fd2, msvcrt.LK_UNLCK)
    os.close(fd2)

    print("=== 5. 同一进程内 LockFileEx 同句柄重复取锁（共享->排他升级）===")
    ok6, e6 = lock_ex(h1, LOCKFILE_FAIL_IMMEDIATELY | LOCKFILE_EXCLUSIVE_LOCK)
    print("  同句柄升级为排他: ok=%s err=%s" % (ok6, e6))

    for h in (h1, h2, h3, h4):
        k32.CloseHandle(h)
    print("PROBE_DONE")


if __name__ == "__main__":
    main()
