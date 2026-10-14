"""Probe: which observable state does FSCTL_SET_SPARSE actually change?

Runs inside the Windows Server Core container on the NTFS system volume.
Pure ASCII. Prints a single line for each measurement.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_ALL = 0x00000007
CREATE_ALWAYS = 2
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_SPARSE_FILE = 0x00000200
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_BEGIN = 0
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

FSCTL_SET_SPARSE = 0x000900C4
FSCTL_QUERY_ALLOCATED_RANGES = 0x000940CF

MB = 1024 * 1024

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                         wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
k.CreateFileW.restype = wintypes.HANDLE
k.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                              wintypes.LPVOID, wintypes.DWORD,
                              ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k.DeviceIoControl.restype = wintypes.BOOL
k.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                               ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
k.SetFilePointerEx.restype = wintypes.BOOL
k.SetEndOfFile.argtypes = [wintypes.HANDLE]
k.SetEndOfFile.restype = wintypes.BOOL
k.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k.WriteFile.restype = wintypes.BOOL
k.FlushFileBuffers.argtypes = [wintypes.HANDLE]
k.FlushFileBuffers.restype = wintypes.BOOL
k.CloseHandle.argtypes = [wintypes.HANDLE]
k.CloseHandle.restype = wintypes.BOOL
k.GetCompressedFileSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
k.GetCompressedFileSizeW.restype = wintypes.DWORD


class FILE_STANDARD_INFO(ctypes.Structure):
    _fields_ = [("AllocationSize", ctypes.c_longlong),
                ("EndOfFile", ctypes.c_longlong),
                ("NumberOfLinks", wintypes.DWORD),
                ("DeletePending", ctypes.c_ubyte),
                ("Directory", ctypes.c_ubyte)]


class RANGE(ctypes.Structure):
    _fields_ = [("FileOffset", ctypes.c_longlong), ("Length", ctypes.c_longlong)]


WORK = "C:\\wsparseprobe"


def err():
    return ctypes.get_last_error()


def openf(path, sparse, flags=FILE_ATTRIBUTE_NORMAL, access=GENERIC_READ | GENERIC_WRITE,
          create=False):
    disposition = CREATE_ALWAYS if create else OPEN_EXISTING
    h = k.CreateFileW(str(path), access, FILE_SHARE_ALL, None,
                      disposition, flags, None)
    if h == INVALID_HANDLE_VALUE:
        print("  CreateFileW failed err=%d for %s" % (err(), path))
        return None
    return h


def set_sparse(h):
    buf = ctypes.c_byte(1)
    got = wintypes.DWORD(0)
    ok = k.DeviceIoControl(h, FSCTL_SET_SPARSE, ctypes.byref(buf), 1, None, 0,
                           ctypes.byref(got), None)
    return bool(ok), err()


def set_length(h, size):
    pos = ctypes.c_longlong(0)
    ok1 = k.SetFilePointerEx(h, ctypes.c_longlong(size), ctypes.byref(pos), FILE_BEGIN)
    ok2 = k.SetEndOfFile(h)
    return bool(ok1 and ok2), err()


def poke(h, offset, blob):
    pos = ctypes.c_longlong(0)
    k.SetFilePointerEx(h, ctypes.c_longlong(offset), ctypes.byref(pos), FILE_BEGIN)
    written = wintypes.DWORD(0)
    ok = k.WriteFile(h, blob, len(blob), ctypes.byref(written), None)
    return bool(ok) and written.value == len(blob)


def alloc_size(h):
    info = FILE_STANDARD_INFO()
    ok = k.GetFileInformationByHandleEx(h, 1, ctypes.byref(info), ctypes.sizeof(info))
    if not ok:
        return None
    return info.AllocationSize


def compressed(path):
    high = wintypes.DWORD(0)
    low = k.GetCompressedFileSizeW(str(path), ctypes.byref(high))
    return (high.value << 32) | low


def attrs(path):
    return os.stat(path).st_file_attributes


def ranges(h, offset, length):
    inbuf = RANGE(offset, length)
    outbuf = (RANGE * 64)()
    got = wintypes.DWORD(0)
    ok = k.DeviceIoControl(h, FSCTL_QUERY_ALLOCATED_RANGES, ctypes.byref(inbuf),
                           ctypes.sizeof(inbuf), ctypes.byref(outbuf),
                           ctypes.sizeof(outbuf), ctypes.byref(got), None)
    if not ok:
        return None, err(), got.value
    n = got.value // ctypes.sizeof(RANGE)
    return [(outbuf[i].FileOffset, outbuf[i].Length) for i in range(n)], 0, got.value


def fsutil(args):
    p = subprocess.run(["fsutil"] + args, capture_output=True, text=True)
    return (p.stdout or "") + (p.stderr or "")


def report(label, path):
    try:
        a = attrs(path)
    except OSError as exc:
        print("  %s attrs=<%s>" % (label, exc))
        return
    print("  %s attrs=0x%x sparse_bit=%s st_size=%d compressed=%d" % (
        label, a, bool(a & FILE_ATTRIBUTE_SPARSE_FILE), os.path.getsize(path),
        compressed(path)))
    print("  %s fsutil-queryflag: %s" % (label, fsutil(["sparse", "queryflag", path]).strip().replace("\n", " | ")))


def main():
    os.makedirs(WORK, exist_ok=True)
    print("=== A: sparse flag first, then extend, then write")
    pa = os.path.join(WORK, "a.bin")
    h = openf(pa, True, access=GENERIC_READ | GENERIC_WRITE, create=True)
    if h is None:
        return 1
    if os.path.exists(pa):
        pass
    print("  setsparse ok=%s err=%d" % set_sparse(h))
    print("  setlength(64MB) ok=%s err=%d" % set_length(h, 64 * MB))
    print("  allocation before write =", alloc_size(h), "compressed =", compressed(pa))
    poke(h, 0, b"A" * 4096)
    poke(h, 32 * MB, b"B" * 8192)
    k.FlushFileBuffers(h)
    print("  allocation after flush =", alloc_size(h), "compressed =", compressed(pa))
    print("  ranges =", ranges(h, 0, 64 * MB)[0])
    k.CloseHandle(h)
    report("A-reopened", pa)
    print("  fsutil queryAllocRanges: %s" % fsutil(
        ["file", "queryAllocRanges", "offset=0", "length=%d" % (64 * MB), pa]).strip().replace("\n", " | "))

    print("=== B: dense file, then set the sparse flag afterwards")
    pb = os.path.join(WORK, "b.bin")
    h = openf(pb, False, access=GENERIC_READ | GENERIC_WRITE, create=True)
    if h is None:
        return 1
    print("  setlength(64MB) ok=%s err=%d" % set_length(h, 64 * MB))
    print("  allocation before setsparse =", alloc_size(h))
    print("  late setsparse ok=%s err=%d" % set_sparse(h))
    k.FlushFileBuffers(h)
    print("  allocation after setsparse =", alloc_size(h), "compressed =", compressed(pb))
    k.CloseHandle(h)
    report("B-reopened", pb)

    print("=== C: small sparse file - does the sparse bit survive a close?")
    pc = os.path.join(WORK, "c.bin")
    h = openf(pc, False, access=GENERIC_READ | GENERIC_WRITE, create=True)
    if h is None:
        return 1
    print("  setsparse ok=%s err=%d" % set_sparse(h))
    print("  allocation right after setsparse (same handle) =", alloc_size(h))
    k.CloseHandle(h)
    report("C-reopened", pc)

    print("=== D: illegal object - directory handle")
    h = openf(WORK, True, flags=FILE_FLAG_BACKUP_SEMANTICS, access=GENERIC_READ)
    if h is not None:
        ok, e = set_sparse(h)
        print("  setsparse(dir) ok=%s err=%d" % (ok, e))
        print("  ranges(dir) =", ranges(h, 0, 4096)[:2])
        k.CloseHandle(h)
    print("  os.stat(dir).st_size =", os.stat(WORK).st_size)
    print("  os.path.getsize(dir) =", os.path.getsize(WORK))
    print("  dir attrs sparse_bit =", bool(attrs(WORK) & FILE_ATTRIBUTE_SPARSE_FILE))

    print("=== E: volume capability")
    print("  fsinfo volumeinfo: %s" % fsutil(["fsinfo", "volumeinfo", "C:"]).strip().replace("\n", " | "))
    print("  fsinfo drivetype: %s" % fsutil(["fsinfo", "drivetype", "C:"]).strip())
    print("=== F: python-level os.truncate on a fresh file")
    pf = os.path.join(WORK, "f.bin")
    if os.path.exists(pf):
        os.remove(pf)
    with open(pf, "wb") as fh:
        pass
    os.truncate(pf, 64 * MB)
    print("  os.truncate(64MB): st_size=%d compressed=%d sparse_bit=%s" % (
        os.path.getsize(pf), compressed(pf),
        bool(attrs(pf) & FILE_ATTRIBUTE_SPARSE_FILE)))
    print("  fsutil queryflag: %s" % fsutil(["sparse", "queryflag", pf]).strip())
    print("PROBE_WSPARSE_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
