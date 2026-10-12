"""容器整体读写：文件头、段区、尾部索引与尾部校验和。

布局（以 ``assets/`` 下的样本为准）::

    [文件头 16B][段区 ...][索引区 8B * seg_count][尾部校验和 8B]

尾部校验和是两个小端 32 位值：

* 第一个：索引区的 CRC-32；
* 第二个：文件头 + **整个段区**（含段内填充）的 CRC-32。

校验和算法是标准 CRC-32，见 ``wlogseg.crc``。
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

_TRAILER = struct.Struct("<II")


def _normalise(segments):
    """校验并规整输入的 (seg_id, payload) 序列。"""
    items = []
    for record in segments:
        try:
            seg_id, payload = record
        except (TypeError, ValueError):
            raise WSegError("structure", f"segment record {record!r} is not a pair") from None
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
    return items


def pack(segments) -> bytes:
    """把 [(seg_id, payload), ...] 序列化为 WLSG 字节串。"""
    items = _normalise(segments)

    entries = []
    region = bytearray()
    cursor = HEADER_SIZE
    for seg_id, payload in items:
        encoded = encode_segment(seg_id, payload)
        entries.append((cursor, len(encoded)))
        region += encoded
        cursor += len(encoded)

    index_offset = cursor
    header = build_header(len(items), index_offset)
    index_region = build_index(entries)
    # 校验和覆盖文件头与整个段区（含填充）。
    trailer = _TRAILER.pack(compute_crc(index_region),
                            compute_crc(bytes(header) + bytes(region)))
    return bytes(header) + bytes(region) + index_region + trailer


def unpack(data) -> list:
    """解析 WLSG 字节串；任何结构 / 完整性问题都抛 WSegError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)

    _version, _flags, seg_count, index_offset = parse_header(data)

    if index_offset < HEADER_SIZE:
        raise WSegError("structure", f"index offset {index_offset} overlaps the header")
    if len(data) < index_offset:
        raise WSegError("truncated",
                        f"segment region needs {index_offset} bytes, got {len(data)}")

    # 按每段声明的长度顺序推进，段区必须正好填满 header..index_offset；
    # 段数与段区长度不符即为结构矛盾。
    records = []
    walked = []
    cursor = HEADER_SIZE
    for number in range(seg_count):
        seg_id, _seg_flags, body_len = parse_segment_header(data, cursor, index_offset)
        start = cursor + SEGMENT_HEADER_SIZE
        total = segment_length(body_len)
        if cursor + total > index_offset:
            raise WSegError("structure", f"segment {number} runs past the segment region")
        records.append((seg_id, data[start:start + body_len]))
        walked.append((cursor, total))
        cursor += total
    if cursor != index_offset:
        raise WSegError("structure",
                        f"segment region ends at {cursor}, index starts at {index_offset}")

    index_end = index_offset + INDEX_ENTRY_SIZE * seg_count
    expected_total = index_end + TRAILER_SIZE
    if len(data) < expected_total:
        raise WSegError("truncated",
                        f"container needs {expected_total} bytes, got {len(data)}")
    if len(data) > expected_total:
        raise WSegError("structure",
                        f"container has {len(data) - expected_total} trailing bytes")

    index_crc, region_crc = _TRAILER.unpack_from(data, index_end)
    if compute_crc(data[index_offset:index_end]) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")
    if compute_crc(data[:index_offset]) != region_crc:
        raise WSegError("checksum", "the segment region does not match its checksum")

    # 尾部索引与顺序推进的结果必须落在同一批位置上。
    entries = parse_index(data, index_offset, seg_count)
    if entries != walked:
        raise WSegError("structure", "the index does not agree with the segment layout")
    return records


def verify(data) -> bool:
    """返回 data 是否是合法 WLSG 容器；**永不抛异常**。"""
    try:
        unpack(data)
        return True
    except Exception:  # noqa: BLE001
        return False
