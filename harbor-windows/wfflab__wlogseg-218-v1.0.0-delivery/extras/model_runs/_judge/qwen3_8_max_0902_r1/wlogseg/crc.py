"""容器尾部校验和使用的 32 位校验和。"""

from __future__ import annotations

import zlib


def crc32_update(data, value: int = 0) -> int:
    """在 ``value`` 的基础上继续累积校验和。"""
    return (zlib.crc32(bytes(data), value) ^ 0xFFFFFFFF) & 0xFFFFFFFF


def compute_crc(data) -> int:
    """返回容器使用的 32 位校验和。"""
    if isinstance(data, str):
        raise TypeError("compute_crc expects a bytes-like object")
    return crc32_update(data, 0)
