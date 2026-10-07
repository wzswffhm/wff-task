"""记录编解码与容器整体读写。"""

from __future__ import annotations

from .crc import CRC_SIZE, compute_crc, pack_crc, unpack_crc
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

#: 每条记录在容器内的对齐字节数（记录体之后补零到该边界）。
ALIGN = 4


def encode_record(tag, payload):
    """把一条记录编码成容器内的字节串（含尾部补零对齐）。"""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    body = encode_uvarint(tag) + encode_uvarint(len(payload)) + bytes(payload)
    return body + b"\x00" * ((-len(body)) % ALIGN)


def decode_record(data, pos=0):
    """从 ``data[pos:]`` 解出一条记录，返回 ``(tag, payload, next_pos)``。"""
    start = pos
    tag, pos = decode_uvarint(data, pos)
    length, pos = decode_uvarint(data, pos)
    if pos + length > len(data):
        raise WFormatError("truncated", "记录载荷不完整")
    payload = bytes(data[pos:pos + length])
    pos += length
    pad = (-(pos - start)) % ALIGN
    if pos + pad > len(data):
        raise WFormatError("truncated", "记录对齐填充不完整")
    if any(data[pos:pos + pad]):
        raise WFormatError("structure", "对齐填充必须为零字节")
    return tag, payload, pos + pad


def pack(records):
    """把 ``(tag, payload)`` 序列打包成完整的容器字节串。"""
    items = [(t, p.encode("utf-8") if isinstance(p, str) else bytes(p)) for t, p in records]
    head = pack_header(len(items))
    body = b"".join(encode_record(t, p) for t, p in items)
    return head + body + pack_crc(compute_crc(head + body))


def unpack(data):
    """解析完整容器，返回 ``[(tag, payload), ...]``。

    任何结构或校验问题都以 ``WFormatError`` 抛出。
    """
    _version, count = parse_header(data)
    if len(data) < HEADER_SIZE + CRC_SIZE:
        raise WFormatError("truncated", "容器缺少尾部校验和")
    end = len(data) - CRC_SIZE
    records = []
    pos = HEADER_SIZE
    for _ in range(count):
        tag, payload, pos = decode_record(data[:end], pos)
        records.append((tag, payload))
    if pos != end:
        raise WFormatError("structure", "记录数与容器长度不一致")
    if compute_crc(data[:end]) != unpack_crc(data, end):
        raise WFormatError("checksum", "容器校验和不匹配")
    return records


def verify(data):
    """结构完整且校验和正确时返回 ``True``，否则返回 ``False``（不抛异常）。"""
    try:
        unpack(data)
    except Exception:
        return False
    return True
