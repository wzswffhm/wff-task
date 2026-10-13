# -*- coding: utf-8 -*-
"""select_pe_assets.py —— 为 219 题包挑选/生成 PE 素材。

产物（写到 env/workspace/assets，由 --out 指定）：
  * amd64-module.bin —— 真实 PE32+ 映像（取自 Python embed 发行包，PSF 许可可再分发）
  * i386-module.bin  —— 合成的 PE32 映像（本脚本按规范逐字段构造，校验和用 Windows 算法写入）

同时打印每个素材的关键结构，便于写测试时钉死期望值。

用法：
    python select_pe_assets.py --out <assets 目录>
"""
from __future__ import annotations

import argparse
import hashlib
import io
import struct
import zipfile
from pathlib import Path

ZIP = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"
           r"\wfflab__wpeimg-219-v1.0.0-delivery\environment\vendor"
           r"\python-3.12.9-embed-amd64.zip")

# ----------------------------------------------------------------- PE 解析


def parse(data: bytes) -> dict:
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e_lfanew:e_lfanew + 4] == b"PE\0\0", hex(e_lfanew)
    coff = e_lfanew + 4
    (machine, nsec, timestamp, symtab, nsym, size_opt, chars) = struct.unpack_from(
        "<HHIIIHH", data, coff)
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    plus = magic == 0x20B
    if plus:
        image_base = struct.unpack_from("<Q", data, opt + 24)[0]
        (align_sec, align_file) = struct.unpack_from("<II", data, opt + 32)
        size_image = struct.unpack_from("<I", data, opt + 56)[0]
        size_headers = struct.unpack_from("<I", data, opt + 60)[0]
        checksum = struct.unpack_from("<I", data, opt + 64)[0]
        subsystem = struct.unpack_from("<H", data, opt + 68)[0]
        nrv = struct.unpack_from("<I", data, opt + 108)[0]
        dd = opt + 112
    else:
        image_base = struct.unpack_from("<I", data, opt + 28)[0]
        (align_sec, align_file) = struct.unpack_from("<II", data, opt + 32)
        size_image = struct.unpack_from("<I", data, opt + 56)[0]
        size_headers = struct.unpack_from("<I", data, opt + 60)[0]
        checksum = struct.unpack_from("<I", data, opt + 64)[0]
        subsystem = struct.unpack_from("<H", data, opt + 68)[0]
        nrv = struct.unpack_from("<I", data, opt + 92)[0]
        dd = opt + 96
    entry = struct.unpack_from("<I", data, opt + 16)[0]
    sectab = opt + size_opt
    sections = []
    for i in range(nsec):
        off = sectab + i * 40
        name = data[off:off + 8].rstrip(b"\0").decode("latin-1")
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
        ch = struct.unpack_from("<I", data, off + 36)[0]
        sections.append(dict(name=name, va=va, vsize=vsize,
                             rawptr=rawptr, rawsize=rawsize, chars=ch))
    return dict(magic=magic, plus=plus, machine=machine, nsec=nsec,
                size_opt=size_opt, entry=entry, image_base=image_base,
                align_sec=align_sec, align_file=align_file,
                size_image=size_image, size_headers=size_headers,
                checksum=checksum, subsystem=subsystem, nrv=nrv,
                dd=dd, sections=sections, e_lfanew=e_lfanew,
                sectab_end=sectab + nsec * 40, size=len(data))


# ------------------------------------------------- Windows PE 校验和算法


def pe_checksum(data: bytes, opt_off: int) -> int:
    """Windows CheckSumMappedFile 等价实现；计算时把 CheckSum 字段视为 0。

    经 checksum_experiment.py 对 12 个真实映像与 MapFileAndCheckSumW 逐一比对确认：
    必须先完整累加（只回收 32 位进位），最后统一做两次 16 位折叠，再叠加文件长度。
    "每步折叠"的写法（网上流传甚广）并不吻合 Windows 的真实结果。
    """
    buf = bytearray(data)
    buf[opt_off + 64:opt_off + 68] = b"\0\0\0\0"
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
    total = (total + n) & 0xFFFFFFFF
    return total


