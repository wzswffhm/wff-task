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
    signature_info,
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


# 目录数组起始偏移随可选头布局变化（PE32 / PE32+），声明数所在偏移也不同。
DIRECTORY_OFFSET = {False: 96, True: 112}
RVA_AND_SIZES_OFFSET = {False: 92, True: 108}
DIRECTORY_ORDER = [
    "export", "import", "resource", "exception", "certificate", "relocation",
    "debug", "architecture", "global_ptr", "tls", "load_config",
    "bound_import", "iat", "delay_import", "clr_runtime", "reserved",
]


def _is_plus(blob, optional):
    return struct.unpack_from("<H", blob, optional)[0] == 0x20B


def _set_declared_count(blob, optional, count):
    plus = _is_plus(blob, optional)
    struct.pack_into("<I", blob, optional + RVA_AND_SIZES_OFFSET[plus], count)


def _set_directory(blob, optional, index, virtual_address, size):
    plus = _is_plus(blob, optional)
    base = optional + DIRECTORY_OFFSET[plus] + index * 8
    struct.pack_into("<II", blob, base, virtual_address, size)


class _Recorder(object):
    """只读的二进制流，记录每次 read 请求的 (起始偏移, 尺寸)。"""

    def __init__(self, blob):
        self._stream = io.BytesIO(bytes(blob))
        self.calls = []

    def read(self, size=-1):
        self.calls.append((self._stream.tell(), size))
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
# 目录表与 Authenticode 尾部（PE 格式的位置语义）
# ---------------------------------------------------------------------------


def test_data_directories_follow_the_pe_order():
    """16 项按 PE 固定顺序排列，名称与样本真实内容一致。"""
    for path in (AMD64, I386):
        info = inspect(load(path))
        directories = info["data_directories"]
        assert isinstance(directories, list)
        assert len(directories) == 16, "%s: %d 项" % (path.name, len(directories))
        assert [d["name"] for d in directories] == DIRECTORY_ORDER
        for entry in directories:
            assert set(entry) >= {"name", "virtual_address", "size"}
            assert isinstance(entry["virtual_address"], int)
            assert isinstance(entry["size"], int)


def test_data_directories_use_the_layout_specific_offset():
    """PE32 与 PE32+ 的目录数组起始偏移不同（96 / 112）。

    判据不依赖某一种写法：先把两个样本的**同一个**目录槽位写成可识别的值，
    再断言读出来的就是那个值。写错布局偏移的实现会把 PE32 的槽位读成
    PE32+ 的位置，因而读到别处的字节。
    """
    for path in (AMD64, I386):
        blob = bytearray(load(path) + b"\0" * 4096)
        _nt, optional, _size_opt, _sectab = _layout(blob)
        plus = _is_plus(blob, optional)
        # 目标槽位 index 12（iat）与 index 15（reserved）各写一组可识别值
        for index, va, size in ((12, 0x00ABCDEF, 0x11), (15, 0x00765432, 0x22)):
            marker = bytearray(blob)
            _set_directory(marker, optional, index, va, size)
            _clear_checksum(marker, optional)
            entry = inspect(bytes(marker))["data_directories"][index]
            assert entry["virtual_address"] == va, (
                "%s slot %d: 0x%X != 0x%X（布局偏移 %d 用错了？）"
                % (path.name, index, entry["virtual_address"], va,
                   DIRECTORY_OFFSET[plus]))
            assert entry["size"] == size
        # PE32 的目录数组必须落在它自己的偏移上，不能是 PE32+ 的偏移
        assert DIRECTORY_OFFSET[plus] == (112 if plus else 96)


