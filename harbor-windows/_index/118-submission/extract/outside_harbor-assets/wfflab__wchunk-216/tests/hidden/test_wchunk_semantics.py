"""wchunk 的容器格式语义测试（隐藏套件）。

被测语义全部来自 instruction.md 的验收标准：

- 以 ``assets/sample.wchk`` 为唯一权威（逐字节往返、记录语义、对齐）；
- 校验和必须是通用 32 位 CRC 变体（用标准测试向量钉死）；
- 结构 / 完整性问题的错误分类（``WChunkError.kind``）；
- ``iter_records`` 必须流式，不得整体读取。
"""

import io
import os

import pytest

from wchunk import (
    WChunkError,
    compute_crc,
    iter_records,
    pack,
    read_all,
    unpack,
    verify,
)

ASSETS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
)
SAMPLE_PATH = os.path.join(ASSETS, "sample.wchk")
EMPTY_PATH = os.path.join(ASSETS, "sample_empty.wchk")

EXPECTED = [
    (1, b"alpha"),
    (2, b""),
    (300, b"x" * 10),
    (4, bytes(range(256))),
    (65000, b"z"),
]


def _load(path):
    with open(path, "rb") as handle:
        return handle.read()


@pytest.fixture(scope="module")
def sample():
    return _load(SAMPLE_PATH)


@pytest.fixture(scope="module")
def empty_sample():
    return _load(EMPTY_PATH)


# --------------------------------------------------------------- A. 样本兼容

def test_sample_verifies(sample, empty_sample):
    assert verify(sample) is True
    assert verify(empty_sample) is True


def test_sample_roundtrip_byte_identical(sample, empty_sample):
    assert pack(unpack(sample)) == sample
    assert pack(unpack(empty_sample)) == empty_sample


def test_sample_records_match_expected(sample):
    assert unpack(sample) == EXPECTED


def test_empty_sample_roundtrip(empty_sample):
    # header(12) + footer(6)；footer 含 CRC 与 tag_sum 两段
    assert len(empty_sample) == 18, f"empty container is {len(empty_sample)} bytes"
    assert unpack(empty_sample) == []


def test_record_alignment_is_eight_bytes():
    # 每条记录占用必须补齐到 8：4 + 1 -> 8，4 + 4 -> 8
    one = pack([(1, b"a")])
    assert len(one) == 12 + 8 + 6, f"single record container is {len(one)}, expected 26"
    exact = pack([(7, b"q" * 4)])
    assert len(exact) == 12 + 8 + 6, f"already-aligned payload padded: {len(exact)}"


# --------------------------------------------------------------- C. 校验和

def test_crc_matches_standard_check_value():
    # CRC-32/ISO-HDLC 的标准测试向量
    assert compute_crc(b"") == 0x00000000
    assert compute_crc(b"a") == 0xE8B7BE43
    assert compute_crc(b"123456789") == 0xCBF43926


def test_tampered_content_is_rejected(sample):
    blob = bytearray(sample)
    blob[12] ^= 0x01  # 落在第一条记录的 payload 内
    tampered = bytes(blob)
    assert verify(tampered) is False
    with pytest.raises(WChunkError) as excinfo:
        unpack(tampered)
    assert excinfo.value.kind == "checksum"


def test_checksum_covers_header_and_records():
    records = [(1, b"alpha"), (2, b""), (7, b"y" * 33)]
    blob = pack(records)
    assert verify(blob) is True
    # 改头部的版本字节之外的计数字段也必须被校验发现
    blob2 = bytearray(blob)
    blob2[5] ^= 0x08  # record_count 的一个字节
    assert verify(bytes(blob2)) is False
    # 改 records 区最后一字节（footer 之前）
    blob3 = bytearray(blob)
    blob3[-7] ^= 0x80
    assert verify(bytes(blob3)) is False


# --------------------------------------------------------------- D. 错误分类

def test_truncated_container_reports_truncated(sample):
    cut = sample[:-3]
    assert verify(cut) is False
    with pytest.raises(WChunkError) as excinfo:
        unpack(cut)
    assert excinfo.value.kind == "truncated"


def test_truncated_stream_reports_truncated(sample):
    with pytest.raises(WChunkError) as excinfo:
        list(iter_records(io.BytesIO(sample[:-3])))
    assert excinfo.value.kind == "truncated"


def test_bad_magic_reports_magic(sample):
    blob = b"XXXX" + sample[4:]
    assert verify(blob) is False
    with pytest.raises(WChunkError) as excinfo:
        unpack(blob)
    assert excinfo.value.kind == "magic"


def test_bad_version_reports_version(sample):
    blob = sample[:4] + bytes([0x77]) + sample[5:]
    assert verify(blob) is False
    with pytest.raises(WChunkError) as excinfo:
        unpack(blob)
    assert excinfo.value.kind == "version"


def test_verify_never_raises():
    for blob in (b"", b"W", b"WCHK", b"WCHK\x02\x00\x00",
                 b"WCHK\x02" + b"\x00" * 20, b"WCHK\x77" + b"\x00" * 30):
        assert verify(blob) is False


# --------------------------------------------------------------- E. 流式读取

class GuardedReader:
    """一次只允许用固定大小的 read(n) 取数据的伪文件对象。"""

    def __init__(self, data):
        self._data = data
        self._pos = 0
        self.max_request = 0
        self.bytes_read = 0

    def read(self, size=-1):
        if size is None or size < 0:
            raise AssertionError("iter_records must not slurp the whole file")
        self.max_request = max(self.max_request, size)
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        self.bytes_read += len(chunk)
        return chunk


def test_iter_records_is_streaming():
    records = [(index % 7 + 1, bytes([index % 256]) * 256) for index in range(4000)]
    blob = pack(records)
    assert len(blob) > 900_000
    reader = GuardedReader(blob)
    stream = iter_records(reader)
    tag, payload = next(stream)
    assert (tag, payload) == (1, b"\x00" * 256)
    assert reader.max_request <= 8192
    assert reader.bytes_read < len(blob) // 4


# --------------------------------------------------------------- F. 不回归

def test_self_roundtrip_small_records():
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
