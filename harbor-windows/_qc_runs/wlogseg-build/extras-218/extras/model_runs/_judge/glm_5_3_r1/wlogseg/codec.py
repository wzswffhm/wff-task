"""容器整体读写：文件头、段区、尾部索引与尾部校验和。

真实布局以 ``assets/`` 下的样本为准（``docs/FORMAT.md`` 是早期草稿，与实际
不一致）::

    偏移
         +----------------------+  <- 0
    0    | 文件头（16 字节）     |
         +----------------------+  <- 16
         | 段 0                 |
         | 段 1                 |   每段：8 字节段头 + payload + 0 填充，
         | ...                  |   段总长补齐到 8 字节的整数倍
         +----------------------+  <- header.index_offset
         | 尾部索引              |   每段 8 字节：(起始偏移, 段总长)
         +----------------------+
         | 尾部校验和（8 字节）   |   (索引区 CRC-32, 头+段区 CRC-32)
         +----------------------+  <- 文件末尾

两个校验和都是标准 CRC-32/ISO-HDLC（见 :mod:`wlogseg.crc`）。第二个校验和
覆盖**文件头与整个段区（含填充）**，第一个覆盖整个尾部索引区。

:func:`scan` 是整体解析（:func:`unpack`）与流式解析
（:mod:`wlogseg.stream`）共用的惰性扫描器，保证两条路径对同一个容器给出
完全一致的结果和完全一致的错误分类。
"""

from __future__ import annotations

import io
import struct

from .crc import compute_crc, crc32_update
from .errors import WSegError
from .header import HEADER_SIZE, build_header, parse_header
from .index import INDEX_ENTRY_SIZE, build_index, parse_index
from .segment import (
    MAX_BODY,
    MAX_SEG_ID,
    SEGMENT_HEADER_SIZE,
    encode_segment,
    parse_segment_header,
    segment_length,
)

TRAILER_SIZE = 8

_TRAILER = struct.Struct("<II")

#: 流式读取时单次向文件对象索要的字节数上限。
MAX_READ_CHUNK = 64 * 1024

#: 段数量字段是 16 位。
MAX_SEGMENTS = 0xFFFF

#: 偏移字段是 32 位。
MAX_CONTAINER_SIZE = 0xFFFFFFFF


# ---------------------------------------------------------------------------
# 受限读取：只允许用固定大小的 read(n) 向文件对象要数据
# ---------------------------------------------------------------------------

def _read_chunk(handle, size):
    """向 ``handle`` 索要至多 ``size`` 字节并返回 ``bytes``。

    只调用 ``read(n)``（``n`` 为正整数），绝不整体读取。
    """
    if size <= 0:
        return b""
    ask = size if size <= MAX_READ_CHUNK else MAX_READ_CHUNK
    chunk = handle.read(ask)
    if chunk is None:
        return b""
    if not isinstance(chunk, (bytes, bytearray, memoryview)):
        raise WSegError(
            "structure", f"the stream returned {type(chunk).__name__} instead of bytes"
        )
    return bytes(chunk)


def _read_exact(handle, size, what):
    """读取恰好 ``size`` 字节；流提前结束时抛 ``truncated``。"""
    if size <= 0:
        return b""
    buf = bytearray()
    while len(buf) < size:
        chunk = _read_chunk(handle, size - len(buf))
        if not chunk:
            raise WSegError(
                "truncated", f"{what} needs {size} bytes, but the stream ended after {len(buf)}"
            )
        buf += chunk
    return bytes(buf)


def _read_header(handle):
    """读取并校验文件头；数据不足时也优先报告 magic / version 问题。"""
    buf = bytearray()
    while len(buf) < HEADER_SIZE:
        chunk = _read_chunk(handle, HEADER_SIZE - len(buf))
        if not chunk:
            break
        buf += chunk
    prefix = bytes(buf)
    version, _flags, _seg_count, _index_offset = parse_header(prefix)
    if len(prefix) < HEADER_SIZE:
        raise WSegError(
            "truncated",
            f"the file header needs {HEADER_SIZE} bytes, got {len(prefix)}",
        )
    return prefix


# ---------------------------------------------------------------------------
# 共用的惰性扫描器
# ---------------------------------------------------------------------------

