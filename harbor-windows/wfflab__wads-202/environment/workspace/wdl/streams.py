"""NTFS 备用数据流的读写。

Windows 上每个文件除了主数据之外，还可以挂若干条**备用数据流**
（Alternate Data Stream, ADS）。从浏览器或下载器落地的文件通常会被写入一条
名为 ``Zone.Identifier`` 的流，用来记录它来自哪个区域（互联网、内网等）。
"""

import os

from .errors import StreamError

#: 下载来源标记使用的备用流名。
ZONE_STREAM = "Zone.Identifier"


def stream_path(path, name):
    """返回 ``path`` 上名为 ``name`` 的备用数据流的可访问路径。"""
    return "%s:%s" % (path, name)


def stream_exists(path, name):
    """``path`` 上是否存在名为 ``name`` 的备用数据流。"""
    return os.path.isfile(stream_path(path, name))


def stream_size(path, name):
    """返回备用数据流的字节数；流不存在时返回 ``0``。"""
    if not stream_exists(path, name):
        return 0
    return os.path.getsize(path)


def read_stream(path, name):
    """读回备用数据流的内容；流不存在时抛 :class:`StreamError`。"""
    target = stream_path(path, name)
    if not os.path.isfile(target):
        raise StreamError("stream %r not present on %r" % (name, path))
    with open(target, "rb") as fh:
        return fh.read()


def write_stream(path, name, data):
    """写入（或覆盖）一条备用数据流。"""
    with open(stream_path(path, name), "wb") as fh:
        fh.write(bytes(data))


def remove_stream(path, name):
    """删除一条备用数据流；流不存在时返回 ``False``。"""
    target = stream_path(path, name)
    if not os.path.isfile(target):
        return False
    os.remove(target)
    return True
