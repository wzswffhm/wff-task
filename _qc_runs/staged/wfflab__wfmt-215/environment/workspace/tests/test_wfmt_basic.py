"""可见冒烟测试：只覆盖最基础的「自己写的能不能自己读回来」。"""

import io

import pytest

from wfmt import WFormatError, iter_records, pack, unpack, verify


def test_roundtrip_small_records():
    records = [(1, b"alpha"), (2, b"beta")]
    blob = pack(records)
    assert unpack(blob) == records
    assert verify(blob) is True


def test_stream_matches_batch():
    records = [(1, b"alpha"), (2, b"beta")]
    blob = pack(records)
    assert list(iter_records(io.BytesIO(blob))) == records


def test_error_type_is_exported():
    assert issubclass(WFormatError, Exception)
