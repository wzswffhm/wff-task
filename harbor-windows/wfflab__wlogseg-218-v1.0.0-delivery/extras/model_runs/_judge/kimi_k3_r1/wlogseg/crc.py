"""容器尾部校验和使用的 32 位校验和。

容器使用标准的 CRC-32（即 ``zlib.crc32`` 实现的 ISO-HDLC 变体）：
初始值 0xFFFFFFFF、按位反射、最终异或 0xFFFFFFFF——这些都已经包含在
``zlib.crc32`` 的返回值里，不要再做额外的异或。
"""

from __future__ import annotations

import zlib


def crc32_update(data, value: int = 0) -> int:
    """在 ``value`` 的基础上继续累积校验和。"""
    return zlib.crc32(bytes(data), value) & 0xFFFFFFFF


def compute_crc(data) -> int:
    """返回容器使用的 32 位校验和。"""
    if isinstance(data, str):
        raise TypeError("compute_crc expects a bytes-like object")
    return crc32_update(data, 0)