def test_data_directories_respect_declared_count():
    """数组长度由 NumberOfRvaAndSizes 决定，未声明的槽位补 0。"""
    blob = bytearray(load(AMD64) + b"\0" * 4096)
    _nt, optional, _size_opt, _sectab = _layout(blob)

    # 声明 3 项：只有前 3 项允许非零，其余 13 项必须是 0
    partial = bytearray(blob)
    _set_declared_count(partial, optional, 3)
    _clear_checksum(partial, optional)
    directories = inspect(bytes(partial))["data_directories"]
    assert len(directories) == 16
    for index in range(3, 16):
        assert directories[index]["virtual_address"] == 0, "slot %d 应补 0" % index
        assert directories[index]["size"] == 0, "slot %d 应补 0" % index

    # 声明 0 项：整张表都是 0
    zero = bytearray(blob)
    _set_declared_count(zero, optional, 0)
    _clear_checksum(zero, optional)
    directories = inspect(bytes(zero))["data_directories"]
    assert all(d["virtual_address"] == 0 and d["size"] == 0 for d in directories)

    # 声明超过 16 项：只取前 16，不越界、不抛错
    over = bytearray(blob)
    _set_declared_count(over, optional, 64)
    _clear_checksum(over, optional)
    directories = inspect(bytes(over))["data_directories"]
    assert len(directories) == 16


def test_data_directories_ignore_slots_the_header_cannot_hold():
    """声明数超出可选头容量时，越界槽位按 0 处理且不得抛异常。

    做法：把可选头**扩大**到刚好容纳前 6 个槽位，再声明 16 项。第 7 项起就落在
    可选头之外了——按契约它们必须按 0 处理，而不能去读节区表或文件尾部的内容。
    节区表随之顺延，所以这里只断言目录数组本身，不看节区。
    """
    blob = bytearray(load(AMD64) + b"\0" * 4096)
    nt, optional, size_opt, _sectab = _layout(blob)
    plus = _is_plus(blob, optional)
    tight = DIRECTORY_OFFSET[plus] + 6 * 8          # 只装得下前 6 项
    # 先把节区表整体后移，给"更大但只声明 6 项容量"的可选头腾地方
    sections_bytes = bytes(blob[optional + size_opt:optional + size_opt + 6 * 40])
    grown = bytearray(blob[:optional + tight])
    grown += sections_bytes
    grown += b"\0" * (len(blob) - len(grown))
    struct.pack_into("<H", grown, nt + 20, tight)
    _set_declared_count(grown, optional, 16)
    _clear_checksum(grown, optional)
    directories = inspect(bytes(grown))["data_directories"]
    assert len(directories) == 16
    for index in range(6, 16):
        assert directories[index]["virtual_address"] == 0, "slot %d 应越界补 0" % index
        assert directories[index]["size"] == 0, "slot %d 应越界补 0" % index


def test_authenticode_signature_detection():
    """证书表目录项指向真实字节才算有签名。"""
    # 真实样本：尾部 13304 字节的签名被证书表覆盖 → True
    amd64 = inspect(load(AMD64))
    assert amd64["has_authenticode_signature"] is True
    # 合成样本：没有证书表 → False
    i386 = inspect(load(I386))
    assert i386["has_authenticode_signature"] is False


def test_authenticode_signature_requires_backing_bytes():
    """记录了一个无法落地的证书表区间时不得报有签名。"""
    blob = bytearray(load(AMD64) + b"\0" * 4096)
    _nt, optional, _size_opt, _sectab = _layout(blob)

    # 区间越过文件末尾
    past = bytearray(blob)
    _set_directory(past, optional, 4, len(past) - 8, 4096)
    _clear_checksum(past, optional)
    assert inspect(bytes(past))["has_authenticode_signature"] is False

    # 有偏移但长度为 0
    empty = bytearray(blob)
    _set_directory(empty, optional, 4, 0x1000, 0)
    _clear_checksum(empty, optional)
    assert inspect(bytes(empty))["has_authenticode_signature"] is False

    # 两个字段都为 0
    none = bytearray(blob)
    _set_directory(none, optional, 4, 0, 0)
    _clear_checksum(none, optional)
    assert inspect(bytes(none))["has_authenticode_signature"] is False


