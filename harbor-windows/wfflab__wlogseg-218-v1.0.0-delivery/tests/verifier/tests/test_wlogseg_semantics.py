"""wlogseg 分段日志容器的语义测试（隐藏套件）。

被测语义全部来自 instruction.md 的验收标准：

- 以 ``assets/sample.wlsg`` / ``assets/sample_empty.wlsg`` 为唯一权威依据
  （逐字节往返、段序列、段对齐、尾部索引布局）；
- 校验和必须是通用 32 位 CRC 变体（用标准测试向量钉死）；
- 结构 / 完整性问题的错误分类（``WSegError.kind``），且**数据不足一律截断优先**；
- ``iter_segments`` 必须惰性，不得整体读取。
"""

import io
import os
import struct

import pytest

from wlogseg import (
    WSegError,
    compute_crc,
    iter_segments,
    pack,
    read_all,
    unpack,
    verify,
)

ASSETS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
)
SAMPLE_PATH = os.path.join(ASSETS, "sample.wlsg")
EMPTY_PATH = os.path.join(ASSETS, "sample_empty.wlsg")

EXPECTED = [
    (1, b"alpha"),
    (2, b""),
    (300, b"x" * 10),
    (4, bytes(range(256))),
    (65000, b"z"),
]

HEADER_SIZE = 16
INDEX_ENTRY_SIZE = 8
TRAILER_SIZE = 8


def _load(path):
    with open(path, "rb") as handle:
        return handle.read()


def _index_offset(blob):
    return struct.unpack_from("<I", blob, 8)[0]


def _kind(blob):
    with pytest.raises(WSegError) as excinfo:
        unpack(blob)
    return excinfo.value.kind


@pytest.fixture(scope="module")
def sample():
    return _load(SAMPLE_PATH)


@pytest.fixture(scope="module")
def empty_sample():
    return _load(EMPTY_PATH)


# ------------------------------------------------------- A. 样本兼容（权威依据）

def test_sample_verifies(sample, empty_sample):
    assert verify(sample) is True
    assert verify(empty_sample) is True


def test_sample_roundtrip_byte_identical(sample, empty_sample):
    assert pack(unpack(sample)) == sample
    assert pack(unpack(empty_sample)) == empty_sample


def test_sample_records_match_expected(sample):
    assert unpack(sample) == EXPECTED


def test_empty_sample_roundtrip(empty_sample):
    assert len(empty_sample) == HEADER_SIZE + TRAILER_SIZE
    assert unpack(empty_sample) == []


# ------------------------------------------------------- B. 段布局与尾部索引

def test_segment_alignment_is_eight_bytes():
    # 段整体（头 + 数据 + 填充）必须是 8 的整数倍
    one = pack([(1, b"a")])
    assert len(one) == HEADER_SIZE + 16 + INDEX_ENTRY_SIZE + TRAILER_SIZE, len(one)
    exact = pack([(7, b"q" * 4)])
    assert len(exact) == HEADER_SIZE + 16 + INDEX_ENTRY_SIZE + TRAILER_SIZE, len(exact)
    spill = pack([(7, b"q" * 9)])
    assert len(spill) == HEADER_SIZE + 24 + INDEX_ENTRY_SIZE + TRAILER_SIZE, len(spill)


def test_index_layout_matches_sample(sample):
    seg_count = struct.unpack_from("<H", sample, 6)[0]
    assert seg_count == len(EXPECTED)
    index_offset = _index_offset(sample)
    assert index_offset == HEADER_SIZE + sum(
        8 + len(payload) + (-(8 + len(payload))) % 8 for _, payload in EXPECTED
    )
    assert len(sample) == index_offset + INDEX_ENTRY_SIZE * seg_count + TRAILER_SIZE
    cursor = HEADER_SIZE
    for index in range(seg_count):
        offset, length = struct.unpack_from("<II", sample, index_offset + index * INDEX_ENTRY_SIZE)
        assert offset == cursor, f"entry {index} offset {offset} != {cursor}"
        assert length % 8 == 0
        cursor += length
    assert cursor == index_offset
    # 重建容器时索引区必须被原样复现
    assert pack(unpack(sample))[index_offset:] == sample[index_offset:]


# ------------------------------------------------------- C. 校验和

def test_crc_matches_standard_check_value():
    # CRC-32/ISO-HDLC 的标准测试向量
    assert compute_crc(b"") == 0x00000000
    assert compute_crc(b"a") == 0xE8B7BE43
    assert compute_crc(b"123456789") == 0xCBF43926


def test_tampered_payload_is_rejected(sample):
    blob = bytearray(sample)
    blob[HEADER_SIZE + 8] ^= 0x01  # 落在第一段的 payload 内
    tampered = bytes(blob)
    assert verify(tampered) is False
    assert _kind(tampered) == "checksum"

    # 段数据之后的填充字节同样被段区校验和覆盖
    padded = bytearray(sample)
    padded[HEADER_SIZE + 8 + len(b"alpha")] ^= 0xFF
    assert verify(bytes(padded)) is False
    assert _kind(bytes(padded)) == "checksum"


# ------------------------------------------------------- D. 截断：数据不足优先于结构矛盾

