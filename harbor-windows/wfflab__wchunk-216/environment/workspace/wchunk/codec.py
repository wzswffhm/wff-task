"""WCHK 容器的 pack / unpack（**候选实现，严格按草稿 FORMAT.md**）。

文件 = Header(12B) + Records + Footer(4B)

草稿要点（本实现照做，与真实样本的差异正是本题要逆向的）：
  * record_count 是**大端 u32**；
  * 记录的 tag / size 用 **uvarint（LEB128）**；
  * 记录之间**不做任何对齐填充**；
  * 尾部只有 **4 字节** CRC，且该 CRC **不做最终异或**。
"""

from __future__ import annotations

import struct

from .crc import compute_crc
from .errors import WChunkError
from .header import HEADER_SIZE, build_header, parse_header
from .varint import decode_varint, encode_varint

FOOTER_SIZE = 4


def pack(records) -> bytes:
    """把 [(tag, payload), ...] 序列化为 WCHK 字节串。"""
    items = []
    for tag, payload in records:
        if not isinstance(tag, int) or tag < 0 or tag > 0xFFFF:
            raise WChunkError("structure", f"tag {tag!r} out of range")
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise WChunkError("structure", f"payload {type(payload).__name__} is not bytes")
        items.append((tag, bytes(payload)))

    body = bytearray()
    for tag, payload in items:
        body += encode_varint(tag) + encode_varint(len(payload)) + payload

    header = build_header(len(items))
    stream = bytes(header) + bytes(body)
    footer = struct.pack("<I", compute_crc(stream) & 0xFFFFFFFF)
    return stream + footer


def unpack(data: bytes) -> list:
    """解析 WCHK 字节串；任何结构/完整性问题都抛 WChunkError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WChunkError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)
    if len(data) < HEADER_SIZE + FOOTER_SIZE:
        raise WChunkError("truncated",
                          f"need at least {HEADER_SIZE + FOOTER_SIZE} bytes, got {len(data)}")

    _version, count = parse_header(data)

    limit = len(data) - FOOTER_SIZE
    pos = HEADER_SIZE
    records = []
    for index in range(count):
        if pos >= limit:
            raise WChunkError("truncated", f"record {index} missing")
        try:
            tag, pos = decode_varint(data, pos)
        except WChunkError as exc:
            if exc.kind == "truncated":
                raise WChunkError("truncated", f"record {index} tag incomplete") from None
            raise
        if pos >= limit:
            raise WChunkError("truncated", f"record {index} size missing")
        size, pos = decode_varint(data, pos)
        if pos + size > limit:
            raise WChunkError("truncated",
                              f"record {index} payload missing ({size} bytes)")
        records.append((tag, data[pos:pos + size]))
        pos += size

    if pos != limit:
        raise WChunkError("structure",
                          f"{count} records end at {pos}, expected {limit}")

    (stored_crc,) = struct.unpack("<I", data[limit:])
    if compute_crc(data[:limit]) & 0xFFFFFFFF != stored_crc:
        raise WChunkError("checksum", "trailing CRC does not match header+records")
    return records


def verify(data: bytes) -> bool:
    """返回 data 是否是合法 WCHK 容器；**永不抛异常**。"""
    try:
        unpack(data)
        return True
    except WChunkError:
        return False
    except Exception:  # noqa: BLE001
        return False