def test_trailing_bytes_are_not_a_structural_error():
    """映像尾部带签名或 overlay 必须被接受，不得因为"多出来的字节"报错。

    追加尾部会改变 Windows 映像校验和，所以这里把重算后的值写回 CheckSum
    字段——考的正是"结构上多出来的字节合法"，而不是校验和。
    """
    for path in (AMD64, I386):
        blob = bytearray(load(path))
        _nt, optional, _size_opt, _sectab = _layout(blob)
        padded = bytearray(bytes(blob) + b"\xA5" * 777)
        _clear_checksum(padded, optional)
        struct.pack_into("<I", padded, optional + 64, compute_checksum(bytes(padded)))
        info = inspect(bytes(padded))
        assert info["number_of_sections"] == inspect(bytes(blob))["number_of_sections"]
        assert verify(bytes(padded)) is True


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
    """取第一个节区时不能把整个文件读进来，且读取量只由节区表位置决定。

    判据不绑定任何缓冲大小：Windows 加载器用的节区表位置由
    ``e_lfanew``、SizeOfOptionalHeader 与 ``NumberOfSections`` 决定，与文件
    总长度无关。因此把同一个映像的**尾部**加长（模拟真实映像普遍携带的
    Authenticode 签名 / overlay），“取到第一条节区之前”的读取量必须**逐字节
    不变**；线性增长的实现（先整体读进来再看）会被这条检查拒绝。
    """
    blob = load(AMD64)
    padded = blob + b"\x00" * (len(blob) * 8)

    baseline = _Recorder(blob)
    sections = iter_sections(baseline)
    first = next(sections)
    assert first["name"] == ".text"
    consumed_base = sum(max(size, 0) for _offset, size in baseline.calls)
    calls_at_first = len(baseline.calls)

    assert all(size >= 0 for _offset, size in baseline.calls), (
        "iter_sections 不允许无尺寸地整读")
    assert consumed_base < len(blob), "首条节区之前读了 %d 字节" % consumed_base

    # 惰性：交出第一条节区之后仍在继续读取，而不是一开始就整体读完。
    rest = list(sections)
    assert [section["name"] for section in rest] == [
        ".rdata", ".data", ".pdata", ".rsrc", ".reloc"]
    assert len(baseline.calls) > calls_at_first

    # 放大 9 倍（尾部加长）后，首条节区之前的读取量不得变化。
    grown = _Recorder(padded)
    grown_sections = iter_sections(grown)
    grown_first = next(grown_sections)
    assert grown_first["name"] == ".text"
    consumed_grown = sum(max(size, 0) for _offset, size in grown.calls)
    assert consumed_grown == consumed_base, (
        "首条节区之前的读取量随文件长度增长：%d -> %d"
        % (consumed_base, consumed_grown))


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


# ---------------------------------------------------------------------------
# Authenticode 签名内容（必须自己解析 DER）
# ---------------------------------------------------------------------------


def _raw_certificate_entry(blob):
    """Return (optional_offset, certificate_entry_offset) of a sample."""
    _nt, optional, _size_opt, _sectab = _layout(blob)
    plus = _is_plus(blob, optional)
    return optional, optional + DIRECTORY_OFFSET[plus] + 4 * 8


def test_signature_info_describes_the_real_signed_data():
    """真实签名：类型、OID、算法、证书数与签名者数都要对。"""
    info = signature_info(load(AMD64))
    assert info["present"] is True
    assert info["offset"] == 13824, info["offset"]
    assert info["size"] == 13304, info["size"]
    assert info["declared_length"] == 13304, info["declared_length"]
    assert info["revision"] == 0x0200, hex(info["revision"])
    assert info["certificate_type"] == 0x0002, hex(info["certificate_type"])
    assert info["content_type"] == "1.2.840.113549.1.7.2", info["content_type"]
    assert info["digest_algorithms"] == ["sha256"], info["digest_algorithms"]
    assert info["certificate_count"] == 4, info["certificate_count"]
    assert info["signer_count"] == 1, info["signer_count"]


def test_signature_info_without_a_certificate_table():
    """没有证书表的映像必须返回「无签名」值且不得抛异常。"""
    info = signature_info(load(I386))
    assert info["present"] is False
    assert info["offset"] == 0 and info["size"] == 0
    assert info["content_type"] is None
    assert info["digest_algorithms"] == []
    assert info["certificate_count"] == 0 and info["signer_count"] == 0
    # 残缺输入同样不得抛异常
    for blob in (b"", b"MZ", b"MZ" + b"\0" * 200):
        assert signature_info(blob)["present"] is False


def test_signature_info_skips_non_pkcs7_records():
    """wCertificateType 不是 0x0002 时只报头字段，不解记录体。"""
    blob = bytearray(load(AMD64))
    optional, entry_off = _raw_certificate_entry(blob)
    offset, size = struct.unpack_from("<II", blob, entry_off)
    struct.pack_into("<H", blob, offset + 6, 0x0001)   # X509，不是 PKCS#7
    info = signature_info(bytes(blob))
    assert info["present"] is True
    assert info["certificate_type"] == 0x0001
    assert info["content_type"] is None
    assert info["certificate_count"] == 0 and info["signer_count"] == 0
    assert info["digest_algorithms"] == []


