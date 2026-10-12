"""尾部段索引。

真实布局（以 ``assets/`` 下的样本为准）：每个条目 **8** 字节，按段顺序排列::

    偏移  长度  含义
    0     4     该段在文件中的起始偏移（小端，指向段头）
    4     4     该段在文件中占用的总长度（小端，含段头与填充）

草稿里写的「每条目 4 字节、只记偏移」已经过时。
"""

from __future__ import annotations

import struct

from .errors import WSegError

INDEX_ENTRY_SIZE = 8

_ENTRY = struct.Struct("<II")


def build_index(entries) -> bytes:
    """``entries`` 为 [(offset, length), ...]。"""
    out = bytearray()
    for offset, length in entries:
        out += _ENTRY.pack(offset & 0xFFFFFFFF, length & 0xFFFFFFFF)
    return bytes(out)


def encode_index_entry(offset: int, length: int) -> bytes:
    return _ENTRY.pack(offset & 0xFFFFFFFF, length & 0xFFFFFFFF)


def decode_index_entry(chunk: bytes):
    if len(chunk) < INDEX_ENTRY_SIZE:
        raise WSegError("truncated", "index entry is incomplete")
    return _ENTRY.unpack_from(chunk, 0)


def parse_index(data: bytes, pos: int, count: int):
    """读取 ``count`` 个索引条目，返回 [(offset, length), ...]。"""
    needed = pos + INDEX_ENTRY_SIZE * count
    if needed > len(data):
        raise WSegError("truncated", f"index needs {INDEX_ENTRY_SIZE * count} bytes at {pos}")
    entries = []
    for index in range(count):
        entries.append(_ENTRY.unpack_from(data, pos + index * INDEX_ENTRY_SIZE))
    return entries