# ------------------------------------------------------- 合成 PE32 映像


def build_i386_image() -> bytes:
    """构造一个结构完全自洽的最小 PE32 控制台映像。

    两个节区：.text（可执行/可读，raw 0x400 起）与 .rdata（只读，raw 0x600 起）。
    可选头按 PE32 布局，NumberOfRvaAndSizes = 16。
    """
    align_file = 0x200
    align_sec = 0x1000
    size_headers = 0x400
    size_opt = 0xE0
    nsec = 2

    text_va, text_vsize, text_rawsize = 0x1000, 0x180, 0x200
    rdata_va, rdata_vsize, rdata_rawsize = 0x2000, 0x40, 0x200
    text_rawptr, rdata_rawptr = 0x400, 0x600
    size_image = rdata_va + ((rdata_vsize + align_sec - 1) // align_sec) * align_sec

    headers = bytearray(size_headers)
    headers[0:2] = b"MZ"
    struct.pack_into("<H", headers, 0x02, 0x90)
    struct.pack_into("<H", headers, 0x04, 0x03)
    struct.pack_into("<H", headers, 0x18, 0x40)
    struct.pack_into("<I", headers, 0x3C, 0x80)
    headers[0x40:0x40 + 64] = (
        b"This program cannot be run in DOS mode.\r\r\n$"
        + b"\0" * 32
    )[:64]

    nt = 0x80
    headers[nt:nt + 4] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", headers, nt + 4,
                     0x14C, nsec, 0x60000000, 0, 0, size_opt, 0x0102)
    opt = nt + 4 + 20
    struct.pack_into("<H", headers, opt + 0, 0x10B)
    headers[opt + 2] = 9
    struct.pack_into("<I", headers, opt + 4, text_rawsize)
    struct.pack_into("<I", headers, opt + 8, rdata_rawsize)
    struct.pack_into("<I", headers, opt + 12, 0)
    struct.pack_into("<I", headers, opt + 16, text_va)          # EntryPoint
    struct.pack_into("<I", headers, opt + 20, text_va)          # BaseOfCode
    struct.pack_into("<I", headers, opt + 24, rdata_va)         # BaseOfData
    struct.pack_into("<I", headers, opt + 28, 0x400000)         # ImageBase
    struct.pack_into("<I", headers, opt + 32, align_sec)
    struct.pack_into("<I", headers, opt + 36, align_file)
    struct.pack_into("<H", headers, opt + 40, 6)
    struct.pack_into("<H", headers, opt + 42, 0)
    struct.pack_into("<H", headers, opt + 44, 0)
    struct.pack_into("<H", headers, opt + 46, 0)
    struct.pack_into("<H", headers, opt + 48, 6)
    struct.pack_into("<H", headers, opt + 50, 0)
    struct.pack_into("<I", headers, opt + 52, 0)
    struct.pack_into("<I", headers, opt + 56, size_image)
    struct.pack_into("<I", headers, opt + 60, size_headers)
    struct.pack_into("<I", headers, opt + 64, 0)                # CheckSum
    struct.pack_into("<H", headers, opt + 68, 3)                # Subsystem = console
    struct.pack_into("<H", headers, opt + 70, 0)
    struct.pack_into("<I", headers, opt + 72, 0x100000)
    struct.pack_into("<I", headers, opt + 76, 0x1000)
    struct.pack_into("<I", headers, opt + 80, 0x100000)
    struct.pack_into("<I", headers, opt + 84, 0x1000)
    struct.pack_into("<I", headers, opt + 88, 0)
    struct.pack_into("<I", headers, opt + 92, 16)               # NumberOfRvaAndSizes

    dd = opt + 96
    struct.pack_into("<II", headers, dd + 0 * 8, 0, 0)          # Export
    struct.pack_into("<II", headers, dd + 1 * 8, 0, 0)          # Import
    struct.pack_into("<II", headers, dd + 2 * 8, rdata_va, 0x20)  # Resource
    struct.pack_into("<II", headers, dd + 3 * 8, 0, 0)
    struct.pack_into("<II", headers, dd + 4 * 8, 0, 0)
    struct.pack_into("<II", headers, dd + 5 * 8, rdata_va + 0x20, 0x10)  # Reloc

    sectab = opt + size_opt
    headers[sectab:sectab + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", headers, sectab + 8,
                     text_vsize, text_va, text_rawsize, text_rawptr)
    struct.pack_into("<I", headers, sectab + 36, 0x60000020)
    sectab2 = sectab + 40
    headers[sectab2:sectab2 + 8] = b".rdata\0\0"
    struct.pack_into("<IIII", headers, sectab2 + 8,
                     rdata_vsize, rdata_va, rdata_rawsize, rdata_rawptr)
    struct.pack_into("<I", headers, sectab2 + 36, 0x40000040)

    text = bytearray(text_rawsize)
    text[0:16] = bytes([0x55, 0x8B, 0xEC, 0x33, 0xC0, 0x5D, 0xC3]) + b"\x90" * 9
    rdata = bytearray(rdata_rawsize)
    rdata[0:16] = b"WFFLAB-WPEIMG219"
    rdata[0x20:0x30] = b"resource-block\0\0"

    blob = bytes(headers) + bytes(text) + bytes(rdata)
    opt_off = nt + 4 + 20
    sum_value = pe_checksum(blob, opt_off)
    blob = bytearray(blob)
    struct.pack_into("<I", blob, opt_off + 64, sum_value)
    return bytes(blob)


