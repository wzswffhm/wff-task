"""容器尾部校验和使用的 32 位校验和。

使用的是通用的 CRC-32（IEEE 802.3 / zlib 变体，多项式 0x04C11DB7，
初值 0xFFFFFFFF，输入输出反射，最终异或 0xFFFFFFFF）。
``compute_crc(b"123456789") == 0xCBF43926``。
"""

from __future__ import annotations

import zlib


def crc32_update(data, value: int = 0) -> int:
    """在 ``value`` 的基础上继续累积校验和。

    ``crc32_update(b)`` 等于 ``compute_crc(b)``，并且
    ``crc32_update(b2, crc32_update(b1)) == compute_crc(b1 + b2)``，
    因此可以用于流式计算。
    """
    if isinstance(data, str):
        raise TypeError("crc32_update expects a bytes-like object")
    return zlib.crc32(bytes(data), value & 0xFFFFFFFF) & 0xFFFFFFFF


def compute_crc(data) -> int:
    """返回容器使用的 32 位校验和。"""
    if isinstance(data, str):
        raise TypeError("compute_crc expects a bytes-like object")
    return crc32_update(data, 0)
