"""流式读取。"""

from __future__ import annotations

import struct

from .crc import crc32_update
from .errors import WSegError
from .header import HEADER_SIZE, parse_header
from .index import INDEX_ENTRY_SIZE, parse_index
from .segment import SEGMENT_HEADER_SIZE, parse_segment_header, segment_length
from .crc import compute_crc

TRAILER_SIZE = 8
_TRAILER = struct.Struct("<II")


def _read_exact(handle, n: int, context: str = "") -> bytes:
    """从 handle 精确读取 n 字节；不足时抛 WSegError(truncated)。"""
    if n <= 0:
        return b""
    chunks = []
    remaining = n
    while remaining > 0:
        chunk = handle.read(remaining)
        if not chunk:
            raise WSegError("truncated",
                            f"unexpected end of stream{': ' + context if context else ''}")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def iter_segments(handle):
    """惰性产出 (seg_id, payload)，不将整个容器读入内存。

    只使用 ``handle.read(n)``（n 为正整数）读取数据。
    取完最后一段后仍校验尾部索引与校验和；失败抛 WSegError。
    """
    # --- 1. 文件头 ---
    header_bytes = _read_exact(handle, HEADER_SIZE, "header")
    _version, _flags, seg_count, index_offset = parse_header(header_bytes)

    # 增量 CRC：覆盖 header + 段区
    running_crc = crc32_update(header_bytes, 0)

    # --- 2. 逐段读取并 yield ---
    for _i in range(seg_count):
        seg_hdr = _read_exact(handle, SEGMENT_HEADER_SIZE, "segment header")
        seg_id, _seg_flags, body_len = parse_segment_header(
            seg_hdr, 0, SEGMENT_HEADER_SIZE
        )
        total_seg_len = segment_length(body_len)
        tail_len = total_seg_len - SEGMENT_HEADER_SIZE  # payload + padding

        if tail_len > 0:
            tail_bytes = _read_exact(handle, tail_len, "segment payload+padding")
        else:
            tail_bytes = b""

        running_crc = crc32_update(seg_hdr, running_crc)
        if tail_bytes:
            running_crc = crc32_update(tail_bytes, running_crc)

        payload = tail_bytes[:body_len]
        yield (seg_id, payload)

    # --- 3. 索引区 ---
    index_size = INDEX_ENTRY_SIZE * seg_count
    if index_size > 0:
        index_region = _read_exact(handle, index_size, "index region")
    else:
        index_region = b""

    # --- 4. trailer ---
    trailer_bytes = _read_exact(handle, TRAILER_SIZE, "trailer")
    index_crc, data_crc = _TRAILER.unpack_from(trailer_bytes, 0)

    # --- 5. 校验 ---
    if compute_crc(index_region) != index_crc:
        raise WSegError("checksum", "the index region does not match its checksum")

    if (running_crc & 0xFFFFFFFF) != data_crc:
        raise WSegError("checksum", "the data region does not match its checksum")

    # 验证索引一致性
    if index_size > 0:
        idx_entries = parse_index(index_region, 0, seg_count)
        expected_offset = HEADER_SIZE
        for i, (off, total_len) in enumerate(idx_entries):
            if off != expected_offset:
                raise WSegError("structure",
                                f"index entry {i}: expected offset {expected_offset}, got {off}")
            expected_offset += total_len
        if expected_offset != index_offset:
            raise WSegError("structure",
                            f"segments end at {expected_offset} but index_offset is {index_offset}")


def read_all(handle) -> list:
    """把结果收成一个列表。"""
    return [item for item in iter_segments(handle)]
