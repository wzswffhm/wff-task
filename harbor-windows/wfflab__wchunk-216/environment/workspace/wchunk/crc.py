"""CRC-32 校验和 —— 按草稿 FORMAT.md 的取值方式实现。

草稿：「初值 0xFFFFFFFF、查表法、**不做最终异或**」。
因此这里对 zlib 的结果再取一次反，得到草稿描述的那类变体
（与 zlib.crc32 / 标准 CRC-32/ISO-HDLC 差一个最终取反）。
"""

from __future__ import annotations

import zlib

from .errors import WChunkError


def compute_crc(data: bytes) -> int:
    """返回 data 的 CRC-32（初值 0xFFFFFFFF、**无最终异或**）。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WChunkError("structure", f"compute_crc expects bytes, got {type(data).__name__}")
    return zlib.crc32(data) ^ 0xFFFFFFFF
