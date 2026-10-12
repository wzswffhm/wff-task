"""段的头布局与编码。

真实布局（以 ``assets/`` 下的样本为准）::

    偏移  长度  含义
    0     2     段号（小端）
    2     1     标志位
    3     1     保留
    4     4     数据长度（小端）
    8     n     数据
    8+n   p     填充，使「段头 + 数据 + 填充」对齐到 8 字节

注意：对齐边界是 **8** 字节，而不是 ``docs/FORMAT.md`` 草稿里写的 4 字节。
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
    """段在文件中占用的总字节数（含段头与填充）。"""
    return SEGMENT_HEADER_SIZE + body_len + padding_for(body_len)


def encode_segment(seg_id: int, payload: bytes, flags: int = 0) -> bytes:
    body = bytes(payload)
    head = _SEGMENT.pack(seg_id & MAX_SEG_ID, flags & 0xFF, 0, len(body))
    return head + body + b"\x00" * padding_for(len(body))


def decode_segment_header(chunk: bytes):
    """解析 8 字节段头，返回 (seg_id, flags, body_len)。"""
    if len(chunk) < SEGMENT_HEADER_SIZE:
        raise WSegError("truncated", "segment header is incomplete")
    seg_id, flags, _reserved, body_len = _SEGMENT.unpack_from(chunk, 0)
    return seg_id, flags, body_len


def parse_segment_header(data: bytes, pos: int, limit: int):
    """从 ``pos`` 读段头；``limit`` 是段区已声明的字节上界。

    段头越过 ``limit`` 说明段区长度与段内容自相矛盾，属于 ``structure``。
    """
    if pos + SEGMENT_HEADER_SIZE > limit:
        raise WSegError("structure", f"segment header at {pos} crosses the segment region")
    seg_id, flags, _reserved, body_len = _SEGMENT.unpack_from(data, pos)
    return seg_id, flags, body_len