def test_signature_info_rejects_a_length_that_cannot_hold():
    """dwLength 与文件对不上时必须抛结构错误。"""
    # 自称长度大于证书表区间
    blob = bytearray(load(AMD64))
    _optional, entry_off = _raw_certificate_entry(blob)
    offset, size = struct.unpack_from("<II", blob, entry_off)
    struct.pack_into("<I", blob, offset, size + 8)
    with pytest.raises(WImgError) as excinfo:
        signature_info(bytes(blob))
    assert excinfo.value.kind == "structure"

    # 自称长度小于 8（连头都装不下）
    blob2 = bytearray(load(AMD64))
    _optional2, entry_off2 = _raw_certificate_entry(blob2)
    offset2, _size2 = struct.unpack_from("<II", blob2, entry_off2)
    struct.pack_into("<I", blob2, offset2, 4)
    with pytest.raises(WImgError) as excinfo2:
        signature_info(bytes(blob2))
    assert excinfo2.value.kind == "structure"


def test_signature_info_is_offline_and_standard_library_only():
    """签名必须自己解析：不得调用系统库或子进程。"""
    import wpeimg.signature as signature_module

    # 被测实现可以叫别的模块名，但包里任何模块都不得碰系统库/子进程
    package_dir = Path(wpeimg.__file__).resolve().parent
    for source in sorted(package_dir.glob("*.py")):
        text = source.read_text(encoding="utf-8", errors="replace")
        for pattern in (r"\bimport\s+ctypes\b", r"\bfrom\s+ctypes\b", r"\bctypes\s*\.",
                        r"\bWinDLL\b", r"\bwindll\b", r"\bimport\s+subprocess\b",
                        r"\bsubprocess\s*\."):
            assert not re.search(pattern, text), "%s 命中了 %s" % (source.name, pattern)
    # DER 解析必须自己实现：返回的 OID 是点号字符串而不是原始字节
    info = signature_info(load(AMD64))
    assert isinstance(info["content_type"], str)
    assert info["content_type"].count(".") == 6, info["content_type"]
    assert signature_module is not None


# ---------------------------------------------------------------------------
# 判分期真实调用 Windows 系统服务（不是离线常量比对）
# ---------------------------------------------------------------------------

WIN_SERVICES_REASON = ""


def _win_services():
    """Import the verifier-side Windows helpers, failing loudly if unavailable.

    判分环境就是 Windows 容器；系统组件拿不到意味着判据没生效，属于判分环境
    故障，必须显式暴露而不是静默跳过。

    套件与 helper 由平台一起投放到 `C:\\tests`，但 pytest 在不同 cwd/rootdir 下
    对 sys.path 的处理并不一致（容器里实测不会自动加入测试文件所在目录），所以
    这里显式把本文件所在目录放进去。
    """
    global WIN_SERVICES_REASON
    import sys
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import win_services
    except Exception as exc:  # noqa: BLE001
        WIN_SERVICES_REASON = ("win_services unavailable (%r); looked in %s; "
                               "dir listing=%s"
                               % (exc, here, sorted(p.name for p in Path(here).iterdir())))
        pytest.fail(WIN_SERVICES_REASON)
    ok, reason = win_services.live_checksum_available()
    if not ok:
        WIN_SERVICES_REASON = reason
        pytest.fail(reason)
    return win_services


def _section_data_offset(blob):
    """返回一个落在第一个节区**文件数据**里的偏移（改它不会破坏结构）。"""
    _nt, optional, size_optional, sectab = _layout(blob)
    nsec = struct.unpack_from("<H", blob, _nt + 6)[0]
    first_raw = struct.unpack_from("<I", blob, sectab + 20)[0]      # PointerToRawData
    first_size = struct.unpack_from("<I", blob, sectab + 16)[0]     # SizeOfRawData
    if first_size < 64 or not first_raw:
        first_raw = struct.unpack_from("<I", blob, sectab + 40 + 20)[0]
    return min(max(first_raw, sectab + 40 * nsec), len(blob) - 64)


