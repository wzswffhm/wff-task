"""清除文件的「来自互联网」标记。"""

import os

from .streams import ZONE_STREAM, stream_path


def is_blocked(path):
    """``path`` 是否带有来自互联网的标记。"""
    return os.path.isfile(stream_path(path, ZONE_STREAM))


def unblock(path):
    """清除 ``path`` 上的来自互联网标记。

    返回是否真的发生了变化。
    """
    target = stream_path(path, ZONE_STREAM)
    os.remove(target)
    return True
