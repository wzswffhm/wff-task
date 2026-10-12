"""容器尾部校验和使用的 32 位校验和。

使用的算法是通用的 CRC-32（CRC-32/ISO-HDLC，即 zip / png / zlib 用的那一个）：
多项式 0x04C11DB7（反射后 0xEDB88320），初值 0xFFFFFFFF，输入输出均反射，
最终异或 0xFFFFFFFF。``zlib.crc32`` 正是这个变体，所以直接复用它，
并且保证 ``crc32_update`` 可以分块累积：

    compute_crc(a + b) == crc32_update(b, crc32_update(a, 0))
"""

from __future__ import annotations

import zlib


def crc32_update(data, value: int = 0) -> int:
    """在 ``value`` 的基础上继续累积校验和。

    ``value`` 为 0 时等价于从头开始计算，因此可以用来流式分块累积。
    """
    if isinstance(data, str):
        raise TypeError("crc32_update expects a bytes-like object")
    return zlib.crc32(bytes(data), value & 0xFFFFFFFF) & 0xFFFFFFFF


def compute_crc(data) -> int:
    """返回容器使用的 32 位校验和（标准 CRC-32）。"""
    if isinstance(data, str):
        raise TypeError("compute_crc expects a bytes-like object")
    return crc32_update(data, 0)
