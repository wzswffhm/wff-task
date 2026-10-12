"""Temporary self-check for the wlogseg rewrite (deleted before submit)."""

import io
import struct
import zlib

from wlogseg import (
    WSegError,
    compute_crc,
    crc32_update,
    iter_segments,
    pack,
    read_all,
    unpack,
    verify,
)

failures = []


def check(name, cond, extra=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {extra}")
        failures.append(name)


def kind_of(fn):
    try:
        fn()
    except WSegError as exc:
        return exc.kind
    except Exception as exc:  # noqa: BLE001
        return f"WRONG-TYPE:{type(exc).__name__}"
    return None


sample = open("assets/sample.wlsg", "rb").read()
empty = open("assets/sample_empty.wlsg", "rb").read()

print("== A. sample compatibility ==")
check("verify(sample)", verify(sample) is True)
check("verify(empty)", verify(empty) is True)
records = unpack(sample)
check("unpack(sample) count", len(records) == 5, repr(records))
check("seg 0", records[0] == (1, b"alpha"))
check("seg 1 empty payload", records[1] == (2, b""))
check("seg 2", records[2] == (300, b"xxxxxxxxxx"))
check("seg 3", records[3] == (4, bytes(range(256))))
check("seg 4", records[4] == (65000, b"z"))
check("payload types are bytes", all(isinstance(p, bytes) for _s, p in records))
check("entries are tuples", all(isinstance(r, tuple) and len(r) == 2 for r in records))
check("pack(unpack(sample)) == sample", pack(records) == sample)
check("pack(unpack(empty)) == empty", pack(unpack(empty)) == empty)
check("unpack(empty)", unpack(empty) == [])

print("== B. segment semantics / pack validation ==")
check("roundtrip mixed", unpack(pack([(0, b""), (65535, b"x" * 9), (7, b"ab")])) ==
      [(0, b""), (65535, b"x" * 9), (7, b"ab")])
check("bytearray payload", unpack(pack([(1, bytearray(b"ab"))])) == [(1, b"ab")])
check("memoryview payload", unpack(pack([(1, memoryview(b"ab"))])) == [(1, b"ab")])
check("generator input", unpack(pack((i, bytes([i])) for i in range(3))) ==
      [(0, b"\x00"), (1, b"\x01"), (2, b"\x02")])
check("pack bad seg_id -1", kind_of(lambda: pack([(-1, b"a")])) == "structure")
check("pack bad seg_id 65536", kind_of(lambda: pack([(65536, b"a")])) == "structure")
check("pack bad seg_id str", kind_of(lambda: pack([("1", b"a")])) == "structure")
check("pack bool seg_id", kind_of(lambda: pack([(True, b"a")])) == "structure")
check("pack str payload", kind_of(lambda: pack([(1, "ab")])) == "structure")
check("pack None payload", kind_of(lambda: pack([(1, None)])) == "structure")
check("pack 3-tuple entry", kind_of(lambda: pack([(1, b"a", 2)])) == "structure")
check("pack non-sequence", kind_of(lambda: pack(12345)) == "structure")
check("pack too many segments",
      kind_of(lambda: pack([(1, b"")] * 65536)) == "structure")
check("verify(pack(...))", verify(pack([(5, b"hello world")])) is True)

print("== C. layout ==")
def expect_len(segs):
    total = 16 + 8
    for _sid, payload in segs:
        total += 8 + len(payload) + (-(8 + len(payload))) % 8
        total += 8
    return total


cases = [
    [],
    [(1, b"alpha")],
    [(1, b"alpha"), (2, b"beta")],
    [(i, bytes([i]) * i) for i in range(9)],
    [(0, b"")],
]
for segs in cases:
    check(f"length {len(segs)} segs", len(pack(segs)) == expect_len(segs),
          f"{len(pack(segs))} != {expect_len(segs)}")
    check(f"roundtrip {len(segs)} segs", unpack(pack(segs)) == segs)

blob = pack(records)
check("index region identical", blob[344:384] == sample[344:384])
check("trailer identical", blob[384:] == sample[384:])
check("header identical", blob[:16] == sample[:16])

print("== D. checksum ==")
check("crc32 check value", compute_crc(b"123456789") == 0xCBF43926)
check("crc32 empty", compute_crc(b"") == 0)
check("crc32 incremental", crc32_update(b"56789", crc32_update(b"1234")) ==
      compute_crc(b"123456789"))
check("crc32_update default", crc32_update(b"abc") == compute_crc(b"abc"))
big = bytes(range(256)) * 40
check("crc32 incremental big", crc32_update(big[1000:], crc32_update(big[:1000])) ==
      compute_crc(big))
check("compute_crc matches zlib", compute_crc(big) == zlib.crc32(big))
check("crc32_update zero", crc32_update(b"") == 0)


def tamper(blob, pos, xor=0xFF):
    out = bytearray(blob)
    out[pos] ^= xor
    return bytes(out)


positions = list(range(0, 40)) + [64, 200, 330, 344, 350, 360, 380, 384, 388, 391]
for pos in positions:
    check(f"verify rejects tamper@{pos}", verify(tamper(sample, pos)) is False)

blob = pack([(3, b"payload-A"), (9, b""), (77, b"B" * 40)])
for pos in range(len(blob)):
    if verify(tamper(blob, pos)):
        check(f"synthetic tamper@{pos} detected", False)
check("synthetic all-byte tampering detected", True)

print("== E. error classification ==")
check("magic kind", kind_of(lambda: unpack(tamper(sample, 0, 0x01))) == "magic")
check("magic kind (full replace)",
      kind_of(lambda: unpack(b"XXXX" + sample[4:])) == "magic")
check("version kind", kind_of(lambda: unpack(tamper(sample, 4, 0x01))) == "version")
check("version 2", kind_of(lambda: unpack(b"WLSG\x02" + sample[5:])) == "version")
for cut in (0, 1, 4, 5, 8, 15, 16, 17, 20, 23, 24, 40, 63, 64, 100, 340, 344, 350,
            383, 384, 390, 391):
    check(f"truncated@{cut}", kind_of(lambda c=cut: unpack(sample[:c])) == "truncated")
check("empty truncated", kind_of(lambda: unpack(b"")) == "truncated")
check("short garbage", kind_of(lambda: unpack(b"ab")) == "truncated")
check("truncated empty sample",
      kind_of(lambda: unpack(empty[:20])) == "truncated")

blob = bytearray(sample)
blob[6:8] = struct.pack("<H", 3)
check("seg_count too small", kind_of(lambda: unpack(bytes(blob))) == "structure")
blob = bytearray(sample)
blob[6:8] = struct.pack("<H", 6)
check("seg_count too large", kind_of(lambda: unpack(bytes(blob))) == "structure")
blob = bytearray(sample)
blob[6:8] = struct.pack("<H", 0xFFFF)
check("seg_count huge", kind_of(lambda: unpack(bytes(blob))) == "structure")
blob = bytearray(sample)
blob[8:12] = struct.pack("<I", 340)
check("index_offset mismatch", kind_of(lambda: unpack(bytes(blob))) == "structure")
blob = bytearray(sample)
blob[8:12] = struct.pack("<I", 1 << 20)
check("index_offset huge", kind_of(lambda: unpack(bytes(blob))) == "structure")
blob = bytearray(sample)
blob[8:12] = struct.pack("<I", 8)
check("index_offset inside header", kind_of(lambda: unpack(bytes(blob))) == "structure")
check("trailing junk", kind_of(lambda: unpack(sample + b"junk")) == "structure")
check("empty + junk", kind_of(lambda: unpack(empty + b"j")) == "structure")
check("length field tamper is structural",
      kind_of(lambda: unpack(tamper(sample, 20))) in ("structure", "checksum"))

blob = bytearray(sample)
blob[344:352] = struct.pack("<II", 16, 24)
blob[384:388] = struct.pack("<I", zlib.crc32(bytes(blob[344:384])))
check("index entry mismatch (fixed crc)", kind_of(lambda: unpack(bytes(blob))) == "structure")
blob = bytearray(sample)
blob[344:348] = struct.pack("<I", 17)
blob[384:388] = struct.pack("<I", zlib.crc32(bytes(blob[344:384])))
check("index offset entry mismatch (fixed crc)",
      kind_of(lambda: unpack(bytes(blob))) == "structure")

check("payload tamper -> checksum", kind_of(lambda: unpack(tamper(sample, 24, 0x01))) == "checksum")
check("payload tamper 2 -> checksum", kind_of(lambda: unpack(tamper(sample, 50, 0x01))) == "checksum")
check("seg_id tamper -> checksum", kind_of(lambda: unpack(tamper(sample, 16, 0x01))) == "checksum")
check("flags tamper -> checksum", kind_of(lambda: unpack(tamper(sample, 18, 0x01))) == "checksum")
check("reserved hdr tamper -> checksum", kind_of(lambda: unpack(tamper(sample, 13, 0x01))) == "checksum")
check("padding tamper -> checksum", kind_of(lambda: unpack(tamper(sample, 29, 0x01))) == "checksum")
check("magic beats checksum", kind_of(lambda: unpack(tamper(sample, 0))) == "magic")
check("index tamper -> checksum", kind_of(lambda: unpack(tamper(sample, 350))) == "checksum")
check("trailer tamper -> checksum", kind_of(lambda: unpack(tamper(sample, 388))) == "checksum")

for bad in (None, 12345, 3.14, b"", b"W", b"WLSG", [], {}, sample[:3], (1, 2), "text"):
    try:
        ok = verify(bad)
    except Exception as exc:  # noqa: BLE001
        check(f"verify({bad!r}) no raise", False, repr(exc))
    else:
        check(f"verify({bad!r}) is False", ok is False, repr(ok))
check("unpack arg type", kind_of(lambda: unpack(None)) == "structure")
check("WSegError kinds", WSegError.KINDS == ("magic", "version", "truncated", "structure", "checksum"))
try:
    WSegError("nope")
except ValueError:
    check("WSegError rejects unknown kind", True)
else:
    check("WSegError rejects unknown kind", False)

print("== F. streaming ==")


class StrictReader:
    """Only allows fixed-size positive read(n); records everything."""

    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.calls = []

    def read(self, n=-1):
        if not isinstance(n, int) or n <= 0:
            raise AssertionError(f"illegal bulk read({n!r})")
        self.calls.append(n)
        chunk = self.data[self.pos:self.pos + n]
        self.pos += len(chunk)
        return chunk

    def readlines(self):
        raise AssertionError("readlines() is forbidden")

    def readline(self):
        raise AssertionError("readline() is forbidden")

    def seek(self, *a):
        raise AssertionError("seek() is forbidden")

    def tell(self):
        raise AssertionError("tell() is forbidden")


reader = StrictReader(sample)
got = list(iter_segments(reader))
check("stream matches unpack", got == records)
check("stream consumed exactly", reader.pos == len(sample), reader.pos)
check("no bulk reads", all(0 < n for n in reader.calls))

reader = StrictReader(sample)
it = iter_segments(reader)
first = next(it)
check("first segment lazy", first == (1, b"alpha"))
check("lazy: read only head+seg0", reader.pos == 32, reader.pos)
check("max single read < container", max(reader.calls) < len(sample))
check("stream rest", list(it) == records[1:])


class DribbleReader(StrictReader):
    def read(self, n=-1):
        if not isinstance(n, int) or n <= 0:
            raise AssertionError(f"illegal bulk read({n!r})")
        self.calls.append(n)
        take = min(n, 7, len(self.data) - self.pos)
        chunk = self.data[self.pos:self.pos + take]
        self.pos += take
        return chunk


check("dribble stream matches", list(iter_segments(DribbleReader(sample))) == records)
check("dribble empty container", list(iter_segments(DribbleReader(empty))) == [])

check("read_all BytesIO", read_all(io.BytesIO(sample)) == records)
check("read_all bytes", read_all(sample) == records)
check("read_all strict", read_all(StrictReader(sample)) == records)
check("iter_segments bytes", list(iter_segments(empty)) == [])
with open("assets/sample.wlsg", "rb") as fh:
    check("read_all real file", read_all(fh) == records)
with open("assets/sample.wlsg", "rb") as fh:
    it = iter_segments(fh)
    check("real file first", next(it) == (1, b"alpha"))
    check("real file rest", list(it) == records[1:])

bad = tamper(sample, 24, 0x01)
try:
    list(iter_segments(io.BytesIO(bad)))
    check("stream checksum raise", False)
except WSegError as exc:
    check("stream checksum raise", exc.kind == "checksum", exc.kind)

bad = tamper(sample, 350)
try:
    read_all(io.BytesIO(bad))
    check("stream index checksum raise", False)
except WSegError as exc:
    check("stream index checksum raise", exc.kind == "checksum", exc.kind)

bad = tamper(sample, 388)
try:
    read_all(io.BytesIO(bad))
    check("stream trailer checksum raise", False)
except WSegError as exc:
    check("stream trailer checksum raise", exc.kind == "checksum", exc.kind)

for cut in (10, 30, 100, 345, 390):
    try:
        list(iter_segments(io.BytesIO(sample[:cut])))
        check(f"stream truncated@{cut}", False)
    except WSegError as exc:
        check(f"stream truncated@{cut}", exc.kind == "truncated", exc.kind)

try:
    list(iter_segments(io.BytesIO(b"XXXX" + sample[4:])))
    check("stream magic", False)
except WSegError as exc:
    check("stream magic", exc.kind == "magic", exc.kind)
try:
    list(iter_segments(io.BytesIO(b"WLSG\x07" + sample[5:])))
    check("stream version", False)
except WSegError as exc:
    check("stream version", exc.kind == "version", exc.kind)
try:
    read_all(io.BytesIO(b"WLSG\x01\x00\x01\x00\x10\x00\x00\x00\x00\x00\x00\x00" + b"j" * 8))
    check("stream seg_count too large", False)
except WSegError as exc:
    check("stream seg_count too large", exc.kind == "structure", exc.kind)


class TextReader:
    def read(self, n=-1):
        return "x" * n


try:
    list(iter_segments(TextReader()))
    check("text stream rejected", False)
except WSegError as exc:
    check("text stream rejected", exc.kind == "structure", exc.kind)

check("non-file handle", kind_of(lambda: list(iter_segments(12345))) == "structure")

big_blob = pack([(1, b"A" * 300000), (2, b"B" * 5)])
reader = StrictReader(big_blob)
it = iter_segments(reader)
check("big first segment", next(it) == (1, b"A" * 300000))
check("big read chunk cap", max(reader.calls) <= 64 * 1024, max(reader.calls))
check("big rest", list(it) == [(2, b"B" * 5)])

print("== G. smoke ==")
check("empty container pack/unpack", unpack(pack([])) == [])
check("verify empty container", verify(pack([])) is True)

print()
if failures:
    print("FAILURES:", len(failures))
    for name in failures:
        print("  -", name)
    raise SystemExit(1)
print("ALL CHECKS PASSED")
