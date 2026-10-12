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

    offsets = []
    lengths = []
    body = bytearray()
    cursor = HEADER_SIZE
    for seg_id, payload in items:
        total = segment_length(len(payload))
        offsets.append(cursor)
        lengths.append(total)
        body += encode_segment(seg_id, payload)
        cursor += total

    index_offset = cursor
    header = build_header(len(items), index_offset)
    index_region = build_index(offsets, lengths)
    data_region = bytes(header) + bytes(body)
    trailer = _TRAILER.pack(compute_crc(index_region), compute_crc(data_region))
    return data_region + index_region + trailer


def unpack(data) -> list:
    """解析 WLSG 字节串；任何结构 / 完整性问题都抛 WSegError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)

    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        raise WSegError("structure",
                        f"need at least {HEADER_SIZE + TRAILER_SIZE} bytes, got {len(data)}")

    _version, _flags, seg_count, index_offset = parse_header(data)

    if index_offset < HEADER_SIZE:
        raise WSegError("structure", f"index offset {index_offset} points inside the header")
    if index_offset > len(data):
        raise WSegError("structure",
                        f"index region starts at {index_offset} but the file ends at {len(data)}")
    index_end = index_offset + INDEX_ENTRY_SIZE * seg_count
    if index_end + TRAILER_SIZE > len(data):
        raise WSegError("structure",
                        f"index and trailer need {index_end + TRAILER_SIZE} bytes, got {len(data)}")
    if index_end + TRAILER_SIZE != len(data):
        raise WSegError("structure",
                        f"{len(data) - index_end - TRAILER_SIZE} trailing bytes after the trailer")

    records = []
    offsets = []
    lengths = []
    cursor = HEADER_SIZE
    for index in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > len(data):
            raise WSegError("structure", f"segment {index} header is incomplete")
        seg_id, _seg_flags, body_len = parse_segment_header(data, cursor, len(data))
        total = segment_length(body_len)
        if cursor + total > len(data):
            raise WSegError("structure",
                            f"segment {index} declares {body_len} payload bytes that are not there")
        if cursor + total > index_offset:
            raise WSegError("structure",
                            f"segment {index} runs past the index region at {index_offset}")
        start = cursor + SEGMENT_HEADER_SIZE
        records.append((seg_id, data[start:start + body_len]))
        offsets.append(cursor)
        lengths.append(total)
        cursor += total

    if cursor != index_offset:
        raise WSegError("structure",
                        f"segments end at {cursor} but the index starts at {index_offset}")

    if parse_index(data, index_offset, seg_count) != list(zip(offsets, lengths)):
        raise WSegError("structure", "index entries do not describe the segment region")

    index_crc, data_crc = _TRAILER.unpack_from(data, len(data) - TRAILER_SIZE)
    if compute_crc(data[:index_offset]) != data_crc:
        raise WSegError("checksum", "the segment region does not match its checksum")
    if compute_crc(data[index_offset:index_end]) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
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