def scan(handle, total_size=None):
    """惰性解析容器，产出 ``(seg_id, payload)``。

    ``handle`` 是任意支持 ``read(n)`` 的文件对象，且**只会**被以固定大小的
    ``read(n)`` 访问，整个容器不会被一次性读进内存。已知容器完整长度时把它
    传给 ``total_size``，可以额外检查“尾部之后没有多余字节”。

    取完最后一段之后，本函数仍会读取并校验尾部索引与尾部校验和，因此调用方
    必须把生成器迭代到底才能得到完整的校验结果。
    """
    header = _read_header(handle)
    _version, _flags, seg_count, index_offset = parse_header(header)
    if index_offset < HEADER_SIZE:
        raise WSegError(
            "structure", f"index offset {index_offset} overlaps the file header"
        )

    crc = crc32_update(header)
    spans = []
    cursor = HEADER_SIZE
    for index in range(seg_count):
        if cursor + SEGMENT_HEADER_SIZE > index_offset:
            raise WSegError(
                "structure",
                f"segment {index} at {cursor} would cross the index offset {index_offset}",
            )
        head = _read_exact(handle, SEGMENT_HEADER_SIZE, f"the header of segment {index}")
        seg_id, _seg_flags, body_len = parse_segment_header(head, 0, len(head))
        total = segment_length(body_len)
        if cursor + total > index_offset:
            raise WSegError(
                "structure",
                f"segment {index} at {cursor} would cross the index offset {index_offset}",
            )
        crc = crc32_update(head, crc)
        payload = _read_exact(handle, body_len, f"the payload of segment {index}")
        crc = crc32_update(payload, crc)
        padding = total - SEGMENT_HEADER_SIZE - body_len
        if padding:
            crc = crc32_update(
                _read_exact(handle, padding, f"the padding of segment {index}"), crc
            )
        spans.append((cursor, total))
        cursor += total
        yield seg_id, payload

    if cursor != index_offset:
        raise WSegError(
            "structure",
            f"the segment region ends at {cursor}, but the index starts at {index_offset}",
        )

    index_end = index_offset + INDEX_ENTRY_SIZE * seg_count
    index_region = _read_exact(handle, INDEX_ENTRY_SIZE * seg_count, "the tail index")
    trailer = _read_exact(handle, TRAILER_SIZE, "the trailer")

    index_crc, data_crc = _TRAILER.unpack(trailer)
    if crc != data_crc:
        raise WSegError(
            "checksum", "the header and the segment region do not match their checksum"
        )
    if compute_crc(index_region) != index_crc:
        raise WSegError("checksum", "the tail index does not match its checksum")

    if total_size is not None and index_end + TRAILER_SIZE != total_size:
        raise WSegError(
            "structure",
            f"the trailer should end at {index_end + TRAILER_SIZE} bytes, "
            f"but the container is {total_size} bytes long",
        )

    entries = parse_index(index_region, 0, seg_count)
    for index, entry in enumerate(entries):
        if entry != spans[index]:
            raise WSegError(
                "structure",
                f"tail index entry {index} is {entry}, but the segment occupies {spans[index]}",
            )


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def _normalize_segments(segments):
    """校验并把输入规整成 ``[(seg_id, bytes), ...]``。"""
    try:
        iterator = iter(segments)
    except TypeError:
        raise WSegError(
            "structure",
            f"pack expects a sequence of (seg_id, payload) pairs, "
            f"got {type(segments).__name__}",
        )
    items = []
    for item in iterator:
        try:
            seg_id, payload = item
        except (TypeError, ValueError):
            raise WSegError(
                "structure", f"segment entry {item!r} is not a (seg_id, payload) pair"
            )
        if isinstance(seg_id, bool) or not isinstance(seg_id, int):
            raise WSegError("structure", f"segment id {seg_id!r} is not an integer")
        if not 0 <= seg_id <= MAX_SEG_ID:
            raise WSegError(
                "structure", f"segment id {seg_id} out of range 0..{MAX_SEG_ID}"
            )
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise WSegError(
                "structure", f"payload {type(payload).__name__} is not a bytes-like object"
            )
        body = bytes(payload)
        if len(body) > MAX_BODY:
            raise WSegError("structure", "payload is too large")
        items.append((seg_id, body))
    if len(items) > MAX_SEGMENTS:
        raise WSegError(
            "structure", f"too many segments: {len(items)} (max {MAX_SEGMENTS})"
        )
    return items


def pack(segments) -> bytes:
    """把 [(seg_id, payload), ...] 序列化为 WLSG 字节串。"""
    items = _normalize_segments(segments)

    body = bytearray()
    entries = []
    cursor = HEADER_SIZE
    for seg_id, payload in items:
        encoded = encode_segment(seg_id, payload)
        entries.append((cursor, len(encoded)))
        body += encoded
        cursor += len(encoded)

    index_offset = cursor
    if index_offset > MAX_CONTAINER_SIZE:
        raise WSegError(
            "structure",
            f"the container is too large to be indexed ({index_offset} bytes)",
        )

    header = build_header(len(items), index_offset)
    index_region = build_index(entries)

    crc = crc32_update(header)
    crc = crc32_update(body, crc)
    trailer = _TRAILER.pack(compute_crc(index_region), crc)
    return bytes(header) + bytes(body) + index_region + trailer


def unpack(data) -> list:
    """解析 WLSG 字节串；任何结构 / 完整性问题都抛 WSegError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WSegError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)
    return list(scan(io.BytesIO(data), len(data)))


def verify(data) -> bool:
    """返回 data 是否是合法 WLSG 容器；**永不抛异常**。"""
    try:
        unpack(data)
        return True
    except Exception:  # noqa: BLE001
        return False
