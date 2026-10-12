"""尾部段索引。

索引区按段顺序排列，每个条目 8 字节（小端）::

    偏移  长度  含义
    0     4     该段在文件中的起始偏移
    4     4     该段的总长度（段头 + 数据 + 填充）

早期草稿写的是「每条 4 字节、只记起始偏移」，与样本实际字节不符。
"""

from __future__ import annotations

import struct

from .errors import WSegError

INDEX_ENTRY_SIZE = 8

_ENTRY = struct.Struct("<II")

assert _ENTRY.size == INDEX_ENTRY_SIZE


def index_region_size(count: int) -> int:
    return INDEX_ENTRY_SIZE * count


def build_index(entries) -> bytes:
    """``entries`` 为 (offset, length) 序列。"""
    out = bytearray()
    for offset, length in entries:
        out += _ENTRY.pack(offset & 0xFFFFFFFF, length & 0xFFFFFFFF)
    return bytes(out)


def parse_index(data, pos: int, count: int):
    """读取 ``count`` 个索引条目，返回 [(offset, length), ...]。"""
    data = bytes(data)
    needed = pos + index_region_size(count)
    if needed > len(data):
        raise WSegError("truncated",
                        f"index needs {index_region_size(count)} bytes at {pos}")
    entries = []
    for i in range(count):
        entries.append(_ENTRY.unpack_from(data, pos + i * INDEX_ENTRY_SIZE))
    return entries
