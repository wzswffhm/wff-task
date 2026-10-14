"""Probe child: report which of two pipe handles actually crossed the boundary.

Pure ASCII. Argv: <write_handle_a> <write_handle_b>
"""

import ctypes
import sys
from ctypes import wintypes

GENERIC_WRITE = 0x40000000

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
                        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
k.WriteFile.restype = wintypes.BOOL
k.GetFileType.argtypes = [wintypes.HANDLE]
k.GetFileType.restype = wintypes.DWORD


def try_write(raw_value, tag):
    h = wintypes.HANDLE(raw_value)
    kind = k.GetFileType(h)
    payload = ("%s:value=%d:GetFileType=%d" % (tag, raw_value, kind)).encode("ascii")
    written = wintypes.DWORD(0)
    ok = k.WriteFile(h, payload, len(payload), ctypes.byref(written), None)
    err = ctypes.get_last_error()
    return "%s ok=%s written=%d err=%d" % (tag, bool(ok), written.value, err)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: probe-handle-child.py <handleA> <handleB>")
    a = int(sys.argv[1])
    b = int(sys.argv[2])
    # The parent reads whatever lands in pipe A and pipe B, so write to both and
    # let the parent's read side show which writes succeeded.
    for tag, value in (("A", a), ("B", b)):
        try:
            result = try_write(value, tag)
        except OSError as exc:
            result = "%s raised %s" % (tag, exc)
        try:
            # report back through the same handle when it works
            h = wintypes.HANDLE(value)
            written = wintypes.DWORD(0)
            k.WriteFile(h, ("%s\n" % result).encode("ascii"), len(result) + 1,
                        ctypes.byref(written), None)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
