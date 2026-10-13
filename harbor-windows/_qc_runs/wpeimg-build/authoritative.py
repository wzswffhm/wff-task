# -*- coding: utf-8 -*-
"""authoritative.py —— 用 Windows 映像帮助库离线生成权威校验和常量。"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import pathlib

ASSETS = pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
    r"\wfflab__wpeimg-219-v1.0.0-delivery\environment\workspace\assets")
TMP = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
                   r"\_qc_runs\wpeimg-build\probe")


def win_checksum(path: pathlib.Path):
    lib = ctypes.WinDLL("imagehlp")
    lib.MapFileAndCheckSumW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.wintypes.DWORD),
        ctypes.POINTER(ctypes.wintypes.DWORD),
    ]
    lib.MapFileAndCheckSumW.restype = ctypes.wintypes.DWORD
    header = ctypes.wintypes.DWORD(0)
    checksum = ctypes.wintypes.DWORD(0)
    status = lib.MapFileAndCheckSumW(
        str(path), ctypes.byref(header), ctypes.byref(checksum))
    return int(status), int(checksum.value)


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    target = TMP / "authoritative-probe.bin"
    out = {}
    for name in ("amd64-module.bin", "i386-module.bin"):
        blob = (ASSETS / name).read_bytes()
        for extra in (b"", b"\x01", b"\x01\x02", b"\x01\x02\x03", b"\xff" * 17):
            target.write_bytes(blob + extra)
            status, value = win_checksum(target)
            key = "%s+%d" % (name, len(extra))
            out[key] = {"status": status, "checksum": value}
            print("%-28s status=%d checksum=%d" % (key, status, value))
    (TMP / "authoritative-checksums.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
