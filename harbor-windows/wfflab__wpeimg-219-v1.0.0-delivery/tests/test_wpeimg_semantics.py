# -*- coding: utf-8 -*-
"""wpeimg 语义契约的隐藏套件。

覆盖三件事：

* 两个冻结样本必须被真实地描述出来，32 位与 64 位两种可选头布局都要正确；
* 校验和必须等于 Windows 映像帮助库给出的权威值，并且与镜像里记录的
  CheckSum 字段无关；
* 错误分类必须按 dos -> signature -> optional -> truncated -> structure ->
  checksum 的顺序判定，结构自检严格先于校验和。

权威校验和由 imagehlp!MapFileAndCheckSumW 在 Windows 上离线取得，作为常量
写在这里，因此本套件不依赖运行时的任何 Windows 组件。
"""

from __future__ import annotations

import io
import re
import struct
from pathlib import Path

import pytest

import wpeimg
from wpeimg import (
    ChecksumAccumulator,
    KIND_CHECKSUM,
    KIND_DOS,
    KIND_OPTIONAL,
    KIND_SIGNATURE,
    KIND_STRUCTURE,
    KIND_TRUNCATED,
    WImgError,
    compute_checksum,
    inspect,
    iter_sections,
    rva_to_offset,
    verify,
)

ASSETS = Path(__file__).resolve().parent.parent / "assets"
AMD64 = ASSETS / "amd64-module.bin"
I386 = ASSETS / "i386-module.bin"

# (样本名, 追加在文件末尾的字节, imagehlp!MapFileAndCheckSumW 给出的值)
AUTHORITATIVE = (
    ("amd64-module.bin", b"", 74415),
    ("amd64-module.bin", b"\x01", 74417),
    ("amd64-module.bin", b"\x01\x02", 74930),
    ("amd64-module.bin", b"\x01\x02\x03", 74934),
    ("amd64-module.bin", bytes([0xFF]) * 17, 74687),
    ("i386-module.bin", b"", 9700),
    ("i386-module.bin", b"\x01", 9702),
    ("i386-module.bin", b"\x01\x02", 10215),
    ("i386-module.bin", b"\x01\x02\x03", 10219),
    ("i386-module.bin", bytes([0xFF]) * 17, 9972),
)


def load(path):
    """读取一个冻结样本。"""
    return Path(path).read_bytes()


def _layout(blob):
    """返回 (NT 头偏移, 可选头偏移, 可选头长度, 节区表偏移)。"""
    nt = struct.unpack_from("<I", blob, 0x3C)[0]
    optional = nt + 24
    size_optional = struct.unpack_from("<H", blob, nt + 20)[0]
    return nt, optional, size_optional, optional + size_optional


def _clear_checksum(blob, optional):
    """把 CheckSum 字段清零，使校验和不再是这些样本的错误来源。"""
    struct.pack_into("<I", blob, optional + 64, 0)


class _Recorder(object):
    """只读的二进制流，记录每次 read 请求的尺寸。"""

    def __init__(self, blob):
        self._stream = io.BytesIO(bytes(blob))
        self.calls = []

    def read(self, size=-1):
        self.calls.append(size)
        return self._stream.read(size)

    def seek(self, offset, whence=0):
        return self._stream.seek(offset, whence)

    def tell(self):
        return self._stream.tell()


# ---------------------------------------------------------------------------
# 两个样本必须被真实描述
# ---------------------------------------------------------------------------


def test_amd64_sample_inspects():
    """64 位样本的全部关键字段。"""
    info = inspect(load(AMD64))
    assert info["machine"] == 0x8664
    assert info["is_pe32_plus"] is True
    assert info["number_of_sections"] == 6
    assert info["image_base"] == 0x180000000
    assert info["size_of_headers"] == 0x400
    assert info["entry_point_rva"] > 0
    assert [section["name"] for section in info["sections"]] == [
        ".text", ".rdata", ".data", ".pdata", ".rsrc", ".reloc"]

    text = info["sections"][0]
    assert text["virtual_address"] == 0x1000
    assert text["virtual_size"] == 0x1068
    assert text["raw_pointer"] == 0x400
    assert text["raw_size"] == 0x1200

    rdata = info["sections"][1]
    assert rdata["virtual_address"] == 0x3000
    assert rdata["raw_pointer"] == 0x1600


def test_i386_sample_inspects():
    """32 位样本的全部关键字段，ImageBase 只有四个字节。"""
    info = inspect(load(I386))
    assert info["machine"] == 0x14C
    assert info["is_pe32_plus"] is False
    assert info["number_of_sections"] == 2
    assert info["image_base"] == 0x400000
    assert info["section_alignment"] == 0x1000
    assert info["file_alignment"] == 0x200
    assert info["size_of_image"] == 0x3000
    assert info["size_of_headers"] == 0x400
    assert [section["name"] for section in info["sections"]] == [".text", ".rdata"]

    text = info["sections"][0]
    assert text["virtual_address"] == 0x1000
    assert text["raw_pointer"] == 0x400
    assert text["raw_size"] == 0x200


