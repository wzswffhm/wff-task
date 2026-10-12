"""标准 CRC-32（ISO-HDLC / zlib.crc32）。

关键语义：初值 0xFFFFFFFF、反射多项式 0xEDB88320、**最终异或 0xFFFFFFFF**。
这是 zlib.crc32 的定义，对任意输入都成立 —— 不是「只对样本成立」的特例，
也不允许改成「初值 0xFFFFFFFF 但不做最终异或」那类变体。

标准测试向量（必须成立）：
    b""            -> 0x00000000
    b"a"           -> 0xE8B7BE43
    b"123456789"   -> 0xCBF43926
"""

from __future__ import annotations

import zlib


def compute_crc(data: bytes) -> int:
    """返回 data 的标准 CRC-32 值（0..0xFFFFFFFF）。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("compute_crc expects bytes-like input")
    return zlib.crc32(data) & 0xFFFFFFFF
