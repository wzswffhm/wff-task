"""段的头布局与编码。

每个段由 8 字节段头和变长数据组成，小端::

    偏移  长度  含义
    0     2     段号
    2     1     标志位
    3     1     保留
    4     4     数据长度

数据之后用 0 填充，使「段头 + 数据 + 填充」的总长度是 8 字节的整数倍
（样本实测为 8 字节对齐，而非早期草稿所写的 4）。
"""

from __future__ import annotations

import struct

from .errors import WSegError

SEGMENT_HEADER_SIZE = 8
ALIGNMENT = 8
MAX_SEG_ID = 0xFFFF
MAX_BODY = 0xFFFFFFFF

_SEGMENT = struct.Struct("<HBBI")

assert _SEGMENT.size == SEGMENT_HEADER_SIZE


def padding_for(body_len: int) -> int:
    """段整体（头 + 数据 + 填充）必须是 ALIGNMENT 的整数倍。"""
    return (-(SEGMENT_HEADER_SIZE + body_len)) % ALIGNMENT


def segment_length(body_len: int) -> int:
    return SEGMENT_HEADER_SIZE + body_len + padding_for(body_len)


def encode_segment(seg_id: int, payload: bytes, flags: int = 0) -> bytes:
    body = bytes(payload)
    head = _SEGMENT.pack(seg_id, flags & 0xFF, 0, len(body))
    return head + body + b"\x00" * padding_for(len(body))


def parse_segment_header(data, pos: int, limit: int):
    """从 ``pos`` 读段头；``limit`` 是已经确认可读的字节上界。"""
    if pos + SEGMENT_HEADER_SIZE > limit:
        raise WSegError("structure", f"segment header at {pos} is incomplete")
    seg_id, flags, _reserved, body_len = _SEGMENT.unpack_from(data, pos)
    return seg_id, flags, body_len


def unpack_segment_header(buf):
    """解析一个独立的 8 字节段头缓冲区，返回 (seg_id, flags, body_len)。"""
    if len(buf) < SEGMENT_HEADER_SIZE:
        raise WSegError("truncated", "segment header is incomplete")
    seg_id, flags, _reserved, body_len = _SEGMENT.unpack_from(bytes(buf), 0)
    return seg_id, flags, body_len
