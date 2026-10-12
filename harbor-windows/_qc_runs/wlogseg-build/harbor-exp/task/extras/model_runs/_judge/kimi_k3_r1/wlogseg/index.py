"""尾部段索引。

每个索引条目 8 字节：段在文件中的起始偏移（4 字节小端）+
段的总长度（含段头与填充，4 字节小端）。
"""

from __future__ import annotations

import struct

from .errors import WSegError

INDEX_ENTRY_SIZE = 8

_ENTRY = struct.Struct("<II")


def build_index(entries) -> bytes:
    """``entries`` 为 (offset, length) 序列。"""
    out = bytearray()
    for offset, length in entries:
        out += _ENTRY.pack(offset & 0xFFFFFFFF, length & 0xFFFFFFFF)
    return bytes(out)


def parse_index(data: bytes, pos: int, count: int):
    """读取 ``count`` 个索引条目，返回 [(offset, length), ...]。"""
    needed = pos + INDEX_ENTRY_SIZE * count
    if needed > len(data):
        raise WSegError("truncated", f"index needs {INDEX_ENTRY_SIZE * count} bytes at {pos}")
    entries = []
    for index in range(count):
        offset, length = _ENTRY.unpack_from(data, pos + index * INDEX_ENTRY_SIZE)
        entries.append((offset, length))
    return entries
