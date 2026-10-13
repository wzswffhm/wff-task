# -*- coding: utf-8 -*-
"""authoritative.py —— 用 Windows 映像帮助库离线生成权威校验和常量。"""
from __future__ import annotations

def _package_root():
    """本文件位于 <pkg>/verifier/evidence/，包根是上溯三层。"""
    return Path(__file__).resolve().parents[2]


def _resolve_assets() -> Path:
    """定位权威样本目录：--assets > WPEIMG_ASSETS > 包内 workspace/assets。"""
    import os
    override = os.environ.get("WPEIMG_ASSETS")
    if override:
        return Path(override)
    return _package_root() / "environment" / "workspace" / "assets"


def _resolve_zip() -> Path:
    """定位内置 python embed 发行包：--zip > WPEIMG_ZIP > 包内 vendor。"""
    import os
    override = os.environ.get("WPEIMG_ZIP")
    if override:
        return Path(override)
    return _package_root() / "environment" / "vendor" / "python-3.12.9-embed-amd64.zip"

import ctypes
import ctypes.wintypes
import json
import pathlib
from pathlib import Path

ASSETS = _resolve_assets()  # noqa: F821 (bound in main)
TMP = _resolve_tmp()  # noqa: F821 (bound in main)


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
