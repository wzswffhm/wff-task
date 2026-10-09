# -*- coding: utf-8 -*-
"""候选实现（按草稿写）的自检：自洽性 + 对权威样本必挂。

两条命门：
  1. 自洽：候选 pack -> unpack -> verify 自己的格式必须全通
     （可见冒烟测试因此是绿的，缺陷被掩盖 —— 215 的核心机制）
  2. 对权威样本必挂：verify(sample.wchk) / CRC 标准向量 / 8 字节对齐
     三条都必须与 Gold 相反，否则 NOP 会拿满分、失去区分度。
"""
import io
import sys
import pathlib

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wchunk-216")
WORKSPACE = TASK / "environment" / "workspace"
sys.path.insert(0, str(WORKSPACE))

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

sample = (WORKSPACE / "assets" / "sample.wchk").read_bytes()
empty_gold = (WORKSPACE / "assets" / "sample_empty.wchk").read_bytes()

failures = []


def check(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
    except AssertionError as exc:
        print(f"  [FAIL] {name}: {exc}")
        failures.append(name)
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")
        failures.append(name)


print("=== 候选自检 ① 自洽（冒烟必须全绿）===")


def c_self_roundtrip():
    blob = pack(EXPECTED)
    assert unpack(blob) == EXPECTED, "unpack(pack(x)) != x"
    assert verify(blob) is True, "verify(self) is False"


def c_empty_self():
    blob = pack([])
    assert unpack(blob) == []
    assert verify(blob) is True


def c_stream_self():
    blob = pack([(1, b"alpha"), (2, b"beta")])
    assert read_all(io.BytesIO(blob)) == unpack(blob)
    assert list(iter_records(io.BytesIO(blob))) == unpack(blob)


def c_error_classes_self():
    # 候选自己的坏数据也必须能分类（不泄漏 struct.error）
    assert verify(b"") is False
    assert verify(b"W") is False
    assert verify(b"WCHK") is False
    try:
        unpack(b"WCHK\x02\x00\x00")  # 短于 16B
        raise AssertionError("did not raise")
    except WChunkError as exc:
        assert exc.kind == "truncated", f"kind={exc.kind}"
    try:
        unpack(b"XXXX" + b"\x00" * 30)
        raise AssertionError("did not raise")
    except WChunkError as exc:
        assert exc.kind == "magic", f"kind={exc.kind}"


def c_streaming_guard():
    class GuardedReader:
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

    recs = [(i % 7 + 1, bytes([i % 256]) * 256) for i in range(4000)]
    blob = pack(recs)
    assert len(blob) > 900_000, f"blob is {len(blob)}"
    reader = GuardedReader(blob)
    tag, payload = next(iter_records(reader))
    assert (tag, payload) == (1, b"\x00" * 256), f"got {tag} {payload[:8]!r}"
    assert reader.max_request <= 8192, f"read request {reader.max_request}"
    assert reader.bytes_read < len(blob) // 4, f"read {reader.bytes_read}/{len(blob)}"


for name, fn in [
    ("自洽 往返", c_self_roundtrip),
    ("自洽 空容器", c_empty_self),
    ("自洽 流式/read_all", c_stream_self),
    ("自洽 错误分类", c_error_classes_self),
    ("自洽 流式守卫", c_streaming_guard),
]:
    check(name, fn)

print()
print("=== 候选自检 ② 对权威样本必挂（NOP 必须拿不到满分）===")


def m_gold_sample_rejected():
    assert verify(sample) is False, "!! 候选竟然能读权威样本 —— NOP 会拿满分"


def m_gold_empty_rejected():
    assert verify(empty_gold) is False, "!! 候选竟然能读空样本"


def m_crc_differs_from_standard():
    assert compute_crc(b"") != 0x00000000, \
        f"candidate crc(b'')={compute_crc(b'')} equals the standard vector"
    assert compute_crc(b"123456789") != 0xCBF43926, \
        "candidate CRC matches the standard check value — draft variant expected"


def m_no_alignment():
    blob = pack([(1, b"a")])
    # uvarint(1)=1B + uvarint(1)=1B + 1B payload = 3B records 区，无对齐
    expected_unaligned = 12 + 3 + 4
    assert len(blob) == expected_unaligned, \
        f"expected draft layout {expected_unaligned}, got {len(blob)}"
    assert len(blob) != 12 + 8 + 6, "candidate accidentally 8-byte aligned"


def m_footer_is_four_bytes():
    blob = pack([])
    assert len(blob) == 12 + 4, f"empty container is {len(blob)}, draft says 16"


for name, fn in [
    ("样本 verify 必须 False", m_gold_sample_rejected),
    ("空样本 verify 必须 False", m_gold_empty_rejected),
    ("CRC 与标准向量不同", m_crc_differs_from_standard),
    ("无 8 字节对齐", m_no_alignment),
    ("footer 为 4 字节", m_footer_is_four_bytes),
]:
    check(name, fn)

print()
print(f"自洽 {5 - len(failures) if not failures else '?'}，失败 {len(failures)}")
print("\n--- 关键对照 ---")
print(f"  候选 verify(sample.wchk) = {verify(sample)}   （必须 False）")
print(f"  候选 crc(b'')            = 0x{compute_crc(b''):08x}   （标准应为 0x00000000）")
print(f"  候选 len(pack([(1,b'a')]))= {len(pack([(1, b'a')]))}   （Gold 为 26 = 12+8+6）")
print(f"  候选空容器 len           = {len(pack([]))}   （Gold 为 18 = 12+6）")
print(f"  Gold 样本 len            = {len(sample)}   （候选自产为 {len(pack(EXPECTED))}）")

sys.exit(1 if failures else 0)
