"""把文件归档到目标目录。"""

import os
import shutil

from .streams import ZONE_STREAM, read_stream, stream_exists, write_stream

#: 归档时需要一并带走的备用数据流。
PORTABLE_STREAMS = (ZONE_STREAM,)


def copy_file(src, dst):
    """把 ``src`` 复制到 ``dst``，返回 ``dst``。

    目标目录不存在时会被创建。
    """
    parent = os.path.dirname(os.path.abspath(dst))
    os.makedirs(parent, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def archive_tree(src_root, dst_root):
    """把 ``src_root`` 下的普通文件归档到 ``dst_root``。

    返回已归档文件相对 ``src_root`` 的路径列表（升序）。
    """
    done = []
    for dirpath, _dirnames, filenames in os.walk(src_root):
        for fname in filenames:
            src = os.path.join(dirpath, fname)
            rel = os.path.relpath(src, src_root)
            copy_file(src, os.path.join(dst_root, rel))
            done.append(rel)
    return sorted(done)
