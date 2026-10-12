"""wlogseg 冒烟测试。"""

import io

from wlogseg import WSegError, iter_segments, pack, read_all, unpack, verify


def test_pack_unpack_roundtrip():
    records = [(1, b"alpha"), (2, b"beta")]
    assert unpack(pack(records)) == records


def test_verify_accepts_own_output():
    assert verify(pack([(5, b"hello world")])) is True


def test_verify_rejects_garbage():
    assert verify(b"not a container at all") is False


def test_bad_magic_is_reported():
    blob = bytearray(pack([(1, b"a")]))
    blob[0:4] = b"XXXX"
    assert verify(bytes(blob)) is False
    try:
        unpack(bytes(blob))
    except WSegError as exc:
        assert exc.kind == "magic"
    else:
        raise AssertionError("unpack should have rejected the bad magic")


def test_iter_segments_matches_unpack():
    blob = pack([(1, b"a"), (2, b"bb")])
    assert read_all(io.BytesIO(blob)) == unpack(blob)
    assert [seg_id for seg_id, _ in iter_segments(io.BytesIO(blob))] == [1, 2]


def test_empty_container():
    assert unpack(pack([])) == []
    assert verify(pack([])) is True
