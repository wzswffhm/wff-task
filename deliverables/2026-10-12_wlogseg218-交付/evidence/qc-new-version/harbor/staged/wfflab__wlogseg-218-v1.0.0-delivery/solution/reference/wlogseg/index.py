"""尾部段索引。"""

from __future__ import annotations

import struct

from .errors import WSegError

INDEX_ENTRY_SIZE = 8

_ENTRY = struct.Struct("<II")


def build_index(offsets, lengths) -> bytes:
    if len(offsets) != len(lengths):
        raise WSegError("structure", "index offset/length count mismatch")
    out = bytearray()
    for offset, length in zip(offsets, lengths):
        out += _ENTRY.pack(offset & 0xFFFFFFFF, length & 0xFFFFFFFF)
    return bytes(out)


def parse_index(data: bytes, pos: int, count: int):
    """读取 ``count`` 个索引条目；数据不足时报 truncated。"""
    needed = pos + INDEX_ENTRY_SIZE * count
    if needed > len(data):
        raise WSegError("truncated", f"index needs {INDEX_ENTRY_SIZE * count} bytes at {pos}")
    entries = []
    for index in range(count):
        offset, length = _ENTRY.unpack_from(data, pos + index * INDEX_ENTRY_SIZE)
        entries.append((offset, length))
    return entries
