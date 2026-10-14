"""wfmt 的容器格式回归测试（隐藏测试）。

被测语义全部来自 instruction.md 的验收标准：

- 以 ``assets/sample.wfmt`` 为唯一权威（逐字节往返、记录语义、校验和变体）；
- 校验和必须是通用 32 位 CRC 变体（用标准测试向量钉死）；
- 结构 / 完整性问题的错误分类（``WFormatError.kind``）；
- ``iter_records`` 必须流式，不得整体读取。
"""

import os

import pytest

from wfmt import WFormatError, compute_crc, iter_records, pack, unpack, verify

ASSETS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets"
)
SAMPLE_PATH = os.path.join(ASSETS, "sample.wfmt")
EMPTY_PATH = os.path.join(ASSETS, "sample_empty.wfmt")

EXPECTED = [
    (1, b"alpha"),
    (2, b""),
    (300, b"x" * 10),
    (4, bytes(range(256))),
    (70000, b"z"),
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


def test_sample_roundtrip_is_byte_identical(sample, empty_sample):
    assert pack(unpack(sample)) == sample
    assert pack(unpack(empty_sample)) == empty_sample


def test_sample_records_match_expected(sample):
    assert unpack(sample) == EXPECTED


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
    with pytest.raises(WFormatError) as excinfo:
        unpack(tampered)
    assert excinfo.value.kind == "checksum"


def test_checksum_covers_header_and_records():
    records = [(1, b"alpha"), (2, b""), (7, b"y" * 33)]
    blob = pack(records)
    assert verify(blob) is True
    # 改文件头里的版本字节之外的位置也必须被校验和发现
    blob2 = bytearray(blob)
    blob2[-5] ^= 0x80  # 尾部校验和之前的一个字节
    assert verify(bytes(blob2)) is False


# --------------------------------------------------------------- D. 错误分类

def test_truncated_container_is_reported_as_truncated(sample):
    cut = sample[:-3]
    assert verify(cut) is False
    with pytest.raises(WFormatError) as excinfo:
        unpack(cut)
    assert excinfo.value.kind == "truncated"


def test_truncated_stream_is_reported_as_truncated(sample):
    import io

    with pytest.raises(WFormatError) as excinfo:
        list(iter_records(io.BytesIO(sample[:-3])))
    assert excinfo.value.kind == "truncated"


def test_bad_magic_is_reported_as_magic(sample):
    blob = b"XXXX" + sample[4:]
    assert verify(blob) is False
    with pytest.raises(WFormatError) as excinfo:
        unpack(blob)
    assert excinfo.value.kind == "magic"


def test_bad_version_is_reported_as_version(sample):
    """版本号不受支持时必须归类为 version。"""
    blob = sample[:4] + bytes([0x77]) + sample[5:]
    assert verify(blob) is False
    with pytest.raises(WFormatError) as excinfo:
        unpack(blob)
    assert excinfo.value.kind == "version"


def test_inconsistent_record_count_is_reported_as_structure(sample):
    """记录数与容器实际长度不符时必须归类为 structure。"""
    import struct

    blob = bytearray(sample)
    count = struct.unpack_from("<I", blob, 5)[0]
    struct.pack_into("<I", blob, 5, count - 1)
    tampered = bytes(blob)
    assert verify(tampered) is False
    with pytest.raises(WFormatError) as excinfo:
        unpack(tampered)
    assert excinfo.value.kind == "structure"


def test_nonzero_alignment_padding_is_reported_as_structure(sample):
    """记录对齐填充必须为零字节,非零填充属于结构自相矛盾。"""
    blob = bytearray(sample)
    # 第一条记录 tag=1 / len=5 / b"alpha" 共 7 字节,按 4 字节对齐补 1 个零字节。
    pad_index = 9 + 7
    assert blob[pad_index] == 0x00
    blob[pad_index] = 0x2A
    tampered = bytes(blob)
    assert verify(tampered) is False
    with pytest.raises(WFormatError) as excinfo:
        unpack(tampered)
    assert excinfo.value.kind == "structure"


def test_out_of_range_varint_is_reported_as_varint(sample):
    """变长整数超出 63 位编码上限时必须归类为 varint。"""
    blob = bytearray(sample)
    blob[9:19] = b"\x80" * 10
    tampered = bytes(blob)
    assert verify(tampered) is False
    with pytest.raises(WFormatError) as excinfo:
        unpack(tampered)
    assert excinfo.value.kind == "varint"


def test_verify_never_raises():
    for blob in (b"", b"W", b"WFMT", b"WFMT\x01\x00\x00", b"WFMT\x01" + b"\x00" * 20):
        assert verify(blob) is False


# --------------------------------------------------------------- E. 流式读取

class GuardedReader:
    """一次只允许用固定大小的 read(n) 取数据的伪文件对象。"""

    def __init__(self, data):
        self._data = data
        self._pos = 0
        self.max_request = 0
        self.bytes_read = 0
        self.calls = 0

    def read(self, size=-1):
        if size is None or size < 0:
            raise AssertionError("iter_records 不得一次性读取全部数据")
        self.calls += 1
        self.max_request = max(self.max_request, size)
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        self.bytes_read += len(chunk)
        return chunk


def _stream_profile(records):
    """完整消费 records，返回（容器、读取器、产出记录、读满容器时尚未产出的条数）。

    "读满容器时尚未产出的条数"是判断流式真伪的关键观测量：有界缓冲下它是常数
    （约等于窗口大小 / 单条记录大小），而伪流式或"先吐一条再把剩余全部读走"
    会随输入规模线性增长。该观测量不假设任何具体块大小。
    """
    blob = pack(records)
    reader = GuardedReader(blob)
    produced = []
    pending_at_full_read = None
    for record in iter_records(reader):
        produced.append(record)
        if pending_at_full_read is None and reader.bytes_read >= len(blob):
            pending_at_full_read = len(records) - len(produced)
    return blob, reader, produced, (pending_at_full_read or 0)


def test_iter_records_is_streaming():
    """流式读取：只允许有界 read(n)，且窗口与预读领先量不得随输入规模增长。"""
    records = [(index % 7 + 1, bytes([index % 256]) * 256) for index in range(4000)]
    blob, reader, produced, pending = _stream_profile(records)
    assert len(blob) > 900_000
    # 必须完整消费、顺序一致：只吐第一条就结束的实现会在这里被拒。
    assert produced == records
    assert reader.calls > 0

    # 1/8 规模的同实现对照：下面两处观测都不得随输入规模增长。
    small_records = records[: len(records) // 8]
    small_blob, small_reader, small_produced, small_pending = _stream_profile(small_records)
    assert len(small_blob) > 100_000
    assert small_produced == small_records

    # 读满容器时仍未产出的条数：8 倍规模下不得增长（允许 2 倍余量）。
    # 合理的定长缓冲（含 64 KiB）在两处观测上都是常数，不会被误杀。
    assert pending <= max(small_pending * 2, 8)
    # read(n) 的请求窗口：同样不得随输入规模增长。
    assert reader.max_request <= max(small_reader.max_request, 1)


def test_stream_tail_checksum_is_rejected():
    """尾部校验和被破坏时：先完整产出记录，再抛出 checksum 分类错误。"""
    records = [(1, b"alpha"), (2, b"beta"), (300, b"x" * 10), (4, bytes(range(64)))]
    blob = bytearray(pack(records))
    # 翻转尾部校验和的 4 个字节（记录区末尾可能带对齐填充，故按尾部长度定位）。
    blob[-4:] = bytes(byte ^ 0xFF for byte in blob[-4:])
    tampered = bytes(blob)
    assert verify(tampered) is False

    produced = []
    with pytest.raises(WFormatError) as excinfo:
        for record in iter_records(GuardedReader(tampered)):
            produced.append(record)
    assert excinfo.value.kind == "checksum"
    assert produced == records


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


def test_pack_verify_agrees_for_generated_data():
    records = [(i, bytes([i]) * i) for i in range(1, 6)]
    assert verify(pack(records)) is True


def test_read_all_matches_unpack():
    from wfmt import read_all
    import io

    records = [(3, b"abc"), (4, b"d" * 9)]
    blob = pack(records)
    assert read_all(io.BytesIO(blob)) == unpack(blob)
