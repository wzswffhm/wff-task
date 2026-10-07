"""文件时间戳的读取与设置。"""

import os

from .errors import WStampError


def snapshot_times(path):
    """返回路径的时间戳快照。

    返回 dict：

    - ``mtime_ns``：修改时间（整数纳秒）。
    - ``atime_ns``：访问时间（整数纳秒）。
    - ``created``：文件创建时间。Windows 上 ``st_ctime`` 就是创建时间
      （birth time），这一点与 Linux（ctime = 元数据变更时间）不同。
    """
    st = os.stat(path)
    return {
        "mtime_ns": st.st_mtime_ns,
        "atime_ns": st.st_atime_ns,
        "created": st.st_ctime,
    }


def stamp_file(path, mtime_ns):
    """把 ``path`` 的 mtime 精确设置为整数纳秒 ``mtime_ns``。

    注意：NTFS 以 100ns 为存储粒度，因此 ``mtime_ns`` 应当是 100 的倍数，
    否则会被截断。
    """
    # 直接把 (atime, mtime) 都设成目标值。
    os.utime(path, ns=(mtime_ns, mtime_ns))
