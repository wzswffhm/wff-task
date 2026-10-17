"""Smoke tests for the wsparse public API.

These are the tests that run while the collector is being developed. They
exercise the module's contract on a scratch file.
"""

import os
import shutil
import tempfile

import pytest

from wsparse import (
    WSParseError,
    allocated_ranges,
    disk_usage,
    preallocate,
    sparse_flag,
    sparse_state,
)

SMALL = 4 * 1024 * 1024


@pytest.fixture()
def scratch(tmp_path):
    return tmp_path


def test_preallocate_creates_the_sink(scratch):
    sink = scratch / "new.bin"
    assert not sink.exists()
    length = preallocate(str(sink), SMALL)
    assert sink.exists()
    assert sink.stat().st_size == SMALL
    assert length == SMALL


def test_preallocate_is_idempotent(scratch):
    sink = scratch / "idem.bin"
    preallocate(str(sink), SMALL)
    preallocate(str(sink), SMALL)
    assert sink.stat().st_size == SMALL


def test_preallocate_never_shrinks(scratch):
    sink = scratch / "keep.bin"
    sink.write_bytes(b"payload")
    preallocate(str(sink), SMALL)
    preallocate(str(sink), 16)
    assert sink.stat().st_size == SMALL
    assert sink.read_bytes()[:7] == b"payload"


def test_preallocate_rejects_a_negative_size(scratch):
    sink = scratch / "neg.bin"
    with pytest.raises(WSParseError) as caught:
        preallocate(str(sink), -1)
    assert caught.value.kind == "badarg"


def test_preallocate_rejects_a_non_integer_size(scratch):
    sink = scratch / "float.bin"
    with pytest.raises(WSParseError) as caught:
        preallocate(str(sink), 1.5)
    assert caught.value.kind == "badarg"


def test_preallocated_sink_accepts_a_write_and_reads_it_back(scratch):
    sink = scratch / "rw.bin"
    preallocate(str(sink), SMALL)
    payload = b"collector-payload"
    with open(sink, "r+b") as handle:
        handle.seek(1024)
        handle.write(payload)
    with open(sink, "rb") as handle:
        handle.seek(1024)
        assert handle.read(len(payload)) == payload


def test_disk_usage_is_a_positive_integer_for_a_dense_sink(scratch):
    sink = scratch / "dense.bin"
    sink.write_bytes(b"x" * 65536)
    used = disk_usage(str(sink))
    assert isinstance(used, int)
    assert used >= 65536


def test_disk_usage_reports_a_missing_file(scratch):
    with pytest.raises(WSParseError) as caught:
        disk_usage(str(scratch / "absent.bin"))
    assert caught.value.kind == "os"


def test_allocated_ranges_of_an_empty_file_is_empty(scratch):
    sink = scratch / "empty.bin"
    sink.write_bytes(b"")
    assert allocated_ranges(str(sink)) == []


def test_allocated_ranges_is_ordered_and_inside_the_file(scratch):
    sink = scratch / "ranges.bin"
    sink.write_bytes(b"y" * 8192)
    ranges = allocated_ranges(str(sink))
    size = sink.stat().st_size
    assert ranges, "a dense sink must report at least one allocated range"
    previous_end = -1
    for offset, length in ranges:
        assert offset >= 0
        assert length > 0
        assert offset + length <= size
        assert offset >= previous_end, "ranges must be ordered and disjoint"
        previous_end = offset + length


def test_sparse_state_of_a_fresh_file_is_a_boolean(scratch):
    sink = scratch / "state.bin"
    sink.write_bytes(b"z")
    assert isinstance(sparse_state(str(sink)), bool)


def test_sparse_flag_of_a_missing_file_is_reported(scratch):
    with pytest.raises(WSParseError) as caught:
        sparse_flag(str(scratch / "gone.bin"), True)
    assert caught.value.kind == "os"
