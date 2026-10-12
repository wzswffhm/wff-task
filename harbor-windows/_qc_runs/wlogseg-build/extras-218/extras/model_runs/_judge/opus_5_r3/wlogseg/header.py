"""文件头布局。

真实布局（以 ``assets/`` 下的样本为准，16 字节）::

    偏移  长度  含义
    0     4     魔数 b"WLSG"
    4     1     版本号
    5     1     标志位
    6     2     段数量（小端）
    8     4     索引区偏移（小端）
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

    魔数一旦可判定就优先判定：不是 WLSG 容器时报 ``magic``，而不是 ``truncated``。
    数据不足 16 字节（但魔数正确）属于 ``truncated``。
    """
    data = bytes(data)
    if len(data) >= len(MAGIC) and data[:len(MAGIC)] != MAGIC:
        raise WSegError("magic", f"bad magic {data[:len(MAGIC)]!r}")
    if len(data) < HEADER_SIZE:
        raise WSegError("truncated", f"header needs {HEADER_SIZE} bytes, got {len(data)}")
    magic, version, flags, seg_count, index_offset, _reserved = _HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise WSegError("magic", f"bad magic {magic!r}")
    if version != SUPPORTED_VERSION:
        raise WSegError("version", f"unsupported version {version}")
    return version, flags, seg_count, index_offset
