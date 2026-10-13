"""wlogseg：分段追加日志容器的读写实现。"""

from .codec import pack, unpack, verify
from .crc import compute_crc, crc32_update
from .errors import WSegError
from .stream import iter_segments, read_all

__all__ = [
    "WSegError",
    "compute_crc",
    "crc32_update",
    "iter_segments",
    "pack",
    "read_all",
    "unpack",
    "verify",
]
