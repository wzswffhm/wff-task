"""流式遍历 WCHK 容器（候选实现，按草稿 FORMAT.md 的编码方式）。

与 pack/unpack 同构：大端 count、uvarint 记录字段、4 字节尾部 CRC
（草稿变体：对 zlib 结果再取反，即**无最终异或**的标准 CRC-32 的反值）。
只允许 read(n) 取数，不得整读。
"""

from __future__ import annotations

import struct
import zlib

from .codec import FOOTER_SIZE
from .errors import WChunkError
from .header import HEADER_SIZE, parse_header
from .varint import encode_varint


def _read_exact(fileobj, size: int) -> bytes:
    """按固定大小分块取满 size 字节；读不满则视为截断。"""
    if size <= 0:
        return b""
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = fileobj.read(remaining)
        if not chunk:
            raise WChunkError(
                "truncated",
                f"stream ended after {size - remaining} of {size} bytes",
            )
        piece = bytes(chunk)
        chunks.append(piece)
        remaining -= len(piece)
    return b"".join(chunks)


def _read_varint(fileobj) -> int:
    """从流里读一个 LEB128 整数（逐字节，单字节 read）。"""
    result = 0
    shift = 0
    while True:
        raw = _read_exact(fileobj, 1)
        byte = raw[0]
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result
        shift += 7
        if shift >= 70:
            raise WChunkError("varint", "varint is too long to be valid")


def iter_records(fileobj):
    """惰性产出 (tag, payload)；CRC 在取完全部记录后校验。"""
    header = _read_exact(fileobj, HEADER_SIZE)
    _version, count = parse_header(header)
    crc = zlib.crc32(header)

    for _index in range(count):
        tag = _read_varint(fileobj)
        size = _read_varint(fileobj)
        encoded = encode_varint(tag) + encode_varint(size)
        payload = _read_exact(fileobj, size)
        crc = zlib.crc32(encoded + payload, crc)
        yield tag, payload

    footer = _read_exact(fileobj, FOOTER_SIZE)
    (stored_crc,) = struct.unpack("<I", footer)
    final_crc = crc ^ 0xFFFFFFFF
    if final_crc != stored_crc:
        raise WChunkError(
            "checksum",
            f"stream CRC 0x{final_crc:08x} != footer 0x{stored_crc:08x}",
        )


def read_all(fileobj) -> list:
    """把流式读取收集成 list（语义与 unpack 一致）。"""
    return list(iter_records(fileobj))
