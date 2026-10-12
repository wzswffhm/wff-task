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

    # 编码所有段并记录每个段的偏移和总长度
    index_entries = []
    body_region = bytearray()
    cursor = HEADER_SIZE
    for seg_id, payload in items:
        encoded = encode_segment(seg_id, payload)
        index_entries.append((cursor, len(encoded)))
        body_region += encoded
        cursor += len(encoded)

    index_offset = cursor
    header = build_header(len(items), index_offset)
    index_region = build_index(index_entries)

    # trailer: [index_crc, data_crc]
    # data_crc 覆盖 header + 整个段区
    data_crc_input = bytes(header) + bytes(body_region)
    trailer = _TRAILER.pack(compute_crc(index_region), compute_crc(data_crc_input))
    return bytes(header) + bytes(body_region) + index_region + trailer


def unpack(data) -> list:
    """解析 WLSG 字节串；任何结构 / 完整性问题都抛 WSegError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)

    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        raise WSegError("truncated", f"container is only {len(data)} bytes")

    _version, _flags, seg_count, index_offset = parse_header(data)

    # 校验索引区和 trailer 是否放得下
    index_end = index_offset + INDEX_ENTRY_SIZE * seg_count
    if index_end + TRAILER_SIZE > len(data):
        raise WSegError("truncated", "the index and the trailer do not fit")

    # 读取并校验索引 CRC
    index_region = data[index_offset:index_end]
    index_crc, data_crc = _TRAILER.unpack_from(data, index_end)
    if compute_crc(index_region) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")

    # 解析索引
    idx_entries = parse_index(data, index_offset, seg_count)

    # 按索引逐段解析
    records = []
    for i, (seg_off, seg_total_len) in enumerate(idx_entries):
        if seg_off + SEGMENT_HEADER_SIZE > len(data):
            raise WSegError("truncated", f"segment {i} header is incomplete")
        if seg_off + seg_total_len > index_offset:
            raise WSegError("structure", f"segment {i} extends beyond segment area")
        seg_id, _seg_flags, body_len = parse_segment_header(data, seg_off, len(data))
        expected_total = segment_length(body_len)
        if expected_total != seg_total_len:
            raise WSegError("structure",
                            f"segment {i}: index says length {seg_total_len} but header implies {expected_total}")
        payload_start = seg_off + SEGMENT_HEADER_SIZE
        if payload_start + body_len > seg_off + seg_total_len:
            raise WSegError("truncated", f"segment {i} payload is incomplete")
        records.append((seg_id, bytes(data[payload_start:payload_start + body_len])))

    # 校验数据区 CRC（header + 段区）
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
