"""Probe: what identity information can Windows give about a file?

Runs inside the Windows Server Core container on the NTFS system volume.
Pure ASCII. Prints one line per measurement.
"""

import ctypes
import os
import subprocess
import sys
from ctypes import wintypes

GENERIC_READ = 0x80000000
FILE_SHARE_ALL = 0x00000007
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

FileIdInfo = 18
FileStandardInfo = 1

WORK = "C:\\widprobe"
MB = 1024 * 1024

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                         wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
k.CreateFileW.restype = wintypes.HANDLE
k.CloseHandle.argtypes = [wintypes.HANDLE]
k.CloseHandle.restype = wintypes.BOOL
k.GetFileInformationByHandleEx.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                           wintypes.LPVOID, wintypes.DWORD]
k.GetFileInformationByHandleEx.restype = wintypes.BOOL
k.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
k.GetFileInformationByHandle.restype = wintypes.BOOL
k.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR,
                                        wintypes.DWORD, wintypes.DWORD]
k.GetFinalPathNameByHandleW.restype = wintypes.DWORD
k.CreateHardLinkW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID]
k.CreateHardLinkW.restype = wintypes.BOOL


class FILE_ID_128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_ubyte * 16)]


class FILE_ID_INFO(ctypes.Structure):
    _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong),
                ("FileId", FILE_ID_128)]


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [("dwFileAttributes", wintypes.DWORD),
                ("ftCreationTime", wintypes.FILETIME),
                ("ftLastAccessTime", wintypes.FILETIME),
                ("ftLastWriteTime", wintypes.FILETIME),
                ("dwVolumeSerialNumber", wintypes.DWORD),
                ("nFileSizeHigh", wintypes.DWORD),
                ("nFileSizeLow", wintypes.DWORD),
                ("nNumberOfLinks", wintypes.DWORD),
                ("nFileIndexHigh", wintypes.DWORD),
                ("nFileIndexLow", wintypes.DWORD)]


class FILE_ID_DESCRIPTOR(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD),
                ("Type", ctypes.c_int),
                ("FileId", FILE_ID_128)]


def err():
    return ctypes.get_last_error()


def openf(path, access=GENERIC_READ, flags=FILE_ATTRIBUTE_NORMAL):
    h = k.CreateFileW(str(path), access, FILE_SHARE_ALL, None, OPEN_EXISTING, flags, None)
    if h == INVALID_HANDLE_VALUE:
        return None
    return h


def file_id_info(h):
    info = FILE_ID_INFO()
    ok = k.GetFileInformationByHandleEx(h, FileIdInfo, ctypes.byref(info), ctypes.sizeof(info))
    if not ok:
        return None
    raw = bytes(bytearray(info.FileId.Identifier))
    return info.VolumeSerialNumber, raw


def by_handle(h):
    info = BY_HANDLE_FILE_INFORMATION()
    if not k.GetFileInformationByHandle(h, ctypes.byref(info)):
        return None
    index = (info.nFileIndexHigh << 32) | info.nFileIndexLow
    return info.dwVolumeSerialNumber, index, info.nNumberOfLinks


def final_path(h):
    buf = ctypes.create_unicode_buffer(512)
    n = k.GetFinalPathNameByHandleW(h, buf, 512, 0)
    return buf.value if n else None


def fsutil(args):
    p = subprocess.run(["fsutil"] + args, capture_output=True, text=True)
    return ((p.stdout or "") + (p.stderr or "")).strip().replace("\n", " | ")


def describe(label, path, flags=FILE_ATTRIBUTE_NORMAL):
    print("--- %s : %s" % (label, path))
    try:
        st = os.stat(path)
        print("   os.stat: st_ino=%d st_dev=%d st_nlink=%d size=%d mode=%o" % (
            st.st_ino, st.st_dev, st.st_nlink, st.st_size, st.st_mode))
    except OSError as exc:
        print("   os.stat failed: %s" % exc)
    h = openf(path, flags=flags)
    if h is None:
        print("   CreateFileW failed err=%d" % err())
        return None, None, None
    fid = file_id_info(h)
    bh = by_handle(h)
    fp = final_path(h)
    print("   FileIdInfo: vol=0x%x id=%s" % (fid[0], fid[1].hex()) if fid else "   FileIdInfo: unsupported")
    print("   ByHandle  : vol=0x%x index=%d links=%d" % bh if bh else "   ByHandle: failed")
    print("   final path: %s" % fp)
    k.CloseHandle(h)
    return fid, bh, fp