# ---------------------------------------------------------------------------
# 校验和
# ---------------------------------------------------------------------------


def test_checksum_matches_authoritative_values():
    """逐个比对权威校验和，包含末尾余数 1、2、3 字节的分支。"""
    for name, extra, expected in AUTHORITATIVE:
        blob = load(ASSETS / name) + extra
        actual = compute_checksum(blob)
        assert actual == expected, "%s + %d 字节尾部：%d != %d" % (
            name, len(extra), actual, expected)


def test_checksum_ignores_the_stored_field():
    """CheckSum 字段自身参与计算前必须当作零。"""
    blob = load(I386)
    _nt, optional, _size_optional, _sectab = _layout(blob)
    expected = 9700
    for value in (0, 1, 0x00009700, 0xDEADBEEF, 0xFFFFFFFF):
        tampered = bytearray(blob)
        struct.pack_into("<I", tampered, optional + 64, value)
        assert compute_checksum(bytes(tampered)) == expected, "字段值 0x%08X" % value


def test_accumulator_matches_authoritative_values():
    """增量累加器给的字节流必须得到同一个权威值，分块边界任意。

    累加器本身只负责它收到的那串字节；把 CheckSum 字段替换成零是调用者的
    事，这里就先做好再喂给它。
    """
    blob = load(AMD64)
    _nt, optional, _size_optional, _sectab = _layout(blob)
    masked = bytearray(blob)
    _clear_checksum(masked, optional)
    expected = 74415
    for step in (1, 3, 7, 4096, len(masked)):
        accumulator = ChecksumAccumulator()
        for start in range(0, len(masked), step):
            accumulator.update(masked[start:start + step])
        assert accumulator.value(len(masked)) == expected, "分块大小 %d" % step


# ---------------------------------------------------------------------------
# RVA 到文件偏移
# ---------------------------------------------------------------------------


def test_rva_inside_headers_maps_to_itself():
    """映像头部直接映射在文件开头，地址不变。"""
    blob = load(I386)
    info = inspect(blob)
    assert info["size_of_headers"] == 0x400
    for rva in (0, 2, 0x40, 0x100, 0x200, 0x3FF):
        assert rva_to_offset(blob, rva) == rva, "rva 0x%X" % rva


def test_rva_inside_a_section_maps_into_the_file():
    """落在一个节区已初始化部分里的地址。"""
    blob = load(AMD64)
    info = inspect(blob)
    for section in info["sections"]:
        if not section["raw_size"] or not section["virtual_size"]:
            continue
        limit = min(section["raw_size"], section["virtual_size"])
        for delta in (0, 1, limit - 1):
            rva = section["virtual_address"] + delta
            expected = section["raw_pointer"] + delta
            assert rva_to_offset(blob, rva) == expected, "rva 0x%X" % rva


def test_rva_in_an_uninitialised_tail_has_no_backing():
    """节区末尾只有虚拟尺寸、没有文件尺寸的那一段没有文件支撑。"""
    blob = load(AMD64)
    info = inspect(blob)
    checked = 0
    for section in info["sections"]:
        assert rva_to_offset(blob, section["virtual_address"]) == section["raw_pointer"]
        if section["virtual_size"] > section["raw_size"]:
            rva = section["virtual_address"] + section["raw_size"]
            assert rva_to_offset(blob, rva) is None, "rva 0x%X" % rva
            checked += 1
    assert checked > 0, "样本里应当至少有一个未初始化尾部"


def test_rva_outside_every_section_has_no_backing():
    """映像范围之外、以及节区之间的空洞都没有文件支撑。"""
    blob = load(I386)
    info = inspect(blob)
    first = info["sections"][0]
    assert rva_to_offset(blob, first["virtual_address"]) == first["raw_pointer"]

    highest = max(section["virtual_address"] + section["virtual_size"]
                  for section in info["sections"])
    assert highest == 0x2040
    for rva in (highest + 1, 0x2800, info["size_of_image"] + 0x1000, 0x7FFFFFFF):
        assert rva_to_offset(blob, rva) is None, "rva 0x%X" % rva


# ---------------------------------------------------------------------------
# 错误分类
# ---------------------------------------------------------------------------


def test_truncated_section_table_reports_truncated():
    """节区表读不完整时是数据不足，不是签名或校验和问题。"""
    blob = load(I386)
    _nt, _optional, _size_optional, sectab = _layout(blob)
    with pytest.raises(WImgError) as excinfo:
        inspect(blob[:sectab + 40])
    assert excinfo.value.kind == KIND_TRUNCATED


