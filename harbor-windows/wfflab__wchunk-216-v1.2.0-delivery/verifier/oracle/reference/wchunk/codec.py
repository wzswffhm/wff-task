"""WCHK 容器的 pack / unpack（格式的权威实现）。

文件 = Header(12B) + Records + Footer(6B)

单条记录：
    +--------+--------+-------------+----------------------+
    | tag    | size   | payload     | padding              |
    | u16 LE | u16 LE | size bytes  | 0x00 到 8 字节边界   |
    +--------+--------+-------------+----------------------+

要点（均为草稿写错、本实现为准的地方）：
  * count 与 tag/size 都是**小端**，且是**定长 u16/u32**（不是 uvarint）；
  * 每条记录**占用的字节数必须是 8 的倍数**（payload 之后补 0x00）；
  * 末尾 6 字节 = CRC-32(header+records, 小端 u32) + tag_sum(u16 LE)；
    CRC 覆盖**文件头与全部记录**（不含 footer 自身）。

校验顺序（错误分类判据依赖，不得调整）：
    长度 -> magic -> version -> 结构解析(含截断) -> CRC -> tag_sum
"""

from __future__ import annotations

import struct

from .crc import compute_crc
from .errors import WChunkError
from .header import HEADER_SIZE, MAGIC, VERSION, build_header, parse_header

FOOTER_SIZE = 6
RECORD_ALIGN = 8
RECORD_PREFIX = 4  # tag u16 + size u16


def _align_up(value: int, boundary: int = RECORD_ALIGN) -> int:
    return ((value + boundary - 1) // boundary) * boundary


def pack(records) -> bytes:
    """把 [(tag, payload), ...] 序列化为 WCHK 字节串。"""
    items = []
    for tag, payload in records:
        if not isinstance(tag, int) or tag < 0 or tag > 0xFFFF:
            raise WChunkError("structure", f"tag {tag!r} out of u16 range")
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise WChunkError("structure", f"payload {type(payload).__name__} is not bytes")
        payload = bytes(payload)
        if len(payload) > 0xFFFF:
            raise WChunkError("structure", f"payload of {len(payload)} bytes exceeds u16 size")
        items.append((tag, payload))

    body = bytearray()
    for tag, payload in items:
        record = struct.pack("<HH", tag, len(payload)) + payload
        padded = _align_up(len(record))
        body += record + b"\x00" * (padded - len(record))

    header = build_header(len(items))
    stream = bytes(header) + bytes(body)
    footer = struct.pack("<IH", compute_crc(stream),
                         sum(tag for tag, _ in items) & 0xFFFF)
    return stream + footer


def _iter_body(data: bytes, count: int):
    """按 8 字节对齐逐条切出记录，产出 (tag, payload)。

    边界判断以**文件总长**为界：footer 是否凑得齐由读完 count 条后单独检查，
    这样「截掉 footer 一部分」会被判为 truncated 而不是别的错。
    """
    pos = HEADER_SIZE
    total = len(data)
    for index in range(count):
        if pos + RECORD_PREFIX > total:
            raise WChunkError("truncated", f"record {index} prefix missing")
        tag, size = struct.unpack_from("<HH", data, pos)
        start = pos + RECORD_PREFIX
        end = start + size
        if end > total:
            raise WChunkError("truncated",
                              f"record {index} payload missing ({size} bytes)")
        span = _align_up(RECORD_PREFIX + size)
        if pos + span > total:
            raise WChunkError("structure",
                              f"record {index} padding runs past end of file")
        pos += span
        yield tag, bytes(data[start:end])
    if pos + FOOTER_SIZE > total:
        raise WChunkError("truncated",
                          f"footer needs {FOOTER_SIZE} bytes but only {total - pos} remain")
    if pos + FOOTER_SIZE < total:
        raise WChunkError("structure",
                          f"{count} records end at {pos}, file allows {total - FOOTER_SIZE}")


def unpack(data: bytes) -> list:
    """解析 WCHK 字节串；任何结构/完整性问题都抛 WChunkError。"""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise WChunkError("structure", f"unpack expects bytes, got {type(data).__name__}")
    data = bytes(data)

    # 1) 长度
    if len(data) < HEADER_SIZE + FOOTER_SIZE:
        raise WChunkError("truncated",
                          f"need at least {HEADER_SIZE + FOOTER_SIZE} bytes, got {len(data)}")
    # 2) 魔数  3) 版本（都在头部自校验里，但显式顺序见下）
    _version, count = parse_header(data)   # magic / version / reserved / count

    # 4) 结构解析（含截断判定）
    records = [(tag, payload) for tag, payload in _iter_body(data, count)]

    # 5) CRC（覆盖 header+records）
    body, footer = data[:-FOOTER_SIZE], data[-FOOTER_SIZE:]
    (stored_crc, stored_sum) = struct.unpack("<IH", footer)
    if compute_crc(body) != stored_crc:
        raise WChunkError("checksum", "trailing CRC-32 does not match header+records")

    # 6) tag_sum
    if sum(tag for tag, _ in records) & 0xFFFF != stored_sum:
        raise WChunkError("structure", "footer tag_sum does not match records")
    return records


def verify(data: bytes) -> bool:
    """返回 data 是否是合法 WCHK 容器；**永不抛异常**。"""
    try:
        unpack(data)
        return True
    except WChunkError:
        return False
    except Exception:  # noqa: BLE001 - verify 是防御性入口
        return False
