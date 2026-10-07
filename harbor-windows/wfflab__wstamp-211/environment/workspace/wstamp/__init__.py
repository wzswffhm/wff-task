"""wstamp —— 带 Windows 语义的文件时间戳与属性工具库。"""

from .errors import WStampError
from .stamps import snapshot_times, stamp_file
from .copier import copy_stamp
from .sync import SyncReport, sync_tree

__all__ = [
    "WStampError",
    "snapshot_times",
    "stamp_file",
    "copy_stamp",
    "SyncReport",
    "sync_tree",
]
