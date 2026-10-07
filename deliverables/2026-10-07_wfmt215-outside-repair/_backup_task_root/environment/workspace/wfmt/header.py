"""容器文件头。"""

from __future__ import annotations

import struct

from .errors import WFormatError

__all__ = ["MAGIC", "VERSION", "HEADER_SIZE", "pack_header", "parse_header"]

MAGIC = b"WFMT"
VERSION = 1
HEADER_SIZE = 9


def pack_header(count):
    """打包文件头。"""
    return MAGIC + bytes([VERSION]) + struct.pack(">I", count)


def parse_header(data):
    """解析文件头，返回 ``(version, count)``。"""
    if len(data) < HEADER_SIZE:
        raise WFormatError("truncated", "文件头不完整")
    if data[:4] != MAGIC:
        raise WFormatError("magic", "魔数不匹配")
    version = data[4]
    if version != VERSION:
        raise WFormatError("version", "不支持的版本号 %r" % (version,))
    count = struct.unpack_from(">I", data, 5)[0]
    return version, count
