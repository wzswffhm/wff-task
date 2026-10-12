"""容器尾部校验和。"""

from __future__ import annotations

import struct

__all__ = ["CRC_SIZE", "compute_crc", "pack_crc", "unpack_crc"]

CRC_SIZE = 4

_POLY = 0xEDB88320


def _build_table():
    table = []
    for index in range(256):
        crc = index
        for _ in range(8):
            crc = (crc >> 1) ^ (_POLY if crc & 1 else 0)
        table.append(crc)
    return table


_TABLE = _build_table()


def compute_crc(data):
    """返回 ``data`` 的 32 位校验和。"""
    crc = 0xFFFFFFFF
    for byte in data:
        crc = (crc >> 8) ^ _TABLE[(crc ^ byte) & 0xFF]
    return crc & 0xFFFFFFFF


def pack_crc(value):
    """把校验和打包成 4 字节。"""
    return struct.pack("<I", value & 0xFFFFFFFF)


def unpack_crc(buf, pos=0):
    """从 ``buf[pos:pos+4]`` 解出校验和。"""
    if pos + CRC_SIZE > len(buf):
        raise ValueError("校验和字段不完整")
    return struct.unpack_from("<I", buf, pos)[0]
