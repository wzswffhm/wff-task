"""容器尾部校验和使用的 32 位校验和。

容器使用标准的 CRC-32（IEEE 802.3，即 zlib / PNG / gzip 所用的那一个）：
反射多项式 0xEDB88320、初值 0xFFFFFFFF、输出再取反。``zlib.crc32`` 正是
这个变体，因此直接委托给它即可，常见测试向量成立::

    compute_crc(b"") == 0x00000000
    compute_crc(b"123456789") == 0xCBF43926
    compute_crc(b"The quick brown fox jumps over the lazy dog") == 0x414FA339
"""

from __future__ import annotations

import zlib


def crc32_update(data, value: int = 0) -> int:
    """在 ``value`` 的基础上继续累积校验和。

    满足增量性质 ``crc32_update(b, crc32_update(a)) == compute_crc(a + b)``，
    流式读取依赖这一点来边读边算。
    """
    if isinstance(data, str):
        raise TypeError("crc32_update expects a bytes-like object")
    return zlib.crc32(bytes(data), value & 0xFFFFFFFF) & 0xFFFFFFFF


def compute_crc(data) -> int:
    """返回容器使用的 32 位校验和（标准 CRC-32）。"""
    if isinstance(data, str):
        raise TypeError("compute_crc expects a bytes-like object")
    return crc32_update(data, 0)
