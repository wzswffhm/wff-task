"""文件头布局。

16 字节，小端::

    偏移  长度  含义
    0     4     魔数 "WLSG"
    4     1     版本号
    5     1     标志位
    6     2     段数量
    8     4     索引区偏移
    12    4     保留，恒为 0
"""

from __future__ import annotations

import struct

from .errors import WSegError

MAGIC = b"WLSG"
SUPPORTED_VERSION = 1
HEADER_SIZE = 16
MAX_SEG_COUNT = 0xFFFF

_HEADER = struct.Struct("<4sBBHII")

assert _HEADER.size == HEADER_SIZE


def build_header(seg_count: int, index_offset: int, flags: int = 0,
                 version: int = SUPPORTED_VERSION) -> bytes:
    return _HEADER.pack(MAGIC, version & 0xFF, flags & 0xFF, seg_count & 0xFFFF,
                        index_offset & 0xFFFFFFFF, 0)


def parse_header(data):
    """解析文件头，返回 (version, flags, seg_count, index_offset)。"""
    if len(data) < HEADER_SIZE:
        raise WSegError("truncated",
                        f"header needs {HEADER_SIZE} bytes, got {len(data)}")
    magic, version, flags, seg_count, index_offset, _reserved = _HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise WSegError("magic", f"bad magic {magic!r}")
    if version != SUPPORTED_VERSION:
        raise WSegError("version", f"unsupported version {version}")
    return version, flags, seg_count, index_offset