# --------------------------------------------------------------- 主流程


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true",
                    help="只校验已有产物，不重写")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    zf = zipfile.ZipFile(ZIP)
    for cand in ("_uuid.pyd", "winsound.pyd", "select.pyd", "_queue.pyd",
                 "python3.dll", "vcruntime140.dll"):
        try:
            raw = zf.read(cand)
        except KeyError:
            continue
        info = parse(raw)
        if info["plus"] and info["checksum"] != 0:
            print("候选 %-22s size=%-7d nsec=%d entry=0x%X csum=%d match=%s"
                  % (cand, info["size"], info["nsec"], info["entry"],
                     info["checksum"], info["checksum"] == pe_checksum(raw, info["dd"] - 112)))
    zf.close()

    amd64 = None
    zf = zipfile.ZipFile(ZIP)
    for cand in ("_uuid.pyd", "winsound.pyd", "select.pyd", "_queue.pyd"):
        raw = zf.read(cand)
        info = parse(raw)
        if info["plus"] and info["checksum"] == pe_checksum(raw, info["dd"] - 112):
            amd64 = (cand, raw, info)
            break
    zf.close()
    if amd64 is None:
        raise SystemExit("没有找到带正确校验和的 PE32+ 候选")

    name, raw, info = amd64
    if not a.check:
        (out / "amd64-module.bin").write_bytes(raw)
        (out / "i386-module.bin").write_bytes(build_i386_image())

    for f in ("amd64-module.bin", "i386-module.bin"):
        blob = (out / f).read_bytes()
        d = parse(blob)
        calc = pe_checksum(blob, d["dd"] - 112 if d["plus"] else d["dd"] - 96)
        print("--- %s (%d bytes, sha256=%s)" % (f, len(blob),
                                               hashlib.sha256(blob).hexdigest()[:16]))
        print("    magic=0x%X machine=0x%X nsec=%d size_opt=0x%X entry=0x%X"
              % (d["magic"], d["machine"], d["nsec"], d["size_opt"], d["entry"]))
        print("    image_base=0x%X align_sec=%d align_file=%d size_image=0x%X size_headers=0x%X"
              % (d["image_base"], d["align_sec"], d["align_file"],
                 d["size_image"], d["size_headers"]))
        print("    checksum recorded=%d computed=%d match=%s"
              % (d["checksum"], calc, d["checksum"] == calc))
        print("    e_lfanew=0x%X sectab_end=0x%X" % (d["e_lfanew"], d["sectab_end"]))
        for s in d["sections"]:
            print("      %-9s va=0x%-6X vsize=0x%-6X rawptr=0x%-6X rawsize=0x%-6X chars=0x%08X"
                  % (s["name"], s["va"], s["vsize"], s["rawptr"], s["rawsize"], s["chars"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
