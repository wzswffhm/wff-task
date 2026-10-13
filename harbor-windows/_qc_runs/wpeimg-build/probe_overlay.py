# -*- coding: utf-8 -*-
"""probe_overlay.py —— 检查候选 PE 素材的节区覆盖与文件尾部。"""
from __future__ import annotations

import struct
import sys
import zipfile
from pathlib import Path

ZIP = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
           r"\wfflab__wpeimg-219-v1.0.0-delivery\environment\vendor"
           r"\python-3.12.9-embed-amd64.zip")
ASSETS = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
              r"\wfflab__wpeimg-219-v1.0.0-delivery\environment\workspace\assets")


def report(name: str, blob: bytes) -> None:
    e = struct.unpack_from("<I", blob, 0x3C)[0]
    coff = e + 4
    machine, nsec, _a, _b, _c, size_opt, _d = struct.unpack_from("<HHIIIHH", blob, coff)
    opt = coff + 20
    magic = struct.unpack_from("<H", blob, opt)[0]
    plus = magic == 0x20B
    size_headers = struct.unpack_from("<I", blob, opt + 60)[0]
    sectab = opt + size_opt
    ends = []
    print("%s  size=%d machine=0x%X nsec=%d size_opt=0x%X size_headers=0x%X"
          % (name, len(blob), machine, nsec, size_opt, size_headers))
    for i in range(nsec):
        off = sectab + i * 40
        nm = blob[off:off + 8].rstrip(b"\0").decode("latin-1")
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", blob, off + 8)
        end = rawptr + rawsize
        ends.append((end, nm))
        print("   %-9s va=0x%-6X vsize=0x%-6X rawptr=0x%-6X rawsize=0x%-6X end=0x%X"
              % (nm, va, vsize, rawptr, rawsize, end))
    if ends:
        last = max(ends)
        tail = len(blob) - last[0]
        print("   节区覆盖结束=0x%X(%d)  文件=%d  尾部多余=%d 字节"
              % (last[0], last[0], len(blob), tail))
        if tail > 0:
            seg = blob[last[0]:last[0] + 48]
            print("   尾部前 48 字节: %s" % seg.hex(" "))
            printable = "".join(chr(c) if 32 <= c < 127 else "." for c in seg)
            print("   可读形式      : %s" % printable)
    print()


def main() -> int:
    zf = zipfile.ZipFile(ZIP)
    for n in ("_uuid.pyd", "winsound.pyd", "select.pyd", "python.exe",
              "python3.dll"):
        try:
            report(n, zf.read(n))
        except KeyError:
            pass
    zf.close()
    for p in sorted(ASSETS.glob("*.bin")):
        report(p.name, p.read_bytes())
    return 0


if __name__ == "__main__":
    sys.exit(main())
