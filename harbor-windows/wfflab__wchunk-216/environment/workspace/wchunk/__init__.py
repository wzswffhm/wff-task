"""WCHK 容器格式库（**候选实现**，按草稿 FORMAT.md）。

公开 API（名称与签名保持不变）：
    pack(records) -> bytes
    unpack(data) -> list[(tag, payload)]
    verify(data) -> bool
    iter_records(fileobj) -> Iterator[(tag, payload)]      # 流式
    read_all(fileobj) -> list[(tag, payload)]
    compute_crc(data) -> int
    WChunkError(kind, message)
"""

from __future__ import annotations

from .codec import pack, unpack, verify
from .crc import compute_crc
from .errors import WChunkError
from .stream import iter_records, read_all

__all__ = [
    "pack",
    "unpack",
    "verify",
    "iter_records",
    "read_all",
    "compute_crc",
    "WChunkError",
]
