"""为 wfflab__wlogseg-218 生成权威样本，并自测参考实现的全部语义分支。

本脚本只在题包构建期运行，不属于交付物。
"""

import io
import os
import struct
import sys

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = os.path.join(os.path.dirname(PKG), "wfflab__wlogseg-218-v1.0.0-delivery")
REF = os.path.join(TASK, "verifier", "oracle", "reference")
ASSETS = os.path.join(TASK, "environment", "workspace", "assets")

sys.path.insert(0, REF)

from wlogseg import (  # noqa: E402
    WSegError,
    compute_crc,
    iter_segments,
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


def expect_kind(fn, kind, label):
    try:
        fn()
    except WSegError as exc:
        assert exc.kind == kind, f"{label}: kind={exc.kind!r}, expected {kind!r}"
        return
    raise AssertionError(f"{label}: no WSegError was raised (expected {kind!r})")


def main():
    os.makedirs(ASSETS, exist_ok=True)
    sample = pack(EXPECTED)
    empty = pack([])
    with open(os.path.join(ASSETS, "sample.wlsg"), "wb") as fh:
        fh.write(sample)
    with open(os.path.join(ASSETS, "sample_empty.wlsg"), "wb") as fh:
        fh.write(empty)
    print(f"sample.wlsg       {len(sample)} bytes")
    print(f"sample_empty.wlsg {len(empty)} bytes")

    # ---- CRC 标准测试向量 ----
    assert compute_crc(b"") == 0x00000000
    assert compute_crc(b"a") == 0xE8B7BE43
    assert compute_crc(b"123456789") == 0xCBF43926
    print("crc: standard check values OK")

    # ---- 样本兼容 ----
    assert verify(sample) is True and verify(empty) is True
    assert pack(unpack(sample)) == sample
    assert pack(unpack(empty)) == empty
    assert unpack(sample) == EXPECTED
    assert unpack(empty) == []
    assert len(empty) == 16 + 8
    print("sample: verify / roundtrip / records OK")

    # ---- 对齐 ----
    assert len(pack([(1, b"a")])) == 16 + 16 + 8 + 8
    assert len(pack([(7, b"q" * 4)])) == 16 + 16 + 8 + 8
    assert len(pack([(7, b"q" * 8)])) == 16 + 16 + 8 + 8
    assert len(pack([(7, b"q" * 9)])) == 16 + 24 + 8 + 8
    print("layout: 8-byte alignment OK")

    # ---- 索引自洽 ----
    header = struct.unpack_from("<4sBBHII", sample, 0)
    assert header[0] == b"WLSG" and header[1] == 1 and header[3] == len(EXPECTED)
    index_offset = header[4]
    assert index_offset == 16 + sum(8 + len(p) + (-(8 + len(p))) % 8 for _, p in EXPECTED)
    assert len(sample) == index_offset + 8 * len(EXPECTED) + 8
    print("index: offset/length layout OK")

    # ---- 篡改 ----
    blob = bytearray(sample)
    blob[16 + 8] ^= 0x01
    expect_kind(lambda: unpack(bytes(blob)), "checksum", "tampered payload")
    assert verify(bytes(blob)) is False

    blob2 = bytearray(sample)
    blob2[index_offset] ^= 0x40
    expect_kind(lambda: unpack(bytes(blob2)), "structure", "tampered index entry")
    assert verify(bytes(blob2)) is False

    # 填充字节不被结构自洽检查覆盖，只能由段区校验和发现
    pad_pos = 16 + 8 + len(b"alpha")
    blob3 = bytearray(sample)
    blob3[pad_pos] ^= 0xFF
    expect_kind(lambda: unpack(bytes(blob3)), "checksum", "padding tamper")
    assert verify(bytes(blob3)) is False
    print("checksum: payload and padding tampering rejected OK")

    # ---- 截断：各位置 ----
    expect_kind(lambda: unpack(sample[:12]), "truncated", "cut in header")
    expect_kind(lambda: unpack(sample[:-3]), "truncated", "cut in trailer")
    expect_kind(lambda: unpack(sample[:index_offset]), "truncated", "index region missing")
    expect_kind(lambda: unpack(sample[:index_offset + 4]), "truncated", "index region half gone")
    expect_kind(lambda: unpack(sample[:20]), "truncated", "cut inside first segment header")
    assert verify(sample[:20]) is False

    # 段头声明超长体，但索引与尾部齐全
    forged = bytearray()
    forged += struct.pack("<4sBBHII", b"WLSG", 1, 0, 1, 24, 0)
    forged += struct.pack("<HBBI", 1, 0, 0, 1000000)
    forged = forged[:24]
    forged += b"\x00" * 8 + b"\x00" * 8
    expect_kind(lambda: unpack(bytes(forged)), "truncated", "segment body far beyond EOF")
    print("truncated: all cut positions classified OK")

    # ---- 结构矛盾 ----
    bad = bytearray(sample)
    struct.pack_into("<I", bad, 8, 4)          # index_offset 落在头部内
    expect_kind(lambda: unpack(bytes(bad)), "structure", "index offset inside header")

    bad2 = bytearray(sample)
    struct.pack_into("<I", bad2, 8, index_offset - 4)  # 段区越过索引区
    expect_kind(lambda: unpack(bytes(bad2)), "structure", "segment runs past the index")

    bad3 = bytearray(sample)
    struct.pack_into("<II", bad3, index_offset, 0, 999999)  # 索引条目失真
    expect_kind(lambda: unpack(bytes(bad3)), "structure", "index entry disagrees")

    bad4 = sample + b"\x00"  # 尾部多余字节
    expect_kind(lambda: unpack(bad4), "structure", "trailing byte after the trailer")

    bad5 = bytearray(sample)
    struct.pack_into("<H", bad5, 6, len(EXPECTED) - 1)  # 段计数与索引区长度不符
    expect_kind(lambda: unpack(bytes(bad5)), "structure", "declared count disagrees with layout")
    print("structure: contradictions classified OK")

    # ---- magic / version ----
    expect_kind(lambda: unpack(b"XXXX" + sample[4:]), "magic", "bad magic")
    expect_kind(lambda: unpack(sample[:4] + b"\x77" + sample[5:]), "version", "bad version")
    for bogus in (b"", b"W", b"WLSG", b"WLSG\x01\x00\x00", b"WLSG\x01" + b"\x00" * 20,
                  b"WLSG\x77" + b"\x00" * 30):
        assert verify(bogus) is False, f"verify({bogus!r}) must be False"
    print("magic/version/verify-never-raises OK")

    # ---- 流式 ----
    class Guarded:
        def __init__(self, data):
            self._data = data
            self._pos = 0
            self.max_request = 0
            self.bytes_read = 0

        def read(self, size=-1):
            if size is None or size < 0:
                raise AssertionError("iter_segments must not slurp")
            self.max_request = max(self.max_request, size)
            chunk = self._data[self._pos:self._pos + size]
            self._pos += len(chunk)
            self.bytes_read += len(chunk)
            return chunk

    big = pack([(i % 7 + 1, bytes([i % 256]) * 256) for i in range(4000)])
    assert len(big) > 900_000
    reader = Guarded(big)
    stream = iter_segments(reader)
    assert next(stream) == (1, b"\x00" * 256)
    assert reader.max_request <= 8192, reader.max_request
    assert reader.bytes_read < len(big) // 4
    assert read_all(io.BytesIO(big)) == unpack(big)
    expect_kind(lambda: list(iter_segments(io.BytesIO(big[:-3]))), "truncated", "stream cut")
    expect_kind(lambda: list(iter_segments(io.BytesIO(bytes(blob)))), "checksum", "stream tamper")
    print("streaming: lazy reads + trailer verification OK")

    # ---- 小回归 ----
    small = [(1, b"alpha"), (2, b"beta")]
    assert unpack(pack(small)) == small and verify(pack(small)) is True
    assert unpack(pack([(9, b"")])) == [(9, b"")]
    assert verify(pack([(i, bytes([i]) * i) for i in range(1, 6)])) is True
    print("regression: small/empty/generated roundtrips OK")

    print("\nALL REFERENCE CHECKS PASSED")


if __name__ == "__main__":
    main()
