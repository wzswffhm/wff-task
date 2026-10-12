"""流式读取。"""

from __future__ import annotations

from .codec import unpack
from .errors import WSegError


def iter_segments(handle):
    """产出 (seg_id, payload)。"""
    data = handle.read()
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"the stream returned {type(data).__name__}")
    for item in unpack(bytes(data)):
        yield item


def read_all(handle) -> list:
    """把结果收成一个列表。"""
    return [item for item in iter_segments(handle)]
