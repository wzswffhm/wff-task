"""流式读取。

``iter_segments`` 惰性地产出段：它只用固定大小的 ``read(n)`` 向文件对象
要数据，绝不会把整个容器一次性读进内存。取完最后一段之后，仍会读取并
校验尾部索引与尾部校验和。
"""

from __future__ import annotations

import struct

from .crc import crc32_update
from .errors import WSegError
from .header import HEADER_SIZE, parse_header
from .index import INDEX_ENTRY_SIZE, parse_index
from .segment import SEGMENT_HEADER_SIZE, parse_segment_header, padding_for

TRAILER_SIZE = 8

_TRAILER = struct.Struct("<II")


def _read_exact(handle, size: int, what: str) -> bytes:
    """从 ``handle`` 精确读取 ``size`` 字节；读不够则抛 truncated。"""
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = handle.read(remaining)
        if chunk is None:
            raise WSegError("structure", f"the stream returned None while reading {what}")
        if isinstance(chunk, str):
            raise WSegError("structure", "the stream returned text, expected bytes")
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise WSegError("structure",
                            f"the stream returned {type(chunk).__name__}, expected bytes")
        chunk = bytes(chunk)
        if not chunk:
            raise WSegError(
                "truncated",
                f"the stream ended early while reading {what} "
                f"({size - remaining}/{size} bytes)",
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def iter_segments(handle):
    """产出 (seg_id, payload)；惰性读取，结尾校验索引与校验和。"""
    header = _read_exact(handle, HEADER_SIZE, "the header")
    _version, _flags, seg_count, index_offset = parse_header(header)
    if index_offset < HEADER_SIZE:
        raise WSegError("structure", f"index offset {index_offset} overlaps the header")

    data_crc = crc32_update(header)

    cursor = HEADER_SIZE
    for index in range(seg_count):
        head = _read_exact(handle, SEGMENT_HEADER_SIZE, f"segment {index} header")
        data_crc = crc32_update(head, data_crc)
        seg_id, _seg_flags, body_len = parse_segment_header(head, 0, SEGMENT_HEADER_SIZE)
        payload = _read_exact(handle, body_len, f"segment {index} payload")
        data_crc = crc32_update(payload, data_crc)
        pad = padding_for(body_len)
        if pad:
            padding = _read_exact(handle, pad, f"segment {index} padding")
            data_crc = crc32_update(padding, data_crc)
        cursor += SEGMENT_HEADER_SIZE + body_len + pad
        yield seg_id, payload

    if cursor != index_offset:
        raise WSegError(
            "structure",
            f"the segment region ends at {cursor} but the index starts at {index_offset}",
        )

    index_region = _read_exact(handle, INDEX_ENTRY_SIZE * seg_count, "the index")
    entries = parse_index(index_region, 0, seg_count)
    expected = HEADER_SIZE
    for index, (entry_offset, entry_length) in enumerate(entries):
        if entry_offset != expected:
            raise WSegError(
                "structure",
                f"index entry {index} points at {entry_offset}, expected {expected}",
            )
        expected += entry_length
    if expected != index_offset:
        raise WSegError(
            "structure",
            f"the index covers {expected - HEADER_SIZE} segment bytes, "
            f"expected {index_offset - HEADER_SIZE}",
        )

    trailer = _read_exact(handle, TRAILER_SIZE, "the trailer")
    index_crc, data_crc_expected = _TRAILER.unpack(trailer)
    if crc32_update(index_region) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
    if data_crc != data_crc_expected:
        raise WSegError("checksum", "the segment region does not match its checksum")


def read_all(handle) -> list:
    """把结果收成一个列表。"""
    return [item for item in iter_segments(handle)]
