"""容器尾部校验和。"""

from __future__ import annotations

import zlib

from .errors import WChunkError


def compute_crc(data: bytes) -> int:
    """返回 ``data`` 的 32 位校验和。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WChunkError("structure", f"compute_crc expects bytes, got {type(data).__name__}")
    return zlib.crc32(data) ^ 0xFFFFFFFF
