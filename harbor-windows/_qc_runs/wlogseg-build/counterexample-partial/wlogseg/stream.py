"""Streaming reader."""

from __future__ import annotations

from .codec import unpack
from .errors import WSegError


def iter_segments(handle):
    data = handle.read()
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"the stream returned {type(data).__name__}")
    for item in unpack(bytes(data)):
        yield item


def read_all(handle) -> list:
    return [item for item in iter_segments(handle)]