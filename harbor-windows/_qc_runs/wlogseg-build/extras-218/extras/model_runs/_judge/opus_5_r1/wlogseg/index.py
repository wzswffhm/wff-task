"""尾部段索引。

每个索引条目 8 字节（小端）：段在文件中的起始偏移（4 字节）+ 段的整体长度
（4 字节，含段头与对齐填充）。条目按段顺序排列。
"""

from __future__ import annotations

import struct

from .errors import WSegError

INDEX_ENTRY_SIZE = 8

_ENTRY = struct.Struct("<II")


def build_index(entries) -> bytes:
    """``entries`` 是 (offset, length) 序列。"""
    out = bytearray()
    for offset, length in entries:
        out += _ENTRY.pack(offset & 0xFFFFFFFF, length & 0xFFFFFFFF)
    return bytes(out)


def parse_index(data, pos: int, count: int):
    """读取 ``count`` 个索引条目，返回 [(offset, length), ...]。"""
    buf = bytes(data)
    needed = pos + INDEX_ENTRY_SIZE * count
    if needed > len(buf):
        raise WSegError("truncated", f"index needs {INDEX_ENTRY_SIZE * count} bytes at {pos}")
    return [_ENTRY.unpack_from(buf, pos + i * INDEX_ENTRY_SIZE) for i in range(count)]
