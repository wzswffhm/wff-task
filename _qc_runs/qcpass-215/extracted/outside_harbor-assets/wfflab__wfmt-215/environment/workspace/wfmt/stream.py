"""容器的读取入口。"""

from __future__ import annotations

from .codec import decode_record
from .crc import CRC_SIZE
from .errors import WFormatError
from .header import HEADER_SIZE, parse_header

__all__ = ["CHUNK_SIZE", "iter_records", "read_all"]

#: 单次从底层文件对象请求的最大字节数。
CHUNK_SIZE = 4096


def iter_records(fileobj):
    """产出容器中的 ``(tag, payload)``。"""
    data = fileobj.read()
    if len(data) < HEADER_SIZE + CRC_SIZE:
        raise ValueError("容器长度不足")
    _version, count = parse_header(data)
    end = len(data) - CRC_SIZE
    pos = HEADER_SIZE
    for _ in range(count):
        if pos >= end:
            raise ValueError("容器数据提前结束")
        tag, payload, pos = decode_record(data, pos)
        if pos > end:
            raise ValueError("记录越界")
        yield tag, payload


def read_all(fileobj):
    """把读取完整消费，返回 ``[(tag, payload), ...]``。"""
    return list(iter_records(fileobj))
