"""流式读取。

``iter_segments`` 惰性地逐段产出数据：只用固定大小的 ``read(n)``（``n`` 为
正整数）向文件对象要字节，绝不会把整个容器读进内存。取完最后一段后仍会
读取并校验尾部索引与尾部校验和。
"""

from __future__ import annotations

import struct

from .crc import crc32_update
from .errors import WSegError
from .header import HEADER_SIZE, parse_header
from .index import INDEX_ENTRY_SIZE, index_region_size
from .segment import SEGMENT_HEADER_SIZE, padding_for, unpack_segment_header

#: 读取段数据时单次 read 的上限，保证内存占用固定。
CHUNK_SIZE = 65536

TRAILER_SIZE = 8

_TRAILER = struct.Struct("<II")
_ENTRY = struct.Struct("<II")


def _read_exactly(handle, size: int) -> bytes:
    """读满 ``size`` 字节，不足即为 truncated。``size`` 始终为正。"""
    out = bytearray()
    while len(out) < size:
        chunk = handle.read(size - len(out))
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise WSegError("structure",
                            f"the stream returned {type(chunk).__name__}")
        chunk = bytes(chunk)
        if not chunk:
            raise WSegError("truncated",
                            f"needed {size} bytes, got {len(out)}")
        out += chunk
    return bytes(out)


def _skip_and_hash(handle, size: int, crc: int) -> int:
    """读掉 ``size`` 字节并累积校验和，不保留内容。"""
    remaining = size
    while remaining > 0:
        chunk = _read_exactly(handle, min(remaining, CHUNK_SIZE))
        crc = crc32_update(chunk, crc)
        remaining -= len(chunk)
    return crc


def iter_segments(handle):
    """惰性产出 (seg_id, payload)。"""
    if not hasattr(handle, "read"):
        raise WSegError("structure",
                        f"{type(handle).__name__} is not a readable file object")

    header = _read_exactly(handle, HEADER_SIZE)
    _version, _flags, seg_count, index_offset = parse_header(header)
    if index_offset < HEADER_SIZE:
        raise WSegError("structure",
                        f"index offset {index_offset} overlaps the header")

    crc = crc32_update(header, 0)
    cursor = HEADER_SIZE
    walked = []

    for i in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > index_offset:
            raise WSegError("structure",
                            f"segment {i} header runs past the segment region")
        head = _read_exactly(handle, SEGMENT_HEADER_SIZE)
        crc = crc32_update(head, crc)
        seg_id, _seg_flags, body_len = unpack_segment_header(head)

        pad = padding_for(body_len)
        total = SEGMENT_HEADER_SIZE + body_len + pad
        if cursor + total > index_offset:
            raise WSegError("structure",
                            f"segment {i} runs past the segment region")

        body = bytearray()
        remaining = body_len
        while remaining > 0:
            chunk = _read_exactly(handle, min(remaining, CHUNK_SIZE))
            crc = crc32_update(chunk, crc)
            body += chunk
            remaining -= len(chunk)
        if pad:
            crc = _skip_and_hash(handle, pad, crc)

        walked.append((cursor, total))
        cursor += total
        yield seg_id, bytes(body)

    if cursor != index_offset:
        raise WSegError("structure",
                        f"segment region ends at {cursor}, index starts at {index_offset}")

    index_size = index_region_size(seg_count)
    index_region = _read_exactly(handle, index_size) if index_size else b""
    trailer = _read_exactly(handle, TRAILER_SIZE)
    index_crc, data_crc = _TRAILER.unpack_from(trailer, 0)

    if crc32_update(index_region, 0) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
    if crc != data_crc:
        raise WSegError("checksum", "the segment region does not match its checksum")

    for i, found in enumerate(walked):
        declared = _ENTRY.unpack_from(index_region, i * INDEX_ENTRY_SIZE)
        if declared != found:
            raise WSegError("structure",
                            f"index entry {i} says {declared}, segments say {found}")

    extra = handle.read(1)
    if isinstance(extra, (bytes, bytearray, memoryview)) and bytes(extra):
        raise WSegError("structure", "trailing bytes after the trailer")


def read_all(handle) -> list:
    """把结果收成一个列表。"""
    return [item for item in iter_segments(handle)]
