"""容器尾部校验和使用的 32 位校验和。

容器使用的是**标准的 CRC-32/ISO-HDLC**（反射多项式 ``0xEDB88320``，初值与
最终异或均为 ``0xFFFFFFFF``，低位字节在前），也就是 ``zlib.crc32`` 以及
gzip / zip / PNG 所使用的算法。因此校验值是数据的确定性函数，对任意输入都
能与常见工具直接对照，例如::

    compute_crc(b"123456789") == 0xCBF43926
    compute_crc(b"") == 0
"""

from __future__ import annotations

import zlib

#: 32 位结果的掩码。
MASK = 0xFFFFFFFF


def crc32_update(data, value: int = 0) -> int:
    """在 ``value`` 的基础上继续累积校验和。

    满足增量不变式：对任意字节串 ``a`` / ``b``，

    ``crc32_update(b, crc32_update(a)) == compute_crc(a + b)``
    """
    if isinstance(data, str):
        raise TypeError("crc32_update expects a bytes-like object, not str")
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("crc32_update expects an integer CRC value")
    return zlib.crc32(bytes(data), value & MASK) & MASK


def compute_crc(data) -> int:
    """返回容器使用的 32 位校验和（标准 CRC-32/ISO-HDLC）。"""
    if isinstance(data, str):
        raise TypeError("compute_crc expects a bytes-like object, not str")
    return crc32_update(data, 0)
