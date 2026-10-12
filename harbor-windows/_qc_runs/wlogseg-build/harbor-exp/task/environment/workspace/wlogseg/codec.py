"""容器整体读写：文件头、段区、尾部索引与尾部校验和。"""

from __future__ import annotations

import struct

from .crc import compute_crc
from .errors import WSegError
from .header import HEADER_SIZE, build_header, parse_header
from .index import INDEX_ENTRY_SIZE, build_index
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

    offsets = []
    body = bytearray()
    checksummed = bytearray()
    cursor = HEADER_SIZE
    for seg_id, payload in items:
        encoded = encode_segment(seg_id, payload)
        offsets.append(cursor)
        body += encoded
        checksummed += encoded[:SEGMENT_HEADER_SIZE + len(payload)]
        cursor += segment_length(len(payload))

    index_offset = cursor
    header = build_header(len(items), index_offset)
    index_region = build_index(offsets)
    trailer = _TRAILER.pack(compute_crc(index_region),
                            compute_crc(bytes(header) + bytes(checksummed)))
    return bytes(header) + bytes(body) + index_region + trailer


def unpack(data) -> list:
    """解析 WLSG 字节串；任何结构 / 完整性问题都抛 WSegError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)

    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        raise WSegError("structure", f"container is only {len(data)} bytes")

    _version, _flags, seg_count, index_offset = parse_header(data)

    if index_offset > len(data):
        raise WSegError("structure", f"index offset {index_offset} is beyond the container")
    index_end = index_offset + INDEX_ENTRY_SIZE * seg_count
    if index_end + TRAILER_SIZE > len(data):
        raise WSegError("structure", "the index and the trailer do not fit")

    records = []
    checksummed = bytearray(data[:HEADER_SIZE])
    cursor = HEADER_SIZE
    for index in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > len(data):
            raise WSegError("structure", f"segment {index} header is incomplete")
        seg_id, _seg_flags, body_len = parse_segment_header(data, cursor, len(data))
        start = cursor + SEGMENT_HEADER_SIZE
        if start + body_len > len(data):
            raise WSegError("structure", f"segment {index} payload is incomplete")
        records.append((seg_id, data[start:start + body_len]))
        checksummed += data[cursor:start + body_len]
        cursor += segment_length(body_len)

    index_crc, data_crc = _TRAILER.unpack_from(data, len(data) - TRAILER_SIZE)
    if compute_crc(data[index_offset:index_end]) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
    if compute_crc(bytes(checksummed)) != data_crc:
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