def test_checksum_matches_a_live_windows_query():
    """权威值必须在判分期向 Windows 系统库现取，而不是比对固化常量。"""
    win = _win_services()
    base = load(AMD64)
    # MapFileAndCheckSumW 返回 (映像里记录的 HeaderSum, 它算出的 CheckSum)
    header_sum, check_sum = win.live_checksum(base)
    assert header_sum == 74415, header_sum
    assert check_sum == 74415, check_sum
    assert compute_checksum(base) == check_sum

    variant = win.make_checksum_variant(base, _section_data_offset(base))
    live_header, live_check = win.live_checksum(variant)
    # 变体是被重写过 CheckSum 字段的：记录值必须等于系统库算出的值
    assert live_header == live_check, (live_header, live_check)
    # 变体是判分期构造的：它的权威值不可能被预先硬编码
    assert live_check != check_sum, (live_check, check_sum)
    assert compute_checksum(variant) == live_check, (
        "compute_checksum=%d but imagehlp!MapFileAndCheckSumW said %d"
        % (compute_checksum(variant), live_check))


def test_checksum_matches_live_queries_across_variants():
    """多个判分期变体逐一与系统库对照，避免只对上某一个巧合值。"""
    win = _win_services()
    base = load(AMD64)
    offset = _section_data_offset(base)
    seen = set()
    for idx, (mask, tail) in enumerate((
            (0x5A, b""),
            (0xA5, b""),
            (0x3C, b"\x00" * 17),
            (0xFF, b"tail-bytes"),
    )):
        variant = win.make_checksum_variant(base, offset + idx * 8, mask, tail)
        _h, live = win.live_checksum(variant)
        seen.add(live)
        assert compute_checksum(variant) == live, (
            "variant %d: compute_checksum=%d, live=%d"
            % (idx, compute_checksum(variant), live))
    assert len(seen) >= 3, "变体没有产生足够不同的权威值：%s" % sorted(seen)


def test_iter_sections_reads_a_real_windows_file_handle():
    """流式读取必须能在 CreateFileW 打开的真实句柄上工作。"""
    win = _win_services()
    handle, size = win.open_real_handle(AMD64)
    try:
        with win.handle_to_file(handle) as fh:
            sections = list(iter_sections(fh))
    finally:
        win.close_handle(handle)
    assert size == AMD64.stat().st_size
    assert [s["name"] for s in sections] == [
        ".text", ".rdata", ".data", ".pdata", ".rsrc", ".reloc"]
    assert [(s["raw_pointer"], s["raw_size"]) for s in sections] == [
        (1024, 4608), (5632, 4096), (9728, 512),
        (10240, 512), (10752, 2560), (13312, 512)]
    assert [(s["virtual_address"], s["virtual_size"]) for s in sections] == [
        (4096, 4200), (12288, 3784), (16384, 1888),
        (20480, 480), (24576, 2456), (28672, 64)]


def test_iter_sections_is_bounded_on_a_real_handle():
    """真实句柄上也不得整体读取：只允许带长度的 read(n)。"""
    win = _win_services()
    base = load(AMD64)
    counts = []
    for _payload in (base, base + b"\x00" * (len(base) * 7)):
        handle, _size = win.open_real_handle(AMD64)
        try:
            with win.handle_to_file(handle) as fh:
                reader = win.BoundedReader(fh)
                stream = iter_sections(reader)
                first = next(stream)
                counts.append((first["name"], reader.bytes_read, reader.unbounded))
                list(stream)
        finally:
            win.close_handle(handle)
        assert reader.unbounded == 0, "出现了无界读取"
    assert counts[0][0] == counts[1][0] == ".text"
    # 判据：读取量由头部与节区表决定，与文件总长度无关（尾部放大 8 倍不改变它）
    assert counts[0][1] == counts[1][1], (
        "尾部放大 8 倍后取第一条节区的读取量从 %d 变成 %d，说明读取没有上界"
        % (counts[0][1], counts[1][1]))
    assert counts[0][1] < len(base) // 4, (
        "取第一条节区就读了 %d 字节（映像 %d 字节），不是惰性读取"
        % (counts[0][1], len(base)))


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
        "signature_info",
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
