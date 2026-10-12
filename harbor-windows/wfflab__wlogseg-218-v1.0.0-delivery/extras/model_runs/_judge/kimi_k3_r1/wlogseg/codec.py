"""容器整体读写：文件头、段区、尾部索引与尾部校验和。"""

from __future__ import annotations

import struct

from .crc import compute_crc
from .errors import WSegError
from .header import HEADER_SIZE, build_header, parse_header
from .index import INDEX_ENTRY_SIZE, build_index, parse_index
from .segment import (
    MAX_BODY,
    MAX_SEG_ID,
    SEGMENT_HEADER_SIZE,
    encode_segment,
    parse_segment_header,
    segment_length,
)

TRAILER_SIZE = 8

_TRAILER = struct.Struct("<II")


def pack(segments) -> bytes:
    """把 [(seg_id, payload), ...] 序列化为 WLSG 字节串。"""
    items = []
    for seg_id, payload in segments:
        if not isinstance(seg_id, int) or isinstance(seg_id, bool) or not 0 <= seg_id <= MAX_SEG_ID:
            raise WSegError("structure", f"segment id {seg_id!r} out of range")
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise WSegError("structure", f"payload {type(payload).__name__} is not bytes")
        body = bytes(payload)
        if len(body) > MAX_BODY:
            raise WSegError("structure", "payload is too large")
        items.append((seg_id, body))

    entries = []
    body = bytearray()
    cursor = HEADER_SIZE
    for seg_id, payload in items:
        encoded = encode_segment(seg_id, payload)
        entries.append((cursor, len(encoded)))
        body += encoded
        cursor += len(encoded)

    index_offset = cursor
    header = build_header(len(items), index_offset)
    index_region = build_index(entries)
    trailer = _TRAILER.pack(compute_crc(index_region),
                            compute_crc(bytes(header) + bytes(body)))
    return bytes(header) + bytes(body) + index_region + trailer


def unpack(data) -> list:
    """解析 WLSG 字节串；任何结构 / 完整性问题都抛 WSegError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)

    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        raise WSegError("truncated", f"container is only {len(data)} bytes")

    _version, _flags, seg_count, index_offset = parse_header(data)

    if index_offset < HEADER_SIZE:
        raise WSegError("structure", f"index offset {index_offset} overlaps the header")
    index_end = index_offset + INDEX_ENTRY_SIZE * seg_count
    if index_end > len(data):
        raise WSegError("truncated", "the index region extends beyond the container")
    if index_end + TRAILER_SIZE > len(data):
        raise WSegError("truncated", "the trailer is incomplete")
    if index_end + TRAILER_SIZE != len(data):
        raise WSegError("structure", "trailing bytes after the trailer")

    entries = parse_index(data, index_offset, seg_count)

    records = []
    cursor = HEADER_SIZE
    for index in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > index_offset:
            raise WSegError("truncated", f"segment {index} header is incomplete")
        seg_id, _seg_flags, body_len = parse_segment_header(data, cursor, index_offset)
        start = cursor + SEGMENT_HEADER_SIZE
        if start + body_len > index_offset:
            raise WSegError("truncated", f"segment {index} payload is incomplete")
        total = segment_length(body_len)
        if cursor + total > index_offset:
            raise WSegError("truncated", f"segment {index} padding is incomplete")
        entry_offset, entry_length = entries[index]
        if entry_offset != cursor or entry_length != total:
            raise WSegError(
                "structure",
                f"segment {index} disagrees with the index "
                f"(index says offset={entry_offset} length={entry_length}, "
                f"walked offset={cursor} length={total})",
            )
        records.append((seg_id, data[start:start + body_len]))
        cursor += total

    if cursor != index_offset:
        raise WSegError(
            "structure",
            f"the segment region ends at {cursor} but the index starts at {index_offset}",
        )

    index_crc, data_crc = _TRAILER.unpack_from(data, index_end)
    if compute_crc(data[index_offset:index_end]) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
    if compute_crc(data[:index_offset]) != data_crc:
        raise WSegError("checksum", "the segment region does not match its checksum")
    return records


def verify(data) -> bool:
    """返回 data 是否是合法 WLSG 容器；**永不抛异常**。"""
    try:
        unpack(data)
        return True
    except WSegError:
        return False
    except Exception:  # noqa: BLE001
        return False
