"""尾部段索引。"""

from __future__ import annotations

import struct

from .errors import WSegError

INDEX_ENTRY_SIZE = 4

_ENTRY = struct.Struct("<I")


def build_index(offsets) -> bytes:
    out = bytearray()
    for offset in offsets:
        out += _ENTRY.pack(offset & 0xFFFFFFFF)
    return bytes(out)


def parse_index(data: bytes, pos: int, count: int):
    """读取 ``count`` 个索引条目，返回各段偏移。"""
    needed = pos + INDEX_ENTRY_SIZE * count
    if needed > len(data):
        raise WSegError("structure", f"index needs {INDEX_ENTRY_SIZE * count} bytes at {pos}")
    offsets = []
    for index in range(count):
        (offset,) = _ENTRY.unpack_from(data, pos + index * INDEX_ENTRY_SIZE)
        offsets.append(offset)
    return offsets
