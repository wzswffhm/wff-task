"""容器使用的无符号变长整数（LEB128）。"""

from __future__ import annotations

from .errors import WFormatError

__all__ = ["encode_uvarint", "decode_uvarint", "MAX_SHIFT"]

MAX_SHIFT = 63


def encode_uvarint(value):
    """把非负整数编码为 LEB128 字节串。"""
    if not isinstance(value, int) or value < 0:
        raise ValueError("uvarint 只能编码非负整数")
    out = bytearray()
    while True:
        group = value & 0x7F
        value >>= 7
        if value:
            out.append(group | 0x80)
        else:
            out.append(group)
            return bytes(out)


def decode_uvarint(buf, pos=0):
    """从 ``buf[pos:]`` 解出一个 uvarint，返回 ``(value, next_pos)``。"""
    if pos >= len(buf):
        raise WFormatError("truncated", "uvarint 数据不足")
    return buf[pos] & 0x7F, pos + 1
