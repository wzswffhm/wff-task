"""wlogseg：分段追加日志容器的参考实现（verifier 侧，永不进入 agent 环境）。"""

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
