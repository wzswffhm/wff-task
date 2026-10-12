"""流式读取。

``iter_segments`` 只用固定大小的 ``read(n)``（``n`` 为正整数）向文件对象要
数据，不会把整个容器读进内存；段是惰性产出的。取完最后一段后仍会校验尾部
索引与尾部校验和。
"""

from __future__ import annotations

import struct

from .crc import crc32_update
from .errors import WSegError
from .header import HEADER_SIZE, parse_header
from .index import INDEX_ENTRY_SIZE
from .segment import SEGMENT_HEADER_SIZE, parse_segment_header, segment_length

TRAILER_SIZE = 8
CHUNK_SIZE = 65536

_TRAILER = struct.Struct("<II")
_ENTRY = struct.Struct("<II")


def _read_exactly(handle, count: int, what: str) -> bytes:
    """固定大小地读 ``count`` 字节；读不满就是 truncated。"""
    if count <= 0:
        return b""
    out = bytearray()
    while len(out) < count:
        chunk = handle.read(min(CHUNK_SIZE, count - len(out)))
        if isinstance(chunk, str) or not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise WSegError("structure", f"the stream returned {type(chunk).__name__}")
        chunk = bytes(chunk)
        if not chunk:
            raise WSegError("truncated",
                            f"{what} needs {count} bytes, got {len(out)}")
        out += chunk
    return bytes(out)


def iter_segments(handle):
    """惰性产出 (seg_id, payload)，并在读完后校验尾部索引与校验和。"""
    if not hasattr(handle, "read"):
        raise WSegError("structure", f"{type(handle).__name__} is not a file object")

    header = _read_exactly(handle, HEADER_SIZE, "header")
    _version, _flags, seg_count, index_offset = parse_header(header)
    if index_offset < HEADER_SIZE:
        raise WSegError("structure", f"index offset {index_offset} overlaps the header")

    data_crc = crc32_update(header)
    entries = []
    cursor = HEADER_SIZE
    for position in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > index_offset:
            raise WSegError("structure",
                            f"segment {position} does not fit in the segment region")
        head = _read_exactly(handle, SEGMENT_HEADER_SIZE, f"segment {position} header")
        data_crc = crc32_update(head, data_crc)
        seg_id, _seg_flags, body_len = parse_segment_header(head, 0, SEGMENT_HEADER_SIZE)
        stride = segment_length(body_len)
        if cursor + stride > index_offset:
            raise WSegError("structure",
                            f"segment {position} does not fit in the segment region")
        rest = _read_exactly(handle, stride - SEGMENT_HEADER_SIZE, f"segment {position} payload")
        data_crc = crc32_update(rest, data_crc)
        entries.append((cursor, stride))
        cursor += stride
        yield seg_id, rest[:body_len]

    if cursor != index_offset:
        raise WSegError("structure",
                        f"the segment region ends at {cursor}, index starts at {index_offset}")

    index_region = _read_exactly(handle, INDEX_ENTRY_SIZE * seg_count, "index")
    trailer = _read_exactly(handle, TRAILER_SIZE, "trailer")
    extra = handle.read(1)
    if isinstance(extra, (bytes, bytearray, memoryview)) and bytes(extra):
        raise WSegError("structure", "the container has trailing bytes")

    index_crc, expected_data_crc = _TRAILER.unpack(trailer)
    if crc32_update(index_region) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
    if data_crc != expected_data_crc:
        raise WSegError("checksum", "the segment region does not match its checksum")

    found = [_ENTRY.unpack_from(index_region, i * INDEX_ENTRY_SIZE) for i in range(seg_count)]
    if found != entries:
        raise WSegError("structure", "the index does not match the segment region")


def read_all(handle) -> list:
    """把结果收成一个列表。"""
    return [item for item in iter_segments(handle)]
