"""wfmt：带尾部校验和的长度前缀记录容器。

对外入口：

- :func:`pack` / :func:`unpack`  —— 整份容器的读写
- :func:`verify`                —— 结构与完整性检查
- :func:`iter_records`          —— 流式读取
"""

from __future__ import annotations

from .codec import ALIGN, decode_record, encode_record, pack, unpack, verify
from .crc import CRC_SIZE, compute_crc
from .errors import WFormatError
from .header import HEADER_SIZE, MAGIC, VERSION, pack_header, parse_header
from .stream import CHUNK_SIZE, iter_records, read_all
from .varint import decode_uvarint, encode_uvarint

__all__ = [
    "WFormatError",
    "MAGIC",
    "VERSION",
    "HEADER_SIZE",
    "CRC_SIZE",
    "CHUNK_SIZE",
    "ALIGN",
    "pack",
    "unpack",
    "verify",
    "iter_records",
    "read_all",
    "encode_record",
    "decode_record",
    "encode_uvarint",
    "decode_uvarint",
    "compute_crc",
    "pack_header",
    "parse_header",
]
