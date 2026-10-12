"""尾部段索引。

真实布局以 ``assets/`` 下的样本为准：索引区紧跟在最后一个段的填充之后，
每个段一个条目，**每条 8 字节**，按段顺序排列::

    偏移  长度  含义
    0     4     该段在文件中的起始偏移（小端 uint32，绝对偏移）
    4     4     该段的总长度（小端 uint32，含段头、payload 与填充）

注意这与早期草稿 ``docs/FORMAT.md`` 中“每条 4 字节、只记录偏移”的描述
不一致，样本才是权威。
"""

from __future__ import annotations

import struct

from .errors import WSegError

INDEX_ENTRY_SIZE = 8

_ENTRY = struct.Struct("<II")


def build_index(entries) -> bytes:
    """把 ``[(offset, length), ...]`` 序列化为索引区字节。"""
    out = bytearray()
    for entry in entries:
        try:
            offset, length = entry
        except (TypeError, ValueError):
            raise WSegError(
                "structure", f"index entry {entry!r} is not an (offset, length) pair"
            )
        out += _ENTRY.pack(offset & 0xFFFFFFFF, length & 0xFFFFFFFF)
    return bytes(out)


def parse_index(data: bytes, pos: int, count: int):
    """读取 ``count`` 个索引条目，返回各段的 ``(起始偏移, 总长度)``。"""
    needed = INDEX_ENTRY_SIZE * count
    if pos + needed > len(data):
        raise WSegError(
            "truncated",
            f"the tail index needs {needed} bytes at {pos}, got {len(data) - pos}",
        )
    return [
        _ENTRY.unpack_from(data, pos + index * INDEX_ENTRY_SIZE)
        for index in range(count)
    ]
