"""流式读取：只使用固定大小的 read(n)，从不整体读取。"""

from __future__ import annotations

import struct

from .crc import crc32_update
from .errors import WSegError
from .header import HEADER_SIZE, parse_header
from .index import INDEX_ENTRY_SIZE
from .segment import SEGMENT_HEADER_SIZE, parse_segment_header, segment_length

TRAILER_SIZE = 8

_CHUNK = 8192

_TRAILER = struct.Struct("<II")


def _read_exact(handle, size: int, what: str) -> bytes:
    """按固定大小分块取足 ``size`` 字节；不足即报 truncated。"""
    if size < 0:
        raise WSegError("truncated", f"{what} claims a negative size")
    chunks = []
    remaining = size
    while remaining > 0:
        chunk = handle.read(min(remaining, _CHUNK))
        if chunk is None:
            raise WSegError("truncated", f"{what} is incomplete")
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise WSegError("structure", f"reading {what} returned {type(chunk).__name__}")
        if len(chunk) == 0:
            raise WSegError("truncated", f"{what} is incomplete")
        data = bytes(chunk)
        chunks.append(data)
        remaining -= len(data)
    return b"".join(chunks)


def iter_segments(handle):
    """惰性产出 (seg_id, payload)；最后一段之后校验索引与尾部校验和。"""
    header = _read_exact(handle, HEADER_SIZE, "the header")
    _version, _flags, seg_count, index_offset = parse_header(header)
    if index_offset < HEADER_SIZE:
        raise WSegError("structure", f"index offset {index_offset} points inside the header")

    data_crc = crc32_update(header)
    cursor = HEADER_SIZE
    for index in range(seg_count):
        head = _read_exact(handle, SEGMENT_HEADER_SIZE, f"segment {index} header")
        seg_id, _seg_flags, body_len = parse_segment_header(head, 0, len(head))
        total = segment_length(body_len)
        payload = _read_exact(handle, body_len, f"segment {index} payload")
        pad = _read_exact(handle, total - SEGMENT_HEADER_SIZE - body_len,
                          f"segment {index} padding")
        if cursor + total > index_offset:
            raise WSegError("structure",
                            f"segment {index} runs past the index region at {index_offset}")
        data_crc = crc32_update(head + payload + pad, data_crc)
        cursor += total
        yield seg_id, payload

    if cursor != index_offset:
        raise WSegError("structure",
                        f"segments end at {cursor} but the index starts at {index_offset}")

    index_region = _read_exact(handle, INDEX_ENTRY_SIZE * seg_count, "the index")
    trailer = _read_exact(handle, TRAILER_SIZE, "the trailer")
    if handle.read(1):
        raise WSegError("structure", "trailing bytes after the trailer")

    index_crc, expected_data_crc = _TRAILER.unpack(trailer)
    if data_crc != expected_data_crc:
        raise WSegError("checksum", "the segment region does not match its checksum")
    if crc32_update(index_region) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")


def read_all(handle) -> list:
    """把流式结果收成一个列表。"""
    return [item for item in iter_segments(handle)]
