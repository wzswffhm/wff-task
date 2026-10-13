"""文件头布局。"""

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
    """解析文件头，返回 (version, flags, seg_count, index_offset)。"""
    if len(data) < HEADER_SIZE:
        raise WSegError("truncated", f"header needs {HEADER_SIZE} bytes, got {len(data)}")
    magic, version, flags, seg_count, index_offset, _reserved = _HEADER.unpack_from(data, 0)
    if magic != MAGIC:
        raise WSegError("magic", f"bad magic {magic!r}")
    if version != SUPPORTED_VERSION:
        raise WSegError("version", f"unsupported version {version}")
    return version, flags, seg_count, index_offset