def test_truncated_header_reports_truncated(sample):
    cut = sample[:12]
    assert verify(cut) is False
    assert _kind(cut) == "truncated"


def test_missing_index_reports_truncated(sample):
    index_offset = _index_offset(sample)
    cut = sample[:index_offset]
    assert verify(cut) is False
    assert _kind(cut) == "truncated"

    half = sample[:index_offset + 4]
    assert verify(half) is False
    assert _kind(half) == "truncated"


def test_truncated_segment_body_reports_truncated():
    # 段头声明了远远超出文件的数据长度，而索引与尾部齐全：
    # 数据在读完该段之前就结束了，必须归为截断。
    forged = bytearray()
    forged += struct.pack("<4sBBHII", b"WLSG", 1, 0, 1, 24, 0)
    forged += struct.pack("<HBBI", 1, 0, 0, 1000000)
    forged = forged[:24]
    forged += b"\x00" * (INDEX_ENTRY_SIZE + TRAILER_SIZE)
    blob = bytes(forged)
    assert verify(blob) is False
    assert _kind(blob) == "truncated"


def test_truncated_stream_reports_truncated(sample):
    with pytest.raises(WSegError) as excinfo:
        list(iter_segments(io.BytesIO(sample[:-3])))
    assert excinfo.value.kind == "truncated"


# ------------------------------------------------------- E. 结构矛盾：数据齐全但不自洽

def test_index_offset_inside_header_reports_structure():
    blob = bytearray(pack([(1, b"a")]))
    struct.pack_into("<I", blob, 8, 4)
    assert verify(bytes(blob)) is False
    assert _kind(bytes(blob)) == "structure"


def test_segment_past_index_reports_structure():
    blob = bytearray(pack([(1, b"a"), (2, b"bb")]))
    struct.pack_into("<I", blob, 8, _index_offset(blob) - 4)
    assert verify(bytes(blob)) is False
    assert _kind(bytes(blob)) == "structure"


def test_index_entry_mismatch_reports_structure(sample):
    blob = bytearray(sample)
    struct.pack_into("<II", blob, _index_offset(sample), 0, 999999)
    assert verify(bytes(blob)) is False
    assert _kind(bytes(blob)) == "structure"

    # 声明段数少于索引区实际容纳的条目数：段区之后留下垃圾
    blob2 = bytearray(sample)
    struct.pack_into("<H", blob2, 6, len(EXPECTED) - 1)
    assert verify(bytes(blob2)) is False
    assert _kind(bytes(blob2)) == "structure"


# ------------------------------------------------------- F. 流式读取

class GuardedReader:
    """只允许固定大小 read(n) 的伪文件对象。"""

    def __init__(self, data):
        self._data = data
        self._pos = 0
        self.max_request = 0
        self.bytes_read = 0

    def read(self, size=-1):
        if size is None or size < 0:
            raise AssertionError("iter_segments must not slurp the whole file")
        self.max_request = max(self.max_request, size)
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        self.bytes_read += len(chunk)
        return chunk


def test_iter_segments_is_streaming():
    records = [(index % 7 + 1, bytes([index % 256]) * 256) for index in range(4000)]
    blob = pack(records)
    assert len(blob) > 900_000
    reader = GuardedReader(blob)
    stream = iter_segments(reader)
    tag, payload = next(stream)
    assert (tag, payload) == (1, b"\x00" * 256)
    assert reader.max_request <= 8192
    assert reader.bytes_read < len(blob) // 4


# ------------------------------------------------------- G. 分类与非回归

def test_bad_magic_reports_magic(sample):
    blob = b"XXXX" + sample[4:]
    assert verify(blob) is False
    assert _kind(blob) == "magic"


def test_bad_version_reports_version(sample):
    blob = sample[:4] + bytes([0x77]) + sample[5:]
    assert verify(blob) is False
    assert _kind(blob) == "version"


def test_verify_never_raises():
    for blob in (b"", b"W", b"WLSG", b"WLSG\x01\x00\x00",
                 b"WLSG\x01" + b"\x00" * 20, b"WLSG\x77" + b"\x00" * 30):
        assert verify(blob) is False


def test_trailing_bytes_reports_structure():
    blob = pack([(1, b"a")]) + b"\x00"
    assert verify(blob) is False
    assert _kind(blob) == "structure"


def test_self_roundtrip_small_segments():
    records = [(1, b"alpha"), (2, b"beta")]
    blob = pack(records)
    assert unpack(blob) == records
    assert verify(blob) is True


def test_empty_payload_roundtrip():
    records = [(9, b"")]
    blob = pack(records)
    assert unpack(blob) == records


def test_generated_data_roundtrip_verified():
    records = [(i, bytes([i]) * i) for i in range(1, 6)]
    assert verify(pack(records)) is True


def test_read_all_matches_unpack():
    records = [(3, b"abc"), (4, b"d" * 9)]
    blob = pack(records)
    assert read_all(io.BytesIO(blob)) == unpack(blob)


def test_pack_rejects_out_of_range_segment_id():
    with pytest.raises(WSegError):
        pack([(70000, b"x")])
    with pytest.raises(WSegError):
        pack([(-1, b"x")])
    with pytest.raises(WSegError):
        pack([(1, "not bytes")])
