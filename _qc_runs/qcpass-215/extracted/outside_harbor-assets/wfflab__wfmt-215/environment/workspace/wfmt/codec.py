"""记录编解码与容器整体读写。"""

from __future__ import annotations

from .crc import CRC_SIZE, compute_crc, pack_crc
from .errors import WFormatError
from .header import HEADER_SIZE, parse_header, pack_header
from .varint import decode_uvarint, encode_uvarint

__all__ = [
    "ALIGN",
    "encode_record",
    "decode_record",
    "pack",
    "unpack",
    "verify",
]

#: 记录对齐粒度。
ALIGN = 4


def encode_record(tag, payload):
    """把一条记录编码成容器内的字节串。"""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return encode_uvarint(tag) + encode_uvarint(len(payload)) + bytes(payload)


def decode_record(data, pos=0):
    """从 ``data[pos:]`` 解出一条记录，返回 ``(tag, payload, next_pos)``。"""
    tag, pos = decode_uvarint(data, pos)
    length, pos = decode_uvarint(data, pos)
    if pos + length > len(data):
        raise WFormatError("truncated", "记录载荷不完整")
    return tag, bytes(data[pos:pos + length]), pos + length


def pack(records):
    """把 ``(tag, payload)`` 序列打包成完整的容器字节串。"""
    items = [(t, p.encode("utf-8") if isinstance(p, str) else bytes(p)) for t, p in records]
    head = pack_header(len(items))
    body = b"".join(encode_record(t, p) for t, p in items)
    return head + body + pack_crc(compute_crc(head + body))


def unpack(data):
    """解析完整容器，返回 ``[(tag, payload), ...]``。"""
    _version, count = parse_header(data)
    if len(data) < HEADER_SIZE + CRC_SIZE:
        raise WFormatError("truncated", "容器缺少尾部校验和")
    if count > len(data):
        raise WFormatError("structure", "记录数超出容器长度")
    end = len(data) - CRC_SIZE
    records = []
    pos = HEADER_SIZE
    for _ in range(count):
        tag, payload, pos = decode_record(data[:end], pos)
        records.append((tag, payload))
    if pos != end:
        raise WFormatError("structure", "记录数与容器长度不一致")
    return records


def verify(data):
    """结构完整时返回 ``True``，否则返回 ``False``（不抛异常）。"""
    try:
        unpack(data)
    except Exception:
        return False
    return True
