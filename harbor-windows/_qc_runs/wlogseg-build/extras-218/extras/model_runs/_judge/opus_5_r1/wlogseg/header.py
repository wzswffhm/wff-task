"""文件头布局。

实际布局（16 字节，小端）：

| 偏移 | 长度 | 含义 |
| --- | --- | --- |
| 0 | 4 | 魔数 ``WLSG`` |
| 4 | 1 | 版本号 |
| 5 | 1 | 标志位 |
| 6 | 2 | 段数量 |
| 8 | 4 | 索引区偏移 |
| 12 | 4 | 保留，恒为 0 |
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


def parse_header(data):
    """解析文件头，返回 (version, flags, seg_count, index_offset)。

    数据不足时抛 ``truncated``；但只要已有的字节足以判定魔数或版本不对，
    就优先报告 ``magic`` / ``version``。
    """
    buf = bytes(data)
    size = len(buf)

    if size < len(MAGIC):
        if buf != MAGIC[:size]:
            raise WSegError("magic", f"bad magic {buf!r}")
        raise WSegError("truncated", f"header needs {HEADER_SIZE} bytes, got {size}")
    if buf[:len(MAGIC)] != MAGIC:
        raise WSegError("magic", f"bad magic {buf[:len(MAGIC)]!r}")
    if size > len(MAGIC) and buf[len(MAGIC)] != SUPPORTED_VERSION:
        raise WSegError("version", f"unsupported version {buf[len(MAGIC)]}")
    if size < HEADER_SIZE:
        raise WSegError("truncated", f"header needs {HEADER_SIZE} bytes, got {size}")

    _magic, version, flags, seg_count, index_offset, _reserved = _HEADER.unpack_from(buf, 0)
    if version != SUPPORTED_VERSION:
        raise WSegError("version", f"unsupported version {version}")
    return version, flags, seg_count, index_offset
