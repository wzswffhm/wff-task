"""uvarint（LEB128）编解码 —— 草稿 FORMAT.md 声称的记录字段编码方式。

草稿：「tag 与 size 都以 uvarint（LEB128）编码」。
"""

from __future__ import annotations

from .errors import WChunkError

VARINT_MAX_BYTES = 10  # u64 的 LEB128 上限


def encode_varint(value: int) -> bytes:
    """把非负整数编码为 LEB128 字节串。"""
    if not isinstance(value, int) or value < 0:
        raise WChunkError("structure", f"varint value {value!r} must be a non-negative int")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def decode_varint(data: bytes, offset: int) -> tuple[int, int]:
    """从 data[offset:] 解出 LEB128，返回 (value, new_offset)。"""
    result = 0
    shift = 0
    pos = offset
    while True:
        if pos >= len(data):
            raise WChunkError("truncated", "varint runs past end of data")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7
        if shift >= VARINT_MAX_BYTES * 7:
            raise WChunkError("varint", "varint is too long to be valid")
