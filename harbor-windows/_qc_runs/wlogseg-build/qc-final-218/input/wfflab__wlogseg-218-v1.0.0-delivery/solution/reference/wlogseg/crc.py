"""容器尾部校验和使用的通用 32 位 CRC。"""

from __future__ import annotations

import zlib


def crc32_update(data, value: int = 0) -> int:
    """增量更新：``crc32_update(chunk, running)`` 等价于对拼接结果一次算完。"""
    return zlib.crc32(bytes(data), value & 0xFFFFFFFF) & 0xFFFFFFFF


def compute_crc(data) -> int:
    """CRC-32/ISO-HDLC：反射、初值 0xFFFFFFFF、多项式 0xEDB88320、结果异或 0xFFFFFFFF。"""
    if isinstance(data, str):
        raise TypeError("compute_crc expects a bytes-like object")
    return crc32_update(data, 0)
