"""Smoke tests that ship with the package.

These describe behaviour the tool must keep whatever else changes: the boolean
entry point never raises, the error type carries a machine-readable kind, the
incremental accumulator agrees with the one-shot helper, and the section stream
accepts a plain binary stream.
"""

import io
import os

import pytest

from wpeimg import (
    ChecksumAccumulator,
    KIND_DOS,
    WImgError,
    compute_checksum,
    inspect,
    iter_sections,
    rva_to_offset,
    verify,
)

ASSETS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
)


def load(name):
    with open(os.path.join(ASSETS, name), "rb") as handle:
        return handle.read()


def test_verify_is_a_boolean_for_arbitrary_bytes():
    assert verify(b"") is False
    assert verify(b"not an image at all") is False
    assert verify(bytes(range(256)) * 4) is False


def test_dos_mismatch_carries_the_dos_kind():
    with pytest.raises(WImgError) as excinfo:
        inspect(b"XX" + b"\0" * 120)
    assert excinfo.value.kind == KIND_DOS


def test_negative_rva_has_no_file_backing():
    assert rva_to_offset(load("i386-module.bin"), -1) is None


def test_accumulator_agrees_with_the_one_shot_helper():
    blob = bytes(range(256)) * 3
    accumulator = ChecksumAccumulator()
    for start in range(0, len(blob), 100):
        accumulator.update(blob[start:start + 100])
    assert accumulator.value(len(blob)) == compute_checksum(blob)


def test_iter_sections_accepts_a_binary_stream():
    sections = list(iter_sections(io.BytesIO(load("i386-module.bin"))))
    assert [section["name"] for section in sections] == [".text", ".rdata"]
