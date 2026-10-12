"""段的头布局与编码。

每个段由 8 字节段头和变长数据组成（小端）：

| 偏移 | 长度 | 含义 |
| --- | --- | --- |
| 0 | 2 | 段号 |
| 2 | 1 | 标志位 |
| 3 | 1 | 保留 |
| 4 | 4 | 数据长度 |

段整体（头 + 数据 + 填充）对齐到 8 字节，填充字节为 0。
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
    return SEGMENT_HEADER_SIZE + body_len + padding_for(body_len)


def encode_segment(seg_id: int, payload: bytes, flags: int = 0) -> bytes:
    body = bytes(payload)
    head = _SEGMENT.pack(seg_id, flags & 0xFF, 0, len(body))
    return head + body + b"\x00" * padding_for(len(body))


def parse_segment_header(data, pos: int, limit: int):
    """从 ``pos`` 读段头；``limit`` 是已经确认可读的字节上界。"""
    if pos + SEGMENT_HEADER_SIZE > limit:
        raise WSegError("truncated", f"segment header at {pos} is incomplete")
    seg_id, flags, _reserved, body_len = _SEGMENT.unpack_from(bytes(data), pos)
    return seg_id, flags, body_len
