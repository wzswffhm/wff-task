# -*- coding: utf-8 -*-
"""checksum_experiment.py —— 用 Windows 原生 API 判定 PE 校验和的唯一正确实现。

对若干真实映像比较 4 种候选算法与 MapFileAndCheckSumW 的结果，输出每种算法的吻合情况。
结果用于钉死 219 题包的参考实现与隐藏测试期望值。
"""
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
import json
import struct
import zipfile
from ctypes import wintypes
from pathlib import Path

ZIP = _resolve_zip()  # noqa: F821 (bound in main)
ASSETS = _resolve_assets()  # noqa: F821 (bound in main)
TMP = _resolve_tmp()  # noqa: F821 (bound in main)

imagehlp = ctypes.WinDLL("imagehlp")
imagehlp.MapFileAndCheckSumW.argtypes = [wintypes.LPCWSTR,
                                         ctypes.POINTER(wintypes.DWORD),
                                         ctypes.POINTER(wintypes.DWORD)]
imagehlp.MapFileAndCheckSumW.restype = wintypes.DWORD


def win_checksum(path: Path):
    hs, cs = wintypes.DWORD(0), wintypes.DWORD(0)
    rc = imagehlp.MapFileAndCheckSumW(str(path), ctypes.byref(hs), ctypes.byref(cs))
    return rc, cs.value


def opt_offset(data: bytes) -> int:
    e = struct.unpack_from("<I", data, 0x3C)[0]
    return e + 4 + 20


def zeroed(data: bytes) -> bytearray:
    buf = bytearray(data)
    o = opt_offset(buf)
    buf[o + 64:o + 68] = b"\0\0\0\0"
    return buf


def variant_a(buf: bytearray) -> int:
    """先全量累加（只回收 32 位进位），最后两次折叠。"""
    total = 0
    n = len(buf)
    i = 0
    while i + 4 <= n:
        total += struct.unpack_from("<I", buf, i)[0]
        total = (total & 0xFFFFFFFF) + (total >> 32)
        i += 4
    rem = n - i
    if rem == 3:
        total += buf[i] | (buf[i + 1] << 8) | (buf[i + 2] << 16)
    elif rem == 2:
        total += buf[i] | (buf[i + 1] << 8)
    elif rem == 1:
        total += buf[i]
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + n) & 0xFFFFFFFF


def variant_b(buf: bytearray) -> int:
    """每步回绕到 32 位并立即 16 位折叠（pefile / ReactOS 风格）。"""
    total = 0
    n = len(buf)
    i = 0
    while i + 4 <= n:
        total = (total + struct.unpack_from("<I", buf, i)[0]) & 0xFFFFFFFF
        total = (total & 0xFFFF) + (total >> 16)
        i += 4
    rem = n - i
    if rem == 3:
        dword = buf[i] | (buf[i + 1] << 8) | (buf[i + 2] << 16)
    elif rem == 2:
        dword = buf[i] | (buf[i + 1] << 8)
    elif rem == 1:
        dword = buf[i]
    else:
        dword = None
    if dword is not None:
        total = (total + dword) & 0xFFFFFFFF
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + n) & 0xFFFFFFFF


def variant_c(buf: bytearray) -> int:
    """每步回绕到 32 位但只在最后折叠一次。"""
    total = 0
    n = len(buf)
    i = 0
    while i + 4 <= n:
        total = (total + struct.unpack_from("<I", buf, i)[0]) & 0xFFFFFFFF
        i += 4
    rem = n - i
    if rem == 3:
        total = (total + (buf[i] | (buf[i + 1] << 8) | (buf[i + 2] << 16))) & 0xFFFFFFFF
    elif rem == 2:
        total = (total + (buf[i] | (buf[i + 1] << 8))) & 0xFFFFFFFF
    elif rem == 1:
        total = (total + buf[i]) & 0xFFFFFFFF
    total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + n) & 0xFFFFFFFF


def variant_d(buf: bytearray) -> int:
    """按 16 位字累加（另一种常见写法）。"""
    total = 0
    n = len(buf)
    i = 0
    while i + 2 <= n:
        total = (total + struct.unpack_from("<H", buf, i)[0]) & 0xFFFFFFFF
        total = (total & 0xFFFF) + (total >> 16)
        i += 2
    if i < n:
        total = (total + buf[i]) & 0xFFFFFFFF
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + n) & 0xFFFFFFFF


VARIANTS = {"A_全量后折叠": variant_a, "B_每步折叠": variant_b,
            "C_每步回绕": variant_c, "D_按字折叠": variant_d}


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    files = []
    zf = zipfile.ZipFile(ZIP)
    for name in ("winsound.pyd", "select.pyd", "python.exe", "vcruntime140.dll",
                 "_uuid.pyd", "_queue.pyd", "python3.dll", "_socket.pyd",
                 "_ssl.pyd", "libffi-8.dll"):
        try:
            raw = zf.read(name)
        except KeyError:
            continue
        p = TMP / name
        p.write_bytes(raw)
        files.append(p)
    zf.close()
    for extra in sorted(ASSETS.glob("*.bin")):
        files.append(extra)

    tally = {k: 0 for k in VARIANTS}
    rows = []
    for p in files:
        rc, win = win_checksum(p)
        if rc != 0:
            continue
        buf = zeroed(p.read_bytes())
        row = {"file": p.name, "size": len(buf), "windows": win}
        for k, fn in VARIANTS.items():
            v = fn(buf)
            row[k] = v
            if v == win:
                tally[k] += 1
            else:
                row[k + "_diff"] = v - win
        rows.append(row)

    print("样本数 = %d" % len(rows))
    for k in VARIANTS:
        print("  %-14s 吻合 %d/%d" % (k, tally[k], len(rows)))
    print()
    for r in rows:
        diffs = {k: r.get(k + "_diff") for k in VARIANTS if k + "_diff" in r}
        print("%-20s size=%-7d win=%-8d %s" % (r["file"], r["size"], r["windows"],
                                               diffs if diffs else "全部吻合"))
    Path("checksum_experiment.json").write_text(
        json.dumps({"tally": tally, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
