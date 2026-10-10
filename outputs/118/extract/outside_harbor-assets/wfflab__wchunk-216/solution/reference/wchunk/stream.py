"""流式遍历 WCHK 容器（iter_records / read_all）。

流式约束（判据会用 GuardedReader 实测）：
  * 只允许 `read(n)` 且 n 为正整数 —— 禁止 `read()` / `read(-1)`；
  * 取出**第一条**记录时，读过的字节应只有头 + 那条记录，
    不得先读整个文件再解析；
  * 末尾仍必须校验 footer 的 CRC（覆盖 header + 全部记录）与 tag_sum。
"""

from __future__ import annotations

import struct
import zlib

from .codec import FOOTER_SIZE, RECORD_PREFIX, _align_up
from .errors import WChunkError
from .header import HEADER_SIZE, parse_header


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
        pieces = bytes(chunk)
        chunks.append(pieces)
        remaining -= len(pieces)
    return b"".join(chunks)


def iter_records(fileobj):
    """惰性产出 (tag, payload)；CRC 与 tag_sum 在取完全部记录后校验。"""
    header = _read_exact(fileobj, HEADER_SIZE)
    _version, count = parse_header(header)
    crc = zlib.crc32(header)
    tag_sum = 0

    for _index in range(count):
        prefix = _read_exact(fileobj, RECORD_PREFIX)
        tag, size = struct.unpack("<HH", prefix)
        payload = _read_exact(fileobj, size)
        span = _align_up(RECORD_PREFIX + size)
        padding = _read_exact(fileobj, span - RECORD_PREFIX - size)
        crc = zlib.crc32(prefix + payload + padding, crc)
        tag_sum += tag
        yield tag, payload

    footer = _read_exact(fileobj, FOOTER_SIZE)
    stored_crc, stored_sum = struct.unpack("<IH", footer)
    actual_crc = crc & 0xFFFFFFFF
    if actual_crc != stored_crc:
        raise WChunkError(
            "checksum",
            f"stream CRC-32 0x{actual_crc:08x} != footer 0x{stored_crc:08x}",
        )
    if (tag_sum & 0xFFFF) != stored_sum:
        raise WChunkError(
            "structure",
            f"stream tag_sum {tag_sum & 0xFFFF} != footer {stored_sum}",
        )


def read_all(fileobj) -> list:
    """把流式读取收集成 list（语义与 unpack 一致）。"""
    return list(iter_records(fileobj))