def test_unknown_optional_magic_reports_optional():
    """可选头幻数既不是 0x10B 也不是 0x20B。"""
    blob = bytearray(load(I386))
    _nt, optional, _size_optional, _sectab = _layout(blob)
    struct.pack_into("<H", blob, optional, 0x0999)
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_OPTIONAL


def test_section_past_end_of_file_reports_structure():
    """节区声明的文件数据越过文件末尾。"""
    blob = bytearray(load(I386))
    _nt, optional, _size_optional, sectab = _layout(blob)
    struct.pack_into("<I", blob, sectab + 40 + 16, 0x4000)
    _clear_checksum(blob, optional)
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_STRUCTURE


def test_overlapping_virtual_sections_reports_structure():
    """两个节区占用同一段虚拟地址。"""
    blob = bytearray(load(I386))
    _nt, optional, _size_optional, sectab = _layout(blob)
    struct.pack_into("<I", blob, sectab + 40 + 12, 0x1000)
    _clear_checksum(blob, optional)
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_STRUCTURE


def test_overlapping_file_ranges_reports_structure():
    """两个节区占用同一段文件区间。"""
    blob = bytearray(load(I386))
    _nt, optional, _size_optional, sectab = _layout(blob)
    struct.pack_into("<I", blob, sectab + 40 + 20, 0x400)
    _clear_checksum(blob, optional)
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_STRUCTURE


def test_unaligned_section_reports_structure():
    """节区虚拟地址没有按 SectionAlignment 对齐。"""
    blob = bytearray(load(I386))
    _nt, optional, _size_optional, sectab = _layout(blob)
    struct.pack_into("<I", blob, sectab + 40 + 12, 0x2100)
    _clear_checksum(blob, optional)
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_STRUCTURE


def test_undersized_size_of_image_reports_structure():
    """SizeOfImage 装不下自己的节区。"""
    blob = bytearray(load(I386))
    _nt, optional, _size_optional, _sectab = _layout(blob)
    struct.pack_into("<I", blob, optional + 56, 0x1000)
    _clear_checksum(blob, optional)
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_STRUCTURE


def test_structure_is_reported_before_checksum():
    """结构自相矛盾时，即使校验和也对不上，必须先报 structure。"""
    blob = bytearray(load(I386))
    _nt, optional, _size_optional, sectab = _layout(blob)
    struct.pack_into("<I", blob, sectab + 40 + 12, 0x1000)
    struct.pack_into("<I", blob, optional + 64, 0xDEADBEEF)
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_STRUCTURE


# ---------------------------------------------------------------------------
# 流的惰性，以及 verify 的整体行为
# ---------------------------------------------------------------------------


def test_iter_sections_does_not_slurp_the_stream():
    """取第一个节区时不能把整个文件读进来。"""
    blob = load(AMD64)
    stream = _Recorder(blob)
    sections = iter_sections(stream)
    first = next(sections)
    assert first["name"] == ".text"

    assert -1 not in stream.calls, "iter_sections 不允许无尺寸地整读"
    consumed = sum(size for size in stream.calls if size > 0)
    assert consumed < len(blob) // 4, "首条节区之前读了 %d 字节" % consumed

    rest = list(sections)
    assert [section["name"] for section in rest] == [
        ".rdata", ".data", ".pdata", ".rsrc", ".reloc"]


def test_verify_rejects_every_structural_variant():
    """结构不合法的每一种变形都不能被 verify 接受。"""
    blob = load(I386)
    assert verify(blob) is True

    variants = _structural_variants(blob)
    assert len(variants) >= 6
    for label in sorted(variants):
        assert verify(variants[label]) is False, "verify 接受了 %s" % label


def _structural_variants(blob):
    """构造若干个只有结构问题、校验和不成问题的变形。"""
    _nt, optional, _size_optional, sectab = _layout(blob)
    variants = {}

    past_end = bytearray(blob)
    struct.pack_into("<I", past_end, sectab + 40 + 16, 0x4000)
    _clear_checksum(past_end, optional)
    variants["section-past-end-of-file"] = bytes(past_end)

    virtual_overlap = bytearray(blob)
    struct.pack_into("<I", virtual_overlap, sectab + 40 + 12, 0x1000)
    _clear_checksum(virtual_overlap, optional)
    variants["overlapping-virtual-sections"] = bytes(virtual_overlap)

    file_overlap = bytearray(blob)
    struct.pack_into("<I", file_overlap, sectab + 40 + 20, 0x400)
    _clear_checksum(file_overlap, optional)
    variants["overlapping-file-ranges"] = bytes(file_overlap)

    unaligned = bytearray(blob)
    struct.pack_into("<I", unaligned, sectab + 40 + 12, 0x2100)
    _clear_checksum(unaligned, optional)
    variants["unaligned-section"] = bytes(unaligned)

    undersized = bytearray(blob)
    struct.pack_into("<I", undersized, optional + 56, 0x1000)
    _clear_checksum(undersized, optional)
    variants["undersized-size-of-image"] = bytes(undersized)

    variants["truncated-section-table"] = blob[:sectab + 40]
    variants["truncated-optional-header"] = blob[:optional + 8]

    return variants


