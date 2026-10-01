"""wsafename —— 面向 Windows 的文件名净化与落盘工具。

上传服务收到用户提交的名称后，先用 :func:`~wsafename.sanitize.sanitize`
把它转换成安全名称，再通过 :class:`~wsafename.store.FileStore` 落盘。
"""

from .errors import (
    CollisionError,
    InvalidNameError,
    NameTooLongError,
    WSafeNameError,
)
from .rules import (
    ILLEGAL_CHARS,
    MAX_SEGMENT_LENGTH,
    RESERVED_BASE_NAMES,
    has_illegal_chars,
    is_reserved,
    is_valid,
)
from .sanitize import REPLACEMENT, sanitize
from .store import FileStore

__version__ = "2.1.0"

__all__ = [
    "CollisionError",
    "FileStore",
    "ILLEGAL_CHARS",
    "InvalidNameError",
    "MAX_SEGMENT_LENGTH",
    "NameTooLongError",
    "REPLACEMENT",
    "RESERVED_BASE_NAMES",
    "WSafeNameError",
    "has_illegal_chars",
    "is_reserved",
    "is_valid",
    "sanitize",
]
