"""wdl —— 下载文件的归档与来源标记处理。

浏览器或下载器落地的文件在 NTFS 上会带一条 ``Zone.Identifier`` 备用数据流。
归档时必须把它一起带走，发布到内网之前又需要按策略清掉。
"""

from .archive import PORTABLE_STREAMS, archive_tree, copy_file
from .errors import ArchiveError, StreamError, WDLError
from .streams import (
    ZONE_STREAM,
    read_stream,
    remove_stream,
    stream_exists,
    stream_path,
    stream_size,
    write_stream,
)
from .unblock import is_blocked, unblock

__version__ = "1.6.0"

__all__ = [
    "ArchiveError",
    "PORTABLE_STREAMS",
    "StreamError",
    "WDLError",
    "ZONE_STREAM",
    "archive_tree",
    "copy_file",
    "is_blocked",
    "read_stream",
    "remove_stream",
    "stream_exists",
    "stream_path",
    "stream_size",
    "unblock",
    "write_stream",
]