def main():
    os.makedirs(WORK, exist_ok=True)
    a = os.path.join(WORK, "a.txt")
    b = os.path.join(WORK, "b_link.txt")
    c = os.path.join(WORK, "c_copy.txt")
    d = os.path.join(WORK, "D_IFFERENT_CASE.txt")
    for p in (a, b, c, d):
        if os.path.exists(p):
            os.remove(p)
    with open(a, "wb") as fh:
        fh.write(b"identity-probe" * 64)
    ok = k.CreateHardLinkW(b, a, None)
    print("CreateHardLinkW ok=%s err=%d" % (bool(ok), err()))
    with open(c, "wb") as fh:
        fh.write(b"identity-probe" * 64)
    with open(d, "wb") as fh:
        fh.write(b"case-probe")

    print("=== A: same file, two names (hard link)")
    describe("a.txt", a)
    describe("b_link.txt", b)

    print("=== B: same size, different file (no link)")
    describe("c_copy.txt", c)

    print("=== C: case difference on a case-insensitive volume")
    describe("upper-case spelling", d.upper())
    describe("D_IFFERENT_CASE.txt", d)

    print("=== D: 8.3 short name")
    long_name = os.path.join(WORK, "a_very_long_file_name_for_short_name_probe.txt")
    if os.path.exists(long_name):
        os.remove(long_name)
    with open(long_name, "wb") as fh:
        fh.write(b"x")
    out = subprocess.run(["cmd", "/c", "dir /x \"%s\"" % WORK],
                         capture_output=True, text=True)
    print("   dir /x: %s" % ((out.stdout or "").replace("\n", " | ")[:400]))
    describe("long name", long_name)

    print("=== E: os.path.samefile / realpath behaviour")
    try:
        print("   samefile(a,b) = %s" % os.path.samefile(a, b))
    except OSError as exc:
        print("   samefile(a,b) failed: %s" % exc)
    print("   realpath(a) = %s" % os.path.realpath(a))
    print("   realpath(b) = %s" % os.path.realpath(b))
    print("   strings equal = %s" % (os.path.realpath(a) == os.path.realpath(b)))

    print("=== F: OpenFileById - reopen a handle from its id")
    h = openf(a)
    fid = file_id_info(h)
    k.CloseHandle(h)
    if fid is None:
        print("   no FileIdInfo available")
    else:
        vol, raw = fid
        desc = FILE_ID_DESCRIPTOR()
        desc.dwSize = ctypes.sizeof(FILE_ID_DESCRIPTOR)
        desc.Type = 0  # FileIdType
        desc.FileId = FILE_ID_128((ctypes.c_ubyte * 16)(*raw))
        volh = k.CreateFileW("\\\\?\\Volume{%08x-0000-0000-0000-000000000000}\\" % vol,
                             GENERIC_READ, FILE_SHARE_ALL, None, OPEN_EXISTING, 0, None)
        print("   volume handle (synthetic guid) = %s err=%d" % (volh != INVALID_HANDLE_VALUE, err()))
        k.OpenFileById = k.OpenFileById
        k.OpenFileById.argtypes = [wintypes.HANDLE, ctypes.POINTER(FILE_ID_DESCRIPTOR),
                                   wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
        k.OpenFileById.restype = wintypes.HANDLE
        h2 = k.OpenFileById(volh if volh != INVALID_HANDLE_VALUE else h, ctypes.byref(desc),
                            GENERIC_READ, FILE_SHARE_ALL, None)
        if h2 == INVALID_HANDLE_VALUE:
            print("   OpenFileById failed err=%d" % err())
        else:
            print("   OpenFileById ok, final path = %s" % final_path(h2))
            k.CloseHandle(h2)
        if volh != INVALID_HANDLE_VALUE:
            k.CloseHandle(volh)

    print("=== G: what does st_ino look like across the hard-linked pair?")
    sa = os.stat(a)
    sb = os.stat(b)
    print("   st_ino a=%d b=%d equal=%s" % (sa.st_ino, sb.st_ino, sa.st_ino == sb.st_ino))
    print("   st_nlink a=%d b=%d" % (sa.st_nlink, sb.st_nlink))

    print("=== H: volume serial from fsutil")
    print("   fsinfo volumeinfo C: %s" % fsutil(["fsinfo", "volumeinfo", "C:"])[:220])

    print("PROBE_IDENT_DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
