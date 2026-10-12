"""尾部段索引。"""

from __future__ import annotations

import struct

from .errors import WSegError

INDEX_ENTRY_SIZE = 8

_ENTRY = struct.Struct("<II")


def build_index(entries) -> bytes:
    """构建索引区。

    ``entries`` 是可迭代的 ``(offset, total_segment_length)`` 对。
    """
    out = bytearray()
    for offset, seg_len in entries:
        out += _ENTRY.pack(offset & 0xFFFFFFFF, seg_len & 0xFFFFFFFF)
    return bytes(out)


def parse_index(data: bytes, pos: int, count: int):
    """读取 ``count`` 个索引条目，返回各段 ``(offset, total_length)`` 列表。"""
    needed = pos + INDEX_ENTRY_SIZE * count
    if needed > len(data):
        raise WSegError("truncated", f"index needs {INDEX_ENTRY_SIZE * count} bytes at {pos}")
    result = []
    for i in range(count):
        offset, seg_len = _ENTRY.unpack_from(data, pos + i * INDEX_ENTRY_SIZE)
        result.append((offset, seg_len))
    return result
