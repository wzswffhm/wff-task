# -*- coding: utf-8 -*-
"""验证 wchunk Gold 实现，并生成权威样本 assets/sample.wchk / sample_empty.wchk。

本脚本的断言集合与新题判据（16 条）等价：Gold 有任何一条过不了，
控制组 Oracle 就无法拿满分，必须先在这里修掉。
"""
import io
import sys
import pathlib

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wchunk-216")
GOLD = TASK / "solution" / "reference"
sys.path.insert(0, str(GOLD))

from wchunk import (  # noqa: E402
    WChunkError,
    compute_crc,
    iter_records,
    pack,
    read_all,
    unpack,
    verify,
)

EXPECTED = [
    (1, b"alpha"),
    (2, b""),
    (300, b"x" * 10),
    (4, bytes(range(256))),
    (65000, b"z"),
]

failures = []


def check(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
        return True
    except AssertionError as exc:
        print(f"  [FAIL] {name}: {exc}")
        failures.append(name)
        return False
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")
        failures.append(name)
        return False


print("=== wchunk Gold 自检（16 条等价断言）===")

blob = pack(EXPECTED)
empty = pack([])


def t_sample_verifies():
    assert verify(blob) is True, "verify(sample) is not True"
    assert verify(empty) is True, "verify(empty) is not True"


def t_roundtrip():
    assert pack(unpack(blob)) == blob, "pack(unpack(sample)) != sample"
    assert pack(unpack(empty)) == empty, "empty roundtrip not byte-identical"


def t_records_match():
    assert unpack(blob) == EXPECTED, f"got {unpack(blob)!r}"


def t_empty_roundtrip():
    assert len(empty) == 18, f"empty must be 12+6=18 bytes, got {len(empty)}"
    assert unpack(empty) == []


def t_crc_vectors():
    assert compute_crc(b"") == 0x00000000, hex(compute_crc(b""))
    assert compute_crc(b"a") == 0xE8B7BE43, hex(compute_crc(b"a"))
    assert compute_crc(b"123456789") == 0xCBF43926, hex(compute_crc(b"123456789"))


def t_tampered():
    bad = bytearray(blob)
    bad[12] ^= 0x01  # 第一条记录 payload 内
    assert verify(bytes(bad)) is False, "tampered sample still verifies"
    try:
        unpack(bytes(bad))
        raise AssertionError("unpack(tampered) did not raise")
    except WChunkError as exc:
        assert exc.kind == "checksum", f"kind={exc.kind}"


def t_checksum_scope():
    bad = bytearray(blob)
    bad[4] ^= 0x08  # header 的 version 字节 -> CRC 必须发现
    assert verify(bytes(bad)) is False, "header mutation not caught"
    bad2 = bytearray(blob)
    bad2[-7] ^= 0x80  # records 区最后一个字节（footer 之前）
    assert verify(bytes(bad2)) is False, "records tail mutation not caught"


def t_truncated():
    cut = blob[:-3]
    assert verify(cut) is False, "truncated still verifies"
    try:
        unpack(cut)
        raise AssertionError("unpack(truncated) did not raise")
    except WChunkError as exc:
        assert exc.kind == "truncated", f"kind={exc.kind}"


def t_truncated_stream():
    try:
        list(iter_records(io.BytesIO(blob[:-3])))
        raise AssertionError("iter_records(truncated) did not raise")
    except WChunkError as exc:
        assert exc.kind == "truncated", f"kind={exc.kind}"


def t_bad_magic():
    bad = b"XXXX" + blob[4:]
    assert verify(bad) is False
    try:
        unpack(bad)
        raise AssertionError("unpack(bad magic) did not raise")
    except WChunkError as exc:
        assert exc.kind == "magic", f"kind={exc.kind}"


def t_bad_version():
    bad = blob[:4] + bytes([0x77]) + blob[5:]
    assert verify(bad) is False
    try:
        unpack(bad)
        raise AssertionError("unpack(bad version) did not raise")
    except WChunkError as exc:
        assert exc.kind == "version", f"kind={exc.kind}"


def t_verify_never_raises():
    for junk in (b"", b"W", b"WCHK", b"WCHK\x02\x00\x00",
                 b"WCHK\x02" + b"\x00" * 20, b"WCHK\x77" + b"\x00" * 30):
        assert verify(junk) is False, f"verify({junk!r}) raised or returned True"


def t_alignment():
    # tag=1, payload=b"a" -> 4+1=5 必须补齐到 8 -> 12+8+6=26
    one = pack([(1, b"a")])
    assert len(one) == 12 + 8 + 6, f"record not 8-aligned: total={len(one)}"
    # 8 字节边界的 payload 不多补也不少补
    exact = pack([(7, b"q" * 4)])  # 4+4=8 -> 已对齐
    assert len(exact) == 12 + 8 + 6, f"already-aligned payload padded: {len(exact)}"


def t_self_roundtrip():
    recs = [(1, b"alpha"), (2, b"beta")]
    b = pack(recs)
    assert unpack(b) == recs
    assert verify(b) is True


def t_empty_payload():
    recs = [(9, b"")]
    b = pack(recs)
    assert unpack(b) == recs


def t_generated_data():
    recs = [(i, bytes([i]) * i) for i in range(1, 6)]
    assert verify(pack(recs)) is True


def t_read_all():
    recs = [(3, b"abc"), (4, b"d" * 9)]
    b = pack(recs)
    assert read_all(io.BytesIO(b)) == unpack(b)


def t_streaming():
    class GuardedReader:
        def __init__(self, data):
            self._data = data
            self._pos = 0
            self.max_request = 0
            self.bytes_read = 0

        def read(self, size=-1):
            if size is None or size < 0:
                raise AssertionError("iter_records 不得一次性读取全部数据")
            self.max_request = max(self.max_request, size)
            chunk = self._data[self._pos:self._pos + size]
            self._pos += len(chunk)
            self.bytes_read += len(chunk)
            return chunk

    recs = [(i % 7 + 1, bytes([i % 256]) * 256) for i in range(4000)]
    big = pack(recs)
    assert len(big) > 900_000, f"big blob is {len(big)}"
    reader = GuardedReader(big)
    stream = iter_records(reader)
    tag, payload = next(stream)
    assert (tag, payload) == (1, b"\x00" * 256), f"got {(tag, payload[:8])!r}"
    assert reader.max_request <= 8192, f"read request {reader.max_request}"
    assert reader.bytes_read < len(big) // 4, f"read {reader.bytes_read} of {len(big)}"


CASES = [
    ("A 样本 verify", t_sample_verifies),
    ("A 往返逐字节", t_roundtrip),
    ("A 记录语义匹配 EXPECTED", t_records_match),
    ("A 空样本 18B 往返", t_empty_roundtrip),
    ("C CRC 标准向量", t_crc_vectors),
    ("C 篡改被拒绝且 kind=checksum", t_tampered),
    ("C CRC 覆盖 header+records", t_checksum_scope),
    ("D 截断 kind=truncated", t_truncated),
    ("D 流式截断 kind=truncated", t_truncated_stream),
    ("D 坏魔数 kind=magic", t_bad_magic),
    ("D 坏版本 kind=version", t_bad_version),
    ("D verify 永不抛", t_verify_never_raises),
    ("A/F 8 字节对齐", t_alignment),
    ("F 小记录往返", t_self_roundtrip),
    ("F 空 payload 往返", t_empty_payload),
    ("F 生成数据往返", t_generated_data),
    ("F read_all == unpack", t_read_all),
    ("E 流式 GuardedReader", t_streaming),
]

for name, fn in CASES:
    check(name, fn)

print(f"\n通过 {len(CASES) - len(failures)}/{len(CASES)}")

# ---- 产出权威样本 -----------------------------------------------------------
assets = TASK / "environment" / "workspace" / "assets"
assets.mkdir(parents=True, exist_ok=True)
(assets / "sample.wchk").write_bytes(blob)
(assets / "sample_empty.wchk").write_bytes(empty)
print(f"\nsample.wchk      = {len(blob)} B")
print(f"sample_empty.wchk = {len(empty)} B")
print(f"records_len      = {len(blob) - 12 - 6} B（含对齐 padding）")
print(f"sha256           = __compute__")

import hashlib  # noqa: E402
for name in ("sample.wchk", "sample_empty.wchk"):
    digest = hashlib.sha256((assets / name).read_bytes()).hexdigest()
    print(f"  {name}: {digest[:32]}…")

sys.exit(1 if failures else 0)
