"""文件头布局。

真实布局以 ``assets/`` 下的样本为准（``docs/FORMAT.md`` 是早期草稿，已经
过时）::

    偏移  长度  含义
    0     4     魔数 ``WLSG``
    4     1     版本号（当前支持 1）
    5     1     标志位
    6     2     段数量（小端 uint16）
    8     4     尾部索引区的起始偏移（小端 uint32，绝对偏移）
    12    4     保留，恒为 0
"""

from __future__ import annotations

import struct

from .errors import WSegError

MAGIC = b"WLSG"
SUPPORTED_VERSION = 1
HEADER_SIZE = 16

_HEADER = struct.Struct("<4sBBHII")


def build_header(seg_count: int, index_offset: int, flags: int = 0,
                 version: int = SUPPORTED_VERSION) -> bytes:
    return _HEADER.pack(MAGIC, version & 0xFF, flags & 0xFF, seg_count & 0xFFFF,
                        index_offset & 0xFFFFFFFF, 0)


def parse_header(data: bytes):
    """解析文件头，返回 (version, flags, seg_count, index_offset)。

    数据不足时抛 ``truncated``；魔数 / 版本号不匹配时，即使数据不足也会
    优先报告 ``magic`` / ``version``。
    """
    if len(data) >= len(MAGIC) and bytes(data[:len(MAGIC)]) != MAGIC:
        raise WSegError("magic", f"bad magic {bytes(data[:len(MAGIC)])!r}")
    if len(data) > 4 and data[4] != SUPPORTED_VERSION:
        raise WSegError("version", f"unsupported version {data[4]}")
    if len(data) < HEADER_SIZE:
        raise WSegError(
            "truncated", f"the file header needs {HEADER_SIZE} bytes, got {len(data)}"
        )
    magic, version, flags, seg_count, index_offset, _reserved = _HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise WSegError("magic", f"bad magic {magic!r}")
    if version != SUPPORTED_VERSION:
        raise WSegError("version", f"unsupported version {version}")
    return version, flags, seg_count, index_offset
