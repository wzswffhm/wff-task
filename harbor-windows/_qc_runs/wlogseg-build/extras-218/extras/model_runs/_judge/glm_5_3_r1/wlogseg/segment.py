"""段的头布局与编码。

真实布局以 ``assets/`` 下的样本为准::

    偏移  长度  含义
    0     2     段号（小端 uint16）
    2     1     标志位
    3     1     保留，恒为 0
    4     4     数据长度（小端 uint32）
    8     n     payload

每个段（头 + payload + 填充）的总长度补零对齐到 **8 字节** 边界，即 payload
之后最多跟 7 个 ``0x00`` 填充字节，下一段紧跟在填充之后。注意这与早期草稿
``docs/FORMAT.md`` 中描述的 4 字节对齐不一致，样本才是权威。
"""

from __future__ import annotations

import struct

from .errors import WSegError

SEGMENT_HEADER_SIZE = 8
ALIGNMENT = 8
MAX_SEG_ID = 0xFFFF
MAX_BODY = 0xFFFFFFFF

_SEGMENT = struct.Struct("<HBBI")


def padding_for(body_len: int) -> int:
    """段整体（头 + 数据 + 填充）必须是 ALIGNMENT 的整数倍。"""
    return (-(SEGMENT_HEADER_SIZE + body_len)) % ALIGNMENT


def segment_length(body_len: int) -> int:
    """段在容器中占据的总字节数（头 + 数据 + 填充）。"""
    return SEGMENT_HEADER_SIZE + body_len + padding_for(body_len)


def encode_segment(seg_id: int, payload: bytes, flags: int = 0) -> bytes:
    body = bytes(payload)
    head = _SEGMENT.pack(seg_id, flags & 0xFF, 0, len(body))
    return head + body + b"\x00" * padding_for(len(body))


def parse_segment_header(data: bytes, pos: int, limit: int):
    """从 ``pos`` 读段头；``limit`` 是已经确认可读的字节上界。"""
    if pos + SEGMENT_HEADER_SIZE > limit:
        raise WSegError("truncated", f"segment header at {pos} is incomplete")
    seg_id, flags, _reserved, body_len = _SEGMENT.unpack_from(data, pos)
    return seg_id, flags, body_len
