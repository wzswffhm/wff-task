"""容器尾部校验和使用的 32 位校验和（标准 CRC-32）。"""

from __future__ import annotations

import zlib


def crc32_update(data, value: int = 0) -> int:
    """在 ``value`` 的基础上继续累积 CRC-32 校验和。

    注意：zlib.crc32 本身已经实现了增量接口，传入前一次的返回值即可。
    初始值应为 0；返回值为无符号 32 位整数。
    """
    return zlib.crc32(bytes(data), value) & 0xFFFFFFFF


def compute_crc(data) -> int:
    """返回容器使用的 32 位 CRC 校验和（标准 CRC-32）。"""
    if isinstance(data, str):
        raise TypeError("compute_crc expects a bytes-like object")
    return zlib.crc32(bytes(data)) & 0xFFFFFFFF
