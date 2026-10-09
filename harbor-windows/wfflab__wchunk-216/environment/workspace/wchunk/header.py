"""WCHK 文件头（12 字节）—— 按草稿 FORMAT.md 实现。

草稿布局：
    +--------+---------+------------------+------------------+
    | 0..4   | 4       | 5..9             | 9..12            |
    | "WCHK" | version | record_count u32 | reserved         |
    +--------+---------+------------------+------------------+

草稿写明 record_count 是**大端 u32**。
"""

from __future__ import annotations

import struct

from .errors import WChunkError

MAGIC = b"WCHK"
VERSION = 0x02
HEADER_SIZE = 12


def build_header(record_count: int) -> bytes:
    if record_count < 0:
        raise WChunkError("structure", "record_count must be non-negative")
    return MAGIC + bytes([VERSION]) + struct.pack(">I", record_count) + b"\x00\x00\x00"


def parse_header(data: bytes) -> tuple[int, int]:
    """校验并解析文件头，返回 (version, record_count)（count 按大端读取）。"""
    if len(data) < HEADER_SIZE:
        raise WChunkError("truncated", f"header needs {HEADER_SIZE} bytes, got {len(data)}")
    if data[:4] != MAGIC:
        raise WChunkError("magic", f"bad magic {data[:4]!r}, expected {MAGIC!r}")
    version = data[4]
    if version != VERSION:
        raise WChunkError("version", f"unsupported version {version}, expected {VERSION}")
    if data[9:12] != b"\x00\x00\x00":
        raise WChunkError("structure", "reserved header bytes must be zero")
    (record_count,) = struct.unpack(">I", data[5:9])
    return version, record_count