# ---------------------------------------------------------------------------
# 不得回归的既有契约
# ---------------------------------------------------------------------------


def test_non_mz_prefix_reports_dos():
    with pytest.raises(WImgError) as excinfo:
        inspect(b"ZZ" + b"\0" * 200)
    assert excinfo.value.kind == KIND_DOS


def test_missing_pe_signature_reports_signature():
    blob = bytearray(load(I386))
    nt, _optional, _size_optional, _sectab = _layout(blob)
    blob[nt:nt + 4] = b"PX\0\0"
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_SIGNATURE


def test_mismatched_checksum_reports_checksum():
    """结构完好但记录的校验和对不上。"""
    blob = bytearray(load(I386))
    _nt, optional, _size_optional, _sectab = _layout(blob)
    struct.pack_into("<I", blob, optional + 64, 0x12345678)
    with pytest.raises(WImgError) as excinfo:
        inspect(bytes(blob))
    assert excinfo.value.kind == KIND_CHECKSUM


def test_verify_never_raises():
    probes = [
        b"",
        b"M",
        b"MZ",
        b"MZ" + b"\0" * 0x3C,
        b"ZZ" + b"\0" * 200,
        bytes(4096),
        bytes(range(256)) * 8,
        load(I386)[:100],
        load(I386)[:0x200],
        load(AMD64)[:0x300],
    ]
    for blob in probes:
        assert verify(blob) is False


def test_negative_rva_has_no_backing():
    for path in (I386, AMD64):
        blob = load(path)
        assert rva_to_offset(blob, -1) is None
        assert rva_to_offset(blob, -0x1000) is None


def test_public_surface_is_unchanged():
    expected = {
        "ChecksumAccumulator",
        "KIND_CHECKSUM",
        "KIND_DOS",
        "KIND_OPTIONAL",
        "KIND_SIGNATURE",
        "KIND_STRUCTURE",
        "KIND_TRUNCATED",
        "KINDS",
        "WImgError",
        "compute_checksum",
        "inspect",
        "iter_sections",
        "rva_to_offset",
        "verify",
    }
    assert set(wpeimg.__all__) == expected
    for name in sorted(expected):
        assert hasattr(wpeimg, name), name

    assert wpeimg.KIND_DOS == "dos"
    assert wpeimg.KIND_SIGNATURE == "signature"
    assert wpeimg.KIND_OPTIONAL == "optional"
    assert wpeimg.KIND_TRUNCATED == "truncated"
    assert wpeimg.KIND_STRUCTURE == "structure"
    assert wpeimg.KIND_CHECKSUM == "checksum"
    assert set(wpeimg.KINDS) == {
        "dos", "signature", "optional", "truncated", "structure", "checksum"}

    accumulator = ChecksumAccumulator()
    assert accumulator.update(b"abcd") is accumulator
    assert isinstance(accumulator.value(4), int)


def test_accumulator_matches_one_shot_helper():
    """对同一串字节，分块喂给累加器与一次性计算必须一致。"""
    blob = bytes(range(256)) * 7 + b"\x01\x02\x03"
    one_shot = compute_checksum(blob)
    assert isinstance(one_shot, int)
    for step in (1, 3, 100, 4096):
        accumulator = ChecksumAccumulator()
        for start in range(0, len(blob), step):
            accumulator.update(blob[start:start + step])
        assert accumulator.value(len(blob)) == one_shot, "分块大小 %d" % step


def test_package_has_no_external_dependencies():
    """包只依赖标准库，也不借系统库或子进程替它算校验和。"""
    package = Path(wpeimg.__file__).resolve().parent
    sources = sorted(package.glob("*.py"))
    assert sources, "包目录里没有找到源码"

    patterns = (
        r"\bimport\s+ctypes\b",
        r"\bfrom\s+ctypes\b",
        r"\bctypes\s*\.",
        r"\bWinDLL\b",
        r"\bwindll\b",
        r"\bimport\s+subprocess\b",
        r"\bsubprocess\s*\.",
    )
    for source in sources:
        text = source.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            assert not re.search(pattern, text), "%s 命中了 %s" % (
                source.name, pattern)
