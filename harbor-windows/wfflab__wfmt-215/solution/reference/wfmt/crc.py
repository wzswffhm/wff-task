"""容器尾部校验和：CRC-32/ISO-HDLC。"""

from __future__ import annotations

import struct
import zlib

__all__ = ["CRC_SIZE", "compute_crc", "pack_crc", "unpack_crc"]

CRC_SIZE = 4


def compute_crc(data):
    """返回 ``data`` 的 CRC-32/ISO-HDLC 值（0 ~ 2**32-1）。"""
    return zlib.crc32(data) & 0xFFFFFFFF


def pack_crc(value):
    """把 CRC 值打包成 4 字节小端。"""
    return struct.pack("<I", value & 0xFFFFFFFF)


def unpack_crc(buf, pos=0):
    """从 ``buf[pos:pos+4]`` 解出 CRC 值。"""
    if pos + CRC_SIZE > len(buf):
        raise ValueError("CRC 字段不完整")
    return struct.unpack_from("<I", buf, pos)[0]
