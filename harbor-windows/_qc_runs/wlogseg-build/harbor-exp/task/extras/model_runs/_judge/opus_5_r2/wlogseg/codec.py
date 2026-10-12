"""容器整体读写：文件头、段区、尾部索引与尾部校验和。

整体布局（以 ``assets/`` 下的样本为准）::

    [ 16 字节文件头 ]
    [ 段区：每段 8 字节段头 + 数据 + 填充到 8 字节对齐 ]
    [ 索引区：每段 8 字节 (起始偏移, 段总长度) ]
    [ 8 字节尾部：索引区 CRC32、文件头+段区 CRC32 ]

文件头中的「索引区偏移」等于 ``HEADER_SIZE`` 加上段区总长度。
"""

from __future__ import annotations

import struct

from .crc import compute_crc
from .errors import WSegError
from .header import HEADER_SIZE, MAX_SEG_COUNT, build_header, parse_header
from .index import build_index, index_region_size, parse_index
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

assert _TRAILER.size == TRAILER_SIZE


def _validate_segments(segments):
    """把输入规整为 [(seg_id, bytes), ...]，非法输入抛 WSegError。"""
    try:
        iterator = iter(segments)
    except TypeError:
        raise WSegError("structure",
                        f"{type(segments).__name__} is not a sequence of segments") from None

    items = []
    for entry in iterator:
        if isinstance(entry, (bytes, bytearray, str)):
            raise WSegError("structure", f"segment entry {entry!r} is not a pair")
        try:
            seg_id, payload = entry
        except (TypeError, ValueError):
            raise WSegError("structure",
                            "each segment must be a (seg_id, payload) pair") from None
        if not isinstance(seg_id, int) or isinstance(seg_id, bool):
            raise WSegError("structure", f"segment id {seg_id!r} is not an int")
        if not 0 <= seg_id <= MAX_SEG_ID:
            raise WSegError("structure", f"segment id {seg_id!r} out of range")
        if not isinstance(payload, (bytes, bytearray, memoryview)):
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
    items = _validate_segments(segments)

    body = bytearray()
    entries = []
    cursor = HEADER_SIZE
    for seg_id, payload in items:
        encoded = encode_segment(seg_id, payload)
        entries.append((cursor, len(encoded)))
        body += encoded
        cursor += len(encoded)

    index_offset = cursor
    header = build_header(len(items), index_offset)
    region = bytes(header) + bytes(body)
    index_region = build_index(entries)
    trailer = _TRAILER.pack(compute_crc(index_region), compute_crc(region))
    return region + index_region + trailer


def unpack(data) -> list:
    """解析 WLSG 字节串；任何结构 / 完整性问题都抛 WSegError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)

    # 文件头能读全就先判魔数 / 版本：它们比长度更能说明"这是什么东西"。
    _version, _flags, seg_count, index_offset = parse_header(data)

    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        raise WSegError("truncated", f"container is only {len(data)} bytes")

    if index_offset < HEADER_SIZE:
        raise WSegError("structure",
                        f"index offset {index_offset} overlaps the header")
    index_end = index_offset + index_region_size(seg_count)
    expected = index_end + TRAILER_SIZE
    if expected > len(data):
        raise WSegError("truncated",
                        f"container needs {expected} bytes, got {len(data)}")
    if expected < len(data):
        raise WSegError("structure",
                        f"{len(data) - expected} trailing bytes after the trailer")

    # 先走一遍段区，确认结构自洽；内容篡改留给后面的校验和去发现。
    records = []
    walked = []
    cursor = HEADER_SIZE
    for i in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > index_offset:
            raise WSegError("structure", f"segment {i} header runs past the segment region")
        seg_id, _seg_flags, body_len = parse_segment_header(data, cursor, index_offset)
        total = segment_length(body_len)
        if cursor + total > index_offset:
            raise WSegError("structure", f"segment {i} runs past the segment region")
        start = cursor + SEGMENT_HEADER_SIZE
        records.append((seg_id, data[start:start + body_len]))
        walked.append((cursor, total))
        cursor += total

    if cursor != index_offset:
        raise WSegError("structure",
                        f"segment region ends at {cursor}, index starts at {index_offset}")

    entries = parse_index(data, index_offset, seg_count)
    for i, (declared, found) in enumerate(zip(entries, walked)):
        if declared != found:
            raise WSegError("structure",
                            f"index entry {i} says {declared}, segments say {found}")

    index_crc, data_crc = _TRAILER.unpack_from(data, len(data) - TRAILER_SIZE)
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
