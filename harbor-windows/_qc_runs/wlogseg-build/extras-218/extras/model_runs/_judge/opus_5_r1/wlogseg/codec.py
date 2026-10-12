"""容器整体读写：文件头、段区、尾部索引与尾部校验和。

实际布局（以 ``assets/`` 下的样本为准）::

    +----------------+  0
    | 文件头 16 字节 |
    +----------------+  HEADER_SIZE
    | 段区           |  每段 8 字节段头 + 数据，整体对齐到 8 字节
    +----------------+  index_offset
    | 尾部索引       |  seg_count 个 8 字节条目：(offset, length)
    +----------------+
    | 尾部校验和     |  8 字节：索引区 CRC-32、文件头+段区 CRC-32
    +----------------+

两个校验和都是标准 CRC-32（见 ``wlogseg.crc``）；第二个覆盖文件头与整个段区
（含对齐填充）。
"""

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
MAX_SEG_COUNT = 0xFFFF

_TRAILER = struct.Struct("<II")


def _normalize(segments):
    """校验并规整输入的 (seg_id, payload) 序列。"""
    try:
        iterator = iter(segments)
    except TypeError:
        raise WSegError("structure", "pack expects an iterable of (seg_id, payload)") from None

    items = []
    for record in iterator:
        if isinstance(record, (bytes, bytearray, str)):
            raise WSegError("structure", f"{record!r} is not a (seg_id, payload) pair")
        try:
            seg_id, payload = record
        except (TypeError, ValueError):
            raise WSegError("structure", f"{record!r} is not a (seg_id, payload) pair") from None
        if (not isinstance(seg_id, int) or isinstance(seg_id, bool)
                or not 0 <= seg_id <= MAX_SEG_ID):
            raise WSegError("structure", f"segment id {seg_id!r} out of range")
        if isinstance(payload, str) or not isinstance(payload, (bytes, bytearray, memoryview)):
            raise WSegError("structure", f"payload {type(payload).__name__} is not bytes")
        body = bytes(payload)
        if len(body) > MAX_BODY:
            raise WSegError("structure", "payload is too large")
        items.append((seg_id, body))

    if len(items) > MAX_SEG_COUNT:
        raise WSegError("structure", f"too many segments: {len(items)}")
    return items


def pack(segments) -> bytes:
    """把 [(seg_id, payload), ...] 序列化为 WLSG 字节串。"""
    items = _normalize(segments)

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
                            compute_crc(header + bytes(body)))
    return header + bytes(body) + index_region + trailer


def unpack(data) -> list:
    """解析 WLSG 字节串；任何结构 / 完整性问题都抛 WSegError。"""
    if isinstance(data, str) or not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"unpack expects bytes, got {type(data).__name__}")
    blob = bytes(data)

    _version, _flags, seg_count, index_offset = parse_header(blob)

    if index_offset < HEADER_SIZE:
        raise WSegError("structure", f"index offset {index_offset} overlaps the header")

    index_end = index_offset + INDEX_ENTRY_SIZE * seg_count
    total = index_end + TRAILER_SIZE
    if len(blob) < total:
        raise WSegError("truncated",
                        f"container needs {total} bytes, got {len(blob)}")
    if len(blob) > total:
        raise WSegError("structure",
                        f"container has {len(blob) - total} trailing bytes")

    records = []
    entries = []
    cursor = HEADER_SIZE
    for position in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > index_offset:
            raise WSegError("structure",
                            f"segment {position} does not fit in the segment region")
        seg_id, _seg_flags, body_len = parse_segment_header(blob, cursor, index_offset)
        start = cursor + SEGMENT_HEADER_SIZE
        stride = segment_length(body_len)
        if cursor + stride > index_offset:
            raise WSegError("structure",
                            f"segment {position} does not fit in the segment region")
        records.append((seg_id, blob[start:start + body_len]))
        entries.append((cursor, stride))
        cursor += stride

    if cursor != index_offset:
        raise WSegError("structure",
                        f"the segment region ends at {cursor}, index starts at {index_offset}")

    index_crc, data_crc = _TRAILER.unpack_from(blob, total - TRAILER_SIZE)
    if compute_crc(blob[index_offset:index_end]) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
    if compute_crc(blob[:index_offset]) != data_crc:
        raise WSegError("checksum", "the segment region does not match its checksum")

    if parse_index(blob, index_offset, seg_count) != entries:
        raise WSegError("structure", "the index does not match the segment region")
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
