"""容器使用的无符号变长整数（LEB128，小端续位）。"""

from __future__ import annotations

from .errors import WFormatError

__all__ = ["encode_uvarint", "decode_uvarint", "MAX_SHIFT"]

MAX_SHIFT = 63


def encode_uvarint(value):
    """把非负整数编码为 LEB128 字节串。

    每字节低 7 位是数据、最高位（0x80）表示「后面还有字节」。最低有效组
    在最前面。
    """
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
    """从 ``buf[pos:]`` 解出一个 uvarint，返回 ``(value, next_pos)``。

    数据在字节中途耗尽时抛 ``WFormatError(kind="truncated")``；超过
    ``MAX_SHIFT`` 位时抛 ``WFormatError(kind="varint")``。
    """
    shift = 0
    result = 0
    while True:
        if pos >= len(buf):
            raise WFormatError("truncated", "uvarint 数据不足")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > MAX_SHIFT:
            raise WFormatError("varint", "uvarint 超出 63 位")
