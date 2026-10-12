"""流式读取。

``iter_segments`` 只用固定大小的 ``read(n)``（``n`` 为正整数）向文件对象要
数据，不会把整个容器读进内存：段数据按段逐个读取，尾部索引按条目逐个读取。
"""

from __future__ import annotations

import struct

from .codec import TRAILER_SIZE
from .crc import crc32_update
from .errors import WSegError
from .header import HEADER_SIZE, parse_header
from .index import INDEX_ENTRY_SIZE, decode_index_entry
from .segment import SEGMENT_HEADER_SIZE, decode_segment_header, padding_for, segment_length

_TRAILER = struct.Struct("<II")

_CHUNK = 65536


def _read_exact(handle, count: int, what: str) -> bytes:
    """精确读取 ``count`` 字节；不足则抛 truncated。

    只使用带正整数参数的 ``read(n)``，并容忍短读。
    """
    if count == 0:
        return b""
    out = bytearray()
    while len(out) < count:
        chunk = handle.read(min(count - len(out), _CHUNK))
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise WSegError("structure",
                            f"the stream returned {type(chunk).__name__} while reading {what}")
        chunk = bytes(chunk)
        if not chunk:
            raise WSegError("truncated",
                            f"the stream ended while reading {what}: "
                            f"wanted {count} bytes, got {len(out)}")
        out += chunk
    return bytes(out)


def _skip_exact(handle, count: int, what: str) -> bytes:
    """读掉并返回 ``count`` 字节（用于填充，量很小）。"""
    return _read_exact(handle, count, what)


def iter_segments(handle):
    """惰性产出 (seg_id, payload)。

    取完最后一段后仍会校验尾部索引与尾部校验和，失败时抛
    ``WSegError``（校验和不符为 ``kind="checksum"``）。
    """
    header = _read_exact(handle, HEADER_SIZE, "the file header")
    _version, _flags, seg_count, index_offset = parse_header(header)

    if index_offset < HEADER_SIZE:
        raise WSegError("structure", f"index offset {index_offset} overlaps the header")

    region_crc = crc32_update(header, 0)
    entries = []
    cursor = HEADER_SIZE

    for number in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > index_offset:
            raise WSegError("structure",
                            f"segment {number} header crosses the segment region")
        seg_head = _read_exact(handle, SEGMENT_HEADER_SIZE, f"segment {number} header")
        seg_id, _seg_flags, body_len = decode_segment_header(seg_head)
        total = segment_length(body_len)
        if cursor + total > index_offset:
            raise WSegError("structure", f"segment {number} runs past the segment region")
        payload = _read_exact(handle, body_len, f"segment {number} payload")
        pad = _skip_exact(handle, padding_for(body_len), f"segment {number} padding")
        region_crc = crc32_update(seg_head, region_crc)
        region_crc = crc32_update(payload, region_crc)
        region_crc = crc32_update(pad, region_crc)
        entries.append((cursor, total))
        cursor += total
        yield seg_id, payload

    if cursor != index_offset:
        raise WSegError("structure",
                        f"segment region ends at {cursor}, index starts at {index_offset}")

    # 尾部索引逐条读取并累积校验和。
    index_crc = 0
    read_entries = []
    for number in range(seg_count):
        chunk = _read_exact(handle, INDEX_ENTRY_SIZE, f"index entry {number}")
        index_crc = crc32_update(chunk, index_crc)
        read_entries.append(decode_index_entry(chunk))

    trailer = _read_exact(handle, TRAILER_SIZE, "the trailer")
    want_index_crc, want_region_crc = _TRAILER.unpack_from(trailer, 0)
    if index_crc != want_index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
    if region_crc != want_region_crc:
        raise WSegError("checksum", "the segment region does not match its checksum")
    if read_entries != entries:
        raise WSegError("structure", "the index does not agree with the segment layout")


def read_all(handle) -> list:
    """把结果收成一个列表。"""
    return list(iter_segments(handle))
